from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from research_agent.config import load_settings
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools import build_tool_registry
from research_agent.tools.base import BaseToolAdapter


WEB_DIR = Path(__file__).resolve().parent / "web"
ARTIFACT_DIR = Path("artifacts").resolve()


class SessionCreateRequest(BaseModel):
    template: str | None = None


class SessionCreateResponse(BaseModel):
    session_id: str
    template: str


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)
    template: str | None = None


class TaskStatus(BaseModel):
    task_id: str
    title: str
    status: str


class ChatResponse(BaseModel):
    kind: str
    assistant_message: str
    run_id: str | None = None
    questions: list[str] = Field(default_factory=list)
    critic_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    section_confidence: dict[str, float] = Field(default_factory=dict)
    task_statuses: list[TaskStatus] = Field(default_factory=list)
    artifact_urls: dict[str, str] = Field(default_factory=dict)


@dataclass
class ChatSession:
    session_id: str
    template: str
    original_topic: str = ""
    awaiting_clarification: bool = False
    pending_questions: list[str] = field(default_factory=list)
    clarification_answers: list[str] = field(default_factory=list)


def _compose_refined_topic(topic: str, questions: list[str], answers: list[str]) -> str:
    if not questions or not answers:
        return topic

    qa_pairs: list[str] = []
    for question, answer in zip(questions, answers):
        qa_pairs.append(f"Q: {question}\nA: {answer}")

    if not qa_pairs:
        return topic

    return topic + "\n\nClarification context:\n" + "\n\n".join(qa_pairs)


def _build_result_message(state: WorkflowState) -> str:
    completed = sum(1 for task in state.tasks if task.status == "complete")
    total = len(state.tasks)
    return (
        f"Run completed for topic: {state.topic}\n"
        f"Completed tasks: {completed}/{total}\n"
        f"Template: {state.template}\n"
        f"Artifacts: {state.artifact_dir}"
    )


def create_app(
    *,
    graph_runner=run_graph,
    registry: dict[str, BaseToolAdapter] | None = None,
) -> FastAPI:
    settings = load_settings()
    tool_registry = build_tool_registry(settings) if registry is None else registry

    sessions: dict[str, ChatSession] = {}

    app = FastAPI(title="Research Agent Web")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    app.mount("/artifacts", StaticFiles(directory=ARTIFACT_DIR), name="artifacts")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/session", response_model=SessionCreateResponse)
    def create_session(request: SessionCreateRequest) -> SessionCreateResponse:
        template = request.template or settings.output.default_template
        if template not in settings.output.supported_templates:
            raise HTTPException(status_code=400, detail="Unsupported template")

        session_id = f"sess-{uuid.uuid4().hex[:10]}"
        sessions[session_id] = ChatSession(session_id=session_id, template=template)
        return SessionCreateResponse(session_id=session_id, template=template)

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        session = sessions.get(request.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        message = request.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        template = request.template or session.template
        session.template = template

        if session.awaiting_clarification:
            session.clarification_answers.append(message)
            topic = _compose_refined_topic(
                session.original_topic,
                session.pending_questions,
                session.clarification_answers,
            )
        else:
            session.original_topic = message
            session.pending_questions = []
            session.clarification_answers = []
            topic = message

        state = WorkflowState(
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            topic=topic,
            template=template,
            artifact_root=str(ARTIFACT_DIR),
        )
        updated = graph_runner(state, registry=tool_registry)

        if updated.phase == "awaiting_user_clarification":
            session.awaiting_clarification = True
            session.pending_questions = list(updated.clarification_questions)
            return ChatResponse(
                kind="clarification",
                assistant_message="I need a few details before I run deep research.",
                run_id=updated.run_id,
                questions=session.pending_questions,
            )

        session.awaiting_clarification = False
        session.pending_questions = []
        session.clarification_answers = []

        artifact_urls = {
            "main_tex": f"/artifacts/{updated.run_id}/main.tex",
            "references_bib": f"/artifacts/{updated.run_id}/references.bib",
            "compile_instructions": f"/artifacts/{updated.run_id}/compile_instructions.md",
            "summary": f"/artifacts/{updated.run_id}/summary.json",
        }

        return ChatResponse(
            kind="result",
            assistant_message=_build_result_message(updated),
            run_id=updated.run_id,
            critic_notes=updated.critic_notes,
            warnings=updated.run_warnings,
            section_confidence=updated.section_confidence,
            task_statuses=[
                TaskStatus(task_id=task.task_id, title=task.title, status=task.status)
                for task in updated.tasks
            ],
            artifact_urls=artifact_urls,
        )

    return app


app = create_app()

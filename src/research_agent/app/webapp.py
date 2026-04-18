from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import html
import json
import os
from pathlib import Path
import uuid
import zipfile

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from research_agent.config import load_settings
from research_agent.models import nvidia_stream_callback
from research_agent.observability import progress_callback
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools import build_tool_registry
from research_agent.tools.base import BaseToolAdapter


WEB_DIR = Path(__file__).resolve().parent / "web"
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_ROOT", ".runtime/artifacts")).resolve()
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


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


class AgentActivity(BaseModel):
    name: str
    status: str
    detail: str = ""


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
    agent_activity: list[AgentActivity] = Field(default_factory=list)
    latex_text: str = ""
    doc_preview_html: str = ""
    overleaf_urls: dict[str, str] = Field(default_factory=dict)


@dataclass
class ChatSession:
    session_id: str
    template: str
    original_topic: str = ""
    awaiting_clarification: bool = False
    pending_questions: list[str] = field(default_factory=list)
    clarification_answers: list[str] = field(default_factory=list)


def _compose_refined_topic(topic: str, questions: list[str], answers: list[str]) -> str:
    if not answers:
        return topic

    context_parts: list[str] = []
    # If we have questions, try to pair them, but don't lose answers if counts mismatch
    for i, answer in enumerate(answers):
        if i < len(questions):
            context_parts.append(f"Q: {questions[i]}\nA: {answer}")
        else:
            context_parts.append(f"A: {answer}")

    return topic + "\n\nClarification context:\n" + "\n\n".join(context_parts)


def _build_result_message(state: WorkflowState) -> str:
    completed = sum(1 for task in state.tasks if task.status == "complete")
    total = len(state.tasks)
    return (
        f"Run completed for topic: {state.topic}\n"
        f"Completed tasks: {completed}/{total}\n"
        f"Template: {state.template}\n"
        f"Artifacts: {state.artifact_dir}"
    )


def _latex_to_doc_html(latex_text: str) -> str:
    if not latex_text.strip():
        return "<p>No LaTeX output generated.</p>"

    lines = latex_text.splitlines()
    in_doc = False
    html_parts: list[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not in_doc:
            if line.startswith("\\begin{document}"):
                in_doc = True
            continue

        if line.startswith("\\end{document}"):
            break
        if not line:
            continue

        if line.startswith("\\section{") and line.endswith("}"):
            title = line[len("\\section{") : -1]
            html_parts.append(f"<h2>{html.escape(title)}</h2>")
            continue

        if line.startswith("\\subsection{") and line.endswith("}"):
            title = line[len("\\subsection{") : -1]
            html_parts.append(f"<h3>{html.escape(title)}</h3>")
            continue

        # Skip template directives and bibliography commands in document preview.
        if line.startswith("\\bibliographystyle") or line.startswith("\\bibliography"):
            continue
        if line.startswith("\\title") or line.startswith("\\author"):
            continue
        if line.startswith("\\maketitle"):
            continue

        cleaned = html.escape(line)
        html_parts.append(f"<p>{cleaned}</p>")

    if not html_parts:
        return "<p>Document preview is not available.</p>"

    return "\n".join(html_parts)


def _create_overleaf_bundle(state: WorkflowState) -> str:
    if not state.artifact_dir:
        return ""

    run_dir = Path(state.artifact_dir)
    if not run_dir.exists():
        return ""

    bundle_path = run_dir / "overleaf_bundle.zip"
    with zipfile.ZipFile(bundle_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename in ["main.tex", "references.bib", "compile_instructions.md"]:
            file_path = run_dir / filename
            if file_path.exists():
                zf.write(file_path, arcname=filename)

    return f"/artifacts/{state.run_id}/overleaf_bundle.zip"


def _build_overleaf_urls(state: WorkflowState) -> dict[str, str]:
    return {
        "new_project": "https://www.overleaf.com/project/new",
        "upload_bundle": _create_overleaf_bundle(state),
    }


def _build_agent_activity(state: WorkflowState) -> list[AgentActivity]:
    activities: list[AgentActivity] = [
        AgentActivity(name="Orchestrator", status="complete", detail="Workflow routed successfully"),
        AgentActivity(name="Planner", status="complete", detail=f"Planned {len(state.tasks)} tasks"),
    ]

    for task in state.tasks:
        activities.append(
            AgentActivity(
                name=f"SubResearch {task.task_id}",
                status=task.status,
                detail=task.title,
            )
        )

    if state.phase == "awaiting_user_clarification":
        activities.append(
            AgentActivity(
                name="Clarifier",
                status="waiting",
                detail="Awaiting user scope details",
            )
        )
        return activities

    activities.extend(
        [
            AgentActivity(name="Critic", status="complete", detail="Confidence scoring done"),
            AgentActivity(name="Combiner", status="complete", detail="Sections synthesized"),
            AgentActivity(name="Citation Verifier", status="complete", detail="References extracted"),
            AgentActivity(name="Composer", status="complete", detail="LaTeX content generated"),
            AgentActivity(name="Exporter", status="complete", detail="Artifacts written"),
        ]
    )
    return activities


def _seed_activity_entries() -> list[dict[str, str]]:
    return [
        {"name": "Orchestrator", "status": "running", "detail": "Preparing pipeline"},
        {"name": "Planner", "status": "pending", "detail": "Building task graph"},
        {"name": "Critic", "status": "pending", "detail": "Confidence scoring"},
        {"name": "Combiner", "status": "pending", "detail": "Section synthesis"},
        {"name": "Citation Verifier", "status": "pending", "detail": "Reference extraction"},
        {"name": "Composer", "status": "pending", "detail": "LaTeX generation"},
        {"name": "Exporter", "status": "pending", "detail": "Artifact export"},
    ]


def _merge_activity_update(
    current: list[dict[str, str]],
    *,
    agent: str,
    status: str,
    detail: str = "",
) -> list[dict[str, str]]:
    updated = [dict(entry) for entry in current]
    for entry in updated:
        if entry.get("name") == agent:
            entry["status"] = status
            if detail:
                entry["detail"] = detail
            return updated

    updated.append({"name": agent, "status": status, "detail": detail})
    return updated


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
                agent_activity=_build_agent_activity(updated),
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

        overleaf_urls = _build_overleaf_urls(updated)

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
            agent_activity=_build_agent_activity(updated),
            latex_text=updated.latex_main,
            doc_preview_html=_latex_to_doc_html(updated.latex_main),
            overleaf_urls=overleaf_urls,
        )

    @app.post("/api/chat/stream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
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

        async def event_generator():
            def emit(event: str, payload: dict) -> str:
                envelope = {"event": event, "payload": payload}
                try:
                    return json.dumps(jsonable_encoder(envelope), ensure_ascii=True) + "\n"
                except Exception:
                    return json.dumps({"event": "error", "payload": {"message": "Encoding error"}}) + "\n"

            event_loop = asyncio.get_running_loop()
            latex_queue: asyncio.Queue[str] = asyncio.Queue()
            progress_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
            activity_entries = _seed_activity_entries()

            def on_latex_chunk(chunk: str) -> None:
                event_loop.call_soon_threadsafe(latex_queue.put_nowait, chunk)

            def on_progress(payload: dict[str, str]) -> None:
                event_loop.call_soon_threadsafe(progress_queue.put_nowait, payload)

            def run_graph_with_stream_hook() -> WorkflowState:
                with progress_callback(on_progress):
                    with nvidia_stream_callback(on_latex_chunk):
                        try:
                            return graph_runner(state, registry=tool_registry)
                        except Exception as e:
                            # Re-raise to be caught by the task handler
                            raise RuntimeError(f"Graph execution failed: {str(e)}") from e

            yield emit(
                "status",
                {
                    "message": "Run accepted",
                    "agent_activity": activity_entries,
                },
            )

            run_task = asyncio.create_task(asyncio.to_thread(run_graph_with_stream_hook))
            streamed_latex = False

            while True:
                # Check for errors in the background task
                if run_task.done():
                    try:
                        # This will raise if the task failed
                        run_task.result()
                    except Exception as e:
                        yield emit("error", {"message": str(e)})
                        return

                if run_task.done() and latex_queue.empty() and progress_queue.empty():
                    break

                # Process all available progress updates at once to stay responsive
                has_updates = False
                while not progress_queue.empty():
                    progress_payload = await progress_queue.get()
                    agent_name = progress_payload.get("agent", "Agent")
                    activity_entries = _merge_activity_update(
                        activity_entries,
                        agent=agent_name,
                        status=progress_payload.get("status", "running"),
                        detail=progress_payload.get("detail", ""),
                    )
                    has_updates = True
                
                if has_updates:
                    yield emit(
                        "status",
                        {
                            "message": "Research in progress",
                            "agent_activity": activity_entries,
                        },
                    )

                try:
                    # Shorter timeout for faster iteration
                    chunk = await asyncio.wait_for(latex_queue.get(), timeout=0.04)
                    if chunk:
                        if not streamed_latex:
                            streamed_latex = True
                            yield emit(
                                "status",
                                {
                                    "message": "Streaming LaTeX generation",
                                    "agent_activity": _merge_activity_update(
                                        activity_entries,
                                        agent="Composer",
                                        status="running",
                                        detail="Receiving model tokens",
                                    ),
                                },
                            )
                        yield emit("latex_chunk", {"chunk": chunk})
                except asyncio.TimeoutError:
                    pass
                
                await asyncio.sleep(0.01)

            updated = await run_task

            if updated.phase == "awaiting_user_clarification":
                session.awaiting_clarification = True
                session.pending_questions = list(updated.clarification_questions)
                clarification = ChatResponse(
                    kind="clarification",
                    assistant_message="I need a few details before I run deep research.",
                    run_id=updated.run_id,
                    questions=session.pending_questions,
                    agent_activity=_build_agent_activity(updated),
                )
                yield emit("clarification", clarification.model_dump())
                return

            session.awaiting_clarification = False
            session.pending_questions = []
            session.clarification_answers = []

            yield emit(
                "status",
                {
                    "message": "Generating LaTeX workbench output",
                    "agent_activity": _build_agent_activity(updated),
                },
            )

            latex_text = updated.latex_main or ""
            if not streamed_latex:
                chunk_size = 120
                for idx in range(0, len(latex_text), chunk_size):
                    yield emit("latex_chunk", {"chunk": latex_text[idx : idx + chunk_size]})
                    await asyncio.sleep(0.01)

            artifact_urls = {
                "main_tex": f"/artifacts/{updated.run_id}/main.tex",
                "references_bib": f"/artifacts/{updated.run_id}/references.bib",
                "compile_instructions": f"/artifacts/{updated.run_id}/compile_instructions.md",
                "summary": f"/artifacts/{updated.run_id}/summary.json",
            }

            result = ChatResponse(
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
                agent_activity=_build_agent_activity(updated),
                latex_text=latex_text,
                doc_preview_html=_latex_to_doc_html(latex_text),
                overleaf_urls=_build_overleaf_urls(updated),
            )
            yield emit("result", result.model_dump())

        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    return app


app = create_app()

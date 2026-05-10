from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import html
import inspect
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid
import zipfile
from typing import Any, Callable

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from research_agent.config import load_settings
from research_agent.models import stream_callback
from research_agent.observability import append_run_event, load_latest_checkpoint, progress_callback, save_checkpoint
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools import build_tool_registry
from research_agent.tools.base import BaseToolAdapter

from research_agent.app.auth import (
    User,
    UserCreate,
    UserRead,
    UserUpdate,
    auth_backend,
    create_db_and_tables,
    current_active_user,
    fastapi_users,
)


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
    language: str | None = None
    depth: str | None = None
    autonomy_mode: str | None = None
    max_runtime_minutes: int | None = None
    max_cost_usd: float | None = None


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
    template: str | None = None
    language: str | None = None
    persona: str | None = None
    questions: list[str] = Field(default_factory=list)
    critic_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    section_confidence: dict[str, float] = Field(default_factory=dict)
    task_statuses: list[TaskStatus] = Field(default_factory=list)
    artifact_urls: dict[str, str] = Field(default_factory=dict)
    agent_activity: list[AgentActivity] = Field(default_factory=list)
    section_evidence: list[dict[str, object]] = Field(default_factory=list)
    latex_text: str = ""
    doc_preview_html: str = ""
    overleaf_urls: dict[str, str] = Field(default_factory=dict)


@dataclass
class ChatSession:
    session_id: str
    user_id: str
    template: str
    original_topic: str = ""
    last_run_id: str = ""
    awaiting_clarification: bool = False
    awaiting_critic_feedback: bool = False
    pending_questions: list[str] = field(default_factory=list)
    clarification_answers: list[str] = field(default_factory=list)


class AsyncRedisSessionStore:
    def __init__(self, url: str):
        self.client = redis.from_url(url, decode_responses=True)
        self.key_prefix = "research_agent:sessions"

    async def get(self, user_id: str, session_id: str) -> ChatSession | None:
        data = await self.client.hgetall(f"{self.key_prefix}:{user_id}:{session_id}")
        if not data:
            return None
        # Convert string representations of lists back to lists
        for list_key in ["pending_questions", "clarification_answers"]:
            if list_key in data and isinstance(data[list_key], str):
                try:
                    data[list_key] = json.loads(data[list_key])
                except Exception:
                    data[list_key] = []
        
        # Boolean conversion
        for bool_key in ["awaiting_clarification", "awaiting_critic_feedback"]:
            if bool_key in data:
                data[bool_key] = data[bool_key] == "True"
            
        return ChatSession(**data)

    async def set(self, session: ChatSession) -> None:
        data = vars(session).copy()
        # Serialize lists to JSON strings for Redis hash
        for list_key in ["pending_questions", "clarification_answers"]:
            data[list_key] = json.dumps(data[list_key])
        
        await self.client.hset(f"{self.key_prefix}:{session.user_id}:{session.session_id}", mapping=data)

    async def delete(self, user_id: str, session_id: str) -> None:
        await self.client.delete(f"{self.key_prefix}:{user_id}:{session_id}")


def _get_session_store_path() -> Path:
    path = Path(os.getenv("CHECKPOINT_ROOT", ".runtime/checkpoints")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path / "sessions.json"


def _load_sessions() -> dict[str, ChatSession]:
    path = _get_session_store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sessions = {}
        for sid, sdata in data.items():
            sessions[sid] = ChatSession(**sdata)
        return sessions
    except Exception as e:
        print(f"Error loading sessions: {e}")
        return {}


def _save_sessions(sessions: dict[str, ChatSession]) -> None:
    path = _get_session_store_path()
    try:
        data = {sid: vars(s) for sid, s in sessions.items()}
        path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error saving sessions: {e}")


class StopResponse(BaseModel):
    ok: bool
    detail: str


def _build_artifact_urls(run_id: str) -> dict[str, str]:
    urls = {
        "main_tex": f"/artifacts/{run_id}/main.tex",
        "references_bib": f"/artifacts/{run_id}/references.bib",
        "compile_instructions": f"/artifacts/{run_id}/compile_instructions.md",
        "summary": f"/artifacts/{run_id}/summary.json",
        "bundle": f"/artifacts/{run_id}/overleaf_bundle.zip",
    }
    
    # Check if PDF exists
    pdf_path = ARTIFACT_DIR / run_id / "main.pdf"
    if pdf_path.exists():
        urls["pdf"] = f"/artifacts/{run_id}/main.pdf"
        
    return urls


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


async def _call_graph_runner(graph_runner, state: WorkflowState, tool_registry: dict[str, BaseToolAdapter]) -> WorkflowState:  # noqa: ANN001
    result = graph_runner(state, registry=tool_registry)
    if inspect.isawaitable(result):
        return await result
    return result


def _build_result_message(state: WorkflowState) -> str:
    completed = sum(1 for task in state.tasks if task.status == "complete")
    total = len(state.tasks)
    return (
        f"Run completed for topic: {state.topic}\n"
        f"Completed tasks: {completed}/{total}\n"
        f"Template: {state.template}\n"
        f"Artifacts: {state.artifact_dir}"
    )


def _build_section_evidence(state: WorkflowState) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    findings = state.task_findings

    for section in state.combined_sections:
        task_id = str(section.get("task_id", "")).strip()
        section_name = str(section.get("heading", "Section"))
        confidence = float(state.section_confidence.get(task_id, 0.0))

        sources: list[str] = []
        for provider_data in findings.get(task_id, {}).values():
            items = provider_data.get("items", [])
            if not isinstance(items, list):
                continue
            for item in items[:3]:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("title") or item.get("url") or "source").strip()
                if label:
                    sources.append(label)

        rows.append(
            {
                "task_id": task_id,
                "section": section_name,
                "confidence": confidence,
                "sources": sources,
            }
        )

    return rows


def _latex_to_doc_html(latex_text: str) -> str:
    if not latex_text.strip():
        return "<p>No LaTeX output generated.</p>"

    lines = latex_text.splitlines()
    html_parts: list[str] = []
    
    # Extract Metadata (Global search)
    title = ""
    author = ""
    
    for line in lines:
        stripped_line = line.strip()
        if "\\title{" in stripped_line:
            match = re.search(r"\\title\{([^}]+)\}", stripped_line)
            if match:
                title = match.group(1)
        elif "\\author{" in stripped_line:
            match = re.search(r"\\author\{([^}]+)\}", stripped_line)
            if match:
                author = match.group(1)
            
    if title:
        html_parts.append(f"<h1 style='text-align: center; color: white;'>{html.escape(title)}</h1>")
    if author:
        html_parts.append(f"<p style='text-align: center; color: #a1a1aa; font-weight: 500;'>{html.escape(author)}</p>")
    
    # Process Body
    in_doc = False
    in_abstract = False
    
    for raw_line in lines:
        line = raw_line.strip()
        if not in_doc:
            if "\\begin{document}" in line:
                in_doc = True
            continue

        if "\\end{document}" in line:
            break
            
        if "\\begin{abstract}" in line:
            in_abstract = True
            html_parts.append("<h2 style='text-transform: uppercase; letter-spacing: 0.1em; color: #8b5cf6;'>Abstract</h2>")
            continue
        if "\\end{abstract}" in line:
            in_abstract = False
            continue
            
        if not line or line.startswith("%"):
            continue

        if "\\section{" in line:
            match = re.search(r"\\section\{([^}]+)\}", line)
            if match:
                html_parts.append(f"<h2 style='color: #f4f4f5; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; margin-top: 32px;'>{html.escape(match.group(1))}</h2>")
                continue

        if "\\subsection{" in line:
            match = re.search(r"\\subsection\{([^}]+)\}", line)
            if match:
                html_parts.append(f"<h3 style='color: #e4e4e7; margin-top: 24px;'>{html.escape(match.group(1))}</h3>")
                continue

        # Skip other commands
        if line.startswith("\\") and not in_abstract:
             # Basic inline citation replacement
             line = re.sub(r"\\cite\{([^}]+)\}", r"[\1]", line)
             if line.startswith("\\"):
                 continue

        cleaned = html.escape(line)
        # Handle some basic LaTeX formatting in HTML
        cleaned = cleaned.replace("\\_", "_").replace("\\&", "&").replace("\\%", "%")
        
        if in_abstract:
            html_parts.append(f"<p style='font-style: italic; color: #d4d4d8; background: rgba(139, 92, 246, 0.05); padding: 12px; border-radius: 8px;'>{cleaned}</p>")
        else:
            html_parts.append(f"<p style='margin-bottom: 16px; line-height: 1.8;'>{cleaned}</p>")

    if not html_parts or (not title and not any("<h2" in p for p in html_parts)):
        return f"<div style='padding: 40px; text-align: center; color: #a1a1aa;'><p>Document preview is being prepared...</p><pre style='text-align: left; font-size: 11px; margin-top: 20px; opacity: 0.5;'>{html.escape(latex_text[:200])}...</pre></div>"

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


async def _execute_research_run(
    *,
    run_id: str,
    session: ChatSession,
    topic: str,
    template: str,
    language: str,
    depth: str,
    autonomy_mode: str,
    max_runtime_minutes: int,
    max_cost_usd: float,
    max_iterations: int,
    graph_runner,
    tool_registry: dict[str, BaseToolAdapter],
    emit_callback: Callable[[str, dict], Any],
    critic_user_feedback: str | None = None,
) -> WorkflowState | None:
    state = WorkflowState(
        run_id=run_id,
        topic=topic,
        template=template,
        language=language,
        depth=depth,
        autonomy_mode=autonomy_mode,
        max_runtime_minutes=max_runtime_minutes,
        max_cost_usd=max_cost_usd,
        max_iterations=max_iterations,
        started_at=time.time(),
        artifact_root=str(ARTIFACT_DIR),
        critic_user_feedback=critic_user_feedback,
    )
    save_checkpoint(state, label="start")

    event_loop = asyncio.get_running_loop()
    latex_queue: asyncio.Queue[str] = asyncio.Queue()
    progress_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
    activity_entries = _seed_activity_entries()

    def on_latex_chunk(chunk: str) -> None:
        event_loop.call_soon_threadsafe(latex_queue.put_nowait, chunk)

    def on_progress(payload: dict[str, str]) -> None:
        event_loop.call_soon_threadsafe(progress_queue.put_nowait, payload)

    async def run_graph_task():
        with progress_callback(on_progress):
            with stream_callback(on_latex_chunk):
                try:
                    return await _call_graph_runner(graph_runner, state, tool_registry)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    raise RuntimeError(f"Graph execution failed: {str(e)}") from e

    await emit_callback(
        "status",
        {
            "message": "Run accepted",
            "agent_activity": activity_entries,
        },
    )

    run_task = asyncio.create_task(run_graph_task())
    streamed_latex = False
    last_heartbeat = time.time()

    while not run_task.done() or not latex_queue.empty() or not progress_queue.empty():
        current_time = time.time()
        
        # Heartbeat
        if current_time - last_heartbeat > 15:
            await emit_callback("ping", {"time": current_time})
            last_heartbeat = current_time

        # Check for updates
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
            await emit_callback(
                "status",
                {
                    "message": "Research in progress",
                    "agent_activity": activity_entries,
                },
            )

        while not latex_queue.empty():
            chunk = await latex_queue.get()
            if chunk:
                if not streamed_latex:
                    streamed_latex = True
                    await emit_callback(
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
                await emit_callback("latex_chunk", {"chunk": chunk})
        
        if run_task.done():
            # Check for exceptions
            try:
                if run_task.exception():
                    await emit_callback("error", {"message": str(run_task.exception())})
                    return None
            except asyncio.CancelledError:
                return None

        await asyncio.sleep(0.05)

    run_error = run_task.exception() if run_task.done() else None
    if run_error:
        await emit_callback("error", {"message": str(run_error)})
        return None

    updated = run_task.result()
    save_checkpoint(updated, label=updated.phase)

    if updated.phase == "awaiting_user_clarification":
        session.awaiting_clarification = True
        session.pending_questions = list(updated.clarification_questions)
        clarification = ChatResponse(
            kind="clarification",
            assistant_message="I need a few details before I run deep research.",
            run_id=updated.run_id,
            template=updated.template,
            language=updated.language,
            persona="planner",
            questions=session.pending_questions,
            agent_activity=_build_agent_activity(updated),
        )
        await emit_callback("clarification", clarification.model_dump())
    elif updated.phase == "await_user_critic":
        session.awaiting_critic_feedback = True
        critic_msg = "The initial findings have low confidence. Please provide guidance to improve the research."
        if updated.critic_notes:
            critic_msg += "\n\n**Critic Notes:**\n" + "\n".join(f"- {n}" for n in updated.critic_notes)
        
        feedback_req = ChatResponse(
            kind="critic_feedback",
            assistant_message=critic_msg,
            run_id=updated.run_id,
            template=updated.template,
            language=updated.language,
            persona="critic",
            critic_notes=updated.critic_notes,
            agent_activity=_build_agent_activity(updated),
        )
        await emit_callback("critic_feedback", feedback_req.model_dump())
    else:
        session.awaiting_clarification = False
        session.awaiting_critic_feedback = False
        session.pending_questions = []
        session.clarification_answers = []

        await emit_callback(
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
                await emit_callback("latex_chunk", {"chunk": latex_text[idx : idx + chunk_size]})
                await asyncio.sleep(0.01)

        artifact_urls = _build_artifact_urls(updated.run_id)

        result = ChatResponse(
            kind="result",
            assistant_message=_build_result_message(updated),
            run_id=updated.run_id,
            template=updated.template,
            language=updated.language,
            persona="critic",
            critic_notes=updated.critic_notes,
            warnings=updated.run_warnings,
            section_confidence=updated.section_confidence,
            task_statuses=[
                TaskStatus(task_id=task.task_id, title=task.title, status=task.status)
                for task in updated.tasks
            ],
            artifact_urls=artifact_urls,
            agent_activity=_build_agent_activity(updated),
            section_evidence=_build_section_evidence(updated),
            latex_text=latex_text,
            doc_preview_html=_latex_to_doc_html(latex_text),
            overleaf_urls=_build_overleaf_urls(updated),
        )
        await emit_callback("result", result.model_dump())
    
    return updated


def create_app(
    *,
    graph_runner=run_graph,
    registry: dict[str, BaseToolAdapter] | None = None,
) -> FastAPI:
    settings = load_settings()
    tool_registry = build_tool_registry(settings) if registry is None else registry

    # Persistence Backend Selection
    session_store = None
    if settings.features.session_persistence == "redis":
        session_store = AsyncRedisSessionStore(settings.redis.url)
    
    # Cache for in-memory fallback
    sessions: dict[str, ChatSession] = _load_sessions()
    session_active_runs: dict[str, str] = {}
    run_interrupt_signals: dict[str, threading.Event] = {}

    app = FastAPI(title="Research Agent Web")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    app.mount("/artifacts", StaticFiles(directory=ARTIFACT_DIR), name="artifacts")

    # AUTH ROUTERS
    app.include_router(
        fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    async def get_session(user_id: str, session_id: str) -> ChatSession | None:
        if session_store:
            return await session_store.get(user_id, session_id)
        # For simple in-memory, we scope by session_id but theoretically should by user_id
        return sessions.get(session_id)

    async def save_session(session: ChatSession) -> None:
        if session_store:
            await session_store.set(session)
        else:
            sessions[session.session_id] = session
            _save_sessions(sessions)

    @app.post("/api/session", response_model=SessionCreateResponse)
    async def create_session(
        request: SessionCreateRequest,
        user: User = Depends(current_active_user)
    ) -> SessionCreateResponse:
        template = request.template or settings.output.default_template
        
        # Robust mapping for legacy/shorthand names
        if template == "ieee":
            template = "ieee-2col"
        
        if template not in settings.output.supported_templates:
            raise HTTPException(status_code=400, detail=f"Unsupported template: {template}")

        session_id = f"sess-{uuid.uuid4().hex[:10]}"
        session = ChatSession(session_id=session_id, user_id=str(user.id), template=template)
        await save_session(session)
        return SessionCreateResponse(session_id=session_id, template=template)

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        user: User = Depends(current_active_user)
    ) -> ChatResponse:
        session = await get_session(str(user.id), request.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        message = request.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        template = request.template or session.template
        session.template = template

        critic_user_feedback = None
        if session.awaiting_critic_feedback:
            critic_user_feedback = message
            topic = session.original_topic # Don't change topic
        elif session.awaiting_clarification:
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

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        interrupt_signal = threading.Event()
        run_interrupt_signals[run_id] = interrupt_signal
        session_active_runs[request.session_id] = run_id
        session.last_run_id = run_id
        await save_session(session)

        runtime_cap = max(1, int(request.max_runtime_minutes or settings.runtime.max_runtime_minutes))
        cost_cap = max(0.0, float(request.max_cost_usd if request.max_cost_usd is not None else settings.runtime.max_cost_usd))
        depth = (request.depth or "balanced").strip().lower()
        autonomy_mode = (request.autonomy_mode or "hybrid").strip().lower()
        max_iterations = max(1, min(settings.runtime.max_iterations, 3))
        if depth == "quick":
            max_iterations = max(1, min(max_iterations, 2))
        elif depth == "deep":
            max_iterations = min(5, max_iterations + 1)

        # Mock emit for sync chat
        async def mock_emit(event, payload): pass

        updated = await _execute_research_run(
            run_id=run_id,
            session=session,
            topic=topic,
            template=template,
            language=request.language or "en",
            depth=depth,
            autonomy_mode=autonomy_mode,
            max_runtime_minutes=runtime_cap,
            max_cost_usd=cost_cap,
            max_iterations=max_iterations,
            graph_runner=graph_runner,
            tool_registry=tool_registry,
            emit_callback=mock_emit,
            critic_user_feedback=critic_user_feedback,
        )
        
        if updated is None:
            raise HTTPException(status_code=500, detail="Graph execution failed")

        run_interrupt_signals.pop(run_id, None)
        if session_active_runs.get(request.session_id) == run_id:
            session_active_runs.pop(request.session_id, None)

        await save_session(session)

        if updated.phase == "awaiting_user_clarification":
            return ChatResponse(
                kind="clarification",
                assistant_message="I need a few details before I run deep research.",
                run_id=updated.run_id,
                template=updated.template,
                language=updated.language,
                persona="planner",
                questions=session.pending_questions,
                agent_activity=_build_agent_activity(updated),
            )
        
        if updated.phase == "await_user_critic":
             return ChatResponse(
                kind="critic_feedback",
                assistant_message="Confidence is low. Please guide the next steps.",
                run_id=updated.run_id,
                template=updated.template,
                language=updated.language,
                persona="critic",
                critic_notes=updated.critic_notes,
                agent_activity=_build_agent_activity(updated),
            )

        artifact_urls = _build_artifact_urls(updated.run_id)
        overleaf_urls = _build_overleaf_urls(updated)

        return ChatResponse(
            kind="result",
            assistant_message=_build_result_message(updated),
            run_id=updated.run_id,
            template=updated.template,
            language=updated.language,
            persona="critic",
            critic_notes=updated.critic_notes,
            warnings=updated.run_warnings,
            section_confidence=updated.section_confidence,
            task_statuses=[
                TaskStatus(task_id=task.task_id, title=task.title, status=task.status)
                for task in updated.tasks
            ],
            artifact_urls=artifact_urls,
            agent_activity=_build_agent_activity(updated),
            section_evidence=_build_section_evidence(updated),
            latex_text=updated.latex_main,
            doc_preview_html=_latex_to_doc_html(updated.latex_main),
            overleaf_urls=overleaf_urls,
        )

    @app.post("/api/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        user: User = Depends(current_active_user)
    ) -> StreamingResponse:
        session = await get_session(str(user.id), request.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        message = request.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        template = request.template or session.template
        session.template = template

        critic_user_feedback = None
        if session.awaiting_critic_feedback:
            critic_user_feedback = message
            topic = session.original_topic
        elif session.awaiting_clarification:
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

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        interrupt_signal = threading.Event()
        run_interrupt_signals[run_id] = interrupt_signal
        session_active_runs[request.session_id] = run_id
        session.last_run_id = run_id
        await save_session(session)

        runtime_cap = max(1, int(request.max_runtime_minutes or settings.runtime.max_runtime_minutes))
        cost_cap = max(0.0, float(request.max_cost_usd if request.max_cost_usd is not None else settings.runtime.max_cost_usd))
        depth = (request.depth or "balanced").strip().lower()
        autonomy_mode = (request.autonomy_mode or "hybrid").strip().lower()
        max_iterations = max(1, min(settings.runtime.max_iterations, 3))
        if depth == "quick":
            max_iterations = max(1, min(max_iterations, 2))
        elif depth == "deep":
            max_iterations = min(5, max_iterations + 1)

        async def event_generator():
            queue = asyncio.Queue()
            
            async def emit(event: str, payload: dict):
                append_run_event(run_id=run_id, event=event, payload=payload)
                await queue.put(json.dumps(jsonable_encoder({"event": event, "payload": payload}), ensure_ascii=True) + "\n")

            run_task = asyncio.create_task(_execute_research_run(
                run_id=run_id,
                session=session,
                topic=topic,
                template=template,
                language=request.language or "en",
                depth=depth,
                autonomy_mode=autonomy_mode,
                max_runtime_minutes=runtime_cap,
                max_cost_usd=cost_cap,
                max_iterations=max_iterations,
                graph_runner=graph_runner,
                tool_registry=tool_registry,
                emit_callback=emit,
                critic_user_feedback=critic_user_feedback
            ))

            try:
                while not run_task.done() or not queue.empty():
                    try:
                        yield await asyncio.wait_for(queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                
                if run_task.result():
                    await save_session(session)
            except Exception as e:
                yield json.dumps({"event": "error", "payload": {"message": str(e)}}) + "\n"
            finally:
                run_interrupt_signals.pop(run_id, None)
                if session_active_runs.get(request.session_id) == run_id:
                    session_active_runs.pop(request.session_id, None)

        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    @app.websocket("/ws/chat/{session_id}")
    async def chat_websocket(
        websocket: WebSocket,
        session_id: str,
        token: str | None = None
    ):
        await websocket.accept()
        # Simple token verification for WS
        from research_agent.app.auth import get_jwt_strategy
        strategy = get_jwt_strategy()
        user = await strategy.read_token(token, fastapi_users.get_user_manager)
        if not user or not user.is_active:
             await websocket.send_json({"event": "error", "payload": {"message": "Unauthorized"}})
             await websocket.close()
             return

        session = await get_session(str(user.id), session_id)
        if not session:
            await websocket.send_json({"event": "error", "payload": {"message": "Session not found"}})
            await websocket.close()
            return

        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                if action == "chat":
                    message = data.get("message", "").strip()
                    if not message:
                        await websocket.send_json({"event": "error", "payload": {"message": "Empty message"}})
                        continue

                    template = data.get("template") or session.template
                    session.template = template
                    language = data.get("language") or "en"

                    critic_user_feedback = None
                    if session.awaiting_critic_feedback:
                        critic_user_feedback = message
                        topic = session.original_topic
                    elif session.awaiting_clarification:
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

                    run_id = f"run-{uuid.uuid4().hex[:8]}"
                    interrupt_signal = threading.Event()
                    run_interrupt_signals[run_id] = interrupt_signal
                    session_active_runs[session_id] = run_id
                    session.last_run_id = run_id
                    await save_session(session)

                    runtime_cap = max(1, int(data.get("max_runtime_minutes") or settings.runtime.max_runtime_minutes))
                    cost_cap = max(0.0, float(data.get("max_cost_usd") if data.get("max_cost_usd") is not None else settings.runtime.max_cost_usd))
                    depth = (data.get("depth") or "balanced").strip().lower()
                    autonomy_mode = (data.get("autonomy_mode") or "hybrid").strip().lower()
                    max_iterations = max(1, min(settings.runtime.max_iterations, 3))
                    
                    async def emit_ws(event: str, payload: dict):
                        append_run_event(run_id=run_id, event=event, payload=payload)
                        await websocket.send_json({"event": event, "payload": payload})

                    try:
                        updated = await _execute_research_run(
                            run_id=run_id,
                            session=session,
                            topic=topic,
                            template=template,
                            language=language,
                            depth=depth,
                            autonomy_mode=autonomy_mode,
                            max_runtime_minutes=runtime_cap,
                            max_cost_usd=cost_cap,
                            max_iterations=max_iterations,
                            graph_runner=graph_runner,
                            tool_registry=tool_registry,
                            emit_callback=emit_ws,
                            critic_user_feedback=critic_user_feedback
                        )
                        if updated:
                            await save_session(session)
                    finally:
                        run_interrupt_signals.pop(run_id, None)
                        if session_active_runs.get(session_id) == run_id:
                            session_active_runs.pop(session_id, None)

                elif action == "stop":
                    await stop_session_run(session_id, user)
                    await websocket.send_json({"event": "status", "payload": {"message": "Stop requested"}})
                
        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await websocket.send_json({"event": "error", "payload": {"message": str(e)}})
            except Exception:
                pass
            await websocket.close()

    @app.post("/api/session/{session_id}/stop", response_model=StopResponse)
    async def stop_session_run(
        session_id: str,
        user: User = Depends(current_active_user)
    ) -> StopResponse:
        run_id = session_active_runs.get(session_id)
        if not run_id:
            return StopResponse(ok=False, detail="No active run for session")

        signal = run_interrupt_signals.get(run_id)
        if signal is None:
            return StopResponse(ok=False, detail="Run signal not found")

        signal.set()
        return StopResponse(ok=True, detail=f"Stop requested for {run_id}")

    @app.post("/api/session/{session_id}/resume", response_model=ChatResponse)
    async def resume_session_run(
        session_id: str,
        user: User = Depends(current_active_user)
    ) -> ChatResponse:
        session = await get_session(str(user.id), session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        run_id = session.last_run_id
        if not run_id:
            raise HTTPException(status_code=404, detail="No run available for resume")

        restored = load_latest_checkpoint(run_id)
        if restored is None:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        if restored.phase == "awaiting_user_clarification":
            session.awaiting_clarification = True
            session.pending_questions = list(restored.clarification_questions)
            return ChatResponse(
                kind="clarification",
                assistant_message="I need a few details before I run deep research.",
                run_id=restored.run_id,
                template=restored.template,
                language=restored.language,
                persona="planner",
                questions=session.pending_questions,
                agent_activity=_build_agent_activity(restored),
            )
        
        if restored.phase == "await_user_critic":
             session.awaiting_critic_feedback = True
             return ChatResponse(
                kind="critic_feedback",
                assistant_message="Confidence is low. Please guide the next steps.",
                run_id=restored.run_id,
                template=restored.template,
                language=restored.language,
                persona="critic",
                critic_notes=restored.critic_notes,
                agent_activity=_build_agent_activity(restored),
            )

        artifact_urls = _build_artifact_urls(restored.run_id)
        return ChatResponse(
            kind="result",
            assistant_message=_build_result_message(restored),
            run_id=restored.run_id,
            template=restored.template,
            language=restored.language,
            persona="critic",
            critic_notes=restored.critic_notes,
            warnings=restored.run_warnings,
            section_confidence=restored.section_confidence,
            task_statuses=[
                TaskStatus(task_id=task.task_id, title=task.title, status=task.status)
                for task in restored.tasks
            ],
            artifact_urls=artifact_urls,
            agent_activity=_build_agent_activity(restored),
            section_evidence=_build_section_evidence(restored),
            latex_text=restored.latex_main,
            doc_preview_html=_latex_to_doc_html(restored.latex_main),
            overleaf_urls=_build_overleaf_urls(restored),
        )

    return app


app = create_app()

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

from fastapi import FastAPI, HTTPException
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
    template: str
    original_topic: str = ""
    awaiting_clarification: bool = False
    pending_questions: list[str] = field(default_factory=list)
    clarification_answers: list[str] = field(default_factory=list)


class StopResponse(BaseModel):
    ok: bool
    detail: str


def _build_artifact_urls(run_id: str) -> dict[str, str]:
    return {
        "main_tex": f"/artifacts/{run_id}/main.tex",
        "references_bib": f"/artifacts/{run_id}/references.bib",
        "compile_instructions": f"/artifacts/{run_id}/compile_instructions.md",
        "summary": f"/artifacts/{run_id}/summary.json",
    }


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


def create_app(
    *,
    graph_runner=run_graph,
    registry: dict[str, BaseToolAdapter] | None = None,
) -> FastAPI:
    settings = load_settings()
    tool_registry = build_tool_registry(settings) if registry is None else registry

    sessions: dict[str, ChatSession] = {}
    session_active_runs: dict[str, str] = {}
    session_last_run: dict[str, str] = {}
    run_interrupt_signals: dict[str, threading.Event] = {}

    app = FastAPI(title="Research Agent Web")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    app.mount("/artifacts", StaticFiles(directory=ARTIFACT_DIR), name="artifacts")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/session", response_model=SessionCreateResponse)
    async def create_session(request: SessionCreateRequest) -> SessionCreateResponse:
        template = request.template or settings.output.default_template
        
        # Robust mapping for legacy/shorthand names
        if template == "ieee":
            template = "ieee-2col"
        
        if template not in settings.output.supported_templates:
            raise HTTPException(status_code=400, detail=f"Unsupported template: {template}")

        session_id = f"sess-{uuid.uuid4().hex[:10]}"
        sessions[session_id] = ChatSession(session_id=session_id, template=template)
        return SessionCreateResponse(session_id=session_id, template=template)

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
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

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        interrupt_signal = threading.Event()
        run_interrupt_signals[run_id] = interrupt_signal
        session_active_runs[request.session_id] = run_id
        session_last_run[request.session_id] = run_id

        runtime_cap = request.max_runtime_minutes or settings.runtime.max_runtime_minutes
        cost_cap = request.max_cost_usd if request.max_cost_usd is not None else settings.runtime.max_cost_usd
        depth = (request.depth or "balanced").strip().lower()
        autonomy_mode = (request.autonomy_mode or "hybrid").strip().lower()
        max_iterations = max(1, min(settings.runtime.max_iterations, 3))
        if depth == "quick":
            max_iterations = max(1, min(max_iterations, 2))
        elif depth == "deep":
            max_iterations = min(5, max_iterations + 1)

        state = WorkflowState(
            run_id=run_id,
            topic=topic,
            template=template,
            depth=depth,
            autonomy_mode=autonomy_mode,
            max_runtime_minutes=max(1, int(runtime_cap)),
            max_cost_usd=max(0.0, float(cost_cap)),
            max_iterations=max_iterations,
            started_at=time.time(),
            artifact_root=str(ARTIFACT_DIR),
        )
        save_checkpoint(state, label="start")
        try:
            updated = await _call_graph_runner(graph_runner, state, tool_registry)
        finally:
            run_interrupt_signals.pop(run_id, None)
            if session_active_runs.get(request.session_id) == run_id:
                session_active_runs.pop(request.session_id, None)

        save_checkpoint(updated, label=updated.phase)

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

        artifact_urls = _build_artifact_urls(updated.run_id)

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
            section_evidence=_build_section_evidence(updated),
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

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        interrupt_signal = threading.Event()
        run_interrupt_signals[run_id] = interrupt_signal
        session_active_runs[request.session_id] = run_id
        session_last_run[request.session_id] = run_id

        runtime_cap = request.max_runtime_minutes or settings.runtime.max_runtime_minutes
        cost_cap = request.max_cost_usd if request.max_cost_usd is not None else settings.runtime.max_cost_usd
        depth = (request.depth or "balanced").strip().lower()
        autonomy_mode = (request.autonomy_mode or "hybrid").strip().lower()
        max_iterations = max(1, min(settings.runtime.max_iterations, 3))
        if depth == "quick":
            max_iterations = max(1, min(max_iterations, 2))
        elif depth == "deep":
            max_iterations = min(5, max_iterations + 1)

        state = WorkflowState(
            run_id=run_id,
            topic=topic,
            template=template,
            depth=depth,
            autonomy_mode=autonomy_mode,
            max_runtime_minutes=max(1, int(runtime_cap)),
            max_cost_usd=max(0.0, float(cost_cap)),
            max_iterations=max_iterations,
            started_at=time.time(),
            artifact_root=str(ARTIFACT_DIR),
        )
        save_checkpoint(state, label="start")

        async def event_generator():
            def emit(event: str, payload: dict) -> str:
                envelope = {"event": event, "payload": payload}
                append_run_event(run_id=run_id, event=event, payload=payload)
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

            async def run_graph_task():
                with progress_callback(on_progress):
                    with stream_callback(on_latex_chunk):
                        try:
                            return await _call_graph_runner(graph_runner, state, tool_registry)
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            raise RuntimeError(f"Graph execution failed: {str(e)}") from e

            try:
                yield emit(
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
                        yield emit("ping", {"time": current_time})
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
                        yield emit(
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
                    
                    if run_task.done():
                        # Check for exceptions
                        try:
                            if run_task.exception():
                                yield emit("error", {"message": str(run_task.exception())})
                                break
                        except asyncio.CancelledError:
                            break

                    await asyncio.sleep(0.05)

                run_error = run_task.exception() if run_task.done() else None
                if run_error:
                    yield emit("error", {"message": str(run_error)})
                    return

                if run_task.done():
                    updated = run_task.result()
                    save_checkpoint(updated, label=updated.phase)

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
                    else:
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

                        artifact_urls = _build_artifact_urls(updated.run_id)

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
                            section_evidence=_build_section_evidence(updated),
                            latex_text=latex_text,
                            doc_preview_html=_latex_to_doc_html(latex_text),
                            overleaf_urls=_build_overleaf_urls(updated),
                        )
                        yield emit("result", result.model_dump())
            except Exception as outer_e:
                import traceback
                traceback.print_exc()
                yield emit("error", {"message": f"Critical stream error: {str(outer_e)}"})
            finally:
                run_interrupt_signals.pop(run_id, None)
                if session_active_runs.get(request.session_id) == run_id:
                    session_active_runs.pop(request.session_id, None)

        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    @app.post("/api/session/{session_id}/stop", response_model=StopResponse)
    async def stop_session_run(session_id: str) -> StopResponse:
        run_id = session_active_runs.get(session_id)
        if not run_id:
            return StopResponse(ok=False, detail="No active run for session")

        signal = run_interrupt_signals.get(run_id)
        if signal is None:
            return StopResponse(ok=False, detail="Run signal not found")

        signal.set()
        return StopResponse(ok=True, detail=f"Stop requested for {run_id}")

    @app.post("/api/session/{session_id}/resume", response_model=ChatResponse)
    async def resume_session_run(session_id: str) -> ChatResponse:
        session = sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        run_id = session_last_run.get(session_id)
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
                questions=session.pending_questions,
                agent_activity=_build_agent_activity(restored),
            )

        artifact_urls = _build_artifact_urls(restored.run_id)
        return ChatResponse(
            kind="result",
            assistant_message=_build_result_message(restored),
            run_id=restored.run_id,
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

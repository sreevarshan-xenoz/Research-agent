from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import threading
import uuid
from typing import Any, Dict, List

from contextlib import asynccontextmanager

from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import logging
import shutil

from research_agent.app.auth import (
    User,
    UserCreate,
    UserRead,
    current_active_user,
    fastapi_users,
    auth_backend,
)
from research_agent.config import load_settings, validate_insecure_defaults
from research_agent.output.grant_proposal import generate_grant_proposal
from research_agent.observability.checkpoints import (
    append_run_event,
    load_latest_checkpoint,
    _event_root,
)
from research_agent.observability.logging import ErrorSeverity, log_error
from research_agent.orchestration.graph import close_redis_pool, get_memory_diagnostics, get_redis_pool, run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools.cache import close_global_tool_cache
from research_agent.tools.registry import build_tool_registry


logger = logging.getLogger(__name__)


@dataclass
class ChatSession:
    session_id: str
    user_id: str
    original_topic: str = ""
    template: str = "ieee"
    pending_questions: List[str] = field(default_factory=list)
    clarification_answers: List[str] = field(default_factory=list)
    awaiting_clarification: bool = False
    awaiting_critic_feedback: bool = False
    last_run_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def _get_session_store_path() -> Path:
    path = Path(".runtime/sessions.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_sessions() -> dict[str, ChatSession]:
    path = _get_session_store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {sid: ChatSession(**s) for sid, s in data.items()}
    except Exception as exc:
        log_error(
            "Failed to load sessions",
            severity=ErrorSeverity.RECOVERABLE,
            component="webapp",
            detail=f"{type(exc).__name__}: {exc}",
        )
        return {}


def _save_sessions(sessions: dict[str, ChatSession]) -> None:
    path = _get_session_store_path()
    try:
        data = {sid: vars(s) for sid, s in sessions.items()}
        path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception as exc:
        log_error(
            "Failed to save sessions",
            severity=ErrorSeverity.RECOVERABLE,
            component="webapp",
            detail=f"{type(exc).__name__}: {exc}",
        )


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        await self.broadcast(session_id, "presence", {"message": "User joined", "active_users": len(self.active_connections[session_id])})

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast(self, session_id: str, event: str, payload: dict):
        if session_id in self.active_connections:
            message = {"event": event, "payload": payload}
            dead_connections = []
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(message)
                except Exception as exc:
                    log_error(
                        "WebSocket broadcast failed for one connection",
                        severity=ErrorSeverity.RECOVERABLE,
                        component="webapp",
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                    dead_connections.append(connection)
            for dead in dead_connections:
                self.disconnect(dead, session_id)


class GrantProposalRequest(BaseModel):
    title: str
    pi_name: str
    pi_institution: str
    abstract: str
    agency: str = "nsf"


class StopResponse(BaseModel):
    success: bool
    message: str


def create_app(
    static_dir: str = "src/research_agent/app/web",
    artifact_root: str = ".runtime/artifacts",
    graph_runner=None,
    registry: dict[str, Any] | None = None,
):
    settings = load_settings()
    validate_insecure_defaults(settings)
    sessions: dict[str, ChatSession] = _load_sessions()
    session_active_runs: dict[str, str] = {}
    run_interrupt_signals: dict[str, threading.Event] = {}
    CHAT_LIBRARIES: dict[str, list[dict[str, Any]]] = {}
    manager = ConnectionManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: start background watchdog scheduler
        watchdog_task = None
        if settings.features.research_watchdog:
            try:
                from research_agent.orchestration.watchdog import start_watchdog_scheduler
                watchdog_task = await start_watchdog_scheduler(tool_registry)
                logger.info("Watchdog scheduler started (interval: 3600s)")
            except Exception as exc:
                logger.warning("Could not start watchdog scheduler: %s", exc)

        yield

        # Shutdown: stop watchdog scheduler
        if watchdog_task is not None:
            try:
                from research_agent.orchestration.watchdog import stop_watchdog_scheduler
                await stop_watchdog_scheduler()
                logger.info("Watchdog scheduler stopped")
            except Exception as exc:
                logger.warning("Error stopping watchdog scheduler: %s", exc)

        # Shutdown: close Redis connections gracefully
        await close_redis_pool()
        await close_global_tool_cache()

    app = FastAPI(title="Research Agent Web", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth routes
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/api/auth/jwt",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth",
        tags=["auth"],
    )

    tool_registry = registry if registry is not None else build_tool_registry(settings)

    async def get_session(user_id: str, session_id: str) -> ChatSession | None:
        if session_id in sessions:
            s = sessions[session_id]
            if s.user_id == user_id:
                return s
        return None

    async def save_session(session: ChatSession):
        sessions[session.session_id] = session
        _save_sessions(sessions)

    @app.get("/api/sessions")
    async def list_sessions(user: User = Depends(current_active_user)):
        user_sessions = [
            {"session_id": s.session_id, "topic": s.original_topic, "last_run_id": s.last_run_id}
            for s in sessions.values()
            if s.user_id == str(user.id)
        ]
        return {"sessions": user_sessions}

    @app.post("/api/sessions")
    async def create_session(user: User = Depends(current_active_user)):
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        new_session = ChatSession(session_id=sid, user_id=str(user.id))
        await save_session(new_session)
        return {"session_id": sid}

    @app.post("/api/session")
    async def create_session_singular(
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        template = body.get("template", "ieee")
        new_session = ChatSession(session_id=sid, user_id=str(user.id), template=template)
        await save_session(new_session)
        return {"session_id": sid}

    @app.get("/api/sessions/{session_id}/history")
    async def get_session_history(
        session_id: str,
        user: User = Depends(current_active_user)
    ):
        session = await get_session(str(user.id), session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        events = []
        event_path = _event_root() / f"{session.last_run_id}.ndjson"
        if event_path.exists():
            try:
                for line in event_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        events.append(json.loads(line))
            except Exception as exc:
                log_error(
                    "Failed to load session history",
                    severity=ErrorSeverity.RECOVERABLE,
                    component="webapp",
                    detail=f"{type(exc).__name__}: {exc}",
                )
        
        return {"events": events}

    @app.post("/api/voice/intake")
    async def voice_intake(
        file: UploadFile = File(...),
        user: User = Depends(current_active_user)
    ):
        from research_agent.app.voice import transcribe_voice_to_topic
        content = await file.read()
        topic = await transcribe_voice_to_topic(content, filename=file.filename or "recording.wav")
        return {"topic": topic}

    @app.websocket("/ws/chat/{session_id}")
    async def chat_websocket(
        websocket: WebSocket,
        session_id: str,
        token: str | None = None
    ):
        await manager.connect(websocket, session_id)
        # Simple token verification for WS
        from research_agent.app.auth import get_jwt_strategy, async_session_maker, UserManager
        from fastapi_users.db import SQLAlchemyUserDatabase
        strategy = get_jwt_strategy()
        async with async_session_maker() as db_session:
            user_db: SQLAlchemyUserDatabase[User, uuid.UUID] = SQLAlchemyUserDatabase(db_session, User)
            user_manager = UserManager(user_db)
            user = await strategy.read_token(token, user_manager)
        if not user or not user.is_active:
             await websocket.send_json({"event": "error", "payload": {"message": "Unauthorized"}})
             manager.disconnect(websocket, session_id)
             return

        session = await get_session(str(user.id), session_id)
        if not session:
            await websocket.send_json({"event": "error", "payload": {"message": "Session not found"}})
            manager.disconnect(websocket, session_id)
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
                    max_iterations = max(1, settings.runtime.max_iterations)
                    
                    actual_graph_runner = graph_runner or run_graph

                    async def emit_ws(event: str, payload: dict):
                        append_run_event(run_id=run_id, event=event, payload=payload)
                        await manager.broadcast(session_id, event, payload)

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
                            graph_runner=actual_graph_runner,
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
                    await manager.broadcast(session_id, "status", {"message": "Stop requested"})
                
        except WebSocketDisconnect:
            manager.disconnect(websocket, session_id)
        except Exception as e:
            try:
                await websocket.send_json({"event": "error", "payload": {"message": str(e)}})
            except Exception as send_exc:
                log_error(
                    "WebSocket error-handler send failed",
                    severity=ErrorSeverity.RECOVERABLE,
                    component="webapp",
                    detail=f"original={e}, send={send_exc}",
                )
            manager.disconnect(websocket, session_id)

    async def stop_session_run(session_id: str, user: User) -> bool:
        session = await get_session(str(user.id), session_id)
        if session and session.last_run_id in run_interrupt_signals:
            run_interrupt_signals[session.last_run_id].set()
            return True
        return False

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/api/health/redis")
    async def health_redis():
        """Health check that pings Redis and returns memory diagnostics."""
        diagnostics = await get_memory_diagnostics()

        redis_status = "not_configured"
        redis_ping_ms = None

        import time as _time

        pool_initialized = bool(
            diagnostics.get("redis_pool", {}).get("initialized", False)
        )

        if pool_initialized:
            # Try to ping via the existing shared pool
            pool = get_redis_pool()
            if pool is not None:
                import redis.asyncio as _redis_asyncio

                r = _redis_asyncio.Redis(connection_pool=pool)
                try:
                    start = _time.monotonic()
                    await r.ping()
                    redis_ping_ms = round((_time.monotonic() - start) * 1000, 1)
                    redis_status = "healthy"
                except Exception as exc:
                    redis_status = f"unhealthy: {exc}"
                finally:
                    try:
                        await r.close()
                    except Exception:
                        pass
        else:
            # Try a standalone connection to check Redis availability
            try:
                _settings = load_settings()
                redis_url = _settings.redis.url if hasattr(_settings, "redis") and hasattr(_settings.redis, "url") else None
                if redis_url:
                    import redis.asyncio as _redis_asyncio
                    r = _redis_asyncio.Redis.from_url(
                        redis_url,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                    )
                    try:
                        start = _time.monotonic()
                        await r.ping()
                        redis_ping_ms = round((_time.monotonic() - start) * 1000, 1)
                        redis_status = "healthy"
                    finally:
                        try:
                            await r.close()
                        except Exception:
                            pass
                else:
                    redis_status = "not_configured"
            except Exception as exc:
                redis_status = f"connection_failed: {exc}"

        return {
            "redis": {
                "status": redis_status,
                "ping_ms": redis_ping_ms,
            },
            "diagnostics": diagnostics,
            "healthy": redis_status == "healthy",
        }

    @app.post("/api/chat")
    async def chat_endpoint(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        session_id = body.get("session_id", "")
        message = body.get("message", "").strip()
        template = body.get("template", "ieee")

        session = await get_session(str(user.id), session_id) if session_id else None
        if not session:
            sid = f"sess-{uuid.uuid4().hex[:8]}"
            session = ChatSession(session_id=sid, user_id=str(user.id), template=template, original_topic=message)
            await save_session(session)
        else:
            session.template = template
            if not session.original_topic:
                session.original_topic = message

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        session.last_run_id = run_id
        await save_session(session)

        actual_graph_runner = graph_runner or run_graph
        tool_registry_local = registry if registry is not None else build_tool_registry(settings)

        initial_state = WorkflowState(
            run_id=run_id,
            topic=session.original_topic,
            template=template,
            language="en",
            depth="balanced",
            autonomy_mode="hybrid",
            max_runtime_minutes=settings.runtime.max_runtime_minutes,
            max_cost_usd=settings.runtime.max_cost_usd,
            max_iterations=settings.runtime.max_iterations,
        )

        try:
            if asyncio.iscoroutinefunction(actual_graph_runner):
                final_state = await actual_graph_runner(initial_state, registry=tool_registry_local)
            else:
                final_state = actual_graph_runner(initial_state, registry=tool_registry_local)

            session.awaiting_clarification = final_state.needs_clarification or bool(final_state.clarification_questions)
            session.pending_questions = final_state.clarification_questions
            await save_session(session)

            if final_state.needs_clarification or final_state.stop_reason == "clarification_required":
                return {
                    "kind": "clarification",
                    "questions": final_state.clarification_questions,
                }
            else:
                section_evidence = {}
                if final_state.section_confidence:
                    section_evidence = {t: {"confidence": c} for t, c in final_state.section_confidence.items()}
                return {
                    "kind": "result",
                    "run_id": run_id,
                    "section_evidence": section_evidence,
                }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/chat/stream")
    async def chat_stream_endpoint(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        session_id = body.get("session_id", "")
        message = body.get("message", "").strip()
        template = body.get("template", "ieee")

        session = await get_session(str(user.id), session_id) if session_id else None
        if not session:
            sid = f"sess-{uuid.uuid4().hex[:8]}"
            session = ChatSession(session_id=sid, user_id=str(user.id), template=template, original_topic=message)
            await save_session(session)
        else:
            session.template = template
            if not session.original_topic:
                session.original_topic = message

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        session.last_run_id = run_id
        await save_session(session)

        actual_graph_runner = graph_runner or run_graph
        tool_registry_local = registry if registry is not None else build_tool_registry(settings)

        async def event_stream():
            from research_agent.observability.progress import set_progress_callback

            initial_state = WorkflowState(
                run_id=run_id,
                topic=session.original_topic,
                template=template,
                language="en",
                depth="balanced",
                autonomy_mode="hybrid",
                max_runtime_minutes=settings.runtime.max_runtime_minutes,
                max_cost_usd=settings.runtime.max_cost_usd,
                max_iterations=settings.runtime.max_iterations,
            )

            # Queue for progress events from the running graph
            event_queue: asyncio.Queue[dict | None] = asyncio.Queue()

            async def progress_handler(payload: dict):
                await event_queue.put({"event": "status", "payload": payload})

            set_progress_callback(progress_handler)

            async def run_graph_task():
                try:
                    if asyncio.iscoroutinefunction(actual_graph_runner):
                        final_state = await actual_graph_runner(initial_state, registry=tool_registry_local)
                    else:
                        final_state = actual_graph_runner(initial_state, registry=tool_registry_local)

                    session.awaiting_clarification = final_state.needs_clarification or bool(final_state.clarification_questions)
                    session.pending_questions = final_state.clarification_questions
                    await save_session(session)

                    if final_state.needs_clarification or final_state.stop_reason == "clarification_required":
                        await event_queue.put({"event": "clarification", "questions": final_state.clarification_questions})
                    else:
                        await event_queue.put({"event": "result", "run_id": run_id})
                except Exception as e:
                    await event_queue.put({"event": "error", "message": str(e)})
                finally:
                    await event_queue.put(None)

            # Launch graph in background, stream events as they arrive
            task = asyncio.create_task(run_graph_task())

            try:
                while True:
                    item = await event_queue.get()
                    if item is None:
                        break
                    yield json.dumps(item) + "\n"
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass  # Expected on teardown — no logging needed

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/session/{session_id}/resume")
    async def resume_session(
        session_id: str,
        user: User = Depends(current_active_user)
    ):
        session = await get_session(str(user.id), session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not session.last_run_id:
            raise HTTPException(status_code=400, detail="No previous run to resume")

        return {
            "kind": "result",
            "run_id": session.last_run_id,
        }

    @app.post("/api/chat/upload")
    async def chat_upload(
        file: UploadFile = File(...),
        user: User = Depends(current_active_user)
    ):
        from research_agent.chat.parser import extract_text_from_pdf
        library_id = f"lib-{uuid.uuid4().hex[:8]}"
        tmp_dir = Path(".runtime/chat_uploads")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / file.filename

        content = await file.read()
        tmp_path.write_bytes(content)

        result = extract_text_from_pdf(tmp_path)
        if result is None:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")

        text = result["text"]
        metadata = result["metadata"]
        metadata["source"] = file.filename
        metadata["library_id"] = library_id

        from research_agent.chat.indexer import ChatLibraryIndex
        index = ChatLibraryIndex(library_id)
        chunk_count = await index.add_document(text, metadata)

        CHAT_LIBRARIES[library_id] = [metadata]

        return {"library_id": library_id, "chunks": chunk_count, "title": metadata.get("title", file.filename)}


    @app.post("/api/chat/ask")
    async def chat_ask(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        library_id = body.get("library_id", "")
        question = body.get("question", "").strip()
        if not library_id or not question:
            raise HTTPException(status_code=400, detail="library_id and question are required")
        if library_id not in CHAT_LIBRARIES:
            raise HTTPException(status_code=404, detail="Library not found")

        from research_agent.chat.ask import answer_question
        result = await answer_question(library_id, question)
        return result


    @app.get("/api/chat/library")
    async def chat_list_libraries(user: User = Depends(current_active_user)):
        libraries = [
            {
                "library_id": lib_id,
                "title": docs[0].get("title", "Untitled") if docs else "Untitled",
                "doc_count": len(docs),
            }
            for lib_id, docs in CHAT_LIBRARIES.items()
        ]
        return {"libraries": libraries}

    @app.get("/", response_class=HTMLResponse)
    async def get_index():
        index_file = Path(static_dir) / "index.html"
        if index_file.exists():
            return index_file.read_text(encoding="utf-8")
        return "<h1>Research Agent Web API</h1><p>Static files not found.</p>"

    if Path(static_dir).exists():
        app.mount("/web", StaticFiles(directory=static_dir), name="web")

    @app.get("/api/runs/{run_id}/graph")
    async def get_run_graph(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        checkpoint = load_latest_checkpoint(run_id)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Build react-flow compatible structure
        nodes = []
        edges = []
        for i, task in enumerate(checkpoint.tasks):
            nodes.append({
                "id": task.task_id,
                "data": {"label": task.title},
                "position": {"x": 250, "y": i * 100},
                "type": "researchTask"
            })
            for dep in task.depends_on:
                edges.append({
                    "id": f"e-{dep}-{task.task_id}",
                    "source": dep,
                    "target": task.task_id
                })
        
        return {"nodes": nodes, "edges": edges}

    @app.get("/api/runs/{run_id}/citation-graph")
    async def get_citation_graph(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        artifact_root = settings.runtime.artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root) / run_id
        graph_path = run_dir / "citation_graph.json"
        if graph_path.exists():
            data = json.loads(graph_path.read_text(encoding="utf-8"))
            return data
        raise HTTPException(status_code=404, detail="No citation graph found for this run")

    @app.get("/api/runs/{run_id}/gaps")
    async def get_gap_analysis(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        artifact_root = settings.runtime.artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root) / run_id
        gap_path = run_dir / "gap_analysis.md"
        if gap_path.exists():
            return {"gap_analysis": gap_path.read_text(encoding="utf-8")}
        raise HTTPException(status_code=404, detail="No gap analysis found for this run")

    @app.post("/api/runs/{run_id}/export/blog")
    async def export_blog(
        run_id: str,
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        artifact_root_local = artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root_local) / run_id
        tex_path = run_dir / "main.tex"
        if not tex_path.exists():
            raise HTTPException(status_code=404, detail="Run artifacts not found")

        tex_content = tex_path.read_text(encoding="utf-8")
        formats = body.get("formats", ["blog", "newsletter", "twitter"])
        topic = body.get("topic", run_id)

        from research_agent.output.blog_generator import generate_all
        output = generate_all(tex_content, topic, formats=formats)

        blog_dir = run_dir / "blog"
        blog_dir.mkdir(parents=True, exist_ok=True)
        for fmt, content in output.items():
            if isinstance(content, str):
                (blog_dir / f"{fmt}.md").write_text(content, encoding="utf-8")
            elif isinstance(content, list):
                (blog_dir / f"{fmt}.md").write_text(
                    "\n\n".join(content), encoding="utf-8"
                )

        return {"formats": list(output.keys()), "path": str(blog_dir)}

    @app.post("/api/runs/{run_id}/export/grant")
    async def generate_grant(
        run_id: str,
        request: GrantProposalRequest,
        user: User = Depends(current_active_user),
    ):
        artifact_root = settings.runtime.artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root) / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail="Run not found")

        findings_path = run_dir / "findings.json"
        papers = []
        if findings_path.exists():
            try:
                findings = json.loads(findings_path.read_text(encoding="utf-8"))
                for task_id, task_data in findings.items():
                    if isinstance(task_data, dict):
                        for provider, provider_data in task_data.items():
                            if isinstance(provider_data, dict):
                                for item in provider_data.get("items", []):
                                    if isinstance(item, dict):
                                        papers.append(item)
            except (json.JSONDecodeError, ValueError):
                pass

        result = generate_grant_proposal(
            title=request.title,
            pi_name=request.pi_name,
            pi_institution=request.pi_institution,
            abstract=request.abstract,
            papers=papers,
            agency=request.agency,
        )

        proposal_path = run_dir / "grant_proposal.md"
        proposal_path.write_text(result, encoding="utf-8")
        return {"grant_proposal": result}

    @app.post("/api/survey")
    async def generate_survey(
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        """Generate a multi-paper survey across a broad research area.

        Accepts a broad research topic, automatically decomposes it into
        sub-topics, researches each, and synthesizes a comprehensive survey
        paper with taxonomy, timeline, and research landscape.
        """
        topic = body.get("topic", "").strip()
        num_topics = max(3, min(8, int(body.get("num_topics", 5))))

        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")

        from research_agent.orchestration.survey import run_survey

        tool_registry_local = registry if registry is not None else build_tool_registry(settings)

        try:
            result = await run_survey(
                broad_topic=topic,
                registry=tool_registry_local,
                num_topics=num_topics,
            )

            # Save survey to artifacts
            artifact_root = settings.runtime.artifact_root or ".runtime/artifacts"
            survey_dir = Path(artifact_root) / result.run_id
            survey_dir.mkdir(parents=True, exist_ok=True)

            (survey_dir / "survey.md").write_text(result.survey_markdown, encoding="utf-8")
            (survey_dir / "taxonomy_table.md").write_text(result.taxonomy_table, encoding="utf-8")
            (survey_dir / "timeline.md").write_text(result.timeline, encoding="utf-8")
            (survey_dir / "research_landscape.md").write_text(result.research_landscape, encoding="utf-8")

            return {
                "run_id": result.run_id,
                "topic": result.topic,
                "sub_topics": [{"name": t.name, "description": t.description, "paper_count": len(t.key_papers)} for t in result.sub_topics],
                "paper_count": result.paper_count,
                "key_findings": result.key_findings,
                "duration_seconds": result.duration_seconds,
                "survey": result.survey_markdown,
                "taxonomy_table": result.taxonomy_table,
                "timeline": result.timeline,
                "research_landscape": result.research_landscape,
                "artifact_dir": str(survey_dir),
                "warnings": result.warnings,
            }
        except Exception as e:
            logger.exception("Survey generation failed")
            raise HTTPException(status_code=500, detail=f"Survey generation failed: {e}")

    @app.post("/api/runs/{run_id}/plagiarism-check")
    async def plagiarism_check(
        run_id: str,
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        """Run a plagiarism check on a completed run's generated content.

        Compares the generated LaTeX/papers against retrieved source chunks
        and returns similarity scores, flagged passages, and rewrite suggestions.
        """
        artifact_root_local = artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root_local) / run_id
        tex_path = run_dir / "main.tex"
        if not tex_path.exists():
            raise HTTPException(status_code=404, detail="Run artifacts not found. Run research first.")

        threshold = float(body.get("threshold", 0.8))
        include_rewrites = bool(body.get("include_rewrites", True))

        tex_content = tex_path.read_text(encoding="utf-8")

        # Collect source chunks from the run's findings
        source_chunks: list[dict] = []
        findings_path = run_dir / "findings.json"
        if findings_path.exists():
            try:
                findings = json.loads(findings_path.read_text(encoding="utf-8"))
                for task_id, task_data in findings.items():
                    if isinstance(task_data, dict):
                        for provider, provider_data in task_data.items():
                            if isinstance(provider_data, dict):
                                for item in provider_data.get("items", []):
                                    if isinstance(item, dict):
                                        snippet = item.get("snippet") or item.get("content") or ""
                                        if snippet:
                                            source_chunks.append({"text": str(snippet)})
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Could not parse findings for plagiarism check: %s", exc)

        # Also check against Qdrant index if available
        try:
            from research_agent.rag.indexer import ResearchIndex
            index = ResearchIndex(collection_name=f"run_{run_id}")
            qdrant_results = await index.asearch(tex_content[:1000], limit=20)
            for hit in qdrant_results:
                text = hit.get("text", "")
                if text:
                    source_chunks.append({"text": str(text)})
        except Exception as exc:
            logger.warning("Qdrant lookup failed for plagiarism check: %s", exc)

        from research_agent.verification.plagiarism_checker import check_plagiarism
        from research_agent.verification.rewrite_suggester import batch_suggest_rewrites

        result = check_plagiarism(tex_content, source_chunks, threshold=threshold)

        if include_rewrites and result["flagged_sentences"]:
            result["rewrite_suggestions"] = batch_suggest_rewrites(result["flagged_sentences"])

        # Save report
        report_path = run_dir / "plagiarism_report.json"
        report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

        return {
            "run_id": run_id,
            "overall_score": result["overall_score"],
            "flagged_count": result["statistics"]["flagged"],
            "total_sentences_checked": result["statistics"]["total_sentences"],
            "exact_matches": result["statistics"]["exact_matches"],
            "paraphrases": result["statistics"]["paraphrases"],
            "flagged_sentences": result["flagged_sentences"],
            "rewrite_suggestions": result.get("rewrite_suggestions", []),
        }

    @app.post("/api/sessions/{session_id}/critic/feedback")
    async def post_critic_feedback(
        session_id: str,
        feedback: str = Body(..., embed=True),
        user: User = Depends(current_active_user)
    ):
        session = await get_session(str(user.id), session_id)
        if not session:
             raise HTTPException(status_code=404, detail="Session not found")
        
        session.awaiting_critic_feedback = False
        # The next WS message will pick this up or we can trigger it here
        return {"success": True}

    @app.post("/api/watchdog/subscribe")
    async def watchdog_subscribe(
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        """Subscribe to a research topic for monitoring.

        Creates an interest profile that the watchdog will monitor for
        new papers at the specified interval.
        """
        topic = body.get("topic", "").strip()
        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")

        keywords = body.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        authors = body.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",") if a.strip()]
        venues = body.get("venues", [])
        if isinstance(venues, str):
            venues = [v.strip() for v in venues.split(",") if v.strip()]

        check_interval = body.get("check_interval", "daily")
        if check_interval not in ("daily", "weekly", "biweekly", "monthly"):
            raise HTTPException(status_code=400, detail="check_interval must be daily, weekly, biweekly, or monthly")

        from research_agent.app.watchdog_storage import (
            InterestProfile,
            get_watchdog_storage,
        )

        profile = InterestProfile(
            profile_id=f"watch-{uuid.uuid4().hex[:8]}",
            user_id=str(user.id),
            topic=topic,
            keywords=keywords,
            authors=authors,
            venues=venues,
            check_interval=check_interval,
        )

        storage = get_watchdog_storage()
        storage.save_profile(profile)

        return {
            "profile_id": profile.profile_id,
            "topic": profile.topic,
            "check_interval": profile.check_interval,
            "keywords": profile.keywords,
            "authors": profile.authors,
            "venues": profile.venues,
            "message": f"Now monitoring '{topic}' {check_interval}.",
        }

    @app.get("/api/watchdog/subscriptions")
    async def watchdog_list_subscriptions(
        user: User = Depends(current_active_user)
    ):
        """List all watchdog subscriptions for the current user."""
        from research_agent.app.watchdog_storage import get_watchdog_storage

        storage = get_watchdog_storage()
        profiles = storage.get_user_profiles(str(user.id))

        return {
            "subscriptions": [
                {
                    "profile_id": p.profile_id,
                    "topic": p.topic,
                    "keywords": p.keywords,
                    "authors": p.authors,
                    "venues": p.venues,
                    "check_interval": p.check_interval,
                    "enabled": p.enabled,
                    "last_checked_at": p.last_checked_at,
                    "created_at": p.created_at,
                }
                for p in profiles
            ],
            "count": len(profiles),
        }

    @app.delete("/api/watchdog/subscriptions/{profile_id}")
    async def watchdog_unsubscribe(
        profile_id: str,
        user: User = Depends(current_active_user)
    ):
        """Unsubscribe from a watchdog subscription."""
        from research_agent.app.watchdog_storage import get_watchdog_storage

        storage = get_watchdog_storage()
        profile = storage.get_profile(profile_id)

        if profile is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if profile.user_id != str(user.id):
            raise HTTPException(status_code=403, detail="Not authorized to delete this subscription")

        storage.delete_profile(profile_id)
        return {"message": f"Unsubscribed from '{profile.topic}'."}

    @app.get("/api/watchdog/digests")
    async def watchdog_list_digests(
        limit: int = 10,
        user: User = Depends(current_active_user)
    ):
        """List recent watchdog digests for the current user."""
        from research_agent.app.watchdog_storage import get_watchdog_storage
        from research_agent.orchestration.watchdog import format_digest_for_display

        storage = get_watchdog_storage()
        digests = storage.get_user_digests(str(user.id), limit=limit)

        return {
            "digests": [
                {
                    "digest_id": d.digest_id,
                    "topic": d.topic,
                    "summary": d.summary,
                    "paper_count": d.paper_count,
                    "generated_at": d.generated_at,
                    "formatted": format_digest_for_display(d),
                    "papers": [
                        {
                            "title": p.get("title", "Untitled"),
                            "authors": p.get("authors", []),
                            "year": p.get("year", "n.d."),
                            "url": p.get("url", ""),
                            "source": p.get("watchdog_provider", p.get("provider", "unknown")),
                        }
                        for p in d.new_papers[:20]
                    ],
                }
                for d in digests
            ],
            "count": len(digests),
        }

    @app.post("/api/watchdog/check")
    async def watchdog_manual_check(
        user: User = Depends(current_active_user)
    ):
        """Manually trigger a watchdog check for all due profiles."""
        from research_agent.orchestration.watchdog import run_all_due_checks

        try:
            digests = await run_all_due_checks(tool_registry)
            return {
                "profiles_checked": len(digests),
                "total_new_papers": sum(d.paper_count for d in digests),
                "digests": [
                    {
                        "profile_id": d.profile_id,
                        "topic": d.topic,
                        "paper_count": d.paper_count,
                        "summary": d.summary,
                    }
                    for d in digests
                ],
            }
        except Exception as exc:
            logger.exception("Manual watchdog check failed")
            raise HTTPException(status_code=500, detail=f"Watchdog check failed: {exc}")

    @app.post("/api/runs/{run_id}/overleaf/push")
    async def overleaf_push(
        run_id: str,
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        """Push a run's generated LaTeX to Overleaf via snip URL or Git.

        Returns either:
        - A snip URL for one-click browser opening (default)
        - A Git push result if a git_url is provided
        """
        artifact_root_local = artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root_local) / run_id
        tex_path = run_dir / "main.tex"

        if not tex_path.exists():
            raise HTTPException(status_code=404, detail="Run artifacts not found. Run research first.")

        main_tex = tex_path.read_text(encoding="utf-8")
        bib_path = run_dir / "references.bib"
        bibtex = bib_path.read_text(encoding="utf-8") if bib_path.exists() else ""

        project_name = body.get("project_name", f"Research: {run_id}")
        git_url = body.get("git_url", "")
        method = body.get("method", "snip")

        from research_agent.output.overleaf import (
            build_overleaf_import_url,
            build_overleaf_form_html,
            git_push_to_overleaf,
        )

        if method == "git" and git_url:
            git_token = body.get("git_token", None)
            result = git_push_to_overleaf(
                git_url=git_url,
                main_tex=main_tex,
                bibtex=bibtex,
                git_token=git_token,
                commit_message=f"Update from Research Agent run {run_id}",
            )
            return result

        elif method == "html":
            html = build_overleaf_form_html(main_tex, bibtex, project_name=project_name)
            return {
                "success": True,
                "method": "html_form",
                "html": html,
                "message": "Auto-submitting HTML form. Opens Overleaf in a new tab.",
            }

        else:
            # Default: snip URL
            url = build_overleaf_import_url(main_tex, bibtex, project_name=project_name)
            return {
                "success": True,
                "method": "snip_url",
                "url": url,
                "message": "Click or open the URL to create an Overleaf project with your content.",
            }

    @app.get("/api/runs/{run_id}/overleaf/status")
    async def overleaf_status(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        """Check if a run's artifacts are ready for Overleaf push and if Git is configured."""
        artifact_root_local = artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root_local) / run_id
        tex_path = run_dir / "main.tex"

        from research_agent.output.overleaf import check_overleaf_config

        config = check_overleaf_config()

        return {
            "run_id": run_id,
            "artifacts_exist": tex_path.exists(),
            "main_tex_size": len(tex_path.read_text(encoding="utf-8")) if tex_path.exists() else 0,
            "git_available": config["git_available"],
            "git_token_configured": config["git_token_configured"],
            "snip_available": config["snip_available"],
        }

    @app.post("/api/runs/{run_id}/overleaf/pull")
    async def overleaf_pull(
        run_id: str,
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        """Pull LaTeX content from an Overleaf project via Git.

        Requires a git_url and OVERLEAF_GIT_TOKEN to be configured.
        """
        git_url = body.get("git_url", "")
        if not git_url:
            raise HTTPException(status_code=400, detail="git_url is required")

        from research_agent.output.overleaf import git_pull_from_overleaf

        result = git_pull_from_overleaf(
            git_url=git_url,
            git_token=body.get("git_token", None),
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "Pull failed"))

        # Save pulled content back to run artifacts
        artifact_root_local = artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root_local) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        if result.get("main_tex"):
            (run_dir / "main.tex").write_text(result["main_tex"], encoding="utf-8")
        if result.get("bibtex"):
            (run_dir / "references.bib").write_text(result["bibtex"], encoding="utf-8")

        return result

    @app.get("/api/overleaf/config")
    async def overleaf_config_check(
        user: User = Depends(current_active_user)
    ):
        """Check Overleaf integration configuration status."""
        from research_agent.output.overleaf import check_overleaf_config
        return check_overleaf_config()

    @app.post("/api/runs/{run_id}/render")
    async def render_pdf(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        artifact_root_local = artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root_local) / run_id
        tex_path = run_dir / "main.tex"
        if not tex_path.exists():
            raise HTTPException(status_code=404, detail="Run artifacts not found")

        from research_agent.output.pdf_renderer import get_pdf_path, compile_pdf

        cached = get_pdf_path(run_dir)
        if cached:
            return {"status": "cached", "pdf_path": cached}

        pdf_path = compile_pdf(run_dir)
        if pdf_path:
            return {"status": "compiled", "pdf_path": pdf_path}
        return {"status": "failed", "detail": "No LaTeX compiler available (try installing tectonic)"}

    @app.get("/api/runs/{run_id}/render/pdf")
    async def get_rendered_pdf(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        artifact_root_local = artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root_local) / run_id
        from research_agent.output.pdf_renderer import get_pdf_path

        pdf_path = get_pdf_path(run_dir)
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF not found. POST /api/runs/{run_id}/render first")
        return FileResponse(pdf_path, media_type="application/pdf", filename=f"{run_id}.pdf")

    @app.get("/api/runs/{run_id}/render/status")
    async def render_status(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        artifact_root_local = artifact_root or ".runtime/artifacts"
        run_dir = Path(artifact_root_local) / run_id
        from research_agent.output.pdf_renderer import get_pdf_path

        cached = get_pdf_path(run_dir)
        tectonic_avail = shutil.which("tectonic") is not None
        docker_avail = shutil.which("docker") is not None
        return {
            "cached": cached is not None,
            "tectonic_available": tectonic_avail,
            "docker_available": docker_avail,
        }

    return app


def _compose_refined_topic(original: str, questions: list[str], answers: list[str]) -> str:
    qa_pairs = []
    for q, a in zip(questions, answers):
        qa_pairs.append(f"Q: {q}\nA: {a}")
    
    return (
        f"Original Topic: {original}\n\n"
        "Clarifications:\n" + "\n".join(qa_pairs)
    )


async def _execute_research_run(
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
    tool_registry,
    emit_callback,
    critic_user_feedback: str | None = None
) -> bool:
    initial_state = WorkflowState(
        run_id=run_id,
        topic=topic,
        template=template,
        language=language,
        depth=depth,
        autonomy_mode=autonomy_mode,
        max_runtime_minutes=max_runtime_minutes,
        max_cost_usd=max_cost_usd,
        max_iterations=max_iterations,
        critic_user_feedback=critic_user_feedback
    )
    
    # Register callback for progress events
    from research_agent.observability.progress import set_progress_callback
    set_progress_callback(emit_callback)

    try:
        final_state = await graph_runner(initial_state, registry=tool_registry)
        
        session.awaiting_clarification = final_state.needs_clarification
        session.pending_questions = final_state.clarification_questions
        session.awaiting_critic_feedback = (final_state.phase == "awaiting_critic_review")
        
        if final_state.phase == "completed":
            await emit_callback("complete", {
                "artifact_dir": final_state.artifact_dir,
                "summary": "Research complete. Artifacts ready."
            })
        elif final_state.needs_clarification:
            await emit_callback("clarification_needed", {
                "questions": final_state.clarification_questions
            })
            
        return True
    except Exception as e:
        await emit_callback("error", {"message": f"Run failed: {str(e)}"})
        return False


app = create_app()

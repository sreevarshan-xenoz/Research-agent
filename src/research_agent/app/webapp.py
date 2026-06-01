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
        # Startup: nothing special needed (connections are lazy)
        yield
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

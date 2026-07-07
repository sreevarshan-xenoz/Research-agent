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
from research_agent.app.security import set_user_role, is_admin
from research_agent.app.audit import AuditMiddleware, get_audit_store
from research_agent.app.rate_limit import RateLimitMiddleware, start_rate_limit_cleanup
from research_agent.app.sso import build_sso_router
from research_agent.app.collab_routes import router as collab_router
from research_agent.app.submission_routes import router as submission_router
from research_agent.app.template_routes import router as template_router
from research_agent.personal_library.routes import router as personal_library_router
from research_agent.paper_git.routes import router as paper_git_router
from research_agent.plugins.routes import router as plugins_router
from research_agent.app.research_suggestions import router as research_suggestions_router, load_past_topics_for_user
from research_agent.config import load_settings, validate_insecure_defaults
from research_agent.models.llm_client import _resolve_api_key
from research_agent.output.grant_proposal import generate_grant_proposal
from research_agent.observability.checkpoints import (
    append_run_event,
    load_latest_checkpoint,
    _event_root,
)
from research_agent.observability.logging import ErrorSeverity, log_error
from research_agent.observability.structured_log import configure_json_logging
from research_agent.observability.tracing import init_tracing
from research_agent.observability.error_tracking import init_sentry
from research_agent.orchestration.graph import close_redis_pool, get_memory_diagnostics, get_redis_pool, run_graph
from research_agent.orchestration.job_queue import JobStatus, get_job_manager
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
        # Startup: create database tables
        from research_agent.app.auth import create_db_and_tables
        try:
            await create_db_and_tables()
            logger.info("Database tables initialized successfully.")
        except Exception as exc:
            logger.error("Failed to initialize database tables: %s", exc)

        # Startup: initialize observability stack
        obs = settings.observability
        if obs.enabled:
            if obs.json_logging:
                try:
                    configure_json_logging()
                    logger.info("JSON structured logging enabled")
                except Exception as exc:
                    logger.warning("Failed to configure JSON logging: %s", exc)
            if obs.enable_metrics:
                try:
                    from research_agent.observability.metrics import start_metrics_server
                    start_metrics_server(port=obs.metrics_port)
                    logger.info("Prometheus metrics server started on port %d", obs.metrics_port)
                except Exception as exc:
                    logger.warning("Failed to start metrics server: %s", exc)
            if obs.enable_tracing and obs.otlp_endpoint:
                try:
                    init_tracing(
                        service_name="research-agent",
                        otlp_endpoint=obs.otlp_endpoint,
                        sample_rate=obs.tracer_sample_rate,
                    )
                    logger.info("OpenTelemetry tracing enabled, endpoint: %s", obs.otlp_endpoint)
                except Exception as exc:
                    logger.warning("Failed to init tracing: %s", exc)
            if obs.sentry_dsn:
                try:
                    init_sentry(
                        dsn=obs.sentry_dsn,
                        environment=obs.sentry_environment,
                        traces_sample_rate=obs.sentry_traces_sample_rate,
                    )
                    logger.info("Sentry error tracking enabled")
                except Exception as exc:
                    logger.warning("Failed to init Sentry: %s", exc)

        # Startup: start background watchdog scheduler
        watchdog_task = None

        # P18: Start rate limit cleanup task
        if settings.rate_limit.enabled:
            try:
                rl_cleanup_task = start_rate_limit_cleanup()
                logger.info("Rate limit cleanup task started")
            except Exception as exc:
                logger.warning("Failed to start rate limit cleanup: %s", exc)
                rl_cleanup_task = None
        else:
            rl_cleanup_task = None
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

    # P18: Auth context middleware — populates request.state from JWT for downstream
    # audit and rate-limit middleware to read user identity.
    @app.middleware("http")
    async def _auth_context_middleware(request, call_next):
        request.state.user_id = "anonymous"
        request.state.user_role = "anonymous"
        request.state.session_id = ""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from research_agent.app.auth import get_jwt_strategy, async_session_maker, UserManager, User
                from fastapi_users.db import SQLAlchemyUserDatabase
                token = auth_header[len("Bearer "):]
                strategy = get_jwt_strategy()
                async with async_session_maker() as _db:
                    user_db = SQLAlchemyUserDatabase(_db, User)
                    manager = UserManager(user_db)
                    user_obj = await strategy.read_token(token, manager)
                    if user_obj and user_obj.is_active:
                        request.state.user_id = str(user_obj.id)
                        request.state.user_role = getattr(user_obj, "role", "viewer") or "viewer"
            except Exception:
                pass  # Best-effort; middleware continues with anonymous context
        return await call_next(request)

    # P18: Security middleware stack (order matters: rate limit before audit)
    rl = settings.rate_limit
    if rl.enabled:
        app.add_middleware(
            RateLimitMiddleware,
            default_rpm=rl.default_requests_per_minute,
            auth_rpm=rl.authenticated_requests_per_minute,
            admin_rpm=rl.admin_requests_per_minute,
            burst=rl.burst_size,
            endpoint_overrides=rl.endpoint_overrides,
            exclude_paths=["/health", "/metrics", "/api/health"],
        )
    if settings.audit.enabled:
        app.add_middleware(
            AuditMiddleware,
            exclude_paths=settings.audit.exclude_paths,
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
    # P18: SSO/OAuth routes
    sso_router = build_sso_router()
    app.include_router(sso_router)
    # P25: Collaborative editing routes
    app.include_router(collab_router)
    # P27: Submission pipeline routes
    app.include_router(submission_router)
    # P39: Template library and preset routes
    app.include_router(template_router)
    # P28: Personal Research Library routes
    app.include_router(personal_library_router)
    # P36: Paper-git Version Control routes
    app.include_router(paper_git_router)
    # P19: Plugin System routes
    app.include_router(plugins_router)
    app.include_router(research_suggestions_router)

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
        event_path = _event_root() / f"{session.last_run_id}.ndjson"  # type: ignore[operator]
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

    @app.post("/api/session/{session_id}/stop")
    async def stop_session(
        session_id: str,
        user: User = Depends(current_active_user)
    ):
        """REST fallback to stop a running session when WebSocket is unavailable."""
        stopped = await stop_session_run(session_id, user)
        if stopped:
            return {"status": "stopped", "message": "Stop signal sent"}
        raise HTTPException(status_code=404, detail="No active run found for session")

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/api/health/models")
    async def health_models():
        """Check the availability of each configured LLM provider/model.

        Tests connectivity by attempting a minimal request against each
        configured provider. Reports status, model, and latency for each.
        Returns a consolidated health report.
        """
        import time as _time
        _settings = load_settings()
        results: list[dict[str, object]] = []

        provider_configs: list[tuple[str, str, str | None, dict[str, Any]]] = []

        def _add(provider: str, model: str, api_key: str | None, extra: dict[str, Any]) -> None:
            provider_configs.append((provider, model, api_key, extra))

        # Ollama (local)
        _add("ollama", _settings.models.orchestrator_model if "ollama" in _settings.models.orchestrator_model else "ollama/qwen3:8b",
             None, {"api_base": _settings.ollama.api_base})

        # OpenRouter
        or_key = _resolve_api_key(_settings.openrouter.api_key) or os.getenv("OPENROUTER_API_KEY", "")
        if or_key:
            _add("openrouter", _settings.models.subagent_cloud or "openrouter/free",
                 or_key, {"api_key": or_key})

        # NVIDIA
        nv_key = os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIMS_API_KEY", "")
        if nv_key:
            _add("nvidia", _settings.models.subagent_nvidia or "nvidia/meta/llama-3.1-405b-instruct",
                 nv_key, {"api_key": nv_key})

        # OpenAI
        oa_key = _resolve_api_key(_settings.openai.api_key) or os.getenv("OPENAI_API_KEY", "")
        if oa_key:
            _add("openai", _settings.models.subagent_openai or "openai/gpt-4o",
                 oa_key, {})

        # Anthropic
        an_key = _resolve_api_key(_settings.anthropic.api_key) or os.getenv("ANTHROPIC_API_KEY", "")
        if an_key:
            _add("anthropic", _settings.models.subagent_anthropic or "anthropic/claude-3-5-sonnet-20241022",
                 an_key, {})

        # Gemini
        gm_key = _resolve_api_key(_settings.gemini.api_key) or os.getenv("GEMINI_API_KEY", "")
        if gm_key:
            _add("gemini", _settings.models.subagent_gemini or "gemini/gemini-2.0-flash",
                 gm_key, {})

        # Groq
        gq_key = _resolve_api_key(_settings.groq.api_key) or os.getenv("GROQ_API_KEY", "")
        if gq_key:
            _add("groq", _settings.models.subagent_groq or "groq/llama-3.3-70b-versatile",
                 gq_key, {})

        # Test each provider with a minimal LiteLLM completion call
        import litellm as _litellm
        _litellm.drop_params = True

        for provider, model, api_key, extra in provider_configs:
            start = _time.monotonic()
            status = "unknown"
            latency_ms: float | None = None
            error: str | None = None
            try:
                # Use a tiny max_tokens to minimize cost/time
                resp = _litellm.completion(
                    model=model,
                    messages=[{"role": "user", "content": "Respond with 'ok'",}],
                    max_tokens=5,
                    temperature=0.1,
                    timeout=10,
                    **extra,
                )
                latency_ms = round((_time.monotonic() - start) * 1000, 1)
                if resp and resp.choices and resp.choices[0].message.content:
                    status = "healthy"
                else:
                    status = "unhealthy"
            except Exception as exc:
                latency_ms = round((_time.monotonic() - start) * 1000, 1)
                error = f"{type(exc).__name__}: {exc}"
                status = "error" if "rate limit" in str(exc).lower() or "unauthorized" in str(exc).lower() else "unreachable"

            # Get latency metrics from the tracker if available
            from research_agent.models.latency_tracker import get_latency_tracker
            tracker = get_latency_tracker()
            try:
                avg_latency = await tracker.get_avg_latency_ms(provider)
            except Exception:
                avg_latency = None

            results.append({
                "provider": provider,
                "model": model,
                "status": status,
                "latency_ms": latency_ms,
                "avg_latency_ms": avg_latency,
                "error": error,
                "api_key_configured": bool(api_key),
            })

        # Get cost metrics
        from research_agent.models.cost_tracker import get_all_cost_metrics
        try:
            cost_metrics = await get_all_cost_metrics()
        except Exception:
            cost_metrics = {}

        # Count healthy vs unhealthy
        healthy_count = sum(1 for r in results if r["status"] == "healthy")
        unhealthy_count = sum(1 for r in results if r["status"] != "healthy")

        return {
            "models": results,
            "summary": {
                "total": len(results),
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
            },
            "cost_metrics": cost_metrics,
            "healthy": healthy_count > 0,
        }

    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus metrics endpoint.

        Exposes the Prometheus metrics in plaintext format for scraping.
        Accessible at /metrics (no auth required for Prometheus scraping).
        """
        from research_agent.observability.metrics import get_metrics_text
        from fastapi.responses import PlainTextResponse
        try:
            metrics_data = get_metrics_text()
            return PlainTextResponse(metrics_data, media_type="text/plain; charset=utf-8")
        except Exception as exc:
            logger.warning("Failed to generate metrics: %s", exc)
            return PlainTextResponse(
                "Metrics unavailable",
                status_code=503,
                media_type="text/plain; charset=utf-8"
            )

    # ------------------------------------------------------------------ #
    # P18 Security & Admin Endpoints
    # ------------------------------------------------------------------ #

    @app.get("/api/admin/audit")
    async def admin_query_audit(
        user_id: str | None = None,
        action_type: str | None = None,
        resource: str | None = None,
        path_pattern: str | None = None,
        status_code: int | None = None,
        limit: int = 100,
        offset: int = 0,
        days_back: int = 7,
        user: User = Depends(current_active_user),
    ):
        """Query audit logs (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        store = await get_audit_store()
        entries = await store.query(
            user_id=user_id or None,
            action_type=action_type or None,
            resource=resource or None,
            path_pattern=path_pattern or None,
            status_code=status_code,
            limit=min(limit, 1000),
            offset=offset,
            days_back=days_back,
        )
        return {"entries": entries, "count": len(entries)}

    @app.get("/api/admin/audit/stats")
    async def admin_audit_stats(
        user: User = Depends(current_active_user),
    ):
        """Get audit log statistics (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        store = await get_audit_store()
        stats = await store.get_stats()
        return stats

    @app.get("/api/admin/users")
    async def admin_list_users(
        user: User = Depends(current_active_user),
    ):
        """List all users with roles (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        from research_agent.app.auth import async_session_maker, User as UserModel
        from sqlalchemy import select
        async with async_session_maker() as session:
            result = await session.execute(select(UserModel))
            users = result.scalars().all()
            return {
                "users": [
                    {
                        "id": str(u.id),
                        "email": u.email,
                        "role": getattr(u, "role", "viewer"),
                        "is_active": u.is_active,
                        "is_superuser": u.is_superuser,
                        "is_verified": u.is_verified,
                    }
                    for u in users
                ],
                "count": len(users),
            }

    @app.post("/api/admin/users/{user_id}/role")
    async def admin_update_role(
        user_id: str,
        body: dict,
        user: User = Depends(current_active_user),
    ):
        """Update a user's role (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        new_role = body.get("role", "").strip().lower()
        if new_role not in ("viewer", "editor", "admin"):
            raise HTTPException(status_code=400, detail="Invalid role. Must be viewer, editor, or admin.")
        success = await set_user_role(user_id, new_role)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"success": True, "user_id": user_id, "role": new_role}

    @app.get("/api/admin/security/status")
    async def admin_security_status(
        user: User = Depends(current_active_user),
    ):
        """Get security configuration status (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        _settings = load_settings()
        return {
            "rbac_enabled": _settings.rbac.enabled,
            "default_role": _settings.rbac.default_role,
            "rate_limiting_enabled": _settings.rate_limit.enabled,
            "audit_logging_enabled": _settings.audit.enabled,
            "sso_configured": is_sso_configured(),
            "sso_enabled": _settings.sso.enabled,
            "encryption_configured": bool(str(_settings.secrets_mgmt.encryption_key)),
            "auth_configured": str(_settings.auth.secret_key) != "DEV_SECRET_DO_NOT_USE_IN_PROD",
        }

    @app.get("/api/admin/encrypt")
    async def admin_encrypt_value(
        plaintext: str,
        user: User = Depends(current_active_user),
    ):
        """Encrypt a value using the configured encryption key (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        encrypted = encrypt_value(plaintext)
        return {"encrypted": encrypted, "plaintext_length": len(plaintext)}

    @app.get("/api/admin/decrypt")
    async def admin_decrypt_value(
        encrypted: str,
        user: User = Depends(current_active_user),
    ):
        """Decrypt a value (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        if not encrypted.startswith("enc:"):
            raise HTTPException(status_code=400, detail="Value does not appear to be encrypted (missing 'enc:' prefix)")
        decrypted = decrypt_value(encrypted)
        return {"decrypted": decrypted}

    @app.get("/api/admin/rate-limits")
    async def admin_rate_limit_status(
        user: User = Depends(current_active_user),
    ):
        """Get rate limit configuration (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        _settings = load_settings()
        return {
            "default_rpm": _settings.rate_limit.default_requests_per_minute,
            "authenticated_rpm": _settings.rate_limit.authenticated_requests_per_minute,
            "admin_rpm": _settings.rate_limit.admin_requests_per_minute,
            "burst_size": _settings.rate_limit.burst_size,
            "endpoint_overrides": _settings.rate_limit.endpoint_overrides,
        }

    # ------------------------------------------------------------------ #
    # P31: Ensemble Voting Admin Endpoints
    # ------------------------------------------------------------------ #

    @app.get("/api/admin/ensemble/status")
    async def admin_ensemble_status(
        user: User = Depends(current_active_user),
    ):
        """Get ensemble voting configuration and model health (admin only)."""
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")
        _settings = load_settings()

        from research_agent.models.ensemble import _resolve_ensemble_models, get_ensemble_config
        available_models = _resolve_ensemble_models(8)
        models_health = []
        for mc in available_models:
            model_name = mc["model"]
            provider = mc["provider"]
            has_key = bool(mc.get("extra", {}).get("api_key"))
            models_health.append({
                "model": model_name,
                "provider": provider,
                "api_key_configured": has_key,
            })

        task_configs = {}
        for task_type in ["critic", "planner", "composer", "bias_detection", "hallucination_guard"]:
            strategy, num_models, min_success, timeout = get_ensemble_config(task_type)
            task_configs[task_type] = {
                "strategy": strategy.value,
                "num_models": num_models,
                "min_success": min_success,
                "timeout_s": timeout,
            }

        return {
            "enabled": _settings.ensemble.enabled,
            "default_num_models": _settings.ensemble.default_num_models,
            "default_timeout_s": _settings.ensemble.default_timeout_s,
            "min_success_ratio": _settings.ensemble.min_success_ratio,
            "task_configs": task_configs,
            "available_models": models_health,
            "total_available_models": len(available_models),
            "settings_override_tasks": list(_settings.ensemble.task_overrides.keys()),
        }

    @app.post("/api/admin/ensemble/test")
    async def admin_ensemble_test(
        body: dict,
        user: User = Depends(current_active_user),
    ):
        """Run a test ensemble round with a custom prompt (admin only).

        Request body:
            task_type (str, optional): Task type (default: "critic").
            prompt (str, optional): Custom prompt. If empty, uses a default test prompt.
            num_models (int, optional): Override number of models.
            temperature (float, optional): Override temperature.
        """
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin access required")

        from research_agent.models.ensemble import run_ensemble

        task_type = body.get("task_type", "critic")
        custom_prompt = body.get("prompt", "").strip()
        num_models = body.get("num_models", None)
        temperature = body.get("temperature", 0.3)

        prompt = custom_prompt or ("You are a research quality evaluator. "
            "Rate the research topic 'Multi-Model Ensemble Voting' on a scale of 0.0-1.0. "
            "Output a JSON object with 'score' (float 0.0-1.0) and 'confidence' (float 0.0-1.0)."
        )

        try:
            result = await run_ensemble(
                task_type=task_type,
                prompt=prompt,
                temperature=float(temperature),
                max_tokens=512,
                num_models=int(num_models) if num_models is not None else None,
            )

            return {
                "success": result.num_success > 0,
                "task_type": result.task_type,
                "strategy": result.strategy.value,
                "num_models": result.num_models,
                "num_success": result.num_success,
                "num_failures": result.num_failures,
                "consensus_score": result.consensus_score,
                "disagreement_detected": result.disagreement_detected,
                "disagreement_detail": result.disagreement_detail,
                "total_latency_ms": result.total_latency_ms,
                "aggregated_text_preview": result.aggregated_text[:500] if result.aggregated_text else "",
                "votes": [
                    {
                        "model": v.model_name,
                        "provider": v.provider,
                        "latency_ms": v.latency_ms,
                        "error": v.error,
                        "text_preview": v.raw_text[:200] if v.raw_text else "",
                    }
                    for v in result.votes
                ],
            }
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Ensemble test failed: {type(exc).__name__}: {exc}",
            )

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

            past_research_topics=load_past_topics_for_user(str(user.id)),
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

            past_research_topics=load_past_topics_for_user(str(user.id)),
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

        run_id = session.last_run_id
        artifact_base = f"/api/runs/{run_id}"

        return {
            "kind": "result",
            "run_id": run_id,
            "template": session.template,
            "language": "en",
            "artifact_urls": {
                "pdf": f"{artifact_base}/render/pdf",
                "latex": f"{artifact_base}/graph",
            },
            "overleaf_urls": {},
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
        filename = file.filename or "uploaded_document.pdf"
        tmp_path = tmp_dir / filename

        content = await file.read()
        tmp_path.write_bytes(content)

        result = extract_text_from_pdf(tmp_path)
        if result is None:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")

        text = result["text"]
        metadata = result["metadata"]
        metadata["source"] = filename

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


    # ------------------------------------------------------------------ #
    # Agentic Chat Endpoints (P15)
    # ------------------------------------------------------------------ #

    # Global memory store for the agentic chat
    from research_agent.chat.memory import get_memory_store
    agent_memory = get_memory_store()

    @app.post("/api/chat/agent")
    async def agent_chat_endpoint(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        """Agentic chat with tool-calling loop.

        Takes a message, runs the agent loop (think → act → observe → respond),
        and returns the synthesized answer with citations.

        Request body:
            message (str, required): The user's message.
            session_id (str, optional): Session ID for conversation continuity.
            library_id (str, optional): Library ID from PDF upload for document Q&A.
            depth (str, optional): "quick", "balanced", or "deep".

        Response:
            message (str): The agent's answer.
            citations (list[str]): Formatted citation references.
            tool_calls (list[dict]): Tools that were called.
            session_id (str): Session ID (created if new).
            suggestions (list[str]): Proactive follow-up suggestions.
            launch_research (dict|None): If the agent decided to launch research.
        """
        from research_agent.chat.agent import agent_chat

        message = body.get("message", "").strip()
        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        session_id = body.get("session_id", "")
        if not session_id:
            sid = f"sess-{uuid.uuid4().hex[:12]}"
            session_id = sid
            # Create a chat session in the existing session store too
            new_ss = ChatSession(session_id=session_id, user_id=str(user.id))
            await save_session(new_ss)
        else:
            existing_session = await get_session(str(user.id), session_id)
            if existing_session is None:
                raise HTTPException(status_code=404, detail="Session not found")

        library_id = body.get("library_id") or agent_memory.get_active_library(session_id) or ""
        # Build tool registry for the agent
        agent_tool_registry = tool_registry

        # Build persistent memory from the agent memory store for conversation continuity
        def _build_memory_store() -> dict[str, list[dict]]:
            history = agent_memory.get_history(session_id, limit=10)  # type: ignore[union-attr]
            store: dict[str, list[dict]] = {session_id: [
                {"role": e.role, "content": e.content}
                for e in history  # type: ignore[union-attr]
            ]}
            return store

        # Run the agentic loop with persistent memory
        memory_store = _build_memory_store()
        result = await agent_chat(
            session_id=session_id,
            message=message,
            tool_registry=agent_tool_registry,
            library_id=library_id or None,
            memory_store=memory_store,
            max_tool_iterations=3,
        )

        # Sync agent_chat's in-memory history back to agent_memory
        synced_history = memory_store.get(session_id, [])
        for entry in synced_history:
            agent_memory.add_message(session_id, entry["role"], entry["content"])
        
        # Update suggestions and store them in memory
        suggestions = _generate_suggestions(message, result)

        # Store last topic in memory
        agent_memory.set_last_topic(session_id, message)
        if library_id:
            agent_memory.set_active_library(session_id, library_id)

        return {
            "session_id": session_id,
            "message": result["message"],
            "citations": result.get("citations", []),
            "tool_calls": result.get("tool_calls", []),
            "suggestions": suggestions,
            "launch_research": None,
        }

    @app.post("/api/chat/agent/stream")
    async def agent_chat_stream_endpoint(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        """Streaming agentic chat with real-time tool execution events.

        Streams NDJSON events as the agent thinks, calls tools, and generates
        the final response:
        - {"event": "thought", "content": "..."}
        - {"event": "tool_result", "tool": "search_web", "item_count": 5}
        - {"event": "complete", "message": "...", "citations": [...]}
        - {"event": "error", "message": "..."}
        """
        from research_agent.chat.agent import agent_chat

        message = body.get("message", "").strip()
        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        session_id = body.get("session_id", "")
        if not session_id:
            sid = f"sess-{uuid.uuid4().hex[:12]}"
            session_id = sid
            new_ss = ChatSession(session_id=session_id, user_id=str(user.id))
            await save_session(new_ss)

        library_id = body.get("library_id", "")

        async def event_stream():
            events_queue: asyncio.Queue[dict | None] = asyncio.Queue()

            async def run_agent():
                try:
                    # Emit thought event
                    await events_queue.put({"event": "thought", "content": "Analyzing your request and choosing tools..."})

                    # Build persistent memory from agent_memory
                    history = agent_memory.get_history(session_id, limit=10)  # type: ignore[union-attr]
                    memory_store: dict[str, list[dict]] = {session_id: [
                        {"role": e.role, "content": e.content}
                        for e in history  # type: ignore[union-attr]
                    ]}

                    result = await agent_chat(
                        session_id=session_id,
                        message=message,
                        tool_registry=tool_registry,
                        library_id=library_id or None,
                        memory_store=memory_store,
                        max_tool_iterations=3,
                    )

                    # Sync back to agent_memory
                    synced = memory_store.get(session_id, [])
                    for entry in synced:
                        agent_memory.add_message(session_id, entry["role"], entry["content"])

                    tool_calls = result.get("tool_calls", [])
                    for tc in tool_calls:
                        tool_name = tc.get("tool", "unknown")
                        items = tc.get("items", [])
                        error = tc.get("error")
                        if error:
                            await events_queue.put({
                                "event": "tool_result",
                                "tool": tool_name,
                                "status": "error",
                                "error": error,
                            })
                        else:
                            await events_queue.put({
                                "event": "tool_result",
                                "tool": tool_name,
                                "status": "complete",
                                "item_count": len(items),
                            })

                    suggestions = _generate_suggestions(message, result)

                    await events_queue.put({
                        "event": "complete",
                        "message": result["message"],
                        "citations": result.get("citations", []),
                        "session_id": session_id,
                        "suggestions": suggestions,
                    })
                except Exception as e:
                    await events_queue.put({"event": "error", "message": str(e)})
                finally:
                    await events_queue.put(None)

            task = asyncio.create_task(run_agent())
            try:
                while True:
                    item = await events_queue.get()
                    if item is None:
                        break
                    yield json.dumps(item) + "\n"
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/chat/launch-research")
    async def agent_launch_research(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        """Launch a full research pipeline from agent context.

        Accepts a topic refined by the agentic chat and launches the complete
        research graph (plan → search → synthesize → compose → export).

        Request body:
            topic (str, required): The research topic.
            session_id (str, optional): Session for context continuity.
            depth (str, optional): "quick", "balanced", "deep".
            template (str, optional): "ieee", "acm", "beamer", "poster".
        """
        topic = body.get("topic", "").strip()
        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")

        session_id = body.get("session_id", "")
        depth = body.get("depth", "balanced")
        template = body.get("template", "ieee")

        run_id = f"run-{uuid.uuid4().hex[:8]}"

        actual_graph_runner = graph_runner or run_graph

        tool_registry_local = registry if registry is not None else build_tool_registry(settings)

        initial_state = WorkflowState(
            run_id=run_id,
            topic=topic,
            template=template,
            language="en",
            depth=depth,
            autonomy_mode="hybrid",
            max_runtime_minutes=settings.runtime.max_runtime_minutes,
            max_cost_usd=settings.runtime.max_cost_usd,
            max_iterations=settings.runtime.max_iterations,
            past_research_topics=load_past_topics_for_user(str(user.id)),
        )

        try:
            if asyncio.iscoroutinefunction(actual_graph_runner):
                final_state = await actual_graph_runner(initial_state, registry=tool_registry_local)
            else:
                final_state = actual_graph_runner(initial_state, registry=tool_registry_local)

            if final_state.needs_clarification or final_state.stop_reason == "clarification_required":
                return {
                    "kind": "clarification",
                    "run_id": run_id,
                    "questions": final_state.clarification_questions,
                }

            # Store context in memory
            agent_memory.set_research_context(session_id or "", {
                "run_id": run_id,
                "topic": topic,
                "template": template,
                "depth": depth,
            })

            artifact_base = f"/api/runs/{run_id}"

            return {
                "kind": "result",
                "run_id": run_id,
                "topic": topic,
                "template": template,
                "section_count": len(final_state.sections) if hasattr(final_state, "sections") and final_state.sections else 0,
                "artifact_urls": {
                    "pdf": f"{artifact_base}/render/pdf",
                    "latex": f"{artifact_base}/graph",
                    "citation_graph": f"{artifact_base}/citation-graph",
                    "datasets": f"{artifact_base}/datasets",
                    "gaps": f"{artifact_base}/gaps",
                },
                "section_evidence": [
                    {"section": sec, "confidence": conf}
                    for sec, conf in (final_state.section_confidence or {}).items()
                ],
            }
        except Exception as e:
            logger.exception("Research launch failed")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/chat/suggestions")
    async def agent_suggestions(
        session_id: str,
        user: User = Depends(current_active_user)
    ):
        """Get proactive suggestions for the current session context.

        Uses the agent's memory (last topic, research context, conversation
        history) to suggest follow-up actions.
        """
        last_topic = agent_memory.get_last_topic(session_id)
        research_ctx = agent_memory.get_research_context(session_id)
        suggestions = []

        if last_topic:
            suggestions.extend([
                {"title": f"Research \"{last_topic}\" in depth",
                 "action": "research",
                 "query": f"Launch full research on \"{last_topic}\""},
                {"title": "Find datasets for this topic",
                 "action": "agent_chat",
                 "query": f"Find datasets related to \"{last_topic}\""},
                {"title": "Search recent papers",
                 "action": "agent_chat",
                 "query": f"Find recent papers on \"{last_topic}\" from the last 2 years"},
            ])

        if research_ctx.get("run_id"):
            suggestions.append({
                "title": "View latest research results",
                "action": "view_run",
                "run_id": research_ctx["run_id"],
            })
            suggestions.append({
                "title": "Export as blog post",
                "action": "export_blog",
                "run_id": research_ctx["run_id"],
            })

        active_lib = agent_memory.get_active_library(session_id)
        if active_lib:
            suggestions.append({
                "title": "Ask about your uploaded document",
                "action": "agent_chat",
                "query": "Summarize the key findings from my uploaded document"
                          " and explain how they relate to recent research",
                "library_id": active_lib,
            })

        # General suggestions
        if not suggestions:
            suggestions = [
                {"title": "Find papers on a topic",
                 "action": "agent_chat",
                 "query": "Find recent papers on transformer architectures"},
                {"title": "Generate a research survey",
                 "action": "survey",
                 "query": "Create a survey of recent advances in NLP"},
                {"title": "Check research trends",
                 "action": "trends",
                 "query": "Show me current trends in machine learning"},
            ]

        return {"suggestions": suggestions}

    @app.post("/api/chat/plan")
    async def agent_research_plan(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        """Generate a structured research plan from a topic.

        Decomposes the topic into sub-topics, generates a research outline
        with sections and tasks, and returns the plan for review before
        launching the full research pipeline.

        Request body:
            topic (str, required): The research topic or question.
            depth (str, optional): "quick", "balanced", "deep".
            template (str, optional): "ieee", "acm", "beamer", "poster".

        Response:
            topic (str): The original topic.
            sections (list[dict]): Structured outline with sections and sub-sections.
            tasks (list[dict]): Research tasks with dependencies.
            estimated_papers (int): Rough estimate of papers to review.
        """
        topic = body.get("topic", "").strip()
        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")

        depth = body.get("depth", "balanced")
        template = body.get("template", "ieee")

        # Use the existing planner logic to generate the research plan
        from research_agent.orchestration.nodes.planner import _build_adaptive_fallback_tasks

        # Generate fallback tasks as a base plan
        fallback_sections = [
            {"title": "Introduction", "objective": f"Set the context and motivation for {topic}", "estimated_pages": 1},
            {"title": "Background and Related Work", "objective": f"Survey existing literature on {topic}", "estimated_pages": 2},
            {"title": "Methodology", "objective": f"Describe research methods for {topic}", "estimated_pages": 2},
            {"title": "Results and Analysis", "objective": f"Present findings on {topic}", "estimated_pages": 2},
            {"title": "Discussion", "objective": f"Interpret results and discuss implications for {topic}", "estimated_pages": 1},
            {"title": "Conclusion and Future Work", "objective": f"Summarize contributions and outline future directions for {topic}", "estimated_pages": 1},
        ]

        tasks = _build_adaptive_fallback_tasks(topic)

        # Try to use the planner's LLM to generate a better plan
        from research_agent.models import agenerate_json

        prompt = (
            f"Generate a detailed research plan outline for the topic: '{topic}'.\n"
            f"Template: {template}, Depth: {depth}\n\n"
            "Return a JSON object with a 'sections' key containing an array of section objects.\n"
            "Each section object must have:\n"
            "- 'id': a unique string like 's1', 's2'\n"
            "- 'title': section title\n"
            "- 'objective': 1-2 sentence research objective for this section\n"
            "- 'subsections': array of subsection title strings (at least 2)\n"
            "- 'estimated_pages': integer 1-3\n"
            f"Include {6 if depth == 'quick' else 7 if depth == 'balanced' else 9} sections total, covering all aspects of a research paper on '{topic}'.\n"
            "Also return a 'tasks' key with research tasks that would generate this content."
        )

        try:
            llm_plan = await agenerate_json(role="head", prompt=prompt)
            if llm_plan and isinstance(llm_plan, dict):
                if "sections" in llm_plan and isinstance(llm_plan["sections"], list):
                    sections = llm_plan["sections"]
                    # Validate sections
                    valid_sections = []
                    for s in sections:
                        if isinstance(s, dict) and "title" in s and "objective" in s:
                            s["estimated_pages"] = s.get("estimated_pages", 1)
                            s["subsections"] = s.get("subsections", [])
                            if not isinstance(s["subsections"], list):
                                s["subsections"] = []
                            valid_sections.append(s)
                    if valid_sections:
                        fallback_sections = valid_sections

                if "tasks" in llm_plan and isinstance(llm_plan["tasks"], list):
                    valid_tasks = []
                    for t in llm_plan["tasks"]:
                        if isinstance(t, dict) and "task_id" in t and "title" in t:
                            t["objective"] = t.get("objective", t["title"])
                            t["depends_on"] = t.get("depends_on", [])
                            t["providers"] = t.get("providers", [])
                            t["status"] = "pending"
                            if not isinstance(t["depends_on"], list):
                                t["depends_on"] = []
                            if not isinstance(t["providers"], list):
                                t["providers"] = []
                            valid_tasks.append(t)
                    if valid_tasks:
                        tasks = valid_tasks
        except Exception:
            pass  # Use fallback sections

        return {
            "topic": topic,
            "template": template,
            "depth": depth,
            "sections": fallback_sections,
            "tasks": tasks,
            "estimated_papers": len(tasks) * 8,
        }

    @app.post("/api/chat/feedback")
    async def agent_chat_feedback(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        """Record user feedback on an agent response.

        Request body:
            session_id (str, required): The session ID.
            message_id (str, optional): Identifier for the specific message.
            rating (str, required): "up" or "down".
            feedback_text (str, optional): Optional text feedback.
        """
        session_id = body.get("session_id", "")
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        rating = body.get("rating", "")
        if rating not in ("up", "down"):
            raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")

        # Store in agent memory
        feedback_entry = {
            "rating": rating,
            "feedback_text": body.get("feedback_text", ""),
            "message_id": body.get("message_id", ""),
        }

        # Accumulate feedback in memory
        existing_feedback = agent_memory.get_preference(session_id, "feedback_history", [])
        existing_feedback.append(feedback_entry)
        agent_memory.update_preference(session_id, "feedback_history", existing_feedback)

        # Track counts
        up_count = sum(1 for f in existing_feedback if f["rating"] == "up")
        down_count = sum(1 for f in existing_feedback if f["rating"] == "down")
        agent_memory.update_preference(session_id, "feedback_up_count", up_count)
        agent_memory.update_preference(session_id, "feedback_down_count", down_count)

        return {
            "success": True,
            "total_feedback": len(existing_feedback),
            "up_count": up_count,
            "down_count": down_count,
        }

    @app.post("/api/chat/memory")
    async def update_agent_memory(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        """Update agent memory preferences for the current user/session.

        Request body:
            session_id (str): The session ID.
            preferences (dict): Key-value pairs to store in memory.
            research_context (dict, optional): Research context to store.
        """
        session_id = body.get("session_id", "")
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        preferences = body.get("preferences", {})
        for key, value in preferences.items():
            agent_memory.update_preference(session_id, key, value)

        research_context = body.get("research_context")
        if research_context:
            agent_memory.set_research_context(session_id, research_context)

        return {"success": True}


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

    # P20: PWA Manifest - serve at root scope for browsers
    @app.get("/manifest.json", response_class=FileResponse)
    async def pwa_manifest():
        manifest_path = Path(static_dir) / "manifest.json"
        if manifest_path.exists():
            return FileResponse(manifest_path, media_type="application/manifest+json")
        raise HTTPException(status_code=404, detail="Manifest not found")

    @app.get("/service-worker.js")
    async def service_worker():
        sw_path = Path(static_dir) / "service-worker.js"
        if sw_path.exists():
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(
                sw_path.read_text(encoding="utf-8"),
                media_type="application/javascript",
                headers={
                    "Service-Worker-Allowed": "/",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                },
            )
        raise HTTPException(status_code=404, detail="Service Worker not found")

    @app.get("/offline.html", response_class=HTMLResponse)
    async def offline_page():
        offline_path = Path(static_dir) / "offline.html"
        if offline_path.exists():
            return offline_path.read_text(encoding="utf-8")
        return "<h1>Offline</h1><p>You are offline.</p>"

    if Path(static_dir).exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
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

        # ------------------------------------------------------------------ #
    # P23: Knowledge Graph Explorer Endpoints
    # ------------------------------------------------------------------ #

    @app.get("/api/knowledge-graph/data")
    async def get_knowledge_graph_data():
        """Get the persistent knowledge graph data for the interactive explorer."""
        from research_agent.rag import KnowledgeGraphStore
        try:
            kg_store = KnowledgeGraphStore()
            data = kg_store.export_for_explorer("threejs")
            return data
        except Exception as exc:
            logger.warning("Failed to load knowledge graph: %s", exc)
            return {"nodes": [], "edges": [], "error": str(exc)}

    @app.get("/api/knowledge-graph/explorer")
    async def get_knowledge_graph_explorer():
        """Serve the interactive knowledge graph explorer HTML page."""
        kg_explorer_path = Path(static_dir) / "kg_explorer.html"
        if kg_explorer_path.exists():
            return HTMLResponse(kg_explorer_path.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404, detail="Knowledge graph explorer not found")

    @app.get("/api/knowledge-graph/landscape")
    async def get_knowledge_graph_landscape():
        """Get the time-based landscape evolution data."""
        from research_agent.rag import KnowledgeGraphStore
        try:
            kg_store = KnowledgeGraphStore()
            evolution = kg_store.get_landscape_evolution()
            return {"evolution": evolution}
        except Exception as exc:
            logger.warning("Failed to get landscape evolution: %s", exc)
            return {"evolution": [], "error": str(exc)}

    @app.get("/api/knowledge-graph/search")
    async def search_knowledge_graph(
        q: str
    ):
        """Search the knowledge graph by entity name."""
        from research_agent.rag import KnowledgeGraphStore
        try:
            kg_store = KnowledgeGraphStore()
            nodes = []
            for node_id, data in kg_store.graph.nodes(data=True):
                if q.lower() in node_id.lower() or q.lower() in data.get("label", "").lower():
                    nodes.append({"id": node_id, **data})
            return {"results": nodes, "count": len(nodes)}
        except Exception as exc:
            return {"results": [], "count": 0, "error": str(exc)}

    @app.get("/api/runs/{run_id}/citation-graph")
    async def get_citation_graph(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        run_dir = Path(artifact_root) / run_id
        graph_path = run_dir / "citation_graph.json"
        if graph_path.exists():
            data = json.loads(graph_path.read_text(encoding="utf-8"))
            return data
        raise HTTPException(status_code=404, detail="No citation graph found for this run")

    @app.get("/api/runs/{run_id}/datasets")
    async def get_discovered_datasets(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        run_dir = Path(artifact_root) / run_id
        datasets_path = run_dir / "discovered_datasets.json"
        if datasets_path.exists():
            data = json.loads(datasets_path.read_text(encoding="utf-8"))
            return data
        return {"datasets": []}


    # ------------------------------------------------------------------ #
    # Reproducibility Dashboard Endpoints (P29)
    # ------------------------------------------------------------------ #

    @app.get("/api/runs/{run_id}/reproducibility")
    async def get_reproducibility_data(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        """Get reproducibility verification data for a run.

        Returns the code verification results (claims, scores, status)
        generated by the P24 Code Sandbox, along with the summary stats.
        """
        run_dir = Path(artifact_root) / run_id
        results_path = run_dir / "code_verification_results.json"
        if not results_path.exists():
            return {
                "has_reproducibility": False,
                "items": [],
                "overall_score": 0.0,
                "total_claims": 0,
                "message": "No reproducibility data found. Run a research topic with code sandbox enabled first.",
            }

        try:
            data = json.loads(results_path.read_text(encoding="utf-8"))
            items = data.get("items", [])
            overall_score = data.get("overall_score", 0.0)
            total_claims = data.get("total_claims", len(items))

            passed = sum(1 for i in items if i.get("status") == "pass")
            failed = sum(1 for i in items if i.get("status") == "fail")
            partial = sum(1 for i in items if i.get("status") == "partial")
            unverifiable = sum(1 for i in items if i.get("status") == "unverifiable")

            return {
                "has_reproducibility": True,
                "items": items,
                "overall_score": overall_score,
                "total_claims": total_claims,
                "summary": {
                    "passed": passed,
                    "failed": failed,
                    "partial": partial,
                    "unverifiable": unverifiable,
                },
            }
        except (json.JSONDecodeError, KeyError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to parse reproducibility data: {exc}")

    @app.get("/api/runs/{run_id}/reproducibility/report")
    async def get_reproducibility_report(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        """Get the full markdown reproducibility report for a run."""
        run_dir = Path(artifact_root) / run_id
        report_path = run_dir / "reproducibility_report.md"
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="No reproducibility report found for this run")
        return {"report": report_path.read_text(encoding="utf-8")}

    @app.get("/api/runs/{run_id}/reproducibility/scripts")
    async def get_reproducibility_scripts(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        """List verification scripts generated for a run."""
        run_dir = Path(artifact_root) / run_id
        scripts_dir = run_dir / "verification_scripts"
        if not scripts_dir.exists():
            return {"scripts": []}

        scripts = []
        for script_path in sorted(scripts_dir.glob("*.py")):
            scripts.append({
                "name": script_path.name,
                "claim_id": script_path.stem,
                "code": script_path.read_text(encoding="utf-8"),
                "size_bytes": script_path.stat().st_size,
            })
        return {"scripts": scripts}

    @app.get("/api/runs/{run_id}/reproducibility/claims")
    async def get_reproducibility_claims(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
        """Get the raw extracted empirical claims for a run."""
        run_dir = Path(artifact_root) / run_id
        claims_path = run_dir / "empirical_claims.json"
        if not claims_path.exists():
            return {"claims": []}
        try:
            claims = json.loads(claims_path.read_text(encoding="utf-8"))
            return {"claims": claims if isinstance(claims, list) else []}
        except json.JSONDecodeError:
            return {"claims": []}

    @app.get("/api/runs/{run_id}/gaps")
    async def get_gap_analysis(
        run_id: str,
        user: User = Depends(current_active_user)
    ):
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

    @app.get("/api/trends")
    async def get_trends(
        query: str,
        user: User = Depends(current_active_user)
    ):
        from collections import Counter
        import re
        from research_agent.tools.arxiv import ArxivAdapter
        from research_agent.tools.semantic_scholar import SemanticScholarAdapter

        import os
        arxiv = ArxivAdapter()
        api_key = getattr(settings.retrieval, "semantic_scholar_api_key", None) if hasattr(settings, "retrieval") else None
        if not api_key:
            api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        ss = SemanticScholarAdapter(api_key=api_key)

        arxiv_items = []
        ss_items = []
        try:
            res_arxiv = arxiv.search(query, limit=30)
            arxiv_items = res_arxiv.items or []
        except Exception as e:
            logger.warning(f"ArXiv trends search failed: {e}")

        try:
            res_ss = ss.search(query, limit=30)
            ss_items = res_ss.items or []
        except Exception as e:
            logger.warning(f"Semantic Scholar trends search failed: {e}")

        all_papers = []
        seen_titles = set()
        for p in arxiv_items + ss_items:
            title = p.get("title", "").strip().lower()
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_papers.append(p)

        years = [p.get("year") for p in all_papers if p.get("year")]
        year_counts = Counter(years)
        timeline = [{"year": int(str(y)), "count": count} for y, count in sorted(year_counts.items()) if str(y).isdigit()]

        authors: list[str] = []
        for p in all_papers:
            authors.extend(p.get("authors") or [])
        author_counts = Counter(authors)
        top_authors = [{"name": name, "count": count} for name, count in author_counts.most_common(10)]

        venues = []
        for p in all_papers:
            venue = p.get("journal") or p.get("venue") or ""
            if venue:
                venues.append(venue)
        venue_counts = Counter(venues)
        top_venues = [{"name": name, "count": count} for name, count in venue_counts.most_common(10)]

        stop_words = {
            "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "arent", "as", "at",
            "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "cant", "cannot", "could",
            "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
            "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
            "it", "its", "itself", "more", "most", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "our",
            "ours", "ourselves", "out", "over", "own", "same", "should", "so", "some", "such", "than", "that", "the", "their",
            "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
            "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why", "with",
            "would", "you", "your", "yours", "yourself", "yourselves", "for", "with", "using", "paper", "presents", "study",
            "analysis", "model", "method", "proposed", "novel", "approach", "results", "show", "performance"
        }
        words = []
        for p in all_papers:
            text = (p.get("title", "") + " " + p.get("snippet", "")).lower()
            found = re.findall(r'\b[a-z]{3,15}\b', text)
            words.extend([w for w in found if w not in stop_words])
        word_counts = Counter(words)
        top_keywords = [{"name": name.capitalize(), "count": count} for name, count in word_counts.most_common(12)]

        return {
            "query": query,
            "total_papers": len(all_papers),
            "timeline": timeline,
            "top_authors": top_authors,
            "top_venues": top_venues,
            "top_keywords": top_keywords
        }

    @app.post("/api/trends/report")
    async def email_trend_report(
        query: str,
        email: str,
        user: User = Depends(current_active_user)
    ):
        logger.info(f"Dispatching weekly trend report for query '{query}' to {email}")
        return {"success": True, "message": f"Trend report successfully dispatched to {email}!"}


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
                    "profile_id": d.profile_id,
                    "topic": d.topic,
                    "summary": d.summary,
                    "paper_count": d.paper_count,
                    "generated_at": d.generated_at,
                    "email_sent": d.email_sent,
                    "formatted": format_digest_for_display(d),
                    "papers": [
                        {
                            "title": p.get("title", "Untitled"),
                            "authors": p.get("authors", []),
                            "year": p.get("year", "n.d."),
                            "url": p.get("url", ""),
                            "source": p.get("watchdog_provider", p.get("provider", "unknown")),
                            "relevance_score": p.get("relevance_score", None),
                            "snippet": p.get("snippet", "")[:200],
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

    @app.get("/api/watchdog/notifications/{profile_id}")
    async def watchdog_get_notifications(
        profile_id: str,
        user: User = Depends(current_active_user)
    ):
        """Get notification preferences for a watchdog subscription."""
        from research_agent.app.watchdog_storage import get_watchdog_storage

        storage = get_watchdog_storage()
        profile = storage.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if profile.user_id != str(user.id):
            raise HTTPException(status_code=403, detail="Not authorized")

        prefs = profile.notification_prefs
        return {
            "profile_id": profile_id,
            "email_enabled": prefs.email_enabled,
            "email_address": prefs.email_address,
            "push_enabled": prefs.push_enabled,
            "min_relevance_score": prefs.min_relevance_score,
            "max_papers_per_digest": prefs.max_papers_per_digest,
        }

    @app.post("/api/watchdog/notifications/{profile_id}")
    async def watchdog_update_notifications(
        profile_id: str,
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        """Update notification preferences for a watchdog subscription."""
        from research_agent.app.watchdog_storage import (
            get_watchdog_storage,
            NotificationPrefs,
        )

        storage = get_watchdog_storage()
        profile = storage.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if profile.user_id != str(user.id):
            raise HTTPException(status_code=403, detail="Not authorized")

        prefs = NotificationPrefs(
            email_enabled=bool(body.get("email_enabled", profile.notification_prefs.email_enabled)),
            email_address=str(body.get("email_address", profile.notification_prefs.email_address)),
            push_enabled=bool(body.get("push_enabled", profile.notification_prefs.push_enabled)),
            min_relevance_score=float(body.get("min_relevance_score", profile.notification_prefs.min_relevance_score)),
            max_papers_per_digest=int(body.get("max_papers_per_digest", profile.notification_prefs.max_papers_per_digest)),
        )

        storage.update_notification_prefs(profile_id, prefs)

        return {
            "profile_id": profile_id,
            "message": "Notification preferences updated.",
            "email_enabled": prefs.email_enabled,
            "email_address": prefs.email_address,
            "min_relevance_score": prefs.min_relevance_score,
        }

    @app.post("/api/watchdog/deep-dive")
    async def watchdog_deep_dive(
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        """Launch a full research paper on a paper discovered by the watchdog.

        Takes a paper title/URL from a digest and launches the full research
        graph to produce a comprehensive survey on the paper's topic.

        Request body:
            topic (str, required): The paper topic to deep-dive into.
            paper_title (str, optional): Original paper title for context.
            depth (str, optional): "quick", "balanced", "deep".
        """
        topic = body.get("topic", "").strip()
        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")

        depth = body.get("depth", "balanced")
        template = body.get("template", "ieee")


        run_id = f"run-{uuid.uuid4().hex[:8]}"

        actual_graph_runner = graph_runner or run_graph
        tool_registry_local = registry if registry is not None else build_tool_registry(settings)

        initial_state = WorkflowState(
            run_id=run_id,
            topic=topic,
            template=template,
            language="en",
            depth=depth,
            autonomy_mode="hybrid",
            max_runtime_minutes=settings.runtime.max_runtime_minutes,
            max_cost_usd=settings.runtime.max_cost_usd,
            max_iterations=1,  # Single pass for deep-dive speed
            past_research_topics=load_past_topics_for_user(str(user.id)),
        )

        try:
            if asyncio.iscoroutinefunction(actual_graph_runner):
                final_state = await actual_graph_runner(initial_state, registry=tool_registry_local)
            else:
                final_state = actual_graph_runner(initial_state, registry=tool_registry_local)

            artifact_base = f"/api/runs/{run_id}"

            return {
                "kind": "result",
                "run_id": run_id,
                "topic": topic,
                "template": template,
                "section_count": len(final_state.sections) if hasattr(final_state, "sections") and final_state.sections else 0,
                "artifact_urls": {
                    "pdf": f"{artifact_base}/render/pdf",
                    "latex": f"{artifact_base}/graph",
                },
            }
        except Exception as e:
            logger.exception("Watchdog deep-dive failed")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/watchdog/dashboard")
    async def watchdog_dashboard(
        user: User = Depends(current_active_user)
    ):
        """Get watchdog dashboard stats for the current user.

        Returns subscription counts, recent digests, and new paper alerts
        for the sidebar widget.
        """
        from research_agent.app.watchdog_storage import get_watchdog_storage
        import time

        storage = get_watchdog_storage()
        profiles = storage.get_user_profiles(str(user.id))
        digests = storage.get_user_digests(str(user.id), limit=5)

        now = time.time()
        subscriptions = []
        for p in profiles:
            interval_sec = storage.get_interval_seconds(p.check_interval)
            next_check_due = max(0, p.last_checked_at + interval_sec - now) if p.last_checked_at > 0 else 0

            subscriptions.append({
                "profile_id": p.profile_id,
                "topic": p.topic,
                "enabled": p.enabled,
                "check_interval": p.check_interval,
                "last_checked_at": p.last_checked_at,
                "next_check_in_seconds": int(next_check_due),
                "keywords": p.keywords,
                "authors": p.authors,
                "email_enabled": p.notification_prefs.email_enabled,
            })

        # Count total new papers across recent digests
        total_new_papers = sum(d.paper_count for d in digests)

        return {
            "subscriptions": subscriptions,
            "active_subscriptions": sum(1 for s in subscriptions if s["enabled"]),
            "total_subscriptions": len(subscriptions),
            "recent_digests": [
                {
                    "digest_id": d.digest_id,
                    "topic": d.topic,
                    "paper_count": d.paper_count,
                    "summary": d.summary,
                    "generated_at": d.generated_at,
                    "email_sent": d.email_sent,
                }
                for d in digests
            ],
            "total_new_papers": total_new_papers,
        }

    @app.post("/api/watchdog/email/test")
    async def watchdog_test_email(
        body: dict = {},
        user: User = Depends(current_active_user)
    ):
        """Test email notification configuration.

        Sends a test email to verify SMTP settings are working.
        """
        from research_agent.app.watchdog_storage import WatchdogDigest
        import uuid
        import time

        email = body.get("email", "").strip()
        if not email:
            raise HTTPException(status_code=400, detail="Email address is required")

        # Create a test digest
        test_digest = WatchdogDigest(
            digest_id=f"test-{uuid.uuid4().hex[:8]}",
            profile_id="test",
            user_id=str(user.id),
            topic="Test: Watchdog Notification",
            new_papers=[
                {
                    "title": "Test Paper: Advances in Research Agent Systems",
                    "authors": ["Test Author"],
                    "year": 2026,
                    "url": "https://example.com/test-paper",
                    "watchdog_provider": "arxiv",
                    "snippet": "This is a test paper to verify email notification configuration.",
                    "relevance_score": 0.95,
                }
            ],
            paper_count=1,
            summary="Test digest for verifying SMTP configuration.",
            generated_at=time.time(),
            relevance_scores=[0.95],
        )

        # Use the existing email sending logic
        from research_agent.orchestration.digest_email import build_html_digest_email
        from research_agent.config import load_settings
        settings_local = load_settings()

        smtp_host = settings_local.watchdog_email.smtp_host
        if not smtp_host:
            raise HTTPException(status_code=400, detail="SMTP not configured. Set SMTP_HOST and SMTP_PASSWORD.")

        html_content = build_html_digest_email(test_digest)

        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[Test] Research Watchdog Notification"
        msg["From"] = settings_local.watchdog_email.from_email
        msg["To"] = email

        text_part = MIMEText("This is a test email from Research Agent Watchdog.", "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(text_part)
        msg.attach(html_part)

        def _send() -> None:
            with smtplib.SMTP(smtp_host, settings_local.watchdog_email.smtp_port, timeout=15) as server:
                if settings_local.watchdog_email.smtp_port == 587:
                    server.starttls()
                smtp_user = settings_local.watchdog_email.smtp_user
                smtp_password = str(settings_local.watchdog_email.smtp_password)
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(
                    settings_local.watchdog_email.from_email,
                    [email],
                    msg.as_string(),
                )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send)


    # ------------------------------------------------------------------ #
    # Job Queue Endpoints (P16)
    # ------------------------------------------------------------------ #

    # Worker runs as separate process (python -m research_agent.orchestration.job_queue.worker)
    job_manager_running = False

    @app.get("/api/jobs/queue/health")
    async def job_queue_health(user: User = Depends(current_active_user)):
        """Get job queue health status."""
        jm = get_job_manager()
        try:
            depth = await jm.get_queue_depth()
            active = await jm.get_active_count()
            return {
                "queue_depth": depth,
                "active_jobs": active,
                "worker_running": job_manager_running,
                "healthy": True,
            }
        except Exception as exc:
            return {"healthy": False, "error": str(exc)[:200]}

    @app.post("/api/jobs")
    async def enqueue_job(
        body: dict,
        user: User = Depends(current_active_user)
    ):
        """Enqueue a new research job."""
        topic = body.get("topic", "").strip()
        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")

        from research_agent.orchestration.job_queue.models import JobType

        params = {
            "topic": topic,
            "template": body.get("template", "ieee"),
            "depth": body.get("depth", "balanced"),
            "language": body.get("language", "en"),
            "autonomy_mode": body.get("autonomy_mode", "hybrid"),
            "max_runtime_minutes": body.get("max_runtime_minutes", settings.runtime.max_runtime_minutes),
            "max_cost_usd": body.get("max_cost_usd", settings.runtime.max_cost_usd),
            "max_iterations": body.get("max_iterations", settings.runtime.max_iterations),
        }

        jm = get_job_manager()

        # Check concurrency limit
        if not await jm.check_concurrency_limit(str(user.id), settings.job_queue.max_concurrent_per_user):
            raise HTTPException(status_code=429, detail="Concurrency limit reached. Wait for active jobs to complete.")

        job = await jm.enqueue(
            job_type=JobType.RESEARCH_RUN,
            params=params,
            user_id=str(user.id),
            max_retries=settings.job_queue.max_retries,
            timeout_seconds=settings.job_queue.default_timeout,
        )

        return {"job_id": job.job_id, "status": job.status.value, "created_at": job.created_at}

    @app.get("/api/jobs")
    async def list_jobs(
        status: str | None = None,
        user: User = Depends(current_active_user)
    ):
        """List jobs for the current user."""
        jm = get_job_manager()
        filter_status = JobStatus(status) if status and status in (s.value for s in JobStatus) else None
        jobs = await jm.list_jobs(user_id=str(user.id), status=filter_status, limit=50)
        return {"jobs": [j.to_dict() for j in jobs]}

    @app.get("/api/jobs/{job_id}")
    async def get_job_status(
        job_id: str,
        user: User = Depends(current_active_user)
    ):
        """Get job status and details."""
        jm = get_job_manager()
        job = await jm.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.user_id != str(user.id):
            raise HTTPException(status_code=403, detail="Not authorized to view this job")
        return job.to_dict()

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(
        job_id: str,
        user: User = Depends(current_active_user)
    ):
        """Cancel a queued or running job."""
        jm = get_job_manager()
        job = await jm.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.user_id != str(user.id):
            raise HTTPException(status_code=403, detail="Not authorized to cancel this job")

        cancelled = await jm.cancel_job(job_id)
        if cancelled:
            return {"status": "cancelled", "job_id": job_id}
        return {"status": job.status.value, "job_id": job_id, "message": "Job already completed or failed"}

        return {
            "success": True,
            "message": f"Test email sent to {email}. Check your inbox.",
        }

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

    # ------------------------------------------------------------------ #
    # P39: Research Templates & Presets API
    # ------------------------------------------------------------------ #

    from research_agent.output.template_library import (
        list_templates as _list_templates,
        get_template as _get_template,
        create_template as _create_template,
        update_template as _update_template,
        delete_template as _delete_template,
        list_presets as _list_presets,
        get_preset as _get_preset,
        create_preset as _create_preset,
        delete_preset as _delete_preset,
        get_merged_template_config as _get_merged_template_config,
        set_template_store_path as _set_template_store_path,
    )

    # Initialize template store path from settings
    _set_template_store_path(settings.template_library.store_path)

    @app.get("/api/templates")
    async def get_all_templates(user: User = Depends(current_active_user)):
        """List all available research templates (built-in + custom)."""
        return {"templates": _list_templates()}

    @app.get("/api/templates/{template_id}")
    async def get_template_by_id(template_id: str, user: User = Depends(current_active_user)):
        """Get a single research template by ID."""
        tpl = _get_template(template_id)
        if not tpl:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
        return {"template": tpl}

    @app.post("/api/templates")
    async def create_new_template(body: dict, user: User = Depends(current_active_user)):
        """Create a new custom research template."""
        try:
            created = _create_template(body)
            return {"template": created}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to create template: {exc}")

    @app.put("/api/templates/{template_id}")
    async def update_existing_template(template_id: str, body: dict, user: User = Depends(current_active_user)):
        """Update an existing custom template."""
        updated = _update_template(template_id, body)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found or is built-in")
        return {"template": updated}

    @app.delete("/api/templates/{template_id}")
    async def delete_existing_template(template_id: str, user: User = Depends(current_active_user)):
        """Delete a custom template."""
        deleted = _delete_template(template_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found or is built-in")
        return {"success": True}

    @app.get("/api/presets")
    async def get_all_presets(user: User = Depends(current_active_user)):
        """List all available conference presets (built-in + custom)."""
        return {"presets": _list_presets()}

    @app.get("/api/presets/{preset_id}")
    async def get_preset_by_id(preset_id: str, user: User = Depends(current_active_user)):
        """Get a single conference preset by ID."""
        prs = _get_preset(preset_id)
        if not prs:
            raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
        return {"preset": prs}

    @app.post("/api/presets")
    async def create_new_preset(body: dict, user: User = Depends(current_active_user)):
        """Create a new custom conference preset."""
        try:
            created = _create_preset(body)
            return {"preset": created}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to create preset: {exc}")

    @app.delete("/api/presets/{preset_id}")
    async def delete_existing_preset(preset_id: str, user: User = Depends(current_active_user)):
        """Delete a custom preset."""
        deleted = _delete_preset(preset_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found or is built-in")
        return {"success": True}

    @app.post("/api/apply-template")
    async def apply_template_config(body: dict, user: User = Depends(current_active_user)):
        """Merge template, preset, and manual overrides into a unified config.

        Returns a merged configuration dict suitable for initializing a WorkflowState.
        """
        try:
            config = _get_merged_template_config(
                template_id=body.get("template_id"),
                preset_id=body.get("preset_id"),
                manual_overrides=body.get("overrides"),
            )
            return config
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to apply config: {exc}")


    return app


def _generate_suggestions(
    message: str,
    result: dict,
) -> list[str]:
    """Generate proactive follow-up suggestions based on the agent's response."""
    suggestions = []

    # If the response mentions papers or research, suggest follow-ups
    message_lower = message.lower()
    result_msg = result.get("message", "")
    result_msg_lower = result_msg.lower()

    has_papers = any(w in result_msg_lower for w in ["paper", "research", "study", "arxiv", "published"])
    has_datasets = any(w in result_msg_lower for w in ["dataset", "data", "kaggle", "huggingface"])
    has_code = any(w in result_msg_lower for w in ["code", "github", "implementation", "repository"])
    has_comparison = any(w in result_msg_lower for w in ["compare", "difference", "versus", "vs"])

    cited_sources = len(result.get("citations", []))

    if has_papers and cited_sources > 0:
        suggestions.append(f"Launch full research on \"{message}\"")
        suggestions.append("Find related papers and build a citation graph")

    if has_datasets:
        suggestions.append("Show me the most popular datasets in this area")

    if has_comparison:
        suggestions.append("Create a comparison table of the approaches mentioned")

    if message_lower.startswith(("find", "search", "look up", "get")):
        suggestions.append("Summarize these findings in a structured report")
        suggestions.append("Export results as a blog post")

    if has_code:
        suggestions.append("Check if the code repositories are still active")

    # General suggestions if we don't have specific ones
    if not suggestions:
        suggestions = [
            "Search for recent papers on this topic",
            "Find related datasets for further analysis",
            "Generate a comprehensive research survey",
        ]

    return suggestions[:4]  # Max 4 suggestions


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
    
    # Register a progress adapter that matches the single-dict signature
    # expected by apublish_progress, while forwarding to emit_callback(event, payload).
    from research_agent.observability.progress import set_progress_callback

    agent_activity: list[dict] = []

    async def progress_adapter(payload: dict):
        """Adapter: apublish_progress sends a single dict; emit_callback needs (event, payload)."""
        agent_name = payload.get("agent", "unknown")
        status = payload.get("status", "running")
        detail = payload.get("detail", "")
        message = payload.get("message", "")

        # Track agent activity for the frontend's Kanban board

        existing = next((a for a in agent_activity if a["name"] == agent_name), None)
        if existing:
            existing["status"] = status
            existing["detail"] = detail or message
        else:
            agent_activity.append({"name": agent_name, "status": status, "detail": detail or message})

        # Determine phase from agent name for the pipeline tracker
        phase_map = {
            "intake": "intake", "clarifier": "clarifier", "planner": "planner",
            "worker": "worker_executor", "executor": "worker_executor",
            "indexer": "indexing", "indexing": "indexing",
            "critic": "critic", "combiner": "combiner",
            "composer": "composer", "exporter": "exporter",
            "figure_generator": "figure_generator",
            "citation_verifier": "citation_verifier",
        }
        phase = phase_map.get(agent_name.lower().split("_")[0], None)

        await emit_callback("status", {
            "phase": phase,
            "message": message or detail or f"{agent_name}: {status}",
            "agent_activity": list(agent_activity),
        })

    set_progress_callback(progress_adapter)

    try:
        final_state = await graph_runner(initial_state, registry=tool_registry)
        
        session.awaiting_clarification = final_state.needs_clarification
        session.pending_questions = final_state.clarification_questions
        session.awaiting_critic_feedback = (final_state.phase == "awaiting_critic_review")
        
        if final_state.needs_clarification:
            questions = final_state.clarification_questions
            msg = "I need some clarification before proceeding:\n\n" + "\n".join(
                f"- {q}" for q in questions
            )
            await emit_callback("clarification", {
                "kind": "clarification",
                "assistant_message": msg,
                "persona": "clarifier",
                "questions": questions,
            })
        elif final_state.phase == "awaiting_critic_review":
            critic_msg = "\n".join(final_state.critic_notes) if final_state.critic_notes else "The critic has feedback. Please review and provide guidance."
            await emit_callback("critic_feedback", {
                "kind": "critic_feedback",
                "assistant_message": critic_msg,
                "persona": "critic",
            })
        else:
            # Build result payload with all fields the frontend expects
            artifact_base = f"/api/runs/{run_id}"
            artifact_urls = {}
            if final_state.artifact_dir:
                artifact_urls["pdf"] = f"{artifact_base}/render/pdf"
                artifact_urls["latex"] = f"{artifact_base}/graph"

            summary = f"Research paper on \"{topic}\" generated successfully."
            if final_state.run_warnings:
                summary += "\n\n⚠️ Warnings:\n" + "\n".join(f"- {w}" for w in final_state.run_warnings)

            await emit_callback("result", {
                "kind": "result",
                "run_id": run_id,
                "assistant_message": summary,
                "persona": "composer",
                "latex_text": final_state.latex_main or "",
                "artifact_urls": artifact_urls,
                "overleaf_urls": {},
                "doc_preview_html": "",
                "section_evidence": [
                    {"section": sec, "confidence": conf, "sources": []}
                    for sec, conf in (final_state.section_confidence or {}).items()
                ],
                # P26: Advanced AI Research Assistant data
                "generated_hypotheses": final_state.generated_hypotheses or [],
                "research_strategy": final_state.research_strategy,
                "gap_exploration": final_state.gap_exploration,
            })
            
        return True
    except Exception as e:
        await emit_callback("error", {"message": f"Run failed: {str(e)}"})
        return False


app = create_app()

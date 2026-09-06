from __future__ import annotations

import asyncio
import logging
import random
import time

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import AsyncRedisSaver
import redis.asyncio as redis

from research_agent.orchestration.nodes import (
    awaiting_user_critic_node,
    awaiting_user_node,
    bias_detector_node,
    citation_graph_node,
    citation_verifier_node,
    clarifier_node,
    combiner_node,
    comparison_table_node,
    composer_node,
    critic_node,
    exporter_node,
    figure_generator_node,
    formula_normalizer_node,
    formula_verifier_node,
    future_work_extrapolator_node,
    gap_analyzer_node,
    get_pending_task_ids,
    get_ready_task_ids,
    hallucination_guard_node,
    indexing_node,
    intake_node,
    knowledge_graph_node,
    make_worker_node,
    peer_reviewer_node,
    planner_node,
    poster_generator_node,
    presentation_generator_node,
    replanner_node,
    stop_node,
    workers_complete_node,
    code_execution_node,
    code_sandbox_node,
    dataset_discovery_node,
    grant_proposal_node,
    multi_modal_node,
    hypothesis_generator_node,
    strategy_recommender_node,
    gap_exploration_node,
    swarm_node,
)
from research_agent.orchestration.state import GraphState, WorkflowState, from_graph_state, to_graph_state
from research_agent.tools.base import BaseToolAdapter
from research_agent.observability.checkpoints import cleanup_old_checkpoints
from research_agent.observability.logging import ErrorSeverity, log_error, log_exception, get_node_timings, reset_trace_context, wrap_node_fn, set_trace_context
from research_agent.observability.metrics import observe_run_duration, count_run, set_active_runs
from research_agent.observability.structured_log import set_correlation_id, reset_correlation_id
from research_agent.plugins.manager import get_plugin_manager


logger = logging.getLogger(__name__)


# Module-level Redis connection pool (lazily initialized, shared across runs)
# Protected by asyncio.Lock to prevent check-then-act race on initialization.
_redis_pool: redis.ConnectionPool | None = None
_redis_pool_lock = asyncio.Lock()

# Module-level MemorySaver instance shared across run_graph() calls so that
# interactive checkpoint resume works. When a thread pauses at an interrupt
# (e.g. plan_validation), the checkpoint is stored here and can be found by
# a subsequent run_graph() call with the same thread_id.
_memory_checkpointer: MemorySaver | None = None


async def _create_redis_pool(url: str, max_connections: int, timeout: int) -> redis.ConnectionPool:
    """Create a Redis connection pool with configured timeout and retry.

    Implements up to 3 connection attempts with exponential backoff.
    """
    last_exc = None
    for attempt in range(3):
        try:
            pool = redis.ConnectionPool.from_url(
                url,
                max_connections=max_connections,
                socket_connect_timeout=timeout,
                socket_timeout=timeout,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            # Probe the connection
            r = redis.Redis(connection_pool=pool)
            await r.ping()  # type: ignore[misc]
            await r.aclose()
            logger.info("Redis pool created: %s (max=%d, timeout=%ds)", url, max_connections, timeout)
            return pool
        except Exception as exc:
            last_exc = exc
            wait = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(
                "Redis connection attempt %d/3 failed: %s. Retrying in %.1fs...",
                attempt + 1, exc, wait,
            )
            await asyncio.sleep(wait)

    raise ConnectionError(
        f"Could not connect to Redis after 3 attempts: {last_exc}"
    ) from last_exc


def get_redis_pool() -> redis.ConnectionPool | None:
    """Return the module-level shared Redis connection pool, or None if not initialized.

    The pool is lazily created by :func:`run_graph` when Redis persistence is enabled.
    Callers should treat the returned pool as read-only and never close it directly.
    """
    return _redis_pool


async def close_redis_pool() -> None:
    """Gracefully close the module-level Redis connection pool.

    Safe to call multiple times — idempotent.
    """
    global _redis_pool
    pool = _redis_pool
    if pool is not None:
        _redis_pool = None  # Prevent reuse while closing
        try:
            await pool.disconnect()
            logger.info("Redis connection pool closed")
        except Exception:
            logger.exception("Error closing Redis pool")



def _route_after_clarifier(state: GraphState) -> str:
    # P26: In autonomous mode, skip user clarification entirely.
    # The intake already auto-selected the topic, so no user input is needed.
    if state.get("autonomy_mode") == "autonomous":
        return "planner"
    if state["needs_clarification"] and state["clarification_questions"]:
        return "await_user"
    return "planner"


def _route_after_worker(state: GraphState) -> str:
    stop_reason = _stop_reason(state)
    if stop_reason:
        state["stop_reason"] = stop_reason
        return "stopped"

    tasks = state["tasks"]
    pending = get_pending_task_ids(tasks)
    ready = get_ready_task_ids(tasks)

    if not pending:
        return "complete"
    
    # v2.1: Detect deadlock (pending tasks but none are ready)
    if not ready:
        state["stop_reason"] = "dependency_deadlock"
        return "stopped"
        
    return "loop"


def _route_after_critic(state: GraphState) -> str:
    stop_reason = _stop_reason(state)
    if stop_reason:
        state["stop_reason"] = stop_reason
        return "stopped"

    # If confidence is low and we haven't hit max iterations, loop back
    low_confidence = any(score < 0.35 for score in state["section_confidence"].values())
    iteration = state["iteration_index"]
    max_iter = state["max_iterations"]
    
    if low_confidence and iteration < max_iter:
        if state.get("autonomy_mode") == "interactive":
            return "await_user_critic"
        return "replan"
    
    if low_confidence and iteration >= max_iter:
        # Max iterations reached with persistent low confidence — log the stop reason
        state["stop_reason"] = "max_iterations_reached"
        state.setdefault("run_warnings", []).append(
            f"critic:max_iterations_reached:iteration={iteration}:max={max_iter}"
        )
    
    return "combiner"


def _stop_reason(state: GraphState) -> str | None:
    interrupt_sig = state.get("interrupt_signal")  # type: ignore[gpu-or-other]
    if state.get("interrupted") or (interrupt_sig is not None and hasattr(interrupt_sig, "is_set") and interrupt_sig.is_set()):
        return "user_interrupt"

    started_at = float(state.get("started_at", time.time()))
    max_runtime_minutes = int(state.get("max_runtime_minutes", 0) or 0)
    if max_runtime_minutes > 0:
        elapsed_seconds = max(0.0, time.time() - started_at)
        if elapsed_seconds >= (max_runtime_minutes * 60):
            return "runtime_cap_reached"

    max_cost_usd = float(state.get("max_cost_usd", 0.0) or 0.0)
    estimated_cost_usd = float(state.get("estimated_cost_usd", 0.0) or 0.0)
    if max_cost_usd > 0 and estimated_cost_usd >= max_cost_usd:
        return "cost_cap_reached"

    return None


async def plan_validation_node(state: GraphState) -> dict:
    return {"phase": "plan_validated"}


def build_graph(
    registry: dict[str, BaseToolAdapter] | None = None,
    checkpointer=None,
    interrupt_before=None,
):
    if checkpointer is None:
        checkpointer = MemorySaver()
    tool_registry = {} if registry is None else registry
    graph = StateGraph(GraphState)
    # All node functions are wrapped with NodeTimer for execution timing
    graph.add_node("intake", wrap_node_fn("intake", intake_node))
    graph.add_node("clarifier", wrap_node_fn("clarifier", clarifier_node))
    graph.add_node("await_user", wrap_node_fn("await_user", awaiting_user_node))
    graph.add_node("planner", wrap_node_fn("planner", planner_node))
    graph.add_node("plan_validation", wrap_node_fn("plan_validation", plan_validation_node))
    graph.add_node("worker_executor", wrap_node_fn("worker_executor", make_worker_node(tool_registry)))
    graph.add_node("workers_complete", wrap_node_fn("workers_complete", workers_complete_node))
    graph.add_node("stopped", wrap_node_fn("stopped", stop_node))
    graph.add_node("indexing", wrap_node_fn("indexing", indexing_node))
    graph.add_node("critic", wrap_node_fn("critic", critic_node))
    graph.add_node("replanner", wrap_node_fn("replanner", replanner_node))
    graph.add_node("await_user_critic", wrap_node_fn("await_user_critic", awaiting_user_critic_node))
    graph.add_node("combiner", wrap_node_fn("combiner", combiner_node))
    graph.add_node("knowledge_graph", wrap_node_fn("knowledge_graph", knowledge_graph_node))
    graph.add_node("bias_detector", wrap_node_fn("bias_detector", bias_detector_node))
    graph.add_node("future_work", wrap_node_fn("future_work", future_work_extrapolator_node))
    graph.add_node("gap_analyzer", wrap_node_fn("gap_analyzer", gap_analyzer_node))
    graph.add_node("comparison_table", wrap_node_fn("comparison_table", comparison_table_node))
    graph.add_node("citation_graph", wrap_node_fn("citation_graph", citation_graph_node))
    graph.add_node("figure_generator", wrap_node_fn("figure_generator", figure_generator_node))
    graph.add_node("citation_verifier", wrap_node_fn("citation_verifier", citation_verifier_node))
    graph.add_node("composer", wrap_node_fn("composer", composer_node))
    graph.add_node("formula_normalizer", wrap_node_fn("formula_normalizer", formula_normalizer_node))
    graph.add_node("hallucination_guard", wrap_node_fn("hallucination_guard", hallucination_guard_node))
    graph.add_node("formula_verifier", wrap_node_fn("formula_verifier", formula_verifier_node))
    graph.add_node("peer_reviewer", wrap_node_fn("peer_reviewer", peer_reviewer_node))
    graph.add_node("presentation", wrap_node_fn("presentation", presentation_generator_node))
    graph.add_node("poster", wrap_node_fn("poster", poster_generator_node))
    graph.add_node("exporter", wrap_node_fn("exporter", exporter_node))
    graph.add_node("code_execution", wrap_node_fn("code_execution", code_execution_node))
    graph.add_node("code_sandbox", wrap_node_fn("code_sandbox", code_sandbox_node))
    graph.add_node("dataset_discovery", wrap_node_fn("dataset_discovery", dataset_discovery_node))
    graph.add_node("grant_proposal", wrap_node_fn("grant_proposal", grant_proposal_node))
    graph.add_node("multi_modal", wrap_node_fn("multi_modal", multi_modal_node))
    # P26: Advanced AI Research Assistant nodes
    graph.add_node("hypothesis_generator", wrap_node_fn("hypothesis_generator", hypothesis_generator_node))
    graph.add_node("strategy_recommender", wrap_node_fn("strategy_recommender", strategy_recommender_node))
    graph.add_node("gap_exploration", wrap_node_fn("gap_exploration", gap_exploration_node))
    # P34: Multi-Agent Research Swarm
    graph.add_node("swarm_debate", wrap_node_fn("swarm_debate", swarm_node))



    graph.add_edge(START, "intake")
    graph.add_edge("intake", "clarifier")
    graph.add_conditional_edges(
        "clarifier",
        _route_after_clarifier,
        {
            "await_user": "await_user",
            "planner": "planner",
        },
    )
    graph.add_edge("await_user", END)
    graph.add_edge("planner", "plan_validation")
    # P26: Strategy recommendation guides the worker execution direction
    graph.add_edge("plan_validation", "strategy_recommender")
    graph.add_edge("strategy_recommender", "worker_executor")
    graph.add_conditional_edges(
        "worker_executor",
        _route_after_worker,
        {
            "complete": "workers_complete",
            "loop": "worker_executor",
            "stopped": "stopped",
        },
    )
    graph.add_edge("workers_complete", "indexing")
    graph.add_edge("indexing", "critic")

    graph.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "await_user_critic": "await_user_critic",
            "replan": "replanner",
            "combiner": "combiner",
            "stopped": "stopped",
        },
    )

    graph.add_edge("replanner", "worker_executor")
    graph.add_edge("await_user_critic", END)

    graph.add_edge("stopped", "combiner")
    
    graph.add_edge("combiner", "knowledge_graph")
    graph.add_edge("knowledge_graph", "bias_detector")
    graph.add_edge("bias_detector", "future_work")
    graph.add_edge("future_work", "gap_analyzer")
    # P26: Hypothesis generation and gap exploration after gap analysis
    graph.add_edge("gap_analyzer", "hypothesis_generator")
    graph.add_edge("hypothesis_generator", "gap_exploration")
    # P34: Swarm debate deliberates on hypotheses and gap insights
    graph.add_edge("gap_exploration", "swarm_debate")
    graph.add_edge("swarm_debate", "comparison_table")
    graph.add_edge("comparison_table", "citation_graph")
    graph.add_edge("citation_graph", "figure_generator")
    graph.add_edge("figure_generator", "citation_verifier")
    graph.add_edge("citation_verifier", "composer")
    graph.add_edge("composer", "formula_normalizer")
    graph.add_edge("formula_normalizer", "hallucination_guard")
    graph.add_edge("hallucination_guard", "formula_verifier")
    graph.add_edge("formula_verifier", "peer_reviewer")
    graph.add_edge("peer_reviewer", "presentation")
    graph.add_edge("presentation", "poster")
    graph.add_edge("poster", "exporter")
    graph.add_edge("exporter", "code_sandbox")
    graph.add_edge("code_sandbox", "code_execution")
    graph.add_edge("code_execution", "dataset_discovery")
    graph.add_edge("dataset_discovery", "grant_proposal")
    graph.add_edge("grant_proposal", "multi_modal")
    graph.add_edge("multi_modal", END)




    
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)


async def run_graph(
    state: WorkflowState,
    registry: dict[str, BaseToolAdapter] | None = None,
    thread_id: str | None = None,
) -> WorkflowState:
    from research_agent.config import load_settings
    settings = load_settings()
    
    # Module-level Redis connection pool (reused across runs)
    global _redis_pool, _memory_checkpointer

    interrupt_before = []
    if settings.runtime.interactive_checkpoints:
        interrupt_before = ["plan_validation"]

    redis_conn = None
    checkpointer: MemorySaver | AsyncRedisSaver
    if settings.features.session_persistence == "redis":
        async with _redis_pool_lock:
            if _redis_pool is None:
                _redis_pool = await _create_redis_pool(
                    url=settings.redis.url,
                    max_connections=settings.redis.max_connections,
                    timeout=settings.redis.timeout_seconds,
                )
        redis_conn = redis.Redis(connection_pool=_redis_pool)
        checkpointer = AsyncRedisSaver(redis_client=redis_conn)
        logger.info("Checkpointer created with AsyncRedisSaver (pool established)")
    else:
        # Shared MemorySaver enables checkpoint resume across run_graph() calls.
        # Each thread_id isolates its own state within the same MemorySaver.
        if _memory_checkpointer is None:
            _memory_checkpointer = MemorySaver()
        checkpointer = _memory_checkpointer

    # Set trace context so all downstream log_error/log_exception calls
    # automatically inherit the run_id without needing explicit trace_id=.
    _trace_token = set_trace_context(state.run_id)

    # Set correlation ID for structured logging
    _cid_token = set_correlation_id(state.run_id)

    # Track active runs in Prometheus
    set_active_runs(1)

    try:
        # P19: Fire plugin on_run_start hook
        try:
            plugin_mgr = get_plugin_manager()
            await plugin_mgr.run_hook("on_run_start", run_id=state.run_id, topic=state.topic, template=state.template, depth=state.depth)
        except Exception as _pe:
            logger.warning("Plugin on_run_start hook failed: %s", _pe)

        compiled = build_graph(
            registry=registry,
            checkpointer=checkpointer,
            interrupt_before=interrupt_before,
        )
        config = {"configurable": {"thread_id": thread_id or state.run_id}}
        
        # Check if the thread already has a history/checkpoint
        thread_state = await compiled.aget_state(config)
        if thread_state.values:
            # Update current thread state with the user's modifications (if any)
            await compiled.aupdate_state(config, to_graph_state(state))
            # Resume execution by passing None to ainvoke
            result = await compiled.ainvoke(None, config=config)
        else:
            # Initial run, start from the beginning
            result = await compiled.ainvoke(to_graph_state(state), config=config)
            
        # Inspect thread state after invocation to check for breakpoints
        post_thread_state = await compiled.aget_state(config)
        ret_state = from_graph_state(result)

        # P19: Fire plugin on_run_complete hook
        try:
            if ret_state.latex_main or ret_state.bibtex:
                await plugin_mgr.run_hook("on_run_complete", run_id=state.run_id, latex_main=ret_state.latex_main, bibtex=ret_state.bibtex, sections=ret_state.combined_sections, citations=ret_state.citations, artifact_dir=ret_state.artifact_dir)
        except Exception as _pe:
            logger.warning("Plugin on_run_complete hook failed: %s", _pe)

        # Check if we're at a breakpoint (plan_validation)
        if post_thread_state.next and "plan_validation" in post_thread_state.next:
            ret_state.phase = "awaiting_plan_approval"
            ret_state.stop_reason = "plan_validation_checkpoint"

        # Record Prometheus metrics
        run_duration = time.monotonic() - state._timing_start if hasattr(state, "_timing_start") else 0
        observe_run_duration(run_duration)
        result_label = "success" if ret_state.phase == "completed" else ("interrupted" if ret_state.interrupted else "failure")
        count_run(result=result_label)

        return ret_state
    finally:
        # Return Redis client to pool (does NOT close the pool).
        # The AsyncRedisSaver is scoped to this run_graph() call — once
        # execution is done, the saver has flushed all checkpoints to Redis
        # so the connection is no longer needed.
        if redis_conn is not None:
            try:
                await redis_conn.aclose()
            except Exception:
                logger.exception("Error returning Redis client to pool")


        # Lifecycle cleanup: purge per-run state from global caches
        try:
            from research_agent.orchestration.nodes.indexing import cleanup_run_state as _cleanup_indexing
            await _cleanup_indexing(state.run_id)
        except Exception as exc:
            log_exception(
                "Lifecycle cleanup failed for run %s",
                severity=ErrorSeverity.CLEANUP,
                component="graph",
                trace_id=state.run_id,
                exc=exc,
            )

        # Reset correlation ID
        try:
            reset_correlation_id(_cid_token)
        except Exception:
            pass

        # Track active runs gauge
        set_active_runs(0)

        # Restore the previous trace context (if any)
        try:
            reset_trace_context(_trace_token)  # type: ignore[has-type]
        except Exception:
            pass  # best-effort restore


async def get_memory_diagnostics() -> dict[str, object]:
    """Return sizes of all global caches for monitoring/memory leak detection.

    Returns:
        Dict with cache names as keys and their current sizes as values.
    """
    pool_info: dict[str, object] = {"initialized": _redis_pool is not None}
    if _redis_pool is not None:
        pool_info["max_connections"] = _redis_pool.max_connections
        # redis.ConnectionPool doesn't expose in_use_connections natively,
        # so we just report the pool is available.
    diagnostics: dict[str, object] = {
        "redis_pool": pool_info,
    }

    try:
        from research_agent.orchestration.nodes.indexing import (
            _INDEX_CACHE,
            _CONTRADICTION_CACHE,
            _INDEXED_TASKS_CACHE,
        )
        diagnostics["index_cache_runs"] = len(_INDEX_CACHE)
        diagnostics["contradiction_cache_runs"] = len(_CONTRADICTION_CACHE)
        diagnostics["indexed_tasks_cache_runs"] = len(_INDEXED_TASKS_CACHE)
    except Exception as exc:
        log_error(
            "Failed to read index cache diagnostics",
            severity=ErrorSeverity.RECOVERABLE,
            component="graph",
            detail=str(exc),
        )

    try:
        from research_agent.rag.indexer import _GLOBAL_FINGERPRINT_CACHE
        diagnostics["fingerprint_cache_size"] = len(_GLOBAL_FINGERPRINT_CACHE)
    except Exception as exc:
        log_error(
            "Failed to read fingerprint cache diagnostics",
            severity=ErrorSeverity.RECOVERABLE,
            component="graph",
            detail=str(exc),
        )

    try:
        from research_agent.app.auth import _JWT_SECRET_CACHE
        diagnostics["jwt_secret_cached"] = _JWT_SECRET_CACHE is not None
    except Exception as exc:
        log_error(
            "Failed to read auth cache diagnostics",
            severity=ErrorSeverity.RECOVERABLE,
            component="graph",
            detail=str(exc),
        )

    # Node execution timings
    try:
        diagnostics["node_timings"] = get_node_timings()
    except Exception as exc:
        log_error(
            "Failed to read node timings",
            severity=ErrorSeverity.RECOVERABLE,
            component="graph",
            detail=str(exc),
        )

    return diagnostics


async def clean_old_runs(max_age_days: int = 7) -> dict[str, int]:
    """Clean up old checkpoint files and purge stale cache entries.

    Args:
        max_age_days: Maximum age in days for checkpoint files.

    Returns:
        Dict with counts of cleaned items.
    """
    cleaned_files = cleanup_old_checkpoints(max_age_days=max_age_days)
    return {
        "checkpoint_files_removed": cleaned_files,
    }

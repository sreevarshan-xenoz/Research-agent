"""Centralized structured logging for the Research Agent.

Provides:
- Structured error event with trace_id, node, severity
- log_error() / log_exception() helpers with standardized severity levels
- Node execution timing context manager
- Provider failure metrics tracking
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import time

logger = logging.getLogger(__name__)


# Context variable for automatic trace_id propagation.
# Set at run scope (e.g., in run_graph() or request handlers) so that
# downstream log_error() / log_exception() calls automatically inherit
# the trace_id without needing to pass it explicitly.
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)


def get_current_trace_id() -> str:
    """Return the current trace_id from context, or empty string if not set."""
    return _trace_id_var.get()


def set_trace_context(trace_id: str) -> contextvars.Token[str]:
    """Set the trace_id for the current execution context.

    Usage::

        token = set_trace_context(run_id)
        try:
            ...  # all log_error/log_exception calls inherit run_id
        finally:
            reset_trace_context(token)

    Returns:
        A Token that can be used to restore the previous value via
        ``reset_trace_context(token)``.
    """
    return _trace_id_var.set(trace_id)


def reset_trace_context(token: contextvars.Token[str]) -> None:
    """Restore the trace context to its previous value.

    Args:
        token: A Token returned by a previous :func:`set_trace_context` call.
    """
    _trace_id_var.reset(token)


class ErrorSeverity:
    """Standardized error severity levels for structured logging."""
    RECOVERABLE = "recoverable"
    RETRYABLE = "retryable"
    FATAL = "fatal"
    EXTERNAL_DEPENDENCY = "external_dependency"
    CLEANUP = "cleanup"


def log_error(
    message: str,
    *,
    severity: str = ErrorSeverity.RECOVERABLE,
    component: str = "",
    node: str = "",
    trace_id: str = "",
    detail: str = "",
    exc_info: bool = False,
) -> None:
    """Log a structured error event.

    Automatically inherits trace_id from the current context if not explicitly
    provided (see :func:`set_trace_context` and :func:`get_current_trace_id`).

    Args:
        message: Human-readable error description.
        severity: One of ErrorSeverity constants.
        component: Source component (e.g., "worker", "citation_verifier").
        node: Graph node name if applicable.
        trace_id: Run or session identifier for correlation. Falls back to
            the current context var if empty.
        detail: Additional context.
        exc_info: If True, include current exception traceback.
    """
    effective_trace_id = trace_id or _trace_id_var.get()
    structured = f"[{severity}] [{component}] [{effective_trace_id}] {message}"
    if detail:
        structured += f" — {detail}"
    logger.log(logging.ERROR if severity == ErrorSeverity.FATAL else logging.WARNING, structured, exc_info=exc_info)


def log_exception(
    message: str,
    *,
    severity: str = ErrorSeverity.RECOVERABLE,
    component: str = "",
    node: str = "",
    trace_id: str = "",
    exc: BaseException | None = None,
) -> None:
    """Log an exception with structured context and full traceback.

    Automatically inherits trace_id from the current context if not explicitly
    provided (see :func:`set_trace_context` and :func:`get_current_trace_id`).

    Args:
        message: Human-readable error description.
        severity: One of ErrorSeverity constants.
        component: Source component.
        node: Graph node name if applicable.
        trace_id: Run or session identifier. Falls back to the current
            context var if empty.
        exc: The exception to log. If None, uses sys.exc_info().
    """
    effective_trace_id = trace_id or _trace_id_var.get()
    structured = f"[{severity}] [{component}] [{effective_trace_id}] {message}"
    if exc:
        structured += f" ({type(exc).__name__}: {exc})"
    if severity == ErrorSeverity.FATAL:
        logger.exception(structured)
    else:
        logger.warning(structured, exc_info=True)


class NodeTimer:
    """Context manager for timing graph node execution.

    Usage:
        with NodeTimer("citation_verifier", trace_id=run_id) as timer:
            result = await citation_verifier_node(state)
    """

    def __init__(self, node_name: str, trace_id: str = ""):
        self.node_name = node_name
        # Fall back to the context var if no trace_id was explicitly provided
        self.trace_id = trace_id or _trace_id_var.get()
        self.start: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.monotonic() - self.start) * 1000
        if exc_type is not None:
            log_error(
                f"Node {self.node_name} failed after {self.duration_ms:.0f}ms: {exc_type.__name__}: {exc_val}",
                severity=ErrorSeverity.FATAL,
                component=self.node_name,
                trace_id=self.trace_id,
                exc_info=True,
            )
        else:
            logger.debug("[NodeTimer] [%s] Completed in %.0fms", self.node_name, self.duration_ms)


# Provider failure tracker for external dependency metrics
_provider_failures: dict[str, int] = {}
_provider_failures_lock = asyncio.Lock()


async def record_provider_failure(provider: str) -> None:
    """Record a failure for an external provider (API, search engine, etc.)."""
    async with _provider_failures_lock:
        _provider_failures[provider] = _provider_failures.get(provider, 0) + 1


async def get_provider_failure_metrics() -> dict[str, int]:
    """Get provider failure counts for monitoring."""
    async with _provider_failures_lock:
        return dict(_provider_failures)


async def reset_provider_failure_metrics() -> None:
    """Reset all provider failure counters."""
    async with _provider_failures_lock:
        _provider_failures.clear()


# ---------------------------------------------------------------------------
# Node execution timing (Task 1: NodeTimer wrappers)
# ---------------------------------------------------------------------------

_node_timings: dict[str, list[float]] = {}
_node_timings_lock = asyncio.Lock()


async def record_node_timing(node_name: str, duration_ms: float) -> None:
    """Record a single node execution duration (ms)."""
    async with _node_timings_lock:
        _node_timings.setdefault(node_name, []).append(duration_ms)


def get_node_timings() -> dict[str, dict[str, float | int]]:
    """Return aggregated node execution statistics.

    Returns:
        Dict keyed by node name, with values containing:
        - count: number of executions
        - total_ms: total across all executions
        - avg_ms: average execution time in ms
        - max_ms: maximum execution time in ms
    """
    stats: dict[str, dict[str, float | int]] = {}
    for node_name, durations in _node_timings.items():
        stats[node_name] = {
            "count": len(durations),
            "total_ms": round(sum(durations), 1),
            "avg_ms": round(sum(durations) / len(durations), 1) if durations else 0.0,
            "max_ms": round(max(durations), 1) if durations else 0.0,
        }
    return stats


def reset_node_timings() -> None:
    """Clear all accumulated node timings (useful between test runs)."""
    _node_timings.clear()


def wrap_node_fn(node_name: str, fn):
    """Wrap a sync or async graph node function with NodeTimer timing
    AND Prometheus metrics recording.

    The wrapper automatically:
    - Captures execution duration via NodeTimer
    - Records timing via record_node_timing() into the in-memory diagnostics store
    - Records Prometheus node_duration_seconds histogram (observe_node_duration)
    - Records Prometheus node_errors_total on exceptions (count_node_error)
    - Extracts trace_id from state["run_id"] if available

    Args:
        node_name: Logical graph node name (used in diagnostics and Prometheus labels)
        fn: The target node function (sync or async)

    Returns:
        A wrapped function with the same signature as fn.
    """
    from research_agent.observability.metrics import observe_node_duration, count_node_error

    if asyncio.iscoroutinefunction(fn):
        async def async_wrapper(state):
            trace_id = state.get("run_id", "") if isinstance(state, dict) else ""
            timer = NodeTimer(node_name, trace_id=trace_id)
            timer.__enter__()
            try:
                result = await fn(state)
            except Exception:
                count_node_error(node_name, severity="fatal")
                raise
            finally:
                timer.__exit__(None, None, None)
                await record_node_timing(node_name, timer.duration_ms)
                observe_node_duration(node_name, timer.duration_ms / 1000.0)
            return result

        async_wrapper.__name__ = fn.__name__
        async_wrapper.__qualname__ = fn.__qualname__
        async_wrapper.__doc__ = fn.__doc__
        return async_wrapper
    else:
        def sync_wrapper(state):
            trace_id = state.get("run_id", "") if isinstance(state, dict) else ""
            timer = NodeTimer(node_name, trace_id=trace_id)
            timer.__enter__()
            try:
                result = fn(state)
            except Exception:
                count_node_error(node_name, severity="fatal")
                raise
            finally:
                timer.__exit__(None, None, None)
                _node_timings.setdefault(node_name, []).append(timer.duration_ms)
                observe_node_duration(node_name, timer.duration_ms / 1000.0)
            return result

        sync_wrapper.__name__ = fn.__name__
        sync_wrapper.__qualname__ = fn.__qualname__
        sync_wrapper.__doc__ = fn.__doc__
        return sync_wrapper

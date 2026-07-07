"""Prometheus metrics for the Research Agent.

Provides:
- Research run duration, total count, success/failure counts
- Per-node execution duration and error counters
- LLM provider latency and cost metrics
- Provider failure counters
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CollectorRegistry, start_http_server

logger = logging.getLogger(__name__)

# Create a custom registry to avoid conflicts with default registry
REGISTRY = CollectorRegistry()

# ------------------------------------------------------------------------- #
# Research Run Metrics
# ------------------------------------------------------------------------- #

RUN_DURATION = Histogram(
    "research_run_duration_seconds",
    "Duration of complete research runs",
    buckets=(30, 60, 120, 300, 600, 900, 1800, 3600),
    registry=REGISTRY,
)

RUN_TOTAL = Counter(
    "research_run_total",
    "Total number of research runs",
    labelnames=["result"],  # "success", "failure", "interrupted"
    registry=REGISTRY,
)

# ------------------------------------------------------------------------- #
# Node Execution Metrics
# ------------------------------------------------------------------------- #

NODE_DURATION = Histogram(
    "research_node_duration_seconds",
    "Duration per graph node execution",
    labelnames=["node"],
    buckets=(1, 5, 10, 30, 60, 120, 300),
    registry=REGISTRY,
)

NODE_ERRORS = Counter(
    "research_node_errors_total",
    "Total errors by node and severity",
    labelnames=["node", "severity"],
    registry=REGISTRY,
)

# ------------------------------------------------------------------------- #
# LLM Provider Metrics
# ------------------------------------------------------------------------- #

LLM_LATENCY = Histogram(
    "research_llm_latency_seconds",
    "LLM request latency by provider",
    labelnames=["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

LLM_COST = Counter(
    "research_llm_cost_total",
    "Total LLM cost in USD by provider",
    labelnames=["provider"],
    registry=REGISTRY,
)

LLM_REQUESTS = Counter(
    "research_llm_requests_total",
    "Total LLM requests by provider and result",
    labelnames=["provider", "result"],  # "success", "error"
    registry=REGISTRY,
)

# ------------------------------------------------------------------------- #
# Provider Failure Metrics
# ------------------------------------------------------------------------- #

PROVIDER_FAILURES = Counter(
    "research_provider_failures_total",
    "Total provider (search, API) failures by provider name",
    labelnames=["provider"],
    registry=REGISTRY,
)

# ------------------------------------------------------------------------- #
# Active Run Gauge
# ------------------------------------------------------------------------- #

ACTIVE_RUNS = Gauge(
    "research_active_runs",
    "Number of currently active research runs",
    registry=REGISTRY,
)

# ------------------------------------------------------------------------- #
# Helper Functions
# ------------------------------------------------------------------------- #


def observe_run_duration(duration_seconds: float) -> None:
    """Record a research run's duration."""
    RUN_DURATION.observe(duration_seconds)


def count_run(result: str = "success") -> None:
    """Increment the run counter with the given result label."""
    RUN_TOTAL.labels(result=result).inc()


def observe_node_duration(node_name: str, duration_seconds: float) -> None:
    """Record a node's execution duration."""
    NODE_DURATION.labels(node=node_name).observe(duration_seconds)


def count_node_error(node_name: str, severity: str = "recoverable") -> None:
    """Increment the node error counter."""
    NODE_ERRORS.labels(node=node_name, severity=severity).inc()


def observe_llm_latency(provider: str, model: str, latency_seconds: float) -> None:
    """Record LLM request latency."""
    LLM_LATENCY.labels(provider=provider, model=model).observe(latency_seconds)


def record_llm_cost(provider: str, cost_usd: float) -> None:
    """Add to the cumulative cost counter for a provider."""
    LLM_COST.labels(provider=provider).inc(cost_usd)


def count_llm_request(provider: str, result: str = "success") -> None:
    """Increment the LLM request counter."""
    LLM_REQUESTS.labels(provider=provider, result=result).inc()


def count_provider_failure(provider: str) -> None:
    """Increment the provider failure counter."""
    PROVIDER_FAILURES.labels(provider=provider).inc()


def set_active_runs(count: int) -> None:
    """Set the active runs gauge."""
    ACTIVE_RUNS.set(count)


def start_metrics_server(port: int = 9090) -> None:
    """Start a Prometheus metrics HTTP server on the given port.

    This runs a lightweight HTTP server that exposes /metrics for
    Prometheus scraping. Uses Python's built-in http.server.
    """
    start_http_server(port, registry=REGISTRY)
    logger.info("Prometheus metrics server listening on port %d", port)


def get_metrics_text() -> bytes:
    """Generate Prometheus metrics text format."""
    return generate_latest(REGISTRY)


# ------------------------------------------------------------------------- #
# Decorator: time_node
# ------------------------------------------------------------------------- #


def time_node(node_name: str) -> Callable:
    """Decorator that times a graph node function and records Prometheus metrics.

    Works with both sync and async functions.

    Usage:
        @time_node("my_node")
        async def my_node(state):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.monotonic()
                try:
                    result = await fn(*args, **kwargs)
                    return result
                except Exception:
                    count_node_error(node_name, severity="fatal")
                    raise
                finally:
                    duration = time.monotonic() - start
                    observe_node_duration(node_name, duration)
            return async_wrapper
        else:
            @wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.monotonic()
                try:
                    result = fn(*args, **kwargs)
                    return result
                except Exception:
                    count_node_error(node_name, severity="fatal")
                    raise
                finally:
                    duration = time.monotonic() - start
                    observe_node_duration(node_name, duration)
            return sync_wrapper
    return decorator


import asyncio  # noqa: E402 - needed for iscoroutinefunction check in decorator

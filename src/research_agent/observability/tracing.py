"""OpenTelemetry tracing for the Research Agent.

Provides:
- init_tracing(): one-call setup for OTel SDK with OTLP exporter
- traced_node(): decorator to wrap graph node functions with spans
- trace_llm_call(): context manager for tracing individual LLM calls
- get_tracer(): access to the configured tracer
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)

_tracer: trace.Tracer | None = None


def get_tracer() -> trace.Tracer:
    """Get the configured tracer. Returns a no-op tracer if not initialized."""
    global _tracer
    if _tracer is not None:
        return _tracer
    return trace.get_tracer(__name__)


def init_tracing(
    service_name: str = "research-agent",
    otlp_endpoint: str | None = None,
    console_export: bool = False,
) -> None:
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Service name for resource attributes.
        otlp_endpoint: OTLP HTTP exporter endpoint (e.g., http://localhost:4318/v1/traces).
            If None, only console export (if enabled) or no export is used.
        console_export: If True, also export spans to console (stderr).
    """
    global _tracer

    resource = Resource.create({
        "service.name": service_name,
        "service.version": "2.0",
    })

    provider = TracerProvider(resource=resource)

    # Add OTLP exporter if endpoint configured
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP tracing enabled, exporting to %s", otlp_endpoint)
        except Exception as exc:
            logger.warning("Failed to configure OTLP exporter: %s", exc)

    # Add console exporter for debugging
    if console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer = provider.get_tracer(service_name, "2.0")
    logger.info("OpenTelemetry tracing initialized (service=%s)", service_name)


def traced_node(node_name: str) -> Callable:
    """Decorator that wraps a graph node function with an OpenTelemetry span.

    Works with both sync and async functions.

    Usage:
        @traced_node("my_node")
        async def my_node(state):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                with tracer.start_as_current_span(
                    f"node.{node_name}",
                    attributes={"node.name": node_name},
                ) as span:
                    try:
                        result = await fn(*args, **kwargs)
                        span.set_attribute("node.completed", True)
                        return result
                    except Exception as exc:
                        span.set_attribute("node.error", str(exc))
                        span.set_attribute("node.completed", False)
                        span.record_exception(exc)
                        raise
            return async_wrapper
        else:
            @wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                with tracer.start_as_current_span(
                    f"node.{node_name}",
                    attributes={"node.name": node_name},
                ) as span:
                    try:
                        result = fn(*args, **kwargs)
                        span.set_attribute("node.completed", True)
                        return result
                    except Exception as exc:
                        span.set_attribute("node.error", str(exc))
                        span.set_attribute("node.completed", False)
                        span.record_exception(exc)
                        raise
            return sync_wrapper
    return decorator


@contextmanager
def trace_llm_call(
    provider: str,
    model: str,
    run_id: str = "",
) -> Generator[trace.Span, None, None]:
    """Context manager to trace an individual LLM call.

    Usage:
        with trace_llm_call("openai", "gpt-4o", run_id=run_id) as span:
            response = await client.complete(...)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"llm.{provider}",
        attributes={
            "llm.provider": provider,
            "llm.model": model,
            "llm.run_id": run_id,
        },
    ) as span:
        yield span


@contextmanager
def trace_run(run_id: str, topic: str) -> Generator[trace.Span, None, None]:
    """Context manager to trace a complete research run.

    Usage:
        with trace_run(run_id, topic):
            final_state = await run_graph(state)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"run.{run_id[:12]}",
        attributes={
            "run.id": run_id,
            "run.topic": topic[:200],
        },
    ) as span:
        yield span


import asyncio  # noqa: E402 - needed for iscoroutinefunction check

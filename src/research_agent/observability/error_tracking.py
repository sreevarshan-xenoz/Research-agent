"""Sentry error tracking integration for the Research Agent.

Provides:
- init_sentry(): one-call setup for Sentry SDK
- capture_error(): log an error to Sentry with context
- sentry_context(): context manager to set Sentry scope tags
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

import sentry_sdk
from sentry_sdk import configure_scope, push_scope

logger = logging.getLogger(__name__)

# Sentinel to track initialization status
_sentry_initialized = False


def init_sentry(
    dsn: str = "",
    environment: str = "development",
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
) -> None:
    """Initialize Sentry SDK for error tracking.

    Args:
        dsn: Sentry DSN. If empty, Sentry is disabled.
        environment: Environment name (development, staging, production).
        traces_sample_rate: Sample rate for performance tracing (0.0-1.0).
        profiles_sample_rate: Sample rate for profiling (0.0-1.0).
    """
    global _sentry_initialized

    if not dsn:
        logger.info("Sentry disabled: no DSN configured")
        _sentry_initialized = False
        return

    if _sentry_initialized:
        logger.debug("Sentry already initialized")
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            send_default_pii=False,
            max_breadcrumbs=50,
            attach_stacktrace=True,
        )
        _sentry_initialized = True
        logger.info("Sentry initialized for environment '%s'", environment)
    except Exception as exc:
        logger.warning("Failed to initialize Sentry: %s", exc)
        _sentry_initialized = False


def is_sentry_enabled() -> bool:
    """Check if Sentry is initialized and active."""
    return _sentry_initialized


def capture_error(
    error: Exception,
    component: str = "",
    run_id: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    """Capture an exception with Sentry, adding contextual tags.

    Args:
        error: The exception to capture.
        component: Source component name.
        run_id: Research run ID for correlation.
        extra: Additional context to attach.
    """
    if not _sentry_initialized:
        return

    with push_scope() as scope:
        if component:
            scope.set_tag("component", component)
        if run_id:
            scope.set_tag("run_id", run_id)
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, str(value))
        sentry_sdk.capture_exception(error)


def capture_message(
    message: str,
    level: str = "warning",
    component: str = "",
    run_id: str = "",
) -> None:
    """Capture a message with Sentry.

    Args:
        message: The message to send.
        level: Severity level (debug, info, warning, error, fatal).
        component: Source component name.
        run_id: Research run ID.
    """
    if not _sentry_initialized:
        return

    with push_scope() as scope:
        if component:
            scope.set_tag("component", component)
        if run_id:
            scope.set_tag("run_id", run_id)
        sentry_sdk.capture_message(message, level=level)  # type: ignore[arg-type]


@contextmanager
def sentry_context(
    run_id: str = "",
    component: str = "",
    tags: dict[str, str] | None = None,
) -> Generator[None, None, None]:
    """Context manager that sets Sentry scope tags for the duration.

    Usage:
        with sentry_context(run_id=run_id, component="worker"):
            # Any errors raised here will have these tags
            ...
    """
    if not _sentry_initialized:
        yield
        return

    with configure_scope() as scope:
        if run_id:
            scope.set_tag("run_id", run_id)
        if component:
            scope.set_tag("component", component)
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)
        yield

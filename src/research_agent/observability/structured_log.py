"""JSON structured logging for the Research Agent.

Provides:
- JsonFormatter: formats log records as JSON with correlation IDs
- configure_json_logging: one-call setup for the root logger
- get_correlation_id / set_correlation_id: context-var-based correlation ID
"""

from __future__ import annotations

import contextvars
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from pythonjsonlogger import jsonlogger  # type: ignore[import-untyped]

# Context variable for correlation ID (run_id or request_id)
_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "research_correlation_id", default=""
)


def get_correlation_id() -> str:
    """Return the current correlation ID from context, or empty string."""
    return _correlation_id_var.get()


def set_correlation_id(cid: str) -> contextvars.Token[str]:
    """Set the correlation ID for the current execution context.

    Usage:
        token = set_correlation_id(run_id)
        try:
            ...
        finally:
            reset_correlation_id(token)
    """
    return _correlation_id_var.set(cid)


def reset_correlation_id(token: contextvars.Token[str]) -> None:
    """Restore the correlation ID to its previous value."""
    _correlation_id_var.reset(token)


class ResearchJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that adds Research Agent specific fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO format
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Add correlation ID from context
        cid = get_correlation_id()
        if cid:
            log_record["correlation_id"] = cid

        # Rename fields for clarity
        if "levelname" in log_record:
            log_record["level"] = log_record.pop("levelname")

        # Ensure logger name is included
        if "name" not in log_record and hasattr(record, "name"):
            log_record["logger"] = record.name


def configure_json_logging(
    level: str = "INFO",
    correlation_id: str = "",
) -> None:
    """Configure the root logger to output structured JSON logs.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        correlation_id: Optional initial correlation ID.
    """
    if correlation_id:
        set_correlation_id(correlation_id)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        ResearchJsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s",
            timestamp=True,
        )
    )

    root_logger = logging.getLogger()
    # Remove existing handlers to avoid duplicate output
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)

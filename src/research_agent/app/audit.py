"""Audit logging for P18 Security Hardening.

Logs all API requests with user context, action type, resource, and outcome.
Provides query endpoints for reviewing audit trails.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audit Entry model
# ---------------------------------------------------------------------------


@dataclass
class AuditEntry:
    """A single audit log entry capturing a security-relevant action."""
    timestamp: float
    user_id: str
    user_role: str
    session_id: str
    method: str
    path: str
    status_code: int
    action_type: str  # "read", "create", "update", "delete", "auth", "admin"
    resource: str  # e.g. "run", "session", "user", "watchdog", "auth"
    duration_ms: float
    ip_address: str
    user_agent: str = ""
    detail: str = ""


# ---------------------------------------------------------------------------
# Audit store (JSONL file-based)
# ---------------------------------------------------------------------------


class AuditStore:
    """Persistent audit log store backed by JSONL files.

    Each day gets its own file for easy rotation and cleanup.
    Thread-safe for concurrent writes from multiple workers.
    """

    def __init__(self, root_dir: str = ".runtime/audit"):
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._write_lock = asyncio.Lock()
        self._buffer: list[AuditEntry] = []
        self._buffer_size = 0
        self._max_buffer = 50  # Flush every 50 entries

    def _get_log_path(self, day_stamp: str | None = None) -> Path:
        if day_stamp is None:
            day_stamp = time.strftime("%Y-%m-%d", time.gmtime())
        return self._root / f"audit-{day_stamp}.jsonl"

    async def log(self, entry: AuditEntry) -> None:
        """Log a single audit entry (buffered, flushed periodically)."""
        async with self._write_lock:
            self._buffer.append(entry)
            self._buffer_size += 1
            if self._buffer_size >= self._max_buffer:
                await self._flush_buffer()

    async def _flush_buffer(self) -> None:
        """Flush buffered entries to disk."""
        if not self._buffer:
            return
        log_path = self._get_log_path()
        try:
            lines = "\n".join(
                json.dumps({
                    "timestamp": e.timestamp,
                    "user_id": e.user_id,
                    "user_role": e.user_role,
                    "session_id": e.session_id,
                    "method": e.method,
                    "path": e.path,
                    "status_code": e.status_code,
                    "action_type": e.action_type,
                    "resource": e.resource,
                    "duration_ms": round(e.duration_ms, 1),
                    "ip_address": e.ip_address,
                    "user_agent": e.user_agent,
                    "detail": e.detail,
                }, default=str)
                for e in self._buffer
            )
            with log_path.open("a", encoding="utf-8") as f:
                f.write(lines + "\n")
        except Exception as exc:
            logger.error("Failed to flush audit buffer: %s", exc)
        self._buffer.clear()
        self._buffer_size = 0

    async def query(
        self,
        *,
        user_id: str | None = None,
        action_type: str | None = None,
        resource: str | None = None,
        path_pattern: str | None = None,
        status_code: int | None = None,
        limit: int = 100,
        offset: int = 0,
        days_back: int = 7,
    ) -> list[dict[str, Any]]:
        """Query audit logs with filters.

        Args:
            user_id: Filter by user ID.
            action_type: Filter by action type (read, create, update, delete, auth, admin).
            resource: Filter by resource type (run, session, user, etc.).
            path_pattern: Filter by path substring.
            status_code: Filter by HTTP status code.
            limit: Max results to return.
            offset: Results offset for pagination.
            days_back: How many days of logs to search.

        Returns:
            List of matching audit entries as dicts.
        """
        results: list[dict[str, Any]] = []
        now = time.time()
        cutoff = now - (days_back * 86400)

        # Scan log files from newest to oldest
        log_files = sorted(self._root.glob("audit-*.jsonl"), reverse=True)
        for log_path in log_files:
            if len(results) >= (offset + limit):
                break

            try:
                with log_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Time filter
                        ts = entry.get("timestamp", 0)
                        if ts < cutoff:
                            continue

                        # Apply filters
                        if user_id and entry.get("user_id") != user_id:
                            continue
                        if action_type and entry.get("action_type") != action_type:
                            continue
                        if resource and entry.get("resource") != resource:
                            continue
                        if path_pattern and path_pattern not in entry.get("path", ""):
                            continue
                        if status_code is not None and entry.get("status_code") != status_code:
                            continue

                        results.append(entry)
            except Exception as exc:
                logger.warning("Error reading audit log %s: %s", log_path, exc)

        # Apply offset and limit
        return results[offset:offset + limit]

    async def get_stats(self) -> dict[str, Any]:
        """Get audit log stats."""
        total_entries = 0
        unique_users: set[str] = set()
        action_counts: dict[str, int] = {}
        resource_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}

        for log_path in self._root.glob("audit-*.jsonl"):
            try:
                with log_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        total_entries += 1
                        uid = entry.get("user_id", "")
                        if uid:
                            unique_users.add(uid)

                        at = entry.get("action_type", "unknown")
                        action_counts[at] = action_counts.get(at, 0) + 1

                        res = entry.get("resource", "unknown")
                        resource_counts[res] = resource_counts.get(res, 0) + 1

                        sc = str(entry.get("status_code", 0))
                        status_counts[sc] = status_counts.get(sc, 0) + 1
            except Exception:
                pass

        return {
            "total_entries": total_entries,
            "unique_users": len(unique_users),
            "action_counts": action_counts,
            "resource_counts": resource_counts,
            "status_code_counts": status_counts,
            "log_files": len(list(self._root.glob("audit-*.jsonl"))),
        }


# ---------------------------------------------------------------------------
# Global audit store instance
# ---------------------------------------------------------------------------

_audit_store: AuditStore | None = None
_audit_store_lock = asyncio.Lock()


async def get_audit_store() -> AuditStore:
    """Get the module-level shared AuditStore instance."""
    global _audit_store
    if _audit_store is not None:
        return _audit_store
    async with _audit_store_lock:
        if _audit_store is not None:
            return _audit_store
        _audit_store = AuditStore()
        return _audit_store


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


class AuditMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that logs all API requests to the audit store.

    Automatically classifies action types and resources based on HTTP
    method and path patterns.
    """

    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self._exclude_paths = set(exclude_paths or ["/health", "/metrics", "/api/health"])

    @staticmethod
    def _classify_action(method: str) -> str:
        return {
            "GET": "read",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }.get(method, "read")

    @staticmethod
    def _classify_resource(path: str) -> str:
        """Determine the resource type from a URL path."""
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            # /api/runs/{id} -> "run"
            # /api/sessions/{id} -> "session"
            # /api/auth/* -> "auth"
            # /api/watchdog/* -> "watchdog"
            if parts[0] == "api" and len(parts) >= 2:
                return parts[1].rstrip("s")  # runs -> run, sessions -> session
        if "auth" in parts:
            return "auth"
        if "admin" in parts:
            return "admin"
        return parts[0] if parts else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        path = request.url.path
        for excluded in self._exclude_paths:
            if path.startswith(excluded):
                return await call_next(request)

        # Extract user info from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", "anonymous")
        user_role = getattr(request.state, "user_role", "anonymous")
        session_id = getattr(request.state, "session_id", "")

        # Skip anonymous paths (pre-auth)
        if user_id == "anonymous" and "/api/auth" in path:
            return await call_next(request)

        start = time.monotonic()

        try:
            response = await call_next(request)
        except Exception as exc:
            # Log even failed requests
            duration_ms = (time.monotonic() - start) * 1000
            entry = AuditEntry(
                timestamp=time.time(),
                user_id=user_id,
                user_role=user_role,
                session_id=session_id,
                method=request.method,
                path=path,
                status_code=500,
                action_type=self._classify_action(request.method),
                resource=self._classify_resource(path),
                duration_ms=duration_ms,
                ip_address=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
                detail=f"Exception: {exc}",
            )
            try:
                store = await get_audit_store()
                await store.log(entry)
            except Exception:
                pass
            raise

        duration_ms = (time.monotonic() - start) * 1000

        # Create audit entry
        entry = AuditEntry(
            timestamp=time.time(),
            user_id=user_id,
            user_role=user_role,
            session_id=session_id,
            method=request.method,
            path=path,
            status_code=response.status_code,
            action_type=self._classify_action(request.method),
            resource=self._classify_resource(path),
            duration_ms=duration_ms,
            ip_address=request.client.host if request.client else "",
            user_agent=request.headers.get("user-agent", ""),
        )

        try:
            store = await get_audit_store()
            await store.log(entry)
        except Exception as exc:
            logger.warning("Failed to write audit entry: %s", exc)

        return response

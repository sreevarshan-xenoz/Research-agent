"""Cross-session memory store for the agentic chat.

Supports both in-memory and Redis-backed storage for conversation history,
research context, and user preferences.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConversationEntry:
    """A single entry in the conversation history."""
    role: str  # "user" | "assistant" | "tool"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionMemory:
    """Memory state for a single session."""
    conversation_history: list[ConversationEntry] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    research_context: dict[str, Any] = field(default_factory=dict)
    last_topic: str = ""
    active_library_id: str = ""


class InMemoryMemoryStore:
    """In-memory memory store. Not persistent across restarts."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionMemory] = {}

    def get_session(self, session_id: str) -> SessionMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory()
        return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
        session = self.get_session(session_id)
        session.conversation_history.append(
            ConversationEntry(role=role, content=content, metadata=metadata or {})
        )
        # Keep last 50 messages
        if len(session.conversation_history) > 50:
            session.conversation_history = session.conversation_history[-50:]

    def get_history(self, session_id: str, limit: int = 10) -> list[ConversationEntry]:
        session = self.get_session(session_id)
        return session.conversation_history[-limit:]

    def update_preference(self, session_id: str, key: str, value: Any) -> None:
        session = self.get_session(session_id)
        session.user_preferences[key] = value

    def get_preference(self, session_id: str, key: str, default: Any = None) -> Any:
        session = self.get_session(session_id)
        return session.user_preferences.get(key, default)

    def set_research_context(self, session_id: str, context: dict[str, Any]) -> None:
        session = self.get_session(session_id)
        session.research_context.update(context)

    def get_research_context(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        return dict(session.research_context)

    def set_last_topic(self, session_id: str, topic: str) -> None:
        session = self.get_session(session_id)
        session.last_topic = topic

    def get_last_topic(self, session_id: str) -> str:
        session = self.get_session(session_id)
        return session.last_topic

    def set_active_library(self, session_id: str, library_id: str) -> None:
        session = self.get_session(session_id)
        session.active_library_id = library_id

    def get_active_library(self, session_id: str) -> str:
        session = self.get_session(session_id)
        return session.active_library_id


class RedisMemoryStore:
    """Redis-backed memory store for persistent cross-session memory.

    Falls back gracefully to InMemoryMemoryStore if Redis is unavailable.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._fallback = InMemoryMemoryStore()
        self._redis = None
        self._redis_url = redis_url

    def _ensure_redis(self):
        if self._redis is None and self._redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self._redis_url)
            except Exception as exc:
                logger.warning("Redis unavailable, using in-memory fallback: %s", exc)

    def _session_key(self, session_id: str, kind: str) -> str:
        return f"memory:{session_id}:{kind}"

    # Proxy methods that try Redis first, fall back to in-memory
    async def add_message(self, session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
        self._ensure_redis()
        if self._redis:
            try:
                entry = json.dumps({"role": role, "content": content, "metadata": metadata or {}})
                key = self._session_key(session_id, "history")
                await self._redis.rpush(key, entry)
                await self._redis.ltrim(key, -50, -1)  # Keep last 50
                return
            except Exception:
                self._redis = None  # Fall back
        self._fallback.add_message(session_id, role, content, metadata)

    async def get_history(self, session_id: str, limit: int = 10) -> list[ConversationEntry]:
        self._ensure_redis()
        if self._redis:
            try:
                key = self._session_key(session_id, "history")
                entries = await self._redis.lrange(key, -limit, -1)
                return [
                    ConversationEntry(**json.loads(e))
                    for e in entries
                ]
            except Exception:
                self._redis = None
        return self._fallback.get_history(session_id, limit)

    def update_preference(self, session_id: str, key: str, value: Any) -> None:
        self._fallback.update_preference(session_id, key, value)

    def get_preference(self, session_id: str, key: str, default: Any = None) -> Any:
        return self._fallback.get_preference(session_id, key, default)

    def set_research_context(self, session_id: str, context: dict[str, Any]) -> None:
        self._fallback.set_research_context(session_id, context)

    def get_research_context(self, session_id: str) -> dict[str, Any]:
        return self._fallback.get_research_context(session_id)

    def set_last_topic(self, session_id: str, topic: str) -> None:
        self._fallback.set_last_topic(session_id, topic)

    def get_last_topic(self, session_id: str) -> str:
        return self._fallback.get_last_topic(session_id)

    def set_active_library(self, session_id: str, library_id: str) -> None:
        self._fallback.set_active_library(session_id, library_id)

    def get_active_library(self, session_id: str) -> str:
        return self._fallback.get_active_library(session_id)


# Global memory store instance (lazy init)
_MemoryStore = Union[InMemoryMemoryStore, RedisMemoryStore]
_memory_store: _MemoryStore | None = None


def get_memory_store() -> _MemoryStore:
    """Get or create the global memory store."""
    global _memory_store
    if _memory_store is None:
        _memory_store = InMemoryMemoryStore()
    return _memory_store


def configure_redis_memory_store(redis_url: str) -> None:
    """Replace the global memory store with a Redis-backed one."""
    global _memory_store
    _memory_store = RedisMemoryStore(redis_url)

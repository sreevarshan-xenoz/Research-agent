from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator, Awaitable, Union


ProgressCallback = Union[Callable[[dict[str, str]], None], Callable[[dict[str, str]], Awaitable[None]]]

_PROGRESS_CALLBACK: ContextVar[ProgressCallback | None] = ContextVar(
    "research_agent_progress_callback",
    default=None,
)


@contextmanager
def progress_callback(callback: ProgressCallback | None) -> Iterator[None]:
    token = _PROGRESS_CALLBACK.set(callback)
    try:
        yield
    finally:
        _PROGRESS_CALLBACK.reset(token)


def get_progress_callback() -> ProgressCallback | None:
    return _PROGRESS_CALLBACK.get()


async def apublish_progress(
    *,
    agent: str,
    status: str,
    detail: str = "",
    message: str = "",
) -> None:
    callback = _PROGRESS_CALLBACK.get()
    if callback is None:
        return

    try:
        if asyncio.iscoroutinefunction(callback):
            await callback(
                {
                    "agent": agent,
                    "status": status,
                    "detail": detail,
                    "message": message,
                }
            )
        else:
            callback(
                {
                    "agent": agent,
                    "status": status,
                    "detail": detail,
                    "message": message,
                }
            )
    except Exception:
        return


def publish_progress(
    *,
    agent: str,
    status: str,
    detail: str = "",
    message: str = "",
) -> None:
    callback = _PROGRESS_CALLBACK.get()
    if callback is None:
        return

    try:
        callback(
            {
                "agent": agent,
                "status": status,
                "detail": detail,
                "message": message,
            }
        )
    except Exception:
        return

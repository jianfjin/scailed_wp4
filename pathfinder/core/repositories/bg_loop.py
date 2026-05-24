"""Background event loop for async PG writes from sync service code.

Uses a single daemon thread running an asyncio event loop. Sync methods
can schedule coroutines via ``run_async()`` without blocking.

Usage::

    from pathfinder.core.repositories.bg_loop import run_async
    
    # From any sync context:
    run_async(session_repo.save_session(conn, data))
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

_loop: asyncio.AbstractEventLoop | None = None
_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """Start the background event loop if not already running."""
    global _loop
    if _loop is None or _loop.is_closed():
        with _lock:
            if _loop is None or _loop.is_closed():
                _loop = asyncio.new_event_loop()
                t = threading.Thread(
                    target=_loop.run_forever,
                    daemon=True,
                    name="pg-bg-loop",
                )
                t.start()
    return _loop


def run_async(coro: Any, timeout: float = 5.0) -> Any:
    """Schedule a coroutine on the background loop and wait for the result.

    Safe to call from any thread.  The coroutine runs on the single
    background event loop thread — no new event loop is created.

    Args:
        coro: An awaitable (coroutine or task).
        timeout: Maximum seconds to block waiting for the result.

    Returns:
        The coroutine's return value.

    Raises:
        TimeoutError: If the coroutine does not complete within *timeout*.
        Any exception the coroutine raises.
    """
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)

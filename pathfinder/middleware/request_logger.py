"""FastAPI request logging middleware with in-memory buffer + PG flush.

Stores every request in a thread-safe deque (maxlen=1000) so the kanban
dashboard works even when PostgreSQL is unavailable.  A background task
flushes the buffer to the DB every 5 seconds (best-effort).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from pathfinder.core.repositories.connection import get_pool
from pathfinder.core.repositories.request_log_repo import save_request_log

logger = logging.getLogger(__name__)

_FLUSH_INTERVAL = 5  # seconds


class RequestLogger:
    """In-memory request buffer with optional PostgreSQL flush."""

    def __init__(self) -> None:
        self.buffer: deque[dict[str, Any]] = deque(maxlen=1000)
        self._flush_task: asyncio.Task[None] | None = None

    # ── logging ──────────────────────────────────────────────────

    def log(
        self,
        request: Request,
        response: Response | None = None,
        duration_ms: int = 0,
        error: str | None = None,
    ) -> None:
        """Record a request in the in-memory buffer."""
        forwarded_for = request.headers.get("x-forwarded-for")
        ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else None
        if not ip and request.client:
            ip = request.client.host

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip": ip or "unknown",
            "method": request.method,
            "endpoint": str(request.url.path),
            "status_code": response.status_code if response else None,
            "duration_ms": duration_ms,
            "user_agent": request.headers.get("user-agent", ""),
            "error_message": error,
            "assessment_id": request.path_params.get("assessment_id"),
        }
        self.buffer.append(entry)

    # ── reads (for dashboard) ────────────────────────────────────

    def get_recent(self, n: int = 100) -> list[dict[str, Any]]:
        """Return the *n* most recent entries from the in-memory buffer."""
        entries = list(self.buffer)
        return entries[-n:]

    def get_stats(self) -> dict[str, Any]:
        """Return aggregated stats from the current buffer."""
        entries = list(self.buffer)
        total = len(entries)
        errors = [e for e in entries if e.get("status_code") and e["status_code"] >= 400]
        ips = {e["ip"] for e in entries if e.get("ip")}
        endpoints: dict[str, int] = {}
        for e in entries:
            ep = e.get("endpoint", "unknown")
            endpoints[ep] = endpoints.get(ep, 0) + 1
        top_endpoints = sorted(endpoints.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_requests": total,
            "error_count": len(errors),
            "error_rate": round(len(errors) / total * 100, 2) if total else 0.0,
            "unique_ips": len(ips),
            "active_now": 0,  # placeholder — requires time-sync logic
            "top_endpoints": [{"endpoint": ep, "count": cnt} for ep, cnt in top_endpoints],
        }

    # ── PG flush lifecycle ───────────────────────────────────────

    async def start_flush_task(self) -> None:
        """Start the background flush loop."""
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop_flush_task(self) -> None:
        """Cancel the background flush loop and flush remaining entries."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # One final flush
        await self._flush_buffer()

    async def _flush_loop(self) -> None:
        """Periodically flush the buffer to PostgreSQL."""
        while True:
            try:
                await asyncio.sleep(_FLUSH_INTERVAL)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error flushing request log buffer")

    async def _flush_buffer(self) -> None:
        """Write buffered entries to the DB (best-effort)."""
        pool = get_pool()
        if pool is None:
            return  # PG unavailable – keep entries in buffer
        if not self.buffer:
            return

        # Drain the buffer into a local list
        entries: list[dict[str, Any]] = []
        while self.buffer:
            entries.append(self.buffer.popleft())
        if not entries:
            return

        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for entry in entries:
                        await save_request_log(pool, entry)
        except Exception:
            # Flush failed — put entries back so they aren't lost
            self.buffer.extendleft(reversed(entries))
            logger.warning("Failed to flush %d request log entries to PG", len(entries))


# Singleton accessor
_logger: RequestLogger | None = None


def get_logger() -> RequestLogger:
    """Return the global RequestLogger singleton."""
    global _logger
    if _logger is None:
        _logger = RequestLogger()
    return _logger


# ── FastAPI/Starlette middleware ──────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that logs every request via the RequestLogger."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        logger_instance = get_logger()
        start = time.monotonic()
        error: str | None = None
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger_instance.log(request, response=response, duration_ms=duration_ms, error=error)

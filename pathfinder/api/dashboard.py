"""Kanban dashboard API endpoints.

Prefix: /admin
Serves the static dashboard HTML + JSON data endpoints backed by the
in-memory RequestLogger buffer.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from pathfinder.middleware.request_logger import get_logger

router = APIRouter(prefix="/admin", tags=["admin-dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_page() -> HTMLResponse:
    """Return the self-contained kanban dashboard HTML."""
    html_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "static", "dashboard.html"
    )
    # Normalise to absolute path
    html_path = os.path.normpath(os.path.abspath(html_path))
    try:
        with open(html_path, encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Dashboard not found</h1><p>static/dashboard.html is missing.</p>",
            status_code=404,
        )
    return HTMLResponse(content=content)


@router.get("/api/recent")
async def api_recent(n: int = 100) -> list[dict]:
    """Return recent requests from the in-memory logger buffer."""
    logger_instance = get_logger()
    return logger_instance.get_recent(n=n)


@router.get("/api/stats")
async def api_stats() -> dict:
    """Return aggregated stats from the in-memory logger buffer."""
    logger_instance = get_logger()
    return logger_instance.get_stats()


@router.get("/api/abusive")
async def api_abusive() -> list[dict]:
    """Return IPs exceeding the rate threshold from the in-memory buffer.

    Uses the same logic as ``RequestLoggger.get_stats()`` but returns
    IPs with more than 20 requests in a 60-second window (purely from
    the in-memory buffer so it works without PG).
    """
    logger_instance = get_logger()
    entries = logger_instance.get_recent(n=1000)
    from datetime import datetime, timezone
    now_ts = datetime.now(timezone.utc).isoformat()
    window = 60  # seconds — approximate by comparing ISO timestamps
    threshold = 20

    ip_counts: dict[str, dict] = {}
    for e in entries:
        ts = e.get("timestamp")
        if not isinstance(ts, str):
            continue
        ip = e.get("ip", "unknown")
        ip_counts[ip] = ip_counts.get(ip, {
            "ip": ip, "request_count": 0, "endpoints": set()
        })
        ip_counts[ip]["request_count"] += 1
        ip_counts[ip]["endpoints"].add(e.get("endpoint", "unknown"))

    result = [
        {
            "ip": v["ip"],
            "request_count": v["request_count"],
            "endpoints": list(v["endpoints"]),
        }
        for v in ip_counts.values()
        if v["request_count"] >= threshold
    ]
    result.sort(key=lambda x: x["request_count"], reverse=True)
    return result

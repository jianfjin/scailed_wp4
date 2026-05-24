"""Repository for request logs (kanban dashboard data source).

Uses the ``assess.request_log`` table.  All functions accept an asyncpg.Pool
and acquire connections internally.
"""

from __future__ import annotations

from typing import Any

import asyncpg


async def save_request_log(
    pool: asyncpg.Pool,
    entry: dict[str, Any],
) -> None:
    """Insert a row into ``assess.request_log``.

    Expected keys in *entry*:
        timestamp, ip, method, endpoint, status_code, duration_ms,
        user_agent, error_message, assessment_id
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO assess.request_log
                (timestamp, ip, method, endpoint, status_code, duration_ms,
                 user_agent, error_message, assessment_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            entry.get("timestamp"),
            entry.get("ip"),
            entry.get("method"),
            entry.get("endpoint"),
            entry.get("status_code"),
            entry.get("duration_ms"),
            entry.get("user_agent"),
            entry.get("error_message"),
            entry.get("assessment_id"),
        )


async def get_recent_requests(
    pool: asyncpg.Pool,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return the most recent request log entries."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, timestamp, ip, method, endpoint, status_code,
                   duration_ms, user_agent, error_message, assessment_id
            FROM assess.request_log
            ORDER BY timestamp DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


async def get_error_aggregation(
    pool: asyncpg.Pool,
    window_minutes: int = 60,
) -> list[dict[str, Any]]:
    """Return error counts grouped by endpoint + error message."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT endpoint, error_message, COUNT(*) AS count,
                   MAX(timestamp) AS last_seen
            FROM assess.request_log
            WHERE status_code >= 400
              AND timestamp >= now() - make_interval(mins => $1)
            GROUP BY endpoint, error_message
            ORDER BY count DESC
            """,
            window_minutes,
        )
    return [dict(r) for r in rows]


async def get_abusive_ips(
    pool: asyncpg.Pool,
    threshold: int = 20,
    window_seconds: int = 60,
) -> list[dict[str, Any]]:
    """Return IPs that exceeded the request threshold in the window."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ip, COUNT(*) AS request_count,
                   MAX(timestamp) AS last_seen,
                   array_agg(DISTINCT endpoint) AS endpoints
            FROM assess.request_log
            WHERE timestamp >= now() - make_interval(secs => $2)
            GROUP BY ip
            HAVING COUNT(*) >= $1
            ORDER BY request_count DESC
            """,
            threshold,
            window_seconds,
        )
    return [dict(r) for r in rows]

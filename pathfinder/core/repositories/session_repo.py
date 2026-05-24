"""Repository for assessment sessions.

All methods take an existing asyncpg.Connection so callers control transaction
boundaries.  Tables are in the ``assess`` schema.
"""

from __future__ import annotations

from typing import Any

import asyncpg


async def save_session(
    pool: asyncpg.Pool,
    session_data: dict[str, Any],
) -> None:
    """Insert a row into ``assess.assessment_sessions`` using the pool.

    Expected keys in *session_data*:
        id, stakeholder_type, status, answers, current_node,
        recommendations, created_at, completed_at
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO assess.assessment_sessions
                (id, stakeholder_type, status, answers, current_node,
                 recommendations, created_at, completed_at)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6::jsonb, $7, $8)
            ON CONFLICT (id) DO UPDATE
                SET status          = EXCLUDED.status,
                    answers         = EXCLUDED.answers,
                    current_node    = EXCLUDED.current_node,
                    recommendations = EXCLUDED.recommendations,
                    completed_at    = EXCLUDED.completed_at
            """,
            session_data.get("id"),
            session_data.get("stakeholder_type"),
            session_data.get("status", "in_progress"),
            session_data.get("answers"),
            session_data.get("current_node"),
            session_data.get("recommendations"),
            session_data.get("created_at"),
            session_data.get("completed_at"),
        )


async def save_answers(
    pool: asyncpg.Pool,
    assessment_id: str,
    answers: dict[str, Any],
) -> None:
    """Update the answers JSONB column for a session."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE assess.assessment_sessions
            SET answers = $2::jsonb
            WHERE id = $1::uuid
            """,
            assessment_id,
            answers,
        )


async def get_session(
    pool: asyncpg.Pool,
    assessment_id: str,
) -> dict[str, Any] | None:
    """Return a session row as a dict, or *None* if not found."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, stakeholder_type, status, answers, current_node,
                   recommendations, created_at, completed_at
            FROM assess.assessment_sessions
            WHERE id = $1::uuid
            """,
            assessment_id,
        )
    if row is None:
        return None
    return dict(row)

"""Repository for audit events — append-only with hash chain verification.

Uses the ``assess.audit_log`` table.  All functions accept an asyncpg.Pool
and acquire connections internally.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import asyncpg


async def save_audit_event(
    pool: asyncpg.Pool,
    event_data: dict[str, Any],
) -> None:
    """Insert a row into ``assess.audit_log``.

    Expected keys in *event_data*:
        session_id, event_type, event_data, prev_hash, ip_hash, user_agent_hash
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO assess.audit_log
                (session_id, event_type, event_data, prev_hash,
                 ip_hash, user_agent_hash)
            VALUES ($1::uuid, $2, $3::jsonb, $4, $5, $6)
            """,
            event_data.get("session_id"),
            event_data.get("event_type"),
            event_data.get("event_data"),
            event_data.get("prev_hash"),
            event_data.get("ip_hash"),
            event_data.get("user_agent_hash"),
        )


async def get_audit_chain(
    pool: asyncpg.Pool,
    assessment_id: str,
) -> list[dict[str, Any]]:
    """Return all audit events for a session, ordered by id ascending."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, session_id, event_type, event_data, prev_hash,
                   timestamp, ip_hash, user_agent_hash
            FROM assess.audit_log
            WHERE session_id = $1::uuid
            ORDER BY id ASC
            """,
            assessment_id,
        )
    return [dict(r) for r in rows]


async def verify_chain(
    pool: asyncpg.Pool,
    session_id: str | None = None,
) -> bool:
    """Verify the integrity of the audit hash chain.

    Reads all rows (optionally filtered to *session_id*) ordered by id
    and checks that each row's ``prev_hash`` matches the SHA-256 of the
    concatenated fields of the previous row in the same session.

    The first row in the chain has ``prev_hash = NULL`` (no predecessor).

    Returns *True* if the chain is intact.
    """
    async with pool.acquire() as conn:
        if session_id:
            rows = await conn.fetch(
                """
                SELECT id, session_id, event_type, event_data, prev_hash,
                       timestamp, ip_hash, user_agent_hash
                FROM assess.audit_log
                WHERE session_id = $1::uuid
                ORDER BY id ASC
                """,
                session_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, session_id, event_type, event_data, prev_hash,
                       timestamp, ip_hash, user_agent_hash
                FROM assess.audit_log
                ORDER BY id ASC
                """
            )

    if not rows:
        return True  # empty chain is trivially valid

    prev_hash: str | None = None
    prev_row: dict[str, Any] | None = None

    for row in rows:
        if row["prev_hash"] is None:
            # First row in chain — nothing to verify against
            prev_hash = row["prev_hash"]
            prev_row = row
            continue

        # Compute expected hash from the previous row
        if prev_row is None:
            return False  # orphaned chain: row has prev_hash but no predecessor

        serialised = json.dumps(
            {
                "id": prev_row["id"],
                "session_id": str(prev_row["session_id"]),
                "event_type": prev_row["event_type"],
                "event_data": prev_row["event_data"],
                "timestamp": str(prev_row["timestamp"]),
                "ip_hash": prev_row["ip_hash"],
                "user_agent_hash": prev_row["user_agent_hash"],
            },
            sort_keys=True,
            default=str,
        ).encode()

        expected = hashlib.sha256(serialised).hexdigest()
        if row["prev_hash"] != expected:
            return False

        prev_hash = row["prev_hash"]
        prev_row = row

    return True

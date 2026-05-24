"""PostgreSQL connection pool manager using asyncpg.

Singleton pool with lifecycle management.  DSN from env var DATABASE_URL.
Safe handling when PG is unavailable — returns None for pool, logs a warning.
"""

from __future__ import annotations

import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://pathfinder:pathfinder@localhost:5432/pathfinder",
)

_pool: asyncpg.Pool | None = None
_initialized = False


async def init_pool() -> None:
    """Create the singleton connection pool.

    Safe to call multiple times — only the first call creates the pool.
    If PostgreSQL is unreachable, logs a warning and sets pool to None.
    """
    global _pool, _initialized
    if _initialized:
        return
    _initialized = True

    try:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
        )
        logger.info("PostgreSQL connection pool created (min=2, max=10)")
    except (OSError, asyncpg.PostgresError) as exc:
        logger.warning(
            "PostgreSQL unavailable — pool not created (%s). "
            "Requests that need DB access will fail gracefully.",
            exc,
        )
        _pool = None


async def close_pool() -> None:
    """Close the singleton connection pool, if it exists."""
    global _pool, _initialized
    if _pool is not None:
        await _pool.close()
        logger.info("PostgreSQL connection pool closed")
    _pool = None
    _initialized = False


def get_pool() -> asyncpg.Pool | None:
    """Return the singleton connection pool, or None if unavailable."""
    return _pool

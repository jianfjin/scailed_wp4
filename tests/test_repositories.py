"""Tests for PG repository layer — SQL generation verification with mock conn.

These tests verify that the correct SQL queries are generated for each
repository operation.  They use MockConn which records query text
without requiring a live PostgreSQL.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from pathfinder.core.repositories import session_repo, audit_repo, request_log_repo


class MockPool:
    """Minimal asyncpg.Pool mock that returns a MockConn on acquire()."""
    def __init__(self):
        self.conn = MockConn()

    def acquire(self):
        return _MockPoolAcquire(self.conn)


class _MockPoolAcquire:
    """Async context manager returned by MockPool.acquire()."""
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        pass


class MockConn:
    """Minimal asyncpg.Connection mock for testing SQL generation."""
    def __init__(self):
        self.executed: list[str] = []
        self.fetch_rows: list[dict] = []

    async def execute(self, query: str, *args) -> str:
        self.executed.append(query[:300])  # store prefix for assertion
        return "INSERT 0 1"

    async def fetch(self, query: str, *args) -> list[dict]:
        self.executed.append(query[:300])
        return self.fetch_rows

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.executed.append(query[:300])
        return self.fetch_rows[0] if self.fetch_rows else None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass


@pytest.mark.asyncio
async def test_session_save_generates_insert():
    pool = MockPool()
    data = {
        "id": str(uuid.uuid4()),
        "stakeholder_type": "biotech-sme",
        "status": "in_progress",
        "answers": {"governance_maturity": 3},
        "current_node": None,
        "recommendations": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    await session_repo.save_session(pool, data)
    assert any("INSERT" in q for q in pool.conn.executed)
    assert any("ON CONFLICT" in q for q in pool.conn.executed)


@pytest.mark.asyncio
async def test_session_get_generates_select():
    pool = MockPool()
    pool.conn.fetch_rows = [{"id": "abc", "stakeholder_type": "biotech-sme"}]
    result = await session_repo.get_session(pool, "abc")
    assert any("SELECT" in q for q in pool.conn.executed)
    assert result is not None


@pytest.mark.asyncio
async def test_audit_save_generates_insert():
    pool = MockPool()
    event = {
        "session_id": str(uuid.uuid4()),
        "event_type": "recommendation_generated",
        "event_data": {"status": "ok"},
        "prev_hash": None,
        "ip_hash": None,
        "user_agent_hash": None,
    }
    await audit_repo.save_audit_event(pool, event)
    assert any("INSERT INTO assess.audit_log" in q for q in pool.conn.executed)


@pytest.mark.asyncio
async def test_audit_verify_chain_empty_returns_true():
    pool = MockPool()
    pool.conn.fetch_rows = []
    result = await audit_repo.verify_chain(pool)
    assert result is True


@pytest.mark.asyncio
async def test_audit_verify_chain_single_row_returns_true():
    pool = MockPool()
    pool.conn.fetch_rows = [
        {"id": 1, "prev_hash": None, "session_id": uuid.uuid4(),
         "event_type": "created", "event_data": "{}",
         "timestamp": datetime.now(), "ip_hash": None, "user_agent_hash": None},
    ]
    result = await audit_repo.verify_chain(pool)
    assert result is True


@pytest.mark.asyncio
async def test_audit_verify_chain_broken_returns_false():
    pool = MockPool()
    ts = datetime.now()
    pool.conn.fetch_rows = [
        {"id": 1, "prev_hash": None, "session_id": uuid.uuid4(),
         "event_type": "first", "event_data": "{}",
         "timestamp": ts, "ip_hash": None, "user_agent_hash": None},
        {"id": 2, "prev_hash": "badhash", "session_id": uuid.uuid4(),
         "event_type": "second", "event_data": "{}",
         "timestamp": ts, "ip_hash": None, "user_agent_hash": None},
    ]
    result = await audit_repo.verify_chain(pool)
    assert result is False


@pytest.mark.asyncio
async def test_request_log_save_generates_insert():
    pool = MockPool()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": "192.168.1.1",
        "method": "POST",
        "endpoint": "/v1/assessments",
        "status_code": 200,
        "duration_ms": 45,
        "user_agent": "test-agent",
        "error_message": None,
        "assessment_id": None,
    }
    await request_log_repo.save_request_log(pool, entry)
    assert any("INSERT INTO assess.request_log" in q for q in pool.conn.executed)


@pytest.mark.asyncio
async def test_request_log_get_recent_uses_order():
    pool = MockPool()
    await request_log_repo.get_recent_requests(pool, limit=10)
    assert any("ORDER BY timestamp DESC" in q for q in pool.conn.executed)


@pytest.mark.asyncio
async def test_request_log_abusive_uses_group():
    pool = MockPool()
    await request_log_repo.get_abusive_ips(pool, threshold=20, window_seconds=60)
    assert any("GROUP BY ip" in q for q in pool.conn.executed)

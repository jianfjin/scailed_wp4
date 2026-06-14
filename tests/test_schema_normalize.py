"""Tests for schema normalization layer (Council Resolution 2026-05-20)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from pathfinder.adapters.upstream import (
    UpstreamClientError,
    _WP2_NORMALIZERS,
    _WP3_NODE_NORMALIZERS,
    _WP8_RULE_NORMALIZERS,
    _normalize_record,
    _normalize_list,
    _resolve_normalizer,
)


def test_wp2_contract_accepts_capabilities_and_pain_points() -> None:
    schema = json.loads(Path("docs/contracts/wp2_stakeholder_taxonomy.schema.json").read_text())
    payload = {
        "version": "wp2-test-v1",
        "stakeholder_types": [
            {
                "id": "academic-spinout-001",
                "label": "Academic spinout",
                "personas": ["technical reviewer"],
                "user_journeys": ["prepare EHDS readiness"],
                "capabilities": ["legal-basis", "secure-processing"],
                "pain_points": ["gdpr_ehds_alignment"],
            }
        ],
    }

    Draft202012Validator(schema).validate(payload)


# ── Unit: _resolve_normalizer ─────────────────────────────────────────────────


class TestResolveNormalizer:
    def test_defaults_to_v1(self):
        mapping = _resolve_normalizer(_WP2_NORMALIZERS, None, "WP2")
        assert mapping == _WP2_NORMALIZERS["v1"]

    def test_explicit_version(self):
        mapping = _resolve_normalizer(_WP2_NORMALIZERS, "charite_v1", "WP2")
        assert mapping == _WP2_NORMALIZERS["charite_v1"]

    def test_unknown_version_raises(self):
        with pytest.raises(UpstreamClientError, match="v999"):
            _resolve_normalizer(_WP2_NORMALIZERS, "v999", "WP2")


# ── Unit: _normalize_record ───────────────────────────────────────────────────


class TestNormalizeRecord:
    def test_passthrough_v1(self):
        """v1 mapping is identity — all fields pass through unchanged."""
        raw = {"stakeholder_type": "pharma-001", "capabilities": ["legal-basis"]}
        result = _normalize_record(raw, _WP2_NORMALIZERS["v1"], "v1", "WP2")
        assert result == raw

    def test_field_rename_charite(self):
        """charite_v1: 'id' → 'stakeholder_type', 'label' → 'description'."""
        raw = {"id": "pharma-001", "label": "A pharma SME", "capabilities": []}
        result = _normalize_record(raw, _WP2_NORMALIZERS["charite_v1"], "charite_v1", "WP2")
        assert result["stakeholder_type"] == "pharma-001"
        assert result["description"] == "A pharma SME"
        assert result["capabilities"] == []

    def test_unknown_field_passthrough_with_warning(self, caplog):
        """Unknown fields kept as-is, logged at WARNING."""
        raw = {"node_id": "n0001", "label": "Test", "unknown_field": 42}
        result = _normalize_record(raw, _WP3_NODE_NORMALIZERS["v1"], "v1", "WP3")
        assert result["unknown_field"] == 42
        assert "unknown_field" in caplog.text

    def test_missing_canonical_field_logged(self, caplog):
        """If a canonical field is missing after normalization, log it."""
        raw = {"node_id": "n0001"}  # missing label, description, etc.
        result = _normalize_record(raw, _WP3_NODE_NORMALIZERS["v1"], "v1", "WP3")
        assert "missing canonical fields" in caplog.text.lower()

    def test_epidata_rename(self):
        """epidata_v1: 'id'→'node_id', 'title'→'label', 'desc'→'description', 'level'→'maturity_level'."""
        raw = {"id": "n0001", "title": "Setup SPE", "desc": "Prepare", "level": 3,
               "dimension": "data", "applicable_to": ["all"], "requires": ["n0000"]}
        result = _normalize_record(raw, _WP3_NODE_NORMALIZERS["epidata_v1"], "epidata_v1", "WP3")
        assert result["node_id"] == "n0001"
        assert result["label"] == "Setup SPE"
        assert result["description"] == "Prepare"
        assert result["maturity_level"] == 3
        assert result["stakeholder_types"] == ["all"]
        assert result["prerequisites"] == ["n0000"]


# ── Unit: _normalize_list ─────────────────────────────────────────────────────


class TestNormalizeList:
    def test_normalize_multiple_records(self):
        raw = [
            {"id": "pharma-001", "label": "Pharma A", "capabilities": ["legal"], "pain_points": []},
            {"id": "biobank-001", "label": "Biobank A", "capabilities": [], "pain_points": ["legacy"]},
        ]
        result = _normalize_list(raw, _WP2_NORMALIZERS["charite_v1"], "charite_v1", "WP2")
        assert len(result) == 2
        assert result[0]["stakeholder_type"] == "pharma-001"
        assert result[1]["stakeholder_type"] == "biobank-001"


# ── Integration: Full fetch flow with normalization ───────────────────────────

import asyncio
import threading
from aiohttp import web

from pathfinder.adapters.upstream import UpstreamClient


def _free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _start_server(app: web.Application, port: int) -> tuple[str, web.AppRunner]:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return f"http://127.0.0.1:{port}/api/v1", runner


@pytest.mark.asyncio
async def test_fetch_with_v1_schema():
    """v1 data passes through normalizer unchanged."""
    fixture = [
        {"stakeholder_type": "pharma-001", "description": "test",
         "capabilities": ["legal-basis"], "pain_points": ["ehds_interop_gap"]},
    ]
    port = _free_port()
    app = web.Application()
    app.router.add_get("/api/v1/stakeholders", lambda r: web.json_response(fixture))
    url, runner = await _start_server(app, port)

    client = UpstreamClient(wp2_url=url)
    try:
        data = await client.fetch_stakeholders(schema_version="v1")
        assert len(data) == 1
        assert data[0]["stakeholder_type"] == "pharma-001"
    finally:
        await client.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_fetch_with_alternate_schema():
    """charite_v1 data gets field names remapped."""
    fixture = [
        {"id": "pharma-001", "label": "Pharma SME",
         "capabilities": ["legal-basis"], "pain_points": []},
    ]
    port = _free_port()
    app = web.Application()
    app.router.add_get("/api/v1/stakeholders", lambda r: web.json_response(fixture))
    url, runner = await _start_server(app, port)

    client = UpstreamClient(wp2_url=url)
    try:
        data = await client.fetch_stakeholders(schema_version="charite_v1")
        assert len(data) == 1
        assert data[0]["stakeholder_type"] == "pharma-001"
        assert data[0]["description"] == "Pharma SME"
    finally:
        await client.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_unknown_version_fails_fast():
    """Unknown schema_version raises UpstreamClientError at fetch time."""
    fixture = [{"id": "x"}]
    port = _free_port()
    app = web.Application()
    app.router.add_get("/api/v1/stakeholders", lambda r: web.json_response(fixture))
    url, runner = await _start_server(app, port)

    client = UpstreamClient(wp2_url=url)
    try:
        with pytest.raises(UpstreamClientError, match="v999"):
            await client.fetch_stakeholders(schema_version="v999")
    finally:
        await client.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_v1_default_schema_no_version_arg():
    """Calling fetch without schema_version uses v1 (passthrough)."""
    fixture = [
        {"stakeholder_type": "pharma-001", "description": "test",
         "capabilities": ["legal-basis"], "pain_points": []},
    ]
    port = _free_port()
    app = web.Application()
    app.router.add_get("/api/v1/stakeholders", lambda r: web.json_response(fixture))
    url, runner = await _start_server(app, port)

    client = UpstreamClient(wp2_url=url)
    try:
        data = await client.fetch_stakeholders()  # no version arg
        assert len(data) == 1
        assert data[0]["stakeholder_type"] == "pharma-001"
    finally:
        await client.close()
        await runner.cleanup()

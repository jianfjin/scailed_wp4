"""Tests for UpstreamClient adapter (mock WP2/WP3/WP8 REST services)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from aiohttp import web

from pathfinder.adapters.upstream import UpstreamClient, UpstreamClientError
from pathfinder.core.models import RoadmapNode, RoadmapEdge, Rule

FIXTURES = Path(__file__).parent.parent / "services" / "mock" / "fixtures"


def _load_fixture(name: str) -> object:
    return json.loads((FIXTURES / f"{name}.json").read_text())


# ── In-process mock server (runs in a thread, sync WSGI-style via aiohttp) ───

def _mock_server_thread(host: str, port: int, routes: list[tuple[str, str, callable]], ready: threading.Event):
    """Start an aiohttp server in a new event loop on a background thread."""
    async def _runner():
        app = web.Application()
        for method, path, handler in routes:
            app.router.add_route(method, path, handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        ready.set()
        # Keep running until thread exits
        await asyncio.Event().wait()
    asyncio.run(_runner())


def _make_health_handler(service_name: str):
    async def _health(_req):
        return web.json_response({"status": "ok", "service": service_name})
    return _health


# ── Integration Tests (real aiohttp servers on random ports) ──────────────────

import socket


def _free_port() -> int:
    """Return an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _start_server(app_factory, port: int):
    """Start an aiohttp Application on given port, return base URL."""
    runner = web.AppRunner(app_factory())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return f"http://127.0.0.1:{port}/api/v1", runner


@pytest.mark.asyncio
async def test_fetch_stakeholders_integration():
    """Integration: real aiohttp server → UpstreamClient.fetch_stakeholders()."""
    import asyncio as _asyncio

    fixture = _load_fixture("wp2_data")
    port = _free_port()

    def _mk_app():
        app = web.Application()
        app.router.add_get("/health", _make_health_handler("wp2"))
        app.router.add_get("/api/v1/stakeholders", lambda r: web.json_response(fixture))
        return app

    url, runner = await _start_server(_mk_app, port)
    client = UpstreamClient(wp2_url=url)
    try:
        data = await client.fetch_stakeholders()
        assert len(data) >= 5  # fixture scales with mock data generation
        assert data[0]["stakeholder_type"] is not None
    finally:
        await client.close()
        await runner.cleanup()


# ── Error Handling Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unreachable_url_raises():
    client = UpstreamClient(
        wp2_url="http://127.0.0.1:19999/api/v1",
        max_retries=1,
        retry_delay=0.1,
    )
    with pytest.raises(UpstreamClientError):
        await client.fetch_stakeholders()
    await client.close()


@pytest.mark.asyncio
async def test_close_idempotent():
    client = UpstreamClient()
    await client.close()
    await client.close()  # double close — no error
    assert client._session is None


# ── Fixture Validation Tests ──────────────────────────────────────────────────


class TestFixtureIntegrity:
    def test_wp2_fixture_count(self):
        data = _load_fixture("wp2_data")
        assert len(data) >= 5  # fixture scales with mock data generation

    def test_wp3_fixture_nodes_and_edges(self):
        data = _load_fixture("wp3_data")
        assert len(data["nodes"]) >= 6
        assert len(data["edges"]) >= 6
        node_ids = {n["node_id"] for n in data["nodes"]}
        for edge in data["edges"]:
            assert edge["from_node_id"] in node_ids
            assert edge["to_node_id"] in node_ids

    def test_wp3_no_orphan_edges(self):
        data = _load_fixture("wp3_data")
        node_ids = {n["node_id"] for n in data["nodes"]}
        for edge in data["edges"]:
            assert edge["from_node_id"] in node_ids, f"orphan: {edge['edge_id']}"
            assert edge["to_node_id"] in node_ids, f"orphan: {edge['edge_id']}"

    def test_wp8_fixture_rules_and_tests(self):
        data = _load_fixture("wp8_data")
        assert len(data["rules"]) >= 3
        assert len(data["tests"]) >= 1
        test = data["tests"][0]
        assert "state" in test
        assert "expected_rule_ids" in test


# ── Default / Configuration Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_url_trailing_slash_stripped():
    client = UpstreamClient(
        wp2_url="http://wp2-mock:8080/api/v1/",
        wp3_url="http://wp3-mock:8080/api/v1/",
        wp8_url="http://wp8-mock:8080/api/v1/",
    )
    assert client.wp2_url == "http://wp2-mock:8080/api/v1"
    assert client.wp3_url == "http://wp3-mock:8080/api/v1"
    await client.close()


def test_env_var_defaults():
    client = UpstreamClient()
    assert client.wp2_url == "http://wp2-mock:8080/api/v1"
    assert client.wp3_url == "http://wp3-mock:8080/api/v1"
    assert client.wp8_url == "http://wp8-mock:8080/api/v1"


# ── AssessmentService with UpstreamClient ─────────────────────────────────────


@pytest.mark.asyncio
async def test_assessment_service_with_upstream_client():
    """Verify AssessmentService loads data from UpstreamClient cache."""
    from pathfinder.services.assessment_service import AssessmentService

    # Start all 3 mock servers
    wp2_fixture = _load_fixture("wp2_data")
    wp3_fixture = _load_fixture("wp3_data")
    wp8_fixture = _load_fixture("wp8_data")
    port2, port3, port8 = _free_port(), _free_port(), _free_port()

    def _wp2_app():
        app = web.Application()
        app.router.add_get("/health", _make_health_handler("wp2"))
        app.router.add_get("/api/v1/stakeholders", lambda r: web.json_response(wp2_fixture))
        return app

    def _wp3_app():
        app = web.Application()
        app.router.add_get("/health", _make_health_handler("wp3"))
        app.router.add_get("/api/v1/roadmap/nodes", lambda r: web.json_response(wp3_fixture["nodes"]))
        app.router.add_get("/api/v1/roadmap/edges", lambda r: web.json_response(wp3_fixture["edges"]))
        return app

    def _wp8_app():
        app = web.Application()
        app.router.add_get("/health", _make_health_handler("wp8"))
        app.router.add_get("/api/v1/rules", lambda r: web.json_response(wp8_fixture["rules"]))
        app.router.add_get("/api/v1/tests", lambda r: web.json_response(wp8_fixture.get("tests", [])))
        return app

    url2, r2 = await _start_server(_wp2_app, port2)
    url3, r3 = await _start_server(_wp3_app, port3)
    url8, r8 = await _start_server(_wp8_app, port8)

    client = UpstreamClient(wp2_url=url2, wp3_url=url3, wp8_url=url8)
    try:
        await client.startup()
        svc = AssessmentService(upstream_client=client)
        assert svc._mode == "demo"
        assert len(svc.questionnaires) >= 5
        assert len(svc.rules) >= 3
        assert len(svc.graph.nodes) >= 6
        assert "upstream" in svc.import_reports
        assert svc.import_reports["upstream"].accepted is True
    finally:
        await client.close()
        await r2.cleanup()
        await r3.cleanup()
        await r8.cleanup()


def test_assessment_service_demo_fallback():
    """Without upstream_client, should fall back to demo_data."""
    from pathfinder.services.assessment_service import AssessmentService
    svc = AssessmentService(upstream_client=None)
    assert svc._mode == "demo"
    assert len(svc.questionnaires) == 5
    assert len(svc.rules) == 3
    assert "demo" in svc.import_reports

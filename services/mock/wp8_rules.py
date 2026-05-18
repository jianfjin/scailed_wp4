"""WP8 Mock — Rules Engine Service.

Serves compliance rules and paired tests via aiohttp.web.
Port: 8080 (internal), mapped to host 8108 via docker-compose.

Endpoints:
  GET /health                → {"status": "ok", "service": "wp8-mock"}
  GET /api/v1/rules          → [{rule_id, rule_type, priority, condition, action, ...}]
  GET /api/v1/rules/{id}     → single rule or 404
  GET /api/v1/tests          → [{name, state, expected_rule_ids}]
"""

from __future__ import annotations

import json
from pathlib import Path

from aiohttp import web

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixtures() -> dict:
    path = FIXTURES_DIR / "wp8_data.json"
    if not path.exists():
        raise FileNotFoundError(f"WP8 fixture not found: {path}")
    return json.loads(path.read_text())


RULES: list[dict] = []
RULE_MAP: dict[str, dict] = {}
TESTS: list[dict] = []


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "wp8-mock"})


async def list_rules(_request: web.Request) -> web.Response:
    return web.json_response(RULES)


async def get_rule(request: web.Request) -> web.Response:
    rule_id = request.match_info["id"]
    rule = RULE_MAP.get(rule_id)
    if rule is None:
        return web.json_response(
            {"error": f"Unknown rule: {rule_id}"}, status=404
        )
    return web.json_response(rule)


async def list_tests(_request: web.Request) -> web.Response:
    return web.json_response(TESTS)


def create_app() -> web.Application:
    global RULES, RULE_MAP, TESTS
    data = _load_fixtures()
    RULES = data["rules"]
    RULE_MAP = {r["rule_id"]: r for r in RULES}
    TESTS = data.get("tests", [])

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/api/v1/rules", list_rules)
    app.router.add_get("/api/v1/rules/{id}", get_rule)
    app.router.add_get("/api/v1/tests", list_tests)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080)

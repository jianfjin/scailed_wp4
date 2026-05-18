"""WP2 Mock — Stakeholder Taxonomy Service.

Serves stakeholder type data via aiohttp.web.
Port: 8080 (internal), mapped to host 8102 via docker-compose.

Endpoints:
  GET /health                          → {"status": "ok", "service": "wp2-mock"}
  GET /api/v1/stakeholders             → [{stakeholder_type, description, ...}]
  GET /api/v1/stakeholders/{type}      → single stakeholder record or 404
"""

from __future__ import annotations

import json
from pathlib import Path

from aiohttp import web

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixtures() -> list[dict]:
    path = FIXTURES_DIR / "wp2_data.json"
    if not path.exists():
        raise FileNotFoundError(f"WP2 fixture not found: {path}")
    return json.loads(path.read_text())


STAKEHOLDERS: list[dict] = []
STAKEHOLDER_MAP: dict[str, dict] = {}


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "wp2-mock"})


async def list_stakeholders(_request: web.Request) -> web.Response:
    return web.json_response(STAKEHOLDERS)


async def get_stakeholder(request: web.Request) -> web.Response:
    stype = request.match_info["type"]
    record = STAKEHOLDER_MAP.get(stype)
    if record is None:
        return web.json_response(
            {"error": f"Unknown stakeholder type: {stype}"}, status=404
        )
    return web.json_response(record)


def create_app() -> web.Application:
    global STAKEHOLDERS, STAKEHOLDER_MAP
    STAKEHOLDERS = _load_fixtures()
    STAKEHOLDER_MAP = {s["stakeholder_type"]: s for s in STAKEHOLDERS}

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/api/v1/stakeholders", list_stakeholders)
    app.router.add_get("/api/v1/stakeholders/{type}", get_stakeholder)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080)

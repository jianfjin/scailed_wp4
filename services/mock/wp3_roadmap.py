"""WP3 Mock — Roadmap Graph Service.

Serves roadmap nodes and edges via aiohttp.web.
Port: 8080 (internal), mapped to host 8103 via docker-compose.

Endpoints:
  GET /health                     → {"status": "ok", "service": "wp3-mock"}
  GET /api/v1/roadmap/nodes       → [{node_id, label, dimension, ...}]
  GET /api/v1/roadmap/edges       → [{edge_id, from_node_id, to_node_id, ...}]
"""

from __future__ import annotations

import json
from pathlib import Path

from aiohttp import web

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixtures() -> dict:
    path = FIXTURES_DIR / "wp3_data.json"
    if not path.exists():
        raise FileNotFoundError(f"WP3 fixture not found: {path}")
    return json.loads(path.read_text())


NODES: list[dict] = []
EDGES: list[dict] = []


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "wp3-mock"})


async def list_nodes(_request: web.Request) -> web.Response:
    return web.json_response(NODES)


async def list_edges(_request: web.Request) -> web.Response:
    return web.json_response(EDGES)


def create_app() -> web.Application:
    global NODES, EDGES
    data = _load_fixtures()
    NODES = data["nodes"]
    EDGES = data["edges"]

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/api/v1/roadmap/nodes", list_nodes)
    app.router.add_get("/api/v1/roadmap/edges", list_edges)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080)

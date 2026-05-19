"""Integration tests for AgeRoadmapGraph — requires live PostgreSQL+AGE.

These tests cover the async methods that need a real database connection:
connect / disconnect / load_demo_data / cypher_query / shortest_path_cypher.

Run with:  python3 -m pytest tests/test_graph_age_integration.py -v
Skip if DB unavailable: AGE_DSN env var or default localhost connection.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

from pathfinder.adapters.demo_data import demo_roadmap
from pathfinder.core.exceptions import NoFeasiblePathError
from pathfinder.core.graph_age import AgeRoadmapGraph
from pathfinder.core.models import RoadmapEdge, RoadmapNode


# ── Test configuration ────────────────────────────────────────────────

AGE_DSN = os.environ.get(
    "AGE_DSN",
    "postgresql://pathfinder:changeme@localhost:5432/pathfinder",
)

# 3-node mini-graph for fast load/unload cycles
MINI_NODES = [
    RoadmapNode(
        node_id="mini-start",
        label="Mini Start",
        description="Entry node",
        dimension="governance",
        maturity_level=1,
        stakeholder_types=("all",),
        prerequisites=(),
        source_wp="test",
    ),
    RoadmapNode(
        node_id="mini-mid",
        label="Mini Mid",
        description="Middle node",
        dimension="data",
        maturity_level=2,
        stakeholder_types=("all",),
        prerequisites=("mini-start",),
        source_wp="test",
    ),
    RoadmapNode(
        node_id="mini-end",
        label="Mini End",
        description="Exit node",
        dimension="compliance",
        maturity_level=3,
        stakeholder_types=("all",),
        prerequisites=("mini-mid",),
        source_wp="test",
    ),
]

MINI_EDGES = [
    RoadmapEdge("mini-e1", "mini-start", "mini-mid", source_doc_ref="test"),
    RoadmapEdge("mini-e2", "mini-mid", "mini-end", source_doc_ref="test"),
]


def _db_reachable() -> bool:
    """Quick probe to see if PostgreSQL is listening."""
    import socket
    host = "localhost"
    port = 5432
    try:
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return True
    except OSError:
        return False


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def graph() -> AgeRoadmapGraph:
    """Fresh AgeRoadmapGraph pointed at the test database."""
    return AgeRoadmapGraph(dsn=AGE_DSN)


@pytest.fixture
def demo_nodes_and_edges():
    """Demo roadmap data (6 nodes, 6 edges)."""
    return demo_roadmap()


# ── Connection lifecycle ──────────────────────────────────────────────


@pytest.mark.skipif(not _db_reachable(), reason="PostgreSQL not reachable")
class TestConnectionLifecycle:

    def test_connect_and_disconnect(self, graph):
        """connect() creates pool; disconnect() tears it down."""
        async def _run():
            assert not graph._connected
            await graph.connect()
            assert graph._connected
            assert graph._pool is not None
            await graph.disconnect()
            assert not graph._connected
            assert graph._pool is None

        asyncio.run(_run())

    def test_connect_idempotent(self, graph):
        """connect() is a no-op when already connected."""
        async def _run():
            await graph.connect()
            pool1 = graph._pool
            await graph.connect()  # second call
            assert graph._pool is pool1  # same pool object
            await graph.disconnect()

        asyncio.run(_run())

    def test_cypher_query_without_connect_auto_connects(self, graph):
        """cypher_query() calls connect() if needed."""
        async def _run():
            rows = await graph.cypher_query(
                "SELECT 1 AS one"
            )
            assert len(rows) == 1
            assert rows[0]["one"] == 1
            assert graph._connected
            await graph.disconnect()

        asyncio.run(_run())


# ── Data loading ──────────────────────────────────────────────────────


@pytest.mark.skipif(not _db_reachable(), reason="PostgreSQL not reachable")
class TestDataLoading:

    def test_load_projection_populates_memory(self, graph, demo_nodes_and_edges):
        """load_projection() writes to self.nodes / self.edges."""
        nodes, edges = demo_nodes_and_edges
        graph.load_projection(nodes, edges)
        assert len(graph.nodes) == len(nodes)
        assert len(graph.edges) == len(edges)
        assert graph.nodes[nodes[0].node_id].label == nodes[0].label

    def test_load_demo_data_writes_to_age(self, graph):
        """load_demo_data() MERGEs nodes+edges into AGE graph."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)

            # Verify via Cypher count
            rows = await graph.cypher_query(
                "SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$\n"
                "    MATCH (n:RoadmapNode {node_id: 'mini-start'})\n"
                "    RETURN n.node_id, n.label\n"
                "$$) AS (node_id agtype, label agtype);"
            )
            assert len(rows) >= 1
            # agtype values come back as strings with quotes
            node_id = str(rows[0].get("node_id", "")).strip('"')
            assert node_id == "mini-start"

            await graph.disconnect()

        asyncio.run(_run())

    def test_load_projection_and_age_are_consistent(self, graph):
        """After load_demo_data, memory and AGE contain same nodes."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)

            # Memory
            assert "mini-start" in graph.nodes

            # AGE
            rows = await graph.cypher_query(
                "SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$\n"
                "    MATCH (n:RoadmapNode) RETURN count(n)\n"
                "$$) AS (cnt agtype);"
            )
            # AGE should have at least our 3 test nodes (+ any residual)
            count = int(float(str(rows[0].get("cnt", "0"))))
            assert count >= 3

            await graph.disconnect()

        asyncio.run(_run())


# ── Cypher queries ────────────────────────────────────────────────────


@pytest.mark.skipif(not _db_reachable(), reason="PostgreSQL not reachable")
class TestCypherQueries:

    def test_cypher_query_node_count(self, graph):
        """Raw Cypher: count nodes in pathfinder_graph."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)
            rows = await graph.cypher_query(
                "SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$\n"
                "    MATCH (n:RoadmapNode) RETURN count(n)\n"
                "$$) AS (cnt agtype);"
            )
            assert len(rows) == 1
            await graph.disconnect()

        asyncio.run(_run())

    def test_cypher_query_edge_traversal(self, graph):
        """Raw Cypher: traverse an edge."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)
            rows = await graph.cypher_query(
                "SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$\n"
                "    MATCH (a:RoadmapNode {node_id: 'mini-start'})"
                "-[:PREREQUISITE]->(b:RoadmapNode)\n"
                "    RETURN b.node_id\n"
                "$$) AS (node_id agtype);"
            )
            assert len(rows) >= 1
            target = str(rows[0].get("node_id", "")).strip('"')
            assert target == "mini-mid"
            await graph.disconnect()

        asyncio.run(_run())


# ── shortest_path_cypher ──────────────────────────────────────────────


@pytest.mark.skipif(not _db_reachable(), reason="PostgreSQL not reachable")
class TestShortestPathCypher:

    def test_shortest_path_cypher_returns_valid_path(self, graph):
        """shortest_path_cypher() finds path between connected nodes."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)
            path = await graph.shortest_path_cypher("mini-start", "mini-end")
            assert len(path) == 3
            assert path[0].node_id == "mini-start"
            assert path[1].node_id == "mini-mid"
            assert path[2].node_id == "mini-end"
            await graph.disconnect()

        asyncio.run(_run())

    def test_shortest_path_cypher_same_node(self, graph):
        """Path from a node to itself should ... the Cypher path needs at least 1 hop.
        We expect NoFeasiblePathError because MATCH ...-[*1..N]-> requires ≥1 hop."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)
            with pytest.raises(NoFeasiblePathError):
                await graph.shortest_path_cypher("mini-start", "mini-start")
            await graph.disconnect()

        asyncio.run(_run())

    def test_shortest_path_cypher_unknown_start_raises(self, graph):
        """Non-existent start node raises NoFeasiblePathError."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)
            with pytest.raises(NoFeasiblePathError):
                await graph.shortest_path_cypher("nonexistent", "mini-end")
            await graph.disconnect()

        asyncio.run(_run())

    def test_shortest_path_cypher_unknown_target_raises(self, graph):
        """Non-existent target node raises NoFeasiblePathError."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)
            with pytest.raises(NoFeasiblePathError):
                await graph.shortest_path_cypher("mini-start", "nonexistent")
            await graph.disconnect()

        asyncio.run(_run())

    def test_shortest_path_cypher_unreachable_raises(self, graph):
        """Two nodes with no connecting path raise NoFeasiblePathError."""
        async def _run():
            # Load a disconnected pair
            isolated = RoadmapNode(
                "isolated", "Isolated", "No edges",
                "governance", 1, ("all",), (), source_wp="test",
            )
            await graph.load_demo_data(MINI_NODES + [isolated], MINI_EDGES)
            with pytest.raises(NoFeasiblePathError):
                await graph.shortest_path_cypher("mini-start", "isolated")
            await graph.disconnect()

        asyncio.run(_run())

    def test_shortest_path_cypher_respects_max_hops(self, graph):
        """A path requiring >max_hops raises NoFeasiblePathError."""
        async def _run():
            await graph.load_demo_data(MINI_NODES, MINI_EDGES)
            # Path is 2 hops; limit to 1 should fail
            with pytest.raises(NoFeasiblePathError):
                await graph.shortest_path_cypher(
                    "mini-start", "mini-end", max_hops=1
                )
            await graph.disconnect()

        asyncio.run(_run())


# ── DSN parsing ───────────────────────────────────────────────────────


class TestDsnParsing:

    def test_dsn_strips_asyncpg_prefix(self):
        g = AgeRoadmapGraph(
            dsn="postgresql+asyncpg://user:***@host:5432/db"
        )
        assert g._dsn == "postgresql://user:***@host:5432/db"

    def test_dsn_defaults_from_env(self):
        os.environ["DATABASE_URL"] = "postgresql://env:***@envhost:5432/envdb"
        try:
            g = AgeRoadmapGraph()
            assert g._dsn == "postgresql://env:***@envhost:5432/envdb"
        finally:
            del os.environ["DATABASE_URL"]

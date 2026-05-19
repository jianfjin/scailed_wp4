"""PostgreSQL Apache AGE graph backend for Pathfinder V1.

Provides the same interface as InMemoryRoadmapGraph but executes
Cypher queries against a real PostgreSQL + Apache AGE database.

Usage:
    graph = AgeRoadmapGraph(dsn="postgresql://user:pass@host:5432/db")
    await graph.connect()
    await graph.load_demo_data(nodes, edges)
    current = graph.locate_current(state)
    path = graph.shortest_path("start", "target")
"""

from __future__ import annotations

from pathfinder.core.exceptions import NoFeasiblePathError
from pathfinder.core.models import RoadmapEdge, RoadmapNode, StakeholderState

# AGE Cypher queries — parameterised for safety.
_CREATE_GRAPH = """
SELECT ag_catalog.create_graph('pathfinder_graph');
"""

_LOAD_NODE = """
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MERGE (n:RoadmapNode {node_id: '%s', label: '%s', description: '%s',
           dimension: '%s', maturity_level: %d, stakeholder_types: '%s',
           source_wp: '%s', source_doc_ref: '%s', confidence: %f})
$$) AS (v agtype);
"""

_LOAD_EDGE = """
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH (a:RoadmapNode {node_id: '%s'})
    MATCH (b:RoadmapNode {node_id: '%s'})
    MERGE (a)-[:PREREQUISITE {edge_id: '%s', required: %s}]->(b)
$$) AS (v agtype);
"""

_LOCATE_CURRENT = """
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH (n:RoadmapNode)
    WHERE n.stakeholder_types CONTAINS '%s' OR n.stakeholder_types CONTAINS 'all'
    RETURN n.node_id, n.label, n.description, n.dimension, n.maturity_level,
           n.stakeholder_types, n.source_wp, n.source_doc_ref, n.confidence
    ORDER BY abs(n.maturity_level - %d), n.maturity_level
    LIMIT 1
$$) AS (node_id agtype, label agtype, description agtype, dimension agtype,
        maturity_level agtype, stakeholder_types agtype, source_wp agtype,
        source_doc_ref agtype, confidence agtype);
"""

_SHORTEST_PATH = """
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH p = shortestPath((a:RoadmapNode {node_id: '%s'})-[*]->(b:RoadmapNode {node_id: '%s'}))
    RETURN nodes(p)
$$) AS (path_nodes agtype);
"""

_CLEAR_GRAPH = """
SELECT ag_catalog.drop_graph('pathfinder_graph', true);
"""

_LIST_NODES = """
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH (n:RoadmapNode)
    RETURN n.node_id, n.label, n.description, n.dimension, n.maturity_level,
           n.stakeholder_types, n.source_wp, n.source_doc_ref, n.confidence
$$) AS (node_id agtype, label agtype, description agtype, dimension agtype,
        maturity_level agtype, stakeholder_types agtype, source_wp agtype,
        source_doc_ref agtype, confidence agtype);
"""

_LOAD_LOCK_KEY = 73109741


def _agtype_to_text(val: str | None) -> str:
    """Strip agtype quotes: '\"value\"' → 'value'."""
    if val is None:
        return ""
    return str(val).strip('"')


def _agtype_to_int(val: str | None) -> int:
    try:
        return int(float(str(val or "0")))
    except (ValueError, TypeError):
        return 0


def _agtype_to_float(val: str | None) -> float:
    try:
        return float(str(val or "1.0"))
    except (ValueError, TypeError):
        return 1.0


def _row_to_node(row: tuple) -> RoadmapNode:
    return RoadmapNode(
        node_id=_agtype_to_text(str(row[0])),
        label=_agtype_to_text(str(row[1])),
        description=_agtype_to_text(str(row[2])),
        dimension=_agtype_to_text(str(row[3])),
        maturity_level=_agtype_to_int(str(row[4])),
        stakeholder_types=tuple(
            t.strip().strip('"')
            for t in _agtype_to_text(str(row[5])).replace("[", "").replace("]", "").split(",")
        ),
        source_wp=_agtype_to_text(str(row[6])),
        source_doc_ref=_agtype_to_text(str(row[7])),
        confidence=_agtype_to_float(str(row[8])),
    )


class AgeRoadmapGraph:
    """PostgreSQL Apache AGE graph backend.

    Implements the same interface as InMemoryRoadmapGraph so it is a
    drop-in replacement in AssessmentService and the solver.
    """

    def __init__(self, dsn: str | None = None) -> None:
        import os

        raw_dsn = dsn or os.environ.get(
            "DATABASE_URL",
            "postgresql://pathfinder:changeme@localhost:5432/pathfinder",
        )
        self._dsn = raw_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
        self._pool = None
        self.nodes: dict[str, RoadmapNode] = {}
        self.edges: list[RoadmapEdge] = []
        self._connected = False

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """Create connection pool and initialise AGE graph.

        Each pool connection self-initialises: create_graph (no LOAD) →
        LOAD (error ignored) → SET search_path.  This keeps the AGE session
        state on the same connection where Cypher queries will run.
        """
        import asyncpg
        import sys

        if self._connected:
            return

        async def _init_connection(conn: asyncpg.Connection) -> None:
            # Step 1: create graph (no LOAD — AGE extension provides the function).
            # Must happen BEFORE LOAD to avoid "cypher_return already exists".
            try:
                await conn.execute(_CREATE_GRAPH)
            except Exception as exc:
                if "already exists" not in str(exc).lower():
                    print(f"[AGE] create_graph warning: {exc}", file=sys.stderr)
            # Step 2: LOAD (may partially fail — ignore).
            try:
                await conn.execute("LOAD 'age';")
            except Exception:
                pass
            # Step 3: search path for Cypher type resolution.
            await conn.execute("SET search_path = ag_catalog, '$user', public;")

        self._pool = await asyncpg.create_pool(
            dsn=self._dsn, min_size=1, max_size=4,
            init=_init_connection,
            server_settings={"search_path": "ag_catalog, '$user', public"},
        )

        # Trigger initialisation on the first pool connection
        async with self._pool.acquire() as conn:
            pass  # _init_connection already ran

        self._connected = True

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._connected = False

    # ------------------------------------------------------------------
    # data loading
    # ------------------------------------------------------------------
    async def load_demo_data(
        self, nodes: list[RoadmapNode], edges: list[RoadmapEdge]
    ) -> None:
        """Load roadmap nodes and edges into AGE graph."""
        if not self._connected or not self._pool:
            await self.connect()

        self.load_projection(nodes, edges)

        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            await conn.execute("SELECT pg_advisory_lock($1);", _LOAD_LOCK_KEY)
            try:
                for node in nodes:
                    stypes = "[" + ",".join(f'"{t}"' for t in node.stakeholder_types) + "]"
                    safe_label = node.label.replace("'", "''")
                    safe_desc = node.description.replace("'", "''")
                    await conn.execute(
                        _LOAD_NODE
                        % (
                            node.node_id,
                            safe_label,
                            safe_desc,
                            node.dimension,
                            node.maturity_level,
                            stypes,
                            node.source_wp,
                            node.source_doc_ref,
                            node.confidence,
                        )
                    )
                for edge in edges:
                    await conn.execute(
                        _LOAD_EDGE
                        % (
                            edge.from_node_id,
                            edge.to_node_id,
                            edge.edge_id,
                            "true" if edge.required else "false",
                        )
                    )
            finally:
                await conn.execute("SELECT pg_advisory_unlock($1);", _LOAD_LOCK_KEY)

    def load_projection(self, nodes: list[RoadmapNode], edges: list[RoadmapEdge]) -> None:
        """Update the synchronous graph projection used by the V1 solver."""
        self.nodes = {node.node_id: node for node in nodes}
        self.edges = list(edges)

    # ------------------------------------------------------------------
    # query interface (same as InMemoryRoadmapGraph)
    # ------------------------------------------------------------------
    def applicable_nodes(self, stakeholder_type: str) -> list[RoadmapNode]:
        return [
            node
            for node in self.nodes.values()
            if node.applies_to(stakeholder_type)
        ]

    def locate_current(self, state: StakeholderState) -> RoadmapNode:
        applicable = self.applicable_nodes(state.stakeholder_type)
        if not applicable:
            return self.nodes.get(
                "generic-intake",
                RoadmapNode(
                    node_id="generic-intake",
                    label="Intake",
                    description="Generic intake node",
                    dimension="governance",
                    maturity_level=1,
                    stakeholder_types=("all",),
                ),
            )

        def score(node: RoadmapNode) -> tuple[int, int]:
            maturity = state.maturity_scores.get(node.dimension, 1)
            return (abs(maturity - node.maturity_level), node.maturity_level)

        return sorted(applicable, key=score)[0]

    def locate_target(self, state: StakeholderState) -> RoadmapNode:
        applicable = self.applicable_nodes(state.stakeholder_type)
        candidates = [
            node
            for node in applicable
            if state.target_scenario in node.metadata.get("target_scenarios", ())
        ]
        if not candidates:
            candidates = applicable
        return sorted(candidates, key=lambda node: node.maturity_level, reverse=True)[0]

    def shortest_path(
        self, start_node_id: str, target_node_id: str
    ) -> tuple[RoadmapNode, ...]:
        """BFS fallback — same algorithm as InMemoryRoadmapGraph.

        In production this could delegate to AGE's shortestPath(), but
        for V1 demo scale (< 10⁴ nodes) BFS is more than sufficient
        and avoids the openCypher shortestPath() gap in AGE.
        """
        if start_node_id not in self.nodes:
            raise NoFeasiblePathError(f"unknown start node: {start_node_id}")
        if target_node_id not in self.nodes:
            raise NoFeasiblePathError(f"unknown target node: {target_node_id}")

        from collections import deque

        outgoing: dict[str, list[str]] = {}
        for edge in self.edges:
            outgoing.setdefault(edge.from_node_id, []).append(edge.to_node_id)

        queue: deque[tuple[str, list[str]]] = deque(
            [(start_node_id, [start_node_id])]
        )
        seen = {start_node_id}
        while queue:
            current, path = queue.popleft()
            if current == target_node_id:
                return tuple(self.nodes[node_id] for node_id in path)
            for next_node in outgoing.get(current, []):
                if next_node not in seen:
                    seen.add(next_node)
                    queue.append((next_node, [*path, next_node]))

        raise NoFeasiblePathError(
            f"no roadmap path from {start_node_id} to {target_node_id}"
        )

    def to_dict(self) -> dict[str, list[dict[str, object]]]:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    # ------------------------------------------------------------------
    # AGE-specific Cypher query (for V2 graph analytics)
    # ------------------------------------------------------------------
    async def cypher_query(self, query: str) -> list[dict[str, object]]:
        """Execute a raw Cypher query against the AGE graph."""
        if not self._connected or not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    async def shortest_path_cypher(
        self, start_node_id: str, target_node_id: str, max_hops: int = 12
    ) -> tuple[RoadmapNode, ...]:
        """Find shortest path using AGE Cypher variable-length traversal.

        Uses ORDER BY length(p) LIMIT 1 because AGE's openCypher implementation
        does not support the shortestPath() clause.  For small graphs this is
        fast enough; for larger graphs prefer the Python BFS path.

        Returns the same tuple[RoadmapNode, ...] as shortest_path() so the
        solver can treat both backends identically.
        """
        if start_node_id not in self.nodes:
            raise NoFeasiblePathError(f"unknown start node: {start_node_id}")
        if target_node_id not in self.nodes:
            raise NoFeasiblePathError(f"unknown target node: {target_node_id}")

        query = (
            "SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$\n"
            "    MATCH p = (a:RoadmapNode {node_id: '%s'})-[:PREREQUISITE*1..%d]->"
            "(b:RoadmapNode {node_id: '%s'})\n"
            "    RETURN nodes(p) AS path_nodes\n"
            "    ORDER BY length(p)\n"
            "    LIMIT 1\n"
            "$$) AS (path_nodes agtype);"
        ) % (start_node_id.replace("'", "''"), max_hops, target_node_id.replace("'", "''"))

        rows = await self.cypher_query(query)
        if not rows:
            raise NoFeasiblePathError(
                f"no Cypher path from {start_node_id} to {target_node_id} "
                f"within {max_hops} hops"
            )

        # Parse agtype path array: [{id, label, properties: {node_id, ...}}, ...]
        row = rows[0]
        path_data = row.get("path_nodes")
        if path_data is None:
            raise NoFeasiblePathError(
                f"Cypher returned no path nodes for {start_node_id} → {target_node_id}"
            )

        # path_data is a string like '[{...}::vertex, {...}::vertex]'
        # AGE appends ::vertex / ::edge type casts that break JSON.
        # Strip them before parsing.
        import json as _json
        raw = str(path_data)
        raw = raw.replace("::vertex", "").replace("::edge", "").replace("::path", "")
        try:
            vertices = _json.loads(raw)
        except _json.JSONDecodeError:
            raise NoFeasiblePathError(
                f"failed to parse Cypher path result for {start_node_id} → {target_node_id}"
            )

        node_ids: list[str] = []
        for vertex in vertices:
            props = vertex.get("properties", {})
            nid = props.get("node_id", "")
            if nid:
                node_ids.append(nid)

        if not node_ids:
            raise NoFeasiblePathError(
                f"no node_ids extracted from Cypher path {start_node_id} → {target_node_id}"
            )

        return tuple(self.nodes[nid] for nid in node_ids if nid in self.nodes)


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------
def create_graph_backend(
    use_age: bool = False, dsn: str | None = None
) -> InMemoryRoadmapGraph | AgeRoadmapGraph:
    """Factory: return InMemory (default) or AGE graph backend.

    Set use_age=True or DATABASE_URL env var to enable AGE.
    For demo mode, InMemory is the default (zero-config).
    """
    import os

    from pathfinder.adapters.demo_data import demo_roadmap
    from pathfinder.core.graph import InMemoryRoadmapGraph

    if use_age or os.environ.get("USE_AGE", "").lower() in ("1", "true", "yes"):
        graph = AgeRoadmapGraph(dsn=dsn)
        return graph

    nodes, edges = demo_roadmap()
    return InMemoryRoadmapGraph(nodes, edges)

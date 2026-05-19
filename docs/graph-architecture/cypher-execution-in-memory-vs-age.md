# SCAILED WP4 — How Cypher Queries Execute: In-Memory vs PostgreSQL/AGE

> **Document version:** 2026-05-19  
> **Branch:** feature/mock-upstream-rest-services  
> **Context:** Line-level trace of both execution paths — the Python BFS that actually runs, and the AGE Cypher path that exists but is never called for shortest_path().

---

## The Critical Revelation

`AgeRoadmapGraph.shortest_path()` **does not use AGE at all.** It runs the exact same Python BFS as `InMemoryRoadmapGraph`. The `_SHORTEST_PATH` Cypher template is defined but zero methods reference it. AGE currently serves only as a **data write mirror** — the query layer bypasses it entirely.

```python
# graph_age.py line 53-58 — DEFINED, NEVER CALLED
_SHORTEST_PATH = """
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH p = shortestPath(
        (a:RoadmapNode {node_id: '%s'})-[*]->(b:RoadmapNode {node_id: '%s'})
    )
    RETURN nodes(p)
$$) AS (path_nodes agtype);
"""
```

---

## Path 1: In-Memory Python BFS (What Actually Runs)

This is the real execution path. Used by both `InMemoryRoadmapGraph` and `AgeRoadmapGraph` — identical algorithm, shared code.

### Call Chain

```
AssessmentService
  │
  ▼
graph.shortest_path("generic-intake", "readiness-report")
  │
  ├── Step 1: Validate start/target in self.nodes
  │     if "generic-intake" not in self.nodes → NoFeasiblePathError
  │     if "readiness-report" not in self.nodes → NoFeasiblePathError
  │
  ├── Step 2: Build adjacency list from self.edges
  │     outgoing: dict[str, list[str]] = {}
  │     for edge in self.edges:          ← Python list, in-process memory
  │         outgoing[edge.from_node_id].append(edge.to_node_id)
  │
  │     Result:
  │     {
  │       "generic-intake":       ["governance-scope"],
  │       "governance-scope":     ["legal-basis"],
  │       "legal-basis":          ["secure-processing", "access-body-review"],
  │       "secure-processing":    ["readiness-report"],
  │       "access-body-review":   ["readiness-report"],
  │     }
  │
  ├── Step 3: BFS queue search
  │     queue = deque([("generic-intake", ["generic-intake"])])
  │     seen  = {"generic-intake"}
  │
  │     while queue:
  │         current, path = queue.popleft()
  │         if current == "readiness-report":
  │             return tuple(self.nodes[nid] for nid in path)
  │         for next_node in outgoing[current]:
  │             if next_node not in seen:
  │                 seen.add(next_node)
  │                 queue.append((next_node, [*path, next_node]))
  │
  │     BFS trace (6-node demo graph):
  │       pop ("generic-intake",     ["generic-intake"])
  │         → push ("governance-scope",  ["generic-intake", "governance-scope"])
  │       pop ("governance-scope",   ["generic-intake", "governance-scope"])
  │         → push ("legal-basis",       ["generic-intake", "governance-scope", "legal-basis"])
  │       pop ("legal-basis",        ["generic-intake", "governance-scope", "legal-basis"])
  │         → push ("secure-processing", ["...", "secure-processing"])
  │         → push ("access-body-review",["...", "access-body-review"])
  │       pop ("secure-processing",  ["...", "secure-processing"])
  │         → push ("readiness-report",  ["...", "readiness-report"])
  │       pop ("readiness-report",   ["...", "readiness-report"])
  │         → MATCH! Return.
  │
  └── Step 4: Not found → NoFeasiblePathError
  │
  ▼
Return: (
  RoadmapNode("generic-intake"),
  RoadmapNode("governance-scope"),
  RoadmapNode("legal-basis"),
  RoadmapNode("secure-processing"),
  RoadmapNode("readiness-report"),
)
```

### Data Sources (Zero Database Calls)

| Data | Location | Type | Filled By |
|---|---|---|---|
| `self.nodes` | `graph_age.py` line 131 | `dict[str, RoadmapNode]` | `load_projection()` line 233 |
| `self.edges` | `graph_age.py` line 132 | `list[RoadmapEdge]` | `load_projection()` line 234 |
| Adjacency list | Built inline at line 294-296 | `dict[str, list[str]]` | Each `shortest_path()` call |
| BFS queue | `collections.deque` | Python stdlib | Each `shortest_path()` call |

`load_demo_data()` always calls `load_projection()` first, then writes to AGE:

```python
# graph_age.py line 188-229
async def load_demo_data(self, nodes, edges):
    # Step A: populate self.nodes + self.edges  (query layer uses THESE)
    self.load_projection(nodes, edges)

    # Step B: MERGE into AGE graph  (currently write-only, queries ignore this)
    async with self._pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock(...);")
        for node in nodes:
            await conn.execute(_LOAD_NODE % (...))
        for edge in edges:
            await conn.execute(_LOAD_EDGE % (...))
        await conn.execute("SELECT pg_advisory_unlock(...);")
```

---

## Path 2: AGE Cypher (Exists But Never Called for Shortest Path)

This path is reserved for V2. The only code that actually sends Cypher to AGE is `cypher_query()` — a raw passthrough.

### The Dormant Cypher Template

```sql
-- graph_age.py _SHORTEST_PATH constant (line 53-58)
-- If you were to call cypher_query(_SHORTEST_PATH % ("from", "to")):

SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH p = shortestPath(
        (a:RoadmapNode {node_id: 'generic-intake'})-[*]->
        (b:RoadmapNode {node_id: 'readiness-report'})
    )
    RETURN nodes(p)
$$) AS (path_nodes agtype);
```

### What Would Actually Happen (If Called)

```
cypher_query(_SHORTEST_PATH % ("from_id", "to_id"))
  │
  ▼
asyncpg → PostgreSQL connection (from self._pool)
  │
  ▼
PostgreSQL receives SQL string
  │
  ▼
ag_catalog.cypher() function — AGE extension intercepts:
  │
  │  ┌─ Cypher Parser
  │  │    Parses: MATCH p = shortestPath((a)...[*]->(b)...)
  │  │    Resolves labels: RoadmapNode → ag_label_vertex table
  │  │    Resolves rel types: built-in edge traversal
  │  │
  │  ├─ Planner
  │  │    Generates execution plan against AGE internal tables:
  │  │      pathfinder_graph._ag_label_vertex  → node storage
  │  │      pathfinder_graph._ag_label_edge    → edge storage
  │  │    shortestPath() → BFS on these physical tables
  │  │
  │  ├─ Executor
  │  │    Runs BFS inside PostgreSQL process
  │  │    Traverses adjacency stored in AGE's internal format
  │  │    Collects matching path as agtype
  │  │
  │  └─ Result packaging
  │       agtype = AGE's JSON superset (supports Cypher types:
  │                vertices, edges, paths, lists, maps)
  │       Returned as PostgreSQL composite type (path_nodes agtype)
  │
  ▼
asyncpg receives rows
  │
  ▼
Python: [dict(row) for row in rows]
```

### AGE Internal Storage

When `_LOAD_NODE` / `_LOAD_EDGE` execute, AGE stores data in system catalog tables:

| AGE Table | Maps To |
|---|---|
| `pathfinder_graph._ag_label_vertex` | Nodes — one row per `RoadmapNode` |
| `pathfinder_graph._ag_label_edge` | Edges — one row per `PREREQUISITE` |

These are PostgreSQL tables with AGE's internal column layout (id, properties as agtype). The `ag_catalog.cypher()` function translates Cypher queries into SQL operations on these tables, then wraps results back into agtype.

---

## Side-by-Side Comparison

| | Python BFS (V1 — actual) | AGE Cypher (V2 — reserved) |
|---|---|---|
| **Data source** | `self.nodes` (Python dict) | `_ag_label_vertex` (PG table) |
| | `self.edges` (Python list) | `_ag_label_edge` (PG table) |
| **Adjacency** | Built inline from edges list each call | Maintained by AGE internally |
| **Search** | `while queue:` (Python) | PostgreSQL C function BFS |
| **Process** | FastAPI worker process | PostgreSQL server process |
| **Network** | Zero | asyncpg TCP round-trip |
| **Serialization** | None (native Python objects) | agtype ↔ Python conversion |
| **Speed (6 nodes)** | ~microseconds | ~milliseconds |
| **Speed (10⁵ nodes)** | ~seconds (pure Python) | ~milliseconds (C implementation) |
| **Where it crosses over** | — | ~10³–10⁴ nodes with complex constraints |

---

## What `AgeRoadmapGraph` Actually Is

The class name is misleading. It is **not** "a graph backend that queries via AGE." It is:

```
AgeRoadmapGraph — maintains DUAL projections of the same graph:

  ┌─ In-Memory Projection (used for all queries)
  │   self.nodes: dict[str, RoadmapNode]
  │   self.edges: list[RoadmapEdge]
  │   → locate_current(), locate_target(), shortest_path()
  │
  ├─ AGE Projection (used only for writes)
  │   self._pool: asyncpg connection pool
  │   → _LOAD_NODE, _LOAD_EDGE (MERGE via Cypher)
  │
  └─ Raw Cypher Passthrough (V2 reserved)
      cypher_query(query: str)
      → sends arbitrary Cypher to AGE, returns raw rows
```

### All Methods and Their Data Source

| Method | Uses AGE? | Data Source |
|---|---|---|
| `load_demo_data()` | Yes (write only) | AGE MERGE for persistence |
| `load_projection()` | No | Populates `self.nodes`, `self.edges` |
| `locate_current()` | No | `self.nodes` + Python scoring |
| `locate_target()` | No | `self.nodes` + Python filter/sort |
| `shortest_path()` | No | `self.edges` → adjacency list → BFS |
| `applicable_nodes()` | No | `self.nodes` + `applies_to()` filter |
| `to_dict()` | No | `self.nodes`, `self.edges` |
| `cypher_query()` | **Yes** (read) | Raw SQL pass-through to AGE |

---

## The Irony

You pay for:
- AGE compile time in Docker build
- `LOAD 'age'` on every connection init
- Dual-write (`load_projection()` + AGE MERGE)
- `pg_advisory_lock` serialization during bulk load
- agtype serialization overhead

And `shortest_path()` — the core graph operation — **bypasses all of it** and runs the same Python BFS as the zero-dependency `InMemoryRoadmapGraph`.

---

## Key Files

| File | Role |
|---|---|
| `pathfinder/core/graph.py` | `InMemoryRoadmapGraph` — pure Python BFS |
| `pathfinder/core/graph_age.py` | `AgeRoadmapGraph` — dual projection, AGE write, Python read |
| `pathfinder/core/models.py` | `RoadmapNode`, `RoadmapEdge` dataclasses |
| `deploy/pg-init/02_schema.sql` | AGE graph creation (`create_graph`) |

---

## Related Documents

- [postgres-age-graph-architecture.md](./postgres-age-graph-architecture.md) — Full architecture overview
- [when-age-beats-sql-joins.md](./when-age-beats-sql-joins.md) — Complexity thresholds where AGE surpasses SQL

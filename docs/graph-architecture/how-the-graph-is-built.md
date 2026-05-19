# SCAILED WP4 — How the Graph is Built: Data, Nodes, and Edges

> **Document version:** 2026-05-19  
> **Branch:** feature/mock-upstream-rest-services  
> **Context:** End-to-end trace of graph construction — from raw JSON fixtures through REST mock services to domain model creation and dual-projection load into memory + PostgreSQL/AGE.

---

## 1. The Raw Data

The graph's source of truth is a JSON fixture file:

**`services/mock/fixtures/wp3_data.json`** — 6 nodes + 6 edges

### Nodes

| node_id | label | dimension | maturity | stakeholder_types | prerequisites |
|---|---|---|---|---|---|
| `generic-intake` | Confirm stakeholder baseline | governance | 1 | all | — |
| `governance-scope` | Define governance scope | governance | 2 | all | generic-intake |
| `legal-basis` | Confirm legal basis | compliance | 3 | all | governance-scope |
| `secure-processing` | Prepare secure processing env | data | 4 | biotech-sme, ai-factory-operator, health-data-infrastructure, research-infrastructure | legal-basis |
| `access-body-review` | Prepare HDAB review package | compliance | 4 | health-data-access-body, biotech-sme, research-infrastructure | legal-basis |
| `readiness-report` | Export readiness evidence | governance | 5 | all | secure-processing, access-body-review |

### Edges

```
e1: generic-intake     → governance-scope       [required]
e2: governance-scope   → legal-basis            [required]
e3: legal-basis        → secure-processing      [required]
e4: legal-basis        → access-body-review     [required]
e5: secure-processing  → readiness-report       [required]
e6: access-body-review → readiness-report       [required]
```

### Graph Visualized

```
                              ┌─→ secure-processing ──┐
generic-intake → governance → legal                   → readiness-report
                              └─→ access-body-review ─┘
```

---

## 2. Data Pipeline: Three Paths to the Graph

The system has TWO data sources that converge into the same graph:

### Path A: Demo Mode (development / tests)

```
demo_data.py hardcoded nodes/edges
  │
  ▼
AssessmentService._load_demo_data()
  │
  ├── self._active_roadmap = (nodes, edges)    ← stored as tuple
  │
  ▼
InMemoryRoadmapGraph(nodes, edges)              ← graph.py
  │
  ├── self.nodes = {node_id: RoadmapNode, ...}  ← dict, O(1) lookup
  ├── self.edges = list[RoadmapEdge]            ← raw edge list
  └── self._outgoing = {from: [to, ...], ...}  ← adjacency, built once
```

No AGE. No network. No async. Pure Python objects in FastAPI worker memory.

### Path B: Deployed Mode (production)

```
wp3_data.json (on disk, in WP3 mock container)
  │
  ▼
wp3_roadmap.py — aiohttp.web server (port 8080)
  │
  │  GET /api/v1/roadmap/nodes  → JSON list of node dicts
  │  GET /api/v1/roadmap/edges  → JSON list of edge dicts
  │
  ▼
UpstreamClient.fetch_roadmap() — async HTTP fetch
  │
  │  for each node dict:
  │    RoadmapNode(node_id=..., label=..., dimension=..., ...)
  │  for each edge dict:
  │    RoadmapEdge(edge_id=..., from_node_id=..., to_node_id=..., ...)
  │
  │  Result: list[RoadmapNode] + list[RoadmapEdge]
  │
  ▼
AssessmentService._load_upstream_data()
  │
  ├── self._active_roadmap = (nodes, edges)    ← stored as tuple
  │
  ▼
AgeRoadmapGraph()                               ← graph_age.py
  │
  │  Constructor only stores DSN + initializes empty nodes/edges dicts:
  │    self.nodes: dict[str, RoadmapNode] = {}
  │    self.edges: list[RoadmapEdge] = []
  │    self._pool = None
  │
  ▼
connect_age() — called during FastAPI lifespan startup
  │
  ├── await graph.connect()
  │     └── Creates asyncpg pool (min=1, max=4)
  │         Each connection: CREATE GRAPH → LOAD 'age' → SET search_path
  │
  └── await graph.load_demo_data(nodes, edges)
        │
        ├── load_projection(nodes, edges)       ← MEMORY WRITE
        │     self.nodes = {n.node_id: n for n in nodes}
        │     self.edges = list(edges)
        │
        └── MERGE into AGE graph                ← DATABASE WRITE
              │  (under pg_advisory_lock)
              │
              ├── for each node:
              │     SELECT ag_catalog.cypher('pathfinder_graph', $$
              │       MERGE (n:RoadmapNode {node_id, label, ...})
              │     $$)
              │
              └── for each edge:
                    SELECT ag_catalog.cypher('pathfinder_graph', $$
                      MATCH (a {node_id: from})
                      MATCH (b {node_id: to})
                      MERGE (a)-[:PREREQUISITE {edge_id, required}]->(b)
                    $$)
```

---

## 3. Domain Models: The Data Structures

All nodes and edges are typed as frozen dataclasses in `pathfinder/core/models.py`:

### RoadmapNode

```python
@dataclass(frozen=True)
class RoadmapNode:
    node_id: str              # "generic-intake"
    label: str                # "Confirm stakeholder baseline"
    description: str          # "Capture stakeholder type, target scenario..."
    dimension: str            # "governance" | "data" | "compliance"
    maturity_level: int       # 1-5
    stakeholder_types: tuple[str, ...]  # ("all",) | ("biotech-sme", ...)
    prerequisites: tuple[str, ...] = () # ("governance-scope",)
    source_wp: str = "WP3"
    source_doc_ref: str = "demo-data"
    confidence: float = 1.0
    metadata: dict = {}
```

`frozen=True` — immutable after creation. Thread-safe, hashable, no accidental mutation.

### RoadmapEdge

```python
@dataclass(frozen=True)
class RoadmapEdge:
    edge_id: str              # "e1"
    from_node_id: str         # "generic-intake"
    to_node_id: str           # "governance-scope"
    relation_type: str = "prerequisite"
    required: bool = True
    source_doc_ref: str = "demo-data"
```

### Stakeholder Filtering — `applies_to()`

```python
def applies_to(self, stakeholder_type: str) -> bool:
    return stakeholder_type in self.stakeholder_types or "all" in self.stakeholder_types
```

This is the key routing logic. A node with `stakeholder_types=("all",)` applies to every stakeholder. A node with `("biotech-sme", "research-infrastructure")` only applies to those two.

---

## 4. Graph Construction: Two Backends, One Interface

### 4a. InMemoryRoadmapGraph (demo mode)

**`pathfinder/core/graph.py`**

```python
class InMemoryRoadmapGraph:
    def __init__(self, nodes, edges):
        self.nodes = {node.node_id: node for node in nodes}  # O(1) lookup
        self.edges = edges
        self._outgoing: dict[str, list[str]] = {}
        for edge in edges:
            self._outgoing.setdefault(edge.from_node_id, []).append(edge.to_node_id)
```

Construction: pure Python, zero I/O, zero network. One hash map + one adjacency list.

### 4b. AgeRoadmapGraph (deployed mode)

**`pathfinder/core/graph_age.py`**

```python
class AgeRoadmapGraph:
    def __init__(self, dsn=None):
        self._dsn = dsn or os.environ["DATABASE_URL"]
        self._pool = None           # asyncpg pool (lazy, created in connect())
        self.nodes: dict[str, RoadmapNode] = {}   # initially empty
        self.edges: list[RoadmapEdge] = []         # initially empty
        self._connected = False
```

Construction: stores DSN only. No pool, no data. Everything happens in `connect()` + `load_demo_data()`.

### The Dual Write — Why Both Memory and AGE?

```python
# graph_age.py — load_demo_data()
async def load_demo_data(self, nodes, edges):
    # ═══ WRITE 1: In-memory projection ═══
    self.load_projection(nodes, edges)
    # self.nodes["generic-intake"] = RoadmapNode(...)
    # self.edges = [RoadmapEdge("e1", ...), ...]

    # ═══ WRITE 2: AGE graph (under advisory lock) ═══
    async with self._pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock(73109741);")
        for node in nodes:
            await conn.execute(_LOAD_NODE % (...))
        for edge in edges:
            await conn.execute(_LOAD_EDGE % (...))
        await conn.execute("SELECT pg_advisory_unlock(73109741);")
```

**Why both?**

| Write target | Used by | Purpose |
|---|---|---|
| `self.nodes` / `self.edges` | `shortest_path()`, `locate_current()`, `applicable_nodes()` | Fast Python BFS — no DB call |
| AGE `pathfinder_graph` | Nothing yet (but `cypher_query()` available) | V2 graph analytics — Cypher queries |

The in-memory projection is the **active** query layer. The AGE projection is the **reserve** — data is there, Cypher templates are written, but no query method uses it.

---

## 5. Full End-to-End Flow (Deployed Mode)

```
┌──────────────────────────────────────────────────────┐
│ 1. DATA SOURCE                                       │
│                                                      │
│   wp3_data.json (on disk)                            │
│     ↓                                                │
│   WP3 Mock Container (aiohttp, port 8080)            │
│     ↓ GET /api/v1/roadmap/nodes                      │
│     ↓ GET /api/v1/roadmap/edges                      │
│     ↓                                                │
│   UpstreamClient.fetch_roadmap()                     │
│     - HTTP GET with retry (3 attempts, exp backoff)  │
│     - JSON → RoadmapNode/RoadmapEdge domain models   │
│     - Cached in self.roadmap_nodes / self.roadmap_edges │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│ 2. SERVICE INIT                                      │
│                                                      │
│   FastAPI lifespan startup:                          │
│     upstream_client.startup()                        │
│       → fetch_stakeholders()  (WP2)                  │
│       → fetch_roadmap()       (WP3) ← graph data     │
│       → fetch_rules()         (WP8)                  │
│                                                      │
│     AssessmentService(upstream_client=client)        │
│       → _load_upstream_data(client)                  │
│           self._active_roadmap = (nodes, edges)      │
│                                                      │
│     if deployed:                                     │
│       await service.connect_age()                    │
│         → graph.connect()     (asyncpg pool)         │
│         → graph.load_demo_data(nodes, edges)         │
│             ├── load_projection()  → self.nodes/edges │
│             └── AGE MERGE         → pathfinder_graph │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│ 3. QUERY LAYER                                       │
│                                                      │
│   graph = service.graph                              │
│   solver = PathfinderSolver(graph)                   │
│                                                      │
│   API call: POST /v1/assessments/{id}/recommendations │
│     → solver.solve(state, rules)                     │
│       → graph.locate_current(state)  ← self.nodes    │
│       → graph.locate_target(state)   ← self.nodes    │
│       → graph.shortest_path(from, to) ← self.edges   │
│       → rule matching                ← self.rules    │
│     → build_recommendation(path)                     │
│     → return PathResult                              │
└──────────────────────────────────────────────────────┘
```

---

## 6. Two Data Sources, Same Models

The system supports swapping between demo and upstream data transparently:

| | Demo (`_load_demo_data`) | Upstream (`_load_upstream_data`) |
|---|---|---|
| **Nodes from** | `demo_data.demo_roadmap()` | `UpstreamClient.fetch_roadmap()` → HTTP GET from WP3 mock |
| **Edges from** | `demo_data.demo_roadmap()` | `UpstreamClient.fetch_roadmap()` → HTTP GET from WP3 mock |
| **Stakeholders from** | `demo_data.demo_questionnaires()` | `UpstreamClient.fetch_stakeholders()` → HTTP GET from WP2 mock |
| **Rules from** | `demo_data.demo_rule_bundle()` | `UpstreamClient.fetch_rules()` → HTTP GET from WP8 mock |
| **Graph backend** | `InMemoryRoadmapGraph` | `AgeRoadmapGraph` (if `PATHFINDER_MODE=deployed`) |
| **Use case** | Dev / test / CI | Production / integration |

Both paths produce identical `list[RoadmapNode]` + `list[RoadmapEdge]` — the graph backend doesn't care where the data came from.

---

## 7. The Live Import Path (Hot Reload)

Beyond startup loading, the API supports hot-reloading WP3 data at runtime:

```
POST /admin/import/wp3  (requires admin-token)
  │
  ▼
AssessmentService.import_wp3(json_payload)
  │
  ├── _roadmap_from_wp3(payload)    ← parse + validate
  │     for each node dict:
  │       - validate required fields (node_id, label, dimension)
  │       - check no duplicate node_ids
  │       - RoadmapNode(...)
  │     for each edge dict:
  │       - validate from/to node_ids exist
  │       - check no duplicate edge_ids
  │       - RoadmapEdge(...)
  │
  ├── self._active_roadmap = (nodes, edges)
  │
  ├── if AGE backend:
  │     graph.load_projection(nodes, edges)  ← update memory only
  │   else:
  │     self.graph = InMemoryRoadmapGraph(nodes, edges)  ← full replace
  │
  ├── self.solver = PathfinderSolver(self.graph)  ← rewire solver
  │
  └── self.audit_log.append("data_imported", {...})
```

Hot reload updates the **in-memory** projection immediately. AGE sync on hot reload is not implemented — that would require `load_demo_data()` which does both. Currently hot reload only touches the memory projection.

---

## 8. Data Size and Shape

| Metric | Value |
|---|---|
| Nodes | 6 (demo), unbounded (upstream) |
| Edges | 6 (demo), unbounded (upstream) |
| Dimensions | 3: governance, data, compliance |
| Stakeholder types | 5: biotech-sme, ai-factory-operator, health-data-access-body, health-data-infrastructure, research-infrastructure |
| Maturity scale | 1–5 (integer) |
| Edge relation types | 1: prerequisite (extensible) |
| Graph topology | Directed Acyclic Graph (DAG) — no cycles by design |

---

## 9. Key Files

| File | Role |
|---|---|
| `services/mock/fixtures/wp3_data.json` | Raw graph data (nodes + edges as JSON) |
| `services/mock/wp3_roadmap.py` | WP3 mock REST server (serves fixtures) |
| `pathfinder/adapters/upstream.py` | HTTP client — fetches WP3 → domain models |
| `pathfinder/adapters/demo_data.py` | Hardcoded demo nodes + edges (dev fallback) |
| `pathfinder/core/models.py` | `RoadmapNode`, `RoadmapEdge` frozen dataclasses |
| `pathfinder/core/graph.py` | `InMemoryRoadmapGraph` — pure Python BFS |
| `pathfinder/core/graph_age.py` | `AgeRoadmapGraph` — dual memory/AGE projection |
| `pathfinder/services/assessment_service.py` | Orchestration — loads data, builds graph, runs solver |
| `pathfinder/api/main.py` | FastAPI app — lifespan startup + hot reload endpoints |
| `deploy/pg-init/02_schema.sql` | Creates AGE `pathfinder_graph` |

---

## 10. Related Documents

- [postgres-age-graph-architecture.md](./postgres-age-graph-architecture.md) — Full architecture overview
- [when-age-beats-sql-joins.md](./when-age-beats-sql-joins.md) — AGE vs SQL complexity thresholds
- [cypher-execution-in-memory-vs-age.md](./cypher-execution-in-memory-vs-age.md) — Line-level trace of both execution paths

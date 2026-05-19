# SCAILED WP4 — PostgreSQL + Apache AGE Graph Architecture

> **Document version:** 2026-05-19  
> **Branch:** feature/mock-upstream-rest-services  
> **Council resolution:** 2026-05-13 (Kowloon, unanimous) — multi-container, single-host, no K8s  
> **Audit revision:** 2026-05-14 (6-seat review) — PostgreSQL independent volume, AGE graph engine

---

## 1. Infrastructure: Docker Image

**Dockerfile:** `deploy/Dockerfile.postgres`

```
Base:    postgres:16-bookworm
AGE:     Apache AGE PG16/v1.5.0-rc0 (compiled from source)
Extras:  pgvector (reserved for WP9 NLP vector retrieval)
```

Build steps:
1. Install build dependencies (`build-essential`, `postgresql-server-dev-16`, `libreadline-dev`, `flex`, `bison`)
2. `git clone --depth 1` Apache AGE, `make install`, remove source
3. Install `postgresql-16-pgvector` via apt
4. Purge build dependencies to keep image lean

### Runtime Configuration

```yaml
# docker-compose.yml — postgres service
shared_preload_libraries: 'age'    # AGE loaded at PostgreSQL startup
max_connections: 100
shared_buffers: 256MB
effective_cache_size: 768MB
maintenance_work_mem: 64MB
```

- **Volume:** Named volume `scailed_pgdata` → `/var/lib/postgresql/data` (persistent)
- **Network:** `backend` only — not exposed to frontend or public
- **Healthcheck:** `pg_isready -U pathfinder -d pathfinder`

---

## 2. Initialization Scripts

Executed automatically on first container start (`deploy/pg-init/`):

| Script | Purpose |
|---|---|
| `01_enable_extensions.sql` | `LOAD 'age'` → `CREATE EXTENSION age` + `CREATE EXTENSION vector` |
| `02_schema.sql` | Creates schemas, tables, triggers, indexes, and the AGE graph |

---

## 3. Schema Design: Dual Schema

```
assess.                          ref.
├── assessment_sessions          ├── roadmap_nodes
├── audit_log (append-only)      ├── recommendation_rules
│   ├── TRIGGER: no UPDATE       ├── schema_versions
│   └── TRIGGER: no DELETE       ├── rule_versions
                                 └── upstream_data_snapshots
```

### `ref` Schema — Reference Data (read-heavy)

#### `ref.roadmap_nodes`
SQL table storing node metadata:
```sql
node_id          TEXT UNIQUE    -- 'R2.3-A'
label            TEXT           -- 'Establish DPO'
description      TEXT
parent_node      TEXT           -- self-referential for DAG
prerequisites    TEXT[]         -- ['R1.2', 'R2.1']
maturity_level   INT CHECK (1-5)
effort_estimate  TEXT           -- 'low' | 'medium' | 'high'
related_wp       TEXT           -- 'WP5' | 'WP6' | 'WP7'
x, y             FLOAT          -- visualization coordinates
metadata         JSONB
```

#### `ref.recommendation_rules`
Rule tree with self-referential foreign key `parent_rule_id`:
```sql
rule_id           TEXT UNIQUE    -- 'R-PHARMA-AI-001'
parent_rule_id    INT → self      -- tree structure
rule_type         TEXT            -- eligibility | exclusion | preference | override
node_id           TEXT → roadmap_nodes
stakeholder_type  TEXT
condition         JSONB           -- {"answers":{"q2.1":{"gte":3}}}
action_title      TEXT
action_text       TEXT
compliance_ref    TEXT[]          -- ['GDPR-Art.37', 'EHDS-Art.50']
priority          INT DEFAULT 0
```

### `assess` Schema — Runtime Data

#### `assess.assessment_sessions`
Session state tracking with `UUID` primary key, JSONB answers, current node reference.

#### `assess.audit_log`
Append-only immutable log:
```sql
-- Triggers prevent mutation
CREATE TRIGGER audit_no_update BEFORE UPDATE ON assess.audit_log ...
CREATE TRIGGER audit_no_delete BEFORE DELETE ON assess.audit_log ...
```
Each row chains to previous via `prev_hash` (SHA-256), forming a verifiable audit chain.

---

## 4. AGE Graph Engine: Dual Representation

### 4a. SQL Relational Table

`ref.roadmap_nodes` stores node metadata with `prerequisites TEXT[]` encoding edge relationships as arrays.

### 4b. AGE Cypher Graph (`pathfinder_graph`)

Created at init:
```sql
SELECT ag_catalog.create_graph('pathfinder_graph');
```

#### Data Loading (Python → AGE Sync)

`AgeRoadmapGraph.load_demo_data()` in `pathfinder/core/graph_age.py` writes to BOTH the in-memory dict AND AGE simultaneously:

```cypher
-- Node loading
MERGE (n:RoadmapNode {
    node_id: 'R2.3-A',
    label: 'Establish DPO',
    description: '...',
    dimension: 'governance',
    maturity_level: 3,
    stakeholder_types: '["biotech-sme","all"]',
    source_wp: 'WP3',
    source_doc_ref: 'demo-data',
    confidence: 1.0
})

-- Edge loading
MATCH (a:RoadmapNode {node_id: 'R1.2'})
MATCH (b:RoadmapNode {node_id: 'R2.1'})
MERGE (a)-[:PREREQUISITE {edge_id: 'e3', required: true}]->(b)
```

Concurrency protection: `pg_advisory_lock(73109741)` during bulk load.

---

## 5. Query Paths: Three-Tier Routing

```
API Request
  │
  ▼
AssessmentService
  │
  ├── locate_current()      ──→ Python BFS (in-memory dict)
  ├── locate_target()       ──→ Python BFS (in-memory dict)
  ├── shortest_path()       ──→ Python BFS (in-memory adjacency list)
  │                              (AGE Cypher _SHORTEST_PATH defined but unused)
  │
  ├── cypher_query()        ──→ AGE Cypher (raw query, reserved for V2)
  │
  └── compliance/rules      ──→ SQL (ref.recommendation_rules)
```

### Why Python BFS Instead of AGE `shortestPath()`?

The `_SHORTEST_PATH` Cypher template exists in the code:
```cypher
MATCH p = shortestPath((a:RoadmapNode {node_id: 'X'})-[*]->(b:RoadmapNode {node_id: 'Y'}))
RETURN nodes(p)
```

But the actual `shortest_path()` method (line 278-313) uses Python BFS with an explicit comment:

> *"In production this could delegate to AGE's shortestPath(), but for V1 demo scale (< 10⁴ nodes) BFS is more than sufficient and avoids the openCypher shortestPath() gap in AGE."*

### Current Truth

| Layer | Uses AGE? | Why |
|---|---|---|
| **Data write** | Yes | MERGE nodes + edges via Cypher |
| **locate_current** | No | Python scoring over in-memory dict |
| **shortest_path** | No | Python BFS; AGE `shortestPath()` has known openCypher gaps |
| **cypher_query** | Yes (reserved) | Raw Cypher passthrough for V2 analytics |
| **Rule matching** | No | SQL over `ref.recommendation_rules` |

AGE currently functions as a **data mirror** rather than a **query engine** — the architecture is pragmatic, not dogmatic.

---

## 6. Connection Pooling

`AgeRoadmapGraph.connect()` uses `asyncpg`:

```python
pool = await asyncpg.create_pool(
    dsn=self._dsn,
    min_size=1, max_size=4,
    init=_init_connection,
    server_settings={"search_path": "ag_catalog, '$user', public"},
)
```

### Per-Connection Initialization

Each pool connection self-initializes:
1. `SELECT ag_catalog.create_graph('pathfinder_graph')` — idempotent, "already exists" ignored
2. `LOAD 'age'` — partial failures silently swallowed
3. `SET search_path = ag_catalog, '$user', public` — Cypher type resolution

This keeps AGE session state on the same connection where Cypher queries execute.

---

## 7. Data Flow: End-to-End

```
WP2 Mock ──→ stakeholder taxonomy (REST)
WP3 Mock ──→ roadmap graph data (REST)
WP8 Mock ──→ rules engine (REST)
     │
     ▼
AssessmentService
     │
     ├── load_demo_data(nodes, edges)
     │     ├── self.nodes = {...}        (in-memory dict)
     │     ├── self.edges = [...]        (in-memory list)
     │     └── MERGE into AGE graph      (Cypher, advisory-locked)
     │
     ├── Questionnaire → StakeholderState
     │     └── answers → maturity_scores + capabilities + regulatory_flags
     │
     ├── Rule matching: SQL (ref.recommendation_rules)
     │     └── condition JSONB → triggered rules
     │
     └── Path computation: Python BFS
           └── current → target via adjacency list
```

---

## 8. Demo Data

`pathfinder/adapters/demo_data.py` provides 6 nodes × 6 edges:

```
generic-intake ──→ governance-scope ──→ legal-basis ──→ secure-processing ──┐
                                                         ┌───────────────────┤
                                                         ↓                   ↓
                                              access-body-review ──→ readiness-report
```

5 stakeholder types: `biotech-sme`, `ai-factory-operator`, `health-data-access-body`, `health-data-infrastructure`, `research-infrastructure`

---

## 9. Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://pathfinder:***@postgres:5432/pathfinder` | Connection string |
| `POSTGRES_USER` | `pathfinder` | Database user |
| `POSTGRES_PASSWORD` | `changeme` | Database password |
| `POSTGRES_DB` | `pathfinder` | Database name |
| `USE_AGE` | (unset) | Set to `1`/`true`/`yes` to force AGE backend |

---

## 10. Architecture Assessment

| Aspect | Assessment |
|---|---|
| **AGE usage depth** | Conservative — writes go to AGE, queries stay in Python/SQL |
| **Rationale** | V1 demo < 100 nodes; Python BFS is fast enough; AGE `shortestPath()` has known openCypher gaps |
| **Dual-write risk** | `load_projection()` + AGE MERGE are synchronous with advisory lock |
| **V2 evolution path** | `cypher_query()` interface ready for complex graph analytics (community detection, centrality, etc.) |
| **Production readiness** | AGE compiled, loaded, graph created, data flowing — query layer intentionally deferred |

---

## 11. Key Files

| File | Role |
|---|---|
| `deploy/Dockerfile.postgres` | PG16 + AGE + pgvector image build |
| `deploy/docker-compose.yml` | Service orchestration, network isolation, healthchecks |
| `deploy/pg-init/01_enable_extensions.sql` | Extension bootstrap |
| `deploy/pg-init/02_schema.sql` | Schema, tables, triggers, AGE graph creation |
| `pathfinder/core/graph.py` | `InMemoryRoadmapGraph` — pure Python BFS (default) |
| `pathfinder/core/graph_age.py` | `AgeRoadmapGraph` — AGE backend with dual in-memory/AGE projection |
| `pathfinder/core/models.py` | `RoadmapNode`, `RoadmapEdge`, `StakeholderState`, `PathResult` |
| `pathfinder/adapters/demo_data.py` | Demo nodes, edges, rules for development |
| `pathfinder/services/assessment_service.py` | Orchestration layer |
| `tests/test_graph_age.py` | AGE backend tests |

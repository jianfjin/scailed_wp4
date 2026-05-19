# Plan: 1000-Record Mock Data + AGE Cypher Query

> **Created:** 2026-05-19  
> **Status:** pending execution  
> **Branch:** feature/mock-upstream-rest-services

---

## Goal

Populate the PostgreSQL/AGE graph with 1000 nodes and run a real Cypher query against it. Scale WP2 and WP8 mock services to match.

---

## Phase 1: Generate Mock Fixtures

### 1a. WP2 — 1000 Stakeholder Types

**Current:** 5 stakeholders in `wp2_data.json`  
**Target:** 1000 stakeholders

**Generation strategy:**
- 9 base categories (pharma-sme, biobank, clinical-cro, device-manufacturer, hospital-network, insurance-payer, academic-spinout, public-health-agency, digital-health-platform) × numerical suffix
- Each gets random capabilities (2-4 from pool of 8) and pain_points (1-3 from pool of 6)
- Output: `services/mock/fixtures/wp2_data.json` (overwrite)

### 1b. WP3 — 1000 Nodes + ~2000 Edges

**Current:** 6 nodes + 6 edges in `wp3_data.json`  
**Target:** 1000 nodes + ~1500-2000 edges

**Generation strategy — Layered DAG:**

```
Layer 1 (entry)     →  ~100 nodes  (maturity=1)
Layer 2             →  ~100 nodes  (maturity=2)
...
Layer 10 (exit)     →  ~100 nodes  (maturity=10)
```

- Each node in layer N connects to 1-3 random nodes in layer N+1
- Node IDs: `n{0000-0999}`
- Labels: generated from dimension + action templates
- Dimensions: random (governance/data/compliance) with weighted distribution
- Stakeholder types: randomly assigned (one of 5 types + "all" with 30% probability)
- Metadata: random target_scenarios
- Output: `services/mock/fixtures/wp3_data.json` (overwrite)

**Edge rules:**
- Every node in layer N has 1-3 outgoing edges to layer N+1
- Guarantee: no orphan nodes (every node except layer 1 has ≥1 incoming edge)
- Guarantee: every node except layer 10 has ≥1 outgoing edge
- Edge IDs: `e{0000-1999}`

### 1c. WP8 — 1000 Rules

**Current:** 3 rules in `wp8_data.json`  
**Target:** 1000 rules

**Generation strategy:**
- Rule IDs: `WP8-RULE-{0001-1000}`
- Rule types: random (eligibility/preference with 60/40 split)
- Priority: random 10-100
- Applies to: random stakeholder types or "all"
- Condition operators: contains, equals, gte, lte — referencing random answer fields
- Actions: reference random WP3 node IDs
- 20 paired test cases
- Output: `services/mock/fixtures/wp8_data.json` (overwrite)

---

## Phase 2: Restart Mock Services

```
docker compose -f deploy/docker-compose.yml up -d --build --force-recreate \
  wp2-mock wp3-mock wp8-mock
```

Mock containers pick up new fixture files on restart (loaded at `create_app()` time).

---

## Phase 3: Reload Backend

Two options:
- **A (restart):** `docker compose restart backend` — clean, picks up new upstream data via lifespan
- **B (hot reload):** `POST /admin/import/wp3` with admin-token — skips restart, but only updates memory projection (not AGE)

Choose A for full AGE graph reload.

---

## Phase 4: Verify Graph Load

```bash
# Check health — should show 1000 nodes loaded
curl -s http://localhost:80/health -H "Authorization: Bearer demo-token"

# Count nodes via API
curl -s http://localhost:80/v1/roadmap -H "Authorization: Bearer demo-token" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'nodes: {len(d[\"nodes\"])}, edges: {len(d[\"edges\"])}')"
```

---

## Phase 5: Run Cypher Queries in AGE

Connect directly to PostgreSQL and run Cypher via `ag_catalog.cypher()`:

### 5a. Count graph

```sql
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH (n:RoadmapNode) RETURN count(n)
$$) AS (cnt agtype);
```

### 5b. Shortest path between two nodes

```sql
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH p = shortestPath(
        (a:RoadmapNode {node_id: 'n0000'})-[*]->(b:RoadmapNode {node_id: 'n0999'})
    )
    RETURN length(p) AS path_length, nodes(p) AS path_nodes
$$) AS (path_length agtype, path_nodes agtype);
```

### 5c. Nodes by dimension

```sql
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH (n:RoadmapNode)
    RETURN n.dimension, count(*)
    ORDER BY count(*) DESC
$$) AS (dimension agtype, cnt agtype);
```

### 5d. Paths through a specific dimension

```sql
SELECT * FROM ag_catalog.cypher('pathfinder_graph', $$
    MATCH p = (start:RoadmapNode {node_id: 'n0000'})-[*]->(end:RoadmapNode {node_id: 'n0999'})
    WHERE ANY(n IN nodes(p) WHERE n.dimension = 'compliance')
    RETURN length(p) AS path_length
    ORDER BY path_length
    LIMIT 5
$$) AS (path_length agtype);
```

---

## Phase 6: Document Results

- Record query execution times
- Compare BFS (in-memory) vs AGE Cypher performance at 1000-node scale
- Update architecture docs with findings

---

## Files to Modify

| File | Action |
|---|---|
| `services/mock/fixtures/wp2_data.json` | Overwrite — 1000 stakeholders |
| `services/mock/fixtures/wp3_data.json` | Overwrite — 1000 nodes + ~2000 edges |
| `services/mock/fixtures/wp8_data.json` | Overwrite — 1000 rules |

---

## Risks

| Risk | Mitigation |
|---|---|
| 1000-node AGE load may be slow | Use advisory lock, batch inserts |
| Backend startup timeout waiting for AGE | Extend healthcheck start_period |
| Memory: 1000 nodes × RoadmapNode + edges | ~5 MB; negligible |
| Mock service fixture load on startup | JSON parse ~500 KB; <1 second |

---

## Rollback

Original 6-node fixtures preserved at:
```bash
git checkout HEAD -- services/mock/fixtures/
docker compose restart wp2-mock wp3-mock wp8-mock backend
```

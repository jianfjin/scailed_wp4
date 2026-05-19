# SCAILED WP4 — When Does AGE Beat SQL JOINs?

> **Document version:** 2026-05-19  
> **Branch:** feature/mock-upstream-rest-services  
> **Context:** Follow-up to the PostgreSQL + AGE graph architecture doc — answering the critical question of *why* have AGE at all if SQL can do the job.

---

## TL;DR

**At V1 scale (< 100 nodes), AGE has zero advantage.** Python BFS + SQL JOINs are faster, simpler, and have no network overhead. AGE is a strategic reserve — compiled, loaded, data flowing, but the query layer intentionally stays in Python/SQL until graph complexity demands Cypher.

---

## 1. What You're Doing Now vs. What AGE Would Do

| | Current (Python BFS + SQL) | If You Used AGE Cypher |
|---|---|---|
| **Shortest path** | `O(V+E)` BFS in memory, dict lookup `O(1)` | `MATCH p = shortestPath(...)` — Cypher parser → planner → executor, agtype serialization overhead |
| **Network** | Zero (in-process) | asyncpg connection pool round-trip |
| **Complexity** | 30 lines of readable Python | 3 lines of Cypher |
| **Winner** | Python BFS — no contest at this scale | AGE only wins on *expressiveness*, not performance |

SQL `WITH RECURSIVE` CTE can also do path finding — `ref.roadmap_nodes.prerequisites TEXT[]` already encodes the graph structure. Three-table JOINs produce assessment results without AGE.

**Honest assessment:** AGE is currently an expensive ornament. Compile cost, dual-write maintenance, advisory lock overhead — all paid, but the query layer doesn't use any of it.

---

## 2. When AGE Starts Making Sense

The threshold is not node count. It's **query complexity**.

### 2.1 Variable-Length Paths with Edge Constraints

> "Find a path from A to B, skip nodes with maturity_level < 3, and ensure at least one node in the 'compliance' dimension."

**SQL recursive CTE:**
```sql
WITH RECURSIVE path AS (
  SELECT node_id, ARRAY[node_id] as visited, 0 as depth
  FROM roadmap_nodes WHERE node_id = 'A'
  UNION ALL
  SELECT r.node_id, p.visited || r.node_id, p.depth + 1
  FROM path p
  JOIN roadmap_nodes r ON r.node_id = ANY(...)  -- getting ugly here
  WHERE NOT r.node_id = ANY(p.visited)
    AND r.maturity_level >= 3
    AND p.depth < 6
)
```

**AGE Cypher:**
```cypher
MATCH p = (a {node_id:'A'})-[*1..6]-(b {node_id:'B'})
WHERE ALL(n IN nodes(p) WHERE n.maturity_level >= 3)
  AND ANY(n IN nodes(p) WHERE n.dimension = 'compliance')
RETURN p
```

Recursive CTEs are *possible*, but **readability collapses fast** as constraints grow. Cypher stays declarative.

### 2.2 Graph Analytics

| Operation | SQL | Cypher/AGE |
|---|---|---|
| Betweenness centrality | Not feasible | Built-in or one-line extension |
| Community detection (Louvain) | Not feasible | Extensible in AGE |
| "All downstream nodes of X" | `WITH RECURSIVE` | `(n)-[*]->(m)` |
| Cycle detection (DAG validation) | Painful workaround | `EXISTS((n)-[*]->(n))` |

None of these are needed in V1. But in V2, if you need "how many stakeholders does this compliance path impact?" — SQL can't answer that.

### 2.3 Pattern Matching

> "Find all subgraphs matching: stakeholder -[:NEEDS]-> compliance_node -[:BLOCKED_BY]-> missing_capability"

Cypher is a native graph pattern matching language. SQL requires nested multi-level JOINs with subqueries.

---

## 3. The Real State of AGE in This Project

```
AGE status:  Compiled ✓  Loaded ✓  Graph created ✓  Data writing ✓  Querying ✗
```

| What's paid | What's received |
|---|---|
| Compile time in Docker build | Zero (query layer unused) |
| Dual-write maintenance (`load_projection` + AGE MERGE) | Zero |
| Advisory lock overhead during bulk load | Zero |
| `_SHORTEST_PATH` Cypher template (written, tested, unused) | Zero |

This is **technical debt with a purpose**, not an architectural defect.

---

## 4. The Defense

> "Better to have AGE running in the container now — schema aligned, data synced, tests passing — than to stop everything and install it when V2 suddenly needs graph analytics."

The `cypher_query()` passthrough interface already exists. The Cypher query templates are written. The switchover cost is **one line of code**.

When V2 demands:
- "Show me the impact radius of changing this regulation"
- "Which stakeholder paths are blocked by missing capability X?"
- "Community-detect the roadmap and find isolated requirements"

...AGE will be ready. Until then, it's a sleeping investment.

---

## 5. Summary

| Question | Answer |
|---|---|
| Is AGE faster than SQL for V1 queries? | No |
| Is AGE more expressive for complex graph queries? | Yes — when complexity crosses the CTE pain threshold |
| Should we remove AGE? | No — marginal cost now, high switching cost later |
| When does AGE start earning its keep? | V2: multi-hop constrained paths, centrality, community detection, pattern matching |

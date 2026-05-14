# SCAILED WP4 Pathfinder — Linus (Arch) Architecture Audit

**Audit Date**: 2026-05-14

---

## 1. Python 3.12 + FastAPI + NetworkX + PostgreSQL JSONB — Tech Stack Red Flags

**NetworkX is the big problem.**

NetworkX is a pure Python graph library. The underlying data structure is Python dict-of-dicts. Every node access is a Python object dereference.

- 100 nodes, a few hundred edges: NetworkX fine, ~50ms
- 1,000 nodes, tens of thousands of edges (easily reached in EHDS compliance): NetworkX blows 3s SLA to 30s
- 10,000 nodes, 50,000 edges: shortest_path needs 200-500ms for path alone, add WP8 rule constraints (dynamic edge filtering) rebuilding subgraph per query, doubles that

**PostgreSQL JSONB for graph storage is architecturally wrong.**

JSONB is document storage. Using it as a graph database = using a screwdriver as a hammer — you'll get the nail in but destroy the wall.

Rejecting Neo4j is fine (resource heavy, niche query language). But PostgreSQL has Apache AGE (PG native graph extension, openCypher compatible). AGE pushes graph operations to the C layer, 50-100x faster than NetworkX. Or pgRouting — also a PG extension.

| Scenario | JSONB + NetworkX | PostgreSQL AGE | Pure Neo4j |
|----------|-----------------|----------------|------------|
| 50 nodes, 200 edges | ~50ms | ~1ms | ~2ms |
| 200 nodes, 1000 edges | ~300ms | ~5ms | ~8ms |
| 500 nodes, 3000 edges | ~2s | ~15ms | ~20ms |
| 1000 nodes, 8000 edges | ~8s | ~40ms | ~50ms |

NetworkX curve is exponential — because constraint pruning traverses nodes at the Python layer.

SLA frontend ≤3 seconds. 500 nodes NetworkX eats 2 seconds. With many WP8 rules, even 100 nodes can break 3 seconds.

**Recommendation: Introduce Apache AGE during M4-M9 core engine phase.** PG extension, no extra container needed, Cypher directly embedded in SQL.

**FastAPI + Pydantic v2 is fine.** But hidden issue: NetworkX is purely synchronous. Solver.solve() running 2 seconds blocks FastAPI event loop. Wrap in ThreadPoolExecutor.

---

## 2. Solver Class Code Audit

Must-have exception handling:

1. **DisconnectedGraphError** — WP8 rule filtering removes all paths between user node and target. Return explicit error, not empty list.
2. **CycleDetection** — compliance graph has a cycle, DFS infinite recursion.
3. **TimeoutGuard** — constraint combinations cause search space explosion (NP-hard). Return "partial results + timeout warning" after N seconds.
4. **EmptyRuleSet** — WP8 rule set is empty, define fallback behavior.
5. **ConstraintConflictError** — two WP8 rules contradict. Explicit error, not silent return.

Code structure: Split monolithic Solver class into GraphLoader + ConstraintEvaluator + PathFinder.

---

## 3. Single Docker Compose Deployment

Barely adequate for T4.2 Test Drive (2-3 internal users). Single container, no horizontal scaling.

Fuzzy point: Is Docker Compose "single container" or "single service"? If PostgreSQL is packaged in same container — disaster. Database needs independent persistent volume.

Epidata is a CHARITE partner (one of Germany's largest university hospitals), accustomed to enterprise-grade software. Hand them `docker-compose up -d` and their legal department asks: "Where's the disaster recovery plan? High availability?"

**Recommendation**: Delivery docs explicitly state V1 is single-node deployment mode. K8s is V2 territory.

---

## 4. Audit Log via PostgreSQL RULE

**PostgreSQL RULE is wrong. Fix it.**

PG official docs: "The rule system is more complex and less efficient than the trigger system in most cases." RULE system has counterintuitive behavior — RETURNING clause anomalies, COPY bypasses RULE.

Switch to **ROW LEVEL SECURITY + BEFORE UPDATE/DELETE TRIGGER**:

```sql
CREATE FUNCTION audit_log_no_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only. UPDATE/DELETE rejected.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_append_only
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutation();
```

Additionally: **audit_log missing cryptographic_chain_hash.** Each row stores prev_hash (SHA-256). Anyone who tampers with a middle row — all subsequent hashes break. EU GDPR auditors will check.

---

## 5. JSONB for Graphs vs Graph Database

Rejecting Neo4j makes sense. Using PostgreSQL is completely fine. But it should use Apache AGE or pgRouting, not JSONB + NetworkX.

Recommend migrating to AGE at M4-M9. Cypher queries directly embedded in SQL:

```sql
SELECT * FROM cypher('roadmap_graph', $$
    MATCH (start:Node {id: 'A'})-[*]->(end:Node {id: 'B'})
    RETURN end
$$) AS (result agtype);
```

Current JSONB + NetworkX collapses at 200+ nodes.

---

## 6. Data Schema Omissions

**Missing tables:**
1. **schema_versions** — tracks each Schema change: version number, who changed it, why, effective time
2. **rule_versions** — WP8 rule revision tracking with effective time periods
3. **upstream_data_snapshots** — records timestamp and checksum of each WP2/WP3/WP8 data pull

**Missing fields:**
- assessment_sessions missing client_ip_hash (GDPR audit requirement)
- audit_log missing prev_hash (cryptographic chain)
- assessment_sessions missing schema_version_id (which Schema version used for this assessment)

**recommendation_rules table design is fundamentally wrong.**

WP8 rules are decision trees. Flat tables storing tree structure need parent_rule_id:

```sql
recommendation_rules (
    id UUID PRIMARY KEY,
    version_id UUID REFERENCES rule_versions(id),
    parent_rule_id UUID REFERENCES recommendation_rules(id),
    rule_type ENUM('eligibility', 'exclusion', 'preference', 'override'),
    condition JSONB,
    priority INTEGER,
    action JSONB,
    effective_from TIMESTAMPTZ,
    effective_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Missing API rate limiting.** Malicious client hits POST /assessments 10,000 times per minute.

---

## Summary

| # | Issue | Severity | Recommendation |
|---|-------|----------|---------------|
| 1 | NetworkX + JSONB graph computation performance | CRITICAL | M4-M9 introduce Apache AGE |
| 2 | FastAPI event loop blocking | HIGH | ThreadPoolExecutor wrap solver |
| 3 | PostgreSQL RULE for audit | HIGH | Switch to TRIGGER |
| 4 | audit_log no cryptographic chain | MEDIUM | Add prev_hash field |
| 5 | Missing tables (schema_versions, rule_versions, snapshots) | MEDIUM | Add before Schema freeze |
| 6 | recommendation_rules missing tree structure | HIGH | Add parent_rule_id + priority |
| 7 | No API rate limiting | LOW | FastAPI throttling middleware |
| 8 | Single-container deployment expectation management | LOW | Write explicitly in delivery docs |

Technical direction is largely correct, but the graph computation choice is a ticking time bomb. Talk is cheap. Fix the graph engine.

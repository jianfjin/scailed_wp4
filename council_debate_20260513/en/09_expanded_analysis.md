# SCAILED WP4 Pathfinder System — Expanded Analysis

## Part 1: Contract Clause Recommendations

### I. Payment Structure

Based on Zhang Xuefeng's audit, a four-tier payment is recommended:

| Milestone | Percentage | Trigger Condition | Tied to Upstream |
|-----------|------------|-------------------|------------------|
| Advance | 30% | Within 15 days of contract signing | None |
| Phase 1 Complete | 15% | M9: Core engine + mock data full-chain pass | Epidata receives CHARITE M9 payment |
| Phase 1 Complete (Deferred) | 15% | M15: Mid-term stable version acceptance | Epidata receives CHARITE M15 payment |
| D4.1 Delivery | 40% | M20: D4.1 acceptance | Epidata receives CHARITE M20 payment |

**Key Protection Clauses:**

- **Upstream Tie-In**: The second through fourth payments are tied to Epidata receiving corresponding milestone payments from CHARITE, not tied to DataWego's own delivery. This prevents DataWego from being dragged down if Epidata experiences cash flow disruption.
- **Deferred Advance Payment Clause**: If CHARITE delays payment by more than 30 days, Epidata must advance that installment to DataWego and then recover from CHARITE independently. This clause prevents a single-point blockage in the upstream payment chain from disrupting DataWego's cash flow.

### II. Scope Boundaries (Must Be Written into Contract)

**Included (DataWego Deliverables):**
- Pathfinder System V1 software (T4.1 scope)
- Source code + Docker Compose deployment package
- API documentation (OpenAPI spec auto-generated)
- User operation manual (README level)
- D4.1 Demo screen recording support
- D4.2 Stakeholder Event technical support

**Explicitly Excluded (Separate Contract):**
- Pathfinder V2 development (T4.3, CHARITE-led)
- D4.3/D4.4 report writing (CHARITE responsibility)
- WP5/6/7 integration development (each WP's own responsibility)
- Production environment operations
- Multi-language support
- User training

### III. Acceptance Criteria (Quantified)

| Item | Criterion |
|------|-----------|
| Supported stakeholder types | ≥5 types (based on WP2 classification) |
| Recommended path generation | ≥3 executable paths per type |
| Compliance check accuracy | 100% match on WP8 known rules |
| Frontend response time | ≤3 seconds (standard questionnaire submission) |
| Code coverage | Shell modules ≥80%, kernel modules ≥98% (pytest) |
| Deployment documentation | CHARITE personnel can complete deployment within one hour |

### IV. Rework Clauses

Rework arising from the following causes is billed at the three-tier rates below, outside the fixed price:

| Tier | Daily Rate | Applicable Scenarios |
|------|------------|----------------------|
| Architect | €800–1,200/day | System architecture changes, cross-module refactoring |
| Senior | €600–800/day | Core module development, algorithm adjustments |
| Junior | €400–600/day | Documentation updates, test supplementation, simple adaptation |

**Rework Process:**
1. Epidata submits a written rework request to DataWego (describing scope of change + rationale)
2. DataWego provides effort estimate and tier assignment within 5 working days
3. Both parties confirm in writing before work begins
4. Any work exceeding the estimate by more than 20% requires re-confirmation

**Rework Trigger Conditions (outside fixed price scope):**
1. WP2/WP3/WP8 upstream data format changes
2. Epidata requirements changes (beyond signed prototype scope)
3. EHDS implementing regulations issued mid-project causing logic changes

**Rework Caps:**
- Single rework ≤ 15% of total contract value
- Annual cumulative rework ≤ 30% of total contract value
- Amounts exceeding the cap require renegotiation or a separate contract

### V. Intellectual Property

Adopt the Background/Foreground IP split model:

**Background IP (Retained by Each Party):**
- DataWego retains pre-existing generic components, utility libraries, and framework code developed before project entry
- Epidata retains its business methodology and consulting frameworks
- Per-file ownership inventory detailed in [IP_BOUNDARY.md](IP_BOUNDARY.md)

**Foreground IP (Project Output):**
- Pathfinder System V1 core engine code: DataWego retains copyright
- Epidata obtains a perpetual, irrevocable, royalty-free usage license within the SCAILED project scope
- Jointly developed parts (e.g., WP3 integration adaptation layer, upstream data connectors): jointly owned by both parties; either party may use in non-competitive contexts
- Pathfinder System commercialization outside the SCAILED project requires a separate agreement; DataWego holds first-right-of-negotiation

---

## Part 2: Technical Implementation Details

### I. Data Schema Design

#### Questionnaire Definitions (questionnaires)

```sql
CREATE TABLE questionnaires (
    id              SERIAL PRIMARY KEY,
    version         TEXT NOT NULL,           -- 'v1.0-m3-freeze'
    stakeholder_type TEXT,                   -- from WP2
    definition      JSONB NOT NULL,          -- question tree structure
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

`definition` JSONB structure:
```json
{
  "title": "EHDS Readiness Self-Assessment",
  "sections": [
    {
      "id": "s1",
      "title": "Organizational Profile",
      "questions": [
        {
          "id": "q1.1",
          "text": "What is your primary role in the biotech value chain?",
          "type": "single_choice",
          "options": [
            {"id": "drug_discovery", "label": "Drug Discovery"},
            {"id": "clinical_trials", "label": "Clinical Trials"},
            {"id": "diagnostics", "label": "Diagnostics/IVD"},
            {"id": "digital_health", "label": "Digital Health/AI"}
          ],
          "maps_to_dimension": "stakeholder_category",
          "weight": 1.0
        }
      ]
    }
  ]
}
```

#### Roadmap Nodes (roadmap_nodes)

```sql
CREATE TABLE roadmap_nodes (
    id              SERIAL PRIMARY KEY,
    node_id         TEXT UNIQUE NOT NULL,    -- 'R2.3-A'
    label           TEXT NOT NULL,           -- 'Establish DPO'
    description     TEXT,
    parent_node     TEXT,                    -- self-ref for DAG
    prerequisites   TEXT[],                  -- ['R1.2', 'R2.1']
    dimension       TEXT,                    -- 'governance'|'technical'|'legal'
    maturity_level  INT CHECK (maturity_level BETWEEN 1 AND 5),
    effort_estimate TEXT,                    -- 'low'|'medium'|'high'
    related_wp      TEXT,                    -- 'WP5'|'WP6'|'WP7'
    x               FLOAT,
    y               FLOAT,                  -- visualization
    metadata        JSONB,
    schema_version  TEXT NOT NULL,           -- 'v1.0-m3-freeze'
    schema_version_id INT REFERENCES schema_versions(id)
);
```

#### Recommendation Rules (recommendation_rules)

```sql
CREATE TYPE rule_type AS ENUM (
    'eligibility',    -- Eligibility: whether this stakeholder qualifies for this recommendation
    'exclusion',      -- Exclusion: exclude this recommendation under specific conditions
    'preference',     -- Preference ordering: priority preference among similar recommendations
    'override'        -- Override: override default recommendation logic under special circumstances
);

CREATE TABLE recommendation_rules (
    id                SERIAL PRIMARY KEY,
    rule_id           TEXT UNIQUE NOT NULL,   -- 'R-PHARMA-AI-001'
    parent_rule_id    TEXT,                   -- Parent rule reference (rule composition/inheritance)
    rule_type         rule_type NOT NULL DEFAULT 'eligibility',
    node_id           TEXT REFERENCES roadmap_nodes(node_id),

    -- Condition: JSONB supporting complex queries
    -- {"answers": {"q2.1": {"gte": 3}, "q3.2": ["A","B"]}}
    condition         JSONB NOT NULL,

    -- Recommended action
    action_title      TEXT NOT NULL,
    action_text       TEXT NOT NULL,          -- "Establish a Data Protection Officer role"

    -- Compliance references (array for batch updates)
    compliance_ref    TEXT[],                 -- ['GDPR-Art.37', 'EHDS-Art.50']

    -- Priority
    priority          INT DEFAULT 0,

    -- Source traceability
    source_wp         TEXT,                   -- 'WP3'|'WP8'
    source_doc_ref    TEXT,                   -- Upstream document reference

    -- Versioning
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now(),
    rule_version      TEXT NOT NULL
);

CREATE INDEX idx_rules_stakeholder ON recommendation_rules(stakeholder_type);
CREATE INDEX idx_rules_node ON recommendation_rules(node_id);
CREATE INDEX idx_rules_condition ON recommendation_rules USING GIN (condition);
CREATE INDEX idx_rules_parent ON recommendation_rules(parent_rule_id);
CREATE INDEX idx_rules_type ON recommendation_rules(rule_type);
CREATE INDEX idx_rules_priority ON recommendation_rules(priority DESC);
```

#### Assessment Sessions + Audit Log

```sql
CREATE TABLE assessment_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stakeholder_type TEXT,
    status          TEXT DEFAULT 'in_progress', -- 'in_progress'|'completed'|'abandoned'
    answers         JSONB,                     -- Full answer snapshot
    current_node    TEXT REFERENCES roadmap_nodes(node_id),
    recommendations JSONB,                     -- Generated recommendations snapshot
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

-- Audit log (immutable, cryptographic chain integrity)
CREATE TABLE audit_log (
    id              SERIAL PRIMARY KEY,
    session_id      UUID REFERENCES assessment_sessions(id),
    event_type      TEXT NOT NULL,            -- 'answer_submitted'|'recommendation_generated'|'report_exported'
    event_data      JSONB NOT NULL,
    timestamp       TIMESTAMPTZ DEFAULT now(),
    ip_hash         TEXT,                     -- Anonymized one-way hash
    client_ip_hash  TEXT,                     -- Client IP hash
    user_agent_hash TEXT,
    prev_hash       TEXT                      -- SHA-256 of previous record, forming cryptographic chain
);

-- Audit log is append-only, no updates or deletes (using TRIGGER instead of RULE for better performance and compatibility)
CREATE OR REPLACE FUNCTION audit_log_prevent_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: UPDATE and DELETE are forbidden';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_prevent_mutation();

CREATE TRIGGER audit_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_prevent_mutation();
```

#### New Tables: Version Management & Upstream Snapshots

```sql
-- Schema version tracking
CREATE TABLE schema_versions (
    id              SERIAL PRIMARY KEY,
    version         TEXT UNIQUE NOT NULL,     -- 'v1.0-m3-freeze'
    applied_at      TIMESTAMPTZ DEFAULT now(),
    description     TEXT,
    migration_file  TEXT,                     -- 'migrations/003_add_prev_hash.sql'
    checksum        TEXT                      -- SQL file SHA-256
);

-- Rule version tracking (independent of schema version; rules may remain unchanged across schema versions)
CREATE TABLE rule_versions (
    id              SERIAL PRIMARY KEY,
    rule_id         TEXT NOT NULL,
    rule_version    TEXT NOT NULL,
    change_type     TEXT,                     -- 'create'|'update'|'deprecate'
    change_summary  TEXT,
    schema_version_id INT REFERENCES schema_versions(id),
    applied_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(rule_id, rule_version)
);

-- Upstream data snapshots (traceable: "what did upstream data look like at M3 freeze")
CREATE TABLE upstream_data_snapshots (
    id              SERIAL PRIMARY KEY,
    source_wp       TEXT NOT NULL,            -- 'WP2'|'WP3'|'WP8'
    source_doc_ref  TEXT,
    snapshot_data   JSONB NOT NULL,           -- Complete upstream data snapshot
    schema_version_id INT REFERENCES schema_versions(id),
    frozen_at       TIMESTAMPTZ DEFAULT now(),
    reason          TEXT                      -- 'M3 freeze'|'WP8 update v2.1'
);
```

### II. Python Core Engine Structure

```
pathfinder/
├── core/
│   ├── __init__.py
│   ├── models.py          # Pydantic models
│   ├── graph.py           # DAG operations (Apache AGE primary, NetworkX fallback)
│   ├── solver.py          # Constrained graph search
│   ├── compliance.py      # Constraint checker
│   └── recommend.py       # Recommendation engine
├── api/
│   ├── __init__.py
│   ├── main.py            # FastAPI app
│   ├── routes/
│   │   ├── assessments.py # /v1/assessments/*
│   │   ├── roadmap.py     # /v1/roadmap/*
│   │   ├── compliance.py  # /v1/compliance/*
│   │   └── admin.py       # /admin/rules/reload
│   ├── middleware/
│   │   ├── rate_limit.py  # Token bucket rate limiter
│   │   └── audit.py       # Automatic audit log recording
│   └── dependencies.py    # DI
├── adapters/
│   ├── wp2_stakeholders.py
│   ├── wp3_roadmap.py
│   └── wp8_compliance.py
├── services/
│   ├── graph_service.py       # ThreadPoolExecutor-wrapped graph operations
│   └── extraction_service.py  # WP3 Plan B: data extraction layer
├── config/
│   ├── settings.py
│   └── rate_limit.yaml
├── rules/
│   ├── pharma_rules.yaml
│   ├── sme_rules.yaml
│   └── academia_rules.yaml
├── migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_add_recommendation_rules.sql
│   └── 003_add_prev_hash.sql
├── exceptions/
│   ├── __init__.py
│   └── handlers.py
├── scripts/
│   ├── seed_data.py
│   └── validate_rules.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sample_graph.json
│   │   ├── sample_questionnaire.json
│   │   └── sample_rules.yaml
│   ├── test_graph.py
│   ├── test_solver.py
│   ├── test_compliance.py
│   ├── test_recommend.py
│   ├── test_rules.py          # .test.yaml rule test framework
│   └── benchmark/
│       └── test_graph_perf.py # pytest-benchmark
├── frontend/                   # Moved out of Python package, standalone frontend project
│   ├── src/
│   ├── public/
│   └── package.json
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

### III. Core Algorithm (Simplified Implementation)

```python
# pathfinder/core/solver.py
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from .models import StakeholderState, RoadmapNode, Recommendation, PathResult
from .graph import GraphEngine  # Abstracts Apache AGE / NetworkX

# ThreadPoolExecutor for graph operations (CPU-bound DAG traversal)
_graph_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="graph-")

class PathfinderSolver:
    """Core pathfinding on regulatory DAG.

    Graph Engine Strategy:
      - Primary: Apache AGE (PostgreSQL native graph extension)
        Rationale: NetworkX (pure Python) crashes with >200 nodes due to
        in-memory DAG operations exhausting Python heap on large regulatory
        graphs. Apache AGE runs graph algorithms inside PostgreSQL, leveraging
        its memory management and persistence. Benchmarks show 10-50x
        improvement on graphs with 200+ nodes.
      - Fallback: NetworkX for local dev/testing (no PostgreSQL dependency).
        Auto-selected when AGE connection is unavailable.
    """

    def __init__(self, graph_engine: GraphEngine):
        # Validate DAG at startup
        if not graph_engine.is_directed_acyclic():
            raise ValueError("EWD498: Roadmap graph must be a DAG")
        self.graph = graph_engine

    def locate(self, state: StakeholderState) -> RoadmapNode:
        """Find current position on roadmap."""
        best_node = None
        best_score = float('inf')

        nodes = self.graph.get_all_nodes()
        for node in nodes:
            if not self._is_compliant(state, node):
                continue
            score = self._distance(state, node)
            if score < best_score:
                best_score = score
                best_node = node

        if best_node is None:
            raise NoFeasiblePositionError("No compliant position found")
        return best_node

    def plan_path(self, current: RoadmapNode, target: RoadmapNode,
                  state: StakeholderState) -> PathResult:
        """Constrained graph search under compliance constraints.
        Graph operations run via ThreadPoolExecutor to avoid blocking the
        async event loop.
        """
        # Run CPU-bound graph traversal in thread pool
        future = _graph_executor.submit(
            self._plan_path_sync, current, target, state
        )
        return future.result()

    def _plan_path_sync(self, current: RoadmapNode, target: RoadmapNode,
                        state: StakeholderState) -> PathResult:
        """Synchronous path computation (runs in ThreadPoolExecutor)."""
        valid_nodes = {n.id for n in self.graph.get_all_nodes()
                       if self._is_compliant(state, n)}

        path = self.graph.shortest_path(
            current.node_id, target.node_id,
            valid_nodes=valid_nodes, weight='cost'
        )
        cost = self.graph.shortest_path_length(
            current.node_id, target.node_id,
            valid_nodes=valid_nodes, weight='cost'
        )

        recommendations = self._path_to_recommendations(path, state)
        return PathResult(path=path, cost=cost,
                          recommendations=recommendations)

    def _is_compliant(self, state: StakeholderState, node: dict) -> bool:
        """Check all WP8 constraints for (state, node) pair."""
        for constraint in node.get('compliance_constraints', []):
            if not constraint.evaluate(state):
                return False
        return True
```

### IV. API Endpoint Design

```
# Core Assessment Endpoints
POST   /v1/assessments                              # Create assessment session
GET    /v1/assessments/{session_id}                  # Get session status
POST   /v1/assessments/{session_id}/answers          # Submit answers
GET    /v1/assessments/{session_id}/recommendations  # Get recommendations
GET    /v1/assessments/{session_id}/report           # Export report

# Roadmap Endpoints
GET    /v1/roadmap                                   # Get full roadmap
GET    /v1/roadmap/nodes/{node_id}                   # Get node details

# Compliance Endpoints
GET    /v1/compliance/check                          # Compliance check
GET    /v1/compliance/rules                          # List all rules

# Questionnaire Template Endpoints (New)
GET    /v1/questionnaires/{type}                     # Get questionnaire template by stakeholder type

# Health Check & Admin Endpoints (New)
GET    /health                                        # Health check (liveness/readiness)
POST   /admin/rules/reload                            # Hot-reload rule files (no restart needed)

# Rate Limiting Policy
# - /v1/assessments/* : 60 req/min per IP (token bucket)
# - /v1/roadmap/*     : 120 req/min per IP
# - /health            : unlimited
# - /admin/*           : 10 req/min per IP + Bearer token auth
```

---

## Part 3: Authentication and Data Security

### Does DataWego Need to Do This?

**Zhang Xuefeng / Jensen's judgment: A full authentication system is NOT needed.**

Rationale:
1. Pathfinder V1 is a Demo (D4.1 type = report + demonstration), not a production system
2. Users are invited stakeholders (internal to Stakeholder Forum)
3. During T4.2 Test Drive phase, CHARITE is responsible for deployment; security is their concern
4. Adding authentication → requires user management, password resets, OAuth integration → scope explosion

### What DataWego Should Do for Security

**1. Minimal Authentication (Add in Phase 2)**
- Simple token-based access control
- Generate a batch of single-use access links, distribute to Stakeholder Event participants
- No registration/login/password required

```python
# Simple implementation
SECRET_TOKENS = set(os.environ.get("ACCESS_TOKENS", "").split(","))

@app.middleware("http")
async def simple_token_auth(request, call_next):
    if request.url.path.startswith("/v1/assessments"):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token not in SECRET_TOKENS:
            return JSONResponse(status_code=403, content={"error": "unauthorized"})
    return await call_next(request)
```

**2. Data Minimization**
- Do not store personally identifiable information (PII)
- Assessment sessions use UUIDs, not associated with email/name
- `audit_log` stores `ip_hash`, `client_ip_hash`, and `user_agent_hash` (one-way hashes)

**3. Transport Security**
- HTTPS (Nginx reverse proxy + Let's Encrypt)
- API responses exclude sensitive internal error information

**4. Data Retention**
- Assessment data retained until project end (M36)
- Data after D4.1 delivery is CHARITE's responsibility

### Security That DataWego Does NOT Need to Handle

- ❌ GDPR compliance declarations — WP8 is responsible
- ❌ Data Protection Impact Assessment (DPIA) — CHARITE/Epidata is responsible
- ❌ EHDS data access rights — SCAILED data governance framework is responsible
- ❌ SPE environment security — AI Factory/WP7 is responsible
- ❌ User authentication SDK — Out of scope

### Guido's Audit Trail (Must Do)

Every answer modification and every recommendation generation for each assessment session → immutable log:
```sql
-- Audit log table characteristics:
-- 1. Append-only (BEFORE UPDATE/DELETE TRIGGER prevents modification, more reliable than RULE)
-- 2. Each event carries a timestamp
-- 3. Contains answer snapshot (JSONB)
-- 4. Contains recommendation snapshot (traceable: "Why this recommendation?")
-- 5. IP/UA hashed (anonymous but verifiable)
-- 6. prev_hash field forms cryptographic chain: each record's hash contains the previous record's hash
--    → Tampering with any intermediate record causes all subsequent record hashes to mismatch
--    → Satisfies EHDS audit trail non-repudiation requirements
```

---

## Part 4: Upstream Interface Checklist

### M1–M3 Must Complete

| Interface Party | What Is Needed | Format | Signatory |
|-----------------|----------------|--------|-----------|
| WP3 (CHARITE) | Strategic roadmap node-edge list | JSON + topological sort proof | WP3 Lead |
| WP8 (Lead TBD) | Regulatory constraint executable rules | YAML rule files | WP8 Lead |
| WP2 (IISLAFE) | Stakeholder classification matrix | JSON Schema | WP2 Lead |
| SHAIPED | Existing code/data audit | Code audit report | Lu Zhao |

### M4–M18 Ongoing Interface

| Interface Party | What Is Needed | What Is Provided |
|-----------------|----------------|------------------|
| WP5 (ELIXIR) | Data infrastructure specifications | Pathfinder API endpoint (for validation) |
| WP6 (Lead TBD) | Use case definitions + evaluation criteria | Pathfinder instance + test datasets |
| WP7 (AI Factories) | SPE environment parameters | Docker image + deployment documentation |

---

## Part 5: Testing Strategy (Supplement)

### Coverage Requirements by Module

| Module | Minimum Coverage | Tool | Notes |
|--------|-----------------|------|-------|
| Shell (API, adapters, routes) | ≥80% | pytest + pytest-cov | Primarily integration tests |
| Kernel (core: graph, solver, compliance, recommend) | ≥98% | pytest + pytest-cov + pytest-benchmark | Full unit test coverage; critical algorithm performance benchmarks |

### Rule Test Framework (.test.yaml)

Each rule file is accompanied by a `.test.yaml` file defining test cases for that rule:

```yaml
# rules/pharma_rules.test.yaml
rule_file: pharma_rules.yaml
scenarios:
  - name: "pharma_ai_company_must_establish_dpo"
    stakeholder_type: "drug_discovery"
    answers:
      q1.1: "drug_discovery"
      q2.1: 4
      q3.2: ["A"]
    expected_recommendations:
      - rule_id: "R-PHARMA-AI-001"
        action: "present"
    expected_exclusions:
      - rule_id: "R-SME-EXEMPT-003"
        action: "absent"

  - name: "small_pharma_below_threshold_no_dpo_required"
    stakeholder_type: "drug_discovery"
    answers:
      q1.1: "drug_discovery"
      q2.1: 1
      q4.1: "<10_employees"
    expected_recommendations:
      - rule_id: "R-PHARMA-AI-001"
        action: "absent"
      - rule_id: "R-SME-EXEMPT-003"
        action: "present"
```

**Execution:**
```bash
pytest tests/test_rules.py --rule-dir=pathfinder/rules/
# Auto-discovers all .test.yaml files, validates one by one
```

---

## Part 6: Performance Benchmarks

### pytest-benchmark Key Metrics

```python
# tests/benchmark/test_graph_perf.py
def test_shortest_path_200_nodes(benchmark, large_graph):
    """200-node DAG — Apache AGE must complete <100ms, NetworkX <5s."""
    solver = PathfinderSolver(large_graph)
    result = benchmark(solver.plan_path, node_start, node_end, test_state)
    assert result.cost < float('inf')

def test_compliance_check_50_rules(benchmark, state_with_50_rules):
    """50 WP8 constraints — must complete <10ms."""
    result = benchmark(solver._is_compliant, test_state, test_node)
    assert result is True
```

---

## Part 7: WP3 Contingency Plan (Plan B)

### Data Extraction Layer

When WP3 (CHARITE) cannot deliver structured roadmap data on time, Pathfinder obtains required data from unstructured documents through an independent data extraction layer:

```
┌─────────────────────────────────────────────────┐
│                  WP3 Plan B                      │
├─────────────────────────────────────────────────┤
│  Data Source Layer                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ JSON API │ │ CSV/TSV  │ │ Unstructured     │ │
│  │ (happy)  │ │ Export   │ │ (PDF, DOCX, MD)  │ │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘ │
│       │            │               │            │
│       ▼            ▼               ▼            │
│  ┌─────────────────────────────────────────────┐ │
│  │         Extraction Service                   │ │
│  │  • Structured: direct mapping                │ │
│  │  • Semi-structured: regex + tabular parser   │ │
│  │  • Unstructured: LLM-assisted extraction     │ │
│  │    (nodes, edges, prerequisites, metadata)   │ │
│  └────────────────────┬────────────────────────┘ │
│                       │                          │
│                       ▼                          │
│  ┌─────────────────────────────────────────────┐ │
│  │         Validation & Normalization           │ │
│  │  • DAG cycle check                           │ │
│  │  • Schema compliance                         │ │
│  │  • Missing prerequisite detection            │ │
│  └────────────────────┬────────────────────────┘ │
│                       │                          │
│                       ▼                          │
│              pathfinder.core.graph               │
└─────────────────────────────────────────────────┘
```

### Graceful Degradation Strategy

When upstream data is incomplete, Pathfinder should not fail completely but degrade according to the following priority:

| Missing Data | Degradation Behavior | User-Visible Impact |
|-------------|---------------------|---------------------|
| WP3 dimension labels missing | Nodes still routable, but category filtering unavailable | "Filter by dimension" button grayed out |
| WP3 maturity levels missing | Default assumption maturity_level=1 | Path may be suboptimal but executable |
| WP3 prerequisites missing | Marked as optional, allowed to skip | Console warning "unverified prerequisites" |
| WP2 stakeholder types incomplete | Use generic questionnaire template | Industry-specific custom questions unavailable |
| WP8 rule files missing | Compliance check degraded to pass-through | All nodes marked as "compliance unverified" |
| All upstream missing | Degrade to demo mode (mock data) | Banner: "DEMO MODE — not for production" |

**Degradation Logging:** All degradation events are written to `audit_log` (event_type='graceful_degradation'), ensuring traceability of which decisions were made under incomplete data.

---

## Appendix A: IP_BOUNDARY.md Reference

The per-file ownership inventory is defined in [IP_BOUNDARY.md](IP_BOUNDARY.md). Key division principles:

| Code Layer | Ownership | License |
|------------|-----------|---------|
| `pathfinder/core/graph.py` | DataWego Background IP | Royalty-free use within project |
| `pathfinder/core/solver.py` | DataWego Foreground IP | Epidata perpetual usage license |
| `pathfinder/adapters/wp3_roadmap.py` | Joint ownership | Free use in non-competitive contexts |
| `pathfinder/adapters/wp8_compliance.py` | Joint ownership | Free use in non-competitive contexts |
| `migrations/*.sql` | DataWego Foreground IP | Epidata perpetual usage license |
| `frontend/` | DataWego Foreground IP | Epidata perpetual usage license |
| `tests/` | DataWego Foreground IP | Epidata perpetual usage license |
| `rules/*.yaml` | WP8 provided, DataWego engineered | Shared within SCAILED consortium |

*End of expanded analysis. Merged with Nine-Dragon Council Resolution to form complete project proposal.*
*Path: ~/projects/scailed_wp4/council_debate_20260513/*

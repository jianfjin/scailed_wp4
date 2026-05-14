# SCAILED WP4 Pathfinder — Guido (CLA) Design Audit

**Audit Date**: 2026-05-14

---

## 1. Pydantic Models and API Design — Core Asset Completely Missing

Three documents contain zero Pydantic model definitions. SQL Schema exists. Python module directories exist. But the middle layer — the type system — does not exist.

**API endpoint design is incomplete:**

Current plan has only 3 route files. Missing critical endpoints:
- `GET /health` — Docker Compose health check essential
- `POST /admin/rules/reload` — docs promise "hot-loadable rules" but no management interface
- `GET /v1/questionnaires/{type}` — frontend needs this as step one
- `POST /v1/assessments/{id}/answers/batch` — 20 questions submitted one at a time or batch? Affects frontend state management and audit granularity
- `GET /v1/assessments` — CHARITE auditing all sessions needs pagination params

**Error response model missing.** solver.py throws NoFeasiblePositionError. Exception class undefined. No corresponding FastAPI exception handler. All API errors should return unified ErrorResponse.

Recommendation: Split core/models.py and api/schemas.py explicitly — database models use SQLAlchemy 2.0 DeclarativeBase, API layer uses Pydantic.

---

## 2. Rule Engine Design — "Declarative YAML → Python Rule Classes" Is Vapor

1. **No YAML Schema.** What does rules/pharma_rules.yaml look like? Who guarantees format legality? Need JSON Schema or Pydantic model for static validation.

2. **Condition DSL incomplete.** Example has `{"gte": 3}` and `["A","B"]`. What's the full operator list? eq, ne, gt, lt, in, contains, regex, and, or, not? Missing DSL definition = interface contract left blank.

3. **Rule conflict detection missing.** Two rules trigger on same (state_type, node_id) but give contradictory advice? priority is just an integer. No conflict resolution strategy.

4. **Hot-reload mechanism undefined.** File system watchdog? SIGHUP signal? API trigger? Docker Compose single-container, file system watch behaves weirdly under volume mounts.

5. **Rule testing framework missing.** Recommend each YAML rule file paired with .test.yaml:
```yaml
- rule_id: "R-PHARMA-AI-001"
  given:
    answers: {q2.1: 4, q3.2: "A"}
  expect:
    action: "Establish DPO"
    triggered: true
```

6. **solver.py line 289: constraint.evaluate(state).** What type is constraint? Python object? Function? Pydantic validator? Type system completely collapses.

Recommendation: Add rules/ subpackage under core/ containing parser.py, validator.py, compiler.py, loader.py. Turn "YAML→Python" magic into an explicit, testable, type-annotated pipeline.

---

## 3. IP Terms — "Core Engine" Is a Legal Vague-Bomb

Current terms:
> "DataWego retains core engine code copyright"
> "Epidata receives perpetual usage license within SCAILED scope"
> "Commercialization outside SCAILED requires separate negotiation"

Specific problems:

1. **"Core engine" has no technical boundary.** Is it the pathfinder/core/ directory? solver.py and compliance.py? Including YAML rule files? If an Epidata engineer submits a PR to fix a graph.py bug, who owns the copyright?

2. **"Perpetual usage license" scope is fuzzy.** Does the license include modification rights? Sublicensing? Distribution rights? What about code inside Docker images?

3. **Third-party dependency license pollution.** FastAPI (MIT), NetworkX (BSD), PostgreSQL (PostgreSQL License), Vue3 (MIT) are all fine. If PyTorch or GPL libraries are added later, "core engine copyright" becomes complex. Contract should require prior written consent for all dependency licenses.

4. **"Post-project commercialization requires negotiation" lacks exclusivity.** Implies DataWego can sell to other clients but Epidata can't. Recommendation: both parties have right of first negotiation for 12 months post-project.

5. **Missing open source license choice.** "Core engine" should not be released under GPL/AGPL (too infectious). Recommend Apache-2.0 or MIT for SCAILED project.

**Recommendation**: Contract attachment IP_BOUNDARY.md, listing per-file copyright ownership.

---

## 4. Code Coverage ≥80% — Insulting to Core Engine

1. 80% is acceptable for FastAPI routing layer and frontend glue code. For solver.py graph algorithms, compliance.py constraint checking, recommend.py path mapping — should be ≥95%, branch coverage close to 100%.

2. No coverage type distinction. Recommend contract specify:
   - Overall line coverage ≥80%
   - core/ directory branch coverage ≥95%
   - solver.py and compliance.py line coverage 100%

3. Coverage can be gamed — test_foo(): assert True to inflate coverage. Contract should require mutation testing verification.

4. Missing performance test quantification. Backend locate() method is O(n) traversing all nodes, high concurrency is problematic. Acceptance criteria should have p95 latency metrics.

Recommendation: Split into "shell 80%, kernel 98%." Add test_performance.py with pytest-benchmark.

---

## 5. Python Module Structure — Missing At Least 6 Critical Directories

Current structure problems:
- frontend/ should not be inside Python package, move to repo root
- Dockerfile/docker-compose.yml should be at repo root or deploy/
- tests/ is too flat

**Missing modules:**

1. **migrations/** (Alembic) — PostgreSQL JSONB, Schema may need micro-adjustments post-freeze. No Alembic = manual ALTER TABLE.

2. **config/ or settings.py** (Pydantic Settings) — SECRET_TOKENS directly via os.environ.get() is too crude.

3. **exceptions/** — PathfinderError → NoFeasiblePositionError, ComplianceViolationError, RuleSyntaxError. These exceptions are scattered across files or don't exist at all.

4. **services/ or usecases/** — missing business logic layer between routes and core. When assessments.py needs "create session + validate questionnaire + generate initial recommendations," orchestration code in routes pollutes API layer, in core/ pollutes engine layer.

5. **scripts/** — data import scripts, rule validation scripts, database backup scripts.

6. **tests/fixtures/** and **tests/conftest.py** — shared mock data.

Other issues:
- No .env.example
- No Makefile or taskipy scripts
- api/routes/ missing questionnaires.py

---

## 6. Wording Overpromise Risk

Email draft dangerous phrases:

1. "Strategic positioning and navigation system with compliance constraints" — the resolution actually says "constrained graph search engine + questionnaire interface." For the client email, it's upgraded to "strategic positioning and navigation system."

2. "Not black-box AI" — negation marketing keeps attention on "AI." Lu Zhao might respond "so can we add ChatGPT functionality?"

3. "Every recommendation is auditable and traceable" — audit_log implemented via PostgreSQL RULE is not blockchain-grade immutable.

4. "Similar to Apple Setup Assistant experience" — Apple has millions of dollars in UX research. Implying this experience = invisible golden handcuffs.

SQL Schema technical bugs:
- roadmap_nodes.parent_node is TEXT without REFERENCES foreign key
- recommendation_rules.node_id references foreign key but primary key is id SERIAL
- audit_log immutability via RULE is paper-thin
- assessment_sessions.answers JSONB has no version validation

---

## Summary: Three Red Lines Requiring Immediate Fix

| Priority | Issue | Action |
|----------|-------|--------|
| 🔴 | Pydantic models completely missing | Complete all type definitions in core/models.py and api/schemas.py |
| 🔴 | "Core engine copyright" boundary fuzzy | Contract attachment IP_BOUNDARY.md, per-file ownership listing |
| 🔴 | Rule engine DSL undefined | Write rules/SCHEMA.json defining complete condition operator set |
| 🟡 | Coverage 80% undifferentiated | Split: "shell 80%, kernel 98%", add performance tests |
| 🟡 | Module structure missing migrations/config/exceptions | Complete directory structure, move frontend out of Python package |
| 🟡 | Email wording overpromises | "Strategic positioning" back to "graph search engine," delete "Apple" analogy |

Code is read much more often than it is written. Currently, nothing in these three documents can run on any machine — because Pydantic models don't exist, exception classes don't exist, the rule DSL doesn't exist. Recommendation: before sending to Lu Zhao, complete section 09_expanded_analysis.md's technical implementation into a pytest-passing skeleton project.

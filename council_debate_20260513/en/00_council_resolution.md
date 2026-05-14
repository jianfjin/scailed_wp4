# SCAILED WP4 Pathfinder System — Nine-Dragon Council Final Resolution

**Project**: DataWego (Contractor) developing SCAILED WP4 Pathfinder System for Epidata (Client)
**Dates**: 2026-05-13 (Initial) / 2026-05-14 (6-Seat Audit Revision)
**Council**: 9-seat plenary (Musk/Xuefeng/Guido/Dijkstra/Jensen/Jobs/Linus/Xiaolong/FengGe)
**Audit**: 6-seat review (Xuefeng/Musk/Jobs/Linus/Guido/Dijkstra)
**Timeline**: EU4Health SCAILED, M1–M36

> **Audit Revision Note**: The 2026-05-14 six-seat joint audit identified 17 risk items (7 critical). This resolution incorporates all audit fixes: IP terms rewrite, graph engine correction, payment restructuring, WP3 Plan B, audit log hardening, rule engine refactor, and wording corrections. Full audit reports in documents 10–16.

---

## Council Consensus: Technical Definition of Pathfinder

Pathfinder = Constrained graph search (CSP framework) + questionnaire interface. Not a web app, not a dashboard, not a "platform."

| Component | What It Is | What It Is Not |
|-----------|-----------|----------------|
| Core | Constraint Satisfaction Problem — graph search pruned by WP8 regulatory rules | GPT chatbot / A* (not claimed without admissible heuristic proof) |
| Input | Structured questionnaire + WP3 roadmap (DAG) + WP8 regulations (declarative rules) | PDF/PPT manual parsing |
| Output | Explainable deterministic paths, each recommendation traceable to rule chain | Natural language paragraphs / black-box probabilistic suggestions |
| Interface | Interactive compliance path planner: questionnaire → current position → recommended steps → export | Flashy dashboard |
| Positioning | Deterministic, auditable decision support system exceeding EU AI Act transparency requirements | Defensive "not AI" messaging |

> **Dijkstra Correction**: This is not pure shortest-path — path feasibility depends on (stakeholder, path) pairs. It is a CSP, not Dijkstra 1959. S is a finite discrete profile set, not ℝⁿ. A* is not claimed — no admissible heuristic has been proven.

## Architecture

Three-layer monolith: Vue 3 frontend → FastAPI backend → PostgreSQL (with Apache AGE graph engine)

```
pathfinder/
├── core/           # Pure Python: Pydantic models, solver, compliance, graph
│   ├── models.py   # Type system (Audit requirement: must exist)
│   ├── solver.py   # Constrained graph search (AGE primary, NetworkX fallback)
│   ├── rules/      # Rule DSL: parser, validator, compiler, loader
│   └── exceptions/ # PathfinderError hierarchy
├── api/            # FastAPI: routes, schemas, dependencies
├── services/       # Business orchestration (Audit requirement: decouple routes from core)
├── adapters/       # WP2/3/5/6/7/8 data adapters
├── migrations/     # Alembic (Audit requirement: must exist)
├── config/         # Pydantic Settings (Audit requirement: replace bare os.environ)
├── scripts/        # Data import, rule validation
├── frontend/       # Vue 3 SPA (Audit requirement: moved out of Python package)
├── tests/          # pytest + fixtures + conftest
│   ├── fixtures/   # Shared mock data
│   └── conftest.py
├── deploy/         # Docker Compose, Nginx config
└── IP_BOUNDARY.md  # Per-file IP ownership (Audit requirement)
```

- **No microservices, No K8s, No Neo4j, No GraphQL**
- **Docker Compose deployment** (PostgreSQL independent volume; V1 single-node mode explicitly declared)
- Rule engine externalized (YAML/JSON, with JSON Schema static validation), hot-loadable (API trigger + watchdog)
- Audit log: PostgreSQL TRIGGER (not RULE) + prev_hash cryptographic chain
- Graph engine: **Apache AGE (PostgreSQL native graph extension, Cypher embedded in SQL)** + NetworkX as dev/testing fallback
- Rule structure: recommendation_rules tree structure (parent_rule_id + rule_type enum + priority)

## Technology Stack

| Layer | Selection | Audit Correction |
|-------|-----------|-----------------|
| Language | Python 3.12 | — |
| Backend | FastAPI + Pydantic v2 | NetworkX ops must use ThreadPoolExecutor to avoid event loop blocking |
| Rule Engine | Declarative YAML → Python rule classes | Added: condition operator JSON Schema + conflict resolution + .test.yaml |
| Database | PostgreSQL 16+ | — |
| Graph Engine | **Apache AGE** (primary) + NetworkX (dev) | Audit fix: pure NetworkX breaks SLA beyond 200 nodes |
| Frontend | Vue 3 + Vite | — |
| Deployment | Docker Compose | V1 single-node; K8s is V2 territory |
| Testing | pytest + hypothesis + pytest-benchmark | Shell ≥80%, kernel ≥98%; mutation testing verification |

## Phase Breakdown

| Phase | Timeline | Scope | Priority | Audit Correction |
|-------|----------|-------|----------|-----------------|
| Phase 0: Formalization Baseline | M1–M3 | Schema confirmation (WP2/3/8) + data extraction layer + code skeleton | 🔴 Go/No-Go | Added: auto-extend to M5 if unsigned |
| Phase 1: Core Engine | M4–M8 | CSP engine (AGE) + constraint checker + questionnaire engine | 🔴 | Compressed 1 month; AGE introduced |
| Phase 2: API + Frontend MVP | M9–M14 | FastAPI + Vue 3 frontend | 🟡 | — |
| Phase 3: V1 Delivery | M15–M20 | Polish + report support | 🟡 | — |
| Phase 4: Test Drive | M21–M24 | T4.2 validation feedback (CHARITE-led) | 🟢 | DataWego bugfix only |
| Phase 5: V2 Iteration | M25–M33 | D4.4 Final Guidelines (CHARITE-led) | 🟢 | Separate contract |

> **Musk Correction**: MVP can be done in 3–4 months. Phases 0–2 compressed from 15 to 14 months. Freed time goes to real user testing, EHDS compliance verification, and actual-scale performance testing.

## Upstream/Downstream Data Exchange

**DataWego Requires**:
- WP3 Roadmap (JSON/CSV + topology verification) — BLOCKING
- WP8 Regulatory constraints (declarative rules/YAML) — BLOCKING
- WP2 Stakeholder classification (JSON Schema) — BLOCKING
- **WP3 Plan B**: Contract requires Epidata to guarantee structured delivery or fund data extraction; Pathfinder runs on "best available" data with confidence markers

**DataWego Delivers**: D4.1 Demo + report, REST API endpoints (with rate limiting), Docker Compose deployment package, cryptographically-chained audit log

## Core Risks (Audit-Hardened)

| Risk | Probability | Impact | Mitigation | Audit Source |
|------|------------|--------|------------|-------------|
| WP3 delivers PDF instead of structured data | Very High | Critical | M2 mandate JSON format + **contractual guarantee from Epidata for structured delivery or extraction funding + data extraction layer** | Musk, Jobs |
| WP8 regulations not formalizable | High | High | Soft checks + hot-loadable rules + .test.yaml rule testing framework | Guido |
| NetworkX performance collapse (200+ nodes) | High | Critical | **Introduce Apache AGE at M4, replacing pure NetworkX** | Linus |
| EU4Health IP rule violation | High | Critical | **Background/Foreground IP split + IP_BOUNDARY.md per-file ownership** | Xuefeng, Guido |
| M9 payment tied to CHARITE → cash flow break | Very High | Critical | **Split to M9 15% + M15 15% + CHARITE delay >30 days → Epidata advances** | Xuefeng |
| M3 schema not signed, no extension mechanism | High | High | **Auto-extend to M5, payment shifts; upstream post-M3 changes billable** | Xuefeng |
| Rework clause EUR-X/day left blank | High | High | **Three-tier rates + written approval process + caps (single ≤15%, annual ≤30%)** | Xuefeng |
| Audit log via RULE unreliable | Medium-High | Medium | **RULE → TRIGGER + prev_hash cryptographic chain** | Linus, Guido |
| EHDS implementing acts change mid-project | Medium-High | Medium | Hot-loadable rule engine + rule_versions table | — |

## Contract Framework (Audit-Hardened)

### IP Terms
- **Background IP**: DataWego's pre-existing graph search algorithm framework (defined per-file in IP_BOUNDARY.md) remains DataWego property
- **Foreground IP**: Customizations developed during SCAILED for EU4Health requirements are jointly owned by the project consortium
- DataWego receives right of first negotiation for commercialization outside SCAILED (12 months post-project)
- License: Apache-2.0 or MIT (not GPL/AGPL)

### Payment Structure
- Advance: 30% (within 15 days of contract signing)
- Core Engine Delivery: 15% (M9, core engine + mock data end-to-end verification passed)
- MVP Delivery: 15% (M15, frontend MVP + API complete)
- D4.1 Final: 40% (M20, acceptance passed)
- CHARITE payment delay >30 days → Epidata advances at milestone

### Rework Terms
- Three-tier rates: Architect €800–1200/day, Senior €600–800/day, Junior €400–600/day
- Process: Written change request → DataWego estimate (5 business days) → mutual written confirmation → start
- Caps: Single change ≤15% of contract total, annual cumulative ≤30%
- Refinements within Schema baseline are included in fixed price (only structural changes post-M3 baseline trigger rework billing)

## Feng Ge's Strategic Rulings

1. **Solid kernel** (AGE graph search + CSP engine + cryptographic audit chain, kernel ≥98% coverage)
2. **Polished shell** (Frontend UI + demo recording + PDF report, shell ≥80% coverage)
3. **Baseline before code** (Jointly confirm Schema baseline by M3; auto-extend to M5 if unsigned)
4. **Contract moat** (Background/Foreground IP split, split payments, three-tier rework rates, advance clause)
5. **Subtraction only** (Xiaolong MVP checklist)
6. **Data without prayer** (WP3 Plan B: contract guarantee + extraction layer + degradation strategy)
7. **Build bridges, not walls** (Collaborative tone: joint baseline, mutual confirmation, coordinated calibration)

> **Jobs' final cut**: *"Pathfinder doesn't help you fill compliance forms. It makes compliance intuitive."*

---

*Archive: ~/projects/scailed_wp4/council_debate_20260513/en/00_council_resolution.md*
*Full council speeches in documents 01–08 · Audit reports in 10–16*
*Audit revision date: 2026-05-14*

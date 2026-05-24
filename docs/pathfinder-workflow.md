# Pathfinder V1 — Workflow & Decision Process

> SCAILED WP4 — Strategic Reasoning Layer for EHDS Compliance Assessment  
> Last updated: 2026-05-24 | Branch: `feature/rules-engine-dsl-schema`

## Overview

Pathfinder is a **deterministic state-transition engine**. Given a stakeholder's current
maturity profile, it finds the optimal path through a roadmap graph toward a target
scenario, applying compliance rules along the way.

```
User ──(select stakeholder)──→ Questionnaire ──(submit answers)──→ StakeholderState
                                                                         │
                              ┌──────────────────────────────────────────┘
                              ▼
                    PathfinderSolver.solve()
                    ├─ graph.locate_current()     ← match maturity to roadmap node
                    ├─ graph.locate_target()      ← match target scenario to node
                    ├─ evaluator.triggered_rules() ← apply WP8 compliance rules
                    └─ graph.shortest_path()      ← BFS (with blocked nodes removed)
                              │
                              ▼
                         PathResult
                    ├─ steps (ordered nodes)
                    ├─ blockers (path cannot proceed)
                    ├─ warnings (non-blocking guidance)
                    └─ triggered_rules (audit trail)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Pathfinder Backend                          │
│                                                                     │
│  AssessmentService (orchestrator)                                   │
│  ├─ QuestionnaireEngine → builds StakeholderState from answers      │
│  ├─ PathfinderSolver → graph search + rule evaluation               │
│  ├─ ComplianceEvaluator → deterministic rule matching               │
│  ├─ InMemoryRoadmapGraph ← NetworkX (BFS fallback, default)        │
│  └─ AgeRoadmapGraph ← PostgreSQL + Apache AGE (production)          │
│                                                                     │
│  Data Sources (upstream)                                            │
│  ├─ WP2 → stakeholder taxonomy (questionnaire definitions)          │
│  ├─ WP3 → roadmap graph (nodes + edges, 1K nodes / 1.8K edges)     │
│  └─ WP8 → compliance rule bundles (1K generated + 6 curated)       │
└─────────────────────────────────────────────────────────────────────┘
```

## Decision Flow — Step by Step

### Phase 1: Data Ingestion (startup)

```
UpstreamClient.startup()
  ├─ GET /api/v1/stakeholders  (WP2:8102) → 1005 stakeholder types
  ├─ GET /api/v1/roadmap/nodes (WP3:8103) → 1000 roadmap nodes
  ├─ GET /api/v1/roadmap/edges (WP3:8103) → 1783 edges
  ├─ GET /api/v1/rules         (WP8:8108) → 1006 rules (incl. 6 curated)
  └─ GET /api/v1/tests         (WP8:8108) → test cases (optional)
```

All three WP services run as local Python `aiohttp.web` apps via systemd
(`scailed-mocks.service`, ports 8102/8103/8108). No Docker dependency.

### Phase 2: Assessment (per session)

```
Step 1 ── User selects stakeholder type + target scenario
              ↓
Step 2 ── QuestionnaireEngine.get(stakeholder_type)
              → returns Questionnaire with 6 questions:
                - governance_maturity (1-5)
                - data_maturity (1-5)
                - compliance_maturity (1-5)
                - capabilities (multi-choice)
                - missing_capabilities (multi-choice)
                - regulatory_flags (multi-choice, optional)
              ↓
Step 3 ── User submits answers
              ↓
Step 4 ── QuestionnaireEngine.build_state()
              → returns StakeholderState:
                - stakeholder_type
                - target_scenario
                - maturity_scores {governance, data, compliance}
                - capabilities [...]
                - missing_capabilities [...]
                - regulatory_flags [...]
                - confidence (based on completeness)
              ↓
Step 5 ── PathfinderSolver.solve(state, rules)
              5a. graph.locate_current(state)
                  → matches stakeholder_type + maturity_scores
                     to nearest roadmap node
              5b. graph.locate_target(state)
                  → matches stakeholder_type + target_scenario
                     to goal node
              5c. evaluator.triggered_rules(state, rules)
                  → iterates all 1006 rules, evaluates conditions:
                    - Atomic: field + operator + value
                    - Compound: and/or/not (recursive)
                    - Empty: always match
                  → returns triggered rules sorted by priority
              5d. graph.shortest_path(current, target)
                  → BFS over DAG, removes blocker nodes
                  → returns ordered node list
              ↓
Step 6 ── build_recommendation(path)
              → PathResult:
                - status: ok | blocked | degraded
                - steps: [...] (cherry-picked path)
                - blockers: [...] (reasons path cannot proceed)
                - warnings: [...] (non-blocking guidance)
                - triggered_rules: N (count)
                - confidence: 0.0-1.0
```

## Condition DSL

Rules use a deterministic condition language — no LLM involvement in
decision-making:

```json
{
  "condition": {
    "and": [
      { "field": "answers.governance_maturity", "operator": "gte", "value": 4 },
      { "field": "capabilities", "operator": "contains", "value": "data-catalog" }
    ]
  }
}
```

| Type | Syntax | Example |
|------|--------|---------|
| Atomic | `{field, operator, value}` | `{"field":"data_maturity","operator":"gte","value":3}` |
| AND | `{and: [condition, ...]}` | All sub-conditions must match |
| OR | `{or: [condition, ...]}` | Any sub-condition matches |
| NOT | `{not: condition}` | Negates the sub-condition |
| Empty | `{}` | Always matches |

### Operators

| Operator | Applies To | Description |
|----------|-----------|-------------|
| `eq` | scalar | Equal |
| `ne` | scalar | Not equal |
| `gt` | scalar | Greater than |
| `gte` | scalar | Greater than or equal |
| `lt` | scalar | Less than |
| `lte` | scalar | Less than or equal |
| `in` | list | Value is in list |
| `not_in` | list | Value not in list |
| `contains` | list | List contains value |
| `exists` | any | Field is non-null/non-empty |

### Action Types

| Action Field | Type | Description |
|-------------|------|-------------|
| `title` | string (req) | Short human-readable title |
| `text` | string (req) | Detailed description |
| `node_id` | string? | Suggested reroute target node |
| `warning` | string? | Warning message |
| `block` | bool | If true, blocks the path |

### Rule Types

| Type | Meaning |
|------|---------|
| `eligibility` | Prerequisite check — must pass to proceed |
| `exclusion` | Blocks path entirely if condition matches |
| `preference` | Recommends a node or action (non-blocking) |
| `override` | Forces reroute to specific node |

## Integration Points

### Mock Services (localhost, systemd-managed)

| Service | Port | Endpoints | Data |
|---------|------|-----------|------|
| WP2 Mock | 8102 | `/api/v1/stakeholders` | 1000 stakeholder types |
| WP3 Mock | 8103 | `/api/v1/roadmap/nodes`, `/edges` | 1000 nodes, 1783 edges |
| WP8 Mock | 8108 | `/api/v1/rules`, `/api/v1/tests` | 1006 rules |

### Graph Backends

| Backend | When | Dependencies |
|---------|------|-------------|
| `InMemoryRoadmapGraph` | Default / demo / fallback | NetworkX |
| `AgeRoadmapGraph` | Production (`PATHFINDER_MODE=deployed`) | PostgreSQL + Apache AGE |

### Schema Validation

All rule bundles are validated against `schema.json` using `jsonschema` on load.
The schema captures the full condition DSL and action structure.

## Deployment

```
Standalone (no Docker):
  systemctl --user start scailed-mocks.service
  ├─ python3 wp2_mock → :8102
  ├─ python3 wp3_mock → :8103
  └─ python3 wp8_mock → :8108

Docker Compose:
  docker compose -f deploy/docker-compose.yml up -d
  ├─ traefik (reverse proxy, :8647)
  ├─ frontend (nginx + React SPA)
  ├─ backend (FastAPI)
  ├─ postgres (PG16 + Apache AGE)
  ├─ redis (optional cache)
  ├─ wp2-mock (:8102)
  ├─ wp3-mock (:8103)
  └─ wp8-mock (:8108)
```

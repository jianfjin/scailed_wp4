# Merged Pathfinder V1 Technical Design

Date: 2026-05-15

Status: Draft architecture

Related docs:

- `docs/12_merged_pathfinder_spec.md`
- `docs/14_merged_pathfinder_plan.md`
- `council_debate_20260513/en/00_council_resolution.md`
- `council_debate_20260513/en/09_expanded_analysis.md`

## Architecture Decision

Use a modular monolith:

```text
frontend -> FastAPI -> PostgreSQL 16 + Apache AGE
                 |
                 -> rule files, import adapters, report export
```

This keeps V1 small enough for D4.1 while preserving a clean path to V2.

Rejected for V1:

- microservices
- Neo4j
- GraphQL
- Kubernetes
- AI/RAG-generated recommendations
- full multi-tenant SaaS

Deferred to V2:

- AI copilot
- GraphRAG
- production integrations
- advanced dashboards
- multi-tenant operations
- Helm/Terraform

## System Components

```text
pathfinder/
  core/
    models.py
    graph.py
    solver.py
    compliance.py
    recommend.py
    rules/
      schema.json
      parser.py
      validator.py
      compiler.py
      loader.py
    exceptions/
  api/
    main.py
    schemas.py
    routes/
      health.py
      questionnaires.py
      assessments.py
      roadmap.py
      compliance.py
      reports.py
      admin.py
    middleware/
      audit.py
      rate_limit.py
  services/
    assessment_service.py
    graph_service.py
    recommendation_service.py
    report_service.py
    extraction_service.py
  adapters/
    wp2_stakeholders.py
    wp3_roadmap.py
    wp8_rules.py
    demo_data.py
  migrations/
  frontend/
  deploy/
  tests/
    fixtures/
  docs/
  IP_BOUNDARY.md
```

## Runtime View

1. Frontend requests questionnaire for stakeholder type.
2. User submits assessment answers.
3. API validates answers and stores versioned session snapshot.
4. Core converts answers to `StakeholderState`.
5. Solver locates current roadmap position.
6. Rule engine filters or annotates feasible paths.
7. Recommendation service ranks paths and builds traceability payload.
8. Report service exports dashboard view and PDF/report artifact.
9. Audit middleware records answer, recommendation, and export events.

## Core Domain Model

### StakeholderState

Represents current user context:

- stakeholder_type
- target_scenario
- answers
- maturity_scores
- capabilities
- constraints
- confidence
- schema_version

### RoadmapNode

Represents a step on the WP3 roadmap:

- node_id
- label
- description
- dimension
- maturity_level
- stakeholder_types
- prerequisites
- source_wp
- source_doc_ref
- confidence
- metadata

### RoadmapEdge

Represents dependency/order between roadmap nodes:

- edge_id
- from_node_id
- to_node_id
- relation_type
- required
- source_doc_ref

### Rule

Represents deterministic recommendation/compliance logic:

- rule_id
- parent_rule_id
- rule_type
- priority
- applies_to
- condition
- action
- compliance_refs
- effective_from
- effective_until
- source_doc_ref

### PathResult

Represents generated next-step path:

- current_node
- target_node
- steps
- blockers
- warnings
- triggered_rules
- confidence
- trace

## Database Design

Core tables:

- `schema_versions`
- `upstream_data_snapshots`
- `stakeholder_types`
- `questionnaires`
- `roadmap_nodes`
- `roadmap_edges`
- `rule_versions`
- `recommendation_rules`
- `assessment_sessions`
- `recommendations`
- `audit_log`

### Graph Storage

Primary graph engine: PostgreSQL AGE.

Rationale:

- keeps deployment in PostgreSQL
- avoids Neo4j operational cost
- avoids pure Python NetworkX performance limits
- supports graph traversal in database layer

NetworkX is allowed only as:

- local development fallback
- unit-test graph backend
- emergency fallback for small graphs

### Versioning

Every assessment stores:

- schema_version_id
- questionnaire_version
- rule_version_id or rule bundle checksum
- upstream snapshot IDs

This answers: "Which inputs produced this recommendation?"

## Rule Engine Design

Rules are stored as YAML or JSON and validated against `core/rules/schema.json`.

Supported rule types:

- `eligibility`
- `exclusion`
- `preference`
- `override`

Supported condition operators:

- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`
- `in`
- `not_in`
- `contains`
- `exists`
- `and`
- `or`
- `not`

Each rule file must have a paired test file:

```text
rules/wp8_ehds.yaml
rules/wp8_ehds.test.yaml
```

Rule load pipeline:

```text
parse -> schema validate -> compile -> conflict scan -> run tests -> activate
```

Hot reload:

- `POST /admin/rules/reload`
- validates new rules before activation
- keeps previous active rules if validation fails
- records audit event

## API Design

Minimum V1 endpoints:

```text
GET  /health
GET  /v1/questionnaires/{stakeholder_type}
POST /v1/assessments
GET  /v1/assessments/{assessment_id}
POST /v1/assessments/{assessment_id}/answers/batch
POST /v1/assessments/{assessment_id}/recommendations
GET  /v1/assessments/{assessment_id}/report
GET  /v1/roadmap
GET  /v1/roadmap/{node_id}
POST /admin/import/wp2
POST /admin/import/wp3
POST /admin/import/wp8
POST /admin/rules/reload
```

Admin endpoints require bearer token access.

Public assessment endpoints use invited bearer token or signed demo link.

## Frontend Design

Framework: React. Epidata/Charite preference is now resolved in favor of React.

V1 views:

- invited landing/session start
- stakeholder selection
- guided questionnaire
- readiness summary
- roadmap path view
- recommendation trace view
- report export view
- admin import/status view

UX principles absorbed from `docs/`:

- product-oriented guided flow
- concise three-step assessment experience
- roadmap visualizer
- report-first output
- clear warnings when data is mock, incomplete, or unverified

Avoid:

- decorative dashboards that do not support D4.1 acceptance
- unexplained AI branding
- client-facing jargon such as CSP, AGE, graph search, or solver

## Data Import Design

Each upstream input has an adapter:

- `wp2_stakeholders.py`
- `wp3_roadmap.py`
- `wp8_rules.py`
- `demo_data.py`

Adapter responsibilities:

- parse accepted format
- validate schema
- normalize IDs
- detect missing fields
- calculate checksum
- store upstream snapshot
- emit import report

Accepted input formats:

- JSON
- YAML
- CSV
- JSON Schema

Fallback formats:

- Markdown
- DOCX
- PDF
- PPTX

Fallback extraction is a separate workstream and must mark extracted data as lower confidence until reviewed.

## Graceful Degradation

Pathfinder must degrade explicitly:

| Missing input | Behavior |
| --- | --- |
| WP2 stakeholder taxonomy | use generic stakeholder questionnaire |
| WP3 roadmap labels | route by node IDs, hide label filters |
| WP3 prerequisites | warn "prerequisites unverified" |
| WP8 rules | mark compliance unverified |
| all upstream inputs | run demo mode with mock data |

All degradation decisions create audit events.

## Security Design

V1 is a controlled demo, not a public production system.

Security controls:

- no patient data
- no direct EHDS production data
- invited access token
- admin bearer token
- rate limiting
- hashed IP/user-agent audit fields
- append-only audit table with previous-hash chain
- safe error responses
- HTTPS via reverse proxy in deployed mode

Out of V1 scope:

- OAuth/OIDC integration
- user self-registration
- password reset
- production RBAC hierarchy
- DPIA authoring

## Deployment Design

V1 deployment:

```text
deploy/docker-compose.yml
  reverse-proxy
  frontend
  backend
  postgres-age
  redis
```

PostgreSQL must use a named volume and must not be packaged inside the backend container.

Kubernetes is V2 scope.

## Testing Design

Test levels:

- unit tests for core models, rule DSL, compliance, graph traversal
- integration tests for API flows
- rule tests from `.test.yaml`
- import validation tests
- report export tests
- benchmark tests for graph/path generation

Coverage targets:

- core engine: very high branch coverage
- solver/compliance/rules: near-complete branch coverage
- API/frontend shell: pragmatic flow coverage

Performance target:

- assessment recommendation generation p95 <= 3 seconds at V1 demo scale

## Observability

V1 should expose:

- `/health`
- import status
- active schema/rule versions
- audit-log integrity check
- basic request/error logs

Full monitoring stack is V2 scope.

## IP Boundary Design

Maintain `IP_BOUNDARY.md` with per-file ownership:

- DataWego background IP
- SCAILED foreground IP
- jointly adapted connectors
- WP-provided rule/content data
- third-party dependencies and licenses

Avoid GPL/AGPL dependencies unless approved in writing.

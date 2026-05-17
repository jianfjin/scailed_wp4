# Merged Pathfinder V1 Execution Plan

Date: 2026-05-15

Status: Draft plan

Related docs:

- `docs/12_merged_pathfinder_spec.md`
- `docs/13_merged_pathfinder_design.md`

## Strategy

Build a narrow D4.1 Pathfinder V1 first, then use stakeholder feedback and partner data to decide V2 scope.

The highest-leverage move is not to build a full EHDS SaaS platform now. It is to build a credible, auditable path planner that proves the Pathfinder methodology, survives incomplete upstream data, and gives Epidata a strong D4.1 demo.

## Success Criteria

By D4.1/M20, DataWego can deliver:

- running Pathfinder V1 demo
- structured questionnaires for at least 5 stakeholder types
- deterministic recommendation/path generation
- visible rule and roadmap traceability
- report export
- mock-data package
- import tooling for WP2/WP3/WP8 data
- Docker Compose deployment package
- technical notes supporting D4.1 report/demo

## Phase 0: Alignment and Baseline (M1-M3)

Goal: freeze enough product and data structure to start safely.

Tasks:

- confirm V1 scope and non-goals with Epidata
- confirm stakeholder types for V1
- confirm D4.1 demo scenario
- define WP2/WP3/WP8 data contracts
- define schema versions and sample inputs
- create mock data set
- define rule DSL and rule test format
- create repo skeleton
- create `IP_BOUNDARY.md`
- create deployment skeleton

Deliverables:

- signed V1 scope
- M3 schema baseline
- mock data package
- rule schema draft
- running skeleton app
- import validation proof of concept

Verification:

- sample WP2/WP3/WP8 data imports without manual database edits
- one demo questionnaire can create one assessment session
- one hard-coded rule can generate one traceable recommendation
- Docker Compose boots app/database locally

Gate:

- If WP2/WP3/WP8 data contracts are not confirmed by M3, continue with mock-data baseline and mark partner data as pending.
- If schema disagreement blocks delivery, extend baseline to M5 and shift later acceptance dates.

## Phase 1: Core Engine (M4-M8)

Goal: build deterministic Pathfinder kernel.

Tasks:

- implement Pydantic domain models
- implement SQL migrations
- implement PostgreSQL AGE graph storage
- implement NetworkX test fallback
- implement questionnaire engine
- implement rule parser/validator/compiler/loader
- implement rule conflict checks
- implement rule `.test.yaml` runner
- implement path solver
- implement compliance evaluator
- implement recommendation ranking
- implement audit log with append-only trigger and previous-hash chain
- implement upstream data snapshots

Deliverables:

- core engine
- rule engine
- graph/path planner
- versioned database
- audit log
- benchmark suite

Verification:

- core unit tests pass
- sample graph imports and traverses
- sample rules validate and execute
- contradictory rules are detected or resolved by priority
- audit log rejects update/delete
- graph benchmark meets V1 latency target at demo scale

## Phase 2: API and Frontend MVP (M9-M14)

Goal: turn kernel into usable D4.1 demo product.

Tasks:

- implement FastAPI endpoints
- implement API schemas and error model
- implement rate limiting
- implement invited-token access
- implement admin imports
- implement frontend guided assessment
- implement stakeholder selection
- implement roadmap path view
- implement recommendation trace view
- implement import/status admin view
- implement report export
- add demo data mode banner

Deliverables:

- end-to-end assessment flow
- frontend MVP
- admin import flow
- report export
- API documentation

Verification:

- user can complete questionnaire end to end
- recommendations include trace payload
- report exports successfully
- admin can reload rules
- invalid rules do not replace active rules
- standard assessment returns within p95 3 seconds at demo scale

Payment/contract alignment:

- M9 milestone should correspond to core engine plus mock data end-to-end verification.
- M15 milestone should correspond to frontend MVP plus API complete.

## Phase 3: D4.1 Hardening and Demo Delivery (M15-M20)

Goal: deliver credible Pathfinder V1/demo.

Tasks:

- polish main user flow
- harden error handling
- improve report language
- add deployment docs
- add demo script
- add seed/demo data
- run stakeholder review sessions
- apply only in-scope refinements
- create D4.1 technical appendix
- create demo recording support material

Deliverables:

- Pathfinder V1 demo
- Docker Compose deployment package
- D4.1 technical appendix
- demo script
- acceptance test report

Verification:

- clean install from deployment docs
- D4.1 demo script completes without manual database changes
- acceptance criteria from `docs/12_merged_pathfinder_spec.md` pass
- audit-log integrity check passes
- report export matches expected content

## Phase 4: Test Drive Support (M21-M24)

Goal: support T4.2 validation without opening uncontrolled V2 scope.

Tasks:

- support Charite-led validation
- collect issue reports
- classify feedback as bug, calibration, upstream data issue, or V2 request
- fix V1 defects
- update rules/data under change control
- preserve traceability of changes

Deliverables:

- validation support log
- bugfix releases
- feedback classification report

Verification:

- each validation issue has disposition
- V1 defects fixed and regression-tested
- V2 requests deferred or separately scoped

## Phase 5: V2 Scoping (M25-M33)

Goal: decide what becomes Pathfinder V2 after real feedback exists.

Candidate V2 additions:

- AI copilot/RAG over regulatory and project docs
- GraphRAG for knowledge exploration
- production-grade auth
- real HDAB/AI Factory integration adapters
- advanced dashboards
- multi-tenant operations
- Kubernetes/Helm/Terraform
- richer ontology package
- multilingual support

V2 should be separately contracted or separately budgeted.

## Workstreams

### Product and UX

- stakeholder flow
- questionnaire UX
- roadmap/path visualizer
- traceability view
- report content
- demo script

### Core Engine

- domain models
- graph backend
- rule DSL
- compliance evaluator
- path solver
- recommendation ranking
- confidence/degradation handling

### Data and Import

- WP2 adapter
- WP3 adapter
- WP8 adapter
- demo data package
- extraction fallback
- upstream snapshots

### API and Frontend

- REST API
- API schemas
- frontend guided flow
- admin import/status
- report export

### Security and Audit

- invited access token
- admin token
- rate limiting
- append-only audit log
- previous-hash chain
- privacy-safe logging

### Deployment and QA

- Docker Compose
- migrations
- seed data
- tests
- benchmarks
- documentation

## Dependency Plan

Blocking dependencies:

- WP2 stakeholder taxonomy
- WP3 roadmap graph
- WP8 regulatory rules

Fallback:

- Use mock data and public EHDS-style demo data.
- Mark all inferred/extracted content with confidence.
- Do not block core platform work on partner document delays.

Data contract rule:

- Structured input is default.
- Unstructured-only input creates extraction effort and lower confidence.

## Risk Management

| Risk | Response |
| --- | --- |
| Scope expands to full platform | Maintain V1/V2 boundary in all docs and meetings |
| Partner data late | Build mock-data-first and import later |
| WP3 output unstructured | Use extraction service and request funded curation |
| WP8 rules ambiguous | Use soft checks, priority rules, and unverified flags |
| Client expects AI | Position V1 as auditable decision support, defer AI to V2 |
| Graph engine complexity | Validate AGE early in Phase 1 |
| Acceptance subjective | Use explicit acceptance criteria and demo script |
| Cash flow tied to upstream payment | Use split milestone and advance-on-delay clause |

## Contract Guardrails

Recommended contract boundaries:

- Phase 1 fixed-price scope covers V1/D4.1 only.
- V2, production operations, and real integrations are separate scope.
- Post-baseline structural changes require written change request.
- Rework has tiered rates, estimate approval, and caps.
- Epidata guarantees structured upstream data or funds extraction.
- Charite/Epidata/WP8 retain responsibility for legal interpretation and formal compliance approval.

Payment structure:

- 30 percent advance on contract signing
- 15 percent at core engine + mock-data end-to-end verification
- 15 percent at frontend MVP + API completion
- 40 percent at D4.1 acceptance
- if upstream coordinator payment is delayed more than 30 days, Epidata advances the milestone payment

## Immediate Next Steps

1. Review `docs/12_merged_pathfinder_spec.md` with Epidata.
2. Confirm V1 non-goals and acceptance criteria.
3. Confirm stakeholder types for first demo.
4. Confirm whether React or Vue is preferred.
5. Draft WP2/WP3/WP8 data contract templates.
6. Create implementation repo skeleton.
7. Build mock-data end-to-end proof.


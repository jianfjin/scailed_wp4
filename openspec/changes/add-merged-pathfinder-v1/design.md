## Context
Pathfinder V1 is a D4.1 demo-grade EHDS readiness path planner for SCAILED WP4. It consumes structured stakeholder, roadmap, and regulatory inputs from WP2, WP3, and WP8; asks users stakeholder-specific readiness questions; maps answers to a roadmap position; produces ranked next steps; and preserves traceability for review.

The change follows the merged source documents:

- `docs/12_merged_pathfinder_spec.md`
- `docs/13_merged_pathfinder_design.md`
- `docs/14_merged_pathfinder_plan.md`

## Goals / Non-Goals
Goals:

- Deliver a credible V1/demo by D4.1/M20.
- Keep recommendations deterministic and auditable.
- Support incomplete upstream data with explicit confidence and degradation markers.
- Provide report export and technical evidence for stakeholder review.
- Keep deployment simple enough for technical reviewers to run with Docker Compose.

Non-Goals:

- Production multi-tenant SaaS.
- AI copilot, RAG, GraphRAG, or LLM-generated recommendations.
- Automated legal decision-making.
- Direct HDAB, SPE, AI Factory, hospital, or production EHDS integration.
- Kubernetes, Helm, Terraform, GraphQL, Neo4j, OAuth/OIDC, public registration, password reset, or full production RBAC.
- V2 guideline authoring or production operations unless separately scoped.

## Decisions
- Decision: Use a modular monolith with frontend, FastAPI backend, PostgreSQL 16, Apache AGE, import adapters, deterministic rule files, and report export.
  Rationale: This is small enough for D4.1 while retaining a clean path to V2.
- Decision: Use PostgreSQL AGE as the primary graph backend, with NetworkX limited to development, unit tests, and emergency fallback for small graphs.
  Rationale: Keeps graph traversal close to the database and avoids Neo4j operational cost.
- Decision: Store rules as YAML or JSON validated by a rule schema, compiled before activation, tested with paired rule test files, and hot-reloaded only after validation.
  Rationale: EHDS/WP8 rules need traceability, versioning, and safe updates.
- Decision: Store schema, questionnaire, rule, and upstream snapshot versions with each assessment and recommendation.
  Rationale: Reviewers must know which inputs produced each recommendation.
- Decision: Use invited demo access and admin bearer tokens for V1.
  Rationale: V1 is controlled-demo software, not a public production system.

Alternatives considered:

- Microservices, Kubernetes, Helm, and Terraform were rejected for V1 as operationally too heavy.
- Neo4j was rejected for V1 to avoid an additional graph database dependency.
- GraphQL was rejected for V1 because REST endpoints cover the demo workflow.
- AI/RAG-generated recommendations were rejected because V1 requires deterministic, explainable behavior.

## Risks / Trade-Offs
- WP2/WP3/WP8 data arrives late or unstructured -> use mock-data baseline, import adapters, extraction fallback, and confidence markers.
- WP8 rules remain ambiguous -> support soft checks, priorities, "unverified" compliance states, and rule test cases.
- Scope expands toward a full platform -> preserve V1/V2 boundaries in proposal, tasks, and acceptance criteria.
- Graph traversal misses the p95 target -> validate Apache AGE early and keep benchmark tests in the core phase.
- Legal/IP boundaries remain unclear -> maintain `IP_BOUNDARY.md` with per-file ownership and dependency license notes.

## Migration Plan
No existing OpenSpec capability or implementation is present. Implementation should proceed only after this proposal is approved.

1. Create the Pathfinder skeleton and mock-data baseline.
2. Implement the deterministic core engine and persistence model.
3. Add API, frontend, report export, admin imports, and deployment package.
4. Harden the D4.1 demo and support validation without opening uncontrolled V2 scope.

## Open Questions
- Which frontend framework should be selected after Epidata/Charite preference: React or Vue?
- Which five stakeholder types are in the first accepted demo set?
- Which WP8 rule bundle forms the initial agreed test set?
- Which D4.1 demo scenario is the authoritative acceptance script?

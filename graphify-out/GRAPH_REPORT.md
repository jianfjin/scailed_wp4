# Graph Report - .  (2026-05-18)

## Corpus Check
- 118 files · ~61,751 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 626 nodes · 748 edges · 45 communities (30 shown, 15 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 138 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Schema Properties|Schema Properties]]
- [[_COMMUNITY_JSON Schema Types|JSON Schema Types]]
- [[_COMMUNITY_AGE Graph Backend|AGE Graph Backend]]
- [[_COMMUNITY_Demo Data Questionnaires|Demo Data Questionnaires]]
- [[_COMMUNITY_Rule Schema JSON|Rule Schema JSON]]
- [[_COMMUNITY_Compliance Imports|Compliance Imports]]
- [[_COMMUNITY_Docker E2E Output|Docker E2E Output]]
- [[_COMMUNITY_Demo E2E Output|Demo E2E Output]]
- [[_COMMUNITY_Contract Schema Fields|Contract Schema Fields]]
- [[_COMMUNITY_Pathfinding Exceptions|Pathfinding Exceptions]]
- [[_COMMUNITY_FastAPI Endpoints|FastAPI Endpoints]]
- [[_COMMUNITY_Council Architecture Audit|Council Architecture Audit]]
- [[_COMMUNITY_API Architecture Choices|API Architecture Choices]]
- [[_COMMUNITY_TypeScript Config|TypeScript Config]]
- [[_COMMUNITY_Frontend Package|Frontend Package]]
- [[_COMMUNITY_Merged Pathfinder Docs|Merged Pathfinder Docs]]
- [[_COMMUNITY_Core Code Modules|Core Code Modules]]
- [[_COMMUNITY_Council Rationale|Council Rationale]]
- [[_COMMUNITY_Service Test Surface|Service Test Surface]]
- [[_COMMUNITY_Audit Log Core|Audit Log Core]]
- [[_COMMUNITY_Demo CLI|Demo CLI]]
- [[_COMMUNITY_Council Personas|Council Personas]]
- [[_COMMUNITY_Deployment Stack|Deployment Stack]]
- [[_COMMUNITY_Backend API Design|Backend API Design]]
- [[_COMMUNITY_EPIDATA Product Role|EPIDATA Product Role]]
- [[_COMMUNITY_OpenSpec Skills|OpenSpec Skills]]
- [[_COMMUNITY_React SPA|React SPA]]
- [[_COMMUNITY_API Tests|API Tests]]
- [[_COMMUNITY_API Package|API Package]]
- [[_COMMUNITY_Rule Pipeline|Rule Pipeline]]
- [[_COMMUNITY_Partner Dependencies|Partner Dependencies]]
- [[_COMMUNITY_Rule Validation|Rule Validation]]
- [[_COMMUNITY_Core Package|Core Package]]
- [[_COMMUNITY_Sample Data Strategy|Sample Data Strategy]]
- [[_COMMUNITY_Adapters Package|Adapters Package]]
- [[_COMMUNITY_Rules Package|Rules Package]]
- [[_COMMUNITY_Pathfinder Package|Pathfinder Package]]
- [[_COMMUNITY_Services Package|Services Package]]
- [[_COMMUNITY_Demo Test Link|Demo Test Link]]
- [[_COMMUNITY_IP Boundary|IP Boundary]]
- [[_COMMUNITY_Repo Strategy|Repo Strategy]]
- [[_COMMUNITY_OpenSpec Project|OpenSpec Project]]
- [[_COMMUNITY_Exception Types|Exception Types]]
- [[_COMMUNITY_Services Namespace|Services Namespace]]

## God Nodes (most connected - your core abstractions)
1. `AssessmentService` - 22 edges
2. `AgeRoadmapGraph` - 21 edges
3. `compilerOptions` - 16 edges
4. `InMemoryRoadmapGraph` - 15 edges
5. `QuestionnaireEngine` - 15 edges
6. `_get_service()` - 14 edges
7. `RuleLoader` - 14 edges
8. `PathfinderSolver` - 11 edges
9. `ComplianceEvaluator` - 11 edges
10. `require_demo_token()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Uvicorn Dependency` --implements--> `Uvicorn API Main Shim`  [INFERRED]
  requirements.txt → api/main.py
- `Pathfinder Architecture Diagrams` --semantically_similar_to--> `Docker Compose Deployment Topology`  [INFERRED] [semantically similar]
  docs/05_pathfinder_diagrams.md → deploy/docker-compose.yml
- `React Pathfinder SPA` --implements--> `Merged Pathfinder V1 Product Spec`  [INFERRED]
  frontend/src/main.tsx → docs/12_merged_pathfinder_spec.md
- `OpenSpec Merged Pathfinder Design` --semantically_similar_to--> `Merged Pathfinder V1 Technical Design`  [INFERRED] [semantically similar]
  openspec/changes/add-merged-pathfinder-v1/design.md → docs/13_merged_pathfinder_design.md
- `OpenSpec Merged Pathfinder Tasks` --semantically_similar_to--> `Merged Pathfinder V1 Execution Plan`  [INFERRED] [semantically similar]
  openspec/changes/add-merged-pathfinder-v1/tasks.md → docs/14_merged_pathfinder_plan.md

## Hyperedges (group relationships)
- **Pathfinder Upstream Data Contract** — scailed_epidata_pathfinder_architecture_diagrams_wp2_stakeholder_forum, scailed_epidata_pathfinder_architecture_diagrams_wp3_strategic_roadmap, scailed_epidata_pathfinder_architecture_diagrams_wp8_regulatory_ethics [EXTRACTED 1.00]
- **Deterministic Pathfinder Core** — 00_council_resolution_csp_graph_search, 04_dijkstra_cso_formal_model, 01_musk_cvo_state_transition_function [INFERRED 0.85]
- **V1 Delivery Architecture** — 07_linus_arch_monolith_architecture, 08_xiaolong_eng_mvp_scope, 00_council_resolution_pg_age_architecture [INFERRED 0.85]
- **Pathfinder Core Architecture** — council_20260513_pathfinder_system_v1, council_20260513_constrained_graph_search, council_20260513_postgresql_age_graph_engine, council_20260513_fastapi_backend, council_20260513_questionnaire_wizard [EXTRACTED 1.00]
- **Upstream Schema Freeze Dependencies** — council_20260513_wp2_stakeholder_schema, council_20260513_wp3_roadmap_dag, council_20260513_wp8_compliance_rules, council_20260513_m3_schema_baseline [EXTRACTED 1.00]
- **Six-Seat Audit Corrections** — council_20260513_wp3_plan_b_extraction_layer, council_20260513_postgresql_age_graph_engine, council_20260513_audit_log_trigger_hash, council_20260513_payment_split_advance_clause, council_20260513_recommendation_rules_tree [EXTRACTED 1.00]
- **Council Persona Review System** — profiles_guido_cla, profiles_jensen_cio, profiles_linus_arch, profiles_musk_cvo, profiles_steve_cpo, profiles_xiaolong_eng, profiles_xuefeng_csa [EXTRACTED 1.00]
- **Deployment Stack** — deploy_docker_topology, deploy_traefik_frontend_api, deploy_postgres_age, deploy_pg_schema [EXTRACTED 1.00]
- **Partner Dependency Model** — docs_project_dependencies, docs_partner_support, docs_partner_data, docs_without_support [EXTRACTED 1.00]
- **Merged Pathfinder Artifact Set** — docs_merged_spec, docs_merged_design, docs_merged_plan, docs_d41_demo_script, docs_d41_technical_appendix [EXTRACTED 1.00]
- **WP Schema Contracts** — contracts_wp2_taxonomy, contracts_wp3_roadmap, contracts_wp8_rules [EXTRACTED 1.00]
- **OpenSpec Change Package** — openspec_add_merged_pathfinder, openspec_design, openspec_tasks, openspec_project [EXTRACTED 1.00]
- **Core Assessment Engine** — code_questionnaire_engine, code_models, code_solver, code_compliance_evaluator, code_inmemory_graph, code_recommendation [EXTRACTED 1.00]
- **Rule Pipeline** — code_rule_parser, code_rule_compiler, code_rule_loader, code_compliance_evaluator [INFERRED 0.84]
- **API and Demo Surface** — code_api_main, code_demo_run_demo, code_demo_data, code_audit_log [INFERRED 0.78]
- **AssessmentService creates sessions, builds stakeholder state from answers, solves rules against the graph, builds recommendations, exports reports, and records audit events.** — pathfinder.services.assessment_service.AssessmentService, pathfinder.core.questionnaire.QuestionnaireEngine, pathfinder.core.rules.loader.RuleLoader, pathfinder.core.solver.PathfinderSolver, pathfinder.core.recommend.build_recommendation, pathfinder.core.audit.AuditLog [EXTRACTED 1.00]
- **Rule bundles are constrained by schema-level required fields and runtime validator checks, with RuleLoader behavior covered by paired-test unit tests.** — pathfinder.core.rules.schema, pathfinder.core.rules.validator.validate_rule_bundle, pathfinder.core.rules.validator.RuleValidationError, pathfinder.core.rules.loader.RuleLoader, tests.test_pathfinder_core.PathfinderCoreTests [INFERRED 0.75]
- **Tests cover API authentication and assessment flow, demo CLI report generation, AGE graph parity, and core end-to-end traceability.** — tests.test_api.ApiTests, tests.test_demo_cli.DemoCliTests, tests.test_graph_age.AgeGraphParityTests, tests.test_pathfinder_core.PathfinderCoreTests, pathfinder.services.assessment_service.AssessmentService, pathfinder.core.graph_age.AgeRoadmapGraph [EXTRACTED 1.00]

## Communities (45 total, 15 thin omitted)

### Community 0 - "Schema Properties"
Cohesion: 0.05
Nodes (46): type, type, type, items, type, type, properties, required (+38 more)

### Community 1 - "JSON Schema Types"
Cohesion: 0.05
Nodes (45): type, items, type, items, type, type, type, type (+37 more)

### Community 2 - "AGE Graph Backend"
Cohesion: 0.06
Nodes (20): AgeRoadmapGraph, _agtype_to_float(), _agtype_to_int(), _agtype_to_text(), create_graph_backend(), PostgreSQL Apache AGE graph backend for Pathfinder V1.  Provides the same interf, PostgreSQL Apache AGE graph backend.      Implements the same interface as InMem, Create connection pool and initialise AGE graph.          Each pool connection s (+12 more)

### Community 3 - "Demo Data Questionnaires"
Cohesion: 0.07
Nodes (14): demo_questionnaires(), demo_roadmap(), demo_rule_bundle(), Realistic demo inputs used until WP2/WP3/WP8 structured data lands., QuestionnaireEngine, Questionnaire validation and stakeholder-state conversion., build_recommendation(), Recommendation assembly. (+6 more)

### Community 4 - "Rule Schema JSON"
Cohesion: 0.05
Nodes (41): type, items, type, items, type, type, items, type (+33 more)

### Community 5 - "Compliance Imports"
Cohesion: 0.07
Nodes (19): ComplianceEvaluator, Deterministic rule condition evaluation., import_structured_payload(), Structured data import helpers., ImportReport, PathResult, Question, Questionnaire (+11 more)

### Community 6 - "Docker E2E Output"
Cohesion: 0.05
Nodes (39): assessment_id, commit, docker_fix_applied, docker_port_mapping, e2e_status, host, notes, pipeline (+31 more)

### Community 7 - "Demo E2E Output"
Cohesion: 0.05
Nodes (37): assessment_id, audit_chain_valid, compliance, data, governance, meta, age_version, commit (+29 more)

### Community 8 - "Contract Schema Fields"
Cohesion: 0.08
Nodes (26): items, type, type, properties, required, type, type, items (+18 more)

### Community 9 - "Pathfinding Exceptions"
Cohesion: 0.11
Nodes (18): BFS fallback — same algorithm as InMemoryRoadmapGraph.          In production th, Exception, NoFeasiblePathError, PathfinderError, Pathfinder exception hierarchy., Rule bundle failed validation., No roadmap path can satisfy current constraints., No questionnaire exists for the stakeholder type. (+10 more)

### Community 10 - "FastAPI Endpoints"
Cohesion: 0.21
Nodes (19): create_assessment(), get_assessment(), _get_service(), health(), import_wp2(), import_wp3(), import_wp8(), lifespan() (+11 more)

### Community 11 - "Council Architecture Audit"
Cohesion: 0.1
Nodes (21): Trigger-Based Hash-Chained Audit Log, Constrained Graph Search, D4.1 Pathfinder V1 Demo, Deterministic Auditable Decision Support, Dijkstra CSO Formal Correctness Persona, DisconnectedGraphError, Interactive Prototype and Demo Evidence, Graceful Degradation Strategy (+13 more)

### Community 12 - "API Architecture Choices"
Cohesion: 0.14
Nodes (18): PostgreSQL AGE Architecture Decision, REST API Design, Monolithic Pathfinder Architecture, MVP Scope Reduction, Compatibility Package, pathfinder.api.main app, Uvicorn API Main Shim, Frontend Technology Choice (+10 more)

### Community 13 - "TypeScript Config"
Cohesion: 0.11
Nodes (17): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+9 more)

### Community 14 - "Frontend Package"
Cohesion: 0.12
Nodes (15): dependencies, react, react-dom, typescript, vite, @vitejs/plugin-react, devDependencies, name (+7 more)

### Community 15 - "Merged Pathfinder Docs"
Cohesion: 0.14
Nodes (16): WP2 Stakeholder Taxonomy Contract, WP3 Roadmap Contract, WP8 Rules Contract, D4.1 Pathfinder Demo Script, D4.1 Technical Appendix, Merged Pathfinder V1 Technical Design, Merged Pathfinder V1 Execution Plan, Merged Pathfinder V1 Product Spec (+8 more)

### Community 16 - "Core Code Modules"
Cohesion: 0.15
Nodes (15): AgeRoadmapGraph, Pathfinder FastAPI Main, AuditLog, ComplianceEvaluator, Demo Data Fixtures, run_demo, Structured Payload Import, InMemoryRoadmapGraph (+7 more)

### Community 17 - "Council Rationale"
Cohesion: 0.19
Nodes (14): CSP Graph Search Pathfinder Definition, Pathfinder as State Transition Function, Project Risk Audit, Formal Pathfinder Model, Infrastructure and Compute Plan, Pathfinder Product Experience, Pathfinder System, Schema Baseline Confirmation (+6 more)

### Community 18 - "Service Test Surface"
Cohesion: 0.2
Nodes (12): FastAPI app, AuditLog, InMemoryRoadmapGraph, AgeRoadmapGraph, QuestionnaireEngine, build_recommendation, RuleLoader, PathfinderSolver (+4 more)

### Community 19 - "Audit Log Core"
Cohesion: 0.24
Nodes (3): AuditEvent, AuditLog, Append-only in-memory audit chain for V1 demo mode.

### Community 20 - "Demo CLI"
Cohesion: 0.32
Nodes (5): async_main(), main(), CLI demo for the Pathfinder V1 deterministic kernel.  Supports AGE backend via U, run_demo(), DemoCliTests

### Community 21 - "Council Personas"
Cohesion: 0.25
Nodes (8): Council Persona Profiles, Guido CLA API Design Persona, Jensen CIO Infrastructure Persona, Linus Architecture Persona, Musk CVO Product Vision Persona, Steve Jobs CPO Product Persona, Xiaolong Engineering Persona, Xuefeng CSA Contract Strategy Persona

### Community 22 - "Deployment Stack"
Cohesion: 0.4
Nodes (5): Docker Compose Deployment Topology, PostgreSQL Pathfinder Schema, PostgreSQL AGE Deployment, Traefik Frontend API Deployment, Pathfinder Architecture Diagrams

### Community 23 - "Backend API Design"
Cohesion: 0.5
Nodes (4): FastAPI Backend, Pathfinder API Endpoints, Questionnaire Wizard Interface, ThreadPoolExecutor Solver Wrapper

### Community 24 - "EPIDATA Product Role"
Cohesion: 0.5
Nodes (4): EHDS HDAB Relationship, EPIDATA Pathfinder Responsibilities, Pathfinder Platform Product Modules, DataWego Ontology Patterns

### Community 25 - "OpenSpec Skills"
Cohesion: 0.5
Nodes (4): OpenSpec Apply Change Workflow, OpenSpec Archive Change Workflow, OpenSpec Explore Mode, OpenSpec Propose Workflow

### Community 29 - "Rule Pipeline"
Cohesion: 0.67
Nodes (3): Rule Compiler, RuleLoader, Rule Bundle Parser

### Community 30 - "Partner Dependencies"
Cohesion: 0.67
Nodes (3): Partner Data Inputs, Partner Support Inputs, WP Dependencies for EPIDATA

### Community 31 - "Rule Validation"
Cohesion: 0.67
Nodes (3): Pathfinder V1 Rule Bundle Schema, RuleValidationError, validate_rule_bundle

## Knowledge Gaps
- **232 isolated node(s):** `audit_chain_valid`, `assessment_id`, `schema_version`, `stakeholder_type`, `target_scenario` (+227 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AssessmentService` connect `Demo Data Questionnaires` to `AGE Graph Backend`, `Compliance Imports`, `FastAPI Endpoints`, `Audit Log Core`, `Demo CLI`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `AgeRoadmapGraph` connect `AGE Graph Backend` to `Pathfinding Exceptions`, `Demo Data Questionnaires`, `Compliance Imports`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `_get_service()` connect `FastAPI Endpoints` to `Demo Data Questionnaires`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `AssessmentService` (e.g. with `AuditLog` and `InMemoryRoadmapGraph`) actually correct?**
  _`AssessmentService` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `AgeRoadmapGraph` (e.g. with `AssessmentService` and `RoadmapEdge`) actually correct?**
  _`AgeRoadmapGraph` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `audit_chain_valid`, `assessment_id`, `schema_version` to the rest of the system?**
  _273 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Schema Properties` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
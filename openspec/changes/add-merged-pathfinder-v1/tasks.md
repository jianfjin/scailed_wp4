## 1. Alignment and Baseline
- [ ] 1.1 Confirm V1 scope, non-goals, stakeholder types, and D4.1 demo scenario with Epidata/Charite.
- [x] 1.2 Define WP2 stakeholder taxonomy, WP3 roadmap, and WP8 rule input contracts. (test: test_api.ApiTests.test_admin_imports_activate_wp2_wp3_and_wp8_payloads)
- [x] 1.3 Define schema versions, sample inputs, rule DSL, and paired rule test format. (test: test_pathfinder_core.PathfinderCoreTests.test_rule_loader_runs_paired_tests)
- [x] 1.4 Create mock-data package, `IP_BOUNDARY.md`, repo skeleton, and Docker Compose skeleton. (test: test_demo_cli.DemoCliTests.test_run_demo_returns_report)
- [ ] 1.5 Verify one sample import, one questionnaire, one assessment session, one hard-coded traceable recommendation, and local Docker Compose boot.

## 2. Core Engine
- [x] 2.1 Implement domain models for stakeholder state, roadmap nodes/edges, rules, path results, recommendations, snapshots, and audit events. (test: test_pathfinder_core.PathfinderCoreTests.test_end_to_end_report_has_traceability_and_audit)
- [ ] 2.2 Implement database migrations, PostgreSQL AGE graph storage, and NetworkX test fallback.
- [x] 2.3 Implement questionnaire engine and stakeholder-state conversion. (test: test_pathfinder_core.PathfinderCoreTests.test_questionnaire_validates_numeric_bounds)
- [x] 2.4 Implement rule parser, schema validation, compiler, conflict checks, loader, and `.test.yaml` runner. (test: test_pathfinder_core.PathfinderCoreTests.test_rule_loader_rejects_failed_tests)
- [x] 2.5 Implement path solver, compliance evaluator, recommendation ranking, confidence calculation, and graceful degradation. (test: test_pathfinder_core.PathfinderCoreTests.test_end_to_end_report_has_traceability_and_audit)
- [x] 2.6 Implement append-only audit log with previous-hash chain and upstream data snapshots. (test: test_pathfinder_core.PathfinderCoreTests.test_failed_import_is_audited_and_keeps_chain_valid)
- [x] 2.7 Verify core tests, rule tests, graph traversal, audit chain integrity, and p95 recommendation latency at demo scale. (test: test_acceptance_baseline.AcceptanceBaselineTests.test_recommendation_p95_under_demo_threshold)

## 3. API and Frontend MVP
- [x] 3.1 Implement health, questionnaire, assessment, roadmap, recommendation, report, and admin import/reload REST endpoints. (test: test_api.ApiTests.test_assessment_flow_api)
- [x] 3.2 Implement API schemas, safe error model, invited access, admin bearer-token protection, and rate limiting. (test: test_api.ApiTests.test_api_hardening_covers_admin_protection_and_rate_limit)
- [x] 3.3 Implement guided assessment frontend, stakeholder selection, readiness summary, roadmap path view, trace view, report export view, and admin import/status view. (test: test_acceptance_baseline.AcceptanceBaselineTests.test_report_export_contains_acceptance_evidence)
- [x] 3.4 Add demo-data mode banner and missing/unverified data warnings. (test: test_demo_cli.DemoCliTests.test_run_demo_returns_report)
- [x] 3.5 Verify end-to-end questionnaire completion, traceable recommendation generation, report export, rule reload safety, and p95 latency target. (test: test_acceptance_baseline.AcceptanceBaselineTests.test_three_stakeholder_paths_are_ready_and_traceable)

## 4. D4.1 Hardening
- [x] 4.1 Polish main user flow, report wording, explicit warnings, and reviewer-facing errors. (test: test_acceptance_baseline.AcceptanceBaselineTests.test_report_export_contains_acceptance_evidence)
- [x] 4.2 Add deployment docs, seed/demo data, demo script, and D4.1 technical appendix. (test: test_demo_cli.DemoCliTests.test_run_demo_returns_report)
- [ ] 4.3 Run stakeholder review sessions and apply only in-scope refinements.
- [ ] 4.4 Verify clean install from docs, demo script completion without manual database edits, audit-log integrity, and acceptance criteria from `docs/12_merged_pathfinder_spec.md`.

## 5. Validation Support and V2 Scoping
- [ ] 5.1 Support Charite-led validation for T4.2 without expanding V1 scope.
- [ ] 5.2 Classify feedback as bug, calibration, upstream data issue, or V2 request.
- [ ] 5.3 Fix V1 defects, regression-test changes, and preserve traceability.
- [ ] 5.4 Defer AI copilot, GraphRAG, production auth, real integrations, advanced dashboards, multi-tenant operations, Kubernetes, richer ontology, and multilingual UX to separate V2 scope.

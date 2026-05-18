---
type: "query"
date: "2026-05-18T05:55:07.630652+00:00"
question: "Why does AssessmentService connect Demo Data Questionnaires to AGE Graph Backend, Compliance Imports, FastAPI Endpoints, Audit Log Core, Demo CLI?"
contributor: "graphify"
source_nodes: ["AssessmentService", "demo_questionnaires", "AgeRoadmapGraph", "import_structured_payload", "_get_service", "AuditLog", "run_demo", "ComplianceEvaluator"]
---

# Q: Why does AssessmentService connect Demo Data Questionnaires to AGE Graph Backend, Compliance Imports, FastAPI Endpoints, Audit Log Core, Demo CLI?

## Answer

AssessmentService is the orchestration hub in the graph. Its constructor links to demo_questionnaires, demo_roadmap, demo_rule_bundle, QuestionnaireEngine, RuleLoader, PathfinderSolver, AuditLog, AgeRoadmapGraph/InMemoryRoadmapGraph, and import_structured_payload. FastAPI reaches it through _get_service in pathfinder/api/main.py; Demo CLI reaches it through async_main/run_demo in pathfinder/demo.py. Compliance connects indirectly through PathfinderSolver to ComplianceEvaluator. Most of these implementation-level links are inferred by AST/semantic extraction except the class/method containment and some method calls, so they should be treated as graph guidance, not proof, until checked against code.

## Source Nodes

- AssessmentService
- demo_questionnaires
- AgeRoadmapGraph
- import_structured_payload
- _get_service
- AuditLog
- run_demo
- ComplianceEvaluator
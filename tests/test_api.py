import pytest
import unittest

from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

import pathfinder.api.main as api_main
from pathfinder.api.middleware import AuditWhitelistMiddleware, RateLimitMiddleware
from pathfinder.api.main import app


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        api_main._service = None

    def test_assessment_flow_api(self) -> None:
        client = TestClient(app)
        headers = {"Authorization": "Bearer demo-token"}

        questionnaires = client.get("/v1/questionnaires", headers=headers)
        self.assertEqual(questionnaires.status_code, 200)
        self.assertGreaterEqual(len(questionnaires.json()["stakeholder_types"]), 5)

        session = client.post(
            "/v1/assessments",
            headers=headers,
            json={
                "stakeholder_type": "biotech-sme",
                "target_scenario": "secondary-use-readiness",
            },
        )
        self.assertEqual(session.status_code, 200)
        assessment_id = session.json()["assessment_id"]

        answers = client.post(
            f"/v1/assessments/{assessment_id}/answers/batch",
            headers=headers,
            json={
                "answers": {
                    "governance_maturity": 2,
                    "data_maturity": 2,
                    "compliance_maturity": 2,
                    "capabilities": ["secure-processing"],
                    "missing_capabilities": ["data-catalog"],
                    "regulatory_flags": ["gdpr-review-needed"],
                }
            },
        )
        self.assertEqual(answers.status_code, 200)

        recommendation = client.post(
            f"/v1/assessments/{assessment_id}/recommendations",
            headers=headers,
        )
        self.assertEqual(recommendation.status_code, 200)
        self.assertIn("trace", recommendation.json())

        report = client.get(f"/v1/assessments/{assessment_id}/report", headers=headers)
        self.assertEqual(report.status_code, 200)
        self.assertTrue(report.json()["audit_chain_valid"])

    def test_assessment_flow_requires_invited_token(self) -> None:
        client = TestClient(app)

        response = client.get("/v1/questionnaires")

        self.assertEqual(response.status_code, 401)

    def test_demo_token_cannot_use_admin_imports(self) -> None:
        client = TestClient(app)

        response = client.post(
            "/admin/import/wp2",
            headers={"Authorization": "Bearer demo-token"},
            json={"version": "wp2-test-v1", "stakeholder_types": []},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "FORBIDDEN")

    def test_rate_limit_blocks_repeated_protected_requests_but_not_health(self) -> None:
        async def inner(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        limited_app = RateLimitMiddleware(inner, max_requests=2, window_seconds=60)
        client = TestClient(limited_app)

        self.assertEqual(client.get("/v1/questionnaires").status_code, 200)
        self.assertEqual(client.get("/v1/questionnaires").status_code, 200)
        limited = client.get("/v1/questionnaires")
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["detail"]["error"], "RATE_LIMITED")
        self.assertEqual(client.get("/health").status_code, 200)

    def test_audit_whitelist_warns_when_mutation_records_no_audit_event(self) -> None:
        async def inner(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        class AuditLog:
            def events(self):
                return ()

        class Service:
            audit_log = AuditLog()

        checked_app = AuditWhitelistMiddleware(inner, get_service=lambda: Service())
        client = TestClient(checked_app)

        with self.assertLogs("pathfinder.middleware", level="WARNING") as logs:
            response = client.post("/v1/mutating")

        self.assertEqual(response.status_code, 200)
        self.assertIn("produced 0 audit events", "\n".join(logs.output))

    def test_api_hardening_covers_admin_protection_and_rate_limit(self) -> None:
        self.test_demo_token_cannot_use_admin_imports()
        self.test_rate_limit_blocks_repeated_protected_requests_but_not_health()

    def test_admin_imports_activate_wp2_wp3_and_wp8_payloads(self) -> None:
        client = TestClient(app)
        admin_headers = {"Authorization": "Bearer admin-token"}
        demo_headers = {"Authorization": "Bearer demo-token"}

        wp2 = {
            "version": "wp2-test-v1",
            "stakeholder_types": [
                {
                    "id": "demo-reviewer",
                    "label": "Demo reviewer",
                    "personas": ["technical reviewer"],
                    "user_journeys": ["review D4.1 evidence"],
                    "feedback_categories": ["acceptance"],
                }
            ],
        }
        wp2_response = client.post("/admin/import/wp2", headers=admin_headers, json=wp2)
        self.assertEqual(wp2_response.status_code, 200)
        self.assertTrue(wp2_response.json()["accepted"])
        self.assertEqual(wp2_response.json()["source"], "wp2")
        self.assertIn("checksum", wp2_response.json())

        questionnaires = client.get("/v1/questionnaires", headers=demo_headers)
        self.assertEqual(questionnaires.status_code, 200)
        self.assertEqual(questionnaires.json()["stakeholder_types"], ["demo-reviewer"])

        wp3 = {
            "version": "wp3-test-v1",
            "nodes": [
                {
                    "node_id": "review-intake",
                    "label": "Review intake",
                    "description": "Reviewer intake node",
                    "dimension": "governance",
                    "maturity_level": 1,
                    "stakeholder_types": ["demo-reviewer", "all"],
                    "prerequisites": [],
                    "source_doc_ref": "wp3-test",
                },
                {
                    "node_id": "review-complete",
                    "label": "Review complete",
                    "description": "Reviewer completion node",
                    "dimension": "governance",
                    "maturity_level": 3,
                    "stakeholder_types": ["demo-reviewer", "all"],
                    "prerequisites": ["review-intake"],
                    "source_doc_ref": "wp3-test",
                },
            ],
            "edges": [
                {
                    "edge_id": "review-e1",
                    "from_node_id": "review-intake",
                    "to_node_id": "review-complete",
                    "relation_type": "prerequisite",
                    "required": True,
                    "source_doc_ref": "wp3-test",
                }
            ],
        }
        wp3_response = client.post("/admin/import/wp3", headers=admin_headers, json=wp3)
        self.assertEqual(wp3_response.status_code, 200)
        self.assertTrue(wp3_response.json()["accepted"])

        roadmap = client.get("/v1/roadmap", headers=demo_headers)
        self.assertEqual(roadmap.status_code, 200)
        self.assertEqual(
            {node["node_id"] for node in roadmap.json()["nodes"]},
            {"review-intake", "review-complete"},
        )

        wp8 = {
            "version": "wp8-test-v1",
            "rules": [
                {
                    "rule_id": "REVIEWER-TRACE-001",
                    "rule_type": "preference",
                    "priority": 10,
                    "applies_to": ["demo-reviewer"],
                    "condition": {"field": "stakeholder_type", "operator": "eq", "value": "demo-reviewer"},
                    "action": {
                        "title": "Trace review evidence",
                        "text": "Review trace evidence before acceptance.",
                        "node_id": "review-complete",
                    },
                    "compliance_refs": ["D4.1"],
                }
            ],
            "tests": [
                {
                    "name": "demo reviewer trace rule",
                    "state": {
                        "stakeholder_type": "demo-reviewer",
                        "target_scenario": "secondary-use-readiness",
                        "answers": {
                            "governance_maturity": 1,
                            "data_maturity": 1,
                            "compliance_maturity": 1,
                            "capabilities": [],
                            "missing_capabilities": [],
                            "regulatory_flags": [],
                        },
                    },
                    "expected_rule_ids": ["REVIEWER-TRACE-001"],
                }
            ],
        }
        wp8_response = client.post("/admin/import/wp8", headers=admin_headers, json=wp8)
        self.assertEqual(wp8_response.status_code, 200)
        self.assertTrue(wp8_response.json()["accepted"])

        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["rule_version"], "wp8-test-v1")
        self.assertIn("wp2", health.json()["import_reports"])
        self.assertIn("wp3", health.json()["import_reports"])
        self.assertIn("wp8", health.json()["import_reports"])

    def test_invalid_admin_import_is_rejected_without_replacing_active_data(self) -> None:
        client = TestClient(app)
        admin_headers = {"Authorization": "Bearer admin-token"}
        demo_headers = {"Authorization": "Bearer demo-token"}

        before = client.get("/v1/roadmap", headers=demo_headers)
        self.assertEqual(before.status_code, 200)
        before_nodes = {node["node_id"] for node in before.json()["nodes"]}

        invalid = {"version": "broken", "nodes": [], "edges": []}
        response = client.post("/admin/import/wp3", headers=admin_headers, json=invalid)

        self.assertEqual(response.status_code, 400)
        after = client.get("/v1/roadmap", headers=demo_headers)
        self.assertEqual(after.status_code, 200)
        self.assertEqual({node["node_id"] for node in after.json()["nodes"]}, before_nodes)

        health = client.get("/health")
        self.assertGreaterEqual(health.json()["audit_events"], 1)

    # ── G7: WP2 import error tests (Guido MEDIUM #7) ─────────────────────────

    def test_import_wp2_rejects_duplicate_ids_via_api(self) -> None:
        """POST /admin/import/wp2 with duplicate stakeholder IDs must return 400."""
        client = TestClient(app)
        admin_headers = {"Authorization": "Bearer admin-token"}

        response = client.post("/admin/import/wp2", headers=admin_headers, json={
            "version": "test-v1",
            "stakeholder_types": [
                {"id": "dup-test", "label": "First",
                 "personas": ["researcher"], "user_journeys": ["test"],
                 "feedback_categories": ["acceptance"]},
                {"id": "dup-test", "label": "Second",
                 "personas": ["researcher"], "user_journeys": ["test"],
                 "feedback_categories": ["acceptance"]},
            ],
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "VALIDATION_ERROR")

    def test_import_wp2_rejects_empty_stakeholder_types_via_api(self) -> None:
        """POST /admin/import/wp2 with empty stakeholder_types must return 400."""
        client = TestClient(app)
        admin_headers = {"Authorization": "Bearer admin-token"}

        response = client.post("/admin/import/wp2", headers=admin_headers, json={
            "version": "test-v1",
            "stakeholder_types": [],
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "VALIDATION_ERROR")

    def test_import_wp2_rejects_missing_version_via_api(self) -> None:
        """POST /admin/import/wp2 without version field must return 400."""
        client = TestClient(app)
        admin_headers = {"Authorization": "Bearer admin-token"}

        response = client.post("/admin/import/wp2", headers=admin_headers, json={
            "stakeholder_types": [{
                "id": "biotech-sme", "label": "Biotech SME",
                "personas": ["researcher"], "user_journeys": ["test"],
                "feedback_categories": ["acceptance"],
            }],
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "VALIDATION_ERROR")

    def test_api_request_metadata_is_hashed_in_audit_events(self) -> None:
        client = TestClient(app)
        headers = {
            "Authorization": "Bearer demo-token",
            "User-Agent": "pathfinder-test-agent",
            "X-Forwarded-For": "203.0.113.10",
        }

        response = client.post(
            "/v1/assessments",
            headers=headers,
            json={
                "stakeholder_type": "biotech-sme",
                "target_scenario": "secondary-use-readiness",
            },
        )

        self.assertEqual(response.status_code, 200)
        event = api_main._get_service().audit_log.events()[-1]
        self.assertEqual(event.event_type, "assessment_session_created")
        self.assertIsNotNone(event.ip_hash)
        self.assertIsNotNone(event.user_agent_hash)
        self.assertNotEqual(event.ip_hash, "203.0.113.10")
        self.assertNotEqual(event.user_agent_hash, "pathfinder-test-agent")
        self.assertNotIn("203.0.113.10", str(event.to_dict()))
        self.assertNotIn("pathfinder-test-agent", str(event.to_dict()))


if __name__ == "__main__":
    unittest.main()

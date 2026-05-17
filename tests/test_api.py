import unittest

from fastapi.testclient import TestClient

from pathfinder.api.main import app


class ApiTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

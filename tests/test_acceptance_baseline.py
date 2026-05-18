import statistics
import time
import unittest

from pathfinder.services.assessment_service import AssessmentService


BASE_ANSWERS = {
    "governance_maturity": 2,
    "data_maturity": 2,
    "compliance_maturity": 2,
    "capabilities": ["secure-processing"],
    "missing_capabilities": ["data-catalog"],
    "regulatory_flags": ["gdpr-review-needed"],
}


class AcceptanceBaselineTests(unittest.TestCase):
    def test_all_demo_stakeholders_have_complete_questionnaires(self) -> None:
        service = AssessmentService()

        self.assertGreaterEqual(len(service.stakeholder_types()), 5)
        for stakeholder_type in service.stakeholder_types():
            questionnaire = service.get_questionnaire(stakeholder_type)
            self.assertGreaterEqual(len(questionnaire["questions"]), 1)
            self.assertTrue(questionnaire["target_scenarios"])

    def test_three_stakeholder_paths_are_ready_and_traceable(self) -> None:
        for stakeholder_type in ("biotech-sme", "health-data-access-body", "research-infrastructure"):
            with self.subTest(stakeholder_type=stakeholder_type):
                service = AssessmentService()
                session = service.create_session(stakeholder_type, "secondary-use-readiness")
                assessment_id = str(session["assessment_id"])
                service.submit_answers(assessment_id, BASE_ANSWERS)
                recommendation = service.generate_recommendation(assessment_id)

                self.assertEqual(recommendation["status"], "ready")
                self.assertTrue(recommendation["trace"]["answer_ids"])
                self.assertTrue(recommendation["trace"]["roadmap_node_ids"])
                self.assertTrue(recommendation["trace"]["triggered_rule_ids"])

    def test_report_export_contains_acceptance_evidence(self) -> None:
        service = AssessmentService()
        session = service.create_session("biotech-sme", "secondary-use-readiness")
        assessment_id = str(session["assessment_id"])
        service.submit_answers(assessment_id, BASE_ANSWERS)
        service.generate_recommendation(assessment_id)
        report = service.report(assessment_id)

        self.assertIn("readiness_snapshot", report)
        self.assertIn("recommended_path", report)
        self.assertIn("blockers", report["recommended_path"])
        self.assertIn("trace", report["recommended_path"])
        self.assertTrue(report["missing_data_warnings"])
        self.assertIn("Demo/non-production", report["disclaimer"])

    def test_recommendation_p95_under_demo_threshold(self) -> None:
        durations: list[float] = []
        for _ in range(20):
            service = AssessmentService()
            session = service.create_session("biotech-sme", "secondary-use-readiness")
            assessment_id = str(session["assessment_id"])
            service.submit_answers(assessment_id, BASE_ANSWERS)
            start = time.perf_counter()
            service.generate_recommendation(assessment_id)
            durations.append(time.perf_counter() - start)

        p95 = statistics.quantiles(durations, n=20)[18]
        self.assertLess(p95, 0.25)


if __name__ == "__main__":
    unittest.main()

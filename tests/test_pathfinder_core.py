import unittest

from pathfinder.adapters.demo_data import STAKEHOLDER_TYPES, demo_questionnaires, demo_rule_bundle
from pathfinder.core.exceptions import RuleValidationError, ValidationError
from pathfinder.core.questionnaire import QuestionnaireEngine
from pathfinder.core.rules.loader import RuleLoader
from pathfinder.services.assessment_service import AssessmentService


class PathfinderCoreTests(unittest.TestCase):
    def test_demo_supports_five_stakeholder_types(self) -> None:
        service = AssessmentService()

        self.assertGreaterEqual(len(service.stakeholder_types()), 5)
        self.assertEqual(sorted(STAKEHOLDER_TYPES), service.stakeholder_types())

    def test_questionnaire_validates_numeric_bounds(self) -> None:
        engine = QuestionnaireEngine(demo_questionnaires())

        with self.assertRaises(ValidationError):
            engine.build_state(
                "biotech-sme",
                "secondary-use-readiness",
                {
                    "governance_maturity": 7,
                    "data_maturity": 2,
                    "compliance_maturity": 2,
                    "capabilities": [],
                    "missing_capabilities": [],
                },
            )

    def test_rule_loader_runs_paired_tests(self) -> None:
        loader = RuleLoader(demo_questionnaires())
        rules = loader.load_bundle(demo_rule_bundle())

        self.assertEqual(loader.active_version, "demo-rules-v1")
        self.assertEqual({rule.rule_id for rule in rules}, {
            "WP8-GDPR-REVIEW-001",
            "WP8-UNVERIFIED-002",
            "DATA-CATALOG-GAP-003",
        })

    def test_rule_loader_rejects_failed_tests(self) -> None:
        bundle = demo_rule_bundle()
        bundle["tests"] = [
            {
                "name": "wrong expected rule",
                "state": {
                    "stakeholder_type": "biotech-sme",
                    "target_scenario": "secondary-use-readiness",
                    "answers": {
                        "governance_maturity": 2,
                        "data_maturity": 2,
                        "compliance_maturity": 2,
                        "capabilities": ["secure-processing"],
                        "missing_capabilities": ["data-catalog"],
                        "regulatory_flags": ["gdpr-review-needed"],
                    },
                },
                "expected_rule_ids": ["WP8-GDPR-REVIEW-001"],
            }
        ]

        with self.assertRaises(RuleValidationError):
            RuleLoader(demo_questionnaires()).load_bundle(bundle)

    def test_end_to_end_report_has_traceability_and_audit(self) -> None:
        service = AssessmentService()
        session = service.create_session("biotech-sme", "secondary-use-readiness")
        assessment_id = str(session["assessment_id"])
        service.submit_answers(
            assessment_id,
            {
                "governance_maturity": 2,
                "data_maturity": 2,
                "compliance_maturity": 2,
                "capabilities": ["secure-processing"],
                "missing_capabilities": ["data-catalog"],
                "regulatory_flags": ["gdpr-review-needed"],
            },
        )
        recommendation = service.generate_recommendation(assessment_id)
        report = service.report(assessment_id)

        self.assertEqual(recommendation["status"], "ready")
        self.assertIn("trace", recommendation)
        self.assertIn("WP8-GDPR-REVIEW-001", recommendation["trace"]["triggered_rule_ids"])
        self.assertIn("access-body-review", recommendation["trace"]["roadmap_node_ids"])
        self.assertTrue(report["audit_chain_valid"])
        self.assertIn("Demo/non-production", report["disclaimer"])


if __name__ == "__main__":
    unittest.main()

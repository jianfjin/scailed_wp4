import os
import unittest
from unittest.mock import patch

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
        self.assertEqual(
            [event.event_type for event in service.audit_log.events()],
            [
                "assessment_session_created",
                "answers_submitted",
                "recommendation_generated",
                "report_exported",
            ],
        )

    def test_failed_import_is_audited_and_keeps_chain_valid(self) -> None:
        service = AssessmentService()

        with self.assertRaises(ValueError):
            service.import_wp3({"version": "broken", "nodes": [], "edges": []})

        events = service.audit_log.events()
        self.assertEqual(events[-1].event_type, "data_import_failed")
        self.assertEqual(events[-1].event_data["source"], "wp3")
        self.assertTrue(service.audit_log.verify_chain())

    # ── G5: Regulatory reference verification (Guido MEDIUM #5) ──────────────

    def test_regulatory_refs_propagate_into_trace(self) -> None:
        """Triggered rules must propagate compliance_refs into trace.regulatory_refs.

        When regulatory_flags include "gdpr-review-needed", the WP8-GDPR-REVIEW-001
        rule fires with compliance_refs=["GDPR-Review", "EHDS-Secondary-Use"], and
        DATA-CATALOG-GAP-003 fires with compliance_refs=["WP3-Roadmap"]. These must
        appear in the trace.
        """
        service = AssessmentService()
        session = service.create_session("biotech-sme", "secondary-use-readiness")
        aid = str(session["assessment_id"])
        service.submit_answers(aid, {
            "governance_maturity": 2,
            "data_maturity": 2,
            "compliance_maturity": 2,
            "capabilities": ["secure-processing"],
            "missing_capabilities": ["data-catalog"],
            "regulatory_flags": ["gdpr-review-needed"],
        })
        rec = service.generate_recommendation(aid)
        trace = rec["trace"]
        refs = trace["regulatory_refs"]

        # Must contain compliance refs from triggered rules
        self.assertIn("GDPR-Review", refs,
                      f"GDPR-Review missing from regulatory_refs: {refs}")
        self.assertIn("EHDS-Secondary-Use", refs,
                      f"EHDS-Secondary-Use missing from regulatory_refs: {refs}")
        self.assertIn("WP3-Roadmap", refs,
                      f"WP3-Roadmap missing from regulatory_refs: {refs}")

        # triggered_rule_ids must match
        self.assertIn("WP8-GDPR-REVIEW-001", trace["triggered_rule_ids"])
        self.assertIn("DATA-CATALOG-GAP-003", trace["triggered_rule_ids"])

    def test_regulatory_refs_empty_without_flags(self) -> None:
        """Without regulatory_flags, trace.regulatory_refs should be empty tuple."""
        service = AssessmentService()
        session = service.create_session("biotech-sme", "secondary-use-readiness")
        aid = str(session["assessment_id"])
        service.submit_answers(aid, {
            "governance_maturity": 2,
            "data_maturity": 2,
            "compliance_maturity": 2,
            "capabilities": ["secure-processing"],
            "missing_capabilities": [],
            "regulatory_flags": [],
        })
        rec = service.generate_recommendation(aid)
        trace = rec["trace"]
        refs = trace["regulatory_refs"]
        self.assertEqual(refs, (), f"Expected empty regulatory_refs, got: {refs}")

    # ── G7: Import error tests (Guido MEDIUM #7) ─────────────────────────────

    def test_import_wp2_rejects_empty_stakeholder_types(self) -> None:
        """Empty stakeholder_types list must raise ValueError."""
        service = AssessmentService()
        with self.assertRaises(ValueError) as ctx:
            service.import_wp2({"version": "test-v1", "stakeholder_types": []})
        self.assertIn("must not be empty", str(ctx.exception))

    def test_import_wp2_rejects_duplicate_stakeholder_ids(self) -> None:
        """Duplicate stakeholder IDs must raise ValueError."""
        service = AssessmentService()
        duplicate = {
            "version": "test-v1",
            "stakeholder_types": [
                {"id": "biotech-sme", "label": "Biotech SME",
                 "personas": ["researcher"], "user_journeys": ["test"],
                 "feedback_categories": ["acceptance"]},
                {"id": "biotech-sme", "label": "Biotech SME (dup)",
                 "personas": ["researcher"], "user_journeys": ["test"],
                 "feedback_categories": ["acceptance"]},
            ],
        }
        with self.assertRaises(ValueError) as ctx:
            service.import_wp2(duplicate)
        self.assertIn("duplicate stakeholder type", str(ctx.exception))

    def test_import_wp2_rejects_missing_version(self) -> None:
        """Missing version field must raise ValueError."""
        service = AssessmentService()
        with self.assertRaises(ValueError) as ctx:
            service.import_wp2({"stakeholder_types": [{
                "id": "biotech-sme", "label": "Biotech SME",
                "personas": ["researcher"], "user_journeys": ["test"],
                "feedback_categories": ["acceptance"],
            }]})
        self.assertIn("version", str(ctx.exception).lower())

    def test_import_wp2_rejects_missing_label(self) -> None:
        """Stakeholder type entry missing label must raise ValueError."""
        service = AssessmentService()
        bad_payload = {
            "version": "test-v1",
            "stakeholder_types": [{
                "id": "biotech-sme",
                # missing "label"
                "personas": ["researcher"],
                "user_journeys": ["test"],
                "feedback_categories": ["acceptance"],
            }],
        }
        with self.assertRaises(ValueError):
            service.import_wp2(bad_payload)

    def test_import_wp2_rejects_non_dict_entries(self) -> None:
        """Non-dict stakeholder_types entries must raise ValueError."""
        service = AssessmentService()
        bad_payload = {
            "version": "test-v1",
            "stakeholder_types": ["not-a-dict"],
        }
        with self.assertRaises(ValueError) as ctx:
            service.import_wp2(bad_payload)
        self.assertIn("must be objects", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

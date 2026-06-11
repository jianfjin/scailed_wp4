import unittest

from pathfinder.adapters.demo_data import demo_questionnaires
from pathfinder.fhir.resources import (
    PATHFINDER_SYSTEM,
    bundle_entry,
    coding,
    codeable_concept,
    create_bundle,
    fhir_id,
    reference,
    require_r4,
)
from pathfinder.services.assessment_service import AssessmentService


BASE_ANSWERS = {
    "governance_maturity": 2,
    "data_maturity": 2,
    "compliance_maturity": 2,
    "capabilities": ["secure-processing"],
    "missing_capabilities": ["data-catalog"],
    "regulatory_flags": ["gdpr-review-needed"],
}


class FhirResourceHelperTests(unittest.TestCase):
    def test_fhir_id_is_stable_and_safe(self) -> None:
        self.assertEqual(
            fhir_id("Assessment", "ABC 123", "ready/path"),
            "assessment-abc-123-ready-path",
        )

    def test_reference_uses_resource_type_and_id(self) -> None:
        self.assertEqual(
            reference("Organization", "org-biotech-sme"),
            {"reference": "Organization/org-biotech-sme"},
        )

    def test_coding_uses_pathfinder_system_by_default(self) -> None:
        self.assertEqual(
            coding("secondary-use-readiness", "Secondary use readiness"),
            {
                "system": PATHFINDER_SYSTEM,
                "code": "secondary-use-readiness",
                "display": "Secondary use readiness",
            },
        )

    def test_codeable_concept_uses_default_coding_and_text(self) -> None:
        self.assertEqual(
            codeable_concept("secondary-use-readiness", "Secondary use readiness"),
            {
                "coding": [
                    {
                        "system": PATHFINDER_SYSTEM,
                        "code": "secondary-use-readiness",
                        "display": "Secondary use readiness",
                    }
                ],
                "text": "Secondary use readiness",
            },
        )

    def test_bundle_entry_uses_full_url(self) -> None:
        resource = {"resourceType": "Organization", "id": "org-biotech-sme"}
        self.assertEqual(
            bundle_entry(resource),
            {
                "fullUrl": "https://scailed.eu/fhir/pathfinder/Organization/org-biotech-sme",
                "resource": resource,
            },
        )

    def test_create_bundle_wraps_entries(self) -> None:
        resource = {"resourceType": "Organization", "id": "org-biotech-sme"}
        bundle = create_bundle("bundle-1", [resource])
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["id"], "bundle-1")
        self.assertEqual(bundle["type"], "collection")
        self.assertEqual(bundle["entry"], [bundle_entry(resource)])

    def test_require_r4_rejects_other_versions(self) -> None:
        require_r4("R4")
        require_r4("r4")
        with self.assertRaisesRegex(ValueError, "unsupported FHIR version"):
            require_r4("R5")


class FhirAssessmentInputMapperTests(unittest.TestCase):
    def _session(self) -> dict[str, object]:
        return {
            "assessment_id": "assessment-123",
            "stakeholder_type": "biotech-sme",
            "target_scenario": "secondary-use-readiness",
            "status": "complete",
            "answers": {
                "governance_maturity": 2,
                "data_maturity": 3,
                "compliance_maturity": 2,
                "capabilities": ["secure-processing", "audit-log"],
                "missing_capabilities": ["data-catalog"],
                "regulatory_flags": ["gdpr-review-needed"],
            },
        }

    def _report(self) -> dict[str, object]:
        session = self._session()
        return {
            "session": session,
            "readiness_snapshot": {
                "stakeholder_type": "biotech-sme",
                "target_scenario": "secondary-use-readiness",
                "answers": session["answers"],
                "maturity_scores": {
                    "governance": 2,
                    "data": 3,
                    "compliance": 2,
                },
                "capabilities": ["secure-processing", "audit-log"],
                "missing_capabilities": ["data-catalog"],
                "regulatory_flags": ["gdpr-review-needed"],
                "confidence": 0.82,
                "confidence_warnings": ["mock data mode: partner inputs pending"],
            },
        }

    def test_questionnaire_to_fhir_maps_demo_questionnaire(self) -> None:
        from pathfinder.fhir.mappers import questionnaire_to_fhir

        resource = questionnaire_to_fhir(demo_questionnaires()[0].to_dict())

        self.assertEqual(resource["resourceType"], "Questionnaire")
        self.assertEqual(resource["status"], "active")
        self.assertEqual(resource["id"], "questionnaire-biotech-sme-v1")
        self.assertEqual(resource["subjectType"], ["Organization"])
        self.assertEqual(resource["item"][0]["linkId"], "governance_maturity")
        self.assertEqual(resource["item"][0]["type"], "integer")
        self.assertTrue(resource["item"][0]["required"])
        items = {item["linkId"]: item for item in resource["item"]}
        self.assertTrue(items["capabilities"]["repeats"])
        self.assertEqual(
            items["capabilities"]["answerOption"][0]["valueCoding"],
            {
                "system": PATHFINDER_SYSTEM,
                "code": "data-catalog",
                "display": "data-catalog",
            },
        )

    def test_questionnaire_to_fhir_defaults_missing_required_to_true(self) -> None:
        from pathfinder.fhir.mappers import questionnaire_to_fhir

        resource = questionnaire_to_fhir(
            {
                "stakeholder_type": "biotech-sme",
                "version": "demo-questionnaire-v1",
                "title": "Minimal questionnaire",
                "questions": [
                    {
                        "question_id": "free_text",
                        "label": "Free text",
                        "question_type": "text",
                    }
                ],
            }
        )

        self.assertTrue(resource["item"][0]["required"])

    def test_organization_from_session_maps_stakeholder_without_patient(self) -> None:
        from pathfinder.fhir.mappers import organization_from_session

        resource = organization_from_session(self._session())

        self.assertEqual(resource["resourceType"], "Organization")
        self.assertEqual(resource["id"], "organization-assessment-123")
        self.assertEqual(resource["type"][0]["coding"][0]["code"], "biotech-sme")
        self.assertNotIn("Patient", str(resource))

    def test_questionnaire_response_from_session_preserves_answer_types(self) -> None:
        from pathfinder.fhir.mappers import questionnaire_response_from_session

        questionnaire = demo_questionnaires()[0].to_dict()
        resource = questionnaire_response_from_session(self._session(), questionnaire)

        self.assertEqual(resource["resourceType"], "QuestionnaireResponse")
        self.assertEqual(resource["status"], "completed")
        self.assertEqual(
            resource["subject"],
            {"reference": "Organization/organization-assessment-123"},
        )
        self.assertEqual(
            resource["questionnaire"],
            "Questionnaire/questionnaire-biotech-sme-v1",
        )
        items = {item["linkId"]: item for item in resource["item"]}
        self.assertEqual(
            items["governance_maturity"]["answer"],
            [{"valueInteger": 2}],
        )
        self.assertEqual(
            items["capabilities"]["answer"],
            [
                {
                    "valueCoding": {
                        "system": PATHFINDER_SYSTEM,
                        "code": "secure-processing",
                        "display": "secure-processing",
                    }
                },
                {
                    "valueCoding": {
                        "system": PATHFINDER_SYSTEM,
                        "code": "audit-log",
                        "display": "audit-log",
                    }
                },
            ],
        )

    def test_questionnaire_response_rejects_session_without_answers(self) -> None:
        from pathfinder.fhir.mappers import questionnaire_response_from_session

        session = self._session()
        session.pop("answers")

        with self.assertRaisesRegex(ValueError, "assessment has no submitted answers"):
            questionnaire_response_from_session(session, demo_questionnaires()[0].to_dict())

    def test_questionnaire_response_rejects_non_dict_answers(self) -> None:
        from pathfinder.fhir.mappers import questionnaire_response_from_session

        session = self._session()
        session["answers"] = []

        with self.assertRaisesRegex(ValueError, "assessment has no submitted answers"):
            questionnaire_response_from_session(session, demo_questionnaires()[0].to_dict())

    def test_readiness_observation_from_report_maps_snapshot_components(self) -> None:
        from pathfinder.fhir.mappers import readiness_observation_from_report

        resource = readiness_observation_from_report(self._report())

        self.assertEqual(resource["resourceType"], "Observation")
        self.assertEqual(resource["status"], "final")
        self.assertEqual(
            resource["focus"],
            [{"reference": "Organization/organization-assessment-123"}],
        )
        self.assertNotIn("subject", resource)
        component_codes = {
            component["code"]["coding"][0]["code"]
            for component in resource["component"]
        }
        self.assertTrue(
            {
                "maturity-governance",
                "capability",
                "missing-capability",
                "regulatory-flag",
                "confidence",
                "confidence-warning",
            }.issubset(component_codes)
        )
        warning_components = [
            component
            for component in resource["component"]
            if component["code"]["coding"][0]["code"] == "confidence-warning"
        ]
        self.assertEqual(
            warning_components,
            [
                {
                    "code": codeable_concept("confidence-warning", "Confidence warning"),
                    "valueString": "mock data mode: partner inputs pending",
                }
            ],
        )

    def test_readiness_observation_uses_quantity_confidence(self) -> None:
        from pathfinder.fhir.mappers import readiness_observation_from_report

        resource = readiness_observation_from_report(self._report())
        confidence_components = [
            component
            for component in resource["component"]
            if component["code"]["coding"][0]["code"] == "confidence"
        ]

        self.assertEqual(
            confidence_components,
            [
                {
                    "code": codeable_concept("confidence", "Confidence"),
                    "valueQuantity": {"value": 0.82, "unit": "score"},
                }
            ],
        )

    def test_readiness_observation_sorts_maturity_components_by_code(self) -> None:
        from pathfinder.fhir.mappers import readiness_observation_from_report

        report = self._report()
        report["readiness_snapshot"]["maturity_scores"] = {
            "governance": 2,
            "data": 3,
            "compliance": 2,
        }

        resource = readiness_observation_from_report(report)
        maturity_codes = [
            component["code"]["coding"][0]["code"]
            for component in resource["component"]
            if component["code"]["coding"][0]["code"].startswith("maturity-")
        ]

        self.assertEqual(
            maturity_codes,
            ["maturity-compliance", "maturity-data", "maturity-governance"],
        )

    def test_readiness_observation_rejects_report_without_snapshot(self) -> None:
        from pathfinder.fhir.mappers import readiness_observation_from_report

        with self.assertRaisesRegex(ValueError, "report has no readiness_snapshot"):
            readiness_observation_from_report({"session": self._session()})

class FhirRecommendationAndBundleTests(unittest.TestCase):
    def _completed_assessment(
        self,
    ) -> tuple[AssessmentService, str, dict[str, object], dict[str, object]]:
        service = AssessmentService()
        session = service.create_session(
            "biotech-sme",
            "secondary-use-readiness",
            ip="192.0.2.10",
            user_agent="raw-test-agent",
        )
        assessment_id = str(session["assessment_id"])
        service.submit_answers(
            assessment_id,
            BASE_ANSWERS,
            ip="192.0.2.10",
            user_agent="raw-test-agent",
        )
        service.generate_recommendation(
            assessment_id,
            ip="192.0.2.10",
            user_agent="raw-test-agent",
        )
        report = service.report(
            assessment_id,
            ip="192.0.2.10",
            user_agent="raw-test-agent",
        )
        questionnaire = service.get_questionnaire("biotech-sme")
        return service, assessment_id, report, questionnaire

    def test_guidance_response_from_report_maps_ready_recommendation(self) -> None:
        from pathfinder.fhir.mappers import guidance_response_from_report

        _, assessment_id, report, _ = self._completed_assessment()

        resource = guidance_response_from_report(report)

        self.assertEqual(resource["resourceType"], "GuidanceResponse")
        self.assertEqual(resource["id"], f"guidance-response-{assessment_id}")
        self.assertEqual(resource["status"], "success")
        self.assertEqual(
            resource["subject"],
            {"reference": f"Group/group-{assessment_id}"},
        )
        self.assertEqual(
            resource["result"],
            {"reference": f"CarePlan/care-plan-{assessment_id}"},
        )

    def test_care_plan_from_report_maps_next_steps_as_activities(self) -> None:
        from pathfinder.fhir.mappers import care_plan_from_report

        _, assessment_id, report, _ = self._completed_assessment()

        resource = care_plan_from_report(report)

        self.assertEqual(resource["resourceType"], "CarePlan")
        self.assertEqual(resource["id"], f"care-plan-{assessment_id}")
        self.assertEqual(resource["status"], "active")
        self.assertEqual(resource["intent"], "plan")
        self.assertEqual(
            resource["subject"],
            {"reference": f"Group/group-{assessment_id}"},
        )
        self.assertGreaterEqual(len(resource["activity"]), 1)
        self.assertIn("detail", resource["activity"][0])

    def test_provenance_from_report_preserves_trace_metadata(self) -> None:
        from pathfinder.fhir.mappers import provenance_from_report

        _, assessment_id, report, _ = self._completed_assessment()

        resource = provenance_from_report(report)

        self.assertEqual(resource["resourceType"], "Provenance")
        self.assertEqual(resource["id"], f"provenance-{assessment_id}")
        self.assertIn(
            {"reference": f"CarePlan/care-plan-{assessment_id}"},
            resource["target"],
        )
        provenance_text = str(resource["entity"])
        self.assertIn("schema_version", provenance_text)
        self.assertIn("rule_version", provenance_text)
        self.assertIn("upstream_snapshot_version", provenance_text)

    def test_audit_event_to_fhir_references_bundle_without_raw_request_metadata(self) -> None:
        from pathfinder.fhir.mappers import audit_event_to_fhir

        service, assessment_id, _, _ = self._completed_assessment()

        resource = audit_event_to_fhir(service.audit_log.events()[0], assessment_id)

        self.assertEqual(resource["resourceType"], "AuditEvent")
        self.assertIn(
            {"what": {"reference": f"Bundle/bundle-{assessment_id}"}},
            resource["entity"],
        )
        self.assertIn("system", resource["subtype"][0])
        self.assertIn("code", resource["subtype"][0])
        self.assertNotIn("coding", resource["subtype"][0])
        resource_text = str(resource)
        self.assertIn("ip_hash", resource_text)
        self.assertIn("user_agent_hash", resource_text)
        self.assertNotIn("192.0.2.10", resource_text)
        self.assertNotIn("raw-test-agent", resource_text)

    def test_repeated_audit_event_types_have_unique_ids_and_full_urls(self) -> None:
        from pathfinder.fhir.export_service import build_assessment_bundle

        service, _, report, questionnaire = self._completed_assessment()
        assessment_id = str(report["session"]["assessment_id"])
        service.audit_log.append(
            "answers_submitted",
            {"assessment_id": assessment_id, "answer_ids": ["alpha"]},
            ip="192.0.2.10",
            user_agent="raw-test-agent",
        )
        service.audit_log.append(
            "answers_submitted",
            {"assessment_id": assessment_id, "answer_ids": ["beta"]},
            ip="192.0.2.10",
            user_agent="raw-test-agent",
        )

        bundle = build_assessment_bundle(
            report,
            questionnaire,
            service.audit_log.events(),
        )

        audit_entries = [
            entry
            for entry in bundle["entry"]
            if entry["resource"]["resourceType"] == "AuditEvent"
        ]
        audit_ids = [entry["resource"]["id"] for entry in audit_entries]
        audit_full_urls = [entry["fullUrl"] for entry in audit_entries]
        self.assertEqual(len(audit_ids), len(set(audit_ids)))
        self.assertEqual(len(audit_full_urls), len(set(audit_full_urls)))
        bundle_text = str(bundle)
        self.assertNotIn("192.0.2.10", bundle_text)
        self.assertNotIn("raw-test-agent", bundle_text)

    def test_build_assessment_bundle_includes_assessment_resources(self) -> None:
        from pathfinder.fhir.export_service import build_assessment_bundle

        service, assessment_id, report, questionnaire = self._completed_assessment()

        bundle = build_assessment_bundle(
            report,
            questionnaire,
            service.audit_log.events(),
        )

        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["id"], f"bundle-{assessment_id}")
        resource_types = {
            entry["resource"]["resourceType"]
            for entry in bundle["entry"]
        }
        self.assertTrue(
            {
                "Questionnaire",
                "QuestionnaireResponse",
                "Organization",
                "Group",
                "Observation",
                "GuidanceResponse",
                "CarePlan",
                "Provenance",
                "AuditEvent",
            }.issubset(resource_types)
        )

    def test_build_assessment_bundle_rejects_unsupported_fhir_version(self) -> None:
        from pathfinder.fhir.export_service import build_assessment_bundle

        service, _, report, questionnaire = self._completed_assessment()

        with self.assertRaisesRegex(ValueError, "unsupported FHIR version"):
            build_assessment_bundle(
                report,
                questionnaire,
                service.audit_log.events(),
                fhir_version="R5",
            )


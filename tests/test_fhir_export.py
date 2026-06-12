import unittest

import pathfinder.api.main as api_main
from fastapi.testclient import TestClient

from pathfinder.adapters.demo_data import demo_questionnaires
from pathfinder.api.main import app
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
        trace = report["recommended_path"]["trace"]
        self.assertIn("schema_version", provenance_text)
        self.assertIn("rule_version", provenance_text)
        self.assertIn("upstream_snapshot_version", provenance_text)
        self.assertIn(f"confidence: {trace['confidence']}", provenance_text)
        self.assertIn(f"answer_ids: {trace['answer_ids'][0]}", provenance_text)
        self.assertIn(f"roadmap_node_ids: {trace['roadmap_node_ids'][0]}", provenance_text)
        self.assertIn(f"triggered_rule_ids: {trace['triggered_rule_ids'][0]}", provenance_text)
        self.assertIn(f"regulatory_refs: {trace['regulatory_refs'][0]}", provenance_text)

    def test_audit_event_to_fhir_references_bundle_without_raw_request_metadata(self) -> None:
        from pathfinder.fhir.mappers import audit_event_to_fhir

        service, assessment_id, _, _ = self._completed_assessment()

        resource = audit_event_to_fhir(service.audit_log.events()[0], assessment_id)

        self.assertEqual(resource["resourceType"], "AuditEvent")
        self.assertIn(
            {"what": {"reference": f"Bundle/bundle-{assessment_id}"}},
            resource["entity"],
        )
        for agent in resource["agent"]:
            self.assertIn("requestor", agent)
            self.assertIsInstance(agent["requestor"], bool)
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

    def test_persisted_dict_audit_events_without_hash_use_unique_ids(self) -> None:
        from pathfinder.fhir.export_service import build_assessment_bundle

        _, _, report, questionnaire = self._completed_assessment()
        assessment_id = str(report["session"]["assessment_id"])
        audit_events = [
            {
                "id": 101,
                "event_type": "answers_submitted",
                "event_data": {"assessment_id": assessment_id, "answer_ids": ["alpha"]},
                "timestamp": "2026-06-12T10:00:00+00:00",
            },
            {
                "id": 102,
                "event_type": "answers_submitted",
                "event_data": {"assessment_id": assessment_id, "answer_ids": ["beta"]},
                "timestamp": "2026-06-12T10:01:00+00:00",
            },
        ]

        bundle = build_assessment_bundle(report, questionnaire, audit_events)

        audit_entries = [
            entry
            for entry in bundle["entry"]
            if entry["resource"]["resourceType"] == "AuditEvent"
        ]
        audit_ids = [entry["resource"]["id"] for entry in audit_entries]
        audit_full_urls = [entry["fullUrl"] for entry in audit_entries]
        self.assertEqual(len(audit_ids), len(set(audit_ids)))
        self.assertEqual(len(audit_full_urls), len(set(audit_full_urls)))

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


class AssessmentServiceFhirExportTests(unittest.TestCase):
    def _service_with_answers(self) -> tuple[AssessmentService, str]:
        service = AssessmentService()
        session = service.create_session(
            "biotech-sme",
            "secondary-use-readiness",
            ip="192.0.2.20",
            user_agent="service-export-test-agent",
        )
        assessment_id = str(session["assessment_id"])
        service.submit_answers(
            assessment_id,
            BASE_ANSWERS,
            ip="192.0.2.20",
            user_agent="service-export-test-agent",
        )
        return service, assessment_id

    def _completed_assessment(self) -> tuple[AssessmentService, str]:
        service, assessment_id = self._service_with_answers()
        service.generate_recommendation(
            assessment_id,
            ip="192.0.2.20",
            user_agent="service-export-test-agent",
        )
        return service, assessment_id

    def test_export_fhir_bundle_returns_bundle_and_audits_success(self) -> None:
        service, assessment_id = self._completed_assessment()
        audit_count = len(service.audit_log.events())

        bundle = service.export_fhir_bundle(
            assessment_id,
            ip="192.0.2.20",
            user_agent="service-export-test-agent",
        )

        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["id"], f"bundle-{assessment_id}")
        events = service.audit_log.events()
        self.assertEqual(len(events), audit_count + 1)
        event = events[-1]
        self.assertEqual(event.event_type, "fhir_bundle_exported")
        self.assertEqual(event.event_data["assessment_id"], assessment_id)
        self.assertEqual(event.event_data["bundle_id"], bundle["id"])
        self.assertEqual(event.event_data["fhir_version"], "R4")
        audit_resources = [
            entry["resource"]
            for entry in bundle["entry"]
            if entry["resource"]["resourceType"] == "AuditEvent"
        ]
        self.assertTrue(
            any(resource["type"]["code"] == "fhir_bundle_exported" for resource in audit_resources)
        )

    def test_export_fhir_bundle_scopes_audit_events_to_assessment(self) -> None:
        service, first_assessment_id = self._completed_assessment()
        second_session = service.create_session(
            "biotech-sme",
            "secondary-use-readiness",
            ip="192.0.2.21",
            user_agent="second-service-export-test-agent",
        )
        second_assessment_id = str(second_session["assessment_id"])
        service.submit_answers(
            second_assessment_id,
            BASE_ANSWERS,
            ip="192.0.2.21",
            user_agent="second-service-export-test-agent",
        )
        service.generate_recommendation(
            second_assessment_id,
            ip="192.0.2.21",
            user_agent="second-service-export-test-agent",
        )

        bundle = service.export_fhir_bundle(
            second_assessment_id,
            ip="192.0.2.21",
            user_agent="second-service-export-test-agent",
        )

        audit_resources = [
            entry["resource"]
            for entry in bundle["entry"]
            if entry["resource"]["resourceType"] == "AuditEvent"
        ]
        self.assertGreater(len(audit_resources), 0)
        for resource in audit_resources:
            subtype_values = {
                coding["display"]
                for coding in resource.get("subtype", [])
            }
            self.assertIn(second_assessment_id, subtype_values)
            self.assertNotIn(first_assessment_id, subtype_values)

    def test_export_fhir_bundle_rejects_unsupported_fhir_version_and_audits_failure(self) -> None:
        service, assessment_id = self._completed_assessment()
        report_exported_count = sum(
            event.event_type == "report_exported"
            for event in service.audit_log.events()
        )

        with self.assertRaisesRegex(ValueError, "unsupported FHIR version"):
            service.export_fhir_bundle(assessment_id, fhir_version="R5")

        events = service.audit_log.events()
        self.assertEqual(
            sum(event.event_type == "report_exported" for event in events),
            report_exported_count,
        )
        event = events[-1]
        self.assertEqual(event.event_type, "fhir_export_failed")
        self.assertEqual(event.event_data["assessment_id"], assessment_id)
        self.assertEqual(event.event_data["fhir_version"], "R5")
        self.assertIn("unsupported FHIR version", event.event_data["error"])

    def test_export_fhir_bundle_rejects_unknown_assessment_id(self) -> None:
        service = AssessmentService()

        with self.assertRaisesRegex(KeyError, "Assessment not found"):
            service.export_fhir_bundle("missing-assessment")

    def test_export_fhir_bundle_requires_generated_recommendation(self) -> None:
        service, assessment_id = self._service_with_answers()

        with self.assertRaisesRegex(ValueError, "recommendation must be generated"):
            service.export_fhir_bundle(assessment_id)

    def test_export_fhir_bundle_requires_submitted_answers(self) -> None:
        service = AssessmentService()
        session = service.create_session(
            "biotech-sme",
            "secondary-use-readiness",
        )

        with self.assertRaisesRegex(ValueError, "answers must be submitted before FHIR export"):
            service.export_fhir_bundle(str(session["assessment_id"]))


class FhirApiEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        api_main._service = AssessmentService()

    def _client(self) -> TestClient:
        return TestClient(app)

    def _create_assessment_with_answers(self, client: TestClient) -> str:
        headers = {"Authorization": "Bearer demo-token"}
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
            json={"answers": BASE_ANSWERS},
        )
        self.assertEqual(answers.status_code, 200)
        return assessment_id

    def _create_completed_assessment(self, client: TestClient) -> str:
        headers = {"Authorization": "Bearer demo-token"}
        assessment_id = self._create_assessment_with_answers(client)
        recommendation = client.post(
            f"/v1/assessments/{assessment_id}/recommendations",
            headers=headers,
        )
        self.assertEqual(recommendation.status_code, 200)
        return assessment_id

    def test_fhir_endpoint_requires_demo_token(self) -> None:
        client = self._client()

        response = client.get("/v1/assessments/assessment-123/fhir")

        self.assertEqual(response.status_code, 401)

    def test_fhir_endpoint_returns_completed_assessment_bundle(self) -> None:
        client = self._client()
        headers = {"Authorization": "Bearer demo-token"}
        assessment_id = self._create_completed_assessment(client)

        response = client.get(f"/v1/assessments/{assessment_id}/fhir", headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/fhir+json")
        body = response.json()
        self.assertEqual(body["resourceType"], "Bundle")
        resource_types = {
            entry["resource"]["resourceType"]
            for entry in body["entry"]
        }
        self.assertTrue(
            {
                "QuestionnaireResponse",
                "Provenance",
                "AuditEvent",
            }.issubset(resource_types)
        )

    def test_fhir_endpoint_rejects_unsupported_fhir_version(self) -> None:
        client = self._client()
        headers = {"Authorization": "Bearer demo-token"}
        assessment_id = self._create_completed_assessment(client)

        response = client.get(
            f"/v1/assessments/{assessment_id}/fhir?fhir_version=R5",
            headers=headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "VALIDATION_ERROR")

    def test_fhir_endpoint_requires_recommendation(self) -> None:
        client = self._client()
        headers = {"Authorization": "Bearer demo-token"}
        assessment_id = self._create_assessment_with_answers(client)

        response = client.get(f"/v1/assessments/{assessment_id}/fhir", headers=headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "VALIDATION_ERROR")

    def test_fhir_endpoint_returns_not_found_for_unknown_assessment(self) -> None:
        client = self._client()
        headers = {"Authorization": "Bearer demo-token"}

        response = client.get("/v1/assessments/missing-assessment/fhir", headers=headers)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["error"], "NOT_FOUND")

    def test_fhir_endpoint_hides_unexpected_exception_details(self) -> None:
        class FailingService:
            def export_fhir_bundle(self, *args: object, **kwargs: object) -> dict[str, object]:
                raise RuntimeError("secret internal detail")

        api_main._service = FailingService()
        client = self._client()
        headers = {"Authorization": "Bearer demo-token"}

        response = client.get("/v1/assessments/assessment-123/fhir", headers=headers)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"]["error"], "SERVER_ERROR")
        self.assertNotIn("secret internal detail", response.text)


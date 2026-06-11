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
            [{"valueString": "secure-processing"}, {"valueString": "audit-log"}],
        )

    def test_readiness_observation_from_report_maps_snapshot_components(self) -> None:
        from pathfinder.fhir.mappers import readiness_observation_from_report

        resource = readiness_observation_from_report(self._report())

        self.assertEqual(resource["resourceType"], "Observation")
        self.assertEqual(resource["status"], "final")
        self.assertEqual(
            resource["subject"],
            {"reference": "Organization/organization-assessment-123"},
        )
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
            }.issubset(component_codes)
        )

    def test_readiness_observation_rejects_report_without_snapshot(self) -> None:
        from pathfinder.fhir.mappers import readiness_observation_from_report

        with self.assertRaisesRegex(ValueError, "report has no readiness_snapshot"):
            readiness_observation_from_report({"session": self._session()})

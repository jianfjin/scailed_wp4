import unittest

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

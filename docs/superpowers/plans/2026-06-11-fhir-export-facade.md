# FHIR Export Facade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 1 of the approved FHIR design: export completed Pathfinder assessments as FHIR R4 JSON Bundles without rewriting the core Pathfinder model.

**Architecture:** Add a focused `pathfinder/fhir/` package with pure resource helpers, mappers, and an export service. `AssessmentService` remains the canonical assessment lifecycle owner and exposes a narrow `export_fhir_bundle()` method used by a new `/v1/assessments/{assessment_id}/fhir` endpoint.

**Tech Stack:** Python 3, FastAPI, Pydantic response conventions already in `pathfinder/api`, stdlib dataclasses/dicts, unittest/pytest, FastAPI `TestClient`.

---

## Scope

This plan implements Phase 1 only. It does not add `/fhir/metadata`, FHIR read/search endpoints, generic FHIR persistence, or FHIR-native solver inputs. Those remain Phase 2/3 work documented in `docs/superpowers/specs/2026-06-11-fhir-implementation-design.md`.

Implementation choices locked by this plan:

- FHIR version: accept only `R4` in Phase 1.
- Readiness state: one multi-component `Observation`.
- Recommendation representation: both `GuidanceResponse` and `CarePlan`.
- Bundle storage: generated on demand; no new database tables.
- Coding-system URI base: `https://scailed.eu/fhir/pathfinder`.
- Endpoint: `GET /v1/assessments/{assessment_id}/fhir`.

## File Structure

Create:

- `pathfinder/fhir/__init__.py`: package exports for the FHIR facade.
- `pathfinder/fhir/resources.py`: stable IDs, references, codings, bundle entry helpers, and FHIR invariant checks.
- `pathfinder/fhir/mappers.py`: pure Pathfinder-to-FHIR resource mappers.
- `pathfinder/fhir/export_service.py`: orchestration for a complete assessment Bundle.
- `tests/test_fhir_export.py`: mapper, export service, API, and regression tests.

Modify:

- `pathfinder/services/assessment_service.py`: add `export_fhir_bundle()` and audit events.
- `pathfinder/api/main.py`: add `/v1/assessments/{assessment_id}/fhir` endpoint.
- `pathfinder/api/schemas.py`: no schema needed for the FHIR body; the endpoint returns a raw FHIR JSON response.

Do not modify:

- `pathfinder/core/models.py`
- `pathfinder/core/solver.py`
- `deploy/pg-init/02_schema.sql`
- frontend files

---

### Task 1: FHIR Resource Primitives

**Files:**
- Create: `pathfinder/fhir/__init__.py`
- Create: `pathfinder/fhir/resources.py`
- Create: `tests/test_fhir_export.py`

- [ ] **Step 1: Write failing tests for stable IDs, references, Bundle entries, and R4 validation**

Add this initial content to `tests/test_fhir_export.py`:

```python
import unittest

from pathfinder.fhir.resources import (
    PATHFINDER_SYSTEM,
    bundle_entry,
    coding,
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

    def test_bundle_entry_uses_full_url(self) -> None:
        resource = {"resourceType": "Organization", "id": "org-biotech-sme"}
        self.assertEqual(
            bundle_entry(resource),
            {
                "fullUrl": "urn:uuid:Organization/org-biotech-sme",
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
```

- [ ] **Step 2: Run the helper tests and verify they fail**

Run:

```bash
pytest tests/test_fhir_export.py -q
```

Expected: FAIL with an import error for `pathfinder.fhir` or `pathfinder.fhir.resources`.

- [ ] **Step 3: Create the FHIR package and helper implementation**

Create `pathfinder/fhir/__init__.py`:

```python
"""FHIR export facade for Pathfinder assessment packages."""
```

Create `pathfinder/fhir/resources.py`:

```python
"""Small FHIR R4 resource helpers used by Pathfinder export mappers."""

from __future__ import annotations

import re
from typing import Any

PATHFINDER_SYSTEM = "https://scailed.eu/fhir/pathfinder"


def fhir_id(*parts: object) -> str:
    raw = "-".join(str(part) for part in parts if str(part).strip())
    lowered = raw.strip().lower()
    safe = re.sub(r"[^a-z0-9.-]+", "-", lowered)
    safe = re.sub(r"-+", "-", safe).strip("-")
    if not safe:
        raise ValueError("FHIR id parts must produce a non-empty id")
    return safe[:64]


def reference(resource_type: str, resource_id: str) -> dict[str, str]:
    return {"reference": f"{resource_type}/{resource_id}"}


def coding(code: str, display: str | None = None, system: str = PATHFINDER_SYSTEM) -> dict[str, str]:
    value = {"system": system, "code": code}
    if display is not None:
        value["display"] = display
    return value


def codeable_concept(code: str, display: str | None = None, system: str = PATHFINDER_SYSTEM) -> dict[str, Any]:
    concept: dict[str, Any] = {"coding": [coding(code, display, system)]}
    if display is not None:
        concept["text"] = display
    return concept


def bundle_entry(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "fullUrl": f"urn:uuid:{resource['resourceType']}/{resource['id']}",
        "resource": resource,
    }


def create_bundle(bundle_id: str, resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "entry": [bundle_entry(resource) for resource in resources],
    }


def require_r4(fhir_version: str) -> None:
    if fhir_version.upper() != "R4":
        raise ValueError(f"unsupported FHIR version: {fhir_version}")
```

- [ ] **Step 4: Run the helper tests and verify they pass**

Run:

```bash
pytest tests/test_fhir_export.py -q
```

Expected: PASS for all helper tests.

- [ ] **Step 5: Commit Task 1**

```bash
git add pathfinder/fhir/__init__.py pathfinder/fhir/resources.py tests/test_fhir_export.py
git commit -m "feat(fhir): add resource helper primitives"
```

---

### Task 2: Questionnaire, Organization, Response, and Readiness Mappers

**Files:**
- Create: `pathfinder/fhir/mappers.py`
- Modify: `tests/test_fhir_export.py`

- [ ] **Step 1: Add mapper tests for assessment input and readiness resources**

Append this to `tests/test_fhir_export.py`:

```python
from pathfinder.adapters.demo_data import demo_questionnaires
from pathfinder.fhir.mappers import (
    organization_from_session,
    questionnaire_response_from_session,
    questionnaire_to_fhir,
    readiness_observation_from_report,
)


class FhirAssessmentInputMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.questionnaire = demo_questionnaires()[0].to_dict()
        self.session = {
            "assessment_id": "assessment-123",
            "stakeholder_type": "biotech-sme",
            "target_scenario": "secondary-use-readiness",
            "answers": {
                "governance_maturity": 2,
                "data_maturity": 3,
                "compliance_maturity": 4,
                "capabilities": ["secure-processing"],
                "missing_capabilities": ["data-catalog"],
                "regulatory_flags": ["gdpr-review-needed"],
            },
        }
        self.report = {
            "session": self.session,
            "readiness_snapshot": {
                "maturity_scores": {"governance": 2, "data": 3, "compliance": 4},
                "capabilities": ["secure-processing"],
                "missing_capabilities": ["data-catalog"],
                "regulatory_flags": ["gdpr-review-needed"],
                "confidence": 0.8,
                "confidence_warnings": ["mock warning"],
            },
        }

    def test_questionnaire_maps_to_fhir_questionnaire(self) -> None:
        resource = questionnaire_to_fhir(self.questionnaire)
        self.assertEqual(resource["resourceType"], "Questionnaire")
        self.assertEqual(resource["status"], "active")
        self.assertEqual(resource["id"], "questionnaire-biotech-sme-v1")
        self.assertEqual(resource["item"][0]["linkId"], "governance_maturity")
        self.assertEqual(resource["item"][0]["type"], "integer")

    def test_organization_uses_stakeholder_context_without_patient_data(self) -> None:
        resource = organization_from_session(self.session)
        self.assertEqual(resource["resourceType"], "Organization")
        self.assertEqual(resource["id"], "organization-assessment-123")
        self.assertEqual(resource["type"][0]["coding"][0]["code"], "biotech-sme")
        self.assertNotIn("Patient", str(resource))

    def test_questionnaire_response_preserves_answers(self) -> None:
        resource = questionnaire_response_from_session(self.session, self.questionnaire)
        self.assertEqual(resource["resourceType"], "QuestionnaireResponse")
        self.assertEqual(resource["status"], "completed")
        self.assertEqual(resource["subject"], {"reference": "Organization/organization-assessment-123"})
        values = {item["linkId"]: item["answer"] for item in resource["item"]}
        self.assertEqual(values["governance_maturity"], [{"valueInteger": 2}])
        self.assertEqual(values["capabilities"], [{"valueString": "secure-processing"}])

    def test_readiness_observation_uses_components(self) -> None:
        resource = readiness_observation_from_report(self.report)
        self.assertEqual(resource["resourceType"], "Observation")
        self.assertEqual(resource["status"], "final")
        self.assertEqual(resource["subject"], {"reference": "Organization/organization-assessment-123"})
        component_codes = [component["code"]["coding"][0]["code"] for component in resource["component"]]
        self.assertIn("maturity-governance", component_codes)
        self.assertIn("capability", component_codes)
        self.assertIn("missing-capability", component_codes)
        self.assertIn("regulatory-flag", component_codes)
        self.assertIn("confidence", component_codes)
```

- [ ] **Step 2: Run mapper tests and verify they fail**

Run:

```bash
pytest tests/test_fhir_export.py::FhirAssessmentInputMapperTests -q
```

Expected: FAIL with import error for `pathfinder.fhir.mappers`.

- [ ] **Step 3: Implement input and readiness mappers**

Create `pathfinder/fhir/mappers.py`:

```python
"""Pure mappers from Pathfinder assessment data to FHIR R4 JSON resources."""

from __future__ import annotations

from typing import Any

from pathfinder.fhir.resources import codeable_concept, fhir_id, reference


def _question_type_to_fhir(question_type: str) -> str:
    return {
        "numeric": "integer",
        "single_choice": "choice",
        "multi_choice": "choice",
        "text": "text",
    }.get(question_type, "text")


def _answer_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, bool):
        return [{"valueBoolean": value}]
    if isinstance(value, int):
        return [{"valueInteger": value}]
    if isinstance(value, list):
        return [{"valueString": str(item)} for item in value]
    return [{"valueString": str(value)}]


def questionnaire_to_fhir(questionnaire: dict[str, Any]) -> dict[str, Any]:
    stakeholder_type = str(questionnaire["stakeholder_type"])
    version = str(questionnaire["version"])
    return {
        "resourceType": "Questionnaire",
        "id": fhir_id("questionnaire", stakeholder_type, version),
        "status": "active",
        "version": version,
        "title": questionnaire["title"],
        "subjectType": ["Organization"],
        "item": [
            {
                "linkId": question["question_id"],
                "text": question["label"],
                "type": _question_type_to_fhir(question["question_type"]),
                "required": bool(question.get("required", True)),
                **(
                    {
                        "answerOption": [
                            {"valueCoding": {"code": option, "display": option}}
                            for option in question.get("options", [])
                        ]
                    }
                    if question.get("options")
                    else {}
                ),
            }
            for question in questionnaire.get("questions", [])
        ],
    }


def organization_from_session(session: dict[str, Any]) -> dict[str, Any]:
    assessment_id = str(session["assessment_id"])
    stakeholder_type = str(session["stakeholder_type"])
    return {
        "resourceType": "Organization",
        "id": fhir_id("organization", assessment_id),
        "active": True,
        "type": [codeable_concept(stakeholder_type, stakeholder_type.replace("-", " ").title())],
        "name": f"Pathfinder assessment organization {assessment_id}",
    }


def questionnaire_response_from_session(
    session: dict[str, Any], questionnaire: dict[str, Any]
) -> dict[str, Any]:
    assessment_id = str(session["assessment_id"])
    questionnaire_resource = questionnaire_to_fhir(questionnaire)
    answers = session.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("assessment has no submitted answers")
    return {
        "resourceType": "QuestionnaireResponse",
        "id": fhir_id("questionnaire-response", assessment_id),
        "status": "completed",
        "questionnaire": f"Questionnaire/{questionnaire_resource['id']}",
        "subject": reference("Organization", fhir_id("organization", assessment_id)),
        "item": [
            {
                "linkId": str(question_id),
                "answer": _answer_value(value),
            }
            for question_id, value in sorted(answers.items())
        ],
    }


def readiness_observation_from_report(report: dict[str, Any]) -> dict[str, Any]:
    session = report["session"]
    snapshot = report.get("readiness_snapshot")
    if not isinstance(snapshot, dict) or not snapshot:
        raise ValueError("report has no readiness_snapshot")
    assessment_id = str(session["assessment_id"])
    components: list[dict[str, Any]] = []

    for dimension, score in sorted(snapshot.get("maturity_scores", {}).items()):
        components.append({
            "code": codeable_concept(f"maturity-{dimension}", f"{dimension} maturity"),
            "valueInteger": int(score),
        })
    for capability in snapshot.get("capabilities", []):
        components.append({
            "code": codeable_concept("capability", "Capability"),
            "valueString": str(capability),
        })
    for missing in snapshot.get("missing_capabilities", []):
        components.append({
            "code": codeable_concept("missing-capability", "Missing capability"),
            "valueString": str(missing),
        })
    for flag in snapshot.get("regulatory_flags", []):
        components.append({
            "code": codeable_concept("regulatory-flag", "Regulatory flag"),
            "valueString": str(flag),
        })
    components.append({
        "code": codeable_concept("confidence", "Confidence"),
        "valueQuantity": {"value": float(snapshot.get("confidence", 0.0)), "unit": "score"},
    })
    for warning in snapshot.get("confidence_warnings", []):
        components.append({
            "code": codeable_concept("confidence-warning", "Confidence warning"),
            "valueString": str(warning),
        })

    return {
        "resourceType": "Observation",
        "id": fhir_id("readiness", assessment_id),
        "status": "final",
        "code": codeable_concept("pathfinder-readiness", "Pathfinder readiness snapshot"),
        "subject": reference("Organization", fhir_id("organization", assessment_id)),
        "component": components,
    }
```

- [ ] **Step 4: Run mapper tests and verify they pass**

Run:

```bash
pytest tests/test_fhir_export.py::FhirAssessmentInputMapperTests -q
```

Expected: PASS for all tests in `FhirAssessmentInputMapperTests`.

- [ ] **Step 5: Run all FHIR tests**

Run:

```bash
pytest tests/test_fhir_export.py -q
```

Expected: PASS for helper and mapper tests.

- [ ] **Step 6: Commit Task 2**

```bash
git add pathfinder/fhir/mappers.py tests/test_fhir_export.py
git commit -m "feat(fhir): map assessment inputs to resources"
```

---

### Task 3: Recommendation, Provenance, Audit, and Bundle Export Service

**Files:**
- Modify: `pathfinder/fhir/mappers.py`
- Create: `pathfinder/fhir/export_service.py`
- Modify: `tests/test_fhir_export.py`

- [ ] **Step 1: Add export service tests**

Append this to `tests/test_fhir_export.py`:

```python
from pathfinder.fhir.export_service import build_assessment_bundle
from pathfinder.fhir.mappers import (
    audit_event_to_fhir,
    care_plan_from_report,
    guidance_response_from_report,
    provenance_from_report,
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


def completed_assessment() -> tuple[AssessmentService, str, dict[str, object]]:
    service = AssessmentService()
    session = service.create_session("biotech-sme", "secondary-use-readiness")
    assessment_id = str(session["assessment_id"])
    service.submit_answers(assessment_id, BASE_ANSWERS)
    service.generate_recommendation(assessment_id)
    report = service.report(assessment_id)
    return service, assessment_id, report


class FhirRecommendationAndBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service, self.assessment_id, self.report = completed_assessment()
        self.questionnaire = self.service.get_questionnaire("biotech-sme")

    def test_guidance_response_maps_recommendation_status(self) -> None:
        resource = guidance_response_from_report(self.report)
        self.assertEqual(resource["resourceType"], "GuidanceResponse")
        self.assertEqual(resource["status"], "success")
        self.assertEqual(resource["subject"], {"reference": f"Organization/organization-{self.assessment_id}"})
        self.assertEqual(resource["result"], {"reference": f"CarePlan/care-plan-{self.assessment_id}"})

    def test_care_plan_contains_ordered_next_steps(self) -> None:
        resource = care_plan_from_report(self.report)
        self.assertEqual(resource["resourceType"], "CarePlan")
        self.assertEqual(resource["status"], "active")
        self.assertGreaterEqual(len(resource["activity"]), 1)
        self.assertIn("detail", resource["activity"][0])

    def test_provenance_carries_trace_versions(self) -> None:
        resource = provenance_from_report(self.report)
        self.assertEqual(resource["resourceType"], "Provenance")
        self.assertGreaterEqual(len(resource["entity"]), 1)
        entity_text = str(resource["entity"])
        self.assertIn("schema_version", entity_text)
        self.assertIn("rule_version", entity_text)
        self.assertIn("upstream_snapshot_version", entity_text)

    def test_audit_event_hides_raw_request_context(self) -> None:
        event = self.service.audit_log.events()[0]
        resource = audit_event_to_fhir(event, self.assessment_id)
        self.assertEqual(resource["resourceType"], "AuditEvent")
        self.assertEqual(resource["entity"][0]["what"], {"reference": f"Bundle/bundle-{self.assessment_id}"})
        self.assertNotIn("ip", str(resource).lower())
        self.assertNotIn("user-agent", str(resource).lower())

    def test_build_assessment_bundle_contains_expected_resource_types(self) -> None:
        bundle = build_assessment_bundle(
            report=self.report,
            questionnaire=self.questionnaire,
            audit_events=self.service.audit_log.events(),
            fhir_version="R4",
        )
        self.assertEqual(bundle["resourceType"], "Bundle")
        resource_types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
        self.assertIn("Questionnaire", resource_types)
        self.assertIn("QuestionnaireResponse", resource_types)
        self.assertIn("Organization", resource_types)
        self.assertIn("Observation", resource_types)
        self.assertIn("GuidanceResponse", resource_types)
        self.assertIn("CarePlan", resource_types)
        self.assertIn("Provenance", resource_types)
        self.assertIn("AuditEvent", resource_types)

    def test_build_assessment_bundle_rejects_r5_for_phase_1(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported FHIR version"):
            build_assessment_bundle(
                report=self.report,
                questionnaire=self.questionnaire,
                audit_events=self.service.audit_log.events(),
                fhir_version="R5",
            )
```

- [ ] **Step 2: Run export tests and verify they fail**

Run:

```bash
pytest tests/test_fhir_export.py::FhirRecommendationAndBundleTests -q
```

Expected: FAIL with missing mapper/export service imports.

- [ ] **Step 3: Add recommendation, provenance, and audit mappers**

Append this to `pathfinder/fhir/mappers.py`:

```python

def guidance_response_from_report(report: dict[str, Any]) -> dict[str, Any]:
    session = report["session"]
    assessment_id = str(session["assessment_id"])
    recommendation = report.get("recommended_path")
    if not isinstance(recommendation, dict) or not recommendation:
        raise ValueError("report has no recommended_path")
    status = "data-required" if recommendation.get("status") == "blocked" else "success"
    return {
        "resourceType": "GuidanceResponse",
        "id": fhir_id("guidance-response", assessment_id),
        "status": status,
        "moduleCanonical": "https://scailed.eu/fhir/pathfinder/GuidanceResponse/pathfinder-readiness",
        "subject": reference("Organization", fhir_id("organization", assessment_id)),
        "result": reference("CarePlan", fhir_id("care-plan", assessment_id)),
        "note": [
            {"text": f"Pathfinder recommendation status: {recommendation.get('status', 'unknown')}"}
        ],
    }


def care_plan_from_report(report: dict[str, Any]) -> dict[str, Any]:
    session = report["session"]
    assessment_id = str(session["assessment_id"])
    recommendation = report.get("recommended_path")
    if not isinstance(recommendation, dict) or not recommendation:
        raise ValueError("report has no recommended_path")
    activities = []
    for index, step in enumerate(recommendation.get("next_steps", []), start=1):
        activities.append({
            "detail": {
                "kind": "Task",
                "code": codeable_concept(str(step.get("node_id", f"step-{index}")), str(step.get("label", "Pathfinder step"))),
                "status": "not-started",
                "description": str(step.get("description", step.get("label", "Pathfinder step"))),
            }
        })
    return {
        "resourceType": "CarePlan",
        "id": fhir_id("care-plan", assessment_id),
        "status": "active" if recommendation.get("status") == "ready" else "draft",
        "intent": "plan",
        "subject": reference("Organization", fhir_id("organization", assessment_id)),
        "title": "Pathfinder EHDS readiness next-step plan",
        "activity": activities,
    }


def provenance_from_report(report: dict[str, Any]) -> dict[str, Any]:
    session = report["session"]
    assessment_id = str(session["assessment_id"])
    recommendation = report.get("recommended_path")
    trace = recommendation.get("trace", {}) if isinstance(recommendation, dict) else {}
    entities = []
    for key in ("schema_version", "rule_version", "upstream_snapshot_version"):
        if trace.get(key):
            entities.append({
                "role": "source",
                "what": {"display": f"{key}: {trace[key]}"},
            })
    for key in ("answer_ids", "roadmap_node_ids", "triggered_rule_ids", "regulatory_refs"):
        for value in trace.get(key, []) or []:
            entities.append({
                "role": "source",
                "what": {"display": f"{key}: {value}"},
            })
    return {
        "resourceType": "Provenance",
        "id": fhir_id("provenance", assessment_id),
        "target": [
            reference("GuidanceResponse", fhir_id("guidance-response", assessment_id)),
            reference("CarePlan", fhir_id("care-plan", assessment_id)),
            reference("Observation", fhir_id("readiness", assessment_id)),
        ],
        "recorded": report.get("session", {}).get("completed_at") or "1970-01-01T00:00:00+00:00",
        "entity": entities,
    }


def audit_event_to_fhir(event: Any, assessment_id: str) -> dict[str, Any]:
    event_data = dict(getattr(event, "event_data", {}) or {})
    return {
        "resourceType": "AuditEvent",
        "id": fhir_id("audit-event", assessment_id, getattr(event, "event_hash", "event")),
        "type": codeable_concept(str(getattr(event, "event_type", "pathfinder-audit")), str(getattr(event, "event_type", "pathfinder-audit"))),
        "action": "E",
        "recorded": str(getattr(event, "timestamp", "1970-01-01T00:00:00+00:00")),
        "outcome": "0",
        "agent": [{"name": "Pathfinder"}],
        "source": {"observer": {"display": "SCAILED Pathfinder"}},
        "entity": [
            {
                "what": reference("Bundle", fhir_id("bundle", assessment_id)),
                "detail": [
                    {"type": str(key), "valueString": str(value)}
                    for key, value in sorted(event_data.items())
                    if key not in {"ip", "user_agent", "ip_hash", "user_agent_hash"}
                ],
            }
        ],
    }
```

- [ ] **Step 4: Create the export service**

Create `pathfinder/fhir/export_service.py`:

```python
"""FHIR Bundle assembly for completed Pathfinder assessments."""

from __future__ import annotations

from typing import Any, Iterable

from pathfinder.fhir.mappers import (
    audit_event_to_fhir,
    care_plan_from_report,
    guidance_response_from_report,
    organization_from_session,
    provenance_from_report,
    questionnaire_response_from_session,
    questionnaire_to_fhir,
    readiness_observation_from_report,
)
from pathfinder.fhir.resources import create_bundle, fhir_id, require_r4


def build_assessment_bundle(
    report: dict[str, Any],
    questionnaire: dict[str, Any],
    audit_events: Iterable[Any],
    fhir_version: str = "R4",
) -> dict[str, Any]:
    require_r4(fhir_version)
    session = report.get("session")
    if not isinstance(session, dict):
        raise ValueError("report has no session")
    assessment_id = str(session["assessment_id"])
    resources = [
        organization_from_session(session),
        questionnaire_to_fhir(questionnaire),
        questionnaire_response_from_session(session, questionnaire),
        readiness_observation_from_report(report),
        care_plan_from_report(report),
        guidance_response_from_report(report),
        provenance_from_report(report),
    ]
    resources.extend(audit_event_to_fhir(event, assessment_id) for event in audit_events)
    return create_bundle(fhir_id("bundle", assessment_id), resources)
```

- [ ] **Step 5: Run export tests and verify they pass**

Run:

```bash
pytest tests/test_fhir_export.py::FhirRecommendationAndBundleTests -q
```

Expected: PASS for all tests in `FhirRecommendationAndBundleTests`.

- [ ] **Step 6: Run all FHIR tests**

Run:

```bash
pytest tests/test_fhir_export.py -q
```

Expected: PASS for the full file.

- [ ] **Step 7: Commit Task 3**

```bash
git add pathfinder/fhir/mappers.py pathfinder/fhir/export_service.py tests/test_fhir_export.py
git commit -m "feat(fhir): assemble assessment bundles"
```

---

### Task 4: AssessmentService FHIR Export Method and Audit Events

**Files:**
- Modify: `pathfinder/services/assessment_service.py`
- Modify: `tests/test_fhir_export.py`

- [ ] **Step 1: Add service tests for successful export, audit, unsupported version, and no recommendation**

Append this to `tests/test_fhir_export.py`:

```python

class AssessmentServiceFhirExportTests(unittest.TestCase):
    def test_export_fhir_bundle_appends_audit_event(self) -> None:
        service, assessment_id, _report = completed_assessment()
        before = len(service.audit_log.events())
        bundle = service.export_fhir_bundle(assessment_id)
        after = len(service.audit_log.events())
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(after, before + 1)
        self.assertEqual(service.audit_log.events()[-1].event_type, "fhir_bundle_exported")

    def test_export_fhir_bundle_rejects_unknown_version_and_audits_failure(self) -> None:
        service, assessment_id, _report = completed_assessment()
        with self.assertRaisesRegex(ValueError, "unsupported FHIR version"):
            service.export_fhir_bundle(assessment_id, fhir_version="R5")
        self.assertEqual(service.audit_log.events()[-1].event_type, "fhir_export_failed")

    def test_export_fhir_bundle_requires_existing_assessment(self) -> None:
        service = AssessmentService()
        with self.assertRaisesRegex(KeyError, "Assessment not found"):
            service.export_fhir_bundle("missing")

    def test_export_fhir_bundle_requires_recommendation(self) -> None:
        service = AssessmentService()
        session = service.create_session("biotech-sme", "secondary-use-readiness")
        assessment_id = str(session["assessment_id"])
        service.submit_answers(assessment_id, BASE_ANSWERS)
        with self.assertRaisesRegex(ValueError, "recommendation must be generated"):
            service.export_fhir_bundle(assessment_id)
```

- [ ] **Step 2: Run service tests and verify they fail**

Run:

```bash
pytest tests/test_fhir_export.py::AssessmentServiceFhirExportTests -q
```

Expected: FAIL because `AssessmentService.export_fhir_bundle` does not exist.

- [ ] **Step 3: Import the export service in `assessment_service.py`**

Near the existing imports in `pathfinder/services/assessment_service.py`, add:

```python
from pathfinder.fhir.export_service import build_assessment_bundle
```

- [ ] **Step 4: Add `export_fhir_bundle()` to `AssessmentService`**

Add this method after `report()` in `pathfinder/services/assessment_service.py`:

```python
    def export_fhir_bundle(
        self,
        assessment_id: str,
        fhir_version: str = "R4",
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        if assessment_id not in self.sessions:
            raise KeyError(f"Assessment not found: {assessment_id}")
        session = self.sessions[assessment_id]
        if not isinstance(session.get("answers"), dict):
            raise ValueError("answers must be submitted before FHIR export")
        if not isinstance(session.get("recommendation"), dict):
            raise ValueError("recommendation must be generated before FHIR export")

        try:
            report = self.report(assessment_id, ip=ip, user_agent=user_agent)
            questionnaire = self.get_questionnaire(str(session["stakeholder_type"]))
            bundle = build_assessment_bundle(
                report=report,
                questionnaire=questionnaire,
                audit_events=self.audit_log.events(),
                fhir_version=fhir_version,
            )
        except Exception as exc:
            self.audit_log.append(
                "fhir_export_failed",
                {"assessment_id": assessment_id, "error": str(exc), "fhir_version": fhir_version},
                ip=ip,
                user_agent=user_agent,
            )
            raise

        self.audit_log.append(
            "fhir_bundle_exported",
            {"assessment_id": assessment_id, "bundle_id": bundle["id"], "fhir_version": fhir_version},
            ip=ip,
            user_agent=user_agent,
        )
        return bundle
```

- [ ] **Step 5: Run service tests and verify they pass**

Run:

```bash
pytest tests/test_fhir_export.py::AssessmentServiceFhirExportTests -q
```

Expected: PASS for all service export tests.

- [ ] **Step 6: Run existing API and acceptance smoke tests for regression**

Run:

```bash
pytest tests/test_api.py::ApiTests::test_assessment_flow_api tests/test_d4_1_acceptance.py::test_d4_1_4_report_includes_all_sections -q
```

Expected: PASS. This verifies the new export method did not disturb the existing assessment/report flow.

- [ ] **Step 7: Commit Task 4**

```bash
git add pathfinder/services/assessment_service.py tests/test_fhir_export.py
git commit -m "feat(fhir): export bundles from assessment service"
```

---

### Task 5: `/v1/assessments/{assessment_id}/fhir` API Endpoint

**Files:**
- Modify: `pathfinder/api/main.py`
- Modify: `tests/test_fhir_export.py`

- [ ] **Step 1: Add API tests for auth, success, content type, unsupported version, and missing recommendation**

Append this to `tests/test_fhir_export.py`:

```python
from fastapi.testclient import TestClient

import pathfinder.api.main as api_main
from pathfinder.api.main import app


class FhirApiEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        api_main._service = None
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer demo-token"}

    def _complete_api_assessment(self) -> str:
        session = self.client.post(
            "/v1/assessments",
            headers=self.headers,
            json={"stakeholder_type": "biotech-sme", "target_scenario": "secondary-use-readiness"},
        )
        self.assertEqual(session.status_code, 200)
        assessment_id = session.json()["assessment_id"]
        answers = self.client.post(
            f"/v1/assessments/{assessment_id}/answers/batch",
            headers=self.headers,
            json={"answers": BASE_ANSWERS},
        )
        self.assertEqual(answers.status_code, 200)
        recommendation = self.client.post(
            f"/v1/assessments/{assessment_id}/recommendations",
            headers=self.headers,
        )
        self.assertEqual(recommendation.status_code, 200)
        return assessment_id

    def test_fhir_endpoint_requires_token(self) -> None:
        response = self.client.get("/v1/assessments/missing/fhir")
        self.assertEqual(response.status_code, 401)

    def test_fhir_endpoint_returns_bundle(self) -> None:
        assessment_id = self._complete_api_assessment()
        response = self.client.get(f"/v1/assessments/{assessment_id}/fhir", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"].split(";")[0], "application/fhir+json")
        body = response.json()
        self.assertEqual(body["resourceType"], "Bundle")
        resource_types = [entry["resource"]["resourceType"] for entry in body["entry"]]
        self.assertIn("QuestionnaireResponse", resource_types)
        self.assertIn("Provenance", resource_types)
        self.assertIn("AuditEvent", resource_types)

    def test_fhir_endpoint_rejects_unsupported_version(self) -> None:
        assessment_id = self._complete_api_assessment()
        response = self.client.get(
            f"/v1/assessments/{assessment_id}/fhir?fhir_version=R5",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "VALIDATION_ERROR")

    def test_fhir_endpoint_requires_recommendation(self) -> None:
        session = self.client.post(
            "/v1/assessments",
            headers=self.headers,
            json={"stakeholder_type": "biotech-sme", "target_scenario": "secondary-use-readiness"},
        )
        assessment_id = session.json()["assessment_id"]
        answers = self.client.post(
            f"/v1/assessments/{assessment_id}/answers/batch",
            headers=self.headers,
            json={"answers": BASE_ANSWERS},
        )
        self.assertEqual(answers.status_code, 200)
        response = self.client.get(f"/v1/assessments/{assessment_id}/fhir", headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "VALIDATION_ERROR")
```

- [ ] **Step 2: Run API endpoint tests and verify they fail**

Run:

```bash
pytest tests/test_fhir_export.py::FhirApiEndpointTests -q
```

Expected: FAIL with 404 for the FHIR endpoint.

- [ ] **Step 3: Import `Response` in `pathfinder/api/main.py`**

Change the FastAPI responses import from:

```python
from fastapi.responses import HTMLResponse, JSONResponse
```

to:

```python
from fastapi.responses import HTMLResponse, JSONResponse, Response
```

Add this stdlib import near the top:

```python
import json
```

- [ ] **Step 4: Add the FHIR endpoint after the existing report endpoint**

Add this function in `pathfinder/api/main.py` after `report()` and before the roadmap endpoints:

```python
@app.get("/v1/assessments/{assessment_id}/fhir")
def fhir_assessment_bundle(
    assessment_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    fhir_version: str = Query(default="R4"),
):
    require_demo_token(authorization)
    try:
        bundle = _get_service().export_fhir_bundle(
            assessment_id,
            fhir_version=fhir_version,
            **_audit_context(request),
        )
    except KeyError as exc:
        raise _not_found("assessment not found") from exc
    except ValueError as exc:
        raise _validation_error(str(exc)) from exc
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"detail": ApiError(error="SERVER_ERROR", detail=str(exc)).model_dump()},
        )
    return Response(
        content=json.dumps(bundle),
        media_type="application/fhir+json",
    )
```

- [ ] **Step 5: Run API endpoint tests and verify they pass**

Run:

```bash
pytest tests/test_fhir_export.py::FhirApiEndpointTests -q
```

Expected: PASS for all endpoint tests.

- [ ] **Step 6: Run existing API test to verify no route regression**

Run:

```bash
pytest tests/test_api.py::ApiTests::test_assessment_flow_api -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git add pathfinder/api/main.py tests/test_fhir_export.py
git commit -m "feat(fhir): expose assessment bundle endpoint"
```

---

### Task 6: Acceptance Coverage, Docs, and Final Verification

**Files:**
- Modify: `tests/test_d4_1_acceptance.py`
- Modify: `docs/superpowers/specs/2026-06-11-fhir-implementation-design.md`

- [ ] **Step 1: Add D4.1 acceptance coverage for FHIR Bundle traceability**

Append this test to `tests/test_d4_1_acceptance.py`:

```python

def test_d4_1_8_fhir_export_contains_traceability_bundle() -> None:
    """FHIR export includes assessment package resources with traceability.

    D4.1 interoperability extension: a completed assessment can be exported
    as a FHIR Bundle containing questionnaire, answer, readiness,
    recommendation, provenance, and audit resources.
    """
    api_main._service = None
    client = TestClient(app)
    headers = {"Authorization": "Bearer demo-token"}

    session = client.post(
        "/v1/assessments",
        headers=headers,
        json={"stakeholder_type": "biotech-sme", "target_scenario": "secondary-use-readiness"},
    )
    assert session.status_code == 200
    assessment_id = session.json()["assessment_id"]

    answers = client.post(
        f"/v1/assessments/{assessment_id}/answers/batch",
        headers=headers,
        json={"answers": BASE_ANSWERS},
    )
    assert answers.status_code == 200

    recommendation = client.post(
        f"/v1/assessments/{assessment_id}/recommendations",
        headers=headers,
    )
    assert recommendation.status_code == 200

    fhir_response = client.get(f"/v1/assessments/{assessment_id}/fhir", headers=headers)
    assert fhir_response.status_code == 200
    assert fhir_response.headers["content-type"].split(";")[0] == "application/fhir+json"
    bundle = fhir_response.json()
    assert bundle["resourceType"] == "Bundle"
    resources = [entry["resource"] for entry in bundle["entry"]]
    resource_types = {resource["resourceType"] for resource in resources}
    assert {
        "Questionnaire",
        "QuestionnaireResponse",
        "Organization",
        "Observation",
        "GuidanceResponse",
        "CarePlan",
        "Provenance",
        "AuditEvent",
    }.issubset(resource_types)
    references = str(bundle)
    assert f"Organization/organization-{assessment_id}" in references
    assert f"CarePlan/care-plan-{assessment_id}" in references
```

- [ ] **Step 2: Run the new acceptance test**

Run:

```bash
pytest tests/test_d4_1_acceptance.py::test_d4_1_8_fhir_export_contains_traceability_bundle -q
```

Expected: PASS.

- [ ] **Step 3: Mark Phase 1 implemented in the design spec**

In `docs/superpowers/specs/2026-06-11-fhir-implementation-design.md`, change:

```markdown
Status: Proposed
```

to:

```markdown
Status: Phase 1 implemented
```

Add this section after `## Summary`:

```markdown
## Phase 1 Implementation Notes

Phase 1 implements the FHIR export facade only. The implementation generates FHIR R4 Bundles on demand through `GET /v1/assessments/{assessment_id}/fhir`, records `fhir_bundle_exported` and `fhir_export_failed` audit events, and leaves Phase 2 REST facade and Phase 3 FHIR-native persistence as future work.
```

- [ ] **Step 4: Run focused FHIR and API verification**

Run:

```bash
pytest tests/test_fhir_export.py tests/test_api.py::ApiTests::test_assessment_flow_api tests/test_d4_1_acceptance.py::test_d4_1_8_fhir_export_contains_traceability_bundle -q
```

Expected: PASS for all selected tests.

- [ ] **Step 5: Run the full test suite**

Run:

```bash
pytest -q
```

Expected: PASS. If unrelated tests fail, capture the exact failing test names and error messages before deciding whether the failure is caused by the FHIR change.

- [ ] **Step 6: Check final git status**

Run:

```bash
git status --short
```

Expected: only files changed by the FHIR implementation are listed before the final commit.

- [ ] **Step 7: Commit Task 6**

```bash
git add tests/test_d4_1_acceptance.py docs/superpowers/specs/2026-06-11-fhir-implementation-design.md
git commit -m "test(fhir): cover bundle export acceptance"
```

- [ ] **Step 8: Summarize implementation state**

Prepare a short handoff note containing:

```text
Implemented Phase 1 FHIR export facade.
Endpoint: GET /v1/assessments/{assessment_id}/fhir
FHIR version: R4 only
Verification: pytest -q
Future work: /fhir/metadata, read/search endpoints, FHIR-native persistence
```

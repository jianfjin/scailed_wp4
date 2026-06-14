"""D4.1 Acceptance Test Suite — one test per D4.1 requirement.

Tests import from actual pathfinder services (not mocks).
Tests depending on R3 (audit events middleware) or R4 (Docker boot)
are marked with @pytest.mark.skip.
"""

from __future__ import annotations

import statistics
import time

import pytest
from fastapi.testclient import TestClient

import pathfinder.api.main as api_main
from pathfinder.api.main import app
from pathfinder.services.assessment_service import AssessmentService

# ── Shared fixtures / helpers ────────────────────────────────────────

BASE_ANSWERS = {
    "governance_maturity": 2,
    "data_maturity": 2,
    "compliance_maturity": 2,
    "capabilities": ["secure-processing"],
    "missing_capabilities": ["data-catalog"],
    "regulatory_flags": ["gdpr-review-needed"],
}

THREE_READY_STAKEHOLDERS = (
    "biotech-sme",
    "health-data-access-body",
    "research-infrastructure",
)


def _full_flow(service: AssessmentService, stakeholder_type: str) -> dict[str, object]:
    """Run create → answers → recommend → report and return the report."""
    session = service.create_session(stakeholder_type, "secondary-use-readiness")
    assessment_id = str(session["assessment_id"])
    service.submit_answers(assessment_id, BASE_ANSWERS)
    service.generate_recommendation(assessment_id)
    return service.report(assessment_id)


# ── D4.1.1 ──────────────────────────────────────────────────────────

def test_d4_1_1_stakeholder_questionnaires() -> None:
    """Verify all five stakeholder types have complete questionnaires.

    D4.1 criterion: Five stakeholder types each have complete
    questionnaires (≥1 question, target_scenarios present).
    """
    service = AssessmentService()

    types = service.stakeholder_types()
    assert len(types) >= 5, f"expected ≥5 stakeholder types, got {len(types)}: {types}"

    for stakeholder_type in types:
        questionnaire = service.get_questionnaire(stakeholder_type)
        questions = questionnaire.get("questions", [])
        target_scenarios = questionnaire.get("target_scenarios", [])
        assert isinstance(questions, list), (
            f"{stakeholder_type}: questions must be a list"
        )
        assert len(questions) >= 1, (
            f"{stakeholder_type}: expected ≥1 question, got {len(questions)}"
        )
        assert target_scenarios, (
            f"{stakeholder_type}: target_scenarios must not be empty"
        )


# ── D4.1.2 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("stakeholder_type", THREE_READY_STAKEHOLDERS)
def test_d4_1_2_three_stakeholders_ready(stakeholder_type: str) -> None:
    """Verify three stakeholders produce ready recommendations.

    D4.1 criterion: Three stakeholder/scenario fixtures produce
    ready recommendations with traceability data.
    """
    service = AssessmentService()
    session = service.create_session(stakeholder_type, "secondary-use-readiness")
    assessment_id = str(session["assessment_id"])
    service.submit_answers(assessment_id, BASE_ANSWERS)
    recommendation = service.generate_recommendation(assessment_id)

    assert recommendation["status"] == "ready", (
        f"{stakeholder_type}: expected status 'ready', "
        f"got '{recommendation['status']}'"
    )
    # Traceability: answer_ids, roadmap_node_ids, triggered_rule_ids
    trace = recommendation.get("trace", {})  # type: ignore[union-attr]
    assert isinstance(trace, dict), f"{stakeholder_type}: trace must be a dict"
    assert trace.get("answer_ids"), (
        f"{stakeholder_type}: trace.answer_ids must not be empty"
    )
    assert trace.get("roadmap_node_ids"), (
        f"{stakeholder_type}: trace.roadmap_node_ids must not be empty"
    )
    assert trace.get("triggered_rule_ids"), (
        f"{stakeholder_type}: trace.triggered_rule_ids must not be empty"
    )


# ── D4.1.3 ──────────────────────────────────────────────────────────

def test_d4_1_3_rule_tests_match_expected() -> None:
    """Verify demo rule tests match expected outcomes.

    D4.1 criterion: Demo rule tests match expected outcomes.
    The RuleLoader runs embedded tests during load_bundle() and
    raises RuleValidationError on mismatch, so a successful
    AssessmentService init implies rule tests pass.
    """
    service = AssessmentService()
    assert service.rules, "expected rules to be loaded"
    assert len(service.rules) >= 1, "expected at least one active rule"

    # Explicitly verify the known rule bundle tests.
    # The demo bundle defines one test expecting these rule IDs:
    expected_ids = {"WP8-GDPR-REVIEW-001", "DATA-CATALOG-GAP-003"}
    active_ids = {r.rule_id for r in service.rules}
    for expected in expected_ids:
        assert expected in active_ids, (
            f"expected rule '{expected}' is not in active rules: {sorted(active_ids)}"
        )


# ── D4.1.4 ──────────────────────────────────────────────────────────

def test_d4_1_4_report_includes_all_sections() -> None:
    """Verify report includes readiness, path, blockers, trace,
    warnings, and disclaimer.

    D4.1 criterion: Report includes readiness_snapshot,
    recommended_path (with blockers + trace), missing_data_warnings,
    and disclaimer.
    """
    service = AssessmentService()
    report = _full_flow(service, "biotech-sme")

    # Top-level sections
    assert "readiness_snapshot" in report, "report missing readiness_snapshot"
    assert "recommended_path" in report, "report missing recommended_path"
    assert "missing_data_warnings" in report, "report missing missing_data_warnings"
    assert "disclaimer" in report, "report missing disclaimer"

    # Recommended path sub-sections
    path = report["recommended_path"]
    assert isinstance(path, dict), "recommended_path must be a dict"
    assert "blockers" in path, "recommended_path missing blockers"
    assert "trace" in path, "recommended_path missing trace"

    # Warnings
    warnings = report["missing_data_warnings"]
    assert isinstance(warnings, list) and len(warnings) >= 1, (
        "missing_data_warnings must be a non-empty list"
    )

    # Disclaimer
    disclaimer = report["disclaimer"]
    assert isinstance(disclaimer, str) and len(disclaimer) > 0, (
        "disclaimer must be a non-empty string"
    )


# ── D4.1.5 ──────────────────────────────────────────────────────────

def test_d4_1_5_full_api_flow_with_audit() -> None:
    """Full API flow: create → answers → recommend → report → audit events.

    D4.1 criterion: Full API flow produces audit events.
    """
    api_main._service = None
    client = TestClient(app)
    headers = {"Authorization": "Bearer demo-token"}

    session = client.post(
        "/v1/assessments",
        headers=headers,
        json={
            "stakeholder_type": "biotech-sme",
            "target_scenario": "secondary-use-readiness",
        },
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

    report_response = client.get(f"/v1/assessments/{assessment_id}/report", headers=headers)
    assert report_response.status_code == 200
    report = report_response.json()

    # Audit chain must be valid
    assert report.get("audit_chain_valid") is True

    # At minimum: session_created, answers_submitted, recommendation_generated,
    # report_exported
    events = api_main._get_service().audit_log.events()
    event_types = {event.event_type for event in events}
    required_events = {
        "assessment_session_created",
        "answers_submitted",
        "recommendation_generated",
        "report_exported",
    }
    missing = required_events - event_types
    assert not missing, f"missing audit events: {missing}"


# ── D4.1.6 ──────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Informational: p95 latency benchmark (not a gate)")
def test_d4_1_6_p95_latency_at_demo_scale() -> None:
    """P95 recommendation latency under demo-scale threshold.

    D4.1 criterion: p95 latency at demo scale meets threshold.
    Skipped as informational — not currently a CI gate.
    """
    durations: list[float] = []
    for _ in range(30):
        service = AssessmentService()
        session = service.create_session("biotech-sme", "secondary-use-readiness")
        assessment_id = str(session["assessment_id"])
        service.submit_answers(assessment_id, BASE_ANSWERS)
        start = time.perf_counter()
        service.generate_recommendation(assessment_id)
        durations.append(time.perf_counter() - start)

    p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
    assert p95 < 0.5, f"p95 latency {p95:.4f}s exceeds 0.5s threshold"


# ── D4.1.7 ──────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Depends on R4: Docker Compose boot and integration smoke")
def test_d4_1_7_docker_boot_integration() -> None:
    """Docker Compose boot path verified with integration smoke.

    D4.1 criterion: Docker Compose boot path verified.
    Skipped until R4 post-deploy integration smoke test is implemented.
    """
    # Would verify: docker compose up → health endpoint → full flow
    pass


# ── D4.1.8 ──────────────────────────────────────────────────────────

def test_d4_1_8_fhir_export_contains_traceability_bundle() -> None:
    """FHIR export returns a traceable Bundle for a completed assessment.

    D4.1 criterion: FHIR Bundle includes core assessment resources and
    stable intra-Bundle references for traceability.
    """
    api_main._service = AssessmentService()
    client = TestClient(app)
    headers = {"Authorization": "Bearer demo-token"}

    session = client.post(
        "/v1/assessments",
        headers=headers,
        json={
            "stakeholder_type": "biotech-sme",
            "target_scenario": "secondary-use-readiness",
        },
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

    response = client.get(f"/v1/assessments/{assessment_id}/fhir", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/fhir+json"
    bundle = response.json()
    assert bundle["resourceType"] == "Bundle"

    resources = [entry["resource"] for entry in bundle["entry"]]
    resource_types = {resource["resourceType"] for resource in resources}
    required_resource_types = {
        "Questionnaire",
        "QuestionnaireResponse",
        "Organization",
        "Group",
        "Observation",
        "GuidanceResponse",
        "CarePlan",
        "Provenance",
        "AuditEvent",
    }
    assert required_resource_types <= resource_types

    resources_by_ref = {
        f"{resource['resourceType']}/{resource['id']}": resource
        for resource in resources
    }
    resources_by_type: dict[str, list[dict[str, object]]] = {}
    for resource in resources:
        resources_by_type.setdefault(str(resource["resourceType"]), []).append(resource)

    references: set[str] = set()

    def collect_references(value: object) -> None:
        if isinstance(value, dict):
            reference_value = value.get("reference")
            if isinstance(reference_value, str):
                references.add(reference_value)
            for nested_value in value.values():
                collect_references(nested_value)
        elif isinstance(value, list):
            for item in value:
                collect_references(item)

    collect_references(bundle)
    exported_resource_types = {
        resource_ref.split("/", 1)[0]
        for resource_ref in resources_by_ref
    }
    internal_references = {
        reference_value
        for reference_value in references
        if reference_value.split("/", 1)[0] in exported_resource_types
    }
    unresolved_references = internal_references - set(resources_by_ref)
    assert not unresolved_references

    questionnaire = resources_by_type["Questionnaire"][0]
    questionnaire_response = resources_by_type["QuestionnaireResponse"][0]
    organization = resources_by_type["Organization"][0]
    group = resources_by_type["Group"][0]
    readiness_observation = next(
        resource
        for resource in resources_by_type["Observation"]
        if str(resource["id"]).startswith("readiness-")
    )
    guidance_response = resources_by_type["GuidanceResponse"][0]
    care_plan = resources_by_type["CarePlan"][0]
    provenance = resources_by_type["Provenance"][0]

    questionnaire_ref = f"Questionnaire/{questionnaire['id']}"
    organization_ref = f"Organization/{organization['id']}"
    group_ref = f"Group/{group['id']}"
    observation_ref = f"Observation/{readiness_observation['id']}"
    guidance_response_ref = f"GuidanceResponse/{guidance_response['id']}"
    care_plan_ref = f"CarePlan/{care_plan['id']}"

    assert questionnaire_response["subject"]["reference"] == organization_ref
    assert questionnaire_response["questionnaire"] == questionnaire_ref
    assert {"reference": organization_ref} in readiness_observation["focus"]
    assert guidance_response["result"]["reference"] == care_plan_ref
    assert guidance_response["subject"] == {"reference": group_ref}
    assert care_plan["subject"]["reference"] == group_ref
    provenance_targets = {
        target["reference"]
        for target in provenance["target"]
    }
    assert {
        guidance_response_ref,
        care_plan_ref,
        observation_ref,
    } <= provenance_targets


def test_d4_1_9_derived_assessment_uses_wp2_wp3_without_client_answers() -> None:
    api_main._service = AssessmentService()
    client = TestClient(app)
    headers = {"Authorization": "Bearer demo-token"}

    session = client.post(
        "/v1/assessments",
        headers=headers,
        json={
            "stakeholder_type": "academic-spinout-001",
            "target_scenario": "secondary-use-readiness",
        },
    )
    assert session.status_code == 200
    assessment_id = session.json()["assessment_id"]

    recommendation = client.post(
        f"/v1/assessments/{assessment_id}/recommendations",
        headers=headers,
    )
    assert recommendation.status_code == 200

    report_response = client.get(f"/v1/assessments/{assessment_id}/report", headers=headers)
    assert report_response.status_code == 200
    report = report_response.json()
    snapshot = report["readiness_snapshot"]

    assert snapshot["derivation_mode"] == "wp2_wp3"
    assert snapshot["source_wp2_stakeholder_id"] == "academic-spinout-001"
    assert snapshot["source_wp2_snapshot_version"]
    assert snapshot["source_wp3_snapshot_version"]
    assert snapshot["maturity_scores"]
    assert set(snapshot["capabilities"]) == {"federated-analytics", "legal-basis", "secure-processing"}
    assert "data-catalog" in snapshot["missing_capabilities"]
    assert "gdpr-review-needed" in snapshot["regulatory_flags"]
    assert report["recommended_path"]["trace"]["roadmap_node_ids"]

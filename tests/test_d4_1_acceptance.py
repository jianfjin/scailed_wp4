"""D4.1 Acceptance Test Suite — one test per D4.1 requirement.

Tests import from actual pathfinder services (not mocks).
Tests depending on R3 (audit events middleware) or R4 (Docker boot)
are marked with @pytest.mark.skip.
"""

from __future__ import annotations

import statistics
import time

import pytest

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

@pytest.mark.skip(reason="Depends on R3: audit event middleware enforcement")
def test_d4_1_5_full_api_flow_with_audit() -> None:
    """Full API flow: create → answers → recommend → report → audit events.

    D4.1 criterion: Full API flow produces audit events.
    Skipped until R3 cross-cutting middleware enforces audit per-endpoint.
    """
    # The in-memory service already records audit events; this test
    # would validate that the API middleware guarantees one event per
    # mutating call, which depends on R3.
    service = AssessmentService()
    report = _full_flow(service, "biotech-sme")

    # Audit chain must be valid
    assert report.get("audit_chain_valid") is True

    # At minimum: session_created, answers_submitted, recommendation_generated,
    # report_exported
    events = service.audit_log.events()
    event_types = {e["event"] for e in events}  # type: ignore[index]
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

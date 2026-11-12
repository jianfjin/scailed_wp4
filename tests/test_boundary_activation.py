"""Acceptance tests for validated snapshot activation and assessment pinning."""
import copy
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pathfinder.adapters.upstream import UpstreamClient
from pathfinder.services.assessment_service import AssessmentService
from scripts.validate_contracts import canonical_checksum

SAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "samples"


def snapshot_set():
    return [json.loads((SAMPLES / f"{name}.snapshot.json").read_text()) for name in (
        "wp2-taxonomy", "wp4-questionnaire", "wp3-roadmap", "wp8-rulebundle")]


@pytest.fixture
def service():
    return AssessmentService(UpstreamClient())


def answers():
    return {"pf:wp4:question:biotech-sme-1": "yes",
            "pf:wp4:question:biotech-sme-2": 3,
            "pf:wp4:question:biotech-sme-3": 3,
            "pf:wp4:question:biotech-sme-4": 3,
            "pf:wp4:question:biotech-sme-capabilities": ["legal-basis"]}


def test_activation_rejects_invalid_set_and_keeps_previous(service):
    snapshots = snapshot_set()
    service.activate_boundary_snapshots(snapshots)
    previous = service.active_boundary.snapshot_ids
    invalid = copy.deepcopy(snapshots)
    invalid[-1]["payload"]["tests"][0]["expect"]["outcome"] = "not-triggered"
    invalid[-1]["manifest"]["items_checksum"] = canonical_checksum(invalid[-1]["payload"])
    with pytest.raises(ValueError, match="rule test"):
        service.activate_boundary_snapshots(invalid)
    assert service.active_boundary.snapshot_ids == previous


def test_session_pins_snapshot_set_and_exposes_unverified(service):
    snapshots = snapshot_set()
    for rule in snapshots[-1]["payload"]["rules"]:
        rule["status"] = "verified"
    for reference in snapshots[-1]["payload"]["references"]:
        reference["status"] = "in-force"
    snapshots[-1]["manifest"]["items_checksum"] = canonical_checksum(snapshots[-1]["payload"])
    service.activate_boundary_snapshots(snapshots)
    stakeholder = snapshots[1]["payload"]["stakeholder_type"]
    scenario = snapshots[1]["payload"]["target_scenarios"][0]
    old = service.create_session(stakeholder, scenario)["assessment_id"]
    changed = copy.deepcopy(snapshots)
    changed[-1]["manifest"]["snapshot_id"] = str(uuid.uuid4())
    changed[-1]["payload"]["rules"][0]["status"] = "provisional"
    changed[-1]["manifest"]["items_checksum"] = canonical_checksum(changed[-1]["payload"])
    service.activate_boundary_snapshots(changed)
    new = service.create_session(stakeholder, scenario)["assessment_id"]
    for session in (old, new):
        service.submit_answers(session, answers())
    old_result = service.generate_recommendation(old)
    new_result = service.generate_recommendation(new)
    assert old_result["trace"]["snapshot_ids"]["pf.rulebundle.v1"] == snapshots[-1]["manifest"]["snapshot_id"]
    assert new_result["trace"]["snapshot_ids"]["pf.rulebundle.v1"] == changed[-1]["manifest"]["snapshot_id"]
    assert old_result["regulatory_status"] == "verified"
    assert new_result["regulatory_status"] == "unverified"
    assert new_result["status"] == "degraded"


def test_boundary_import_api_requires_admin_and_activates(service, monkeypatch):
    from pathfinder.api import main
    monkeypatch.setattr(main, "_service", service)
    client = TestClient(main.app)
    payload = {"snapshots": snapshot_set()}
    assert client.post("/v1/admin/import", json=payload, headers={"Authorization": "Bearer demo-token"}).status_code == 403
    response = client.post("/v1/admin/import", json=payload, headers={"Authorization": "Bearer admin-token"})
    assert response.status_code == 200, response.text
    assert response.json()["accepted"]
    assert any(e.event_type == "boundary_snapshots_activated" for e in service.audit_log.events())
    demo = {"Authorization": "Bearer demo-token"}
    session = client.post("/v1/assessments", headers=demo, json={
        "stakeholder_type": payload["snapshots"][1]["payload"]["stakeholder_type"],
        "target_scenario": payload["snapshots"][1]["payload"]["target_scenarios"][0],
    })
    assert session.status_code == 200, session.text
    session_id = session.json()["assessment_id"]
    assert session.json()["snapshot_ids"]["pf.rulebundle.v1"] == payload["snapshots"][-1]["manifest"]["snapshot_id"]
    assert client.post(f"/v1/assessments/{session_id}/recommendations", headers=demo).status_code == 400
    assert client.post(f"/v1/assessments/{session_id}/answers/batch", headers=demo, json={"answers": answers()}).status_code == 200
    recommendation = client.post(f"/v1/assessments/{session_id}/recommendations", headers=demo)
    assert recommendation.status_code == 200, recommendation.text
    assert recommendation.json()["regulatory_status"] == "unverified"
    assert recommendation.json()["trace"]["evaluation_date"] == session.json()["evaluation_date"]
    report = client.get(f"/v1/assessments/{session_id}/report?format=html", headers=demo)
    assert report.status_code == 200, report.text
    assert "unverified" in report.text.lower()


def test_snapshot_identity_cannot_be_reused_for_different_content(service):
    snapshots = snapshot_set()
    service.activate_boundary_snapshots(snapshots)
    modified = copy.deepcopy(snapshots)
    modified[-1]["payload"]["rules"][0]["action"]["title"] = "Changed"
    modified[-1]["manifest"]["items_checksum"] = canonical_checksum(modified[-1]["payload"])
    with pytest.raises(ValueError, match="already used"):
        service.activate_boundary_snapshots(modified)


def test_ineffective_rule_is_not_applied_and_marks_unverified(service):
    snapshots = snapshot_set()
    snapshots[-1]["payload"]["rules"][1]["effective_from"] = "2999-01-01"
    snapshots[-1]["manifest"]["items_checksum"] = canonical_checksum(snapshots[-1]["payload"])
    service.activate_boundary_snapshots(snapshots)
    session = service.create_session(snapshots[1]["payload"]["stakeholder_type"], snapshots[1]["payload"]["target_scenarios"][0])
    submitted = answers()
    submitted["pf:wp4:question:biotech-sme-capabilities"] = []
    service.submit_answers(session["assessment_id"], submitted)
    result = service.generate_recommendation(session["assessment_id"])
    assert "pf:wp8:rule:missing-legal-basis-block" not in result["trace"]["triggered_rule_ids"]
    assert result["regulatory_status"] == "unverified"
    assert any("effective dates" in warning for warning in result["warnings"])


def test_missing_regulatory_reference_marks_rule_unverified(service):
    snapshots = snapshot_set()
    snapshots[-1]["payload"]["rules"][0]["compliance_refs"] = ["pf:wp8:reg:unknown"]
    snapshots[-1]["manifest"]["items_checksum"] = canonical_checksum(snapshots[-1]["payload"])
    service.activate_boundary_snapshots(snapshots)
    session = service.create_session(snapshots[1]["payload"]["stakeholder_type"], snapshots[1]["payload"]["target_scenarios"][0])
    service.submit_answers(session["assessment_id"], answers())
    result = service.generate_recommendation(session["assessment_id"])
    assert result["regulatory_status"] == "unverified"
    assert next(rule for rule in result["triggered_rules"] if rule["rule_id"] == "pf:wp8:rule:secondary-use-eligibility")["regulatory_status"] == "unverified"


def test_concurrent_activation_and_session_creation_keep_whole_generations(service):
    first = snapshot_set()
    second = copy.deepcopy(first)
    second[-1]["manifest"]["snapshot_id"] = str(uuid.uuid4())
    second[-1]["payload"]["rules"][0]["action"]["title"] = "New generation"
    second[-1]["manifest"]["items_checksum"] = canonical_checksum(second[-1]["payload"])
    service.activate_boundary_snapshots(first)
    stakeholder = first[1]["payload"]["stakeholder_type"]
    scenario = first[1]["payload"]["target_scenarios"][0]

    def create_or_activate(index):
        if index % 3 == 0:
            service.activate_boundary_snapshots(second if index % 2 else first)
            return None
        return service.create_session(stakeholder, scenario)["assessment_id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        sessions = list(pool.map(create_or_activate, range(15)))
    expected = {first[-1]["manifest"]["snapshot_id"]: first[-1]["payload"]["rules"][0]["action"]["title"],
                second[-1]["manifest"]["snapshot_id"]: "New generation"}
    for session_id in filter(None, sessions):
        service.submit_answers(session_id, answers())
        result = service.generate_recommendation(session_id)
        bundle_id = result["trace"]["snapshot_ids"]["pf.rulebundle.v1"]
        rule = next(r for r in result["triggered_rules"] if r["rule_id"] == "pf:wp8:rule:secondary-use-eligibility")
        assert rule["action"]["title"] == expected[bundle_id]
    assert service.audit_log.verify_chain()

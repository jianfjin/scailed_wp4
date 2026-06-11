"""FHIR Bundle export assembly for Pathfinder assessments."""

from __future__ import annotations

from typing import Any

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
    audit_events: Any,
    fhir_version: str = "R4",
) -> dict[str, Any]:
    require_r4(fhir_version)

    session = report.get("session", {})
    if not isinstance(session, dict):
        session = {}
    assessment_id = str(session.get("assessment_id", "assessment"))

    resources = [
        questionnaire_to_fhir(questionnaire),
        questionnaire_response_from_session(session, questionnaire),
        organization_from_session(session),
        readiness_observation_from_report(report),
        guidance_response_from_report(report),
        care_plan_from_report(report),
        provenance_from_report(report),
    ]
    resources.extend(
        audit_event_to_fhir(event, assessment_id)
        for event in audit_events
    )

    return create_bundle(fhir_id("bundle", assessment_id), resources)

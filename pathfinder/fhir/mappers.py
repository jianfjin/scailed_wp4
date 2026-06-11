"""Pure FHIR R4 mappers for Pathfinder assessment inputs."""

from __future__ import annotations

from typing import Any

from pathfinder.fhir.resources import codeable_concept, coding, fhir_id, reference


def _questionnaire_version_suffix(version: object) -> str:
    value = str(version or "v1").strip()
    return value.rsplit("-", 1)[-1] if value else "v1"


def _questionnaire_id(questionnaire: dict[str, Any]) -> str:
    return fhir_id(
        "questionnaire",
        questionnaire.get("stakeholder_type", "unknown"),
        _questionnaire_version_suffix(questionnaire.get("version")),
    )


def _organization_id(session: dict[str, Any]) -> str:
    return fhir_id("organization", session.get("assessment_id", "assessment"))


def _question_type_to_fhir(question_type: str) -> str:
    return {
        "numeric": "integer",
        "single_choice": "choice",
        "multi_choice": "choice",
        "text": "text",
    }.get(str(question_type), "text")


def _answer_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, bool):
        return [{"valueBoolean": value}]
    if isinstance(value, int):
        return [{"valueInteger": value}]
    if isinstance(value, list):
        return [{"valueString": str(item)} for item in value]
    return [{"valueString": str(value)}]


def _choice_coding(value: Any) -> dict[str, str]:
    text = str(value)
    return coding(text, text)


def _choice_answer_value(value: Any) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    return [{"valueCoding": _choice_coding(item)} for item in values]


def _answer_value_for_question(value: Any, question: dict[str, Any]) -> list[dict[str, Any]]:
    question_type = str(question.get("question_type", "text"))
    if question_type in {"single_choice", "multi_choice"}:
        return _choice_answer_value(value)
    return _answer_value(value)


def questionnaire_to_fhir(questionnaire: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for question in questionnaire.get("questions", []):
        question_type = str(question.get("question_type", "text"))
        item: dict[str, Any] = {
            "linkId": str(question.get("question_id", "")),
            "text": str(question.get("label", "")),
            "type": _question_type_to_fhir(question_type),
            "required": bool(question.get("required", True)),
        }
        if question_type == "multi_choice":
            item["repeats"] = True
        options = question.get("options") or []
        if options:
            item["answerOption"] = [
                {"valueCoding": _choice_coding(option)}
                for option in options
            ]
        items.append(item)

    return {
        "resourceType": "Questionnaire",
        "id": _questionnaire_id(questionnaire),
        "status": "active",
        "title": str(questionnaire.get("title", "Pathfinder assessment")),
        "subjectType": ["Organization"],
        "item": items,
    }


def organization_from_session(session: dict[str, Any]) -> dict[str, Any]:
    assessment_id = str(session.get("assessment_id", "assessment"))
    stakeholder_type = str(session.get("stakeholder_type", "unknown"))
    return {
        "resourceType": "Organization",
        "id": _organization_id(session),
        "name": f"Pathfinder assessment organization {assessment_id}",
        "type": [codeable_concept(stakeholder_type, stakeholder_type)],
    }


def questionnaire_response_from_session(
    session: dict[str, Any],
    questionnaire: dict[str, Any],
) -> dict[str, Any]:
    questionnaire_resource = questionnaire_to_fhir(questionnaire)
    answers = session.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("assessment has no submitted answers")

    items: list[dict[str, Any]] = []
    for question in questionnaire.get("questions", []):
        question_id = str(question.get("question_id", ""))
        if question_id not in answers:
            continue
        items.append({
            "linkId": question_id,
            "answer": _answer_value_for_question(answers[question_id], question),
        })

    return {
        "resourceType": "QuestionnaireResponse",
        "id": fhir_id(
            "questionnaire-response",
            session.get("assessment_id", "assessment"),
        ),
        "status": "completed",
        "questionnaire": "Questionnaire/" + str(questionnaire_resource["id"]),
        "subject": reference("Organization", _organization_id(session)),
        "item": items,
    }


def readiness_observation_from_report(report: dict[str, Any]) -> dict[str, Any]:
    snapshot = report.get("readiness_snapshot")
    if not isinstance(snapshot, dict) or not snapshot:
        raise ValueError("report has no readiness_snapshot")

    session = report.get("session", {})
    if not isinstance(session, dict):
        session = {}

    components: list[dict[str, Any]] = []
    maturity_scores = snapshot.get("maturity_scores", {})
    if isinstance(maturity_scores, dict):
        for dimension, score in sorted(maturity_scores.items()):
            component: dict[str, Any] = {
                "code": codeable_concept(f"maturity-{dimension}", f"Maturity {dimension}"),
            }
            if isinstance(score, int):
                component["valueInteger"] = score
            else:
                component["valueString"] = str(score)
            components.append(component)

    for capability in snapshot.get("capabilities", []) or []:
        components.append(
            {
                "code": codeable_concept("capability", "Capability"),
                "valueString": str(capability),
            }
        )
    for capability in snapshot.get("missing_capabilities", []) or []:
        components.append(
            {
                "code": codeable_concept("missing-capability", "Missing capability"),
                "valueString": str(capability),
            }
        )
    for flag in snapshot.get("regulatory_flags", []) or []:
        components.append(
            {
                "code": codeable_concept("regulatory-flag", "Regulatory flag"),
                "valueString": str(flag),
            }
        )

    if "confidence" in snapshot:
        components.append(
            {
                "code": codeable_concept("confidence", "Confidence"),
                "valueQuantity": {"value": snapshot["confidence"], "unit": "score"},
            }
        )
    for warning in snapshot.get("confidence_warnings", []) or []:
        components.append(
            {
                "code": codeable_concept("confidence-warning", "Confidence warning"),
                "valueString": str(warning),
            }
        )

    return {
        "resourceType": "Observation",
        "id": fhir_id("readiness", session.get("assessment_id", "assessment")),
        "status": "final",
        "code": codeable_concept("secondary-use-readiness", "Secondary use readiness"),
        "focus": [reference("Organization", _organization_id(session))],
        "component": components,
    }


def _report_session(report: dict[str, Any]) -> dict[str, Any]:
    session = report.get("session", {})
    return session if isinstance(session, dict) else {}


def _assessment_id_from_report(report: dict[str, Any]) -> str:
    return str(_report_session(report).get("assessment_id", "assessment"))


def _recommendation_from_report(report: dict[str, Any]) -> dict[str, Any]:
    recommendation = report.get("recommended_path", {})
    return recommendation if isinstance(recommendation, dict) else {}


def _trace_from_report(report: dict[str, Any]) -> dict[str, Any]:
    trace = _recommendation_from_report(report).get("trace", {})
    return trace if isinstance(trace, dict) else {}


def _metadata_extension(name: str, value: Any) -> dict[str, str]:
    return {
        "url": f"https://scailed.eu/fhir/pathfinder/StructureDefinition/{name}",
        "valueString": str(value),
    }


def guidance_response_from_report(report: dict[str, Any]) -> dict[str, Any]:
    assessment_id = _assessment_id_from_report(report)
    recommendation = _recommendation_from_report(report)
    status = "success" if recommendation.get("status") == "ready" else "data-required"

    return {
        "resourceType": "GuidanceResponse",
        "id": fhir_id("guidance-response", assessment_id),
        "status": status,
        "moduleUri": "https://scailed.eu/fhir/pathfinder/PlanDefinition/secondary-use-readiness",
        "subject": reference("Organization", fhir_id("organization", assessment_id)),
        "result": reference("CarePlan", fhir_id("care-plan", assessment_id)),
    }


def care_plan_from_report(report: dict[str, Any]) -> dict[str, Any]:
    assessment_id = _assessment_id_from_report(report)
    recommendation = _recommendation_from_report(report)
    next_steps = recommendation.get("next_steps", [])
    if not isinstance(next_steps, list):
        next_steps = []

    activities: list[dict[str, Any]] = []
    for step in next_steps:
        if not isinstance(step, dict):
            continue
        node_id = str(step.get("node_id") or "next-step")
        label = str(step.get("label") or node_id)
        detail: dict[str, Any] = {
            "kind": "Task",
            "code": codeable_concept(node_id, label),
            "status": "not-started",
        }
        if step.get("description"):
            detail["description"] = str(step["description"])
        activities.append({"detail": detail})

    if not activities:
        activities.append({
            "detail": {
                "kind": "Task",
                "code": codeable_concept("review-readiness-report", "Review readiness report"),
                "status": "not-started",
            }
        })

    return {
        "resourceType": "CarePlan",
        "id": fhir_id("care-plan", assessment_id),
        "status": "active" if recommendation.get("status") == "ready" else "draft",
        "intent": "plan",
        "title": "Pathfinder readiness recommendation",
        "description": str(report.get("disclaimer", "Pathfinder assessment recommendation")),
        "supportingInfo": [
            reference("Organization", fhir_id("organization", assessment_id)),
            reference("Observation", fhir_id("readiness", assessment_id)),
        ],
        "activity": activities,
    }


def provenance_from_report(report: dict[str, Any]) -> dict[str, Any]:
    assessment_id = _assessment_id_from_report(report)
    trace = _trace_from_report(report)
    extensions = [
        _metadata_extension(name, trace[name])
        for name in ("schema_version", "rule_version", "upstream_snapshot_version")
        if name in trace
    ]

    entity: dict[str, Any] = {
        "role": "source",
        "what": {"display": "Pathfinder recommendation trace"},
    }
    if extensions:
        entity["extension"] = extensions

    return {
        "resourceType": "Provenance",
        "id": fhir_id("provenance", assessment_id),
        "target": [
            reference("GuidanceResponse", fhir_id("guidance-response", assessment_id)),
            reference("CarePlan", fhir_id("care-plan", assessment_id)),
            reference("Observation", fhir_id("readiness", assessment_id)),
        ],
        "recorded": "1970-01-01T00:00:00+00:00",
        "agent": [{"who": {"display": "Pathfinder AssessmentService"}}],
        "entity": [entity],
    }


def _event_attr(event: Any, name: str, default: Any = None) -> Any:
    if isinstance(event, dict):
        return event.get(name, default)
    return getattr(event, name, default)


def audit_event_to_fhir(event: Any, assessment_id: str) -> dict[str, Any]:
    event_type = str(_event_attr(event, "event_type", "audit-event"))
    event_hash = str(_event_attr(event, "event_hash", ""))
    event_data = _event_attr(event, "event_data", {})
    if not isinstance(event_data, dict):
        event_data = {}

    extensions: list[dict[str, str]] = []
    for name in ("prev_hash", "event_hash", "ip_hash", "user_agent_hash"):
        value = _event_attr(event, name)
        if value:
            extensions.append(_metadata_extension(name, value))

    audit_event: dict[str, Any] = {
        "resourceType": "AuditEvent",
        "id": fhir_id("audit-event", assessment_id, event_type, event_hash[:12]),
        "type": coding(event_type, event_type),
        "action": "E",
        "recorded": str(_event_attr(event, "timestamp", "1970-01-01T00:00:00+00:00")),
        "outcome": "0",
        "agent": [{"who": {"display": "Pathfinder AssessmentService"}}],
        "source": {"observer": {"display": "Pathfinder"}},
        "entity": [{"what": reference("Bundle", fhir_id("bundle", assessment_id))}],
    }
    if event_data:
        audit_event["subtype"] = [
            coding(str(key), str(value))
            for key, value in sorted(event_data.items())
            if key not in {"ip", "user_agent"}
        ]
    if extensions:
        audit_event["extension"] = extensions
    return audit_event


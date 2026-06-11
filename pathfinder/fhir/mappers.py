"""Pure FHIR R4 mappers for Pathfinder assessment inputs."""

from __future__ import annotations

from typing import Any

from pathfinder.fhir.resources import codeable_concept, fhir_id, reference


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


def _choice_answer_value(value: Any) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    return [
        {"valueCoding": {"code": str(item), "display": str(item)}}
        for item in values
    ]


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
                {"valueCoding": {"code": str(option), "display": str(option)}}
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
        for dimension, score in maturity_scores.items():
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
                "valueDecimal": snapshot["confidence"],
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
        "subject": reference("Organization", _organization_id(session)),
        "component": components,
    }

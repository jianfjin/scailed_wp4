"""Translate versioned WP boundary data into the existing domain model."""

from pathfinder.core.models import Question, Questionnaire, QuestionType


def questionnaire_from_snapshots(taxonomy: dict, questionnaire: dict) -> Questionnaire:
    """Map taxonomy dimension IDs and namespaced question IDs to runtime state."""
    if questionnaire["manifest"]["dependencies"].get("pf.taxonomy.v1") != taxonomy["manifest"]["snapshot_id"]:
        raise ValueError("questionnaire taxonomy dependency does not match supplied snapshot")
    dimensions = {item["dimension_id"]: item["state_key"] for item in taxonomy["payload"]["dimensions"]}
    payload = questionnaire["payload"]
    questions = []
    for item in payload["questions"]:
        if item.get("visible_if") is not None:
            raise ValueError("conditional question visibility is not supported")
        dimension = item.get("maturity_dimension")
        questions.append(Question(
            question_id=item["question_id"], label=item["label"],
            question_type=QuestionType(item["question_type"]), required=item["required"],
            options=tuple(item.get("options", [])), min_value=item.get("min_value"),
            max_value=item.get("max_value"),
            maturity_dimension=dimensions[dimension] if dimension else None,
            state_field=item.get("state_field"),
        ))
    return Questionnaire(payload["stakeholder_type"], payload["version"], payload["title"],
                         tuple(payload["target_scenarios"]), tuple(questions))

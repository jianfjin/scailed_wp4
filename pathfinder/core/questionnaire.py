"""Questionnaire validation and stakeholder-state conversion."""

from __future__ import annotations

from typing import Any

from pathfinder.core.exceptions import UnknownStakeholderTypeError, ValidationError
from pathfinder.core.models import Questionnaire, QuestionType, StakeholderState


class QuestionnaireEngine:
    def __init__(self, questionnaires: list[Questionnaire]) -> None:
        self._questionnaires = {
            questionnaire.stakeholder_type: questionnaire
            for questionnaire in questionnaires
        }

    def stakeholder_types(self) -> list[str]:
        return sorted(self._questionnaires)

    def get(self, stakeholder_type: str) -> Questionnaire:
        try:
            return self._questionnaires[stakeholder_type]
        except KeyError as exc:
            raise UnknownStakeholderTypeError(
                f"unknown stakeholder type: {stakeholder_type}"
            ) from exc

    def validate_answers(self, stakeholder_type: str, answers: dict[str, Any]) -> tuple[str, ...]:
        questionnaire = self.get(stakeholder_type)
        warnings: list[str] = []

        for question in questionnaire.questions:
            value = answers.get(question.question_id)
            missing = value in (None, "") or (value == [] and question.question_type != QuestionType.MULTI_CHOICE)
            if question.required and missing:
                raise ValidationError(f"missing required answer: {question.question_id}")

            if missing:
                warnings.append(f"missing optional answer: {question.question_id}")
                continue

            if question.question_type == QuestionType.NUMERIC:
                if not isinstance(value, int):
                    raise ValidationError(f"numeric answer required: {question.question_id}")
                if question.min_value is not None and value < question.min_value:
                    raise ValidationError(f"answer below minimum: {question.question_id}")
                if question.max_value is not None and value > question.max_value:
                    raise ValidationError(f"answer above maximum: {question.question_id}")
            elif question.question_type == QuestionType.SINGLE_CHOICE:
                if value not in question.options:
                    raise ValidationError(f"invalid option for {question.question_id}: {value}")
            elif question.question_type == QuestionType.MULTI_CHOICE:
                if not isinstance(value, list):
                    raise ValidationError(f"list answer required: {question.question_id}")
                invalid = sorted(set(value).difference(question.options))
                if invalid:
                    raise ValidationError(f"invalid options for {question.question_id}: {invalid}")

        return tuple(warnings)

    def build_state(
        self,
        stakeholder_type: str,
        target_scenario: str,
        answers: dict[str, Any],
    ) -> StakeholderState:
        questionnaire = self.get(stakeholder_type)
        warnings = list(self.validate_answers(stakeholder_type, answers))

        maturity_scores: dict[str, int] = {}
        capabilities: list[str] = []
        missing_capabilities: list[str] = []
        regulatory_flags: list[str] = []

        for question in questionnaire.questions:
            value = answers.get(question.question_id)
            if question.maturity_dimension and isinstance(value, int):
                maturity_scores[question.maturity_dimension] = value
            if question.question_id == "capabilities" and isinstance(value, list):
                capabilities.extend(value)
            if question.question_id == "missing_capabilities" and isinstance(value, list):
                missing_capabilities.extend(value)
            if question.question_id == "regulatory_flags" and isinstance(value, list):
                regulatory_flags.extend(value)

        required_count = sum(1 for question in questionnaire.questions if question.required)
        answered_required = sum(
            1
            for question in questionnaire.questions
            if question.required
            and (
                answers.get(question.question_id) not in (None, "")
                and (answers.get(question.question_id) != [] or question.question_type == QuestionType.MULTI_CHOICE)
            )
        )
        confidence = 1.0 if required_count == 0 else answered_required / required_count
        if warnings:
            confidence = max(0.0, confidence - min(0.3, 0.05 * len(warnings)))

        return StakeholderState(
            stakeholder_type=stakeholder_type,
            target_scenario=target_scenario,
            answers=dict(answers),
            maturity_scores=maturity_scores,
            capabilities=tuple(sorted(set(capabilities))),
            missing_capabilities=tuple(sorted(set(missing_capabilities))),
            regulatory_flags=tuple(sorted(set(regulatory_flags))),
            confidence=round(confidence, 3),
            confidence_warnings=tuple(warnings),
            questionnaire_version=questionnaire.version,
        )

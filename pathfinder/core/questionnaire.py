"""Questionnaire validation and stakeholder-state conversion."""

from __future__ import annotations

from pathfinder.core.contract_registry import EVIDENCE_PROFILE, LEGACY_PROFILE

from typing import Any

from pathfinder.core.exceptions import UnknownStakeholderTypeError, ValidationError
from pathfinder.core.models import CapabilityFinding, Questionnaire, QuestionType, StakeholderState


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
        if questionnaire.profile_id == EVIDENCE_PROFILE.profile_id:
            unknown = set(answers) - {q.question_id for q in questionnaire.questions}
            if unknown:
                raise ValidationError(f"unknown answer IDs: {sorted(unknown)}")

        for question in questionnaire.questions:
            value = answers.get(question.question_id)
            missing = value in (None, "") or (value == [] and question.question_type != QuestionType.MULTI_CHOICE)
            if question.required and missing:
                raise ValidationError(f"missing required answer: {question.question_id}")

            if missing:
                warnings.append(f"missing optional answer: {question.question_id}")
                continue

            if question.question_type == QuestionType.NUMERIC:
                if not isinstance(value, int) or (questionnaire.profile_id == EVIDENCE_PROFILE.profile_id and isinstance(value, bool)):
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
                if not all(isinstance(item, str) for item in value):
                    raise ValidationError(f"string options required: {question.question_id}")
                invalid = sorted(set(value).difference(question.options))
                if invalid:
                    raise ValidationError(f"invalid options for {question.question_id}: {invalid}")

            elif question.question_type == QuestionType.TEXT and questionnaire.profile_id == EVIDENCE_PROFILE.profile_id and not isinstance(value, str):
                raise ValidationError(f"text answer required: {question.question_id}")

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
            state_field = question.state_field or question.question_id
            if questionnaire.profile_id == LEGACY_PROFILE.profile_id and state_field == "capabilities" and isinstance(value, list):
                capabilities.extend(value)
            if questionnaire.profile_id == LEGACY_PROFILE.profile_id and state_field == "missing_capabilities" and isinstance(value, list):
                missing_capabilities.extend(value)
            if state_field == "regulatory_flags" and isinstance(value, list):
                regulatory_flags.extend(value)

        findings: dict[str, CapabilityFinding] = {}
        if questionnaire.profile_id == EVIDENCE_PROFILE.profile_id:
            findings = {cap: CapabilityFinding(cap) for cap in questionnaire.capability_vocabulary}

            def assert_finding(cap: str, judgment: str, answer_id: str) -> None:
                if cap not in findings:
                    raise ValidationError(f"unknown capability ID: {cap}")
                previous = findings[cap]
                if previous.judgment != "unknown" and judgment != "unknown" and previous.judgment != judgment:
                    raise ValidationError(f"contradictory capability assertion: {cap}")
                findings[cap] = CapabilityFinding(
                    cap, judgment if previous.judgment == "unknown" else previous.judgment,
                    "self_reported", tuple(sorted(set(previous.answer_ids + (answer_id,)))),
                    previous.evidence_refs,
                )

            for question in questionnaire.questions:
                value = answers.get(question.question_id)
                if question.capability_id and value not in (None, "", []):
                    assert_finding(question.capability_id, {"yes": "present", "no": "absent", "unknown": "unknown"}[value], question.question_id)
                state_field = question.state_field or question.question_id
                if state_field in ("capabilities", "missing_capabilities") and isinstance(value, list):
                    for cap in value:
                        assert_finding(cap, "present" if state_field == "capabilities" else "absent", question.question_id)
            capabilities = [cap for cap, finding in findings.items() if finding.judgment == "present"]
            missing_capabilities = [cap for cap, finding in findings.items() if finding.judgment == "absent"]

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
            capability_findings=findings,
            profile_id=questionnaire.profile_id,
        )

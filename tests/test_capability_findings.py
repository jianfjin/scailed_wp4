"""Answer assertions retain uncertainty and self-report provenance."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from pathfinder.adapters.boundary import questionnaire_from_snapshots
from pathfinder.adapters.demo_data import demo_questionnaires
from pathfinder.core.exceptions import ValidationError
from pathfinder.core.models import Question, QuestionType
from pathfinder.core.questionnaire import QuestionnaireEngine

SAMPLES = Path(__file__).resolve().parents[1] / 'contracts/samples/v2'


def questionnaire():
    taxonomy = json.loads((SAMPLES / 'wp2-taxonomy.snapshot.json').read_text())
    snapshot = json.loads((SAMPLES / 'wp4-questionnaire.snapshot.json').read_text())
    return questionnaire_from_snapshots(taxonomy, snapshot)


def answer_set(q, capability='unknown'):
    return {item.question_id: (capability if item.capability_id else
            item.min_value or 0 if item.question_type == QuestionType.NUMERIC else
            [] if item.question_type == QuestionType.MULTI_CHOICE else item.options[0])
            for item in q.questions if item.required}


def test_legacy_required_empty_multichoice_and_confidence_characterization():
    q = demo_questionnaires()[0]
    engine = QuestionnaireEngine([q])
    answers = {item.question_id: (2 if item.question_type == QuestionType.NUMERIC else [])
               for item in q.questions if item.required}
    state = engine.build_state(q.stakeholder_type, q.target_scenarios[0], answers)
    assert state.capabilities == ()
    assert state.confidence >= .9
    del answers[next(item.question_id for item in q.questions if item.required)]
    with pytest.raises(ValidationError, match='missing required'):
        engine.build_state(q.stakeholder_type, q.target_scenarios[0], answers)


@pytest.mark.parametrize('answer,judgment,positive,negative', [
    ('yes', 'present', True, False), ('no', 'absent', False, True),
    ('unknown', 'unknown', False, False)])
def test_snapshot_answers_preserve_judgment_and_provenance(answer, judgment, positive, negative):
    q = questionnaire()
    state = QuestionnaireEngine([q]).build_state(q.stakeholder_type, q.target_scenarios[0], answer_set(q, answer))
    finding = state.capability_findings['secure-processing']
    assert finding.judgment == judgment
    assert finding.verification_status == 'unverified'
    assert finding.source == 'self_reported'
    assert finding.answer_ids == tuple(item.question_id for item in q.questions if item.capability_id)
    assert ('secure-processing' in state.capabilities) == positive
    assert ('secure-processing' in state.missing_capabilities) == negative
    assert state.confidence == 1
    for capability_id, other in state.capability_findings.items():
        if capability_id != 'secure-processing':
            assert other.judgment == 'unknown'
            assert other.source == 'unanswered'
    assert state.to_dict()['capability_findings']['secure-processing']['verification_status'] == 'unverified'


def test_positive_omission_and_explicit_negative_collection():
    q = questionnaire()
    q = replace(q, questions=(
        Question('positive', 'Available', QuestionType.MULTI_CHOICE, options=('secure-processing', 'legal-basis'), state_field='capabilities'),
        Question('negative', 'Absent', QuestionType.MULTI_CHOICE, required=False, options=('secure-processing', 'legal-basis'), state_field='missing_capabilities'),
    ))
    engine = QuestionnaireEngine([q])
    state = engine.build_state(q.stakeholder_type, q.target_scenarios[0], {'positive': []})
    assert state.missing_capabilities == ()
    assert all(f.judgment == 'unknown' for f in state.capability_findings.values())
    state = engine.build_state(q.stakeholder_type, q.target_scenarios[0], {'positive': [], 'negative': ['legal-basis']})
    assert state.missing_capabilities == ('legal-basis',)
    with pytest.raises(ValidationError, match='contradictory'):
        engine.build_state(q.stakeholder_type, q.target_scenarios[0], {'positive': ['legal-basis'], 'negative': ['legal-basis']})
    with pytest.raises(ValidationError):
        engine.build_state(q.stakeholder_type, q.target_scenarios[0], {'positive': ['invented']})


@pytest.mark.parametrize('extra', [{'verified': True}, {'capability_findings': {'secure-processing': {'verification_status': 'verified'}}}])
def test_client_cannot_upgrade_verification(extra):
    q = questionnaire()
    with pytest.raises(ValidationError, match='unknown answer'):
        QuestionnaireEngine([q]).build_state(q.stakeholder_type, q.target_scenarios[0], answer_set(q, 'yes') | extra)

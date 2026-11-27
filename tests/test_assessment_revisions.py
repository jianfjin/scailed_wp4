"""Results retain the answers that produced them across all session profiles."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from pathfinder.adapters.upstream import UpstreamClient
from pathfinder.services.assessment_service import AssessmentService

SAMPLES = Path(__file__).resolve().parents[1] / 'contracts/samples'


def snapshots(version=2):
    directory=SAMPLES / 'v2' if version==2 else SAMPLES
    return [json.loads((directory/f'{name}.snapshot.json').read_text()) for name in ('wp2-taxonomy','wp4-questionnaire','wp3-roadmap','wp8-rulebundle')]


def setup(version=2, store=None):
    service=AssessmentService(UpstreamClient(), boundary_store=store)
    docs=snapshots(version)
    service.activate_boundary_snapshots(docs)
    q=docs[1]['payload']
    session=service.create_session(q['stakeholder_type'],q['target_scenarios'][0],profile_id='evidence-v2' if version==2 else 'legacy-v1')
    answers={item['question_id']: 'yes' if item.get('capability_id') or item['question_type']=='single_choice' else [] if item['question_type']=='multi_choice' else 3 for item in q['questions']}
    service.submit_answers(session['assessment_id'],answers)
    return service,session['assessment_id'],answers


@pytest.mark.parametrize('version',[1,2])
def test_answer_change_invalidates_current_result_but_preserves_history(version):
    service,aid,answers=setup(version)
    first=service.generate_recommendation(aid)
    assert first['answer_revision']==1
    changed=deepcopy(answers)
    numeric=next(key for key,value in changed.items() if type(value) is int)
    changed[numeric]=4
    service.submit_answers(aid,changed)
    current=service.get_session(aid)
    assert current['answer_revision']==2
    assert current.get('recommendation') is None
    historical=service.report(aid,result_id=first['result_id'])
    assert historical['session']['answers']==answers
    assert historical['readiness_snapshot']['answers']==answers
    assert historical['result']['answer_revision']==1
    assert historical['recommended_path']['result_id']==first['result_id']
    second=service.generate_recommendation(aid)
    assert second['answer_revision']==2 and second['result_id']!=first['result_id']
    assert service.report(aid)['session']['answers']==changed
    service.submit_answers(aid,changed)
    assert service.get_session(aid)['answer_revision']==2


def test_v2_has_no_implicit_report_recomputation_or_type_inheritance():
    service,aid,answers=setup()
    with pytest.raises(ValueError,match='recommendation_required'):
        service.report(aid)
    q=service.get_questionnaire(service.get_session(aid)['stakeholder_type'],profile_id='evidence-v2')
    cap_id=next(item['question_id'] for item in q['questions'] if item.get('capability_id'))
    answers[cap_id]='unknown'
    state=service.submit_answers(aid,answers)
    assert state['capabilities']==()
    assert state['missing_capabilities']==()
    rec=service.generate_recommendation(aid)
    assert rec['recommendation_kind']=='conditional_direction'
    assert rec['capability_findings']['secure-processing']['verification_status']=='unverified'
    assert rec['current_validity']['valid']


def test_result_identity_does_not_pollute_deterministic_hash():
    service,aid,_=setup()
    first=service.generate_recommendation(aid); second=service.generate_recommendation(aid)
    assert first['result_id']!=second['result_id']
    assert first['content_hash']==second['content_hash']


def test_answer_change_during_compute_cannot_publish(monkeypatch):
    service,aid,answers=setup()
    original=service._recommend_for_session
    changed=deepcopy(answers)
    changed[next(key for key,value in changed.items() if type(value) is int)]=4
    def concurrent_answer(session,state):
        service.submit_answers(aid,changed)
        return original(session,state)
    monkeypatch.setattr(service,'_recommend_for_session',concurrent_answer)
    with pytest.raises(ValueError,match='changed'):
        service.generate_recommendation(aid)
    assert service.get_session(aid).get('result_id') is None
    assert not any(event.event_type=='recommendation_generated' for event in service.audit_log.events())

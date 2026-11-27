"""Regression proofs for versioned evidence, legacy history and release gates."""
from copy import deepcopy
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path.cwd() / 'tests'))
from test_assessment_revisions import setup, snapshots
from pathfinder.adapters.upstream import UpstreamClient
from pathfinder.api import main
from pathfinder.core.boundary_validation import canonical_checksum
from pathfinder.core.repositories.boundary_store import PostgresBoundaryStore
from pathfinder.services.assessment_service import AssessmentService

DEMO={'Authorization':'Bearer demo-token'}


@pytest.fixture(autouse=True)
def development(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT','development')
    monkeypatch.setenv('PATHFINDER_MODE','demo')
    monkeypatch.setenv('PATHFINDER_DEMO_TOKEN','demo-token')
    monkeypatch.setenv('PATHFINDER_ADMIN_TOKEN','admin-token')
    monkeypatch.setattr(main,'ENVIRONMENT','development')


def http(service,monkeypatch):
    monkeypatch.setattr(main,'_service',service)
    return TestClient(main.app,raise_server_exceptions=False)


def modified_questionnaire(extra=None, optional=False):
    docs=snapshots()
    if optional:docs[1]['payload']['questions'][0]['required']=False
    if extra:docs[1]['payload']['questions'].append(extra)
    docs[1]['manifest']['items_checksum']=canonical_checksum(docs[1]['payload'])
    service=AssessmentService(UpstreamClient());service.activate_boundary_snapshots(docs)
    q=docs[1]['payload']
    aid=service.create_session(q['stakeholder_type'],q['target_scenarios'][0],profile_id='evidence-v2')['assessment_id']
    answers={item['question_id']:'yes' if item.get('capability_id') else 3 for item in q['questions'] if item['required']}
    cap=next(item['question_id'] for item in q['questions'] if item.get('capability_id'))
    return service,aid,answers,cap


@pytest.mark.parametrize('change',[lambda a,cap:a.update({cap:'maybe'}),lambda a,cap:a.update({'verified':True}), lambda a,cap:a.clear(), lambda a,cap:a.update({next(key for key,value in a.items() if type(value) is int):'invalid'})])
def test_v2_invalid_answer_is_a_structured_domain_error(monkeypatch,change):
    service,aid,answers,cap=modified_questionnaire()
    change(answers,cap)
    response=http(service,monkeypatch).post(f'/v2/assessments/{aid}/answers/batch',headers=DEMO,json={'answers':answers})
    assert response.status_code==400,response.text
    assert response.json()['detail']['error']=='VALIDATION_ERROR'


@pytest.mark.parametrize('blank',[None,'',[]])
def test_blank_optional_capability_remains_unanswered(monkeypatch,blank):
    service,aid,answers,cap=modified_questionnaire(optional=True)
    answers[cap]=blank
    response=http(service,monkeypatch).post(f'/v2/assessments/{aid}/answers/batch',headers=DEMO,json={'answers':answers})
    assert response.status_code==200,response.text
    finding=response.json()['capability_findings']['secure-processing']
    assert finding['judgment']=='unknown' and finding['source']=='unanswered'
    assert finding['answer_ids']==[]


@pytest.mark.parametrize('kind,value',[('multi_choice',[{}]),('multi_choice',['invalid',3]),('text',{'verified':True})])
def test_v2_malformed_typed_answers_are_rejected(monkeypatch,kind,value):
    extra={'question_id':'pf:wp4:question:extra','label':'Extra answer','question_type':kind,'required':False}
    if kind=='multi_choice':extra.update(options=['legal-basis'],state_field='capabilities')
    service,aid,answers,_=modified_questionnaire(extra=extra)
    answers[extra['question_id']]=value
    response=http(service,monkeypatch).post(f'/v2/assessments/{aid}/answers/batch',headers=DEMO,json={'answers':answers})
    assert response.status_code==400,response.text
    assert response.json()['detail']['error']=='VALIDATION_ERROR'


def test_bound_legacy_extra_answer_cannot_select_reference_inference():
    docs=snapshots(1);q=docs[1]['payload'];client=UpstreamClient()
    client.stakeholders=[{'stakeholder_type':q['stakeholder_type'],'description':'Reference','capabilities':['secure-processing'],'pain_points':[]}]
    service=AssessmentService(client);service.activate_boundary_snapshots(docs)
    aid=service.create_session(q['stakeholder_type'],q['target_scenarios'][0])['assessment_id']
    answers={item['question_id']:'yes' if item['question_type']=='single_choice' else [] if item['question_type']=='multi_choice' else 3 for item in q['questions']}
    answers['derivation_mode']='wp2_wp3'
    service.submit_answers(aid,answers);service.generate_recommendation(aid)
    report=service.report(aid)
    assert report['readiness_snapshot']['capabilities']==()
    assert report['readiness_snapshot'].get('derivation_mode') is None
    assert report['result']['answers']==answers


@pytest.mark.parametrize('operation',['create','answers','recommend'])
def test_production_gate_covers_loaded_profiles_and_existing_sessions(monkeypatch,operation):
    service,aid,answers=setup()
    first=service.generate_recommendation(aid)
    session=service.get_session(aid)
    monkeypatch.setenv('ENVIRONMENT','production')
    monkeypatch.delenv('PATHFINDER_SEMANTIC_V2_APPROVAL_REF',raising=False)
    with pytest.raises(ValueError,match='semantic_approval_required'):
        if operation=='create':service.create_session(session['stakeholder_type'],session['target_scenario'],profile_id='evidence-v2')
        elif operation=='answers':service.submit_answers(aid,answers)
        else:service.generate_recommendation(aid)
    assert service.report(aid,result_id=first['result_id'])['result']['result_id']==first['result_id']


def test_v2_report_never_implicitly_evaluates_a_legacy_session(monkeypatch):
    service,aid,_=setup(1)
    before=service.audit_event_count()
    response=http(service,monkeypatch).get(f'/v2/assessments/{aid}/report',headers=DEMO)
    assert response.status_code==409,response.text
    assert response.json()['detail']['error']=='RECOMMENDATION_REQUIRED'
    assert service.audit_event_count()==before
    assert service.get_session(aid).get('result_id') is None
    assert http(service,monkeypatch).get(f'/v1/assessments/{aid}/report',headers=DEMO).status_code==200


@pytest.fixture
def migrated_history():
    dsn=os.getenv('TEST_BOUNDARY_DATABASE_URL')
    if not dsn:pytest.skip('isolated TEST_BOUNDARY_DATABASE_URL required')
    store=PostgresBoundaryStore(dsn,schema='pf_review_'+uuid4().hex[:16]);store.migrate()
    try:
        service,aid,answers=setup(1,store)
        first=service.generate_recommendation(aid)
        original=store.load_result(aid,first['result_id'])['original_output']
        session,revision,_=store.load_session(aid)
        session['answers']={'current':'changed after historical result'}
        session['answer_revision']=2;session.pop('result_id',None)
        store.save_session(session,revision,'answers_submitted',{'assessment_id':aid})
        with store._connect() as conn:
            for table in ('withdrawal_targets','withdrawals','results','profile_active'):conn.execute(f'DROP TABLE {store.schema}.{table}')
            conn.execute(f'UPDATE {store.schema}.schema_version SET version=1')
        store.migrate()
        record=store.load_result(aid)
        yield service,aid,record,original
    finally:
        with store._connect() as conn:conn.execute(f'DROP SCHEMA {store.schema} CASCADE')


def test_migrated_history_is_discoverable_and_keeps_unknown_evidence(monkeypatch,migrated_history):
    service,aid,record,original=migrated_history;client=http(service,monkeypatch)
    assessment=client.get(f'/v2/assessments/{aid}',headers=DEMO)
    assert assessment.status_code==200,assessment.text
    assert not assessment.json().get('recommendation')
    assert record['result_id'] in [item['result_id'] for item in assessment.json()['result_history']]
    assert client.get(f'/v1/assessments/{aid}',headers=DEMO).status_code==409
    response=client.get(f'/v2/assessments/{aid}/report',params={'result_id':record['result_id']},headers=DEMO)
    assert response.status_code==200,response.text
    report=response.json()
    assert report['result']['binding_status']=='legacy_unbound'
    assert report['result']['original_output']==original
    assert report['readiness_snapshot'] is None
    assert report['session']['answers'] is None and report['session']['answer_revision'] is None
    assert report['result']['findings'] is None
    html=client.get(f'/v2/assessments/{aid}/report',params={'result_id':record['result_id'],'format':'html'},headers=DEMO)
    assert html.status_code==200,html.text
    assert 'ORIGINAL EVIDENCE UNAVAILABLE' in html.text
    assert 'HISTORICAL' in html.text
    assert client.get(f'/v2/assessments/{aid}/fhir',params={'result_id':record['result_id']},headers=DEMO).status_code==409
    assert store_result(service,aid,record['result_id'])==record


def store_result(service,aid,result_id):
    return service._boundary_store.load_result(aid,result_id)


def test_v1_withdrawn_creation_returns_exact_lifecycle_conflict(monkeypatch):
    from test_boundary_lifecycle import notice_for
    service,aid,_=setup(1);docs=snapshots(1);session=service.get_session(aid)
    service.withdraw_inputs(notice_for(docs[0]),actor='authenticated_admin')
    response=http(service,monkeypatch).post('/v1/assessments',headers=DEMO,json={key:session[key] for key in ('stakeholder_type','target_scenario')})
    assert response.status_code==409,response.text
    assert response.json()['detail']['error']=='INPUTS_WITHDRAWN'
    observation=response.json()['detail']['current_validity']
    assert not observation['valid']
    assert observation['affected_inputs'][0]['snapshot_id']==docs[0]['manifest']['snapshot_id']


@pytest.mark.parametrize('binding',['answers','input_set'])
def test_postgres_rejects_each_incorrect_result_binding_without_partial_writes(migrated_history,binding):
    from test_boundary_postgres import persisted_answer_session, result_for
    service,_,_,_=migrated_history;store=service._boundary_store
    (session,revision,_),docs=persisted_answer_session(store)
    result=result_for(session,docs)
    if binding=='answers':result['answers']={'other':'not the persisted answers'}
    else:result['input_set']=result['input_set'][:-1]
    before_session=store.load_session(session['assessment_id'])
    before_audit=store.audit_count()
    with pytest.raises(ValueError,match='answers|input set'):
        store.publish_result(session,revision,result)
    assert store.load_session(session['assessment_id'])==before_session
    assert store.audit_count()==before_audit
    assert store.results_for_session(session['assessment_id'])==[]

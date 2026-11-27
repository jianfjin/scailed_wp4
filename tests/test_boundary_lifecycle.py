"""Exact runtime dependency closure and withdrawal observations."""
import copy

import pytest

from pathfinder.core.boundary_lifecycle import dependency_closure, observe_validity, runtime_input_set


def document(contract, snapshot_id, producer, dependencies=None, **manifest):
    return {'contract': contract, 'manifest': {'snapshot_id': snapshot_id, 'producer_wp': producer,
            'dependencies': dependencies or {}, **manifest}, 'payload': {}}


def test_dependency_closure_is_transitive_and_ignores_supersedes():
    tax = document('pf.taxonomy.v1', 't1', 'WP2')
    replacement = document('pf.taxonomy.v1', 't2', 'WP2', supersedes='t1')
    road = document('pf.roadmap.v1', 'r1', 'WP3', {'pf.taxonomy.v1': 't1'})
    rule = document('pf.rulebundle.v2', 'l1', 'WP8', {'pf.roadmap.v1': 'r1'})
    closure = dependency_closure([tax, replacement, road, rule], [{'contract': rule['contract'], 'snapshot_id': 'l1', 'producer_wp': 'WP8'}])
    assert {item['snapshot_id'] for item in closure} == {'l1', 'r1', 't1'}
    validity = observe_validity(closure, [{'payload': {'notice_id': 'n', 'targets': [{'contract':'pf.taxonomy.v1','snapshot_id':'t1','producer_wp':'WP2'}], 'reason':'withdrawn'}}], 4)
    assert not validity['valid']
    assert validity['status'] == 'dependency_affected'
    assert validity['lifecycle_revision'] == 4
    assert validity['affected_inputs'][0]['dependency_path'] == ['l1', 'r1', 't1']
    assert observe_validity(dependency_closure([tax, replacement], [{'contract':'pf.taxonomy.v1','snapshot_id':'t2','producer_wp':'WP2'}]), [{'payload': {'notice_id':'n','targets':[{'contract':'pf.taxonomy.v1','snapshot_id':'t1','producer_wp':'WP2'}], 'reason':'withdrawn'}}])['valid']


def test_membership_of_unselected_questionnaire_is_not_a_dependency():
    docs = [document('pf.taxonomy.v1','t','WP2'), document('pf.roadmap.v1','r','WP3',{'pf.taxonomy.v1':'t'}),
            document('pf.rulebundle.v2','l','WP8',{'pf.roadmap.v1':'r','pf.taxonomy.v1':'t'})]
    q1 = document('pf.questionnaire.v2','q1','WP4',{'pf.taxonomy.v1':'t'}); q1['payload']['stakeholder_type']='one'
    q2 = copy.deepcopy(q1); q2['manifest']['snapshot_id']='q2'; q2['payload']['stakeholder_type']='two'
    inputs = runtime_input_set(docs+[q1,q2], 'two')
    assert {i['snapshot_id'] for i in inputs} == {'t','r','l','q2'}
    notice={'payload':{'notice_id':'n','targets':[{'contract':'pf.questionnaire.v2','snapshot_id':'q1','producer_wp':'WP4'}],'reason':'bad'}}
    assert observe_validity(inputs, [notice])['valid']


def test_dependency_must_resolve_exact_contract_and_producer():
    q = document('pf.questionnaire.v2','q','WP4',{'pf.taxonomy.v1':'t'})
    with pytest.raises(ValueError, match='dependency'):
        dependency_closure([q], [{'contract':q['contract'],'snapshot_id':'q','producer_wp':'WP4'}])
    wrong = document('pf.taxonomy.v1','t','WP3')
    with pytest.raises(ValueError, match='producer'):
        dependency_closure([wrong,q], [{'contract':q['contract'],'snapshot_id':'q','producer_wp':'WP4'}])

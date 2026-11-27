"""Finite truth algebra and the real versioned recommendation path."""
from dataclasses import replace
from itertools import product
import json
from pathlib import Path

import pytest

from pathfinder.core.compliance import ComplianceEvaluator
from pathfinder.core.models import StakeholderState, TruthValue
from pathfinder.core.boundary_runtime import build_boundary_generation
from pathfinder.core.recommend import build_recommendation

T, F, U = TruthValue.TRUE, TruthValue.FALSE, TruthValue.UNKNOWN


def state(**answers):
    return StakeholderState('test', 'target', answers, {}, (), (), (), 1, (), '2', profile_id='evidence-v2')


def leaf(value):
    return {'field': {T: 'yes', F: 'no', U: 'missing'}[value], 'op': 'eq', 'value': True}


@pytest.mark.parametrize('a,b', product((T,F,U), repeat=2))
def test_compound_truth_table(a,b):
    evaluator = ComplianceEvaluator('evidence-v2')
    s = state(yes=True, no=False)
    expected_and = F if F in (a,b) else U if U in (a,b) else T
    expected_or = T if T in (a,b) else U if U in (a,b) else F
    assert evaluator.evaluate({'and':[leaf(a),leaf(b)]},s) is expected_and
    assert evaluator.evaluate({'or':[leaf(a),leaf(b)]},s) is expected_or
    result = evaluator.evaluate_details({'and':[leaf(a),leaf(b)]},s)
    assert bool(result.missing_fields) == (expected_and is U)


@pytest.mark.parametrize('value,expected', [(T,F),(F,T),(U,U)])
def test_not_preserves_unknown(value,expected):
    assert ComplianceEvaluator('evidence-v2').evaluate({'not':leaf(value)},state(yes=True,no=False)) is expected


def test_absent_null_false_zero_exists_and_invalid_types():
    e = ComplianceEvaluator('evidence-v2')
    s = state(null=None, false=False, zero=0)
    assert e.evaluate({'field':'null','op':'eq','value':None},s) is U
    assert e.evaluate({'field':'false','op':'eq','value':False},s) is T
    assert e.evaluate({'field':'zero','op':'eq','value':0},s) is T
    assert e.evaluate({'field':'missing','op':'exists'},s) is F
    assert e.evaluate({'field':'false','op':'exists'},s) is T
    assert e.evaluate({},s) is T
    for condition in ({'and':[]},{'or':[]},{'field':'zero','op':'invented','value':0}, {'field':'zero','op':'gt','value':'text'}, {'field':'capabilities','op':'eq','value':[]}):
        with pytest.raises(ValueError):
            e.evaluate(condition,s)
    with pytest.raises(TypeError):
        bool(U)


@pytest.mark.parametrize('answer,kind,status', [('yes','executable_path','degraded'),('no','blocked','blocked'),('unknown','conditional_direction','degraded')])
def test_v2_snapshot_paired_tests_and_runtime_agree(answer,kind,status):
    directory = Path(__file__).resolve().parents[1] / 'contracts/samples/v2'
    generation = build_boundary_generation([json.loads(p.read_text()) for p in directory.glob('*.snapshot.json')])
    q = generation.questionnaire_engine.get(next(iter(generation.questionnaire_ids)))
    answers = {item.question_id: answer if item.capability_id else item.min_value for item in q.questions}
    s = generation.questionnaire_engine.build_state(q.stakeholder_type,q.target_scenarios[0],answers)
    result = build_recommendation(generation.solver.solve(s,list(generation.rules)))
    assert result['recommendation_kind'] == kind
    assert result['status'] == status
    assert bool(result['missing_information']) == (answer=='unknown')
    assert result['trace']['condition_evaluations']

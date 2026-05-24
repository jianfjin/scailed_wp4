"""Tests for curated WP8 rules (superset check — additional rules from the
1000-rule generated set are OK as long as curated rules are triggered)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pathfinder.adapters.demo_data import demo_questionnaires
from pathfinder.core.compliance import ComplianceEvaluator
from pathfinder.core.questionnaire import QuestionnaireEngine
from pathfinder.core.rules.compiler import compile_rules

_FIXTURE = Path(__file__).parent.parent / "services" / "mock" / "fixtures" / "wp8_data.json"
_QUESTIONNAIRES = demo_questionnaires()


def _load_rules():
    with open(_FIXTURE) as f:
        bundle = json.load(f)
    return compile_rules(bundle)


def _check(stakeholder_type, answers, must_contain):
    """Superset check: must_contain ⊆ triggered_rule_ids."""
    engine = QuestionnaireEngine(_QUESTIONNAIRES)
    evaluator = ComplianceEvaluator()
    rules = _load_rules()
    state = engine.build_state(stakeholder_type, "secondary-use-readiness", answers)
    triggered = {r.rule_id for r in evaluator.triggered_rules(state, rules)}
    missing = set(must_contain) - triggered
    assert not missing, (
        f"Expected curated rules {sorted(must_contain)} to be triggered by "
        f"{stakeholder_type}, but {sorted(missing)} were missing. "
        f"Triggered {len(triggered)} rules total."
    )


class TestCuratedRules:
    """Curated complex rules should trigger with the expected inputs."""

    def test_compound_andor_high_maturity(self):
        """WP8-COMPOUND-ANDOR-001: governance>=4, compliance>=3, data-catalog in capabilities."""
        _check("biotech-sme", {
            "governance_maturity": 4,
            "data_maturity": 3,
            "compliance_maturity": 3,
            "capabilities": ["data-catalog", "secure-processing"],
            "missing_capabilities": [],
            "regulatory_flags": [],
        }, ["WP8-COMPOUND-ANDOR-001"])

    def test_compound_not_no_legal_basis(self):
        """WP8-COMPOUND-NOT-001: NOT contains legal-basis → eligibility block."""
        _check("biotech-sme", {
            "governance_maturity": 2,
            "data_maturity": 2,
            "compliance_maturity": 2,
            "capabilities": ["secure-processing"],
            "missing_capabilities": ["legal-basis"],
            "regulatory_flags": [],
        }, ["WP8-COMPOUND-NOT-001"])

    def test_exclusion_low_data_no_catalog(self):
        """WP8-EXCLUSION-LOW-DATA-001: data_maturity<2 AND missing data-catalog."""
        _check("biotech-sme", {
            "governance_maturity": 1,
            "data_maturity": 1,
            "compliance_maturity": 1,
            "capabilities": [],
            "missing_capabilities": ["data-catalog"],
            "regulatory_flags": [],
        }, ["WP8-EXCLUSION-LOW-DATA-001"])

    def test_override_high_maturity(self):
        """WP8-OVERRIDE-SECURE-001: ai-factory with data>=4, governance>=3."""
        _check("ai-factory-operator", {
            "governance_maturity": 4,
            "data_maturity": 4,
            "compliance_maturity": 4,
            "capabilities": ["data-catalog", "legal-basis", "secure-processing"],
            "missing_capabilities": [],
            "regulatory_flags": [],
        }, ["WP8-OVERRIDE-SECURE-001", "WP8-COMPOUND-ANDOR-001"])

    def test_cross_border_block(self):
        """WP8-PREFERENCE-CROSS-BORDER-001: cross-border-use flag triggers block."""
        _check("health-data-access-body", {
            "governance_maturity": 3,
            "data_maturity": 3,
            "compliance_maturity": 3,
            "capabilities": ["legal-basis", "secure-processing"],
            "missing_capabilities": [],
            "regulatory_flags": ["cross-border-use"],
        }, ["WP8-PREFERENCE-CROSS-BORDER-001", "WP8-COMPOUND-ANDOR-001"])

    def test_deep_andor_incomplete_baseline(self):
        """WP8-CURATED-DEEP-ANDOR-001: data>=3 AND NOT (data-quality-kpi AND audit-log)."""
        _check("biotech-sme", {
            "governance_maturity": 3,
            "data_maturity": 3,
            "compliance_maturity": 3,
            "capabilities": ["data-catalog"],
            "missing_capabilities": [],
            "regulatory_flags": [],
        }, ["WP8-CURATED-DEEP-ANDOR-001"])

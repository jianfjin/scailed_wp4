"""Safe rule activation pipeline."""

from __future__ import annotations

from pathfinder.core.compliance import ComplianceEvaluator
from pathfinder.core.exceptions import RuleValidationError
from pathfinder.core.models import Questionnaire, Rule
from pathfinder.core.questionnaire import QuestionnaireEngine
from pathfinder.core.rules.compiler import compile_rules
from pathfinder.core.rules.parser import parse_rule_bundle
from pathfinder.core.rules.validator import validate_rule_bundle


class RuleLoader:
    def __init__(self, questionnaires: list[Questionnaire]) -> None:
        self._questionnaire_engine = QuestionnaireEngine(questionnaires)
        self._evaluator = ComplianceEvaluator()
        self.active_rules: list[Rule] = []
        self.active_version: str | None = None

    def load_bundle(self, bundle: dict[str, object]) -> list[Rule]:
        validate_rule_bundle(bundle)
        compiled = compile_rules(bundle)
        self._run_tests(bundle, compiled)
        self.active_rules = compiled
        self.active_version = str(bundle["version"])
        return compiled

    def load_file(self, path: str) -> list[Rule]:
        return self.load_bundle(parse_rule_bundle(path))

    def _run_tests(self, bundle: dict[str, object], rules: list[Rule]) -> None:
        tests = bundle.get("tests", [])
        for test in tests:  # type: ignore[assignment]
            state_def = test["state"]
            state = self._questionnaire_engine.build_state(
                state_def["stakeholder_type"],
                state_def["target_scenario"],
                state_def["answers"],
            )
            actual = {rule.rule_id for rule in self._evaluator.triggered_rules(state, rules)}
            expected = set(test["expected_rule_ids"])
            if actual != expected:
                raise RuleValidationError(
                    f"rule test failed: {test['name']} expected {sorted(expected)} got {sorted(actual)}"
                )

"""Deterministic rule condition evaluation."""

from __future__ import annotations

from pathfinder.core.contract_registry import EVIDENCE_PROFILE, LEGACY_PROFILE

from typing import Any

from pathfinder.core.models import ConditionEvaluation, Rule, StakeholderState, TruthValue


class ComplianceEvaluator:
    def __init__(self, profile_id: str = LEGACY_PROFILE.profile_id) -> None:
        if profile_id not in (LEGACY_PROFILE.profile_id, EVIDENCE_PROFILE.profile_id):
            raise ValueError(f"unsupported evaluation profile: {profile_id}")
        self.profile_id = profile_id

    def triggered_rules(self, state: StakeholderState, rules: list[Rule]) -> tuple[Rule, ...]:
        triggered = [
            rule
            for rule in rules
            if rule.applies_to_stakeholder(state.stakeholder_type)
            and self.is_triggered(self.evaluate(rule.condition, state))
        ]
        return tuple(sorted(triggered, key=lambda rule: rule.priority, reverse=True))

    @staticmethod
    def is_triggered(value: bool | TruthValue) -> bool:
        return value is True or value is TruthValue.TRUE

    def evaluate(self, condition: dict[str, Any], state: StakeholderState) -> bool | TruthValue:
        if self.profile_id == EVIDENCE_PROFILE.profile_id:
            return self.evaluate_details(condition, state).truth
        if not condition:
            return True

        if "and" in condition:
            return all(self.evaluate(item, state) for item in condition["and"])
        if "or" in condition:
            return any(self.evaluate(item, state) for item in condition["or"])
        if "not" in condition:
            return not self.evaluate(condition["not"], state)

        field = condition.get("field")
        operator = condition.get("operator", condition.get("op", "eq"))
        expected = condition.get("value")
        actual = self._resolve_field(field, state)
        return self._compare(actual, operator, expected)

    def evaluate_details(self, condition: dict[str, Any], state: StakeholderState) -> ConditionEvaluation:
        """Evaluate once, retaining the unresolved inputs that affect the result."""
        T, F, U = TruthValue.TRUE, TruthValue.FALSE, TruthValue.UNKNOWN
        if not isinstance(condition, dict):
            raise ValueError("condition must be an object")
        if not condition:
            return ConditionEvaluation(T, condition=condition)
        for branch in ("and", "or", "not"):
            if branch not in condition:
                continue
            if set(condition) != {branch}:
                raise ValueError("condition must contain one expression")
            items = [condition[branch]] if branch == "not" else condition[branch]
            if not isinstance(items, list) or not items:
                raise ValueError("compound conditions must be nonempty")
            children = tuple(self.evaluate_details(item, state) for item in items)
            values = tuple(child.truth for child in children)
            if branch == "not":
                truth = {T: F, F: T, U: U}[values[0]]
            elif branch == "and":
                truth = F if F in values else U if U in values else T
            else:
                truth = T if T in values else U if U in values else F
            missing = tuple(sorted({field for child in children for field in child.missing_fields})) if truth is U else ()
            return ConditionEvaluation(truth, missing, condition, children=children)

        field = condition.get("field")
        op = condition.get("operator", condition.get("op", "eq"))
        expected = condition.get("value")
        if not isinstance(field, str) or op not in {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "exists"}:
            raise ValueError("invalid condition field or operator")
        actual = self._resolve_field(field, state)
        if field in ("capabilities", "missing_capabilities") and op != "contains":
            raise ValueError("capability conditions require contains on a mapped capability")
        if op == "exists":
            return ConditionEvaluation(T if actual is not None else F, condition=condition, actual=actual)
        if field in ("capabilities", "missing_capabilities"):
            if not isinstance(expected, str):
                raise ValueError("capability contains requires a capability ID")
            finding = state.capability_findings.get(expected)
            judgment = finding.judgment if finding else "unknown"
            positive = "present" if field == "capabilities" else "absent"
            truth = U if judgment == "unknown" else T if judgment == positive else F
            return ConditionEvaluation(truth, (f"capability:{expected}",) if truth is U else (), condition, judgment)
        if actual is None:
            return ConditionEvaluation(U, (field,), condition)
        numeric = lambda value: type(value) in (int, float)
        if op in {"gt", "gte", "lt", "lte"} and not (numeric(actual) and numeric(expected)):
            raise ValueError("ordered comparison requires numbers")
        if op in {"eq", "ne"} and not (type(actual) is type(expected) or numeric(actual) and numeric(expected)):
            raise ValueError("comparison has incompatible types")
        if op in {"in", "not_in"} and not isinstance(expected, (list, tuple)):
            raise ValueError("membership comparison requires an array")
        if op == "contains" and not isinstance(actual, (list, tuple, str)):
            raise ValueError("contains requires a collection")
        try:
            truth = T if self._compare(actual, op, expected) else F
        except TypeError as exc:
            raise ValueError("invalid comparison types") from exc
        return ConditionEvaluation(truth, condition=condition, actual=actual)

    def _resolve_field(self, field: str | None, state: StakeholderState) -> Any:
        if field is None:
            return None
        if field.startswith("answers."):
            return state.answers.get(field.removeprefix("answers."))
        if field.startswith("maturity."):
            return state.maturity_scores.get(field.removeprefix("maturity."))
        if field == "stakeholder_type":
            return state.stakeholder_type
        if field == "target_scenario":
            return state.target_scenario
        if field == "capabilities":
            return state.capabilities
        if field == "missing_capabilities":
            return state.missing_capabilities
        if field == "regulatory_flags":
            return state.regulatory_flags
        return state.answers.get(field)

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        if operator == "eq":
            return actual == expected
        if operator == "ne":
            return actual != expected
        if operator == "gt":
            return actual is not None and actual > expected
        if operator == "gte":
            return actual is not None and actual >= expected
        if operator == "lt":
            return actual is not None and actual < expected
        if operator == "lte":
            return actual is not None and actual <= expected
        if operator == "in":
            return actual in expected
        if operator == "not_in":
            return actual not in expected
        if operator == "contains":
            return expected in (actual or ())
        if operator == "exists":
            return actual not in (None, "", [])
        raise ValueError(f"unsupported condition operator: {operator}")

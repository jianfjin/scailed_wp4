"""Deterministic rule condition evaluation."""

from __future__ import annotations

from typing import Any

from pathfinder.core.models import Rule, StakeholderState


class ComplianceEvaluator:
    def triggered_rules(self, state: StakeholderState, rules: list[Rule]) -> tuple[Rule, ...]:
        triggered = [
            rule
            for rule in rules
            if rule.applies_to_stakeholder(state.stakeholder_type)
            and self.evaluate(rule.condition, state)
        ]
        return tuple(sorted(triggered, key=lambda rule: rule.priority, reverse=True))

    def triggered_rules_for_node(
        self,
        state: StakeholderState,
        rules: list[Rule],
        node_id: str,
    ) -> tuple[Rule, ...]:
        """Return rules triggered *at* a specific roadmap node.

        Only includes rules whose action.node_id matches the given node_id.
        This is used by locate_current() to check whether a candidate starting
        node would immediately block the stakeholder.
        """
        triggered = [
            rule
            for rule in rules
            if rule.action.node_id == node_id
            and rule.applies_to_stakeholder(state.stakeholder_type)
            and self.evaluate(rule.condition, state)
        ]
        return tuple(sorted(triggered, key=lambda rule: rule.priority, reverse=True))

    def evaluate(self, condition: dict[str, Any], state: StakeholderState) -> bool:
        if not condition:
            return True

        if "and" in condition:
            return all(self.evaluate(item, state) for item in condition["and"])
        if "or" in condition:
            return any(self.evaluate(item, state) for item in condition["or"])
        if "not" in condition:
            return not self.evaluate(condition["not"], state)

        field = condition.get("field")
        operator = condition.get("operator", "eq")
        expected = condition.get("value")
        actual = self._resolve_field(field, state)
        return self._compare(actual, operator, expected)

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

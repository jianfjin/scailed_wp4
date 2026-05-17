"""Rule bundle validation."""

from __future__ import annotations

from typing import Any

from pathfinder.core.exceptions import RuleValidationError

REQUIRED_RULE_FIELDS = {
    "rule_id",
    "rule_type",
    "priority",
    "applies_to",
    "condition",
    "action",
    "compliance_refs",
}
VALID_RULE_TYPES = {"eligibility", "exclusion", "preference", "override"}


def validate_rule_bundle(bundle: dict[str, Any]) -> None:
    if not isinstance(bundle.get("version"), str):
        raise RuleValidationError("rule bundle requires string version")
    rules = bundle.get("rules")
    if not isinstance(rules, list) or not rules:
        raise RuleValidationError("rule bundle requires non-empty rules list")
    tests = bundle.get("tests")
    if not isinstance(tests, list):
        raise RuleValidationError("rule bundle requires tests list")

    seen: set[str] = set()
    conflict_keys: dict[tuple[str, str, str], str] = {}
    for raw_rule in rules:
        missing = sorted(REQUIRED_RULE_FIELDS.difference(raw_rule))
        if missing:
            raise RuleValidationError(f"rule missing fields: {missing}")
        rule_id = raw_rule["rule_id"]
        if rule_id in seen:
            raise RuleValidationError(f"duplicate rule_id: {rule_id}")
        seen.add(rule_id)
        if raw_rule["rule_type"] not in VALID_RULE_TYPES:
            raise RuleValidationError(f"invalid rule_type: {raw_rule['rule_type']}")
        if not isinstance(raw_rule["applies_to"], list):
            raise RuleValidationError(f"applies_to must be list: {rule_id}")
        if not isinstance(raw_rule["action"], dict):
            raise RuleValidationError(f"action must be object: {rule_id}")
        key = (
            raw_rule["rule_type"],
            json_like(raw_rule["applies_to"]),
            json_like(raw_rule["condition"]),
        )
        existing = conflict_keys.get(key)
        if existing:
            raise RuleValidationError(f"conflicting duplicate rule logic: {existing} and {rule_id}")
        conflict_keys[key] = rule_id

    for test in tests:
        if "name" not in test or "state" not in test or "expected_rule_ids" not in test:
            raise RuleValidationError("rule tests require name, state, expected_rule_ids")


def json_like(value: object) -> str:
    return repr(value)

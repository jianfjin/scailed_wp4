"""Compile raw rule dictionaries into domain rules."""

from __future__ import annotations

from typing import Any

from pathfinder.core.models import Rule, RuleAction, RuleType


def compile_rules(bundle: dict[str, Any]) -> list[Rule]:
    version = bundle["version"]
    rules: list[Rule] = []
    for raw in bundle["rules"]:
        action = raw["action"]
        rules.append(
            Rule(
                rule_id=raw["rule_id"],
                rule_type=RuleType(raw["rule_type"]),
                priority=raw["priority"],
                applies_to=tuple(raw["applies_to"]),
                condition=raw["condition"],
                action=RuleAction(
                    title=action["title"],
                    text=action["text"],
                    node_id=action.get("node_id"),
                    warning=action.get("warning"),
                    block=bool(action.get("block", False)),
                ),
                compliance_refs=tuple(raw["compliance_refs"]),
                parent_rule_id=raw.get("parent_rule_id"),
                source_doc_ref=raw.get("source_doc_ref", "demo-data"),
                rule_version=version,
            )
        )
    return rules

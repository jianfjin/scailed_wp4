"""View model dataclasses for Pathfinder report visualization.

Guido's rule: templates receive frozen dataclasses, never raw dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConditionMatch:
    """A rule condition and the user's matching (or non-matching) value."""

    field: str
    operator: str
    expected: Any
    actual: Any
    matched: bool

    def display_operator(self) -> str:
        labels = {
            "eq": "=",
            "ne": "≠",
            "gt": ">",
            "gte": "≥",
            "lt": "<",
            "lte": "≤",
            "in": "in",
            "not_in": "not in",
            "contains": "contains",
            "exists": "exists",
        }
        return labels.get(self.operator, self.operator)


@dataclass(frozen=True)
class BlockerEvidence:
    """A single blocker with traceable evidence back to the triggering rule."""

    blocker_text: str
    rule_id: str
    rule_type: str
    priority: int
    condition_matches: tuple[ConditionMatch, ...] = ()
    action_title: str = ""
    action_text: str = ""
    node_id: str | None = None
    compliance_refs: tuple[str, ...] = ()
    source_doc_ref: str = ""


@dataclass(frozen=True)
class PathStepView:
    """A single step in the compliance path, with visual status."""

    node_id: str
    label: str
    description: str = ""
    dimension: str = ""
    maturity_level: int = 1
    status: str = "unreached"  # completed | blocked | current | unreached

    def status_color(self) -> str:
        return {
            "completed": "#166534",
            "blocked": "#9B2C2C",
            "current": "#1E40AF",
            "unreached": "#87867F",
        }.get(self.status, "#87867F")

    def status_label(self) -> str:
        return {
            "completed": "✓ Done",
            "blocked": "✗ Blocked",
            "current": "▶ Here",
            "unreached": "○ Pending",
        }.get(self.status, "?")


@dataclass(frozen=True)
class ReadinessSummary:
    """Top-line readiness snapshot."""

    status: str  # "blocked" | "ready"
    confidence: float
    path_backend: str
    audit_chain_valid: bool
    stakeholder_type: str = ""
    target_scenario: str = ""
    total_rules_triggered: int = 0
    total_blockers: int = 0
    total_steps: int = 0

    def status_label(self) -> str:
        if self.status == "blocked":
            return "NOT READY"
        return "READY"

    def status_color(self) -> str:
        if self.status == "blocked":
            return "#9B2C2C"
        return "#166534"

    def status_bg(self) -> str:
        if self.status == "blocked":
            return "#FED7D7"
        return "#DCFCE7"

    def confidence_pct(self) -> str:
        return f"{self.confidence * 100:.0f}%"


@dataclass(frozen=True)
class RuleCard:
    """A triggered rule, expanded for evidence display."""

    rule_id: str
    rule_type: str
    priority: int
    condition_matches: tuple[ConditionMatch, ...] = ()
    action_title: str = ""
    action_text: str = ""
    node_id: str | None = None
    warning: str | None = None
    compliance_refs: tuple[str, ...] = ()
    source_doc_ref: str = ""
    is_blocker: bool = False

    def rule_type_label(self) -> str:
        labels = {
            "eligibility": "ELIGIBILITY",
            "exclusion": "EXCLUSION",
            "preference": "PREFERENCE",
            "override": "OVERRIDE",
        }
        return labels.get(self.rule_type, self.rule_type.upper())

    def rule_type_color(self) -> str:
        return {
            "exclusion": "#9B2C2C",
            "eligibility": "#166534",
            "preference": "#92400E",
            "override": "#1E40AF",
        }.get(self.rule_type, "#87867F")


@dataclass(frozen=True)
class ReportViewModel:
    """Top-level view model for the visualization page."""

    summary: ReadinessSummary
    blockers: tuple[BlockerEvidence, ...] = ()
    path_steps: tuple[PathStepView, ...] = ()
    triggered_rules: tuple[RuleCard, ...] = ()
    trace_answer_ids: tuple[str, ...] = ()
    trace_node_ids: tuple[str, ...] = ()
    trace_rule_ids: tuple[str, ...] = ()
    trace_refs: tuple[str, ...] = ()
    upstream_snapshot: str = ""
    disclaimer: str = ""
    generated_at: str = ""

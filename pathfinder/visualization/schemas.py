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
    matched: bool | None

    def outcome_label(self) -> str:
        return "Unknown / not evaluated" if self.matched is None else "True" if self.matched else "False"

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

    status: str  # "blocked" | "ready" | "degraded"
    confidence: float
    path_backend: str
    audit_chain_valid: bool
    stakeholder_type: str = ""
    target_scenario: str = ""
    total_rules_triggered: int = 0
    total_blockers: int = 0
    total_steps: int = 0
    recommendation_kind: str = ""
    profile_id: str = "legacy-v1"
    inputs_valid: bool | None = None
    validity_status: str = "not_observed"
    result_id: str = ""
    answer_revision: int | None = None
    lifecycle_revision: int | None = None

    def status_label(self) -> str:
        if self.inputs_valid is False:
            return "HISTORICAL — INPUTS WITHDRAWN"
        if self.status == "blocked":
            return "NOT READY"
        if self.recommendation_kind == "conditional_direction":
            return "CONDITIONAL DIRECTION"
        if self.status == "degraded":
            return "UNVERIFIED"
        if self.profile_id == "evidence-v2":
            return "GUIDANCE AVAILABLE"
        return "READY"

    def status_color(self) -> str:
        if self.status == "blocked" or self.inputs_valid is False:
            return "#9B2C2C"
        if self.status == "degraded":
            return "#92400E"
        return "#166534"

    def status_bg(self) -> str:
        if self.status == "blocked" or self.inputs_valid is False:
            return "#FED7D7"
        if self.status == "degraded":
            return "#FEF3C7"
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
    truth: str = "not_evaluated"

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
class CapabilityFindingView:
    capability_id: str
    judgment: str
    source: str
    verification_status: str
    answer_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class InputValidityView:
    contract: str
    snapshot_id: str
    producer_wp: str
    notice_id: str
    reason: str
    dependency_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleEvaluationView:
    rule_id: str
    truth: str
    critical: bool
    condition_matches: tuple[ConditionMatch, ...] = ()


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
    missing_information: tuple[str, ...] = ()
    capability_findings: tuple[CapabilityFindingView, ...] = ()
    affected_inputs: tuple[InputValidityView, ...] = ()
    condition_evaluations: tuple[RuleEvaluationView, ...] = ()

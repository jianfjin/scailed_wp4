"""Core domain models for Pathfinder V1.

These models intentionally use stdlib dataclasses so the deterministic kernel can
run in tests and demos before FastAPI/Pydantic dependencies are installed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


SCHEMA_VERSION = "v1.0-m3-baseline"
DEMO_UPSTREAM_SNAPSHOT = "demo-snapshot-2026-05-15"


class QuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    NUMERIC = "numeric"
    TEXT = "text"


class RuleType(StrEnum):
    ELIGIBILITY = "eligibility"
    EXCLUSION = "exclusion"
    PREFERENCE = "preference"
    OVERRIDE = "override"


@dataclass(frozen=True)
class Question:
    question_id: str
    label: str
    question_type: QuestionType
    required: bool = True
    options: tuple[str, ...] = ()
    min_value: int | None = None
    max_value: int | None = None
    maturity_dimension: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Questionnaire:
    stakeholder_type: str
    version: str
    title: str
    target_scenarios: tuple[str, ...]
    questions: tuple[Question, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["questions"] = [question.to_dict() for question in self.questions]
        return data


@dataclass(frozen=True)
class StakeholderState:
    stakeholder_type: str
    target_scenario: str
    answers: dict[str, Any]
    maturity_scores: dict[str, int]
    capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    regulatory_flags: tuple[str, ...]
    confidence: float
    confidence_warnings: tuple[str, ...]
    questionnaire_version: str
    schema_version: str = SCHEMA_VERSION
    upstream_snapshot_version: str = DEMO_UPSTREAM_SNAPSHOT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoadmapNode:
    node_id: str
    label: str
    description: str
    dimension: str
    maturity_level: int
    stakeholder_types: tuple[str, ...]
    prerequisites: tuple[str, ...] = ()
    source_wp: str = "WP3"
    source_doc_ref: str = "demo-data"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def applies_to(self, stakeholder_type: str) -> bool:
        return stakeholder_type in self.stakeholder_types or "all" in self.stakeholder_types

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoadmapEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    relation_type: str = "prerequisite"
    required: bool = True
    source_doc_ref: str = "demo-data"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleAction:
    title: str
    text: str
    node_id: str | None = None
    warning: str | None = None
    block: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    rule_type: RuleType
    priority: int
    applies_to: tuple[str, ...]
    condition: dict[str, Any]
    action: RuleAction
    compliance_refs: tuple[str, ...]
    effective_from: date | None = None
    effective_until: date | None = None
    parent_rule_id: str | None = None
    source_doc_ref: str = "demo-data"
    rule_version: str = "demo-rules-v1"

    def applies_to_stakeholder(self, stakeholder_type: str) -> bool:
        return stakeholder_type in self.applies_to or "all" in self.applies_to

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rule_type"] = self.rule_type.value
        if self.effective_from:
            data["effective_from"] = self.effective_from.isoformat()
        if self.effective_until:
            data["effective_until"] = self.effective_until.isoformat()
        return data


@dataclass(frozen=True)
class TraceRecord:
    answer_ids: tuple[str, ...]
    roadmap_node_ids: tuple[str, ...]
    triggered_rule_ids: tuple[str, ...]
    regulatory_refs: tuple[str, ...]
    upstream_snapshot_version: str
    schema_version: str
    rule_version: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PathResult:
    current_node: str
    target_node: str
    steps: tuple[RoadmapNode, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    triggered_rules: tuple[Rule, ...]
    confidence: float
    trace: TraceRecord
    effort_estimate: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        data["triggered_rules"] = [rule.to_dict() for rule in self.triggered_rules]
        data["trace"] = self.trace.to_dict()
        return data


@dataclass(frozen=True)
class ImportReport:
    source: str
    accepted: bool
    checksum: str
    snapshot_version: str
    warnings: tuple[str, ...] = ()
    activated_records: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

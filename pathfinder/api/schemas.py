"""Pydantic API schemas for Pathfinder V1.

All response types are locked here. The frontend contract is defined
by these models — changes to these schemas require coordinated frontend updates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Error Model (standardized, 5 codes) ────────────────────────────

class ApiError(BaseModel):
    """Standard error response. 5 error codes cover all V1 scenarios."""

    error: str = Field(description="Machine-readable error code")
    detail: str = Field(description="Human-readable message")

    # Error codes:
    #   AUTH_REQUIRED    — missing or invalid demo/admin token
    #   FORBIDDEN        — demo token used on admin endpoint
    #   NOT_FOUND        — assessment, questionnaire, or node not found
    #   VALIDATION_ERROR — invalid answers, missing fields, out-of-range values
    #   SERVER_ERROR     — unexpected internal error


# ─── Health ─────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    mode: str
    graph_backend: str
    stakeholder_types: list[str]
    rule_version: str | None
    audit_events: int
    audit_chain_valid: bool
    import_reports: dict[str, Any] = Field(default_factory=dict)


# ─── Questionnaire ──────────────────────────────────────────────────

class QuestionSchema(BaseModel):
    question_id: str
    label: str
    question_type: str
    required: bool = True
    options: list[str] = []
    min_value: int | None = None
    max_value: int | None = None


class QuestionnaireResponse(BaseModel):
    stakeholder_type: str
    version: str
    title: str
    target_scenarios: list[str]
    questions: list[QuestionSchema]


class StakeholderTypesResponse(BaseModel):
    stakeholder_types: list[str]
    mock_data_mode: bool = True


# ─── Assessment ─────────────────────────────────────────────────────

class CreateAssessmentRequest(BaseModel):
    stakeholder_type: str
    target_scenario: str


class CreateAssessmentResponse(BaseModel):
    assessment_id: str
    stakeholder_type: str
    target_scenario: str
    status: str
    mock_data_mode: bool = True


class BatchAnswersRequest(BaseModel):
    answers: dict[str, Any]


class StakeholderStateResponse(BaseModel):
    stakeholder_type: str
    target_scenario: str
    answers: dict[str, Any]
    maturity_scores: dict[str, int]
    capabilities: list[str]
    missing_capabilities: list[str]
    regulatory_flags: list[str]
    confidence: float
    confidence_warnings: list[str]
    questionnaire_version: str
    schema_version: str
    derivation_mode: str | None = None
    pain_points: list[str] = Field(default_factory=list)
    source_wp2_stakeholder_id: str | None = None
    source_wp2_snapshot_version: str | None = None
    source_wp3_snapshot_version: str | None = None


# ─── Recommendation ─────────────────────────────────────────────────

class TraceRecordResponse(BaseModel):
    answer_ids: list[str]
    roadmap_node_ids: list[str]
    triggered_rule_ids: list[str]
    regulatory_refs: list[str]
    upstream_snapshot_version: str
    schema_version: str
    rule_version: str
    confidence: float


class RuleActionResponse(BaseModel):
    title: str
    text: str
    node_id: str | None = None
    warning: str | None = None
    block: bool = False


class RuleResponse(BaseModel):
    rule_id: str
    rule_type: str
    priority: int
    applies_to: list[str]
    condition: dict[str, Any]
    action: RuleActionResponse
    compliance_refs: list[str]
    rule_version: str


class RecommendationResponse(BaseModel):
    status: str = Field(description="ready | blocked")
    current_node: str
    target_node: str
    next_steps: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    triggered_rules: list[dict[str, Any]]
    trace: TraceRecordResponse
    confidence: float
    path_backend: str = "python"  # "python" | "cypher" | "n/a (blocked)"


# ─── Report ─────────────────────────────────────────────────────────

class ReportResponse(BaseModel):
    disclaimer: str
    audit_chain_valid: bool
    missing_data_warnings: list[str]
    session: dict[str, Any]
    readiness_snapshot: StakeholderStateResponse
    recommended_path: RecommendationResponse


# ─── Roadmap ────────────────────────────────────────────────────────

class RoadmapNodeResponse(BaseModel):
    node_id: str
    label: str
    description: str
    dimension: str
    maturity_level: int
    stakeholder_types: list[str]
    prerequisites: list[str] = []


class RoadmapEdgeResponse(BaseModel):
    edge_id: str
    from_node_id: str
    to_node_id: str
    relation_type: str = "prerequisite"


class RoadmapResponse(BaseModel):
    nodes: list[RoadmapNodeResponse]
    edges: list[RoadmapEdgeResponse]


# ─── Admin ──────────────────────────────────────────────────────────

class AdminImportResponse(BaseModel):
    accepted: bool
    mode: str = "demo"
    message: str = ""
    source: str
    checksum: str
    snapshot_version: str
    warnings: list[str] = []
    activated_records: int


class AdminReloadResponse(BaseModel):
    accepted: bool
    active_rule_version: str

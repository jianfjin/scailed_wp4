"""Pydantic API schemas for Pathfinder V1.

All response types are locked here. The frontend contract is defined
by these models — changes to these schemas require coordinated frontend updates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ─── Error Models ─────────────────────────────────────────────────

class ApiError(BaseModel):
    """Machine-readable error carried inside FastAPI's detail envelope."""

    current_validity: CurrentValidityResponse | None = None
    error: str = Field(description="Machine-readable error code")
    detail: str = Field(description="Human-readable message")

    # Error codes:
    #   AUTH_REQUIRED    — missing or invalid demo/admin token
    #   FORBIDDEN        — demo token used on admin endpoint
    #   NOT_FOUND        — assessment, questionnaire, or node not found
    #   VALIDATION_ERROR — invalid answers, missing fields, out-of-range values
    #   SERVER_ERROR     — unexpected internal error
    #   RATE_LIMITED     — per-token/IP rate limit exceeded


class ApiErrorEnvelope(BaseModel):
    """Wire format shared by HTTP exceptions and middleware errors."""

    detail: ApiError


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
    active_snapshot_ids: dict[str, str] = Field(default_factory=dict)
    regulatory_status: str = "unverified"


# ─── Questionnaire ──────────────────────────────────────────────────

class QuestionSchema(BaseModel):
    question_id: str
    label: str
    question_type: str
    required: bool = True
    options: list[str] = []
    min_value: int | None = None
    max_value: int | None = None
    maturity_dimension: str | None = None
    state_field: str | None = None
    capability_id: str | None = None


class QuestionnaireResponse(BaseModel):
    stakeholder_type: str
    version: str
    title: str
    target_scenarios: list[str]
    questions: list[QuestionSchema]
    profile_id: str = "legacy-v1"
    capability_vocabulary: list[str] = Field(default_factory=list)


class StakeholderTypesResponse(BaseModel):
    stakeholder_types: list[str]
    mock_data_mode: bool = True


# ─── Assessment ─────────────────────────────────────────────────────

class CreateAssessmentRequest(BaseModel):
    stakeholder_type: str
    target_scenario: str


class CreateAssessmentResponse(BaseModel):
    profile_id: str = "legacy-v1"
    semantics_version: str = "legacy-v1.0"
    answer_revision: int = 0
    assessment_id: str
    stakeholder_type: str
    target_scenario: str
    status: str
    mock_data_mode: bool = True
    snapshot_ids: dict[str, str] | None = None
    evaluation_date: str | None = None
    boundary_generation_id: str | None = None


class BatchAnswersRequest(BaseModel):
    answers: dict[str, Any]


class StakeholderStateResponse(BaseModel):
    profile_id: str = "legacy-v1"
    capability_findings: dict[str, CapabilityFindingResponse] = Field(default_factory=dict)
    confidence_meaning: str | None = None
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
    condition_evaluations: list[RuleEvaluationResponse] = Field(default_factory=list)
    answer_ids: list[str]
    roadmap_node_ids: list[str]
    triggered_rule_ids: list[str]
    regulatory_refs: list[str]
    upstream_snapshot_version: str
    schema_version: str
    rule_version: str
    confidence: float
    snapshot_ids: dict[str, str] | None = None
    evaluation_date: str | None = None
    boundary_generation_id: str | None = None


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
    regulatory_status: str = "verified"


class RecommendationResponse(BaseModel):
    status: str = Field(description="ready | blocked | degraded")
    profile_id: str = "legacy-v1"
    semantics_version: str | None = None
    result_id: str | None = None
    answer_revision: int | None = None
    content_hash: str | None = None
    recommendation_kind: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    confidence_meaning: str | None = None
    capability_findings: dict[str, CapabilityFindingResponse] = Field(default_factory=dict)
    current_validity: CurrentValidityResponse | None = None
    current_node: str
    target_node: str
    next_steps: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    triggered_rules: list[dict[str, Any]]
    trace: TraceRecordResponse
    confidence: float
    path_backend: str = "python"  # "python" | "cypher" | "n/a (blocked)"
    regulatory_status: str | None = None


# ─── Report ─────────────────────────────────────────────────────────

class ReportResponse(BaseModel):
    disclaimer: str
    audit_chain_valid: bool
    missing_data_warnings: list[str]
    session: dict[str, Any]
    readiness_snapshot: StakeholderStateResponse | None
    recommended_path: RecommendationResponse
    result: ResultRecordResponse | None = None
    current_validity: CurrentValidityResponse | None = None


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


class ResultHistoryEntryResponse(BaseModel):
    result_id: str
    answer_revision: int | None
    binding_status: str
    profile_id: str


class AssessmentStateResponse(BaseModel):
    """Current state of an assessment session (GET /v1/assessments/{id})."""

    model_config = ConfigDict(extra="allow")
    result_history: list[ResultHistoryEntryResponse] = Field(default_factory=list)

    assessment_id: str
    stakeholder_type: str
    target_scenario: str
    status: str
    mock_data_mode: bool
    snapshot_ids: dict[str, str] | None = None
    evaluation_date: str | None = None
    boundary_generation_id: str | None = None


class TopEndpoint(BaseModel):
    endpoint: str
    count: int


class RequestStatsResponse(BaseModel):
    total_requests: int
    error_count: int
    error_rate: float
    unique_ips: int
    active_now: int
    top_endpoints: list[TopEndpoint]


class RequestLogEntry(BaseModel):
    timestamp: str
    ip: str
    method: str
    endpoint: str
    status_code: int | None = None
    duration_ms: int = 0
    user_agent: str = ""
    error_message: str | None = None
    assessment_id: str | None = None


class AbusiveIp(BaseModel):
    ip: str
    request_count: int
    endpoints: list[str] = []


class FhirBundle(BaseModel):
    """Minimal FHIR Bundle envelope (contents follow the FHIR version)."""

    model_config = ConfigDict(extra="allow")

    resourceType: str = "Bundle"
    type: str
    entry: list[dict[str, Any]] = []


class WithdrawalReceipt(BaseModel):
    accepted: bool
    created: bool
    notice_id: str
    lifecycle_revision: int


class CapabilityFindingResponse(BaseModel):
    capability_id: str
    judgment: str
    source: str
    answer_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    verification_status: str


class ConditionEvaluationResponse(BaseModel):
    truth: str
    missing_fields: list[str] = Field(default_factory=list)
    condition: dict[str, Any] = Field(default_factory=dict)
    actual: Any = None
    children: list[ConditionEvaluationResponse] = Field(default_factory=list)


class RuleEvaluationResponse(ConditionEvaluationResponse):
    rule_id: str
    critical: bool


class RuntimeInputResponse(BaseModel):
    contract: str
    snapshot_id: str
    producer_wp: str
    dependency_path: list[str]


class AffectedInputResponse(RuntimeInputResponse):
    notice_id: str
    reason: str


class CurrentValidityResponse(BaseModel):
    valid: bool
    status: str
    lifecycle_revision: int
    affected_inputs: list[AffectedInputResponse] = Field(default_factory=list)


class ResultRecordResponse(BaseModel):
    result_id: str
    assessment_id: str
    answer_revision: int | None
    answers: dict[str, Any] | None
    findings: dict[str, CapabilityFindingResponse] | None
    readiness_snapshot: StakeholderStateResponse | None = None
    input_set: list[RuntimeInputResponse]
    profile_id: str
    semantics_version: str
    evaluation_date: str | None = None
    binding_status: str
    original_output: dict[str, Any]
    content_hash: str | None = None

for response in (ApiError, ApiErrorEnvelope, StakeholderStateResponse, TraceRecordResponse, RecommendationResponse, ReportResponse, ResultRecordResponse):
    response.model_rebuild()

"""Derive Pathfinder readiness state from WP2/WP3 evidence."""

from __future__ import annotations

from typing import Any

from pathfinder.core.models import SCHEMA_VERSION, StakeholderState

REQUIRED_EHDS_CAPABILITIES = (
    "data-catalog",
    "legal-basis",
    "secure-processing",
    "audit-log",
    "data-quality-kpi",
)

CAPABILITIES_BY_DIMENSION = {
    "governance": ("legal-basis", "audit-log"),
    "data": ("data-catalog", "data-quality-kpi", "secure-processing", "federated-analytics"),
    "compliance": ("legal-basis", "secure-processing", "audit-log"),
}

PAIN_POINT_FLAGS = {
    "gdpr_ehds_alignment": "gdpr-review-needed",
    "ehds_interop_gap": "ehds-rule-unverified",
    "cross_border_data_governance": "cross-border-use",
}


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


def _maturity_for(capabilities: set[str], expected: tuple[str, ...]) -> int:
    if not expected:
        return 1
    coverage = len(capabilities.intersection(expected)) / len(expected)
    return max(1, min(5, round(1 + coverage * 4)))


def derive_readiness_state(
    *,
    stakeholder: dict[str, Any],
    target_scenario: str,
    wp2_snapshot_version: str,
    wp3_snapshot_version: str,
) -> StakeholderState:
    stakeholder_type = str(stakeholder.get("stakeholder_type", "")).strip()
    capabilities = _string_list(stakeholder.get("capabilities"))
    pain_points = _string_list(stakeholder.get("pain_points"))
    capability_set = set(capabilities)

    maturity_scores = {
        dimension: _maturity_for(capability_set, expected)
        for dimension, expected in CAPABILITIES_BY_DIMENSION.items()
    }
    missing_capabilities = tuple(
        capability for capability in sorted(REQUIRED_EHDS_CAPABILITIES) if capability not in capability_set
    )
    regulatory_flags = tuple(
        sorted({PAIN_POINT_FLAGS[pain_point] for pain_point in pain_points if pain_point in PAIN_POINT_FLAGS})
    )

    warnings: list[str] = []
    confidence = 1.0
    if not capabilities:
        warnings.append("WP2 capabilities missing or empty")
        confidence = 0.7

    answers = {
        "derivation_mode": "wp2_wp3",
        "source_wp2_stakeholder_id": stakeholder_type,
        "source_wp2_snapshot_version": wp2_snapshot_version,
        "source_wp3_snapshot_version": wp3_snapshot_version,
        "pain_points": list(pain_points),
        "capabilities": list(capabilities),
        "missing_capabilities": list(missing_capabilities),
        "regulatory_flags": list(regulatory_flags),
        "maturity_scores": dict(maturity_scores),
    }

    return StakeholderState(
        stakeholder_type=stakeholder_type,
        target_scenario=target_scenario,
        answers=answers,
        maturity_scores=maturity_scores,
        capabilities=capabilities,
        missing_capabilities=missing_capabilities,
        regulatory_flags=regulatory_flags,
        confidence=confidence,
        confidence_warnings=tuple(warnings),
        questionnaire_version="derived-wp2-wp3-v1",
        schema_version=SCHEMA_VERSION,
        upstream_snapshot_version=wp3_snapshot_version or wp2_snapshot_version,
    )

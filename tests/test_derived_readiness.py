from pathfinder.services.derived_readiness import derive_readiness_state


def test_derive_readiness_uses_wp2_capabilities() -> None:
    state = derive_readiness_state(
        stakeholder={
            "stakeholder_type": "academic-spinout-001",
            "description": "Academic spinout",
            "capabilities": ["legal-basis", "secure-processing", "federated-analytics"],
            "pain_points": ["gdpr_ehds_alignment", "ehds_interop_gap"],
        },
        target_scenario="secondary-use-readiness",
        wp2_snapshot_version="wp2-test-v1",
        wp3_snapshot_version="wp3-test-v1",
    )

    assert state.stakeholder_type == "academic-spinout-001"
    assert state.target_scenario == "secondary-use-readiness"
    assert state.capabilities == ("federated-analytics", "legal-basis", "secure-processing")
    assert state.missing_capabilities == ("audit-log", "data-catalog", "data-quality-kpi")
    assert state.regulatory_flags == ("ehds-rule-unverified", "gdpr-review-needed")
    assert state.maturity_scores == {"governance": 3, "data": 3, "compliance": 4}
    assert state.answers["derivation_mode"] == "wp2_wp3"
    assert state.answers["source_wp2_stakeholder_id"] == "academic-spinout-001"
    assert state.answers["source_wp2_snapshot_version"] == "wp2-test-v1"
    assert state.answers["source_wp3_snapshot_version"] == "wp3-test-v1"
    assert state.confidence == 1.0


def test_derive_readiness_handles_missing_capabilities_with_warning() -> None:
    state = derive_readiness_state(
        stakeholder={
            "stakeholder_type": "empty-stakeholder",
            "description": "Empty stakeholder",
            "pain_points": ["cross_border_data_governance"],
        },
        target_scenario="secondary-use-readiness",
        wp2_snapshot_version="wp2-test-v1",
        wp3_snapshot_version="wp3-test-v1",
    )

    assert state.capabilities == ()
    assert state.maturity_scores == {"governance": 1, "data": 1, "compliance": 1}
    assert state.missing_capabilities == (
        "audit-log",
        "data-catalog",
        "data-quality-kpi",
        "legal-basis",
        "secure-processing",
    )
    assert state.regulatory_flags == ("cross-border-use",)
    assert state.confidence == 0.7
    assert "WP2 capabilities missing or empty" in state.confidence_warnings

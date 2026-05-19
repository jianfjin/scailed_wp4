"""Pytest fixtures for Pathfinder tests."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: object) -> None:
    """Default tests to zero-config demo mode unless a test overrides it."""
    os.environ.setdefault("PATHFINDER_MODE", "demo")


def pytest_unconfigure(config: object) -> None:
    """No fixture cleanup required."""


# ═══════════════════════════════════════════════════════════════════════
# Visualization module fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_report() -> dict:
    """Realistic Pathfinder report dict exercising all adapter code paths.

    Returns a dict matching AssessmentService.report() output shape.
    Two exclusion rules (blockers) + one compound-and preference rule.
    5 path steps with mixed maturity levels.
    """
    return {
        "recommended_path": {
            "status": "blocked",
            "confidence": 0.72,
            "path_backend": "langgraph",
            "blockers": [
                "GDPR review required",
                "Missing data catalog",
            ],
            "triggered_rules": [
                {
                    "rule_id": "WP8-GDPR-REVIEW-001",
                    "rule_type": "exclusion",
                    "priority": 90,
                    "condition": {
                        "field": "regulatory_flags",
                        "operator": "contains",
                        "value": "gdpr-review-needed",
                    },
                    "action": {
                        "title": "GDPR Review Required",
                        "text": "GDPR review required",
                        "node_id": "node-2",
                        "block": True,
                        "warning": "Immediate action needed",
                    },
                    "compliance_refs": ["GDPR Art. 30", "GDPR Art. 35"],
                    "source_doc_ref": "gdpr-compliance-checklist",
                },
                {
                    "rule_id": "DATA-CATALOG-GAP-003",
                    "rule_type": "exclusion",
                    "priority": 70,
                    "condition": {
                        "field": "missing_capabilities",
                        "operator": "contains",
                        "value": "data-catalog",
                    },
                    "action": {
                        "title": "Missing Data Catalog",
                        "text": "Missing data catalog",
                        "node_id": "node-2",
                        "block": True,
                    },
                    "compliance_refs": ["EHDS Art. 58"],
                    "source_doc_ref": "ehds-data-quality",
                },
                {
                    "rule_id": "WP8-UNVERIFIED-002",
                    "rule_type": "preference",
                    "priority": 50,
                    "condition": {
                        "and": [
                            {
                                "field": "governance_maturity",
                                "operator": "lt",
                                "value": 3,
                            },
                            {
                                "field": "regulatory_flags",
                                "operator": "contains",
                                "value": "unverified-source",
                            },
                        ],
                    },
                    "action": {
                        "title": "Verify External Sources",
                        "text": "Verify external data sources",
                        "node_id": None,
                        "block": False,
                        "warning": "Recommended action",
                    },
                    "compliance_refs": [],
                    "source_doc_ref": "",
                },
            ],
            "next_steps": [
                {
                    "node_id": "node-1",
                    "label": "Self-Assessment",
                    "description": "Complete initial self-assessment",
                    "dimension": "governance",
                    "maturity_level": 1,
                },
                {
                    "node_id": "node-2",
                    "label": "GDPR Compliance Check",
                    "description": "Review GDPR obligations thoroughly",
                    "dimension": "compliance",
                    "maturity_level": 2,
                },
                {
                    "node_id": "node-3",
                    "label": "Data Catalog Setup",
                    "description": "Set up data catalog infrastructure",
                    "dimension": "infrastructure",
                    "maturity_level": 2,
                },
                {
                    "node_id": "node-4",
                    "label": "Audit Trail",
                    "description": "Establish audit trail mechanisms",
                    "dimension": "governance",
                    "maturity_level": 3,
                },
                {
                    "node_id": "node-5",
                    "label": "EHDS Submission",
                    "description": "Submit EHDS application package",
                    "dimension": "compliance",
                    "maturity_level": 4,
                },
            ],
            "current_node": "node-2",
            "trace": {
                "answer_ids": ["a1", "a2", "a3"],
                "roadmap_node_ids": ["node-1", "node-2", "node-3"],
                "triggered_rule_ids": [
                    "WP8-GDPR-REVIEW-001",
                    "DATA-CATALOG-GAP-003",
                    "WP8-UNVERIFIED-002",
                ],
                "regulatory_refs": ["GDPR Art. 30", "GDPR Art. 35", "EHDS Art. 58"],
                "upstream_snapshot_version": "2025-Q4-v3",
            },
        },
        "session": {
            "stakeholder_type": "Biotech SME",
            "target_scenario": "Secondary Use Readiness",
        },
        "audit_chain_valid": True,
        "disclaimer": "This is an automated compliance assessment.",
        "readiness_snapshot": {
            "answers": {
                "regulatory_flags": ["gdpr-review-needed", "unverified-source"],
                "missing_capabilities": ["data-catalog"],
                "governance_maturity": 2,
            },
        },
    }

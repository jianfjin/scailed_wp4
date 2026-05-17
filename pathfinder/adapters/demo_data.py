"""Realistic demo inputs used until WP2/WP3/WP8 structured data lands."""

from __future__ import annotations

from pathfinder.core.models import (
    Question,
    Questionnaire,
    QuestionType,
    RoadmapEdge,
    RoadmapNode,
)

STAKEHOLDER_TYPES = (
    "biotech-sme",
    "ai-factory-operator",
    "health-data-access-body",
    "health-data-infrastructure",
    "research-infrastructure",
)


def demo_questionnaires() -> list[Questionnaire]:
    questions = (
        Question(
            "governance_maturity",
            "Governance readiness",
            QuestionType.NUMERIC,
            min_value=1,
            max_value=5,
            maturity_dimension="governance",
        ),
        Question(
            "data_maturity",
            "Data readiness",
            QuestionType.NUMERIC,
            min_value=1,
            max_value=5,
            maturity_dimension="data",
        ),
        Question(
            "compliance_maturity",
            "Compliance readiness",
            QuestionType.NUMERIC,
            min_value=1,
            max_value=5,
            maturity_dimension="compliance",
        ),
        Question(
            "capabilities",
            "Known capabilities",
            QuestionType.MULTI_CHOICE,
            options=(
                "data-catalog",
                "legal-basis",
                "secure-processing",
                "audit-log",
                "data-quality-kpi",
            ),
        ),
        Question(
            "missing_capabilities",
            "Missing capabilities",
            QuestionType.MULTI_CHOICE,
            options=(
                "data-catalog",
                "legal-basis",
                "secure-processing",
                "audit-log",
                "data-quality-kpi",
            ),
        ),
        Question(
            "regulatory_flags",
            "Regulatory flags",
            QuestionType.MULTI_CHOICE,
            required=False,
            options=("gdpr-review-needed", "ehds-rule-unverified", "cross-border-use"),
        ),
    )
    return [
        Questionnaire(
            stakeholder_type=stakeholder,
            version="demo-questionnaire-v1",
            title=f"EHDS readiness assessment for {stakeholder}",
            target_scenarios=("secondary-use-readiness", "ai-factory-validation"),
            questions=questions,
        )
        for stakeholder in STAKEHOLDER_TYPES
    ]


def demo_roadmap() -> tuple[list[RoadmapNode], list[RoadmapEdge]]:
    nodes = [
        RoadmapNode(
            "generic-intake",
            "Confirm stakeholder baseline",
            "Capture stakeholder type, target scenario, and current maturity.",
            "governance",
            1,
            ("all",),
        ),
        RoadmapNode(
            "governance-scope",
            "Define governance scope",
            "Document accountability, owners, and decision boundaries.",
            "governance",
            2,
            ("all",),
            ("generic-intake",),
        ),
        RoadmapNode(
            "legal-basis",
            "Confirm legal basis",
            "Map intended secondary-use scenario to legal and ethics review inputs.",
            "compliance",
            3,
            ("all",),
            ("governance-scope",),
            source_wp="WP8",
            source_doc_ref="WP8-rule-demo",
        ),
        RoadmapNode(
            "secure-processing",
            "Prepare secure processing environment",
            "Identify SPE, AI Factory, or infrastructure controls needed for the use case.",
            "data",
            4,
            ("biotech-sme", "ai-factory-operator", "health-data-infrastructure", "research-infrastructure"),
            ("legal-basis",),
            metadata={"target_scenarios": ("ai-factory-validation",)},
        ),
        RoadmapNode(
            "access-body-review",
            "Prepare HDAB review package",
            "Assemble traceability evidence and readiness report for review discussion.",
            "compliance",
            4,
            ("health-data-access-body", "biotech-sme", "research-infrastructure"),
            ("legal-basis",),
            source_wp="WP8",
            metadata={"target_scenarios": ("secondary-use-readiness",)},
        ),
        RoadmapNode(
            "readiness-report",
            "Export readiness evidence",
            "Export blockers, next steps, rule traces, and roadmap references.",
            "governance",
            5,
            ("all",),
            ("secure-processing", "access-body-review"),
        ),
    ]
    edges = [
        RoadmapEdge("e1", "generic-intake", "governance-scope"),
        RoadmapEdge("e2", "governance-scope", "legal-basis"),
        RoadmapEdge("e3", "legal-basis", "secure-processing"),
        RoadmapEdge("e4", "legal-basis", "access-body-review"),
        RoadmapEdge("e5", "secure-processing", "readiness-report"),
        RoadmapEdge("e6", "access-body-review", "readiness-report"),
    ]
    return nodes, edges


def demo_rule_bundle() -> dict[str, object]:
    return {
        "version": "demo-rules-v1",
        "rules": [
            {
                "rule_id": "WP8-GDPR-REVIEW-001",
                "rule_type": "preference",
                "priority": 100,
                "applies_to": ["all"],
                "condition": {
                    "field": "regulatory_flags",
                    "operator": "contains",
                    "value": "gdpr-review-needed",
                },
                "action": {
                    "title": "GDPR review needed",
                    "text": "Confirm GDPR and ethics review inputs before downstream data access.",
                    "node_id": "legal-basis",
                    "warning": "compliance trace is provisional until WP8 confirms the rule bundle",
                },
                "compliance_refs": ["GDPR-Review", "EHDS-Secondary-Use"],
                "source_doc_ref": "docs/12_merged_pathfinder_spec.md#F5",
            },
            {
                "rule_id": "WP8-UNVERIFIED-002",
                "rule_type": "preference",
                "priority": 80,
                "applies_to": ["all"],
                "condition": {
                    "field": "regulatory_flags",
                    "operator": "contains",
                    "value": "ehds-rule-unverified",
                },
                "action": {
                    "title": "EHDS rule unverified",
                    "text": "Mark compliance output unverified until WP8 rules are loaded.",
                    "warning": "compliance unverified",
                },
                "compliance_refs": ["EHDS-Unverified"],
                "source_doc_ref": "docs/12_merged_pathfinder_spec.md#F9",
            },
            {
                "rule_id": "DATA-CATALOG-GAP-003",
                "rule_type": "preference",
                "priority": 50,
                "applies_to": ["biotech-sme", "research-infrastructure"],
                "condition": {
                    "field": "missing_capabilities",
                    "operator": "contains",
                    "value": "data-catalog",
                },
                "action": {
                    "title": "Data catalog gap",
                    "text": "Create or update a data catalog before requesting secondary-use review.",
                    "node_id": "governance-scope",
                },
                "compliance_refs": ["WP3-Roadmap"],
                "source_doc_ref": "docs/12_merged_pathfinder_spec.md#F4",
            },
        ],
        "tests": [
            {
                "name": "gdpr flag triggers GDPR review rule",
                "state": {
                    "stakeholder_type": "biotech-sme",
                    "target_scenario": "secondary-use-readiness",
                    "answers": {
                        "governance_maturity": 2,
                        "data_maturity": 2,
                        "compliance_maturity": 2,
                        "capabilities": ["secure-processing"],
                        "missing_capabilities": ["data-catalog"],
                        "regulatory_flags": ["gdpr-review-needed"],
                    },
                },
                "expected_rule_ids": ["WP8-GDPR-REVIEW-001", "DATA-CATALOG-GAP-003"],
            }
        ],
    }

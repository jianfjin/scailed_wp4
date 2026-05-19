#!/usr/bin/env python3
"""Generate 1000 mock records each for WP2, WP3, WP8.
Writes updated fixture JSON files.
Usage: python scripts/generate_1000_mock_records.py
"""

import json
import random
import sys
from pathlib import Path

random.seed(42)  # deterministic generation

FIXTURES_DIR = Path("services/mock/fixtures")


# ═══════════════════════════════════════════════════════════════════
# WP2: 1000 Stakeholder Types
# ═══════════════════════════════════════════════════════════════════

WP2_CATEGORIES = [
    "pharma-sme", "biobank", "clinical-cro", "device-manufacturer",
    "hospital-network", "insurance-payer", "academic-spinout",
    "public-health-agency", "digital-health-platform",
]

WP2_CAPABILITIES = [
    "data-catalog", "legal-basis", "secure-processing",
    "audit-log", "data-quality-kpi", "market-surveillance",
    "federated-analytics", "synthetic-data-gen",
]

WP2_PAIN_POINTS = [
    "ehds_interop_gap", "limited_regulatory_expertise",
    "cross_border_data_governance", "gdpr_ehds_alignment",
    "legacy_review_process", "certification_timeline",
]


def generate_wp2(count: int = 1000) -> list[dict]:
    stakeholders = []
    for i in range(count):
        cat = WP2_CATEGORIES[i % len(WP2_CATEGORIES)]
        idx = i // len(WP2_CATEGORIES) + 1
        stype = f"{cat}-{idx:03d}"
        stakeholders.append({
            "stakeholder_type": stype,
            "description": f"Generated {cat.replace('-', ' ')} stakeholder #{idx} for EHDS secondary-use readiness assessment.",
            "capabilities": random.sample(WP2_CAPABILITIES, k=random.randint(2, 4)),
            "pain_points": random.sample(WP2_PAIN_POINTS, k=random.randint(1, 3)),
        })
    return stakeholders


# ═══════════════════════════════════════════════════════════════════
# WP3: 1000 Nodes + ~2000 Edges (Layered DAG)
# ═══════════════════════════════════════════════════════════════════

LAYERS = 10
NODES_PER_LAYER = 100  # total = 1000

DIMENSIONS = ["governance", "data", "compliance"]
DIMENSION_WEIGHTS = [0.30, 0.35, 0.35]

STAKEHOLDER_BASE = [
    "biotech-sme", "ai-factory-operator", "health-data-access-body",
    "health-data-infrastructure", "research-infrastructure",
]

DIM_LABEL_TEMPLATES = {
    "governance": [
        "Establish governance framework v{layer}",
        "Define accountability matrix v{layer}",
        "Setup steering committee level {layer}",
        "Document decision boundaries phase {layer}",
        "Ratify data governance policy {layer}",
    ],
    "data": [
        "Deploy data catalog tier {layer}",
        "Validate data quality metrics v{layer}",
        "Implement secure processing layer {layer}",
        "Configure federated query node {layer}",
        "Benchmark data pipeline stage {layer}",
    ],
    "compliance": [
        "Complete GDPR review cycle {layer}",
        "Submit EHDS compliance package v{layer}",
        "Audit consent management phase {layer}",
        "Certify processing environment level {layer}",
        "File regulatory submission round {layer}",
    ],
}


def generate_wp3(count: int = 1000) -> dict:
    nodes = []
    edges = []

    # Pre-generate nodes per layer
    layer_nodes: list[list[str]] = [[] for _ in range(LAYERS)]

    edge_id_counter = 0
    for layer in range(LAYERS):
        maturity = layer + 1
        for pos in range(NODES_PER_LAYER):
            idx = layer * NODES_PER_LAYER + pos
            node_id = f"n{idx:04d}"
            dim = random.choices(DIMENSIONS, weights=DIMENSION_WEIGHTS, k=1)[0]
            templates = DIM_LABEL_TEMPLATES[dim]
            label = templates[idx % len(templates)].format(layer=maturity)

            # Stakeholder assignment
            if random.random() < 0.30:
                stypes = ["all"]
            else:
                n_stypes = random.randint(1, 3)
                stypes = list(random.sample(STAKEHOLDER_BASE, k=n_stypes))

            # Prerequisites (filled after edges generated)
            target_scenarios = []
            if random.random() < 0.25:
                target_scenarios.append("ai-factory-validation")
            if random.random() < 0.25:
                target_scenarios.append("secondary-use-readiness")

            nodes.append({
                "node_id": node_id,
                "label": label,
                "description": f"Auto-generated {dim} milestone at maturity level {maturity}. "
                               f"Node {idx} in layered DAG with {NODES_PER_LAYER} peers at this level.",
                "dimension": dim,
                "maturity_level": maturity,
                "stakeholder_types": stypes,
                "prerequisites": [],  # filled below
                "source_wp": "WP3-gen",
                "source_doc_ref": f"gen-1000-layer-{layer}",
                "confidence": round(random.uniform(0.7, 1.0), 2),
                "metadata": {
                    "target_scenarios": target_scenarios,
                    "generated": True,
                    "layer": layer,
                },
            })

            layer_nodes[layer].append(node_id)

    # Generate edges: each node in layer N connects to 1-3 nodes in layer N+1
    for layer in range(LAYERS - 1):
        next_ids = layer_nodes[layer + 1]
        for from_id in layer_nodes[layer]:
            n_edges = random.randint(1, 3)
            targets = random.sample(next_ids, k=min(n_edges, len(next_ids)))
            for to_id in targets:
                edge_id = f"e{edge_id_counter:04d}"
                edges.append({
                    "edge_id": edge_id,
                    "from_node_id": from_id,
                    "to_node_id": to_id,
                    "relation_type": "prerequisite",
                    "required": random.random() < 0.85,
                    "source_doc_ref": "gen-1000",
                })
                edge_id_counter += 1

    # Fill prerequisites from edges
    incoming: dict[str, list[str]] = {}
    for e in edges:
        incoming.setdefault(e["to_node_id"], []).append(e["from_node_id"])

    for node in nodes:
        node["prerequisites"] = incoming.get(node["node_id"], [])

    return {
        "version": "gen-1000-v1",
        "snapshot_date": "2026-05-19",
        "nodes": nodes,
        "edges": edges,
    }


# ═══════════════════════════════════════════════════════════════════
# WP8: 1000 Rules
# ═══════════════════════════════════════════════════════════════════

RULE_FIELDS = [
    ("regulatory_flags", "contains"),
    ("missing_capabilities", "contains"),
    ("capabilities", "contains"),
    ("governance_maturity", "gte"),
    ("data_maturity", "gte"),
    ("compliance_maturity", "lte"),
]

RULE_FIELD_VALUES = {
    "regulatory_flags": ["gdpr-review-needed", "ehds-rule-unverified", "cross-border-use", "ai-act-review", "data-localization"],
    "missing_capabilities": ["data-catalog", "legal-basis", "secure-processing", "audit-log", "data-quality-kpi"],
    "capabilities": ["data-catalog", "legal-basis", "secure-processing", "audit-log", "data-quality-kpi"],
    "governance_maturity": [1, 2, 3, 4, 5],
    "data_maturity": [1, 2, 3, 4, 5],
    "compliance_maturity": [1, 2, 3, 4, 5],
}

COMPLIANCE_REFS = [
    "GDPR-Art.5", "GDPR-Art.6", "GDPR-Art.9", "GDPR-Art.25",
    "GDPR-Art.30", "GDPR-Art.32", "GDPR-Art.35", "GDPR-Art.37",
    "EHDS-Art.33", "EHDS-Art.34", "EHDS-Art.46", "EHDS-Art.50",
    "EHDS-Art.51", "EHDS-Art.54", "AI-Act-Art.9", "AI-Act-Art.10",
    "AI-Act-Art.15", "AI-Act-Art.16", "DGA-Art.5", "DGA-Art.7",
    "DGA-Art.12", "DGA-Art.31", "NIS2-Art.21", "MDR-Annex-I",
]


def generate_wp8(count: int = 1000, node_ids: list[str] | None = None) -> dict:
    rules = []
    for i in range(count):
        rule_id = f"WP8-RULE-{i+1:04d}"

        field, operator = random.choice(RULE_FIELDS)
        value_pool = RULE_FIELD_VALUES[field]
        if operator in ("gte", "lte"):
            value = random.choice(value_pool)
        else:
            value = random.choice(value_pool)

        rule_type = "preference" if random.random() < 0.60 else "eligibility"
        n_stypes = random.randint(1, 3)
        applies_to = list(random.sample(STAKEHOLDER_BASE, k=n_stypes))
        if random.random() < 0.15:
            applies_to = ["all"]

        action_node = None
        if node_ids and random.random() < 0.70:
            action_node = random.choice(node_ids)

        rules.append({
            "rule_id": rule_id,
            "rule_type": rule_type,
            "priority": random.randint(10, 100),
            "applies_to": applies_to,
            "condition": {
                "field": field,
                "operator": operator,
                "value": value,
            },
            "action": {
                "title": f"Generated rule action for {rule_id}",
                "text": f"Automated compliance check: {field} {operator} {value}. "
                        f"Review and confirm before proceeding to next maturity level.",
                "node_id": action_node,
                "warning": f"Generated rule — verify against WP8 official bundle",
            },
            "compliance_refs": random.sample(COMPLIANCE_REFS, k=random.randint(1, 3)),
            "source_doc_ref": f"gen-1000-rule-{i}",
            "rule_version": "gen-1000-rules-v1",
            "effective_from": None,
            "effective_until": None,
            "parent_rule_id": None,
        })

    # Generate 20 test cases
    tests = []
    for t in range(20):
        stakeholder = random.choice(STAKEHOLDER_BASE)
        triggered = random.sample([r["rule_id"] for r in rules], k=random.randint(1, 4))
        tests.append({
            "name": f"gen-test-{t+1:02d}: {stakeholder} triggers {len(triggered)} rules",
            "state": {
                "stakeholder_type": stakeholder,
                "target_scenario": random.choice(["secondary-use-readiness", "ai-factory-validation"]),
                "answers": {
                    "governance_maturity": random.randint(1, 5),
                    "data_maturity": random.randint(1, 5),
                    "compliance_maturity": random.randint(1, 5),
                    "capabilities": random.sample(WP2_CAPABILITIES, k=random.randint(1, 4)),
                    "missing_capabilities": random.sample(WP2_CAPABILITIES, k=random.randint(0, 2)),
                    "regulatory_flags": random.sample(
                        ["gdpr-review-needed", "ehds-rule-unverified", "cross-border-use"],
                        k=random.randint(0, 2),
                    ),
                },
            },
            "expected_rule_ids": triggered,
        })

    return {
        "version": "gen-1000-rules-v1",
        "snapshot_date": "2026-05-19",
        "rules": rules,
        "tests": tests,
    }


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    fixtures = FIXTURES_DIR.resolve()
    print(f"Generating 1000-record mock fixtures → {fixtures}")

    # WP2
    wp2 = generate_wp2(1000)
    path2 = fixtures / "wp2_data.json"
    path2.write_text(json.dumps(wp2, indent=2))
    print(f"  WP2: {len(wp2)} stakeholders → {path2}")

    # WP3
    wp3 = generate_wp3(1000)
    path3 = fixtures / "wp3_data.json"
    path3.write_text(json.dumps(wp3, indent=2))
    print(f"  WP3: {len(wp3['nodes'])} nodes + {len(wp3['edges'])} edges → {path3}")

    # WP8
    wp8 = generate_wp8(1000, node_ids=[n["node_id"] for n in wp3["nodes"]])
    path8 = fixtures / "wp8_data.json"
    path8.write_text(json.dumps(wp8, indent=2))
    print(f"  WP8: {len(wp8['rules'])} rules + {len(wp8['tests'])} tests → {path8}")

    # Stats
    print(f"\nDone. Total records: {len(wp2) + len(wp3['nodes']) + len(wp8['rules'])}")
    print(f"  Edge count: {len(wp3['edges'])}")
    print(f"  Layers: {LAYERS} × {NODES_PER_LAYER} nodes")


if __name__ == "__main__":
    main()

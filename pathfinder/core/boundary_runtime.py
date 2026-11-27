"""Build a validated, isolated runtime generation from WP snapshots."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Mapping

from pathfinder.adapters.boundary import questionnaire_from_snapshots
from pathfinder.core.boundary_validation import canonical_checksum, validate_documents
from pathfinder.core.graph import InMemoryRoadmapGraph
from pathfinder.core.compliance import ComplianceEvaluator
from pathfinder.core.models import RoadmapEdge, RoadmapNode, Rule, RuleAction, RuleType
from pathfinder.core.questionnaire import QuestionnaireEngine
from pathfinder.core.solver import PathfinderSolver
from pathfinder.core.contract_registry import LEGACY_PROFILE, profile_for_contracts


@dataclass(frozen=True)
class BoundaryGeneration:
    snapshot_ids: Mapping[str, str]
    questionnaire_ids: Mapping[str, str]
    snapshot_hashes: Mapping[str, str]
    questionnaire_engine: QuestionnaireEngine
    graph: InMemoryRoadmapGraph
    solver: PathfinderSolver
    rules: tuple[Rule, ...]
    regulatory_status: str
    warnings: tuple[str, ...]
    profile_id: str = LEGACY_PROFILE.profile_id
    semantics_version: str = LEGACY_PROFILE.semantics_version
    questionnaire_contract: str = LEGACY_PROFILE.questionnaire_contract
    rulebundle_contract: str = LEGACY_PROFILE.rulebundle_contract

    def versions_for(self, stakeholder_type: str) -> dict[str, str]:
        return {**self.snapshot_ids, self.questionnaire_contract: self.questionnaire_ids[stakeholder_type]}

    def rules_for(self, evaluation_date: date) -> tuple[list[Rule], bool]:
        active = [rule for rule in self.rules if
                  (rule.effective_from is None or rule.effective_from <= evaluation_date) and
                  (rule.effective_until is None or evaluation_date <= rule.effective_until)]
        return active, len(active) != len(self.rules)


def build_boundary_generation(snapshots: list[dict]) -> BoundaryGeneration:
    """Validate and prepare the entire generation before publishing any part of it."""
    snapshots = deepcopy(snapshots)
    errors, warnings = validate_documents(snapshots)
    if errors:
        raise ValueError("; ".join(errors))
    groups: dict[str, list[dict]] = {}
    for snapshot in snapshots:
        groups.setdefault(snapshot["contract"], []).append(snapshot)
    profile = profile_for_contracts(groups)
    for name in ("pf.taxonomy.v1", "pf.roadmap.v1", profile.rulebundle_contract):
        if len(groups.get(name, [])) != 1:
            raise ValueError(f"activation requires exactly one {name} snapshot")
    if not groups.get(profile.questionnaire_contract) or set(groups) - profile.runtime_contracts:
        raise ValueError("activation requires questionnaires and only runtime input contracts")
    tax, road, bundle = (groups[k][0] for k in ("pf.taxonomy.v1", "pf.roadmap.v1", profile.rulebundle_contract))
    questionnaires = [questionnaire_from_snapshots(tax, q) for q in groups[profile.questionnaire_contract]]
    ids = {q["payload"]["stakeholder_type"]: q["manifest"]["snapshot_id"] for q in groups[profile.questionnaire_contract]}
    if len(ids) != len(questionnaires):
        raise ValueError("activation requires one questionnaire per stakeholder type")
    nodes = [RoadmapNode(node_id=n["node_id"], label=n["label"], description=n.get("description", ""),
        dimension=n["dimension"], maturity_level=n["maturity_level"], stakeholder_types=tuple(n["stakeholder_types"]),
        prerequisites=tuple(n["prerequisites"]), source_wp=n["source_wp"], source_doc_ref=n["source_doc_ref"],
        confidence=n["confidence"], metadata=n.get("metadata", {}))
        for n in road["payload"]["nodes"] if n.get("status", "active") == "active"]
    node_ids = {n.node_id for n in nodes}
    edges = [RoadmapEdge(edge_id=e["edge_id"], from_node_id=e["from_node_id"], to_node_id=e["to_node_id"],
        relation_type=e["relation_type"], required=e.get("required", True), source_doc_ref=e.get("source_doc_ref", ""))
        for e in road["payload"]["edges"] if e["from_node_id"] in node_ids and e["to_node_id"] in node_ids]
    pairs = {(edge.from_node_id, edge.to_node_id) for edge in edges}
    for node in nodes:
        for prerequisite in node.prerequisites:
            if prerequisite not in node_ids:
                raise ValueError(f"active node {node.node_id} has inactive prerequisite {prerequisite}")
            if (prerequisite, node.node_id) not in pairs:
                edges.append(RoadmapEdge(edge_id=f"implicit:{prerequisite}:{node.node_id}",
                    from_node_id=prerequisite, to_node_id=node.node_id, relation_type="prerequisite"))
    graph = InMemoryRoadmapGraph(nodes, edges)
    for q in questionnaires:
        if not graph.applicable_nodes(q.stakeholder_type):
            raise ValueError(f"no active roadmap nodes for {q.stakeholder_type}")
    references = {r["ref_id"]: r for r in bundle["payload"]["references"]}
    rules = []
    unverified = False
    for r in bundle["payload"]["rules"]:
        if r["action"].get("node_id") and r["action"]["node_id"] not in node_ids:
            raise ValueError(f"rule {r['rule_id']} references an inactive roadmap node")
        unverified |= r["status"] != "verified" or not r["compliance_refs"] or any(
            ref not in references or references[ref]["status"] != "in-force" for ref in r["compliance_refs"])
        action = r["action"]
        rules.append(Rule(rule_id=r["rule_id"], rule_type=RuleType(r["rule_type"]), priority=r["priority"],
            applies_to=tuple(r["applies_to"]), condition=r["condition"],
            action=RuleAction(title=action["title"], text=action["text"], node_id=action.get("node_id"),
                              warning=action.get("warning"), block=action.get("block", False)),
            compliance_refs=tuple(r["compliance_refs"]), parent_rule_id=r.get("parent_rule_id"),
            source_doc_ref=r["source_doc_ref"], rule_version=r["rule_version"],
            effective_from=date.fromisoformat(r["effective_from"]) if r.get("effective_from") else None,
            effective_until=date.fromisoformat(r["effective_until"]) if r.get("effective_until") else None,
            regulatory_status="verified" if r["status"] == "verified" and r["compliance_refs"] and all(ref in references and references[ref]["status"] == "in-force" for ref in r["compliance_refs"]) else "unverified"))
    if unverified:
        warnings.append("Regulatory rules or references are provisional or unverified.")
    versions = {d["contract"]: d["manifest"]["snapshot_id"] for d in (tax, road, bundle)}
    hashes = {d["manifest"]["snapshot_id"]: canonical_checksum(d) for d in snapshots}
    return BoundaryGeneration(MappingProxyType(versions), MappingProxyType(ids), MappingProxyType(hashes), QuestionnaireEngine(questionnaires),
        graph, PathfinderSolver(graph, ComplianceEvaluator(profile.profile_id)), tuple(rules), "unverified" if unverified else "verified", tuple(warnings),
        profile.profile_id, profile.semantics_version, profile.questionnaire_contract, profile.rulebundle_contract)

"""In-memory roadmap graph used for demo mode and tests."""

from __future__ import annotations

from collections import deque

from pathfinder.core.exceptions import NoFeasiblePathError
from pathfinder.core.models import RoadmapEdge, RoadmapNode, StakeholderState


# Category → roadmap base type mapping for generated stakeholder types.
# WP2 generates categories like "academic-spinout-001", "public-health-agency-005".
# These don't directly match the roadmap's base stakeholder_types.
# This table maps each WP2 category prefix to the closest roadmap base type.
STAKEHOLDER_GROUP_MAP: dict[str, str] = {
    "pharma-sme": "biotech-sme",
    "biobank": "research-infrastructure",
    "clinical-cro": "biotech-sme",
    "device-manufacturer": "ai-factory-operator",
    "hospital-network": "health-data-access-body",
    "insurance-payer": "health-data-access-body",
    "academic-spinout": "research-infrastructure",
    "public-health-agency": "health-data-infrastructure",
    "digital-health-platform": "ai-factory-operator",
}


def _stakeholder_group(stakeholder_type: str) -> str:
    """Map a WP2 generated stakeholder type to its roadmap base group.

    For types like "academic-spinout-001" or "pharma-sme-042", the
    category prefix determines the group. Unknown types fall back
    to the raw type value (which will match "all" nodes).

    NOTE: Keys are sorted by length descending to avoid prefix collision —
    e.g., "pharma" must not match before "pharma-sme".
    """
    sorted_prefixes = sorted(STAKEHOLDER_GROUP_MAP, key=len, reverse=True)
    for prefix in sorted_prefixes:
        if stakeholder_type.startswith(prefix):
            return STAKEHOLDER_GROUP_MAP[prefix]
    return stakeholder_type


class InMemoryRoadmapGraph:
    def __init__(self, nodes: list[RoadmapNode], edges: list[RoadmapEdge]) -> None:
        self.nodes = {node.node_id: node for node in nodes}
        self.edges = edges
        self._outgoing: dict[str, list[str]] = {}
        for edge in edges:
            self._outgoing.setdefault(edge.from_node_id, []).append(edge.to_node_id)

    def applicable_nodes(self, stakeholder_type: str) -> list[RoadmapNode]:
        # Also check against the stakeholder's roadmap group so generated
        # types (e.g. "academic-spinout-001") see type-specific nodes.
        group = _stakeholder_group(stakeholder_type)
        return [
            node
            for node in self.nodes.values()
            if node.applies_to(stakeholder_type) or node.applies_to(group)
        ]

    def locate_current(self, state: StakeholderState) -> RoadmapNode:
        """Find the best starting node for a given stakeholder state.

        Returns the node whose maturity level best matches the stakeholder's
        maturity scores, along the matching dimension.  Tie-broken by
        preferring higher maturity.
        """
        applicable = self.applicable_nodes(state.stakeholder_type)
        if not applicable:
            return self.nodes["generic-intake"]

        def score(node: RoadmapNode) -> tuple[int, int]:
            maturity = state.maturity_scores.get(node.dimension, 1)
            return (abs(maturity - node.maturity_level), node.maturity_level)

        return sorted(applicable, key=score)[0]

    def locate_current_candidates(self, state: StakeholderState) -> list[RoadmapNode]:
        """Return all applicable nodes sorted by maturity-match score.

        The solver uses this list to find a non-blocked starting node
        when the first candidate would trigger blocking rules.
        """
        applicable = self.applicable_nodes(state.stakeholder_type)
        if not applicable:
            return [self.nodes["generic-intake"]]

        def score(node: RoadmapNode) -> tuple[int, int]:
            maturity = state.maturity_scores.get(node.dimension, 1)
            return (abs(maturity - node.maturity_level), node.maturity_level)

        return sorted(applicable, key=score)

    def locate_target(self, state: StakeholderState) -> RoadmapNode:
        applicable = self.applicable_nodes(state.stakeholder_type)
        candidates = [
            node
            for node in applicable
            if state.target_scenario in node.metadata.get("target_scenarios", ())
        ]
        if not candidates:
            candidates = applicable
        return sorted(candidates, key=lambda node: node.maturity_level, reverse=True)[0]

    def shortest_path(self, start_node_id: str, target_node_id: str) -> tuple[RoadmapNode, ...]:
        if start_node_id not in self.nodes:
            raise NoFeasiblePathError(f"unknown start node: {start_node_id}")
        if target_node_id not in self.nodes:
            raise NoFeasiblePathError(f"unknown target node: {target_node_id}")

        queue: deque[tuple[str, list[str]]] = deque([(start_node_id, [start_node_id])])
        seen = {start_node_id}
        while queue:
            current, path = queue.popleft()
            if current == target_node_id:
                return tuple(self.nodes[node_id] for node_id in path)
            for next_node in self._outgoing.get(current, []):
                if next_node not in seen:
                    seen.add(next_node)
                    queue.append((next_node, [*path, next_node]))

        raise NoFeasiblePathError(f"no roadmap path from {start_node_id} to {target_node_id}")

    def to_dict(self) -> dict[str, list[dict[str, object]]]:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

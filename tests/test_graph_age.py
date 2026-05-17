"""AGE graph backend tests.

These tests verify the AGE backend interface parity with InMemoryGraph.
They do NOT require a running PostgreSQL + AGE instance — the AGE-specific
Cypher queries are tested via integration tests on a real database.
"""

from __future__ import annotations

import unittest

from pathfinder.adapters.demo_data import demo_roadmap
from pathfinder.core.graph_age import AgeRoadmapGraph
from pathfinder.core.models import StakeholderState


class AgeGraphParityTests(unittest.TestCase):
    """Verify AGE backend interface parity with InMemoryRoadmapGraph."""

    def setUp(self) -> None:
        nodes, edges = demo_roadmap()
        self.graph = AgeRoadmapGraph(dsn="postgresql://test:test@localhost:5432/test")
        self.graph.nodes = {node.node_id: node for node in nodes}
        self.graph.edges = list(edges)
        self.graph._connected = False

    def test_locate_current_finds_closest_maturity_node(self) -> None:
        state = StakeholderState(
            stakeholder_type="biotech-sme",
            target_scenario="secondary-use-readiness",
            answers={"governance_maturity": 2},
            maturity_scores={"governance": 2, "data": 2, "compliance": 2},
            capabilities=("secure-processing",),
            missing_capabilities=(),
            regulatory_flags=(),
            confidence=1.0,
            confidence_warnings=(),
            questionnaire_version="v1",
        )
        node = self.graph.locate_current(state)
        self.assertIsNotNone(node)
        self.assertTrue(hasattr(node, 'node_id'))

    def test_shortest_path_between_known_nodes(self) -> None:
        if len(self.graph.nodes) < 2:
            self.skipTest("need at least 2 demo nodes")
        node_ids = list(self.graph.nodes.keys())
        path = self.graph.shortest_path(node_ids[0], node_ids[-1])
        self.assertGreaterEqual(len(path), 1)
        self.assertEqual(path[0].node_id, node_ids[0])

    def test_shortest_path_unknown_start_raises(self) -> None:
        from pathfinder.core.exceptions import NoFeasiblePathError

        with self.assertRaises(NoFeasiblePathError):
            self.graph.shortest_path("nonexistent", list(self.graph.nodes.keys())[0])

    def test_to_dict_returns_nodes_and_edges(self) -> None:
        data = self.graph.to_dict()
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertGreater(len(data["nodes"]), 0)

    def test_applicable_nodes_filters_by_stakeholder(self) -> None:
        nodes = self.graph.applicable_nodes("biotech-sme")
        self.assertGreater(len(nodes), 0)
        for node in nodes:
            self.assertTrue(
                "biotech-sme" in node.stakeholder_types or "all" in node.stakeholder_types
            )


if __name__ == "__main__":
    unittest.main()

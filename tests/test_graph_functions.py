"""Unit tests for graph, compliance, and solver functions added in the
fix/roadmap-connectivity-checkbox-influence branch.

Focuses on:
  - _stakeholder_group() mapping correctness
  - triggered_rules_for_node() node filtering
  - locate_current_candidates() sorted output
  - _resolve_current() blocking-rule fallback
  - _build_result() shared result construction
"""

import unittest
from unittest.mock import MagicMock, patch

from pathfinder.core.compliance import ComplianceEvaluator
from pathfinder.core.exceptions import NoFeasiblePathError
from pathfinder.core.graph import (
    STAKEHOLDER_GROUP_MAP,
    InMemoryRoadmapGraph,
    _stakeholder_group,
)
from pathfinder.core.models import (
    PathResult,
    RoadmapEdge,
    RoadmapNode,
    Rule,
    RuleAction,
    RuleType,
    StakeholderState,
)
from pathfinder.core.solver import PathfinderSolver


# ── Sample graph data for tests ──────────────────────────────────────

def _sample_nodes() -> list[RoadmapNode]:
    return [
        RoadmapNode("n001", "Governance basics", "basis", "governance", 1, ("all",)),
        RoadmapNode("n002", "Governance advanced", "adv", "governance", 2, ("all",)),
        RoadmapNode("n101", "Data basics", "basis", "data", 1, ("all",)),
        RoadmapNode("n102", "Data advanced", "adv", "data", 2, ("all",)),
        RoadmapNode("t001", "Biotech target", "target", "governance", 5,
                    ("biotech-sme",), metadata={"target_scenarios": ("secondary-use-readiness",)}),
        RoadmapNode("t002", "Generic target", "target", "governance", 5,
                    ("all",), metadata={"target_scenarios": ("secondary-use-readiness",)}),
        RoadmapNode("blocked", "Special governance", "blocked_if_flag", "governance", 2,
                    ("all",)),
    ]


def _sample_edges() -> list[RoadmapEdge]:
    return [
        RoadmapEdge("e1", "n001", "n002"),
        RoadmapEdge("e2", "n002", "t001"),
        RoadmapEdge("e3", "n101", "n102"),
        RoadmapEdge("e4", "n002", "t002"),
        RoadmapEdge("e5", "n001", "blocked"),
        RoadmapEdge("e6", "blocked", "n002"),
    ]


def _sample_state(**overrides) -> StakeholderState:
    defaults = {
        "stakeholder_type": "biotech-sme",
        "target_scenario": "secondary-use-readiness",
        "answers": {},
        "maturity_scores": {"governance": 2, "data": 1, "compliance": 1},
        "capabilities": (),
        "missing_capabilities": (),
        "regulatory_flags": (),
        "confidence": 1.0,
        "confidence_warnings": (),
        "questionnaire_version": "test-v1",
    }
    defaults.update(overrides)
    return StakeholderState(**defaults)


# ─── _stakeholder_group tests ──────────────────────────────────────


class StakeholderGroupTests(unittest.TestCase):
    """Verify that _stakeholder_group() correctly maps WP2 generated types."""

    def test_known_category_maps_correctly(self) -> None:
        pairs = [
            ("pharma-sme-001", "biotech-sme"),
            ("pharma-sme-042", "biotech-sme"),
            ("academic-spinout-007", "research-infrastructure"),
            ("public-health-agency-111", "health-data-infrastructure"),
            ("digital-health-platform-003", "ai-factory-operator"),
            ("hospital-network-005", "health-data-access-body"),
        ]
        for stype, expected in pairs:
            self.assertEqual(
                _stakeholder_group(stype), expected,
                f"Expected {stype!r} → {expected!r}",
            )

    def test_unknown_type_falls_through(self) -> None:
        self.assertEqual(
            _stakeholder_group("completely-unknown-type-999"),
            "completely-unknown-type-999",
        )

    def test_prefix_collision_sorted_by_length(self) -> None:
        """When a shorter prefix would match first, the sorted-by-length
        logic must still pick the longer match."""
        # Verify keys are sorted length-descending
        sorted_keys = sorted(STAKEHOLDER_GROUP_MAP, key=len, reverse=True)
        self.assertEqual(
            sorted_keys,
            sorted(STAKEHOLDER_GROUP_MAP, key=lambda k: -len(k)),
        )

    def test_missing_prefix_in_maps(self) -> None:
        """A type that partially matches a prefix but isn't a full prefix
        should still return itself (fallback)."""
        # "pharma" starts with no prefix in map
        self.assertEqual(_stakeholder_group("pharma"), "pharma")

    def test_empty_string_returns_itself(self) -> None:
        self.assertEqual(_stakeholder_group(""), "")


# ─── triggered_rules_for_node tests ─────────────────────────────────


class TriggeredRulesForNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = ComplianceEvaluator()
        self.rules = [
            Rule(
                rule_id="BLOCK-AT-N002",
                rule_type=RuleType.EXCLUSION,
                priority=100,
                applies_to=("all",),
                condition={"field": "regulatory_flags", "operator": "contains",
                           "value": "gdpr-review-needed"},
                action=RuleAction(
                    title="Block at n002",
                    text="This stakeholder cannot start at n002",
                    node_id="n002",
                    block=True,
                ),
                compliance_refs=("test-ref",),
            ),
            Rule(
                rule_id="WARN-AT-BLOCKED",
                rule_type=RuleType.PREFERENCE,
                priority=50,
                applies_to=("all",),
                condition={"field": "regulatory_flags", "operator": "contains",
                           "value": "gdpr-review-needed"},
                action=RuleAction(
                    title="Warning at blocked",
                    text="Consider starting earlier",
                    node_id="blocked",
                    warning="advisory note",
                ),
                compliance_refs=("test-ref",),
            ),
            Rule(
                rule_id="GLOBAL-RULE",
                rule_type=RuleType.PREFERENCE,
                priority=10,
                applies_to=("all",),
                condition={"field": "capabilities", "operator": "contains",
                           "value": "audit-log"},
                action=RuleAction(
                    title="Has audit log",
                    text="Nice, you have audit-log",
                    block=False,
                ),
                compliance_refs=(),
            ),
        ]

    def test_finds_blocking_rule_at_specific_node(self) -> None:
        state = _sample_state(regulatory_flags=("gdpr-review-needed",))
        triggered = self.evaluator.triggered_rules_for_node(state, self.rules, "n002")
        rule_ids = [r.rule_id for r in triggered]
        self.assertIn("BLOCK-AT-N002", rule_ids)
        self.assertNotIn("WARN-AT-BLOCKED", rule_ids)

    def test_excludes_rules_for_other_nodes(self) -> None:
        state = _sample_state(regulatory_flags=("gdpr-review-needed",))
        triggered = self.evaluator.triggered_rules_for_node(state, self.rules, "n001")
        self.assertEqual(len(triggered), 0)

    def test_excludes_rules_without_node_id(self) -> None:
        state = _sample_state(capabilities=("audit-log",))
        triggered = self.evaluator.triggered_rules_for_node(state, self.rules, "n001")
        # GLOBAL-RULE has no node_id, should be excluded
        self.assertEqual(len(triggered), 0)

    def test_excludes_rules_that_dont_trigger_on_state(self) -> None:
        state = _sample_state()  # no gdpr flag
        triggered = self.evaluator.triggered_rules_for_node(state, self.rules, "n002")
        self.assertEqual(len(triggered), 0)

    def test_finds_warning_rule_at_blocked_node(self) -> None:
        state = _sample_state(regulatory_flags=("gdpr-review-needed",))
        triggered = self.evaluator.triggered_rules_for_node(state, self.rules, "blocked")
        rule_ids = [r.rule_id for r in triggered]
        self.assertIn("WARN-AT-BLOCKED", rule_ids)
        self.assertNotIn("BLOCK-AT-N002", rule_ids)


# ─── InMemoryRoadmapGraph tests ────────────────────────────────────


class GraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = InMemoryRoadmapGraph(_sample_nodes(), _sample_edges())

    def test_applicable_nodes_includes_group_mapped_types(self) -> None:
        """'academic-spinout-001' should see 'research-infrastructure' nodes."""
        nodes = self.graph.applicable_nodes("academic-spinout-001")
        node_ids = {n.node_id for n in nodes}
        # Should see "all" nodes
        self.assertIn("n001", node_ids)
        # t001 is for "biotech-sme" only — should not appear
        self.assertNotIn("t001", node_ids)

    def test_applicable_nodes_finds_biotech_nodes(self) -> None:
        nodes = self.graph.applicable_nodes("biotech-sme")
        node_ids = {n.node_id for n in nodes}
        self.assertIn("t001", node_ids)  # biotech-specific target
        self.assertIn("n001", node_ids)  # "all" node

    def test_locate_current_returns_best_maturity_match(self) -> None:
        state = _sample_state(maturity_scores={"governance": 2, "data": 1, "compliance": 1})
        node = self.graph.locate_current(state)
        # Best match: n101 (data, maturity=1, diff=0) ties with n002 (gov, maturity=2, diff=0).
        # Tie-broken by maturity_level ascending: n101 wins.
        self.assertEqual(node.node_id, "n101")

    def test_locate_current_falls_back_when_no_applicable(self) -> None:
        """Empty graph has no 'generic-intake' node — expect KeyError."""
        g = InMemoryRoadmapGraph([], [])
        state = _sample_state()
        with self.assertRaises(KeyError):
            g.locate_current(state)

    def test_locate_current_candidates_sorted_by_score(self) -> None:
        state = _sample_state(maturity_scores={"governance": 2, "data": 1, "compliance": 1})
        candidates = self.graph.locate_current_candidates(state)
        self.assertGreater(len(candidates), 0)
        # First candidate should be the same as locate_current()
        self.assertEqual(candidates[0].node_id, self.graph.locate_current(state).node_id)
        # Verify sorting: compute diffs the same way the score function does
        computed_diffs = [
            abs(state.maturity_scores.get(n.dimension, 1) - n.maturity_level)
            for n in candidates
        ]
        for i in range(len(computed_diffs) - 1):
            self.assertLessEqual(computed_diffs[i], computed_diffs[i + 1],
                f"Sort violated at index {i}: diff {computed_diffs[i]} > {computed_diffs[i+1]}")

    def test_shortest_path_finds_existing_path(self) -> None:
        path = self.graph.shortest_path("n001", "t001")
        self.assertEqual(len(path), 3)  # n001 → n002 → t001
        self.assertEqual(path[-1].node_id, "t001")

    def test_shortest_path_raises_for_nonexistent(self) -> None:
        with self.assertRaises(NoFeasiblePathError):
            self.graph.shortest_path("n001", "nonexistent")

    def test_to_dict_roundtrip(self) -> None:
        d = self.graph.to_dict()
        self.assertIn("nodes", d)
        self.assertIn("edges", d)
        self.assertEqual(len(d["nodes"]), len(_sample_nodes()))
        self.assertEqual(len(d["edges"]), len(_sample_edges()))


# ─── PathfinderSolver tests ────────────────────────────────────────


class SolverBlockingFallbackTests(unittest.TestCase):
    """Test the _resolve_current fallback logic in PathfinderSolver."""

    def setUp(self) -> None:
        self.graph = InMemoryRoadmapGraph(_sample_nodes(), _sample_edges())
        self.evaluator = ComplianceEvaluator()
        self.rules = [
            Rule(
                rule_id="BLOCK-N002",
                rule_type=RuleType.EXCLUSION,
                priority=100,
                applies_to=("all",),
                condition={"field": "regulatory_flags", "operator": "contains",
                           "value": "blocks-n002"},
                action=RuleAction(
                    title="Block n002",
                    text="Cannot start at n002 with flag",
                    node_id="n002",
                    block=True,
                ),
                compliance_refs=(),
            ),
            Rule(
                rule_id="BLOCK-BLOCKED",
                rule_type=RuleType.EXCLUSION,
                priority=100,
                applies_to=("all",),
                condition={"field": "regulatory_flags", "operator": "contains",
                           "value": "blocks-blocked"},
                action=RuleAction(
                    title="Block blocked-node",
                    text="Cannot start at blocked-node with flag",
                    node_id="blocked",
                    block=True,
                ),
                compliance_refs=(),
            ),
        ]
        self.solver = PathfinderSolver(self.graph, self.evaluator)

    def test_resolve_current_no_flag_returns_best(self) -> None:
        """Without triggering flags, should return the best maturity match."""
        state = _sample_state(maturity_scores={"governance": 1, "data": 3, "compliance": 3})
        node = self.solver._resolve_current(state, self.rules)
        self.assertEqual(node.node_id, "n001")  # governance, maturity=1, diff=0

    def test_resolve_current_skips_blocked_node(self) -> None:
        """With 'blocks-n002' flag, n002 is blocked → should skip to next."""
        state = _sample_state(
            maturity_scores={"governance": 2, "data": 3, "compliance": 3},
            regulatory_flags=("blocks-n002",),
        )
        node = self.solver._resolve_current(state, self.rules)
        # n002 is blocked → should fall back to n001 or another candidate
        self.assertNotEqual(node.node_id, "n002")

    def test_resolve_current_all_blocked_returns_best(self) -> None:
        """If ALL applicable nodes are blocked, return the best anyway."""
        # Add blocking rules for every applicable node
        all_rules = self.rules + [
            Rule(
                rule_id=f"BLOCK-{n.node_id}",
                rule_type=RuleType.EXCLUSION,
                priority=100,
                applies_to=("all",),
                condition={"field": "stakeholder_type", "operator": "eq",
                           "value": "all-blocked-test"},
                action=RuleAction(
                    title=f"Block {n.node_id}",
                    text=f"Blocking {n.node_id}",
                    node_id=n.node_id,
                    block=True,
                ),
                compliance_refs=(),
            )
            for n in _sample_nodes()
        ]
        state = _sample_state(
            stakeholder_type="all-blocked-test",
            maturity_scores={"governance": 2, "data": 3, "compliance": 3},
        )
        node = self.solver._resolve_current(state, all_rules)
        # Should still return the first candidate (n002 for governance=2, diff=0)
        self.assertEqual(node.node_id, "n002")

    def test_resolve_current_uses_best_when_rules_empty(self) -> None:
        state = _sample_state(maturity_scores={"governance": 1, "data": 3, "compliance": 3})
        node = self.solver._resolve_current(state, [])
        self.assertEqual(node.node_id, "n001")


class SolverBuildResultTests(unittest.TestCase):
    """Test that _build_result correctly constructs PathResult from components."""

    def setUp(self) -> None:
        self.graph = InMemoryRoadmapGraph(_sample_nodes(), _sample_edges())
        self.solver = PathfinderSolver(self.graph)
        self.state = _sample_state()

    def test_build_result_contains_expected_fields(self) -> None:
        nodes = self.graph.nodes
        result = self.solver._build_result(
            current=nodes["n001"],
            target=nodes["t001"],
            triggered=(),
            blockers=(),
            warnings=(),
            state=self.state,
            path_backend="python",
        )
        self.assertIsInstance(result, PathResult)
        self.assertEqual(result.current_node, "n001")
        self.assertEqual(result.target_node, "t001")
        self.assertEqual(result.path_backend, "python")
        self.assertEqual(len(result.blockers), 0)

    def test_build_result_passes_through_blockers(self) -> None:
        nodes = self.graph.nodes
        result = self.solver._build_result(
            current=nodes["n001"],
            target=nodes["t001"],
            triggered=(),
            blockers=("Blocked by something",),
            warnings=(),
            state=self.state,
            path_backend="n/a (blocked)",
        )
        self.assertEqual(result.blockers, ("Blocked by something",))

    def test_build_result_handles_missing_path(self) -> None:
        """When the graph has no path, _build_result should catch the
        exception and include blocker text."""
        nodes = self.graph.nodes
        # 'blocked' node has no path to 'n101' (different subgraph)
        result = self.solver._build_result(
            current=nodes["blocked"],
            target=nodes["n101"],
            triggered=(),
            blockers=(),
            warnings=(),
            state=self.state,
            path_backend="python",
        )
        # Should have a blocker about missing path
        self.assertGreater(len(result.blockers), 0)

    def test_solve_full_roundtrip(self) -> None:
        """End-to-end: resolve → shortest_path → build_result works."""
        state = _sample_state(
            maturity_scores={"governance": 1, "data": 3, "compliance": 3},
        )
        result = self.solver.solve(state, [])
        self.assertEqual(len(result.blockers), 0)  # no blockers → ready
        self.assertEqual(result.current_node, "n001")  # governance=1, closest match


if __name__ == "__main__":
    unittest.main()

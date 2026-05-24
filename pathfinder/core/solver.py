"""Roadmap path solver with dual backend support (Python BFS / AGE Cypher)."""

from __future__ import annotations

from pathfinder.core.compliance import ComplianceEvaluator
from pathfinder.core.exceptions import NoFeasiblePathError
from pathfinder.core.graph import InMemoryRoadmapGraph
from pathfinder.core.graph_age import AgeRoadmapGraph
from pathfinder.core.models import PathResult, Rule, RoadmapNode, StakeholderState, TraceRecord


class PathfinderSolver:
    def __init__(
        self, graph: InMemoryRoadmapGraph, evaluator: ComplianceEvaluator | None = None
    ) -> None:
        self.graph = graph
        self.evaluator = evaluator or ComplianceEvaluator()

    def _resolve_current(self, state: StakeholderState, rules: list[Rule]) -> RoadmapNode:
        """Find the best starting node, skipping any that would immediately block.

        The graph returns nodes sorted by maturity-match.  We iterate through
        candidates and pick the first one that does NOT trigger a blocking rule
        at that node.  If all candidates are blocked, return the best match
        anyway (the solver will include blocker text in the result).
        """
        candidates = self.graph.locate_current_candidates(state)
        for candidate in candidates:
            triggered_at = self.evaluator.triggered_rules_for_node(
                state, rules, candidate.node_id
            )
            if not any(rule.action.block for rule in triggered_at):
                return candidate
        # All candidates blocked — return the best match (graceful degradation)
        return candidates[0]

    def _build_result(
        self,
        current: RoadmapNode,
        target: RoadmapNode,
        triggered: tuple[Rule, ...],
        blockers: tuple[str, ...],
        warnings: tuple[str, ...],
        state: StakeholderState,
        path_backend: str,
    ) -> PathResult:
        """Shared PathResult construction for both sync and async paths."""
        if blockers:
            try:
                steps = self.graph.shortest_path(current.node_id, target.node_id)
            except NoFeasiblePathError:
                steps = (current, target)
        else:
            try:
                steps = self.graph.shortest_path(current.node_id, target.node_id)
            except NoFeasiblePathError as exc:
                blockers = (str(exc),)
                steps = (current,)

        trace = TraceRecord(
            answer_ids=tuple(sorted(state.answers)),
            roadmap_node_ids=tuple(step.node_id for step in steps),
            triggered_rule_ids=tuple(rule.rule_id for rule in triggered),
            regulatory_refs=tuple(
                ref for rule in triggered for ref in rule.compliance_refs
            ),
            upstream_snapshot_version=state.upstream_snapshot_version,
            schema_version=state.schema_version,
            rule_version=triggered[0].rule_version if triggered else "demo-rules-v1",
            confidence=state.confidence,
        )
        return PathResult(
            current_node=current.node_id,
            target_node=target.node_id,
            steps=steps,
            blockers=blockers,
            warnings=warnings,
            triggered_rules=triggered,
            confidence=state.confidence,
            trace=trace,
            path_backend=path_backend,
        )

    def solve(
        self,
        state: StakeholderState,
        rules: list[Rule],
    ) -> PathResult:
        current = self._resolve_current(state, rules)
        target = self.graph.locate_target(state)
        triggered = self.evaluator.triggered_rules(state, rules)
        blockers = tuple(
            rule.action.text
            for rule in triggered
            if rule.rule_type == "exclusion" or rule.action.block
        )
        warnings = tuple(
            item
            for item in (
                *state.confidence_warnings,
                *(rule.action.warning for rule in triggered if rule.action.warning),
            )
            if item
        )
        return self._build_result(
            current, target, triggered, blockers, warnings, state, "python"
        )

    async def solve_async(
        self,
        state: StakeholderState,
        rules: list[Rule],
        use_cypher: bool = False,
    ) -> PathResult:
        current = self._resolve_current(state, rules)
        target = self.graph.locate_target(state)
        triggered = self.evaluator.triggered_rules(state, rules)
        blockers = tuple(
            rule.action.text
            for rule in triggered
            if rule.rule_type == "exclusion" or rule.action.block
        )
        warnings = tuple(
            item
            for item in (
                *state.confidence_warnings,
                *(rule.action.warning for rule in triggered if rule.action.warning),
            )
            if item
        )

        path_backend_used = "python"
        if blockers:
            path_backend_used = "n/a (blocked)"
            try:
                steps = self.graph.shortest_path(current.node_id, target.node_id)
            except NoFeasiblePathError:
                steps = (current, target)
        elif use_cypher and isinstance(self.graph, AgeRoadmapGraph):
            try:
                steps = await self.graph.shortest_path_cypher(
                    current.node_id, target.node_id
                )
                path_backend_used = "cypher"
            except NoFeasiblePathError as exc:
                blockers = (str(exc),)
                steps = (current, target)
                path_backend_used = "cypher (failed)"
        else:
            try:
                steps = self.graph.shortest_path(current.node_id, target.node_id)
            except NoFeasiblePathError as exc:
                blockers = (str(exc),)
                steps = (current, target)

        trace = TraceRecord(
            answer_ids=tuple(sorted(state.answers)),
            roadmap_node_ids=tuple(step.node_id for step in steps),
            triggered_rule_ids=tuple(rule.rule_id for rule in triggered),
            regulatory_refs=tuple(
                ref for rule in triggered for ref in rule.compliance_refs
            ),
            upstream_snapshot_version=state.upstream_snapshot_version,
            schema_version=state.schema_version,
            rule_version=triggered[0].rule_version if triggered else "demo-rules-v1",
            confidence=state.confidence,
        )
        return PathResult(
            current_node=current.node_id,
            target_node=target.node_id,
            steps=steps,
            blockers=blockers,
            warnings=warnings,
            triggered_rules=triggered,
            confidence=state.confidence,
            trace=trace,
            path_backend=path_backend_used,
        )

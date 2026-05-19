"""Tests for pathfinder.visualization — adapter, schemas, graph, renderer.

Focus areas: renderer output correctness, SVG generation edge cases.
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from pathfinder.visualization.adapter import (
    ReportAdapterError,
    build_view_model,
)
from pathfinder.visualization.graph import render_path_svg
from pathfinder.visualization.renderer import render_html
from pathfinder.visualization.schemas import (
    BlockerEvidence,
    ConditionMatch,
    PathStepView,
    ReadinessSummary,
    ReportViewModel,
    RuleCard,
)


# ═══════════════════════════════════════════════════════════════════════
# Schema tests
# ═══════════════════════════════════════════════════════════════════════


class TestSchemasImmutability:
    """All 6 dataclasses are frozen=True — mutation must raise FrozenInstanceError."""

    def test_condition_match_is_frozen(self) -> None:
        cm = ConditionMatch("field_x", "eq", 5, 5, True)
        with pytest.raises(FrozenInstanceError):
            cm.matched = False  # type: ignore[misc]

    def test_blocker_evidence_is_frozen(self) -> None:
        be = BlockerEvidence("text", "R1", "exclusion", 90)
        with pytest.raises(FrozenInstanceError):
            be.blocker_text = "new"  # type: ignore[misc]

    def test_path_step_view_is_frozen(self) -> None:
        ps = PathStepView("n1", "label")
        with pytest.raises(FrozenInstanceError):
            ps.status = "completed"  # type: ignore[misc]

    def test_readiness_summary_is_frozen(self) -> None:
        rs = ReadinessSummary("blocked", 0.5, "python", True)
        with pytest.raises(FrozenInstanceError):
            rs.status = "ready"  # type: ignore[misc]

    def test_rule_card_is_frozen(self) -> None:
        rc = RuleCard("R1", "exclusion", 90)
        with pytest.raises(FrozenInstanceError):
            rc.rule_id = "R2"  # type: ignore[misc]

    def test_report_view_model_is_frozen(self) -> None:
        rs = ReadinessSummary("ready", 0.9, "python", True)
        vm = ReportViewModel(summary=rs)
        with pytest.raises(FrozenInstanceError):
            vm.summary = rs  # type: ignore[misc]


class TestPathStepViewMethods:
    """status_color, status_label methods on PathStepView."""

    def test_status_color_all_statuses(self) -> None:
        colors = {
            "completed": "#166534",
            "blocked": "#9B2C2C",
            "current": "#1E40AF",
            "unreached": "#87867F",
        }
        for status, expected in colors.items():
            ps = PathStepView("n", "l", status=status)
            assert ps.status_color() == expected

    def test_status_color_unknown_defaults_to_gray(self) -> None:
        ps = PathStepView("n", "l", status="nonexistent")
        assert ps.status_color() == "#87867F"

    def test_status_label_all_statuses(self) -> None:
        labels = {
            "completed": "✓ Done",
            "blocked": "✗ Blocked",
            "current": "▶ Here",
            "unreached": "○ Pending",
        }
        for status, expected in labels.items():
            ps = PathStepView("n", "l", status=status)
            assert ps.status_label() == expected


class TestReadinessSummaryMethods:
    """status_label, status_color, status_bg, confidence_pct."""

    def test_blocked_status_label(self) -> None:
        rs = ReadinessSummary("blocked", 0.3, "python", False)
        assert rs.status_label() == "NOT READY"
        assert rs.status_color() == "#9B2C2C"
        assert rs.status_bg() == "#FED7D7"

    def test_ready_status_label(self) -> None:
        rs = ReadinessSummary("ready", 0.95, "langgraph", True)
        assert rs.status_label() == "READY"
        assert rs.status_color() == "#166534"
        assert rs.status_bg() == "#DCFCE7"

    def test_confidence_pct_rounds(self) -> None:
        rs = ReadinessSummary("ready", 0.726, "python", True)
        assert rs.confidence_pct() == "73%"

    def test_confidence_pct_zero(self) -> None:
        rs = ReadinessSummary("blocked", 0.0, "python", False)
        assert rs.confidence_pct() == "0%"

    def test_confidence_pct_perfect(self) -> None:
        rs = ReadinessSummary("ready", 1.0, "python", True)
        assert rs.confidence_pct() == "100%"


# ═══════════════════════════════════════════════════════════════════════
# Adapter tests
# ═══════════════════════════════════════════════════════════════════════


class TestAdapterValidReport:
    """build_view_model with a complete, valid report."""

    def test_summary_fields(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        s = vm.summary
        assert s.status == "blocked"
        assert s.confidence == pytest.approx(0.72)
        assert s.path_backend == "langgraph"
        assert s.audit_chain_valid is True
        assert s.stakeholder_type == "Biotech SME"
        assert s.target_scenario == "Secondary Use Readiness"
        assert s.total_rules_triggered == 3
        assert s.total_blockers == 2
        assert s.total_steps == 5

    def test_blockers_count_and_ids(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        assert len(vm.blockers) == 2
        assert vm.blockers[0].rule_id == "WP8-GDPR-REVIEW-001"
        assert vm.blockers[1].rule_id == "DATA-CATALOG-GAP-003"

    def test_blocker_evidence_fields(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        b0 = vm.blockers[0]
        assert b0.blocker_text == "GDPR review required"
        assert b0.rule_type == "exclusion"
        assert b0.priority == 90
        assert b0.action_title == "GDPR Review Required"
        assert b0.action_text == "GDPR review required"
        assert b0.node_id == "node-2"
        assert len(b0.condition_matches) == 1

    def test_path_steps_count_and_statuses(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        assert len(vm.path_steps) == 5
        # _build_path_steps: with blockers present AND current_node=node-2:
        #   node-1: i==0 + blockers → blocked (not completed — blockers dominate)
        #   node-2: == current_node + blockers → blocked
        #   node-3,4,5: after found_current → unreached
        assert vm.path_steps[0].status == "blocked"
        assert vm.path_steps[1].status == "blocked"
        assert vm.path_steps[2].status == "unreached"
        assert vm.path_steps[3].status == "unreached"
        assert vm.path_steps[4].status == "unreached"

    def test_triggered_rules_all_present(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        assert len(vm.triggered_rules) == 3
        rule_ids = [r.rule_id for r in vm.triggered_rules]
        assert "WP8-GDPR-REVIEW-001" in rule_ids
        assert "DATA-CATALOG-GAP-003" in rule_ids
        assert "WP8-UNVERIFIED-002" in rule_ids

    def test_trace_fields(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        assert len(vm.trace_answer_ids) == 3
        assert vm.trace_answer_ids[0] == "a1"
        assert len(vm.trace_node_ids) == 3
        assert len(vm.trace_rule_ids) == 3
        assert len(vm.trace_refs) == 3
        assert vm.upstream_snapshot == "2025-Q4-v3"

    def test_disclaimer_and_generated_at(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        assert vm.disclaimer == "This is an automated compliance assessment."
        assert len(vm.generated_at) > 0
        # Should match "YYYY-MM-DD HH:MM UTC" format
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", vm.generated_at)


class TestAdapterConditionExtraction:
    """Condition match extraction: contains, eq, compound and/or."""

    def test_contains_operator(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        # WP8-GDPR-REVIEW-001 uses "contains" on regulatory_flags
        rule = _find_rule(vm, "WP8-GDPR-REVIEW-001")
        assert len(rule.condition_matches) == 1
        cm = rule.condition_matches[0]
        assert cm.field == "regulatory_flags"
        assert cm.operator == "contains"
        assert cm.expected == "gdpr-review-needed"
        assert isinstance(cm.actual, list)
        assert cm.matched is True

    def test_eq_operator(self) -> None:
        report = _minimal_report(
            rules=[
                _rule_dict("R-EQ", "preference", 10,
                           condition={"field": "governance_maturity", "operator": "eq", "value": 2},
                           action_text="eq action"),
            ]
        )
        vm = build_view_model(report)
        rule = _find_rule(vm, "R-EQ")
        cm = rule.condition_matches[0]
        assert cm.operator == "eq"
        assert cm.expected == 2
        assert cm.actual == 2
        assert cm.matched is True

    def test_compound_and(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        # WP8-UNVERIFIED-002 uses compound "and" with 2 sub-conditions
        rule = _find_rule(vm, "WP8-UNVERIFIED-002")
        assert len(rule.condition_matches) == 2
        fields = {cm.field for cm in rule.condition_matches}
        assert fields == {"governance_maturity", "regulatory_flags"}

    def test_compound_or(self) -> None:
        report = _minimal_report(
            rules=[
                _rule_dict("R-OR", "preference", 10,
                           condition={
                               "or": [
                                   {"field": "governance_maturity", "operator": "gte", "value": 5},
                                   {"field": "compliance_maturity", "operator": "gte", "value": 4},
                               ],
                           },
                           action_text="or action"),
            ]
        )
        vm = build_view_model(report)
        rule = _find_rule(vm, "R-OR")
        assert len(rule.condition_matches) == 2

    def test_empty_condition_returns_empty_tuple(self) -> None:
        report = _minimal_report(
            rules=[
                _rule_dict("R-EMPTY", "preference", 10,
                           condition={},
                           action_text="no condition"),
            ]
        )
        vm = build_view_model(report)
        rule = _find_rule(vm, "R-EMPTY")
        assert rule.condition_matches == ()


class TestAdapterBlockerRuleBackMapping:
    """Blocker → rule back-mapping via exact action.text match."""

    def test_exact_action_text_match(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        # GDP blocker has action.text == blocker text → match
        gdpr = vm.blockers[0]
        assert gdpr.blocker_text == "GDPR review required"
        assert gdpr.rule_id == "WP8-GDPR-REVIEW-001"
        assert gdpr.action_title == "GDPR Review Required"

    def test_no_match_fallback_to_unknown(self) -> None:
        report = _minimal_report(
            blockers=["Unmatched blocker text"],
            rules=[
                _rule_dict("R-OTHER", "preference", 10,
                           action_text="completely different"),
            ],
        )
        vm = build_view_model(report)
        assert len(vm.blockers) == 1
        b = vm.blockers[0]
        assert b.rule_id == "unknown"
        assert b.rule_type == "unknown"
        assert b.priority == 0


class TestAdapterMissingPath:
    """Reports missing recommended_path or with path=None."""

    def test_missing_recommended_path(self) -> None:
        with pytest.raises(ReportAdapterError, match="missing 'recommended_path'"):
            build_view_model({"session": {}})

    def test_recommended_path_not_a_dict(self) -> None:
        with pytest.raises(ReportAdapterError, match="missing 'recommended_path'"):
            build_view_model({"recommended_path": "not_a_dict"})

    def test_report_not_a_dict(self) -> None:
        with pytest.raises(ReportAdapterError, match="must be a dict"):
            build_view_model([])  # type: ignore[arg-type]

    def test_missing_status_in_path(self) -> None:
        with pytest.raises(ReportAdapterError, match="missing 'status'"):
            build_view_model({"recommended_path": {}})


class TestAdapterEdgeCases:
    """Graceful handling of empty/missing collections and edge cases."""

    def test_empty_blockers(self) -> None:
        report = _minimal_report(blockers=[])
        vm = build_view_model(report)
        assert vm.blockers == ()

    def test_empty_rules(self) -> None:
        report = _minimal_report(rules=[])
        vm = build_view_model(report)
        assert vm.triggered_rules == ()
        assert vm.summary.total_rules_triggered == 0

    def test_empty_path_steps(self) -> None:
        report = _minimal_report(steps=[])
        vm = build_view_model(report)
        assert vm.path_steps == ()
        assert vm.summary.total_steps == 0

    def test_missing_path_backend_defaults_to_python(self) -> None:
        report = _minimal_report()
        # Remove path_backend key entirely
        del report["recommended_path"]["path_backend"]
        vm = build_view_model(report)
        assert vm.summary.path_backend == "python"

    def test_null_triggered_rules_becomes_empty_tuple(self) -> None:
        report = _minimal_report()
        report["recommended_path"]["triggered_rules"] = None  # type: ignore[dict-item]
        vm = build_view_model(report)
        assert vm.triggered_rules == ()
        assert vm.summary.total_rules_triggered == 0

    def test_no_session_defaults_to_empty_strings(self) -> None:
        report = _minimal_report()
        if "session" in report:
            del report["session"]
        vm = build_view_model(report)
        assert vm.summary.stakeholder_type == ""
        assert vm.summary.target_scenario == ""

    def test_no_trace_defaults_to_empty_tuples(self) -> None:
        report = _minimal_report()
        del report["recommended_path"]["trace"]
        vm = build_view_model(report)
        assert vm.trace_answer_ids == ()
        assert vm.trace_node_ids == ()
        assert vm.trace_rule_ids == ()
        assert vm.trace_refs == ()
        assert vm.upstream_snapshot == ""


# ═══════════════════════════════════════════════════════════════════════
# Graph (SVG) tests
# ═══════════════════════════════════════════════════════════════════════


class TestGraphEmpty:
    """Empty steps → empty string."""

    def test_empty_steps_returns_empty_string(self) -> None:
        assert render_path_svg(()) == ""

    def test_empty_tuple_returns_empty_string(self) -> None:
        assert render_path_svg(tuple()) == ""


class TestGraphSvgStructure:
    """SVG output structure and correctness."""

    def test_output_is_valid_svg(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        svg = render_path_svg(vm.path_steps)
        assert svg.startswith("<svg")
        assert svg.rstrip().endswith("</svg>")
        assert 'viewBox="0 0' in svg

    def test_svg_contains_rect_for_each_node(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        svg = render_path_svg(vm.path_steps)
        # 5 nodes → 5 <rect> elements for node bodies + 1 background = 6
        assert svg.count("<rect") == 6

    def test_svg_contains_text_labels(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        svg = render_path_svg(vm.path_steps)
        assert "Self-Assessment" in svg
        assert "GDPR Compliance Che" in svg  # truncated to 20 chars
        assert "Data Catalog Setup" in svg
        assert "Audit Trail" in svg
        assert "EHDS Submission" in svg

    def test_svg_contains_edges_between_levels(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        svg = render_path_svg(vm.path_steps)
        # 5 nodes across levels 1,2,2,3,4: edges 1→2(2), 2→3(2), 3→4(1) = 5
        assert svg.count("<line") == 5

    def test_svg_contains_arrow_markers(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        svg = render_path_svg(vm.path_steps)
        for status in ["completed", "blocked", "current", "unreached"]:
            assert f'id="arrow-{status}"' in svg


class TestGraphColorsByStatus:
    """Nodes and edges colored correctly by status."""

    def test_blocked_node_has_red_colors(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        svg = render_path_svg(vm.path_steps)
        # Blocked fill = #FED7D7 (light red), stroke = #9B2C2C (dark red)
        assert "#FED7D7" in svg  # fill for blocked nodes
        assert "#9B2C2C" in svg  # stroke for blocked nodes

    def test_completed_node_has_green_colors(self) -> None:
        # mock_report has blockers → no completed nodes. Build clean path.
        steps = (
            PathStepView("n1", "Done", status="completed", maturity_level=1, dimension="gov"),
        )
        svg = render_path_svg(steps)
        assert "#DCFCE7" in svg  # fill for completed nodes
        assert "#166534" in svg  # stroke for completed

    def test_unreached_node_has_gray_colors(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        svg = render_path_svg(vm.path_steps)
        assert "#D1CFC5" in svg  # stroke for unreached nodes
        assert "#87867F" in svg  # text color for unreached

    def test_blocked_nodes_have_correct_badge_color(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        svg = render_path_svg(vm.path_steps)
        # The blocked node (node-2) should have a red circle badge
        assert 'fill="#9B2C2C"' in svg  # badge fill appears for blocked

    def test_dash_pattern_varies_by_status(self) -> None:
        # Two completed nodes → edge gets stroke-dasharray="none"
        steps = (
            PathStepView("n1", "A", status="completed", maturity_level=1, dimension="gov"),
            PathStepView("n2", "B", status="completed", maturity_level=2, dimension="gov"),
        )
        svg = render_path_svg(steps)
        assert 'stroke-dasharray="none"' in svg

        # Two non-completed nodes → dashed
        steps2 = (
            PathStepView("n1", "A", status="blocked", maturity_level=1, dimension="gov"),
            PathStepView("n2", "B", status="unreached", maturity_level=2, dimension="gov"),
        )
        svg2 = render_path_svg(steps2)
        assert 'stroke-dasharray="4,4"' in svg2


class TestGraphSingleNode:
    """Single node SVG — no edges, minimal layout."""

    def test_single_node_svg(self) -> None:
        step = PathStepView("n1", "Solo", status="current", maturity_level=2, dimension="test")
        svg = render_path_svg((step,))
        assert svg.startswith("<svg")
        assert svg.rstrip().endswith("</svg>")
        assert "Solo" in svg
        # Single node → no edges
        assert "<line" not in svg


class TestGraphAllStatusesPresent:
    """5 nodes, one of each status + extra → all colors present."""

    def test_all_four_statuses_in_svg(self) -> None:
        steps = (
            PathStepView("n1", "Done", status="completed", maturity_level=1, dimension="gov"),
            PathStepView("n2", "Blocked!", status="blocked", maturity_level=1, dimension="gov"),
            PathStepView("n3", "Current", status="current", maturity_level=2, dimension="comp"),
            PathStepView("n4", "Pending", status="unreached", maturity_level=2, dimension="comp"),
            PathStepView("n5", "Also Done", status="completed", maturity_level=3, dimension="infra"),
        )
        svg = render_path_svg(steps)
        # All four stroke colors present
        assert "#166534" in svg  # completed
        assert "#9B2C2C" in svg  # blocked
        assert "#1E40AF" in svg  # current
        assert "#87867F" in svg  # unreached
        # All four fills present
        assert "#DCFCE7" in svg  # completed fill
        assert "#FED7D7" in svg  # blocked fill
        assert "#DBEAFE" in svg  # current fill


# ═══════════════════════════════════════════════════════════════════════
# Renderer tests
# ═══════════════════════════════════════════════════════════════════════


class TestRendererProducesValidHtml:
    """render_html produces valid HTML with all 5 sections."""

    def test_output_is_complete_html_document(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert html.startswith("<!doctype html>")
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_all_five_sections_present(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "Readiness" in html or "NOT READY" in html  # section 1
        assert "<h2>Blockers</h2>" in html  # section 2
        assert "<h2>Compliance Path</h2>" in html  # section 3
        assert "<h2>Path Graph</h2>" in html  # section 3b
        assert "<h2>Evidence: Triggered Rules</h2>" in html  # section 4

    def test_title_set(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "<title>SCAILED Pathfinder — Compliance Report</title>" in html

    def test_footer_present(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "Generated" in html
        assert "SCAILED WP4 Pathfinder" in html


class TestRendererNoJsNoCdn:
    """No JavaScript, no external CDN references."""

    def test_no_script_tags(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "<script" not in html.lower()

    def test_no_external_cdn_references(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        # No http:// or https:// in src/href attributes
        assert 'src="http' not in html
        assert "src='http" not in html
        assert 'href="http' not in html
        assert "href='http" not in html

    def test_no_onclick_or_event_handlers(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "onclick" not in html.lower()
        assert "onload" not in html.lower()


class TestRendererSvgPresence:
    """SVG present only when path steps exist."""

    def test_svg_present_when_steps_exist(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "<svg" in html
        assert "</svg>" in html

    def test_no_svg_when_no_steps(self) -> None:
        report = _minimal_report(steps=[])
        vm = build_view_model(report)
        html = render_html(vm)
        assert "<svg" not in html


class TestRendererContentIncludes:
    """Key content from the view model appears in rendered HTML."""

    def test_blocker_content_in_html(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "GDPR review required" in html
        assert "Missing data catalog" in html

    def test_path_step_labels_in_html(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "Self-Assessment" in html
        assert "EHDS Submission" in html

    def test_triggered_rule_ids_in_html(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "WP8-GDPR-REVIEW-001" in html
        assert "WP8-UNVERIFIED-002" in html

    def test_audit_trace_section_present(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "Audit Trace" in html
        assert "machine-readable" in html


class TestRendererEmptyCollections:
    """Graceful HTML output when collections are empty."""

    def test_no_blockers_shows_clean_message(self) -> None:
        report = _minimal_report(blockers=[], rules=[])
        vm = build_view_model(report)
        html = render_html(vm)
        assert "No blockers found" in html

    def test_no_rules_shows_clean_message(self) -> None:
        report = _minimal_report(rules=[])
        vm = build_view_model(report)
        html = render_html(vm)
        assert "No rules triggered" in html

    def test_no_steps_shows_clean_message(self) -> None:
        report = _minimal_report(steps=[])
        vm = build_view_model(report)
        html = render_html(vm)
        assert "No path steps available" in html


class TestRendererEvidenceSection:
    """Evidence section: rule cards with condition matches, blocker badges."""

    def test_exclusion_rule_has_blocker_badge(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "BLOCKER" in html

    def test_preference_rule_has_correct_label(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "PREFERENCE" in html

    def test_rule_with_warning_shows_it(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        # WP8-GDPR-REVIEW-001 has warning "Immediate action needed"
        assert "⚠" in html
        assert "Immediate action needed" in html

    def test_condition_matches_rendered_in_evidence(self, mock_report: dict[str, Any]) -> None:
        vm = build_view_model(mock_report)
        html = render_html(vm)
        assert "regulatory_flags" in html
        assert "gdpr-review-needed" in html


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _find_rule(vm: ReportViewModel, rule_id: str) -> RuleCard:
    """Find a RuleCard by rule_id, raising if not found."""
    for r in vm.triggered_rules:
        if r.rule_id == rule_id:
            return r
    raise ValueError(f"Rule {rule_id} not found in triggered_rules")


def _minimal_report(
    *,
    status: str = "ready",
    blockers: list[str] | None = None,
    rules: list[dict[str, Any]] | None = None,
    steps: list[dict[str, Any]] | None = None,
    snapshot_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal valid report dict for targeted adapter tests."""
    if blockers is None:
        blockers = ["Test blocker"]
    if rules is None:
        rules = [
            _rule_dict("R-TEST", "exclusion", 90,
                       condition={"field": "governance_maturity", "operator": "eq", "value": 2},
                       action_text="Test blocker"),
        ]
    if steps is None:
        steps = [
            {"node_id": "node-1", "label": "Step 1", "description": "First", "dimension": "gov", "maturity_level": 1},
        ]
    if snapshot_answers is None:
        snapshot_answers = {
            "governance_maturity": 2,
            "compliance_maturity": 3,
            "regulatory_flags": [],
            "missing_capabilities": [],
        }

    return {
        "recommended_path": {
            "status": status,
            "confidence": 0.85,
            "path_backend": "python",
            "blockers": blockers,
            "triggered_rules": rules,
            "next_steps": steps,
            "current_node": "node-1",
            "trace": {
                "answer_ids": ["a1"],
                "roadmap_node_ids": ["node-1"],
                "triggered_rule_ids": ["R-TEST"],
                "regulatory_refs": [],
                "upstream_snapshot_version": "",
            },
        },
        "session": {
            "stakeholder_type": "Test",
            "target_scenario": "Minimal",
        },
        "audit_chain_valid": True,
        "disclaimer": "",
        "readiness_snapshot": {
            "answers": snapshot_answers,
        },
    }


def _rule_dict(
    rule_id: str,
    rule_type: str,
    priority: int,
    *,
    condition: dict[str, Any] | None = None,
    action_title: str = "",
    action_text: str = "",
    action_node_id: str | None = None,
    action_block: bool = False,
    action_warning: str | None = None,
    compliance_refs: list[str] | None = None,
    source_doc_ref: str = "",
) -> dict[str, Any]:
    """Build a single triggered_rule entry dict."""
    action: dict[str, Any] = {
        "title": action_title or action_text,
        "text": action_text,
        "block": action_block,
    }
    if action_node_id is not None:
        action["node_id"] = action_node_id
    if action_warning is not None:
        action["warning"] = action_warning

    rule: dict[str, Any] = {
        "rule_id": rule_id,
        "rule_type": rule_type,
        "priority": priority,
        "condition": condition or {},
        "action": action,
        "compliance_refs": compliance_refs or [],
        "source_doc_ref": source_doc_ref,
    }
    return rule

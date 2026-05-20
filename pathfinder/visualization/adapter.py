"""Transform Pathfinder report JSON into view model dataclasses.

Guido's contract: recommendation JSON → validated view models → template.
Templates never see raw dicts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pathfinder.visualization.schemas import (
    BlockerEvidence,
    ConditionMatch,
    PathStepView,
    ReadinessSummary,
    ReportViewModel,
    RuleCard,
)


class ReportAdapterError(ValueError):
    """Raised when the report JSON doesn't match the expected shape."""


def build_view_model(raw_report: dict[str, Any]) -> ReportViewModel:
    """Convert a Pathfinder report dict to a validated ReportViewModel.

    Accepts the output of AssessmentService.report().
    """
    _validate_report_shape(raw_report)

    path = raw_report["recommended_path"]
    session = raw_report.get("session", {})

    # ── Summary ──────────────────────────────────────────────────────
    summary = ReadinessSummary(
        status=path.get("status", "unknown"),
        confidence=float(path.get("confidence", 0.0)),
        path_backend=str(path.get("path_backend", "python")),
        audit_chain_valid=bool(raw_report.get("audit_chain_valid", False)),
        stakeholder_type=str(session.get("stakeholder_type", "")),
        target_scenario=str(session.get("target_scenario", "")),
        total_rules_triggered=len(path.get("triggered_rules") or []),
        total_blockers=len(path.get("blockers", [])),
        total_steps=len(path.get("next_steps", [])),
    )

    # ── Rule evidence (triggered rules → RuleCards) ──────────────────
    triggered_rules_raw: list[dict] = path.get("triggered_rules") or []
    rule_cards: list[RuleCard] = []
    for rule_dict in triggered_rules_raw:
        condition = rule_dict.get("condition", {})
        action = rule_dict.get("action", {})
        card = RuleCard(
            rule_id=str(rule_dict.get("rule_id", "")),
            rule_type=str(rule_dict.get("rule_type", "preference")),
            priority=int(rule_dict.get("priority", 0)),
            condition_matches=_build_condition_matches(
                condition, raw_report.get("readiness_snapshot", {})
            ),
            action_title=str(action.get("title", "")),
            action_text=str(action.get("text", "")),
            node_id=str(action.get("node_id")) if action.get("node_id") else None,
            warning=str(action.get("warning")) if action.get("warning") else None,
            compliance_refs=tuple(
                str(r) for r in rule_dict.get("compliance_refs", [])
            ),
            source_doc_ref=str(rule_dict.get("source_doc_ref", "")),
            is_blocker=(
                rule_dict.get("rule_type") == "exclusion"
                or bool(action.get("block", False))
            ),
        )
        rule_cards.append(card)

    # ── Blockers with evidence ───────────────────────────────────────
    blocker_texts: list[str] = [str(b) for b in path.get("blockers", [])]
    blocker_evidences: list[BlockerEvidence] = []
    for blocker_text in blocker_texts:
        # Match blocker text back to the triggering rule
        matching_card = _find_rule_by_action_text(rule_cards, blocker_text)
        if matching_card:
            evidence = BlockerEvidence(
                blocker_text=blocker_text,
                rule_id=matching_card.rule_id,
                rule_type=matching_card.rule_type,
                priority=matching_card.priority,
                condition_matches=matching_card.condition_matches,
                action_title=matching_card.action_title,
                action_text=matching_card.action_text,
                node_id=matching_card.node_id,
                compliance_refs=matching_card.compliance_refs,
                source_doc_ref=matching_card.source_doc_ref,
            )
        else:
            evidence = BlockerEvidence(
                blocker_text=blocker_text,
                rule_id="unknown",
                rule_type="unknown",
                priority=0,
            )
        blocker_evidences.append(evidence)

    # ── Path steps ───────────────────────────────────────────────────
    path_steps = _build_path_steps(
        path.get("next_steps", []),
        blocker_texts,
        str(path.get("current_node", "")),
    )

    # ── Trace ────────────────────────────────────────────────────────
    trace = path.get("trace", {})

    return ReportViewModel(
        summary=summary,
        blockers=tuple(blocker_evidences),
        path_steps=tuple(path_steps),
        triggered_rules=tuple(rule_cards),
        trace_answer_ids=tuple(str(a) for a in trace.get("answer_ids", [])),
        trace_node_ids=tuple(str(n) for n in trace.get("roadmap_node_ids", [])),
        trace_rule_ids=tuple(str(r) for r in trace.get("triggered_rule_ids", [])),
        trace_refs=tuple(str(r) for r in trace.get("regulatory_refs", [])),
        upstream_snapshot=str(trace.get("upstream_snapshot_version", "")),
        disclaimer=str(raw_report.get("disclaimer", "")),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _validate_report_shape(raw: dict[str, Any]) -> None:
    """Check that the report has the minimum expected keys."""
    if not isinstance(raw, dict):
        raise ReportAdapterError("Report must be a dict")
    path = raw.get("recommended_path")
    if not isinstance(path, dict):
        raise ReportAdapterError("Report missing 'recommended_path'")
    if "status" not in path:
        raise ReportAdapterError("recommended_path missing 'status'")


def _build_condition_matches(
    condition: dict[str, Any], snapshot: dict[str, Any]
) -> tuple[ConditionMatch, ...]:
    """Extract flat condition matches from a rule condition dict."""
    if not condition:
        return ()

    # Flat condition: {"field": "regulatory_flags", "operator": "contains", "value": "gdpr"}
    field = condition.get("field")
    operator = condition.get("operator", "eq")
    expected = condition.get("value")

    if field:
        # Resolve actual value from readiness snapshot
        answers = snapshot.get("answers", {})
        actual = answers.get(field)
        if actual is None and isinstance(snapshot, dict):
            actual = snapshot.get(field)
        matched = _compare(actual, operator, expected)
        return (ConditionMatch(
            field=str(field),
            operator=str(operator),
            expected=expected,
            actual=actual,
            matched=matched,
        ),)

    # Compound: "and" / "or" → recurse (flatten one level)
    sub_key = None
    if "and" in condition:
        sub_key = "and"
    elif "or" in condition:
        sub_key = "or"
    if sub_key and isinstance(condition[sub_key], list):
        matches: list[ConditionMatch] = []
        for sub in condition[sub_key]:
            if isinstance(sub, dict):
                matches.extend(_build_condition_matches(sub, snapshot))
        return tuple(matches)

    return ()


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    """Same logic as ComplianceEvaluator._compare."""
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "gt":
        return actual is not None and actual > expected
    if operator == "gte":
        return actual is not None and actual >= expected
    if operator == "lt":
        return actual is not None and actual < expected
    if operator == "lte":
        return actual is not None and actual <= expected
    if operator == "in":
        return actual in expected
    if operator == "not_in":
        return actual not in expected
    if operator == "contains":
        return expected in (actual or ())
    if operator == "exists":
        return actual not in (None, "", [])
    return False


def _find_rule_by_action_text(
    cards: list[RuleCard], blocker_text: str
) -> RuleCard | None:
    """Match a blocker text back to the rule that produced it."""
    for card in cards:
        if card.action_text == blocker_text:
            return card
    return None


def _build_path_steps(
    next_steps: list[dict[str, Any]],
    blocker_texts: list[str],
    current_node: str,
) -> list[PathStepView]:
    """Build PathStepView list with status annotations.
    
    Status rules:
    - Nodes before current_node: completed
    - current_node with blockers: blocked  
    - current_node without blockers: completed
    - Nodes after current_node with blockers: unreached
    - Nodes after current_node without blockers: unreached (future steps)
    """
    if not next_steps:
        return []

    steps: list[PathStepView] = []
    found_current = False

    for i, step_raw in enumerate(next_steps):
        nid = str(step_raw.get("node_id", ""))
        status = "unreached"

        if not found_current:
            if nid == current_node and blocker_texts:
                status = "blocked"
                found_current = True
            elif nid == current_node:
                status = "completed"
                found_current = True
            elif blocker_texts and i == 0:
                # Fallback: first node is the de-facto blocker when
                # current_node isn't in the next_steps list.
                status = "blocked"
            else:
                status = "completed"

        steps.append(
            PathStepView(
                node_id=nid,
                label=str(step_raw.get("label", "")),
                description=str(step_raw.get("description", "")),
                dimension=str(step_raw.get("dimension", "")),
                maturity_level=int(step_raw.get("maturity_level", 1)),
                status=status,
            )
        )

    return steps

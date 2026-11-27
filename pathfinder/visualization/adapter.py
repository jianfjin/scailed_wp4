"""Transform Pathfinder report JSON into view model dataclasses.

Guido's contract: recommendation JSON → validated view models → template.
Templates never see raw dicts.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from pathfinder.visualization.schemas import (
    BlockerEvidence,
    CapabilityFindingView,
    InputValidityView,
    RuleEvaluationView,
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
    validity = raw_report.get("current_validity") or path.get("current_validity") or {}
    evaluations = path.get("trace", {}).get("condition_evaluations", ())
    evaluation_by_rule = {item["rule_id"]: item for item in evaluations}


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
        recommendation_kind=path.get("recommendation_kind", ""),
        profile_id=path.get("profile_id", session.get("profile_id", "legacy-v1")),
        inputs_valid=validity.get("valid"),
        validity_status=validity.get("status", "not_observed"),
        result_id=path.get("result_id", session.get("result_id", "")),
        answer_revision=path.get("answer_revision", session.get("answer_revision")),
        lifecycle_revision=validity.get("lifecycle_revision"),
        binding_status=(raw_report.get("result") or {}).get("binding_status", "not_recorded"),
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
                condition, evaluation_by_rule.get(rule_dict.get("rule_id"))
            ),
            action_title=str(action.get("title", "")),
            action_text=str(action.get("text", "")),
            node_id=str(action.get("node_id")) if action.get("node_id") else None,
            warning=str(action.get("warning")) if action.get("warning") else None,
            compliance_refs=tuple(
                str(r) for r in rule_dict.get("compliance_refs", [])
            ),
            source_doc_ref=str(rule_dict.get("source_doc_ref", "")),
            truth=evaluation_by_rule.get(rule_dict.get("rule_id"), {}).get("truth", "not_evaluated"),
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

    if summary.profile_id == "evidence-v2":
        path_steps = [replace(step, status="current" if step.node_id == path.get("current_node") and summary.inputs_valid is not False else "unreached") for step in path_steps]

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
        disclaimer=(str(raw_report.get("disclaimer", "")) +
                    (" Regulatory status is unverified." if path.get("regulatory_status") == "unverified" else "")),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        missing_information=tuple(path.get("missing_information", ())),
        capability_findings=tuple(CapabilityFindingView(
            capability_id=key, judgment=item.get("judgment", "unknown"),
            source=item.get("source", "unanswered"), verification_status=item.get("verification_status", "unverified"),
            answer_ids=tuple(item.get("answer_ids", ())), evidence_refs=tuple(item.get("evidence_refs", ())),
        ) for key, item in sorted(((raw_report.get("readiness_snapshot") or {}).get("capability_findings") or path.get("capability_findings") or {}).items())),
        affected_inputs=tuple(InputValidityView(
            contract=item["contract"], snapshot_id=item["snapshot_id"], producer_wp=item["producer_wp"],
            notice_id=item["notice_id"], reason=item["reason"], dependency_path=tuple(item.get("dependency_path", ())),
        ) for item in validity.get("affected_inputs", ())),
        condition_evaluations=tuple(RuleEvaluationView(
            rule_id=item["rule_id"], truth=item["truth"], critical=item.get("critical", False),
            condition_matches=_build_condition_matches(item.get("condition", {}), item),
        ) for item in evaluations),
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
    condition: dict[str, Any], evaluation: dict[str, Any] | None = None,
) -> tuple[ConditionMatch, ...]:
    """Project the core trace; older results retain an unevaluated condition."""
    if not condition:
        return ()
    if condition.get("field"):
        truth = evaluation.get("truth") if evaluation else None
        return (ConditionMatch(
            field=str(condition["field"]), operator=str(condition.get("operator", condition.get("op", "eq"))),
            expected=condition.get("value"), actual=evaluation.get("actual") if evaluation else None,
            matched=True if truth == "true" else False if truth == "false" else None,
        ),)
    if evaluation:
        return tuple(match for child in evaluation.get("children", ())
                     for match in _build_condition_matches(child.get("condition", {}), child))
    children = condition.get("and", condition.get("or", [condition["not"]] if "not" in condition else []))
    return tuple(match for child in children for match in _build_condition_matches(child))


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

"""Generate self-contained HTML report from ReportViewModel.

Musk's rule: one file, vertical scroll, no tabs.
html-spec style: ivory background, serif headings, clay accents.
"""

from __future__ import annotations

import html as _html

from pathfinder.visualization.schemas import (
    BlockerEvidence,
    ConditionMatch,
    PathStepView,
    ReadinessSummary,
    ReportViewModel,
    RuleCard,
)
from pathfinder.visualization.graph import render_path_svg


def render_html(vm: ReportViewModel) -> str:
    """Produce complete, self-contained HTML page string."""
    return _HTML_TEMPLATE.format(
        title="SCAILED Pathfinder — Compliance Report",
        readiness_section=_render_readiness(vm.summary),
        blockers_section=_render_blockers(vm),
        path_section=_render_path(vm.path_steps),
        path_graph_section=render_path_svg(vm.path_steps),
        evidence_section=_render_evidence(vm),
        trace_json=_json_safe(vm),
        footer=f"Generated {vm.generated_at} · SCAILED WP4 Pathfinder",
    )


# ═══════════════════════════════════════════════════════════════════════
# Section renderers
# ═══════════════════════════════════════════════════════════════════════


def _render_readiness(s: ReadinessSummary) -> str:
    confidence_bar = ""
    if s.confidence > 0:
        pct = min(int(s.confidence * 100), 100)
        bar_color = s.status_color()
        confidence_bar = f"""
        <div style="margin-top:16px;">
          <div style="font-size:12px; color:var(--g500); margin-bottom:4px;">Confidence</div>
          <div style="background:var(--g200); border-radius:6px; height:8px; overflow:hidden;">
            <div style="background:{bar_color}; width:{pct}%; height:100%; border-radius:6px;"></div>
          </div>
          <div style="font-size:12px; color:var(--g500); margin-top:2px;">{s.confidence_pct()}</div>
        </div>"""

    audit_badge = "✓ Valid" if s.audit_chain_valid else "✗ Invalid"
    audit_color = "#166534" if s.audit_chain_valid else "#9B2C2C"

    return f"""
    <div style="background:{s.status_bg()}; border-radius:14px; padding:32px 36px; margin-bottom:32px;">
      <div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap;">
        <div style="font-family:var(--mono); font-size:48px; font-weight:700; color:{s.status_color()}; letter-spacing:-0.02em;">
          {_esc(s.status_label())}
        </div>
        <div style="flex:1; min-width:200px;">
          <div style="font-size:15px; color:var(--g700);">
            {_esc(s.stakeholder_type)} · {_esc(s.target_scenario)}
          </div>
          <div style="font-size:13px; color:var(--g500); margin-top:4px;">
            Backend: {_esc(s.path_backend)} · Audit Chain: <span style="color:{audit_color};">{audit_badge}</span>
          </div>
        </div>
        <div style="display:flex; gap:12px;">
          <div style="text-align:center;">
            <div style="font-size:28px; font-weight:600; color:var(--slate);">{s.total_rules_triggered}</div>
            <div style="font-size:10px; color:var(--g500); text-transform:uppercase;">Rules</div>
          </div>
          <div style="text-align:center;">
            <div style="font-size:28px; font-weight:600; color:{s.status_color()};">{s.total_blockers}</div>
            <div style="font-size:10px; color:var(--g500); text-transform:uppercase;">Blockers</div>
          </div>
          <div style="text-align:center;">
            <div style="font-size:28px; font-weight:600; color:var(--slate);">{s.total_steps}</div>
            <div style="font-size:10px; color:var(--g500); text-transform:uppercase;">Steps</div>
          </div>
        </div>
      </div>
      {confidence_bar}
    </div>"""


def _render_blockers(vm: ReportViewModel) -> str:
    if not vm.blockers:
        return """
    <div style="padding:20px 0;">
      <div style="font-size:18px; color:#166534; font-weight:500;">No blockers found.</div>
      <div style="font-size:14px; color:var(--g500); margin-top:4px;">All compliance checks passed.</div>
    </div>"""

    cards = ""
    for i, blocker in enumerate(vm.blockers, 1):
        condition_rows = ""
        for cm in blocker.condition_matches:
            match_icon = "✓" if cm.matched else "✗"
            match_color = "#166534" if cm.matched else "#9B2C2C"
            condition_rows += f"""
            <tr>
              <td style="font-family:var(--mono); font-size:12px; color:{match_color};">{match_icon}</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--g700);">{_esc(str(cm.field))}</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--g500);">{_esc(str(cm.display_operator()))}</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--slate);">{_esc(str(cm.expected))}</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--g500);">→</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--slate); font-weight:600;">{_esc(str(cm.actual))}</td>
            </tr>"""

        refs = " · ".join(blocker.compliance_refs) if blocker.compliance_refs else "none"
        cards += f"""
      <div style="background:var(--paper); border:1.5px solid #FCA5A5; border-radius:10px; padding:20px 24px; margin-bottom:12px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
          <span style="font-family:var(--mono); font-size:10px; background:#FED7D7; color:#9B2C2C; padding:3px 8px; border-radius:4px; text-transform:uppercase;">{_esc(blocker.rule_type)}</span>
          <span style="font-family:var(--mono); font-size:11px; color:var(--g500);">#{i} · {_esc(blocker.rule_id)} · priority {blocker.priority}</span>
        </div>
        <div style="font-size:15px; font-weight:600; color:var(--slate); margin-bottom:6px;">{_esc(blocker.action_title)}</div>
        <div style="font-size:14px; color:var(--g700); margin-bottom:12px;">{_esc(blocker.blocker_text)}</div>
        <details>
          <summary style="cursor:pointer; font-family:var(--mono); font-size:11px; color:var(--clay);">Why did this rule fire?</summary>
          <table style="width:100%; margin-top:8px; font-size:12px; border-collapse:collapse;">
            <thead><tr>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Match</th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Field</th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Op</th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Expected</th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);"></th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Your Value</th>
            </tr></thead>
            <tbody>{condition_rows}</tbody>
          </table>
          <div style="font-size:11px; color:var(--g500); margin-top:8px;">
            Compliance refs: {_esc(refs)} · Source: {_esc(blocker.source_doc_ref)}
          </div>
        </details>
      </div>"""
    return cards


def _render_path(steps: tuple[PathStepView, ...]) -> str:
    if not steps:
        return '<div style="color:var(--g500); font-size:14px;">No path steps available.</div>'

    items = ""
    for i, step in enumerate(steps):
        connector = ""
        if i < len(steps) - 1:
            connector = f"""
            <div style="margin-left:12px; border-left:2px solid {step.status_color()}; height:20px;"></div>"""

        items += f"""
        <div style="display:flex; gap:12px; align-items:flex-start;">
          <div style="min-width:24px; text-align:center; font-size:14px; line-height:1.4; color:{step.status_color()};">
            {_esc(step.status_label())}
          </div>
          <div style="flex:1;">
            <div style="font-size:14px; font-weight:600; color:var(--slate);">{_esc(step.label)}</div>
            <div style="font-size:12px; color:var(--g500);">{_esc(step.dimension)} · maturity {step.maturity_level}</div>
            <div style="font-size:13px; color:var(--g700); margin-top:2px;">{_esc(step.description)}</div>
          </div>
        </div>
        {connector}"""
    return items


def _render_evidence(vm: ReportViewModel) -> str:
    if not vm.triggered_rules:
        return '<div style="color:var(--g500); font-size:14px;">No rules triggered.</div>'

    cards = ""
    for rule in vm.triggered_rules:
        condition_rows = ""
        for cm in rule.condition_matches:
            match_icon = "✓" if cm.matched else "✗"
            match_color = "#166534" if cm.matched else "#9B2C2C"
            condition_rows += f"""
            <tr>
              <td style="font-family:var(--mono); font-size:12px; color:{match_color};">{match_icon}</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--g700);">{_esc(str(cm.field))}</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--g500);">{_esc(str(cm.display_operator()))}</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--slate);">{_esc(str(cm.expected))}</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--g500);">→</td>
              <td style="font-family:var(--mono); font-size:12px; color:var(--slate); font-weight:600;">{_esc(str(cm.actual))}</td>
            </tr>"""

        blocker_badge = ' <span style="font-family:var(--mono); font-size:9px; background:#FED7D7; color:#9B2C2C; padding:2px 6px; border-radius:3px;">BLOCKER</span>' if rule.is_blocker else ""
        warning_note = f'<div style="font-size:11px; color:#92400E; margin-top:4px;">⚠ {_esc(rule.warning)}</div>' if rule.warning else ""
        refs = " · ".join(rule.compliance_refs) if rule.compliance_refs else "none"

        cards += f"""
      <div style="background:var(--paper); border:1px solid var(--g200); border-radius:10px; padding:18px 22px; margin-bottom:10px;">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px; flex-wrap:wrap;">
          <span style="font-family:var(--mono); font-size:10px; background:var(--g100); color:{rule.rule_type_color()}; padding:3px 8px; border-radius:4px; text-transform:uppercase;">{_esc(rule.rule_type_label())}</span>
          <span style="font-family:var(--mono); font-size:11px; color:var(--g500);">{_esc(rule.rule_id)} · priority {rule.priority}</span>
          {blocker_badge}
        </div>
        <div style="font-size:15px; font-weight:600; color:var(--slate);">{_esc(rule.action_title)}</div>
        <div style="font-size:13px; color:var(--g700); margin-top:2px;">{_esc(rule.action_text)}</div>
        {warning_note}
        <details style="margin-top:10px;">
          <summary style="cursor:pointer; font-family:var(--mono); font-size:11px; color:var(--clay);">Show condition match</summary>
          <table style="width:100%; margin-top:8px; font-size:12px; border-collapse:collapse;">
            <thead><tr>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Match</th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Field</th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Op</th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Expected</th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);"></th>
              <th style="text-align:left; padding:4px 8px; color:var(--g500); border-bottom:1px solid var(--g200);">Your Value</th>
            </tr></thead>
            <tbody>{condition_rows}</tbody>
          </table>
          <div style="font-size:11px; color:var(--g500); margin-top:8px;">
            Refs: {_esc(refs)} · Source: {_esc(rule.source_doc_ref)}
          </div>
        </details>
      </div>"""
    return cards


def _render_trace_json(vm: ReportViewModel) -> str:
    """Embed trace data as commented JSON for machine-readability."""
    import json
    data = {
        "answer_ids": list(vm.trace_answer_ids),
        "roadmap_node_ids": list(vm.trace_node_ids),
        "triggered_rule_ids": list(vm.trace_rule_ids),
        "regulatory_refs": list(vm.trace_refs),
        "upstream_snapshot": vm.upstream_snapshot,
        "audit_chain_valid": vm.summary.audit_chain_valid,
        "confidence": vm.summary.confidence,
    }
    return json.dumps(data, indent=2)


def _json_safe(vm: ReportViewModel) -> str:
    import json
    data = {
        "answer_ids": list(vm.trace_answer_ids),
        "roadmap_node_ids": list(vm.trace_node_ids),
        "triggered_rule_ids": list(vm.trace_rule_ids),
    }
    return json.dumps(data, indent=2)


def _esc(s: str) -> str:
    return _html.escape(s)


# ═══════════════════════════════════════════════════════════════════════
# HTML Template (html-spec ivory style, 4-section vertical scroll)
# ═══════════════════════════════════════════════════════════════════════

_HTML_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --ivory: #FAF9F5;
    --paper: #FFFFFF;
    --slate: #141413;
    --clay:  #D97757;
    --g100:  #F0EEE6;
    --g200:  #E6E3DA;
    --g300:  #D1CFC5;
    --g500:  #87867F;
    --g700:  #3D3D3A;
    --serif: ui-serif, Georgia, "Times New Roman", Times, serif;
    --sans:  system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --mono:  ui-monospace, "SF Mono", Menlo, Monaco, Consolas, monospace;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:var(--sans); background:var(--ivory); color:var(--slate); line-height:1.6; }}
  main {{ max-width:780px; margin:0 auto; padding:48px 24px 80px; }}

  h1 {{ font-family:var(--serif); font-weight:500; font-size:34px; letter-spacing:-0.014em; margin-bottom:6px; }}
  h2 {{ font-family:var(--serif); font-weight:500; font-size:22px; letter-spacing:-0.01em; margin:40px 0 16px; border-bottom:1px solid var(--g200); padding-bottom:8px; }}
  .subtitle {{ color:var(--g500); font-size:13px; margin-bottom:32px; }}
  code {{ font-family:var(--mono); font-size:0.88em; }}
  hr {{ border:none; border-top:1px solid var(--g200); margin:40px 0; }}

  details summary {{ user-select:none; }}
  details summary:hover {{ color:var(--slate) !important; }}

  /* Trace section */
  .trace-block {{ background:var(--g100); border-radius:8px; padding:16px 20px; margin-top:24px; }}
  .trace-block pre {{ font-family:var(--mono); font-size:12px; color:var(--g700); overflow-x:auto; margin:0; }}

  @media print {{
    body {{ background:white; }}
    main {{ max-width:100%; }}
    details {{ display:block; }}
  }}
</style>
</head>
<body>
<main>
  <h1>SCAILED Pathfinder</h1>
  <div class="subtitle">Compliance Assessment Report · Self-contained · No JavaScript</div>

  <!-- ====== 1. Readiness Score ====== -->
{readiness_section}

  <!-- ====== 2. Blockers ====== -->
  <h2>Blockers</h2>
{blockers_section}

  <!-- ====== 3. Compliance Path ====== -->
  <h2>Compliance Path</h2>
{path_section}

  <!-- ====== 3b. Path Graph ====== -->
  <h2>Path Graph</h2>
  <div style="overflow-x:auto; padding:8px 0;">
{path_graph_section}
  </div>

  <!-- ====== 4. Evidence — Triggered Rules ====== -->
  <h2>Evidence: Triggered Rules</h2>
{evidence_section}

  <hr>

  <!-- Trace -->
  <details>
    <summary style="cursor:pointer; font-family:var(--mono); font-size:11px; color:var(--g500);">Audit Trace (machine-readable)</summary>
    <div class="trace-block"><pre>{trace_json}</pre></div>
  </details>

  <div style="margin-top:40px; font-size:11px; color:var(--g500); text-align:center;">
{footer}
  </div>
</main>
</body>
</html>"""

"""Inline SVG path graph renderer for Pathfinder report.

Layout: maturity_level = x-axis, simple vertical stacking per column.
Renders the full compliance chain with blocked node indication and legend.
"""

from __future__ import annotations

from pathfinder.visualization.schemas import PathStepView


def render_path_svg(steps: tuple[PathStepView, ...]) -> str:
    """Generate inline SVG showing the full compliance path.

    All nodes in the chain are shown.  Blocked nodes get a prominent
    red indicator.  A compact legend explains the colour coding.
    """
    if not steps:
        return ""

    # Group nodes by maturity level
    levels: dict[int, list[PathStepView]] = {}
    for step in steps:
        levels.setdefault(step.maturity_level, []).append(step)

    # Layout parameters — adaptive: fewer levels = wider columns
    num_levels = len(levels)
    if num_levels <= 5:
        col_w = 200
    elif num_levels <= 8:
        col_w = 160
    else:
        col_w = 140
    node_h = 78   # node height
    v_gap = 24    # vertical gap between nodes
    margin = 32

    max_level = max(levels.keys()) if levels else 1
    max_nodes_in_col = max(len(v) for v in levels.values()) if levels else 1
    legend_h = 44  # extra height for legend strip
    width = (max_level + 1) * col_w + margin * 2
    height = max_nodes_in_col * (node_h + v_gap) + margin * 2 + legend_h

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" style="width:{width}px; max-width:none; font-family:system-ui,sans-serif;">',
        f'<rect width="100%" height="100%" fill="#FAF9F5"/>',
    ]

    # ── Arrow markers ──────────────────────────────────────────
    for status in ["completed", "blocked", "current", "unreached"]:
        color = _status_stroke(status)
        svg_parts.append(
            f'<defs><marker id="arrow-{status}" markerWidth="8" markerHeight="6" '
            f'refX="7" refY="3" orient="auto">'
            f'<polygon points="0 0, 8 3, 0 6" fill="{color}"/>'
            f'</marker></defs>'
        )

    # ── Edges between consecutive levels ───────────────────────
    sorted_levels = sorted(levels.keys())
    for i in range(len(sorted_levels) - 1):
        from_lv = sorted_levels[i]
        to_lv = sorted_levels[i + 1]
        from_nodes = levels[from_lv]
        to_nodes = levels[to_lv]

        for fi, fn in enumerate(from_nodes):
            fx = from_lv * col_w + margin + col_w - 10
            fy = margin + fi * (node_h + v_gap) + node_h // 2 + legend_h
            for ti, tn in enumerate(to_nodes):
                tx = to_lv * col_w + margin + 10
                ty = margin + ti * (node_h + v_gap) + node_h // 2 + legend_h
                color = _status_stroke(fn.status)
                svg_parts.append(
                    f'<line x1="{fx}" y1="{fy}" x2="{tx}" y2="{ty}" '
                    f'stroke="{color}" stroke-width="1.5" stroke-dasharray="{_edge_dash(fn.status)}" '
                    f'marker-end="url(#arrow-{fn.status})"/>'
                )

    # ── Nodes ──────────────────────────────────────────────────
    for lv in sorted_levels:
        for ni, node in enumerate(levels[lv]):
            x = lv * col_w + margin
            y = margin + ni * (node_h + v_gap) + legend_h
            fill, stroke, text_color = _node_style(node.status)
            is_blocked = node.status == "blocked"

            # Shadow glow for blocked nodes
            if is_blocked:
                svg_parts.append(
                    f'<rect x="{x - 2}" y="{y - 2}" width="{col_w - 4}" height="{node_h + 4}" '
                    f'rx="10" fill="none" stroke="#FCA5A5" stroke-width="3" opacity="0.6"/>'
                )

            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{col_w - 8}" height="{node_h}" '
                f'rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            )
            # Title — wrap into two lines when >18 chars
            line1, line2 = _wrap_label(node.label, 18)
            svg_parts.append(
                f'<text x="{x + 14}" y="{y + 22}" fill="{text_color}" '
                f'font-size="13" font-weight="600">{_esc(line1)}</text>'
            )
            if line2:
                svg_parts.append(
                    f'<text x="{x + 14}" y="{y + 40}" fill="{text_color}" '
                    f'font-size="13" font-weight="600">{_esc(line2)}</text>'
                )
            # Dimension line
            dim_y = y + 58 if line2 else y + 40
            svg_parts.append(
                f'<text x="{x + 14}" y="{dim_y}" fill="#87867F" '
                f'font-size="11">{_esc(node.dimension[:18])} · L{node.maturity_level}</text>'
            )

            # Status badge (right side of node)
            badge_color = _status_stroke(node.status)
            if is_blocked:
                svg_parts.append(
                    f'<text x="{x + col_w - 24}" y="{y + 22}" font-size="16" '
                    f'text-anchor="middle">⛔</text>'
                )
            else:
                svg_parts.append(
                    f'<circle cx="{x + col_w - 20}" cy="{y + 18}" r="6" fill="{badge_color}"/>'
                )

    # ── Legend ─────────────────────────────────────────────────
    _draw_legend(svg_parts, margin, max_level, col_w)

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _draw_legend(parts: list[str], margin: int, max_level: int, col_w: int) -> None:
    """Append a compact legend strip at the top."""
    items = [
        ("completed", "Done"),
        ("blocked", "Blocked"),
        ("unreached", "Future"),
    ]
    legend_x = margin
    legend_y = 8
    item_w = 130

    parts.append(
        f'<text x="{margin}" y="{legend_y + 14}" fill="#87867F" '
        f'font-size="11" font-weight="600">Legend:</text>'
    )

    for j, (status, label) in enumerate(items):
        cx = legend_x + 72 + j * item_w
        color = _status_stroke(status)
        parts.append(
            f'<circle cx="{cx}" cy="{legend_y + 11}" r="5" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{cx + 12}" y="{legend_y + 15}" fill="#3D3D3A" '
            f'font-size="11">{label}</text>'
        )

    # Blocked icon explanation
    parts.append(
        f'<text x="{margin + 72 + len(items) * item_w}" y="{legend_y + 15}" '
        f'fill="#3D3D3A" font-size="11">⛔ = Blocker active</text>'
    )


def _status_stroke(status: str) -> str:
    return {
        "completed": "#166534",
        "blocked": "#9B2C2C",
        "current": "#1E40AF",
        "unreached": "#87867F",
    }.get(status, "#87867F")


def _edge_dash(status: str) -> str:
    return "none" if status == "completed" else "4,4"


def _node_style(status: str) -> tuple[str, str, str]:
    """Return (fill, stroke, text_color)."""
    styles = {
        "completed": ("#DCFCE7", "#166534", "#141413"),
        "blocked": ("#FED7D7", "#9B2C2C", "#141413"),
        "current": ("#DBEAFE", "#1E40AF", "#141413"),
        "unreached": ("#FFFFFF", "#D1CFC5", "#87867F"),
    }
    return styles.get(status, styles["unreached"])


def _esc(s: str) -> str:
    import html
    return html.escape(s)


def _wrap_label(label: str, max_chars: int = 18) -> tuple[str, str]:
    """Split a label into two lines at word boundary when too long."""
    if len(label) <= max_chars:
        return (label, "")
    # Try to break at a space near the middle
    mid = len(label) // 2
    space_before = label.rfind(" ", 0, mid)
    space_after = label.find(" ", mid)
    if space_before > 0 and space_before <= max_chars:
        return (label[:space_before].strip(), label[space_before:].strip())
    if space_after > 0 and space_after <= max_chars:
        return (label[:space_after].strip(), label[space_after:].strip())
    # No good break point — just split at max_chars
    return (label[:max_chars], label[max_chars:max_chars * 2])

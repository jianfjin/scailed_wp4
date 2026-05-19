"""Inline SVG path graph renderer for Pathfinder report.

Linus: "The 1000-node concern is FUD — you're rendering subgraphs."
Layout: maturity_level = x-axis, simple vertical stacking per column.
"""

from __future__ import annotations

from pathfinder.visualization.schemas import PathStepView


def render_path_svg(steps: tuple[PathStepView, ...]) -> str:
    """Generate inline SVG showing the compliance path as a layered DAG.

    Only renders the path-relevant subgraph (the nodes in 'steps'),
    not the full 1000-node roadmap.
    """
    if not steps:
        return ""

    # Layout parameters — sized to match surrounding HTML text (~14px base)
    col_w = 200   # column width per maturity level
    node_h = 72   # node height
    v_gap = 20    # vertical gap between nodes
    margin = 32

    # Group nodes by maturity level
    levels: dict[int, list[PathStepView]] = {}
    for step in steps:
        levels.setdefault(step.maturity_level, []).append(step)

    max_level = max(levels.keys()) if levels else 1
    max_nodes_in_col = max(len(v) for v in levels.values()) if levels else 1
    width = (max_level + 1) * col_w + margin * 2
    height = max_nodes_in_col * (node_h + v_gap) + margin * 2

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" style="width:100%; font-family:system-ui,sans-serif;">',
        f'<rect width="100%" height="100%" fill="#FAF9F5"/>',
    ]

    # Draw edges between consecutive levels
    sorted_levels = sorted(levels.keys())
    for i in range(len(sorted_levels) - 1):
        from_lv = sorted_levels[i]
        to_lv = sorted_levels[i + 1]
        from_nodes = levels[from_lv]
        to_nodes = levels[to_lv]

        for fi, fn in enumerate(from_nodes):
            fx = from_lv * col_w + margin + col_w - 10
            fy = margin + fi * (node_h + v_gap) + node_h // 2
            for ti, tn in enumerate(to_nodes):
                tx = to_lv * col_w + margin + 10
                ty = margin + ti * (node_h + v_gap) + node_h // 2
                color = _status_stroke(fn.status)
                svg_parts.append(
                    f'<line x1="{fx}" y1="{fy}" x2="{tx}" y2="{ty}" '
                    f'stroke="{color}" stroke-width="1.5" stroke-dasharray="{_edge_dash(fn.status)}" '
                    f'marker-end="url(#arrow-{fn.status})"/>'
                )

    # Arrow markers
    for status in ["completed", "blocked", "current", "unreached"]:
        color = _status_stroke(status)
        svg_parts.append(
            f'<defs><marker id="arrow-{status}" markerWidth="8" markerHeight="6" '
            f'refX="7" refY="3" orient="auto">'
            f'<polygon points="0 0, 8 3, 0 6" fill="{color}"/>'
            f'</marker></defs>'
        )

    # Draw nodes
    for lv in sorted_levels:
        for ni, node in enumerate(levels[lv]):
            x = lv * col_w + margin
            y = margin + ni * (node_h + v_gap)
            fill, stroke, text_color = _node_style(node.status)

            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{col_w - 8}" height="{node_h}" '
                f'rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            )
            svg_parts.append(
                f'<text x="{x + 14}" y="{y + 26}" fill="{text_color}" '
                f'font-size="14" font-weight="600">{_esc(node.label[:24])}</text>'
            )
            svg_parts.append(
                f'<text x="{x + 14}" y="{y + 48}" fill="#87867F" '
                f'font-size="11">{_esc(node.dimension)} · L{node.maturity_level}</text>'
            )
            # Status badge
            badge_color = _status_stroke(node.status)
            svg_parts.append(
                f'<circle cx="{x + col_w - 24}" cy="{y + 18}" r="6" fill="{badge_color}"/>'
            )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


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

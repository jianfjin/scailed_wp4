"""Recommendation assembly."""

from __future__ import annotations

from pathfinder.core.models import PathResult


def build_recommendation(path: PathResult) -> dict[str, object]:
    status = "blocked" if path.blockers else "ready"
    next_steps = [
        {
            "node_id": step.node_id,
            "label": step.label,
            "description": step.description,
            "dimension": step.dimension,
            "maturity_level": step.maturity_level,
            "source": step.source_doc_ref,
        }
        for step in path.steps
    ]
    return {
        "status": status,
        "current_node": path.current_node,
        "target_node": path.target_node,
        "next_steps": next_steps,
        "blockers": list(path.blockers),
        "warnings": list(path.warnings),
        "confidence": path.confidence,
        "triggered_rules": [rule.to_dict() for rule in path.triggered_rules],
        "trace": path.trace.to_dict(),
        "path_backend": path.path_backend,
    }

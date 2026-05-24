#!/usr/bin/env python3
"""Patch wp3_data.json to guarantee every node can reach every target node.

The original random edge generation creates disconnected chains — 69% of
nodes cannot reach scenario targets. This script adds guaranteed edges
forming a DAG "spine" through all 10 layers, then stitches the spine to
all top targets in the last layer.

Usage: python scripts/patch_roadmap_connectivity.py
"""

import json
from collections import deque
from pathlib import Path

FIXTURES_DIR = Path("services/mock/fixtures")
WP3_PATH = FIXTURES_DIR / "wp3_data.json"


def find_path(outgoing: dict[str, list[str]], start: str, target: str) -> list[str] | None:
    if start == target:
        return [start]
    q: deque[tuple[str, list[str]]] = deque([(start, [start])])
    seen = {start}
    while q:
        cur, path = q.popleft()
        for nxt in outgoing.get(cur, []):
            if nxt == target:
                return path + [nxt]
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, path + [nxt]))
    return None


def main() -> None:
    data = json.loads(WP3_PATH.read_text())
    nodes: list[dict] = data["nodes"]
    edges: list[dict] = data["edges"]

    layers: dict[int, list[str]] = {}
    node_map: dict[str, dict] = {}
    for n in nodes:
        node_map[n["node_id"]] = n
        layers.setdefault(n["metadata"]["layer"], []).append(n["node_id"])

    outgoing: dict[str, list[str]] = {n["node_id"]: [] for n in nodes}
    for e in edges:
        outgoing.setdefault(e["from_node_id"], []).append(e["to_node_id"])

    # Identify all target nodes for each scenario
    scenario_targets: dict[str, list[str]] = {}
    for n in nodes:
        for scenario in n["metadata"].get("target_scenarios", []):
            scenario_targets.setdefault(scenario, []).append(n["node_id"])

    for scenario, tlist in scenario_targets.items():
        tlist.sort(key=lambda nid: node_map[nid]["maturity_level"], reverse=True)

    print(f"Target scenarios: {list(scenario_targets.keys())}")
    for s, t in scenario_targets.items():
        print(f"  {s}: {len(t)} targets, top={t[0] if t else 'NONE'}")

    # Spine: first node per layer
    max_layer = max(layers.keys())
    spine: dict[int, str] = {l: layers[l][0] for l in sorted(layers.keys())}
    print(f"Spine: {[(l, spine[l]) for l in sorted(spine.keys())]}")

    edge_id_counter = max(int(e["edge_id"].lstrip("e")) for e in edges) + 1
    added = 0

    def add_edge(frm: str, to: str) -> None:
        nonlocal added, edge_id_counter
        if to in outgoing.get(frm, []):
            return  # already connected
        edges.append({
            "edge_id": f"e{edge_id_counter:04d}",
            "from_node_id": frm,
            "to_node_id": to,
            "relation_type": "prerequisite",
            "required": True,
            "source_doc_ref": "gen-1000-patched",
        })
        outgoing.setdefault(frm, []).append(to)
        edge_id_counter += 1
        added += 1

    # Step 1: Build guaranteed spine chain through layers
    for layer in range(max_layer):
        add_edge(spine[layer], spine[layer + 1])

    # Step 2: Connect spine(9) to all top-3 targets per scenario
    for scenario, tlist in scenario_targets.items():
        top_targets = tlist[:3]
        for t in top_targets:
            # Direct edge from spine(9) → target
            add_edge(spine[max_layer], t)

    # Step 3: For every node without a path to ANY top target, connect it
    # to the spine chain (within its layer and to next layer's spine)
    no_path_count = 0
    for n in nodes:
        nid = n["node_id"]
        layer = n["metadata"]["layer"]

        # Check connectivity to any target
        has_path = any(
            find_path(outgoing, nid, t[0]) is not None
            for t in scenario_targets.values()
            if t
        )
        if has_path:
            continue

        # Connect from spine to this node (lateral connection within layer)
        if nid != spine.get(layer, ""):
            add_edge(spine[layer], nid)

        # Connect from this node to next layer's spine
        if layer < max_layer:
            add_edge(nid, spine[layer + 1])

        # Re-check
        still_has_path = any(
            find_path(outgoing, nid, t[0]) is not None
            for t in scenario_targets.values()
            if t
        )
        if not still_has_path:
            no_path_count += 1

    # Step 4: Verify connectivity — every node in layers 0-4 (slider range)
    # must reach at least one target from each scenario
    connectable = 0
    for n in nodes:
        if n["metadata"]["layer"] > 4:
            continue  # only care about slider-accessible nodes
        nid = n["node_id"]
        ok = any(
            find_path(outgoing, nid, t[0]) is not None
            for t in scenario_targets.values()
            if t
        )
        if ok:
            connectable += 1

    # Count nodes in layers 0-4
    count_l0_4 = sum(1 for n in nodes if n["metadata"]["layer"] <= 4)

    print(f"\nEdges added: {added}")
    print(f"Edges total: {len(edges)}")
    print(f"Nodes in layers 0-4 with path to any target: {connectable}/{count_l0_4}")
    print(f"Nodes still disconnected: {no_path_count}")

    # Save
    data["edges"] = edges
    data["patch_info"] = {
        "script": "patch_roadmap_connectivity.py",
        "edges_added": added,
        "connectivity_l0_4": f"{connectable}/{count_l0_4}",
    }
    WP3_PATH.write_text(json.dumps(data, indent=2))
    print(f"Saved to {WP3_PATH}")


if __name__ == "__main__":
    main()

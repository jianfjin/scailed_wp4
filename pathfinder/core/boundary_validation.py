#!/usr/bin/env python3
"""Validate WP boundary contracts: schema, checksum, and referential rules.

Validates a directory of snapshots, including the exact dependencies named in
their manifests. Checks schema, checksums, references, rule examples and feedback
suppression. Defaults to the golden samples; --snapshot-dir selects a delivery.
Exit code 0 means the supplied checks passed; warnings do not fail validation.
"""

from __future__ import annotations

import hashlib
import argparse
import json
import sys
import unicodedata
import uuid
from pathlib import Path
from datetime import datetime

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    print("jsonschema is required: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[2]
CD = ROOT / "contracts"
SAMPLES = CD / "samples"

CONTRACT_PRODUCER = {
    "pf.taxonomy.v1": "WP2",
    "pf.questionnaire.v1": "WP4",
    "pf.roadmap.v1": "WP3",
    "pf.rulebundle.v1": "WP8",
    "pf.feedback.v1": "WP4",
}

DEPENDENCIES = {
    "pf.taxonomy.v1": (),
    "pf.questionnaire.v1": ("pf.taxonomy.v1",),
    "pf.roadmap.v1": ("pf.taxonomy.v1",),
    "pf.rulebundle.v1": ("pf.taxonomy.v1", "pf.roadmap.v1"),
    "pf.feedback.v1": ("pf.taxonomy.v1", "pf.questionnaire.v1", "pf.roadmap.v1", "pf.rulebundle.v1"),
}


def load(path: Path):
    return json.loads(path.read_text())


def canonical_checksum(payload) -> str:
    """Single canonicalisation for CI and runtime (docs/15 §3): NFC-normalised,
    sorted keys, compact separators, UTF-8. pathfinder must import this exact
    function rather than re-implementing it."""
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(unicodedata.normalize("NFC", data).encode("utf-8")).hexdigest()


def _retarget_refs(node, old_prefix, new_prefix):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str) and v.startswith(old_prefix):
                node[k] = new_prefix + v[len(old_prefix):]
            else:
                _retarget_refs(v, old_prefix, new_prefix)
    elif isinstance(node, list):
        for item in node:
            _retarget_refs(item, old_prefix, new_prefix)


def inline_external_refs(schema_dir: Path):
    """Load envelope.schema.json and inline the per-contract payload schemas,
    retargeting their internal '#/...' refs to the embed location, so validation
    is deterministic and offline (no cross-file resolver). Branches without a
    payload $ref (e.g. producer_wp bindings) pass through untouched."""
    env = load(schema_dir / "envelope.schema.json")
    for i, branch in enumerate(env["allOf"]):
        props = branch.get("then", {}).get("properties", {})
        slot = props.get("payload")
        if not (isinstance(slot, dict) and "$ref" in slot):
            continue
        doc = load(schema_dir / slot["$ref"])
        doc.pop("$id", None)
        doc.pop("$schema", None)
        target = f"#/allOf/{i}/then/properties/payload"
        _retarget_refs(doc, "#", target)
        slot.clear()
        slot.update(doc)
    return env


def active_docs(docs: list) -> list:
    """Drop snapshots that a newer active snapshot of the same contract supersedes."""
    superseded = {d["manifest"].get("supersedes") for d in docs if d["manifest"].get("supersedes")}
    return [d for d in docs if d["manifest"]["snapshot_id"] not in superseded]


def referential_checks(by_contract: dict, errors: list, warnings: list | None = None):
    # Back-compat: accept {contract: doc} (review16 probes) as well as {contract: [docs]}.
    if warnings is None:
        warnings = []
    by_contract = {c: (ds if isinstance(ds, list) else [ds]) for c, ds in by_contract.items()}
    by_contract = {c: [d["payload"] if "payload" in d else d for d in ds] for c, ds in by_contract.items()}
    by_contract = {c: [{"payload": p} for p in ds] for c, ds in by_contract.items()}
    tax_docs = [d["payload"] for d in by_contract.get("pf.taxonomy.v1", [])]
    road_docs = [d["payload"] for d in by_contract.get("pf.roadmap.v1", [])]
    rb_docs = [d["payload"] for d in by_contract.get("pf.rulebundle.v1", [])]
    qs_docs = [d["payload"] for d in by_contract.get("pf.questionnaire.v1", [])]
    fb_docs = [d["payload"] for d in by_contract.get("pf.feedback.v1", [])]

    st_ids = {s["stakeholder_type_id"] for t in tax_docs for s in t.get("stakeholder_types", [])}
    dim_ids = {d["dimension_id"] for t in tax_docs for d in t.get("dimensions", [])}
    sc_applicable = {}
    for t in tax_docs:
        for s in t.get("scenarios", []):
            sc_applicable[s["scenario_id"]] = s.get("applicable_stakeholder_types", ["all"])
    sc_ids = set(sc_applicable)
    node_ids = {n["node_id"] for r in road_docs for n in r.get("nodes", [])}
    ds_ids = {d["dataset_id"] for r in road_docs for d in r.get("datasets", [])}
    reg_ids = {x["ref_id"] for b in rb_docs for x in b.get("references", [])}
    rule_ids = {r["rule_id"] for b in rb_docs for r in b.get("rules", [])}
    q_ids = {q["question_id"] for qs in qs_docs for q in qs.get("questions", [])}

    def guard(known: set, label: str):
        if not known and ((label == "stakeholder types" and (road_docs or rb_docs or qs_docs)) or (label == "roadmap nodes" and rb_docs) or (label == "rules" and fb_docs) or (label == "questions" and fb_docs) or (label == "scenarios" and qs_docs)):
            warnings.append(f"{label} empty — cross-refs against it were skipped")

    # taxonomy internal: scenario applicable lists resolve
    for t in tax_docs:
        for s in t.get("scenarios", []):
            for a in s.get("applicable_stakeholder_types", []):
                if a != "all" and st_ids and a not in st_ids:
                    errors.append(f"scenario {s['scenario_id']}: applicable_stakeholder_type '{a}' not in taxonomy")
        vocabulary = set(t.get("capability_vocabulary", []))
        for stakeholder in t.get("stakeholder_types", []):
            if not set(stakeholder.get("capabilities", [])) <= vocabulary:
                errors.append(f"stakeholder {stakeholder['stakeholder_type_id']}: capabilities not in taxonomy vocabulary")

    # roadmap internal + node stakeholder refs
    guard(st_ids, "stakeholder types")
    for road in road_docs:
        for e in road.get("edges", []):
            for side in ("from_node_id", "to_node_id"):
                if e[side] not in node_ids:
                    errors.append(f"roadmap edge {e['edge_id']}: {side} '{e[side]}' not an existing node")
        for n in road.get("nodes", []):
            if tax_docs and n["dimension"] not in {d["state_key"] for t in tax_docs for d in t["dimensions"]}:
                errors.append(f"roadmap node {n['node_id']}: dimension is not in taxonomy state keys")
            for p in n.get("prerequisites", []):
                if p not in node_ids:
                    errors.append(f"roadmap node {n['node_id']}: prerequisite '{p}' not an existing node")
            for d in n.get("dataset_refs", []):
                if d not in ds_ids:
                    errors.append(f"roadmap node {n['node_id']}: dataset_ref '{d}' not in catalog")
            for st in n.get("stakeholder_types", []):
                if st != "all" and st_ids and st not in st_ids:
                    errors.append(f"roadmap node {n['node_id']}: stakeholder_type '{st}' not in active taxonomy (RFQ 3.2)")

    # acyclicity over required edges AND prerequisites (a prerequisite is a required edge)
    adj: dict[str, list] = {}
    for road in road_docs:
        for n in road.get("nodes", []):
            adj.setdefault(n["node_id"], [])
            for e in road.get("edges", []):
                if e["from_node_id"] == n["node_id"] and e.get("required", True):
                    adj[n["node_id"]].append(e["to_node_id"])
            for p in n.get("prerequisites", []):
                adj.setdefault(p, []).append(n["node_id"])
    state: dict[str, int] = {}

    def dfs(u):
        state[u] = 1
        for v in adj.get(u, []):
            if state.get(v) == 1:
                errors.append(f"roadmap cycle through {u} -> {v}")
                return
            if state.get(v) is None:
                dfs(v)
        state[u] = 2

    for u in list(adj):
        if state.get(u) is None:
            dfs(u)

    # rulebundle: cross refs + paired tests; unresolved compliance_ref = unverified warning
    guard(node_ids, "roadmap nodes")
    guard(rule_ids, "rules")
    for rb in rb_docs:
        tested = set()
        for t in rb.get("tests", []):
            tested.add(t["rule_id"])
            if t["rule_id"] not in rule_ids:
                errors.append(f"rule test {t['test_id']}: rule_id '{t['rule_id']}' not in bundle")
        for r in rb.get("rules", []):
            if r["rule_id"] not in tested:
                errors.append(f"rule {r['rule_id']}: no paired rule test")
            for a in r.get("applies_to", []):
                if a != "all" and st_ids and a not in st_ids:
                    errors.append(f"rule {r['rule_id']}: applies_to '{a}' not in active taxonomy")
            nid = r.get("action", {}).get("node_id")
            if nid and node_ids and nid not in node_ids:
                errors.append(f"rule {r['rule_id']}: action.node_id '{nid}' not in active roadmap")
            for c in r.get("compliance_refs", []):
                if c not in reg_ids:
                    warnings.append(f"rule {r['rule_id']}: compliance_ref '{c}' unresolved — consumer must mark it unverified")

    # questionnaire refs + supported stakeholder/scenario combinations (RFQ 3.2)
    guard(sc_ids, "scenarios")
    for qs in qs_docs:
        mapped_dimensions = [q["maturity_dimension"] for q in qs.get("questions", []) if q.get("maturity_dimension")]
        if len(mapped_dimensions) != len(set(mapped_dimensions)):
            errors.append("questionnaire: multiple questions map to the same maturity dimension")
        if st_ids and qs["stakeholder_type"] not in st_ids:
            errors.append(f"questionnaire: stakeholder_type '{qs['stakeholder_type']}' not in active taxonomy")
        for s in qs.get("target_scenarios", []):
            if sc_ids and s not in sc_ids:
                errors.append(f"questionnaire: scenario '{s}' not in active taxonomy")
                continue
            applicable = sc_applicable.get(s, ["all"])
            if "all" not in applicable and st_ids and qs["stakeholder_type"] not in applicable:
                errors.append(
                    f"questionnaire: unsupported combination stakeholder '{qs['stakeholder_type']}' x scenario '{s}' (RFQ 3.2 supported combinations)"
                )
        for q in qs.get("questions", []):
            d = q.get("maturity_dimension")
            if d and dim_ids and d not in dim_ids:
                errors.append(f"questionnaire {q['question_id']}: maturity_dimension '{d}' not in taxonomy dimensions")
            if d and q["question_type"] != "numeric":
                errors.append(f"questionnaire {q['question_id']}: maturity_dimension requires a numeric question")
            if q["question_type"] == "numeric" and q.get("maturity_dimension") and (q.get("min_value") != 1 or q.get("max_value") != 5):
                errors.append(f"questionnaire {q['question_id']}: numeric maturity question must use 1..5 (RFQ 3.2)")
            if q.get("visible_if") is not None:
                errors.append(f"questionnaire {q['question_id']}: visible_if is not supported by the runtime")
            if q.get("state_field") and q["question_type"] != "multi_choice":
                errors.append(f"questionnaire {q['question_id']}: state_field requires multi_choice")
            if q.get("state_field") in {"capabilities", "missing_capabilities"} and tax_docs:
                vocabulary = set(tax_docs[0].get("capability_vocabulary", []))
                if not set(q.get("options", [])) <= vocabulary:
                    errors.append(f"questionnaire {q['question_id']}: capability options not in taxonomy vocabulary")

    for tax in tax_docs:
        keys = [d["state_key"] for d in tax["dimensions"]]
        if len(keys) != len(set(keys)):
            errors.append("taxonomy: duplicate dimension state_key")

    # feedback refs
    guard(q_ids, "questions")
    for fb in fb_docs:
        for s in fb.get("roadmap", {}).get("node_stats", []):
            if node_ids and s["node_id"] not in node_ids:
                errors.append(f"feedback roadmap: node '{s['node_id']}' not in active roadmap")
        for s in fb.get("rules", {}).get("rule_stats", []):
            if rule_ids and s["rule_id"] not in rule_ids:
                errors.append(f"feedback rules: rule '{s['rule_id']}' not in active bundle")
        for s in fb.get("questionnaire", {}).get("question_stats", []):
            if q_ids and s["question_id"] not in q_ids:
                errors.append(f"feedback questionnaire: question '{s['question_id']}' not in active questionnaire")


def manifest_hard_checks(docs, errors):
    """Machine-checkable manifest rules the schema cannot express: UUID format,
    producer_wp/contract binding, supersedes self-reference."""
    for fname, doc in docs:
        m = doc.get("manifest", {})
        for field in ("snapshot_id", *(("supersedes",) if m.get("supersedes") else ())):
            try:
                uuid.UUID(m[field])
            except (ValueError, TypeError, KeyError):
                errors.append(f"{fname}: manifest.{field} '{m.get(field)}' is not a UUID")
        want = CONTRACT_PRODUCER.get(doc.get("contract"))
        if want and m.get("producer_wp") != want:
            errors.append(f"{fname}: contract {doc.get('contract')} must have producer_wp {want}, got {m.get('producer_wp')}")
        if m.get("supersedes") == m.get("snapshot_id"):
            errors.append(f"{fname}: supersedes references itself")
        if doc.get("contract", "").endswith(".v1") and not m.get("contract_version", "").startswith("1."):
            errors.append(f"{fname}: contract_version major must match contract")
        try:
            timestamp = datetime.fromisoformat(m.get("generated_at", "").replace("Z", "+00:00"))
            if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
                raise ValueError("not UTC")
        except (TypeError, ValueError):
            errors.append(f"{fname}: generated_at must be a UTC date-time")


def behavioral_checks(doc, errors):
    """Validate IDs, executable conditions and disclosure-sensitive counts."""
    from pathfinder.core.compliance import ComplianceEvaluator
    from pathfinder.core.models import StakeholderState

    payload = doc["payload"]
    contract = doc["contract"]
    id_fields = {
        "pf.taxonomy.v1": (("dimensions", "dimension_id"), ("stakeholder_types", "stakeholder_type_id"), ("scenarios", "scenario_id")),
        "pf.questionnaire.v1": (("questions", "question_id"),),
        "pf.roadmap.v1": (("nodes", "node_id"), ("edges", "edge_id"), ("datasets", "dataset_id")),
        "pf.rulebundle.v1": (("rules", "rule_id"), ("references", "ref_id"), ("tests", "test_id")),
    }
    for collection, field in id_fields.get(contract, ()):
        seen = set()
        for item in payload.get(collection, []):
            value = item[field]
            if value in seen:
                errors.append(f"{contract} {collection}: duplicate {field} '{value}'")
            seen.add(value)

    if contract == "pf.feedback.v1":
        threshold = payload["min_cohort_size"]
        for section, collection in (("roadmap", "node_stats"), ("rules", "rule_stats"), ("questionnaire", "question_stats")):
            for row in payload.get(section, {}).get(collection, []):
                if row["cohort_size"] < threshold:
                    errors.append(f"feedback {section}: cohort_size below {threshold}")
                for key, value in row.items():
                    if type(value) is int and 0 < value < threshold:
                        errors.append(f"feedback {section}.{key}: suppress counts below {threshold}")
                    if key.endswith("rate"):
                        errors.append(f"feedback {section}.{key}: rates require a separate disclosure review")

    if contract != "pf.rulebundle.v1":
        return

    def check_condition(condition, context):
        for branch in ("and", "or"):
            if branch in condition:
                for child in condition[branch]:
                    check_condition(child, context)
                return
        if "not" in condition:
            check_condition(condition["not"], context)
            return
        field, op = condition["field"], condition["op"]
        numeric = field in {"maturity.governance", "maturity.data", "maturity.compliance", "maturity.infrastructure", "maturity.capability"}
        collection = field in {"capabilities", "missing_capabilities", "regulatory_flags"}
        scalar = field in {"stakeholder_type", "target_scenario"}
        if not (numeric or collection or scalar):
            errors.append(f"{context}: unknown state field '{field}'")
        elif numeric and (op not in {"eq", "ne", "gt", "gte", "lt", "lte", "exists"} or (op != "exists" and type(condition.get("value")) is not int)):
            errors.append(f"{context}: invalid numeric condition on {field}")
        elif collection and (op not in {"contains", "exists"} or (op == "contains" and not isinstance(condition.get("value"), str))):
            errors.append(f"{context}: invalid collection condition on {field}")
        elif scalar and (op not in {"eq", "ne", "in", "not_in", "exists"} or (op in {"eq", "ne"} and not isinstance(condition.get("value"), str)) or (op in {"in", "not_in"} and (not isinstance(condition.get("value"), list) or not all(isinstance(v, str) for v in condition["value"])))):
            errors.append(f"{context}: invalid scalar condition on {field}")

    rules = {rule["rule_id"]: rule for rule in payload["rules"]}
    before = len(errors)
    for rule in payload["rules"]:
        check_condition(rule["condition"], f"rule {rule['rule_id']}")
        if rule.get("effective_from") and rule.get("effective_until") and rule["effective_from"] > rule["effective_until"]:
            errors.append(f"rule {rule['rule_id']}: effective_from is after effective_until")
    if len(errors) != before:
        return
    evaluator = ComplianceEvaluator()
    for test in payload["tests"]:
        rule = rules.get(test["rule_id"])
        if rule is None:
            continue
        given = test["given"]
        allowed = {"stakeholder_type", "target_scenario", "capabilities", "missing_capabilities", "regulatory_flags", "maturity.governance", "maturity.data", "maturity.compliance", "maturity.infrastructure", "maturity.capability"}
        if set(given) - allowed:
            errors.append(f"rule test {test['test_id']}: unknown given fields {sorted(set(given) - allowed)}")
            continue
        if any(not isinstance(given.get(k, []), list) or not all(isinstance(v, str) for v in given.get(k, [])) for k in ("capabilities", "missing_capabilities", "regulatory_flags")) or any(type(v) is not int or not 1 <= v <= 5 for k, v in given.items() if k.startswith("maturity.")):
            errors.append(f"rule test {test['test_id']}: invalid given field type or maturity")
            continue
        state = StakeholderState(given.get("stakeholder_type", rule["applies_to"][0]), given.get("target_scenario", ""), {},
            {k.removeprefix("maturity."): v for k, v in given.items() if k.startswith("maturity.")},
            tuple(given.get("capabilities", [])), tuple(given.get("missing_capabilities", [])), tuple(given.get("regulatory_flags", [])), 1.0, (), "test")
        try:
            triggered = ("all" in rule["applies_to"] or state.stakeholder_type in rule["applies_to"]) and evaluator.evaluate(rule["condition"], state)
            actual = "blocked" if triggered and rule["action"].get("block", False) else "triggered" if triggered else "not-triggered"
            if actual != test["expect"]["outcome"] or ("action_contains" in test["expect"] and test["expect"]["action_contains"] not in rule["action"]["text"]):
                errors.append(f"rule test {test['test_id']}: expected {test['expect']}, got {actual}")
        except (TypeError, ValueError) as exc:
            errors.append(f"rule test {test['test_id']}: invalid state or comparison: {exc}")


def validate_documents(snapshots):
    """Validate supplied snapshots without activating them; return errors and warnings."""
    errors: list[str] = []
    warnings: list[str] = []
    docs: list = []
    by_contract: dict[str, list] = {}
    ev = Draft202012Validator(inline_external_refs(CD), format_checker=FormatChecker())
    for index, doc in enumerate(snapshots):
        name = f"snapshot[{index}]"
        errs = sorted(ev.iter_errors(doc), key=lambda e: tuple(str(part) for part in e.absolute_path))
        for e in errs[:5]:
            errors.append(f"{name}: schema at {'/'.join(map(str, e.absolute_path)) or '$'}: {e.message[:160]}")
        if errs:
            continue
        got = canonical_checksum(doc["payload"])
        want = doc["manifest"]["items_checksum"]
        if got != want:
            errors.append(f"{name}: items_checksum mismatch (computed {got[:20]}..., stored {want[:20]}...)")
        docs.append((name, doc))
        by_contract.setdefault(doc["contract"], []).append(doc)
    if not docs:
        errors.append("no valid snapshots supplied")
    active = {c: active_docs(ds) for c, ds in by_contract.items()}
    manifest_hard_checks(docs, errors)
    by_id = {d['manifest']['snapshot_id']: d for _, d in docs}
    if len(by_id) != len(docs):
        errors.append("duplicate snapshot_id")
    for fname, doc in docs:
        contract = doc["contract"]
        dependencies = doc["manifest"].get("dependencies", {})
        selected = {contract: doc}
        if set(dependencies) != set(DEPENDENCIES[contract]):
            errors.append(f"{fname}: dependencies must contain exactly {list(DEPENDENCIES[contract])}")
        for required in DEPENDENCIES[contract]:
            dep = by_id.get(dependencies.get(required))
            if dep is None or dep["contract"] != required:
                errors.append(f"{fname}: missing exact dependency {required}: {dependencies.get(required)}")
            else:
                selected[required] = dep
                for transitive_contract, transitive_id in dep["manifest"].get("dependencies", {}).items():
                    if transitive_contract in dependencies and dependencies[transitive_contract] != transitive_id:
                        errors.append(f"{fname}: conflicting dependency {transitive_contract}")
        if len(selected) == 1 + len(DEPENDENCIES[contract]):
            referential_checks(selected, errors, warnings)
        behavioral_checks(doc, errors)

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, default=SAMPLES, help="directory containing the complete set of *.snapshot.json deliveries")
    args = parser.parse_args()
    files = sorted(args.snapshot_dir.glob("*.snapshot.json"))
    try:
        snapshots = [load(f) for f in files]
    except (OSError, ValueError) as exc:
        print(f"FAIL: cannot read snapshot: {exc}")
        return 1
    errors, warnings = validate_documents(snapshots)
    for w in warnings:
        print("WARN:", w)
    if errors:
        print(f"FAIL: {len(errors)} contract violation(s)")
        for e in errors:
            print("  -", e)
        return 1
    print(f"PASS: {len(snapshots)} snapshots valid (schema + checksum + referential + rule tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

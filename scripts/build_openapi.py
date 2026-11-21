#!/usr/bin/env python3
"""Build the SCAILED Pathfinder Swagger/OpenAPI document.

The operations, parameters and response models are exported from the LIVE
FastAPI app (pathfinder.api.main.app) so the document can never drift from
the code. This script then layers the WP boundary interface design on top:
  * components.schemas.SnapshotEnvelope + the five contract payload schemas,
    taken verbatim from contracts/*.schema.json (single source of truth);
  * golden examples taken from contracts/samples/*.snapshot.json;
  * admin security scheme, tags and protocol cross-references.

Outputs: docs/18_pathfinder_openapi.json / .yaml (+ Swagger UI via
build_swagger_ui.py). Run with the project venv python:
  python scripts/build_openapi.py
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
OUT_JSON = ROOT / "docs/18_pathfinder_openapi.json"
OUT_YAML = ROOT / "docs/18_pathfinder_openapi.yaml"

CONTRACT_COMPONENTS = {  # contract name -> payload schema file
    "pf.taxonomy.v1": "wp2-taxonomy.schema.json",
    "pf.questionnaire.v1": "wp4-questionnaire.schema.json",
    "pf.roadmap.v1": "wp3-roadmap.schema.json",
    "pf.rulebundle.v1": "wp8-rulebundle.schema.json",
    "pf.feedback.v1": "wp4-feedback.schema.json",
}
SAMPLES = {
    "pf.taxonomy.v1": "wp2-taxonomy.snapshot.json",
    "pf.questionnaire.v1": "wp4-questionnaire.snapshot.json",
    "pf.roadmap.v1": "wp3-roadmap.snapshot.json",
    "pf.rulebundle.v1": "wp8-rulebundle.snapshot.json",
    "pf.feedback.v1": "wp4-feedback.snapshot.json",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def strip_meta(schema: dict) -> dict:
    for key in ("$schema", "$id", "$comment"):
        schema.pop(key, None)
    return schema


def build() -> dict:
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from pathfinder.api.main import app  # live surface, never hand-copied

    spec = copy.deepcopy(app.openapi())

    spec["info"].update({
        "title": "SCAILED Pathfinder — Public Interface (WP Boundary Contracts + Service API)",
        "version": "0.1.0",
        "description": (
            "Machine-readable view of the WP boundary data interface and the Pathfinder service API.\n\n"
            "* Normative companion (human-readable): `docs/16_wp_boundary_data_protocol.md` "
            "([Confluence page](https://edmf.atlassian.net/wiki/spaces/S/pages/11370498)).\n"
            "* Source of truth for payload structures: `contracts/*.schema.json` — the `SnapshotEnvelope` "
            "components below are embedded verbatim from those files.\n"
            "* Every imported snapshot passes the four validation gates at activation time "
            "(`scripts/validate_contracts.py`, also executed in-process by the server).\n\n"
            "Boundary flow: WP2/WP3/WP8 (and WP4 self-descriptions) deliver versioned JSON snapshots via "
            "`POST /v1/admin/import`; `GET /health` reports the active snapshot generation. "
            "Paths under `/admin/import/*` are the legacy per-WP demo endpoints retained for the in-memory mode."
        ),
    })
    spec["servers"] = [
        {"url": "http://localhost:8000", "description": "local development (docker compose up)"},
    ]
    spec["tags"] = [
        {"name": "Boundary contracts", "description": "WP2/WP3/WP4/WP8 snapshot import and activation (the frozen interface)."},
        {"name": "Questionnaires", "description": "WP4 questionnaire definitions served from the active snapshot generation."},
        {"name": "Assessments", "description": "Stakeholder assessment session lifecycle and deterministic results."},
        {"name": "Roadmap", "description": "WP3 roadmap graph, projected from the active pf.roadmap.v1 snapshot."},
        {"name": "Admin (legacy demo)", "description": "Single-file per-WP imports and rule reload for the in-memory mode."},
        {"name": "Health", "description": "Liveness and readiness."},
    ]
    spec.setdefault("components", {})["securitySchemes"] = {
        "AdminBearer": {
            "type": "http", "scheme": "bearer",
            "description": "PATHFINDER_ADMIN_TOKEN. Required on all boundary/admin operations.",
        }
    }

    schemas = spec["components"]["schemas"]

    # --- contract payload components, verbatim from contracts/ -------------
    payload_refs = []
    for contract, fname in CONTRACT_COMPONENTS.items():
        name = "PF_" + contract.replace(".", "_")
        comp = strip_meta(load(CONTRACTS / fname))
        # "#/$defs/x" must resolve inside the component, not the OpenAPI root
        comp = json.loads(json.dumps(comp).replace('"#/$defs/', f'"#/components/schemas/{name}/$defs/'))
        comp.setdefault("title", contract)
        schemas[name] = comp
        payload_refs.append({"$ref": f"#/components/schemas/{name}"})

    envelope = strip_meta(load(CONTRACTS / "envelope.schema.json"))
    # map external payload refs ("wpN-x.schema.json") to the component refs defined above
    by_file = {fname: "PF_" + contract.replace(".", "_") for contract, fname in CONTRACT_COMPONENTS.items()}
    env_txt = json.dumps(envelope)
    env_txt = re.sub(r'"([a-z0-9-]+)\.schema\.json"',
                     lambda m: '"#/components/schemas/' + by_file[m.group(1) + ".schema.json"] + '"',
                     env_txt)
    envelope = json.loads(env_txt)
    envelope = json.loads(json.dumps(envelope).replace('"#/$defs/', '"#/components/schemas/SnapshotEnvelope/$defs/'))
    envelope["title"] = "SnapshotEnvelope"
    envelope["description"] = ("The single delivery format for every cross-WP artefact "
                               "(protocol §3): {contract, manifest, payload}.")
    schemas["SnapshotEnvelope"] = envelope

    schemas["BoundaryImportRequest"] = {
        "type": "object", "required": ["snapshots"], "additionalProperties": False,
        "properties": {"snapshots": {"type": "array", "minItems": 1, "items": {"$ref": "#/components/schemas/SnapshotEnvelope"},
            "description": "Complete dependency closure: every snapshot referenced by supersedes/depends_on must be present in this call or already active."}},
        "title": "BoundaryImportRequest",
    }
    schemas["ActivationReport"] = {
        "type": "object", "required": ["accepted"],
        "properties": {
            "accepted": {"type": "boolean"},
            "generation_id": {"type": "string", "description": "Identifier of the newly activated snapshot generation."},
            "snapshot_ids": {"type": "object", "additionalProperties": {"type": "string"},
                             "description": "contract -> snapshot id now active."},
            "questionnaire_ids": {"type": "object", "additionalProperties": {"type": "string"},
                                  "description": "stakeholder type -> active questionnaire snapshot id."},
            "regulatory_status": {"type": "string", "description": "Status projected from the active rule bundle."},
            "warnings": {"type": "array", "items": {"type": "string"},
                         "description": "Non-blocking findings (e.g. unverified compliance references, protocol §6)."},
        }, "title": "ActivationReport",
        "description": "400 + Validation error when any gate fails (all-or-nothing activation).",
    }

    # --- enrich operations --------------------------------------------------
    def op(path: str, method: str = "post") -> dict:
        return spec["paths"][path][method]

    examples = {c: load(CONTRACTS / "samples" / f) for c, f in SAMPLES.items()}

    imp = op("/v1/admin/import")
    imp["tags"] = ["Boundary contracts"]
    imp["security"] = [{"AdminBearer": []}]
    imp["summary"] = "Import & activate boundary snapshots (atomic)"
    imp["description"] = ("Validates each envelope against `contracts/` (Gate 1 schema, Gate 2 checksum + manifest, "
                          "Gate 3 referential R1–R13, Gate 4 rule tests) and, only if the whole batch passes, "
                          "activates it as a new generation. On any violation nothing changes and a 400 Validation "
                          "error lists every finding.")
    imp["requestBody"] = {
        "required": True,
        "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/BoundaryImportRequest"},
            "examples": {"full-delivery": {"summary": "One snapshot per producer contract",
                                           "value": {"snapshots": [examples[c] for c in
                                                       ("pf.taxonomy.v1", "pf.roadmap.v1", "pf.questionnaire.v1", "pf.rulebundle.v1")]}}},
        }},
    }
    imp["responses"]["200"] = {"description": "Batch validated and activated as a new generation.",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ActivationReport"}}}}

    legacy_map = {"/admin/import/wp2": "pf.taxonomy.v1", "/admin/import/wp3": "pf.roadmap.v1",
                  "/admin/import/wp8": "pf.rulebundle.v1"}
    for path, contract in legacy_map.items():
        o = op(path)
        o["tags"] = ["Admin (legacy demo)"]
        o["security"] = [{"AdminBearer": []}]
        o["description"] = (f"Legacy single-snapshot import for the in-memory demo mode; accepts one "
                            f"`{contract}` SnapshotEnvelope. In PostgreSQL boundary mode this endpoint is "
                            "disabled — use `POST /v1/admin/import` (protocol §8–9).")
        o["requestBody"] = {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SnapshotEnvelope"},
            "examples": {contract: {"value": examples[contract]}}}}}

    op("/admin/rules/reload")["tags"] = ["Admin (legacy demo)"]
    op("/admin/rules/reload")["security"] = [{"AdminBearer": []}]
    op("/admin/rules/reload")["description"] = "Reload rule bundle in the in-memory demo mode; rejected in PostgreSQL boundary mode."
    for path in ("/admin/", "/admin/api/recent", "/admin/api/stats", "/admin/api/abusive"):
        for m in spec["paths"][path]:
            spec["paths"][path][m]["tags"] = ["Admin (legacy demo)"]
    for p in spec["paths"]:
        for m, o in spec["paths"][p].items():
            if "tags" in o:
                continue
            if p.startswith("/v1/questionnaires"):
                o["tags"] = ["Questionnaires"]
            elif "/assessments" in p:
                o["tags"] = ["Assessments"]
            elif "/roadmap" in p:
                o["tags"] = ["Roadmap"]
            elif p == "/health":
                o["tags"] = ["Health"]

    # Any schema referenced by a $ref but not emitted by FastAPI (e.g. models
    # only used inside a manual responses={...} declaration) gets injected here.
    import pathfinder.api.schemas as api_schemas

    refs: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str) and v.startswith("#/components/schemas/"):
                    refs.add(v.rsplit("/", 1)[-1])
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(spec.get("paths", {}))
    for name in sorted(refs - set(spec["components"]["schemas"])):
        model = getattr(api_schemas, name, None)
        if model is not None and hasattr(model, "model_json_schema"):
            schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
            schema.pop("$defs", None)
            spec["components"]["schemas"][name] = schema

    health = op("/health", "get")
    health.setdefault("description", "Reports the active boundary snapshot generation when PostgreSQL mode is on.")
    return spec


def _render_yaml(spec: dict) -> str | None:
    try:
        import yaml
    except ImportError:
        return None
    return yaml.safe_dump(spec, sort_keys=False, width=110, allow_unicode=True)


def main(check: bool = False) -> None:
    spec = build()
    rendered = json.dumps(spec, indent=2) + "\n"
    if check:
        if OUT_JSON.read_text() != rendered:
            print(f"DRIFT: {OUT_JSON.name} is stale - run: python3 scripts/build_openapi.py")
            raise SystemExit(1)
        y = _render_yaml(spec)
        if y is not None and OUT_YAML.exists() and OUT_YAML.read_text() != y:
            print(f"DRIFT: {OUT_YAML.name} is stale - run: python3 scripts/build_openapi.py")
            raise SystemExit(1)
        print("openapi contract up to date")
        return
    OUT_JSON.write_text(rendered)
    print(f"wrote {OUT_JSON.name} ({OUT_JSON.stat().st_size//1024} KB)")
    out_yaml = OUT_YAML
    try:
        import yaml
        out_yaml.write_text(yaml.safe_dump(spec, sort_keys=False, width=110, allow_unicode=True))
        print(f"wrote {out_yaml.name} ({out_yaml.stat().st_size//1024} KB)")
    except ImportError:
        print("pyyaml unavailable - JSON only")


if __name__ == "__main__":
    main(check="--check" in sys.argv[1:])

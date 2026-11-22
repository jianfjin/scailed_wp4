"""The shared live/exported OpenAPI contract, enriched from repository schemas."""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"

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


def _enrich_legacy_imports(spec: dict) -> None:
    """Document the flat demo payloads consumed by the existing importers."""
    schemas = spec["components"]["schemas"]
    strings = {"type": "array", "items": {"type": "string"}}
    nonempty_string = {"type": "string", "minLength": 1}
    schemas["LegacyWP2ImportRequest"] = {
        "type": "object", "required": ["version", "stakeholder_types"],
        "properties": {
            "version": nonempty_string,
            "stakeholder_types": {"type": "array", "minItems": 1, "items": {
                "type": "object", "required": ["id", "label", "personas", "user_journeys"],
                "properties": {
                    "id": nonempty_string, "label": nonempty_string,
                    "personas": strings, "user_journeys": strings,
                    "capabilities": strings, "pain_points": strings,
                    "feedback_categories": strings,
                },
            }},
        },
    }
    schemas["LegacyWP3ImportRequest"] = {
        "type": "object", "required": ["version", "nodes", "edges"],
        "properties": {
            "version": nonempty_string,
            "nodes": {"type": "array", "minItems": 1, "items": {
                "type": "object",
                "required": ["node_id", "label", "dimension", "maturity_level", "stakeholder_types"],
                "properties": {
                    "node_id": nonempty_string, "label": nonempty_string,
                    "dimension": nonempty_string, "maturity_level": {"type": "integer"},
                    "stakeholder_types": strings, "description": {"type": "string"},
                    "prerequisites": strings, "source_doc_ref": {"type": "string"},
                },
            }},
            "edges": {"type": "array", "items": {
                "type": "object", "required": ["edge_id", "from_node_id", "to_node_id"],
                "properties": {
                    "edge_id": nonempty_string, "from_node_id": nonempty_string,
                    "to_node_id": nonempty_string, "relation_type": {"type": "string"},
                    "required": {"type": "boolean"}, "source_doc_ref": {"type": "string"},
                },
            }},
        },
    }
    # Reuse the exact schema used by RuleLoader, including its recursive DSL.
    wp8 = strip_meta(load(ROOT / "pathfinder/core/rules/schema.json"))
    schemas["LegacyWP8ImportRequest"] = json.loads(json.dumps(wp8).replace(
        '"#/$defs/', '"#/components/schemas/LegacyWP8ImportRequest/$defs/'))

    examples = {
        "wp2": {
            "version": "legacy-wp2-v1", "stakeholder_types": [{
                "id": "biotech-sme", "label": "Biotech SME",
                "personas": ["Research lead"], "user_journeys": ["Assess secondary-use readiness"],
                "capabilities": ["secure-processing"], "pain_points": [],
            }],
        },
        "wp3": {
            "version": "legacy-wp3-v1", "nodes": [{
                "node_id": "legacy-intake", "label": "Readiness intake", "dimension": "governance",
                "maturity_level": 1, "stakeholder_types": ["all"], "prerequisites": [],
            }], "edges": [],
        },
        "wp8": {
            "version": "legacy-wp8-v1", "rules": [{
                "rule_id": "LEGACY-REVIEW-001", "rule_type": "preference", "priority": 10,
                "applies_to": ["all"], "condition": {},
                "action": {"title": "Review evidence", "text": "Review readiness evidence before proceeding."},
                "compliance_refs": ["D4.1"],
            }], "tests": [{
                "name": "Readiness evidence review", "state": {
                    "stakeholder_type": "biotech-sme", "target_scenario": "secondary-use-readiness",
                    "answers": {"governance_maturity": 1, "data_maturity": 1, "compliance_maturity": 1,
                                "capabilities": [], "missing_capabilities": [], "regulatory_flags": []},
                }, "expected_rule_ids": ["LEGACY-REVIEW-001"],
            }],
        },
    }
    for wp, example in examples.items():
        operation = spec["paths"][f"/admin/import/{wp}"]["post"]
        operation.update({
            "tags": ["Admin (legacy demo)"], "deprecated": True,
            "description": (
                "Admin token required. Legacy flat JSON import for the in-memory demo mode. "
                "The root contains version and stakeholder_types (WP2), nodes/edges (WP3), "
                "or rules/tests (WP8); it is not a SnapshotEnvelope. Schema validation, "
                "duplicate/reference checks and paired rule tests run before activation. "
                "Disabled in PostgreSQL boundary mode; use POST /v1/admin/import."
            ),
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"$ref": f"#/components/schemas/Legacy{wp.upper()}ImportRequest"},
                "examples": {"flat-demo": {"summary": "Legacy demo payload", "value": example}},
            }}},
        })


def enrich_openapi(spec: dict) -> dict:
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
        {"url": "/", "description": "Current API origin (hosted documentation)"},
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
    schemas = spec["components"]["schemas"]

    # --- contract payload components, verbatim from contracts/ -------------
    for contract, fname in CONTRACT_COMPONENTS.items():
        name = "PF_" + contract.replace(".", "_")
        comp = strip_meta(load(CONTRACTS / fname))
        # "#/$defs/x" must resolve inside the component, not the OpenAPI root
        comp = json.loads(json.dumps(comp).replace('"#/$defs/', f'"#/components/schemas/{name}/$defs/'))
        comp.setdefault("title", contract)
        schemas[name] = comp

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
            "description": "Complete runtime dependency closure in THIS batch: include taxonomy, roadmap, questionnaire(s) and rulebundle, plus every exact manifest.dependencies snapshot. Active snapshots are not merged into this batch. manifest.supersedes is historical lineage and does not require resubmitting its predecessor."}},
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

    _enrich_legacy_imports(spec)

    op("/admin/rules/reload")["tags"] = ["Admin (legacy demo)"]
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

    for methods in spec["paths"].values():
        for operation in methods.values():
            if operation.get("security"):
                operation["responses"]["429"] = {
                    "description": "Per-token/IP rate limit exceeded",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorEnvelope"}}},
                }
            # HTTPException/middleware errors are JSON even on HTML/FHIR routes.
            # FastAPI otherwise inherits that route's success media type here.
            for status, response in operation["responses"].items():
                if status in {"400", "401", "403", "404", "409", "429", "500", "503"}:
                    response["content"] = {"application/json": {
                        "schema": {"$ref": "#/components/schemas/ApiErrorEnvelope"},
                    }}

    health = op("/health", "get")
    health.setdefault("description", "Reports the active boundary snapshot generation when PostgreSQL mode is on.")
    return spec


def install_openapi(app: FastAPI) -> None:
    """Cache one enriched schema for /openapi.json, /docs, and offline exports."""
    def custom_openapi() -> dict:
        if app.openapi_schema is None:
            app.openapi_schema = enrich_openapi(get_openapi(
                title=app.title,
                version=app.version,
                openapi_version=app.openapi_version,
                description=app.description,
                routes=app.routes,
                separate_input_output_schemas=app.separate_input_output_schemas,
            ))
        return app.openapi_schema

    app.openapi = custom_openapi

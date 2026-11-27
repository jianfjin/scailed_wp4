"""Contract test for the committed OpenAPI specification.

Guards against drift between the FastAPI code (pathfinder/api/main.py and
pathfinder/api/dashboard.py) and the version-controlled contract in
docs/18_pathfinder_openapi.{json,yaml}. The same checks run in CI via
.github/workflows/openapi-contract.yml.

Run directly:  python3 tests/test_openapi_contract.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SPEC_PATH = ROOT / "docs/18_pathfinder_openapi.json"


def _generated_spec() -> dict:
    """Build the spec exactly as scripts/build_openapi.py does."""
    import build_openapi

    return copy.deepcopy(build_openapi.build())


def _check_matches_committed() -> tuple[bool, list[str]]:
    """Compare in-code contract with committed file (JSON semantics)."""
    generated = _generated_spec()
    committed = json.loads(SPEC_PATH.read_text())
    diffs: list[str] = []
    if set(generated) != set(committed):
        diffs.append("top-level keys differ")
    # Compare per-path so failure output is actionable.
    gen_paths = generated.get("paths", {})
    com_paths = committed.get("paths", {})
    for p in sorted(set(gen_paths) | set(com_paths)):
        if json.dumps(gen_paths.get(p), sort_keys=True) != json.dumps(com_paths.get(p), sort_keys=True):
            diffs.append(f"path {p} differs")
    gen_comps = generated.get("components", {}).get("schemas", {})
    com_comps = committed.get("components", {}).get("schemas", {})
    for name in sorted(set(gen_comps) | set(com_comps)):
        if json.dumps(gen_comps.get(name), sort_keys=True) != json.dumps(com_comps.get(name), sort_keys=True):
            diffs.append(f"component schema {name} differs")
    if generated != committed and not diffs:
        diffs.append("metadata, security schemes, or other contract fields differ")
    return (not diffs, diffs)


def _check_valid_openapi() -> tuple[bool, str]:
    generated = _generated_spec()
    try:
        from openapi_spec_validator import validate
    except ImportError:
        return False, "openapi-spec-validator not installed"
    try:
        validate(generated)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:500]


def _check_every_operation_typed() -> tuple[bool, list[str]]:
    """Every POST/PATCH must declare a requestBody; every 2xx JSON response
    must reference a named schema (no bare additionalProperties objects)."""
    spec = json.loads(SPEC_PATH.read_text())
    # POSTs that act as triggers (no JSON body by design):
    bodyless_posts = {
        "/v1/assessments/{assessment_id}/recommendations",  # path + query only
        "/v2/assessments/{assessment_id}/recommendations",
        "/admin/rules/reload",  # reload trigger
    }
    gaps: list[str] = []
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method in ("post", "put", "patch") and "requestBody" not in op and path not in bodyless_posts:
                gaps.append(f"{method.upper()} {path}: no requestBody")
            resp = op.get("responses", {}).get("200", {})
            content = resp.get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema", {})
                loose = schema.get("additionalProperties") is True or schema == {}
                if loose:
                    gaps.append(f"{method.upper()} {path}: weak 200 schema {schema}")
    return (not gaps, gaps)


def main() -> int:
    rc = 0
    ok, diffs = _check_matches_committed()
    print(f"spec matches committed contract: {'OK' if ok else 'DRIFT'}")
    for d in diffs[:20]:
        print(f"  - {d}")
        rc = 1
    ok, err = _check_valid_openapi()
    print(f"openapi-spec-validator: {'VALID' if ok else 'INVALID: ' + err}")
    rc = rc or (0 if ok else 1)
    ok, gaps = _check_every_operation_typed()
    print(f"all operations typed: {'OK' if ok else f'{len(gaps)} gap(s)'}")
    for g in gaps[:20]:
        print(f"  - {g}")
    rc = rc or (0 if ok else 1)
    return rc


def test_spec_matches_committed_contract():
    ok, diffs = _check_matches_committed()
    assert ok, "committed OpenAPI file drifted from code:\n" + "\n".join(diffs)


def test_committed_contract_is_valid_openapi():
    ok, err = _check_valid_openapi()
    assert ok, f"invalid OpenAPI: {err}"


def test_all_operations_have_typed_models():
    ok, gaps = _check_every_operation_typed()
    assert ok, "untyped request/response models:\n" + "\n".join(gaps)


def test_live_json_yaml_and_swagger_serve_the_same_contract():
    import yaml
    from fastapi.testclient import TestClient
    from pathfinder.api.main import app

    spec = json.loads(SPEC_PATH.read_text())
    assert spec["servers"][0]["url"] == "/"  # Hosted docs must target their own origin.
    assert TestClient(app).get("/openapi.json").json() == spec
    assert yaml.safe_load(SPEC_PATH.with_suffix(".yaml").read_text()) == spec
    html = (ROOT / "docs/18_pathfinder_swagger.html").read_text()
    embedded, _ = json.JSONDecoder().raw_decode(html.rsplit("const SPEC = ", 1)[1])
    assert embedded == spec


def test_all_local_schema_references_resolve():
    spec = _generated_spec()

    def walk(node):
        if isinstance(node, dict):
            ref = node.get("$ref", "")
            if ref.startswith("#/"):
                target = spec
                for part in ref[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(spec)


def test_every_protected_operation_declares_bearer_auth_and_rate_limits():
    spec = _generated_spec()
    assert spec["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    for path, methods in spec["paths"].items():
        for operation in methods.values():
            if path == "/health":
                assert not operation.get("security")
                continue
            assert operation["security"] == [{"BearerAuth": []}], path
            assert "429" in operation["responses"], path
            assert not any(p["in"] == "header" and p["name"].lower() == "authorization"
                           for p in operation.get("parameters", [])), path


if __name__ == "__main__":
    sys.exit(main())


def test_v2_boundary_schemas_and_examples_are_explicit():
    from jsonschema import Draft202012Validator
    spec=_generated_spec()
    schemas=spec['components']['schemas']
    for contract in ('pf.questionnaire.v2','pf.rulebundle.v2','pf.withdrawal.v1'):
        assert 'PF_'+contract.replace('.','_') in schemas
    notice=json.loads((ROOT/'contracts/samples/v2/withdrawal.notice.json').read_text())
    schema=spec['paths']['/v2/admin/withdrawals']['post']['requestBody']['content']['application/json']['schema']
    Draft202012Validator({**schema,'components':spec['components']}).validate(notice)
    assert schemas['RecommendationResponse']['properties']['current_validity']
    assert schemas['StakeholderStateResponse']['properties']['capability_findings']

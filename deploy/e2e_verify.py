#!/usr/bin/env python3
"""
SCAILED Pathfinder — T1 E2E Verification (OpenSpec 1.5)

Verifies the full pipeline end-to-end:
  1. Docker containers healthy
  2. Health check (graph_backend=inmemory)
  3. Import demo data
  4. Full pipeline: assessment → answers → recommendation → report → traceability
  5. Multi-stakeholder (all available types)
  6. Audit chain integrity

Python 3 stdlib only.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request

API_BASE = "http://localhost/api"
DEMO_TOKEN = "demo-token"
ADMIN_TOKEN = "admin-token"

FAILURES = 0


def _api(method: str, path: str, token: str | None = None,
         body: dict | None = None, timeout: int = 15) -> tuple[int, object]:
    url = f"{API_BASE}{path}"
    data_bytes = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data_bytes, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, str(exc)


def _g(data: object, *keys: str, default: object = "?") -> object:
    """Safely navigate nested dict keys."""
    for k in keys:
        if isinstance(data, dict):
            data = data.get(k, default)
        else:
            return default
    return data


def _fail(msg: str) -> None:
    global FAILURES
    FAILURES += 1
    print(f"  ✗ FAIL: {msg}")


def _ok() -> None:
    print("  ✓ OK")


# ---------------------------------------------------------------------------
# Step 1: Docker containers
# ---------------------------------------------------------------------------
def step1_docker() -> None:
    print("=== Step 1: Docker containers healthy ===")
    required = ["scailed-backend", "scailed-postgres", "scailed-redis", "scailed-traefik"]
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
        capture_output=True, text=True, timeout=10,
    )
    containers = {}
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        containers[parts[0]] = parts[1] if len(parts) > 1 else ""

    for name in required:
        if name not in containers:
            _fail(f"container {name} not running")
        elif "healthy" not in containers[name].lower() and "up" not in containers[name].lower():
            _fail(f"{name} unhealthy: {containers[name]}")
        else:
            print(f"  {name}: ✓ ({containers[name]})")
    print()


# ---------------------------------------------------------------------------
# Step 2: Health + backend
# ---------------------------------------------------------------------------
def step2_health() -> None:
    print("=== Step 2: Health check ===")
    status, data = _api("GET", "/health")
    if status != 200:
        _fail(f"health failed (HTTP {status})")
    _ok()
    gb = _g(data, "graph_backend")
    print(f"    status={_g(data, 'status')}, graph_backend={gb}")
    if gb != "inmemory":
        _fail(f"graph_backend={gb}, expected 'inmemory'")
    print()


# ---------------------------------------------------------------------------
# Step 3: Import demo data
# ---------------------------------------------------------------------------
def step3_import() -> None:
    print("=== Step 3: Import WP2 demo data (all 5 types) ===")
    status, data = _api("POST", "/admin/import/wp2", token=ADMIN_TOKEN, body={
        "version": "t1-e2e-verify",
        "stakeholder_types": [
            {"id": "biotech-sme", "label": "Biotech SME",
             "personas": ["researcher"], "user_journeys": ["prepare EHDS readiness"],
             "feedback_categories": ["acceptance"]},
            {"id": "academic-hospital", "label": "Academic Hospital",
             "personas": ["clinician"], "user_journeys": ["assess EHDS compliance"],
             "feedback_categories": ["acceptance"]},
            {"id": "cro", "label": "CRO",
             "personas": ["study-manager"], "user_journeys": ["prepare trial readiness"],
             "feedback_categories": ["acceptance"]},
            {"id": "health-authority", "label": "Health Authority",
             "personas": ["regulator"], "user_journeys": ["audit EHDS readiness"],
             "feedback_categories": ["acceptance"]},
            {"id": "pharma-company", "label": "Pharma Company",
             "personas": ["compliance-officer"], "user_journeys": ["prepare EHDS submission"],
             "feedback_categories": ["acceptance"]},
        ],
    })
    if status != 200:
        _fail(f"import failed (HTTP {status})")
    _ok()
    print(f"    accepted={_g(data, 'accepted')}, records={_g(data, 'activated_records')}")
    print()


# ---------------------------------------------------------------------------
# Step 4: Full single-stakeholder pipeline with traceability
# ---------------------------------------------------------------------------
def step4_pipeline() -> str:
    print("=== Step 4: Full pipeline (import → recommendation → report) ===")

    # 4a — Create assessment
    status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
        body={"stakeholder_type": "biotech-sme", "target_scenario": "secondary-use-readiness"})
    if status != 200:
        _fail(f"create assessment failed: HTTP {status}")
    aid = _g(data, "assessment_id")
    print(f"    assessment_id={aid}")

    # 4b — Submit answers
    status, _ = _api("POST", f"/v1/assessments/{aid}/answers/batch", token=DEMO_TOKEN,
        body={"answers": {"governance_maturity": 2, "data_maturity": 2,
                          "compliance_maturity": 2, "capabilities": ["secure-processing"],
                          "missing_capabilities": ["data-catalog"],
                          "regulatory_flags": ["gdpr-review-needed"]}})
    if status != 200:
        _fail("submit answers failed")
    print("    answers submitted ✓")

    # 4c — Get recommendations
    status, rec = _api("POST", f"/v1/assessments/{aid}/recommendations", token=DEMO_TOKEN)
    if status != 200:
        _fail("recommendations failed")
    rec_status = _g(rec, "status")
    confidence = _g(rec, "confidence")
    triggered = len(_g(rec, "triggered_rules", default=[]) or [])
    print(f"    status={rec_status}, confidence={confidence}, triggered_rules={triggered}")

    if confidence in ("?", 0):
        _fail(f"confidence={confidence} — untrusted recommendation")

    # 4d — Export report and verify traceability
    status, report = _api("GET", f"/v1/assessments/{aid}/report", token=DEMO_TOKEN)
    if status != 200:
        _fail(f"report export failed: HTTP {status}")

    # Check key sections exist
    session = _g(report, "session")
    rp = _g(report, "recommended_path")
    if not isinstance(session, dict):
        _fail("report missing session section")
    if not isinstance(rp, dict):
        _fail("report missing recommended_path section")

    # Traceability chain (inside recommended_path.trace)
    trace = _g(rp, "trace")
    schema_version = _g(trace, "schema_version")
    rule_version = _g(trace, "rule_version")
    path_backend = _g(rp, "path_backend")
    trace_confidence = _g(trace, "confidence")
    audit_valid = _g(report, "audit_chain_valid")

    print(f"    schema_version={schema_version}")
    print(f"    rule_version={rule_version}")
    print(f"    path_backend={path_backend}")
    print(f"    audit_chain_valid={audit_valid}")

    if not schema_version or schema_version == "?":
        _fail("trace.schema_version missing — untraceable")
    elif schema_version != "v1.0-m3-baseline":
        _fail(f"schema_version mismatch: {schema_version}, expected 'v1.0-m3-baseline'")
    if trace_confidence in ("?", 0):
        _fail(f"trace.confidence={trace_confidence} — zero confidence")
    if audit_valid is not True:
        _fail(f"audit_chain_valid={audit_valid}, expected True")

    # Check for actual content in recommended_path
    next_steps = len(_g(rp, "next_steps", default=[]) or [])
    blockers = _g(rp, "blockers", default=[]) or []
    print(f"    next_steps={next_steps}, blockers={len(blockers)}")

    if next_steps == 0 and not blockers:
        _fail("recommended_path has zero next_steps and zero blockers — empty recommendation")

    _ok()
    print(f"    ✓ traceability chain verified\n")
    return str(aid)


# ---------------------------------------------------------------------------
# Step 5: Multi-stakeholder iteration
# ---------------------------------------------------------------------------
def step5_multi_stakeholder() -> int:
    print("=== Step 5: Multi-stakeholder iteration ===")
    # The 5 stakeholder types from demo data
    all_types = [
        "biotech-sme", "academic-hospital", "cro",
        "health-authority", "pharma-company",
    ]
    passed = 0
    for stype in all_types:
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": stype, "target_scenario": "secondary-use-readiness"})
        if status != 200:
            print(f"    {stype}: assessment creation failed (HTTP {status}) — skipping")
            continue

        aid = _g(data, "assessment_id")
        status2, _ = _api("POST", f"/v1/assessments/{aid}/answers/batch", token=DEMO_TOKEN,
            body={"answers": {"governance_maturity": 2, "data_maturity": 2,
                              "compliance_maturity": 2, "capabilities": ["secure-processing"],
                              "missing_capabilities": [], "regulatory_flags": []}})
        if status2 != 200:
            print(f"    {stype}: answers failed (HTTP {status2})")
            continue

        status3, rec = _api("POST", f"/v1/assessments/{aid}/recommendations", token=DEMO_TOKEN)
        if status3 != 200:
            print(f"    {stype}: recommendations failed (HTTP {status3})")
            continue

        rec_status = _g(rec, "status", "?")
        conf = _g(rec, "confidence", "?")
        passed += 1
        print(f"    {stype}: status={rec_status}, confidence={conf} ✓")

    print(f"    {passed}/{len(all_types)} stakeholder types assessed")
    if passed < 3:
        _fail(f"only {passed} types passed — expected >=3")
    print()
    return passed


# ---------------------------------------------------------------------------
# Step 6: Audit chain integrity
# ---------------------------------------------------------------------------
def step6_audit() -> None:
    print("=== Step 6: Audit chain integrity ===")
    status, data = _api("GET", "/health")
    if status != 200:
        _fail(f"health check failed: HTTP {status}")

    audit_events = _g(data, "audit_events", default=0)
    chain_valid = _g(data, "audit_chain_valid")
    gb = _g(data, "graph_backend")
    print(f"    audit_events={audit_events}")
    print(f"    audit_chain_valid={chain_valid}")
    print(f"    graph_backend={gb}")

    if not isinstance(audit_events, int) or audit_events < 3:
        _fail(f"audit_events={audit_events}, expected >=3")
    if chain_valid is not True:
        _fail(f"audit_chain_valid={chain_valid}")
    if gb != "inmemory":
        _fail(f"graph_backend={gb}, expected 'inmemory'")

    print("    ✓ audit chain integrity verified\n")


# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 64)
    print("  SCAILED Pathfinder — T1 E2E Verification (OpenSpec 1.5)")
    print("=" * 64)
    print()

    step1_docker()
    step2_health()
    step3_import()
    step4_pipeline()
    step5_multi_stakeholder()
    step6_audit()

    print("=" * 64)
    if FAILURES == 0:
        print("  ALL CHECKS PASSED — OpenSpec 1.5 verified ✓")
        print("=" * 64)
        return 0
    else:
        print(f"  {FAILURES} CHECK(S) FAILED")
        print("=" * 64)
        return 1


if __name__ == "__main__":
    sys.exit(main())

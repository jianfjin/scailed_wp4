#!/usr/bin/env python3
"""Post-Deploy Smoke Test for SCAILED Pathfinder.

Runs against deployed containers and verifies end-to-end functionality:
  1. docker ps — required containers healthy (frontend optional for API smoke)
  2. Import WP2 demo data via admin API (Bearer admin-token)
  3. Create assessment via public API (Bearer demo-token)
  4. Submit answers + get recommendations
  5. Verify graph_backend is "inmemory"
  6. Verify audit_events > 0
  7. Exit 0 on success

Uses Python 3 stdlib only (urllib, json — no requests dependency).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

API_BASE = "http://localhost/api"
DEMO_TOKEN = "demo-token"
ADMIN_TOKEN = "admin-token"
DOCKER_CMD = shlex.split(os.environ.get("DOCKER_CMD", "docker"))

EXPECTED_CONTAINERS = [
    "scailed-backend",
    "scailed-postgres",
    "scailed-redis",
    "scailed-traefik",
]
OPTIONAL_CONTAINERS = ["scailed-frontend"]


def _api_request(
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
) -> tuple[int, object]:
    """Make an HTTP request to the API and return (status_code, parsed_body)."""
    url = f"{API_BASE}{path}"
    data_bytes = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data_bytes, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            err_body = json.loads(exc.read().decode())
        except Exception:
            err_body = str(exc)
        return exc.code, err_body


def _step(msg: str) -> None:
    """Print an in-progress step marker."""
    print(f"  [{msg}]", end=" ", flush=True)


def _ok() -> None:
    """Print OK and move to next line."""
    print("OK")


def _fail(reason: str) -> None:
    """Print failure reason and exit with code 1."""
    print(f"FAIL: {reason}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Step 1: docker ps — verify 5 containers healthy
# ---------------------------------------------------------------------------
def step1_docker_ps() -> None:
    print("=== Step 1: docker ps (verify required containers healthy) ===")

    result = None
    try:
        result = subprocess.run(
            [*DOCKER_CMD, "ps", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        _fail("docker not found on PATH")
    except Exception as exc:
        _fail(f"docker ps unexpected error: {exc}")

    assert result is not None  # _fail() above exits, so result is always set here
    if result.returncode != 0:
        command = " ".join(DOCKER_CMD)
        _fail(f"{command} ps failed (rc={result.returncode}): {result.stderr.strip()}")

    containers: dict[str, str] = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        name, _, status_str = line.partition(" ")
        containers[name] = status_str

    missing = [c for c in EXPECTED_CONTAINERS if c not in containers]
    if missing:
        _fail(f"missing containers: {missing}")

    all_healthy = True
    for name in EXPECTED_CONTAINERS:
        status_str = containers.get(name, "")
        is_healthy = "healthy" in status_str.lower() or "up" in status_str.lower()
        marker = "✓" if is_healthy else "✗ UNHEALTHY"
        print(f"  {name}: {marker}  ({status_str})")
        if not is_healthy:
            all_healthy = False

    if not all_healthy:
        _fail("some containers are not healthy")
    for name in OPTIONAL_CONTAINERS:
        status_str = containers.get(name)
        if status_str is None:
            print(f"  {name}: optional, not running")
            continue
        is_healthy = "healthy" in status_str.lower() or "up" in status_str.lower()
        marker = "✓" if is_healthy else "✗ UNHEALTHY"
        print(f"  {name}: {marker}  ({status_str})")
        if not is_healthy:
            _fail(f"optional container is present but unhealthy: {name}")
    print("  Required containers present and healthy.\n")


# ---------------------------------------------------------------------------
# Step 2: Import WP2 demo data via admin API
# ---------------------------------------------------------------------------
def step2_import_demo_data() -> None:
    print("=== Step 2: Import WP2 demo data via admin API ===")
    payload: dict = {
        "version": "smoke-test-wp2-v1",
        "stakeholder_types": [
            {
                "id": "biotech-sme",
                "label": "Biotech SME",
                "personas": ["researcher", "data officer"],
                "user_journeys": ["prepare EHDS readiness self-assessment"],
                "feedback_categories": ["acceptance"],
            }
        ],
    }
    _step("POST /admin/import/wp2")
    status, data = _api_request(
        "POST", "/admin/import/wp2", token=ADMIN_TOKEN, body=payload
    )
    if status != 200:
        _fail(f"import failed (HTTP {status}): {data}")
    _ok()
    print(
        f"    accepted={_get(data, 'accepted')}, "
        f"source={_get(data, 'source')}, "
        f"activated_records={_get(data, 'activated_records')}"
    )
    print()


# ---------------------------------------------------------------------------
# Step 3: Create assessment via public API
# ---------------------------------------------------------------------------
def step3_create_assessment() -> str:
    print("=== Step 3: Create assessment via public API ===")
    _step("POST /v1/assessments")
    status, data = _api_request(
        "POST",
        "/v1/assessments",
        token=DEMO_TOKEN,
        body={
            "stakeholder_type": "biotech-sme",
            "target_scenario": "secondary-use-readiness",
        },
    )
    if status != 200:
        _fail(f"create assessment failed (HTTP {status}): {data}")
    assessment_id = _get(data, "assessment_id")
    if not assessment_id:
        _fail(f"no assessment_id in response: {data}")
    _ok()
    print(f"    assessment_id={assessment_id}")
    print()
    return str(assessment_id)


# ---------------------------------------------------------------------------
# Step 4: Submit answers and get recommendations
# ---------------------------------------------------------------------------
def step4_answers_and_recommend(assessment_id: str) -> None:
    print("=== Step 4: Submit answers and get recommendations ===")
    answers_payload: dict = {
        "governance_maturity": 2,
        "data_maturity": 2,
        "compliance_maturity": 2,
        "capabilities": ["secure-processing"],
        "missing_capabilities": ["data-catalog"],
        "regulatory_flags": ["gdpr-review-needed"],
    }

    # 4a — submit answers
    _step("POST /v1/assessments/{id}/answers/batch")
    status, data = _api_request(
        "POST",
        f"/v1/assessments/{assessment_id}/answers/batch",
        token=DEMO_TOKEN,
        body={"answers": answers_payload},
    )
    if status != 200:
        _fail(f"submit answers failed (HTTP {status}): {data}")
    _ok()
    print(
        f"    stakeholder_type={_get(data, 'stakeholder_type')}, "
        f"confidence={_get(data, 'confidence')}"
    )

    # 4b — get recommendations
    _step("POST /v1/assessments/{id}/recommendations")
    status, data = _api_request(
        "POST",
        f"/v1/assessments/{assessment_id}/recommendations",
        token=DEMO_TOKEN,
    )
    if status != 200:
        _fail(f"recommendations failed (HTTP {status}): {data}")
    _ok()
    print(
        f"    status={_get(data, 'status')}, "
        f"confidence={_get(data, 'confidence')}, "
        f"trace.schema_version={_get(_get(data, 'trace'), 'schema_version')}"
    )
    print()


# ---------------------------------------------------------------------------
# Step 5: Verify graph_backend is "inmemory"
# ---------------------------------------------------------------------------
def step5_verify_graph_backend() -> None:
    print("=== Step 5: Verify graph_backend is inmemory ===")
    _step("GET /health")
    status, data = _api_request("GET", "/health")
    if status != 200:
        _fail(f"health check failed (HTTP {status}): {data}")
    _ok()

    backend = _get(data, "graph_backend")
    print(f"    graph_backend={backend}")
    if backend != "inmemory":
        _fail(f"expected graph_backend='inmemory', got '{backend}'")
    print("    graph_backend is 'inmemory' ✓\n")


# ---------------------------------------------------------------------------
# Step 6: Verify audit_events > 0
# ---------------------------------------------------------------------------
def step6_check_audit_events() -> None:
    print("=== Step 6: Check audit_events > 0 ===")
    _step("GET /health")
    status, data = _api_request("GET", "/health")
    if status != 200:
        _fail(f"health check failed (HTTP {status}): {data}")
    _ok()

    audit_events = _get(data, "audit_events")
    chain_valid = _get(data, "audit_chain_valid")
    print(f"    audit_events={audit_events}, audit_chain_valid={chain_valid}")

    if not isinstance(audit_events, int) or audit_events <= 0:
        _fail(f"expected audit_events > 0, got {audit_events}")
    print("    audit_events > 0 ✓\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get(data: object, key: str, default: object = "?") -> object:
    """Safely get a key from a dict-like object."""
    if isinstance(data, dict):
        return data.get(key, default)
    return default


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 62)
    print("  SCAILED Pathfinder — Post-Deploy Smoke Test")
    print("=" * 62)
    print()

    step1_docker_ps()
    step2_import_demo_data()
    assessment_id = step3_create_assessment()
    step4_answers_and_recommend(assessment_id)
    step5_verify_graph_backend()
    step6_check_audit_events()

    print("=" * 62)
    print("  ALL CHECKS PASSED")
    print("=" * 62)
    sys.exit(0)


if __name__ == "__main__":
    main()

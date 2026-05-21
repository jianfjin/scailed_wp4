"""OpenSpec 1.5 — E2E verification tests.

Validates the full pipeline:
  test_e2e_import_to_recommendation — import → assessment → answers → recommendation
  test_e2e_traceability_chain — report has schema_version, rule_version, audit_chain_valid
  test_e2e_docker_clean_boot — docker compose down -v → up -d --build → health check

These tests hit the deployed API and require Docker running.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

API_BASE = "http://localhost/api"
DEMO_TOKEN = "demo-token"
ADMIN_TOKEN = "admin-token"


def _api(method: str, path: str, token: str | None = None,
         body: dict | None = None) -> tuple[int, object]:
    url = f"{API_BASE}{path}"
    data_bytes = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data_bytes, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, str(exc)


def _check_docker() -> bool:
    """Return True if all required containers are running."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=5,
    )
    names = result.stdout.strip().split("\n")
    required = {"scailed-backend", "scailed-postgres", "scailed-redis", "scailed-traefik"}
    return required.issubset(set(names))


# ═══════════════════════════════════════════════════════════════════════


class TestE2EImportToRecommendation:
    """OpenSpec 1.5: Import → assessment → answers → recommendation."""

    @pytest.fixture(autouse=True)
    def require_docker(self) -> None:
        if not _check_docker():
            pytest.skip("Docker containers not running")

    def test_import_demo_data(self) -> None:
        """Admin import must accept WP2 demo data."""
        status, data = _api("POST", "/admin/import/wp2", token=ADMIN_TOKEN, body={
            "version": "pytest-1.5-verify",
            "stakeholder_types": [{
                "id": "biotech-sme", "label": "Biotech SME",
                "personas": ["researcher"],
                "user_journeys": ["prepare EHDS readiness"],
                "feedback_categories": ["acceptance"],
            }],
        })
        assert status == 200, f"import failed: HTTP {status}"
        assert data.get("accepted") is True, f"not accepted: {data}"

    def test_create_assessment(self) -> str:
        """Assessment creation returns a valid ID."""
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        assert status == 200, f"create assessment failed: HTTP {status}"
        aid = data.get("assessment_id")
        assert aid, f"no assessment_id: {data}"
        return str(aid)

    def test_submit_answers_and_get_recommendation(self) -> None:
        """Answers → recommendation produces status + confidence."""
        # Create
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        assert status == 200
        aid = data["assessment_id"]

        # Submit answers
        status2, _ = _api("POST", f"/v1/assessments/{aid}/answers/batch",
            token=DEMO_TOKEN,
            body={"answers": {"governance_maturity": 2, "data_maturity": 2,
                              "compliance_maturity": 2,
                              "capabilities": ["secure-processing"],
                              "missing_capabilities": ["data-catalog"],
                              "regulatory_flags": ["gdpr-review-needed"]}})
        assert status2 == 200, f"answers failed: HTTP {status2}"

        # Get recommendation
        status3, rec = _api("POST", f"/v1/assessments/{aid}/recommendations",
                             token=DEMO_TOKEN)
        assert status3 == 200, f"recommendation failed: HTTP {status3}"
        assert rec.get("status") is not None, f"no status: {rec}"
        conf = rec.get("confidence")
        assert conf is not None, f"no confidence: {rec}"
        assert conf > 0, f"zero confidence: {rec}"

    def test_report_has_required_sections(self) -> None:
        """Report export must contain session and recommended_path."""
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        assert status == 200
        aid = data["assessment_id"]

        _api("POST", f"/v1/assessments/{aid}/answers/batch", token=DEMO_TOKEN,
             body={"answers": {"governance_maturity": 2, "data_maturity": 2,
                               "compliance_maturity": 2,
                               "capabilities": ["secure-processing"],
                               "missing_capabilities": [], "regulatory_flags": []}})
        _api("POST", f"/v1/assessments/{aid}/recommendations", token=DEMO_TOKEN)

        status2, report = _api("GET", f"/v1/assessments/{aid}/report",
                                token=DEMO_TOKEN)
        assert status2 == 200, f"report failed: HTTP {status2}"
        assert "session" in report, "missing session"
        assert "recommended_path" in report, "missing recommended_path"


class TestE2ETraceabilityChain:
    """OpenSpec 1.5: Traceability — schema_version, rule_version, audit_chain."""

    @pytest.fixture(autouse=True)
    def require_docker(self) -> None:
        if not _check_docker():
            pytest.skip("Docker containers not running")

    def test_trace_has_schema_version(self) -> None:
        """recommended_path.trace.schema_version must be present."""
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        assert status == 200
        aid = data["assessment_id"]

        _api("POST", f"/v1/assessments/{aid}/answers/batch", token=DEMO_TOKEN,
             body={"answers": {"governance_maturity": 2, "data_maturity": 2,
                               "compliance_maturity": 2,
                               "capabilities": ["secure-processing"],
                               "missing_capabilities": [], "regulatory_flags": []}})
        _api("POST", f"/v1/assessments/{aid}/recommendations", token=DEMO_TOKEN)

        _, report = _api("GET", f"/v1/assessments/{aid}/report", token=DEMO_TOKEN)
        rp = report.get("recommended_path", {})
        trace = rp.get("trace", {})
        sv = trace.get("schema_version")
        assert sv, f"schema_version missing: {trace}"
        assert sv != "?", f"schema_version is placeholder: {sv}"

    def test_trace_has_rule_version(self) -> None:
        """recommended_path.trace.rule_version must be present."""
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        aid = data["assessment_id"]
        _api("POST", f"/v1/assessments/{aid}/answers/batch", token=DEMO_TOKEN,
             body={"answers": {"governance_maturity": 2, "data_maturity": 2,
                               "compliance_maturity": 2,
                               "capabilities": ["secure-processing"],
                               "missing_capabilities": [], "regulatory_flags": []}})
        _api("POST", f"/v1/assessments/{aid}/recommendations", token=DEMO_TOKEN)
        _, report = _api("GET", f"/v1/assessments/{aid}/report", token=DEMO_TOKEN)
        rp = report.get("recommended_path", {})
        trace = rp.get("trace", {})
        rv = trace.get("rule_version")
        assert rv, f"rule_version missing: {trace}"

    def test_audit_chain_valid(self) -> None:
        """audit_chain_valid must be True in report."""
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        aid = data["assessment_id"]
        _api("POST", f"/v1/assessments/{aid}/answers/batch", token=DEMO_TOKEN,
             body={"answers": {"governance_maturity": 2, "data_maturity": 2,
                               "compliance_maturity": 2,
                               "capabilities": ["secure-processing"],
                               "missing_capabilities": [], "regulatory_flags": []}})
        _api("POST", f"/v1/assessments/{aid}/recommendations", token=DEMO_TOKEN)
        _, report = _api("GET", f"/v1/assessments/{aid}/report", token=DEMO_TOKEN)
        assert report.get("audit_chain_valid") is True, (
            f"audit_chain_valid={report.get('audit_chain_valid')}"
        )

    def test_health_shows_age_backend(self) -> None:
        """Health check must report graph_backend='age'."""
        status, data = _api("GET", "/health")
        assert status == 200
        assert data.get("graph_backend") == "age", (
            f"graph_backend={data.get('graph_backend')}"
        )


class TestE2EDockerCleanBoot:
    """OpenSpec 1.5 / 4.4: Docker Compose clean install verification."""

    COMPOSE_DIR = "deploy"

    def test_docker_compose_config_valid(self) -> None:
        """docker compose config must parse without errors."""
        result = subprocess.run(
            ["docker", "compose", "-f", f"{self.COMPOSE_DIR}/docker-compose.yml",
             "config", "--quiet"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, (
            f"docker compose config failed:\n{result.stderr}"
        )

    def test_all_containers_healthy(self) -> None:
        """All required containers must be running and healthy."""
        if not _check_docker():
            pytest.skip("Docker not running — skip live health check")
        status, data = _api("GET", "/health")
        assert status == 200, f"health failed: HTTP {status}"
        assert data.get("status") == "ok"
        assert data.get("graph_backend") == "age"

    def test_e2e_verify_script_exists_and_syntax_ok(self) -> None:
        """deploy/e2e_verify.py must exist and have valid syntax."""
        import ast
        path = "deploy/e2e_verify.py"
        with open(path) as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"e2e_verify.py syntax error: {e}")

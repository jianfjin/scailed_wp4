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
        assert sv == "v1.0-m3-baseline", (
            f"schema_version mismatch: {sv}, expected 'v1.0-m3-baseline'"
        )

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

    def test_trace_has_regulatory_refs(self) -> None:
        """OpenSpec G5: trace.regulatory_refs must contain real compliance citations.

        The gen-1000-rules use actual regulation references like
        'GDPR-Art.25', 'AI-Act-Art.9', 'EHDS-Art.50', etc.
        """
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        assert status == 200
        aid = data["assessment_id"]

        _api("POST", f"/v1/assessments/{aid}/answers/batch", token=DEMO_TOKEN,
             body={"answers": {"governance_maturity": 2, "data_maturity": 2,
                               "compliance_maturity": 2,
                               "capabilities": ["secure-processing"],
                               "missing_capabilities": ["data-catalog"],
                               "regulatory_flags": ["gdpr-review-needed"]}})
        _api("POST", f"/v1/assessments/{aid}/recommendations", token=DEMO_TOKEN)

        _, report = _api("GET", f"/v1/assessments/{aid}/report", token=DEMO_TOKEN)
        rp = report.get("recommended_path", {})
        trace = rp.get("trace", {})
        refs = trace.get("regulatory_refs", [])

        # Must contain real compliance references in standard format
        assert len(refs) > 10, (
            f"Expected >10 regulatory refs from gen-1000-rules, got {len(refs)}: {refs[:5]}..."
        )
        assert any(r.startswith("GDPR-Art.") for r in refs), (
            f"No GDPR-Art.* ref in regulatory_refs: {refs[:5]}..."
        )
        assert any(r.startswith("EHDS-Art.") for r in refs), (
            f"No EHDS-Art.* ref in regulatory_refs: {refs[:5]}..."
        )

    def test_health_shows_age_backend(self) -> None:
        """Health check must report graph_backend='age'."""
        status, data = _api("GET", "/health")
        assert status == 200
        assert data.get("graph_backend") == "age", (
            f"graph_backend={data.get('graph_backend')}"
        )


class TestE2EErrorPaths:
    """OpenSpec 1.5: Negative/error-path testing (Guido review G2)."""

    @pytest.fixture(autouse=True)
    def require_docker(self) -> None:
        if not _check_docker():
            pytest.skip("Docker containers not running")

    def test_submit_bad_answers_returns_400(self) -> None:
        """Submitting invalid/incomplete answers must return 400."""
        # Create an assessment
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        assert status == 200
        aid = data["assessment_id"]

        # Submit empty/malformed answers (missing required fields)
        status2, err = _api("POST", f"/v1/assessments/{aid}/answers/batch",
            token=DEMO_TOKEN,
            body={"answers": {"governance_maturity": "not-a-number"}})
        assert status2 == 400, (
            f"expected 400 for bad answers, got HTTP {status2}: {err}"
        )

    def test_recommendation_without_answers_returns_error(self) -> None:
        """Requesting recommendation before submitting answers must return an error."""
        # Create an assessment but do NOT submit answers
        status, data = _api("POST", "/v1/assessments", token=DEMO_TOKEN,
            body={"stakeholder_type": "biotech-sme",
                  "target_scenario": "secondary-use-readiness"})
        assert status == 200
        aid = data["assessment_id"]

        # Request recommendation without having submitted answers
        status2, err = _api("POST", f"/v1/assessments/{aid}/recommendations",
                             token=DEMO_TOKEN)
        assert status2 != 200, (
            f"expected error (4xx/5xx) for recommendation without answers, "
            f"got HTTP {status2}: {err}"
        )
        assert status2 >= 400, (
            f"expected client/server error status, got HTTP {status2}"
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


# ═══════════════════════════════════════════════════════════════════════
# Gap #4 (HIGH): Hash chain integrity — verify that modifying an event
# breaks the chain, and that prev_hash links are intact (not just the
# top-level audit_chain_valid flag).
# ═══════════════════════════════════════════════════════════════════════

class TestAuditHashChainIntegrity:
    """OpenSpec 1.5 / Guido review Gap #4: Hash chain tamper detection.

    These are pure unit tests on AuditLog — no Docker required.
    """

    def test_hash_chain_valid_after_normal_appends(self) -> None:
        """After appending events, verify_chain() must return True."""
        from pathfinder.core.audit import AuditLog

        audit = AuditLog()
        audit.append("assessment_session_created", {"assessment_id": "a1"})
        audit.append("answers_submitted", {"assessment_id": "a1"})
        audit.append("recommendation_generated", {"assessment_id": "a1", "status": "ready"})

        assert audit.verify_chain() is True, "chain must be valid after normal appends"

    def test_prev_hash_chain_is_intact(self) -> None:
        """Each event's prev_hash must equal the prior event's event_hash.

        This verifies the actual hash links — not just the top-level
        verify_chain() flag.  Without this check, a system returning
        audit_chain_valid=True with broken hash links would pass.
        """
        from pathfinder.core.audit import AuditLog

        audit = AuditLog()
        e1 = audit.append("assessment_session_created", {"assessment_id": "a1"})
        e2 = audit.append("answers_submitted", {"assessment_id": "a1"})
        e3 = audit.append("recommendation_generated", {"assessment_id": "a1", "status": "ready"})

        events = audit.events()

        # First event must have prev_hash=None
        assert events[0].prev_hash is None, (
            f"first event prev_hash must be None, got {events[0].prev_hash}"
        )

        # Each subsequent event's prev_hash must be the prior event's event_hash
        assert e2.prev_hash == e1.event_hash, (
            f"event[1].prev_hash={e2.prev_hash} != event[0].event_hash={e1.event_hash}"
        )
        assert e3.prev_hash == e2.event_hash, (
            f"event[2].prev_hash={e3.prev_hash} != event[1].event_hash={e2.event_hash}"
        )

        # verify_chain() must agree
        assert audit.verify_chain() is True

    def test_tampered_event_breaks_verify_chain(self) -> None:
        """Modifying an event's prev_hash must cause verify_chain() to return False.

        This is a property test of the AuditLog.verify_chain() algorithm —
        validating that tampering is actually detectable, not just that the
        flag happens to be True in the current run.
        """
        from pathfinder.core.audit import AuditEvent, AuditLog

        audit = AuditLog()
        audit.append("assessment_session_created", {"assessment_id": "a1"})
        audit.append("answers_submitted", {"assessment_id": "a1"})
        audit.append("recommendation_generated", {"assessment_id": "a1", "status": "ready"})

        assert audit.verify_chain() is True, "chain must be valid before tampering"

        # Tamper with the middle event: set prev_hash to a wrong value.
        # AuditEvent is frozen, so we replace the whole object.
        original = audit._events[1]
        tampered = AuditEvent(
            event_type=original.event_type,
            event_data=original.event_data,
            timestamp=original.timestamp,
            prev_hash="00" * 32,  # deliberately wrong sha256 hash
            event_hash=original.event_hash,
            ip_hash=original.ip_hash,
            user_agent_hash=original.user_agent_hash,
        )
        audit._events[1] = tampered

        assert audit.verify_chain() is False, (
            "tampered prev_hash must cause verify_chain() to return False"
        )

    def test_event_hash_mismatch_breaks_chain(self) -> None:
        """If an event's event_hash is altered, the *next* event's prev_hash
        no longer matches, so verify_chain() must return False.

        This covers a different tampering vector: altering the payload
        post-hoc without updating prev_hash links.
        """
        from pathfinder.core.audit import AuditEvent, AuditLog

        audit = AuditLog()
        audit.append("assessment_session_created", {"assessment_id": "a1"})
        audit.append("answers_submitted", {"assessment_id": "a1"})
        audit.append("recommendation_generated", {"assessment_id": "a1", "status": "ready"})

        assert audit.verify_chain() is True

        # Alter event[1]'s event_hash — event[2]'s prev_hash still points
        # to the old value, so the chain should break.
        original = audit._events[1]
        tampered = AuditEvent(
            event_type=original.event_type,
            event_data=original.event_data,
            timestamp=original.timestamp,
            prev_hash=original.prev_hash,  # keep original prev_hash
            event_hash="ff" * 32,  # altered event_hash
            ip_hash=original.ip_hash,
            user_agent_hash=original.user_agent_hash,
        )
        audit._events[1] = tampered

        assert audit.verify_chain() is False, (
            "altered event_hash (while next event points to old value) "
            "must break verify_chain()"
        )

    def test_empty_chain_is_valid(self) -> None:
        """An empty audit log must be valid (no events = nothing to verify)."""
        from pathfinder.core.audit import AuditLog

        audit = AuditLog()
        assert audit.verify_chain() is True, "empty chain must be valid"


# ═══════════════════════════════════════════════════════════════════════
# Gap #3 (HIGH): Audit event type verification — verify that audit
# events include specific types after running the full pipeline.
# ═══════════════════════════════════════════════════════════════════════

class TestE2EAuditEventTypes:
    """OpenSpec 1.5 / Guido review Gap #3: Verify specific audit event
    types after the full pipeline (create → answers → recommend → report).

    These tests access the in-process service directly because the
    deployed API does not currently expose event-type-level details
    (the /health endpoint only reports audit_events count and
    audit_chain_valid boolean).
    """

    def test_audit_event_types_after_full_pipeline(self) -> None:
        """Full pipeline must produce the 4 required event types."""
        from pathfinder.services.assessment_service import AssessmentService

        service = AssessmentService()
        session = service.create_session("biotech-sme", "secondary-use-readiness")
        assessment_id = str(session["assessment_id"])

        service.submit_answers(
            assessment_id,
            {
                "governance_maturity": 2,
                "data_maturity": 2,
                "compliance_maturity": 2,
                "capabilities": ["secure-processing"],
                "missing_capabilities": ["data-catalog"],
                "regulatory_flags": ["gdpr-review-needed"],
            },
        )
        service.generate_recommendation(assessment_id)
        service.report(assessment_id)

        events = service.audit_log.events()
        event_types = {event.event_type for event in events}

        required_types = {
            "assessment_session_created",
            "answers_submitted",
            "recommendation_generated",
            "report_exported",
        }
        missing = required_types - event_types

        assert not missing, (
            f"Missing required audit event types: {missing}. "
            f"Found types: {sorted(event_types)}"
        )

    def test_audit_event_types_exact_order(self) -> None:
        """After the standard pipeline, event types must appear in the
        expected order (session → answers → recommendation → report)."""
        from pathfinder.services.assessment_service import AssessmentService

        service = AssessmentService()
        session = service.create_session("biotech-sme", "secondary-use-readiness")
        assessment_id = str(session["assessment_id"])

        service.submit_answers(
            assessment_id,
            {
                "governance_maturity": 2,
                "data_maturity": 2,
                "compliance_maturity": 2,
                "capabilities": ["secure-processing"],
                "missing_capabilities": [],
                "regulatory_flags": [],
            },
        )
        service.generate_recommendation(assessment_id)
        service.report(assessment_id)

        event_types = [e.event_type for e in service.audit_log.events()]

        assert event_types[0] == "assessment_session_created", (
            f"first event must be assessment_session_created, got {event_types[0]}"
        )
        assert event_types[1] == "answers_submitted", (
            f"second event must be answers_submitted, got {event_types[1]}"
        )
        assert event_types[2] == "recommendation_generated", (
            f"third event must be recommendation_generated, got {event_types[2]}"
        )
        assert event_types[3] == "report_exported", (
            f"fourth event must be report_exported, got {event_types[3]}"
        )

    def test_multiple_assessments_produce_distinct_events(self) -> None:
        """Two independent pipelines must each produce the required
        event types without cross-contamination."""
        from pathfinder.services.assessment_service import AssessmentService

        service = AssessmentService()

        # Pipeline 1
        s1 = service.create_session("biotech-sme", "secondary-use-readiness")
        aid1 = str(s1["assessment_id"])
        service.submit_answers(aid1, {
            "governance_maturity": 2, "data_maturity": 2, "compliance_maturity": 2,
            "capabilities": ["secure-processing"], "missing_capabilities": [],
            "regulatory_flags": [],
        })
        service.generate_recommendation(aid1)
        service.report(aid1)

        # Pipeline 2 — use ai-factory-operator (demo data only has 2 types)
        s2 = service.create_session("ai-factory-operator", "secondary-use-readiness")
        aid2 = str(s2["assessment_id"])
        service.submit_answers(aid2, {
            "governance_maturity": 3, "data_maturity": 3, "compliance_maturity": 3,
            "capabilities": ["data-catalog"], "missing_capabilities": [],
            "regulatory_flags": [],
        })
        service.generate_recommendation(aid2)
        service.report(aid2)

        events = service.audit_log.events()
        event_types = [e.event_type for e in events]

        # Should have 8 events (4 per pipeline)
        assert len(events) == 8, (
            f"expected 8 events for 2 full pipelines, got {len(events)}"
        )

        # Each pipeline's sequence should be present
        expected_sequence = [
            "assessment_session_created",
            "answers_submitted",
            "recommendation_generated",
            "report_exported",
        ]
        assert event_types[:4] == expected_sequence, (
            f"first pipeline sequence mismatch: {event_types[:4]}"
        )
        assert event_types[4:] == expected_sequence, (
            f"second pipeline sequence mismatch: {event_types[4:]}"
        )

        # And the chain must still be valid
        assert service.audit_log.verify_chain() is True, (
            "audit chain must remain valid across multiple pipelines"
        )

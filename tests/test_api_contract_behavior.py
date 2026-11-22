"""Executable OpenAPI examples and runtime error/auth contract regressions.

These tests use an empty upstream cache; no mock servers or database are needed.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import psycopg
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from pathfinder.adapters.upstream import UpstreamClient
from pathfinder.api import main
from pathfinder.core.repositories.boundary_store import SessionConflict
from pathfinder.services.assessment_service import AssessmentService

ADMIN = {"Authorization": "Bearer admin-token"}
DEMO = {"Authorization": "Bearer demo-token"}
ASSESSMENT = "/v1/assessments/{assessment_id}"


@pytest.fixture
def service():
    return AssessmentService(UpstreamClient())


@pytest.fixture
def client(monkeypatch, service):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("PATHFINDER_DEMO_TOKEN", "demo-token")
    monkeypatch.setenv("PATHFINDER_ADMIN_TOKEN", "admin-token")
    monkeypatch.setattr(main, "ENVIRONMENT", "development")
    monkeypatch.setattr(main, "_service", service)
    monkeypatch.setattr(main.app, "middleware_stack", None)
    # Intentionally no lifespan: production pool/bootstrap is outside these tests.
    return TestClient(main.app)


def validate_payload(payload, schema):
    Draft202012Validator({
        **schema, "components": main.app.openapi()["components"],
    }).validate(payload)


def assert_error(response, path, method, status, code):
    assert response.status_code == status, response.text
    declared = main.app.openapi()["paths"][path][method]["responses"][str(status)]
    validate_payload(response.json(), declared["content"]["application/json"]["schema"])
    assert response.json()["detail"]["error"] == code


@pytest.mark.parametrize("token,status,code", [
    (None, 401, "AUTH_REQUIRED"), ("invalid-token", 401, "AUTH_REQUIRED"),
    ("demo-token", 200, None), ("admin-token", 200, None),
])
def test_business_bearer_auth(client, token, status, code):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.get("/v1/questionnaires", headers=headers)
    if code:
        assert_error(response, "/v1/questionnaires", "get", status, code)
    else:
        assert response.status_code == status, response.text


@pytest.mark.parametrize("path,method,kwargs", [
    ("/admin/", "get", {}), ("/admin/api/recent", "get", {}),
    ("/admin/api/stats", "get", {}), ("/admin/api/abusive", "get", {}),
    ("/v1/admin/import", "post", {"json": {"snapshots": []}}),
    ("/admin/import/wp2", "post", {"json": {}}),
    ("/admin/import/wp3", "post", {"json": {}}),
    ("/admin/import/wp8", "post", {"json": {}}),
    ("/admin/rules/reload", "post", {}),
])
def test_demo_token_cannot_access_admin_operations(client, path, method, kwargs):
    response = client.request(method, path, headers=DEMO, **kwargs)
    assert_error(response, path, method, 403, "FORBIDDEN")


@pytest.mark.parametrize("path", ["/admin/", "/admin/api/recent", "/admin/api/stats", "/admin/api/abusive"])
def test_admin_bearer_can_access_dashboard(client, path):
    assert client.get(path, headers=ADMIN).status_code == 200


def test_development_query_token_links_remain_usable(client, service):
    session_id = service.create_session("biotech-sme", "secondary-use-readiness")["assessment_id"]
    assert client.get("/admin/?token=admin-token").status_code == 200
    # Missing ID isolates authentication from report generation.
    response = client.get("/v1/assessments/missing/report?token=demo-token&format=html")
    assert_error(response, ASSESSMENT + "/report", "get", 404, "NOT_FOUND")
    assert client.get(f"/v1/assessments/{session_id}", headers=DEMO).status_code == 200


@pytest.mark.parametrize("path", ["/admin/?token=admin-token", "/v1/assessments/missing/report?token=demo-token"])
def test_production_rejects_query_token(client, monkeypatch, path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(main, "ENVIRONMENT", "production")
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("wp", ["wp2", "wp3", "wp8"])
def test_documented_legacy_example_is_valid_and_executable(client, wp):
    path = f"/admin/import/{wp}"
    operation = main.app.openapi()["paths"][path]["post"]
    media = operation["requestBody"]["content"]["application/json"]
    assert operation["deprecated"] is True
    for example in media["examples"].values():
        payload = copy.deepcopy(example["value"])
        validate_payload(payload, media["schema"])
        response = client.post(path, json=payload, headers=ADMIN)
        assert response.status_code == 200, response.text
        validate_payload(response.json(), operation["responses"]["200"]["content"]["application/json"]["schema"])
        assert response.json()["accepted"] is True


def test_boundary_example_requires_complete_batch_even_after_activation(client, service):
    path = "/v1/admin/import"
    media = main.app.openapi()["paths"][path]["post"]["requestBody"]["content"]["application/json"]
    payload = copy.deepcopy(media["examples"]["full-delivery"]["value"])
    validate_payload(payload, media["schema"])
    response = client.post(path, json=payload, headers=ADMIN)
    assert response.status_code == 200, response.text
    previous = service.active_boundary
    rulebundle = next(s for s in payload["snapshots"] if s["contract"] == "pf.rulebundle.v1")
    response = client.post(path, json={"snapshots": [rulebundle]}, headers=ADMIN)
    assert_error(response, path, "post", 400, "VALIDATION_ERROR")
    assert "missing exact dependency" in response.json()["detail"]["detail"].lower()
    assert service.active_boundary is previous


@pytest.mark.parametrize("suffix,media_type", [("/report", "application/json"), ("/fhir", "application/fhir+json")])
def test_report_and_fhir_success_match_documented_schemas(client, service, suffix, media_type):
    operation = main.app.openapi()["paths"]["/v1/admin/import"]["post"]
    snapshots = copy.deepcopy(operation["requestBody"]["content"]["application/json"]["examples"]["full-delivery"]["value"]["snapshots"])
    service.activate_boundary_snapshots(snapshots)
    questionnaire = next(s["payload"] for s in snapshots if s["contract"] == "pf.questionnaire.v1")
    session_id = service.create_session(questionnaire["stakeholder_type"], questionnaire["target_scenarios"][0])["assessment_id"]
    service.submit_answers(session_id, {
        "pf:wp4:question:biotech-sme-1": "yes",
        "pf:wp4:question:biotech-sme-2": 3,
        "pf:wp4:question:biotech-sme-3": 3,
        "pf:wp4:question:biotech-sme-4": 3,
        "pf:wp4:question:biotech-sme-capabilities": ["legal-basis"],
    })
    service.generate_recommendation(session_id)
    response = client.get(f"/v1/assessments/{session_id}" + suffix, headers=DEMO)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == media_type
    schema = main.app.openapi()["paths"][ASSESSMENT + suffix]["get"]["responses"]["200"]["content"][media_type]["schema"]
    validate_payload(response.json(), schema)


@pytest.mark.parametrize("method,suffix,kwargs", [
    ("get", "", {}), ("post", "/answers/batch", {"json": {"answers": {}}}),
    ("post", "/recommendations", {}), ("get", "/report", {}),
    ("get", "/report", {"params": {"format": "html"}}), ("get", "/fhir", {}),
])
def test_missing_assessment_is_always_404(client, method, suffix, kwargs):
    response = client.request(method, "/v1/assessments/missing" + suffix, headers=DEMO, **kwargs)
    assert_error(response, ASSESSMENT + suffix, method, 404, "NOT_FOUND")


def test_invalid_answers_remain_400(client, service):
    session_id = service.create_session("biotech-sme", "secondary-use-readiness")["assessment_id"]
    response = client.post(f"/v1/assessments/{session_id}/answers/batch", headers=DEMO,
                           json={"answers": {"governance_maturity": 99}})
    assert_error(response, ASSESSMENT + "/answers/batch", "post", 400, "VALIDATION_ERROR")


def test_fastapi_request_validation_remains_422(client):
    response = client.post("/v1/assessments", headers=DEMO, json={})
    assert response.status_code == 422
    schema = main.app.openapi()["paths"]["/v1/assessments"]["post"]["responses"]["422"]["content"]["application/json"]["schema"]
    validate_payload(response.json(), schema)
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("method,suffix,kwargs", [
    ("submit_answers", "/answers/batch", {"json": {"answers": {}}}),
    ("generate_recommendation_async", "/recommendations", {}),
])
def test_session_conflict_matches_documented_409(client, service, monkeypatch, method, suffix, kwargs):
    stub = AsyncMock if method.endswith("_async") else Mock
    monkeypatch.setattr(service, method, stub(side_effect=SessionConflict("session revision changed")))
    response = client.post("/v1/assessments/example" + suffix, headers=DEMO, **kwargs)
    assert_error(response, ASSESSMENT + suffix, "post", 409, "VALIDATION_ERROR")


def test_rate_limit_matches_documented_429(client, monkeypatch):
    monkeypatch.setenv("PATHFINDER_RATE_LIMIT_MAX", "1")
    assert client.get("/v1/questionnaires", headers=DEMO).status_code == 200
    assert_error(client.get("/v1/questionnaires", headers=DEMO),
                 "/v1/questionnaires", "get", 429, "RATE_LIMITED")


def test_database_outage_matches_documented_503(client, service, monkeypatch):
    monkeypatch.setattr(service, "status", Mock(side_effect=psycopg.OperationalError("unavailable")))
    assert_error(client.get("/health"), "/health", "get", 503, "SERVER_ERROR")


@pytest.mark.parametrize("path", ["/v1/roadmap", "/v1/roadmap/{node_id}"])
def test_no_active_generation_matches_documented_503(client, service, monkeypatch, path):
    monkeypatch.setattr(service, "_boundary_store", SimpleNamespace(active_generation_id=lambda: None))
    response = client.get(path.replace("{node_id}", "missing"), headers=DEMO)
    assert_error(response, path, "get", 503, "SERVER_ERROR")

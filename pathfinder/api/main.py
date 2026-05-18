"""FastAPI wrapper for the Pathfinder V1 deterministic kernel.

Supports AGE backend via USE_AGE=1 environment variable.
All response types are locked via Pydantic schemas in api/schemas.py.
Error model: 5 standardized codes (AUTH_REQUIRED, FORBIDDEN, NOT_FOUND,
VALIDATION_ERROR, SERVER_ERROR).
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pathfinder.api.schemas import (
    AdminImportResponse,
    AdminReloadResponse,
    ApiError,
    BatchAnswersRequest,
    CreateAssessmentRequest,
    CreateAssessmentResponse,
    HealthResponse,
    QuestionnaireResponse,
    RecommendationResponse,
    ReportResponse,
    RoadmapNodeResponse,
    RoadmapResponse,
    StakeholderStateResponse,
    StakeholderTypesResponse,
)
from pathfinder.services.assessment_service import AssessmentService

_USE_AGE = os.environ.get("USE_AGE", "").lower() in ("1", "true", "yes")
_service: AssessmentService | None = None


def _get_service() -> AssessmentService:
    global _service
    if _service is None:
        _service = AssessmentService(use_age=_USE_AGE)
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = _get_service()
    if _USE_AGE:
        await service.connect_age()
    yield
    if _USE_AGE:
        await service.disconnect_age()


app = FastAPI(
    title="SCAILED Pathfinder V1",
    version="0.1.0",
    lifespan=lifespan,
    responses={
        401: {"model": ApiError, "description": "Missing or invalid token"},
        403: {"model": ApiError, "description": "Insufficient permissions"},
        404: {"model": ApiError, "description": "Resource not found"},
        400: {"model": ApiError, "description": "Validation error"},
        500: {"model": ApiError, "description": "Internal server error"},
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()
DEMO_TOKEN = os.environ.get("PATHFINDER_DEMO_TOKEN", "demo-token" if ENVIRONMENT != "production" else "")
ADMIN_TOKEN = os.environ.get("PATHFINDER_ADMIN_TOKEN", "admin-token" if ENVIRONMENT != "production" else "")
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("PATHFINDER_RATE_LIMIT_MAX", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("PATHFINDER_RATE_LIMIT_WINDOW_SECONDS", "60"))
_rate_limit_hits: dict[str, tuple[int, float]] = {}


def _auth_error(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=ApiError(error="AUTH_REQUIRED", detail=detail).model_dump())


def _forbidden_error(detail: str) -> HTTPException:
    return HTTPException(status_code=403, detail=ApiError(error="FORBIDDEN", detail=detail).model_dump())


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail=ApiError(error="NOT_FOUND", detail=detail).model_dump())


def _validation_error(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=ApiError(error="VALIDATION_ERROR", detail=detail).model_dump())


def _rate_limited(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": ApiError(error="RATE_LIMITED", detail=detail).model_dump()},
    )


def require_demo_token(authorization: str | None) -> None:
    if authorization not in {f"Bearer {DEMO_TOKEN}", f"Bearer {ADMIN_TOKEN}"}:
        raise _auth_error("invited demo token required")


def require_admin_token(authorization: str | None) -> None:
    if authorization != f"Bearer {ADMIN_TOKEN}":
        raise _forbidden_error("admin token required")


def _audit_context(request: Request) -> dict[str, str | None]:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else None
    if not ip and request.client:
        ip = request.client.host
    return {"ip": ip, "user_agent": request.headers.get("user-agent")}


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    now = time.monotonic()
    authorization = request.headers.get("authorization", "")
    ip = _audit_context(request)["ip"] or "unknown"
    key = f"{authorization}:{ip}"
    count, window_start = _rate_limit_hits.get(key, (0, now))
    if now - window_start >= RATE_LIMIT_WINDOW_SECONDS:
        count = 0
        window_start = now
    count += 1
    _rate_limit_hits[key] = (count, window_start)
    if count > RATE_LIMIT_MAX_REQUESTS:
        return _rate_limited("too many requests")
    return await call_next(request)


# ─── Public ─────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, object]:
    svc = _get_service()
    return {"status": "ok", **svc.status()}


# ─── Questionnaire ──────────────────────────────────────────────────

@app.get("/v1/questionnaires", response_model=StakeholderTypesResponse)
def stakeholder_types(authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    return {"stakeholder_types": svc.stakeholder_types(), "mock_data_mode": True}


@app.get("/v1/questionnaires/{stakeholder_type}", response_model=QuestionnaireResponse)
def questionnaire(stakeholder_type: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    try:
        return svc.get_questionnaire(stakeholder_type)
    except Exception as exc:
        raise _not_found(str(exc)) from exc


# ─── Assessment ─────────────────────────────────────────────────────

@app.post("/v1/assessments", response_model=CreateAssessmentResponse)
async def create_assessment(
    request: Request, authorization: str | None = Header(default=None)
) -> dict[str, object]:
    require_demo_token(authorization)
    body = CreateAssessmentRequest.model_validate(await request.json())
    return _get_service().create_session(
        stakeholder_type=body.stakeholder_type,
        target_scenario=body.target_scenario,
        **_audit_context(request),
    )


@app.get("/v1/assessments/{assessment_id}", response_model=dict[str, object])
def get_assessment(assessment_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    try:
        return svc.sessions[assessment_id]
    except KeyError:
        raise _not_found("assessment not found")


@app.post("/v1/assessments/{assessment_id}/answers/batch", response_model=StakeholderStateResponse)
async def submit_answers(
    assessment_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    require_demo_token(authorization)
    body = BatchAnswersRequest.model_validate(await request.json())
    try:
        return _get_service().submit_answers(assessment_id, body.answers, **_audit_context(request))
    except Exception as exc:
        raise _validation_error(str(exc)) from exc


@app.post("/v1/assessments/{assessment_id}/recommendations", response_model=RecommendationResponse)
def recommendations(
    assessment_id: str, request: Request, authorization: str | None = Header(default=None)
) -> dict[str, object]:
    require_demo_token(authorization)
    try:
        return _get_service().generate_recommendation(assessment_id, **_audit_context(request))
    except Exception as exc:
        raise _validation_error(str(exc)) from exc


@app.get("/v1/assessments/{assessment_id}/report", response_model=ReportResponse)
def report(assessment_id: str, request: Request, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    try:
        return _get_service().report(assessment_id, **_audit_context(request))
    except Exception as exc:
        raise _validation_error(str(exc)) from exc


# ─── Roadmap ────────────────────────────────────────────────────────

@app.get("/v1/roadmap", response_model=RoadmapResponse)
def roadmap(authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    return _get_service().graph.to_dict()


@app.get("/v1/roadmap/{node_id}", response_model=RoadmapNodeResponse)
def roadmap_node(node_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    try:
        return svc.graph.nodes[node_id].to_dict()
    except KeyError:
        raise _not_found("roadmap node not found")


# ─── Admin ──────────────────────────────────────────────────────────

@app.post("/admin/import/wp2", response_model=AdminImportResponse)
async def import_wp2(request: Request, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_admin_token(authorization)
    try:
        report = _get_service().import_wp2(await request.json(), **_audit_context(request))
    except Exception as exc:
        raise _validation_error(str(exc)) from exc
    return {"mode": "demo", "message": "WP2 import activated", **report.to_dict()}


@app.post("/admin/import/wp3", response_model=AdminImportResponse)
async def import_wp3(request: Request, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_admin_token(authorization)
    try:
        report = _get_service().import_wp3(await request.json(), **_audit_context(request))
    except Exception as exc:
        raise _validation_error(str(exc)) from exc
    return {"mode": "demo", "message": "WP3 import activated", **report.to_dict()}


@app.post("/admin/import/wp8", response_model=AdminImportResponse)
async def import_wp8(request: Request, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_admin_token(authorization)
    try:
        report = _get_service().import_wp8(await request.json(), **_audit_context(request))
    except Exception as exc:
        raise _validation_error(str(exc)) from exc
    return {"mode": "demo", "message": "WP8 import activated", **report.to_dict()}


@app.post("/admin/rules/reload", response_model=AdminReloadResponse)
def reload_rules(request: Request, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_admin_token(authorization)
    svc = _get_service()
    svc.audit_log.append("rule_reload", {"rule_version": svc.rule_loader.active_version}, **_audit_context(request))
    return {"accepted": True, "active_rule_version": svc.rule_loader.active_version}

"""FastAPI wrapper for the Pathfinder demo kernel.

Supports AGE backend via USE_AGE=1 environment variable.
Start with: USE_AGE=1 uvicorn pathfinder.api.main:app
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

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


app = FastAPI(title="SCAILED Pathfinder V1", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

DEMO_TOKEN = "demo-token"
ADMIN_TOKEN = "admin-token"


def require_demo_token(authorization: str | None) -> None:
    if authorization not in {f"Bearer {DEMO_TOKEN}", f"Bearer {ADMIN_TOKEN}"}:
        raise HTTPException(status_code=401, detail="invited demo token required")


def require_admin_token(authorization: str | None) -> None:
    if authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(status_code=403, detail="admin token required")


@app.get("/health")
def health() -> dict[str, object]:
    svc = _get_service()
    return {"status": "ok", **svc.status()}


@app.get("/v1/questionnaires")
def stakeholder_types(authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    return {"stakeholder_types": svc.stakeholder_types(), "mock_data_mode": True}


@app.get("/v1/questionnaires/{stakeholder_type}")
def questionnaire(stakeholder_type: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    try:
        return svc.get_questionnaire(stakeholder_type)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/assessments")
async def create_assessment(request: Request, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    payload = await request.json()
    return svc.create_session(
        stakeholder_type=payload["stakeholder_type"],
        target_scenario=payload["target_scenario"],
    )


@app.get("/v1/assessments/{assessment_id}")
def get_assessment(assessment_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    try:
        return svc.sessions[assessment_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="assessment not found") from exc


@app.post("/v1/assessments/{assessment_id}/answers/batch")
async def submit_answers(
    assessment_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    payload: dict[str, Any] = await request.json()
    try:
        return svc.submit_answers(assessment_id, payload["answers"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/assessments/{assessment_id}/recommendations")
def recommendations(assessment_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    try:
        return svc.generate_recommendation(assessment_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/assessments/{assessment_id}/report")
def report(assessment_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    try:
        return svc.report(assessment_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/roadmap")
def roadmap(authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    return svc.graph.to_dict()


@app.get("/v1/roadmap/{node_id}")
def roadmap_node(node_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_demo_token(authorization)
    svc = _get_service()
    try:
        return svc.graph.nodes[node_id].to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="roadmap node not found") from exc


@app.post("/admin/import/wp2")
def import_wp2(authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_admin_token(authorization)
    return {"accepted": True, "mode": "demo", "message": "WP2 import endpoint scaffolded"}


@app.post("/admin/import/wp3")
def import_wp3(authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_admin_token(authorization)
    return {"accepted": True, "mode": "demo", "message": "WP3 import endpoint scaffolded"}


@app.post("/admin/import/wp8")
def import_wp8(authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_admin_token(authorization)
    return {"accepted": True, "mode": "demo", "message": "WP8 import endpoint scaffolded"}


@app.post("/admin/rules/reload")
def reload_rules(authorization: str | None = Header(default=None)) -> dict[str, object]:
    require_admin_token(authorization)
    svc = _get_service()
    svc.audit_log.append("rule_reload", {"rule_version": svc.rule_loader.active_version})
    return {"accepted": True, "active_rule_version": svc.rule_loader.active_version}

"""End-to-end assessment service.

Uses InMemoryRoadmapGraph as the only graph backend.
Data can come from upstream REST services (production) or demo fixtures (local).

This is a synchronous kernel — all async wrappers are retained only for
API backward compatibility and delegate to the synchronous solver.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pathfinder.adapters.demo_data import (
    demo_questionnaires,
)
from pathfinder.adapters.upstream import UpstreamClient
from pathfinder.core.audit import AuditLog
from pathfinder.core.graph import InMemoryRoadmapGraph
from pathfinder.core.imports import import_structured_payload
from pathfinder.core.models import ImportReport, Questionnaire, RoadmapEdge, RoadmapNode
from pathfinder.core.questionnaire import QuestionnaireEngine
from pathfinder.core.recommend import build_recommendation
from pathfinder.core.repositories import audit_repo, session_repo
from pathfinder.core.repositories.bg_loop import run_async
from pathfinder.core.repositories.connection import get_pool as _get_pool
from pathfinder.core.rules.loader import RuleLoader
from pathfinder.core.solver import PathfinderSolver
from pathfinder.fhir.export_service import build_assessment_bundle
from pathfinder.services.derived_readiness import derive_readiness_state


class AssessmentService:
    def __init__(
        self,
        upstream_client: Optional[UpstreamClient] = None,
    ) -> None:
        # ── Data source: upstream client (mock REST) or demo fixtures ──
        if upstream_client is not None:
            self._load_upstream_data(upstream_client)
        else:
            self._load_demo_data()

        # ── Graph backend (always InMemoryRoadmapGraph) ──
        nodes, edges = self._active_roadmap
        self.graph = InMemoryRoadmapGraph(nodes, edges)
        self.solver = PathfinderSolver(self.graph)

    # ── PG persistence helpers (best-effort via background event loop) ──

    def _pg_write_session(self, session: dict) -> None:
        """Persist session to PG via background event loop (best-effort)."""
        if not _get_pool():
            return  # PG pool not initialised
        from datetime import datetime, timezone
        pg = {
            "id": session.get("assessment_id"),
            "stakeholder_type": session.get("stakeholder_type"),
            "status": session.get("status", "in_progress"),
            "answers": session.get("answers"),
            "current_node": None,
            "recommendations": session.get("recommendation"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat()
                if session.get("status") == "complete" else None,
        }
        run_async(session_repo.save_session(_get_pool(), pg), timeout=2.0)

    def _pg_write_audit(self, event: dict) -> None:
        """Persist audit event via background event loop (best-effort)."""
        if not _get_pool():
            return
        run_async(audit_repo.save_audit_event(_get_pool(), event), timeout=2.0)

    def _load_demo_data(self) -> None:
        """Load WP2/WP3/WP8 data from local mock REST services (zero Docker dep).

        Starts an ``UpstreamClient`` pointed at the local mock services
        (started by the VM agent) and reuses ``_load_upstream_data`` so both
        paths converge on exactly the same conversion logic.
        """
        import asyncio
        import threading

        def run_client_coro(coro):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(coro)

            result: dict[str, object] = {}

            def runner() -> None:
                try:
                    result["value"] = asyncio.run(coro)
                except BaseException as exc:  # pragma: no cover - re-raised in caller thread
                    result["error"] = exc

            thread = threading.Thread(target=runner)
            thread.start()
            thread.join()
            if "error" in result:
                raise result["error"]  # type: ignore[misc]
            return result.get("value")

        client = UpstreamClient(
            wp2_url="http://localhost:8102/api/v1",
            wp3_url="http://localhost:8103/api/v1",
            wp8_url="http://localhost:8108/api/v1",
            max_retries=2,
            retry_delay=0.5,
        )
        run_client_coro(client.startup())

        # Inject the 5 demo-compatible stakeholder types so WP3 nodes and WP8
        # rules (which reference biotech-sme etc.) find matching questionnaires.
        _DEMO_TYPES = (
            "biotech-sme",
            "ai-factory-operator",
            "health-data-access-body",
            "health-data-infrastructure",
            "research-infrastructure",
        )
        _existing = {r.get("stakeholder_type", "") for r in client.stakeholders}
        for _st in _DEMO_TYPES:
            if _st not in _existing:
                client.stakeholders.append({
                    "stakeholder_type": _st,
                    "description": _st.replace("-", " ").title(),
                    "capabilities": [],
                    "pain_points": [],
                })

        # Delegate to the same conversion logic as the upstream path.
        self._load_upstream_data(client)

        # Re-key import report from "upstream" → "demo".
        self.import_reports["demo"] = self.import_reports.pop("upstream")

        # Clean up the aiohttp session.
        run_client_coro(client.close())

    def _load_upstream_data(self, client: UpstreamClient) -> None:
        """Load data from UpstreamClient cache (mock REST or real WP services).

        The UpstreamClient has already fetched all data during FastAPI lifespan startup.
        We convert its cached dicts/lists into domain models.
        """
        # WP2: stakeholder records → questionnaires.
        # Use the real upstream stakeholder taxonomy for the selectable types,
        # while reusing the demo question template until WP2 supplies
        # stakeholder-specific questionnaire definitions.
        template = demo_questionnaires()[0]
        self.wp2_stakeholders = {}
        stakeholder_types: list[str] = []
        questionnaires: list[Questionnaire] = []
        seen: set[str] = set()
        warnings: list[str] = []
        skipped_empty = 0
        skipped_duplicate = 0
        for record in client.stakeholders:
            stakeholder_type = str(record.get("stakeholder_type", "")).strip()
            if not stakeholder_type:
                skipped_empty += 1
                continue
            if stakeholder_type in seen:
                skipped_duplicate += 1
                continue
            self.wp2_stakeholders[stakeholder_type] = dict(record)
            seen.add(stakeholder_type)
            stakeholder_types.append(stakeholder_type)
            label = str(record.get("description") or stakeholder_type)
            questionnaires.append(
                Questionnaire(
                    stakeholder_type=stakeholder_type,
                    version=template.version,
                    title=f"EHDS readiness assessment for {label}",
                    target_scenarios=template.target_scenarios,
                    questions=template.questions,
                )
            )
        if skipped_empty:
            warnings.append(f"WP2 upstream skipped {skipped_empty} stakeholder records with empty stakeholder_type")
        if skipped_duplicate:
            warnings.append(f"WP2 upstream skipped {skipped_duplicate} duplicate stakeholder_type records")
        if not questionnaires:
            warnings.append("WP2 upstream produced no usable stakeholder types; demo questionnaire fallback active")
        self.questionnaires = questionnaires or demo_questionnaires()

        # WP3: roadmap nodes + edges → domain models
        nodes = client.roadmap_nodes
        edges = client.roadmap_edges
        self._active_roadmap = (nodes, edges)

        self.questionnaire_engine = QuestionnaireEngine(self.questionnaires)
        self.rule_loader = RuleLoader(self.questionnaires)

        # WP8: rules (already domain models from UpstreamClient) + tests
        self.rules = client.rules
        if self.rules and self.rule_loader.active_version is None:
            self.rule_loader.active_version = self.rules[0].rule_version

        self.audit_log = AuditLog()
        self.sessions: dict[str, dict[str, object]] = {}
        self.import_reports = {
            "upstream": import_structured_payload(
                "upstream",
                {
                    "stakeholder_types": stakeholder_types,
                    "roadmap_nodes": [node.to_dict() for node in nodes],
                    "roadmap_edges": [edge.to_dict() for edge in edges],
                    "rules": [rule.to_dict() for rule in self.rules],
                    "rule_tests_count": len(client.rule_tests),
                    "warnings": warnings,
                },
            )
        }

    def stakeholder_types(self) -> list[str]:
        return self.questionnaire_engine.stakeholder_types()

    def get_questionnaire(self, stakeholder_type: str) -> dict[str, object]:
        return self.questionnaire_engine.get(stakeholder_type).to_dict()

    def create_session(
        self,
        stakeholder_type: str,
        target_scenario: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        stakeholder_type = stakeholder_type.strip()
        target_scenario = target_scenario.strip()
        questionnaire = self.questionnaire_engine.get(stakeholder_type)
        if not target_scenario:
            raise ValueError("target_scenario is required")
        if target_scenario not in questionnaire.target_scenarios:
            raise ValueError(f"unknown target scenario for {stakeholder_type}: {target_scenario}")
        session_id = str(uuid4())
        session = {
            "assessment_id": session_id,
            "stakeholder_type": stakeholder_type,
            "target_scenario": target_scenario,
            "status": "in_progress",
            "mock_data_mode": True,
        }
        self.sessions[session_id] = session
        self.audit_log.append("assessment_session_created", session, ip=ip, user_agent=user_agent)
        self._pg_write_session(session)
        return session

    def submit_answers(
        self,
        assessment_id: str,
        answers: dict[str, object],
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        if assessment_id not in self.sessions:
            raise KeyError(f"Assessment not found: {assessment_id}")
        session = self.sessions[assessment_id]
        state = self.questionnaire_engine.build_state(
            str(session["stakeholder_type"]),
            str(session["target_scenario"]),
            answers,
        )
        session["answers"] = answers
        session["stakeholder_state"] = state.to_dict()
        self.audit_log.append(
            "answers_submitted",
            {"assessment_id": assessment_id, "answer_ids": sorted(answers)},
            ip=ip,
            user_agent=user_agent,
        )
        self._pg_write_session(session)
        return state.to_dict()

    def _snapshot_version(self, key: str) -> str:
        report = self.import_reports.get(key) or self.import_reports.get("upstream") or self.import_reports.get("demo")
        return report.snapshot_version if report else "unknown-snapshot"

    def _derive_state_for_session(self, session: dict[str, object]) -> dict[str, object]:
        stakeholder_type = str(session["stakeholder_type"])
        stakeholder = getattr(self, "wp2_stakeholders", {}).get(stakeholder_type)
        if stakeholder is None:
            raise ValueError(f"WP2 stakeholder record not found: {stakeholder_type}")
        state = derive_readiness_state(
            stakeholder=stakeholder,
            target_scenario=str(session["target_scenario"]),
            wp2_snapshot_version=self._snapshot_version("upstream"),
            wp3_snapshot_version=self._snapshot_version("upstream"),
        )
        payload = state.to_dict()
        payload.update({
            "derivation_mode": "wp2_wp3",
            "pain_points": list(state.answers.get("pain_points", [])),
            "source_wp2_stakeholder_id": state.answers["source_wp2_stakeholder_id"],
            "source_wp2_snapshot_version": state.answers["source_wp2_snapshot_version"],
            "source_wp3_snapshot_version": state.answers["source_wp3_snapshot_version"],
        })
        session["stakeholder_state"] = payload
        session["answers"] = state.answers
        self.audit_log.append(
            "readiness_derived",
            {
                "assessment_id": session["assessment_id"],
                "stakeholder_type": stakeholder_type,
                "derivation_mode": "wp2_wp3",
            },
        )
        return payload

    def _state_for_recommendation(self, session: dict[str, object]) -> object:
        answers = session.get("answers")
        if isinstance(answers, dict) and answers.get("derivation_mode") != "wp2_wp3":
            return self.questionnaire_engine.build_state(
                str(session["stakeholder_type"]),
                str(session["target_scenario"]),
                answers,
            )
        state_payload = session.get("stakeholder_state")
        if not isinstance(state_payload, dict) or state_payload.get("derivation_mode") != "wp2_wp3":
            state_payload = self._derive_state_for_session(session)
        return derive_readiness_state(
            stakeholder=getattr(self, "wp2_stakeholders", {})[str(session["stakeholder_type"])],
            target_scenario=str(session["target_scenario"]),
            wp2_snapshot_version=str(state_payload.get("source_wp2_snapshot_version", "unknown-snapshot")),
            wp3_snapshot_version=str(state_payload.get("source_wp3_snapshot_version", "unknown-snapshot")),
        )

    def generate_recommendation(
        self,
        assessment_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        if assessment_id not in self.sessions:
            raise KeyError(f"Assessment not found: {assessment_id}")
        session = self.sessions[assessment_id]
        state = self._state_for_recommendation(session)
        path = self.solver.solve(state, self.rules)
        recommendation = build_recommendation(path)

        session["recommendation"] = recommendation
        session["status"] = "complete"
        self.audit_log.append(
            "recommendation_generated",
            {"assessment_id": assessment_id, "status": recommendation["status"]},
            ip=ip,
            user_agent=user_agent,
        )
        self._pg_write_session(session)
        return recommendation

    async def generate_recommendation_async(
        self,
        assessment_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
        path_backend: str = "python",
    ) -> dict[str, object]:
        if assessment_id not in self.sessions:
            raise KeyError(f"Assessment not found: {assessment_id}")
        session = self.sessions[assessment_id]
        state = self._state_for_recommendation(session)
        path = self.solver.solve(state, self.rules)
        recommendation = build_recommendation(path)

        session["recommendation"] = recommendation
        session["status"] = "complete"
        self.audit_log.append(
            "recommendation_generated",
            {"assessment_id": assessment_id, "status": recommendation["status"],
             "path_backend": path_backend},
            ip=ip,
            user_agent=user_agent,
        )
        return recommendation

    def _build_report_payload(self, assessment_id: str) -> dict[str, object]:
        if assessment_id not in self.sessions:
            raise KeyError(f"Assessment not found: {assessment_id}. It may have expired after server restart.")
        session = self.sessions[assessment_id]
        if not isinstance(session.get("stakeholder_state"), dict):
            self._derive_state_for_session(session)
        recommendation = session.get("recommendation")
        if not isinstance(recommendation, dict):
            recommendation = self.generate_recommendation(assessment_id)
        return {
            "disclaimer": "Demo/non-production report. Real WP2/WP3/WP8 data may change recommendations.",
            "session": session,
            "readiness_snapshot": session.get("stakeholder_state", {}),
            "recommended_path": recommendation,
            "audit_chain_valid": self.audit_log.verify_chain(),
            "missing_data_warnings": ["mock data mode: partner upstream inputs pending"],
        }

    def report(
        self,
        assessment_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        report = self._build_report_payload(assessment_id)
        self.audit_log.append("report_exported", {"assessment_id": assessment_id}, ip=ip, user_agent=user_agent)
        return report

    def _audit_events_for_assessment(self, assessment_id: str) -> tuple[Any, ...]:
        return tuple(
            event for event in self.audit_log.events()
            if event.event_data.get("assessment_id") == assessment_id
        )

    def export_fhir_bundle(
        self,
        assessment_id: str,
        fhir_version: str = "R4",
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        if assessment_id not in self.sessions:
            raise KeyError(f"Assessment not found: {assessment_id}")
        session = self.sessions[assessment_id]
        if not isinstance(session.get("answers"), dict):
            raise ValueError("answers must be submitted before FHIR export")
        if not isinstance(session.get("recommendation"), dict):
            raise ValueError("recommendation must be generated before FHIR export")

        try:
            report = self._build_report_payload(assessment_id)
            questionnaire = self.get_questionnaire(str(session["stakeholder_type"]))
            bundle = build_assessment_bundle(
                report=report,
                questionnaire=questionnaire,
                audit_events=self._audit_events_for_assessment(assessment_id),
                fhir_version=fhir_version,
            )
        except Exception as exc:
            self.audit_log.append(
                "fhir_export_failed",
                {
                    "assessment_id": assessment_id,
                    "error": str(exc),
                    "fhir_version": fhir_version,
                },
                ip=ip,
                user_agent=user_agent,
            )
            raise

        self.audit_log.append(
            "fhir_bundle_exported",
            {
                "assessment_id": assessment_id,
                "bundle_id": bundle["id"],
                "fhir_version": fhir_version,
            },
            ip=ip,
            user_agent=user_agent,
        )
        return build_assessment_bundle(
            report=report,
            questionnaire=questionnaire,
            audit_events=self._audit_events_for_assessment(assessment_id),
            fhir_version=fhir_version,
        )

    def import_wp2(
        self,
        payload: dict[str, object],
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> ImportReport:
        try:
            questionnaires = self._questionnaires_from_wp2(payload)
            report = import_structured_payload("wp2", payload)
        except Exception as exc:
            self.audit_log.append("data_import_failed", {"source": "wp2", "error": str(exc)}, ip=ip, user_agent=user_agent)
            raise

        self.questionnaires = questionnaires
        self.questionnaire_engine = QuestionnaireEngine(questionnaires)
        loader = RuleLoader(questionnaires)
        loader.active_rules = self.rules
        loader.active_version = self.rule_loader.active_version
        self.rule_loader = loader
        self.import_reports["wp2"] = report
        self.audit_log.append(
            "data_imported",
            {"source": "wp2", "snapshot_version": report.snapshot_version, "activated_records": report.activated_records},
            ip=ip,
            user_agent=user_agent,
        )
        return report

    def import_wp3(
        self,
        payload: dict[str, object],
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> ImportReport:
        try:
            nodes, edges = self._roadmap_from_wp3(payload)
            report = import_structured_payload("wp3", payload)
        except Exception as exc:
            self.audit_log.append("data_import_failed", {"source": "wp3", "error": str(exc)}, ip=ip, user_agent=user_agent)
            raise

        self._active_roadmap = (nodes, edges)
        self.graph = InMemoryRoadmapGraph(nodes, edges)
        self.solver = PathfinderSolver(self.graph)
        self.import_reports["wp3"] = report
        self.audit_log.append(
            "data_imported",
            {"source": "wp3", "snapshot_version": report.snapshot_version, "activated_records": report.activated_records},
            ip=ip,
            user_agent=user_agent,
        )
        return report

    def import_wp8(
        self,
        payload: dict[str, object],
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> ImportReport:
        try:
            loader = RuleLoader(self.questionnaires)
            rules = loader.load_bundle(payload)
            report = import_structured_payload("wp8", payload)
        except Exception as exc:
            self.audit_log.append("data_import_failed", {"source": "wp8", "error": str(exc)}, ip=ip, user_agent=user_agent)
            raise

        self.rule_loader = loader
        self.rules = rules
        self.import_reports["wp8"] = report
        self.audit_log.append(
            "data_imported",
            {"source": "wp8", "snapshot_version": report.snapshot_version, "activated_records": report.activated_records},
            ip=ip,
            user_agent=user_agent,
        )
        return report

    def status(self) -> dict[str, object]:
        return {
            "service": "pathfinder",
            "mode": "demo",
            "graph_backend": "inmemory",
            "stakeholder_types": self.stakeholder_types(),
            "rule_version": self.rule_loader.active_version,
            "audit_events": len(self.audit_log.events()),
            "audit_chain_valid": self.audit_log.verify_chain(),
            "import_reports": {key: report.to_dict() for key, report in self.import_reports.items()},
        }

    def _questionnaires_from_wp2(self, payload: dict[str, object]) -> list[Questionnaire]:
        version = self._required_string(payload, "version")
        stakeholder_types = self._required_list(payload, "stakeholder_types")
        if not stakeholder_types:
            raise ValueError("wp2 stakeholder_types must not be empty")

        template = demo_questionnaires()[0]
        questionnaires: list[Questionnaire] = []
        seen: set[str] = set()
        for raw in stakeholder_types:
            if not isinstance(raw, dict):
                raise ValueError("wp2 stakeholder_types entries must be objects")
            stakeholder_id = self._required_string(raw, "id")
            label = self._required_string(raw, "label")
            self._required_list(raw, "personas")
            self._required_list(raw, "user_journeys")
            if stakeholder_id in seen:
                raise ValueError(f"duplicate stakeholder type: {stakeholder_id}")
            seen.add(stakeholder_id)
            questionnaires.append(
                Questionnaire(
                    stakeholder_type=stakeholder_id,
                    version=f"{version}-questionnaire",
                    title=f"EHDS readiness assessment for {label}",
                    target_scenarios=template.target_scenarios,
                    questions=template.questions,
                )
            )
        return questionnaires

    def _roadmap_from_wp3(self, payload: dict[str, object]) -> tuple[list[RoadmapNode], list[RoadmapEdge]]:
        self._required_string(payload, "version")
        raw_nodes = self._required_list(payload, "nodes")
        raw_edges = self._required_list(payload, "edges")
        if not raw_nodes:
            raise ValueError("wp3 nodes must not be empty")

        nodes: list[RoadmapNode] = []
        seen_nodes: set[str] = set()
        for raw in raw_nodes:
            if not isinstance(raw, dict):
                raise ValueError("wp3 nodes entries must be objects")
            node_id = self._required_string(raw, "node_id")
            if node_id in seen_nodes:
                raise ValueError(f"duplicate roadmap node: {node_id}")
            seen_nodes.add(node_id)
            maturity_level = raw.get("maturity_level")
            if not isinstance(maturity_level, int):
                raise ValueError(f"wp3 node {node_id} maturity_level must be an integer")
            nodes.append(
                RoadmapNode(
                    node_id=node_id,
                    label=self._required_string(raw, "label"),
                    description=str(raw.get("description", "")),
                    dimension=self._required_string(raw, "dimension"),
                    maturity_level=maturity_level,
                    stakeholder_types=tuple(str(value) for value in self._required_list(raw, "stakeholder_types")),
                    prerequisites=tuple(str(value) for value in raw.get("prerequisites", ())),
                    source_doc_ref=str(raw.get("source_doc_ref", "wp3-import")),
                )
            )

        edges: list[RoadmapEdge] = []
        seen_edges: set[str] = set()
        for raw in raw_edges:
            if not isinstance(raw, dict):
                raise ValueError("wp3 edges entries must be objects")
            edge_id = self._required_string(raw, "edge_id")
            from_node_id = self._required_string(raw, "from_node_id")
            to_node_id = self._required_string(raw, "to_node_id")
            if edge_id in seen_edges:
                raise ValueError(f"duplicate roadmap edge: {edge_id}")
            if from_node_id not in seen_nodes or to_node_id not in seen_nodes:
                raise ValueError(f"wp3 edge {edge_id} references unknown node")
            seen_edges.add(edge_id)
            edges.append(
                RoadmapEdge(
                    edge_id=edge_id,
                    from_node_id=from_node_id,
                    to_node_id=to_node_id,
                    relation_type=str(raw.get("relation_type", "prerequisite")),
                    required=bool(raw.get("required", True)),
                    source_doc_ref=str(raw.get("source_doc_ref", "wp3-import")),
                )
            )
        return nodes, edges

    def _required_string(self, payload: dict[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{key} is required")
        return value

    def _required_list(self, payload: dict[str, object], key: str) -> list[object]:
        value = payload.get(key)
        if not isinstance(value, list):
            raise ValueError(f"{key} must be a list")
        return value

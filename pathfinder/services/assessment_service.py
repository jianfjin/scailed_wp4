"""End-to-end demo assessment service.

Supports two graph backends:
  - InMemoryRoadmapGraph (default, zero-config for demos/tests)
  - AgeRoadmapGraph (PostgreSQL + Apache AGE for production)

Set USE_AGE=1 or pass use_age=True to enable the AGE backend.
"""

from __future__ import annotations

import os
from uuid import uuid4

from pathfinder.adapters.demo_data import (
    demo_questionnaires,
    demo_roadmap,
    demo_rule_bundle,
)
from pathfinder.core.audit import AuditLog
from pathfinder.core.graph import InMemoryRoadmapGraph
from pathfinder.core.graph_age import AgeRoadmapGraph
from pathfinder.core.imports import import_structured_payload
from pathfinder.core.models import ImportReport, Questionnaire, RoadmapEdge, RoadmapNode
from pathfinder.core.questionnaire import QuestionnaireEngine
from pathfinder.core.recommend import build_recommendation
from pathfinder.core.rules.loader import RuleLoader
from pathfinder.core.solver import PathfinderSolver


class AssessmentService:
    def __init__(self, use_age: bool | None = None) -> None:
        if use_age is None:
            use_age = os.environ.get("USE_AGE", "").lower() in ("1", "true", "yes")

        self.questionnaires = demo_questionnaires()
        nodes, edges = demo_roadmap()
        self._active_roadmap = (nodes, edges)

        if use_age:
            self.graph = AgeRoadmapGraph()
            self._graph_backend = "age"
        else:
            self.graph = InMemoryRoadmapGraph(nodes, edges)
            self._graph_backend = "inmemory"

        self.questionnaire_engine = QuestionnaireEngine(self.questionnaires)
        self.rule_loader = RuleLoader(self.questionnaires)
        self.rules = self.rule_loader.load_bundle(demo_rule_bundle())
        self.solver = PathfinderSolver(self.graph)
        self.audit_log = AuditLog()
        self.sessions: dict[str, dict[str, object]] = {}
        self.import_reports = {
            "demo": import_structured_payload(
                "demo",
                {
                    "stakeholder_types": self.questionnaire_engine.stakeholder_types(),
                    "roadmap_nodes": [node.to_dict() for node in nodes],
                    "rules": [rule.to_dict() for rule in self.rules],
                    "warnings": ["demo mode: partner WP2/WP3/WP8 inputs not loaded"],
                },
            )
        }

    async def connect_age(self) -> None:
        """Connect to AGE backend and load demo data (async, called once at startup)."""
        if isinstance(self.graph, AgeRoadmapGraph):
            nodes, edges = self._active_roadmap
            await self.graph.connect()
            await self.graph.load_demo_data(nodes, edges)

    async def disconnect_age(self) -> None:
        if isinstance(self.graph, AgeRoadmapGraph):
            await self.graph.disconnect()

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
        return session

    def submit_answers(
        self,
        assessment_id: str,
        answers: dict[str, object],
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
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
        return state.to_dict()

    def generate_recommendation(
        self,
        assessment_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        session = self.sessions[assessment_id]
        answers = session.get("answers")
        if not isinstance(answers, dict):
            raise ValueError("answers must be submitted before recommendation generation")
        state = self.questionnaire_engine.build_state(
            str(session["stakeholder_type"]),
            str(session["target_scenario"]),
            answers,
        )
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
        return recommendation

    def report(
        self,
        assessment_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        session = self.sessions[assessment_id]
        recommendation = session.get("recommendation")
        if not isinstance(recommendation, dict):
            recommendation = self.generate_recommendation(assessment_id)
        report = {
            "disclaimer": "Demo/non-production report. Real WP2/WP3/WP8 data may change recommendations.",
            "session": session,
            "readiness_snapshot": session.get("stakeholder_state", {}),
            "recommended_path": recommendation,
            "audit_chain_valid": self.audit_log.verify_chain(),
            "missing_data_warnings": ["mock data mode: partner upstream inputs pending"],
        }
        self.audit_log.append("report_exported", {"assessment_id": assessment_id}, ip=ip, user_agent=user_agent)
        return report

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
        if isinstance(self.graph, AgeRoadmapGraph):
            self.graph.load_projection(nodes, edges)
        else:
            self.graph = InMemoryRoadmapGraph(nodes, edges)
            self._graph_backend = "inmemory"
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
            "graph_backend": self._graph_backend,
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

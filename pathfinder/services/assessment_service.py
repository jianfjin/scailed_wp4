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
            nodes, edges = demo_roadmap()
            await self.graph.connect()
            await self.graph.load_demo_data(nodes, edges)

    async def disconnect_age(self) -> None:
        if isinstance(self.graph, AgeRoadmapGraph):
            await self.graph.disconnect()

    def stakeholder_types(self) -> list[str]:
        return self.questionnaire_engine.stakeholder_types()

    def get_questionnaire(self, stakeholder_type: str) -> dict[str, object]:
        return self.questionnaire_engine.get(stakeholder_type).to_dict()

    def create_session(self, stakeholder_type: str, target_scenario: str) -> dict[str, object]:
        session_id = str(uuid4())
        session = {
            "assessment_id": session_id,
            "stakeholder_type": stakeholder_type,
            "target_scenario": target_scenario,
            "status": "in_progress",
            "mock_data_mode": True,
        }
        self.sessions[session_id] = session
        self.audit_log.append("assessment_session_created", session)
        return session

    def submit_answers(self, assessment_id: str, answers: dict[str, object]) -> dict[str, object]:
        session = self.sessions[assessment_id]
        state = self.questionnaire_engine.build_state(
            str(session["stakeholder_type"]),
            str(session["target_scenario"]),
            answers,
        )
        session["answers"] = answers
        session["stakeholder_state"] = state.to_dict()
        self.audit_log.append("answers_submitted", {"assessment_id": assessment_id, "answer_ids": sorted(answers)})
        return state.to_dict()

    def generate_recommendation(self, assessment_id: str) -> dict[str, object]:
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
        self.audit_log.append("recommendation_generated", {"assessment_id": assessment_id, "status": recommendation["status"]})
        return recommendation

    def report(self, assessment_id: str) -> dict[str, object]:
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
        self.audit_log.append("report_exported", {"assessment_id": assessment_id})
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

"""End-to-end assessment service.

Uses InMemoryRoadmapGraph as the only graph backend.
Data can come from upstream REST services (production) or demo fixtures (local).

This is a synchronous kernel — all async wrappers are retained only for
API backward compatibility and delegate to the synchronous solver.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from collections import OrderedDict
import logging
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
from threading import RLock
from datetime import datetime, timezone, date

from pathfinder.adapters.demo_data import (
    demo_questionnaires,
)
from pathfinder.adapters.upstream import UpstreamClient
from pathfinder.core.audit import AuditLog
from pathfinder.core.graph import InMemoryRoadmapGraph
from pathfinder.core.imports import import_structured_payload
from pathfinder.core.models import ImportReport, Questionnaire, RoadmapEdge, RoadmapNode, StakeholderState
from pathfinder.core.contract_registry import LEGACY_PROFILE, EVIDENCE_PROFILE, PROFILES
from pathfinder.core.boundary_lifecycle import dependency_closure, identity, runtime_input_set, observe_validity
from pathfinder.core.boundary_validation import canonical_checksum, validate_withdrawal_notice
from pathfinder.core.repositories.boundary_store import SessionConflict, InputsWithdrawn, NoticeConflict
from pathfinder.core.questionnaire import QuestionnaireEngine
from pathfinder.core.recommend import build_recommendation
from pathfinder.core.repositories import audit_repo, session_repo
from pathfinder.core.repositories.bg_loop import run_async
from pathfinder.core.repositories.connection import get_pool as _get_pool
from pathfinder.core.rules.loader import RuleLoader
from pathfinder.core.solver import PathfinderSolver
from pathfinder.fhir.export_service import build_assessment_bundle
from pathfinder.services.derived_readiness import derive_readiness_state

logger = logging.getLogger(__name__)


class AssessmentService:
    def __init__(
        self,
        upstream_client: Optional[UpstreamClient] = None,
        boundary_store=None,
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
        self._active_boundary = None
        self._boundary_store = boundary_store
        self._generation_cache = OrderedDict()
        self._boundary_lock = RLock()
        self._session_boundaries = {}
        self._boundary_snapshot_hashes = {}
        self._active_boundaries = {}
        self._boundary_documents = {}
        self._result_records = {}
        self._memory_revisions = {}
        self._withdrawals = {}
        self._lifecycle_revision = 0

    def _generation(self, generation_id, snapshots=None):
        from pathfinder.core.boundary_runtime import build_boundary_generation
        with self._boundary_lock:
            generation = self._generation_cache.get(generation_id)
            if generation is None:
                generation = build_boundary_generation(snapshots if snapshots is not None else self._boundary_store.load_generation(generation_id))
                self._generation_cache[generation_id] = generation
                if len(self._generation_cache) > 32:
                    self._generation_cache.popitem(last=False)
            else:
                self._generation_cache.move_to_end(generation_id)
            return generation

    def _active_generation(self, profile_id=LEGACY_PROFILE.profile_id):
        if profile_id not in PROFILES:
            raise ValueError("unsupported evaluation profile")
        if not self._boundary_store:
            return None, self._active_boundaries.get(profile_id)
        generation_id = self._boundary_store.active_generation_id(profile_id)
        if not generation_id:
            return None, None
        return generation_id, self._generation(generation_id)

    @property
    def active_boundary(self):
        return self._active_generation()[1]

    def activate_boundary_snapshots(self, snapshots, ip=None, user_agent=None):
        from pathfinder.core.boundary_runtime import build_boundary_generation

        snapshots = deepcopy(snapshots)
        try:
            generation = build_boundary_generation(snapshots)
        except (ValueError, TypeError, KeyError):
            if self._boundary_store:
                self._boundary_store.append_event("boundary_snapshots_rejected", {"reason": "validation failed"}, ip, user_agent)
            else:
                self.audit_log.append("boundary_snapshots_rejected", {"reason": "validation failed"}, ip=ip, user_agent=user_agent)
            raise
        if generation.profile_id == EVIDENCE_PROFILE.profile_id and os.getenv('ENVIRONMENT', 'development').lower() == 'production' and not os.getenv('PATHFINDER_SEMANTIC_V2_APPROVAL_REF', '').strip():
            raise ValueError('semantic_approval_required: record affected-WP RFC and consumer readiness before production activation')
        if self._boundary_store:
            try:
                generation_id = self._boundary_store.activate(snapshots, generation, ip, user_agent)
            except ValueError:
                self._boundary_store.append_event("boundary_snapshots_rejected", {"reason": "snapshot identity reused"}, ip, user_agent)
                raise
            with self._boundary_lock:
                self._generation_cache[generation_id] = generation
                if len(self._generation_cache) > 32:
                    self._generation_cache.popitem(last=False)
            return {"accepted": True, "generation_id": generation_id, "snapshot_ids": dict(generation.snapshot_ids),
                    "questionnaire_ids": dict(generation.questionnaire_ids), "regulatory_status": generation.regulatory_status,
                    "warnings": list(generation.warnings)}
        with self._boundary_lock:
            self._require_valid_inputs(dependency_closure(snapshots, [identity(doc) for doc in snapshots]))
            for doc in snapshots:
                self._check_memory_target(identity(doc))
            for snapshot_id, digest in generation.snapshot_hashes.items():
                existing = self._boundary_snapshot_hashes.get(snapshot_id)
                if existing is not None and existing != digest:
                    self.audit_log.append("boundary_snapshots_rejected", {"reason": "snapshot identity reused", "snapshot_id": snapshot_id}, ip=ip, user_agent=user_agent)
                    raise ValueError(f"snapshot_id {snapshot_id} was already used for different content")
            self.audit_log.append("boundary_snapshots_activated", {
                "snapshot_ids": dict(generation.snapshot_ids),
                "questionnaire_ids": dict(generation.questionnaire_ids),
                "regulatory_status": generation.regulatory_status,
            }, ip=ip, user_agent=user_agent)
            self._boundary_snapshot_hashes.update(generation.snapshot_hashes)
            self._active_boundary = generation
            self._active_boundaries[generation.profile_id] = generation
            self._boundary_documents[id(generation)] = snapshots
        return {"accepted": True, "snapshot_ids": dict(generation.snapshot_ids),
                "questionnaire_ids": dict(generation.questionnaire_ids),
                "regulatory_status": generation.regulatory_status, "warnings": list(generation.warnings)}

    def _check_memory_target(self, target):
        known = [identity(doc) for docs in self._boundary_documents.values() for doc in docs]
        known += [item for notice in self._withdrawals.values() for item in notice['payload']['targets']]
        expected = {key: target[key] for key in ('contract', 'snapshot_id', 'producer_wp')}
        if any(item['snapshot_id'] == target['snapshot_id'] and item != expected for item in known):
            raise ValueError('snapshot target identity conflicts with contract or producer')

    def withdraw_inputs(self, notice, actor, ip=None, user_agent=None):
        errors = validate_withdrawal_notice(notice)
        if errors:
            raise ValueError('invalid withdrawal notice: ' + '; '.join(errors))
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError('authenticated administrator identity is required')
        if self._boundary_store:
            return self._boundary_store.withdraw(notice, actor, ip, user_agent)
        notice = deepcopy(notice)
        notice_id = notice['payload']['notice_id']
        with self._boundary_lock:
            previous = self._withdrawals.get(notice_id)
            if previous is not None:
                if canonical_checksum(previous) != canonical_checksum(notice):
                    raise NoticeConflict('withdrawal notice identity was already used for different content')
                return {'accepted': True, 'created': False, 'notice_id': notice_id,
                        'lifecycle_revision': self._lifecycle_revision}
            for target in notice['payload']['targets']:
                self._check_memory_target(target)
            self.audit_log.append('boundary_inputs_withdrawn', {'notice_id': notice_id, 'actor': actor,
                'targets': notice['payload']['targets'], 'source_confirmation': notice['payload']['source_confirmation']}, ip=ip, user_agent=user_agent)
            self._withdrawals[notice_id] = notice
            self._lifecycle_revision += 1
            return {'accepted': True, 'created': True, 'notice_id': notice_id,
                    'lifecycle_revision': self._lifecycle_revision}

    def _boundary_for_session(self, session):
        if self._boundary_store and session.get("boundary_generation_id"):
            return self._generation(session["boundary_generation_id"])
        return self._session_boundaries.get(str(session["assessment_id"]))

    def _load_session(self, assessment_id):
        if self._boundary_store:
            stored = self._boundary_store.load_session(assessment_id)
            if stored is None:
                raise KeyError(f"Assessment not found: {assessment_id}")
            session, revision, generation_id = stored
            if session.get("boundary_generation_id") != generation_id:
                raise ValueError("session generation binding is inconsistent")
            return session, revision
        if assessment_id not in self.sessions:
            raise KeyError(f"Assessment not found: {assessment_id}")
        with self._boundary_lock:
            return deepcopy(self.sessions[assessment_id]), self._memory_revisions.get(assessment_id, 0)

    def get_session(self, assessment_id):
        return self._load_session(assessment_id)[0]

    def audit_event_count(self):
        return self._boundary_store.audit_count() if self._boundary_store else len(self.audit_log.events())

    # ── PG persistence helpers (best-effort via background event loop) ──

    def _schedule_pg_write(self, coro: object, label: str) -> None:
        """Run optional PG persistence without failing the assessment flow."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                run_async(coro, timeout=2.0)
            except Exception as exc:  # pragma: no cover - logged best-effort path
                logger.warning("Failed to persist %s to PostgreSQL: %s", label, exc)
            return

        task = loop.create_task(coro)  # type: ignore[arg-type]

        def log_failure(done: asyncio.Task[object]) -> None:
            try:
                done.result()
            except Exception as exc:  # pragma: no cover - callback exercised in deployed async loop
                logger.warning("Failed to persist %s to PostgreSQL: %s", label, exc)

        task.add_done_callback(log_failure)

    def _pg_write_session(self, session: dict) -> None:
        """Persist session to PG best-effort; in-memory state remains authoritative."""
        pool = _get_pool()
        if not pool:
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
        self._schedule_pg_write(session_repo.save_session(pool, pg), "assessment session")

    def _pg_write_audit(self, event: dict) -> None:
        """Persist audit event best-effort; in-memory audit remains authoritative."""
        pool = _get_pool()
        if not pool:
            return
        self._schedule_pg_write(audit_repo.save_audit_event(pool, event), "audit event")

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

    def stakeholder_types(self, profile_id=LEGACY_PROFILE.profile_id) -> list[str]:
        generation = self._active_generation(profile_id)[1]
        if generation is None and (self._boundary_store or profile_id != LEGACY_PROFILE.profile_id):
            return []
        return (generation.questionnaire_engine if generation else self.questionnaire_engine).stakeholder_types()

    def get_questionnaire(self, stakeholder_type: str, profile_id=LEGACY_PROFILE.profile_id) -> dict[str, object]:
        generation = self._active_generation(profile_id)[1]
        if generation is None and (self._boundary_store or profile_id != LEGACY_PROFILE.profile_id):
            raise ValueError("no validated boundary generation is active for this profile")
        return (generation.questionnaire_engine if generation else self.questionnaire_engine).get(stakeholder_type).to_dict()

    def _input_set(self, session):
        generation = self._boundary_for_session(session)
        if generation is None:
            return []
        documents = (self._boundary_store.load_generation(session['boundary_generation_id'])
                     if self._boundary_store else self._boundary_documents[id(generation)])
        return runtime_input_set(documents, session['stakeholder_type'])

    def current_validity(self, input_set):
        if self._boundary_store:
            return self._boundary_store.current_validity(input_set)
        with self._boundary_lock:
            return observe_validity(input_set, self._withdrawals.values(), self._lifecycle_revision)

    def _require_valid_inputs(self, input_set):
        observation = self.current_validity(input_set)
        if not observation['valid']:
            raise InputsWithdrawn(observation)
        return observation

    def create_session(
        self, stakeholder_type: str, target_scenario: str,
        ip: str | None = None, user_agent: str | None = None,
        profile_id=LEGACY_PROFILE.profile_id,
    ) -> dict[str, object]:
        stakeholder_type, target_scenario = stakeholder_type.strip(), target_scenario.strip()
        generation_id, generation = self._active_generation(profile_id)
        if generation is None and (self._boundary_store or profile_id != LEGACY_PROFILE.profile_id):
            raise ValueError("no validated boundary generation is active for this profile")
        questionnaire = (generation.questionnaire_engine if generation else self.questionnaire_engine).get(stakeholder_type)
        if not target_scenario or target_scenario not in questionnaire.target_scenarios:
            raise ValueError(f"unknown target scenario for {stakeholder_type}: {target_scenario}")
        session_id = str(uuid4())
        session = {"assessment_id": session_id, "stakeholder_type": stakeholder_type,
                   "target_scenario": target_scenario, "status": "in_progress",
                   "mock_data_mode": generation is None, "profile_id": profile_id,
                   "semantics_version": PROFILES[profile_id].semantics_version, "answer_revision": 0}
        if generation:
            session["snapshot_ids"] = generation.versions_for(stakeholder_type)
            session["evaluation_date"] = datetime.now(timezone.utc).date().isoformat()
            if self._boundary_store:
                session["boundary_generation_id"] = generation_id
                self._boundary_store.create_session(session, generation_id, ip, user_agent)
                return deepcopy(session)
        with self._boundary_lock:
            if generation:
                inputs = runtime_input_set(self._boundary_documents[id(generation)], stakeholder_type)
                self._require_valid_inputs(inputs)
                self._session_boundaries[session_id] = generation
            self.audit_log.append("assessment_session_created", session, ip=ip, user_agent=user_agent)
            self.sessions[session_id] = deepcopy(session)
            self._memory_revisions[session_id] = 0
        self._pg_write_session(session)
        return deepcopy(session)

    def _save_session(self, session, revision, event_type, event_data, ip=None, user_agent=None):
        if self._boundary_store:
            self._boundary_store.save_session(session, revision, event_type, event_data, ip, user_agent)
            return
        with self._boundary_lock:
            aid = session['assessment_id']
            if self._memory_revisions.get(aid, 0) != revision:
                raise SessionConflict("assessment session changed concurrently; reload and retry")
            self.audit_log.append(event_type, event_data, ip=ip, user_agent=user_agent)
            self.sessions[aid] = deepcopy(session)
            self._memory_revisions[aid] = revision + 1
        self._pg_write_session(session)

    def submit_answers(
        self,
        assessment_id: str,
        answers: dict[str, object],
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        session, revision = self._load_session(assessment_id)
        generation = self._boundary_for_session(session)
        state = (generation.questionnaire_engine if generation else self.questionnaire_engine).build_state(
            str(session["stakeholder_type"]),
            str(session["target_scenario"]),
            answers,
        )
        if session.get('answers') != answers:
            session['answer_revision'] = session.get('answer_revision', 0) + 1
            session.pop('recommendation', None)
            session.pop('result_id', None)
            session['status'] = 'in_progress'
        session['answers'] = deepcopy(answers)
        session['stakeholder_state'] = state.to_dict()
        self._save_session(session, revision, 'answers_submitted',
                           {'assessment_id': assessment_id, 'answer_ids': sorted(answers),
                            'answer_revision': session.get('answer_revision', 0)}, ip, user_agent)
        return state.to_dict()

    def _snapshot_version(self, source: str) -> str:
        report = (
            self.import_reports.get(source)
            or self.import_reports.get("upstream")
            or self.import_reports.get("demo")
        )
        return report.snapshot_version if report else "unknown-snapshot"

    def _derive_state_for_session(self, session: dict[str, object]) -> dict[str, object]:
        if session.get("profile_id") == EVIDENCE_PROFILE.profile_id or os.getenv("PATHFINDER_MODE", "demo") != "demo":
            raise ValueError("type capabilities are reference only; submit current questionnaire answers")
        stakeholder_type = str(session["stakeholder_type"])
        stakeholder = getattr(self, "wp2_stakeholders", {}).get(stakeholder_type)
        if stakeholder is None:
            raise ValueError(f"WP2 stakeholder record not found: {stakeholder_type}")
        state = derive_readiness_state(
            stakeholder=stakeholder,
            target_scenario=str(session["target_scenario"]),
            wp2_snapshot_version=self._snapshot_version("wp2"),
            wp3_snapshot_version=self._snapshot_version("wp3"),
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

    def _state_from_stored_payload(self, payload: dict[str, object]) -> StakeholderState:
        def string_tuple(key: str) -> tuple[str, ...]:
            value = payload.get(key, ())
            if isinstance(value, (list, tuple)):
                return tuple(str(item) for item in value)
            return ()

        maturity_scores = payload.get("maturity_scores", {})
        if not isinstance(maturity_scores, dict):
            maturity_scores = {}

        answers = payload.get("answers", {})
        if not isinstance(answers, dict):
            answers = {}

        return StakeholderState(
            stakeholder_type=str(payload.get("stakeholder_type", "")),
            target_scenario=str(payload.get("target_scenario", "")),
            answers=dict(answers),
            maturity_scores={str(key): int(value) for key, value in maturity_scores.items()},
            capabilities=string_tuple("capabilities"),
            missing_capabilities=string_tuple("missing_capabilities"),
            regulatory_flags=string_tuple("regulatory_flags"),
            confidence=float(payload.get("confidence", 0.0)),
            confidence_warnings=string_tuple("confidence_warnings"),
            questionnaire_version=str(payload.get("questionnaire_version", "")),
            schema_version=str(payload.get("schema_version", "")),
            upstream_snapshot_version=str(payload.get("upstream_snapshot_version", "")),
        )

    def _state_for_recommendation(self, session: dict[str, object]) -> StakeholderState:
        answers = session.get("answers")
        generation = self._boundary_for_session(session)
        if generation and not isinstance(answers, dict):
            raise ValueError("submit questionnaire answers before requesting a boundary recommendation")
        if isinstance(answers, dict) and answers.get("derivation_mode") != "wp2_wp3":
            return (generation.questionnaire_engine if generation else self.questionnaire_engine).build_state(
                str(session["stakeholder_type"]),
                str(session["target_scenario"]),
                answers,
            )
        state_payload = session.get("stakeholder_state")
        if not isinstance(state_payload, dict) or state_payload.get("derivation_mode") != "wp2_wp3":
            state_payload = self._derive_state_for_session(session)
        return self._state_from_stored_payload(state_payload)

    def _recommend_for_session(self, session, state):
        generation = self._boundary_for_session(session)
        if not generation:
            return build_recommendation(self.solver.solve(state, self.rules))
        evaluation_date = date.fromisoformat(session["evaluation_date"])
        rules, incomplete = generation.rules_for(evaluation_date)
        recommendation = build_recommendation(generation.solver.solve(state, rules))
        status = "unverified" if incomplete else generation.regulatory_status
        recommendation["regulatory_status"] = status
        recommendation["warnings"].extend(generation.warnings)
        if incomplete:
            recommendation["warnings"].append("Some rules are outside their effective dates; regulatory coverage is unverified.")
        recommendation["trace"]["snapshot_ids"] = generation.versions_for(str(session["stakeholder_type"]))
        recommendation["trace"]["evaluation_date"] = evaluation_date.isoformat()
        if session.get("boundary_generation_id"):
            recommendation["trace"]["boundary_generation_id"] = session["boundary_generation_id"]
        recommendation["trace"]["rule_version"] = generation.snapshot_ids[generation.rulebundle_contract]
        recommendation["trace"]["upstream_snapshot_version"] = generation.snapshot_ids["pf.taxonomy.v1"]
        if status == "unverified" and recommendation["status"] == "ready":
            recommendation["status"] = "degraded"
        return recommendation

    def generate_recommendation(
        self,
        assessment_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, object]:
        session, revision = self._load_session(assessment_id)
        inputs = self._input_set(session)
        self._require_valid_inputs(inputs)
        state = self._state_for_recommendation(session)
        recommendation = self._recommend_for_session(session, state)
        if session.get('profile_id') == EVIDENCE_PROFILE.profile_id:
            recommendation['capability_findings'] = state.to_dict()['capability_findings']
        record = {
            'result_id': str(uuid4()), 'assessment_id': assessment_id,
            'answer_revision': session.get('answer_revision', 0), 'answers': deepcopy(session.get('answers')),
            'findings': deepcopy(state.to_dict().get('capability_findings', {})),
            'readiness_snapshot': state.to_dict(), 'input_set': inputs,
            'profile_id': session.get('profile_id', LEGACY_PROFILE.profile_id),
            'semantics_version': session.get('semantics_version', LEGACY_PROFILE.semantics_version),
            'evaluation_date': session.get('evaluation_date', datetime.now(timezone.utc).date().isoformat()),
            'binding_status': 'bound', 'original_output': deepcopy(recommendation),
            'content_hash': canonical_checksum(recommendation),
        }
        session['recommendation'] = deepcopy(recommendation)
        session['result_id'] = record['result_id']
        session['status'] = 'complete'
        session['stakeholder_state'] = state.to_dict()
        if self._boundary_store:
            self._boundary_store.publish_result(session, revision, record, ip, user_agent)
        else:
            with self._boundary_lock:
                current = self.sessions[assessment_id]
                if self._memory_revisions.get(assessment_id, 0) != revision or current.get('answer_revision', 0) != record['answer_revision']:
                    raise SessionConflict('assessment answers changed during evaluation')
                self._require_valid_inputs(inputs)
                self.audit_log.append('recommendation_generated',
                    {'assessment_id': assessment_id, 'status': recommendation['status'],
                     'result_id': record['result_id'], 'answer_revision': record['answer_revision']}, ip=ip, user_agent=user_agent)
                self._result_records[record['result_id']] = deepcopy(record)
                self.sessions[assessment_id] = deepcopy(session)
                self._memory_revisions[assessment_id] = revision + 1
            self._pg_write_session(session)
        return self._result_projection(record, self.current_validity(inputs))

    @staticmethod
    def _result_projection(record, observation):
        result = deepcopy(record['original_output'])
        result.update({key: record[key] for key in ('result_id', 'answer_revision', 'profile_id', 'semantics_version', 'content_hash') if key in record})
        result['current_validity'] = observation
        return result

    def _result_record(self, session, result_id=None):
        if self._boundary_store:
            record = self._boundary_store.load_result(session['assessment_id'], result_id)
        else:
            record = self._result_records.get(result_id or session.get('result_id'))
        if record is not None and record['assessment_id'] != session['assessment_id']:
            record = None
        if result_id and record is None:
            raise KeyError('result not found for assessment')
        if result_id is None and record is not None and record['answer_revision'] != session.get('answer_revision', 0):
            record = None
        return deepcopy(record)

    async def generate_recommendation_async(
        self,
        assessment_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
        path_backend: str = "python",
    ) -> dict[str, object]:
        return await asyncio.to_thread(self.generate_recommendation, assessment_id, ip, user_agent)

    def _build_report_payload(self, assessment_id: str, result_id=None) -> dict[str, object]:
        session, _ = self._load_session(assessment_id)
        record = self._result_record(session, result_id)
        if record is None:
            if session.get('profile_id') == EVIDENCE_PROFILE.profile_id:
                raise ValueError('recommendation_required: generate a result for the current answers')
            self.generate_recommendation(assessment_id)
            session, _ = self._load_session(assessment_id)
            record = self._result_record(session)
        observation = self.current_validity(record['input_set'])
        historical_session = deepcopy(session)
        historical_session['answers'] = deepcopy(record['answers'])
        historical_session['answer_revision'] = record['answer_revision']
        historical_session['result_id'] = record['result_id']
        historical_session['recommendation'] = deepcopy(record['original_output'])
        historical_session['stakeholder_state'] = deepcopy(record.get('readiness_snapshot', {}))
        generation = self._boundary_for_session(session)
        return {
            'disclaimer': 'Guidance is not a legal conclusion.' if generation else 'Demo/non-production report. Real WP2/WP3/WP8 data may change recommendations.',
            'session': historical_session, 'readiness_snapshot': record.get('readiness_snapshot', {}),
            'recommended_path': self._result_projection(record, observation), 'result': record,
            'current_validity': observation,
            'audit_chain_valid': self._boundary_store.verify_audit_chain() if self._boundary_store else self.audit_log.verify_chain(),
            'missing_data_warnings': list(generation.warnings) if generation else ['mock data mode: partner upstream inputs pending'],
        }

    def report(self, assessment_id: str, ip: str | None = None, user_agent: str | None = None, result_id=None) -> dict[str, object]:
        report = self._build_report_payload(assessment_id, result_id)
        if self._boundary_store:
            self._boundary_store.append_event('report_exported', {'assessment_id': assessment_id}, ip, user_agent)
        else:
            self.audit_log.append('report_exported', {'assessment_id': assessment_id}, ip=ip, user_agent=user_agent)
        return report

    def _audit_events_for_assessment(self, assessment_id: str) -> tuple[Any, ...]:
        if self._boundary_store:
            return tuple(self._boundary_store.events_for_assessment(assessment_id))
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
        session, _ = self._load_session(assessment_id)
        if not isinstance(session.get("answers"), dict):
            raise ValueError("answers must be submitted before FHIR export")
        if not isinstance(session.get("recommendation"), dict):
            raise ValueError("recommendation must be generated before FHIR export")

        try:
            report = self._build_report_payload(assessment_id)
            generation = self._boundary_for_session(session)
            questionnaire = (generation.questionnaire_engine.get(str(session["stakeholder_type"])).to_dict()
                             if generation else self.get_questionnaire(str(session["stakeholder_type"])))
            bundle = build_assessment_bundle(
                report=report,
                questionnaire=questionnaire,
                audit_events=self._audit_events_for_assessment(assessment_id),
                fhir_version=fhir_version,
            )
        except Exception as exc:
            event = {"assessment_id": assessment_id, "error": str(exc), "fhir_version": fhir_version}
            if self._boundary_store:
                self._boundary_store.append_event("fhir_export_failed", event, ip, user_agent)
            else:
                self.audit_log.append("fhir_export_failed", event, ip=ip, user_agent=user_agent)
            raise

        event = {"assessment_id": assessment_id, "bundle_id": bundle["id"], "fhir_version": fhir_version}
        if self._boundary_store:
            self._boundary_store.append_event("fhir_bundle_exported", event, ip, user_agent)
        else:
            self.audit_log.append("fhir_bundle_exported", event, ip=ip, user_agent=user_agent)
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
        if self._boundary_store:
            raise ValueError("legacy imports are disabled in PostgreSQL boundary mode; use /v1/admin/import")
        try:
            questionnaires = self._questionnaires_from_wp2(payload)
            stakeholders = self._stakeholders_from_wp2(payload)
            report = import_structured_payload("wp2", payload)
            report = replace(report, snapshot_version=self._required_string(payload, "version"))
        except Exception as exc:
            self.audit_log.append("data_import_failed", {"source": "wp2", "error": str(exc)}, ip=ip, user_agent=user_agent)
            raise

        self.questionnaires = questionnaires
        self.wp2_stakeholders = stakeholders
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
        if self._boundary_store:
            raise ValueError("legacy imports are disabled in PostgreSQL boundary mode; use /v1/admin/import")
        try:
            nodes, edges = self._roadmap_from_wp3(payload)
            report = import_structured_payload("wp3", payload)
            report = replace(report, snapshot_version=self._required_string(payload, "version"))
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
        if self._boundary_store:
            raise ValueError("legacy imports are disabled in PostgreSQL boundary mode; use /v1/admin/import")
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
        generation = self.active_boundary
        return {
            "service": "pathfinder",
            "mode": "deployed" if self._boundary_store else "demo",
            "graph_backend": "inmemory",
            "stakeholder_types": self.stakeholder_types(),
            "rule_version": generation.snapshot_ids[generation.rulebundle_contract] if generation else self.rule_loader.active_version,
            "audit_events": self._boundary_store.audit_count() if self._boundary_store else len(self.audit_log.events()),
            "audit_chain_valid": self._boundary_store.verify_audit_chain() if self._boundary_store else self.audit_log.verify_chain(),
            "import_reports": {key: report.to_dict() for key, report in self.import_reports.items()},
            "active_snapshot_ids": dict(generation.snapshot_ids) if generation else {},
            "regulatory_status": generation.regulatory_status if generation else "unverified",
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

    def _stakeholders_from_wp2(self, payload: dict[str, object]) -> dict[str, dict[str, object]]:
        self._required_string(payload, "version")
        stakeholder_types = self._required_list(payload, "stakeholder_types")
        if not stakeholder_types:
            raise ValueError("wp2 stakeholder_types must not be empty")

        stakeholders: dict[str, dict[str, object]] = {}
        for raw in stakeholder_types:
            if not isinstance(raw, dict):
                raise ValueError("wp2 stakeholder_types entries must be objects")
            stakeholder_id = self._required_string(raw, "id")
            label = self._required_string(raw, "label")
            self._required_list(raw, "personas")
            self._required_list(raw, "user_journeys")
            if stakeholder_id in stakeholders:
                raise ValueError(f"duplicate stakeholder type: {stakeholder_id}")
            stakeholders[stakeholder_id] = {
                "stakeholder_type": stakeholder_id,
                "description": label,
                "capabilities": self._optional_string_list(raw, "capabilities"),
                "pain_points": self._optional_string_list(raw, "pain_points"),
            }
        return stakeholders

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

    def _optional_string_list(self, payload: dict[str, object], key: str) -> list[str]:
        value = payload.get(key, [])
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"{key} must be a list")
        return [str(item) for item in value if str(item).strip()]

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

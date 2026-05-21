"""OpenSpec 2.2 — NetworkX fallback tests.

Verifies that when AGE backend is unavailable, the system
degrades gracefully to NetworkX with explicit markers:
  - path_backend = "networkx_fallback"
  - confidence = 0.0
  - health status has degraded=True

Joint resolution 15/0 (Linus plan): degradation markers, not silent failure.
"""

from __future__ import annotations

import os

import pytest

from pathfinder.services.assessment_service import AssessmentService


class TestNetworkXFallback:
    """OpenSpec 2.2: NetworkX fallback when AGE is unavailable."""

    def test_fallback_triggers_when_age_unavailable(self, monkeypatch) -> None:
        """When deployed mode and AGE connect fails, fallback activates."""
        monkeypatch.setenv("PATHFINDER_MODE", "deployed")

        # Force AGE connect to fail with unreachable host
        monkeypatch.setenv("PGHOST", "255.255.255.255")
        monkeypatch.setenv("PGPORT", "1")

        # startup_check=True triggers the fallback (OpenSpec 2.2)
        svc = AssessmentService(startup_check=True)

        assert svc._age_unavailable is True, "fallback should trigger"
        assert svc._graph_backend == "networkx_fallback", (
            f"expected networkx_fallback, got {svc._graph_backend}"
        )

        # Status must expose degradation
        status = svc.status()
        assert status.get("degraded") is True, (
            f"status should have degraded=True: {status}"
        )
        assert "fallback" in str(status.get("degraded_reason", "")).lower(), (
            f"status.degraded_reason should mention fallback: {status}"
        )

    def test_fallback_produces_valid_recommendation(self, monkeypatch) -> None:
        """Fallback path still produces a recommendation with zero confidence."""
        monkeypatch.setenv("PATHFINDER_MODE", "deployed")
        monkeypatch.setenv("PGHOST", "255.255.255.255")
        monkeypatch.setenv("PGPORT", "1")

        svc = AssessmentService(startup_check=True)

        # Import demo data and run pipeline
        svc.import_wp2({
            "version": "test-fallback",
            "stakeholder_types": [{
                "id": "biotech-sme", "label": "Biotech SME",
                "personas": ["researcher"],
                "user_journeys": ["test"],
                "feedback_categories": ["acceptance"],
            }],
        })

        # Create assessment
        session = svc.create_session("biotech-sme", "secondary-use-readiness")
        aid = session["assessment_id"]

        # Submit answers
        svc.submit_answers(aid, {
            "governance_maturity": 2, "data_maturity": 2,
            "compliance_maturity": 2, "capabilities": ["secure-processing"],
            "missing_capabilities": [], "regulatory_flags": [],
        })

        # Get recommendation
        rec = svc.generate_recommendation(aid)

        # Degradation markers must be present
        assert rec.get("confidence") == 0.0, (
            f"fallback confidence should be 0.0, got {rec.get('confidence')}"
        )
        assert rec.get("path_backend") == "networkx_fallback", (
            f"fallback backend should be networkx_fallback, got {rec.get('path_backend')}"
        )
        warnings = rec.get("warnings", [])
        assert any("DEGRADED" in str(w) for w in warnings), (
            f"fallback should add DEGRADED warning: {warnings}"
        )

        # Recommendation should still have a status (not crash)
        assert rec.get("status") is not None, (
            f"fallback recommendation should have status: {rec}"
        )

    def test_demo_mode_does_not_degrade(self) -> None:
        """Demo mode should use inmemory without degradation markers."""
        svc = AssessmentService(startup_check=False)
        assert svc._age_unavailable is False
        assert svc._graph_backend == "inmemory"
        status = svc.status()
        assert status.get("degraded") is not True, (
            f"demo mode should not be degraded: {status}"
        )

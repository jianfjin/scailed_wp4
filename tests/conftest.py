"""Pytest fixtures for Pathfinder tests.

Module-level global to control AssessmentService startup_check behavior.
When running tests, no real PostgreSQL connection should be attempted.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import unittest.mock

# ── patch AssessmentService.__init__ so startup_check defaults to False ──

_original_init: Callable[..., None] | None = None


def pytest_configure(config: object) -> None:
    """Apply startup_check=False patch before any test module is imported."""
    global _original_init

    from pathfinder.services.assessment_service import AssessmentService

    _original_init = AssessmentService.__init__

    def patched_init(self: Any, use_age: bool | None = None, startup_check: bool = False, **kwargs: Any) -> None:
        # Force startup_check=False for all tests.
        _original_init(self, use_age=use_age, startup_check=False, **kwargs)  # type: ignore[misc]

    AssessmentService.__init__ = patched_init


def pytest_unconfigure(config: object) -> None:
    """Restore original AssessmentService.__init__ after tests."""
    global _original_init
    if _original_init is not None:
        from pathfinder.services.assessment_service import AssessmentService

        AssessmentService.__init__ = _original_init
        _original_init = None

"""Pytest fixtures for Pathfinder tests."""

from __future__ import annotations

import os


def pytest_configure(config: object) -> None:
    """Default tests to zero-config demo mode unless a test overrides it."""
    os.environ.setdefault("PATHFINDER_MODE", "demo")


def pytest_unconfigure(config: object) -> None:
    """No fixture cleanup required."""

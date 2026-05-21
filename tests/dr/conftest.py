"""Pytest fixtures for DR (Disaster Recovery) verification tests.

Tests validate the 4-layer verification pipeline:
  V1: sha256 file integrity
  V2: pg_restore schema recovery
  V3: AGE catalog consistency
  V4: total row count

Requires: PostgreSQL container (scailed-postgres) running, /backups/pg/ exists.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# ─── Constants ─────────────────────────────────────────────────────────
BACKUP_ROOT = Path("/backups/pg")
PG_CONTAINER = os.environ.get("SCAILED_PG_CONTAINER", "scailed-postgres")
PG_USER = os.environ.get("SCAILED_PG_USER", "pathfinder")
PG_DB = os.environ.get("SCAILED_PG_DB", "pathfinder")


def _docker_exec(cmd: str) -> str:
    """Run a command inside the PostgreSQL container."""
    result = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "bash", "-c", cmd],
        capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip()


def _psql(query: str) -> str:
    """Run a psql query inside the container."""
    # Escape single quotes in query for bash -c
    escaped = query.replace("'", "'\"'\"'")
    return _docker_exec(f"psql -U {PG_USER} -d {PG_DB} -t -A -c '{escaped}'")


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def pg_container_running() -> bool:
    """Verify PostgreSQL container is running. Skip all DR tests if not."""
    result = subprocess.run(
        ["docker", "inspect", "--format={{.State.Running}}", PG_CONTAINER],
        capture_output=True, text=True, timeout=5,
    )
    if result.stdout.strip() != "true":
        pytest.skip(f"Container {PG_CONTAINER} not running")
    return True


@pytest.fixture(scope="session")
def pg_version(pg_container_running: bool) -> str:
    """Get PostgreSQL version string."""
    return _psql("SELECT version()")


@pytest.fixture(scope="session")
def pg_table_count(pg_container_running: bool) -> int:
    """Count user tables (excludes system schemas)."""
    result = _psql(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_type='BASE TABLE' "
        "AND table_schema NOT IN ('pg_catalog','information_schema')"
    )
    return int(result) if result else 0


@pytest.fixture(scope="session")
def pg_age_stats(pg_container_running: bool) -> dict:
    """Extract live AGE graph/label stats for comparison."""
    graphs = _psql("SELECT count(*) FROM ag_catalog.ag_graph")
    labels = _psql("SELECT count(*) FROM ag_catalog.ag_label")
    return {"graphs": int(graphs), "labels": int(labels)}


@pytest.fixture(scope="session")
def pg_total_rows(pg_container_running: bool) -> int:
    """Total rows across user tables (ANALYZE first)."""
    _psql("ANALYZE")
    result = _psql(
        "SELECT COALESCE(sum(n_live_tup), 0) FROM pg_stat_user_tables "
        "WHERE schemaname NOT IN ('pg_catalog','information_schema')"
    )
    return int(result) if result else 0


@pytest.fixture
def backup_dir() -> Path:
    """Find the latest backup (symlinked)."""
    latest = BACKUP_ROOT / "latest"
    if not latest.exists():
        pytest.skip("No backup found — run deploy/backup.sh first")
    return latest.resolve()


@pytest.fixture
def catalog_json(backup_dir: Path) -> dict:
    """Load the AGE catalog JSON from the latest backup."""
    catalogs = sorted(backup_dir.glob("pathfinder_*_catalog.json"))
    if not catalogs:
        pytest.skip("No catalog.json in backup")
    with open(catalogs[-1]) as f:
        return json.load(f)


@pytest.fixture
def checksum_file(backup_dir: Path) -> Path:
    """Path to checksums.sha256 in the latest backup."""
    cf = backup_dir / "checksums.sha256"
    if not cf.exists():
        pytest.skip("No checksums.sha256 in backup")
    return cf


@pytest.fixture
def dump_file(backup_dir: Path) -> Path:
    """Path to the .dump file in the latest backup."""
    dumps = sorted(backup_dir.glob("pathfinder_*.dump"))
    if not dumps:
        pytest.skip("No .dump file in backup")
    return dumps[-1]


@pytest.fixture
def schema_file(backup_dir: Path) -> Path:
    """Path to the schema-only .sql file in the latest backup."""
    schemas = sorted(backup_dir.glob("pathfinder_*_schema.sql"))
    if not schemas:
        pytest.skip("No schema.sql in backup")
    return schemas[-1]

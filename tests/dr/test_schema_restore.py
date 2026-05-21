"""V2: Schema restore verification.

Creates a temp database from the dump, restores schema-only,
and verifies table count matches the live database.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PG_CONTAINER = "scailed-postgres"
PG_USER = "pathfinder"


def _docker_exec(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", PG_CONTAINER, "bash", "-c", cmd],
        capture_output=True, text=True, timeout=15,
    )


class TestSchemaRestore:
    """V2 — pg_restore --schema-only to temp database."""

    @pytest.fixture(autouse=True)
    def cleanup_temp_db(self) -> None:
        """Ensure verify_restore DB is cleaned up before and after."""
        _docker_exec(
            f"dropdb --if-exists -U {PG_USER} verify_restore 2>/dev/null"
        )
        yield
        _docker_exec(
            f"dropdb --if-exists -U {PG_USER} verify_restore 2>/dev/null"
        )
        _docker_exec("rm -f /tmp/verify_test.dump 2>/dev/null")

    def test_schema_restore_creates_tables(
        self, dump_file: Path, pg_table_count: int
    ) -> None:
        """Restoring schema from dump should create same number of tables."""
        # Copy dump into container
        subprocess.run(
            ["docker", "cp", str(dump_file),
             f"{PG_CONTAINER}:/tmp/verify_test.dump"],
            capture_output=True, timeout=10, check=True,
        )

        # Create temp DB and restore schema
        r = _docker_exec(
            f"createdb -U {PG_USER} verify_restore 2>/dev/null && "
            f"pg_restore -U {PG_USER} -d verify_restore --schema-only "
            f"/tmp/verify_test.dump 2>&1"
        )
        assert r.returncode == 0, f"pg_restore failed: {r.stderr}"

        # Count restored tables
        r2 = _docker_exec(
            f"psql -U {PG_USER} -d verify_restore -t -A -c "
            f"\"SELECT count(*) FROM information_schema.tables "
            f"WHERE table_type='BASE TABLE' "
            f"AND table_schema NOT IN ('pg_catalog','information_schema')\""
        )
        restored_count = int(r2.stdout.strip())
        assert restored_count == pg_table_count, (
            f"Table count mismatch: restored={restored_count}, "
            f"live={pg_table_count}"
        )

    def test_schema_restore_no_errors(self, dump_file: Path) -> None:
        """pg_restore must not produce ERROR-level output."""
        subprocess.run(
            ["docker", "cp", str(dump_file),
             f"{PG_CONTAINER}:/tmp/verify_test.dump"],
            capture_output=True, timeout=10, check=True,
        )

        _docker_exec(
            f"createdb -U {PG_USER} verify_restore 2>/dev/null"
        )
        r = _docker_exec(
            f"pg_restore -U {PG_USER} -d verify_restore --schema-only "
            f"/tmp/verify_test.dump 2>&1"
        )
        # pg_restore may produce NOTICE/WARNING but not ERROR
        for line in r.stderr.split("\n"):
            line_upper = line.upper()
            if "ERROR:" in line_upper and "0 errors" not in line_upper:
                pytest.fail(f"pg_restore produced ERROR: {line}")

        assert r.returncode == 0

    def test_dump_is_restorable(self, dump_file: Path) -> None:
        """Dump file must be non-empty and have pg_dump custom format header."""
        # Custom format starts with "PGDMP"
        header = dump_file.read_bytes()[:5]
        assert header == b"PGDMP", (
            f"Not a valid pg_dump custom format: {header}"
        )

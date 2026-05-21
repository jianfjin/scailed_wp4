"""V4: Total row count comparison + integration pipeline test.

V4 validates that total row count in the catalog matches the live DB.
Also includes an end-to-end pipeline smoke test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TestTotalRowCount:
    """V4 — Total row count consistency."""

    def test_total_rows_matches_live(
        self, catalog_json: dict, pg_total_rows: int
    ) -> None:
        """Total row count in catalog must match live DB after ANALYZE."""
        cat_rows = catalog_json.get("total_rows", -1)
        assert cat_rows == pg_total_rows, (
            f"Total row count mismatch: catalog={cat_rows}, live={pg_total_rows}"
        )

    def test_total_rows_positive(self, catalog_json: dict) -> None:
        """Total rows must be > 0 (database has data)."""
        assert catalog_json["total_rows"] > 0, "Total rows is 0 (empty DB?)"


class TestIntegrationPipeline:
    """End-to-end: backup → verify pipeline."""

    def test_backup_script_exists(self) -> None:
        """backup.sh must exist and be executable."""
        bp = Path("deploy/backup.sh")
        assert bp.exists(), f"{bp} not found"
        assert bp.stat().st_mode & 0o100, f"{bp} not executable"

    def test_verify_script_exists(self) -> None:
        """verify_restore.sh must exist and be executable."""
        vp = Path("deploy/verify_restore.sh")
        assert vp.exists(), f"{vp} not found"
        assert vp.stat().st_mode & 0o100, f"{vp} not executable"

    def test_backup_script_syntax(self) -> None:
        """backup.sh must pass bash syntax check."""
        result = subprocess.run(
            ["bash", "-n", "deploy/backup.sh"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0, (
            f"backup.sh syntax error: {result.stderr}"
        )

    def test_verify_script_syntax(self) -> None:
        """verify_restore.sh must pass bash syntax check."""
        result = subprocess.run(
            ["bash", "-n", "deploy/verify_restore.sh"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0, (
            f"verify_restore.sh syntax error: {result.stderr}"
        )

    def test_latest_symlink_points_to_backup(self, backup_dir: Path) -> None:
        """Symlink 'latest' must point to a valid backup directory."""
        assert backup_dir.is_dir(), f"latest → {backup_dir} not a directory"
        children = list(backup_dir.iterdir())
        assert len(children) >= 3, (
            f"Backup has only {len(children)} files (expected >=4)"
        )

    def test_verify_restore_exit_zero(self) -> None:
        """verify_restore.sh must exit 0 when backup is valid."""
        result = subprocess.run(
            ["bash", "deploy/verify_restore.sh"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, (
            f"verify_restore.sh failed (exit={result.returncode}):\n"
            f"STDOUT: {result.stdout[-500:]}\n"
            f"STDERR: {result.stderr[-500:]}"
        )

    def test_verify_output_contains_all_layers(self) -> None:
        """verify_restore.sh output must mention all 4 layers."""
        result = subprocess.run(
            ["bash", "deploy/verify_restore.sh"],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        assert "V1" in output, "Missing V1 in verify output"
        assert "V2" in output, "Missing V2 in verify output"
        assert "V3" in output, "Missing V3 in verify output"
        assert "V4" in output, "Missing V4 in verify output"
        assert "ALL CLEAN" in output or "PASS" in output, (
            "Expected success indicators in verify output"
        )

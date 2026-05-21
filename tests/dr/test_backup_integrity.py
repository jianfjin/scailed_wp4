"""V1: sha256 file integrity verification.

Validates that backup files match their recorded checksums.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest


class TestChecksumVerification:
    """V1 — File integrity via sha256."""

    def test_checksum_file_exists(self, checksum_file: Path) -> None:
        """checksums.sha256 must exist in the backup directory."""
        assert checksum_file.exists(), f"Missing {checksum_file}"
        assert checksum_file.stat().st_size > 0, "checksums.sha256 is empty"

    def test_checksum_file_has_entries(self, checksum_file: Path) -> None:
        """checksums.sha256 must contain hash entries."""
        content = checksum_file.read_text()
        assert content.strip(), "checksums.sha256 is empty"
        lines = [l for l in content.strip().split("\n") if l.strip()]
        assert len(lines) >= 3, f"Expected >=3 entries, got {len(lines)}"

    def test_sha256sum_check_passes(
        self, backup_dir: Path, checksum_file: Path
    ) -> None:
        """sha256sum -c must verify all files in backup."""
        result = subprocess.run(
            ["sha256sum", "-c", str(checksum_file.name), "--quiet"],
            capture_output=True, text=True, timeout=5,
            cwd=str(backup_dir),
        )
        assert result.returncode == 0, (
            f"sha256sum -c failed (exit={result.returncode}): {result.stderr}"
        )

    def test_dump_file_present(self, dump_file: Path) -> None:
        """Backup must contain a .dump file."""
        assert dump_file.exists()
        assert dump_file.stat().st_size > 1000, (
            f"dump too small: {dump_file.stat().st_size} bytes"
        )

    def test_schema_file_present(self, schema_file: Path) -> None:
        """Backup must contain a schema-only .sql file."""
        assert schema_file.exists()
        assert schema_file.stat().st_size > 500, (
            f"schema file too small: {schema_file.stat().st_size} bytes"
        )

    def test_known_hash_integrity(
        self, dump_file: Path, checksum_file: Path
    ) -> None:
        """Cross-check: manual sha256 of dump matches recorded checksum."""
        recorded_hashes = {}
        for line in checksum_file.read_text().strip().split("\n"):
            if not line.strip():
                continue
            h, _, path = line.strip().partition("  ")
            recorded_hashes[Path(path).name] = h

        computed = hashlib.sha256(dump_file.read_bytes()).hexdigest()
        fname = dump_file.name
        assert fname in recorded_hashes, f"{fname} not in checksums"
        assert computed == recorded_hashes[fname], (
            f"sha256 mismatch for {fname}: computed={computed[:16]}..., "
            f"expected={recorded_hashes[fname][:16]}..."
        )

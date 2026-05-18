#!/usr/bin/env python3
"""Verify OpenSpec tasks.md checkboxes against D4.1 acceptance tests.

Usage: python3 scripts/verify_tasks.py [--strict]

Scans tasks.md for [x] checkboxes with (test: module.Class.method) annotations,
runs the corresponding tests, and reports which checkboxes pass/fail.

Exit codes:
  0 — all annotated checkboxes pass or no annotations found
  1 — one or more annotated checkboxes fail
  2 — tasks.md not found or parse error
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_MD = PROJECT_ROOT / "openspec" / "changes" / "add-merged-pathfinder-v1" / "tasks.md"


def parse_checkboxes(path: Path) -> list[tuple[int, str, str | None]]:
    """Extract (line_no, checkbox_text, test_id) from tasks.md."""
    items: list[tuple[int, str, str | None]] = []
    if not path.exists():
        print(f"[ERROR] tasks.md not found at {path}")
        sys.exit(2)

    with open(path) as f:
        for i, line in enumerate(f, 1):
            m = re.match(r"\s*- \[x\]\s+(.+)", line)
            if not m:
                continue
            text = m.group(1).strip()
            test_id = None
            tm = re.search(r"\(test:\s*([^\s)]+)\)", text)
            if tm:
                test_id = tm.group(1)
                text = re.sub(r"\s*\(test:\s*[^\s)]+\)", "", text).strip()
            items.append((i, text, test_id))
    return items


def run_test(test_id: str) -> tuple[bool, str]:
    """Run a single pytest test and return (passed, output_summary)."""
    # Convert module.Class.method → path::Class::method
    parts = test_id.split(".")
    if len(parts) < 2:
        return False, f"invalid test_id format: {test_id}"

    # Build pytest nodeid: module.py::ClassName::method_name
    module = parts[0]
    rest = "::".join(parts[1:])
    nodeid = f"tests/{module}.py::{rest}"

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", nodeid, "-q", "--tb=no", "--no-header"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        passed = result.returncode == 0
        output = result.stdout.strip().split("\n")[-1] if result.stdout else result.stderr.strip()
        return passed, output
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)


def main(
    argv: list[str] | None = None,
    tasks_path: Path | None = None,
    test_runner: "callable | None" = None,
) -> int:
    """Run verify_tasks. Returns exit code (0=pass, 1=fail, 2=parse error).

    Args:
        argv: Command-line arguments (defaults to sys.argv).
        tasks_path: Override tasks.md path for testing.
        test_runner: Override test runner function for testing
            (takes test_id str, returns (passed: bool, output: str)).
    """
    if argv is None:
        argv = sys.argv
    strict = "--strict" in argv

    path = tasks_path if tasks_path is not None else TASKS_MD
    items = parse_checkboxes(path)

    _runner = test_runner if test_runner is not None else run_test

    checked = [it for it in items if it[2] is not None]
    unchecked = [it for it in items if it[2] is None]

    print(f"tasks.md: {len(items)} checked items ({len(checked)} with test annotations, {len(unchecked)} without)\n")

    if not checked:
        print("No test-annotated checkboxes found.")
        # strict: only fail when there are checked ([x]) items without test annotations
        checked_without_annotation = [it for it in items if it[2] is None]
        if strict and checked_without_annotation:
            print(f"\n[FAIL] Strict mode: {len(checked_without_annotation)} checked items have no test annotation.")
            for line_no, text, _ in checked_without_annotation:
                print(f"  L{line_no}: {text[:80]}")
            return 1
        print("Nothing to verify. Non-strict mode — informational only.")
        if unchecked:
            print(f"\n{len(unchecked)} checked items have no test mapping:")
            for line_no, text, _ in unchecked:
                print(f"  L{line_no}: {text[:80]}")
        return 0

    passed = 0
    failed = 0
    for line_no, text, test_id in checked:
        assert test_id is not None
        ok, output = _runner(test_id)
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] L{line_no}: {text[:70]}")
        print(f"         test: {test_id}  →  {output}")

    print(f"\nResult: {passed} passed, {failed} failed, {len(unchecked)} unverified (no test annotation)")

    if unchecked:
        print("\nUnverified items (no test ID annotation):")
        for line_no, text, _ in unchecked:
            print(f"  L{line_no}: {text[:80]}")

    if failed > 0:
        print("\n[FAIL] Some annotated checkboxes do not pass their acceptance tests.")
        return 1

    if unchecked and strict:
        print("\n[FAIL] Strict mode: unverified items exist.")
        return 1

    print("\n[OK] All annotated checkboxes pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

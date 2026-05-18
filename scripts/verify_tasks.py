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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_MD = PROJECT_ROOT / "openspec" / "changes" / "add-merged-pathfinder-v1" / "tasks.md"


@dataclass(frozen=True)
class TaskItem:
    line_no: int
    checked: bool
    text: str
    test_id: str | None


TestRunner = Callable[[str], tuple[bool, str]]


def parse_checkboxes(path: Path) -> list[TaskItem]:
    """Extract checkbox items from tasks.md."""
    items: list[TaskItem] = []
    if not path.exists():
        raise FileNotFoundError(f"tasks.md not found at {path}")

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            m = re.match(r"\s*- \[([ xX])\]\s+(.+)", line)
            if not m:
                continue
            checked = m.group(1).lower() == "x"
            text = m.group(2).strip()
            test_id = None
            tm = re.search(r"\(test:\s*([^\s)]+)\)", text)
            if tm:
                test_id = tm.group(1)
                text = re.sub(r"\s*\(test:\s*[^\s)]+\)", "", text).strip()
            items.append(TaskItem(i, checked, text, test_id))
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
    tasks_path: Path = TASKS_MD,
    test_runner: TestRunner = run_test,
) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    strict = "--strict" in argv
    try:
        items = parse_checkboxes(tasks_path)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 2

    checked_items = [item for item in items if item.checked]
    checked_with_tests = [item for item in checked_items if item.test_id is not None]
    checked_without_tests = [item for item in checked_items if item.test_id is None]
    unchecked_without_tests = [item for item in items if not item.checked and item.test_id is None]

    print(
        f"tasks.md: {len(checked_items)} checked items "
        f"({len(checked_with_tests)} with test annotations, {len(checked_without_tests)} without)\n"
    )

    passed = 0
    failed = 0
    for item in checked_with_tests:
        assert item.test_id is not None
        ok, output = test_runner(item.test_id)
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] L{item.line_no}: {item.text[:70]}")
        print(f"         test: {item.test_id}  →  {output}")

    print(
        f"\nResult: {passed} passed, {failed} failed, "
        f"{len(checked_without_tests)} checked unverified, "
        f"{len(unchecked_without_tests)} unchecked informational"
    )

    if checked_without_tests:
        print("\nChecked items without test ID annotation:")
        for item in checked_without_tests:
            print(f"  L{item.line_no}: {item.text[:80]}")

    if unchecked_without_tests:
        print("\nUnchecked items without test mapping (informational only):")
        for item in unchecked_without_tests:
            print(f"  L{item.line_no}: {item.text[:80]}")

    if failed > 0:
        print("\n[FAIL] Some annotated checkboxes do not pass their acceptance tests.")
        return 1

    if checked_without_tests and strict:
        print("\n[FAIL] Strict mode: checked items without test annotations exist.")
        return 1

    print("\n[OK] All annotated checkboxes pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

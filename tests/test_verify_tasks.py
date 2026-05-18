from pathlib import Path

from scripts import verify_tasks


def _write_tasks(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "tasks.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_strict_fails_checked_item_without_test_annotation(tmp_path: Path) -> None:
    path = _write_tasks(tmp_path, "- [x] Implement the thing\n")

    exit_code = verify_tasks.main(["--strict"], tasks_path=path, test_runner=lambda _: (True, "ok"))

    assert exit_code == 1


def test_strict_passes_checked_item_with_passing_test(tmp_path: Path) -> None:
    path = _write_tasks(tmp_path, "- [x] Implement the thing (test: test_module.test_name)\n")

    exit_code = verify_tasks.main(["--strict"], tasks_path=path, test_runner=lambda _: (True, "ok"))

    assert exit_code == 0


def test_strict_fails_checked_item_with_failing_test(tmp_path: Path) -> None:
    path = _write_tasks(tmp_path, "- [x] Implement the thing (test: test_module.test_name)\n")

    exit_code = verify_tasks.main(["--strict"], tasks_path=path, test_runner=lambda _: (False, "failed"))

    assert exit_code == 1


def test_strict_ignores_unchecked_item_without_test_annotation(tmp_path: Path) -> None:
    path = _write_tasks(tmp_path, "- [ ] Implement the thing\n")

    exit_code = verify_tasks.main(["--strict"], tasks_path=path, test_runner=lambda _: (True, "ok"))

    assert exit_code == 0

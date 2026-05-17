"""Parse JSON/YAML rule bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pathfinder.core.exceptions import RuleValidationError


def parse_rule_bundle(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() == ".json":
        return json.loads(text)
    if file_path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise RuleValidationError("YAML rule parsing requires PyYAML") from exc
        return yaml.safe_load(text)
    raise RuleValidationError(f"unsupported rule file type: {file_path.suffix}")

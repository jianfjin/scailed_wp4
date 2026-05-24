"""Rule bundle validation — schema-driven + semantic checks.

Loads schema.json as the structural source of truth (condition DSL, action fields,
rule shape), then applies semantic rules (duplicate IDs) that cannot be expressed
in JSON Schema.

Conflict resolution between overlapping conditions is handled at runtime by
priority ordering (see ComplianceEvaluator.triggered_rules).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pathfinder.core.exceptions import RuleValidationError

_SCHEMA_PATH = Path(__file__).parent / "schema.json"


def _load_schema() -> dict[str, Any]:
    """Load the canonical rule bundle JSON Schema."""
    try:
        return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise RuleValidationError(f"cannot load rule schema: {exc}") from exc


def validate_rule_bundle(bundle: dict[str, Any]) -> None:
    """Validate a rule bundle using schema.json + semantic checks.

    Steps:
      1. Load schema.json (fail fast if missing/corrupt).
      2. Run jsonschema validation against the bundle (covers structure,
         condition DSL, action shape, required fields, types, enums).
      3. Semantic check: no duplicate rule_id.

    Raises RuleValidationError on first failure.
    """
    # ── Step 1: load schema (cached) ────────────────────────────────
    import jsonschema

    schema = _load_schema()

    # ── Step 2: JSON Schema structural validation ───────────────────
    try:
        jsonschema.validate(instance=bundle, schema=schema)
    except jsonschema.ValidationError as exc:
        path = " → ".join(str(p) for p in exc.absolute_path) if exc.absolute_path else "(root)"
        raise RuleValidationError(
            f"schema validation failed at {path}: {exc.message}"
        ) from exc

    # ── Step 3: semantic check — duplicate rule_id ──────────────────
    rules: list[dict[str, Any]] = bundle.get("rules", [])
    seen: set[str] = set()
    for raw_rule in rules:
        rule_id: str = raw_rule["rule_id"]
        if rule_id in seen:
            raise RuleValidationError(f"duplicate rule_id: {rule_id}")
        seen.add(rule_id)

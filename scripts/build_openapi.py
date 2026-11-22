#!/usr/bin/env python3
"""Export the same enriched contract served at /openapi.json.

Run python3 scripts/build_openapi.py, then scripts/build_swagger_ui.py.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs/18_pathfinder_openapi.json"
OUT_YAML = ROOT / "docs/18_pathfinder_openapi.yaml"


def build() -> dict:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from pathfinder.api.main import app

    return copy.deepcopy(app.openapi())


def _render_yaml(spec: dict) -> str | None:
    try:
        import yaml
    except ImportError:
        return None
    return yaml.safe_dump(spec, sort_keys=False, width=110, allow_unicode=True)


def main(check: bool = False) -> None:
    spec = build()
    rendered = json.dumps(spec, indent=2) + "\n"
    if check:
        if OUT_JSON.read_text() != rendered:
            print(f"DRIFT: {OUT_JSON.name} is stale - run: python3 scripts/build_openapi.py")
            raise SystemExit(1)
        y = _render_yaml(spec)
        if y is not None and OUT_YAML.exists() and OUT_YAML.read_text() != y:
            print(f"DRIFT: {OUT_YAML.name} is stale - run: python3 scripts/build_openapi.py")
            raise SystemExit(1)
        print("openapi contract up to date")
        return
    OUT_JSON.write_text(rendered)
    print(f"wrote {OUT_JSON.name} ({OUT_JSON.stat().st_size//1024} KB)")
    out_yaml = OUT_YAML
    try:
        import yaml
        out_yaml.write_text(yaml.safe_dump(spec, sort_keys=False, width=110, allow_unicode=True))
        print(f"wrote {out_yaml.name} ({out_yaml.stat().st_size//1024} KB)")
    except ImportError:
        print("pyyaml unavailable - JSON only")


if __name__ == "__main__":
    main(check="--check" in sys.argv[1:])

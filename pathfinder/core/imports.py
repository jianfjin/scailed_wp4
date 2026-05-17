"""Structured data import helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pathfinder.core.models import ImportReport


def import_structured_payload(source: str, payload: dict[str, Any]) -> ImportReport:
    raw = json.dumps(payload, sort_keys=True)
    checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    records = sum(1 for value in payload.values() if isinstance(value, list) for _ in value)
    warnings = tuple(payload.get("warnings", ()))
    return ImportReport(
        source=source,
        accepted=True,
        checksum=checksum,
        snapshot_version=f"{source.lower()}-{checksum[:12]}",
        warnings=warnings,
        activated_records=records,
    )

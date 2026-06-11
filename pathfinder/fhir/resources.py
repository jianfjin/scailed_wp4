"""Small FHIR R4 resource helpers used by Pathfinder export mappers."""

from __future__ import annotations

import re
from typing import Any

PATHFINDER_SYSTEM = "https://scailed.eu/fhir/pathfinder"


def fhir_id(*parts: object) -> str:
    raw = "-".join(str(part) for part in parts if str(part).strip())
    lowered = raw.strip().lower()
    safe = re.sub(r"[^a-z0-9.-]+", "-", lowered)
    safe = re.sub(r"-+", "-", safe).strip("-")
    if not safe:
        raise ValueError("FHIR id parts must produce a non-empty id")
    return safe[:64]


def reference(resource_type: str, resource_id: str) -> dict[str, str]:
    return {"reference": f"{resource_type}/{resource_id}"}


def coding(code: str, display: str | None = None, system: str = PATHFINDER_SYSTEM) -> dict[str, str]:
    value = {"system": system, "code": code}
    if display is not None:
        value["display"] = display
    return value


def codeable_concept(code: str, display: str | None = None, system: str = PATHFINDER_SYSTEM) -> dict[str, Any]:
    concept: dict[str, Any] = {"coding": [coding(code, display, system)]}
    if display is not None:
        concept["text"] = display
    return concept


def bundle_entry(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "fullUrl": f"urn:uuid:{resource['resourceType']}/{resource['id']}",
        "resource": resource,
    }


def create_bundle(bundle_id: str, resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "entry": [bundle_entry(resource) for resource in resources],
    }


def require_r4(fhir_version: str) -> None:
    if fhir_version.upper() != "R4":
        raise ValueError(f"unsupported FHIR version: {fhir_version}")

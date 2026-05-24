"""Async upstream client for WP2/WP3/WP8 services (mock or real).

Uses aiohttp.ClientSession for non-blocking HTTP fetches.
Startup-time fetch + in-memory cache — deterministic within a single backend session.

Environment variables (with Docker Compose defaults):
  WP2_API_URL=http://wp2-mock:8080/api/v1
  WP3_API_URL=http://wp3-mock:8080/api/v1
  WP8_API_URL=http://wp8-mock:8080/api/v1

Switch to real consortium APIs by changing env vars — zero code change.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import aiohttp

from pathfinder.core.models import (
    RoadmapEdge,
    RoadmapNode,
    Rule,
    RuleAction,
    RuleType,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Schema Normalization Layer (Council Resolution 2026-05-20, 5/5 vote)
#
# Each WP can deliver data in multiple schema versions.  The normalizer
# mapping translates raw field names into the canonical names that the
# domain-model constructors expect.
#
# To add a new schema version:
#   1. Add a mapping dict under the version key below.
#   2. The key is the RAW field name, the value is the CANONICAL name.
#   3. Fields NOT listed are passed through unchanged with a warning.
#   4. Unknown schema_version → ValueError at startup (fail fast).
# ═══════════════════════════════════════════════════════════════════════

# ── WP2: Stakeholder Taxonomy ────────────────────────────────────────

_WP2_NORMALIZERS: dict[str, dict[str, str]] = {
    "v1": {
        "stakeholder_type": "stakeholder_type",
        "description":      "description",
        "capabilities":     "capabilities",
        "pain_points":      "pain_points",
    },
    # CHARITE WP2 real-data schema (predicted — Council analysis §2)
    "charite_v1": {
        "id":               "stakeholder_type",
        "label":            "description",
        "capabilities":     "capabilities",
        "pain_points":      "pain_points",
    },
}

# ── WP3: Roadmap Nodes / Edges ───────────────────────────────────────

_WP3_NODE_NORMALIZERS: dict[str, dict[str, str]] = {
    "v1": {
        "node_id":           "node_id",
        "label":             "label",
        "description":       "description",
        "dimension":         "dimension",
        "maturity_level":    "maturity_level",
        "stakeholder_types": "stakeholder_types",
        "prerequisites":     "prerequisites",
        "source_wp":         "source_wp",
        "source_doc_ref":    "source_doc_ref",
        "confidence":        "confidence",
        "metadata":          "metadata",
    },
    # Epidata WP3 real-data schema (predicted)
    "epidata_v1": {
        "id":                "node_id",
        "title":             "label",
        "desc":              "description",
        "dimension":         "dimension",
        "level":             "maturity_level",
        "applicable_to":     "stakeholder_types",
        "requires":          "prerequisites",
        "source_wp":         "source_wp",
        "source_doc_ref":    "source_doc_ref",
        "confidence":        "confidence",
        "metadata":          "metadata",
    },
}

_WP3_EDGE_NORMALIZERS: dict[str, dict[str, str]] = {
    "v1": {
        "edge_id":       "edge_id",
        "from_node_id":  "from_node_id",
        "to_node_id":    "to_node_id",
        "relation_type": "relation_type",
        "required":      "required",
        "source_doc_ref":"source_doc_ref",
    },
}

# ── WP8: Rules ───────────────────────────────────────────────────────

_WP8_RULE_NORMALIZERS: dict[str, dict[str, str]] = {
    "v1": {
        "rule_id":         "rule_id",
        "rule_type":       "rule_type",
        "priority":        "priority",
        "applies_to":      "applies_to",
        "condition":       "condition",
        "action":          "action",
        "compliance_refs": "compliance_refs",
        "source_doc_ref":  "source_doc_ref",
        "rule_version":    "rule_version",
        "parent_rule_id":  "parent_rule_id",
        "effective_from":  "effective_from",
        "effective_until": "effective_until",
    },
}


def _normalize_record(
    raw: dict,
    mapping: dict[str, str],
    version: str,
    label: str = "",
) -> dict:
    """Translate raw field names to canonical names using an explicit mapping.

    Council invariants (Dijkstra):
      I1 – output contains all keys from mapping.values()
      I2 – idempotent on already-normalized records
      I4 – unknown fields logged, not silently dropped
    """
    normalized: dict = {}
    mapped_keys: set[str] = set()

    for raw_key, raw_value in raw.items():
        canonical = mapping.get(raw_key)
        if canonical is not None:
            normalized[canonical] = raw_value
            mapped_keys.add(raw_key)
        else:
            logger.warning(
                "Schema drift [%s v%s]: unknown field %r (value kept as-is)",
                label, version, raw_key,
            )
            normalized[raw_key] = raw_value

    # I1 check: are all expected canonical keys present?
    expected = set(mapping.values())
    missing = expected - set(normalized.keys())
    if missing:
        logger.warning(
            "Schema drift [%s v%s]: missing canonical fields %s after normalization",
            label, version, sorted(missing),
        )

    return normalized


def _normalize_list(
    raw_list: list,
    mapping: dict[str, str],
    version: str,
    label: str = "",
) -> list[dict]:
    """Normalize every record in a list."""
    return [_normalize_record(r, mapping, version, label) for r in raw_list]


def _resolve_normalizer(
    normalizers: dict[str, dict[str, str]],
    version: str | None,
    label: str = "",
) -> dict[str, str]:
    """Dispatch to the correct normalizer for a schema version."""
    version = version or "v1"
    if version not in normalizers:
        raise UpstreamClientError(
            f"Unsupported {label} schema version: {version!r}. "
            f"Known versions: {sorted(normalizers.keys())}"
        )
    logger.info("Using %s normalizer version: %s", label, version)
    return normalizers[version]


class UpstreamClientError(Exception):
    """Raised when an upstream fetch fails after retries."""


class UpstreamClient:
    """Async HTTP client for consortium upstream services.

    On startup: fetch_stakeholders + fetch_roadmap + fetch_rules.
    Results cached in-memory for the lifetime of the FastAPI process.
    """

    def __init__(
        self,
        wp2_url: str | None = None,
        wp3_url: str | None = None,
        wp8_url: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.wp2_url = (wp2_url or os.getenv("WP2_API_URL", "http://wp2-mock:8080/api/v1")).rstrip("/")
        self.wp3_url = (wp3_url or os.getenv("WP3_API_URL", "http://wp3-mock:8080/api/v1")).rstrip("/")
        self.wp8_url = (wp8_url or os.getenv("WP8_API_URL", "http://wp8-mock:8080/api/v1")).rstrip("/")
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._session: Optional[aiohttp.ClientSession] = None

        # In-memory cache populated at startup
        self.stakeholders: list[dict] = []
        self.roadmap_nodes: list[RoadmapNode] = []
        self.roadmap_edges: list[RoadmapEdge] = []
        self.rules: list[Rule] = []
        self.rule_tests: list[dict] = []

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                raise_for_status=True,
            )
        return self._session

    async def _fetch_json(self, url: str, label: str) -> object:
        """GET JSON from an upstream endpoint with retry logic."""
        session = await self._ensure_session()
        last_err: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with session.get(url) as resp:
                    data = await resp.json()
                    logger.info("Upstream fetch OK: %s (attempt %d)", label, attempt)
                    return data
            except (aiohttp.ClientError, OSError) as exc:
                last_err = exc
                logger.warning(
                    "Upstream fetch failed: %s (attempt %d/%d): %s",
                    label, attempt, self._max_retries, exc,
                )
                if attempt < self._max_retries:
                    import asyncio
                    await asyncio.sleep(self._retry_delay * attempt)
        raise UpstreamClientError(
            f"Failed to fetch {label} after {self._max_retries} retries: {last_err}"
        ) from last_err

    # ── WP2: Stakeholder Taxonomy ────────────────────────────────────

    async def fetch_stakeholders(self, schema_version: str | None = None) -> list[dict]:
        """GET /api/v1/stakeholders → raw stakeholder type records."""
        url = f"{self.wp2_url}/stakeholders"
        data = await self._fetch_json(url, "WP2 stakeholders")
        if not isinstance(data, list):
            raise UpstreamClientError(f"WP2 expected list, got {type(data).__name__}")

        mapping = _resolve_normalizer(_WP2_NORMALIZERS, schema_version, "WP2")
        normalized = _normalize_list(data, mapping, schema_version or "v1", "WP2")

        self.stakeholders = normalized
        logger.info("Loaded %d stakeholder types from WP2", len(normalized))
        return normalized

    # ── WP3: Roadmap Graph ───────────────────────────────────────────

    async def fetch_roadmap(
        self, schema_version: str | None = None
    ) -> tuple[list[RoadmapNode], list[RoadmapEdge]]:
        """GET /api/v1/roadmap/nodes + /edges → domain model lists."""
        nodes_data = await self._fetch_json(
            f"{self.wp3_url}/roadmap/nodes", "WP3 roadmap nodes"
        )
        edges_data = await self._fetch_json(
            f"{self.wp3_url}/roadmap/edges", "WP3 roadmap edges"
        )

        # ── Normalize field names per schema version ──
        node_mapping = _resolve_normalizer(_WP3_NODE_NORMALIZERS, schema_version, "WP3 nodes")
        edge_mapping = _resolve_normalizer(_WP3_EDGE_NORMALIZERS, schema_version, "WP3 edges")
        nodes_data = _normalize_list(nodes_data, node_mapping, schema_version or "v1", "WP3 nodes")
        edges_data = _normalize_list(edges_data, edge_mapping, schema_version or "v1", "WP3 edges")

        nodes = [
            RoadmapNode(
                node_id=n["node_id"],
                label=n["label"],
                description=n.get("description", ""),
                dimension=n.get("dimension", "governance"),
                maturity_level=n.get("maturity_level", 1),
                stakeholder_types=tuple(n.get("stakeholder_types", ["all"])),
                prerequisites=tuple(n.get("prerequisites", [])),
                source_wp=n.get("source_wp", "WP3"),
                source_doc_ref=n.get("source_doc_ref", "demo-data"),
                confidence=n.get("confidence", 1.0),
                metadata=n.get("metadata", {}),
            )
            for n in nodes_data
        ]
        edges = [
            RoadmapEdge(
                edge_id=e["edge_id"],
                from_node_id=e["from_node_id"],
                to_node_id=e["to_node_id"],
                relation_type=e.get("relation_type", "prerequisite"),
                required=e.get("required", True),
                source_doc_ref=e.get("source_doc_ref", "demo-data"),
            )
            for e in edges_data
        ]

        self.roadmap_nodes = nodes
        self.roadmap_edges = edges
        logger.info(
            "Loaded %d roadmap nodes + %d edges from WP3",
            len(nodes), len(edges),
        )
        return nodes, edges

    # ── WP8: Rules + Tests ───────────────────────────────────────────

    async def fetch_rules(self, schema_version: str | None = None) -> list[Rule]:
        """GET /api/v1/rules → compliance Rule domain models."""
        data = await self._fetch_json(f"{self.wp8_url}/rules", "WP8 rules")
        if not isinstance(data, list):
            raise UpstreamClientError(f"WP8 expected list, got {type(data).__name__}")

        mapping = _resolve_normalizer(_WP8_RULE_NORMALIZERS, schema_version, "WP8 rules")
        data = _normalize_list(data, mapping, schema_version or "v1", "WP8 rules")

        rules = [
            Rule(
                rule_id=r["rule_id"],
                rule_type=RuleType(r.get("rule_type", "preference")),
                priority=r.get("priority", 50),
                applies_to=tuple(r.get("applies_to", ["all"])),
                condition=r["condition"],
                action=RuleAction(
                    title=r["action"]["title"],
                    text=r["action"]["text"],
                    node_id=r["action"].get("node_id"),
                    warning=r["action"].get("warning"),
                    block=r["action"].get("block", False),
                ),
                compliance_refs=tuple(r.get("compliance_refs", [])),
                effective_from=None,
                effective_until=None,
                parent_rule_id=r.get("parent_rule_id"),
                source_doc_ref=r.get("source_doc_ref", "demo-data"),
                rule_version=r.get("rule_version", "demo-rules-v1"),
            )
            for r in data
        ]

        self.rules = rules
        logger.info("Loaded %d rules from WP8", len(rules))
        return rules

    async def fetch_rule_tests(self) -> list[dict]:
        """GET /api/v1/tests → paired test cases (optional)."""
        try:
            data = await self._fetch_json(f"{self.wp8_url}/tests", "WP8 tests")
            if isinstance(data, list):
                self.rule_tests = data
                logger.info("Loaded %d rule tests from WP8", len(data))
                return data
        except Exception:
            logger.warning("WP8 tests unavailable (non-fatal)")
        return []

    # ── Lifecycle ────────────────────────────────────────────────────

    async def startup(self) -> None:
        """Fetch all upstream data and populate in-memory cache.

        Called once during FastAPI lifespan (startup event).
        """
        logger.info("UpstreamClient startup: fetching WP2/WP3/WP8 data...")
        await self.fetch_stakeholders()
        await self.fetch_roadmap()
        await self.fetch_rules()
        await self.fetch_rule_tests()
        logger.info(
            "UpstreamClient ready: %d stakeholders, %d nodes, %d edges, %d rules, %d tests",
            len(self.stakeholders),
            len(self.roadmap_nodes),
            len(self.roadmap_edges),
            len(self.rules),
            len(self.rule_tests),
        )

    async def close(self) -> None:
        """Close the aiohttp session (called during FastAPI shutdown)."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("UpstreamClient session closed")

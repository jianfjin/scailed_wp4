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

    async def fetch_stakeholders(self) -> list[dict]:
        """GET /api/v1/stakeholders → raw stakeholder type records."""
        url = f"{self.wp2_url}/stakeholders"
        data = await self._fetch_json(url, "WP2 stakeholders")
        if not isinstance(data, list):
            raise UpstreamClientError(f"WP2 expected list, got {type(data).__name__}")
        self.stakeholders = data
        logger.info("Loaded %d stakeholder types from WP2", len(data))
        return data

    # ── WP3: Roadmap Graph ───────────────────────────────────────────

    async def fetch_roadmap(self) -> tuple[list[RoadmapNode], list[RoadmapEdge]]:
        """GET /api/v1/roadmap/nodes + /edges → domain model lists."""
        nodes_data = await self._fetch_json(
            f"{self.wp3_url}/roadmap/nodes", "WP3 roadmap nodes"
        )
        edges_data = await self._fetch_json(
            f"{self.wp3_url}/roadmap/edges", "WP3 roadmap edges"
        )

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

    async def fetch_rules(self) -> list[Rule]:
        """GET /api/v1/rules → compliance Rule domain models."""
        data = await self._fetch_json(f"{self.wp8_url}/rules", "WP8 rules")
        if not isinstance(data, list):
            raise UpstreamClientError(f"WP8 expected list, got {type(data).__name__}")

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

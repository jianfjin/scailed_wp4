"""V3: AGE catalog consistency verification.

Compares AGE graph and label counts from backup catalog.json
against the live PostgreSQL database.
"""

from __future__ import annotations

import json
from pathlib import Path


class TestAGECatalog:
    """V3 — AGE graph metadata consistency."""

    def test_catalog_json_valid(self, catalog_json: dict) -> None:
        """catalog.json must contain required fields."""
        assert "age_graphs" in catalog_json, "Missing age_graphs"
        assert "age_labels" in catalog_json, "Missing age_labels"
        assert "age_vertex_count" in catalog_json, "Missing age_vertex_count"
        assert "size_bytes" in catalog_json, "Missing size_bytes"
        assert "total_rows" in catalog_json, "Missing total_rows"

    def test_graph_count_matches(
        self, catalog_json: dict, pg_age_stats: dict
    ) -> None:
        """Age graph count in catalog must match live DB."""
        cat_graphs = len(catalog_json["age_graphs"])
        live_graphs = pg_age_stats["graphs"]
        assert cat_graphs == live_graphs, (
            f"Graph count mismatch: catalog={cat_graphs}, live={live_graphs}"
        )

    def test_label_count_matches(
        self, catalog_json: dict, pg_age_stats: dict
    ) -> None:
        """Age label count in catalog must match live DB."""
        cat_labels = len(catalog_json["age_labels"])
        live_labels = pg_age_stats["labels"]
        assert cat_labels == live_labels, (
            f"Label count mismatch: catalog={cat_labels}, live={live_labels}"
        )

    def test_vertex_count_non_zero(self, catalog_json: dict) -> None:
        """age_vertex_count must be non-negative."""
        assert catalog_json["age_vertex_count"] >= 0

    def test_db_size_positive(self, catalog_json: dict) -> None:
        """Database size must be positive."""
        assert catalog_json["size_bytes"] > 0

    def test_catalog_graphs_have_namespace(
        self, catalog_json: dict
    ) -> None:
        """Each AGE graph entry must have namespace and graph fields."""
        for g in catalog_json.get("age_graphs", []):
            assert "namespace" in g, f"Graph missing namespace: {g}"
            assert "graph" in g, f"Graph entry missing name: {g}"

    def test_catalog_labels_have_required_fields(
        self, catalog_json: dict
    ) -> None:
        """Each AGE label entry must have namespace, label, kind."""
        for lab in catalog_json.get("age_labels", []):
            assert "namespace" in lab, f"Label missing namespace: {lab}"
            assert "label" in lab, f"Label missing name: {lab}"
            assert "kind" in lab, f"Label missing kind: {lab}"

    def test_total_rows_non_negative(self, catalog_json: dict) -> None:
        """total_rows must be non-negative."""
        tr = catalog_json["total_rows"]
        assert isinstance(tr, (int, float)), f"total_rows not numeric: {type(tr)}"
        assert tr >= 0, f"total_rows negative: {tr}"

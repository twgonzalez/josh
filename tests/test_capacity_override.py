# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""Unit tests for _apply_capacity_overrides() in agents/capacity_analysis.py.

Tests:
  1. capacity_vph override changes capacity_vph on the matching segment.
  2. Missing reason/source logs WARNING and skips the segment (no change).
  3. Stale osmid (not in roads_gdf) logs WARNING and skips (no crash).
  4. capacity_source column is set correctly for overridden vs. non-overridden segments.
  5. capacity_override_reason and capacity_override_source_doc are set on overridden segments.
  6. Entry with capacity_vph keyed by name (not osmid) logs WARNING and skips.
  7. No override file → returns unchanged gdf with capacity_source = "hcm".
"""
import logging
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import pandas as pd
import unittest
from shapely.geometry import LineString

from agents.capacity_analysis import _apply_capacity_overrides


def _make_roads_gdf(osmids=None):
    """Build a minimal roads GeoDataFrame with three segments."""
    if osmids is None:
        osmids = ["111", "222", "333"]
    return gpd.GeoDataFrame(
        {
            "osmid": osmids,
            "name": ["Main St", "Oak Ave", "Elm Dr"],
            "capacity_vph": [1350.0, 1900.0, 900.0],
            "road_type": ["two_lane", "multilane", "two_lane"],
            "lane_count": [2, 4, 2],
            "speed_limit": [30, 45, 20],
            "geometry": [
                LineString([(0, 0), (1, 1)]),
                LineString([(1, 1), (2, 2)]),
                LineString([(2, 2), (3, 3)]),
            ],
        },
        crs="EPSG:4326",
    )


def _write_override_yaml(tmp_dir: Path, city_slug: str, content: str) -> Path:
    """Write a road override YAML in the expected location under tmp_dir."""
    cities_dir = tmp_dir / "config" / "private" / "cities"
    cities_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = cities_dir / f"{city_slug}_road_overrides.yaml"
    yaml_path.write_text(textwrap.dedent(content))
    return yaml_path


class TestApplyCapacityOverrides(unittest.TestCase):
    """Tests for _apply_capacity_overrides()."""

    def _run(self, yaml_content: str, city_slug: str = "testcity") -> gpd.GeoDataFrame:
        """
        Helper: write a YAML override file to a temp tree, run the function,
        return the resulting GeoDataFrame.
        """
        roads = _make_roads_gdf()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_override_yaml(tmp_path, city_slug, yaml_content)

            # Monkey-patch _REPO_ROOT so the function finds the temp config tree
            import agents.capacity_analysis as ca
            orig_root = ca._REPO_ROOT
            ca._REPO_ROOT = tmp_path
            try:
                data_dir = tmp_path / "data" / city_slug
                data_dir.mkdir(parents=True, exist_ok=True)
                result = _apply_capacity_overrides(roads, {}, data_dir)
            finally:
                ca._REPO_ROOT = orig_root
        return result

    def test_capacity_vph_override_applied(self):
        """capacity_vph entry with valid reason+source changes capacity_vph on match."""
        yaml = """\
            road_overrides:
              - osmid: "222"
                capacity_vph: 800
                reason: "Field count shows 800 vph peak throughput"
                source: "Caltrans TMC report 2024-08-15"
        """
        result = self._run(yaml)
        row = result[result["osmid"] == "222"].iloc[0]
        self.assertAlmostEqual(row["capacity_vph"], 800.0)
        self.assertEqual(row["capacity_source"], "city_override")
        self.assertEqual(row["capacity_override_reason"], "Field count shows 800 vph peak throughput")
        self.assertEqual(row["capacity_override_source_doc"], "Caltrans TMC report 2024-08-15")

    def test_non_overridden_segments_unchanged(self):
        """Segments without a capacity_vph entry retain HCM values and capacity_source='hcm'."""
        yaml = """\
            road_overrides:
              - osmid: "222"
                capacity_vph: 800
                reason: "Field count"
                source: "Caltrans TMC 2024"
        """
        result = self._run(yaml)
        for osmid, expected_cap in [("111", 1350.0), ("333", 900.0)]:
            row = result[result["osmid"] == osmid].iloc[0]
            self.assertAlmostEqual(row["capacity_vph"], expected_cap,
                                   msg=f"osmid {osmid} capacity should be unchanged")
            self.assertEqual(row["capacity_source"], "hcm",
                             msg=f"osmid {osmid} capacity_source should be 'hcm'")

    def test_missing_reason_logs_warning_and_skips(self):
        """Entry with capacity_vph but no reason logs WARNING and does not change capacity_vph."""
        yaml = """\
            road_overrides:
              - osmid: "111"
                capacity_vph: 500
                source: "Some report"
        """
        with self.assertLogs("agents.capacity_analysis", level=logging.WARNING) as cm:
            result = self._run(yaml)
        self.assertTrue(any("reason" in msg and "source" in msg for msg in cm.output),
                        msg="Expected WARNING about missing reason/source")
        row = result[result["osmid"] == "111"].iloc[0]
        self.assertAlmostEqual(row["capacity_vph"], 1350.0, msg="capacity_vph must be unchanged")
        self.assertEqual(row["capacity_source"], "hcm")

    def test_missing_source_logs_warning_and_skips(self):
        """Entry with capacity_vph but no source logs WARNING and does not change capacity_vph."""
        yaml = """\
            road_overrides:
              - osmid: "333"
                capacity_vph: 400
                reason: "Observed congestion at this segment"
        """
        with self.assertLogs("agents.capacity_analysis", level=logging.WARNING) as cm:
            result = self._run(yaml)
        self.assertTrue(any("reason" in msg and "source" in msg for msg in cm.output),
                        msg="Expected WARNING about missing reason/source")
        row = result[result["osmid"] == "333"].iloc[0]
        self.assertAlmostEqual(row["capacity_vph"], 900.0, msg="capacity_vph must be unchanged")

    def test_stale_osmid_logs_warning_and_skips(self):
        """Entry whose osmid is not in roads_gdf logs WARNING and does not crash."""
        yaml = """\
            road_overrides:
              - osmid: "999999"
                capacity_vph: 500
                reason: "Stale entry"
                source: "Old survey 2020"
        """
        with self.assertLogs("agents.capacity_analysis", level=logging.WARNING) as cm:
            result = self._run(yaml)
        self.assertTrue(any("999999" in msg for msg in cm.output),
                        msg="Expected WARNING mentioning the stale osmid")
        # All original capacities unchanged
        for osmid, expected in [("111", 1350.0), ("222", 1900.0), ("333", 900.0)]:
            row = result[result["osmid"] == osmid].iloc[0]
            self.assertAlmostEqual(row["capacity_vph"], expected)

    def test_name_keyed_entry_logs_warning_and_skips(self):
        """Entry with capacity_vph keyed by name (not osmid) logs WARNING and skips."""
        yaml = """\
            road_overrides:
              - name: "Main St"
                capacity_vph: 600
                reason: "Field count"
                source: "City survey 2024"
        """
        with self.assertLogs("agents.capacity_analysis", level=logging.WARNING) as cm:
            result = self._run(yaml)
        self.assertTrue(any("osmid" in msg.lower() for msg in cm.output),
                        msg="Expected WARNING about missing osmid")
        row = result[result["osmid"] == "111"].iloc[0]
        self.assertAlmostEqual(row["capacity_vph"], 1350.0)

    def test_no_override_file_returns_hcm_source(self):
        """When no override file exists, all segments get capacity_source='hcm'."""
        roads = _make_roads_gdf()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            import agents.capacity_analysis as ca
            orig_root = ca._REPO_ROOT
            ca._REPO_ROOT = tmp_path
            try:
                data_dir = tmp_path / "data" / "nocity"
                data_dir.mkdir(parents=True, exist_ok=True)
                result = _apply_capacity_overrides(roads, {}, data_dir)
            finally:
                ca._REPO_ROOT = orig_root
        self.assertTrue((result["capacity_source"] == "hcm").all())
        self.assertTrue(result["capacity_override_reason"].isna().all())
        self.assertTrue(result["capacity_override_source_doc"].isna().all())

    def test_capacity_source_column_present_without_override(self):
        """capacity_source column is always added even when no overrides apply."""
        roads = _make_roads_gdf()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            import agents.capacity_analysis as ca
            orig_root = ca._REPO_ROOT
            ca._REPO_ROOT = tmp_path
            try:
                result = _apply_capacity_overrides(roads, {}, None)
            finally:
                ca._REPO_ROOT = orig_root
        self.assertIn("capacity_source", result.columns)
        self.assertIn("capacity_override_reason", result.columns)
        self.assertIn("capacity_override_source_doc", result.columns)

    def test_multiple_overrides_applied(self):
        """Multiple valid capacity_vph entries all applied correctly."""
        yaml = """\
            road_overrides:
              - osmid: "111"
                capacity_vph: 700
                reason: "Count at segment A"
                source: "City survey 2024-01"
              - osmid: "333"
                capacity_vph: 450
                reason: "Count at segment C"
                source: "City survey 2024-02"
        """
        result = self._run(yaml)
        self.assertAlmostEqual(result[result["osmid"] == "111"].iloc[0]["capacity_vph"], 700.0)
        self.assertAlmostEqual(result[result["osmid"] == "333"].iloc[0]["capacity_vph"], 450.0)
        # Untouched segment
        self.assertAlmostEqual(result[result["osmid"] == "222"].iloc[0]["capacity_vph"], 1900.0)
        self.assertEqual(result[result["osmid"] == "222"].iloc[0]["capacity_source"], "hcm")


if __name__ == "__main__":
    unittest.main()

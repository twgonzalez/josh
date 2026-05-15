# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""Unit tests for extracted wildland routing functions.

Tests the pure functions that were extracted from identify_routes():
- _filter_by_travel_time: travel-time ratio filter
- SegmentIndex: single-object road attribute lookup
"""
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from agents.scenarios.routing import RawCandidate
from agents.scenarios.segment_index import SegmentIndex, SegmentInfo
from agents.scenarios.wildland import _filter_by_travel_time


def _make_raw(travel_time_s=100.0, exit_node=1, osmids=None, exit_osmid="100"):
    """Helper: build a minimal RawCandidate."""
    return RawCandidate(
        travel_time_s=travel_time_s,
        exit_node_id=exit_node,
        path_osmids=osmids or ["100", "200", "300"],
        exit_osmid=exit_osmid,
        path_length_m=500.0,
        path_wgs84_coords=[[37.0, -122.0], [37.1, -122.1]],
        osmid_to_uv={"100": (1, 2), "200": (2, 3), "300": (3, 4)},
    )


class TestFilterByTravelTime(unittest.TestCase):
    """Tests for _filter_by_travel_time."""

    def test_empty_input(self):
        self.assertEqual(_filter_by_travel_time([], 2.0), [])

    def test_all_within_ratio(self):
        c1 = _make_raw(travel_time_s=100.0, exit_node=1)
        c2 = _make_raw(travel_time_s=150.0, exit_node=2)
        result = _filter_by_travel_time([c1, c2], 2.0)
        self.assertEqual(len(result), 2)

    def test_excludes_beyond_ratio(self):
        c1 = _make_raw(travel_time_s=100.0, exit_node=1)
        c2 = _make_raw(travel_time_s=250.0, exit_node=2)  # 2.5× → excluded at 2.0
        result = _filter_by_travel_time([c1, c2], 2.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].exit_node_id, 1)

    def test_boundary_exactly_at_ratio(self):
        c1 = _make_raw(travel_time_s=100.0, exit_node=1)
        c2 = _make_raw(travel_time_s=200.0, exit_node=2)  # exactly 2.0×
        result = _filter_by_travel_time([c1, c2], 2.0)
        self.assertEqual(len(result), 2)


class TestSegmentIndex(unittest.TestCase):
    """Tests for SegmentIndex construction from roads_gdf."""

    def _make_roads_gdf(self):
        """Build a minimal roads GeoDataFrame."""
        return gpd.GeoDataFrame({
            "osmid": ["100", "200", "300"],
            "name": ["Main St", "Oak Ave", ""],
            "effective_capacity_vph": [900.0, 1800.0, 500.0],
            "capacity_vph": [1200.0, 1900.0, 700.0],
            "road_type": ["two_lane", "multilane", "two_lane"],
            "fhsz_zone": ["vhfhsz", "non_fhsz", "high_fhsz"],
            "hazard_degradation": [0.35, 1.0, 0.50],
            "lane_count": [2, 4, 2],
            "speed_limit": [25, 45, 30],
            "geometry": [
                LineString([(0, 0), (1, 1)]),
                LineString([(1, 1), (2, 2)]),
                LineString([(2, 2), (3, 3)]),
            ],
        }, crs="EPSG:4326")

    def test_basic_lookup(self):
        idx = SegmentIndex(self._make_roads_gdf())
        info = idx.get("100")
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "Main St")
        self.assertEqual(info.effective_capacity_vph, 900.0)
        self.assertEqual(info.fhsz_zone, "vhfhsz")
        self.assertEqual(info.haz_class, 3)
        self.assertEqual(info.lane_count, 2)
        self.assertEqual(info.speed_limit, 25)

    def test_eff_cap_shortcut(self):
        idx = SegmentIndex(self._make_roads_gdf())
        self.assertEqual(idx.eff_cap("200"), 1800.0)
        self.assertEqual(idx.eff_cap("missing"), 0.0)

    def test_missing_osmid(self):
        idx = SegmentIndex(self._make_roads_gdf())
        self.assertIsNone(idx.get("999"))

    def test_haz_class_mapping(self):
        idx = SegmentIndex(self._make_roads_gdf())
        self.assertEqual(idx.get("100").haz_class, 3)  # vhfhsz
        self.assertEqual(idx.get("200").haz_class, 0)  # non_fhsz
        self.assertEqual(idx.get("300").haz_class, 2)  # high_fhsz


if __name__ == "__main__":
    unittest.main()

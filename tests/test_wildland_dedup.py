# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""Unit tests for extracted wildland routing functions.

Tests the pure functions that were extracted from identify_routes():
- _filter_by_travel_time: travel-time ratio filter
- bake_capacity_onto_graph: per-edge eff_cap_vph + related attrs (v4.13)
"""
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString

from agents.capacity_analysis import bake_capacity_onto_graph
from agents.scenarios.routing import RawCandidate
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


class TestBakeCapacityOntoGraph(unittest.TestCase):
    """Tests for bake_capacity_onto_graph — the per-edge cap injector that
    replaced SegmentIndex (v4.13 parity fix)."""

    def _make_roads_gdf(self):
        """Build a minimal roads GeoDataFrame matching analyze_capacity output."""
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

    def _make_graph(self, edges):
        """Build a minimal MultiDiGraph matching OSMnx output."""
        G = nx.MultiDiGraph()
        for u, v, osmid in edges:
            G.add_edge(u, v, 0, osmid=osmid)
        return G

    def test_single_osmid_edge_baked(self):
        roads = self._make_roads_gdf()
        G = self._make_graph([(1, 2, "100"), (2, 3, "200"), (3, 4, "300")])
        n = bake_capacity_onto_graph(G, roads)
        self.assertEqual(n, 3)
        self.assertEqual(G[1][2][0]["eff_cap_vph"], 900.0)
        self.assertEqual(G[1][2][0]["fhsz_zone"], "vhfhsz")
        self.assertEqual(G[1][2][0]["bottleneck_name"], "Main St")
        self.assertEqual(G[2][3][0]["eff_cap_vph"], 1800.0)
        self.assertEqual(G[3][4][0]["eff_cap_vph"], 500.0)

    def test_multi_osmid_edge_picks_bottleneck(self):
        # OSMnx-simplified edge with osmid=[100, 200] should bake to the
        # LOWER eff_cap (100 → 900) — the binding sub-segment.
        roads = self._make_roads_gdf()
        G = self._make_graph([(1, 2, ["100", "200"])])
        bake_capacity_onto_graph(G, roads)
        self.assertEqual(G[1][2][0]["eff_cap_vph"], 900.0,
                         "multi-osmid edge takes MIN eff_cap (bottleneck semantics)")
        # Metadata also comes from the chosen (lowest-cap) row
        self.assertEqual(G[1][2][0]["bottleneck_name"], "Main St")

    def test_missing_osmid_eff_cap_zero(self):
        # Edge with an osmid not in roads_gdf gets eff_cap_vph=0 (skipped
        # by the bottleneck argmin downstream).  This was the source of the
        # v4.12 parity divergence: Python returned 0 (skip), JS defaulted
        # to 1000 (consider as bottleneck).  Bake gives them the same 0.
        roads = self._make_roads_gdf()
        G = self._make_graph([(1, 2, "999")])  # 999 not in roads_gdf
        bake_capacity_onto_graph(G, roads)
        self.assertEqual(G[1][2][0]["eff_cap_vph"], 0.0)

    def test_multi_osmid_one_missing_uses_present(self):
        # OSMnx simplified an edge to osmid=[100, 999].  100 is in roads_gdf
        # (eff_cap 900); 999 isn't.  Bake should still pick up 100's data.
        roads = self._make_roads_gdf()
        G = self._make_graph([(1, 2, ["100", "999"])])
        bake_capacity_onto_graph(G, roads)
        self.assertEqual(G[1][2][0]["eff_cap_vph"], 900.0)
        self.assertEqual(G[1][2][0]["bottleneck_name"], "Main St")


if __name__ == "__main__":
    unittest.main()

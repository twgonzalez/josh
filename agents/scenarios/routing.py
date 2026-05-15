# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""Routing data structures for wildland evacuation Dijkstra.

Replaces magic 7-element tuples with named dataclasses so that fields
are self-documenting and adding new attributes never requires updating
positional unpacking.
"""
from dataclasses import dataclass, field


@dataclass
class RawCandidate:
    """A candidate evacuation path from Dijkstra, before bottleneck/dedup."""

    travel_time_s: float
    exit_node_id: int
    path_osmids: list[str]
    exit_osmid: str
    path_length_m: float
    path_wgs84_coords: list[list[float]]
    osmid_to_uv: dict[str, tuple[int, int]]


@dataclass
class CandidateWithBottleneck:
    """Candidate after bottleneck identification and optional enrichment."""

    # Carried forward from RawCandidate
    travel_time_s: float
    exit_node_id: int
    path_osmids: list[str]
    exit_osmid: str
    path_length_m: float
    path_wgs84_coords: list[list[float]]
    osmid_to_uv: dict[str, tuple[int, int]]

    # Bottleneck identification
    bottleneck_osmid: str = ""
    bottleneck_eff_cap: float = 0.0
    bottleneck_name: str = ""

    # Cross-street enrichment
    cross_street_a: str = ""
    cross_street_b: str = ""
    distance_mi: float = 0.0
    bearing: str = ""


@dataclass
class EgressOrigin:
    """An egress origin point for Dijkstra routing."""

    node_id: int
    label: str


@dataclass
class GraphContext:
    """Loaded graph, exits, and projection state."""

    G: object  # nx.MultiDiGraph — untyped to avoid hard networkx import
    G_undirected: object  # undirected copy with travel_time_s weights
    exit_nodes: list[int]
    nearest_node: int
    transformer: object  # pyproj.Transformer
    proj_x: float
    proj_y: float

# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
SB 99 single-access area identification.

SB 99 (2019), companion to AB 747, requires cities to identify residential areas
that lack at least two separate and distinct evacuation routes (Gov. Code §65302.15(b)(3)).

This module maps "distinct exit routes" to distinct exit_segment_osmids reachable
from a block group's modeled evacuation paths. Each unique exit_segment_osmid
represents a physically separate handoff point from the local road network into the
regional evacuation network (motorway/trunk/primary).

IMPORTANT methodological note: Agent 2 (capacity_analysis.py) currently computes
the single fastest Dijkstra path per block group. A block group with one modeled
path therefore has one modeled exit, and is flagged as single-access. This is a
conservative (safety-favoring) bound — it may over-count single-access areas when
a second physical exit exists but was not modeled as a shorter/faster path. The
report narrative discloses this limitation.

Legal basis: Gov. Code §65302.15(b)(3) (SB 99).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import geopandas as gpd


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BlockGroupAccess:
    geoid: str
    housing_units: float
    exit_count: int             # number of distinct exit_segment_osmids modeled
    exit_osmids: list[str]
    is_single_access: bool      # exit_count < 2
    label: str = ""             # human-readable location, e.g. "near Telegraph Ave & Dwight Way"


@dataclass
class Sb99Result:
    total_block_groups: int
    modeled_block_groups: int           # BGs with at least one evacuation path
    single_access_count: int            # BGs with < 2 distinct exit osmids
    single_access_housing_units: float
    fraction_single_access: float       # single_access_HU / total_HU
    block_group_details: list[BlockGroupAccess] = field(default_factory=list)
    methodology_note: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

METHODOLOGY_NOTE = (
    "Agent 2 (capacity analysis) computes the single fastest Dijkstra path per "
    "block group origin. A block group with one modeled path therefore shows one "
    "distinct exit, and is conservatively flagged as single-access. Physical "
    "secondary exits may exist but were not modeled as the shortest/fastest route. "
    "This analysis is a conservative upper bound per SB 99 methodology — it "
    "over-counts rather than under-counts single-access areas. "
    "Gov. Code §65302.15(b)(3) requires identification; resolution requires "
    "field verification of secondary access routes for flagged areas."
)


def scan_single_access_areas(
    evacuation_paths: list,
    block_groups_gdf: gpd.GeoDataFrame,
    roads_gdf: gpd.GeoDataFrame | None = None,
) -> Sb99Result:
    """
    Identify block groups with fewer than 2 distinct modeled evacuation exits.

    Parameters
    ----------
    evacuation_paths : list
        List of EvacuationPath objects or dicts (duck-typed).
        Must have fields: origin_block_group, exit_segment_osmid.
    block_groups_gdf : GeoDataFrame
        Census block groups with GEOID and housing_units columns.
    roads_gdf : GeoDataFrame, optional
        Road network (from roads.gpkg). When provided, each BlockGroupAccess
        receives a human-readable ``label`` like "near Telegraph Ave & Dwight Way"
        derived from the 2 nearest named road segments to the block group centroid.
        When omitted, ``label`` falls back to the raw GEOID.

    Returns
    -------
    Sb99Result
    """
    geoid_col = _detect_geoid_column(block_groups_gdf)
    hu_col = _detect_hu_column(block_groups_gdf)

    # ------------------------------------------------------------------
    # Step 1 — Build block group → set of exit osmids
    # ------------------------------------------------------------------
    bg_exits: dict[str, set[str]] = defaultdict(set)
    for path in evacuation_paths:
        bg_geoid = _get(path, "origin_block_group")
        exit_osmid = _get(path, "exit_segment_osmid")
        if bg_geoid and exit_osmid:
            bg_exits[str(bg_geoid)].add(str(exit_osmid))

    # ------------------------------------------------------------------
    # Step 2 — Classify each block group
    # ------------------------------------------------------------------
    details: list[BlockGroupAccess] = []
    total_hu = 0.0
    single_access_hu = 0.0

    for _, row in block_groups_gdf.iterrows():
        geoid = str(row[geoid_col])
        hu = float(row.get(hu_col, 0) or 0.0)
        total_hu += hu

        exits = bg_exits.get(geoid, set())
        exit_count = len(exits)
        is_single = exit_count < 2

        if is_single:
            single_access_hu += hu

        details.append(BlockGroupAccess(
            geoid=geoid,
            housing_units=hu,
            exit_count=exit_count,
            exit_osmids=sorted(exits),
            is_single_access=is_single,
        ))

    # Sort: single-access first, then by housing units descending
    details.sort(key=lambda b: (not b.is_single_access, -b.housing_units))

    # Attach human-readable location labels
    if roads_gdf is not None:
        label_map = _label_block_groups(block_groups_gdf, roads_gdf, geoid_col)
        for bg in details:
            bg.label = label_map.get(bg.geoid, bg.geoid)
    else:
        for bg in details:
            bg.label = bg.geoid

    total_bgs = len(details)
    modeled_bgs = sum(1 for b in details if b.exit_count > 0)
    single_count = sum(1 for b in details if b.is_single_access)
    fraction = single_access_hu / total_hu if total_hu > 0 else 0.0

    return Sb99Result(
        total_block_groups=total_bgs,
        modeled_block_groups=modeled_bgs,
        single_access_count=single_count,
        single_access_housing_units=single_access_hu,
        fraction_single_access=fraction,
        block_group_details=details,
        methodology_note=METHODOLOGY_NOTE,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get(obj, key: str):
    """Duck-type attribute access for EvacuationPath objects or plain dicts."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _label_block_groups(
    block_groups_gdf: gpd.GeoDataFrame,
    roads_gdf: gpd.GeoDataFrame,
    geoid_col: str,
) -> dict[str, str]:
    """
    Return {geoid: label} using the 2 nearest named road segments to each BG centroid.

    Label format: "near {road1} & {road2}".
    Falls back to the raw GEOID if no named roads are nearby.
    Completely offline — uses the already-cached roads_gdf.
    """
    analysis_crs = "EPSG:3310"  # CA Albers — same CRS used throughout JOSH
    bg = block_groups_gdf.copy().to_crs(analysis_crs)
    centroids = bg.geometry.centroid

    roads = roads_gdf.copy().to_crs(analysis_crs)
    named = roads[
        roads["name"].notna()
        & (roads["name"].astype(str).str.strip() != "")
        & (roads["name"].astype(str) != "nan")
    ].copy()

    if named.empty:
        return {str(bg[geoid_col].iloc[i]): str(bg[geoid_col].iloc[i]) for i in range(len(bg))}

    named_centroids = named.geometry.centroid

    labels: dict[str, str] = {}
    for i in range(len(bg)):
        centroid = centroids.iloc[i]
        geoid = str(bg[geoid_col].iloc[i])

        dists = named_centroids.distance(centroid)
        nearest_idx = dists.nsmallest(5).index
        nearby_names = named.loc[nearest_idx, "name"].tolist()

        # Deduplicate while preserving nearest-first order
        seen: set[str] = set()
        unique_names: list[str] = []
        for n in nearby_names:
            n_clean = str(n).strip()
            if n_clean and n_clean not in seen:
                seen.add(n_clean)
                unique_names.append(n_clean)
            if len(unique_names) == 2:
                break

        if len(unique_names) >= 2:
            labels[geoid] = f"near {unique_names[0]} & {unique_names[1]}"
        elif len(unique_names) == 1:
            labels[geoid] = f"near {unique_names[0]}"
        else:
            labels[geoid] = geoid

    return labels


def _detect_geoid_column(gdf: gpd.GeoDataFrame) -> str:
    for candidate in ("GEOID", "geoid", "GEOID20", "GEOID10", "bg_geoid"):
        if candidate in gdf.columns:
            return candidate
    raise ValueError(
        "block_groups_gdf has no recognizable GEOID column. "
        f"Available columns: {list(gdf.columns)}"
    )


def _detect_hu_column(gdf: gpd.GeoDataFrame) -> str:
    for candidate in ("housing_units", "housing_units_in_city", "housing_units_total"):
        if candidate in gdf.columns:
            return candidate
    for col in gdf.columns:
        if "housing" in col.lower():
            return col
    raise ValueError(
        "block_groups_gdf has no recognizable housing_units column. "
        f"Available columns: {list(gdf.columns)}"
    )

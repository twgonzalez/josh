# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
City-wide evacuation clearance time computation.

Computes how long it would take to evacuate all residents from a city under
fire conditions, given the degraded effective capacity of exit routes.

Formula:
    clearance_time_minutes = (total_vehicles / total_exit_capacity_vph) * 60

where:
    total_vehicles = sum(block_group.housing_units) * vehicles_per_unit * mobilization_rate
    total_exit_capacity_vph = sum of unique exit segment effective_capacity_vph
                               (deduplicated by exit_segment_osmid)

Legal basis: Gov. Code §65302.15 (AB 747) — requires evaluation of evacuation route
capacity sufficient to serve the jurisdiction's population within the applicable
safe egress window.

Source references:
    - NIST TN 2135 (Camp Fire clearance timeline)
    - HCM 2022 (capacity methodology)
    - NFPA 101 (mobilization rate design basis)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import geopandas as gpd
import pandas as pd


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

ZONE_ORDER = ("vhfhsz", "high_fhsz", "moderate_fhsz", "non_fhsz")

_ZONE_HAZ_CLASS = {
    "vhfhsz": [3],
    "high_fhsz": [2],
    "moderate_fhsz": [1],
    # non_fhsz is the complement — block groups with no FHSZ intersection
}

_ZONE_LABEL = {
    "vhfhsz": "Very High FHSZ",
    "high_fhsz": "High FHSZ",
    "moderate_fhsz": "Moderate FHSZ",
    "non_fhsz": "Non-FHSZ",
}


@dataclass
class ZoneClearance:
    zone: str                           # "vhfhsz" | "high_fhsz" | "moderate_fhsz" | "non_fhsz"
    zone_label: str                     # Human-readable label
    housing_units: float                # Housing units in this zone (area-weighted)
    total_vehicles: float               # housing_units * vpu * mobilization_rate
    exit_capacity_vph: float            # sum of unique exit effective_capacity_vph serving zone
    clearance_time_minutes: float       # total_vehicles / exit_capacity_vph * 60 (inf if no exits)
    safe_egress_window_minutes: float   # from config
    ratio_to_window: float              # clearance_time / safe_egress_window (inf if no exits)
    is_over_window: bool                # ratio > 1.0


@dataclass
class ClearanceResult:
    total_housing_units: float
    total_vehicles: float
    total_exit_capacity_vph: float
    total_clearance_time_minutes: float  # inf if no exits found
    per_zone: list[ZoneClearance] = field(default_factory=list)
    methodology_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_clearance_time(
    block_groups_gdf: gpd.GeoDataFrame,
    evacuation_paths: list,
    fhsz_gdf: gpd.GeoDataFrame,
    config: dict,
) -> ClearanceResult:
    """
    Compute city-wide and per-zone evacuation clearance times.

    Parameters
    ----------
    block_groups_gdf : GeoDataFrame
        Census block groups with a "housing_units" column (from data_acquisition).
    evacuation_paths : list
        List of EvacuationPath objects or dicts (duck-typed).
        Must have fields: origin_block_group, exit_segment_osmid,
        bottleneck_effective_capacity_vph.
    fhsz_gdf : GeoDataFrame
        CAL FIRE FHSZ polygons with a "HAZ_CLASS" integer column (1/2/3).
    config : dict
        Global parameters dict (from parameters.yaml).

    Returns
    -------
    ClearanceResult
    """
    vpu = float(config.get("vehicles_per_unit", 2.5))
    mob = float(config.get("mobilization_rate", 0.90))
    safe_windows = config.get("safe_egress_window", {})

    notes: list[str] = []

    # ------------------------------------------------------------------
    # Step 1 — Total vehicles (all block groups, regardless of FHSZ zone)
    # ------------------------------------------------------------------
    hu_col = _detect_hu_column(block_groups_gdf)
    total_hu = float(block_groups_gdf[hu_col].sum())
    total_vehicles = total_hu * vpu * mob
    notes.append(
        f"Total vehicles = {total_hu:,.0f} housing units x {vpu} vpu x {mob} mob = {total_vehicles:,.0f} vph"
    )

    # ------------------------------------------------------------------
    # Step 2 — Deduplicate exits: first path per exit_segment_osmid wins
    # ------------------------------------------------------------------
    exit_capacity: dict[str, float] = {}
    for path in evacuation_paths:
        osmid = _get(path, "exit_segment_osmid")
        eff_cap = float(_get(path, "bottleneck_effective_capacity_vph") or 0.0)
        if osmid and osmid not in exit_capacity:
            exit_capacity[osmid] = eff_cap

    total_exit_cap = sum(exit_capacity.values())
    notes.append(
        f"Unique exit segments: {len(exit_capacity)} — total exit capacity {total_exit_cap:,.0f} vph"
    )

    # ------------------------------------------------------------------
    # Step 3 — City-wide clearance time
    # ------------------------------------------------------------------
    if total_exit_cap > 0:
        total_clearance = (total_vehicles / total_exit_cap) * 60.0
    else:
        total_clearance = float("inf")
        notes.append("WARNING: No exit segment capacity found — clearance time is undefined.")

    # ------------------------------------------------------------------
    # Step 4 — Per-zone breakdown
    # ------------------------------------------------------------------
    # Build block group → zone assignment (area-weighted, may overlap zones)
    zone_hu = _compute_zone_housing_units(block_groups_gdf, fhsz_gdf, hu_col)

    # Build zone → set of reachable exit osmids
    zone_exits = _compute_zone_exits(block_groups_gdf, evacuation_paths, fhsz_gdf, hu_col)

    per_zone: list[ZoneClearance] = []
    for zone in ZONE_ORDER:
        z_hu = zone_hu.get(zone, 0.0)
        z_vehicles = z_hu * vpu * mob
        z_exit_osmids = zone_exits.get(zone, set())
        z_exit_cap = sum(exit_capacity.get(osmid, 0.0) for osmid in z_exit_osmids)

        if z_exit_cap > 0:
            z_clearance = (z_vehicles / z_exit_cap) * 60.0
        else:
            z_clearance = float("inf")

        window = float(safe_windows.get(zone, 120))
        ratio = z_clearance / window if z_clearance != float("inf") else float("inf")

        per_zone.append(ZoneClearance(
            zone=zone,
            zone_label=_ZONE_LABEL[zone],
            housing_units=z_hu,
            total_vehicles=z_vehicles,
            exit_capacity_vph=z_exit_cap,
            clearance_time_minutes=z_clearance,
            safe_egress_window_minutes=window,
            ratio_to_window=ratio,
            is_over_window=(ratio > 1.0),
        ))

    notes.append(
        "Per-zone clearance uses paths from block groups whose centroid overlaps "
        "each FHSZ zone. A block group straddling multiple zones is counted proportionally."
    )

    return ClearanceResult(
        total_housing_units=total_hu,
        total_vehicles=total_vehicles,
        total_exit_capacity_vph=total_exit_cap,
        total_clearance_time_minutes=total_clearance,
        per_zone=per_zone,
        methodology_notes=notes,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _detect_hu_column(gdf: gpd.GeoDataFrame) -> str:
    """Return the housing_units column name, tolerating minor naming variations."""
    for candidate in ("housing_units", "housing_units_in_city", "housing_units_total"):
        if candidate in gdf.columns:
            return candidate
    # Fall back to any column with "housing" in the name
    for col in gdf.columns:
        if "housing" in col.lower():
            return col
    raise ValueError(
        "block_groups_gdf has no recognizable housing_units column. "
        f"Available columns: {list(gdf.columns)}"
    )


def _get(obj, key: str):
    """Duck-type attribute access for EvacuationPath objects or plain dicts."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _compute_zone_housing_units(
    bg_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    hu_col: str,
) -> dict[str, float]:
    """
    Return {zone: housing_units} using area-weighted intersection of block groups
    against FHSZ polygons.

    A block group that is 60% in VHFHSZ and 40% in High FHSZ contributes 60% of
    its housing units to VHFHSZ and 40% to High.
    """
    result: dict[str, float] = defaultdict(float)

    if fhsz_gdf is None or len(fhsz_gdf) == 0:
        # No FHSZ data — treat all HUs as non_fhsz
        result["non_fhsz"] = float(bg_gdf[hu_col].sum())
        return dict(result)

    # Reproject to a common projected CRS for area calculations
    analysis_crs = "EPSG:3310"  # CA Albers, same as rest of JOSH
    bg = bg_gdf.copy().to_crs(analysis_crs)
    bg["_bg_area"] = bg.geometry.area
    bg["_bg_idx"] = range(len(bg))

    # For each FHSZ zone, compute how much of each BG falls in that zone
    fhsz = fhsz_gdf.copy().to_crs(analysis_crs)

    fhsz_accounted: pd.Series = pd.Series(0.0, index=bg.index)  # area accounted by any FHSZ

    for zone in ("vhfhsz", "high_fhsz", "moderate_fhsz"):
        haz_classes = _ZONE_HAZ_CLASS[zone]
        zone_poly = fhsz[fhsz["HAZ_CLASS"].isin(haz_classes)].copy()
        if len(zone_poly) == 0:
            result[zone] = 0.0
            continue

        # Dissolve to a single geometry for the zone (avoids double-counting overlaps)
        zone_dissolved = zone_poly.dissolve()

        # Intersect BGs with this zone
        intersected = gpd.overlay(bg, zone_dissolved, how="intersection", keep_geom_type=False)
        if len(intersected) == 0:
            result[zone] = 0.0
            continue

        intersected["_intersect_area"] = intersected.geometry.area
        # _bg_area and _bg_idx are already present from the left side of the overlay.
        # Avoid re-merging, which would create duplicate _x/_y suffixed columns.
        intersected["_frac"] = intersected["_intersect_area"] / intersected["_bg_area"].clip(lower=1.0)
        intersected["_zone_hu"] = intersected[hu_col] * intersected["_frac"]

        zone_hu = intersected.groupby("_bg_idx")["_zone_hu"].sum()
        result[zone] = float(zone_hu.sum())

        # Track how much area is accounted for (for non_fhsz remainder)
        for idx, row in intersected.iterrows():
            bg_idx = int(row["_bg_idx"])
            fhsz_accounted.iloc[bg_idx] += row["_frac"]

    # non_fhsz = housing units NOT in any FHSZ polygon
    fhsz_accounted_clamped = fhsz_accounted.clip(upper=1.0)
    bg["_non_fhsz_frac"] = (1.0 - fhsz_accounted_clamped).clip(lower=0.0)
    bg["_non_fhsz_hu"] = bg[hu_col] * bg["_non_fhsz_frac"]
    result["non_fhsz"] = float(bg["_non_fhsz_hu"].sum())

    return dict(result)


def _compute_zone_exits(
    bg_gdf: gpd.GeoDataFrame,
    evacuation_paths: list,
    fhsz_gdf: gpd.GeoDataFrame,
    hu_col: str,
) -> dict[str, set[str]]:
    """
    For each FHSZ zone, return the set of exit osmids reachable from block groups
    whose centroid is primarily in that zone.

    Uses centroid-based zone assignment (simpler than area-weighted for routing).
    """
    # Assign each BG centroid to its primary zone
    bg = bg_gdf.copy().to_crs("EPSG:3310")
    bg["_centroid"] = bg.geometry.centroid
    bg_centroids = gpd.GeoDataFrame(bg[["geometry"]], geometry="geometry", crs="EPSG:3310")
    bg_centroids.geometry = bg["_centroid"]

    geoid_col = _detect_geoid_column(bg_gdf)

    if fhsz_gdf is not None and len(fhsz_gdf) > 0:
        fhsz = fhsz_gdf.copy().to_crs("EPSG:3310")
        joined = gpd.sjoin(bg_centroids, fhsz[["HAZ_CLASS", "geometry"]], how="left", predicate="within")
        # Take max HAZ_CLASS per BG (most hazardous zone wins for centroid)
        haz = joined.groupby(joined.index)["HAZ_CLASS"].max().fillna(0).astype(int)
    else:
        haz = pd.Series(0, index=bg_gdf.index)

    def haz_to_zone(h: int) -> str:
        if h >= 3:
            return "vhfhsz"
        if h == 2:
            return "high_fhsz"
        if h == 1:
            return "moderate_fhsz"
        return "non_fhsz"

    bg["_zone"] = haz.reindex(bg.index).fillna(0).astype(int).map(haz_to_zone)
    bg[geoid_col] = bg_gdf[geoid_col].values

    geoid_to_zone = dict(zip(bg[geoid_col], bg["_zone"]))

    # Group paths by zone
    zone_exits: dict[str, set[str]] = defaultdict(set)
    for path in evacuation_paths:
        bg_geoid = _get(path, "origin_block_group")
        exit_osmid = _get(path, "exit_segment_osmid")
        if bg_geoid and exit_osmid:
            zone = geoid_to_zone.get(str(bg_geoid), "non_fhsz")
            zone_exits[zone].add(str(exit_osmid))

    return dict(zone_exits)


def _detect_geoid_column(gdf: gpd.GeoDataFrame) -> str:
    """Return the Census GEOID column name."""
    for candidate in ("GEOID", "geoid", "GEOID20", "GEOID10", "bg_geoid"):
        if candidate in gdf.columns:
            return candidate
    raise ValueError(
        "block_groups_gdf has no recognizable GEOID column. "
        f"Available columns: {list(gdf.columns)}"
    )

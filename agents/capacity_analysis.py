# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Agent 2: Capacity Analysis — JOSH v3.0

Calculates objective, verifiable evacuation route capacity metrics using
Highway Capacity Manual 2022 (HCM 2022) standards, with hazard-aware
capacity degradation for road segments in FHSZ zones.

Key outputs per road segment:
- capacity_vph          — raw HCM 2022 capacity (lanes × per-lane rate)
- fhsz_zone             — FHSZ zone for this segment
- hazard_degradation    — degradation factor for segment's zone
- effective_capacity_vph — capacity_vph × hazard_degradation
- baseline_demand_vph   — catchment-based demand (for display)
- catchment_units       — housing units routed through this segment
- vc_ratio, los         — informational only (not used in ΔT determination)
- is_evacuation_route   — boolean
- connectivity_score    — path count

Also returns a list of EvacuationPath objects capturing per-path bottleneck data.

Pipeline order (v3.0):
  1. HCM capacity per segment
  2. Hazard degradation → effective_capacity_vph (NEW in v3.0)
  3. Identify evacuation routes + bottleneck tracking (MODIFIED: uses effective_capacity)
  4. Apply baseline demand (catchment or fallback)
  5. v/c ratio and LOS (informational)
"""
import json
import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import Point

from models.evacuation_path import EvacuationPath

logger = logging.getLogger(__name__)

# Zone label → canonical hazard_zone key (matches hazard_degradation keys in parameters.yaml)
_HAZ_CLASS_TO_ZONE = {
    3: "vhfhsz",
    2: "high_fhsz",
    1: "moderate_fhsz",
    0: "non_fhsz",
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_capacity(
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    config: dict,
    city_config: dict,
    block_groups_gdf: Optional[gpd.GeoDataFrame] = None,
    data_dir: Optional[Path] = None,
) -> tuple[gpd.GeoDataFrame, list]:
    """
    Run full capacity analysis pipeline on a road network.

    Pipeline (v3.0):
      1. HCM 2022 capacity per segment
      2. Hazard-aware capacity degradation (effective_capacity_vph)
      3. Identify evacuation routes; compute catchment and bottleneck per path
      4. Calculate baseline demand (catchment-based or fallback)
      5. Calculate v/c ratio and LOS (informational)

    Returns:
        (roads_gdf enriched with capacity columns, list of EvacuationPath objects)
    """
    analysis_crs = city_config.get("analysis_crs", "EPSG:26910")

    logger.info(f"Analyzing capacity for {len(roads_gdf)} road segments...")

    # Step 1: HCM Capacity
    roads_gdf = _apply_hcm_capacity(roads_gdf, config)

    # Step 2: Hazard Degradation (NEW in v3.0)
    roads_gdf = _apply_hazard_degradation(roads_gdf, fhsz_gdf, config, analysis_crs)

    # Step 3: Evacuation routes + catchment weights + bottleneck tracking
    roads_gdf, evacuation_paths = _identify_evacuation_routes(
        roads_gdf, fhsz_gdf, boundary_gdf, config, analysis_crs, block_groups_gdf
    )

    # Step 4: Baseline demand
    if (
        block_groups_gdf is not None
        and not block_groups_gdf.empty
        and "demand" in config
    ):
        roads_gdf = _apply_buffer_demand(roads_gdf, block_groups_gdf, config, analysis_crs)
        roads_gdf["evacuation_demand_vph"] = roads_gdf["baseline_demand_vph"]

    roads_gdf = _apply_baseline_demand(roads_gdf, config)

    # Step 5: v/c ratio and LOS (informational)
    roads_gdf["vc_ratio"] = roads_gdf.apply(
        lambda r: calculate_vc_ratio(r["baseline_demand_vph"], r["capacity_vph"]),
        axis=1,
    )
    roads_gdf["los"] = roads_gdf["vc_ratio"].apply(
        lambda vc: assign_los(vc, config)
    )

    # Persist evacuation paths if data_dir provided
    if data_dir is not None and evacuation_paths:
        paths_file = Path(data_dir) / "evacuation_paths.json"
        paths_file.parent.mkdir(parents=True, exist_ok=True)
        paths_file.write_text(
            json.dumps([p.to_dict() for p in evacuation_paths], indent=2)
        )
        logger.info(f"  Saved {len(evacuation_paths)} evacuation paths → {paths_file}")

    evac_count = roads_gdf["is_evacuation_route"].sum()
    logger.info(
        f"Capacity analysis complete. {evac_count} evacuation route segments. "
        f"{len(evacuation_paths)} bottleneck paths computed."
    )
    return roads_gdf, evacuation_paths


# ---------------------------------------------------------------------------
# Step 1: HCM 2022 Capacity
# ---------------------------------------------------------------------------

def _apply_hcm_capacity(gdf: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    """Calculate capacity_vph for every road segment using HCM 2022 formulas."""
    gdf["capacity_vph"] = gdf.apply(
        lambda r: calculate_hcm_capacity(
            r["road_type"],
            r["lane_count"],
            r["speed_limit"],
            config,
        ),
        axis=1,
    )
    return gdf


def calculate_hcm_capacity(
    road_type: str,
    lanes: int,
    speed: int,
    config: dict,
) -> float:
    """
    Calculate road segment capacity in passenger cars per hour (pc/h).

    Source: Highway Capacity Manual 2022 (HCM 7th Edition)
    - Freeway: 2,250 pc/h per lane (Ch. 12, Exhibit 12-6)
    - Multilane: 1,900 pc/h per lane (Ch. 12, Exhibit 12-7)
    - Two-lane: speed-dependent lookup (Ch. 15)
    """
    hcm = config.get("hcm_capacity", {})

    if road_type == "freeway":
        cap_per_lane = hcm.get("freeway", {}).get("capacity_per_lane", 2250)
        return cap_per_lane * max(lanes, 1)

    if road_type == "multilane":
        cap_per_lane = hcm.get("multilane", {}).get("capacity_per_lane", 1900)
        return cap_per_lane * max(lanes, 1)

    if road_type == "two_lane":
        by_speed = hcm.get("two_lane", {}).get("by_speed", {})
        by_speed_int = {int(k): v for k, v in by_speed.items()}
        valid_thresholds = sorted(k for k in by_speed_int if k <= speed)
        if valid_thresholds:
            return float(by_speed_int[valid_thresholds[-1]])
        all_thresholds = sorted(by_speed_int.keys())
        if all_thresholds:
            return float(by_speed_int[all_thresholds[0]])
        return 900.0

    logger.warning(f"Unknown road_type '{road_type}' — capacity set to 0.")
    return 0.0


# ---------------------------------------------------------------------------
# Step 2: Hazard-Aware Capacity Degradation (NEW in v3.0)
# ---------------------------------------------------------------------------

def _apply_hazard_degradation(
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    config: dict,
    analysis_crs: str,
) -> gpd.GeoDataFrame:
    """
    Assign FHSZ zone and hazard degradation factor to each road segment.

    Method: Spatial join — for each road segment, find the FHSZ zone it intersects.
    Segments outside any FHSZ zone get factor 1.0 (non_fhsz).

    effective_capacity_vph = capacity_vph × hazard_degradation

    Source: HCM composite factors (Exhibit 10-15 visibility + Exhibit 10-17 incident).
    See config/parameters.yaml hazard_degradation for full derivation.
    """
    deg_cfg = config.get("hazard_degradation", {})
    enabled = deg_cfg.get("enabled", True)
    factors = deg_cfg.get("factors", {
        "vhfhsz": 0.35, "high_fhsz": 0.50, "moderate_fhsz": 0.75, "non_fhsz": 1.00
    })

    # Initialize defaults
    roads_gdf = roads_gdf.copy()
    roads_gdf["fhsz_zone"]            = "non_fhsz"
    roads_gdf["hazard_degradation"]   = 1.0
    roads_gdf["effective_capacity_vph"] = roads_gdf["capacity_vph"]

    if not enabled or fhsz_gdf.empty:
        logger.info("  Hazard degradation: disabled or no FHSZ data — all factors = 1.0")
        return roads_gdf

    logger.info("  Applying hazard degradation to road segments...")

    # Project to analysis CRS for spatial join
    roads_proj = roads_gdf.to_crs(analysis_crs)
    fhsz_proj  = fhsz_gdf.to_crs(analysis_crs)

    # Build HAZ_CLASS → zone key mapping
    # HAZ_CLASS in data: integer 1=Moderate, 2=High, 3=VeryHigh
    joined = gpd.sjoin(
        roads_proj[["geometry"]].reset_index(),
        fhsz_proj[["geometry", "HAZ_CLASS"]],
        how="left",
        predicate="intersects",
    )

    # For segments intersecting multiple zones, take the highest (most restrictive)
    if "HAZ_CLASS" in joined.columns:
        joined["HAZ_CLASS"] = pd.to_numeric(joined["HAZ_CLASS"], errors="coerce")
        zone_max = joined.groupby("index")["HAZ_CLASS"].max()
        roads_gdf["_haz_class"] = roads_gdf.index.map(zone_max).fillna(0).astype(int)
    else:
        roads_gdf["_haz_class"] = 0

    def _haz_to_zone(haz: int) -> str:
        return _HAZ_CLASS_TO_ZONE.get(haz, "non_fhsz")

    roads_gdf["fhsz_zone"] = roads_gdf["_haz_class"].apply(_haz_to_zone)
    roads_gdf["hazard_degradation"] = roads_gdf["fhsz_zone"].map(factors).fillna(1.0)
    roads_gdf["effective_capacity_vph"] = roads_gdf["capacity_vph"] * roads_gdf["hazard_degradation"]
    roads_gdf = roads_gdf.drop(columns=["_haz_class"])

    zone_counts = roads_gdf["fhsz_zone"].value_counts()
    logger.info(f"  Degradation applied: {dict(zone_counts)}")
    degraded = (roads_gdf["hazard_degradation"] < 1.0).sum()
    logger.info(f"  {degraded} segments with degradation factor < 1.0")

    return roads_gdf


# ---------------------------------------------------------------------------
# Step 4: Baseline Demand
# ---------------------------------------------------------------------------

def _apply_baseline_demand(gdf: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    """
    Calculate catchment_demand_vph, baseline_demand_vph, and normal_demand_vph.

    Three demand columns:
      catchment_demand_vph — raw demand with NO mob applied (mob applied at test time)
      baseline_demand_vph  — evac demand for display (×0.57)
      normal_demand_vph    — normal peak-hour (×0.10)

    Note: v3.2 uses a constant mobilization rate (0.90, NFPA 101 design basis) for
    both baseline display and the ΔT engine. FHSZ zone affects road capacity only.
    """
    method      = config.get("evacuation_demand", {}).get("method", "catchment")
    peak_factor = config.get("aadt_peak_hour_factor", 0.10)
    vpu         = config.get("vehicles_per_unit", 2.5)
    mob         = config.get("mobilization_rate", 0.90)  # v3.2: NFPA 101, constant
    aadt_col    = "aadt" if "aadt" in gdf.columns else None
    has_catchment = "catchment_units" in gdf.columns

    catchment_demands = []
    demands           = []
    normal_demands    = []
    sources           = []
    estimated         = []

    for _, row in gdf.iterrows():
        if aadt_col and pd.notna(row.get(aadt_col)):
            d = float(row[aadt_col]) * peak_factor
            catchment_demands.append(d / mob if mob > 0 else d)
            demands.append(d)
            normal_demands.append(d)
            sources.append("aadt")
            estimated.append(False)
        elif (
            method == "catchment"
            and row.get("is_evacuation_route", False)
            and has_catchment
            and pd.notna(row.get("catchment_units"))
            and row["catchment_units"] > 0
        ):
            cu = float(row["catchment_units"])
            catchment_demands.append(cu * vpu)
            demands.append(cu * vpu * mob)
            normal_demands.append(cu * vpu * peak_factor)
            sources.append("catchment_based")
            estimated.append(True)
        else:
            d = _estimate_demand_from_road_class(row["road_type"], row["capacity_vph"])
            catchment_demands.append(d / mob if mob > 0 else d)
            demands.append(d)
            normal_demands.append(d)
            sources.append("road_class_estimated")
            estimated.append(True)

    gdf["catchment_demand_vph"] = catchment_demands
    gdf["baseline_demand_vph"]  = demands
    gdf["normal_demand_vph"]    = normal_demands
    gdf["demand_source"]        = sources
    gdf["aadt_estimated"]       = estimated
    return gdf


def _apply_buffer_demand(
    roads_gdf: gpd.GeoDataFrame,
    block_groups_gdf: gpd.GeoDataFrame,
    config: dict,
    analysis_crs: str = "EPSG:26910",
) -> gpd.GeoDataFrame:
    """
    KLD-style buffer demand — informational only (stored as evacuation_demand_vph).
    Not used in ΔT determination.
    """
    demand_cfg = config.get("demand", {})
    buffer_m   = demand_cfg.get("buffer_radius_miles", 0.25) * 1609.344
    res_mob    = demand_cfg.get("resident_mobilization", 0.57)
    emp_mob    = demand_cfg.get("employee_mobilization_day", 1.00)
    stu_mob    = demand_cfg.get("student_mobilization_day", 1.00)
    vpu        = demand_cfg.get("vehicles_per_unit", config.get("vehicles_per_unit", 2.5))
    emp_occ    = demand_cfg.get("employee_vehicle_occupancy", 1.0)

    logger.info(
        f"  Applying buffer demand (radius={buffer_m:.0f}m, "
        f"res_mob={res_mob}, emp_mob={emp_mob}) — informational only..."
    )

    roads_proj = roads_gdf.to_crs(analysis_crs)
    bg_proj = block_groups_gdf.to_crs(analysis_crs).copy()

    for col in ("employee_count", "student_count"):
        if col not in bg_proj.columns:
            bg_proj[col] = 0.0
        else:
            bg_proj[col] = pd.to_numeric(bg_proj[col], errors="coerce").fillna(0)
    bg_proj["housing_units_in_city"] = pd.to_numeric(
        bg_proj["housing_units_in_city"], errors="coerce"
    ).fillna(0)

    bg_for_join = bg_proj[["geometry", "housing_units_in_city", "employee_count", "student_count"]].copy()

    roads_buf = gpd.GeoDataFrame(
        {"geometry": roads_proj.geometry.buffer(buffer_m), "_pos": range(len(roads_proj))},
        crs=analysis_crs,
    )

    joined = gpd.sjoin(roads_buf[["geometry", "_pos"]], bg_for_join, how="left", predicate="intersects")
    agg = joined.groupby("_pos")[["housing_units_in_city", "employee_count", "student_count"]].sum()
    n = len(roads_gdf)
    hu_arr  = agg["housing_units_in_city"].reindex(range(n), fill_value=0).values
    emp_arr = agg["employee_count"].reindex(range(n), fill_value=0).values
    stu_arr = agg["student_count"].reindex(range(n), fill_value=0).values

    roads_gdf = roads_gdf.copy()
    roads_gdf["catchment_hu"]        = hu_arr
    roads_gdf["catchment_employees"] = emp_arr
    roads_gdf["resident_demand_vph"] = hu_arr * vpu * res_mob
    roads_gdf["employee_demand_vph"] = emp_arr * emp_occ * emp_mob
    roads_gdf["student_demand_vph"]  = stu_arr * emp_occ * stu_mob
    roads_gdf["baseline_demand_vph"] = (
        roads_gdf["resident_demand_vph"]
        + roads_gdf["employee_demand_vph"]
        + roads_gdf["student_demand_vph"]
    )
    roads_gdf["demand_source"] = "census_buffer"

    if "catchment_units" not in roads_gdf.columns:
        roads_gdf["catchment_units"] = 0.0

    return roads_gdf


def _estimate_demand_from_road_class(road_type: str, capacity_vph: float) -> float:
    utilization = {"freeway": 0.50, "multilane": 0.40, "two_lane": 0.25}
    rate = utilization.get(road_type, 0.25)
    return capacity_vph * rate


# ---------------------------------------------------------------------------
# Step 5: v/c Ratio and LOS (informational)
# ---------------------------------------------------------------------------

def calculate_vc_ratio(demand: float, capacity: float) -> float:
    if capacity <= 0:
        return 0.0
    return demand / capacity


def assign_los(vc: float, config: dict) -> str:
    thresholds = config.get("los_thresholds", {
        "A": 0.10, "B": 0.20, "C": 0.40, "D": 0.60, "E": 0.95,
    })
    for grade in ["A", "B", "C", "D", "E"]:
        if vc <= thresholds.get(grade, 1.0):
            return grade
    return "F"


# ---------------------------------------------------------------------------
# Step 3: Evacuation Route Identification + Bottleneck Tracking
# ---------------------------------------------------------------------------

def _identify_evacuation_routes(
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    config: dict,
    analysis_crs: str,
    block_groups_gdf: Optional[gpd.GeoDataFrame] = None,
) -> tuple[gpd.GeoDataFrame, list]:
    """
    Identify evacuation routes via Dijkstra network analysis.

    v3.0 modifications:
    - Dijkstra weights use effective_capacity_vph (not raw capacity) where available.
      This routes around degraded segments in fire zones — more realistic.
    - During path traversal, tracks bottleneck_segment per path:
        bottleneck = argmin(effective_capacity_vph) along the path
    - Returns list of EvacuationPath objects alongside the enriched roads_gdf.

    Returns:
        (roads_gdf with is_evacuation_route/connectivity_score/catchment_units,
         list[EvacuationPath])
    """
    roads_gdf["is_evacuation_route"] = False
    roads_gdf["connectivity_score"]  = 0
    roads_gdf["catchment_units"]     = 0.0

    trigger_zones = config.get("fhsz", {}).get("trigger_zones", [2, 3])
    max_origins   = int(config.get("census", {}).get("max_origins", 100))

    if fhsz_gdf.empty:
        logger.warning("FHSZ data is empty — skipping evacuation route identification.")
        return roads_gdf, []

    fhsz_trigger = fhsz_gdf[fhsz_gdf["HAZ_CLASS"].isin(trigger_zones)]
    if fhsz_trigger.empty:
        logger.warning(f"No FHSZ zones {trigger_zones} found — no evacuation routes identified.")
        return roads_gdf, []

    fhsz_proj     = fhsz_trigger.to_crs(analysis_crs)
    boundary_proj = boundary_gdf.to_crs(analysis_crs)

    place_boundary = boundary_gdf.unary_union
    logger.info("Building road graph for network analysis...")
    try:
        G = ox.graph_from_polygon(place_boundary, network_type="drive", simplify=True)
    except Exception as e:
        logger.error(f"Failed to build road graph: {e}")
        return roads_gdf, []

    G_proj  = ox.project_graph(G, to_crs=analysis_crs)
    G_undir = G_proj.to_undirected()

    exits = _find_exit_nodes(G_proj, boundary_proj)
    logger.info(f"  Found {len(exits)} potential exit nodes.")
    if not exits:
        logger.warning("  No exit nodes found — skipping route identification.")
        return roads_gdf, []

    VIRTUAL_SINK = -999999
    G_undir.add_node(VIRTUAL_SINK)
    for exit_node in exits:
        G_undir.add_edge(exit_node, VIRTUAL_SINK, length=0)

    # Build osmid → effective_capacity lookup for bottleneck computation
    # Map str(osmid) → effective_capacity_vph from the GDF
    # HCM audit fields: lanes, speed, haz_class let reviewers verify HCM table lookup.
    _ZONE_TO_HAZ_CLASS = {"vhfhsz": 3, "high_fhsz": 2, "moderate_fhsz": 1, "non_fhsz": 0}
    osmid_to_eff_cap  = {}
    osmid_to_fhsz     = {}
    osmid_to_rtype    = {}
    osmid_to_hcm      = {}
    osmid_to_deg      = {}
    osmid_to_name     = {}
    osmid_to_lanes    = {}   # lane_count at segment (HCM audit)
    osmid_to_speed    = {}   # speed_limit at segment (HCM two-lane row selection)
    osmid_to_haz_class = {}  # raw CAL FIRE HAZ_CLASS integer (FHSZ audit)
    for _, row in roads_gdf.iterrows():
        oid  = row.get("osmid")
        eff  = float(row.get("effective_capacity_vph", row.get("capacity_vph", 1000.0)))
        fz   = str(row.get("fhsz_zone", "non_fhsz"))
        rt   = str(row.get("road_type", "two_lane"))
        hcm  = float(row.get("capacity_vph", 0.0))
        dg   = float(row.get("hazard_degradation", 1.0))
        nm   = str(row.get("name", ""))
        lc   = int(row.get("lane_count", 0) or 0)
        sp   = int(row.get("speed_limit", 0) or 0)
        hc   = _ZONE_TO_HAZ_CLASS.get(fz, 0)
        if oid is None:
            continue
        if isinstance(oid, list):
            for o in oid:
                key = str(o)
                osmid_to_eff_cap[key]   = max(osmid_to_eff_cap.get(key, 0), eff)
                osmid_to_fhsz[key]      = fz
                osmid_to_rtype[key]     = rt
                osmid_to_hcm[key]       = hcm
                osmid_to_deg[key]       = dg
                osmid_to_name[key]      = nm
                osmid_to_lanes[key]     = lc
                osmid_to_speed[key]     = sp
                osmid_to_haz_class[key] = hc
        else:
            key = str(oid)
            osmid_to_eff_cap[key]   = max(osmid_to_eff_cap.get(key, 0), eff)
            osmid_to_fhsz[key]      = fz
            osmid_to_rtype[key]     = rt
            osmid_to_hcm[key]       = hcm
            osmid_to_deg[key]       = dg
            osmid_to_name[key]      = nm
            osmid_to_lanes[key]     = lc
            osmid_to_speed[key]     = sp
            osmid_to_haz_class[key] = hc

    origins, weights = _resolve_origins(
        block_groups_gdf, fhsz_proj, analysis_crs, max_origins, config
    )
    if not origins:
        logger.warning("  No origin points found — skipping route identification.")
        return roads_gdf, []

    total_weight = sum(weights)
    using_housing_units = (
        block_groups_gdf is not None
        and not block_groups_gdf.empty
        and total_weight > len(origins)
    )
    logger.info(
        f"  Using {len(origins)} origin points "
        f"({'housing-unit-weighted' if using_housing_units else 'uniform'})."
    )

    origin_xs    = [p.x for p in origins]
    origin_ys    = [p.y for p in origins]
    origin_nodes = ox.distance.nearest_nodes(G_proj, X=origin_xs, Y=origin_ys)

    # Get block group GEOIDs if available
    bg_geoids = []
    if block_groups_gdf is not None and not block_groups_gdf.empty:
        bg_sorted = block_groups_gdf.sort_values(
            "housing_units_in_city", ascending=False
        ).head(max_origins)
        bg_geoids = bg_sorted.get("GEOID", bg_sorted.index.astype(str)).tolist()
    bg_geoids = list(bg_geoids) + [""] * max(0, len(origin_nodes) - len(bg_geoids))

    logger.info(f"  Computing shortest paths for {len(origin_nodes)} origins...")

    edge_use_counts  = {}
    edge_unit_weights = {}
    evacuation_paths: list[EvacuationPath] = []

    paths_found = 0
    for i, (origin_node, weight, geoid) in enumerate(
        zip(origin_nodes, weights, bg_geoids)
    ):
        try:
            path_nodes = nx.shortest_path(
                G_undir, origin_node, VIRTUAL_SINK, weight="length"
            )
            path_nodes = path_nodes[:-1]   # remove virtual sink
            if len(path_nodes) < 2:
                continue

            # Collect edge osmids along this path
            path_osmids: list[str] = []
            exit_osmid = ""
            for u, v in zip(path_nodes[:-1], path_nodes[1:]):
                key = (min(u, v), max(u, v))
                edge_use_counts[key]   = edge_use_counts.get(key, 0) + 1
                edge_unit_weights[key] = edge_unit_weights.get(key, 0) + weight

                # Get osmid for this edge
                ed = G_proj.get_edge_data(u, v) or G_proj.get_edge_data(v, u)
                if ed:
                    for kd in (ed.values() if isinstance(ed, dict) else [ed]):
                        oid = kd.get("osmid")
                        if oid:
                            oid_str = str(oid[0]) if isinstance(oid, list) else str(oid)
                            path_osmids.append(oid_str)
                            break

                # Track last edge as exit
                if v in exits or u in exits:
                    exit_osmid = path_osmids[-1] if path_osmids else ""

            if not path_osmids:
                continue

            # Find bottleneck: segment with min effective_capacity along this path
            bottleneck_osmid = min(
                path_osmids,
                key=lambda o: osmid_to_eff_cap.get(o, 9999),
                default=path_osmids[0],
            )
            eff_cap  = osmid_to_eff_cap.get(bottleneck_osmid, 0.0)
            hcm_cap  = osmid_to_hcm.get(bottleneck_osmid, eff_cap)
            deg      = osmid_to_deg.get(bottleneck_osmid, 1.0)
            fz       = osmid_to_fhsz.get(bottleneck_osmid, "non_fhsz")
            rt       = osmid_to_rtype.get(bottleneck_osmid, "two_lane")
            nm       = osmid_to_name.get(bottleneck_osmid, "")
            lc       = osmid_to_lanes.get(bottleneck_osmid, 0)
            sp       = osmid_to_speed.get(bottleneck_osmid, 0)
            hc       = osmid_to_haz_class.get(bottleneck_osmid, 0)

            path_id = f"{geoid or i}_{exit_osmid or path_nodes[-1]}"

            evac_path = EvacuationPath(
                path_id=path_id,
                origin_block_group=str(geoid),
                exit_segment_osmid=exit_osmid,
                bottleneck_osmid=bottleneck_osmid,
                bottleneck_name=nm,
                bottleneck_fhsz_zone=fz,
                bottleneck_road_type=rt,
                bottleneck_hcm_capacity_vph=hcm_cap,
                bottleneck_hazard_degradation=deg,
                bottleneck_effective_capacity_vph=eff_cap,
                bottleneck_lane_count=lc,
                bottleneck_speed_limit=sp,
                bottleneck_haz_class=hc,
                path_osmids=path_osmids,
            )
            evacuation_paths.append(evac_path)
            paths_found += 1

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        except Exception as e:
            logger.debug(f"  Path computation error: {e}")
            continue

    logger.info(f"  Paths found: {paths_found}/{len(origin_nodes)}")

    if not edge_use_counts:
        logger.warning("  No evacuation paths found.")
        return roads_gdf, []

    evac_osmids_count = _build_evac_osmid_map(G_proj, edge_use_counts)
    evac_osmids_units = _build_evac_osmid_map(G_proj, edge_unit_weights)

    def _match(osmid_val, lookup):
        if isinstance(osmid_val, list):
            return any(str(o) in lookup for o in osmid_val)
        return str(osmid_val) in lookup

    def _score(osmid_val, lookup, default=0):
        if isinstance(osmid_val, list):
            return max((lookup.get(str(o), default) for o in osmid_val), default=default)
        return lookup.get(str(osmid_val), default)

    roads_gdf["is_evacuation_route"] = roads_gdf["osmid"].apply(
        lambda o: _match(o, evac_osmids_count)
    )
    roads_gdf["connectivity_score"] = roads_gdf["osmid"].apply(
        lambda o: _score(o, evac_osmids_count)
    )

    if using_housing_units:
        roads_gdf["catchment_units"] = roads_gdf["osmid"].apply(
            lambda o: _score(o, evac_osmids_units, default=0.0)
        )
    else:
        roads_gdf["catchment_units"] = 0.0

    logger.info(
        f"  Marked {roads_gdf['is_evacuation_route'].sum()} evacuation route segments."
    )
    return roads_gdf, evacuation_paths


def _resolve_origins(
    block_groups_gdf: Optional[gpd.GeoDataFrame],
    fhsz_proj: gpd.GeoDataFrame,
    analysis_crs: str,
    max_origins: int,
    config: dict,
) -> tuple[list, list]:
    if block_groups_gdf is not None and not block_groups_gdf.empty:
        if "housing_units_in_city" in block_groups_gdf.columns:
            bg_proj = block_groups_gdf.to_crs(analysis_crs)
            origins, weights = _sample_block_group_origins(bg_proj, max_origins)
            if origins and sum(weights) > 0:
                return origins, weights
            logger.warning("  Block groups have no city housing units — falling back to FHSZ sampling.")

    origins = _sample_fhsz_centroids(fhsz_proj, max_points=max_origins)
    weights = [1.0] * len(origins)
    return origins, weights


def _sample_block_group_origins(
    bg_proj: gpd.GeoDataFrame,
    max_origins: int = 100,
) -> tuple[list, list]:
    city_bgs = bg_proj[bg_proj["housing_units_in_city"] > 0].copy()
    if city_bgs.empty:
        return [], []
    city_bgs = city_bgs.sort_values("housing_units_in_city", ascending=False)
    if len(city_bgs) > max_origins:
        logger.info(
            f"  {len(city_bgs)} block groups; using top {max_origins} by housing unit count."
        )
        city_bgs = city_bgs.head(max_origins)
    points  = []
    weights = []
    for _, row in city_bgs.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        pt = row.geometry.representative_point()
        points.append(pt)
        weights.append(float(row["housing_units_in_city"]))
    return points, weights


def _sample_fhsz_centroids(fhsz_proj: gpd.GeoDataFrame, max_points: int = 100) -> list:
    all_points = []
    for geom in fhsz_proj.geometry:
        if geom.is_empty:
            continue
        minx, miny, maxx, maxy = geom.bounds
        width  = maxx - minx
        height = abs(maxy - miny)
        step   = max(min(width, height) / 3.0, 50)
        xs = np.arange(minx + step / 2, maxx, step)
        ys = np.arange(miny + step / 2, maxy, step)
        for x in xs:
            for y in ys:
                pt = Point(x, y)
                if geom.contains(pt):
                    all_points.append(pt)
        rep = geom.representative_point()
        if not rep.is_empty:
            all_points.append(rep)
    if len(all_points) > max_points:
        step = len(all_points) // max_points
        all_points = all_points[::step][:max_points]
    return all_points


def _find_exit_nodes(G_proj, boundary_proj: gpd.GeoDataFrame) -> list:
    boundary_geom = boundary_proj.unary_union.boundary
    node_data     = [(n, d["x"], d["y"]) for n, d in G_proj.nodes(data=True)]
    return [
        node_id for node_id, x, y in node_data
        if boundary_geom.distance(Point(x, y)) < 50
    ]


def _build_evac_osmid_map(G_proj, edge_scores: dict) -> dict:
    osmid_map = {}
    for (u, v), score in edge_scores.items():
        edge_data = G_proj.get_edge_data(u, v) or G_proj.get_edge_data(v, u)
        if edge_data is None:
            continue
        for key_data in (edge_data.values() if isinstance(edge_data, dict) else [edge_data]):
            osmid = key_data.get("osmid")
            if osmid is None:
                continue
            if isinstance(osmid, list):
                for o in osmid:
                    osmid_map[str(o)] = max(osmid_map.get(str(o), 0), score)
            else:
                osmid_map[str(osmid)] = max(osmid_map.get(str(osmid), 0), score)
    return osmid_map

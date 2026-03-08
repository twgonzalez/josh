"""
Agent 2: Capacity Analysis

Calculates objective, verifiable evacuation route capacity metrics using
Highway Capacity Manual 2022 (HCM 2022) standards.

All calculations are documented and reproducible. Estimated values are flagged.

Key outputs:
- capacity_vph per road segment (HCM 2022)
- baseline_demand_vph — catchment-based evacuation demand when Census data
  is available; AADT or road-class estimate otherwise
- catchment_units — FHSZ housing units whose evacuation paths use each segment
- demand_source — "catchment_based" | "aadt" | "road_class_estimated"
- vc_ratio and LOS (A-F)
- evacuation route identification via network analysis (NetworkX)
- connectivity_score per segment (path count)

Demand method:
  "catchment" (default): demand = catchment_units × vehicles_per_unit × peak_hour_mobilization
  "road_class" (fallback): flat utilization rate by road class

Pipeline order (new):
  1. HCM capacity per segment
  2. Identify evacuation routes + compute housing-unit-weighted catchment
  3. Apply baseline demand (catchment or fallback)
  4. v/c ratio and LOS
"""
import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import Point

logger = logging.getLogger(__name__)


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
) -> gpd.GeoDataFrame:
    """
    Run full capacity analysis pipeline on a road network.

    Pipeline:
      1. Calculate HCM 2022 capacity per segment
      2. Identify evacuation routes via network analysis;
         compute housing-unit-weighted catchment per segment
      3. Calculate baseline demand (catchment-based or fallback)
      4. Calculate v/c ratio and LOS

    block_groups_gdf: Census block groups with housing_units_in_fhsz column.
      If provided and non-empty, enables catchment-based evacuation demand.
      If None or empty, falls back to road-class utilization estimates.

    Returns the enriched GeoDataFrame with all capacity columns added.
    """
    analysis_crs = city_config.get("analysis_crs", "EPSG:26910")

    logger.info(f"Analyzing capacity for {len(roads_gdf)} road segments...")

    # Step 1: HCM Capacity
    roads_gdf = _apply_hcm_capacity(roads_gdf, config)

    # Step 2: Evacuation routes + catchment weights
    # (must precede demand calculation so catchment_units is available)
    roads_gdf = _identify_evacuation_routes(
        roads_gdf, fhsz_gdf, boundary_gdf, config, analysis_crs, block_groups_gdf
    )

    # Step 3: Baseline demand
    # CLAUDE.md item 2: Use catchment-based demand (network path analysis) as baseline_demand_vph
    # for Standard 4 marginal impact test. The KLD simultaneous-evacuation buffer model is
    # appropriate for citywide infrastructure sizing but produces 30-40× overload at the
    # project level, making the marginal causation test impossible to satisfy.
    #
    # KLD buffer demand (if available) is stored in evacuation_demand_vph for informational
    # purposes (citywide planning) but NOT used as baseline for Standard 4.
    if (
        block_groups_gdf is not None
        and not block_groups_gdf.empty
        and "demand" in config
    ):
        roads_gdf = _apply_buffer_demand(roads_gdf, block_groups_gdf, config, analysis_crs)
        # Preserve KLD buffer demand separately; baseline_demand_vph will be overwritten below
        roads_gdf["evacuation_demand_vph"] = roads_gdf["baseline_demand_vph"]

    # Catchment-based or road-class demand for project-level marginal analysis (Standard 4)
    roads_gdf = _apply_baseline_demand(roads_gdf, config)
    demand_method = config.get("evacuation_demand", {}).get("method", "catchment")

    # Step 4: v/c ratio and LOS
    roads_gdf["vc_ratio"] = roads_gdf.apply(
        lambda r: calculate_vc_ratio(r["baseline_demand_vph"], r["capacity_vph"]),
        axis=1,
    )
    roads_gdf["los"] = roads_gdf["vc_ratio"].apply(
        lambda vc: assign_los(vc, config)
    )

    evac_count = roads_gdf["is_evacuation_route"].sum()
    logger.info(
        f"Capacity analysis complete. {evac_count} evacuation route segments. "
        f"Demand method: {demand_method} (AADT proxy for Standard 4 marginal test)."
    )
    return roads_gdf


# ---------------------------------------------------------------------------
# HCM 2022 Capacity
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
    - Freeway: 2,250 pc/h per lane (Table 12-2, conservative estimate)
    - Multilane: 1,900 pc/h per lane (Table 14-2)
    - Two-lane: speed-dependent lookup (Table 15-2)

    Returns 0.0 if road_type is unknown (logged as warning).
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
# Baseline Demand
# ---------------------------------------------------------------------------

def _apply_baseline_demand(gdf: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    """
    Calculate catchment_demand_vph, baseline_demand_vph, and normal_demand_vph for every segment.

    Three demand columns are produced:
      catchment_demand_vph — raw per-unit demand with NO mobilization factor applied
        catchment formula: catchment_units × vpu
        AADT/road-class formula: baseline_demand_vph / peak_hour_mobilization (approximate raw)
        Used by ratio_test() with scenario-specific mob_factor at test time.

      baseline_demand_vph — evacuation-scenario demand (for vc_ratio map display)
        catchment formula: catchment_units × vpu × peak_hour_mobilization (0.57)

      normal_demand_vph — normal peak-hour demand (for display reference)
        catchment formula: catchment_units × vpu × aadt_peak_hour_factor  (0.10)

    Priority 1 (AADT) and Priority 3 (road-class fallback) produce identical values
    for baseline_demand_vph and normal_demand_vph — AADT already reflects real observed
    traffic under normal conditions.  catchment_demand_vph is reconstructed as
    baseline_demand_vph / mob so that multiplying by mob at test time recovers the
    AADT-equivalent demand.

    Also sets demand_source and aadt_estimated columns.
    """
    method      = config.get("evacuation_demand", {}).get("method", "catchment")
    peak_factor = config.get("aadt_peak_hour_factor", 0.10)
    vpu         = config.get("vehicles_per_unit", 2.5)
    mob         = config.get("peak_hour_mobilization", 0.57)
    aadt_col    = "aadt" if "aadt" in gdf.columns else None

    has_catchment = "catchment_units" in gdf.columns

    catchment_demands = []   # raw demand (no mob) → catchment_demand_vph
    demands           = []   # evacuation demand    → baseline_demand_vph
    normal_demands    = []   # normal peak-hour     → normal_demand_vph
    sources           = []
    estimated         = []

    for _, row in gdf.iterrows():
        # Priority 1: Measured AADT — normal traffic; same for both demand columns
        if aadt_col and pd.notna(row.get(aadt_col)):
            d = float(row[aadt_col]) * peak_factor
            catchment_demands.append(d / mob if mob > 0 else d)  # reconstruct raw
            demands.append(d)
            normal_demands.append(d)
            sources.append("aadt")
            estimated.append(False)

        # Priority 2: Catchment-based (evacuation routes with census data)
        # catchment_demand_vph is raw (no mob); baseline uses 0.57; normal uses 0.10
        elif (
            method == "catchment"
            and row.get("is_evacuation_route", False)
            and has_catchment
            and pd.notna(row.get("catchment_units"))
            and row["catchment_units"] > 0
        ):
            cu = float(row["catchment_units"])
            catchment_demands.append(cu * vpu)                    # raw: no mob
            demands.append(cu * vpu * mob)                        # evac: ×0.57
            normal_demands.append(cu * vpu * peak_factor)         # normal: ×0.10
            sources.append("catchment_based")
            estimated.append(True)

        # Priority 3: Road-class flat rate — same for both demand columns
        else:
            d = _estimate_demand_from_road_class(row["road_type"], row["capacity_vph"])
            catchment_demands.append(d / mob if mob > 0 else d)  # reconstruct raw
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
    Assign demand to each road segment from all residents + employees + students
    within a quarter-mile buffer. Matches KLD Engineering AB 747 methodology.

    Applied to ALL road segments (not just evacuation routes).

    Formula per segment:
      resident_demand_vph  = catchment_hu × vehicles_per_unit × resident_mobilization
      employee_demand_vph  = catchment_employees × employee_vehicle_occupancy × employee_mobilization_day
      student_demand_vph   = student_count × employee_vehicle_occupancy × student_mobilization_day
      baseline_demand_vph  = resident + employee + student

    Source: KLD Engineering TR-1381, Berkeley AB 747 Study, March 2024.
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
        f"res_mob={res_mob}, emp_mob={emp_mob})..."
    )

    # Project to analysis CRS for accurate buffering
    roads_proj = roads_gdf.to_crs(analysis_crs)
    bg_proj = block_groups_gdf.to_crs(analysis_crs).copy()

    # Ensure employee/student columns exist with numeric values
    for col in ("employee_count", "student_count"):
        if col not in bg_proj.columns:
            bg_proj[col] = 0.0
        else:
            bg_proj[col] = pd.to_numeric(bg_proj[col], errors="coerce").fillna(0)
    bg_proj["housing_units_in_city"] = pd.to_numeric(
        bg_proj["housing_units_in_city"], errors="coerce"
    ).fillna(0)

    bg_for_join = bg_proj[["geometry", "housing_units_in_city", "employee_count", "student_count"]].copy()

    # Buffer all roads at once (vectorized — much faster than iterrows)
    roads_buf = gpd.GeoDataFrame(
        {"geometry": roads_proj.geometry.buffer(buffer_m), "_pos": range(len(roads_proj))},
        crs=analysis_crs,
    )

    # Spatial join: each road buffer × intersecting block groups
    joined = gpd.sjoin(roads_buf[["geometry", "_pos"]], bg_for_join, how="left", predicate="intersects")

    # Aggregate sums per road position
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

    # Keep catchment_units for connectivity weighting (sum of HUs traversing each segment)
    # This is populated by _identify_evacuation_routes; only update if missing
    if "catchment_units" not in roads_gdf.columns:
        roads_gdf["catchment_units"] = 0.0

    logger.info(
        f"  Buffer demand applied: "
        f"resident={roads_gdf['resident_demand_vph'].median():.0f} vph median, "
        f"employee={roads_gdf['employee_demand_vph'].median():.0f} vph median"
    )
    return roads_gdf


def _estimate_demand_from_road_class(road_type: str, capacity_vph: float) -> float:
    """
    Estimate baseline demand when no traffic count data is available.

    Uses typical utilization rates by road class (conservative estimates).
    This is clearly flagged as estimated in outputs.
    """
    utilization = {
        "freeway":   0.50,
        "multilane": 0.40,
        "two_lane":  0.25,
    }
    rate = utilization.get(road_type, 0.25)
    return capacity_vph * rate


# ---------------------------------------------------------------------------
# v/c Ratio and LOS
# ---------------------------------------------------------------------------

def calculate_vc_ratio(demand: float, capacity: float) -> float:
    """
    Calculate volume-to-capacity (v/c) ratio.

    Returns 0.0 if capacity is zero (avoids division by zero).
    """
    if capacity <= 0:
        return 0.0
    return demand / capacity


def assign_los(vc: float, config: dict) -> str:
    """
    Assign Level of Service (LOS) letter grade based on v/c ratio.

    Source: HCM 2022
    """
    thresholds = config.get("los_thresholds", {
        "A": 0.10, "B": 0.20, "C": 0.40, "D": 0.60, "E": 0.95,
    })
    for grade in ["A", "B", "C", "D", "E"]:
        if vc <= thresholds.get(grade, 1.0):
            return grade
    return "F"


# ---------------------------------------------------------------------------
# Evacuation Route Identification + Catchment Weighting
# ---------------------------------------------------------------------------

def _identify_evacuation_routes(
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    config: dict,
    analysis_crs: str,
    block_groups_gdf: Optional[gpd.GeoDataFrame] = None,
) -> gpd.GeoDataFrame:
    """
    Identify evacuation routes via network analysis.

    Origin weighting (new):
      When block_groups_gdf is provided with housing_units_in_fhsz, each origin
      point carries the block group's housing unit weight. The path computation
      accumulates these weights per edge, producing catchment_units per segment:
        catchment_units[s] = sum of housing_units_in_fhsz for all block groups
                             whose shortest evacuation path passes through segment s

      This directly feeds the evacuation demand formula:
        demand_vph = catchment_units × vehicles_per_unit × peak_hour_mobilization

      Fallback (block_groups_gdf absent or no FHSZ housing units):
        Uses uniform FHSZ polygon sampling (original behavior).
        catchment_units is set to 0 for all segments (demand falls back to road-class).

    Returns roads_gdf with columns added:
      is_evacuation_route, connectivity_score, catchment_units
    """
    roads_gdf["is_evacuation_route"] = False
    roads_gdf["connectivity_score"]  = 0
    roads_gdf["catchment_units"]     = 0.0

    trigger_zones = config.get("fhsz", {}).get("trigger_zones", [2, 3])
    max_origins   = int(config.get("census", {}).get("max_origins", 100))

    if fhsz_gdf.empty:
        logger.warning("FHSZ data is empty — skipping evacuation route identification.")
        return roads_gdf

    fhsz_trigger = fhsz_gdf[fhsz_gdf["HAZ_CLASS"].isin(trigger_zones)]
    if fhsz_trigger.empty:
        logger.warning(f"No FHSZ zones {trigger_zones} found — no evacuation routes identified.")
        return roads_gdf

    fhsz_proj     = fhsz_trigger.to_crs(analysis_crs)
    boundary_proj = boundary_gdf.to_crs(analysis_crs)

    # Build road graph
    place_boundary = boundary_gdf.unary_union
    logger.info("Building road graph for network analysis...")
    try:
        G = ox.graph_from_polygon(place_boundary, network_type="drive", simplify=True)
    except Exception as e:
        logger.error(f"Failed to build road graph: {e}")
        return roads_gdf

    G_proj  = ox.project_graph(G, to_crs=analysis_crs)
    G_undir = G_proj.to_undirected()

    # Virtual sink: connect all boundary exits with zero-cost edges
    exits = _find_exit_nodes(G_proj, boundary_proj)
    logger.info(f"  Found {len(exits)} potential exit nodes.")
    if not exits:
        logger.warning("  No exit nodes found — skipping route identification.")
        return roads_gdf

    VIRTUAL_SINK = -999999
    G_undir.add_node(VIRTUAL_SINK)
    for exit_node in exits:
        G_undir.add_edge(exit_node, VIRTUAL_SINK, length=0)

    # --- Choose origin sampling strategy ---
    origins, weights = _resolve_origins(
        block_groups_gdf, fhsz_proj, analysis_crs, max_origins, config
    )
    if not origins:
        logger.warning("  No origin points found — skipping route identification.")
        return roads_gdf

    total_weight = sum(weights)
    using_housing_units = (
        block_groups_gdf is not None
        and not block_groups_gdf.empty
        and total_weight > len(origins)   # weights > 1 → real housing unit counts
    )
    if using_housing_units:
        logger.info(
            f"  Using {len(origins)} block group origin points "
            f"({total_weight:,.0f} total city housing units — all residents as evacuation origins)."
        )
    else:
        logger.info(
            f"  Using {len(origins)} FHSZ origin points "
            f"(uniform weights — Census data unavailable)."
        )

    # Nearest graph node for each origin
    origin_xs    = [p.x for p in origins]
    origin_ys    = [p.y for p in origins]
    origin_nodes = ox.distance.nearest_nodes(G_proj, X=origin_xs, Y=origin_ys)
    logger.info(f"  Computing shortest paths for {len(origin_nodes)} origins...")

    edge_use_counts  = {}   # count of paths  → connectivity_score
    edge_unit_weights = {}  # sum of HU weights → catchment_units

    paths_found = 0
    for origin_node, weight in zip(origin_nodes, weights):
        try:
            path_nodes = nx.shortest_path(
                G_undir, origin_node, VIRTUAL_SINK, weight="length"
            )
            path_nodes = path_nodes[:-1]   # remove virtual sink
            if len(path_nodes) < 2:
                continue
            for u, v in zip(path_nodes[:-1], path_nodes[1:]):
                key = (min(u, v), max(u, v))
                edge_use_counts[key]   = edge_use_counts.get(key, 0)   + 1
                edge_unit_weights[key] = edge_unit_weights.get(key, 0) + weight
            paths_found += 1
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        except Exception as e:
            logger.debug(f"  Path computation error: {e}")
            continue

    logger.info(f"  Paths found: {paths_found}/{len(origin_nodes)}")

    if not edge_use_counts:
        logger.warning("  No evacuation paths found.")
        return roads_gdf

    # Map back to GeoDataFrame via osmid
    evac_osmids_count   = _build_evac_osmid_map(G_proj, edge_use_counts)
    evac_osmids_units   = _build_evac_osmid_map(G_proj, edge_unit_weights)

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

    # catchment_units: only meaningful when housing unit weights were used
    if using_housing_units:
        roads_gdf["catchment_units"] = roads_gdf["osmid"].apply(
            lambda o: _score(o, evac_osmids_units, default=0.0)
        )
    else:
        roads_gdf["catchment_units"] = 0.0  # signals demand fallback

    logger.info(
        f"  Marked {roads_gdf['is_evacuation_route'].sum()} evacuation route segments."
    )
    if using_housing_units:
        evac = roads_gdf[roads_gdf["is_evacuation_route"]]
        logger.info(
            f"  Total catchment housing units across all evac segments: "
            f"{evac['catchment_units'].sum():,.0f} "
            f"(sum > total city HUs because each HU traverses multiple segments)"
        )
    return roads_gdf


def _resolve_origins(
    block_groups_gdf: Optional[gpd.GeoDataFrame],
    fhsz_proj: gpd.GeoDataFrame,
    analysis_crs: str,
    max_origins: int,
    config: dict,
) -> tuple[list, list]:
    """
    Return (origin_points, weights) for path computation.

    Strategy A (preferred): ALL block group centroids weighted by housing_units_in_city.
      Uses all city residents as evacuation origins — matches KLD AB 747 methodology.
    Strategy B (fallback):  Uniform FHSZ polygon sampling with weight=1.
    """
    # Strategy A: all block group centroids (city-wide, not just FHSZ zones)
    if block_groups_gdf is not None and not block_groups_gdf.empty:
        if "housing_units_in_city" in block_groups_gdf.columns:
            bg_proj = block_groups_gdf.to_crs(analysis_crs)
            origins, weights = _sample_block_group_origins(bg_proj, max_origins)
            if origins and sum(weights) > 0:
                return origins, weights
            logger.warning(
                "  Block groups have no city housing units — "
                "falling back to uniform FHSZ sampling."
            )

    # Strategy B: fallback uniform sampling
    origins = _sample_fhsz_centroids(fhsz_proj, max_points=max_origins)
    weights = [1.0] * len(origins)
    return origins, weights


def _sample_block_group_origins(
    bg_proj: gpd.GeoDataFrame,
    max_origins: int = 100,
) -> tuple[list, list]:
    """
    Sample one representative point per block group that has city housing units.

    Each point carries housing_units_in_city as its weight for path accumulation.
    Uses ALL city block groups (not just FHSZ zones) to match KLD AB 747 methodology
    — all city residents are potential evacuees.

    If more block groups exist than max_origins, the top N by housing units are used
    (prioritizes dense areas most likely to stress evacuation routes).
    """
    city_bgs = bg_proj[bg_proj["housing_units_in_city"] > 0].copy()
    if city_bgs.empty:
        return [], []

    # Sort by housing units descending; take top max_origins
    city_bgs = city_bgs.sort_values("housing_units_in_city", ascending=False)
    if len(city_bgs) > max_origins:
        logger.info(
            f"  {len(city_bgs)} block groups with city housing units; "
            f"using top {max_origins} by housing unit count."
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
    """
    Sample interior points from FHSZ trigger zone polygons (fallback when
    block group data is unavailable).

    Uses a regular grid to capture points deep inside each polygon.
    Returns list of shapely Point objects in the projected CRS.
    """
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
    """
    Find graph nodes on or near the city boundary (potential exit points).
    """
    boundary_geom = boundary_proj.unary_union.boundary
    node_data     = [(n, d["x"], d["y"]) for n, d in G_proj.nodes(data=True)]
    return [
        node_id for node_id, x, y in node_data
        if boundary_geom.distance(Point(x, y)) < 50   # within 50 m of boundary
    ]


def _build_evac_osmid_map(G_proj, edge_scores: dict) -> dict:
    """
    Map edge scores (count or housing-unit weight) to osmid strings.

    For edges with multiple parallel OSM ways, uses the maximum score.
    """
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

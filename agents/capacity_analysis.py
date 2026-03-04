"""
Agent 2: Capacity Analysis

Calculates objective, verifiable evacuation route capacity metrics using
Highway Capacity Manual 2022 (HCM 2022) standards.

All calculations are documented and reproducible. Estimated values are flagged.

Key outputs:
- capacity_vph per road segment (HCM 2022)
- baseline_demand_vph (from AADT or road-class estimate)
- vc_ratio and LOS (A-F)
- evacuation route identification via network analysis (NetworkX)
- connectivity_score per segment
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
) -> gpd.GeoDataFrame:
    """
    Run full capacity analysis pipeline on a road network.

    1. Calculate HCM capacity per segment
    2. Calculate baseline demand
    3. Calculate v/c ratio and LOS
    4. Identify evacuation routes via network analysis
    5. Calculate connectivity scores

    Returns the enriched GeoDataFrame with all capacity columns added.
    """
    analysis_crs = city_config.get("analysis_crs", "EPSG:26910")

    logger.info(f"Analyzing capacity for {len(roads_gdf)} road segments...")

    # Step 1: HCM Capacity
    roads_gdf = _apply_hcm_capacity(roads_gdf, config)

    # Step 2: Baseline demand
    roads_gdf = _apply_baseline_demand(roads_gdf, config)

    # Step 3: v/c ratio and LOS
    roads_gdf["vc_ratio"] = roads_gdf.apply(
        lambda r: calculate_vc_ratio(r["baseline_demand_vph"], r["capacity_vph"]),
        axis=1,
    )
    roads_gdf["los"] = roads_gdf["vc_ratio"].apply(
        lambda vc: assign_los(vc, config)
    )

    # Step 4 & 5: Evacuation routes + connectivity
    roads_gdf = _identify_evacuation_routes(roads_gdf, fhsz_gdf, boundary_gdf, config, analysis_crs)

    evac_count = roads_gdf["is_evacuation_route"].sum()
    logger.info(f"Capacity analysis complete. {evac_count} evacuation route segments identified.")
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
        # Find the highest speed threshold that is <= the actual speed
        valid_thresholds = sorted([int(k) for k in by_speed.keys() if int(k) <= speed])
        if valid_thresholds:
            return float(by_speed[str(valid_thresholds[-1])])
        # Speed below minimum threshold — use the lowest value
        all_thresholds = sorted(int(k) for k in by_speed.keys())
        if all_thresholds:
            return float(by_speed[str(all_thresholds[0])])
        return 900.0  # absolute fallback

    logger.warning(f"Unknown road_type '{road_type}' — capacity set to 0.")
    return 0.0


# ---------------------------------------------------------------------------
# Baseline Demand
# ---------------------------------------------------------------------------

def _apply_baseline_demand(gdf: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    """Calculate baseline_demand_vph for every segment."""
    peak_factor = config.get("aadt_peak_hour_factor", 0.10)
    aadt_col = "aadt" if "aadt" in gdf.columns else None

    def demand_for_row(row):
        if aadt_col and pd.notna(row.get(aadt_col)):
            return row[aadt_col] * peak_factor, False  # (demand, is_estimated)
        # Fallback: estimate from road type and capacity
        return _estimate_demand_from_road_class(row["road_type"], row["capacity_vph"]), True

    results = gdf.apply(demand_for_row, axis=1, result_type="expand")
    gdf["baseline_demand_vph"] = results[0]
    gdf["aadt_estimated"] = gdf.get("aadt_estimated", results[1])
    return gdf


def _estimate_demand_from_road_class(road_type: str, capacity_vph: float) -> float:
    """
    Estimate baseline demand when no traffic count data is available.

    Uses typical utilization rates by road class (conservative estimates).
    This is clearly flagged as estimated in outputs.
    """
    utilization = {
        "freeway": 0.50,     # 50% of capacity
        "multilane": 0.40,   # 40% of capacity
        "two_lane": 0.25,    # 25% of capacity
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
# Evacuation Route Identification
# ---------------------------------------------------------------------------

def _identify_evacuation_routes(
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    config: dict,
    analysis_crs: str,
) -> gpd.GeoDataFrame:
    """
    Identify evacuation routes via network analysis.

    Process (per spec Standard 3):
    1. Find census block centroids in FHSZ Zone 2 or 3
       (approximated here by sampling points within FHSZ polygons)
    2. Find city boundary exit nodes
    3. Calculate shortest path from each centroid to nearest exit
    4. Mark all used road segments as evacuation routes
    5. Count frequency (connectivity_score)

    Returns roads_gdf with is_evacuation_route and connectivity_score added.
    """
    roads_gdf["is_evacuation_route"] = False
    roads_gdf["connectivity_score"] = 0

    trigger_zones = config.get("fhsz", {}).get("trigger_zones", [2, 3])

    if fhsz_gdf.empty:
        logger.warning("FHSZ data is empty — skipping evacuation route identification.")
        return roads_gdf

    # Filter to trigger zones
    fhsz_trigger = fhsz_gdf[fhsz_gdf["HAZ_CLASS"].isin(trigger_zones)]
    if fhsz_trigger.empty:
        logger.warning(f"No FHSZ zones {trigger_zones} found — no evacuation routes identified.")
        return roads_gdf

    # Project to metric CRS for accurate distance/path analysis
    fhsz_proj = fhsz_trigger.to_crs(analysis_crs)
    boundary_proj = boundary_gdf.to_crs(analysis_crs)

    # Build OSM graph clipped to city boundary
    place_boundary = boundary_gdf.unary_union
    logger.info("Building road graph for network analysis...")
    try:
        G = ox.graph_from_polygon(place_boundary, network_type="drive", simplify=True)
    except Exception as e:
        logger.error(f"Failed to build road graph: {e}")
        return roads_gdf

    G_proj = ox.project_graph(G, to_crs=analysis_crs)

    # Sample origin points from FHSZ trigger zones
    origins = _sample_fhsz_centroids(fhsz_proj, max_points=50)
    logger.info(f"  Using {len(origins)} FHSZ origin points.")

    # Find exit nodes (nodes on or near city boundary)
    exits = _find_exit_nodes(G_proj, boundary_proj)
    logger.info(f"  Found {len(exits)} potential exit nodes.")

    if not exits:
        logger.warning("  No exit nodes found — skipping route identification.")
        return roads_gdf

    # For each origin, find shortest path to nearest exit
    edge_use_counts = {}
    for i, origin_point in enumerate(origins):
        try:
            origin_node = ox.distance.nearest_nodes(
                G_proj, X=origin_point.x, Y=origin_point.y
            )
            # Find nearest exit
            nearest_exit = min(
                exits,
                key=lambda n: nx.shortest_path_length(G_proj, origin_node, n, weight="length")
                if nx.has_path(G_proj, origin_node, n) else float("inf")
            )
            if not nx.has_path(G_proj, origin_node, nearest_exit):
                continue
            path_nodes = nx.shortest_path(G_proj, origin_node, nearest_exit, weight="length")
            for u, v in zip(path_nodes[:-1], path_nodes[1:]):
                edge_key = (min(u, v), max(u, v))
                edge_use_counts[edge_key] = edge_use_counts.get(edge_key, 0) + 1
        except (nx.NetworkXNoPath, nx.NodeNotFound, Exception) as e:
            logger.debug(f"  Path from origin {i} failed: {e}")
            continue

    if not edge_use_counts:
        logger.warning("  No evacuation paths found.")
        return roads_gdf

    # Map OSM edge usage back to GeoDataFrame rows by osmid
    evac_osmids = _build_evac_osmid_map(G_proj, edge_use_counts)

    def _match_osmid(osmid_val):
        if isinstance(osmid_val, list):
            return any(str(o) in evac_osmids for o in osmid_val)
        return str(osmid_val) in evac_osmids

    roads_gdf["is_evacuation_route"] = roads_gdf["osmid"].apply(_match_osmid)
    roads_gdf["connectivity_score"] = roads_gdf["osmid"].apply(
        lambda o: evac_osmids.get(str(o[0] if isinstance(o, list) else o), 0)
    )

    logger.info(f"  Marked {roads_gdf['is_evacuation_route'].sum()} evacuation route segments.")
    return roads_gdf


def _sample_fhsz_centroids(fhsz_proj: gpd.GeoDataFrame, max_points: int = 50) -> list:
    """
    Sample centroid points from FHSZ trigger zone polygons.

    Returns list of shapely Point objects in the projected CRS.
    """
    centroids = []
    for geom in fhsz_proj.geometry:
        centroid = geom.centroid
        if not centroid.is_empty:
            centroids.append(centroid)

    # If too many, sample evenly
    if len(centroids) > max_points:
        step = len(centroids) // max_points
        centroids = centroids[::step][:max_points]

    return centroids


def _find_exit_nodes(G_proj, boundary_proj: gpd.GeoDataFrame) -> list:
    """
    Find graph nodes that are on or near the city boundary (potential exit points).

    Returns list of node IDs.
    """
    boundary_geom = boundary_proj.unary_union.boundary

    node_data = [(n, d["x"], d["y"]) for n, d in G_proj.nodes(data=True)]
    exit_nodes = []

    for node_id, x, y in node_data:
        pt = Point(x, y)
        if boundary_geom.distance(pt) < 200:  # within 200 meters of boundary
            exit_nodes.append(node_id)

    return exit_nodes


def _build_evac_osmid_map(G_proj, edge_use_counts: dict) -> dict:
    """Map OSM edge IDs to their evacuation connectivity scores."""
    evac_osmids = {}
    for (u, v), count in edge_use_counts.items():
        edge_data = G_proj.get_edge_data(u, v) or G_proj.get_edge_data(v, u)
        if edge_data is None:
            continue
        # edge_data may have multiple keys (parallel edges)
        for key_data in (edge_data.values() if isinstance(edge_data, dict) else [edge_data]):
            osmid = key_data.get("osmid")
            if osmid is None:
                continue
            if isinstance(osmid, list):
                for o in osmid:
                    evac_osmids[str(o)] = max(evac_osmids.get(str(o), 0), count)
            else:
                evac_osmids[str(osmid)] = max(evac_osmids.get(str(osmid), 0), count)
    return evac_osmids

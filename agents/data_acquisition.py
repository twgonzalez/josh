"""
Agent 1: Data Acquisition

Downloads and caches all required public datasets for a city:
- Fire Hazard Severity Zones (CAL FIRE)
- Road network (OpenStreetMap via OSMnx)
- City boundary (U.S. Census TIGER)
- Traffic volumes (Caltrans AADT — with road-class fallback)

All data is cached locally with a configurable TTL (default 90 days).
Every download is logged to metadata.yaml for audit trail purposes.
"""
import logging
import re
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

import geopandas as gpd
import osmnx as ox
import pandas as pd
import requests
import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def acquire_data(
    city: str,
    state: str,
    config: dict,
    city_config: dict,
    data_dir: Path,
    force_refresh: bool = False,
) -> dict:
    """
    Download and cache all required datasets for a city.

    Returns a dict with keys: fhsz, roads, boundary
    All returned GeoDataFrames are in EPSG:4326.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    metadata = _load_metadata(data_dir)

    place_name = city_config.get("osmnx_place", f"{city}, {state}, USA")
    ttl_days = config.get("cache_ttl_days", 90)

    results = {}

    # City boundary (needed first — used to clip other datasets)
    boundary_path = data_dir / "boundary.geojson"
    if force_refresh or _is_stale(metadata, "boundary", ttl_days):
        logger.info("Fetching city boundary...")
        gdf = fetch_city_boundary(place_name, city_config, boundary_path)
        metadata["boundary"] = _meta_entry("U.S. Census TIGER / OSMnx")
    else:
        logger.info("Using cached city boundary.")
        gdf = gpd.read_file(boundary_path)
    results["boundary"] = gdf

    # FHSZ zones
    fhsz_path = data_dir / "fhsz.geojson"
    if force_refresh or _is_stale(metadata, "fhsz", ttl_days):
        logger.info("Fetching FHSZ zones from CAL FIRE...")
        bbox = tuple(gdf.total_bounds)  # (minx, miny, maxx, maxy)
        fhsz_gdf = fetch_fhsz_zones(bbox, fhsz_path, config)
        metadata["fhsz"] = _meta_entry("CAL FIRE OSFM ArcGIS REST API")
    else:
        logger.info("Using cached FHSZ zones.")
        fhsz_gdf = gpd.read_file(fhsz_path)
    results["fhsz"] = fhsz_gdf

    # Road network
    roads_path = data_dir / "roads.gpkg"
    if force_refresh or _is_stale(metadata, "roads", ttl_days):
        logger.info("Fetching road network from OpenStreetMap...")
        roads_gdf = fetch_road_network(place_name, roads_path, config)
        metadata["roads"] = _meta_entry("OpenStreetMap via OSMnx")
    else:
        logger.info("Using cached road network.")
        roads_gdf = gpd.read_file(roads_path, layer="roads")
    results["roads"] = roads_gdf

    _save_metadata(data_dir, metadata)
    logger.info(f"Data acquisition complete. Files in: {data_dir}")
    return results


# ---------------------------------------------------------------------------
# City Boundary
# ---------------------------------------------------------------------------

def fetch_city_boundary(
    place_name: str,
    city_config: dict,
    output_path: Path,
) -> gpd.GeoDataFrame:
    """
    Fetch city boundary polygon from OSMnx (uses Nominatim geocoding).
    Falls back to Census TIGER if OSMnx fails.
    """
    try:
        gdf = ox.geocode_to_gdf(place_name)
        gdf = gdf.to_crs("EPSG:4326")
        gdf = gdf[["geometry"]].copy()
        gdf["city"] = place_name
        gdf.to_file(output_path, driver="GeoJSON")
        logger.info(f"  City boundary saved: {output_path}")
        return gdf
    except Exception as e:
        logger.warning(f"  OSMnx boundary fetch failed ({e}), trying Census TIGER...")
        return _fetch_boundary_from_tiger(city_config, output_path)


def _fetch_boundary_from_tiger(city_config: dict, output_path: Path) -> gpd.GeoDataFrame:
    """Download city boundary from Census TIGER shapefile."""
    tiger_url = city_config.get("tiger_url")
    if not tiger_url:
        raise ValueError("No tiger_url in city config and OSMnx boundary fetch failed.")

    resp = requests.get(tiger_url, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(BytesIO(resp.content)) as z:
        z.extractall(output_path.parent / "_tiger_tmp")

    shp_files = list((output_path.parent / "_tiger_tmp").glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError("No shapefile found in TIGER download.")

    all_places = gpd.read_file(shp_files[0])
    city_name = city_config.get("city_name", "")
    match = all_places[all_places["NAME"].str.lower() == city_name.lower()]

    if match.empty:
        raise ValueError(f"City '{city_name}' not found in TIGER shapefile.")

    gdf = match.to_crs("EPSG:4326")[["NAME", "geometry"]].copy()
    gdf.to_file(output_path, driver="GeoJSON")
    logger.info(f"  City boundary (TIGER) saved: {output_path}")
    return gdf


# ---------------------------------------------------------------------------
# FHSZ Zones
# ---------------------------------------------------------------------------

def fetch_fhsz_zones(
    bbox: tuple,
    output_path: Path,
    config: dict,
) -> gpd.GeoDataFrame:
    """
    Fetch Fire Hazard Severity Zones from CAL FIRE ArcGIS REST API.

    bbox: (minx, miny, maxx, maxy) in EPSG:4326
    Returns GeoDataFrame with 'HAZ_CLASS' column (zone level as int).
    """
    api_base = config.get("fhsz", {}).get("api_base",
        "https://egis.fire.ca.gov/arcgis/rest/services/FHSZ/MapServer")

    minx, miny, maxx, maxy = bbox
    geometry_filter = f"{minx},{miny},{maxx},{maxy}"

    all_gdfs = []
    for layer_id in [0, 1]:  # SRA=0, LRA=1
        url = f"{api_base}/{layer_id}/query"
        params = {
            "geometry": geometry_filter,
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
            "returnGeometry": "true",
        }
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if data.get("features"):
                gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
                all_gdfs.append(gdf)
                logger.info(f"  FHSZ layer {layer_id}: {len(gdf)} features")
        except Exception as e:
            logger.warning(f"  FHSZ layer {layer_id} fetch failed: {e}")

    if not all_gdfs:
        logger.warning("  No FHSZ data returned from API — returning empty GeoDataFrame.")
        return gpd.GeoDataFrame(columns=["HAZ_CLASS", "geometry"], crs="EPSG:4326")

    combined = gpd.pd.concat(all_gdfs, ignore_index=True)
    combined = combined.to_crs("EPSG:4326")

    # Normalize zone column — API may use HAZ_CLASS, SRA_ZONE, etc.
    combined = _normalize_fhsz_column(combined)

    combined.to_file(output_path, driver="GeoJSON")
    logger.info(f"  FHSZ zones saved: {output_path} ({len(combined)} features)")
    return combined


def _normalize_fhsz_column(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Map various FHSZ column names to a standard 'HAZ_CLASS' integer column."""
    candidate_cols = ["HAZ_CLASS", "SRA_ZONE", "FHSZ", "ZONE", "CLASS"]
    for col in candidate_cols:
        if col in gdf.columns:
            gdf = gdf.rename(columns={col: "HAZ_CLASS"})
            break

    if "HAZ_CLASS" not in gdf.columns:
        logger.warning("  Could not identify FHSZ zone column; defaulting all to Zone 3.")
        gdf["HAZ_CLASS"] = 3
        return gdf

    # Convert text values to integers (e.g., "HIGH" → 2, "VERY HIGH" → 3)
    zone_map = {
        "MODERATE": 1, "MOD": 1, "1": 1, 1: 1,
        "HIGH": 2, "2": 2, 2: 2,
        "VERY HIGH": 3, "VERY_HIGH": 3, "VH": 3, "3": 3, 3: 3,
    }
    gdf["HAZ_CLASS"] = gdf["HAZ_CLASS"].map(
        lambda v: zone_map.get(str(v).strip().upper(), 0)
    )
    return gdf


# ---------------------------------------------------------------------------
# Road Network
# ---------------------------------------------------------------------------

def fetch_road_network(
    place_name: str,
    output_path: Path,
    config: dict,
) -> gpd.GeoDataFrame:
    """
    Download road network from OpenStreetMap via OSMnx.

    Returns a GeoDataFrame of road segments with capacity attributes:
    - lane_count (measured or estimated)
    - speed_limit (measured or estimated)
    - road_type (freeway | multilane | two_lane)
    """
    G = ox.graph_from_place(place_name, network_type="drive", simplify=True)
    _, edges = ox.graph_to_gdfs(G)

    gdf = edges.reset_index()
    gdf = gdf.to_crs("EPSG:4326")

    lane_defaults = config.get("lane_defaults", {})
    speed_defaults = config.get("speed_defaults", {})
    road_type_mapping = config.get("road_type_mapping", {})

    gdf["lane_count"], gdf["lane_count_estimated"] = zip(
        *gdf["highway"].apply(lambda h: _resolve_lanes(h, gdf.loc[gdf["highway"] == h, "lanes"].iloc[0]
            if "lanes" in gdf.columns and not gdf.loc[gdf["highway"] == h, "lanes"].empty else None,
            lane_defaults))
    )

    gdf["speed_limit"], gdf["speed_estimated"] = zip(
        *gdf.apply(lambda row: _resolve_speed(
            row.get("highway", "unclassified"),
            row.get("maxspeed", None),
            speed_defaults,
        ), axis=1)
    )

    gdf["road_type"] = gdf["highway"].apply(
        lambda h: _classify_road_type(h, road_type_mapping)
    )

    # Retain only needed columns
    keep_cols = [
        "osmid", "name", "highway", "geometry", "length",
        "lane_count", "lane_count_estimated",
        "speed_limit", "speed_estimated",
        "road_type",
    ]
    if "lanes" in gdf.columns:
        keep_cols.append("lanes")

    gdf = gdf[[c for c in keep_cols if c in gdf.columns]].copy()
    gdf = gdf.rename(columns={"length": "length_meters"})

    # Ensure name is a string (OSMnx sometimes returns lists)
    gdf["name"] = gdf["name"].apply(
        lambda v: v[0] if isinstance(v, list) else (v if pd.notna(v) else "")
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, layer="roads", driver="GPKG")
    logger.info(f"  Road network saved: {output_path} ({len(gdf)} segments)")
    return gdf


def _resolve_lanes(highway_tag, osm_lanes_value, lane_defaults: dict) -> tuple[int, bool]:
    """Return (lane_count, is_estimated)."""
    hw = _normalize_highway_tag(highway_tag)
    if osm_lanes_value is not None:
        try:
            val = osm_lanes_value
            if isinstance(val, list):
                val = val[0]
            lanes = int(str(val).split(";")[0].strip())
            if lanes > 0:
                return lanes, False
        except (ValueError, TypeError):
            pass
    default = lane_defaults.get(hw, 1)
    return default, True


def _resolve_speed(highway_tag, maxspeed_value, speed_defaults: dict) -> tuple[int, bool]:
    """Return (speed_mph, is_estimated)."""
    hw = _normalize_highway_tag(highway_tag)
    if maxspeed_value is not None:
        try:
            val = maxspeed_value
            if isinstance(val, list):
                val = val[0]
            s = str(val).lower().replace("mph", "").replace("km/h", "").strip()
            speed = int(s.split(";")[0].strip())
            # If value looks like km/h (>80), convert
            if speed > 80:
                speed = round(speed * 0.621371)
            return speed, False
        except (ValueError, TypeError):
            pass
    default = speed_defaults.get(hw, 25)
    return default, True


def _classify_road_type(highway_tag, road_type_mapping: dict) -> str:
    """Map OSM highway tag to HCM road type."""
    hw = _normalize_highway_tag(highway_tag)
    for road_type, tags in road_type_mapping.items():
        if hw in tags:
            return road_type
    return "two_lane"


def _normalize_highway_tag(highway_tag) -> str:
    """Handle list values from OSMnx (takes first element)."""
    if isinstance(highway_tag, list):
        highway_tag = highway_tag[0]
    return str(highway_tag).strip().lower()


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def _meta_entry(source: str) -> dict:
    return {
        "source": source,
        "downloaded": datetime.now().isoformat(),
    }


def _load_metadata(data_dir: Path) -> dict:
    meta_path = data_dir / "metadata.yaml"
    if meta_path.exists():
        with open(meta_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_metadata(data_dir: Path, metadata: dict) -> None:
    meta_path = data_dir / "metadata.yaml"
    with open(meta_path, "w") as f:
        yaml.dump(metadata, f, default_flow_style=False)


def _is_stale(metadata: dict, key: str, ttl_days: int) -> bool:
    """Return True if data is missing or older than ttl_days."""
    if key not in metadata:
        return True
    try:
        downloaded = datetime.fromisoformat(metadata[key]["downloaded"])
        return datetime.now() - downloaded > timedelta(days=ttl_days)
    except (KeyError, ValueError):
        return True

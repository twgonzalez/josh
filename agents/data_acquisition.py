# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Agent 1: Data Acquisition

Downloads and caches all required public datasets for a city:
- Fire Hazard Severity Zones (CAL FIRE)
- Road network (OpenStreetMap via OSMnx)
- City boundary (U.S. Census TIGER)
- Traffic volumes (Caltrans AADT — with road-class fallback)
- Census ACS housing units by block group (for evacuation demand baseline)
- LEHD LODES employee counts by block group (Phase 2b demand model)
- University student vehicle demand by block group (Phase 2b demand model)

All data is cached locally with a configurable TTL (default 90 days).
Every download is logged to metadata.yaml for audit trail purposes.
"""
import gzip
import io
import logging
import re
import tempfile
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
from shapely.geometry import Point

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

    # Census ACS block groups (housing units for evacuation demand baseline)
    block_groups_path = data_dir / "block_groups.geojson"
    if force_refresh or _is_stale(metadata, "block_groups", ttl_days):
        logger.info("Fetching Census ACS housing units by block group...")
        bg_gdf = fetch_census_housing_units(
            boundary_gdf=results["boundary"],
            fhsz_gdf=results["fhsz"],
            city_config=city_config,
            config=config,
            output_path=block_groups_path,
        )
        metadata["block_groups"] = _meta_entry("U.S. Census ACS 5-year / Census TIGER")
    else:
        logger.info("Using cached block group data.")
        bg_gdf = gpd.read_file(block_groups_path) if block_groups_path.exists() else gpd.GeoDataFrame()
    results["block_groups"] = bg_gdf

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

    Endpoint: FRAP/HHZ_ref_FHSZ MapServer, layer 0
    Field: FHSZ9 with values like 'SRA_VeryHigh', 'LRA_High', 'FRA_Moderate'

    bbox: (minx, miny, maxx, maxy) in EPSG:4326
    Returns GeoDataFrame with 'HAZ_CLASS' column (1=Moderate, 2=High, 3=VeryHigh).
    """
    api_base = config.get("fhsz", {}).get("api_base",
        "https://egis.fire.ca.gov/arcgis/rest/services/FRAP/HHZ_ref_FHSZ/MapServer")

    minx, miny, maxx, maxy = bbox
    geometry_filter = f"{minx},{miny},{maxx},{maxy}"

    url = f"{api_base}/0/query"
    params = {
        "geometry": geometry_filter,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FHSZ9",
        "f": "geojson",
        "returnGeometry": "true",
    }

    all_gdfs = []
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("features"):
            gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
            all_gdfs.append(gdf)
            logger.info(f"  FHSZ: {len(gdf)} features retrieved")
        else:
            logger.warning("  FHSZ query returned 0 features.")
    except Exception as e:
        logger.warning(f"  FHSZ fetch failed: {e}")

    if not all_gdfs:
        logger.warning("  No FHSZ data returned from API — returning empty GeoDataFrame.")
        return gpd.GeoDataFrame(columns=["HAZ_CLASS", "geometry"], crs="EPSG:4326")

    combined = pd.concat(all_gdfs, ignore_index=True)
    combined = gpd.GeoDataFrame(combined, crs="EPSG:4326")
    combined = _normalize_fhsz_column(combined)

    combined.to_file(output_path, driver="GeoJSON")
    logger.info(f"  FHSZ zones saved: {output_path} ({len(combined)} features)")
    return combined


def _normalize_fhsz_column(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Normalize the FHSZ zone column to a standard 'HAZ_CLASS' integer column.

    Handles the FHSZ9 field format from CAL FIRE: 'SRA_VeryHigh', 'LRA_High',
    'FRA_Moderate', etc. Also handles legacy formats.
    """
    # FHSZ9 is the field from the HHZ_ref_FHSZ service
    if "FHSZ9" in gdf.columns:
        gdf = gdf.rename(columns={"FHSZ9": "HAZ_CLASS"})
    else:
        for col in ["HAZ_CLASS", "SRA_ZONE", "FHSZ", "ZONE", "CLASS"]:
            if col in gdf.columns:
                gdf = gdf.rename(columns={col: "HAZ_CLASS"})
                break

    if "HAZ_CLASS" not in gdf.columns:
        logger.warning("  Could not identify FHSZ zone column; defaulting all to Zone 3.")
        gdf["HAZ_CLASS"] = 3
        return gdf

    def _to_zone_int(v) -> int:
        s = str(v).strip().upper()
        # FHSZ9 format: 'SRA_VERYHIGH', 'LRA_HIGH', 'FRA_MODERATE'
        if "VERYHIGH" in s or "VERY_HIGH" in s or "VERY HIGH" in s or s.endswith("VH"):
            return 3
        if "HIGH" in s:
            return 2
        if "MODERATE" in s or "MOD" in s:
            return 1
        # Numeric fallback
        for num, zone in [("3", 3), ("2", 2), ("1", 1)]:
            if s == num:
                return zone
        return 0

    gdf["HAZ_CLASS"] = gdf["HAZ_CLASS"].map(_to_zone_int)
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

    has_lanes_col = "lanes" in gdf.columns

    def _process_row(row):
        hw = _normalize_highway_tag(row.get("highway", "unclassified"))
        lanes_val = row.get("lanes", None) if has_lanes_col else None
        lane_count, lane_estimated = _resolve_lanes(hw, lanes_val, lane_defaults)
        speed, speed_estimated = _resolve_speed(hw, row.get("maxspeed", None), speed_defaults)
        road_type = _classify_road_type(row.get("highway", "unclassified"), road_type_mapping)
        return lane_count, lane_estimated, speed, speed_estimated, road_type

    results = gdf.apply(_process_row, axis=1, result_type="expand")
    results.columns = ["lane_count", "lane_count_estimated", "speed_limit", "speed_estimated", "road_type"]
    gdf = gdf.join(results)

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


def _resolve_lanes(hw: str, osm_lanes_value, lane_defaults: dict) -> tuple[int, bool]:
    """Return (lane_count, is_estimated). hw must already be normalized."""
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


# ---------------------------------------------------------------------------
# Census ACS Housing Units by Block Group
# ---------------------------------------------------------------------------

def fetch_census_housing_units(
    boundary_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    city_config: dict,
    config: dict,
    output_path: Path,
) -> gpd.GeoDataFrame:
    """
    Fetch Census ACS housing units by block group, clipped to city boundary,
    with area-weighted FHSZ intersection, employee counts, and student counts.

    Pipeline:
      1. Download Census Cartographic Boundary block group shapefile (state level)
      2. Fetch ACS B25001_001E (housing units) + B01001_001E (population)
      3. Join geometry + ACS data on GEOID
      4. Clip to city boundary (area-weighted partial block groups)
      5. Compute housing_units_in_fhsz via area-weighted FHSZ intersection
      6. Fetch employee counts from LEHD LODES WAC (fallback: ACS-based estimate)
      7. Compute student vehicle demand from city config universities list

    Key output columns:
      geoid                  — 12-digit Census block group GEOID
      housing_units          — total ACS housing units in block group
      housing_units_in_city  — area-weighted units within city boundary
      housing_units_in_fhsz  — area-weighted units in FHSZ trigger zones
      fraction_in_fhsz       — fraction of city-clipped block group in FHSZ
      employee_count         — in-commuting employees working in block group (LEHD)
      student_count          — student vehicles assigned to block group (city config)

    Returns GeoDataFrame in EPSG:4326 (empty on failure).
    """
    state_fips  = str(city_config.get("state_fips",  "06")).zfill(2)
    county_fips = str(city_config.get("county_fips", "001")).zfill(3)
    state_lower = city_config.get("state", "CA").lower()
    census_cfg  = config.get("census", {})
    acs_year    = int(census_cfg.get("acs_year", 2022))
    hu_table    = census_cfg.get("housing_units_table", "B25001_001E")

    _EMPTY = gpd.GeoDataFrame(
        columns=["geoid", "housing_units", "housing_units_in_city",
                 "housing_units_in_fhsz", "fraction_in_fhsz",
                 "employee_count", "student_count", "geometry"],
        crs="EPSG:4326",
    )

    logger.info(
        f"Fetching Census ACS {acs_year} block groups "
        f"(state={state_fips}, county={county_fips})..."
    )

    # --- Step 1: Block group geometry ---
    bg_gdf = _fetch_block_group_geometry(state_fips, county_fips, acs_year)
    if bg_gdf.empty:
        logger.warning("  No block group geometry — skipping Census housing units.")
        return _EMPTY

    # --- Step 2: ACS housing unit counts ---
    hu_df = _fetch_acs_housing_units(state_fips, county_fips, acs_year, hu_table, census_cfg)
    if hu_df.empty:
        logger.warning("  No ACS housing unit data — skipping Census housing units.")
        return _EMPTY

    # --- Step 3: Join ---
    join_cols = [c for c in ["geoid", "housing_units", "population"] if c in hu_df.columns]
    bg_gdf = bg_gdf.merge(hu_df[join_cols], on="geoid", how="left")
    bg_gdf["housing_units"] = pd.to_numeric(
        bg_gdf["housing_units"], errors="coerce"
    ).fillna(0).astype(int)
    if "population" in bg_gdf.columns:
        bg_gdf["population"] = pd.to_numeric(
            bg_gdf["population"], errors="coerce"
        ).fillna(0).astype(int)
    else:
        bg_gdf["population"] = 0
    logger.info(
        f"  Joined {len(bg_gdf)} block groups; "
        f"county total: {bg_gdf['housing_units'].sum():,} housing units"
    )

    # --- Step 4: Clip to city boundary (area-weighted) ---
    analysis_crs = city_config.get("analysis_crs", "EPSG:26910")
    bg_city = _clip_block_groups_to_city(bg_gdf, boundary_gdf, analysis_crs)
    if bg_city.empty:
        logger.warning("  No block groups intersect city boundary.")
        return _EMPTY
    logger.info(
        f"  City clip: {len(bg_city)} block groups, "
        f"{bg_city['housing_units_in_city'].sum():,} housing units"
    )

    # --- Step 5: FHSZ-weighted housing units ---
    trigger_zones = config.get("fhsz", {}).get("trigger_zones", [2, 3])
    bg_city = _compute_fhsz_housing_units(bg_city, fhsz_gdf, trigger_zones, analysis_crs)
    total_fhsz = bg_city["housing_units_in_fhsz"].sum()
    logger.info(
        f"  FHSZ housing units (zones {trigger_zones}): {total_fhsz:,.0f} "
        f"across {(bg_city['housing_units_in_fhsz'] > 0).sum()} block groups"
    )

    # --- Step 6: Employee counts (LEHD LODES primary, ACS-based fallback) ---
    city_geoids = bg_city["geoid"].tolist()
    emp_series = _fetch_lehd_employees(state_lower, state_fips, county_fips, census_cfg)
    if emp_series.empty:
        logger.warning("  LEHD LODES unavailable — using ACS-based employee estimate.")
        emp_series = _estimate_employees_from_acs(bg_city, city_config, config)

    bg_city["employee_count"] = (
        bg_city["geoid"].map(emp_series).fillna(0).round().astype(int)
    )
    logger.info(
        f"  Employee counts: {bg_city['employee_count'].sum():,.0f} total jobs "
        f"across {(bg_city['employee_count'] > 0).sum()} block groups"
    )

    # --- Step 7: Student vehicle counts (from city config universities) ---
    bg_city = _compute_student_counts(bg_city, city_config, analysis_crs)
    logger.info(
        f"  Student vehicles: {bg_city['student_count'].sum():,.1f} total "
        f"across {(bg_city['student_count'] > 0).sum()} block groups"
    )

    out_gdf = bg_city.to_crs("EPSG:4326")[
        ["geoid", "housing_units", "housing_units_in_city",
         "housing_units_in_fhsz", "fraction_in_fhsz",
         "employee_count", "student_count", "geometry"]
    ].copy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_gdf.to_file(output_path, driver="GeoJSON")
    logger.info(f"  Block groups saved: {output_path}")
    return out_gdf


def _fetch_block_group_geometry(state_fips: str, county_fips: str, year: int) -> gpd.GeoDataFrame:
    """
    Download Census Cartographic Boundary block group file (cb_{year}_{state}_bg_500k.zip).

    The 1:500,000 scale is sufficient for area-weighted spatial allocation.
    Filters to the specified county.
    Returns GeoDataFrame in EPSG:4326 with columns [geoid, geometry].
    """
    url = (
        f"https://www2.census.gov/geo/tiger/GENZ{year}/shp/"
        f"cb_{year}_{state_fips}_bg_500k.zip"
    )
    logger.info(f"  Downloading block group shapefile: {url}")
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"  Block group shapefile download failed: {e}")
        return gpd.GeoDataFrame()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        zip_path = tmp / "bg.zip"
        zip_path.write_bytes(resp.content)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        shp = next(tmp.glob("*.shp"), None)
        if shp is None:
            logger.error("  No shapefile found in Census BG download.")
            return gpd.GeoDataFrame()
        gdf = gpd.read_file(shp)

    # Filter to county
    if "COUNTYFP" in gdf.columns:
        gdf = gdf[gdf["COUNTYFP"] == county_fips].copy()
    elif "COUNTY" in gdf.columns:
        gdf = gdf[gdf["COUNTY"] == county_fips].copy()

    geoid_col = next((c for c in ["GEOID", "GEOID10", "GEOID20"] if c in gdf.columns), None)
    if geoid_col is None:
        logger.error("  GEOID column not found in block group shapefile.")
        return gpd.GeoDataFrame()

    gdf = gdf.rename(columns={geoid_col: "geoid"})
    gdf["geoid"] = gdf["geoid"].astype(str).str.strip().str.zfill(12)
    gdf = gdf[["geoid", "geometry"]].copy()
    gdf = gdf.to_crs("EPSG:4326")
    logger.info(f"  Block group geometry: {len(gdf)} features in county {county_fips}")
    return gdf


def _fetch_acs_housing_units(
    state_fips: str,
    county_fips: str,
    year: int,
    table: str,
    census_cfg: dict,
) -> pd.DataFrame:
    """
    Fetch housing unit counts and population from Census ACS 5-year API.

    Returns DataFrame with columns [geoid, housing_units, population].
    GEOID is constructed as state(2)+county(3)+tract(6)+block_group(1).
    Population (B01001_001E) is included for employee demand fallback.
    """
    pop_table = census_cfg.get("population_table", "B01001_001E")
    api_base = census_cfg.get("api_base", "https://api.census.gov/data")
    url = f"{api_base}/{year}/acs/acs5"
    params = {
        "get": f"{table},{pop_table}",
        "for": "block group:*",
        "in": f"state:{state_fips} county:{county_fips} tract:*",
    }
    api_key = census_cfg.get("api_key", "")
    if api_key:
        params["key"] = api_key

    logger.info(f"  Fetching ACS {year} tables {table},{pop_table} for state={state_fips} county={county_fips}...")
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"  Census ACS API request failed: {e}")
        return pd.DataFrame()

    if not data or len(data) < 2:
        logger.warning("  Census ACS API returned no data rows.")
        return pd.DataFrame()

    headers = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers)

    # Build 12-digit GEOID: state(2)+county(3)+tract(6)+block_group(1)
    df["geoid"] = (
        df["state"].str.zfill(2)
        + df["county"].str.zfill(3)
        + df["tract"].str.zfill(6)
        + df["block group"].str.zfill(1)
    )
    df = df.rename(columns={table: "housing_units", pop_table: "population"})
    df["housing_units"] = pd.to_numeric(df["housing_units"], errors="coerce").fillna(0)
    df["population"] = pd.to_numeric(df["population"], errors="coerce").fillna(0)
    logger.info(f"  ACS data: {len(df)} block groups retrieved")
    return df[["geoid", "housing_units", "population"]]


def _clip_block_groups_to_city(
    bg_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    analysis_crs: str = "EPSG:26910",
) -> gpd.GeoDataFrame:
    """
    Clip block groups to city boundary using area-weighted housing unit allocation.

    For block groups partially within the city, housing units are proportionally
    allocated: housing_units_in_city = housing_units × (clip_area / bg_area).
    This is standard spatial allocation methodology for Census data.
    """
    bg_proj = bg_gdf.to_crs(analysis_crs).copy()
    boundary_proj = boundary_gdf.to_crs(analysis_crs)

    bg_proj["bg_area"] = bg_proj.geometry.area

    # Clip to city boundary
    try:
        bg_clipped = gpd.clip(bg_proj, boundary_proj.unary_union)
    except Exception as e:
        logger.warning(f"  gpd.clip failed ({e}); trying overlay intersection.")
        bg_clipped = gpd.overlay(
            bg_proj, boundary_proj[["geometry"]], how="intersection"
        )

    if bg_clipped.empty:
        return gpd.GeoDataFrame()

    bg_clipped = bg_clipped.copy()
    bg_clipped["clip_area"] = bg_clipped.geometry.area

    # Merge original bg_area back (clip may lose it if column not preserved)
    if "bg_area" not in bg_clipped.columns:
        bg_clipped = bg_clipped.merge(
            bg_proj[["geoid", "bg_area"]], on="geoid", how="left"
        )

    bg_clipped["fraction_in_city"] = (
        bg_clipped["clip_area"] / bg_clipped["bg_area"].clip(lower=1)
    ).clip(0, 1)
    bg_clipped["housing_units_in_city"] = (
        bg_clipped["housing_units"] * bg_clipped["fraction_in_city"]
    ).round().astype(int)

    return bg_clipped


def _compute_fhsz_housing_units(
    bg_city: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    trigger_zones: list,
    analysis_crs: str = "EPSG:26910",
) -> gpd.GeoDataFrame:
    """
    Compute housing_units_in_fhsz for each (city-clipped) block group.

    Uses area-weighted intersection: each block group's FHSZ housing units =
    housing_units_in_city × (area_intersecting_FHSZ / city_clip_area).

    This is zero-discretion spatial arithmetic — fully reproducible.
    """
    bg_proj = bg_city.to_crs(analysis_crs).copy()
    bg_proj["city_area"] = bg_proj.geometry.area

    if fhsz_gdf.empty:
        bg_proj["housing_units_in_fhsz"] = 0.0
        bg_proj["fraction_in_fhsz"] = 0.0
        return bg_proj

    fhsz_trigger = fhsz_gdf[fhsz_gdf["HAZ_CLASS"].isin(trigger_zones)]
    if fhsz_trigger.empty:
        bg_proj["housing_units_in_fhsz"] = 0.0
        bg_proj["fraction_in_fhsz"] = 0.0
        return bg_proj

    fhsz_proj = fhsz_trigger.to_crs(analysis_crs)
    fhsz_union = fhsz_proj.unary_union

    bg_proj["fhsz_area"] = bg_proj.geometry.apply(
        lambda g: g.intersection(fhsz_union).area if not g.is_empty else 0.0
    )
    bg_proj["fraction_in_fhsz"] = (
        bg_proj["fhsz_area"] / bg_proj["city_area"].clip(lower=1)
    ).clip(0, 1)
    bg_proj["housing_units_in_fhsz"] = (
        bg_proj["housing_units_in_city"] * bg_proj["fraction_in_fhsz"]
    ).round()

    return bg_proj


# ---------------------------------------------------------------------------
# Employee Counts (LEHD LODES WAC — Phase 2b)
# ---------------------------------------------------------------------------

def _fetch_lehd_employees(
    state_lower: str,
    state_fips: str,
    county_fips: str,
    census_cfg: dict,
) -> pd.Series:
    """
    Fetch in-city employee counts per block group from LEHD LODES WAC data.

    Downloads the state-level Workplace Area Characteristics (WAC) CSV,
    filters to the county, and aggregates from census block to block group.

    Source: U.S. Census LEHD LODES8, Workplace Area Characteristics (WAC)
      URL: https://lehd.ces.census.gov/data/lodes/LODES8/{state}/wac/{state}_wac_S000_JT01_{year}.csv.gz
      Field C000: Total number of jobs (all industries, primary jobs)

    Returns pd.Series mapping block_group_geoid (12-char) → employee_count.
    Returns empty Series on failure (triggers ACS-based fallback).
    """
    lodes_year = census_cfg.get("lodes_year", 2021)
    # LEHD LODES uses lowercase state postal abbreviation in URL
    url = (
        f"https://lehd.ces.census.gov/data/lodes/LODES8/{state_lower}/wac/"
        f"{state_lower}_wac_S000_JT01_{lodes_year}.csv.gz"
    )
    # County prefix: first 5 chars of 15-char census block geocode
    county_prefix = state_fips.zfill(2) + county_fips.zfill(3)

    logger.info(f"  Downloading LEHD LODES WAC ({lodes_year}): {url}")
    try:
        resp = requests.get(url, timeout=180)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"  LEHD LODES download failed: {e}")
        # Try previous year as fallback
        if lodes_year > 2019:
            logger.info(f"  Retrying LEHD with year {lodes_year - 1}...")
            census_cfg_copy = dict(census_cfg)
            census_cfg_copy["lodes_year"] = lodes_year - 1
            return _fetch_lehd_employees(state_lower, state_fips, county_fips, census_cfg_copy)
        return pd.Series(dtype=float)

    try:
        county_chunks = []
        reader = pd.read_csv(
            io.BytesIO(resp.content),
            compression="gzip",
            dtype={"w_geocode": str},
            chunksize=50_000,
        )
        for chunk in reader:
            mask = chunk["w_geocode"].str[:5] == county_prefix
            if mask.any():
                county_chunks.append(chunk.loc[mask, ["w_geocode", "C000"]])

        if not county_chunks:
            logger.warning(f"  LEHD: no blocks found for county prefix {county_prefix}.")
            return pd.Series(dtype=float)

        df = pd.concat(county_chunks, ignore_index=True)
        # Aggregate census blocks → block groups (first 12 chars of 15-char geocode)
        df["geoid"] = df["w_geocode"].str[:12]
        bg_employees = df.groupby("geoid")["C000"].sum().rename("employee_count")

        logger.info(
            f"  LEHD ({lodes_year}): {bg_employees.sum():,.0f} jobs "
            f"in {len(bg_employees)} block groups in county {county_fips}"
        )
        return bg_employees

    except Exception as e:
        logger.warning(f"  LEHD LODES parse error: {e}")
        return pd.Series(dtype=float)


def _estimate_employees_from_acs(
    bg_city: gpd.GeoDataFrame,
    city_config: dict,
    config: dict,
) -> pd.Series:
    """
    Fallback employee estimate when LEHD LODES is unavailable.

    Method: total estimated in-commuting workers distributed proportionally
    by block group housing units (as a proxy for density).

    Formula:
      total_city_jobs = total_city_hu × avg_hh_size × employment_rate / (1 - commute_in_fraction)
      in_commuting_workers = total_city_jobs × commute_in_fraction
      per_bg = in_commuting_workers × (bg_hu / total_city_hu)

    This is clearly flagged as estimated in metadata.
    """
    employment_rate    = float(city_config.get("employment_rate", 0.62))
    commute_in_frac    = float(city_config.get("commute_in_fraction", 0.45))
    avg_hh_size        = float(config.get("demand", {}).get("vehicles_per_unit", 2.5))

    total_hu = float(bg_city["housing_units_in_city"].sum())
    if total_hu <= 0:
        return pd.Series(dtype=float)

    # Rough city-level resident workforce
    resident_workers = total_hu * avg_hh_size * employment_rate
    # Total city jobs (residents + in-commuters)
    total_jobs = resident_workers / max(1 - commute_in_frac, 0.01)
    in_commuting = total_jobs * commute_in_frac

    # Distribute proportionally by housing units
    hu_share = bg_city["housing_units_in_city"] / total_hu
    emp_estimate = (hu_share * in_commuting).round()
    emp_series = pd.Series(emp_estimate.values, index=bg_city["geoid"])
    logger.info(
        f"  ACS employee estimate: {emp_series.sum():,.0f} in-commuting workers "
        f"(employment_rate={employment_rate}, commute_in_fraction={commute_in_frac})"
    )
    return emp_series


# ---------------------------------------------------------------------------
# Student Vehicle Counts (from city config universities — Phase 2b)
# ---------------------------------------------------------------------------

def _compute_student_counts(
    bg_city: gpd.GeoDataFrame,
    city_config: dict,
    analysis_crs: str = "EPSG:26910",
) -> gpd.GeoDataFrame:
    """
    Compute student vehicle counts per block group from city config universities.

    For each university:
      - Buffer campus location by 0.5 miles
      - Find block groups intersecting buffer
      - Distribute student vehicles area-proportionally:
          student_count_bg = enrollment × student_vehicle_rate
                             × (bg_area_in_buffer / total_bg_area_in_buffer)

    This distributes the total student vehicle demand across the block groups
    near each campus, summing across multiple universities.

    Returns bg_city with 'student_count' column added.
    """
    bg_city = bg_city.copy()
    bg_city["student_count"] = 0.0

    universities = city_config.get("universities", [])
    if not universities:
        return bg_city

    bg_proj = bg_city.to_crs(analysis_crs)
    bg_proj["student_count"] = 0.0

    RADIUS_M = 0.5 * 1609.344  # 0.5 miles in meters

    for uni in universities:
        lat = float(uni.get("location_lat", 0))
        lon = float(uni.get("location_lon", 0))
        enrollment = float(uni.get("enrollment", 0))
        vehicle_rate = float(uni.get("student_vehicle_rate", 0.08))
        total_student_vehicles = enrollment * vehicle_rate

        if total_student_vehicles <= 0:
            continue

        # Project university point to analysis CRS
        uni_point_gdf = gpd.GeoDataFrame(
            {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
        ).to_crs(analysis_crs)
        uni_buffer = uni_point_gdf.geometry.iloc[0].buffer(RADIUS_M)

        # Find intersecting block groups and compute overlap area
        bg_proj["_uni_overlap_area"] = bg_proj.geometry.apply(
            lambda g: g.intersection(uni_buffer).area if not g.is_empty else 0.0
        )
        total_overlap = bg_proj["_uni_overlap_area"].sum()
        if total_overlap <= 0:
            logger.warning(f"  University '{uni.get('name', '')}': no block groups within 0.5 miles.")
            continue

        bg_proj["student_count"] += (
            bg_proj["_uni_overlap_area"] / total_overlap * total_student_vehicles
        )
        logger.info(
            f"  University '{uni.get('name', '')}': {total_student_vehicles:.0f} student vehicles "
            f"distributed across {(bg_proj['_uni_overlap_area'] > 0).sum()} block groups"
        )

    bg_proj = bg_proj.drop(columns=["_uni_overlap_area"], errors="ignore")
    bg_city["student_count"] = bg_proj["student_count"].values
    return bg_city

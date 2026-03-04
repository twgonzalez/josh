"""
Agent 3: Objective Standards Engine

Provides zero-discretion determination of ministerial vs. discretionary review
for proposed development projects in California cities.

All four standards are algorithmic — no professional judgment, no discretion.
Every calculation is stored for a complete audit trail.

Legal basis: AB 747 (California Government Code Section 65913.4)
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from models.project import Project

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def evaluate_project(
    project: Project,
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    config: dict,
    city_config: dict,
) -> tuple[Project, dict]:
    """
    Run all four objective standards and produce a final determination.

    Returns:
        (updated Project, audit_trail dict)
    """
    audit = {
        "evaluation_date": datetime.now().isoformat(),
        "project": project.to_dict(),
        "parameters_used": {
            "vc_threshold": config.get("vc_threshold", 0.80),
            "unit_threshold": config.get("unit_threshold", 50),
            "vehicles_per_unit": config.get("vehicles_per_unit", 2.5),
            "peak_hour_mobilization": config.get("peak_hour_mobilization", 0.57),
            "evacuation_route_radius_miles": config.get("evacuation_route_radius_miles", 0.5),
        },
        "standards": {},
    }

    # Standard 1: Fire Zone
    std1_result, std1_detail = check_fire_zone(
        (project.location_lat, project.location_lon),
        fhsz_gdf,
    )
    project.in_fire_zone = std1_result
    project.fire_zone_level = std1_detail.get("zone_level", 0)
    audit["standards"]["standard_1_fire_zone"] = std1_detail

    # Standard 2: Size Threshold
    threshold = config.get("unit_threshold", 50)
    std2_result, std2_detail = check_size_threshold(project.dwelling_units, threshold)
    project.meets_size_threshold = std2_result
    project.size_threshold_used = threshold
    audit["standards"]["standard_2_size_threshold"] = std2_detail

    # Standard 3: Serving Routes
    radius = config.get("evacuation_route_radius_miles", 0.5)
    analysis_crs = city_config.get("analysis_crs", "EPSG:26910")
    serving_ids, std3_detail = identify_serving_routes(
        (project.location_lat, project.location_lon),
        roads_gdf,
        radius,
        analysis_crs,
    )
    project.serving_route_ids = serving_ids
    project.search_radius_miles = radius
    audit["standards"]["standard_3_serving_routes"] = std3_detail

    # Standard 4: Capacity Threshold
    exceeds, project_vph, std4_detail = check_capacity_threshold(
        serving_ids,
        project.dwelling_units,
        roads_gdf,
        config,
    )
    project.exceeds_capacity_threshold = exceeds
    project.project_vehicles_peak_hour = project_vph
    project.flagged_route_ids = std4_detail.get("flagged_route_ids", [])
    audit["standards"]["standard_4_capacity_threshold"] = std4_detail

    # Final Determination
    if std1_result and std2_result and exceeds:
        project.determination = "DISCRETIONARY"
        project.determination_reason = (
            "Project is in FHSZ Zone 2 or 3 (Standard 1), "
            "meets the size threshold (Standard 2), "
            "and at least one serving evacuation route exceeds the v/c threshold (Standard 4). "
            "Discretionary review is required per AB 747."
        )
    else:
        project.determination = "MINISTERIAL"
        reasons = []
        if not std1_result:
            reasons.append("project is not in FHSZ Zone 2 or 3 (Standard 1 not triggered)")
        if not std2_result:
            reasons.append(f"project has fewer than {threshold} dwelling units (Standard 2 not triggered)")
        if not exceeds:
            reasons.append("no serving evacuation route exceeds the v/c threshold (Standard 4 not triggered)")
        project.determination_reason = "Ministerial approval eligible because: " + "; ".join(reasons) + "."

    audit["determination"] = {
        "result": project.determination,
        "standard_1_triggered": std1_result,
        "standard_2_triggered": std2_result,
        "standard_4_triggered": exceeds,
        "logic": "DISCRETIONARY if std1 AND std2 AND std4, else MINISTERIAL",
        "reason": project.determination_reason,
    }

    return project, audit


# ---------------------------------------------------------------------------
# Standard 1: Fire Zone Determination
# ---------------------------------------------------------------------------

def check_fire_zone(
    location: tuple[float, float],
    fhsz_gdf: gpd.GeoDataFrame,
) -> tuple[bool, dict]:
    """
    Standard 1: Is the project in FHSZ Zone 2 or Zone 3?

    Method: GIS point-in-polygon test
    Discretion: Zero — binary result from spatial query

    Returns:
        (is_in_trigger_zone: bool, detail dict for audit trail)
    """
    lat, lon = location
    project_point = gpd.GeoDataFrame(
        {"geometry": [Point(lon, lat)]},
        crs="EPSG:4326",
    )

    if fhsz_gdf.empty:
        return False, {
            "result": False,
            "zone_level": 0,
            "note": "FHSZ data unavailable — defaulting to not in fire zone (conservative for ministerial)",
        }

    fhsz_wgs84 = fhsz_gdf.to_crs("EPSG:4326")
    joined = gpd.sjoin(project_point, fhsz_wgs84, how="left", predicate="within")

    detail = {
        "input_lat": lat,
        "input_lon": lon,
        "method": "GIS point-in-polygon (shapely/geopandas)",
        "data_source": "CAL FIRE FHSZ",
    }

    if joined.empty or joined["HAZ_CLASS"].isna().all():
        detail.update({"result": False, "zone_level": 0, "zone_description": "Not in FHSZ"})
        return False, detail

    zone_level = int(joined["HAZ_CLASS"].dropna().max())
    in_trigger = zone_level >= 2

    detail.update({
        "result": in_trigger,
        "zone_level": zone_level,
        "zone_description": {0: "Not in FHSZ", 1: "Zone 1 (Moderate)", 2: "Zone 2 (High)", 3: "Zone 3 (Very High)"}.get(zone_level, f"Zone {zone_level}"),
        "triggers_standard": in_trigger,
    })
    return in_trigger, detail


# ---------------------------------------------------------------------------
# Standard 2: Project Size Threshold
# ---------------------------------------------------------------------------

def check_size_threshold(
    units: int,
    threshold: int,
) -> tuple[bool, dict]:
    """
    Standard 2: Does the project include >= threshold dwelling units?

    Method: Integer comparison
    Discretion: Zero

    Returns:
        (meets_threshold: bool, detail dict)
    """
    result = units >= threshold
    return result, {
        "dwelling_units": units,
        "threshold": threshold,
        "result": result,
        "method": f"{units} >= {threshold}",
        "triggers_standard": result,
    }


# ---------------------------------------------------------------------------
# Standard 3: Serving Evacuation Routes
# ---------------------------------------------------------------------------

def identify_serving_routes(
    location: tuple[float, float],
    roads_gdf: gpd.GeoDataFrame,
    radius_miles: float,
    analysis_crs: str,
) -> tuple[list, dict]:
    """
    Standard 3: Which evacuation routes serve this project?

    Method: Buffer project location by radius, find intersecting evacuation routes
    Discretion: Zero — algorithmic spatial query

    Returns:
        (list of segment osmids, detail dict)
    """
    lat, lon = location
    project_point = gpd.GeoDataFrame(
        {"geometry": [Point(lon, lat)]},
        crs="EPSG:4326",
    ).to_crs(analysis_crs)

    roads_proj = roads_gdf.to_crs(analysis_crs)

    radius_meters = radius_miles * 1609.344  # miles to meters
    buffer = project_point.geometry.iloc[0].buffer(radius_meters)

    if "is_evacuation_route" not in roads_proj.columns:
        # If no evacuation routes identified yet, use all roads in radius
        nearby = roads_proj[roads_proj.geometry.intersects(buffer)]
        evac_nearby = nearby
    else:
        evac_only = roads_proj[roads_proj["is_evacuation_route"] == True]
        evac_nearby = evac_only[evac_only.geometry.intersects(buffer)]

    serving_ids = evac_nearby["osmid"].tolist()

    detail = {
        "project_lat": lat,
        "project_lon": lon,
        "radius_miles": radius_miles,
        "radius_meters": round(radius_meters, 1),
        "method": "Buffer + intersect with evacuation route segments",
        "serving_route_count": len(evac_nearby),
        "serving_routes": [
            {
                "osmid": str(row["osmid"]),
                "name": row.get("name", ""),
                "vc_ratio": round(row.get("vc_ratio", 0), 4),
                "los": row.get("los", ""),
                "capacity_vph": round(row.get("capacity_vph", 0), 0),
                "baseline_demand_vph": round(row.get("baseline_demand_vph", 0), 1),
            }
            for _, row in evac_nearby.iterrows()
        ],
    }
    return serving_ids, detail


# ---------------------------------------------------------------------------
# Standard 4: Capacity Threshold Test
# ---------------------------------------------------------------------------

def check_capacity_threshold(
    serving_route_ids: list,
    dwelling_units: int,
    roads_gdf: gpd.GeoDataFrame,
    config: dict,
) -> tuple[bool, float, dict]:
    """
    Standard 4: Do any serving routes exceed the v/c threshold?

    Two tests (either triggers discretionary):
    A) Baseline test: does any route have baseline_vc >= threshold?
    B) Proposed test: after adding project vehicles, does any route exceed threshold?

    Vehicle distribution: project vehicles distributed equally across all serving routes.

    Returns:
        (exceeds_threshold: bool, project_vph: float, detail dict)
    """
    vc_threshold = config.get("vc_threshold", 0.80)
    vehicles_per_unit = config.get("vehicles_per_unit", 2.5)
    peak_hour_factor = config.get("peak_hour_mobilization", 0.57)

    # Project vehicle generation (Standard 4 formula)
    project_vph = dwelling_units * vehicles_per_unit * peak_hour_factor
    vehicles_per_route = project_vph / max(len(serving_route_ids), 1)

    serving_routes = roads_gdf[
        roads_gdf["osmid"].apply(lambda o: o in serving_route_ids or
            (isinstance(o, list) and any(x in serving_route_ids for x in o)))
    ].copy()

    route_results = []
    baseline_flagged = []
    proposed_flagged = []

    for _, row in serving_routes.iterrows():
        baseline_vc = row.get("vc_ratio", 0.0)
        capacity = row.get("capacity_vph", 0.0)
        baseline_demand = row.get("baseline_demand_vph", 0.0)

        proposed_demand = baseline_demand + vehicles_per_route
        proposed_vc = calculate_proposed_vc(proposed_demand, capacity)

        baseline_exceeds = baseline_vc >= vc_threshold
        proposed_exceeds = proposed_vc > vc_threshold

        if baseline_exceeds:
            baseline_flagged.append(str(row.get("osmid", "")))
        if proposed_exceeds:
            proposed_flagged.append(str(row.get("osmid", "")))

        route_results.append({
            "osmid": str(row.get("osmid", "")),
            "name": row.get("name", ""),
            "capacity_vph": round(capacity, 0),
            "baseline_demand_vph": round(baseline_demand, 1),
            "baseline_vc": round(baseline_vc, 4),
            "baseline_exceeds": baseline_exceeds,
            "vehicles_added": round(vehicles_per_route, 1),
            "proposed_demand_vph": round(proposed_demand, 1),
            "proposed_vc": round(proposed_vc, 4),
            "proposed_exceeds": proposed_exceeds,
        })

    any_flagged = bool(baseline_flagged or proposed_flagged)
    flagged_ids = list(set(baseline_flagged + proposed_flagged))

    detail = {
        "vc_threshold": vc_threshold,
        "vehicles_per_unit": vehicles_per_unit,
        "peak_hour_mobilization": peak_hour_factor,
        "project_vehicles_formula": f"{dwelling_units} units × {vehicles_per_unit} veh/unit × {peak_hour_factor} peak factor",
        "project_vehicles_peak_hour": round(project_vph, 1),
        "vehicles_per_route": round(vehicles_per_route, 1),
        "serving_routes_evaluated": len(serving_routes),
        "baseline_test_flagged": baseline_flagged,
        "proposed_test_flagged": proposed_flagged,
        "flagged_route_ids": flagged_ids,
        "result": any_flagged,
        "triggers_standard": any_flagged,
        "route_details": route_results,
    }

    return any_flagged, project_vph, detail


def calculate_proposed_vc(proposed_demand: float, capacity: float) -> float:
    """Calculate proposed v/c ratio after adding project vehicles."""
    if capacity <= 0:
        return 0.0
    return proposed_demand / capacity


# ---------------------------------------------------------------------------
# Output: Audit Trail
# ---------------------------------------------------------------------------

def generate_audit_trail(
    project: Project,
    audit: dict,
    output_path: Path,
) -> str:
    """
    Write a human-readable audit trail document for legal compliance.

    Returns the text content (also written to output_path).
    """
    lines = [
        "=" * 70,
        "FIRE EVACUATION CAPACITY ANALYSIS — PROJECT DETERMINATION",
        "=" * 70,
        f"Date: {audit['evaluation_date']}",
        f"Project: {project.project_name or 'Unnamed'}",
        f"Address: {project.address or 'Not provided'}",
        f"APN: {project.apn or 'Not provided'}",
        f"Location: {project.location_lat}, {project.location_lon}",
        f"Dwelling Units: {project.dwelling_units}",
        "",
        "PARAMETERS USED",
        "-" * 40,
    ]

    for k, v in audit["parameters_used"].items():
        lines.append(f"  {k}: {v}")

    lines += [
        "",
        "STANDARD 1: FIRE HAZARD SEVERITY ZONE",
        "-" * 40,
    ]
    s1 = audit["standards"]["standard_1_fire_zone"]
    lines.append(f"  Method: {s1.get('method', '')}")
    lines.append(f"  Zone: {s1.get('zone_description', '')}")
    lines.append(f"  Triggers Standard: {'YES' if s1.get('result') else 'NO'}")

    lines += [
        "",
        "STANDARD 2: PROJECT SIZE THRESHOLD",
        "-" * 40,
    ]
    s2 = audit["standards"]["standard_2_size_threshold"]
    lines.append(f"  Dwelling Units: {s2['dwelling_units']}")
    lines.append(f"  Threshold: {s2['threshold']}")
    lines.append(f"  Calculation: {s2['method']}")
    lines.append(f"  Triggers Standard: {'YES' if s2['result'] else 'NO'}")

    lines += [
        "",
        "STANDARD 3: SERVING EVACUATION ROUTES",
        "-" * 40,
    ]
    s3 = audit["standards"]["standard_3_serving_routes"]
    lines.append(f"  Search Radius: {s3['radius_miles']} miles ({s3['radius_meters']} meters)")
    lines.append(f"  Method: {s3['method']}")
    lines.append(f"  Routes Found: {s3['serving_route_count']}")
    for r in s3.get("serving_routes", []):
        lines.append(f"    - {r['name'] or r['osmid']}: v/c={r['vc_ratio']}, LOS={r['los']}, "
                     f"cap={r['capacity_vph']:.0f} vph, demand={r['baseline_demand_vph']:.1f} vph")

    lines += [
        "",
        "STANDARD 4: CAPACITY THRESHOLD TEST",
        "-" * 40,
    ]
    s4 = audit["standards"]["standard_4_capacity_threshold"]
    lines.append(f"  V/C Threshold: {s4['vc_threshold']}")
    lines.append(f"  Project Vehicle Generation: {s4['project_vehicles_formula']}")
    lines.append(f"  Project Vehicles (peak hour): {s4['project_vehicles_peak_hour']}")
    lines.append(f"  Vehicles Added Per Route: {s4['vehicles_per_route']}")
    lines.append("")
    lines.append("  Route-by-Route Results:")
    for r in s4.get("route_details", []):
        flag = " *** FLAGGED ***" if r["baseline_exceeds"] or r["proposed_exceeds"] else ""
        lines.append(f"    {r['name'] or r['osmid']}:{flag}")
        lines.append(f"      Baseline: demand={r['baseline_demand_vph']:.1f} vph, "
                     f"v/c={r['baseline_vc']:.4f} {'[EXCEEDS]' if r['baseline_exceeds'] else '[OK]'}")
        lines.append(f"      Proposed: demand={r['proposed_demand_vph']:.1f} vph (+{r['vehicles_added']:.1f}), "
                     f"v/c={r['proposed_vc']:.4f} {'[EXCEEDS]' if r['proposed_exceeds'] else '[OK]'}")
    lines.append(f"  Triggers Standard: {'YES' if s4['result'] else 'NO'}")

    lines += [
        "",
        "=" * 70,
        "FINAL DETERMINATION",
        "=" * 70,
        f"  RESULT: {project.determination}",
        "",
        f"  {project.determination_reason}",
        "",
        "  Determination Logic:",
        "    IF Standard 1 (fire zone) AND Standard 2 (size) AND Standard 4 (capacity)",
        "    THEN: DISCRETIONARY REVIEW REQUIRED",
        "    ELSE: MINISTERIAL APPROVAL ELIGIBLE",
        "",
        f"  Standard 1 triggered: {'YES' if audit['determination']['standard_1_triggered'] else 'NO'}",
        f"  Standard 2 triggered: {'YES' if audit['determination']['standard_2_triggered'] else 'NO'}",
        f"  Standard 4 triggered: {'YES' if audit['determination']['standard_4_triggered'] else 'NO'}",
        "",
        "  This determination is based solely on objective, verifiable criteria.",
        "  No professional discretion was applied. All calculations are reproducible.",
        "=" * 70,
    ]

    text = "\n".join(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text)
    logger.info(f"Audit trail written to: {output_path}")

    return text

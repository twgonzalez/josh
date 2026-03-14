# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Scenario A: Wildland Evacuation Capacity (Standards 1–4) — JOSH v3.2

Legal basis: AB 747 (California Government Code §65302.15), HCM 2022,
NFPA 101 (Life Safety Code) mobilization design basis.

ΔT Standard (v3.2):
  Standard 1 — Project Size:       units >= threshold (scale gate)
  Standard 2 — Evac Routes Served: network buffer → identifies serving EvacuationPaths
  Standard 3 — FHSZ Modifier:      GIS point-in-polygon; sets hazard_zone string which
                                    controls ROAD capacity degradation and ΔT threshold
                                    (FHSZ does NOT affect mobilization in v3.2)
  Standard 4 — ΔT Test:            ΔT = (project_vehicles / bottleneck_effective_capacity) × 60 + egress
                                    Project is DISCRETIONARY if ΔT > threshold for hazard_zone
                                    threshold = safe_egress_window(zone) × max_project_share

Key v3.2 changes from v3.1:
  - Mobilization rate is now constant 0.90 (NFPA 101 design basis)
  - FHSZ zone now affects ONE thing only: road capacity (hazard_degradation factor)
  - Removed tiered mob rates (Zhao et al. 2022) — behavioral observation ≠ design standard
  - Berkeley regression test: 75-unit non-FHSZ hills → DISCRETIONARY (was MINISTERIAL WITH STANDARD CONDITIONS under v3.1)

Key v3.0 changes from v2.0:
  - No baseline precondition: routes already at LOS F are tested equally
  - Hazard-aware capacity degradation (HCM composite factors) applied upstream by Agent 2
  - Building egress penalty (NFPA 101/IBC) added to ΔT for buildings ≥ 4 stories
  - Returns EvacuationPath objects (not osmid lists) from identify_routes()

Three-tier output:
  DISCRETIONARY           — size threshold met AND ΔT > threshold (safe_egress_window × max_project_share) on any serving path
  MINISTERIAL WITH STANDARD CONDITIONS — size threshold met AND ΔT within threshold on all paths
  MINISTERIAL             — below size threshold
"""
import logging

import geopandas as gpd
from shapely.geometry import Point

from models.project import Project
from models.evacuation_path import EvacuationPath
from .base import EvacuationScenario, Tier

logger = logging.getLogger(__name__)

_LEGAL_BASIS = (
    "AB 747 (California Government Code §65302.15) — General Plan Safety Element "
    "mandatory update for evacuation route capacity analysis; "
    "HCM 2022 (Highway Capacity Manual, 7th Edition) — effective capacity with hazard degradation; "
    "NFPA 101 (Life Safety Code) — 0.90 mobilization design basis (100% occupant evacuation, "
    "adjusted for ~10% zero-vehicle households per Census ACS B25044); "
    "NIST TN 2135 (Maranghides et al.) — safe egress windows by hazard zone"
)

# HAZ_CLASS integer → canonical hazard_zone key (matches safe_egress_window and hazard_degradation keys)
_HAZ_CLASS_TO_ZONE = {
    3: "vhfhsz",
    2: "high_fhsz",
    1: "moderate_fhsz",
    0: "non_fhsz",
}


class WildlandScenario(EvacuationScenario):
    """
    Evaluates wildland evacuation capacity impact (Standards 1–4) using v3.0 ΔT metric.

    Standard 1 (size) gates the analysis.
    Standard 3 (FHSZ modifier) sets project.hazard_zone which controls:
      - ΔT threshold (safe_egress_window × max_project_share by hazard zone)
      - capacity degradation factor (applied upstream in Agent 2 to road segments)
      NOTE (v3.2): FHSZ does NOT affect mobilization. Mobilization is constant 0.90 (NFPA 101).
    Standard 4 (ΔT test) uses compute_delta_t() from base class.
    """

    @property
    def name(self) -> str:
        return "wildland_ab747"

    @property
    def legal_basis(self) -> str:
        return _LEGAL_BASIS

    @property
    def unit_threshold(self) -> int:
        return int(self.config.get("unit_threshold", 15))

    @property
    def fallback_tier(self) -> Tier:
        return Tier.CONDITIONAL_MINISTERIAL

    # ------------------------------------------------------------------
    # Step 1: Applicability — always applicable; sets FHSZ hazard zone
    # ------------------------------------------------------------------

    def check_applicability(self, project: Project, context: dict) -> tuple[bool, dict]:
        """
        Standard 3 (FHSZ Modifier): Sets project.hazard_zone based on site location.

        This scenario is ALWAYS applicable — the citywide FHSZ gate was removed in v3.0.

        The GIS point-in-polygon test determines project.hazard_zone, which controls:
          - ΔT threshold via config["safe_egress_window"][hazard_zone] × config["max_project_share"]
          - road capacity degradation (applied upstream in Agent 2)
          NOTE (v3.2): FHSZ does NOT affect mobilization rate. Mobilization is constant 0.90.

        Method: GIS point-in-polygon test against CAL FIRE FHSZ zones.
        Discretion: Zero — binary spatial result with deterministic zone mapping.
        """
        fhsz_gdf = context.get("fhsz_gdf", gpd.GeoDataFrame())

        fire_zone_result, fire_zone_detail = check_fire_zone(
            (project.location_lat, project.location_lon), fhsz_gdf
        )

        # Set project fire zone fields
        project.in_fire_zone    = fire_zone_result
        project.fire_zone_level = fire_zone_detail.get("zone_level", 0)
        project.hazard_zone     = fire_zone_detail.get("hazard_zone", "non_fhsz")

        # Mobilization is constant (NFPA 101 design basis) — not FHSZ-dependent
        project.mobilization_rate = self.config.get("mobilization_rate", 0.90)

        return True, {
            "result":                    True,
            "method":                    "Always applicable; site FHSZ check via GIS point-in-polygon",
            "std3_fhsz_flagged":         fire_zone_result,
            "std3_zone_level":           project.fire_zone_level,
            "std3_zone_desc":            fire_zone_detail.get("zone_description", "Not in FHSZ"),
            "std3_hazard_zone":          project.hazard_zone,
            "std3_mobilization_rate":    project.mobilization_rate,
            "fire_zone_severity_modifier": fire_zone_detail,
            "note": (
                f"FHSZ Zone {project.fire_zone_level} ({project.hazard_zone}) — "
                f"road capacity degradation applied; mobilization unaffected. "
                f"Mobilization rate {project.mobilization_rate:.2f} (NFPA 101 design basis, constant)."
                if fire_zone_result else
                f"Not in FHSZ (hazard_zone=non_fhsz) — no road degradation. "
                f"Mobilization rate {project.mobilization_rate:.2f} (NFPA 101 design basis, constant)."
            ),
        }

    # ------------------------------------------------------------------
    # Step 3: Route Identification — serving EvacuationPath objects
    # ------------------------------------------------------------------

    def identify_routes(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> tuple[list, dict]:
        """
        Standard 2 (Evac Routes Served): Which EvacuationPaths serve this project?

        Method:
          1. Buffer project location by evacuation.serving_route_radius_miles.
          2. Find all evacuation route segment osmids within the buffer.
          3. Filter context["evacuation_paths"] to those whose bottleneck_osmid
             or exit_segment_osmid is within the buffer.
          4. If no paths match proximity filter, use all paths (conservative fallback).

        Returns list[EvacuationPath] for consumption by compute_delta_t().
        Discretion: Zero — algorithmic spatial query.
        """
        evac_cfg     = self.config.get("evacuation", {})
        radius       = evac_cfg.get(
            "serving_route_radius_miles",
            self.config.get("evacuation_route_radius_miles", 0.5),
        )
        analysis_crs = self.city_config.get("analysis_crs", "EPSG:26910")

        lat, lon = project.location_lat, project.location_lon
        project_pt = gpd.GeoDataFrame(
            {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
        ).to_crs(analysis_crs)

        roads_proj    = roads_gdf.to_crs(analysis_crs)
        radius_meters = radius * 1609.344
        buffer        = project_pt.geometry.iloc[0].buffer(radius_meters)

        # Find nearby evacuation route segments
        if "is_evacuation_route" not in roads_proj.columns:
            evac_nearby = roads_proj[roads_proj.geometry.intersects(buffer)]
        else:
            evac_only   = roads_proj[roads_proj["is_evacuation_route"] == True]
            evac_nearby = evac_only[evac_only.geometry.intersects(buffer)]

        # Build set of nearby osmids (handle list-type osmid columns)
        nearby_osmids: set[str] = set()
        for osmid_val in evac_nearby["osmid"].tolist():
            if isinstance(osmid_val, list):
                for o in osmid_val:
                    nearby_osmids.add(str(o))
            else:
                nearby_osmids.add(str(osmid_val))

        # Update project display fields
        project.serving_route_ids   = list(nearby_osmids)
        project.search_radius_miles = radius

        # Filter EvacuationPaths from context by proximity of bottleneck only.
        # Exit proximity is intentionally excluded: a path's city-boundary exit can be
        # coincidentally near the project even when the path originates from a distant
        # block group traveling in the wrong direction (e.g., flatland block group whose
        # path exits at a hills boundary near a hills project). The bottleneck is the
        # capacity constraint the project's traffic must pass through; it must be in the
        # project's road shed for the path to be meaningfully "serving" the project.
        all_evac_paths: list = context.get("evacuation_paths", [])
        serving_paths: list[EvacuationPath] = [
            p for p in all_evac_paths
            if str(getattr(p, "bottleneck_osmid", "")) in nearby_osmids
        ]

        fallback_used = False
        if not serving_paths and all_evac_paths:
            # Conservative: if no proximity match, evaluate against all paths
            serving_paths = list(all_evac_paths)
            fallback_used = True
            logger.warning(
                f"  No evacuation paths matched proximity filter for "
                f"({lat:.4f}, {lon:.4f}) — using all {len(all_evac_paths)} paths (conservative)"
            )

        detail = {
            "project_lat":          lat,
            "project_lon":          lon,
            "radius_miles":         radius,
            "radius_meters":        round(radius_meters, 1),
            "method":               (
                "Buffer project location + filter EvacuationPath objects "
                "by bottleneck/exit osmid proximity"
            ),
            "serving_route_count":  len(evac_nearby),
            "serving_paths_count":  len(serving_paths),
            "fallback_all_paths":   fallback_used,
            "triggers_standard":    len(serving_paths) > 0,
            "serving_routes": [
                {
                    "osmid":                  str(row["osmid"]),
                    "name":                   row.get("name", ""),
                    "fhsz_zone":              row.get("fhsz_zone", "non_fhsz"),
                    "hazard_degradation":     row.get("hazard_degradation", 1.0),
                    "effective_capacity_vph": round(
                        row.get("effective_capacity_vph", row.get("capacity_vph", 0)), 0
                    ),
                    "vc_ratio":               round(row.get("vc_ratio", 0), 4),
                    "los":                    row.get("los", ""),
                }
                for _, row in evac_nearby.iterrows()
            ],
        }
        return serving_paths, detail

    # ------------------------------------------------------------------
    # Override reason builders to include fire zone / ΔT context
    # ------------------------------------------------------------------

    def _reason_discretionary(self, project: Project, step5: dict) -> str:
        max_dt    = step5.get("max_delta_t_minutes", 0.0)
        threshold = step5.get("threshold_minutes", 0.0)
        hz        = step5.get("hazard_zone", "non_fhsz")
        mob       = step5.get("mobilization_rate", 0.90)
        n_paths   = sum(1 for r in step5.get("path_results", []) if r.get("flagged"))
        fire_note = (
            f"FHSZ Zone {project.fire_zone_level} ({hz}) — road capacity degradation applied. "
            if project.in_fire_zone else
            f"Not in FHSZ (hazard_zone={hz}) — no road degradation. "
        )
        return (
            f"Project meets the {self.unit_threshold}-unit applicability threshold and "
            f"{n_paths} serving path(s) exceed the ΔT threshold of {threshold:.2f} min "
            f"(max ΔT: {max_dt:.1f} min). "
            f"{fire_note}"
            f"Mobilization: {mob:.2f} (NFPA 101 design basis, constant). "
            f"Discretionary review required. Legal basis: {self.legal_basis}."
        )

    def _reason_fallback(self, project: Project, step3: dict, step5: dict) -> str:
        n_paths   = step3.get("serving_paths_count", 0)
        max_dt    = step5.get("max_delta_t_minutes", 0.0)
        threshold = step5.get("threshold_minutes", 0.0)
        hz        = step5.get("hazard_zone", "non_fhsz")
        mob       = step5.get("mobilization_rate", 0.90)
        fire_note = (
            f"FHSZ Zone {project.fire_zone_level} ({hz}) — road capacity degradation applied. "
            if project.in_fire_zone else
            f"Not in FHSZ (hazard_zone={hz}) — no road degradation. "
        )
        return (
            f"Project meets the {self.unit_threshold}-unit applicability threshold and "
            f"has {n_paths} serving path(s). "
            f"Max ΔT {max_dt:.1f} min within threshold ({threshold:.2f} min). "
            f"{fire_note}"
            f"Mobilization: {mob:.2f} (NFPA 101 design basis, constant). "
            f"Ministerial approval with standard conditions applied automatically. "
            f"Legal basis: {self.legal_basis}."
        )


# ---------------------------------------------------------------------------
# Helper functions (module-level — reusable and independently testable)
# ---------------------------------------------------------------------------

def check_fire_zone(
    location: tuple[float, float],
    fhsz_gdf: gpd.GeoDataFrame,
) -> tuple[bool, dict]:
    """
    Standard 3 (FHSZ Modifier): Is the project site in FHSZ Zone 2 or 3?

    Returns (in_trigger_zone: bool, detail: dict).
    detail["hazard_zone"] contains the canonical zone key for mobilization_rate lookup.

    HAZ_CLASS mapping:
      3 → "vhfhsz" (Very High)
      2 → "high_fhsz" (High) — trigger zone
      1 → "moderate_fhsz" (Moderate)
      0 → "non_fhsz"

    in_trigger_zone is True for HAZ_CLASS >= 2 (High and Very High).
    Moderate FHSZ (HAZ_CLASS=1) sets hazard_zone="moderate_fhsz" but returns False
    (does not trigger FHSZ status; mobilization_rate applied via hazard_zone lookup).
    Discretion: Zero — binary spatial result.
    """
    lat, lon = location
    project_pt = gpd.GeoDataFrame(
        {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
    )

    detail = {
        "input_lat":   lat,
        "input_lon":   lon,
        "method":      "GIS point-in-polygon (shapely/geopandas sjoin)",
        "data_source": "CAL FIRE FHSZ",
        "role":        "Sets hazard_zone for mobilization_rate and ΔT threshold lookup",
    }

    if fhsz_gdf.empty:
        detail.update({
            "result":       False,
            "zone_level":   0,
            "hazard_zone":  "non_fhsz",
            "note":         "FHSZ data unavailable",
        })
        return False, detail

    fhsz_wgs84 = fhsz_gdf.to_crs("EPSG:4326")
    joined     = gpd.sjoin(project_pt, fhsz_wgs84, how="left", predicate="within")

    if joined.empty or joined["HAZ_CLASS"].isna().all():
        detail.update({
            "result":           False,
            "zone_level":       0,
            "hazard_zone":      "non_fhsz",
            "zone_description": "Not in FHSZ",
        })
        return False, detail

    zone_level  = int(joined["HAZ_CLASS"].dropna().max())
    in_trigger  = zone_level >= 2
    hazard_zone = _HAZ_CLASS_TO_ZONE.get(zone_level, "non_fhsz")

    detail.update({
        "result":           in_trigger,
        "zone_level":       zone_level,
        "hazard_zone":      hazard_zone,
        "zone_description": {
            0: "Not in FHSZ",
            1: "Zone 1 (Moderate)",
            2: "Zone 2 (High)",
            3: "Zone 3 (Very High)",
        }.get(zone_level, f"Zone {zone_level}"),
    })
    return in_trigger, detail

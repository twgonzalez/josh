"""
Scenario A: Wildland Evacuation Capacity (Standards 1–4)

Legal basis: AB 747 (California Government Code §65302.15) and HCM 2022.

This scenario evaluates whether a proposed project adds vehicles to evacuation routes
and whether those routes operate at or above LOS E/F (v/c ≥ 0.95) under the maximum
evacuation demand scenario.

Standard numbering (new order):
  Standard 1 — Project Size:        units >= threshold (scale gate)
  Standard 2 — Evac Routes Served:  network buffer identifies serving routes
  Standard 3 — FHSZ Modifier:       GIS point-in-polygon; when flagged, activates
                                     city-configured surge multiplier for Standard 4
  Standard 4 — Evac Capacity Test:  marginal causation v/c ratio test
                                     (baseline × surge_multiplier + project_vph vs capacity)

Three-tier output:
  DISCRETIONARY           — size threshold met AND Standard 4 capacity exceeded
  CONDITIONAL MINISTERIAL — size threshold met AND capacity OK (any city, with or without FHSZ)
  MINISTERIAL             — below size threshold

Framework applies universally — citywide FHSZ gate removed. Standard 3 is an informational
modifier that activates the surge multiplier; it does not gate the determination.
"""
import logging

import geopandas as gpd
from shapely.geometry import Point

from models.project import Project
from .base import EvacuationScenario, ScenarioResult, Tier

logger = logging.getLogger(__name__)

_LEGAL_BASIS = (
    "AB 747 (California Government Code §65302.15) — General Plan Safety Element "
    "mandatory update for evacuation route capacity analysis; "
    "HCM 2022 (Highway Capacity Manual, 7th Edition) v/c capacity threshold"
)


class WildlandScenario(EvacuationScenario):
    """
    Evaluates wildland evacuation capacity impact (Standards 1–4).

    Standard 1 (size) gates the analysis. Standard 3 (FHSZ modifier) activates
    the surge multiplier for Standard 4 when the project is within FHSZ Zone 2/3.
    Scenario parameters are read from config["determination_tiers"]["discretionary"].
    """

    @property
    def name(self) -> str:
        return "wildland_ab747"

    @property
    def legal_basis(self) -> str:
        return _LEGAL_BASIS

    @property
    def unit_threshold(self) -> int:
        return int(
            self.config.get("determination_tiers", {})
            .get("discretionary", {})
            .get("unit_threshold", self.config.get("unit_threshold", 50))
        )

    @property
    def vc_threshold(self) -> float:
        return float(
            self.config.get("determination_tiers", {})
            .get("discretionary", {})
            .get("vc_threshold", self.config.get("vc_threshold", 0.95))
        )

    @property
    def fallback_tier(self) -> Tier:
        return Tier.CONDITIONAL_MINISTERIAL

    # ------------------------------------------------------------------
    # Step 1: Applicability — does this city have FHSZ zones?
    # Also records the fire zone severity modifier for the project site.
    # ------------------------------------------------------------------

    def check_applicability(self, project: Project, context: dict) -> tuple[bool, dict]:
        """
        Standard 3 (FHSZ Modifier): Is the project site within FHSZ Zone 2 or 3?

        This scenario is always applicable — the citywide FHSZ gate has been removed.
        Evacuation capacity matters for all natural disasters, not only wildfire. The
        point-in-polygon test records the FHSZ modifier for the project site:

          Standard 3 flagged (in FHSZ):     city-configured surge multiplier activates
                                             for Standard 4 ratio test.
          Standard 3 not flagged (no FHSZ): surge_multiplier = 1.0 (no effect on Std 4).

        Method: GIS point-in-polygon test. Always returns True (applicable).
        Discretion: Zero.
        """
        fhsz_gdf = context.get("fhsz_gdf", gpd.GeoDataFrame())

        fire_zone_result, fire_zone_detail = check_fire_zone(
            (project.location_lat, project.location_lon), fhsz_gdf
        )

        # Update project fields used by downstream audit trail and map visualization
        project.in_fire_zone    = fire_zone_result
        project.fire_zone_level = fire_zone_detail.get("zone_level", 0)

        # Surge multiplier activated by Standard 3 flag; used in Standard 4 ratio test
        surge = float(self.config.get("fhsz_surge_multiplier", 1.0)) if fire_zone_result else 1.0

        return True, {
            "result":                      True,
            "method":                      "Always applicable; site FHSZ check via GIS point-in-polygon",
            "std3_fhsz_modifier":          fire_zone_result,
            "std3_zone_level":             fire_zone_detail.get("zone_description", "Not in FHSZ"),
            "std3_surge_multiplier_active": surge,
            "fire_zone_severity_modifier": fire_zone_detail,
            "note": (
                f"Standard 3 flagged: project in FHSZ Zone {project.fire_zone_level} — "
                f"surge multiplier {surge}× will be applied in Standard 4."
                if fire_zone_result else
                "Standard 3: project not in FHSZ — surge multiplier not applied (1.0×)."
            ),
        }

    # ------------------------------------------------------------------
    # Step 3: Route Identification — serving evacuation routes
    # ------------------------------------------------------------------

    def identify_routes(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> tuple[list, dict]:
        """
        Standard 2 (Evac Routes Served): Which evacuation routes serve this project?

        Method: Buffer project location by evacuation_route_radius_miles, intersect
        with road segments flagged is_evacuation_route == True.
        Discretion: Zero — algorithmic spatial query.
        """
        radius      = self.config.get("evacuation_route_radius_miles", 0.5)
        analysis_crs = self.city_config.get("analysis_crs", "EPSG:26910")

        lat, lon = project.location_lat, project.location_lon
        project_pt = gpd.GeoDataFrame(
            {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
        ).to_crs(analysis_crs)

        roads_proj   = roads_gdf.to_crs(analysis_crs)
        radius_meters = radius * 1609.344
        buffer        = project_pt.geometry.iloc[0].buffer(radius_meters)

        if "is_evacuation_route" not in roads_proj.columns:
            evac_nearby = roads_proj[roads_proj.geometry.intersects(buffer)]
        else:
            evac_only   = roads_proj[roads_proj["is_evacuation_route"] == True]
            evac_nearby = evac_only[evac_only.geometry.intersects(buffer)]

        serving_ids = evac_nearby["osmid"].tolist()

        # Update project fields
        project.serving_route_ids   = serving_ids
        project.search_radius_miles = radius

        detail = {
            "project_lat":        lat,
            "project_lon":        lon,
            "radius_miles":       radius,
            "radius_meters":      round(radius_meters, 1),
            "method":             "Buffer project location + intersect with is_evacuation_route segments",
            "serving_route_count": len(evac_nearby),
            "triggers_standard":  len(evac_nearby) > 0,
            "serving_routes": [
                {
                    "osmid":               str(row["osmid"]),
                    "name":                row.get("name", ""),
                    "vc_ratio":            round(row.get("vc_ratio", 0), 4),
                    "los":                 row.get("los", ""),
                    "capacity_vph":        round(row.get("capacity_vph", 0), 0),
                    "baseline_demand_vph": round(row.get("baseline_demand_vph", 0), 1),
                }
                for _, row in evac_nearby.iterrows()
            ],
        }
        return serving_ids, detail

    # ------------------------------------------------------------------
    # FHSZ surge multiplier — applied when project is in fire zone
    # ------------------------------------------------------------------

    def _get_surge_multiplier(self, project: Project) -> float:
        """
        Return the city-adopted FHSZ evacuation surge multiplier.

        Only applied when the project site is within FHSZ Zone 2 or 3.
        Value is read from config (merged parameters.yaml + city overrides).
        Default 1.0 if city has not adopted a multiplier.
        """
        if not project.in_fire_zone:
            return 1.0
        return float(self.config.get("fhsz_surge_multiplier", 1.0))

    # ------------------------------------------------------------------
    # Override reason builders to include fire zone context
    # ------------------------------------------------------------------

    def _reason_discretionary(self, project: Project, step5: dict) -> str:
        n_flagged = len(step5.get("flagged_route_ids", []))
        surge = float(self.config.get("fhsz_surge_multiplier", 1.0))
        fire_note = (
            f"Standard 3 flagged: project is in FHSZ Zone {project.fire_zone_level} — "
            f"surge multiplier {surge}× applied in Standard 4. "
            if project.in_fire_zone else
            "Standard 3: project is not within a designated FHSZ zone — "
            "surge multiplier not applied; capacity impact alone triggers DISCRETIONARY. "
        )
        return (
            f"Project meets the {self.unit_threshold}-unit size threshold (Standard 1) and "
            f"{n_flagged} serving evacuation route(s) exceed the v/c threshold of "
            f"{self.vc_threshold:.2f} under the Standard 4 evacuation capacity test. "
            f"{fire_note}"
            f"Discretionary review required. Legal basis: {self.legal_basis}."
        )

    def _reason_fallback(self, project: Project, step3: dict, step5: dict) -> str:
        n_routes = step3.get("serving_route_count", 0)
        cond_cfg  = self.config.get("determination_tiers", {}).get("conditional_ministerial", {})
        cond_legal = cond_cfg.get(
            "legal_basis",
            "General Plan Safety Element consistency and AB 1600 nexus",
        )
        route_note = (
            f"has {n_routes} serving evacuation route segment(s) within "
            f"{self.config.get('evacuation_route_radius_miles', 0.5)} miles (Standard 2)"
            if n_routes > 0 else
            "has no serving routes within the search radius but adds vehicles to the evacuation network"
        )
        surge = float(self.config.get("fhsz_surge_multiplier", 1.0))
        fhsz_note = (
            f"Standard 3 flagged: FHSZ Zone {project.fire_zone_level} — "
            f"surge multiplier {surge}× applied in Standard 4 evaluation. "
            if project.in_fire_zone else
            "Standard 3: not in FHSZ — surge multiplier not applied. "
        )
        return (
            f"Project meets the {self.unit_threshold}-unit size threshold (Standard 1) and "
            f"{route_note}. "
            f"{fhsz_note}"
            f"V/C threshold ({self.vc_threshold:.2f}) not exceeded (Standard 4 not triggered). "
            f"Ministerial approval eligible with mandatory evacuation conditions. "
            f"Legal basis: {cond_legal}."
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

    When True, activates the city-configured surge multiplier for Standard 4.
    Does NOT gate the DISCRETIONARY determination — capacity impact (Standard 4) does.

    Method: GIS point-in-polygon test.
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
        "role":        "Severity modifier — affects required conditions, NOT the DISCRETIONARY gate",
    }

    if fhsz_gdf.empty:
        detail.update({"result": False, "zone_level": 0, "note": "FHSZ data unavailable"})
        return False, detail

    fhsz_wgs84 = fhsz_gdf.to_crs("EPSG:4326")
    joined     = gpd.sjoin(project_pt, fhsz_wgs84, how="left", predicate="within")

    if joined.empty or joined["HAZ_CLASS"].isna().all():
        detail.update({"result": False, "zone_level": 0, "zone_description": "Not in FHSZ"})
        return False, detail

    zone_level = int(joined["HAZ_CLASS"].dropna().max())
    in_trigger = zone_level >= 2

    detail.update({
        "result":       in_trigger,
        "zone_level":   zone_level,
        "zone_description": {
            0: "Not in FHSZ",
            1: "Zone 1 (Moderate)",
            2: "Zone 2 (High)",
            3: "Zone 3 (Very High)",
        }.get(zone_level, f"Zone {zone_level}"),
    })
    return in_trigger, detail

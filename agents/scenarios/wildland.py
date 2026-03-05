"""
Scenario A: Wildland Evacuation Capacity (Standards 1–4)

Legal basis: AB 747 (California Government Code §65302.15) and HCM 2022.

This scenario evaluates whether a proposed project adds vehicles to citywide
evacuation routes that serve FHSZ Zone 2 or 3 areas, and whether those routes
operate at or above LOS E/F (v/c ≥ 0.80) under the maximum evacuation demand scenario.

Three-tier output:
  DISCRETIONARY          — size threshold met AND capacity exceeded on any serving route
  CONDITIONAL MINISTERIAL — city has FHSZ zones AND size threshold met (capacity OK)
  MINISTERIAL            — city has no FHSZ zones OR below size threshold

Fire zone severity modifier: whether the project site itself is in FHSZ Zone 2/3 is
recorded in the audit trail and affects required mitigation conditions, but does NOT
gate the DISCRETIONARY determination. Capacity impact alone triggers DISCRETIONARY.
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
    Evaluates citywide wildland evacuation capacity impact (Standards 1–4).

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
            .get("vc_threshold", self.config.get("vc_threshold", 0.80))
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
        Standard 1 (Citywide Applicability): Does the city contain FHSZ Zone 2 or 3?

        Also evaluates the Fire Zone Severity Modifier: is the project site itself in
        FHSZ Zone 2/3? This is recorded as context in the audit trail — it does NOT
        gate the DISCRETIONARY determination (capacity impact alone does that), but it
        affects the required mitigation conditions.

        Method: Non-empty GeoDataFrame check + point-in-polygon test.
        Discretion: Zero.
        """
        fhsz_gdf = context.get("fhsz_gdf", gpd.GeoDataFrame())

        citywide_result, citywide_detail = check_citywide_fhsz(fhsz_gdf)
        fire_zone_result, fire_zone_detail = check_fire_zone(
            (project.location_lat, project.location_lon), fhsz_gdf
        )

        # Update project fields used by downstream audit trail and map visualization
        project.in_fire_zone    = fire_zone_result
        project.fire_zone_level = fire_zone_detail.get("zone_level", 0)

        return citywide_result, {
            "result":                   citywide_result,
            "method":                   "Citywide: non-empty FHSZ GeoDataFrame check; Site: point-in-polygon",
            "citywide_fhsz":            citywide_detail,
            "fire_zone_severity_modifier": fire_zone_detail,
            "note": (
                "City contains FHSZ zones — three-tier wildland framework applies citywide."
                if citywide_result else
                "City has no FHSZ zones — wildland scenario not applicable; project is MINISTERIAL."
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
        Standard 3: Which evacuation routes serve this project?

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
    # Override reason builders to include fire zone context
    # ------------------------------------------------------------------

    def _reason_discretionary(self, project: Project, step5: dict) -> str:
        n_flagged = len(step5.get("flagged_route_ids", []))
        fire_note = (
            f"Project is in FHSZ Zone {project.fire_zone_level} "
            "(fire zone is a severity modifier — affects required mitigation conditions). "
            if project.in_fire_zone else
            "Project is not within a designated FHSZ zone "
            "(capacity impact alone triggers DISCRETIONARY — fire zone is not a gate). "
        )
        return (
            f"Project meets the {self.unit_threshold}-unit size threshold and "
            f"{n_flagged} serving evacuation route(s) exceed the v/c threshold of "
            f"{self.vc_threshold:.2f} under the citywide evacuation demand scenario. "
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
            f"{self.config.get('evacuation_route_radius_miles', 0.5)} miles"
            if n_routes > 0 else
            "has no serving routes within the search radius but adds vehicles to the citywide network"
        )
        return (
            f"City contains FHSZ zones. Project meets the {self.unit_threshold}-unit "
            f"size threshold and {route_note}. "
            f"V/C threshold ({self.vc_threshold:.2f}) not exceeded (Standard 4 not triggered). "
            f"Ministerial approval eligible with mandatory evacuation conditions. "
            f"Legal basis: {cond_legal}."
        )


# ---------------------------------------------------------------------------
# Helper functions (module-level — reusable and independently testable)
# ---------------------------------------------------------------------------

def check_citywide_fhsz(fhsz_gdf: gpd.GeoDataFrame) -> tuple[bool, dict]:
    """
    Standard 1 (Citywide Applicability): Does this city have any FHSZ Zone 2 or 3?

    Method: Non-empty GeoDataFrame check.
    Discretion: Zero — presence/absence of data.
    """
    has_fhsz   = not fhsz_gdf.empty
    zone_count = len(fhsz_gdf) if has_fhsz else 0

    return has_fhsz, {
        "result":              has_fhsz,
        "fhsz_polygon_count":  zone_count,
        "method":              "Non-empty check on city-intersected FHSZ GeoDataFrame",
        "data_source":         "CAL FIRE FHSZ (OSFM ArcGIS REST API)",
        "triggers_standard":   has_fhsz,
        "note": (
            "City contains FHSZ zones — three-tier framework applies citywide."
            if has_fhsz else
            "City has no FHSZ zones — framework not applicable; all projects are MINISTERIAL."
        ),
    }


def check_fire_zone(
    location: tuple[float, float],
    fhsz_gdf: gpd.GeoDataFrame,
) -> tuple[bool, dict]:
    """
    Fire Zone Severity Modifier: Is the project site in FHSZ Zone 2 or 3?

    Role: Severity modifier recorded in the audit trail. Does NOT gate the
    DISCRETIONARY determination (capacity impact alone does that).
    When True, it affects required mitigation conditions.

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

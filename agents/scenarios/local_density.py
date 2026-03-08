"""
Scenario B: Local Capacity Test (Standard 5)

Legal basis:
  - California Government Code §65302(g) — General Plan Safety Element (evacuation routes)
  - California Fire Code 503 — fire apparatus access road minimum width and capacity
  - SB 79 (2025) objective health and safety standard carve-out — cities may apply
    objective, non-discretionary health and safety standards to by-right projects
    provided the standard: (a) is quantitative, (b) is uniformly applied, and
    (c) was adopted before the project application was submitted.

Standard 5 asks: "Will adding this project's vehicles to local streets (using existing
baseline demand) push any local street above v/c 0.95 — creating gridlock under normal
conditions?" No evacuation surge modifier is applied (FHSZ status is irrelevant to this test).

The wildland scenario (Standards 1–4) evaluates citywide evacuation routes.
Standard 5 evaluates collector and arterial roads within 0.25 miles of the project —
the streets that provide immediate egress regardless of FHSZ status.

STATUS: Active (enabled: true in parameters.yaml). Applied citywide.
Reuses baseline_demand_vph already on roads_gdf (no separate demand calculation needed).
Fallback tier is MINISTERIAL (not CONDITIONAL MINISTERIAL) — intentional, as Standard 5
is a supplemental test that only contributes to DISCRETIONARY when triggered.
"""
import logging

import geopandas as gpd
from shapely.geometry import Point

from models.project import Project
from .base import EvacuationScenario, Tier

logger = logging.getLogger(__name__)

_LEGAL_BASIS = (
    "California Government Code §65302(g) — General Plan Safety Element evacuation route "
    "capacity analysis; California Fire Code 503 — fire apparatus access road capacity; "
    "SB 79 (2025) objective health and safety standard carve-out"
)


class LocalDensityScenario(EvacuationScenario):
    """
    Standard 5: Local Capacity Test.

    Evaluates whether project vehicles push any local street above v/c 0.95 under
    normal (non-evacuation) conditions. Activated when config["local_density"]["enabled"].

    When active:
      - Serving routes = collector/arterial roads within local_density.radius_miles
      - Demand = project vehicles added to normal_demand_vph (catchment × vpu × 0.10)
        NOT the evacuation baseline (catchment × vpu × 0.57) — Standard 5 tests
        ordinary traffic conditions, not evacuation scenarios
      - No FHSZ mobilization adjustment (Standard 5 is FHSZ-agnostic)
      - Ratio test uses shared marginal causation test from base class
    """

    @property
    def name(self) -> str:
        return "local_density_sb79"

    @property
    def legal_basis(self) -> str:
        return _LEGAL_BASIS

    @property
    def unit_threshold(self) -> int:
        return int(
            self.config.get("local_density", {})
            .get("unit_threshold", self.config.get("unit_threshold", 50))
        )

    @property
    def vc_threshold(self) -> float:
        return float(
            self.config.get("local_density", {})
            .get("vc_threshold", self.config.get("vc_threshold", 0.95))
        )

    @property
    def fallback_tier(self) -> Tier:
        return Tier.MINISTERIAL

    def _get_mob_factor(self, project: Project) -> float:
        """Standard 5 uses normal peak-hour conditions: aadt_peak_hour_factor (0.10)."""
        return float(self.config.get("aadt_peak_hour_factor", 0.10))

    # ------------------------------------------------------------------
    # Step 1: Applicability
    # ------------------------------------------------------------------

    def check_applicability(self, project: Project, context: dict) -> tuple[bool, dict]:
        """
        Standard 5 applicability: Is the local capacity scenario enabled?

        Applies citywide to all projects above the size threshold. No transit proximity
        gate — local gridlock can occur anywhere, not only near transit.

        Discretion: Zero — boolean config flag.
        """
        ld_cfg  = self.config.get("local_density", {})
        enabled = ld_cfg.get("enabled", False)

        if not enabled:
            return False, {
                "result": False,
                "method": "Config flag check: local_density.enabled",
                "note":   (
                    "Standard 5 (Local Capacity Test) is disabled in parameters.yaml "
                    "(local_density.enabled: false). Set to true to activate citywide. "
                    "See legal.md §Standard 5."
                ),
            }

        return True, {
            "result": True,
            "method": "Config flag enabled; applies citywide",
            "note":   "Standard 5 applies to all projects above the size threshold.",
        }

    # ------------------------------------------------------------------
    # Step 3: Route Identification — local egress roads only
    # ------------------------------------------------------------------

    def identify_routes(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> tuple[list, dict]:
        """
        Standard 5 (Local Capacity Test): Which local streets serve this project?

        Method: Buffer project by local_density.radius_miles; intersect with
        collector and arterial road segments (road_type in multilane/two_lane).
        Freeways are excluded — they are not local egress roads.

        Discretion: Zero — algorithmic spatial query with config-driven filter.
        """
        ld_cfg       = self.config.get("local_density", {})
        radius       = ld_cfg.get("radius_miles", 0.25)
        allowed_types = set(ld_cfg.get("local_egress_road_types", ["multilane", "two_lane"]))
        analysis_crs  = self.city_config.get("analysis_crs", "EPSG:26910")

        lat, lon = project.location_lat, project.location_lon
        project_pt = gpd.GeoDataFrame(
            {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
        ).to_crs(analysis_crs)

        roads_proj    = roads_gdf.to_crs(analysis_crs)
        radius_meters = radius * 1609.344
        buffer        = project_pt.geometry.iloc[0].buffer(radius_meters)

        # Filter to local egress road types (excludes freeways)
        if "road_type" in roads_proj.columns:
            local_roads = roads_proj[roads_proj["road_type"].isin(allowed_types)]
        else:
            local_roads = roads_proj

        local_nearby = local_roads[local_roads.geometry.intersects(buffer)]
        serving_ids  = local_nearby["osmid"].tolist()

        detail = {
            "project_lat":         lat,
            "project_lon":         lon,
            "radius_miles":        radius,
            "radius_meters":       round(radius_meters, 1),
            "allowed_road_types":  sorted(allowed_types),
            "method":              "Buffer + intersect with collector/arterial segments (freeways excluded)",
            "serving_route_count": len(local_nearby),
            "triggers_standard":   len(local_nearby) > 0,
            "serving_routes": [
                {
                    "osmid":               str(row["osmid"]),
                    "name":                row.get("name", ""),
                    "road_type":           row.get("road_type", ""),
                    "vc_ratio":            round(row.get("vc_ratio", 0), 4),
                    "los":                 row.get("los", ""),
                    "capacity_vph":        round(row.get("capacity_vph", 0), 0),
                    "baseline_demand_vph": round(row.get("baseline_demand_vph", 0), 1),
                }
                for _, row in local_nearby.iterrows()
            ],
        }
        return serving_ids, detail

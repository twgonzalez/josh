# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Scenario B: SB 79 Transit Proximity Flag (Standard 5 — Informational Only)

Legal basis:
  SB 79 (2025, AB 2097 successor) — objective health and safety carve-out for
  by-right projects; transit proximity is a contextual planning factor, not a
  capacity constraint.

This scenario is INFORMATIONAL ONLY — it never raises the determination tier.
It checks whether a proposed project falls within 0.5 miles of a Tier 1 or Tier 2
transit stop as defined by the Public Utilities Code § 21155.

v3.0 replaces LocalDensityScenario (v2.0 Standard 5 v/c local street test) with
this informational transit flag. The local v/c test was removed because:
  1. It tested ordinary peak-hour conditions, not evacuation scenarios.
  2. Merging ordinary traffic with evacuation capacity analysis was methodologically
     inconsistent.
  3. SB 79 transit proximity is the correct supplemental context for ministerial
     projects — it informs conditions, not tier.

Integration with determination:
  - evaluate_project() in objective_standards.py reads sb79_flag from this result
    and stores it on project.sb79_transit_flag (informational field).
  - The flag appears in the audit trail and determination brief.
  - This scenario always returns Tier.NOT_APPLICABLE so the most-restrictive-wins
    aggregation ignores it for tier purposes.

GTFS integration (Phase 3):
  Full Tier 1/2 transit stop lookup requires GTFS data download. Current implementation
  uses a placeholder (False) until GTFS integration is added. The scenario is structured
  to accept a transit_stops_gdf from context["transit_stops_gdf"] when available.
"""
import logging

import geopandas as gpd
from shapely.geometry import Point

from models.project import Project
from .base import EvacuationScenario, ScenarioResult, Tier

logger = logging.getLogger(__name__)

_LEGAL_BASIS = (
    "SB 79 (2025) — objective health and safety standard carve-out for by-right projects "
    "(transit proximity context); California Public Utilities Code §21155 (Tier 1/2 transit)"
)


class Sb79TransitScenario(EvacuationScenario):
    """
    Standard 5: SB 79 Transit Proximity Flag (informational).

    Checks whether project is within 0.5 miles of Tier 1 or Tier 2 transit.
    Returns NOT_APPLICABLE tier — never raises determination above MINISTERIAL.
    Sets project.sb79_transit_flag for audit trail and brief.
    """

    @property
    def name(self) -> str:
        return "sb79_transit"

    @property
    def legal_basis(self) -> str:
        return _LEGAL_BASIS

    @property
    def unit_threshold(self) -> int:
        # Not used — scenario never gates on size
        return 1

    @property
    def fallback_tier(self) -> Tier:
        return Tier.NOT_APPLICABLE

    def check_applicability(self, project: Project, context: dict) -> tuple[bool, dict]:
        enabled = self.config.get("sb79_transit", {}).get("enabled", True)
        if not enabled:
            return False, {
                "result": False,
                "method": "Config flag check: sb79_transit.enabled",
                "note":   "SB 79 transit flag disabled in parameters.yaml.",
            }
        return True, {
            "result": True,
            "method": "Config flag enabled; informational only",
            "note":   "SB 79 transit proximity check — no tier impact.",
        }

    def identify_routes(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> tuple[list, dict]:
        # No routes needed for transit proximity check
        return [], {
            "method":              "SB 79 transit proximity — no evacuation routes evaluated",
            "serving_route_count": 0,
        }

    # ------------------------------------------------------------------
    # Override evaluate() — bypass 5-step algorithm entirely
    # ------------------------------------------------------------------

    def evaluate(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> ScenarioResult:
        """
        Check SB 79 transit proximity and store result on project.

        Always returns NOT_APPLICABLE tier — informational only.
        """
        sb79_cfg = self.config.get("sb79_transit", {})
        enabled  = sb79_cfg.get("enabled", True)

        if not enabled:
            project.sb79_transit_flag = False
            return ScenarioResult(
                scenario_name = self.name,
                legal_basis   = self.legal_basis,
                tier          = Tier.NOT_APPLICABLE,
                triggered     = False,
                steps         = {"sb79_enabled": False},
                reason        = "SB 79 transit flag disabled in parameters.yaml.",
            )

        radius = sb79_cfg.get("radius_miles", 0.5)

        # Check for transit stops in context (GTFS integration — Phase 3)
        transit_stops = context.get("transit_stops_gdf", None)
        near_transit  = False

        if transit_stops is not None and not transit_stops.empty:
            analysis_crs = self.city_config.get("analysis_crs", "EPSG:26910")
            lat, lon = project.location_lat, project.location_lon
            project_pt = gpd.GeoDataFrame(
                {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
            ).to_crs(analysis_crs)
            stops_proj    = transit_stops.to_crs(analysis_crs)
            radius_meters = radius * 1609.344
            buf           = project_pt.geometry.iloc[0].buffer(radius_meters)
            near_transit  = stops_proj.geometry.intersects(buf).any()
        else:
            # Phase 3 placeholder: GTFS not yet integrated
            logger.debug(
                "  SB 79: no transit_stops_gdf in context — GTFS integration pending (Phase 3). "
                "Flag set to False."
            )

        project.sb79_transit_flag = near_transit

        reason = (
            f"SB 79: project is within {radius} miles of Tier 1/2 transit — "
            f"informational flag set. No tier impact."
            if near_transit else
            f"SB 79: project is not within {radius} miles of Tier 1/2 transit. "
            f"Informational only — no tier impact."
        )

        return ScenarioResult(
            scenario_name = self.name,
            legal_basis   = self.legal_basis,
            tier          = Tier.NOT_APPLICABLE,
            triggered     = False,
            steps         = {
                "sb79_enabled":       True,
                "radius_miles":       radius,
                "near_transit":       near_transit,
                "gtfs_integrated":    transit_stops is not None,
                "note":               "Informational only — no tier impact.",
            },
            reason = reason,
        )

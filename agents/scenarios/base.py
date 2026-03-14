# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Evacuation Scenario — Abstract Base and Shared Infrastructure — JOSH v3.0

Every evacuation capacity standard follows the same five-step algorithm.
v3.0 replaces the v/c marginal causation test (Step 5) with ΔT (marginal
evacuation clearance time in minutes).

Five-step algorithm:
  Step 1 — Applicability Check:  Is this scenario relevant to this location/city?
  Step 2 — Scale Gate:           Is the project large enough to trigger analysis?
  Step 3 — Route Identification: Which evacuation paths does this scenario evaluate?
  Step 4 — Demand Calculation:   How many vehicles does the project generate?
  Step 5 — ΔT Test:              Does project ΔT > threshold on any path?
                                 threshold = safe_egress_window(zone) × max_project_share

ΔT formula:
  ΔT = (project_vehicles / bottleneck_effective_capacity_vph) × 60 + egress_penalty
  where:
    project_vehicles = units × vpu × 0.90  (mobilization constant, NFPA 101 design basis)
    egress_penalty   = NFPA 101 penalty for buildings ≥ 4 stories (0 for low-rise)

Key v3.0 change from v2.0:
  v2.0: flagged = (baseline_vc < 0.95) AND (proposed_vc >= 0.95)  — REPLACED
  v3.0: flagged = delta_t > threshold(hazard_zone)
        where threshold = safe_egress_window(hazard_zone) × max_project_share  [v3.1 derived]
  The baseline condition is eliminated — projects in already-failing zones are tested equally.

Determination tiers (most restrictive wins across all scenarios):
  DISCRETIONARY          — Steps 1+2+5 all triggered
  CONDITIONAL_MINISTERIAL — Applicable + scale met, but ΔT within threshold
  MINISTERIAL            — Below scale threshold or not applicable
  NOT_APPLICABLE         — Scenario does not apply to this project/city
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import geopandas as gpd
from shapely.geometry import Point

from models.project import Project
from models.evacuation_path import EvacuationPath

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier enum
# ---------------------------------------------------------------------------

class Tier(str, Enum):
    """
    Determination tier. Uses str mixin so Tier.DISCRETIONARY == "DISCRETIONARY".

    Rank order (most to least restrictive):
      DISCRETIONARY (3) > MINISTERIAL_WITH_STANDARD_CONDITIONS (2) > MINISTERIAL (1) > NOT_APPLICABLE (0)
    """
    DISCRETIONARY          = "DISCRETIONARY"
    CONDITIONAL_MINISTERIAL = "MINISTERIAL WITH STANDARD CONDITIONS"
    MINISTERIAL            = "MINISTERIAL"
    NOT_APPLICABLE         = "NOT_APPLICABLE"


TIER_RANK: dict[Tier, int] = {
    Tier.DISCRETIONARY:           3,
    Tier.CONDITIONAL_MINISTERIAL: 2,
    Tier.MINISTERIAL:             1,
    Tier.NOT_APPLICABLE:          0,
}


# ---------------------------------------------------------------------------
# ScenarioResult
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    """
    Output from one EvacuationScenario.evaluate() call.

    Each step's audit dict is preserved verbatim for the legal record.
    """
    scenario_name:    str
    legal_basis:      str
    tier:             Tier
    triggered:        bool
    steps:            dict = field(default_factory=dict)
    reason:           str  = ""
    delta_t_results:  list = field(default_factory=list)   # per-path ΔT dicts
    max_delta_t:      float = 0.0


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class EvacuationScenario(ABC):
    """
    Abstract base for all evacuation capacity scenarios.

    Subclasses implement check_applicability() and identify_routes().
    compute_delta_t() is a shared implementation on this base class.
    """

    def __init__(self, config: dict, city_config: dict):
        self.config      = config
        self.city_config = city_config

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def legal_basis(self) -> str: ...

    @property
    @abstractmethod
    def unit_threshold(self) -> int: ...

    @property
    @abstractmethod
    def fallback_tier(self) -> Tier: ...

    @abstractmethod
    def check_applicability(self, project: Project, context: dict) -> tuple[bool, dict]:
        """Step 1: Is this scenario applicable to this project and city?"""
        ...

    @abstractmethod
    def identify_routes(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> tuple[list, dict]:
        """
        Step 3: Which evacuation paths does this scenario evaluate?

        Returns:
            (serving_paths: list[EvacuationPath], detail: dict)
        """
        ...

    # ------------------------------------------------------------------
    # Shared implementations
    # ------------------------------------------------------------------

    def check_scale(self, project: Project) -> tuple[bool, dict]:
        """Step 2: Is the project large enough to trigger analysis?"""
        result = project.dwelling_units >= self.unit_threshold
        return result, {
            "dwelling_units":    project.dwelling_units,
            "threshold":         self.unit_threshold,
            "result":            result,
            "method":            f"{project.dwelling_units} >= {self.unit_threshold}",
            "triggers_standard": result,
        }

    def calculate_demand(self, project: Project) -> tuple[float, dict]:
        """
        Step 4: How many peak-hour vehicles does the project generate?

        Formula: dwelling_units × vehicles_per_unit × mobilization_rate
        Source: Census ACS (vpu) + NFPA 101 design basis (mob rate constant 0.90).
        """
        vpu         = self.config.get("vehicles_per_unit", 2.5)
        mob         = self.config.get("mobilization_rate", 0.90)  # NFPA 101 design basis, constant
        hazard_zone = getattr(project, "hazard_zone", "non_fhsz")

        project_vph = project.dwelling_units * vpu * mob

        mob_citation = (
            "NFPA 101 (Life Safety Code) design basis — 100% occupant evacuation; "
            "adjusted 0.90 for ~10% zero-vehicle households (Census ACS B25044)."
        )

        return project_vph, {
            "vehicles_per_unit":          vpu,
            "hazard_zone":                hazard_zone,
            "mobilization_rate":          mob,
            "formula":                    f"{project.dwelling_units} × {vpu} × {mob:.2f}",
            "project_vehicles_peak_hour": round(project_vph, 1),
            "source_vehicles_per_unit":   "U.S. Census ACS B25044",
            "source_mobilization":        mob_citation,
        }

    def compute_delta_t(
        self,
        project: Project,
        serving_paths: list,
        config: dict,
    ) -> tuple[bool, list, dict]:
        """
        Step 5: ΔT computation for each serving EvacuationPath.

        ΔT = (project_vehicles / bottleneck_effective_capacity_vph) × 60 + egress_minutes

        project_vehicles = units × vpu × mobilization_rate(hazard_zone)
        egress_minutes   = 0 for buildings < threshold_stories;
                           stories × min_per_story (capped) for taller buildings.

        A path is flagged when ΔT > threshold(hazard_zone),
        where threshold = safe_egress_window(hazard_zone) × max_project_share (v3.1 derived).

        No baseline precondition: a path already at LOS F is still tested.
        The baseline state of the road is irrelevant — ΔT measures only the
        project's contribution relative to the road's physical capacity.

        Returns:
            (triggered: bool, delta_t_results: list[dict], detail: dict)
        """
        hazard_zone      = getattr(project, "hazard_zone", "non_fhsz")
        mob              = config.get("mobilization_rate", 0.90)  # NFPA 101 design basis, constant
        vpu              = config.get("vehicles_per_unit", 2.5)
        project_vehicles = project.dwelling_units * vpu * mob

        # Building egress penalty (NFPA 101 / IBC)
        ep_cfg = config.get("egress_penalty", {})
        stories = getattr(project, "stories", 0)
        egress_minutes = 0.0
        if stories >= ep_cfg.get("threshold_stories", 4):
            egress_minutes = min(
                stories * ep_cfg.get("minutes_per_story", 1.5),
                ep_cfg.get("max_minutes", 12),
            )

        safe_window = config.get("safe_egress_window", {}).get(hazard_zone, 120.0)
        max_project_share = config.get("max_project_share", 0.05)
        max_minutes = safe_window * max_project_share

        results = []
        triggered = False

        for path in serving_paths:
            # EvacuationPath or a plain dict
            if isinstance(path, EvacuationPath):
                eff_cap  = path.bottleneck_effective_capacity_vph
                bn_osmid = path.bottleneck_osmid
                bn_name  = path.bottleneck_name
                bn_fhsz  = path.bottleneck_fhsz_zone
                bn_hcm   = path.bottleneck_hcm_capacity_vph
                bn_deg   = path.bottleneck_hazard_degradation
                path_id  = path.path_id
            else:
                eff_cap  = float(path.get("bottleneck_effective_capacity_vph", 0))
                bn_osmid = str(path.get("bottleneck_osmid", ""))
                bn_name  = str(path.get("bottleneck_name", ""))
                bn_fhsz  = str(path.get("bottleneck_fhsz_zone", "non_fhsz"))
                bn_hcm   = float(path.get("bottleneck_hcm_capacity_vph", eff_cap))
                bn_deg   = float(path.get("bottleneck_hazard_degradation", 1.0))
                path_id  = str(path.get("path_id", ""))

            if eff_cap <= 0:
                continue

            delta_t  = (project_vehicles / eff_cap) * 60 + egress_minutes
            flagged  = delta_t > max_minutes

            if flagged:
                triggered = True

            results.append({
                "path_id":                       path_id,
                "origin_block_group":            getattr(path, "origin_block_group", ""),
                "path_segment_count":            len(getattr(path, "path_osmids", [])),
                "bottleneck_osmid":              bn_osmid,
                "bottleneck_name":               bn_name,
                "bottleneck_fhsz_zone":          bn_fhsz,
                "bottleneck_road_type":          getattr(path, "bottleneck_road_type", ""),
                "bottleneck_lane_count":         getattr(path, "bottleneck_lane_count", 0),
                "bottleneck_speed_limit":        getattr(path, "bottleneck_speed_limit", 0),
                "bottleneck_haz_class":          getattr(path, "bottleneck_haz_class", 0),
                "bottleneck_hcm_capacity_vph":   round(bn_hcm, 0),
                "bottleneck_hazard_degradation": bn_deg,
                "bottleneck_effective_capacity_vph": round(eff_cap, 0),
                "project_vehicles":              round(project_vehicles, 1),
                "egress_minutes":                round(egress_minutes, 1),
                "delta_t_minutes":               round(delta_t, 2),
                "safe_egress_window_minutes":    safe_window,
                "max_project_share":             max_project_share,
                "threshold_minutes":             round(max_minutes, 4),
                "hazard_zone":                   hazard_zone,
                "mobilization_rate":             mob,
                "flagged":                       flagged,
            })

        max_dt = max((r["delta_t_minutes"] for r in results), default=0.0)

        detail = {
            "hazard_zone":                hazard_zone,
            "mobilization_rate":          mob,
            "project_vehicles":           round(project_vehicles, 1),
            "egress_minutes":             round(egress_minutes, 1),
            "safe_egress_window_minutes": safe_window,
            "max_project_share":          max_project_share,
            "threshold_minutes":          round(max_minutes, 4),
            "paths_evaluated":            len(results),
            "triggered":                  triggered,
            "max_delta_t_minutes":        round(max_dt, 2),
            "method":                     "ΔT = (project_vehicles / bottleneck_effective_capacity) × 60 + egress",
            "source_mobilization":        "NFPA 101 design basis (constant 0.90; Census ACS B25044 zero-vehicle adjustment)",
            "source_egress":              "NFPA 101 / IBC",
            "source_threshold":           "NIST TN 2135 (safe_egress_window) × max_project_share (policy)",
            "path_results":               results,
        }
        return triggered, results, detail

    # ------------------------------------------------------------------
    # Evaluate — runs all 5 steps
    # ------------------------------------------------------------------

    def evaluate(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> ScenarioResult:
        """Run the universal 5-step algorithm. Returns ScenarioResult."""
        steps: dict = {}

        # Step 1: Applicability
        applicable, step1 = self.check_applicability(project, context)
        steps["step1_applicability"] = step1

        if not applicable:
            return ScenarioResult(
                scenario_name = self.name,
                legal_basis   = self.legal_basis,
                tier          = Tier.NOT_APPLICABLE,
                triggered     = False,
                steps         = steps,
                reason        = step1.get("note", "Scenario not applicable."),
            )

        # Step 2: Scale Gate
        scale_met, step2 = self.check_scale(project)
        steps["step2_scale"] = step2

        if not scale_met:
            return ScenarioResult(
                scenario_name = self.name,
                legal_basis   = self.legal_basis,
                tier          = Tier.MINISTERIAL,
                triggered     = False,
                steps         = steps,
                reason        = (
                    f"Project has {project.dwelling_units} dwelling units, "
                    f"below the {self.unit_threshold}-unit threshold. "
                    f"Ministerial approval eligible."
                ),
            )

        # Step 3: Route Identification
        serving_paths, step3 = self.identify_routes(project, roads_gdf, context)
        steps["step3_routes"] = step3

        # Step 4: Demand Calculation
        project_vph, step4 = self.calculate_demand(project)
        steps["step4_demand"] = step4

        # Step 5: ΔT Test
        triggered, delta_t_results, step5 = self.compute_delta_t(
            project, serving_paths, self.config
        )
        steps["step5_delta_t"] = step5

        if triggered:
            tier   = Tier.DISCRETIONARY
            reason = self._reason_discretionary(project, step5)
        else:
            tier   = self.fallback_tier
            reason = self._reason_fallback(project, step3, step5)

        max_dt = step5.get("max_delta_t_minutes", 0.0)
        return ScenarioResult(
            scenario_name   = self.name,
            legal_basis     = self.legal_basis,
            tier            = tier,
            triggered       = triggered,
            steps           = steps,
            reason          = reason,
            delta_t_results = delta_t_results,
            max_delta_t     = max_dt,
        )

    # ------------------------------------------------------------------
    # Reason builders — can be overridden by subclasses
    # ------------------------------------------------------------------

    def _reason_discretionary(self, project: Project, step5: dict) -> str:
        max_dt     = step5.get("max_delta_t_minutes", 0.0)
        threshold  = step5.get("threshold_minutes", 0.0)
        hz         = step5.get("hazard_zone", "non_fhsz")
        n_paths    = sum(1 for r in step5.get("path_results", []) if r.get("flagged"))
        return (
            f"Project meets the {self.unit_threshold}-unit size threshold and "
            f"{n_paths} serving route(s) exceed the ΔT threshold of {threshold:.2f} min "
            f"(hazard zone: {hz}, max ΔT: {max_dt:.1f} min). "
            f"Discretionary review required. Legal basis: {self.legal_basis}."
        )

    def _reason_fallback(self, project: Project, step3: dict, step5: dict) -> str:
        n_paths   = step3.get("serving_route_count", 0)
        max_dt    = step5.get("max_delta_t_minutes", 0.0)
        threshold = step5.get("threshold_minutes", 0.0)
        return (
            f"Project meets the {self.unit_threshold}-unit size threshold and "
            f"has {n_paths} serving route(s). "
            f"Max ΔT {max_dt:.1f} min within threshold ({threshold:.2f} min). "
            f"Tier: {self.fallback_tier.value}. Legal basis: {self.legal_basis}."
        )

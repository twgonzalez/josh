"""
Evacuation Scenario — Abstract Base and Shared Infrastructure

Every evacuation capacity standard in this system follows the same five-step algorithm.
The logic is identical across all scenarios; only the parameters differ. Parameters are
adopted by the city before any project is submitted (legislative act). The algorithm is
HCM 2022 mathematics (technical standard). These are structurally separate concerns.

Five-step algorithm (universal):
  Step 1 — Applicability Check:  Is this scenario relevant to this location/city?
  Step 2 — Scale Gate:           Is the project large enough to trigger analysis?
  Step 3 — Route Identification: Which road segments does this scenario evaluate?
  Step 4 — Demand Calculation:   How many vehicles does the project generate?
  Step 5 — Capacity Ratio Test:  Does demand / capacity exceed the threshold?

Determination tiers (most restrictive wins across all scenarios):
  DISCRETIONARY          — Steps 1+2+5 all triggered
  CONDITIONAL_MINISTERIAL — Applicable + scale met, but capacity threshold not exceeded
  MINISTERIAL            — Below scale threshold or not applicable
  NOT_APPLICABLE         — Scenario does not apply to this project/city
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from models.project import Project

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier enum
# ---------------------------------------------------------------------------

class Tier(str, Enum):
    """
    Determination tier. Uses str mixin so Tier.DISCRETIONARY == "DISCRETIONARY" (backward compat).

    Rank order (most to least restrictive):
      DISCRETIONARY (3) > CONDITIONAL_MINISTERIAL (2) > MINISTERIAL (1) > NOT_APPLICABLE (0)

    When multiple scenarios are evaluated, the most restrictive tier prevails.
    """
    DISCRETIONARY          = "DISCRETIONARY"
    CONDITIONAL_MINISTERIAL = "CONDITIONAL MINISTERIAL"
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

    Each step's audit dict is preserved verbatim for the legal record. The steps
    dict is keyed by step name and contains every input, intermediate, and output
    used in that step — sufficient to reproduce the result independently.
    """
    scenario_name:  str
    legal_basis:    str
    tier:           Tier
    triggered:      bool
    steps:          dict = field(default_factory=dict)
    reason:         str  = ""
    flagged_route_ids: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class EvacuationScenario(ABC):
    """
    Abstract base for all evacuation capacity scenarios.

    Subclasses implement check_applicability() and identify_routes().
    All other steps (scale check, demand calculation, ratio test, evaluate flow)
    are shared implementations on this base class.

    The evaluate() method runs all five steps in order and returns a ScenarioResult
    with a complete step-by-step audit dict.
    """

    def __init__(self, config: dict, city_config: dict):
        self.config      = config
        self.city_config = city_config

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique scenario identifier (e.g. 'wildland_ab747')."""
        ...

    @property
    @abstractmethod
    def legal_basis(self) -> str:
        """Full legal citation for this scenario."""
        ...

    @property
    @abstractmethod
    def unit_threshold(self) -> int:
        """Minimum dwelling units that trigger this scenario."""
        ...

    @property
    @abstractmethod
    def vc_threshold(self) -> float:
        """Volume-to-capacity ratio threshold (e.g. 0.95)."""
        ...

    @property
    @abstractmethod
    def fallback_tier(self) -> Tier:
        """
        Tier returned when scenario is applicable + scale met, but capacity NOT exceeded.
        WildlandScenario → CONDITIONAL_MINISTERIAL.
        LocalDensityScenario → MINISTERIAL.
        """
        ...

    @abstractmethod
    def check_applicability(self, project: Project, context: dict) -> tuple[bool, dict]:
        """
        Step 1: Is this scenario applicable to this project and city?

        Returns:
            (applicable: bool, detail: dict)

        If False, the scenario returns NOT_APPLICABLE and subsequent steps are skipped.
        """
        ...

    @abstractmethod
    def identify_routes(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> tuple[list, dict]:
        """
        Step 3: Which road segments does this scenario evaluate?

        Returns:
            (route_ids: list, detail: dict)

        route_ids are osmid values. detail documents the method, radius, and results.
        """
        ...

    # ------------------------------------------------------------------
    # Shared implementations — identical for all scenarios
    # ------------------------------------------------------------------

    def check_scale(self, project: Project) -> tuple[bool, dict]:
        """
        Step 2: Is the project large enough to trigger analysis?

        Method: Integer comparison — project.dwelling_units >= self.unit_threshold.
        Discretion: Zero.
        """
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

        Formula: dwelling_units × vehicles_per_unit × peak_hour_mobilization
        Source:  U.S. Census ACS (vehicles_per_unit) + city-adopted mobilization factor.
        Discretion: Zero — formula is fixed; inputs are Census-derived or city-adopted.

        Mobilization source is read from city_config.mobilization_source and
        city_config.mobilization_citation — set these in config/cities/{city}.yaml.
        See docs/city_onboarding.md for guidance on establishing a defensible factor.
        """
        vpu = self.config.get("vehicles_per_unit", 2.5)
        # City config overrides parameters.yaml default — allows per-city calibration
        mob = self.city_config.get(
            "peak_hour_mobilization",
            self.config.get("peak_hour_mobilization", 0.57),
        )
        project_vph = project.dwelling_units * vpu * mob

        mob_source_type = self.city_config.get("mobilization_source", "conservative_default")
        mob_citation    = self.city_config.get(
            "mobilization_citation",
            "No city-specific study on file — conservative California WUI default applied. "
            "See docs/city_onboarding.md.",
        )
        mob_note = self.city_config.get("mobilization_note", "")

        return project_vph, {
            "vehicles_per_unit":          vpu,
            "peak_hour_mobilization":     mob,
            "mobilization_source_type":   mob_source_type,
            "formula":                    f"{project.dwelling_units} units × {vpu} veh/unit × {mob} peak factor",
            "project_vehicles_peak_hour": round(project_vph, 1),
            "source_vehicles_per_unit":   "U.S. Census ACS",
            "source_mobilization":        mob_citation,
            "mobilization_note":          mob_note,
        }

    def _get_mob_factor(self, project: Project) -> float:
        """
        Return the mobilization factor for Standard 4/5 ratio test.

        Default: peak_hour_mobilization from config (0.57 — staggered peak-hour departure).
        WildlandScenario overrides this: returns fhsz_mobilization_factor (1.0) when the
        project is in FHSZ Zone 2/3 (mandatory simultaneous evacuation).
        LocalDensityScenario overrides this: returns aadt_peak_hour_factor (0.10).
        """
        return float(self.config.get("peak_hour_mobilization", 0.57))

    def ratio_test(
        self,
        route_ids: list,
        project_vph: float,
        roads_gdf: gpd.GeoDataFrame,
        mob_factor: float = 0.57,
    ) -> tuple[bool, list, dict]:
        """
        Step 5: Does the project's demand cause any serving route to exceed the v/c threshold?

        Marginal causation test — a route is flagged only when the project itself causes the
        threshold crossing:
            effective_baseline_vc < threshold  AND  proposed_vc >= threshold

        effective_baseline = catchment_demand_vph × mob_factor
          - Non-FHSZ wildland (mob=0.57): staggered peak-hour departure
          - FHSZ wildland (mob=1.00):     mandatory simultaneous evacuation
          - Local density (mob=0.10):     normal peak-hour conditions (Standard 5)

        Routes already failing at the effective baseline are recorded in the audit for
        transparency but do NOT trigger DISCRETIONARY. This is consistent with standard CEQA
        significance methodology and prevents the standard from functioning as a categorical
        prohibition on infill near pre-existing congestion.

        Returns:
            (triggered: bool, flagged_ids: list, detail: dict)

        Discretion: Zero — arithmetic comparison against city-adopted threshold.
        """
        vc_threshold = self.vc_threshold
        # Worst-case marginal impact: each serving route is independently evaluated
        # against the project's full peak-hour vehicle load. This tests whether any
        # single route would be pushed over the threshold if it absorbed all project
        # vehicles — consistent with the marginal causation standard.
        vehicles_per_route = project_vph

        serving = roads_gdf[
            roads_gdf["osmid"].apply(
                lambda o: o in route_ids or
                (isinstance(o, list) and any(x in route_ids for x in o))
            )
        ].copy()

        route_results   = []
        already_failing = []   # effective baseline >= threshold — recorded but NOT a trigger
        project_caused  = []   # effective baseline < threshold AND proposed >= threshold — flagged

        for _, row in serving.iterrows():
            capacity         = float(row.get("capacity_vph", 0.0))
            # Raw per-unit demand (no mob baked in); mob_factor applied here at test time
            catchment_demand = float(row.get("catchment_demand_vph", 0.0))
            # Keep for audit trail / brief display
            evac_demand      = float(row.get("baseline_demand_vph", 0.0))
            normal_demand    = float(row.get("normal_demand_vph", evac_demand))

            # Apply mob_factor: converts raw catchment demand to scenario-specific demand
            # Non-FHSZ ×0.57, FHSZ ×1.00, Standard 5 ×0.10
            effective_baseline = catchment_demand * mob_factor
            effective_vc       = effective_baseline / capacity if capacity > 0 else 0.0

            proposed_demand = effective_baseline + vehicles_per_route
            proposed_vc     = proposed_demand / capacity if capacity > 0 else 0.0

            baseline_exceeds          = effective_vc >= vc_threshold
            proposed_exceeds          = proposed_vc >= vc_threshold
            project_causes_exceedance = (not baseline_exceeds) and proposed_exceeds

            osmid_str = str(row.get("osmid", ""))
            if baseline_exceeds:
                already_failing.append(osmid_str)
            if project_causes_exceedance:
                project_caused.append(osmid_str)

            route_results.append({
                "osmid":                     osmid_str,
                "name":                      row.get("name", ""),
                "capacity_vph":              round(capacity, 0),
                "catchment_demand_vph":      round(catchment_demand, 1),
                "mob_factor":                mob_factor,
                # Kept for audit trail reference
                "evac_demand_vph":           round(evac_demand, 1),
                "normal_demand_vph":         round(normal_demand, 1),
                "effective_baseline_demand": round(effective_baseline, 1),
                "effective_baseline_vc":     round(effective_vc, 4),
                "baseline_exceeds":          baseline_exceeds,
                "vehicles_added":            round(vehicles_per_route, 1),
                "proposed_demand_vph":       round(proposed_demand, 1),
                "proposed_vc":               round(proposed_vc, 4),
                "proposed_exceeds":          proposed_exceeds,
                "project_causes_exceedance": project_causes_exceedance,
            })

        any_flagged = bool(project_caused)
        flagged_ids = list(set(project_caused))

        detail = {
            "vc_threshold":                vc_threshold,
            "mob_factor":                  mob_factor,
            "project_vehicles_peak_hour":  round(project_vph, 1),
            "vehicles_per_route":          round(vehicles_per_route, 1),
            "serving_routes_evaluated":    len(serving),
            "already_failing_at_baseline": already_failing,
            "project_caused_exceedance":   project_caused,
            "flagged_route_ids":           flagged_ids,
            "result":                      any_flagged,
            "triggers_standard":           any_flagged,
            "method":                      "Marginal causation: effective_baseline_vc < threshold AND proposed_vc >= threshold",
            "route_details":               route_results,
        }
        return any_flagged, flagged_ids, detail

    # ------------------------------------------------------------------
    # Evaluate — runs all 5 steps
    # ------------------------------------------------------------------

    def evaluate(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> ScenarioResult:
        """
        Run the universal 5-step evacuation capacity algorithm for this scenario.

        Short-circuits at Steps 1 and 2 if not applicable or below scale — avoids
        unnecessary spatial computation and produces a clean audit record.

        Returns a ScenarioResult with tier, triggered flag, and full step audit.
        """
        steps: dict = {}

        # ── Step 1: Applicability ──────────────────────────────────────
        applicable, step1 = self.check_applicability(project, context)
        steps["step1_applicability"] = step1

        if not applicable:
            return ScenarioResult(
                scenario_name  = self.name,
                legal_basis    = self.legal_basis,
                tier           = Tier.NOT_APPLICABLE,
                triggered      = False,
                steps          = steps,
                reason         = step1.get("note", "Scenario not applicable to this project/city."),
            )

        # ── Step 2: Scale Gate ─────────────────────────────────────────
        scale_met, step2 = self.check_scale(project)
        steps["step2_scale"] = step2

        if not scale_met:
            return ScenarioResult(
                scenario_name  = self.name,
                legal_basis    = self.legal_basis,
                tier           = Tier.MINISTERIAL,
                triggered      = False,
                steps          = steps,
                reason         = (
                    f"Project has {project.dwelling_units} dwelling units, "
                    f"below the {self.unit_threshold}-unit threshold for this scenario. "
                    f"Ministerial approval eligible."
                ),
            )

        # ── Step 3: Route Identification ───────────────────────────────
        route_ids, step3 = self.identify_routes(project, roads_gdf, context)
        steps["step3_routes"] = step3

        # ── Step 4: Demand Calculation ─────────────────────────────────
        project_vph, step4 = self.calculate_demand(project)
        steps["step4_demand"] = step4

        # ── Step 5: Capacity Ratio Test ────────────────────────────────
        mob_factor = self._get_mob_factor(project)
        triggered, flagged_ids, step5 = self.ratio_test(
            route_ids, project_vph, roads_gdf, mob_factor=mob_factor,
        )
        steps["step5_ratio_test"] = step5

        # ── Determination ──────────────────────────────────────────────
        if triggered:
            tier = Tier.DISCRETIONARY
            reason = self._reason_discretionary(project, step5)
        else:
            tier = self.fallback_tier
            reason = self._reason_fallback(project, step3, step5)

        return ScenarioResult(
            scenario_name     = self.name,
            legal_basis       = self.legal_basis,
            tier              = tier,
            triggered         = triggered,
            steps             = steps,
            reason            = reason,
            flagged_route_ids = flagged_ids,
        )

    # ------------------------------------------------------------------
    # Reason builders — can be overridden by subclasses
    # ------------------------------------------------------------------

    def _reason_discretionary(self, project: Project, step5: dict) -> str:
        n_flagged = len(step5.get("flagged_route_ids", []))
        return (
            f"Project meets the {self.unit_threshold}-unit size threshold and "
            f"{n_flagged} serving route(s) exceed the v/c threshold of {self.vc_threshold:.2f} "
            f"under the {self.name} demand scenario. "
            f"Discretionary review required. Legal basis: {self.legal_basis}."
        )

    def _reason_fallback(self, project: Project, step3: dict, step5: dict) -> str:
        n_routes = step3.get("serving_route_count", 0)
        return (
            f"Project meets the {self.unit_threshold}-unit size threshold and "
            f"has {n_routes} serving route(s). "
            f"V/C threshold ({self.vc_threshold:.2f}) not exceeded under the {self.name} scenario. "
            f"Tier: {self.fallback_tier.value}. Legal basis: {self.legal_basis}."
        )

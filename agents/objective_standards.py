"""
Agent 3: Objective Standards Engine — Orchestrator

Runs all applicable evacuation capacity scenarios against a proposed project
and returns the most restrictive tier determination.

Architecture:
  Each scenario implements the universal 5-step algorithm:
    1. Applicability check
    2. Scale gate
    3. Route identification
    4. Demand calculation
    5. Capacity ratio test (demand / capacity > threshold)

  The orchestrator runs all scenarios, then applies "most restrictive wins":
    DISCRETIONARY (3) > CONDITIONAL MINISTERIAL (2) > MINISTERIAL (1)

  Adding a new scenario requires only a new class in agents/scenarios/.
  No changes to this orchestrator are needed.

Active scenarios:
  A. WildlandScenario     — Standards 1–4 (AB 747, Gov. Code §65302.15)
  B. LocalDensityScenario — Standard 5 (General Plan §65302(g), Fire Code 503, SB 79)
                            [ENABLED — citywide, no transit gate; see parameters.yaml local_density block]
                            [Phase 3: GTFS transit proximity gating available via require_transit_proximity]

Public API (unchanged from prior architecture):
  evaluate_project(project, roads_gdf, fhsz_gdf, config, city_config) → (Project, audit)
  generate_audit_trail(project, audit, output_path) → str
"""
import logging
from datetime import datetime
from pathlib import Path

import geopandas as gpd

from models.project import Project
from agents.scenarios.base import ScenarioResult, Tier, TIER_RANK
from agents.scenarios.wildland import WildlandScenario
from agents.scenarios.local_density import LocalDensityScenario

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
    Run all objective standards scenarios and produce a final determination.

    Each scenario independently evaluates the project using the universal
    5-step algorithm. The most restrictive tier across all applicable scenarios
    is the final determination.

    Returns:
        (updated Project, audit_trail dict)
    """
    context = {"fhsz_gdf": fhsz_gdf}

    scenarios = [
        WildlandScenario(config, city_config),
        LocalDensityScenario(config, city_config),
    ]

    results: list[ScenarioResult] = [
        s.evaluate(project, roads_gdf, context)
        for s in scenarios
    ]

    final_tier = _most_restrictive(results)

    # Update project fields (wildland result populates serving/flagged routes)
    wildland_result = next(r for r in results if r.scenario_name == "wildland_ab747")
    _update_project_from_wildland(project, wildland_result, config)

    project.determination        = final_tier.value
    project.determination_reason = _build_combined_reason(results, final_tier)

    audit = {
        "evaluation_date": datetime.now().isoformat(),
        "project": project.to_dict(),
        "algorithm": {
            "name":        "Universal 5-Step Evacuation Capacity Algorithm",
            "version":     "2.0 (multi-scenario)",
            "description": (
                "Each scenario applies: (1) applicability check, (2) scale gate, "
                "(3) route identification, (4) demand calculation, "
                "(5) capacity ratio test (demand/capacity > threshold). "
                "Most restrictive tier across all applicable scenarios is the final determination."
            ),
            "legal_doc":   "See legal.md for full legal basis and defense reference.",
        },
        "scenarios": {
            r.scenario_name: {
                "legal_basis": r.legal_basis,
                "tier":        r.tier.value,
                "triggered":   r.triggered,
                "reason":      r.reason,
                "steps":       r.steps,
                "flagged_route_ids": r.flagged_route_ids,
            }
            for r in results
        },
        "determination": {
            "result":          final_tier.value,
            "tier":            final_tier.value,
            "scenario_tiers":  {r.scenario_name: r.tier.value for r in results},
            "logic":           "Most restrictive tier across all applicable scenarios wins.",
            "tier_rank":       "DISCRETIONARY(3) > CONDITIONAL MINISTERIAL(2) > MINISTERIAL(1) > NOT_APPLICABLE(0)",
            "reason":          project.determination_reason,
        },
    }

    return project, audit


# ---------------------------------------------------------------------------
# Tier aggregation
# ---------------------------------------------------------------------------

def _most_restrictive(results: list[ScenarioResult]) -> Tier:
    """Return the most restrictive tier across all applicable scenario results."""
    applicable = [r for r in results if r.tier != Tier.NOT_APPLICABLE]
    if not applicable:
        return Tier.MINISTERIAL
    return max(applicable, key=lambda r: TIER_RANK[r.tier]).tier


def _update_project_from_wildland(
    project: Project,
    result: ScenarioResult,
    config: dict,
) -> None:
    """Populate Project fields from the wildland scenario's step results."""
    steps = result.steps

    # Scale check
    s2 = steps.get("step2_scale", {})
    project.meets_size_threshold = s2.get("result", False)
    project.unit_threshold_used  = s2.get("threshold", config.get("unit_threshold", 15))

    # Route identification
    s3 = steps.get("step3_routes", {})
    if s3:
        route_list = s3.get("serving_routes", [])
        project.serving_route_ids = [r["osmid"] for r in route_list]

    # Ratio test
    s5 = steps.get("step5_ratio_test", {})
    if s5:
        project.exceeds_capacity_threshold = s5.get("result", False)
        project.project_vehicles_peak_hour = steps.get("step4_demand", {}).get(
            "project_vehicles_peak_hour", 0.0
        )
        project.flagged_route_ids = s5.get("flagged_route_ids", [])


def _build_combined_reason(results: list[ScenarioResult], final_tier: Tier) -> str:
    """Build a combined determination reason across all scenarios."""
    triggered = [r for r in results if r.triggered]
    applicable = [r for r in results if r.tier != Tier.NOT_APPLICABLE]

    if triggered:
        # Lead with the triggering scenario(s)
        parts = [r.reason for r in triggered]
        if len(parts) == 1:
            return parts[0]
        return " | ".join(f"[{r.scenario_name}] {r.reason}" for r in triggered)

    if applicable:
        # Most restrictive applicable non-triggered scenario
        best = max(applicable, key=lambda r: TIER_RANK[r.tier])
        return best.reason

    return f"No applicable scenarios triggered. Tier: {final_tier.value}."


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

    Iterates over all scenario results and renders each step.
    Format is designed for inclusion in planning record.

    Returns the text content (also written to output_path).
    """
    det = project.determination
    det_label = {
        "DISCRETIONARY":           "DISCRETIONARY REVIEW REQUIRED",
        "CONDITIONAL MINISTERIAL": "CONDITIONAL MINISTERIAL APPROVAL",
        "MINISTERIAL":             "MINISTERIAL APPROVAL ELIGIBLE",
    }.get(det, det)

    lines = [
        "=" * 70,
        "FIRE EVACUATION CAPACITY ANALYSIS — PROJECT DETERMINATION",
        "=" * 70,
        f"Date:          {audit['evaluation_date']}",
        f"Project:       {project.project_name or 'Unnamed'}",
        f"Address:       {project.address or 'Not provided'}",
        f"APN:           {project.apn or 'Not provided'}",
        f"Location:      {project.location_lat}, {project.location_lon}",
        f"Dwelling Units: {project.dwelling_units}",
        "",
        "ALGORITHM",
        "-" * 40,
    ]
    alg = audit.get("algorithm", {})
    lines.append(f"  {alg.get('name', '')} v{alg.get('version', '')}")
    lines.append(f"  {alg.get('description', '')}")
    lines.append(f"  Reference: {alg.get('legal_doc', '')}")

    # ── Render each scenario ──────────────────────────────────────────
    for scenario_name, scenario_data in audit.get("scenarios", {}).items():
        tier      = scenario_data["tier"]
        triggered = scenario_data["triggered"]
        steps     = scenario_data.get("steps", {})

        lines += [
            "",
            "=" * 70,
            f"SCENARIO: {scenario_name.upper()}",
            f"  Legal Basis: {scenario_data['legal_basis']}",
            f"  Result: {tier}  |  Triggered: {'YES' if triggered else 'NO'}",
            "=" * 70,
        ]

        if tier == "NOT_APPLICABLE":
            s1 = steps.get("step1_applicability", {})
            lines.append(f"  NOT APPLICABLE: {s1.get('note', scenario_data.get('reason', ''))}")
            continue

        # Step 1: Applicability
        s1 = steps.get("step1_applicability", {})
        lines += [
            "",
            "  STEP 1 — APPLICABILITY CHECK",
            "  " + "-" * 38,
            f"  Method: {s1.get('method', '')}",
            f"  Result: {'APPLICABLE' if s1.get('result') else 'NOT APPLICABLE'}",
        ]
        if "note" in s1:
            lines.append(f"  Note: {s1['note']}")

        # Standard 3: FHSZ modifier (surge multiplier applied in Std 4 when flagged)
        if "fire_zone_severity_modifier" in s1:
            fz = s1["fire_zone_severity_modifier"]
            surge = s1.get("std3_surge_multiplier_active", 1.0)
            lines.append(
                f"  Standard 3 (FHSZ Modifier): {fz.get('zone_description', 'Not in FHSZ')} "
                f"({'IN FIRE ZONE — surge multiplier ' + str(surge) + '× applied in Std 4' if fz.get('result') else 'not in FHSZ — surge multiplier not applied'})"
            )

        # Step 2: Scale Gate
        s2 = steps.get("step2_scale", {})
        if s2:
            lines += [
                "",
                "  STEP 2 — SCALE GATE",
                "  " + "-" * 38,
                f"  {s2.get('method', '')} → {'TRIGGERED' if s2.get('result') else 'not triggered'}",
                f"  ({s2.get('dwelling_units')} units vs. {s2.get('threshold')} threshold)",
            ]

        if tier == "MINISTERIAL" and not s2.get("result"):
            lines.append(f"  → Determination: MINISTERIAL (below scale threshold)")
            lines.append(f"  Reason: {scenario_data['reason']}")
            continue

        # Step 3: Route Identification
        s3 = steps.get("step3_routes", {})
        if s3:
            lines += [
                "",
                "  STEP 3 — ROUTE IDENTIFICATION",
                "  " + "-" * 38,
                f"  Method: {s3.get('method', '')}",
                f"  Radius: {s3.get('radius_miles')} miles ({s3.get('radius_meters')} m)",
                f"  Routes found: {s3.get('serving_route_count', 0)}",
            ]
            for r in s3.get("serving_routes", []):
                lines.append(
                    f"    - {r.get('name') or r['osmid']}: "
                    f"v/c={r.get('vc_ratio', 0):.4f}, LOS={r.get('los', '')}, "
                    f"cap={r.get('capacity_vph', 0):.0f} vph, "
                    f"demand={r.get('baseline_demand_vph', 0):.1f} vph"
                )

        # Step 4: Demand Calculation
        s4 = steps.get("step4_demand", {})
        if s4:
            lines += [
                "",
                "  STEP 4 — DEMAND CALCULATION",
                "  " + "-" * 38,
                f"  Formula: {s4.get('formula', '')}",
                f"  Project vehicles (peak hour): {s4.get('project_vehicles_peak_hour', 0):.1f} vph",
                f"  Source (vehicles/unit): {s4.get('source_vehicles_per_unit', '')}",
                f"  Source (mobilization):  {s4.get('source_mobilization', '')}",
            ]

        # Step 5: Capacity Ratio Test
        s5 = steps.get("step5_ratio_test", {})
        if s5:
            lines += [
                "",
                "  STEP 5 — CAPACITY RATIO TEST",
                "  " + "-" * 38,
                f"  V/C Threshold: {s5.get('vc_threshold', 0.95)}",
                f"  Method: {s5.get('method', '')}",
                f"  Project vehicles per route: {s5.get('vehicles_per_route', 0):.1f} vph",
                f"  Routes evaluated: {s5.get('serving_routes_evaluated', 0)}",
                f"  Already failing at baseline (not caused by project): {s5.get('already_failing_at_baseline', [])}",
                f"  Project-caused exceedance (triggers DISCRETIONARY): {s5.get('project_caused_exceedance', [])}",
                "",
                "  Route-by-Route Results:",
            ]
            for r in s5.get("route_details", []):
                # Only mark routes the PROJECT causes to cross the threshold (marginal causation).
                # Routes already failing at baseline are noted separately — they do not trigger DISCRETIONARY.
                if r.get("project_causes_exceedance"):
                    flag = " *** PROJECT CAUSES EXCEEDANCE ***"
                elif r.get("baseline_exceeds"):
                    flag = " [pre-existing LOS F — not caused by project]"
                else:
                    flag = ""
                lines.append(f"    {r.get('name') or r['osmid']}:{flag}")
                lines.append(
                    f"      Baseline: {r['baseline_demand_vph']:.1f} vph, "
                    f"v/c={r.get('effective_baseline_vc', r.get('baseline_vc', 0)):.4f} {'[EXCEEDS]' if r['baseline_exceeds'] else '[OK]'}"
                )
                lines.append(
                    f"      Proposed: {r['proposed_demand_vph']:.1f} vph (+{r['vehicles_added']:.1f}), "
                    f"v/c={r['proposed_vc']:.4f} {'[EXCEEDS]' if r['proposed_exceeds'] else '[OK]'}"
                )
            lines.append(f"  → Triggered: {'YES' if s5.get('result') else 'NO'}")

        lines += [
            "",
            f"  → Scenario Tier: {tier}",
            f"  Reason: {scenario_data['reason']}",
        ]

    # ── Final Determination ───────────────────────────────────────────
    d = audit.get("determination", {})

    tier_explanation = {
        "DISCRETIONARY": (
            "DISCRETIONARY REVIEW REQUIRED\n\n"
            "  At least one scenario triggered DISCRETIONARY: the project meets the\n"
            "  dwelling unit size threshold and at least one serving route exceeds the\n"
            "  HCM 2022 v/c capacity threshold under the applicable demand scenario.\n\n"
            "  NOTE: For the wildland scenario, DISCRETIONARY is triggered by capacity\n"
            "  impact (Standard 4), not by fire zone location. Fire zone location is\n"
            "  recorded as a severity modifier and may affect required mitigation conditions."
        ),
        "CONDITIONAL MINISTERIAL": (
            "CONDITIONAL MINISTERIAL APPROVAL\n\n"
            "  The city contains FHSZ zones and the project meets the dwelling unit size\n"
            "  threshold. No scenario triggered DISCRETIONARY (v/c threshold not exceeded).\n\n"
            "  Ministerial approval eligible with mandatory evacuation-related conditions\n"
            "  defined by the city pursuant to its General Plan Safety Element."
        ),
        "MINISTERIAL": (
            "MINISTERIAL APPROVAL ELIGIBLE\n\n"
            "  No scenario triggered DISCRETIONARY or CONDITIONAL MINISTERIAL.\n"
            "  No evacuation-related conditions are flagged by this analysis."
        ),
    }.get(det, det)

    lines += [
        "",
        "=" * 70,
        "FINAL DETERMINATION",
        "=" * 70,
        f"  RESULT: {det_label}",
        "",
        f"  {project.determination_reason}",
        "",
        "  Determination Tier:",
        f"    {tier_explanation}",
        "",
        "  Scenario Tier Summary:",
    ]
    for sname, stier in d.get("scenario_tiers", {}).items():
        lines.append(f"    {sname}: {stier}")

    lines += [
        "",
        f"  Aggregation Logic: {d.get('logic', '')}",
        f"  Tier Ranking: {d.get('tier_rank', '')}",
        "",
        "  This determination is based solely on objective, verifiable criteria.",
        "  No professional discretion was applied. All calculations are reproducible.",
        "  See legal.md for full legal basis and defense reference.",
        "=" * 70,
    ]

    text = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text)
    logger.info(f"Audit trail written to: {output_path}")
    return text


# ---------------------------------------------------------------------------
# Backward-compat helper (used by capacity_analysis.py indirectly)
# ---------------------------------------------------------------------------

def calculate_proposed_vc(proposed_demand: float, capacity: float) -> float:
    """Calculate proposed v/c ratio after adding project vehicles."""
    if capacity <= 0:
        return 0.0
    return proposed_demand / capacity

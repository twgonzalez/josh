# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Determination Brief Generator v3 — thin adapter (Phase 2 refactor).

All HTML is rendered by static/brief_renderer.js via Node subprocess.
This module maps the Python audit dict → BriefInput JSON schema (v1)
and calls the renderer.

Public API:
    create_determination_brief_v3(project, audit, config, city_config, output_path)
    _build_brief_input(project, audit, config, city_config, ...)  — testable adapter
"""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path

# Path to the JS renderer — three parents up from this file reaches project root
_BRIEF_RENDERER_PATH = Path(__file__).parent.parent.parent / "static" / "brief_renderer.js"

# HCM hazard capacity degradation factors (mirrors agents/scenarios constants)
_DEG_FACTORS: dict[str, float] = {
    "vhfhsz":        0.35,
    "high_fhsz":     0.50,
    "moderate_fhsz": 0.75,
    "non_fhsz":      1.00,
}


# ---------------------------------------------------------------------------
# Public API — signature unchanged from v2
# ---------------------------------------------------------------------------

def create_determination_brief_v3(
    project,
    audit: dict,
    config: dict,
    city_config: dict,
    output_path: Path,
) -> Path:
    """Write a legally defensible HTML determination letter (v3) and return output_path."""
    city_slug = output_path.parent.name  # e.g. "berkeley"

    # Read sibling audit trail text for inline embedding
    lat_str        = f"{project.location_lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str        = f"{project.location_lon:.4f}".replace(".", "_").replace("-", "n")
    units_str      = project.dwelling_units
    audit_filename = f"determination_{lat_str}_{lon_str}_{units_str}u.txt"
    audit_txt_path = output_path.parent / audit_filename
    audit_text     = audit_txt_path.read_text(encoding="utf-8") if audit_txt_path.exists() else ""

    brief_input = _build_brief_input(
        project, audit, config, city_config,
        city_slug=city_slug,
        audit_text=audit_text,
        audit_filename=audit_filename,
    )
    html = _call_brief_renderer(brief_input)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# BriefInput builder (BriefInput schema v1)
# ---------------------------------------------------------------------------

def _build_brief_input(
    project,
    audit: dict,
    config: dict,
    city_config: dict,
    *,
    city_slug: str = "",
    audit_text: str = "",
    audit_filename: str = "",
) -> dict:
    """Map Python objects → flat BriefInput JSON schema (brief_input_version: 1)."""
    city_name = city_config.get("city_name", city_config.get("name", city_config.get("city", "City")))

    lat       = project.location_lat
    lon       = project.location_lon
    units     = project.dwelling_units
    proj_name = getattr(project, "project_name", "") or ""

    lat_str   = f"{lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str   = f"{lon:.4f}".replace(".", "_").replace("-", "n")
    proj_slug = proj_name.strip().upper().replace(" ", "-")[:20]
    year      = datetime.date.today().year
    case_num  = (
        f"JOSH-{year}-{proj_slug}-{lat_str}-{lon_str}"
        if proj_slug else
        f"JOSH-{year}-{lat_str}-{lon_str}"
    )

    eval_date = audit.get("evaluation_date", str(datetime.date.today()))
    if "T" in eval_date:
        eval_date = eval_date.split("T")[0]

    # ── Unpack audit dict ────────────────────────────────────────────────────
    determination = audit.get("determination", {})
    wildland      = audit.get("scenarios", {}).get("wildland_ab747", {})
    w_steps       = wildland.get("steps", {})
    s1_app        = w_steps.get("step1_applicability", {})
    s2_scale      = w_steps.get("step2_scale", {})
    s3_routes     = w_steps.get("step3_routes", {})
    s5            = w_steps.get("step5_delta_t", {})

    tier        = (determination.get("result", getattr(project, "determination", None) or "MINISTERIAL")).strip().upper()
    hazard_zone = s5.get("hazard_zone", s1_app.get("std3_hazard_zone", "non_fhsz"))
    deg_factor  = _DEG_FACTORS.get(hazard_zone, 1.00)

    # ── analysis block ───────────────────────────────────────────────────────
    analysis = {
        "applicability_met":         bool(s2_scale.get("result", False)),
        "dwelling_units":            s2_scale.get("dwelling_units", units),
        "unit_threshold":            config.get("unit_threshold", 15),
        "fhsz_flagged":              bool(s1_app.get("std3_fhsz_flagged", False)),
        "fhsz_desc":                 s1_app.get("std3_zone_desc", "Not in FHSZ"),
        "fhsz_level":                s1_app.get("std3_zone_level", 0),
        "hazard_zone":               s1_app.get("std3_hazard_zone", "non_fhsz"),
        "behavioral_mobilization":   s1_app.get("std3_behavioral_mobilization",
                                                 config.get("behavioral_mobilization", 0.90)),
        "hazard_degradation_factor": deg_factor,
        "serving_route_count":       s3_routes.get("serving_route_count", 0),
        "route_radius_miles":        s3_routes.get("radius_miles", 0.5),
        "routes_trigger_analysis":   bool(s3_routes.get("triggers_standard", False)),
        "delta_t_triggered":         bool(s5.get("triggered", False)),
        "egress_minutes":            s5.get("egress_minutes", 0.0),
    }

    # ── paths ────────────────────────────────────────────────────────────────
    paths = [
        {
            "path_id":                       p.get("path_id", ""),
            "bottleneck_osmid":              p.get("bottleneck_osmid", ""),
            "bottleneck_name":               p.get("bottleneck_name", ""),
            "bottleneck_fhsz_zone":          hazard_zone,
            "bottleneck_hcm_capacity_vph":   p.get("bottleneck_hcm_capacity_vph", 0),
            "bottleneck_eff_cap_vph":        p.get("bottleneck_effective_capacity_vph", 0),
            "bottleneck_hazard_degradation": p.get("bottleneck_hazard_degradation", deg_factor),
            "bottleneck_road_type":          p.get("bottleneck_road_type", ""),
            "bottleneck_speed_mph":          p.get("bottleneck_speed_limit", 0),
            "bottleneck_lanes":              p.get("bottleneck_lane_count", 0),
            "delta_t_minutes":               p.get("delta_t_minutes", 0.0),
            "threshold_minutes":             p.get("threshold_minutes",
                                                   s5.get("threshold_minutes", 6.0)),
            "safe_egress_window_minutes":    p.get("safe_egress_window_minutes",
                                                   s5.get("safe_egress_window_minutes", 120.0)),
            "max_project_share":             p.get("max_project_share",
                                                   s5.get("max_project_share", 0.05)),
            "flagged":                       bool(p.get("flagged", False)),
            "project_vehicles":              p.get("project_vehicles",
                                                   s5.get("project_vehicles", 0)),
            "egress_minutes":                s5.get("egress_minutes", 0.0),
        }
        for p in s5.get("path_results", [])
    ]

    # ── result block ─────────────────────────────────────────────────────────
    result = {
        "tier":                       tier,
        "hazard_zone":                hazard_zone,
        "project_vehicles":           s5.get("project_vehicles", 0.0),
        "max_delta_t_minutes":        s5.get("max_delta_t_minutes", 0.0),
        "threshold_minutes":          s5.get("threshold_minutes", 6.0),
        "safe_egress_window_minutes": s5.get("safe_egress_window_minutes", 120.0),
        "max_project_share":          s5.get("max_project_share", 0.05),
        "serving_paths_count":        len(paths),
        "egress_minutes":             s5.get("egress_minutes", 0.0),
        "parameters_version":         config.get("parameters_version", "4.0"),
        "analyzed_at":                eval_date,
        "determination_reason":       determination.get("reason", ""),
        "triggered":                  bool(wildland.get("triggered", False)),
        "paths":                      paths,
    }

    return {
        "brief_input_version": 1,
        "source":              "pipeline",
        "city_name":           city_name,
        "city_slug":           city_slug,
        "case_number":         case_num,
        "eval_date":           eval_date,
        "audit_text":          audit_text,
        "audit_filename":      audit_filename,
        "project": {
            "name":    proj_name,
            "address": getattr(project, "address", "") or "",
            "lat":     lat,
            "lon":     lon,
            "units":   units,
            "stories": getattr(project, "stories", None),
            "apn":     getattr(project, "apn", "") or "",
        },
        "analysis":   analysis,
        "result":     result,
        "parameters": {
            "unit_threshold":     config.get("unit_threshold", 15),
            "vehicles_per_unit":       config.get("vehicles_per_unit", 1.9),
            "behavioral_mobilization": config.get("behavioral_mobilization", 0.90),
            "hazard_degradation": config.get("hazard_degradation", {}),
            "safe_egress_window": config.get("safe_egress_window", {}),
            "max_project_share":  config.get("max_project_share", 0.05),
            "egress_penalty":     config.get("egress_penalty", {}),
        },
    }


# ---------------------------------------------------------------------------
# Node subprocess caller
# ---------------------------------------------------------------------------

def _call_brief_renderer(brief_input: dict) -> str:
    """Invoke static/brief_renderer.js via Node; return rendered HTML string."""
    proc = subprocess.run(
        ["node", str(_BRIEF_RENDERER_PATH)],
        input=json.dumps(brief_input),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"brief_renderer.js failed (exit {proc.returncode}):\n{proc.stderr}"
        )
    if not proc.stdout.strip():
        raise RuntimeError("brief_renderer.js returned empty output")
    return proc.stdout

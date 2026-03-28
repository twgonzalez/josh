# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
AB 747 Evacuation Capacity Report Generator

Produces output/{city}/ab747_report.html — a self-contained, printable HTML
document satisfying California Government Code §65302.15 (AB 747) and SB 99.

The report covers:
  A. Legal Authority
  B. Methodology
  C. Evacuation Route Inventory
  D. City-Wide Clearance Time Analysis
  E. Population at Risk by FHSZ Zone
  F. SB 99 Single-Access Area Identification
  G. System Bottleneck Summary
  H. Improvement Recommendations
  I. Viability Scenarios
  J. Evacuation Shelter Locations
  GIS Export Notice

All data is sourced from cached files produced by `analyze` — no network calls.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

from agents.analysis.clearance_time import (
    ClearanceResult,
    ZoneClearance,
    ZONE_ORDER,
    compute_clearance_time,
)
from agents.analysis.sb99 import Sb99Result, scan_single_access_areas
from agents.visualization.themes import (
    FHSZ_LABELS,
    _EFFECTIVE_CAPACITY_RAMP,
    _effective_capacity_heatmap_color,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_ab747_report(
    city: str,
    roads_gdf: gpd.GeoDataFrame,
    block_groups_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    evacuation_paths: list,
    config: dict,
    city_config: dict,
    output_path: Path,
) -> Path:
    """
    Generate the AB 747 compliance report HTML and write to output_path.

    Parameters
    ----------
    city : str
        City slug (e.g. "berkeley").
    roads_gdf : GeoDataFrame
        Road network with capacity columns (from analyze_capacity).
    block_groups_gdf : GeoDataFrame
        Census block groups with housing_units (from acquire_data).
    fhsz_gdf : GeoDataFrame
        CAL FIRE FHSZ polygons (from acquire_data).
    evacuation_paths : list
        EvacuationPath objects or dicts (from data/{city}/evacuation_paths.json).
    config : dict
        Global parameters (from config/parameters.yaml).
    city_config : dict
        City-specific config (from config/cities/{city}.yaml).
    output_path : Path
        Where to write ab747_report.html.

    Returns
    -------
    Path
        output_path (written).
    """
    # --- Run analysis modules ---
    clearance = compute_clearance_time(block_groups_gdf, evacuation_paths, fhsz_gdf, config)
    sb99 = scan_single_access_areas(evacuation_paths, block_groups_gdf, roads_gdf)

    # --- Filter roads to evacuation routes for tables ---
    routes_df = _to_dataframe(roads_gdf)
    if "is_evacuation_route" in routes_df.columns:
        evac_df = routes_df[routes_df["is_evacuation_route"].astype(bool)].copy()
    else:
        evac_df = routes_df.copy()

    # --- Generate recommendations ---
    recommendations = _generate_recommendations(evac_df, sb99, clearance, config)

    # --- Render HTML ---
    city_name = city_config.get("city_name", city_config.get("name", city_config.get("city", city.title())))
    report_date = str(datetime.date.today())
    html = _render_report(
        city=city,
        city_name=city_name,
        report_date=report_date,
        evac_df=evac_df,
        clearance=clearance,
        sb99=sb99,
        recommendations=recommendations,
        config=config,
        city_config=city_config,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------

def _generate_recommendations(
    evac_df: pd.DataFrame,
    sb99: Sb99Result,
    clearance: ClearanceResult,
    config: dict,
) -> list[dict]:
    """
    Rule-based recommendation engine. All thresholds from config["ab747"].

    Returns list of dicts: {priority, type, description, basis}
    Priority: "HIGH" | "MEDIUM" | "LOW"
    """
    ab747_cfg = config.get("ab747", {})
    top_n = int(ab747_cfg.get("bottleneck_top_n", 10))
    second_egress_min = float(ab747_cfg.get("second_egress_min_units", 50))
    contraflow_vc = float(ab747_cfg.get("contraflow_vc_threshold", 0.80))
    cap_threshold = float(ab747_cfg.get("capacity_improvement_eff_cap_threshold", 700))
    min_conn = int(ab747_cfg.get("capacity_improvement_min_connectivity", 2))

    recs: list[dict] = []
    seen_road_names: set[str] = set()

    # Rule 1 — Network capacity deficit (city-wide)
    safe_windows = config.get("safe_egress_window", {})
    vhfhsz_window = float(safe_windows.get("vhfhsz", 45))
    if (
        clearance.total_clearance_time_minutes != float("inf")
        and clearance.total_clearance_time_minutes > vhfhsz_window
    ):
        recs.append({
            "priority": "HIGH",
            "type": "Network Capacity Deficit",
            "description": (
                f"Modeled city-wide clearance time "
                f"({clearance.total_clearance_time_minutes:.1f} min) exceeds the VHFHSZ "
                f"safe egress window ({vhfhsz_window:.0f} min per NIST TN 2135). "
                "Network-level capacity improvements or demand-management strategies "
                "(contraflow, staged evacuation zones) are required to achieve a defensible "
                "evacuation clearance standard."
            ),
            "basis": "NIST TN 2135 (Camp Fire timeline); Gov. Code §65302.15",
        })

    # Rule 2 — Widen/add lanes to high-connectivity bottleneck segments
    if not evac_df.empty and "effective_capacity_vph" in evac_df.columns:
        worst = _rank_bottlenecks(evac_df, top_n)
        for _, row in worst.iterrows():
            name = str(row.get("name", "") or "Unnamed road")
            eff_cap = float(row.get("effective_capacity_vph", 0) or 0)
            conn = int(row.get("connectivity_score", 0) or 0)
            if eff_cap < cap_threshold and conn >= min_conn and name not in seen_road_names:
                seen_road_names.add(name)
                recs.append({
                    "priority": "HIGH",
                    "type": "Capital Improvement — Capacity",
                    "description": (
                        f"Widen or add lanes to {name} "
                        f"(effective capacity {eff_cap:.0f} vph under fire conditions; "
                        f"{conn} evacuation path(s) route through this segment). "
                        "Increasing lane count or reducing FHSZ-related impedance would "
                        "raise effective capacity and reduce ΔT for all dependent projects."
                    ),
                    "basis": "HCM 2022 §12; ITE Traffic Engineering Handbook",
                })

    # Rule 3 — Second egress for large single-access block groups
    for bg in sb99.block_group_details:
        if bg.is_single_access and bg.housing_units >= second_egress_min:
            loc = bg.label if bg.label and bg.label != bg.geoid else f"block group {bg.geoid}"
            recs.append({
                "priority": "HIGH",
                "type": "Capital Improvement — Second Egress",
                "description": (
                    f"Area {loc} ({bg.housing_units:,.0f} housing units, {bg.geoid}) "
                    f"has only {bg.exit_count} modeled evacuation exit(s). "
                    "Evaluate opportunities for a secondary road connection to the "
                    "regional network. Consider requiring secondary access as a "
                    "condition on new development in this area."
                ),
                "basis": "Gov. Code §65302.15(b)(3) (SB 99 single-access identification)",
            })

    # Rule 4 — Contraflow operations on near-capacity multilane roads
    if not evac_df.empty and "vc_ratio" in evac_df.columns and "road_type" in evac_df.columns:
        contraflow_candidates = evac_df[
            (evac_df["road_type"] == "multilane")
            & (evac_df["vc_ratio"].fillna(0) > contraflow_vc)
        ].copy()
        seen_contraflow: set[str] = set()
        for _, row in contraflow_candidates.iterrows():
            name = str(row.get("name", "") or "Unnamed road")
            vc = float(row.get("vc_ratio", 0) or 0)
            if name not in seen_contraflow:
                seen_contraflow.add(name)
                recs.append({
                    "priority": "MEDIUM",
                    "type": "Operational — Contraflow",
                    "description": (
                        f"Consider contraflow operations on {name} during declared "
                        f"evacuations (baseline v/c {vc:.2f}, approaching capacity). "
                        "Pre-plan contraflow zones in the Emergency Operations Plan and "
                        "coordinate with county sheriff and Caltrans."
                    ),
                    "basis": "FHWA Emergency Transportation Operations (2012), Chapter 4",
                })

    # Rule 5 — Low: verify non-FHSZ areas have modeled paths
    if sb99.modeled_block_groups < sb99.total_block_groups:
        unmapped = sb99.total_block_groups - sb99.modeled_block_groups
        recs.append({
            "priority": "LOW",
            "type": "Data Quality — Unmapped Block Groups",
            "description": (
                f"{unmapped} of {sb99.total_block_groups} block group(s) have no "
                "modeled evacuation path. This may indicate block groups outside the "
                "road network graph or in areas with no qualifying exit highway. "
                "Re-run `analyze --refresh` or review the road network coverage for "
                "these areas."
            ),
            "basis": "Internal data quality check — no statutory basis",
        })

    return recs


# ---------------------------------------------------------------------------
# Bottleneck helper
# ---------------------------------------------------------------------------

def _rank_bottlenecks(evac_df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Return top_n worst evacuation segments sorted by effective_capacity_vph ascending."""
    df = evac_df.copy()
    if "effective_capacity_vph" not in df.columns:
        return pd.DataFrame()
    df = df.sort_values("effective_capacity_vph", ascending=True).head(top_n)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def _render_report(
    city: str,
    city_name: str,
    report_date: str,
    evac_df: pd.DataFrame,
    clearance: ClearanceResult,
    sb99: Sb99Result,
    recommendations: list[dict],
    config: dict,
    city_config: dict,
) -> str:
    ab747_cfg = config.get("ab747", {})
    top_n = int(ab747_cfg.get("bottleneck_top_n", 10))

    sections = "\n".join([
        _build_report_header(city_name, report_date),
        _build_executive_summary(clearance, sb99, config),
        "<main>",
        _build_legal_authority_section(),
        _build_methodology_section(config),
        _build_route_inventory_section(evac_df, config),
        _build_clearance_time_section(clearance, config),
        _build_population_risk_section(clearance, config),
        _build_sb99_section(sb99),
        _build_bottleneck_section(evac_df, config),
        _build_recommendations_section(recommendations),
        _build_viability_scenarios_section(),
        _build_shelters_section(city_config),
        _build_gis_export_notice(city),
        "</main>",
        _build_report_footer(report_date),
    ])

    return _wrap_report_html(city_name, report_date, sections)


# ---------------------------------------------------------------------------
# HTML wrapper
# ---------------------------------------------------------------------------

def _wrap_report_html(city_name: str, report_date: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AB 747 Evacuation Capacity Report — {city_name} ({report_date})</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 13px;
      line-height: 1.55;
      color: #212529;
      background: #f8f9fa;
      margin: 0;
      padding: 0;
    }}
    main {{
      max-width: 900px;
      margin: 0 auto;
      padding: 0 24px 48px;
    }}
    h2 {{ font-size: 15px; font-weight: 700; color: #1a1a2e; margin: 0 0 6px; }}
    h3 {{ font-size: 13px; font-weight: 600; color: #333; margin: 0 0 4px; }}
    p  {{ margin: 0 0 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin: 8px 0; }}
    th {{ background: #e9ecef; color: #495057; font-weight: 600; text-align: left;
          padding: 5px 8px; border-bottom: 2px solid #dee2e6; }}
    td {{ padding: 4px 8px; border-bottom: 1px solid #e9ecef; vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    .section-card {{
      background: #fff;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      padding: 18px 20px;
      margin: 16px 0;
    }}
    .section-label {{
      display: inline-block;
      background: #1a1a2e;
      color: #fff;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.08em;
      padding: 2px 7px;
      border-radius: 3px;
      margin-bottom: 6px;
      text-transform: uppercase;
    }}
    .stat-grid {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; }}
    .stat-card {{
      flex: 1; min-width: 150px;
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      padding: 12px 16px;
      text-align: center;
    }}
    .stat-value {{ font-size: 22px; font-weight: 700; color: #1a1a2e; }}
    .stat-label {{ font-size: 11px; color: #6c757d; margin-top: 2px; }}
    .status-ok  {{ background: #e8f5e9; color: #2e7d32; padding: 2px 8px;
                   border-radius: 10px; font-size: 11px; font-weight: 600; }}
    .status-warn {{ background: #fff3e0; color: #e65100; padding: 2px 8px;
                    border-radius: 10px; font-size: 11px; font-weight: 600; }}
    .status-alert {{ background: #fdecea; color: #c62828; padding: 2px 8px;
                     border-radius: 10px; font-size: 11px; font-weight: 600; }}
    .rec-card {{
      border-left: 4px solid #dee2e6;
      padding: 10px 14px;
      margin: 8px 0;
      background: #fafafa;
      border-radius: 0 4px 4px 0;
    }}
    .rec-high   {{ border-left-color: #c62828; background: #fdecea; }}
    .rec-medium {{ border-left-color: #e65100; background: #fff3e0; }}
    .rec-low    {{ border-left-color: #2e7d32; background: #e8f5e9; }}
    .rec-priority {{
      font-size: 10px; font-weight: 700; letter-spacing: 0.05em;
      text-transform: uppercase; display: inline-block;
      padding: 1px 6px; border-radius: 3px; margin-bottom: 4px;
    }}
    .rec-priority-HIGH   {{ background: #c62828; color: #fff; }}
    .rec-priority-MEDIUM {{ background: #e65100; color: #fff; }}
    .rec-priority-LOW    {{ background: #2e7d32; color: #fff; }}
    .rec-type  {{ font-weight: 600; font-size: 12px; color: #1a1a2e; }}
    .rec-basis {{ font-size: 11px; color: #6c757d; margin-top: 4px; }}
    .badge-placeholder {{
      background: #f0f0f0; border: 1px dashed #bbb;
      border-radius: 6px; padding: 14px;
      color: #888; font-style: italic; font-size: 12px;
    }}
    .note {{ font-size: 11px; color: #6c757d; font-style: italic; margin-top: 6px; }}
    a {{ color: #1a6eb5; }}
    @media print {{
      @page {{ size: letter; margin: 0.75in; }}
      body {{ background: white; font-size: 11px; }}
      main {{ max-width: none; padding: 0; }}
      .section-card {{ break-inside: avoid; border: 1px solid #ccc; }}
      .rec-card  {{ break-inside: avoid; }}
      .stat-grid {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_report_header(city_name: str, report_date: str) -> str:
    return f"""
<div style="background:#1a1a2e; color:#fff; padding:28px 32px 22px;">
  <div style="max-width:900px; margin:0 auto;">
    <div style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase;
                color:#8899bb; margin-bottom:6px;">
      JOSH — Jurisdictional Objective Standards for Housing
    </div>
    <h1 style="font-size:22px; font-weight:700; margin:0 0 4px;">
      AB 747 Fire Evacuation Capacity Report
    </h1>
    <div style="font-size:14px; color:#c8d0e0; margin-bottom:12px;">
      {city_name} &nbsp;·&nbsp; Gov. Code §65302.15 (AB 747) + SB 99 Compliance
    </div>
    <div style="font-size:11px; color:#8899bb;">
      Report date: {report_date} &nbsp;·&nbsp;
      JOSH v3.4 &nbsp;·&nbsp;
      Legal basis: <em>AB 747 (2019)</em>, <em>SB 99 (2019)</em>
    </div>
  </div>
</div>"""


def _build_executive_summary(
    clearance: ClearanceResult,
    sb99: Sb99Result,
    config: dict,
) -> str:
    safe_windows = config.get("safe_egress_window", {})
    vhfhsz_window = float(safe_windows.get("vhfhsz", 45))

    ct = clearance.total_clearance_time_minutes
    if ct == float("inf"):
        ct_display = "N/A"
        ct_status = '<span class="status-warn">No exit data</span>'
    elif ct > vhfhsz_window:
        ct_display = f"{ct:.1f} min"
        ct_status = f'<span class="status-alert">Exceeds {vhfhsz_window:.0f}-min VHFHSZ window</span>'
    else:
        ct_display = f"{ct:.1f} min"
        ct_status = f'<span class="status-ok">Within {vhfhsz_window:.0f}-min VHFHSZ window</span>'

    fhsz_hu = sum(
        z.housing_units for z in clearance.per_zone if z.zone != "non_fhsz"
    )
    total_hu = clearance.total_housing_units
    fhsz_pct = (fhsz_hu / total_hu * 100) if total_hu > 0 else 0

    single_pct = sb99.fraction_single_access * 100

    return f"""
<div style="max-width:900px; margin:0 auto; padding:20px 24px 0;">
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-value">{ct_display}</div>
      <div class="stat-label">City-Wide Clearance Time</div>
      <div style="margin-top:6px">{ct_status}</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{fhsz_hu:,.0f}</div>
      <div class="stat-label">Housing Units in FHSZ Zones ({fhsz_pct:.1f}% of city)</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{sb99.single_access_count}</div>
      <div class="stat-label">Block Groups with &lt;2 Modeled Exits (SB 99)</div>
      <div style="margin-top:6px">
        <span class="{'status-alert' if sb99.single_access_count > 0 else 'status-ok'}">
          {single_pct:.0f}% of housing units
        </span>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{clearance.total_exit_capacity_vph:,.0f}</div>
      <div class="stat-label">Total Exit Capacity (vph, fire-degraded)</div>
    </div>
  </div>
</div>"""


def _build_legal_authority_section() -> str:
    rows = [
        ("AB 747 (2019)", "Gov. Code §65302.15", "Safety Element must identify evacuation routes, capacity, safety, and viability", "Route inventory, capacity analysis, viability scenarios — Sections C, D, I"),
        ("SB 99 (2019)", "Gov. Code §65302.15(b)(3)", "Identify residential areas lacking 2+ distinct evacuation routes", "Single-access scan — Section F"),
        ("HCM 2022", "TRB Highway Capacity Manual, 7th Ed.", "Capacity methodology for road segments (pc/h/lane by road type and speed)", "All capacity calculations — Sections C, D, G"),
        ("NIST TN 2135", "Maranghides et al. (2021)", "Camp Fire timeline — basis for VHFHSZ 45-min safe egress window", "Clearance time comparison — Section D"),
        ("NFPA 101", "Life Safety Code", "100% building occupant evacuation design basis — mobilization rate 0.90", "Demand calculations — Sections D, E"),
        ("CAL FIRE OSFM", "FHSZ ArcGIS REST API", "Fire Hazard Severity Zone designations (HAZ_CLASS 1/2/3)", "Zone classification — all sections"),
    ]
    table_rows = "\n".join(
        f"<tr><td><strong>{r[0]}</strong></td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"
        for r in rows
    )
    return f"""
<div class="section-card">
  <span class="section-label">A — Legal Authority</span>
  <h2>Legal Authority &amp; Source Citations</h2>
  <table>
    <thead><tr><th>Authority</th><th>Citation</th><th>Requirement</th><th>This Report</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>"""


def _build_methodology_section(config: dict) -> str:
    vpu = config.get("vehicles_per_unit", 2.5)
    mob = config.get("mobilization_rate", 0.90)
    safe_windows = config.get("safe_egress_window", {})
    deg = config.get("hazard_degradation", {}).get("factors", {})

    deg_rows = "\n".join(
        f"<tr><td>{zone}</td><td>{factor}</td><td>{int(float(safe_windows.get(zone, 120)))} min</td>"
        f"<td>{int(float(safe_windows.get(zone, 120)) * float(config.get('max_project_share', 0.05)))} min</td></tr>"
        for zone, factor in deg.items()
    )

    return f"""
<div class="section-card">
  <span class="section-label">B — Methodology</span>
  <h2>Analytical Methodology</h2>
  <h3>City-Wide Clearance Time Formula</h3>
  <p style="font-family:monospace; background:#f8f9fa; padding:8px; border-radius:4px; font-size:12px;">
    total_vehicles = &Sigma;(block_group.housing_units) &times; {vpu} vpu &times; {mob} mobilization<br>
    total_exit_capacity_vph = &Sigma; unique exit segments (effective_capacity_vph, deduplicated)<br>
    clearance_time_minutes = (total_vehicles / total_exit_capacity_vph) &times; 60
  </p>
  <p>
    <strong>Mobilization rate {mob}:</strong> Derived from NFPA 101 Life Safety Code design basis
    (100% occupant evacuation) adjusted for ~10% zero-vehicle households (Census ACS B25044).
    Not zone-dependent — applies uniformly per v3.4 architecture.
  </p>
  <h3>Hazard Degradation &amp; Safe Egress Windows</h3>
  <table>
    <thead><tr><th>FHSZ Zone</th><th>Road Capacity Factor</th><th>Safe Egress Window</th><th>Per-Project &Delta;T Threshold (5%)</th></tr></thead>
    <tbody>{deg_rows}</tbody>
  </table>
  <p class="note">
    Degradation factors: HCM 2022 Exhibits 10-15/10-17 composite, validated against NIST Camp Fire road closure data.
    Safe egress windows: NIST TN 2135, TN 2252, TN 2262.
    ΔT threshold = safe_egress_window &times; 5% (max project share, standard engineering significance).
  </p>
  <h3>Road Capacity (HCM 2022)</h3>
  <p>
    Freeway: 2,250 pc/h/lane. Multilane: 1,900 pc/h/lane.
    Two-lane: 900–1,700 vph by posted speed (HCM 2022 Ch. 15).
    Effective capacity = HCM capacity &times; hazard degradation factor.
  </p>
  <h3>SB 99 Methodology</h3>
  <p>
    A block group is flagged as single-access when fewer than 2 distinct
    <code>exit_segment_osmid</code> values appear in its modeled evacuation paths.
    Each unique exit osmid represents a physically separate handoff point from
    the local road network into the regional network (motorway/trunk/primary).
  </p>
</div>"""


def _build_route_inventory_section(evac_df: pd.DataFrame, config: dict) -> str:
    if evac_df.empty:
        return """
<div class="section-card">
  <span class="section-label">C — Route Inventory</span>
  <h2>Evacuation Route Inventory</h2>
  <p class="badge-placeholder">No evacuation route data available. Run <code>analyze</code> first.</p>
</div>"""

    required_cols = ["name", "road_type", "lane_count", "speed_limit",
                     "fhsz_zone", "hazard_degradation", "effective_capacity_vph"]
    display_df = evac_df.copy()
    for col in required_cols:
        if col not in display_df.columns:
            display_df[col] = ""

    display_df = display_df.sort_values("effective_capacity_vph", ascending=True)

    # Count by FHSZ zone
    zone_counts = {}
    if "fhsz_zone" in display_df.columns:
        zone_counts = display_df["fhsz_zone"].value_counts().to_dict()

    zone_summary = " &nbsp;|&nbsp; ".join(
        f"{z}: {n}" for z, n in sorted(zone_counts.items())
    )

    rows_html = ""
    for _, row in display_df.iterrows():
        eff_cap = float(row.get("effective_capacity_vph") or 0)
        color, opacity = _effective_capacity_heatmap_color(eff_cap)
        bg = _hex_to_rgba(color, opacity * 0.6)
        hcm_cap = float(row.get("capacity_vph") or 0)
        deg = float(row.get("hazard_degradation") or 1.0)
        vc = row.get("vc_ratio", "")
        los = row.get("los", "")
        vc_display = f"{float(vc):.2f}" if vc != "" and vc is not None and str(vc) != "nan" else "—"
        los_display = str(los) if los and str(los) != "nan" else "—"
        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td>{row.get("name") or "—"}</td>'
            f'<td>{row.get("road_type") or "—"}</td>'
            f'<td style="text-align:center">{int(row.get("lane_count") or 1)}</td>'
            f'<td style="text-align:center">{int(row.get("speed_limit") or 0)}</td>'
            f'<td>{_fhsz_badge(str(row.get("fhsz_zone") or ""))}</td>'
            f'<td style="text-align:right">{hcm_cap:,.0f}</td>'
            f'<td style="text-align:center">{deg:.2f}</td>'
            f'<td style="text-align:right; font-weight:600">{eff_cap:,.0f}</td>'
            f'<td style="text-align:center">{vc_display}</td>'
            f'<td style="text-align:center">{los_display}</td>'
            f'</tr>\n'
        )

    legend = _capacity_ramp_legend()

    return f"""
<div class="section-card">
  <span class="section-label">C — Route Inventory</span>
  <h2>Evacuation Route Inventory</h2>
  <p>
    <strong>{len(display_df):,} evacuation route segments</strong> identified within
    the city network. {zone_summary}
  </p>
  {legend}
  <div style="max-height:400px; overflow-y:auto; margin-top:8px;">
    <table>
      <thead>
        <tr>
          <th>Road Name</th><th>Type</th><th>Lanes</th><th>Speed (mph)</th>
          <th>FHSZ Zone</th><th>HCM Cap (vph)</th><th>Degradation</th>
          <th>Eff. Cap (vph)</th><th>v/c</th><th>LOS</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <p class="note">
    Sorted by effective capacity ascending (worst first).
    v/c and LOS are informational only — not used in ΔT determination.
  </p>
</div>"""


def _build_clearance_time_section(clearance: ClearanceResult, config: dict) -> str:
    safe_windows = config.get("safe_egress_window", {})

    ct = clearance.total_clearance_time_minutes
    ct_display = f"{ct:.1f}" if ct != float("inf") else "∞"

    zone_rows = ""
    for z in clearance.per_zone:
        window = z.safe_egress_window_minutes
        ct_z = z.clearance_time_minutes
        ct_z_disp = f"{ct_z:.1f}" if ct_z != float("inf") else "&infin;"
        ratio_disp = f"{z.ratio_to_window:.2f}" if z.ratio_to_window != float("inf") else "&infin;"
        if z.is_over_window:
            row_style = 'background:#fdecea'
            status = '<span class="status-alert">EXCEEDS</span>'
        else:
            row_style = 'background:#e8f5e9'
            status = '<span class="status-ok">Within Window</span>'
        zone_rows += (
            f'<tr style="{row_style}">'
            f'<td>{z.zone_label}</td>'
            f'<td style="text-align:right">{z.housing_units:,.0f}</td>'
            f'<td style="text-align:right">{z.total_vehicles:,.0f}</td>'
            f'<td style="text-align:right">{z.exit_capacity_vph:,.0f}</td>'
            f'<td style="text-align:right; font-weight:600">{ct_z_disp}</td>'
            f'<td style="text-align:right">{window:.0f}</td>'
            f'<td style="text-align:right">{ratio_disp}</td>'
            f'<td style="text-align:center">{status}</td>'
            f'</tr>\n'
        )

    notes_html = "".join(f"<li>{n}</li>" for n in clearance.methodology_notes)

    return f"""
<div class="section-card">
  <span class="section-label">D — Clearance Time</span>
  <h2>City-Wide Evacuation Clearance Time Analysis</h2>
  <p>
    <strong>Formula:</strong>
    clearance_time = (total_vehicles / total_exit_capacity_vph) &times; 60
  </p>
  <div class="stat-grid" style="margin-bottom:12px;">
    <div class="stat-card">
      <div class="stat-value">{clearance.total_housing_units:,.0f}</div>
      <div class="stat-label">Total Housing Units</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{clearance.total_vehicles:,.0f}</div>
      <div class="stat-label">Peak Evacuation Vehicles</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{clearance.total_exit_capacity_vph:,.0f} vph</div>
      <div class="stat-label">Total Exit Capacity (fire-degraded)</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{ct_display} min</div>
      <div class="stat-label">City-Wide Clearance Time</div>
    </div>
  </div>
  <h3>Per-Zone Breakdown</h3>
  <table>
    <thead>
      <tr>
        <th>Zone</th><th>Housing Units</th><th>Vehicles</th>
        <th>Exit Cap (vph)</th><th>Clearance (min)</th>
        <th>Safe Window (min)</th><th>Ratio</th><th>Status</th>
      </tr>
    </thead>
    <tbody>{zone_rows}</tbody>
  </table>
  <p class="note">
    City-wide clearance assumes simultaneous full-mobilization evacuation — a
    planning worst case per NIST TN 2135. Staged/zone-based evacuation produces
    lower per-zone demand and shorter actual clearance times.
    Exit capacity is the sum of unique exit segment effective_capacity_vph
    (deduplicated by OSM segment ID to avoid double-counting parallel exits).
  </p>
  <ul class="note">{notes_html}</ul>
</div>"""


def _build_population_risk_section(clearance: ClearanceResult, config: dict) -> str:
    max_share = float(config.get("max_project_share", 0.05))
    total_hu = clearance.total_housing_units

    rows = ""
    for z in clearance.per_zone:
        pct = (z.housing_units / total_hu * 100) if total_hu > 0 else 0
        window = z.safe_egress_window_minutes
        dt_thresh = window * max_share
        fhsz_desc = {
            "vhfhsz": "Very High — imminent flame and smoke, severe visibility loss",
            "high_fhsz": "High — significant fire hazard, moderate smoke possible",
            "moderate_fhsz": "Moderate — fire hazard present, lower immediate risk",
            "non_fhsz": "Not designated — standard emergency planning applies",
        }.get(z.zone, "")
        rows += (
            f"<tr>"
            f"<td>{z.zone_label}</td>"
            f"<td style='text-align:right'>{z.housing_units:,.0f}</td>"
            f"<td style='text-align:right'>{pct:.1f}%</td>"
            f"<td>{fhsz_desc}</td>"
            f"<td style='text-align:right'>{window:.0f} min</td>"
            f"<td style='text-align:right'>{dt_thresh:.2f} min</td>"
            f"</tr>\n"
        )

    return f"""
<div class="section-card">
  <span class="section-label">E — Population at Risk</span>
  <h2>Population at Risk by FHSZ Zone</h2>
  <table>
    <thead>
      <tr>
        <th>FHSZ Zone</th><th>Housing Units</th><th>% of City</th>
        <th>Hazard Description</th><th>Safe Egress Window</th>
        <th>&Delta;T Threshold (5%)</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="note">
    Housing unit counts are area-weighted intersections of Census ACS block groups
    with CAL FIRE FHSZ polygons. The &Delta;T threshold is the per-project clearance
    time budget: safe_egress_window &times; 5% maximum project share.
  </p>
</div>"""


def _build_sb99_section(sb99: Sb99Result) -> str:
    flag_rows = ""
    for bg in sb99.block_group_details:
        if bg.is_single_access:
            label_html = (
                f"{bg.label}"
                f"<br><span style='font-family:monospace; font-size:10px; color:#aaa'>{bg.geoid}</span>"
            )
            flag_rows += (
                f"<tr>"
                f"<td>{label_html}</td>"
                f"<td style='text-align:right'>{bg.housing_units:,.0f}</td>"
                f"<td style='text-align:center'>{bg.exit_count}</td>"
                f"<td style='font-family:monospace; font-size:10px'>"
                f"{', '.join(bg.exit_osmids) if bg.exit_osmids else '—'}"
                f"</td>"
                f"</tr>\n"
            )

    table_html = f"""
<table>
  <thead>
    <tr><th>Block Group Location</th><th>Housing Units</th><th>Modeled Exits</th><th>Exit Osmid(s)</th></tr>
  </thead>
  <tbody>{flag_rows or '<tr><td colspan="4" style="text-align:center; color:#888;">No single-access block groups identified.</td></tr>'}</tbody>
</table>""" if sb99.single_access_count > 0 else '<p class="status-ok" style="display:inline-block">No single-access block groups identified.</p>'

    return f"""
<div class="section-card">
  <span class="section-label">F — SB 99</span>
  <h2>SB 99: Single-Access Area Identification</h2>
  <p>
    <strong>{sb99.single_access_count}</strong> of {sb99.total_block_groups} block groups
    ({sb99.fraction_single_access * 100:.1f}% of housing units,
    {sb99.single_access_housing_units:,.0f} units)
    have fewer than 2 distinct modeled evacuation exit routes.
  </p>
  {table_html}
  <p class="note">{sb99.methodology_note}</p>
</div>"""


def _build_bottleneck_section(evac_df: pd.DataFrame, config: dict) -> str:
    ab747_cfg = config.get("ab747", {})
    top_n = int(ab747_cfg.get("bottleneck_top_n", 10))

    if evac_df.empty or "effective_capacity_vph" not in evac_df.columns:
        return f"""
<div class="section-card">
  <span class="section-label">G — Bottlenecks</span>
  <h2>System Bottleneck Summary</h2>
  <p class="badge-placeholder">No capacity data available.</p>
</div>"""

    worst = _rank_bottlenecks(evac_df, top_n)
    rows_html = ""
    for _, row in worst.iterrows():
        eff_cap = float(row.get("effective_capacity_vph") or 0)
        color, opacity = _effective_capacity_heatmap_color(eff_cap)
        bg = _hex_to_rgba(color, opacity * 0.5)
        conn = int(row.get("connectivity_score") or 0)
        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td>{row.get("name") or "—"}</td>'
            f'<td>{_fhsz_badge(str(row.get("fhsz_zone") or ""))}</td>'
            f'<td>{row.get("road_type") or "—"}</td>'
            f'<td style="text-align:center">{int(row.get("lane_count") or 1)}</td>'
            f'<td style="text-align:right">{float(row.get("capacity_vph") or 0):,.0f}</td>'
            f'<td style="text-align:center">{float(row.get("hazard_degradation") or 1):.2f}</td>'
            f'<td style="text-align:right; font-weight:600">{eff_cap:,.0f}</td>'
            f'<td style="text-align:center">{conn}</td>'
            f'</tr>\n'
        )

    return f"""
<div class="section-card">
  <span class="section-label">G — Bottlenecks</span>
  <h2>System Bottleneck Summary — Top {top_n} Constrained Segments</h2>
  <p>
    These segments represent the binding constraints on evacuation flow
    and are priority candidates for capital improvement.
  </p>
  <table>
    <thead>
      <tr>
        <th>Road Name</th><th>FHSZ Zone</th><th>Type</th><th>Lanes</th>
        <th>HCM Cap (vph)</th><th>Degradation</th>
        <th>Eff. Cap (vph)</th><th>Paths Through</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  {_capacity_ramp_legend()}
</div>"""


def _build_recommendations_section(recommendations: list[dict]) -> str:
    if not recommendations:
        return """
<div class="section-card">
  <span class="section-label">H — Recommendations</span>
  <h2>Improvement Recommendations</h2>
  <p class="status-ok" style="display:inline-block">No improvement recommendations generated.</p>
</div>"""

    cards_html = ""
    for rec in recommendations:
        pri = rec["priority"]
        css_class = f"rec-{pri.lower()}"
        pri_class = f"rec-priority-{pri}"
        cards_html += f"""
<div class="rec-card {css_class}">
  <span class="rec-priority {pri_class}">{pri}</span>
  <div class="rec-type">{rec['type']}</div>
  <p style="margin:4px 0 4px;">{rec['description']}</p>
  <div class="rec-basis">Basis: {rec['basis']}</div>
</div>"""

    return f"""
<div class="section-card">
  <span class="section-label">H — Recommendations</span>
  <h2>Improvement Recommendations</h2>
  <p>Recommendations are generated algorithmically from the capacity analysis results.
  All thresholds trace to published standards (see Section A).</p>
  {cards_html}
</div>"""


def _build_viability_scenarios_section() -> str:
    return """
<div class="section-card">
  <span class="section-label">I — Viability Scenarios</span>
  <h2>Evacuation Viability Scenarios</h2>
  <p>
    <strong>Wildfire scenario:</strong> This report analyzes the wildfire evacuation
    scenario using CAL FIRE FHSZ zone designations and HCM 2022 composite degradation
    factors validated against the 2018 Camp Fire (NIST TN 2135). This is the primary
    hazard scenario required by AB 747 for jurisdictions with land in High or
    Very High FHSZ zones.
  </p>
  <p>
    <strong>Other hazard scenarios:</strong> Gov. Code §65302.15(d) requires analysis
    across a range of emergency scenarios. Flood, earthquake, hazardous materials,
    and multi-hazard compounding scenarios were not modeled in this analysis and
    should be addressed in separate planning documents, consistent with the
    Local Hazard Mitigation Plan and Emergency Operations Plan.
  </p>
  <p>
    <strong>SB 79 transit proximity:</strong> Projects within 0.5 miles of Tier 1 or
    Tier 2 transit are flagged informatively. Transit proximity does not affect the
    evacuation capacity determination tier and is reported separately in project-level
    determination letters.
  </p>
</div>"""


def _build_shelters_section(city_config: dict) -> str:
    shelters = city_config.get("shelters", [])
    if not shelters:
        return """
<div class="section-card">
  <span class="section-label">J — Shelters</span>
  <h2>Evacuation Shelter Locations</h2>
  <div class="badge-placeholder">
    Shelter data not configured. Add a <code>shelters:</code> list to
    <code>config/cities/{city}.yaml</code> to populate this section.<br><br>
    Each entry should include: <code>name</code>, <code>address</code>,
    <code>capacity</code> (persons), <code>lat</code>, <code>lon</code>.
  </div>
</div>"""

    rows = "".join(
        f"<tr>"
        f"<td>{s.get('name', '—')}</td>"
        f"<td>{s.get('address', '—')}</td>"
        f"<td style='text-align:right'>{s.get('capacity', '—')}</td>"
        f"<td style='text-align:right'>{s.get('lat', '—')}</td>"
        f"<td style='text-align:right'>{s.get('lon', '—')}</td>"
        f"</tr>\n"
        for s in shelters
    )
    return f"""
<div class="section-card">
  <span class="section-label">J — Shelters</span>
  <h2>Evacuation Shelter Locations</h2>
  <table>
    <thead><tr><th>Name</th><th>Address</th><th>Capacity (persons)</th><th>Lat</th><th>Lon</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


def _build_gis_export_notice(city: str) -> str:
    return f"""
<div class="section-card">
  <span class="section-label">GIS Export</span>
  <h2>Machine-Readable Data Export</h2>
  <p>
    The following files contain all route geometry and capacity attributes
    required for GIS import into ArcGIS, QGIS, or equivalent:
  </p>
  <ul>
    <li>
      <code>output/{city}/routes.csv</code> — Evacuation route segments with
      capacity_vph, effective_capacity_vph, fhsz_zone, hazard_degradation,
      vc_ratio, los, is_evacuation_route, connectivity_score, catchment_units,
      and geometry.
    </li>
    <li>
      <code>data/{city}/evacuation_paths.json</code> — Per-path bottleneck data
      with WGS-84 coordinate chains (compatible with GeoJSON LineString import).
    </li>
    <li>
      <code>data/{city}/fhsz.geojson</code> — CAL FIRE FHSZ zone polygons
      (HAZ_CLASS 1/2/3, WGS-84).
    </li>
  </ul>
</div>"""


def _build_report_footer(report_date: str) -> str:
    return f"""
<footer style="max-width:900px; margin:32px auto 0; padding:16px 24px;
               border-top:1px solid #dee2e6; font-size:11px; color:#6c757d;">
  JOSH v3.4 &nbsp;&middot;&nbsp; California Stewardship Alliance &nbsp;&middot;&nbsp;
  Generated {report_date} &nbsp;&middot;&nbsp;
  Gov. Code §65302.15 (AB 747) compliance &nbsp;&middot;&nbsp;
  AGPL-3.0-or-later &nbsp;&middot;&nbsp;
  <a href="https://github.com/csf/josh">github.com/csf/josh</a>
</footer>"""


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _to_dataframe(gdf) -> pd.DataFrame:
    """Convert GeoDataFrame to plain DataFrame, dropping geometry."""
    if isinstance(gdf, gpd.GeoDataFrame):
        return pd.DataFrame(gdf.drop(columns=gdf.geometry.name, errors="ignore"))
    if isinstance(gdf, pd.DataFrame):
        return gdf
    return pd.DataFrame()


def _hex_to_rgba(hex_color: str, opacity: float) -> str:
    """Convert #rrggbb + opacity to rgba(r,g,b,a) CSS string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{opacity:.2f})"


def _fhsz_badge(zone: str) -> str:
    """Return a small colored badge for an FHSZ zone string."""
    colors = {
        "vhfhsz":       ("#d7301f", "#fff"),
        "high_fhsz":    ("#fc8d59", "#fff"),
        "moderate_fhsz": ("#ffeda0", "#555"),
        "non_fhsz":     ("#dee2e6", "#555"),
    }
    labels = {
        "vhfhsz":       "VH",
        "high_fhsz":    "High",
        "moderate_fhsz": "Mod",
        "non_fhsz":     "Non",
    }
    bg, fg = colors.get(zone, ("#dee2e6", "#555"))
    label = labels.get(zone, zone or "—")
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:10px; font-weight:600; '
        f'padding:1px 5px; border-radius:3px;">{label}</span>'
    )


def _capacity_ramp_legend() -> str:
    """Return a small HTML legend for the capacity color ramp."""
    items = [
        ("#dc3545", "&lt;350 vph — Severe"),
        ("#fd7e14", "350–700 vph — Low"),
        ("#ffc107", "700–1200 vph — Moderate"),
        ("#adb5bd", "&gt;1200 vph — Ample"),
    ]
    swatches = "".join(
        f'<span style="display:inline-flex; align-items:center; margin-right:12px;">'
        f'<span style="width:12px; height:12px; background:{c}; display:inline-block; '
        f'border-radius:2px; margin-right:4px;"></span>'
        f'<span style="font-size:11px; color:#555">{label}</span>'
        f'</span>'
        for c, label in items
    )
    return f'<div style="margin:6px 0;">{swatches}</div>'

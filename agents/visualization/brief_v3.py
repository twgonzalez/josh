# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Determination Brief Generator v3 — JOSH / California Stewardship Alliance

Reframed from legacy "5 Standards" structure to reflect v3.4 ΔT architecture:
  - "Standards Analysis" replaced by "Analysis" with four named sections:
      1. Applicability Threshold   — size gate (formerly Standard 1)
      2. Site Parameters           — FHSZ zone lookup + derived inputs
                                     (formerly Standard 3; not a determination
                                      step — sets degradation factor + ΔT threshold)
      3. Evacuation Clearance Analysis — route identification + ΔT test
                                     (formerly Standards 2+4 merged)
      4. SB 79 Disclosure          — informational strip only, no badge number
                                     (formerly Standard 5)
  - "Standards 1–4" language removed from determination box; replaced with
    "Wildland Evacuation Analysis"
  - Cleaned v1 errors (unchanged from v3 init):
      · 0.57 ITE peak-hour factor removed
      · "mobilization rates differ by hazard zone" removed (v3.4 constant)
      · "Zhao et al. 2022" citation removed
      · Baseline v/c and LOS columns removed from route table
  - Methodology section replaced by Legal Authority section

Output: output/{city}/brief_v3_{lat}_{lon}_{units}u.html
"""

from __future__ import annotations

import datetime
from pathlib import Path

from .themes import _TIER_CSS_COLOR, _TIER_BG_COLOR, _TIER_BORDER_COLOR


# ---------------------------------------------------------------------------
# Public API
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

    # Read the plain-text audit trail from the sibling .txt file so it can be
    # embedded inline — the viewer.html link fails on file:// (no server to serve it).
    lat_str   = f"{project.location_lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str   = f"{project.location_lon:.4f}".replace(".", "_").replace("-", "n")
    units_str = project.dwelling_units
    audit_txt_path = output_path.parent / f"determination_{lat_str}_{lon_str}_{units_str}u.txt"
    audit_text = audit_txt_path.read_text(encoding="utf-8") if audit_txt_path.exists() else ""

    html = _render_brief_v3(project, audit, config, city_config, city_slug, audit_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def _render_brief_v3(project, audit: dict, config: dict, city_config: dict, city_slug: str = "berkeley", audit_text: str = "") -> str:
    city_name = city_config.get("city_name", city_config.get("name", city_config.get("city", "City")))
    determination = audit.get("determination", {})
    tier = determination.get("result", project.determination or "MINISTERIAL")
    tier_upper = tier.strip().upper()

    lat  = project.location_lat
    lon  = project.location_lon
    lat_str = f"{lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{lon:.4f}".replace(".", "_").replace("-", "n")
    units = project.dwelling_units
    proj_slug = (
        getattr(project, "project_name", "") or ""
    ).strip().upper().replace(" ", "-")[:20]
    case_num = (
        f"JOSH-{datetime.date.today().year}-{proj_slug}-{lat_str}-{lon_str}"
        if proj_slug else
        f"JOSH-{datetime.date.today().year}-{lat_str}-{lon_str}"
    )

    eval_date = audit.get("evaluation_date", str(datetime.date.today()))
    if "T" in eval_date:
        eval_date = eval_date.split("T")[0]

    scenarios = audit.get("scenarios", {})
    wildland  = scenarios.get("wildland_ab747", {})
    local5    = scenarios.get("sb79_transit", {})

    sections = [
        _build_print_css(),
        _build_screen_css_v3(tier_upper),
        "<body>",
        _build_header(city_name, case_num, eval_date, project),
        "<main>",
        _build_summary_stats(tier_upper, wildland, local5),
        _build_controlling_finding(tier_upper, wildland, project, config),
        _build_standards_analysis_v3(tier_upper, wildland, local5, config),
        _build_determination_box(tier_upper, determination, wildland, local5),
        _build_conditions_v3(tier_upper, wildland, local5),
        _build_legal_authority(project, audit, config, city_slug, audit_text),
        _build_appeal_rights(city_name),
        "</main>",
        _build_footer(),
        "</body>",
    ]
    return _wrap_html(city_name, case_num, "\n".join(sections))


# ---------------------------------------------------------------------------
# HTML skeleton
# ---------------------------------------------------------------------------

def _wrap_html(city_name: str, case_num: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Determination Letter — {case_num}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f8f9fa;
      color: #212529;
      font-size: 14px;
      line-height: 1.55;
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 28px 24px 48px;
    }}
    h2.section-label {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1.4px;
      text-transform: uppercase;
      color: #c0392b;
      margin: 32px 0 14px;
      padding-bottom: 8px;
      border-bottom: 2px solid #e9ecef;
    }}
  details summary::marker {{ display: none; }}
  details summary::-webkit-details-marker {{ display: none; }}
  </style>
</head>
{body}
</html>"""


# ---------------------------------------------------------------------------
# Print CSS
# ---------------------------------------------------------------------------

def _build_print_css() -> str:
    return """<style>
@media print {
  body { background: #fff !important; font-size: 12px; }
  main { padding: 0 !important; max-width: 100% !important; }

  .no-print { display: none !important; }

  .brief-header {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .stat-card, .standard-row, .determination-box, .conditions-box,
  .legal-authority-box, .appeal-box {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    break-inside: avoid;
  }
  .conditions-section { page-break-before: always; }

  @page {
    size: letter;
    margin: 0.75in 0.75in 0.85in;
    @bottom-center {
      content: "JOSH · California Stewardship Alliance · Determination Brief · Page " counter(page);
      font-size: 9px;
      color: #868e96;
    }
  }
}
</style>"""


# ---------------------------------------------------------------------------
# Screen CSS (v3 — adds controlling-badge, legal-table)
# ---------------------------------------------------------------------------

def _build_screen_css_v3(tier: str) -> str:
    tc = _TIER_CSS_COLOR.get(tier, "#555")
    return f"""<style>
.brief-header {{
  background: #1c4a6e;
  color: #fff;
  padding: 28px 36px;
}}
.stat-cards {{
  display: grid;
  grid-template-columns: 1fr 1fr 2fr;
  gap: 14px;
  margin-bottom: 8px;
}}
.stat-card {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 18px 16px;
  text-align: center;
}}
.stat-card .big-num {{
  font-size: 38px;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 6px;
}}
.stat-card .label {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: #868e96;
}}
.tier-pill {{
  display: inline-block;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: {tc};
  background: {_TIER_BG_COLOR.get(tier, "#f8f9fa")};
  border: 2px solid {_TIER_BORDER_COLOR.get(tier, "#dee2e6")};
  border-radius: 8px;
  padding: 10px 20px;
  margin-top: 4px;
  line-height: 1.2;
}}
.criteria-badge {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px; height: 26px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 800;
  flex-shrink: 0;
  color: #fff;
}}
.criteria-badge-wide {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px; height: 26px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 800;
  flex-shrink: 0;
  color: #fff;
  padding: 0 5px;
}}
.standard-row {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 14px 16px;
  margin-bottom: 8px;
}}
.standard-row-header {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.standard-title {{
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: #212529;
}}
.standard-sub {{
  font-size: 11px;
  color: #868e96;
  margin-top: 1px;
}}
.result-chip {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: 20px;
  white-space: nowrap;
}}
.chip-pass    {{ background: #e8f5e9; color: #27ae60; }}
.chip-fail    {{ background: #fdf2f2; color: #c0392b; }}
.chip-triggered {{ background: #fff3cd; color: #856404; }}
.chip-na      {{ background: #f1f3f5; color: #868e96; }}
.chip-scope   {{ background: #e7f1ff; color: #1a56db; }}
.chip-controlling {{
  background: #c0392b;
  color: #fff;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 20px;
  white-space: nowrap;
}}
.detail-block {{
  margin-top: 12px;
  padding: 12px 14px;
  background: #f8f9fa;
  border-radius: 5px;
  border-left: 3px solid #dee2e6;
  font-size: 12px;
}}
.route-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  margin-top: 8px;
}}
.route-table th {{
  text-align: left;
  font-weight: 700;
  color: #495057;
  padding: 4px 8px;
  border-bottom: 1px solid #dee2e6;
  background: #f1f3f5;
}}
.route-table td {{
  padding: 5px 8px;
  border-bottom: 1px solid #f1f3f5;
  color: #343a40;
}}
.route-table tr:last-child td {{ border-bottom: none; }}
.route-table tr.row-controlling {{ background: #fff8f8; }}
.determination-box {{
  border-left: 4px solid {tc};
  background: {_TIER_BG_COLOR.get(tier, "#f8f9fa")};
  border-radius: 0 6px 6px 0;
  padding: 18px 20px;
  margin-bottom: 12px;
}}
.determination-box .action-label {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: {tc};
  margin-bottom: 8px;
}}
.conditions-box {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 18px 20px;
  margin-bottom: 8px;
}}
.conditions-box ol {{
  margin: 10px 0 0;
  padding-left: 22px;
}}
.conditions-box li {{
  margin-bottom: 6px;
  font-size: 13px;
}}
.legal-authority-box {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 16px 20px;
  font-size: 12px;
  color: #495057;
}}
.legal-table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
  font-size: 11px;
}}
.legal-table th {{
  text-align: left;
  font-weight: 700;
  color: #343a40;
  padding: 5px 8px;
  border-bottom: 2px solid #dee2e6;
  background: #f8f9fa;
}}
.legal-table td {{
  padding: 5px 8px;
  border-bottom: 1px solid #f1f3f5;
  vertical-align: top;
}}
.legal-table tr.derived-row td {{
  background: #fffbec;
  font-weight: 600;
  border-bottom: 1px solid #f1c40f44;
}}
.legal-num-badge {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px; height: 20px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 800;
  color: #fff;
  background: #495057;
  flex-shrink: 0;
}}
.legal-num-badge.derived {{ background: #e67e22; }}
.appeal-box {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 16px 20px;
  font-size: 13px;
  color: #495057;
}}
.brief-footer {{
  text-align: center;
  font-size: 10px;
  color: #adb5bd;
  letter-spacing: 0.8px;
  padding: 18px 0 8px;
  border-top: 1px solid #dee2e6;
  margin-top: 36px;
}}
</style>"""


# ---------------------------------------------------------------------------
# Header (unchanged from v1)
# ---------------------------------------------------------------------------

def _build_header(city_name: str, case_num: str, eval_date: str, project) -> str:
    addr = getattr(project, "address", "") or ""
    apn  = getattr(project, "apn", "")  or ""
    proj_name = getattr(project, "project_name", "") or ""
    lat  = project.location_lat
    lon  = project.location_lon
    units = project.dwelling_units

    proj_line = proj_name if proj_name else f"{units}-unit project at ({lat:.4f}, {lon:.4f})"
    if addr:
        proj_line = f"{proj_name + ' — ' if proj_name else ''}{addr}"

    apn_line = f"APN: {apn} &nbsp;&middot;&nbsp;" if apn else ""

    return f"""<header class="brief-header no-print-border">
  <div style="max-width:860px; margin:0 auto;">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:24px; flex-wrap:wrap; margin-bottom:18px;">
      <div>
        <div style="font-size:10px; letter-spacing:2px; text-transform:uppercase; color:#a8c8e8; font-weight:600; margin-bottom:6px;">
          California Stewardship Alliance
        </div>
        <div style="font-size:24px; font-weight:800; color:#fff; line-height:1.2; margin-bottom:4px;">
          City of {city_name} &mdash; Planning Department
        </div>
        <div style="font-size:13px; color:#c8dff0; font-weight:500;">
          Fire Evacuation Capacity Determination &nbsp;&middot;&nbsp; AB 747 &nbsp;&middot;&nbsp; Gov. Code &sect;65302.15
        </div>
      </div>
      <div style="text-align:right; font-size:11px; color:#a8c8e8; line-height:1.8; flex-shrink:0;">
        <div style="font-weight:700; color:#fff; font-size:12px;">{case_num}</div>
        <div>{apn_line}Issued: {eval_date}</div>
        <div>{units} dwelling units</div>
      </div>
    </div>
    <div style="border-top:1px solid rgba(255,255,255,0.18); padding-top:14px;">
      <div style="font-size:10px; letter-spacing:1.5px; text-transform:uppercase; color:#a8c8e8; font-weight:600; margin-bottom:4px;">
        Project
      </div>
      <div style="font-size:20px; font-weight:800; color:#fff; line-height:1.2;">
        {proj_line}
      </div>
      <div style="font-size:15px; font-weight:700; color:#c8dff0; margin-top:6px; letter-spacing:0.3px;">
        {units} dwelling unit{"s" if units != 1 else ""}
      </div>
    </div>
  </div>
</header>"""


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

def _build_summary_stats(tier: str, wildland: dict, local5: dict) -> str:
    tier_label = {
        "DISCRETIONARY":           "DISCRETIONARY<br>REVIEW REQUIRED",
        "MINISTERIAL WITH STANDARD CONDITIONS": "MINISTERIAL W/<br>STANDARD CONDITIONS",
        "MINISTERIAL":             "MINISTERIAL<br>APPROVAL ELIGIBLE",
    }.get(tier, tier)

    if tier == "MINISTERIAL":
        # No ΔT analysis was run — single full-width tier card
        return f"""<div class="stat-cards" style="margin-top:20px; grid-template-columns:1fr;">
  <div class="stat-card" style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:24px 16px;">
    <div class="tier-pill">{tier_label}</div>
  </div>
</div>"""

    # DISCRETIONARY or MINISTERIAL WITH STANDARD CONDITIONS — show ΔT metrics
    s5        = wildland.get("steps", {}).get("step5_delta_t", {})
    max_dt    = s5.get("max_delta_t_minutes", 0.0)
    threshold = s5.get("threshold_minutes", 6.0)

    dt_color  = "#c0392b" if tier == "DISCRETIONARY" else "#27ae60"

    return f"""<div class="stat-cards" style="margin-top:20px;">

  <div class="stat-card">
    <div class="big-num" style="color:{dt_color};">{max_dt:.1f}</div>
    <div class="label">Max &Delta;T (min)</div>
  </div>

  <div class="stat-card">
    <div class="big-num" style="color:#495057;">{threshold:.2f}</div>
    <div class="label">Threshold (min)</div>
  </div>

  <div class="stat-card" style="display:flex; flex-direction:column; align-items:center; justify-content:center;">
    <div class="tier-pill">{tier_label}</div>
  </div>

</div>"""


# ---------------------------------------------------------------------------
# Controlling finding callout (unchanged from v1)
# ---------------------------------------------------------------------------

def _build_controlling_finding(tier: str, wildland: dict, project, config: dict) -> str:
    tc  = _TIER_CSS_COLOR.get(tier, "#555")
    bg  = _TIER_BG_COLOR.get(tier, "#f8f9fa")

    s5           = wildland.get("steps", {}).get("step5_delta_t", {})
    s2           = wildland.get("steps", {}).get("step2_scale", {})
    path_results = s5.get("path_results", [])
    threshold    = s5.get("threshold_minutes", 6.0)
    safe_window  = s5.get("safe_egress_window_minutes", 120.0)
    max_share    = s5.get("max_project_share", 0.05)
    hazard_zone  = s5.get("hazard_zone", "non_fhsz")
    ut           = config.get("unit_threshold", 15)

    _zone_labels = {
        "vhfhsz": "Very High FHSZ", "high_fhsz": "High FHSZ",
        "moderate_fhsz": "Moderate FHSZ", "non_fhsz": "Non-FHSZ",
    }
    hz_label = _zone_labels.get(hazard_zone, hazard_zone)

    if tier == "MINISTERIAL":
        units = s2.get("dwelling_units", project.dwelling_units)
        text  = (
            f"<strong>Size threshold not met.</strong> "
            f"The project ({units} units) is below the {ut}-unit threshold. "
            f"Evacuation clearance analysis is not required. Approval is ministerial."
        )
    elif tier == "DISCRETIONARY":
        flagged = [r for r in path_results if r.get("flagged")]
        if flagged:
            worst  = max(flagged, key=lambda r: r.get("delta_t_minutes", 0))
            nm     = worst.get("bottleneck_name") or worst.get("bottleneck_osmid", "bottleneck segment")
            dt     = worst.get("delta_t_minutes", 0)
            thr    = worst.get("threshold_minutes", threshold)
            ratio  = dt / max(thr, 0.001)
            excess = dt - thr
            text   = (
                f"<strong>Controlling finding:</strong> {nm} adds <strong>{dt:.2f} min</strong> "
                f"of marginal evacuation clearance time — <strong>{ratio:.1f}&times;</strong> the "
                f"{thr:.2f}-min threshold ({safe_window:.0f} min &times; {max_share*100:.0f}%, "
                f"{hz_label}, NIST TN 2135). Exceeds threshold by <strong>{excess:.2f} min</strong>."
            )
        else:
            text = "<strong>ΔT threshold exceeded</strong> on one or more serving evacuation paths."
    else:  # MINISTERIAL WITH STANDARD CONDITIONS
        if path_results:
            worst     = max(path_results, key=lambda r: r.get("delta_t_minutes", 0))
            nm        = worst.get("bottleneck_name") or worst.get("bottleneck_osmid", "bottleneck segment")
            dt        = worst.get("delta_t_minutes", 0)
            thr       = worst.get("threshold_minutes", threshold)
            remaining = thr - dt
            pct_used  = (dt / max(thr, 0.001)) * 100
            text      = (
                f"<strong>All serving paths are within the ΔT threshold.</strong> "
                f"Most constrained path: {nm} at {dt:.2f} min "
                f"({pct_used:.0f}% of the {thr:.2f}-min limit, <strong>{remaining:.2f} min remaining</strong>)."
            )
        else:
            text = "<strong>All serving paths are within the ΔT threshold.</strong>"

    return (
        f'<div style="border-left:4px solid {tc}; background:{bg}; '
        f'border-radius:0 6px 6px 0; padding:12px 16px; margin:16px 0 0; '
        f'font-size:13px; color:#212529; line-height:1.6;">'
        f'<span style="font-size:10px; font-weight:700; letter-spacing:1.2px; '
        f'text-transform:uppercase; color:{tc}; display:block; margin-bottom:5px;">'
        f'Controlling Finding</span>'
        f'{text}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Analysis sections v3 — Applicability → Site Parameters → Clearance Test → SB79
# ---------------------------------------------------------------------------

def _build_standards_analysis_v3(tier: str, wildland: dict, local5: dict, config: dict) -> str:
    w_steps  = wildland.get("steps", {})
    l5_steps = local5.get("steps", {})
    l5_tier  = local5.get("tier", "NOT_APPLICABLE")
    l5_applicable = l5_tier != "NOT_APPLICABLE"

    unit_threshold = config.get("unit_threshold", 15)

    rows = []

    # -----------------------------------------------------------------------
    # Applicability Threshold (formerly Standard 1)
    # -----------------------------------------------------------------------
    s2      = w_steps.get("step2_scale", {})
    s1_result   = s2.get("result", False)
    du          = s2.get("dwelling_units", 0)
    if not s1_result:
        s1_chip     = "BELOW THRESHOLD"
        s1_chip_cls = "chip-na"
    elif tier == "MINISTERIAL WITH STANDARD CONDITIONS":
        s1_chip     = "IN SCOPE — CONDITIONS APPLY"
        s1_chip_cls = "chip-scope"
    else:
        s1_chip     = "IN SCOPE"
        s1_chip_cls = "chip-scope"

    if s1_result:
        cond_note = (
            " Since this project meets the applicability threshold, the evacuation clearance"
            " analysis (Criteria B and C) applies. If all criteria are met, pre-adopted"
            " standard conditions apply automatically — see <em>Required Next Steps</em>."
            if tier == "MINISTERIAL WITH STANDARD CONDITIONS" else ""
        )
        s1_detail = f"""<div class="detail-block">
          {du} dwelling units proposed &nbsp;&ge;&nbsp; {unit_threshold}-unit threshold.
          Project size threshold: {unit_threshold} dwelling units
          (ITE Trip Generation de minimis; SB 330, Gov. Code &sect;65913.4).{cond_note}
        </div>"""
    else:
        s1_detail = f"""<div class="detail-block">
          {du} dwelling units proposed &nbsp;&lt;&nbsp; {unit_threshold}-unit threshold —
          project is below the ITE de minimis for measurable evacuation impact.
          Evacuation clearance analysis is not required.
        </div>"""

    rows.append(_analysis_row("A", "#1a56db" if s1_result else "#6c757d",
        "Applicability Threshold",
        f"Minimum {unit_threshold} dwelling units — integer comparison, no discretion",
        s1_chip, s1_chip_cls, s1_detail))

    # -----------------------------------------------------------------------
    # Site Parameters (formerly Standard 3) — FHSZ lookup sets inputs to
    # clearance analysis; not a determination step in itself
    # -----------------------------------------------------------------------
    s1_applicability = w_steps.get("step1_applicability", {})
    fz_result   = s1_applicability.get("std3_fhsz_flagged", False)
    fz_desc     = s1_applicability.get("std3_zone_desc", "Not in FHSZ")
    fz_level    = s1_applicability.get("std3_zone_level", 0)
    hazard_zone = s1_applicability.get("std3_hazard_zone", "non_fhsz")
    mob_rate    = s1_applicability.get("std3_mobilization_rate", 0.90)

    # Degradation factor lookup (matches config hazard_degradation)
    _deg_factors = {
        "vhfhsz": 0.35, "high_fhsz": 0.50, "moderate_fhsz": 0.75, "non_fhsz": 1.00
    }
    deg_factor = _deg_factors.get(hazard_zone, 1.00)
    _zone_labels = {
        "vhfhsz": "Very High FHSZ", "high_fhsz": "High FHSZ",
        "moderate_fhsz": "Moderate FHSZ", "non_fhsz": "Non-FHSZ",
    }
    hz_label = _zone_labels.get(hazard_zone, hazard_zone)

    if not s1_result:
        s3_chip = "PENDING"
        s3_chip_cls = "chip-na"
        s3_badge_color = "#adb5bd"
        s3_detail = ""
    elif fz_result:
        s3_chip = hz_label.upper()
        s3_chip_cls = "chip-triggered"
        s3_badge_color = "#c0392b"
        s3_detail = f"""<div class="detail-block" style="border-left-color:#c0392b;">
          <strong>Project site:</strong> {fz_desc} (source: CAL FIRE OSFM)<br>
          <strong>CAL FIRE HAZ_CLASS:</strong> {fz_level} —
          <code>{hazard_zone}</code>; road capacity reduced to {deg_factor:.2f}&times; HCM base
          (HCM Exhibit 10-15/10-17 composite + NIST Camp Fire validation).<br>
          <strong>ΔT threshold:</strong> reduced proportionally (shorter safe egress window
          applies; see Clearance Analysis below).<br>
          <strong>Mobilization rate:</strong> {mob_rate:.2f} (NFPA 101 constant — unaffected by
          FHSZ zone; ~10% zero-vehicle HH per Census ACS B25044).
        </div>"""
    else:
        s3_chip = "NON-FHSZ"
        s3_chip_cls = "chip-na"
        s3_badge_color = "#6c757d"
        s3_detail = f"""<div class="detail-block">
          Project site is not within a designated fire hazard severity zone
          (<strong>CAL FIRE HAZ_CLASS: 0</strong>, <code>non_fhsz</code>).
          No road capacity degradation applied (factor = 1.00&times;).
          Standard 120-min safe egress window applies.<br>
          <strong>Mobilization rate:</strong> {mob_rate:.2f} (NFPA 101 constant).
        </div>"""

    rows.append(_analysis_row("B", s3_badge_color,
        "Site Parameters",
        "CAL FIRE FHSZ classification — sets road capacity degradation factor and ΔT threshold for clearance analysis",
        s3_chip, s3_chip_cls, s3_detail))

    # -----------------------------------------------------------------------
    # Evacuation Clearance Analysis (formerly Standards 2+4 merged)
    # This is the operative determination step.
    # -----------------------------------------------------------------------
    s3_routes_step = w_steps.get("step3_routes", {})
    s2_result = s3_routes_step.get("triggers_standard", False)
    n_routes  = s3_routes_step.get("serving_route_count", 0)
    radius    = s3_routes_step.get("radius_miles", 0.5)

    s5           = w_steps.get("step5_delta_t", {})
    s4_triggered = s5.get("triggered", False)
    path_results = s5.get("path_results", [])
    proj_vph     = s5.get("project_vehicles", 0)
    egress_min   = s5.get("egress_minutes", 0)
    max_dt       = s5.get("max_delta_t_minutes", 0.0)
    max_threshold = s5.get("threshold_minutes", 6.0)
    safe_window   = s5.get("safe_egress_window_minutes", 120.0)
    max_share_v   = s5.get("max_project_share", 0.05)

    # Chip reflects ΔT verdict
    if not s1_result:
        s24_chip = "NOT REQUIRED"
        s24_chip_cls = "chip-na"
        s24_badge_color = "#adb5bd"
    elif s4_triggered:
        s24_chip = "EXCEEDS THRESHOLD"
        s24_chip_cls = "chip-fail"
        s24_badge_color = "#c0392b"
    elif s2_result:
        s24_chip = "WITHIN THRESHOLD"
        s24_chip_cls = "chip-pass"
        s24_badge_color = "#27ae60"
    else:
        s24_chip = "NO ROUTES"
        s24_chip_cls = "chip-na"
        s24_badge_color = "#6c757d"

    # Build the merged route+ΔT table
    merged_table_html = ""
    if s1_result:
        # Find controlling path (highest ΔT)
        controlling_pid = None
        if path_results:
            worst_path = max(path_results, key=lambda r: r.get("delta_t_minutes", 0))
            controlling_pid = worst_path.get("path_id")

        # Threshold derivation mini-block
        derivation_block = (
            f"<div style='font-size:11px; background:#f0f4f8; border:1px solid #ccd6e0; "
            f"border-radius:4px; padding:7px 10px; margin-bottom:8px; line-height:1.8;'>"
            f"<strong>ΔT threshold:</strong> "
            f"{safe_window:.0f} min safe egress window (NIST TN 2135, {hz_label}) "
            f"&times; {max_share_v*100:.0f}% max project share "
            f"= <strong>{max_threshold:.2f} min</strong></div>"
        )

        egress_note = (
            f"<span style='color:#6f42c1;font-weight:600'>"
            f"Building egress: +{egress_min:.1f} min (NFPA 101/IBC, stories &ge; 4)</span> &nbsp;|&nbsp; "
            if egress_min > 0 else ""
        )

        if path_results:
            # Show flagged paths + near-threshold paths
            flagged_paths = [r for r in path_results if r.get("flagged")]
            near_paths = [r for r in path_results
                          if not r.get("flagged")
                          and r.get("delta_t_minutes", 0) > max_threshold * 0.70][:3]
            display_paths = flagged_paths + near_paths
            n_omitted = len(path_results) - len(display_paths)

            _rt_abbr = {"freeway": "Fwy", "multilane": "Multi-lane", "two_lane": "Two-lane"}

            table_rows = ""
            for r in display_paths:
                pid     = r.get("path_id", "—")
                bname   = r.get("bottleneck_name") or r.get("bottleneck_osmid", "—")
                eff_cap = r.get("bottleneck_effective_capacity_vph", 0)
                dt      = r.get("delta_t_minutes", 0)
                thr     = r.get("threshold_minutes", max_threshold)
                flg     = r.get("flagged", False)
                margin  = dt - thr
                is_controlling = (pid == controlling_pid)

                # HCM classification fields for bottleneck subtitle
                b_rt    = r.get("bottleneck_road_type", "")
                b_spd   = r.get("bottleneck_speed_limit", 0)
                b_lns   = r.get("bottleneck_lane_count", 0)
                b_hcm   = r.get("bottleneck_hcm_capacity_vph", 0)
                b_deg   = r.get("bottleneck_hazard_degradation", 1.0)
                rt_parts = [_rt_abbr.get(b_rt, b_rt)] if b_rt else []
                if b_spd: rt_parts.append(f"{b_spd}\u202fmph")
                if b_lns: rt_parts.append(f"{b_lns}\u202fln")
                hcm_str = (
                    f"HCM\u202f{b_hcm:,.0f}\u202f\u00d7\u202f{b_deg:.2f}\u202f=\u202f{eff_cap:,.0f}\u202fvph"
                    if b_hcm else ""
                )
                subtitle_parts = [" \u00b7 ".join(rt_parts)]
                if hcm_str:
                    subtitle_parts.append(hcm_str)
                bn_subtitle = "  \u2192  ".join(p for p in subtitle_parts if p)
                bname_cell = (
                    f"{bname}"
                    f"<br><span style='font-size:9px;color:#868e96;font-weight:normal'>"
                    f"{bn_subtitle}</span>"
                ) if bn_subtitle else bname

                dt_color     = "#c0392b" if flg else "#212529"
                margin_color = "#c0392b" if flg else "#27ae60"
                margin_str   = f"+{margin:.2f}" if flg else f"−{abs(margin):.2f}"

                if is_controlling and flg:
                    status_html = '<span class="chip-controlling">CONTROLLING</span>'
                elif flg:
                    status_html = "<span style='color:#c0392b;font-weight:700'>&#9888; EXCEEDS</span>"
                elif is_controlling:
                    status_html = '<span class="chip-controlling" style="background:#495057;">WORST</span>'
                else:
                    status_html = "<span style='color:#27ae60'>&#10003; within</span>"

                row_class = "row-controlling" if is_controlling else ""
                table_rows += (
                    f"<tr class='{row_class}'>"
                    f"<td style='font-size:10px;color:#868e96'>{pid}</td>"
                    f"<td>{bname_cell}</td>"
                    f"<td style='font-size:10px'>{hz_label}</td>"
                    f"<td style='font-weight:600'>{eff_cap:,.0f}</td>"
                    f"<td style='font-weight:700;color:{dt_color}'>{dt:.2f}</td>"
                    f"<td style='color:#868e96'>{thr:.2f}</td>"
                    f"<td style='font-weight:600;color:{margin_color}'>{margin_str}</td>"
                    f"<td>{status_html}</td>"
                    f"</tr>"
                )

            if n_omitted > 0:
                table_rows += (
                    f"<tr><td colspan='8' style='color:#868e96;font-style:italic'>"
                    f"{n_omitted} additional path(s) within threshold — omitted for brevity. "
                    f"See full audit trail.</td></tr>"
                )

            merged_table_html = f"""
{derivation_block}
<div style='font-size:11px;color:#6c757d;margin-bottom:4px;'>
  {egress_note}Project vehicles: <strong>{proj_vph:.0f}</strong>
  (units &times; 2.5 vpu &times; 0.90 NFPA 101 constant).
  Effective capacity = HCM raw &times; {deg_factor:.2f} hazard degradation.
</div>
<table class='route-table'>
  <thead><tr>
    <th>Path</th><th>Bottleneck Segment</th><th>FHSZ Zone</th>
    <th>Eff. Cap (vph)</th><th>&#916;T (min)</th><th>Threshold</th>
    <th>Margin</th><th>Result</th>
  </tr></thead>
  <tbody>{table_rows}</tbody>
</table>"""
        else:
            # No path results — show route count only
            merged_table_html = f"""
{derivation_block}
<div style='color:#6c757d;'>
  {n_routes} evacuation route segment{"s" if n_routes != 1 else ""} identified
  within {radius} miles. No path ΔT results available.
</div>"""

    s24_detail = f"""<div class="detail-block" style="border-left-color:{'#c0392b' if s4_triggered else ('#dee2e6' if not s1_result else '#27ae60')};">
      {f"{n_routes} serving route segment{'s' if n_routes != 1 else ''} within {radius} mi (OSM evacuation route network)." if s1_result else ""}
      {merged_table_html}
    </div>""" if s1_result else ""

    rows.append(_analysis_row_wide("C", s24_badge_color,
        "Evacuation Clearance Analysis",
        "Route identification (0.5 mi radius) + per-path ΔT test — this is the operative determination step",
        s24_chip, s24_chip_cls, s24_detail))

    # -----------------------------------------------------------------------
    # SB 79 Disclosure — informational strip, no badge letter
    # -----------------------------------------------------------------------
    sb79_chip = "INFORMATIONAL" if s1_result else "NOT REQUIRED"
    rows.append(_disclosure_row(
        "SB 79 Transit Proximity",
        "Transit stop within 0.5 mi — does not affect this determination",
        sb79_chip))

    return f"""<h2 class="section-label">Analysis</h2>
{"".join(rows)}"""


def _analysis_row(letter: str, badge_color: str, title: str, subtitle: str,
                  chip_text: str, chip_cls: str, detail_html: str) -> str:
    return f"""<div class="standard-row">
  <div class="standard-row-header">
    <span class="criteria-badge" style="background:{badge_color};">{letter}</span>
    <div style="flex:1;">
      <div class="standard-title">{title}</div>
      <div class="standard-sub">{subtitle}</div>
    </div>
    <span class="result-chip {chip_cls}">{chip_text}</span>
  </div>
  {detail_html}
</div>"""


def _analysis_row_wide(letter: str, badge_color: str, title: str, subtitle: str,
                       chip_text: str, chip_cls: str, detail_html: str) -> str:
    """Like _analysis_row but uses a wider badge (letter C is fine, kept for layout consistency)."""
    return f"""<div class="standard-row">
  <div class="standard-row-header">
    <span class="criteria-badge" style="background:{badge_color};">{letter}</span>
    <div style="flex:1;">
      <div class="standard-title">{title}</div>
      <div class="standard-sub">{subtitle}</div>
    </div>
    <span class="result-chip {chip_cls}">{chip_text}</span>
  </div>
  {detail_html}
</div>"""


def _disclosure_row(title: str, subtitle: str, chip_text: str) -> str:
    """Informational disclosure strip — no badge letter, always gray."""
    return f"""<div class="standard-row" style="border-left:3px solid #dee2e6; background:#fafafa;">
  <div class="standard-row-header">
    <div style="flex:1;">
      <div class="standard-title" style="color:#6c757d;">{title}</div>
      <div class="standard-sub">{subtitle}</div>
    </div>
    <span class="result-chip chip-na">{chip_text}</span>
  </div>
</div>"""


# ---------------------------------------------------------------------------
# Determination box (unchanged from v1)
# ---------------------------------------------------------------------------

def _build_determination_box(tier: str, determination: dict,
                              wildland: dict, local5: dict) -> str:
    tc = _TIER_CSS_COLOR.get(tier, "#555")
    reason = determination.get("reason", "")

    bases = []
    for sc in [wildland, local5]:
        if sc.get("triggered") or sc.get("tier") not in ("MINISTERIAL", "NOT_APPLICABLE", None):
            lb = sc.get("legal_basis", "")
            if lb and lb not in bases:
                bases.append(lb)

    legal_html = ""
    if bases:
        legal_html = "<div style='margin-top:12px; font-size:11px; color:#495057;'>" \
            "<strong>Legal authority:</strong> " + " &nbsp;&bull;&nbsp; ".join(bases) + "</div>"

    sc_tiers = determination.get("scenario_tiers", {})
    sc_rows = ""
    for sc_name, sc_tier in sc_tiers.items():
        label = {
            "wildland_ab747":    "Wildland Evacuation Analysis",
            "sb79_transit":      "SB 79 Transit Proximity (Informational)",
        }.get(sc_name, sc_name)
        color = _TIER_CSS_COLOR.get(sc_tier.upper(), "#555")
        sc_rows += f"<div style='font-size:11px;margin-bottom:3px;'>{label}: <strong style='color:{color}'>{sc_tier}</strong></div>"

    if sc_rows:
        sc_rows = f"<div style='margin-top:10px; padding-top:10px; border-top:1px solid {_TIER_BORDER_COLOR.get(tier, '#dee2e6')};'>{sc_rows}</div>"

    return f"""<h2 class="section-label">Determination</h2>
<div class="determination-box">
  <div class="action-label">DETERMINATION &nbsp;&rarr;</div>
  <div style="font-size:13px; color:#212529; line-height:1.6;">{reason}</div>
  {sc_rows}
  {legal_html}
</div>"""


# ---------------------------------------------------------------------------
# Conditions (v3 — fixes "JOSH v3.1" and "Zhao et al." references)
# ---------------------------------------------------------------------------

def _build_conditions_v3(tier: str, wildland: dict, local5: dict) -> str:
    w_steps = wildland.get("steps", {})
    fz_level = w_steps.get("step1_applicability", {}).get(
        "fire_zone_severity_modifier", {}).get("zone_level", 0)

    if tier == "MINISTERIAL":
        body = _conditions_ministerial()
    elif tier == "MINISTERIAL WITH STANDARD CONDITIONS":
        body = _conditions_conditional(fz_level)
    else:
        body = _conditions_discretionary_v3(wildland, local5)

    return f"""<h2 class="section-label conditions-section">Required Next Steps</h2>
<div class="conditions-box">{body}</div>"""


def _conditions_ministerial() -> str:
    return """<p style="margin:0 0 10px;">
      This project <strong>qualifies for ministerial approval</strong> under Government Code §65589.4
      and the adopted AB 747 objective standards. No discretionary review is required. No public
      hearing is required.
    </p>
    <ol>
      <li>Submit building permit application to the Building &amp; Safety Division per normal procedures.</li>
      <li>Standard fire and life safety plan check applies (Health &amp; Safety Code §13108).</li>
      <li>No CEQA review is required for ministerial approvals (Pub. Resources Code §21080(b)(1)).</li>
      <li>Applicant shall not reduce the width or lane count of any identified evacuation route during construction.</li>
    </ol>"""


def _conditions_conditional(fz_level: int) -> str:
    fhsz_conditions = ""
    if fz_level >= 2:
        fhsz_conditions = """
      <li><strong>Defensible space compliance — PRC §4291.</strong>
        The project site is located within a Very High or High Fire Hazard Severity Zone.
        Prior to permit issuance, the applicant shall submit documentation to the Fire Marshal
        confirming that all structures will maintain the 100-foot defensible space clearance
        zones required under Public Resources Code §4291.</li>
      <li><strong>WUI building standards compliance — CBC Chapter 7A / SFM Chapter 12-7A.</strong>
        All new structures shall comply with wildland-urban interface fire area construction
        requirements applicable to the project's FHSZ classification, including ignition-resistant
        building materials, ember-resistant vents, and deck/eave construction standards.</li>"""

    return f"""<p style="margin:0 0 12px;">
      This project is <strong>approved ministerially</strong>. The following pre-adopted, objective
      conditions apply automatically by operation of law and local ordinance. No discretionary review
      or public hearing is required. (Gov. Code §65589.4)
    </p>
    <ol>{fhsz_conditions}
      <li><strong>Evacuation infrastructure impact fee — AB 1600 (Gov. Code §66000 et seq.).</strong>
        If the city has adopted an evacuation infrastructure impact fee schedule pursuant to the
        Mitigation Fee Act (AB 1600), the applicable fee is due at building permit issuance.</li>
      <li><strong>Emergency vehicle access — local fire code (IFC §503).</strong>
        The project shall maintain minimum fire apparatus access road width, vertical clearance,
        and turning radii as required by the adopted local fire code throughout construction
        and operation.</li>
    </ol>"""


def _conditions_discretionary_v3(wildland: dict, local5: dict) -> str:
    """Fixed v3: JOSH v3.4; NFPA 101 design basis mobilization rate."""
    s5           = wildland.get("steps", {}).get("step5_delta_t", {})
    path_results = s5.get("path_results", [])
    max_dt       = s5.get("max_delta_t_minutes", 0.0)
    threshold    = s5.get("threshold_minutes", 6.0)
    hazard_zone  = s5.get("hazard_zone", "non_fhsz")
    flagged_paths = [r for r in path_results if r.get("flagged")]

    path_note = ""
    if flagged_paths:
        parts = []
        for r in flagged_paths[:3]:
            pid   = r.get("path_id", "—")
            bname = r.get("bottleneck_name") or r.get("bottleneck_osmid", "—")
            dt    = r.get("delta_t_minutes", 0)
            thr   = r.get("threshold_minutes", threshold)
            parts.append(f"Path {pid} — bottleneck: {bname} (ΔT {dt:.1f} min vs {thr:.2f}-min threshold)")
        route_list = "; ".join(parts)
        n_more = len(flagged_paths) - len(parts)
        if n_more > 0:
            route_list += f"; and {n_more} more paths"
        path_note = (
            f"<p style='margin:10px 0 0; font-size:12px; color:#495057;'>"
            f"<strong>ΔT exceedance identified on {len(flagged_paths)} path(s):</strong> "
            f"{route_list}</p>"
        )

    return f"""<p style="margin:0 0 10px;">
      This project <strong>requires discretionary review</strong> under AB 747
      (Gov. Code §65302.15). The objective standards analysis has determined that this project
      would add more than {threshold:.2f} minutes of marginal evacuation clearance time (ΔT)
      on one or more serving evacuation paths in hazard zone <code>{hazard_zone}</code>
      (maximum ΔT: {max_dt:.2f} min vs. {threshold:.2f}-min threshold).
    </p>
    {path_note}
    <ol>
      <li><strong>Environmental Impact Report (EIR)</strong> required under CEQA
      (Pub. Resources Code §21100) — evacuation clearance time impact must be analyzed
      as a significant transportation impact.</li>
      <li><strong>Evacuation Clearance Time Analysis:</strong> Applicant shall commission
      a study conforming to the JOSH v3.4 ΔT methodology (AB 747 / Gov. Code §65302.15),
      analyzing marginal evacuation clearance time on all serving paths within 0.5 miles,
      using NFPA 101 design basis mobilization rate (0.90 constant) and HCM 2022
      hazard-degraded capacity factors.</li>
      <li><strong>Public Hearing</strong> before the Planning Commission is required prior to any
      project approval (Gov. Code §65905).</li>
      <li><strong>Fire Department Review:</strong> Submit project plans to the Fire Marshal for
      review of evacuation access, egress widths, and compliance with Fire Code §503.</li>
      <li><strong>Mitigation Measures or Project Redesign:</strong> Applicant must demonstrate
      — through the clearance time analysis — either (a) that mitigation measures reduce ΔT
      below {threshold:.2f} minutes on all serving paths, or (b) that the project scope
      (units, stories, or both) is reduced to fall within the ΔT threshold, to qualify for
      ministerial review.</li>
      <li>Approval is not ministerial until the ΔT exceedance is mitigated or the project
      is redesigned to fall within the ΔT threshold on all serving evacuation paths.</li>
    </ol>"""


# ---------------------------------------------------------------------------
# Legal Authority (replaces Methodology section)
# ---------------------------------------------------------------------------

def _build_audit_trail_block(audit_file: str, audit_text: str) -> str:
    """
    Render the plain-text audit trail inline as a collapsible <details> block.
    Replaces the old viewer.html link which fails on file:// (no server to serve it).
    """
    import html as _html
    if not audit_text:
        return (
            f'<p style="margin:0; font-size:11px; color:#adb5bd;">Audit trail not available: '
            f'<code>{audit_file}</code></p>'
        )
    escaped = _html.escape(audit_text)
    return f"""<details class="no-print" style="margin-top:4px;">
  <summary style="cursor:pointer; font-size:11px; color:#1a56db; font-family:monospace;
                  background:#f1f3f5; padding:3px 8px; border-radius:3px; display:inline-block;
                  user-select:none; list-style:none;">
    &#9654; {audit_file}
  </summary>
  <pre style="margin:8px 0 0; padding:10px 12px; background:#f8f9fa; border:1px solid #dee2e6;
              border-radius:4px; font-size:10px; line-height:1.5; overflow-x:auto;
              white-space:pre-wrap; word-break:break-word; color:#212529;">{escaped}</pre>
</details>"""


def _build_legal_authority(project, audit: dict, config: dict, city_slug: str = "berkeley", audit_text: str = "") -> str:
    """Numbered citation table tracing every value in the determination to a published source."""
    scenarios = audit.get("scenarios", {})
    wildland  = scenarios.get("wildland_ab747", {})
    w_steps   = wildland.get("steps", {})
    s1_app    = w_steps.get("step1_applicability", {})
    s5        = w_steps.get("step5_delta_t", {})

    # Parameters
    ut         = config.get("unit_threshold", 15)
    vpu        = config.get("vehicles_per_unit", 2.5)
    mob_rate   = config.get("mobilization_rate", 0.90)
    haz_deg    = config.get("hazard_degradation", {})
    safe_egr   = config.get("safe_egress_window", {})
    max_share  = config.get("max_project_share", 0.05)
    egress_cfg = config.get("egress_penalty", {})

    hazard_zone   = s5.get("hazard_zone", s1_app.get("std3_hazard_zone", "non_fhsz"))
    fz_desc       = s1_app.get("std3_zone_desc", "Not in FHSZ")
    safe_window   = s5.get("safe_egress_window_minutes", safe_egr.get(hazard_zone, 120))
    threshold     = s5.get("threshold_minutes", safe_window * max_share)
    max_dt        = s5.get("max_delta_t_minutes", 0.0)
    proj_vph      = s5.get("project_vehicles", 0)
    egress_min    = s5.get("egress_minutes", 0)

    deg_factor    = haz_deg.get(hazard_zone, 1.00)

    # Controlling path bottleneck capacity
    path_results   = s5.get("path_results", [])
    eff_cap_ctrl   = 0
    ctrl_road_name = "—"
    ctrl_road_type = ""
    ctrl_speed     = 0
    ctrl_lanes     = 0
    hcm_raw_ctrl   = 0
    if path_results:
        worst = max(path_results, key=lambda r: r.get("delta_t_minutes", 0))
        eff_cap_ctrl   = worst.get("bottleneck_effective_capacity_vph", 0)
        ctrl_road_name = worst.get("bottleneck_name") or worst.get("bottleneck_osmid", "—")
        # Use stored HCM inputs — no back-derivation needed
        hcm_raw_ctrl   = int(worst.get("bottleneck_hcm_capacity_vph", 0))
        ctrl_road_type = worst.get("bottleneck_road_type", "")
        ctrl_speed     = worst.get("bottleneck_speed_limit", 0)
        ctrl_lanes     = worst.get("bottleneck_lane_count", 0)

    _rt_labels_la = {"freeway": "Freeway", "multilane": "Multi-lane", "two_lane": "Two-lane"}
    ctrl_rt_label = _rt_labels_la.get(ctrl_road_type, ctrl_road_type)
    ctrl_hcm_detail_parts = [ctrl_rt_label] if ctrl_rt_label else []
    if ctrl_speed: ctrl_hcm_detail_parts.append(f"{ctrl_speed} mph")
    if ctrl_lanes: ctrl_hcm_detail_parts.append(f"{ctrl_lanes} lanes")
    ctrl_hcm_detail = ", ".join(ctrl_hcm_detail_parts)

    egr_thr = egress_cfg.get("threshold_stories", 4)
    egr_mps = egress_cfg.get("minutes_per_story", 1.5)
    egr_max = egress_cfg.get("max_minutes", 12)

    _zone_labels = {
        "vhfhsz": "Very High FHSZ", "high_fhsz": "High FHSZ",
        "moderate_fhsz": "Moderate FHSZ", "non_fhsz": "Non-FHSZ",
    }
    hz_label = _zone_labels.get(hazard_zone, hazard_zone)

    ev_date = audit.get("evaluation_date", "")
    if "T" in ev_date:
        ev_date = ev_date.split("T")[0]

    lat_str = f"{audit.get('project', {}).get('location_lat', project.location_lat):.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{audit.get('project', {}).get('location_lon', project.location_lon):.4f}".replace(".", "_").replace("-", "n")
    units_str = audit.get('project', {}).get('dwelling_units', project.dwelling_units)
    audit_file = f"determination_{lat_str}_{lon_str}_{units_str}u.txt"
    audit_viewer_url = f"../viewer.html?doc={city_slug}/{audit_file}"

    def badge(n, derived=False):
        cls = "legal-num-badge derived" if derived else "legal-num-badge"
        return f'<span class="{cls}">{n}</span>'

    return f"""<h2 class="section-label">Legal Authority</h2>
<div class="legal-authority-box">
  <p style="margin:0 0 12px; font-size:12px; color:#495057;">
    Every numerical value in this determination is derived mechanically from the authorities below.
    No engineering judgment was exercised. The same methodology is applied uniformly to all projects
    under AB 747.
  </p>

  <table class="legal-table">
    <thead>
      <tr>
        <th style="width:28px;">#</th>
        <th>Authority</th>
        <th>Published / Adopted</th>
        <th>Parameter</th>
        <th>Value Applied</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>{badge(1)}</td>
        <td><strong>AB 747</strong>, Gov. Code §65302.15</td>
        <td>2021 Ch. 394</td>
        <td>Analysis mandate</td>
        <td>—</td>
      </tr>
      <tr>
        <td>{badge(2)}</td>
        <td><strong>CAL FIRE OSFM FHSZ</strong> (state-adopted SRA map)</td>
        <td>Current SRA designation</td>
        <td>Hazard zone</td>
        <td><code>{hazard_zone}</code> — {fz_desc}</td>
      </tr>
      <tr>
        <td>{badge(3)}</td>
        <td><strong>NIST TN 2135</strong> (Maranghides et al., Camp Fire)</td>
        <td>2021</td>
        <td>Safe egress window ({hz_label})</td>
        <td><strong>{safe_window:.0f} min</strong></td>
      </tr>
      <tr>
        <td>{badge(4)}</td>
        <td>Standard engineering significance criterion</td>
        <td>—</td>
        <td>Maximum project share of egress window</td>
        <td><strong>{max_share*100:.0f}%</strong></td>
      </tr>
      <tr class="derived-row">
        <td>{badge("→", derived=True)}</td>
        <td colspan="2"><em>Derived from ③ × ④</em></td>
        <td>ΔT threshold for this location</td>
        <td><strong>{safe_window:.0f} &times; {max_share:.2f} = {threshold:.2f} min</strong></td>
      </tr>
      <tr>
        <td>{badge(5)}</td>
        <td><strong>HCM 2022</strong> Exhibit 12-7 (TRB 7th Ed.)</td>
        <td>TRB 2022</td>
        <td>Road HCM base capacity (controlling: {ctrl_road_name}
          {f"<br><span style='font-size:10px;color:#6c757d'>{ctrl_hcm_detail}</span>" if ctrl_hcm_detail else ""})</td>
        <td><strong>{hcm_raw_ctrl:,} vph</strong></td>
      </tr>
      <tr>
        <td>{badge(6)}</td>
        <td><strong>HCM 2022</strong> Ex. 10-15/10-17 + NIST Camp Fire validation</td>
        <td>TRB 2022 / NIST 2021</td>
        <td>Hazard capacity degradation ({hz_label})</td>
        <td><strong>{deg_factor:.2f}&times;</strong></td>
      </tr>
      <tr class="derived-row">
        <td>{badge("→", derived=True)}</td>
        <td colspan="2"><em>Derived from ⑤ × ⑥</em></td>
        <td>Effective bottleneck capacity</td>
        <td><strong>{eff_cap_ctrl:,} vph</strong></td>
      </tr>
      <tr>
        <td>{badge(7)}</td>
        <td><strong>NFPA 101</strong> Life Safety Code, 2021 Ed.</td>
        <td>2021</td>
        <td>Evacuation mobilization rate (design basis)</td>
        <td><strong>{mob_rate:.2f} (constant)</strong></td>
      </tr>
      <tr>
        <td>{badge(8)}</td>
        <td><strong>U.S. Census ACS B25044</strong></td>
        <td>2020 5-yr</td>
        <td>Zero-vehicle household adjustment (~10%)</td>
        <td>Incorporated in NFPA 101 constant</td>
      </tr>
      <tr class="derived-row">
        <td>{badge("→", derived=True)}</td>
        <td colspan="2"><em>Formula result</em></td>
        <td>ΔT (marginal evacuation clearance time)</td>
        <td><strong>{max_dt:.2f} min</strong> {"vs. " + f"{threshold:.2f}-min limit" if max_dt > 0 else ""}</td>
      </tr>
    </tbody>
  </table>

  <div style="margin-top:14px; font-size:11px; font-weight:700; letter-spacing:0.8px;
              text-transform:uppercase; color:#495057; margin-bottom:6px;">Core Formula</div>
  <div style="font-family:monospace; font-size:11px; background:#f1f3f5; padding:8px 12px;
              border-radius:4px; color:#212529; margin-bottom:12px; line-height:1.9;">
    &#916;T = (project_vehicles / bottleneck_effective_capacity_vph) &times; 60 + egress_penalty<br>
    project_vehicles = {project.dwelling_units} units &times; {vpu} vpu &times; {mob_rate:.2f} (NFPA 101 constant)
    = <strong>{proj_vph:.0f} vph</strong><br>
    {"egress_penalty = " + f"min(stories &times; {egr_mps}, {egr_max}) = {egress_min:.1f} min (NFPA 101/IBC)<br>" if egress_min > 0 else f"egress_penalty = 0 (building &lt; {egr_thr} stories)<br>"}
    Flagged when &#916;T &gt; {threshold:.2f} min (threshold = {safe_window:.0f} min &times; {max_share*100:.0f}%)
  </div>

  <p style="margin:0 0 10px; font-size:11px; color:#6c757d; font-style:italic;">
    This determination applies the above authorities mechanically. No engineering judgment was
    exercised. The same methodology is applied uniformly to all projects under AB 747.
  </p>
  {_build_audit_trail_block(audit_file, audit_text)}
</div>"""


# ---------------------------------------------------------------------------
# Appeal rights (unchanged from v1)
# ---------------------------------------------------------------------------

def _build_appeal_rights(city_name: str) -> str:
    return f"""<h2 class="section-label">Appeal Rights</h2>
<div class="appeal-box">
  <p style="margin:0 0 10px;">
    This determination is the result of an objective, algorithmic analysis under adopted city
    standards. All inputs, calculations, and threshold comparisons are recorded in the attached
    audit trail and are fully reproducible.
  </p>
  <p style="margin:0 0 10px;">
    An applicant who disagrees with this determination may appeal within <strong>10 business days</strong>
    of the date of this letter to the City of {city_name} Planning Commission. The appeal must
    identify a specific factual error in the data inputs or threshold parameters. Engineering
    judgment is not a basis for appeal — these are objective standards.
  </p>
  <p style="margin:0;">
    For questions, contact the Planning Department. Reference the case number on this letter.
  </p>
</div>"""


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def _build_footer() -> str:
    return """<div class="brief-footer no-print">
  JOSH &nbsp;&middot;&nbsp; Jurisdictional Objective Standards for Housing
  &nbsp;&middot;&nbsp; California Stewardship Alliance
  &nbsp;&middot;&nbsp; v3.4 &nbsp;&middot;&nbsp; AB 747 &nbsp;&middot;&nbsp; Gov. Code &sect;65302.15
</div>"""

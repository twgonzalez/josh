"""
Determination Brief Generator — JOSH / California Stewardship Alliance

Produces a print-ready HTML determination letter that a planning department
can send to an applicant. Matches the visual language of the CA Housing Policy
Intelligence newsletter: dark header, stat cards, numbered criteria badges,
action box.

Generated automatically by `main.py evaluate` alongside the .txt audit trail.
Output: output/{city}/brief_{lat}_{lon}_{units}u.html
"""

from __future__ import annotations

import datetime
from pathlib import Path

from .themes import _TIER_CSS_COLOR, _TIER_BG_COLOR, _TIER_BORDER_COLOR


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_determination_brief(
    project,
    audit: dict,
    config: dict,
    city_config: dict,
    output_path: Path,
) -> Path:
    """Write a legally defensible HTML determination letter and return output_path."""
    html = _render_brief(project, audit, config, city_config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def _render_brief(project, audit: dict, config: dict, city_config: dict) -> str:
    city_name = city_config.get("city_name", city_config.get("name", city_config.get("city", "City")))
    determination = audit.get("determination", {})
    tier = determination.get("result", project.determination or "MINISTERIAL")
    tier_upper = tier.strip().upper()

    # Build case number
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
        _build_screen_css(tier_upper),
        "<body>",
        _build_header(city_name, case_num, eval_date, project),
        "<main>",
        _build_summary_stats(tier_upper, wildland, local5),
        _build_controlling_finding(tier_upper, wildland, project, config),
        _build_standards_analysis(tier_upper, wildland, local5, config),
        _build_determination_box(tier_upper, determination, wildland, local5),
        _build_conditions(tier_upper, wildland, local5),
        _build_methodology(audit, config, city_config),
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
  .methodology-box, .appeal-box {
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
# Screen CSS
# ---------------------------------------------------------------------------

def _build_screen_css(tier: str) -> str:
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
.methodology-box {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 16px 20px;
  font-size: 12px;
  color: #495057;
}}
.methodology-box table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
  font-size: 11px;
}}
.methodology-box th {{
  text-align: left;
  font-weight: 700;
  color: #343a40;
  padding: 4px 8px;
  border-bottom: 1px solid #dee2e6;
  background: #f8f9fa;
}}
.methodology-box td {{
  padding: 4px 8px;
  border-bottom: 1px solid #f8f9fa;
}}
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
# Header
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
    <!-- Top row: org + case block -->
    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:24px; flex-wrap:wrap; margin-bottom:18px;">
      <div>
        <!-- Org identity -->
        <div style="font-size:10px; letter-spacing:2px; text-transform:uppercase; color:#a8c8e8; font-weight:600; margin-bottom:6px;">
          California Stewardship Alliance
        </div>
        <!-- Department name -->
        <div style="font-size:24px; font-weight:800; color:#fff; line-height:1.2; margin-bottom:4px;">
          City of {city_name} &mdash; Planning Department
        </div>
        <!-- Document type -->
        <div style="font-size:13px; color:#c8dff0; font-weight:500;">
          Fire Evacuation Capacity Determination &nbsp;&middot;&nbsp; AB 747 &nbsp;&middot;&nbsp; Gov. Code &sect;65302.15
        </div>
      </div>
      <!-- Case block -->
      <div style="text-align:right; font-size:11px; color:#a8c8e8; line-height:1.8; flex-shrink:0;">
        <div style="font-weight:700; color:#fff; font-size:12px;">{case_num}</div>
        <div>{apn_line}Issued: {eval_date}</div>
        <div>{units} dwelling units</div>
      </div>
    </div>
    <!-- Project title bar -->
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
    w_steps = wildland.get("steps", {})
    l5_applicable = local5.get("tier", "NOT_APPLICABLE") != "NOT_APPLICABLE"

    # Count how many standards evaluated (1–4 always, 5 if applicable)
    n_evaluated = 5 if l5_applicable else 4

    # Count triggered standards
    w_triggered = wildland.get("triggered", False)
    l5_triggered = local5.get("triggered", False)
    n_triggered = (1 if w_triggered else 0) + (1 if l5_triggered else 0)

    trig_color = "#c0392b" if n_triggered > 0 else "#27ae60"

    tc = _TIER_CSS_COLOR.get(tier, "#555")

    tier_label = {
        "DISCRETIONARY":           "DISCRETIONARY<br>REVIEW REQUIRED",
        "CONDITIONAL MINISTERIAL": "CONDITIONAL<br>MINISTERIAL",
        "MINISTERIAL":             "MINISTERIAL<br>APPROVAL ELIGIBLE",
    }.get(tier, tier)

    return f"""<div class="stat-cards" style="margin-top:20px;">

  <div class="stat-card">
    <div class="big-num" style="color:#495057;">{n_evaluated}</div>
    <div class="label">Standards Evaluated</div>
  </div>

  <div class="stat-card">
    <div class="big-num" style="color:{trig_color};">{n_triggered}</div>
    <div class="label">{"Standards" if n_triggered != 1 else "Standard"} Triggered</div>
  </div>

  <div class="stat-card" style="text-align:center; display:flex; flex-direction:column; align-items:center; justify-content:center;">
    <div class="tier-pill">{tier_label}</div>
  </div>

</div>"""


# ---------------------------------------------------------------------------
# Controlling finding callout
# ---------------------------------------------------------------------------

def _build_controlling_finding(tier: str, wildland: dict, project, config: dict) -> str:
    """One-sentence callout box — the single fact that drives the determination."""
    tc  = _TIER_CSS_COLOR.get(tier, "#555")
    bg  = _TIER_BG_COLOR.get(tier, "#f8f9fa")
    bdr = _TIER_BORDER_COLOR.get(tier, "#dee2e6")

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
            f"Standards 2–4 are not evaluated. Approval is ministerial."
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
    else:  # CONDITIONAL MINISTERIAL
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
# Standards analysis
# ---------------------------------------------------------------------------

def _build_standards_analysis(tier: str, wildland: dict, local5: dict, config: dict) -> str:
    w_steps  = wildland.get("steps", {})
    l5_steps = local5.get("steps", {})
    l5_tier  = local5.get("tier", "NOT_APPLICABLE")
    l5_applicable = l5_tier != "NOT_APPLICABLE"

    unit_threshold = config.get("unit_threshold", 15)

    rows = []

    # --- Standard 1: Project Size ---
    s2 = w_steps.get("step2_scale", {})
    s1_result = s2.get("result", False)
    du        = s2.get("dwelling_units", 0)
    s1_chip     = "IN SCOPE" if s1_result else "BELOW THRESHOLD"
    s1_chip_cls = "chip-scope" if s1_result else "chip-na"
    s1_detail = f"""<div class="detail-block">
      {du} dwelling units proposed &nbsp;&ge;&nbsp; {unit_threshold} unit threshold
      (ITE de minimis basis: {unit_threshold} units &times; 2.5 vpu &times; 0.57 ITE peak-hour factor =
      {round(unit_threshold * 2.5 * 0.57, 1)} peak-hour trips — exceeds ITE Trip Generation
      Handbook de minimis of 10–15 trips; statutory anchor: SB 330, Gov. Code §65905.5.
      Note: evacuation mobilization rates differ by hazard zone — see Standard 3.)
    </div>""" if s1_result else f"""<div class="detail-block">
      {du} dwelling units proposed &nbsp;&lt;&nbsp; {unit_threshold} unit threshold —
      project is below the ITE de minimis for measurable evacuation impact.
      Standards 2–5 are not evaluated.
    </div>"""

    rows.append(_std_row("1", "#1a56db" if s1_result else "#6c757d",
        "Project Size ≥ Threshold",
        f"Minimum {unit_threshold} dwelling units — integer comparison, no discretion",
        s1_chip, s1_chip_cls, s1_detail))

    # --- Standard 2: Serving evacuation routes ---
    s3 = w_steps.get("step3_routes", {})
    s2_result = s3.get("triggers_standard", False)
    n_routes  = s3.get("serving_route_count", 0)
    radius    = s3.get("radius_miles", 0.5)
    s3_routes = s3.get("serving_routes", [])

    s2_chip     = "ROUTES FOUND" if s2_result else ("NOT EVALUATED" if not s1_result else "NO ROUTES")
    s2_chip_cls = "chip-scope" if s2_result else "chip-na"

    route_rows_html = ""
    if s3_routes:
        route_rows_html = (
            "<br><div style='font-size:10px;color:#6c757d;margin-bottom:3px'>"
            "Eff. capacity = HCM raw capacity &times; hazard degradation factor. "
            "v/c shown for reference only — not used in v3.0 determination.</div>"
            "<table class='route-table'><thead><tr>"
            "<th>Route Name</th><th>FHSZ Zone</th>"
            "<th>Eff. Cap (vph)</th><th>Baseline v/c</th><th>LOS</th></tr></thead><tbody>"
        )
        for r in s3_routes[:10]:
            nm   = r.get("name") or r.get("osmid", "—")
            los  = r.get("los", "—")
            eff  = r.get("effective_capacity_vph", r.get("capacity_vph", 0))
            vc   = r.get("vc_ratio", 0)
            zone = r.get("fhsz_zone", "non_fhsz")
            deg  = r.get("hazard_degradation", 1.0)
            deg_note = f" ({deg:.2f}×)" if deg < 1.0 else ""
            route_rows_html += (
                f"<tr><td>{nm}</td>"
                f"<td style='font-size:10px'>{zone}{deg_note}</td>"
                f"<td style='font-weight:600'>{eff:,.0f}</td>"
                f"<td style='color:#868e96'>{vc:.3f}</td>"
                f"<td>{los}</td></tr>"
            )
        if len(s3_routes) > 10:
            route_rows_html += (
                f"<tr><td colspan='5' style='color:#868e96'>"
                f"… and {len(s3_routes)-10} more</td></tr>"
            )
        route_rows_html += "</tbody></table>"

    s2_detail = f"""<div class="detail-block">
      {n_routes} evacuation route segment{"s" if n_routes != 1 else ""} identified
      within {radius} miles (network buffer + OSM is_evacuation_route flag)
      {route_rows_html}
    </div>""" if s1_result else ""

    rows.append(_std_row("2", "#1a56db" if s2_result else "#6c757d",
        "Serving Evacuation Routes Within Radius",
        f"Network buffer {radius} mi — GIS intersection with identified evacuation routes",
        s2_chip, s2_chip_cls, s2_detail))

    # --- Standard 3: FHSZ Hazard Zone (v3.0) ---
    s1_applicability = w_steps.get("step1_applicability", {})
    fz_result   = s1_applicability.get("std3_fhsz_flagged", False)
    fz_desc     = s1_applicability.get("std3_zone_desc", "Not in FHSZ")
    fz_level    = s1_applicability.get("std3_zone_level", 0)
    hazard_zone = s1_applicability.get("std3_hazard_zone", "non_fhsz")
    mob_rate    = s1_applicability.get("std3_mobilization_rate", 0.25)

    if not s1_result:
        s3_chip = "NOT EVALUATED"
        s3_chip_cls = "chip-na"
        s3_badge_color = "#adb5bd"
        s3_detail = ""
    elif fz_result:
        s3_chip = "FLAGGED"
        s3_chip_cls = "chip-triggered"
        s3_badge_color = "#c0392b"
        s3_detail = f"""<div class="detail-block" style="border-left-color:#c0392b;">
          <strong>Project site:</strong> {fz_desc} (source: CAL FIRE OSFM)<br>
          <strong>Hazard zone:</strong> <code>{hazard_zone}</code> &nbsp;&middot;&nbsp;
          <strong>Mobilization rate:</strong> {mob_rate:.2f}
          (Zhao et al. 2022 GPS-empirical, 44M records, Kincade Fire)<br>
          Road capacity is additionally degraded by zone-specific factors
          (vhfhsz=0.35, high_fhsz=0.50, moderate_fhsz=0.75) applied upstream by Agent 2
          (HCM Exhibit 10-15/10-17 composite + NIST Camp Fire validation).
        </div>"""
    else:
        s3_chip = "NOT IN FHSZ"
        s3_chip_cls = "chip-na"
        s3_badge_color = "#6c757d"
        s3_detail = f"""<div class="detail-block">
          Project site is not within a designated fire hazard severity zone —
          <strong>hazard_zone:</strong> <code>non_fhsz</code> &nbsp;&middot;&nbsp;
          <strong>mobilization rate:</strong> {mob_rate:.2f}
          (shadow evacuation baseline, Zhao et al. 2022). No road capacity degradation applied.
        </div>"""

    rows.append(_std_row("3", s3_badge_color,
        "FHSZ Hazard Zone",
        "GIS point-in-polygon — sets hazard_zone controlling mobilization rate and ΔT threshold",
        s3_chip, s3_chip_cls, s3_detail))

    # --- Standard 4: ΔT capacity test (v3.0) ---
    s5           = w_steps.get("step5_delta_t", {})
    s4_triggered = s5.get("triggered", False)
    path_results = s5.get("path_results", [])
    proj_vph     = s5.get("project_vehicles", 0)
    egress_min   = s5.get("egress_minutes", 0)
    max_dt       = s5.get("max_delta_t_minutes", 0.0)
    hazard_zone  = s5.get("hazard_zone", "non_fhsz")
    mob_rate     = s5.get("mobilization_rate", 0.25)
    max_threshold = s5.get("threshold_minutes", 6.0)
    safe_window   = s5.get("safe_egress_window_minutes", 120.0)
    max_share     = s5.get("max_project_share", 0.05)

    s4_chip = "TRIGGERED" if s4_triggered else ("NOT EVALUATED" if not s1_result else "WITHIN THRESHOLD")
    s4_chip_cls = "chip-triggered" if s4_triggered else ("chip-na" if not s1_result else "chip-pass")

    flagged_paths = [r for r in path_results if r.get("flagged")]
    n_flagged     = len(flagged_paths)

    flagged_table = ""
    if path_results and s1_result:
        near_paths    = [r for r in path_results
                         if not r.get("flagged")
                         and r.get("delta_t_minutes", 0) > max_threshold * 0.70][:3]
        display_paths = flagged_paths + near_paths
        n_omitted     = len(path_results) - len(display_paths)

        fhsz_note = (
            f" &nbsp;|&nbsp; <span style='color:#c0392b;font-weight:600'>"
            f"FHSZ zone: {hazard_zone} — mob rate {mob_rate:.2f} (Zhao et al. 2022)</span>"
        )
        egress_note = (
            f" &nbsp;|&nbsp; <span style='color:#6f42c1'>Egress: +{egress_min:.1f} min (NFPA 101)</span>"
            if egress_min > 0 else ""
        )
        flagged_table = (
            f"<br><div style='font-size:11px;color:#6c757d;margin-bottom:4px'>"
            f"ΔT = (project vph / bottleneck effective capacity) × 60 + egress"
            f"{fhsz_note}{egress_note}</div>"
            "<table class='route-table'><thead><tr>"
            "<th>Path ID</th>"
            "<th>Bottleneck Segment</th>"
            "<th>Eff. Cap (vph)</th>"
            "<th>ΔT (min)</th>"
            "<th>Threshold</th>"
            "<th>Margin</th>"
            "<th>Status</th></tr></thead><tbody>"
        )
        for r in display_paths:
            pid     = r.get("path_id", "—")
            bname   = r.get("bottleneck_name") or r.get("bottleneck_osmid", "—")
            eff_cap = r.get("bottleneck_effective_capacity_vph", 0)
            dt      = r.get("delta_t_minutes", 0)
            thr     = r.get("threshold_minutes", max_threshold)
            flg     = r.get("flagged", False)
            margin  = dt - thr
            dt_color     = "#c0392b" if flg else "#212529"
            margin_color = "#c0392b" if flg else "#27ae60"
            margin_str   = f"+{margin:.2f}" if flg else f"−{abs(margin):.2f}"
            if flg:
                status = "<span style='color:#c0392b;font-weight:700'>⚠ EXCEEDS</span>"
            else:
                status = "<span style='color:#27ae60'>✓ within</span>"
            flagged_table += (
                f"<tr><td style='font-size:10px;color:#868e96'>{pid}</td>"
                f"<td>{bname}</td>"
                f"<td>{eff_cap:,.0f}</td>"
                f"<td style='font-weight:600;color:{dt_color}'>{dt:.2f}</td>"
                f"<td>{thr:.2f}</td>"
                f"<td style='font-weight:600;color:{margin_color}'>{margin_str}</td>"
                f"<td>{status}</td></tr>"
            )
        if n_omitted > 0:
            flagged_table += (
                f"<tr><td colspan='7' style='color:#868e96;font-style:italic'>"
                f"{n_omitted} additional paths within threshold — omitted for brevity. "
                f"See full audit trail.</td></tr>"
            )
        flagged_table += "</tbody></table>"

    _zone_labels_4 = {
        "vhfhsz": "Very High FHSZ", "high_fhsz": "High FHSZ",
        "moderate_fhsz": "Moderate FHSZ", "non_fhsz": "Non-FHSZ",
    }
    hz_label_4 = _zone_labels_4.get(hazard_zone, hazard_zone)

    derivation_block = (
        f"<div style='font-size:11px; background:#f0f4f8; border:1px solid #ccd6e0; "
        f"border-radius:4px; padding:8px 12px; margin-bottom:8px; line-height:1.8;'>"
        f"<strong>Threshold derivation:</strong><br>"
        f"Safe egress window:&nbsp; <strong>{safe_window:.0f} min</strong>"
        f"&nbsp; ({hz_label_4}, NIST TN 2135<sup style='font-size:9px'>¹</sup>)<br>"
        f"Maximum project share:&nbsp; <strong>{max_share*100:.0f}%</strong>"
        f"&nbsp; (standard engineering significance threshold)<br>"
        f"Threshold:&nbsp; <strong>{safe_window:.0f} &times; {max_share:.2f}"
        f" = {max_threshold:.2f} min</strong>"
        f"</div>"
    ) if s1_result else ""

    s4_detail = f"""<div class="detail-block" style="border-left-color:{'#c0392b' if s4_triggered else '#dee2e6'};">
      {derivation_block}
      Project vehicles: {proj_vph:.0f} vph &nbsp;&middot;&nbsp;
      {n_flagged} path{"s" if n_flagged != 1 else ""} exceed{"s" if n_flagged == 1 else ""} threshold
      (max ΔT: {max_dt:.2f} min vs. {max_threshold:.2f}-min limit)
      {flagged_table}
    </div>""" if s1_result else ""

    rows.append(_std_row("4", "#c0392b" if s4_triggered else ("#6c757d" if not s1_result else "#27ae60"),
        "ΔT Evacuation Clearance Test",
        f"Does this project add &gt;{max_threshold:.2f} min of marginal clearance time on any serving path?",
        s4_chip, s4_chip_cls, s4_detail))

    # --- Standard 5: SB 79 Transit Proximity (v3.0 — informational only) ---
    # Sb79TransitScenario always returns NOT_APPLICABLE — never raises tier.
    # GTFS integration pending Phase 3; flag currently always False.
    l5_near_transit = local5.get("steps", {}).get("near_transit", False)
    l5_radius_sb79  = local5.get("steps", {}).get("radius_miles", 0.5)

    if not s1_result:
        s5_chip = "NOT EVALUATED"
        s5_chip_cls = "chip-na"
        s5_badge_color = "#adb5bd"
        s5_detail = ""
    elif not l5_applicable:
        # sb79_transit always returns NOT_APPLICABLE — this is always the branch taken
        s5_chip = "INFORMATIONAL"
        s5_chip_cls = "chip-na"
        s5_badge_color = "#adb5bd"
        gtfs_note = (
            "GTFS data not yet integrated (Phase 3) — transit proximity flag pending."
        )
        s5_detail = f"""<div class="detail-block">
          <strong>SB 79 transit proximity ({l5_radius_sb79} mi radius):</strong>
          {"Near transit — flag set (informational)" if l5_near_transit else "No Tier 1/2 transit within radius."}<br>
          <em style="font-size:11px; color:#868e96;">{gtfs_note if not l5_near_transit else ""}
          This flag is informational only — it does not affect the determination tier.</em>
        </div>"""
    else:
        # Future: if a non-NOT_APPLICABLE scenario replaces sb79_transit
        s5_chip = "N/A"
        s5_chip_cls = "chip-na"
        s5_badge_color = "#adb5bd"
        s5_detail = ""

    rows.append(_std_row("5", s5_badge_color,
        "SB 79 Transit Proximity (Informational)",
        "SB 79 — transit stop within 0.5 mi; informational flag only, does not affect tier",
        s5_chip, s5_chip_cls, s5_detail))

    return f"""<h2 class="section-label">Standards Analysis</h2>
{"".join(rows)}"""


def _std_row(num: str, badge_color: str, title: str, subtitle: str,
             chip_text: str, chip_cls: str, detail_html: str) -> str:
    return f"""<div class="standard-row">
  <div class="standard-row-header">
    <span class="criteria-badge" style="background:{badge_color};">{num}</span>
    <div style="flex:1;">
      <div class="standard-title">{title}</div>
      <div class="standard-sub">{subtitle}</div>
    </div>
    <span class="result-chip {chip_cls}">{chip_text}</span>
  </div>
  {detail_html}
</div>"""


# ---------------------------------------------------------------------------
# Determination box
# ---------------------------------------------------------------------------

def _build_determination_box(tier: str, determination: dict,
                              wildland: dict, local5: dict) -> str:
    tc = _TIER_CSS_COLOR.get(tier, "#555")
    reason = determination.get("reason", "")

    # Collect legal basis from all triggered scenarios
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

    # Scenario tier summary
    sc_tiers = determination.get("scenario_tiers", {})
    sc_rows = ""
    for sc_name, sc_tier in sc_tiers.items():
        label = {
            "wildland_ab747":    "Wildland Scenario (Standards 1–4)",
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
# Conditions
# ---------------------------------------------------------------------------

def _build_conditions(tier: str, wildland: dict, local5: dict) -> str:
    w_steps = wildland.get("steps", {})
    fz_level = w_steps.get("step1_applicability", {}).get(
        "fire_zone_severity_modifier", {}).get("zone_level", 0)

    if tier == "MINISTERIAL":
        body = _conditions_ministerial()
    elif tier == "CONDITIONAL MINISTERIAL":
        body = _conditions_conditional(fz_level)
    else:
        body = _conditions_discretionary(wildland, local5)

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
    fire_condition = ""
    if fz_level >= 2:
        fire_condition = """<li><strong>[Fire Zone — Severity Modifier]</strong>
        Project site is within a Very High or High FHSZ zone. Submit a Wildfire Evacuation Access
        and Egress Plan to the Fire Marshal prior to permit issuance, demonstrating that project
        design does not impede evacuation access for existing residents.</li>"""

    return f"""<p style="margin:0 0 10px;">
      This project <strong>qualifies for ministerial approval</strong> subject to the following
      conditions. These conditions are objective and do not require discretionary review or a
      public hearing. Once conditions are satisfied, approval is ministerial (Gov. Code §65589.4).
    </p>
    <ol>
      {fire_condition}
      <li>Submit a <strong>Fire Evacuation Access Plan</strong> to the Fire Marshal prior to permit
      issuance, confirming that no serving evacuation route is narrowed or obstructed by project
      construction or operation.</li>
      <li>Project shall not reduce the paved width, lane count, or sight distance of any evacuation
      route segment within 0.5 miles of the project site.</li>
      <li>A <strong>Transportation Demand Management (TDM) Plan</strong> is required per the General
      Plan Mobility Element. TDM measures shall target a minimum 10% reduction in project peak-hour
      vehicle trips.</li>
      <li>Record a covenant on title confirming ongoing compliance with evacuation access conditions
      (Fire Code §503).</li>
    </ol>"""


def _conditions_discretionary(wildland: dict, local5: dict) -> str:
    # Collect flagged path summaries from v3.0 ΔT step
    s5          = wildland.get("steps", {}).get("step5_delta_t", {})
    path_results = s5.get("path_results", [])
    max_dt      = s5.get("max_delta_t_minutes", 0.0)
    threshold   = s5.get("threshold_minutes", 6.0)
    hazard_zone = s5.get("hazard_zone", "non_fhsz")
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
      a study conforming to the JOSH v3.1 ΔT methodology (AB 747 / Gov. Code §65302.15),
      analyzing marginal evacuation clearance time on all serving paths within 0.5 miles,
      using Zhao et al. (2022) GPS-empirical mobilization rates and HCM 2022
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
      <li>Approval is not ministerial until Standard 4 ΔT impact is mitigated or the project
      is redesigned to fall within the ΔT threshold on all serving evacuation paths.</li>
    </ol>"""


# ---------------------------------------------------------------------------
# Methodology reference
# ---------------------------------------------------------------------------

def _build_methodology(audit: dict, config: dict, city_config: dict) -> str:
    algo    = audit.get("algorithm", {})
    version = algo.get("version", "3.0 (ΔT Standard)")
    name    = algo.get("name", "Universal 5-Step Evacuation Capacity Algorithm")
    ev_date = audit.get("evaluation_date", "")
    if "T" in ev_date:
        ev_date = ev_date.split("T")[0]

    ut  = config.get("unit_threshold", 15)
    vpu = config.get("vehicles_per_unit", 2.5)

    # v3.0 / v3.1 parameters
    mob_rates    = config.get("mobilization_rates", {})
    haz_deg      = config.get("hazard_degradation", {})
    safe_egress  = config.get("safe_egress_window", {})
    max_share    = config.get("max_project_share", 0.05)
    egress_cfg   = config.get("egress_penalty", {})
    vc_t         = config.get("vc_threshold", 0.95)

    mob_vhf  = mob_rates.get("vhfhsz", 0.75)
    mob_hi   = mob_rates.get("high_fhsz", 0.57)
    mob_mod  = mob_rates.get("moderate_fhsz", 0.40)
    mob_non  = mob_rates.get("non_fhsz", 0.25)

    deg_vhf  = haz_deg.get("vhfhsz", 0.35)
    deg_hi   = haz_deg.get("high_fhsz", 0.50)
    deg_mod  = haz_deg.get("moderate_fhsz", 0.75)

    # Derived thresholds: safe_egress_window × max_project_share
    win_vhf  = safe_egress.get("vhfhsz", 45)
    win_hi   = safe_egress.get("high_fhsz", 90)
    win_mod  = safe_egress.get("moderate_fhsz", 120)
    win_non  = safe_egress.get("non_fhsz", 120)
    thr_vhf  = win_vhf * max_share
    thr_hi   = win_hi  * max_share
    thr_mod  = win_mod * max_share
    thr_non  = win_non * max_share

    egr_thr  = egress_cfg.get("threshold_stories", 4)
    egr_mps  = egress_cfg.get("minutes_per_story", 1.5)
    egr_max  = egress_cfg.get("max_minutes", 12)

    lat_str = f"{audit.get('project', {}).get('location_lat', ''):.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{audit.get('project', {}).get('location_lon', ''):.4f}".replace(".", "_").replace("-", "n")
    audit_file = f"determination_{lat_str}_{lon_str}.txt"

    return f"""<h2 class="section-label">Methodology &amp; Parameters</h2>
<div class="methodology-box">
  <div style="margin-bottom:8px;">
    <strong>{name}</strong> &nbsp;(v{version}) &nbsp;&middot;&nbsp; Evaluated: {ev_date}
  </div>

  <div style="font-size:11px; font-weight:700; letter-spacing:0.8px; text-transform:uppercase;
              color:#495057; margin:12px 0 6px;">Core Formula</div>
  <div style="font-family:monospace; font-size:12px; background:#f1f3f5; padding:8px 12px;
              border-radius:4px; color:#212529; margin-bottom:12px;">
    ΔT = (project_vehicles / bottleneck_effective_capacity_vph) &times; 60 + egress_penalty<br>
    project_vehicles = units &times; {vpu} vpu &times; mobilization_rate(hazard_zone)<br>
    egress_penalty = min(stories &times; {egr_mps}, {egr_max}) min &nbsp;[if stories &ge; {egr_thr}; else 0]<br>
    Flagged when ΔT &gt; threshold(hazard_zone) = safe_egress_window × max_project_share
  </div>

  <table>
    <thead><tr><th>Parameter</th><th>Value</th><th>Source</th></tr></thead>
    <tbody>
      <tr><td>Unit threshold (Standard 1 scale gate)</td><td><strong>{ut}</strong></td>
          <td>ITE de minimis; SB 330, Gov. Code §65905.5</td></tr>
      <tr><td>Vehicles per dwelling unit</td><td><strong>{vpu}</strong></td>
          <td>U.S. Census ACS B25044</td></tr>
      <tr><td colspan="3" style="padding-top:8px; font-weight:700; color:#495057;
              font-size:11px; letter-spacing:0.5px;">
          Mobilization Rates by Hazard Zone (Zhao et al. 2022, 44M GPS records, Kincade Fire)
      </td></tr>
      <tr><td>&nbsp;&nbsp;Very High FHSZ (vhfhsz)</td>
          <td><strong>{mob_vhf:.2f}</strong></td><td>Zhao et al. 2022</td></tr>
      <tr><td>&nbsp;&nbsp;High FHSZ (high_fhsz)</td>
          <td><strong>{mob_hi:.2f}</strong></td><td>Zhao et al. 2022</td></tr>
      <tr><td>&nbsp;&nbsp;Moderate FHSZ (moderate_fhsz)</td>
          <td><strong>{mob_mod:.2f}</strong></td><td>Zhao et al. 2022</td></tr>
      <tr><td>&nbsp;&nbsp;Non-FHSZ (non_fhsz)</td>
          <td><strong>{mob_non:.2f}</strong></td><td>Zhao et al. 2022 (shadow evacuation)</td></tr>
      <tr><td colspan="3" style="padding-top:8px; font-weight:700; color:#495057;
              font-size:11px; letter-spacing:0.5px;">
          Hazard Capacity Degradation Factors (HCM Exhibit 10-15/10-17 + NIST Camp Fire)
      </td></tr>
      <tr><td>&nbsp;&nbsp;Very High FHSZ</td>
          <td><strong>{deg_vhf:.2f}&times;</strong></td><td>HCM composite + NIST validation</td></tr>
      <tr><td>&nbsp;&nbsp;High FHSZ</td>
          <td><strong>{deg_hi:.2f}&times;</strong></td><td>HCM composite</td></tr>
      <tr><td>&nbsp;&nbsp;Moderate FHSZ</td>
          <td><strong>{deg_mod:.2f}&times;</strong></td><td>HCM composite</td></tr>
      <tr><td>&nbsp;&nbsp;Non-FHSZ</td>
          <td><strong>1.00&times;</strong></td><td>No degradation</td></tr>
      <tr><td colspan="3" style="padding-top:8px; font-weight:700; color:#495057;
              font-size:11px; letter-spacing:0.5px;">
          ΔT Thresholds — derived as safe_egress_window × {max_share*100:.0f}% (NIST TN 2135)
      </td></tr>
      <tr><td>&nbsp;&nbsp;Very High FHSZ</td>
          <td><strong>{thr_vhf:.2f} min</strong></td>
          <td>{win_vhf} min × {max_share*100:.0f}% — NIST TN 2135 (Camp Fire)</td></tr>
      <tr><td>&nbsp;&nbsp;High FHSZ</td>
          <td><strong>{thr_hi:.2f} min</strong></td>
          <td>{win_hi} min × {max_share*100:.0f}%</td></tr>
      <tr><td>&nbsp;&nbsp;Moderate FHSZ</td>
          <td><strong>{thr_mod:.2f} min</strong></td>
          <td>{win_mod} min × {max_share*100:.0f}%</td></tr>
      <tr><td>&nbsp;&nbsp;Non-FHSZ</td>
          <td><strong>{thr_non:.2f} min</strong></td>
          <td>{win_non} min × {max_share*100:.0f}% (FEMA standard)</td></tr>
      <tr><td colspan="3" style="padding-top:8px; font-weight:700; color:#495057;
              font-size:11px; letter-spacing:0.5px;">
          Building Egress Penalty (NFPA 101 / IBC)
      </td></tr>
      <tr><td>&nbsp;&nbsp;Threshold</td>
          <td><strong>&ge; {egr_thr} stories</strong></td><td>NFPA 101</td></tr>
      <tr><td>&nbsp;&nbsp;Rate</td>
          <td><strong>{egr_mps} min/story</strong></td><td>NFPA 101</td></tr>
      <tr><td>&nbsp;&nbsp;Maximum</td>
          <td><strong>{egr_max} min</strong></td><td>NFPA 101 cap</td></tr>
      <tr><td colspan="3" style="padding-top:8px; font-weight:700; color:#495057;
              font-size:11px; letter-spacing:0.5px;">
          Other
      </td></tr>
      <tr><td>Evacuation route radius (Standard 2)</td>
          <td><strong>0.5 mi</strong></td><td>Network buffer methodology</td></tr>
      <tr><td>v/c threshold (LOS E/F boundary)</td>
          <td><strong>{vc_t:.2f}</strong></td>
          <td>HCM 2022 — <em>informational only</em>; not used for v3.0 determination</td></tr>
    </tbody>
  </table>

  <div style="margin-top:12px; font-size:11px;">
    Full reproducible audit trail (all inputs, intermediates, and outputs):
    <a href="{audit_file}" style="font-family:monospace; font-size:10px; background:#f1f3f5;
       padding:2px 6px; border-radius:3px; color:#1a56db; text-decoration:none;"
       title="Open full audit trail">{audit_file}</a>
  </div>
</div>"""


# ---------------------------------------------------------------------------
# Appeal rights
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
  &nbsp;&middot;&nbsp; AB 747 &nbsp;&middot;&nbsp; Gov. Code &sect;65302.15
</div>"""

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
    case_num = f"JOSH-{datetime.date.today().year}-{lat_str}-{lon_str}"

    eval_date = audit.get("evaluation_date", str(datetime.date.today()))
    if "T" in eval_date:
        eval_date = eval_date.split("T")[0]

    scenarios = audit.get("scenarios", {})
    wildland  = scenarios.get("wildland_ab747", {})
    local5    = scenarios.get("local_density_sb79", {})

    sections = [
        _build_print_css(),
        _build_screen_css(tier_upper),
        "<body>",
        _build_header(city_name, case_num, eval_date, project),
        "<main>",
        _build_summary_stats(tier_upper, wildland, local5),
        _build_standards_analysis(tier_upper, wildland, local5, config),
        _build_determination_box(tier_upper, determination, wildland, local5),
        _build_conditions(tier_upper, wildland, local5),
        _build_methodology(audit, config),
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
# Standards analysis
# ---------------------------------------------------------------------------

def _build_standards_analysis(tier: str, wildland: dict, local5: dict, config: dict) -> str:
    w_steps  = wildland.get("steps", {})
    l5_steps = local5.get("steps", {})
    l5_tier  = local5.get("tier", "NOT_APPLICABLE")
    l5_applicable = l5_tier != "NOT_APPLICABLE"

    vc_threshold = config.get("vc_threshold", 0.95)
    unit_threshold = config.get("unit_threshold", 50)

    rows = []

    # --- Standard 1: FHSZ citywide ---
    s1 = w_steps.get("step1_applicability", {})
    citywide = s1.get("citywide_fhsz", {})
    s1_result = citywide.get("result", False)
    s1_poly   = citywide.get("fhsz_polygon_count", 0)
    fz_mod    = s1.get("fire_zone_severity_modifier", {})
    fz_result = fz_mod.get("result", False)
    fz_desc   = fz_mod.get("zone_description", "Not in FHSZ")
    fz_level  = fz_mod.get("zone_level", 0)

    s1_chip = "PASS" if s1_result else "NOT MET"
    s1_chip_cls = "chip-pass" if s1_result else "chip-fail"
    s1_detail = f"""<div class="detail-block">
      <strong>Citywide FHSZ zones:</strong> {s1_poly} polygon{"s" if s1_poly != 1 else ""} on record
      &nbsp;(source: CAL FIRE OSFM ArcGIS REST API)<br>
      <strong>Project site fire zone:</strong> {fz_desc}
      {"— severity modifier applies (affects required conditions, not tier gate)" if fz_level >= 2 else "— no site-level fire zone severity modifier"}
    </div>"""

    rows.append(_std_row("1", "#27ae60" if s1_result else "#6c757d",
        "FHSZ Citywide Fire Zones",
        "Government Code §65302.15 — city must have adopted FHSZ data to apply AB 747",
        s1_chip, s1_chip_cls, s1_detail if s1_result else ""))

    # --- Standard 2: Scale ---
    s2 = w_steps.get("step2_scale", {})
    s2_result = s2.get("result", False)
    du        = s2.get("dwelling_units", 0)
    s2_chip   = "PASS" if s2_result else "BELOW THRESHOLD"
    s2_chip_cls = "chip-pass" if s2_result else "chip-na"
    s2_detail = f"""<div class="detail-block">
      {du} dwelling units proposed &nbsp;&ge;&nbsp; {unit_threshold} unit threshold
      (source: Gov. Code §65589.4 vehicle-generation floor; city-adopted)
    </div>""" if s2_result else f"""<div class="detail-block">
      {du} dwelling units proposed &nbsp;&lt;&nbsp; {unit_threshold} unit threshold —
      project is below the vehicle-generation floor for measurable evacuation impact.
      Standards 3 and 4 are not evaluated.
    </div>"""

    rows.append(_std_row("2", "#27ae60" if s2_result else "#6c757d",
        "Project Scale ≥ Threshold",
        f"Minimum {unit_threshold} dwelling units — integer comparison, no discretion",
        s2_chip, s2_chip_cls, s2_detail))

    # --- Standard 3: Serving routes ---
    s3 = w_steps.get("step3_routes", {})
    s3_result = s3.get("triggers_standard", False)
    n_routes  = s3.get("serving_route_count", 0)
    radius    = s3.get("radius_miles", 0.5)
    s3_routes = s3.get("serving_routes", [])

    s3_chip = "PASS" if s3_result else ("NOT EVALUATED" if not s2_result else "NO ROUTES")
    s3_chip_cls = "chip-pass" if s3_result else "chip-na"

    route_rows_html = ""
    if s3_routes:
        route_rows_html = "<br><table class='route-table'><thead><tr>" \
            "<th>Route Name</th><th>Type</th><th>Capacity (vph)</th>" \
            "<th>Baseline v/c</th><th>LOS</th></tr></thead><tbody>"
        for r in s3_routes[:10]:
            nm  = r.get("name") or r.get("osmid", "—")
            los = r.get("los", "—")
            cap = r.get("capacity_vph", 0)
            vc  = r.get("vc_ratio", 0)
            rt  = r.get("road_type", "—")
            route_rows_html += (
                f"<tr><td>{nm}</td><td>{rt}</td>"
                f"<td>{cap:,.0f}</td>"
                f"<td style='font-weight:600'>{vc:.3f}</td>"
                f"<td>{los}</td></tr>"
            )
        if len(s3_routes) > 10:
            route_rows_html += f"<tr><td colspan='5' style='color:#868e96'>… and {len(s3_routes)-10} more</td></tr>"
        route_rows_html += "</tbody></table>"

    s3_detail = f"""<div class="detail-block">
      {n_routes} evacuation route segment{"s" if n_routes != 1 else ""} identified
      within {radius} miles (network buffer + OSM is_evacuation_route flag)
      {route_rows_html}
    </div>""" if s2_result else ""

    rows.append(_std_row("3", "#27ae60" if s3_result else "#6c757d",
        "Serving Evacuation Routes Within Radius",
        f"Network buffer {radius} mi — GIS intersection with identified evacuation routes",
        s3_chip, s3_chip_cls, s3_detail))

    # --- Standard 4: Capacity ratio ---
    s5 = w_steps.get("step5_ratio_test", {})
    s4_triggered = s5.get("result", False)
    flagged_ids  = s5.get("project_caused_exceedance", [])
    already_ids  = s5.get("already_failing_at_baseline", [])
    proj_vph     = s5.get("vehicles_per_route", 0)
    route_details = s5.get("route_details", [])

    s4_chip = "TRIGGERED" if s4_triggered else ("NOT EVALUATED" if not s2_result else "PASS")
    s4_chip_cls = "chip-triggered" if s4_triggered else ("chip-na" if not s2_result else "chip-pass")

    flagged_table = ""
    if route_details and s2_result:
        # Deduplicate by osmid — OSM road names map to multiple geometry segments
        seen_osmids: set = set()
        deduped_details = []
        for r in route_details:
            oid = r.get("osmid", "")
            if oid not in seen_osmids:
                seen_osmids.add(oid)
                deduped_details.append(r)
        # Show: all project-caused exceedances + up to 3 near-threshold examples, truncate rest
        caused_rows  = [r for r in deduped_details if r.get("project_causes_exceedance")]
        near_rows    = [r for r in deduped_details
                        if not r.get("project_causes_exceedance")
                        and not r.get("baseline_exceeds")
                        and r.get("proposed_vc", 0) > 0.80][:3]
        display_rows = caused_rows + near_rows
        n_omitted    = len(deduped_details) - len(display_rows)

        flagged_table = "<br><table class='route-table'><thead><tr>" \
            "<th>Route Name</th><th>Baseline v/c</th><th>Project adds</th>" \
            "<th>Proposed v/c</th><th>Status</th></tr></thead><tbody>"
        for r in display_rows:
            nm   = r.get("name") or r.get("osmid", "—")
            bvc  = r.get("baseline_vc", 0)
            pvc  = r.get("proposed_vc", 0)
            adds = r.get("vehicles_added", 0)
            causes = r.get("project_causes_exceedance", False)
            bfail  = r.get("baseline_exceeds", False)
            if causes:
                status = "<span style='color:#c0392b;font-weight:700'>⚠ PROJECT CAUSES EXCEEDANCE</span>"
            elif bfail:
                status = "<span style='color:#868e96'>pre-existing LOS F</span>"
            else:
                status = "<span style='color:#27ae60'>below threshold</span>"
            flagged_table += (
                f"<tr><td>{nm}</td>"
                f"<td style='font-weight:600'>{bvc:.3f}</td>"
                f"<td style='color:#6f42c1'>+{adds:.0f} vph</td>"
                f"<td style='font-weight:600'>{pvc:.3f}</td>"
                f"<td>{status}</td></tr>"
            )
        if n_omitted > 0:
            flagged_table += (
                f"<tr><td colspan='5' style='color:#868e96;font-style:italic'>"
                f"{n_omitted} additional route segments below threshold — omitted for brevity. "
                f"See full audit trail.</td></tr>"
            )
        flagged_table += "</tbody></table>"

    already_note = ""
    if already_ids:
        already_note = f"<br><em style='color:#868e96;font-size:11px'>Note: {len(already_ids)} route(s) already failing at baseline — not counted as project impact (marginal causation).</em>"

    s4_detail = f"""<div class="detail-block" style="border-left-color:{'#c0392b' if s4_triggered else '#dee2e6'};">
      <strong>Marginal causation test</strong> (threshold: v/c {vc_threshold:.2f} — exact HCM 2022 LOS E/F boundary):<br>
      Project adds {proj_vph:.0f} vph worst-case per route &nbsp;&middot;&nbsp;
      {len(flagged_ids)} route{"s" if len(flagged_ids) != 1 else ""} caused to exceed threshold
      {already_note}
      {flagged_table}
    </div>""" if s2_result else ""

    rows.append(_std_row("4", "#c0392b" if s4_triggered else ("#6c757d" if not s2_result else "#27ae60"),
        "Capacity Ratio Test (Marginal Causation)",
        f"baseline_vc < {vc_threshold} AND proposed_vc ≥ {vc_threshold} — project must cause the LOS E/F crossing",
        s4_chip, s4_chip_cls, s4_detail))

    # --- Standard 5: Local density ---
    l5_triggered = local5.get("triggered", False)
    l5_s3 = l5_steps.get("step3_routes", {})
    l5_s5 = l5_steps.get("step5_ratio_test", {})
    l5_n_routes  = l5_s3.get("serving_route_count", 0)
    l5_radius    = l5_s3.get("radius_miles", 0.25)
    l5_flagged   = l5_s5.get("project_caused_exceedance", [])
    l5_details   = l5_s5.get("route_details", [])
    l5_proj_vph  = l5_s5.get("vehicles_per_route", 0)

    if not l5_applicable:
        s5_chip = "N/A"
        s5_chip_cls = "chip-na"
        s5_badge_color = "#adb5bd"
        s5_detail = ""
    else:
        s5_chip = "TRIGGERED" if l5_triggered else "PASS"
        s5_chip_cls = "chip-triggered" if l5_triggered else "chip-pass"
        s5_badge_color = "#c0392b" if l5_triggered else "#27ae60"

        l5_table = ""
        if l5_details:
            seen_l5: set = set()
            l5_deduped = []
            for r in l5_details:
                oid = r.get("osmid", "")
                if oid not in seen_l5:
                    seen_l5.add(oid)
                    l5_deduped.append(r)
            l5_caused = [r for r in l5_deduped if r.get("project_causes_exceedance")]
            l5_near   = [r for r in l5_deduped
                         if not r.get("project_causes_exceedance")
                         and not r.get("baseline_exceeds")
                         and r.get("proposed_vc", 0) > 0.80][:3]
            l5_display = l5_caused + l5_near
            l5_omitted = len(l5_deduped) - len(l5_display)
            l5_table = "<br><table class='route-table'><thead><tr>" \
                "<th>Local Route</th><th>Road Type</th><th>Baseline v/c</th>" \
                "<th>Project adds</th><th>Proposed v/c</th><th>Status</th></tr></thead><tbody>"
            for r in l5_display:
                nm   = r.get("name") or r.get("osmid", "—")
                rt   = r.get("road_type", "—")
                bvc  = r.get("baseline_vc", 0)
                pvc  = r.get("proposed_vc", 0)
                adds = r.get("vehicles_added", 0)
                causes = r.get("project_causes_exceedance", False)
                bfail  = r.get("baseline_exceeds", False)
                if causes:
                    status = "<span style='color:#c0392b;font-weight:700'>⚠ TRIGGERED</span>"
                elif bfail:
                    status = "<span style='color:#868e96'>pre-existing</span>"
                else:
                    status = "<span style='color:#27ae60'>OK</span>"
                l5_table += (
                    f"<tr><td>{nm}</td><td>{rt}</td>"
                    f"<td style='font-weight:600'>{bvc:.3f}</td>"
                    f"<td style='color:#6f42c1'>+{adds:.0f} vph</td>"
                    f"<td style='font-weight:600'>{pvc:.3f}</td>"
                    f"<td>{status}</td></tr>"
                )
            if l5_omitted > 0:
                l5_table += (
                    f"<tr><td colspan='6' style='color:#868e96;font-style:italic'>"
                    f"{l5_omitted} additional segments omitted. See full audit trail.</td></tr>"
                )
            l5_table += "</tbody></table>"

        s5_detail = f"""<div class="detail-block" style="border-left-color:{'#c0392b' if l5_triggered else '#dee2e6'};">
          <strong>Local collector/arterial proximity:</strong>
          {l5_n_routes} route{"s" if l5_n_routes != 1 else ""} within {l5_radius} mi
          &nbsp;&middot;&nbsp; {len(l5_flagged)} triggered<br>
          Project adds {l5_proj_vph:.0f} vph per route (worst-case)
          {l5_table}
        </div>"""

    rows.append(_std_row("5", s5_badge_color,
        "Local Evacuation Density (Standard 5)",
        "General Plan §65302(g) · SB 79 — local collector/arterial capacity within 0.25 mi",
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
            "local_density_sb79":"Local Density Scenario (Standard 5)",
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
    # Collect flagged route names from both scenarios
    all_flagged_routes = []
    for sc in [wildland, local5]:
        rd = sc.get("steps", {}).get("step5_ratio_test", {}).get("route_details", [])
        for r in rd:
            if r.get("project_causes_exceedance"):
                nm = r.get("name") or r.get("osmid", "route")
                bvc = r.get("baseline_vc", 0)
                pvc = r.get("proposed_vc", 0)
                all_flagged_routes.append(f"{nm} (v/c {bvc:.3f} → {pvc:.3f})")

    route_note = ""
    if all_flagged_routes:
        route_list = "; ".join(all_flagged_routes[:3])
        route_note = f"<p style='margin:10px 0 0; font-size:12px; color:#495057;'>" \
            f"<strong>Capacity impact identified on:</strong> {route_list}</p>"

    return f"""<p style="margin:0 0 10px;">
      This project <strong>requires discretionary review</strong> under AB 747
      (Gov. Code §65302.15). The objective standards analysis has determined that this project
      would cause one or more serving evacuation routes to exceed the HCM 2022 LOS E/F capacity
      boundary (v/c 0.95).
    </p>
    {route_note}
    <ol>
      <li><strong>Environmental Impact Report (EIR)</strong> required under CEQA
      (Pub. Resources Code §21100) — evacuation capacity must be analyzed as a
      significant transportation impact.</li>
      <li><strong>Traffic Impact Analysis (Evacuation Focus):</strong> Applicant shall commission
      a study conforming to the KLD Engineering AB 747 methodology, analyzing peak-hour evacuation
      demand on all serving routes within 0.5 miles, under baseline and proposed conditions.</li>
      <li><strong>Public Hearing</strong> before the Planning Commission is required prior to any
      project approval (Gov. Code §65905).</li>
      <li><strong>Fire Department Review:</strong> Submit project plans to the Fire Marshal for
      review of evacuation access, egress widths, and compliance with Fire Code §503.</li>
      <li><strong>Mitigation Measures or Project Redesign:</strong> Applicant must demonstrate
      — through the TIA — either (a) that mitigation measures reduce proposed v/c below 0.95
      on all serving routes, or (b) that the project scope is reduced to below the capacity
      threshold, to qualify for ministerial review.</li>
      <li>Approval is not ministerial until Standard 4 capacity impact is mitigated or the project
      is redesigned to fall below the v/c threshold on all serving evacuation routes.</li>
    </ol>"""


# ---------------------------------------------------------------------------
# Methodology reference
# ---------------------------------------------------------------------------

def _build_methodology(audit: dict, config: dict) -> str:
    algo    = audit.get("algorithm", {})
    version = algo.get("version", "2.0")
    name    = algo.get("name", "Universal 5-Step Evacuation Capacity Algorithm")
    ev_date = audit.get("evaluation_date", "")
    if "T" in ev_date:
        ev_date = ev_date.split("T")[0]

    vc_t  = config.get("vc_threshold", 0.95)
    ut    = config.get("unit_threshold", 50)
    vpu   = config.get("vehicles_per_unit", 2.5)
    mob   = config.get("peak_hour_mobilization", 0.57)

    lat_str = f"{audit.get('project', {}).get('location_lat', ''):.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{audit.get('project', {}).get('location_lon', ''):.4f}".replace(".", "_").replace("-", "n")
    audit_file = f"determination_{lat_str}_{lon_str}.txt"

    return f"""<h2 class="section-label">Methodology &amp; Parameters</h2>
<div class="methodology-box">
  <div style="margin-bottom:8px;">
    <strong>{name}</strong> &nbsp;(v{version}) &nbsp;&middot;&nbsp; Evaluated: {ev_date}
  </div>
  <table>
    <thead><tr><th>Parameter</th><th>Value</th><th>Source</th></tr></thead>
    <tbody>
      <tr><td>V/C threshold (LOS E/F boundary)</td><td><strong>{vc_t:.2f}</strong></td>
          <td>HCM 2022 — exact LOS E/F boundary</td></tr>
      <tr><td>Unit threshold (project scale gate)</td><td><strong>{ut}</strong></td>
          <td>Vehicle-generation floor (city-adopted)</td></tr>
      <tr><td>Vehicles per dwelling unit</td><td><strong>{vpu}</strong></td>
          <td>U.S. Census ACS</td></tr>
      <tr><td>Peak-hour mobilization factor</td><td><strong>{mob}</strong></td>
          <td>KLD Engineering AB 747 Study (Berkeley, 2024), Figure 12</td></tr>
      <tr><td>Evacuation route radius</td><td><strong>0.5 mi</strong></td>
          <td>Standard 3 — network buffer methodology</td></tr>
      <tr><td>Impact method</td><td><strong>Worst-case per route</strong></td>
          <td>Full project_vph tested against each route independently</td></tr>
    </tbody>
  </table>
  <div style="margin-top:12px; font-size:11px;">
    Full reproducible audit trail (all inputs, intermediates, and outputs):
    <code style="background:#f1f3f5; padding:2px 6px; border-radius:3px; font-size:10px;">{audit_file}</code>
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

"""
Determination Brief v2 — Audience-First Design — JOSH v3.2 / California Stewardship Alliance

Alternative to brief.py. Same data, completely different information architecture.
Design rationale: the current brief is organized around how the algorithm runs (Steps 1–5).
This version is organized around what each audience needs to act on:

  City Planner  → verdict, case number, defensibility at a glance
  Developer     → redesign options computed algorithmically (not judgment)
  City Attorney → numbered citation table: every number traced to a published source

Key differences from brief.py:
  - Leads with the tier verdict and plain-English one-liner
  - ΔT gauge (CSS-only bar) shows margin visually, not just numerically
  - Redesign options: units-to-conditional and story-reduction computed by inverting the
    ΔT formula — always shown for DISCRETIONARY (no gating)
  - Standards shown as a compact at-a-glance table (not 5 equal-weight expanded rows)
  - Legal authority chain: numbered citation table, attorney-readable
  - Technical appendix in a collapsible <details> element

Output: output/{city}/brief_v2_{lat}_{lon}_{units}u.html
"""

from __future__ import annotations

import datetime
import math
from pathlib import Path

from .themes import _TIER_CSS_COLOR, _TIER_BG_COLOR, _TIER_BORDER_COLOR


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_determination_brief_v2(
    project,
    audit: dict,
    config: dict,
    city_config: dict,
    output_path: Path,
) -> Path:
    """Write audience-first HTML determination brief v2 and return output_path."""
    html = _render_brief_v2(project, audit, config, city_config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def _render_brief_v2(project, audit: dict, config: dict, city_config: dict) -> str:
    city_name = city_config.get("city_name", city_config.get("name", city_config.get("city", "City")))
    determination = audit.get("determination", {})
    tier = determination.get("result", project.determination or "MINISTERIAL")
    tier_upper = tier.strip().upper()

    lat  = project.location_lat
    lon  = project.location_lon
    lat_str = f"{lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{lon:.4f}".replace(".", "_").replace("-", "n")
    units   = project.dwelling_units
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
    steps     = wildland.get("steps", {})
    step1     = steps.get("step1_applicability", {})
    step2     = steps.get("step2_scale", {})
    step3     = steps.get("step3_routes", {})
    step5     = steps.get("step5_delta_t", {})
    sb79      = scenarios.get("sb79_transit", {})

    redesign = _compute_redesign(project, step5, config) if tier_upper == "DISCRETIONARY" else None

    sections = [
        _build_styles(tier_upper),
        "<body>",
        _build_verdict_panel(city_name, case_num, eval_date, project, tier_upper, determination),
        "<main>",
        _build_key_number(tier_upper, step5, config),
        _build_redesign_options(project, tier_upper, step5, config, redesign),
        _build_standards_glance(tier_upper, step1, step2, step3, step5, sb79),
        _build_legal_chain(project, tier_upper, step1, step5, config),
        _build_conditions_v2(tier_upper, project, step5, redesign),
        _build_appeal_rights(city_name),
        _build_technical_appendix(tier_upper, step3, step5, config),
        "</main>",
        _build_footer(case_num),
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
  <title>Determination v2 — {case_num}</title>
</head>
{body}
</html>"""


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles(tier: str) -> str:
    tc  = _TIER_CSS_COLOR.get(tier, "#555")
    tbg = _TIER_BG_COLOR.get(tier, "#f8f9fa")
    tbd = _TIER_BORDER_COLOR.get(tier, "#dee2e6")
    return f"""<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f0f2f5;
  color: #212529;
  font-size: 14px;
  line-height: 1.55;
}}
main {{
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 24px 56px;
}}

/* ── Verdict panel ── */
.verdict-panel {{
  background: #1c4a6e;
  color: #fff;
  padding: 0;
}}
.verdict-top {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 28px 36px 20px;
  gap: 24px;
}}
.verdict-tier-block {{ flex: 1; }}
.verdict-org {{
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.6px;
  text-transform: uppercase;
  opacity: 0.7;
  margin-bottom: 12px;
}}
.verdict-tier-badge {{
  display: inline-block;
  font-size: 28px;
  font-weight: 900;
  letter-spacing: 0.5px;
  color: {tc};
  background: {tbg};
  border: 2px solid {tbd};
  border-radius: 8px;
  padding: 10px 24px;
  margin-bottom: 12px;
  line-height: 1.1;
}}
.verdict-oneliner {{
  font-size: 15px;
  opacity: 0.92;
  line-height: 1.45;
  max-width: 520px;
}}
.verdict-meta {{
  text-align: right;
  flex-shrink: 0;
}}
.verdict-meta .meta-label {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  opacity: 0.55;
  margin-bottom: 3px;
}}
.verdict-meta .meta-val {{
  font-size: 12px;
  opacity: 0.9;
  margin-bottom: 10px;
  font-family: 'SF Mono', 'Fira Mono', monospace;
}}
.verdict-project-bar {{
  background: rgba(255,255,255,0.08);
  border-top: 1px solid rgba(255,255,255,0.12);
  padding: 14px 36px;
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
}}
.verdict-project-bar .pitem {{
  display: flex;
  flex-direction: column;
}}
.verdict-project-bar .plabel {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.1px;
  text-transform: uppercase;
  opacity: 0.55;
  margin-bottom: 2px;
}}
.verdict-project-bar .pval {{
  font-size: 13px;
  opacity: 0.95;
  font-weight: 500;
}}

/* ── Section headers ── */
.section-hdr {{
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.8px;
  text-transform: uppercase;
  color: #868e96;
  margin: 28px 0 12px;
  padding-bottom: 6px;
  border-bottom: 2px solid #e9ecef;
}}

/* ── Key number / gauge ── */
.key-number-block {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 24px 28px 20px;
  margin-bottom: 16px;
}}
.key-number-row {{
  display: flex;
  align-items: baseline;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}}
.key-dt-big {{
  font-size: 52px;
  font-weight: 900;
  color: {tc};
  line-height: 1;
  font-variant-numeric: tabular-nums;
}}
.key-dt-unit {{
  font-size: 20px;
  font-weight: 600;
  color: {tc};
  opacity: 0.7;
}}
.key-dt-limit {{
  font-size: 14px;
  color: #6c757d;
  line-height: 1.4;
}}
.key-dt-limit strong {{ color: #343a40; }}
.key-dt-ratio {{
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  color: {tc};
  background: {tbg};
  border: 1px solid {tbd};
  border-radius: 4px;
  padding: 2px 8px;
  margin-left: 4px;
}}
.key-margin {{
  font-size: 13px;
  color: {tc};
  font-weight: 600;
  margin-bottom: 12px;
}}
/* Gauge */
.gauge-wrap {{
  position: relative;
  height: 14px;
  border-radius: 7px;
  background: #e9ecef;
  overflow: visible;
  margin-bottom: 6px;
}}
.gauge-fill {{
  height: 100%;
  border-radius: 7px;
  background: {tc};
  position: relative;
}}
.gauge-safe {{
  position: absolute;
  top: 0; left: 0;
  height: 100%;
  background: #27ae60;
  border-radius: 7px 0 0 7px;
}}
.gauge-tick {{
  position: absolute;
  top: -4px;
  width: 2px;
  height: 22px;
  background: #212529;
  border-radius: 1px;
}}
.gauge-tick-label {{
  position: absolute;
  top: 22px;
  font-size: 10px;
  font-weight: 700;
  color: #495057;
  white-space: nowrap;
  transform: translateX(-50%);
}}
.gauge-labels {{
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #adb5bd;
  margin-top: 22px;
}}
.gauge-segment-label {{
  font-size: 11px;
  color: #6c757d;
  margin-top: 4px;
}}

/* ── Redesign cards ── */
.redesign-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}}
.redesign-card {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 18px 16px;
  position: relative;
}}
.redesign-card.current {{
  border-color: {tbd};
  border-width: 2px;
  background: {tbg};
}}
.redesign-card.option-ministerial {{
  border-color: #a8d5b8;
  border-width: 2px;
}}
.redesign-card.option-conditional {{
  border-color: #f5d49a;
  border-width: 2px;
}}
.redesign-card-label {{
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #868e96;
  margin-bottom: 10px;
}}
.redesign-tier-badge {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.5px;
  padding: 4px 10px;
  border-radius: 4px;
  display: inline-block;
  margin-bottom: 12px;
  text-transform: uppercase;
}}
.redesign-stat {{
  font-size: 12px;
  color: #495057;
  margin-bottom: 4px;
}}
.redesign-stat strong {{ color: #212529; }}
.redesign-dt {{
  font-size: 22px;
  font-weight: 800;
  margin: 8px 0 4px;
  font-variant-numeric: tabular-nums;
}}
.redesign-dt-status {{
  font-size: 11px;
  font-weight: 600;
}}

/* ── Standards at-a-glance ── */
.standards-table {{
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #dee2e6;
  font-size: 13px;
  margin-bottom: 16px;
}}
.standards-table th {{
  background: #f1f3f5;
  text-align: left;
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: #6c757d;
  padding: 10px 14px;
  border-bottom: 1px solid #dee2e6;
}}
.standards-table td {{
  padding: 11px 14px;
  border-bottom: 1px solid #f1f3f5;
  vertical-align: middle;
}}
.standards-table tr:last-child td {{ border-bottom: none; }}
.std-num {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px; height: 22px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 800;
  color: #fff;
}}
.std-num.triggered {{ background: #c0392b; }}
.std-num.passed    {{ background: #1a56db; }}
.std-num.na        {{ background: #adb5bd; }}
.std-icon {{ font-size: 15px; }}

/* ── Legal chain ── */
.legal-table {{
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #dee2e6;
  font-size: 12px;
  margin-bottom: 16px;
}}
.legal-table th {{
  background: #f1f3f5;
  text-align: left;
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: #6c757d;
  padding: 9px 14px;
  border-bottom: 1px solid #dee2e6;
}}
.legal-table td {{
  padding: 9px 14px;
  border-bottom: 1px solid #f1f3f5;
  vertical-align: top;
  line-height: 1.45;
}}
.legal-table tr:last-child td {{ border-bottom: none; }}
.legal-table tr.derived td {{
  background: #f8f9fa;
  font-weight: 700;
  color: #212529;
}}
.legal-table tr.derived td:last-child {{
  color: {tc};
}}
.legal-src-badge {{
  display: inline-block;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: #fff;
  background: #495057;
  border-radius: 3px;
  padding: 1px 5px;
  margin-right: 4px;
  vertical-align: middle;
}}
.legal-attestation {{
  font-size: 11px;
  color: #6c757d;
  font-style: italic;
  margin-top: 8px;
  padding: 8px 12px;
  background: #f8f9fa;
  border-left: 3px solid #dee2e6;
  border-radius: 0 4px 4px 0;
}}

/* ── Conditions ── */
.conditions-box {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;
}}
.conditions-box h3 {{
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 700;
  color: #212529;
}}
.conditions-box ol, .conditions-box ul {{
  margin: 0; padding-left: 20px;
}}
.conditions-box li {{
  margin-bottom: 6px;
  font-size: 13px;
  color: #343a40;
  line-height: 1.5;
}}
.failure-mode-tag {{
  display: inline-block;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 3px;
  margin-bottom: 8px;
  color: #fff;
  background: {tc};
}}

/* ── Appeal box ── */
.appeal-box {{
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 16px 20px;
  font-size: 12px;
  color: #6c757d;
  margin-bottom: 16px;
}}
.appeal-box strong {{ color: #495057; }}

/* ── Technical appendix ── */
details.tech-appendix {{
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: hidden;
}}
details.tech-appendix summary {{
  cursor: pointer;
  padding: 14px 20px;
  font-size: 12px;
  font-weight: 700;
  color: #495057;
  background: #f1f3f5;
  border-bottom: 1px solid #dee2e6;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
}}
details.tech-appendix summary::-webkit-details-marker {{ display: none; }}
details.tech-appendix summary::before {{
  content: "▶";
  font-size: 10px;
  transition: transform 0.15s;
  display: inline-block;
}}
details.tech-appendix[open] summary::before {{
  transform: rotate(90deg);
}}
.tech-inner {{
  padding: 16px 20px;
}}
.mini-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  margin-top: 8px;
}}
.mini-table th {{
  text-align: left;
  font-weight: 700;
  color: #495057;
  padding: 4px 8px;
  border-bottom: 1px solid #dee2e6;
  background: #f8f9fa;
}}
.mini-table td {{
  padding: 5px 8px;
  border-bottom: 1px solid #f8f9fa;
  color: #343a40;
}}
.mini-table tr:last-child td {{ border-bottom: none; }}
.mini-table tr.flagged-row td {{ background: #fdf2f2; color: #c0392b; }}
.mini-table tr.ok-row td {{ color: #495057; }}
.code-block {{
  font-family: 'SF Mono', 'Fira Mono', 'Consolas', monospace;
  font-size: 11px;
  background: #f1f3f5;
  border-radius: 4px;
  padding: 12px 14px;
  margin: 8px 0;
  white-space: pre;
  overflow-x: auto;
  color: #212529;
}}

/* ── Footer ── */
.brief-footer {{
  text-align: center;
  font-size: 10px;
  color: #adb5bd;
  padding: 24px 0 8px;
  letter-spacing: 0.5px;
}}

/* ── Print ── */
@media print {{
  body {{ background: #fff !important; font-size: 11px; }}
  main {{ padding: 0 !important; max-width: 100% !important; }}
  .verdict-panel, .redesign-card, .conditions-box, .legal-table, .standards-table {{
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    break-inside: avoid;
  }}
  details.tech-appendix {{ display: none; }}
  @page {{
    size: letter;
    margin: 0.65in 0.75in 0.80in;
    @bottom-center {{
      content: "JOSH v2 · California Stewardship Alliance · Page " counter(page);
      font-size: 8px;
      color: #868e96;
    }}
  }}
}}
</style>"""


# ---------------------------------------------------------------------------
# Section 1: Verdict panel
# ---------------------------------------------------------------------------

def _build_verdict_panel(city_name, case_num, eval_date, project, tier, determination) -> str:
    tc = _TIER_CSS_COLOR.get(tier, "#555")
    tbg = _TIER_BG_COLOR.get(tier, "#f8f9fa")
    tbd = _TIER_BORDER_COLOR.get(tier, "#dee2e6")

    _VERDICT_TEXT = {
        "DISCRETIONARY":           "This project requires discretionary environmental review before any approval may be issued.",
        "CONDITIONAL MINISTERIAL": "This project qualifies for ministerial approval subject to mandatory evacuation conditions.",
        "MINISTERIAL":             "This project qualifies for ministerial (over-the-counter) approval. No evacuation capacity analysis is required.",
    }
    verdict_text = _VERDICT_TEXT.get(tier, "Determination complete.")

    units   = project.dwelling_units
    stories = getattr(project, "stories", 0)
    addr    = getattr(project, "address", "") or ""
    pname   = getattr(project, "project_name", "") or ""
    hz      = getattr(project, "hazard_zone", "non_fhsz")
    hz_label = {
        "vhfhsz":        "Zone 3 — Very High FHSZ",
        "high_fhsz":     "Zone 2 — High FHSZ",
        "moderate_fhsz": "Zone 1 — Moderate FHSZ",
        "non_fhsz":      "Non-FHSZ",
    }.get(hz, hz)
    in_fhsz = getattr(project, "in_fire_zone", False)
    hz_note = f'<span style="color:#fc8d59;font-weight:700;">{hz_label}</span>' if in_fhsz else hz_label

    stories_str = f"{stories} {'story' if stories == 1 else 'stories'}" if stories > 0 else "stories not specified"
    lat_str = f"{project.location_lat:.4f}"
    lon_str = f"{project.location_lon:.4f}"

    pname_row = f'<div class="pitem"><div class="plabel">Project</div><div class="pval">{pname}</div></div>' if pname else ""
    addr_row  = f'<div class="pitem"><div class="plabel">Address</div><div class="pval">{addr}</div></div>' if addr else ""

    return f"""<div class="verdict-panel">
  <div class="verdict-top">
    <div class="verdict-tier-block">
      <div class="verdict-org">California Stewardship Alliance · {city_name} Planning</div>
      <div class="verdict-tier-badge">{tier}</div>
      <div class="verdict-oneliner">{verdict_text}</div>
    </div>
    <div class="verdict-meta">
      <div class="meta-label">Case Number</div>
      <div class="meta-val">{case_num}</div>
      <div class="meta-label">Issue Date</div>
      <div class="meta-val">{eval_date}</div>
      <div class="meta-label">Authority</div>
      <div class="meta-val">AB 747 · Gov. Code §65302.15</div>
    </div>
  </div>
  <div class="verdict-project-bar">
    {pname_row}
    {addr_row}
    <div class="pitem"><div class="plabel">Units</div><div class="pval">{units} dwelling units</div></div>
    <div class="pitem"><div class="plabel">Height</div><div class="pval">{stories_str}</div></div>
    <div class="pitem"><div class="plabel">Location</div><div class="pval">{lat_str}, {lon_str}</div></div>
    <div class="pitem"><div class="plabel">Fire Zone</div><div class="pval">{hz_note}</div></div>
  </div>
</div>"""


# ---------------------------------------------------------------------------
# Section 2: The Controlling Number (ΔT gauge)
# ---------------------------------------------------------------------------

def _build_key_number(tier: str, step5: dict, config: dict) -> str:
    if tier == "MINISTERIAL":
        # Below size threshold — no ΔT computed
        unit_threshold = config.get("unit_threshold", 15)
        return f"""<div class="section-hdr">Controlling Factor</div>
<div class="key-number-block">
  <div style="font-size:18px;font-weight:700;color:#27ae60;margin-bottom:8px;">
    ✓ Below Size Threshold
  </div>
  <div style="font-size:13px;color:#495057;">
    Project has fewer than <strong>{unit_threshold} dwelling units</strong> —
    the Standard 1 size gate is not triggered. No evacuation capacity analysis is required.
    Ministerial approval is available regardless of fire zone designation or road conditions.
  </div>
</div>"""

    max_dt    = step5.get("max_delta_t_minutes", 0.0)
    threshold = step5.get("threshold_minutes", 6.0)
    egress    = step5.get("egress_minutes", 0.0)
    hz        = step5.get("hazard_zone", "non_fhsz")
    project_veh = step5.get("project_vehicles", 0.0)
    tc        = _TIER_CSS_COLOR.get(tier, "#555")

    # Find the controlling (worst-case) path
    path_results = step5.get("path_results", [])
    worst = None
    if path_results:
        worst = max(path_results, key=lambda r: r.get("delta_t_minutes", 0))

    ratio = (max_dt / threshold) if threshold > 0 else 0
    margin = max_dt - threshold
    margin_str = (
        f"+{margin:.2f} min over threshold ({ratio:.1f}× the limit)"
        if margin > 0 else
        f"{abs(margin):.2f} min under limit ({ratio:.0%} of limit used)"
    )

    # Gauge geometry
    scale_max = max(max_dt * 1.25, threshold * 2.0, 1.0)
    safe_pct  = min(threshold / scale_max * 100, 100)
    fill_pct  = min(max_dt / scale_max * 100, 100)
    tick_pct  = safe_pct

    safe_bar_width   = f"{safe_pct:.1f}%"
    excess_bar_left  = f"{safe_pct:.1f}%"
    excess_bar_width = f"{max(fill_pct - safe_pct, 0):.1f}%"
    tick_left        = f"{tick_pct:.1f}%"

    controlling_seg = ""
    if worst:
        bn_name = worst.get("bottleneck_name", str(worst.get("bottleneck_osmid", "")))
        bn_cap  = worst.get("bottleneck_effective_capacity_vph", 0)
        bn_fhsz = worst.get("bottleneck_fhsz_zone", hz)
        controlling_seg = (
            f"Controlling segment: <strong>{bn_name or worst.get('bottleneck_osmid','')}</strong> · "
            f"effective capacity {bn_cap:,.0f} vph · FHSZ zone: {bn_fhsz}"
        )

    hz_label = {
        "vhfhsz":        "Very High FHSZ — 45 min safe window",
        "high_fhsz":     "High FHSZ — 90 min safe window",
        "moderate_fhsz": "Moderate FHSZ — 120 min safe window",
        "non_fhsz":      "Non-FHSZ — 120 min safe window",
    }.get(hz, hz)

    # Egress breakdown note
    vehicle_dt = max_dt - egress
    egress_note = ""
    if egress > 0:
        egress_note = (
            f'<div style="font-size:11px;color:#6c757d;margin-top:6px;">'
            f'Components: <strong>{vehicle_dt:.2f} min</strong> vehicle clearance + '
            f'<strong>{egress:.1f} min</strong> building egress penalty = {max_dt:.2f} min total'
            f'</div>'
        )

    return f"""<div class="section-hdr">The Controlling Number</div>
<div class="key-number-block">
  <div class="key-number-row">
    <div>
      <div class="key-dt-big">{max_dt:.1f}</div>
      <div class="key-dt-unit">min ΔT</div>
    </div>
    <div class="key-dt-limit">
      <div style="margin-bottom:4px;">Marginal evacuation clearance time added by this project</div>
      <div>Limit for this location:
        <strong>{threshold:.2f} min</strong>
        <span class="key-dt-ratio">{ratio:.1f}×</span>
      </div>
      <div style="font-size:11px;color:#6c757d;margin-top:2px;">{hz_label} · {threshold:.2f} min = safe window × 5% project share</div>
    </div>
  </div>

  <div class="key-margin" style="margin-bottom:10px;">{margin_str}</div>

  <div class="gauge-wrap" style="margin-bottom:36px;">
    <div class="gauge-safe" style="width:{safe_bar_width};"></div>
    <div style="position:absolute;top:0;left:{excess_bar_left};width:{excess_bar_width};height:100%;background:{tc};border-radius:0 7px 7px 0;"></div>
    <div class="gauge-tick" style="left:{tick_left};"></div>
    <div class="gauge-tick-label" style="left:{tick_left};">Limit<br>{threshold:.2f} min</div>
  </div>
  <div class="gauge-labels">
    <span>0</span>
    <span>← safe zone →</span>
    <span>{scale_max:.1f} min</span>
  </div>

  {egress_note}
  <div class="gauge-segment-label" style="margin-top:12px;">{controlling_seg}</div>
</div>"""


# ---------------------------------------------------------------------------
# Section 3: Redesign options (DISCRETIONARY only)
# ---------------------------------------------------------------------------

def _compute_redesign(project, step5: dict, config: dict) -> dict:
    """Invert the ΔT formula to compute minimum changes that shift the tier."""
    mob       = config.get("mobilization_rate", 0.90)
    vpu       = config.get("vehicles_per_unit", 2.5)
    threshold = step5.get("threshold_minutes", 6.0)
    egress    = step5.get("egress_minutes", 0.0)
    unit_threshold = config.get("unit_threshold", 15)

    path_results = step5.get("path_results", [])
    if not path_results:
        return {}

    # Find the bottleneck path (lowest effective capacity)
    worst = min(path_results, key=lambda r: r.get("bottleneck_effective_capacity_vph", 9999))
    eff_cap = worst.get("bottleneck_effective_capacity_vph", 0)
    if eff_cap <= 0:
        return {}

    # Option A: Reduce units so vehicle ΔT + egress ≤ threshold
    # (units * vpu * mob / eff_cap) * 60 ≤ threshold - egress
    headroom = threshold - egress
    if headroom > 0:
        max_veh = headroom * eff_cap / 60
        units_for_conditional = int(max_veh / (vpu * mob))
    else:
        units_for_conditional = 0  # egress alone exceeds threshold

    units_for_ministerial = unit_threshold - 1  # always unit_threshold - 1

    # Compute ΔT for Option A (units_for_conditional)
    if units_for_conditional > 0:
        veh_a = units_for_conditional * vpu * mob
        dt_a  = (veh_a / eff_cap) * 60 + egress
    else:
        dt_a = None

    # Option B: Reduce stories to eliminate egress penalty
    ep_cfg         = config.get("egress_penalty", {})
    ep_threshold_s = ep_cfg.get("threshold_stories", 4)
    stories        = getattr(project, "stories", 0)

    dt_no_egress  = None
    tier_no_egress = None
    target_stories = None
    if stories >= ep_threshold_s:
        # Recalculate ΔT with egress = 0 (stories = ep_threshold_s - 1)
        dt_no_egress   = (project.dwelling_units * vpu * mob / eff_cap) * 60
        tier_no_egress = "CONDITIONAL MINISTERIAL" if dt_no_egress <= threshold else "DISCRETIONARY"
        target_stories = ep_threshold_s - 1

    # Current ΔT from step5
    current_dt = step5.get("max_delta_t_minutes", 0.0)

    return {
        "units_for_conditional":  units_for_conditional,
        "units_for_ministerial":  units_for_ministerial,
        "dt_option_a":            round(dt_a, 2) if dt_a is not None else None,
        "tier_option_a":          "CONDITIONAL MINISTERIAL" if (dt_a is not None and dt_a <= threshold) else "DISCRETIONARY",
        "has_egress_penalty":     stories >= ep_threshold_s,
        "dt_no_egress":           round(dt_no_egress, 2) if dt_no_egress is not None else None,
        "tier_no_egress":         tier_no_egress,
        "target_stories":         target_stories,
        "current_dt":             current_dt,
        "threshold":              threshold,
        "worst_eff_cap":          eff_cap,
        "mob":                    mob,
        "vpu":                    vpu,
    }


def _redesign_card_tier_badge(tier: str, tc: str, tbg: str) -> str:
    return f'<div class="redesign-tier-badge" style="background:{tbg};color:{tc};border:1px solid {tc};">{tier}</div>'


def _build_redesign_options(project, tier: str, step5: dict, config: dict, redesign: dict) -> str:
    if tier != "DISCRETIONARY" or not redesign:
        return ""

    tc  = _TIER_CSS_COLOR.get(tier, "#c0392b")
    units   = project.dwelling_units
    stories = getattr(project, "stories", 0)
    current_dt = redesign.get("current_dt", 0.0)
    threshold  = redesign.get("threshold", 6.0)

    unit_threshold = config.get("unit_threshold", 15)

    # Card A: reduce units → CONDITIONAL
    units_cond = redesign.get("units_for_conditional", 0)
    dt_a       = redesign.get("dt_option_a")
    tier_a     = redesign.get("tier_option_a", "DISCRETIONARY")
    tc_a = _TIER_CSS_COLOR.get(tier_a, "#555")
    tbg_a = _TIER_BG_COLOR.get(tier_a, "#f8f9fa")

    if units_cond > 0:
        card_a_dt = f'<div class="redesign-dt" style="color:{tc_a};">{dt_a:.1f} min</div>' if dt_a else ""
        card_a_status = f'<div class="redesign-dt-status" style="color:{tc_a};">{"✓ within threshold" if tier_a != "DISCRETIONARY" else "✗ still exceeds"}</div>'
        card_a_units_note = f"Reduce from {units} → <strong>{units_cond}</strong> units"
        card_a_stories_note = f"Stories unchanged ({stories})"
        card_class = "option-conditional" if tier_a != "DISCRETIONARY" else "current"
    else:
        dt_a_display = "—"
        card_a_dt = f'<div class="redesign-dt" style="color:#adb5bd;">{dt_a_display}</div>'
        card_a_status = '<div class="redesign-dt-status" style="color:#adb5bd;">Egress penalty alone exceeds threshold</div>'
        card_a_units_note = "Unit reduction alone is insufficient"
        card_a_stories_note = "Must also reduce height"
        card_class = "current"

    card_a_html = f"""<div class="redesign-card {card_class}">
  <div class="redesign-card-label">Option A — Reduce Units</div>
  {_redesign_card_tier_badge(tier_a, tc_a, tbg_a)}
  <div class="redesign-stat">{card_a_units_note}</div>
  <div class="redesign-stat">{card_a_stories_note}</div>
  {card_a_dt}
  {card_a_status}
</div>"""

    # Card B: reduce stories (only if egress penalty applies)
    has_egress = redesign.get("has_egress_penalty", False)
    if has_egress:
        target_s   = redesign.get("target_stories", 3)
        dt_b       = redesign.get("dt_no_egress")
        tier_b     = redesign.get("tier_no_egress", "DISCRETIONARY")
        tc_b  = _TIER_CSS_COLOR.get(tier_b, "#555")
        tbg_b = _TIER_BG_COLOR.get(tier_b, "#f8f9fa")
        card_b_dt  = f'<div class="redesign-dt" style="color:{tc_b};">{dt_b:.1f} min</div>' if dt_b else ""
        card_b_status = f'<div class="redesign-dt-status" style="color:{tc_b};">{"✓ within threshold" if tier_b != "DISCRETIONARY" else "✗ still exceeds (vehicle ΔT is the driver)"}</div>'

        card_b_html = f"""<div class="redesign-card {'option-conditional' if tier_b != 'DISCRETIONARY' else ''}">
  <div class="redesign-card-label">Option B — Reduce Stories</div>
  {_redesign_card_tier_badge(tier_b, tc_b, tbg_b)}
  <div class="redesign-stat">Reduce from {stories} → <strong>{target_s}</strong> stories</div>
  <div class="redesign-stat">Units unchanged ({units})</div>
  {card_b_dt}
  {card_b_status}
</div>"""
    else:
        card_b_html = f"""<div class="redesign-card" style="opacity:0.5;">
  <div class="redesign-card-label">Option B — Reduce Stories</div>
  <div style="font-size:11px;color:#6c757d;margin-top:8px;">
    Not applicable — this project is {stories} {'story' if stories==1 else 'stories'}, below the 4-story height
    threshold. Building egress penalty does not apply.
  </div>
</div>"""

    # Card C: MINISTERIAL (always ≤ unit_threshold - 1 units)
    units_min = redesign.get("units_for_ministerial", unit_threshold - 1)
    card_c_html = f"""<div class="redesign-card option-ministerial">
  <div class="redesign-card-label">Always Ministerial</div>
  {_redesign_card_tier_badge("MINISTERIAL", "#27ae60", "#f0faf4")}
  <div class="redesign-stat">Reduce to ≤ <strong>{units_min}</strong> units</div>
  <div class="redesign-stat">Standard 1 size gate not triggered</div>
  <div class="redesign-dt" style="color:#27ae60;">—</div>
  <div class="redesign-dt-status" style="color:#27ae60;">No analysis required</div>
</div>"""

    note = (
        "<p style='font-size:11px;color:#6c757d;margin:8px 0 0;'>"
        "These options are computed algebraically from the ΔT formula — no engineering judgment. "
        "They represent the minimum change at this location. Site redesign (alternate access, "
        "reduced footprint) or a different location may offer additional pathways."
        "</p>"
    )

    # Current design card (shown above the grid for context)
    current_card = f"""<div style="background:#fff;border:2px solid {tc};border-radius:8px;padding:14px 16px;margin-bottom:12px;display:flex;align-items:center;gap:20px;flex-wrap:wrap;">
  <div>
    <div style="font-size:9px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#868e96;margin-bottom:6px;">Current Design</div>
    <div class="redesign-tier-badge" style="background:{_TIER_BG_COLOR.get(tier,'#fdf2f2')};color:{tc};border:1px solid {tc};">{tier}</div>
  </div>
  <div style="flex:1;display:flex;gap:24px;flex-wrap:wrap;">
    <div><div style="font-size:10px;color:#868e96;margin-bottom:2px;">Units</div><div style="font-weight:700;">{units}</div></div>
    <div><div style="font-size:10px;color:#868e96;margin-bottom:2px;">Stories</div><div style="font-weight:700;">{stories}</div></div>
    <div><div style="font-size:10px;color:#868e96;margin-bottom:2px;">Max ΔT</div><div style="font-weight:700;color:{tc};">{current_dt:.2f} min</div></div>
    <div><div style="font-size:10px;color:#868e96;margin-bottom:2px;">Limit</div><div style="font-weight:700;">{threshold:.2f} min</div></div>
  </div>
</div>"""

    return f"""<div class="section-hdr">Redesign Options — Computed from ΔT Formula</div>
{current_card}
<div class="redesign-grid">
  {card_a_html}
  {card_b_html}
  {card_c_html}
</div>
{note}"""


# ---------------------------------------------------------------------------
# Section 4: Standards at-a-glance
# ---------------------------------------------------------------------------

def _build_standards_glance(tier, step1, step2, step3, step5, sb79) -> str:
    tc = _TIER_CSS_COLOR.get(tier, "#555")

    def _std_icon(result: bool | None, triggered: bool = False) -> str:
        if result is None:
            return '<span style="color:#adb5bd;">—</span>'
        if triggered:
            return '<span style="color:#c0392b;">⚠</span>'
        if result:
            return '<span style="color:#1a56db;">✓</span>'
        return '<span style="color:#adb5bd;">✗</span>'

    def _num_badge(n, cls):
        return f'<span class="std-num {cls}">{n}</span>'

    def _metric(txt, color="#495057"):
        return f'<span style="font-size:12px;color:{color};">{txt}</span>'

    unit_threshold = step2.get("threshold", 15)
    units = step2.get("dwelling_units", 0)
    scale_met = step2.get("result", False)
    std1_icon = _std_icon(scale_met)
    std1_result_txt = f"{units} units ≥ {unit_threshold} — IN SCOPE" if scale_met else f"{units} units < {unit_threshold} — NOT TRIGGERED"
    std1_color = "#1a56db" if scale_met else "#27ae60"

    route_count = step3.get("serving_paths_count", step3.get("serving_route_count", 0))
    radius = step3.get("radius_miles", 0.5)
    std2_icon = _std_icon(route_count > 0)
    std2_result_txt = f"{route_count} evacuation paths within {radius} mi"

    hz = step1.get("std3_hazard_zone", step5.get("hazard_zone", "non_fhsz"))
    fhsz_flagged = step1.get("std3_fhsz_flagged", False)
    hz_label = {
        "vhfhsz":        "Zone 3 — Very High",
        "high_fhsz":     "Zone 2 — High",
        "moderate_fhsz": "Zone 1 — Moderate",
        "non_fhsz":      "Non-FHSZ",
    }.get(hz, hz)
    deg_factors = {"vhfhsz": "0.35×", "high_fhsz": "0.50×", "moderate_fhsz": "0.75×", "non_fhsz": "1.00×"}
    std3_icon = _std_icon(True, triggered=fhsz_flagged)
    std3_result_txt = f"{hz_label} · road capacity degradation {deg_factors.get(hz,'1.00×')}"
    std3_color = "#c0392b" if fhsz_flagged else "#27ae60"

    max_dt    = step5.get("max_delta_t_minutes", 0.0)
    threshold = step5.get("threshold_minutes", 6.0)
    triggered_s4 = step5.get("triggered", False)
    std4_icon = _std_icon(True, triggered=triggered_s4)
    s4_color  = "#c0392b" if triggered_s4 else "#27ae60"
    std4_result_txt = (
        f"ΔT {max_dt:.2f} min vs {threshold:.2f} min limit — {'⚠ EXCEEDED' if triggered_s4 else '✓ within threshold'}"
        if tier != "MINISTERIAL" else
        "Not evaluated (below size threshold)"
    )

    sb79_tier = sb79.get("tier", "NOT_APPLICABLE")
    sb79_near = sb79.get("steps", {}).get("near_transit", False)
    std5_icon = _std_icon(None) if sb79_tier == "NOT_APPLICABLE" else _std_icon(sb79_near, triggered=False)
    std5_result_txt = "Informational only — does not affect tier"

    rows = [
        (1, "Project Size", "Size gate — units ≥ threshold", _num_badge(1, "passed" if scale_met else "na"),
         std1_icon, std1_result_txt, std1_color),
        (2, "Evacuation Routes", "Standard 2 — 0.5 mi proximity buffer", _num_badge(2, "passed"),
         std2_icon, std2_result_txt, "#1a56db"),
        (3, "FHSZ Zone", "Standard 3 — road capacity modifier", _num_badge(3, "triggered" if fhsz_flagged else "passed"),
         std3_icon, std3_result_txt, std3_color),
        (4, "ΔT Clearance Test", "Standard 4 — marginal clearance time", _num_badge(4, "triggered" if triggered_s4 else "passed"),
         std4_icon, std4_result_txt, s4_color),
        (5, "SB 79 Transit", "Standard 5 — transit proximity flag", _num_badge(5, "na"),
         std5_icon, std5_result_txt, "#868e96"),
    ]

    rows_html = ""
    for _, name, sub, badge, icon, metric_txt, mcolor in rows:
        rows_html += f"""<tr>
  <td style="width:32px;text-align:center;">{badge}</td>
  <td>
    <div style="font-weight:600;font-size:13px;">{name}</div>
    <div style="font-size:10px;color:#868e96;">{sub}</div>
  </td>
  <td style="width:24px;text-align:center;font-size:16px;">{icon}</td>
  <td style="color:{mcolor};font-size:12px;">{metric_txt}</td>
</tr>"""

    return f"""<div class="section-hdr">Standards at a Glance</div>
<table class="standards-table">
  <thead>
    <tr>
      <th style="width:32px;">Std</th>
      <th>Standard</th>
      <th style="width:24px;"></th>
      <th>Key Metric</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>"""


# ---------------------------------------------------------------------------
# Section 5: Legal authority chain
# ---------------------------------------------------------------------------

def _build_legal_chain(project, tier, step1, step5, config) -> str:
    hz = step5.get("hazard_zone", getattr(project, "hazard_zone", "non_fhsz"))
    tc = _TIER_CSS_COLOR.get(tier, "#555")

    hz_window = {
        "vhfhsz":        45,
        "high_fhsz":     90,
        "moderate_fhsz": 120,
        "non_fhsz":      120,
    }.get(hz, 120)
    hz_label_map = {
        "vhfhsz":        "Zone 3 (Very High FHSZ)",
        "high_fhsz":     "Zone 2 (High FHSZ)",
        "moderate_fhsz": "Zone 1 (Moderate FHSZ)",
        "non_fhsz":      "Non-FHSZ",
    }
    hz_label = hz_label_map.get(hz, hz)

    deg_map = {"vhfhsz": 0.35, "high_fhsz": 0.50, "moderate_fhsz": 0.75, "non_fhsz": 1.00}
    deg = deg_map.get(hz, 1.00)

    max_proj_share = config.get("max_project_share", 0.05)
    threshold = step5.get("threshold_minutes", hz_window * max_proj_share)

    mob = step5.get("mobilization_rate", config.get("mobilization_rate", 0.90))
    vpu = config.get("vehicles_per_unit", 2.5)
    units = project.dwelling_units
    project_veh = step5.get("project_vehicles", units * vpu * mob)
    egress = step5.get("egress_minutes", 0.0)
    max_dt = step5.get("max_delta_t_minutes", 0.0)

    # Find controlling path bottleneck stats
    path_results = step5.get("path_results", [])
    hcm_cap = 0
    eff_cap  = 0
    if path_results:
        worst = min(path_results, key=lambda r: r.get("bottleneck_effective_capacity_vph", 9999))
        hcm_cap = worst.get("bottleneck_hcm_capacity_vph", 0)
        eff_cap  = worst.get("bottleneck_effective_capacity_vph", 0)

    def _badge(color, label):
        return f'<span class="legal-src-badge" style="background:{color};">{label}</span>'

    if tier == "MINISTERIAL":
        # Simplified chain for below-threshold projects
        unit_threshold = config.get("unit_threshold", 15)
        rows_html = f"""
<tr>
  <td>1</td>
  <td>{_badge('#1c4a6e','AB 747')} AB 747 §65302.15</td>
  <td>Requires analysis for projects ≥ {unit_threshold} units in cities updating Safety Element</td>
  <td>Triggers this evaluation framework</td>
</tr>
<tr>
  <td>—</td>
  <td>{_badge('#27ae60','SIZE GATE')} Standard 1</td>
  <td>Project units ({units}) &lt; threshold ({unit_threshold})</td>
  <td>Analysis not required — size gate not met</td>
</tr>
<tr class="derived">
  <td>—</td>
  <td>Determination</td>
  <td>Size gate: {units} &lt; {unit_threshold}</td>
  <td style="color:#27ae60;">→ MINISTERIAL (no analysis required)</td>
</tr>"""
    else:
        fhsz_flagged = step1.get("std3_fhsz_flagged", False)
        fhsz_note = (
            f"GIS point-in-polygon → {hz_label}"
            if fhsz_flagged else
            f"GIS point-in-polygon → {hz_label} (no degradation)"
        )

        egress_row = ""
        ep_cfg = config.get("egress_penalty", {})
        ep_s = ep_cfg.get("threshold_stories", 4)
        stories = getattr(project, "stories", 0)
        if stories >= ep_s:
            min_per_story = ep_cfg.get("minutes_per_story", 1.5)
            max_ep = ep_cfg.get("max_minutes", 12)
            egress_row = f"""
<tr>
  <td>8</td>
  <td>{_badge('#7048e8','NFPA 101')} NFPA 101 / IBC</td>
  <td>Stair descent penalty ≥ 4 stories: min({stories} × {min_per_story}, {max_ep}) min</td>
  <td>Egress penalty = {egress:.1f} min added to ΔT</td>
</tr>"""

        dt_formula = f"({project_veh:.1f} / {eff_cap:.0f}) × 60 + {egress:.1f}" if egress > 0 else f"({project_veh:.1f} / {eff_cap:.0f}) × 60"

        rows_html = f"""
<tr>
  <td>1</td>
  <td>{_badge('#1c4a6e','AB 747')} AB 747 §65302.15</td>
  <td>Mandates evacuation route capacity analysis in Safety Element update</td>
  <td>Triggers this analysis</td>
</tr>
<tr>
  <td>2</td>
  <td>{_badge('#dc3545','CAL FIRE')} CAL FIRE FHSZ GIS</td>
  <td>{fhsz_note}</td>
  <td>Road capacity degradation factor: {deg:.2f}×</td>
</tr>
<tr>
  <td>3</td>
  <td>{_badge('#fd7e14','NIST')} NIST TN 2135</td>
  <td>Safe egress window for {hz_label}: {hz_window} min (Camp Fire timeline + 5 min WEA)</td>
  <td>Threshold numerator: {hz_window} min</td>
</tr>
<tr>
  <td>4</td>
  <td>{_badge('#868e96','POLICY')} max_project_share</td>
  <td>5% engineering significance threshold (standard)</td>
  <td>Threshold denominator: 5%</td>
</tr>
<tr class="derived">
  <td>—</td>
  <td>Derived threshold</td>
  <td>{hz_window} min × {max_proj_share:.0%}</td>
  <td style="color:{tc};">= {threshold:.2f} min (this location)</td>
</tr>
<tr>
  <td>5</td>
  <td>{_badge('#17a2b8','HCM 2022')} HCM 2022 Ex. 12-7</td>
  <td>Two-lane road HCM capacity table (by posted speed)</td>
  <td>HCM capacity: {hcm_cap:,.0f} vph</td>
</tr>
<tr>
  <td>6</td>
  <td>{_badge('#17a2b8','HCM 2022')} HCM Ex. 10-15/10-17</td>
  <td>{hz_label} fire zone degradation: {deg:.2f}× composite (visibility + incident factors)</td>
  <td>Effective capacity: {hcm_cap:,.0f} × {deg:.2f} = {eff_cap:,.0f} vph</td>
</tr>
<tr>
  <td>7</td>
  <td>{_badge('#7048e8','NFPA 101')} NFPA 101 Life Safety Code</td>
  <td>100% occupant evacuation design basis; 0.90 mob rate = {mob:.2f} (Census ACS B25044: ~10% zero-vehicle HH)</td>
  <td>{units} × {vpu} vpu × {mob:.2f} = {project_veh:.1f} project vehicles</td>
</tr>
{egress_row}
<tr class="derived">
  <td>—</td>
  <td>Derived ΔT</td>
  <td>{dt_formula} = {max_dt:.2f} min</td>
  <td style="color:{tc};">{max_dt:.2f} {'>' if max_dt > threshold else '≤'} {threshold:.2f} min → {tier}</td>
</tr>"""

    attestation = (
        "This determination applies the above authorities mechanically. "
        "No engineering judgment was exercised. Every value shown is either (a) directly "
        "read from a published source, (b) a geometric result of a GIS spatial query, "
        "or (c) a deterministic arithmetic computation from the above inputs."
    )

    return f"""<div class="section-hdr">Legal Authority Chain</div>
<table class="legal-table">
  <thead>
    <tr>
      <th style="width:28px;">#</th>
      <th style="width:200px;">Authority</th>
      <th>Provision / Data Used</th>
      <th>Value in This Determination</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
<div class="legal-attestation">{attestation}</div>"""


# ---------------------------------------------------------------------------
# Section 6: Conditions / Next steps
# ---------------------------------------------------------------------------

def _build_conditions_v2(tier: str, project, step5: dict, redesign: dict) -> str:
    tc = _TIER_CSS_COLOR.get(tier, "#555")
    egress = step5.get("egress_minutes", 0.0)
    max_dt = step5.get("max_delta_t_minutes", 0.0)
    threshold = step5.get("threshold_minutes", 6.0)
    vehicle_dt = max_dt - egress

    if tier == "MINISTERIAL":
        return f"""<div class="section-hdr">Next Steps</div>
<div class="conditions-box">
  <h3 style="color:#27ae60;">✓ Ministerial Approval Eligible</h3>
  <p style="margin:0;font-size:13px;color:#495057;">
    This project qualifies for ministerial approval under AB 747 §65302.15.
    Submit a standard building permit application. No environmental impact analysis
    related to evacuation route capacity is required for this project.
  </p>
</div>"""

    if tier == "CONDITIONAL MINISTERIAL":
        return f"""<div class="section-hdr">Required Conditions</div>
<div class="conditions-box">
  <h3 style="color:#d67c00;">Mandatory Evacuation Conditions</h3>
  <p style="margin:0 0 10px;font-size:13px;color:#495057;">
    Ministerial approval is available subject to these conditions of approval:
  </p>
  <ol>
    <li>Applicant shall record a notice to future purchasers disclosing the property's
        location within an evacuation analysis corridor and identifying the designated
        evacuation routes serving this parcel.</li>
    <li>Project shall provide resident-accessible evacuation route maps posted in common
        areas and included in the lease or CC&amp;R package.</li>
    <li>Applicant shall participate in any citywide evacuation monitoring program adopted
        pursuant to AB 747 within 24 months of this determination.</li>
    <li>This determination is conditioned on no material change to the serving evacuation
        route network. Any road closure, lane reduction, or capacity change affecting
        the bottleneck segment triggers re-evaluation.</li>
  </ol>
</div>"""

    # DISCRETIONARY — failure-mode specific conditions
    # Determine driving factor
    egress_is_driver = (egress > 0) and (vehicle_dt <= threshold)
    vehicle_is_driver = vehicle_dt > threshold
    both_contribute  = (egress > 0) and vehicle_is_driver

    if egress_is_driver:
        failure_tag = "BUILDING HEIGHT"
        failure_note = (
            f"The egress penalty ({egress:.1f} min) from this {getattr(project,'stories',0)}-story building "
            f"pushes ΔT above the {threshold:.2f} min threshold. Vehicle clearance alone "
            f"({vehicle_dt:.2f} min) is within the limit."
        )
        specific_steps = """<li><strong>Building height reduction:</strong> Redesign to ≤ 3 stories
        eliminates the NFPA 101 stair-descent egress penalty. Verify ΔT with reduced height
        using the ΔT formula above.</li>
      <li><strong>Stairwell performance improvement:</strong> Additional stairwells or wider
        egress paths may reduce the effective minutes-per-story penalty. Document with IBC
        egress analysis from a licensed fire protection engineer.</li>"""
    elif vehicle_is_driver and not both_contribute:
        failure_tag = "PROJECT SCALE"
        failure_note = (
            f"Vehicle clearance time ({vehicle_dt:.2f} min) exceeds the {threshold:.2f} min threshold. "
            f"No building egress penalty applies (building is {'below' if getattr(project,'stories',0) < 4 else 'at'} "
            f"the 4-story threshold)."
        )
        redesign_hint = ""
        if redesign:
            units_cond = redesign.get("units_for_conditional", 0)
            if units_cond > 0:
                redesign_hint = f" Algebraic minimum: reduce to ≤ {units_cond} units for CONDITIONAL MINISTERIAL."
        specific_steps = f"""<li><strong>Unit count reduction:</strong> Reduce dwelling unit count so that
        project vehicles / bottleneck effective capacity × 60 ≤ {threshold:.2f} min threshold.{redesign_hint}</li>
      <li><strong>Off-site evacuation route improvement:</strong> Demonstrate that a road widening,
        signal timing improvement, or contraflow lane on the controlling segment increases effective
        capacity such that project ΔT falls within threshold. Requires traffic engineering study.</li>"""
    else:
        failure_tag = "COMBINED: SCALE + HEIGHT"
        failure_note = (
            f"Both vehicle clearance ({vehicle_dt:.2f} min) and building egress ({egress:.1f} min) "
            f"contribute to the exceedance. Combined ΔT = {max_dt:.2f} min vs {threshold:.2f} min limit."
        )
        specific_steps = """<li><strong>Reduce units AND height:</strong> Either change alone may be
        insufficient. See Redesign Options above.</li>
      <li><strong>Traffic study for route improvement:</strong> If height reduction is not feasible,
        document an off-site capacity improvement that brings vehicle ΔT within threshold.</li>"""

    return f"""<div class="section-hdr">Required Next Steps</div>
<div class="conditions-box">
  <div class="failure-mode-tag">{failure_tag}</div>
  <h3 style="color:{tc};">Discretionary Review Required</h3>
  <p style="margin:0 0 10px;font-size:13px;color:#495057;">{failure_note}</p>
  <p style="font-size:13px;font-weight:600;margin:0 0 8px;">Required actions before any approval may be issued:</p>
  <ol>
    <li><strong>CEQA environmental review:</strong> Prepare and circulate an Initial Study /
      Mitigated Negative Declaration or full EIR addressing wildfire evacuation route impacts
      consistent with AB 747 §65302.15.</li>
    {specific_steps}
    <li><strong>Fire department review:</strong> Submit project to the local fire authority
      for review of fire apparatus access roads per IFC §503.</li>
    <li><strong>Public hearing required:</strong> Project may not be approved ministerially.
      A noticed public hearing before the planning commission or equivalent body is required.</li>
  </ol>
  <p style="font-size:11px;color:#868e96;margin:10px 0 0;">
    Ministerial approval may be available at this location if the project is redesigned
    to reduce ΔT to ≤ {threshold:.2f} min. See Redesign Options section above.
  </p>
</div>"""


# ---------------------------------------------------------------------------
# Appeal rights
# ---------------------------------------------------------------------------

def _build_appeal_rights(city_name: str) -> str:
    return f"""<div class="appeal-box">
  <strong>Appeal Rights:</strong>
  This determination is the result of a ministerial application of objective, algorithmic
  standards pursuant to AB 747. No planning discretion was exercised. Appeals must be filed
  within <strong>10 business days</strong> of this notice and must identify a specific factual
  error in the input data (e.g., incorrect road capacity, incorrect FHSZ boundary, incorrect
  unit count). Appeals based on disagreement with the methodology or policy thresholds are
  not within the scope of this proceeding.
  Contact {city_name} Planning Department for appeal procedures.
</div>"""


# ---------------------------------------------------------------------------
# Technical appendix (collapsible)
# ---------------------------------------------------------------------------

def _build_technical_appendix(tier: str, step3: dict, step5: dict, config: dict) -> str:
    if tier == "MINISTERIAL":
        return ""

    path_results = step5.get("path_results", [])
    threshold    = step5.get("threshold_minutes", 6.0)

    if not path_results:
        return ""

    # Sort: flagged first, then by ΔT descending
    sorted_paths = sorted(path_results, key=lambda r: (-int(r.get("flagged", False)), -r.get("delta_t_minutes", 0)))

    rows = ""
    for r in sorted_paths[:50]:  # cap at 50 rows
        flagged   = r.get("flagged", False)
        dt        = r.get("delta_t_minutes", 0.0)
        eff_cap   = r.get("bottleneck_effective_capacity_vph", 0)
        bn_name   = r.get("bottleneck_name", "") or str(r.get("bottleneck_osmid", ""))
        fhsz      = r.get("bottleneck_fhsz_zone", "")
        margin    = dt - threshold
        cls       = "flagged-row" if flagged else "ok-row"
        status    = "⚠ EXCEEDS" if flagged else "✓ ok"
        margin_str = f"+{margin:.2f}" if margin > 0 else f"{margin:.2f}"
        rows += f"""<tr class="{cls}">
  <td>{bn_name}</td>
  <td style="text-align:right;">{eff_cap:,.0f}</td>
  <td style="text-align:right;">{dt:.2f}</td>
  <td style="text-align:right;">{threshold:.2f}</td>
  <td style="text-align:right;">{margin_str}</td>
  <td>{status}</td>
</tr>"""

    n_total = len(path_results)
    n_shown = min(n_total, 50)
    overflow = f'<p style="font-size:10px;color:#6c757d;margin-top:6px;">Showing {n_shown} of {n_total} paths.</p>' if n_total > 50 else ""

    # Parameters block
    mob = config.get("mobilization_rate", 0.90)
    vpu = config.get("vehicles_per_unit", 2.5)
    ep  = config.get("egress_penalty", {})
    safe_window = config.get("safe_egress_window", {})
    mps = config.get("max_project_share", 0.05)

    params_html = f"""<div style="margin-top:16px;">
  <div style="font-size:11px;font-weight:700;color:#495057;margin-bottom:6px;letter-spacing:0.8px;text-transform:uppercase;">Parameters</div>
  <div class="code-block">ΔT formula: (project_vehicles / bottleneck_effective_capacity_vph) × 60 + egress_penalty
project_vehicles = units × {vpu} vpu × {mob:.2f} mob (NFPA 101 constant)
egress_penalty   = 0 if stories &lt; {ep.get('threshold_stories',4)}; else min(stories × {ep.get('minutes_per_story',1.5)}, {ep.get('max_minutes',12)}) min
threshold        = safe_egress_window[hazard_zone] × {mps:.0%} (max_project_share)

safe_egress_window:
  vhfhsz:        {safe_window.get('vhfhsz',45)} min   (NIST TN 2135 Camp Fire)
  high_fhsz:     {safe_window.get('high_fhsz',90)} min  (NIST TN 2135)
  moderate_fhsz: {safe_window.get('moderate_fhsz',120)} min (NIST TN 2135)
  non_fhsz:      {safe_window.get('non_fhsz',120)} min (FEMA emergency planning)

hazard_degradation factors (HCM 2022 Ex. 10-15/10-17 + NIST Camp Fire validation):
  vhfhsz: 0.35×  high_fhsz: 0.50×  moderate_fhsz: 0.75×  non_fhsz: 1.00×</div>
</div>"""

    return f"""<div class="section-hdr">Technical Record</div>
<details class="tech-appendix">
  <summary>▸ Full Path Results &amp; Parameters</summary>
  <div class="tech-inner">
    <table class="mini-table">
      <thead>
        <tr>
          <th>Controlling Segment</th>
          <th style="text-align:right;">Eff. Cap (vph)</th>
          <th style="text-align:right;">ΔT (min)</th>
          <th style="text-align:right;">Limit (min)</th>
          <th style="text-align:right;">Margin</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    {overflow}
    {params_html}
  </div>
</details>"""


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def _build_footer(case_num: str) -> str:
    return f"""<div class="brief-footer">
  JOSH v3.2 · California Stewardship Alliance · Case {case_num}<br>
  Generated {datetime.date.today().isoformat()} · AB 747 §65302.15 · ΔT Standard
</div>"""

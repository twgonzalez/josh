# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
HTML popup and marker popup builders for the demo map.

v3.0 ΔT Standard: all route popups show effective_capacity_vph and ΔT clearance
time rather than v/c ratios. v/c and LOS remain informational footnotes only.

Popup A/B/C structure (mirrors brief_v3 determination letter):
  A — Applicability Threshold (15-unit size gate)
  B — Site Parameters (FHSZ zone, degradation, threshold)
  C — Evacuation Clearance Analysis (routes + ΔT test — operative step)
  SB 79 — informational only, no tier impact (footnote)
"""
from models.project import Project
from .themes import _TIER_CSS_COLOR, _TIER_BG_COLOR


# ---------------------------------------------------------------------------
# Popup action labels — mirrors determination brief language
# ---------------------------------------------------------------------------

_POPUP_ACTION_LABELS = {
    "DISCRETIONARY":           "Planning Commission review required",
    "MINISTERIAL WITH STANDARD CONDITIONS": "Ministerial approval — standard conditions apply automatically",
    "MINISTERIAL":             "Over-the-counter — below size threshold",
}

_HAZARD_ZONE_SAFE_WINDOW = {
    "vhfhsz":        45,
    "high_fhsz":     90,
    "moderate_fhsz": 120,
    "non_fhsz":      120,
}

_HAZARD_ZONE_DEG = {
    "vhfhsz":        0.35,
    "high_fhsz":     0.50,
    "moderate_fhsz": 0.75,
    "non_fhsz":      1.00,
}

_HAZARD_ZONE_FULL_LABEL = {
    "vhfhsz":        "Zone 3 — Very High FHSZ",
    "high_fhsz":     "Zone 2 — High FHSZ",
    "moderate_fhsz": "Zone 1 — Moderate FHSZ",
    "non_fhsz":      "Non-FHSZ",
}


# ---------------------------------------------------------------------------
# ΔT bar widget — v3.0
# ---------------------------------------------------------------------------

def _delta_t_bar_html(delta_t: float, threshold: float, height_px: int = 10) -> str:
    """
    HTML progress bar showing ΔT position relative to its threshold.

    The threshold tick is pinned at THRESHOLD_LINE_PCT (60%) of bar width,
    matching the mini-bar scale. Bars exceeding the threshold extend past
    the tick; bars within it stop short.
    Color: green (< 50%), yellow (50–75%), orange (75–100%), red (> 100%).
    """
    if threshold <= 0:
        threshold = 10.0

    THRESHOLD_LINE_PCT = 60  # matches _multi_path_bars_html scale

    ratio = delta_t / threshold
    pct   = min(ratio * THRESHOLD_LINE_PCT, 100)

    if ratio >= 1.0:
        bar_color = "#dc3545"   # red — exceeded
    elif ratio >= 0.75:
        bar_color = "#fd7e14"   # orange — approaching
    elif ratio >= 0.50:
        bar_color = "#ffc107"   # yellow — moderate
    else:
        bar_color = "#28a745"   # green — comfortable

    tick_h = height_px + 6

    return (
        f'<div style="position:relative; background:#e9ecef; border-radius:4px; '
        f'height:{height_px}px; overflow:visible; margin:4px 0 10px;">'
        f'<div style="position:absolute; left:{THRESHOLD_LINE_PCT}%; top:-3px; '
        f'width:2px; height:{tick_h}px; background:#6c757d; z-index:2;"></div>'
        f'<div style="width:{pct:.1f}%; background:{bar_color}; height:100%; '
        f'border-radius:4px; position:relative; z-index:1;"></div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Multi-path mini bar chart — popup C section
# ---------------------------------------------------------------------------

def _multi_path_bars_html(
    dt_results: list,
    threshold: float,
    show_max: int = 6,
) -> str:
    """
    Mini per-path bar chart for the project popup.

    One row per unique bottleneck name (deduped, highest ΔT wins).
    Sorted ΔT descending. Up to show_max rows; remainder noted in footer.

    The threshold reference line is pinned at THRESHOLD_LINE_PCT of the bar
    width. Bars that exceed the threshold visibly extend past the line;
    bars within it stop short. A legend below labels the tick value.

    Returns empty string if dt_results is empty or threshold <= 0.
    """
    if not dt_results or threshold <= 0:
        return ""

    # Threshold line sits at this percentage of bar width.
    # Bars fill: min(dt / threshold × THRESHOLD_LINE_PCT, 100)%.
    # A bar at exactly the threshold reaches the tick; beyond it, goes right.
    THRESHOLD_LINE_PCT = 60

    # Deduplicate by bottleneck name — keep highest ΔT per name
    seen: dict[str, dict] = {}
    for r in dt_results:
        name = str(r.get("bottleneck_name", "") or r.get("bottleneck_osmid", ""))
        if not name:
            continue
        if name not in seen or r.get("delta_t_minutes", 0) > seen[name].get("delta_t_minutes", 0):
            seen[name] = r

    if not seen:
        return ""

    sorted_rows = sorted(seen.values(), key=lambda r: r.get("delta_t_minutes", 0), reverse=True)
    n_total   = len(sorted_rows)
    n_flagged = sum(1 for r in sorted_rows if r.get("flagged"))

    hdr_clr = "#c0392b" if n_flagged > 0 else "#27ae60"
    if n_flagged > 0:
        hdr_txt = (
            f"{n_flagged} of {n_total} path{'s' if n_total != 1 else ''} "
            f"exceed threshold"
        )
    else:
        hdr_txt = f"All {n_total} path{'s' if n_total != 1 else ''} within limit"

    html = (
        f'<div style="margin-top:6px; padding-top:6px; border-top:1px solid #f1f3f5;">'
        f'<div style="font-size:9px; font-weight:700; color:{hdr_clr}; margin-bottom:4px;">'
        f'{hdr_txt}</div>'
    )

    shown = sorted_rows[:show_max]
    extra = sorted_rows[show_max:]

    for r in shown:
        name    = str(r.get("bottleneck_name", "") or r.get("bottleneck_osmid", ""))
        dt      = r.get("delta_t_minutes", 0)
        flagged = r.get("flagged", False)
        nm_str  = (name[:22] + "…") if len(name) > 22 else name
        bar_pct = min((dt / threshold) * THRESHOLD_LINE_PCT, 100)
        bar_clr = "#c0392b" if flagged else "#27ae60"
        icon    = "⚠" if flagged else "✓"
        html += (
            f'<div style="display:flex; align-items:center; gap:5px; margin-bottom:3px;">'
            f'<div style="font-size:9px; color:#555; width:80px; flex-shrink:0; overflow:hidden; '
            f'text-overflow:ellipsis; white-space:nowrap;">{nm_str}</div>'
            # bar container — overflow:visible so the threshold tick can extend above/below
            f'<div style="flex:1; position:relative; height:6px; background:#e9ecef; '
            f'border-radius:3px; overflow:visible;">'
            f'<div style="width:{bar_pct:.0f}%; height:100%; background:{bar_clr}; '
            f'border-radius:3px; position:relative; z-index:1;"></div>'
            # threshold reference tick
            f'<div style="position:absolute; left:{THRESHOLD_LINE_PCT}%; top:-4px; '
            f'width:2px; height:14px; background:#888; border-radius:1px; z-index:2;"></div>'
            f'</div>'
            f'<div style="font-size:9px; color:{bar_clr}; font-weight:600; width:44px; '
            f'flex-shrink:0; text-align:right;">{dt:.1f}&nbsp;{icon}</div>'
            f'</div>'
        )

    if extra:
        extra_flagged = sum(1 for r in extra if r.get("flagged"))
        extra_within  = len(extra) - extra_flagged
        if extra_flagged == 0:
            extra_txt = f"+ {len(extra)} more — all within limit"
        else:
            extra_txt = f"+ {len(extra)} more ({extra_flagged} exceed, {extra_within} within)"
        html += (
            f'<div style="font-size:8px; color:#adb5bd; margin-top:2px;">{extra_txt}</div>'
        )

    # Legend: label the threshold tick
    html += (
        f'<div style="display:flex; align-items:center; gap:3px; margin-top:4px; '
        f'padding-left:85px;">'
        f'<div style="width:2px; height:9px; background:#888; border-radius:1px; '
        f'flex-shrink:0;"></div>'
        f'<span style="font-size:8px; color:#999;">{threshold:.1f} min limit</span>'
        f'</div>'
    )

    html += "</div>"
    return html


# ---------------------------------------------------------------------------
# Route ΔT popup — v3.0 (serving route segments on per-project layer)
# ---------------------------------------------------------------------------

_ROAD_TYPE_LABELS = {
    "freeway":   "Freeway",
    "multilane": "Multi-lane highway",
    "two_lane":  "Two-lane highway",
}


def _build_route_delta_t_popup(
    name_str: str,
    eff_cap: float,
    hcm_cap: float,
    fhsz_zone: str,
    hazard_degradation: float,
    delta_t_result: "dict | None",
    is_flagged: bool,
    road_type: str = "",
    lane_count: int = 0,
    speed_limit: int = 0,
) -> str:
    """
    Popup shown when clicking a serving route segment on the per-project layer.

    If this segment is the bottleneck of a ΔT-evaluated path (delta_t_result
    is not None), the full ΔT formula is shown. Otherwise the segment is shown
    as an analysis footprint with its effective capacity.

    Replaces _build_route_impact_popup() from v2.0.
    """
    if is_flagged and delta_t_result:
        status_color = "#c0392b"
        status_icon  = "⚠"
        status_text  = (
            f"ΔT threshold exceeded — "
            f"{delta_t_result['delta_t_minutes']:.2f} min "
            f"&gt; {delta_t_result['threshold_minutes']:.2f} min limit"
        )
    elif delta_t_result:
        ratio = (delta_t_result["delta_t_minutes"] /
                 max(delta_t_result["threshold_minutes"], 0.001))
        if ratio >= 0.75:
            status_color = "#e67e22"
            status_icon  = "◑"
        else:
            status_color = "#27ae60"
            status_icon  = "✓"
        status_text = (
            f"ΔT within threshold — "
            f"{delta_t_result['delta_t_minutes']:.2f} min "
            f"of {delta_t_result['threshold_minutes']:.2f} min limit"
        )
    else:
        status_color = "#868e96"
        status_icon  = "—"
        status_text  = "Serving route — not a bottleneck segment for this project"

    # Hazard zone label
    _zone_labels = {
        "vhfhsz":       "Very High FHSZ",
        "high_fhsz":    "High FHSZ",
        "moderate_fhsz": "Moderate FHSZ",
        "non_fhsz":     "Non-FHSZ",
    }
    zone_label = _zone_labels.get(str(fhsz_zone or "non_fhsz"), str(fhsz_zone))
    deg_pct    = f"{hazard_degradation * 100:.0f}%"

    # Road classification row — enables HCM table lookup verification
    rt_label   = _ROAD_TYPE_LABELS.get(road_type, road_type)
    rt_parts   = [rt_label] if rt_label else []
    if speed_limit: rt_parts.append(f"{speed_limit} mph")
    if lane_count:  rt_parts.append(f"{lane_count} lanes")
    rt_str = " · ".join(rt_parts)
    road_class_row = (
        f'<tr><td style="padding:2px 0;color:#868e96;">Road classification</td>'
        f'<td style="text-align:right;color:#868e96;">{rt_str}</td></tr>'
    ) if rt_str else ""

    capacity_rows = (
        '<table style="width:100%; border-collapse:collapse; font-size:11px; '
        'color:#555; margin-bottom:10px;">'
        + road_class_row
        + f'<tr><td style="padding:2px 0;">HCM raw capacity</td>'
        f'<td style="text-align:right; font-weight:600;">{hcm_cap:.0f} vph</td></tr>'
        f'<tr><td style="padding:2px 0;">Hazard zone</td>'
        f'<td style="text-align:right; font-weight:600; color:#555;">{zone_label}</td></tr>'
        f'<tr><td style="padding:2px 0;">Degradation factor</td>'
        f'<td style="text-align:right; font-weight:600;">{deg_pct} of HCM</td></tr>'
        f'<tr><td style="padding:2px 0; font-weight:700; color:#212529;">'
        f'Effective capacity</td>'
        f'<td style="text-align:right; font-weight:700; color:#1c4a6e;">'
        f'{eff_cap:.0f} vph</td></tr>'
        '</table>'
    )

    if delta_t_result:
        dt       = delta_t_result["delta_t_minutes"]
        thr      = delta_t_result["threshold_minutes"]
        pveh     = delta_t_result.get("project_vehicles", 0)
        egr      = delta_t_result.get("egress_minutes", 0)
        mob      = delta_t_result.get("mobilization_rate", 0.90)
        hz       = delta_t_result.get("hazard_zone", "non_fhsz")
        safe_win = delta_t_result.get("safe_egress_window_minutes", 120.0)
        max_shr  = delta_t_result.get("max_project_share", 0.05)
        margin   = dt - thr
        margin_color = "#c0392b" if margin > 0 else "#27ae60"
        margin_str   = f"+{margin:.2f} min over" if margin > 0 else f"−{abs(margin):.2f} min remaining"
        delta_t_rows = (
            f'<div style="font-weight:700; font-size:11px; color:#444; margin-bottom:2px;">'
            f'ΔT = {dt:.2f} min &nbsp;'
            f'<span style="font-weight:400; color:#868e96;">(limit {thr:.2f} min)</span>'
            f'&nbsp;<span style="font-weight:600; color:{margin_color}; font-size:10px;">'
            f'{margin_str}</span>'
            f'</div>'
            f'{_delta_t_bar_html(dt, thr)}'
            f'<div style="font-size:9px; color:#868e96; margin:-6px 0 8px;">'
            f'Limit: {thr:.2f} min = {safe_win:.0f} min safe egress &times; {max_shr*100:.0f}% '
            f'project share <span style="font-size:8px;">(NIST TN 2135)</span></div>'
            '<table style="width:100%; border-collapse:collapse; font-size:10px; '
            'color:#666; margin-bottom:8px;">'
            f'<tr><td style="padding:1px 0;">Mob rate (NFPA 101 constant)</td>'
            f'<td style="text-align:right;">{mob:.0%}</td></tr>'
            f'<tr><td style="padding:1px 0;">Project vehicles</td>'
            f'<td style="text-align:right;">{pveh:.1f} vph</td></tr>'
            f'<tr><td style="padding:1px 0;">Vehicle ΔT</td>'
            f'<td style="text-align:right;">{(pveh / max(eff_cap, 1)) * 60:.2f} min</td></tr>'
            + (
                f'<tr><td style="padding:1px 0;">Egress penalty</td>'
                f'<td style="text-align:right;">+{egr:.1f} min</td></tr>'
                if egr > 0 else ""
            )
            + '</table>'
        )
    else:
        delta_t_rows = (
            '<div style="font-size:10px; color:#868e96; font-style:italic; '
            'margin-bottom:8px;">Select a project to see ΔT impact on this route.</div>'
        )

    return (
        '<div style="font-family:system-ui,-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',sans-serif; font-size:12px; min-width:300px; max-width:350px; '
        'color:#333; line-height:1.5;">'
        f'<div style="font-weight:700; font-size:13px; margin-bottom:4px; color:#111;">'
        f'{name_str[:45]}</div>'
        f'<div style="color:{status_color}; font-weight:600; font-size:11px; '
        f'margin-bottom:10px;">{status_icon} {status_text}</div>'
        + capacity_rows
        + delta_t_rows
        + f'<div style="border-top:1px solid #dee2e6; padding-top:6px; '
        f'font-size:10px; color:#868e96;">'
        f'ΔT = (project vehicles ÷ effective capacity) × 60 + egress penalty<br>'
        f'Sources: HCM 2022 (capacity) · NFPA 101 (mob rate) · '
        f'NFPA 101/IBC (egress) · NIST TN 2135 (safe egress window)'
        f'</div>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Heatmap baseline popup — v3.0 (citywide evacuation capacity layer)
# ---------------------------------------------------------------------------

def _build_heatmap_route_popup(
    name_str: str,
    eff_cap: float,
    hcm_cap: float,
    fhsz_zone: str,
    hazard_degradation: float,
    vc_base: float,
    los: str,
    road_type: str = "",
    lane_count: int = 0,
    speed_limit: int = 0,
) -> str:
    """
    Popup shown when clicking an evacuation route segment on the heatmap base
    layer. Shows effective_capacity_vph as the primary metric — the actual
    bottleneck capacity used in the ΔT formula.

    v/c and LOS are shown as informational footnotes.
    """
    _zone_labels = {
        "vhfhsz":        "Very High FHSZ",
        "high_fhsz":     "High FHSZ",
        "moderate_fhsz": "Moderate FHSZ",
        "non_fhsz":      "Non-FHSZ",
    }
    zone_label = _zone_labels.get(str(fhsz_zone or "non_fhsz"), str(fhsz_zone))
    deg_pct    = f"{hazard_degradation * 100:.0f}%"

    if eff_cap < 350:
        status_color = "#c0392b"
        status_icon  = "⚠"
        status_text  = f"Severely constrained — {eff_cap:.0f} vph effective"
    elif eff_cap < 700:
        status_color = "#e67e22"
        status_icon  = "◑"
        status_text  = f"Low capacity — {eff_cap:.0f} vph effective"
    elif eff_cap < 1200:
        status_color = "#e0a800"
        status_icon  = "◔"
        status_text  = f"Moderate capacity — {eff_cap:.0f} vph effective"
    else:
        status_color = "#27ae60"
        status_icon  = "✓"
        status_text  = f"Ample capacity — {eff_cap:.0f} vph effective"

    # Road classification row — enables HCM table lookup verification
    rt_label_h  = _ROAD_TYPE_LABELS.get(road_type, road_type)
    rt_parts_h  = [rt_label_h] if rt_label_h else []
    if speed_limit: rt_parts_h.append(f"{speed_limit} mph")
    if lane_count:  rt_parts_h.append(f"{lane_count} lanes")
    rt_str_h = " · ".join(rt_parts_h)
    road_class_row_h = (
        f'<tr><td style="padding:2px 0;color:#868e96;">Road classification</td>'
        f'<td style="text-align:right;color:#868e96;">{rt_str_h}</td></tr>'
    ) if rt_str_h else ""

    return (
        '<div style="font-family:system-ui,-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',sans-serif; font-size:12px; min-width:280px; max-width:340px; '
        'color:#333; line-height:1.5;">'
        f'<div style="font-weight:700; font-size:13px; margin-bottom:4px; color:#111;">'
        f'{name_str[:45]}</div>'
        f'<div style="color:{status_color}; font-weight:600; font-size:11px; '
        f'margin-bottom:10px;">{status_icon} {status_text}</div>'
        '<table style="width:100%; border-collapse:collapse; font-size:11px; '
        'color:#555; margin-bottom:8px;">'
        + road_class_row_h
        + f'<tr><td style="padding:2px 0;">HCM raw capacity</td>'
        f'<td style="text-align:right; font-weight:600;">{hcm_cap:.0f} vph</td></tr>'
        f'<tr><td style="padding:2px 0;">Hazard zone</td>'
        f'<td style="text-align:right; font-weight:600;">{zone_label}</td></tr>'
        f'<tr><td style="padding:2px 0;">Degradation factor</td>'
        f'<td style="text-align:right; font-weight:600;">{deg_pct} of HCM</td></tr>'
        f'<tr><td style="padding:2px 0; font-weight:700; color:#212529;">'
        f'Effective capacity</td>'
        f'<td style="text-align:right; font-weight:700; color:#1c4a6e;">'
        f'{eff_cap:.0f} vph</td></tr>'
        '</table>'
        f'<div style="border-top:1px solid #dee2e6; padding-top:6px; '
        f'font-size:10px; color:#868e96;">'
        f'v/c {vc_base:.3f} &nbsp;|&nbsp; LOS {los} &nbsp;(informational — not used in ΔT determination)'
        f'<br>Select a project to see ΔT clearance time impact'
        f'</div>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Demo map project marker popup — A/B/C structure (mirrors brief_v3)
# ---------------------------------------------------------------------------

def _build_demo_project_popup(
    project: Project,
    proj_color: str,
    vc_threshold: float,
    unit_threshold: int = 15,
    worst_wildland_route: "dict | None" = None,
    worst_local_route: "dict | None" = None,
    ld_tier: str = "NOT_APPLICABLE",
    ld_triggered: bool = False,
) -> str:
    """Popup shown when clicking a project marker on the demo map.

    Mirrors the determination brief (brief_v3) A/B/C criteria structure:
      Hero    — verdict + plain-English action label (city planner first)
      Finding — controlling finding (plain-English outcome, mirrors brief)
      C       — Evacuation Clearance Analysis (ΔT gauge + multi-path bars)
      A + B   — compact screening strip (size gate + site parameters)
      SB 79   — footnote (informational only, no tier impact)
    """
    det       = project.determination or "UNKNOWN"
    det_color = _TIER_CSS_COLOR.get(det, "#555")
    bg_color  = _TIER_BG_COLOR.get(det, "#fafafa")

    action_label = _POPUP_ACTION_LABELS.get(det, "")
    met_size     = project.meets_size_threshold
    hazard_zone  = project.hazard_zone or "non_fhsz"

    # Zone label for hero subtitle
    if project.in_fire_zone:
        zone_label = _HAZARD_ZONE_FULL_LABEL.get(hazard_zone, hazard_zone)
    else:
        zone_label = "Non-FHSZ"

    # ── ΔT summary ────────────────────────────────────────────────────────
    dt_results = project.delta_t_results or []
    max_dt     = 0.0
    threshold  = 0.0
    if dt_results:
        max_dt    = max(r.get("delta_t_minutes", 0) for r in dt_results)
        threshold = dt_results[0].get("threshold_minutes", 0.0)
    if threshold <= 0:
        safe_win  = _HAZARD_ZONE_SAFE_WINDOW.get(hazard_zone, 120)
        threshold = safe_win * 0.05

    # ── Controlling Finding ───────────────────────────────────────────────
    if not met_size:
        finding_html = (
            f'<div style="border-left:3px solid {det_color}; background:#fafbfc; '
            f'padding:7px 12px; margin:0;">'
            f'<div style="font-size:9px; font-weight:700; letter-spacing:1.1px; '
            f'text-transform:uppercase; color:{det_color}; margin-bottom:3px;">'
            f'Controlling Finding</div>'
            f'<div style="font-size:11px; color:#333; line-height:1.45;">'
            f'{project.dwelling_units} units — below {unit_threshold}-unit threshold. '
            f'No capacity analysis required.'
            f'</div></div>'
        )
    elif worst_wildland_route:
        dt_wc  = worst_wildland_route.get("delta_t_minutes", 0.0)
        thr_wc = worst_wildland_route.get("threshold_minutes", threshold)
        nm_wc  = str(worst_wildland_route.get("name", "bottleneck segment") or "")[:38]
        if worst_wildland_route.get("flagged"):
            ratio    = dt_wc / max(thr_wc, 0.001)
            margin   = dt_wc - thr_wc
            body_str = (
                f"{nm_wc} adds <strong>{dt_wc:.1f} min</strong> — "
                f"{ratio:.1f}&times; the {thr_wc:.2f}-min limit "
                f"(exceeds by {margin:.1f} min)"
            )
        else:
            pct      = (dt_wc / max(thr_wc, 0.001)) * 100
            body_str = (
                f"All paths within limit — worst case: {nm_wc} at {dt_wc:.1f} min "
                f"({pct:.0f}% of {thr_wc:.2f}-min limit)"
            )
        finding_html = (
            f'<div style="border-left:3px solid {det_color}; background:#fafbfc; '
            f'padding:7px 12px; margin:0;">'
            f'<div style="font-size:9px; font-weight:700; letter-spacing:1.1px; '
            f'text-transform:uppercase; color:{det_color}; margin-bottom:3px;">'
            f'Controlling Finding</div>'
            f'<div style="font-size:11px; color:#333; line-height:1.45;">'
            f'{body_str}</div></div>'
        )
    else:
        finding_html = ""

    # ── Criterion C: status chip ──────────────────────────────────────────
    if not met_size:
        c_chip_label, c_chip_bg, c_chip_fg = "— NOT EVALUATED", "#f1f3f5", "#868e96"
    elif project.capacity_exceeded:
        c_chip_label, c_chip_bg, c_chip_fg = "⚠ EXCEEDS THRESHOLD", "#fff3cd", "#856404"
    else:
        c_chip_label, c_chip_bg, c_chip_fg = "✓ WITHIN THRESHOLD", "#e8f5e9", "#27ae60"

    # ── Criterion C: content (ΔT gauge + multi-path bars or placeholder) ──
    if met_size and dt_results:
        max_dt_clr  = det_color if project.capacity_exceeded else "#27ae60"
        worst_name  = str((worst_wildland_route or {}).get("name", "") or "")[:32]
        worst_dt_v  = (worst_wildland_route or {}).get("delta_t_minutes", max_dt)
        worst_line  = (
            f'<div style="font-size:10px; color:#555; margin-bottom:4px;">'
            f'Worst path: <strong>{worst_name}</strong> — {worst_dt_v:.1f} min'
            f'</div>'
        ) if worst_name else ""

        c_content = (
            f'<div style="font-size:13px; font-weight:700; color:{max_dt_clr}; '
            f'margin-bottom:2px;">{max_dt:.1f} min &nbsp;'
            f'<span style="font-size:10px; font-weight:400; color:#868e96;">'
            f'/ {threshold:.2f} min limit</span></div>'
            + _delta_t_bar_html(max_dt, threshold, height_px=14)
            + worst_line
            + _multi_path_bars_html(dt_results, threshold)
        )
    else:
        c_content = (
            '<div style="font-size:10px; color:#adb5bd; font-style:italic; '
            'padding:6px 0;">— Not evaluated — size threshold not met</div>'
        )

    # ── Criterion A: applicability ────────────────────────────────────────
    if met_size:
        a_badge_bg = "#1a56db"
        a_scope    = "IN SCOPE"
        a_text     = f"{project.dwelling_units} &ge; {unit_threshold} units &nbsp;&middot;&nbsp; {a_scope}"
    else:
        a_badge_bg = "#868e96"
        a_scope    = "OUT OF SCOPE"
        a_text     = f"{project.dwelling_units} &lt; {unit_threshold} units &nbsp;&middot;&nbsp; {a_scope}"

    # ── Criterion B: site parameters ──────────────────────────────────────
    hz_full    = _HAZARD_ZONE_FULL_LABEL.get(hazard_zone, hazard_zone)
    deg_factor = _HAZARD_ZONE_DEG.get(hazard_zone, 1.0)
    deg_str    = f"{deg_factor:.2f}&times; capacity" if deg_factor < 1.0 else "no road degradation"
    b_badge_bg = "#c0392b" if project.in_fire_zone else "#6c757d"

    if met_size and threshold > 0:
        b_text = f"{hz_full} &nbsp;&middot;&nbsp; {deg_str} &nbsp;&middot;&nbsp; {threshold:.2f} min limit"
    else:
        b_text = f"{hz_full} &nbsp;&middot;&nbsp; {deg_str}"

    def _criterion_badge(letter: str, bg: str) -> str:
        return (
            f'<span style="display:inline-flex; align-items:center; justify-content:center; '
            f'width:16px; height:16px; border-radius:3px; font-size:9px; font-weight:800; '
            f'color:#fff; background:{bg}; flex-shrink:0; margin-right:5px;">{letter}</span>'
        )

    def _ab_row(badge_html: str, text: str) -> str:
        return (
            f'<div style="display:flex; align-items:flex-start; gap:4px; '
            f'font-size:10px; color:#6c757d; margin-bottom:3px; line-height:1.4;">'
            + badge_html
            + f'<span>{text}</span></div>'
        )

    # ── Assemble final HTML ────────────────────────────────────────────────
    hero = (
        f'<div style="background:{bg_color}; margin:-14px -16px 0; '
        f'padding:10px 14px; border-radius:8px 8px 0 0; '
        f'border-bottom:1px solid #dee2e6;">'
        f'<div style="font-size:16px; font-weight:800; color:{det_color};">{det}</div>'
        f'<div style="font-size:11px; font-style:italic; color:{det_color}; '
        f'opacity:0.85; margin-top:1px;">{action_label}</div>'
        f'<div style="font-size:10px; color:#555; margin-top:3px;">'
        f'{project.project_name or "Project"} &nbsp;&middot;&nbsp; '
        f'{project.dwelling_units} units &nbsp;&middot;&nbsp; {zone_label}'
        f'</div></div>'
    )

    section_c = (
        f'<div style="padding:8px 14px 6px;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; '
        f'margin-bottom:6px;">'
        f'<span style="font-size:10px; font-weight:700; color:#343a40;">'
        + _criterion_badge("C", "#c0392b")
        + f'Evacuation Clearance Analysis</span>'
        + f'<span style="padding:2px 8px; border-radius:9px; font-size:9px; font-weight:700; '
        f'background:{c_chip_bg}; color:{c_chip_fg}; white-space:nowrap;">'
        f'{c_chip_label}</span></div>'
        + c_content
        + '</div>'
    )

    section_ab = (
        f'<div style="background:#f8f9fa; padding:6px 14px 5px; '
        f'border-top:1px solid #e9ecef;">'
        + _ab_row(_criterion_badge("A", a_badge_bg), a_text)
        + _ab_row(_criterion_badge("B", b_badge_bg), b_text)
        + '</div>'
    )

    footnote = (
        f'<div style="font-size:9px; color:#adb5bd; padding:4px 14px 6px; '
        f'border-top:1px solid #f1f3f5;">'
        f'SB 79 transit proximity: N/A &nbsp;&mdash;&nbsp; informational only'
        f'</div>'
    )

    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif; '
        'font-size:12px; min-width:300px; max-width:360px; line-height:1.5;">'
        + hero
        + finding_html
        + section_c
        + section_ab
        + footnote
        + '</div>'
    )

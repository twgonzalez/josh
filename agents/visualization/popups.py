"""
HTML popup and marker popup builders for the demo map.

v3.0 ΔT Standard: all route popups show effective_capacity_vph and ΔT clearance
time rather than v/c ratios. v/c and LOS remain informational footnotes only.
"""
from models.project import Project
from .themes import _TIER_CSS_COLOR, _TIER_BG_COLOR


# ---------------------------------------------------------------------------
# ΔT bar widget — v3.0
# ---------------------------------------------------------------------------

def _delta_t_bar_html(delta_t: float, threshold: float) -> str:
    """
    HTML progress bar showing ΔT position relative to its threshold.

    Bar fills left-to-right: full bar = at threshold. Overflow = red cap at 100%.
    A vertical tick marks the threshold at 100% width.
    Color: green (< 50%), yellow (50–75%), orange (75–100%), red (> 100%).
    """
    if threshold <= 0:
        threshold = 10.0
    ratio = delta_t / threshold
    pct = min(ratio * 100, 100)

    if ratio >= 1.0:
        bar_color = "#dc3545"   # red — exceeded
    elif ratio >= 0.75:
        bar_color = "#fd7e14"   # orange — approaching
    elif ratio >= 0.50:
        bar_color = "#ffc107"   # yellow — moderate
    else:
        bar_color = "#28a745"   # green — comfortable

    return (
        f'<div style="position:relative; background:#e9ecef; border-radius:4px; '
        f'height:10px; overflow:visible; margin:4px 0 10px;">'
        f'<div style="position:absolute; right:0; top:-3px; '
        f'width:2px; height:16px; background:#6c757d; z-index:2;"></div>'
        f'<div style="width:{pct:.1f}%; background:{bar_color}; height:100%; '
        f'border-radius:4px; position:relative; z-index:1;"></div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Route ΔT popup — v3.0 (serving route segments on per-project layer)
# ---------------------------------------------------------------------------

def _build_route_delta_t_popup(
    name_str: str,
    eff_cap: float,
    hcm_cap: float,
    fhsz_zone: str,
    hazard_degradation: float,
    delta_t_result: "dict | None",
    is_flagged: bool,
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

    capacity_rows = (
        '<table style="width:100%; border-collapse:collapse; font-size:11px; '
        'color:#555; margin-bottom:10px;">'
        f'<tr><td style="padding:2px 0;">HCM raw capacity</td>'
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
        mob      = delta_t_result.get("mobilization_rate", 0.25)
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
            f'<tr><td style="padding:1px 0;">Mob rate ({hz})</td>'
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
        f'Sources: HCM 2022 (capacity) · Zhao et al. 2022 (mob rates) · '
        f'NFPA 101 (egress) · NIST TN 2135 (safe egress window)'
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
        f'<tr><td style="padding:2px 0;">HCM raw capacity</td>'
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
# Demo map project marker popup
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

    Two-section layout (UI/UX best practice for hierarchical info):
      §1 — Analysis Scope (Stds 1–3): prerequisite conditions — compact, neutral
      §2 — Capacity Tests (Stds 4–5): decision drivers — prominent, full color

    worst_wildland_route: dict with keys
        name, delta_t_minutes, threshold_minutes, flagged — shown inline.
    worst_local_route: unused in v3.0 (SB 79 has no route details); pass None.
    """
    det       = project.determination or "UNKNOWN"
    det_color = _TIER_CSS_COLOR.get(det, "#555")
    bg_color  = _TIER_BG_COLOR.get(det, "#fafafa")

    n_srv     = len(project.serving_route_ids or [])
    met_size  = project.meets_size_threshold
    radius_mi = project.search_radius_miles
    in_zone   = f"Zone {project.fire_zone_level}" if project.in_fire_zone else "Not in FHSZ"
    reason_short = (project.determination_reason or "").split(".")[0] + "."

    # ── §1 Scope icons (Stds 1–3) ─────────────────────────────────────────
    # Std 1: project size gate
    s1_icon = "✓" if met_size else "✗"
    s1_clr  = "#1a56db" if met_size else "#adb5bd"
    s1_text = f"{project.dwelling_units} of {unit_threshold} units"
    # Std 2: serving evacuation routes (gated on size threshold)
    if not met_size:
        s2_icon, s2_clr, s2_text = "—", "#adb5bd", "not evaluated"
    elif n_srv > 0:
        s2_icon, s2_clr = "✓", "#1a56db"
        s2_text = f"{n_srv} routes · {radius_mi} mi"
    else:
        s2_icon, s2_clr, s2_text = "✗", "#adb5bd", "no routes found"
    # Std 3: FHSZ modifier (activates surge in Std 4 when flagged)
    in_fhsz = project.in_fire_zone
    if not met_size:
        s3_icon, s3_clr, s3_text = "—", "#adb5bd", "not evaluated"
    elif in_fhsz:
        s3_icon, s3_clr = "✓", "#c0392b"
        s3_text = f"{in_zone} — surge active"
    else:
        s3_icon, s3_clr, s3_text = "—", "#adb5bd", "Not in FHSZ"

    _SL = (
        "font-size:9px;font-weight:700;letter-spacing:1.2px;"
        "text-transform:uppercase;color:#adb5bd;margin-bottom:5px;"
    )

    def _scope_row(icon, clr, text):
        return (
            f'<div style="display:flex;align-items:baseline;gap:6px;'
            f'font-size:10px;color:#555;margin-bottom:2px;">'
            f'<span style="color:{clr};font-weight:700;min-width:10px;'
            f'flex-shrink:0;">{icon}</span>'
            f'<span>{text}</span></div>'
        )

    # ── §2 Capacity chips (Stds 4–5) ──────────────────────────────────────
    _TRIGGERED  = ("⚠ TRIGGERED",            "#fff3cd", "#856404")
    _WITHIN_THR = ("✓ ΔT WITHIN THRESHOLD",  "#e8f5e9", "#27ae60")
    _NOT_EVAL   = ("— NOT EVALUATED",         "#f1f3f5", "#868e96")
    _NA         = ("N/A",                     "#f1f3f5", "#868e96")

    # Std 4: ΔT clearance time test
    if not met_size:
        s4 = _NOT_EVAL
    elif project.capacity_exceeded:
        s4 = _TRIGGERED
    else:
        s4 = _WITHIN_THR

    # Std 5: SB 79 transit proximity — informational flag, never triggers
    ld_applicable = ld_tier not in ("NOT_APPLICABLE", "")
    if not met_size:
        s5 = _NOT_EVAL
    elif not ld_applicable:
        s5 = _NA
    elif ld_triggered:
        s5 = _TRIGGERED
    else:
        s5 = _NA   # SB 79 is always N/A for tier — informational only

    def _cap_chip(label, bg, fg):
        return (
            f'<span style="padding:2px 8px;border-radius:9px;font-size:10px;'
            f'font-weight:700;background:{bg};color:{fg};'
            f'white-space:nowrap;flex-shrink:0;">{label}</span>'
        )

    def _route_line(route):
        """Show ΔT result for the worst-case evacuation path."""
        if not route:
            return ""
        nm      = route.get("name", "Bottleneck segment")
        nm      = nm[:25] + "…" if len(nm) > 25 else nm
        dt      = route.get("delta_t_minutes", 0.0)
        thr     = route.get("threshold_minutes", 10.0)
        flagged = route.get("flagged", False)
        margin  = dt - thr
        clr     = "#856404" if flagged else "#27ae60"
        icon    = "⚠" if flagged else "✓"
        margin_str = f"+{margin:.2f} over" if flagged else f"−{abs(margin):.2f} left"
        return (
            f'<div style="font-size:10px;color:{clr};padding-left:6px;'
            f'margin-top:2px;font-style:italic;">'
            f'{icon} {nm}: ΔT {dt:.2f} min (limit {thr:.2f} min · {margin_str})</div>'
        )

    scope_html = (
        _scope_row(s1_icon, s1_clr, s1_text)
        + _scope_row(s2_icon, s2_clr, s2_text)
        + _scope_row(s3_icon, s3_clr, s3_text)
    )

    s4_html = (
        f'<div style="margin-bottom:7px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:11px;color:#343a40;font-weight:600;">'
        f'Std 4 &middot; ΔT Clearance</span>'
        + _cap_chip(*s4)
        + f'</div>'
        + (_route_line(worst_wildland_route) if worst_wildland_route else "")
        + f'</div>'
    )

    s5_html = (
        f'<div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:11px;color:#343a40;font-weight:600;">'
        f'Std 5 &middot; SB 79 Transit</span>'
        + _cap_chip(*s5)
        + f'</div>'
        + f'</div>'
    )

    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif;'
        'font-size:12px;min-width:280px;max-width:310px;line-height:1.5;">'

        # Header: determination + project name + units/zone
        f'<div style="background:{bg_color};margin:-14px -16px 0;'
        f'padding:10px 14px;border-radius:8px 8px 0 0;border-bottom:1px solid #dee2e6;">'
        f'<div style="font-size:15px;font-weight:700;color:{det_color};">{det}</div>'
        f'<div style="font-size:11px;color:#444;margin-top:1px;">'
        f'{project.project_name or "Project"}</div>'
        f'<div style="font-size:10px;color:#6c757d;margin-top:2px;">'
        f'{project.dwelling_units} units &nbsp;&middot;&nbsp; {in_zone}</div>'
        f'</div>'

        # §1 Analysis Scope — subdued gray background, compact rows
        f'<div style="background:#f8f9fa;padding:7px 14px 5px;border-bottom:1px solid #e9ecef;">'
        f'<div style="{_SL}">Analysis Scope &nbsp;&middot;&nbsp; Stds 1–3</div>'
        + scope_html
        + '</div>'

        # §2 Capacity Tests — white background, prominent chips + route detail
        f'<div style="padding:8px 14px 6px;">'
        f'<div style="{_SL}">Capacity Tests &nbsp;&middot;&nbsp; Stds 4–5</div>'
        + s4_html
        + s5_html
        + '</div>'

        # Footer: short determination reason
        f'<div style="font-size:10px;color:#868e96;border-top:1px solid #f1f3f5;'
        f'padding:5px 14px 8px;font-style:italic;line-height:1.4;">'
        f'{reason_short[:160]}</div>'
        '</div>'
    )

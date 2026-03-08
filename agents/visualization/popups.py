"""
HTML popup and marker popup builders for the demo map.
"""
from models.project import Project
from .themes import _TIER_CSS_COLOR, _TIER_BG_COLOR


# ---------------------------------------------------------------------------
# v/c bar widget
# ---------------------------------------------------------------------------

def _vc_bar_html(vc: float, threshold: float) -> str:
    """HTML progress bar for a v/c ratio (capped at 150% for display)."""
    pct = min(vc / 1.5 * 100, 100)
    thresh_pct = min(threshold / 1.5 * 100, 100)

    if vc >= threshold:
        bar_color = "#e74c3c"
    elif vc >= 0.60:
        bar_color = "#e67e22"
    else:
        bar_color = "#27ae60"

    return (
        f'<div style="position:relative; background:#e9ecef; border-radius:4px; '
        f'height:10px; overflow:visible; margin:4px 0 10px;">'
        f'<div style="position:absolute; left:{thresh_pct:.1f}%; top:-3px; '
        f'width:2px; height:16px; background:#6c757d; z-index:2;"></div>'
        f'<div style="width:{pct:.1f}%; background:{bar_color}; height:100%; '
        f'border-radius:4px; position:relative; z-index:1;"></div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Route impact popup (shared by evaluation and demo maps)
# ---------------------------------------------------------------------------

def _build_route_impact_popup(
    name_str: str,
    los: str,
    cap: float,
    demand_base: float,
    demand_proposed: float,
    vc_base: float,
    vc_proposed: float,
    vc_threshold: float,
    project_vph: float,
    is_flagged: bool,
    already_failing: bool = False,
) -> str:
    """HTML popup showing baseline vs proposed v/c impact for a serving route."""
    if is_flagged:
        status_html = (
            '<div style="color:#c0392b; font-weight:700; font-size:11px; '
            'margin-bottom:10px;">⚠ Capacity exceeded — Standard 4 triggered</div>'
        )
    elif already_failing:
        status_html = (
            '<div style="color:#868e96; font-weight:600; font-size:11px; '
            f'margin-bottom:10px;">ℹ Pre-existing congestion — baseline v/c {vc_base:.3f} '
            f'already ≥ {vc_threshold:.2f} before this project</div>'
        )
    else:
        status_html = (
            '<div style="color:#27ae60; font-weight:600; font-size:11px; '
            'margin-bottom:10px;">✓ Within capacity threshold</div>'
        )

    delta_vc = vc_proposed - vc_base
    delta_str = f"+{delta_vc:.3f}" if delta_vc >= 0 else f"{delta_vc:.3f}"

    return (
        '<div style="font-family:system-ui,-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',sans-serif; font-size:12px; min-width:300px; max-width:350px; '
        'color:#333; line-height:1.5;">'
        f'<div style="font-weight:700; font-size:13px; margin-bottom:4px; color:#111;">'
        f'{name_str[:45]}</div>'
        f'{status_html}'
        '<table style="width:100%; border-collapse:collapse; font-size:11px; '
        'color:#555; margin-bottom:12px;">'
        f'<tr><td style="padding:2px 0;">Capacity</td>'
        f'<td style="text-align:right; font-weight:600;">{cap:.0f} vph</td></tr>'
        f'<tr><td style="padding:2px 0;">Baseline demand</td>'
        f'<td style="text-align:right; font-weight:600;">{demand_base:.0f} vph</td></tr>'
        f'<tr><td style="padding:2px 0;">Project adds</td>'
        f'<td style="text-align:right; font-weight:600; color:#7c55b8;">+{project_vph:.1f} vph</td></tr>'
        f'<tr><td style="padding:2px 0;">Proposed demand</td>'
        f'<td style="text-align:right; font-weight:600;">{demand_proposed:.0f} vph</td></tr>'
        '</table>'
        f'<div style="font-weight:600; font-size:11px; color:#444; margin-bottom:2px;">'
        f'Baseline v/c &nbsp; <span style="font-weight:700;">{vc_base:.3f}</span></div>'
        f'{_vc_bar_html(vc_base, vc_threshold)}'
        f'<div style="font-weight:600; font-size:11px; color:#444; margin-bottom:2px;">'
        f'Proposed v/c &nbsp; <span style="font-weight:700;">{vc_proposed:.3f}</span> '
        f'<span style="color:#7c55b8; font-size:10px;">({delta_str})</span></div>'
        f'{_vc_bar_html(vc_proposed, vc_threshold)}'
        f'<div style="border-top:1px solid #dee2e6; padding-top:6px; '
        f'font-size:10px; color:#868e96;">'
        f'Threshold: {vc_threshold:.2f} &nbsp;|&nbsp; LOS: {los}'
        f'<br>Worst-case method: full project load tested on each route independently'
        f'</div>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Heatmap baseline popup (citywide layer — no project context)
# ---------------------------------------------------------------------------

def _build_heatmap_route_popup(
    name_str: str,
    los: str,
    cap: float,
    demand_base: float,
    vc_base: float,
    vc_threshold: float,
) -> str:
    """
    Popup shown when clicking an evacuation route segment on the heatmap base
    layer. Shows baseline capacity state only — no project comparison.
    Visual style matches _build_route_impact_popup() for consistency.
    """
    if vc_base >= vc_threshold:
        status_color = "#c0392b"
        status_icon  = "⚠"
        status_text  = f"At/over capacity — v/c {vc_base:.3f} ≥ {vc_threshold:.2f}"
    elif vc_base >= 0.60:
        status_color = "#e67e22"
        status_icon  = "◑"
        status_text  = f"Moderate stress — v/c {vc_base:.3f}"
    else:
        status_color = "#27ae60"
        status_icon  = "✓"
        status_text  = f"Within capacity — v/c {vc_base:.3f}"

    return (
        '<div style="font-family:system-ui,-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',sans-serif; font-size:12px; min-width:280px; max-width:340px; '
        'color:#333; line-height:1.5;">'
        f'<div style="font-weight:700; font-size:13px; margin-bottom:4px; color:#111;">'
        f'{name_str[:45]}</div>'
        f'<div style="color:{status_color}; font-weight:600; font-size:11px; '
        f'margin-bottom:10px;">{status_icon} {status_text}</div>'
        '<table style="width:100%; border-collapse:collapse; font-size:11px; '
        'color:#555; margin-bottom:12px;">'
        f'<tr><td style="padding:2px 0;">Capacity</td>'
        f'<td style="text-align:right; font-weight:600;">{cap:.0f} vph</td></tr>'
        f'<tr><td style="padding:2px 0;">Baseline demand</td>'
        f'<td style="text-align:right; font-weight:600;">{demand_base:.0f} vph</td></tr>'
        '</table>'
        f'<div style="font-weight:600; font-size:11px; color:#444; margin-bottom:2px;">'
        f'Baseline v/c &nbsp; <span style="font-weight:700;">{vc_base:.3f}</span></div>'
        f'{_vc_bar_html(vc_base, vc_threshold)}'
        f'<div style="border-top:1px solid #dee2e6; padding-top:6px; '
        f'font-size:10px; color:#868e96;">'
        f'Threshold: {vc_threshold:.2f} &nbsp;|&nbsp; LOS: {los}'
        f'<br>Select a project to see baseline → projected impact'
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

    worst_wildland_route / worst_local_route: dict with keys
        name, baseline_vc, proposed_vc — shown inline when triggered.
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
    _TRIGGERED  = ("⚠ TRIGGERED",       "#fff3cd", "#856404")
    _WITHIN_CAP = ("✓ WITHIN CAPACITY", "#e8f5e9", "#27ae60")
    _NOT_EVAL   = ("— NOT EVALUATED",   "#f1f3f5", "#868e96")
    _NA         = ("N/A",               "#f1f3f5", "#868e96")

    # Std 4: wildland evac capacity
    if not met_size:
        s4 = _NOT_EVAL
    elif project.exceeds_capacity_threshold:
        s4 = _TRIGGERED
    else:
        s4 = _WITHIN_CAP

    # Std 5: local density capacity
    ld_applicable = ld_tier not in ("NOT_APPLICABLE", "")
    if not met_size:
        s5 = _NOT_EVAL
    elif not ld_applicable:
        s5 = _NA
    elif ld_triggered:
        s5 = _TRIGGERED
    else:
        s5 = _WITHIN_CAP

    def _cap_chip(label, bg, fg):
        return (
            f'<span style="padding:2px 8px;border-radius:9px;font-size:10px;'
            f'font-weight:700;background:{bg};color:{fg};'
            f'white-space:nowrap;flex-shrink:0;">{label}</span>'
        )

    def _route_line(route):
        if not route:
            return ""
        nm  = route["name"]
        nm  = nm[:25] + "…" if len(nm) > 25 else nm
        bvc = route["baseline_vc"]
        pvc = route["proposed_vc"]
        return (
            f'<div style="font-size:10px;color:#856404;padding-left:6px;'
            f'margin-top:2px;font-style:italic;">'
            f'{nm}: {bvc:.3f} → {pvc:.3f} v/c</div>'
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
        f'Std 4 &middot; Evac Capacity</span>'
        + _cap_chip(*s4)
        + f'</div>'
        + (_route_line(worst_wildland_route) if project.exceeds_capacity_threshold else "")
        + f'</div>'
    )

    s5_html = (
        f'<div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:11px;color:#343a40;font-weight:600;">'
        f'Std 5 &middot; Local Capacity</span>'
        + _cap_chip(*s5)
        + f'</div>'
        + (_route_line(worst_local_route) if ld_triggered else "")
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

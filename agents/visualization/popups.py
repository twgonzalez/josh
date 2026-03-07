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
) -> str:
    """Popup shown when clicking a project marker on the demo map."""
    det       = project.determination or "UNKNOWN"
    det_color = _TIER_CSS_COLOR.get(det, "#555")
    bg_color  = _TIER_BG_COLOR.get(det, "#fafafa")

    def std_row(label, triggered, detail=""):
        chip_bg    = "#fde8e8" if triggered else "#e8f5e9"
        chip_color = "#c0392b" if triggered else "#27ae60"
        return (
            f'<tr><td style="padding:3px 0; color:#555; font-size:11px;">{label}</td>'
            f'<td style="text-align:right; padding:3px 0;">'
            f'<span style="padding:1px 7px; border-radius:9px; font-size:10px; '
            f'font-weight:700; background:{chip_bg}; color:{chip_color};">'
            f'{"YES" if triggered else "NO"}</span></td>'
            f'<td style="padding:3px 0 3px 8px; font-size:10px; color:#868e96;">{detail}</td></tr>'
        )

    n_srv   = len(project.serving_route_ids or [])
    n_flg   = len(project.flagged_route_ids or [])
    in_zone = (
        f"Zone {project.fire_zone_level}" if project.in_fire_zone
        else "Not in FHSZ"
    )
    reason_short = (project.determination_reason or "").split(".")[0] + "."

    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif; '
        'font-size:12px; min-width:270px; max-width:310px; line-height:1.5;">'
        f'<div style="background:{bg_color}; margin:-14px -16px 12px; '
        f'padding:10px 14px; border-bottom:1px solid #dee2e6; '
        f'border-radius:8px 8px 0 0;">'
        f'<div style="font-size:15px; font-weight:700; color:{det_color};">{det}</div>'
        f'<div style="font-size:11px; color:#444; margin-top:1px;">'
        f'{project.project_name or "Project"}'
        f'</div>'
        f'</div>'
        f'<div style="font-size:11px; color:#555; margin-bottom:10px;">'
        f'{project.address or ""}'
        f'<br>{project.dwelling_units} dwelling units'
        f' &nbsp;·&nbsp; {project.location_lat:.4f}, {project.location_lon:.4f}'
        f'<br>Fire zone: {in_zone}'
        f'</div>'
        '<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">'
        + std_row("Std 2 · Size", project.meets_size_threshold,
                  f"{project.dwelling_units} units")
        + std_row("Std 3 · Routes", bool(n_srv), f"{n_srv} segs")
        + std_row("Std 4 · Capacity", project.exceeds_capacity_threshold,
                  f"{n_flg} flagged")
        + '</table>'
        f'<div style="font-size:11px; color:#444; border-top:1px solid #f1f3f5; '
        f'padding-top:8px; margin-top:4px;">'
        f'Peak vehicles generated: '
        f'<strong style="color:{proj_color};">'
        f'{project.project_vehicles_peak_hour:.0f} vph</strong>'
        f'</div>'
        f'<div style="font-size:10px; color:#868e96; margin-top:6px; '
        f'font-style:italic; line-height:1.4;">'
        f'{reason_short[:180]}'
        f'</div>'
        '</div>'
    )

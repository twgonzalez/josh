"""
Agent 6: Visualization

Generates interactive Folium maps for project evaluations.

Map layers (all toggleable via LayerControl):
  - City Boundary
  - FHSZ Fire Zones (colored by hazard class)
  - Road Network (LOS) — all roads colored by level of service
  - Evacuation Routes — highlighted by LOS
  - Serving Routes — evacuation routes within search radius, with impact popups
  - Flagged Routes — glow overlay for routes exceeding v/c threshold
  - Search Radius — buffer circle around project
  - Project Marker — pin with determination tier color

Fixed UI panels (non-map overlays):
  - Project Card (top-left, collapsible) — tier badge, standards checklist, impact metrics
  - Legend (bottom-right) — LOS scale, FHSZ zones, route types
"""
import logging
from pathlib import Path

import folium
import geopandas as gpd
from shapely.geometry import Point, mapping

from models.project import Project

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------

# LOS color scale: green (good) → dark red (failed)
LOS_COLORS = {
    "A": "#2ca02c",
    "B": "#98df8a",
    "C": "#ffbb78",
    "D": "#ff7f0e",
    "E": "#d62728",
    "F": "#8c0000",
}

FHSZ_COLORS = {
    1: "#ffeda0",   # Moderate — yellow
    2: "#fc8d59",   # High — orange
    3: "#d7301f",   # Very High — red
}

FHSZ_LABELS = {
    1: "Zone 1 — Moderate",
    2: "Zone 2 — High",
    3: "Zone 3 — Very High",
}

_TIER_MARKER_COLOR = {
    "DISCRETIONARY":           "red",
    "CONDITIONAL MINISTERIAL": "orange",
    "MINISTERIAL":             "green",
}

_TIER_CSS_COLOR = {
    "DISCRETIONARY":           "#c0392b",
    "CONDITIONAL MINISTERIAL": "#d67c00",
    "MINISTERIAL":             "#27ae60",
}

_TIER_BG_COLOR = {
    "DISCRETIONARY":           "#fdf2f2",
    "CONDITIONAL MINISTERIAL": "#fffbf0",
    "MINISTERIAL":             "#f0faf4",
}

_TIER_BORDER_COLOR = {
    "DISCRETIONARY":           "#e8b4b0",
    "CONDITIONAL MINISTERIAL": "#f5d49a",
    "MINISTERIAL":             "#a8d5b8",
}


# ---------------------------------------------------------------------------
# OSMid matching helpers
# ---------------------------------------------------------------------------

def _osmid_set(ids) -> set:
    """
    Flatten a list of osmids (each may be an int, string, or list) into a flat
    set that includes both raw and string representations.  This handles the
    discrepancy between serving_route_ids (raw values from OSMnx) and
    flagged_route_ids (str-converted in objective_standards).
    """
    result: set = set()
    for v in (ids or []):
        if isinstance(v, list):
            for x in v:
                result.add(x)
                result.add(str(x))
        else:
            result.add(v)
            result.add(str(v))
    return result


def _osmid_matches(osmid_val, target_set: set) -> bool:
    """Return True if osmid_val (possibly a list) appears in target_set."""
    if isinstance(osmid_val, list):
        return any(o in target_set or str(o) in target_set for o in osmid_val)
    return osmid_val in target_set or str(osmid_val) in target_set


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def create_evaluation_map(
    project: Project,
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    config: dict,
    output_path: Path,
) -> Path:
    """
    Generate an interactive Folium HTML map for a project evaluation.

    Returns the path to the saved HTML file.
    """
    lat, lon = project.location_lat, project.location_lon
    vc_threshold = config.get("vc_threshold", 0.80)

    # Precompute osmid sets for fast lookup
    serving_set = _osmid_set(project.serving_route_ids)
    flagged_set = _osmid_set(project.flagged_route_ids)

    # Project vehicle contribution per serving route (for impact visualisation)
    num_serving = max(len(project.serving_route_ids or []), 1)
    project_vph_per_route = project.project_vehicles_peak_hour / num_serving

    # Reproject roads to WGS84 once
    roads_wgs84 = roads_gdf.to_crs("EPSG:4326")

    # Base map — CartoDB Positron for a clean, light background
    m = folium.Map(
        location=[lat, lon],
        zoom_start=14,
        tiles="CartoDB positron",
    )

    # -----------------------------------------------------------------------
    # Layer 1: City Boundary
    # -----------------------------------------------------------------------
    boundary_layer = folium.FeatureGroup(name="City Boundary", show=True)
    boundary_wgs84 = boundary_gdf.to_crs("EPSG:4326")
    for _, row in boundary_wgs84.iterrows():
        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _: {
                "fillColor": "none",
                "color": "#1a6eb5",
                "weight": 2,
                "dashArray": "8 5",
                "fillOpacity": 0,
            },
            tooltip="City Boundary",
        ).add_to(boundary_layer)
    boundary_layer.add_to(m)

    # -----------------------------------------------------------------------
    # Layer 2: FHSZ Fire Zones
    # -----------------------------------------------------------------------
    fhsz_layer = folium.FeatureGroup(name="FHSZ Fire Zones", show=True)
    if not fhsz_gdf.empty and "HAZ_CLASS" in fhsz_gdf.columns:
        fhsz_wgs84 = fhsz_gdf.to_crs("EPSG:4326")
        for _, row in fhsz_wgs84.iterrows():
            haz = _to_int_safe(row.get("HAZ_CLASS", 0))
            color = FHSZ_COLORS.get(haz, "#ffeda0")
            label = FHSZ_LABELS.get(haz, f"Zone {haz}")
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _, c=color: {
                    "fillColor": c,
                    "color": c,
                    "weight": 1,
                    "fillOpacity": 0.30,
                },
                tooltip=label,
            ).add_to(fhsz_layer)
    fhsz_layer.add_to(m)

    # -----------------------------------------------------------------------
    # Layer 3: All Roads (colored by LOS) — off by default
    # -----------------------------------------------------------------------
    all_roads_layer = folium.FeatureGroup(name="Road Network (LOS)", show=False)
    if "los" in roads_wgs84.columns:
        for _, row in roads_wgs84.iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            los = str(row.get("los", "C"))
            color = LOS_COLORS.get(los, "#aaaaaa")
            name_str = str(row.get("name", "Unnamed") or "Unnamed")
            vc = row.get("vc_ratio", 0)
            cap = row.get("capacity_vph", 0)
            weight = max(_highway_weight(row.get("highway", "")) * 0.40, 1.0)
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _, c=color, w=weight: {
                    "color": c,
                    "weight": w,
                    "opacity": 0.50,
                },
                tooltip=f"{name_str} | LOS {los} | v/c {vc:.2f} | {cap:.0f} vph cap",
            ).add_to(all_roads_layer)
    all_roads_layer.add_to(m)

    # -----------------------------------------------------------------------
    # Layer 4: Evacuation Routes (LOS-colored thick lines)
    # -----------------------------------------------------------------------
    evac_layer = folium.FeatureGroup(name="Evacuation Routes", show=True)
    evac_routes_gdf = roads_wgs84[roads_wgs84.get("is_evacuation_route", False) == True]
    for _, row in evac_routes_gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        los = str(row.get("los", "C"))
        color = LOS_COLORS.get(los, "#aaaaaa")
        name_str = str(row.get("name", "Unnamed") or "Unnamed")
        vc = row.get("vc_ratio", 0)
        conn = row.get("connectivity_score", 0)
        weight = max(_highway_weight(row.get("highway", "")) * 0.50, 2.5)  # scaled, min 2.5px
        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _, c=color, w=weight: {
                "color": c,
                "weight": w,
                "opacity": 0.60,
            },
            tooltip=f"[EVAC] {name_str} | LOS {los} | v/c {vc:.2f} | conn {conn}",
        ).add_to(evac_layer)
    evac_layer.add_to(m)

    # -----------------------------------------------------------------------
    # Layer 5: Serving Routes (within search radius, with impact popups)
    # -----------------------------------------------------------------------
    serving_layer = folium.FeatureGroup(name="Serving Routes", show=True)
    if serving_set and "osmid" in roads_wgs84.columns:
        serving_mask = roads_wgs84["osmid"].apply(
            lambda o: _osmid_matches(o, serving_set)
        )
        serving_routes_gdf = roads_wgs84[serving_mask]
    else:
        serving_routes_gdf = roads_wgs84.iloc[0:0]

    for _, row in serving_routes_gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        osmid_val = row.get("osmid")
        is_flagged = _osmid_matches(osmid_val, flagged_set)

        name_str = str(row.get("name", "Unnamed") or "Unnamed")
        vc_base = float(row.get("vc_ratio", 0) or 0)
        los = str(row.get("los", "?"))
        cap = float(row.get("capacity_vph", 1) or 1)
        demand_base = float(row.get("baseline_demand_vph", 0) or 0)
        demand_proposed = demand_base + project_vph_per_route
        vc_proposed = demand_proposed / cap if cap > 0 else vc_base

        # Flagged = hot-pink, normal serving = purple
        route_color = "#e8186d" if is_flagged else "#7c55b8"
        weight = 6 if is_flagged else 5

        popup_html = _build_route_impact_popup(
            name_str, los, cap, demand_base, demand_proposed,
            vc_base, vc_proposed, vc_threshold, project_vph_per_route, is_flagged,
        )
        tip = f"{'⚠ FLAGGED' if is_flagged else '→'} {name_str} | LOS {los} | v/c {vc_base:.3f}"

        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _, c=route_color, w=weight: {
                "color": c,
                "weight": w,
                "opacity": 1.0,
            },
            popup=folium.Popup(popup_html, max_width=360),
            tooltip=tip,
        ).add_to(serving_layer)
    serving_layer.add_to(m)

    # -----------------------------------------------------------------------
    # Layer 6: Flagged Routes — glow overlay for capacity-exceeded routes
    # -----------------------------------------------------------------------
    flagged_layer = folium.FeatureGroup(name="Flagged Routes (v/c exceeded)", show=True)
    if flagged_set and "osmid" in roads_wgs84.columns:
        flagged_mask = roads_wgs84["osmid"].apply(
            lambda o: _osmid_matches(o, flagged_set)
        )
        flagged_routes_gdf = roads_wgs84[flagged_mask]
        for _, row in flagged_routes_gdf.iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            name_str = str(row.get("name", "Unnamed") or "Unnamed")
            vc = float(row.get("vc_ratio", 0) or 0)
            los = str(row.get("los", "F"))
            # Wide semi-transparent halo for a glow effect
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _: {
                    "color": "#ff1744",
                    "weight": 14,
                    "opacity": 0.20,
                },
                tooltip=f"⚠ CAPACITY EXCEEDED: {name_str} | LOS {los} | v/c {vc:.3f}",
            ).add_to(flagged_layer)
    flagged_layer.add_to(m)

    # -----------------------------------------------------------------------
    # Layer 7: Search Radius Buffer
    # -----------------------------------------------------------------------
    radius_miles = config.get("evacuation_route_radius_miles", 0.5)
    radius_meters = radius_miles * 1609.344
    buffer_layer = folium.FeatureGroup(
        name=f"Search Radius ({radius_miles} mi)", show=True
    )
    folium.Circle(
        location=[lat, lon],
        radius=radius_meters,
        color="#6c757d",
        weight=1.5,
        fill=True,
        fill_color="#adb5bd",
        fill_opacity=0.07,
        dash_array="10 5",
        tooltip=f"Evacuation route search radius — {radius_miles} mi",
    ).add_to(buffer_layer)
    buffer_layer.add_to(m)

    # -----------------------------------------------------------------------
    # Layer 8: Project Marker
    # -----------------------------------------------------------------------
    det = project.determination or "UNKNOWN"
    marker_color = _TIER_MARKER_COLOR.get(det, "gray")
    project_layer = folium.FeatureGroup(name="Project Marker", show=True)
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(
            _build_project_popup(project, serving_set, vc_threshold),
            max_width=300,
        ),
        tooltip=f"Project · {det}",
        icon=folium.Icon(color=marker_color, icon="home", prefix="fa"),
    ).add_to(project_layer)
    project_layer.add_to(m)

    # -----------------------------------------------------------------------
    # Fixed HTML panels: Project Card + Legend + global styles
    # -----------------------------------------------------------------------
    m.get_root().html.add_child(folium.Element(
        _build_project_card_html(project, serving_set, flagged_set, config)
    ))
    m.get_root().html.add_child(folium.Element(_build_legend_html(config)))
    m.get_root().html.add_child(folium.Element(_build_global_styles()))

    # Layer control (collapsed by default for cleaner initial view)
    folium.LayerControl(collapsed=True).add_to(m)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    logger.info(f"Map saved: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Route impact popup
# ---------------------------------------------------------------------------

def _vc_bar_html(vc: float, threshold: float) -> str:
    """HTML progress bar for a v/c ratio (capped at 150% for display)."""
    pct = min(vc / 1.5 * 100, 100)          # scale so 1.5 = full bar
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
        # threshold tick mark
        f'<div style="position:absolute; left:{thresh_pct:.1f}%; top:-3px; '
        f'width:2px; height:16px; background:#6c757d; z-index:2;"></div>'
        # filled bar
        f'<div style="width:{pct:.1f}%; background:{bar_color}; height:100%; '
        f'border-radius:4px; position:relative; z-index:1;"></div>'
        f'</div>'
    )


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
) -> str:
    """HTML popup showing baseline vs proposed v/c impact for a serving route."""
    if is_flagged:
        status_html = (
            '<div style="color:#c0392b; font-weight:700; font-size:11px; '
            'margin-bottom:10px;">⚠ Capacity exceeded — Standard 4 triggered</div>'
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

        # Route name header
        f'<div style="font-weight:700; font-size:13px; margin-bottom:4px; color:#111;">'
        f'{name_str[:45]}</div>'

        f'{status_html}'

        # Quick stats
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

        # v/c bars
        f'<div style="font-weight:600; font-size:11px; color:#444; margin-bottom:2px;">'
        f'Baseline v/c &nbsp; <span style="font-weight:700;">{vc_base:.3f}</span></div>'
        f'{_vc_bar_html(vc_base, vc_threshold)}'

        f'<div style="font-weight:600; font-size:11px; color:#444; margin-bottom:2px;">'
        f'Proposed v/c &nbsp; <span style="font-weight:700;">{vc_proposed:.3f}</span> '
        f'<span style="color:#7c55b8; font-size:10px;">({delta_str})</span></div>'
        f'{_vc_bar_html(vc_proposed, vc_threshold)}'

        # Footer
        f'<div style="border-top:1px solid #dee2e6; padding-top:6px; '
        f'font-size:10px; color:#868e96;">'
        f'Threshold: {vc_threshold:.2f} &nbsp;|&nbsp; LOS: {los}'
        f'</div>'

        '</div>'
    )


# ---------------------------------------------------------------------------
# Project marker popup (minimal — full info is in the card panel)
# ---------------------------------------------------------------------------

def _build_project_popup(project: Project, serving_set: set, vc_threshold: float) -> str:
    det = project.determination or "UNKNOWN"
    det_color = _TIER_CSS_COLOR.get(det, "#555555")
    display_name = project.project_name or "Proposed Project"
    in_zone = f"Zone {project.fire_zone_level}" if project.in_fire_zone else "Not in FHSZ"
    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif; '
        'font-size:12px; min-width:200px; line-height:1.6;">'
        f'<div style="font-size:14px; font-weight:700; color:{det_color}; '
        f'margin-bottom:6px;">{det}</div>'
        f'<div style="color:#444; font-weight:600;">{display_name}</div>'
        f'<div style="color:#555;">{project.dwelling_units} dwelling units</div>'
        f'<div style="color:#555;">{project.location_lat:.4f}, {project.location_lon:.4f}</div>'
        f'<div style="color:#888; margin-top:4px;">Fire zone: {in_zone}</div>'
        '<div style="color:#aaa; font-size:10px; margin-top:8px;">'
        'See project card (top-left) for full details</div>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Project Card panel (fixed top-left, collapsible)
# ---------------------------------------------------------------------------

def _build_project_card_html(
    project: Project,
    serving_set: set,
    flagged_set: set,
    config: dict,
) -> str:
    det = project.determination or "UNKNOWN"
    det_color = _TIER_CSS_COLOR.get(det, "#555555")
    bg_color = _TIER_BG_COLOR.get(det, "#fafafa")
    border_color = _TIER_BORDER_COLOR.get(det, "#dee2e6")

    vc_threshold = config.get("vc_threshold", 0.80)
    display_name = project.project_name or "Proposed Project"

    # ---- Project info rows ----
    def info_row(label, value, value_color="#222"):
        return (
            f'<div style="display:flex; justify-content:space-between; '
            f'align-items:baseline; margin-bottom:4px;">'
            f'<span style="color:#6c757d; font-size:11px;">{label}</span>'
            f'<span style="color:{value_color}; font-weight:500; font-size:11px; '
            f'text-align:right; max-width:160px; overflow:hidden; '
            f'text-overflow:ellipsis; white-space:nowrap;">{value}</span>'
            f'</div>'
        )

    in_zone_str = (
        f"Zone {project.fire_zone_level} ({'Moderate' if project.fire_zone_level == 1 else 'High' if project.fire_zone_level == 2 else 'Very High'})"
        if project.in_fire_zone else "Not in FHSZ"
    )
    in_zone_color = "#c0392b" if project.in_fire_zone else "#27ae60"

    project_info = (
        info_row("Name", display_name[:30])
        + (info_row("Address", project.address[:30]) if project.address else "")
        + (info_row("APN", project.apn) if project.apn else "")
        + info_row("Units", str(project.dwelling_units))
        + info_row("Location", f"{project.location_lat:.4f}, {project.location_lon:.4f}")
        + info_row("Fire zone", in_zone_str, in_zone_color)
    )

    # ---- Standards checklist ----
    def std_row(label, triggered, detail=""):
        yes_no = "YES" if triggered else "NO"
        chip_bg = "#fde8e8" if triggered else "#e8f5e9"
        chip_color = "#c0392b" if triggered else "#27ae60"
        row = (
            f'<div style="display:flex; justify-content:space-between; '
            f'align-items:center; margin-bottom:6px;">'
            f'<div style="flex:1;">'
            f'<span style="font-size:11px; color:#444;">{label}</span>'
        )
        if detail:
            row += (
                f'<div style="font-size:10px; color:#868e96; margin-top:1px;">'
                f'{detail}</div>'
            )
        row += (
            f'</div>'
            f'<span style="padding:2px 9px; border-radius:10px; font-size:10px; '
            f'font-weight:700; background:{chip_bg}; color:{chip_color}; '
            f'margin-left:8px; white-space:nowrap;">{yes_no}</span>'
            f'</div>'
        )
        return row

    n_serving = len(project.serving_route_ids or [])
    n_flagged = len(project.flagged_route_ids or [])
    threshold = project.size_threshold_used or config.get("unit_threshold", 50)
    vc_threshold_display = config.get("vc_threshold", 0.80)

    standards_rows = (
        std_row(
            "Std 1 · Citywide FHSZ",
            # Standard 1 is about whether the CITY has FHSZ zones — use in_fire_zone as proxy
            # (True if project is in a city that has FHSZ, best we have in Project model)
            project.in_fire_zone or bool(project.serving_route_ids),
            "City contains FHSZ zones",
        )
        + std_row(
            "Std 2 · Size threshold",
            project.meets_size_threshold,
            f"{project.dwelling_units} units vs {threshold} threshold",
        )
        + std_row(
            "Std 3 · Serving routes",
            n_serving > 0,
            f"{n_serving} segment(s) within {project.search_radius_miles} mi",
        )
        + std_row(
            "Std 4 · Capacity exceeded",
            project.exceeds_capacity_threshold,
            f"{n_flagged} route(s) at v/c ≥ {vc_threshold_display:.2f}",
        )
    )

    # ---- Impact summary ----
    impact_rows = (
        info_row("Peak vehicles generated", f"{project.project_vehicles_peak_hour:.1f} vph", "#7c55b8")
        + info_row("Serving route segments", str(n_serving))
        + info_row("Flagged segments", str(n_flagged), "#c0392b" if n_flagged > 0 else "#27ae60")
        + info_row("Fire zone modifier", "YES" if project.in_fire_zone else "NO",
                   "#c0392b" if project.in_fire_zone else "#555")
    )

    return f"""
<div id="proj-card" style="
    position: fixed;
    top: 10px; left: 10px;
    z-index: 9999;
    width: 290px;
    background: white;
    border: 1px solid {border_color};
    border-left: 4px solid {det_color};
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.13);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px;
    overflow: hidden;
">

  <!-- Card header (click to toggle) -->
  <div id="proj-card-header" style="
      background: {bg_color};
      padding: 11px 14px 10px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid {border_color};
      user-select: none;
  " onclick="toggleProjCard()">
    <div>
      <div style="font-size:10px; color:#868e96; text-transform:uppercase;
                  letter-spacing:0.6px; margin-bottom:2px;">
        Fire Evacuation Analysis
      </div>
      <div style="font-size:15px; font-weight:700; color:{det_color}; line-height:1.2;">
        {det}
      </div>
      <div style="font-size:10px; color:#555; margin-top:3px;">
        {display_name[:28]}
      </div>
    </div>
    <button id="proj-toggle-btn" style="
        background:none; border:none; cursor:pointer;
        font-size:14px; color:#868e96; padding:0 0 0 8px;
        line-height:1; margin-top:2px;
    ">▼</button>
  </div>

  <!-- Card body (collapsible) -->
  <div id="proj-card-body" style="padding: 13px 14px; display:block;">

    <!-- Project details -->
    <div style="margin-bottom:12px;">
      {project_info}
    </div>

    <!-- Standards checklist -->
    <div style="border-top:1px solid #f1f3f5; padding-top:11px; margin-bottom:12px;">
      <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
                  letter-spacing:0.6px; margin-bottom:8px;">Standards</div>
      {standards_rows}
    </div>

    <!-- Impact metrics -->
    <div style="border-top:1px solid #f1f3f5; padding-top:11px;">
      <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
                  letter-spacing:0.6px; margin-bottom:8px;">Impact</div>
      {impact_rows}
    </div>

  </div>
</div>

<script>
function toggleProjCard() {{
    var body = document.getElementById('proj-card-body');
    var btn  = document.getElementById('proj-toggle-btn');
    if (body.style.display === 'none') {{
        body.style.display = 'block';
        btn.textContent = '▼';
    }} else {{
        body.style.display = 'none';
        btn.textContent = '▶';
    }}
}}
</script>
"""


# ---------------------------------------------------------------------------
# Legend panel (bottom-right)
# ---------------------------------------------------------------------------

def _build_legend_html(config: dict) -> str:
    vc_threshold = config.get("vc_threshold", 0.80)

    los_items = "".join(
        f'<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:28px; height:5px; '
        f'background:{c}; border-radius:2px; flex-shrink:0;"></span>'
        f'<span style="color:#444;">{grade}</span>'
        f'</div>'
        for grade, c in LOS_COLORS.items()
    )

    fhsz_items = "".join(
        f'<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:13px; height:13px; '
        f'background:{FHSZ_COLORS[k]}; opacity:0.65; border-radius:2px; '
        f'border:1px solid rgba(0,0,0,0.1); flex-shrink:0;"></span>'
        f'<span style="color:#444;">{FHSZ_LABELS[k]}</span>'
        f'</div>'
        for k in sorted(FHSZ_COLORS)
    )

    tier_items = (
        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        '<span style="display:inline-block; width:12px; height:12px; border-radius:50%; '
        'background:#c0392b; flex-shrink:0;"></span>'
        '<span style="color:#444;">Discretionary</span></div>'
        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        '<span style="display:inline-block; width:12px; height:12px; border-radius:50%; '
        'background:#d67c00; flex-shrink:0;"></span>'
        '<span style="color:#444;">Cond. Ministerial</span></div>'
        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        '<span style="display:inline-block; width:12px; height:12px; border-radius:50%; '
        'background:#27ae60; flex-shrink:0;"></span>'
        '<span style="color:#444;">Ministerial</span></div>'
    )

    route_items = (
        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        '<span style="display:inline-block; width:28px; height:5px; '
        'background:#7c55b8; border-radius:2px; flex-shrink:0;"></span>'
        '<span style="color:#444;">Serving routes</span></div>'
        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        '<span style="display:inline-block; width:28px; height:5px; '
        'background:#e8186d; border-radius:2px; flex-shrink:0;"></span>'
        '<span style="color:#444;">Flagged (v/c exceeded)</span></div>'
    )

    return f"""
<div id="map-legend" style="
    position: fixed;
    bottom: 26px; right: 10px;
    z-index: 9999;
    width: 186px;
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 13px 14px;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 11px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.11);
    line-height: 1.4;
">

  <div style="font-weight:700; font-size:12px; color:#212529; margin-bottom:10px;
              border-bottom:1px solid #f1f3f5; padding-bottom:7px;">
    Legend
  </div>

  <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:6px;">LOS (v/c ratio)</div>
  {los_items}
  <div style="font-size:10px; color:#adb5bd; margin-top:2px; margin-bottom:10px;">
    threshold: {vc_threshold:.2f}
  </div>

  <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:6px;">Determination Tier</div>
  {tier_items}
  <div style="margin-bottom:10px;"></div>

  <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:6px;">Route Types</div>
  {route_items}
  <div style="margin-bottom:10px;"></div>

  <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:6px;">Fire Hazard Zones</div>
  {fhsz_items}

  <div style="margin-top:10px; border-top:1px solid #f1f3f5; padding-top:8px;
              font-size:9px; color:#adb5bd;">
    Fire Evac Capacity Analysis
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Global map styles
# ---------------------------------------------------------------------------

def _build_global_styles() -> str:
    """Inject CSS to improve Leaflet default UI styling."""
    return """
<style>
  /* ---- Leaflet container font ---- */
  .leaflet-container {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  }

  /* ---- Layer control ---- */
  .leaflet-control-layers {
    font-family: system-ui, -apple-system, sans-serif !important;
    font-size: 12px !important;
    border-radius: 10px !important;
    border: 1px solid #dee2e6 !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.10) !important;
    overflow: hidden;
  }
  .leaflet-control-layers-toggle {
    border-radius: 10px !important;
  }
  .leaflet-control-layers-expanded {
    padding: 10px 12px !important;
  }
  .leaflet-control-layers-list {
    min-width: 170px;
  }
  .leaflet-control-layers label {
    display: flex !important;
    align-items: center !important;
    gap: 5px !important;
    margin-bottom: 5px !important;
    cursor: pointer;
    color: #333 !important;
  }
  .leaflet-control-layers-separator {
    margin: 6px 0 !important;
    border-top: 1px solid #f1f3f5 !important;
  }

  /* ---- Zoom control ---- */
  .leaflet-control-zoom {
    border-radius: 10px !important;
    border: 1px solid #dee2e6 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    overflow: hidden;
  }
  .leaflet-control-zoom a {
    font-family: system-ui, sans-serif !important;
    color: #333 !important;
  }

  /* ---- Popups ---- */
  .leaflet-popup-content-wrapper {
    border-radius: 10px !important;
    box-shadow: 0 6px 24px rgba(0,0,0,0.14) !important;
    border: 1px solid #dee2e6 !important;
  }
  .leaflet-popup-content {
    margin: 14px 16px !important;
  }
  .leaflet-popup-tip-container {
    margin-top: -1px;
  }

  /* ---- Tooltips ---- */
  .leaflet-tooltip {
    font-family: system-ui, -apple-system, sans-serif !important;
    font-size: 11px !important;
    border-radius: 6px !important;
    border: 1px solid #dee2e6 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.10) !important;
    padding: 4px 8px !important;
    color: #333 !important;
  }

  /* ---- Attribution ---- */
  .leaflet-control-attribution {
    font-family: system-ui, sans-serif !important;
    font-size: 10px !important;
    color: #adb5bd !important;
    border-radius: 6px 0 0 0 !important;
  }
</style>
"""


# ---------------------------------------------------------------------------
# Multi-project demo map
# ---------------------------------------------------------------------------

# Serving route colors keyed by determination tier.
# DISC = red (problem), MIN = green (OK), COND = orange (watch).
_TIER_ROUTE_COLOR = {
    "DISCRETIONARY":           "#d62728",
    "CONDITIONAL MINISTERIAL": "#e07000",
    "MINISTERIAL":             "#2ca02c",
}

# Flagged-route variant (darker / heavier weight)
_TIER_ROUTE_COLOR_FLAGGED = {
    "DISCRETIONARY":           "#a01010",
    "CONDITIONAL MINISTERIAL": "#a05000",
    "MINISTERIAL":             "#1a7a1a",
}

# Pastel traffic-load colors (background road layer, low opacity).
# Bucketed so we only create ~5 Leaflet layers instead of one per road.
_TRAFFIC_BG_BUCKETS = [
    (0.40, "#d6d6d6"),   # uncongested — light gray
    (0.60, "#f5dfc0"),   # moderate    — light peach
    (0.80, "#f5c096"),   # heavy       — light orange
    (1.00, "#f5a0a0"),   # near-cap    — light red
    (9999, "#ee8080"),   # over-cap    — coral
]

# Line weights (pixels) by OSM highway type.
# These approximate road width: at low zoom lines are thin and subtle;
# as the user zooms in they fill the actual road width and the v/c
# color coding becomes clearly legible.
_HIGHWAY_WEIGHT: dict = {
    "motorway":        12,
    "motorway_link":    7,
    "trunk":           11,
    "trunk_link":       6,
    "primary":          9,
    "primary_link":     5,
    "secondary":        7,
    "secondary_link":   4,
    "tertiary":         5,
    "tertiary_link":    3,
    "residential":      4,
    "living_street":    3,
    "unclassified":     3,
    "service":          2,
    "track":            2,
    "path":             1,
    "cycleway":         1,
}
_HIGHWAY_WEIGHT_DEFAULT = 3   # fallback for unknown types

# v/c weight multipliers — applied on top of the highway base weight so that
# congested roads are both a different color AND visibly thicker.
# Keyed by the traffic background color (same 5 buckets as _TRAFFIC_BG_BUCKETS).
_VC_WEIGHT_MULTIPLIER: dict = {
    "#d6d6d6": 0.6,   # v/c < 0.40 — uncongested: noticeably thinner
    "#f5dfc0": 0.85,  # v/c 0.40–0.60 — moderate
    "#f5c096": 1.1,   # v/c 0.60–0.80 — heavy: slightly above baseline
    "#f5a0a0": 1.45,  # v/c 0.80–1.00 — near capacity: clearly thicker
    "#ee8080": 1.9,   # v/c > 1.00    — over capacity: boldly thick
}


def _highway_weight(highway_val) -> float:
    """Return a line weight for an OSM highway value (which may be a list)."""
    if isinstance(highway_val, list):
        highway_val = highway_val[0] if highway_val else ""
    return _HIGHWAY_WEIGHT.get(str(highway_val or ""), _HIGHWAY_WEIGHT_DEFAULT)


def _traffic_weight(highway_val, vc_color: str) -> float:
    """
    Combine road-class base weight with a v/c congestion multiplier.
    Result is rounded to 0.5 px increments to keep (color, weight) bucket
    count low (≤ ~70) while still showing clear width differences.
    """
    base = _highway_weight(highway_val)
    mult = _VC_WEIGHT_MULTIPLIER.get(vc_color, 1.0)
    raw  = base * mult
    return round(raw * 2) / 2   # round to nearest 0.5


def _vc_background_color(vc: float) -> str:
    """Return a muted pastel color for the road traffic background layer."""
    for threshold, color in _TRAFFIC_BG_BUCKETS:
        if vc < threshold:
            return color
    return _TRAFFIC_BG_BUCKETS[-1][1]


def create_demo_map(
    projects: list,
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    config: dict,
    output_path: Path,
    demo_title: str = "Fire Evacuation Impact Analysis",
) -> Path:
    """
    Generate a multi-project comparison map.

    Visual hierarchy (bottom → top):
      1. CartoDB Positron base
      2. FHSZ fire zones (light fill)
      3. Traffic load background — all roads, thin, pastel-colored by v/c
      4. City boundary (dashed)
      5. Per-project FeatureGroup (serving routes + marker + radius)
         — only ONE visible at a time, controlled by panel dropdown

    Serving route color = determination tier (red=DISC, green=MIN, orange=COND)
    so the story is immediately legible without reading any labels.

    Returns the path to the saved HTML file.
    """
    import json
    from collections import defaultdict

    if not projects:
        raise ValueError("No projects to display.")

    vc_threshold = config.get("vc_threshold", 0.80)
    radius_miles = config.get("evacuation_route_radius_miles", 0.5)
    radius_meters = radius_miles * 1609.344

    all_lats = [p.location_lat for p in projects]
    all_lons = [p.location_lon for p in projects]
    center_lat = (min(all_lats) + max(all_lats)) / 2
    center_lon = (min(all_lons) + max(all_lons)) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="CartoDB positron",
    )
    map_js_name = m.get_name()
    roads_wgs84 = roads_gdf.to_crs("EPSG:4326")

    # ── Layer 1: FHSZ Fire Zones (drawn first — under everything) ─────────
    if not fhsz_gdf.empty and "HAZ_CLASS" in fhsz_gdf.columns:
        fhsz_wgs84 = fhsz_gdf.to_crs("EPSG:4326")
        for _, row in fhsz_wgs84.iterrows():
            haz = _to_int_safe(row.get("HAZ_CLASS", 0))
            color = FHSZ_COLORS.get(haz, "#ffeda0")
            label = FHSZ_LABELS.get(haz, f"Zone {haz}")
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _, c=color: {
                    "fillColor": c, "color": c,
                    "weight": 0.5, "fillOpacity": 0.20,
                },
                tooltip=label,
            ).add_to(m)

    # ── Layer 2: Traffic load background (all roads, pastel by v/c) ────────
    # Bucket by (color, weight) so line width approximates road width.
    # At low zoom lines are subtle; zooming in fills road width and makes the
    # v/c color coding clearly legible.  ~50 buckets vs ~5800 segments.
    if "vc_ratio" in roads_wgs84.columns:
        buckets: dict = defaultdict(list)
        for _, row in roads_wgs84.iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            vc     = float(row.get("vc_ratio", 0) or 0)
            color  = _vc_background_color(vc)
            weight = _traffic_weight(row.get("highway"), color)
            buckets[(color, weight)].append(mapping(row.geometry))

        for (color, weight), geoms in buckets.items():
            fc = {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": g, "properties": {}}
                    for g in geoms
                ],
            }
            folium.GeoJson(
                fc,
                style_function=lambda _, c=color, w=weight: {
                    "color": c, "weight": w, "opacity": 0.32,
                },
            ).add_to(m)

    # ── Layer 3: City Boundary (on top of background, under routes) ────────
    boundary_wgs84 = boundary_gdf.to_crs("EPSG:4326")
    for _, row in boundary_wgs84.iterrows():
        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _: {
                "fillColor": "none", "color": "#1a6eb5",
                "weight": 2, "dashArray": "8 5", "fillOpacity": 0,
            },
            tooltip="City Boundary",
        ).add_to(m)

    # ── Per-project FeatureGroups ──────────────────────────────────────────
    # Route color = tier (not a per-project unique color).
    # All groups are added to the map; JS immediately hides all but project 0.
    proj_js_names: list[str] = []

    for i, project in enumerate(projects):
        tier         = project.determination or "UNKNOWN"
        marker_color = _TIER_MARKER_COLOR.get(tier, "gray")
        route_color  = _TIER_ROUTE_COLOR.get(tier, "#7f7f7f")
        route_flagged_color = _TIER_ROUTE_COLOR_FLAGGED.get(tier, "#555")
        serving_set  = _osmid_set(project.serving_route_ids)
        flagged_set  = _osmid_set(project.flagged_route_ids)

        num_serving        = max(len(project.serving_route_ids or []), 1)
        project_vph_per_rt = project.project_vehicles_peak_hour / num_serving

        proj_group = folium.FeatureGroup(
            name=f"{project.project_name or f'Project {i+1}'} — {tier}",
            show=True,
        )
        proj_js_names.append(proj_group.get_name())

        # ---- Search radius (dashed circle, tier color) ----
        folium.Circle(
            location=[project.location_lat, project.location_lon],
            radius=radius_meters,
            color=route_color,
            weight=1.5,
            fill=True,
            fill_color=route_color,
            fill_opacity=0.04,
            dash_array="8 4",
            tooltip=f"{project.project_name} — {radius_miles} mi search radius",
        ).add_to(proj_group)

        # ---- Serving routes (tier-colored, thick) ----
        if serving_set and "osmid" in roads_wgs84.columns:
            serving_mask   = roads_wgs84["osmid"].apply(
                lambda o: _osmid_matches(o, serving_set)
            )
            serving_subset = roads_wgs84[serving_mask]

            for _, row in serving_subset.iterrows():
                if row.geometry is None or row.geometry.is_empty:
                    continue
                osmid_val   = row.get("osmid")
                is_flagged  = _osmid_matches(osmid_val, flagged_set)
                seg_color   = route_flagged_color if is_flagged else route_color
                weight      = 7 if is_flagged else 4

                name_str    = str(row.get("name", "Unnamed") or "Unnamed")
                vc_base     = float(row.get("vc_ratio", 0) or 0)
                los         = str(row.get("los", "?"))
                cap         = float(row.get("capacity_vph", 1) or 1)
                demand_base = float(row.get("baseline_demand_vph", 0) or 0)
                demand_prop = demand_base + project_vph_per_rt
                vc_proposed = demand_prop / cap if cap > 0 else vc_base

                popup_html = _build_route_impact_popup(
                    name_str, los, cap, demand_base, demand_prop,
                    vc_base, vc_proposed, vc_threshold,
                    project_vph_per_rt, is_flagged,
                )
                tip = (
                    f"{'⚠ ' if is_flagged else ''}{name_str} "
                    f"| v/c {vc_base:.3f} | {tier}"
                )
                folium.GeoJson(
                    mapping(row.geometry),
                    style_function=lambda _, c=seg_color, w=weight: {
                        "color": c, "weight": w, "opacity": 0.92,
                    },
                    popup=folium.Popup(popup_html, max_width=360),
                    tooltip=tip,
                ).add_to(proj_group)

        # ---- Project marker (drawn last — on top of routes) ----
        folium.Marker(
            location=[project.location_lat, project.location_lon],
            popup=folium.Popup(
                _build_demo_project_popup(project, route_color, vc_threshold),
                max_width=320,
            ),
            tooltip=f"{project.project_name} · {tier}",
            icon=folium.Icon(color=marker_color, icon="home", prefix="fa"),
        ).add_to(proj_group)

        proj_group.add_to(m)

    # ── Fixed panels ───────────────────────────────────────────────────────
    m.get_root().html.add_child(folium.Element(
        _build_demo_panel_html(
            projects, demo_title, config,
            proj_js_names=proj_js_names,
            map_js_name=map_js_name,
        )
    ))
    m.get_root().html.add_child(folium.Element(_build_demo_legend_html(config)))
    m.get_root().html.add_child(folium.Element(_build_global_styles()))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    logger.info(f"Demo map saved: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Demo legend (bottom-right)
# ---------------------------------------------------------------------------

def _build_demo_legend_html(config: dict) -> str:
    """
    Legend for the demo map.  Shows:
      • Evacuation route colors by determination tier
      • Traffic background load scale
      • FHSZ fire hazard zone colors
    """
    vc_threshold = config.get("vc_threshold", 0.80)

    route_tier_items = (
        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:28px; height:5px; '
        f'background:{_TIER_ROUTE_COLOR["DISCRETIONARY"]}; border-radius:2px; flex-shrink:0;"></span>'
        '<span style="color:#444;">Discretionary (DISC)</span></div>'

        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:28px; height:5px; '
        f'background:{_TIER_ROUTE_COLOR["CONDITIONAL MINISTERIAL"]}; border-radius:2px; flex-shrink:0;"></span>'
        '<span style="color:#444;">Cond. Ministerial</span></div>'

        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:28px; height:5px; '
        f'background:{_TIER_ROUTE_COLOR["MINISTERIAL"]}; border-radius:2px; flex-shrink:0;"></span>'
        '<span style="color:#444;">Ministerial (MIN)</span></div>'
    )

    traffic_labels = [
        "v/c < 0.40 — uncongested",
        "v/c 0.40–0.60 — moderate",
        "v/c 0.60–0.80 — heavy",
        "v/c 0.80–1.00 — near capacity",
        "v/c > 1.00 — over capacity",
    ]
    traffic_items = "".join(
        f'<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:28px; height:5px; '
        f'background:{color}; border-radius:2px; flex-shrink:0; opacity:0.9;"></span>'
        f'<span style="color:#555;">{label}</span></div>'
        for (_, color), label in zip(_TRAFFIC_BG_BUCKETS, traffic_labels)
    )

    fhsz_items = "".join(
        f'<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:13px; height:13px; '
        f'background:{FHSZ_COLORS[k]}; opacity:0.65; border-radius:2px; '
        f'border:1px solid rgba(0,0,0,0.1); flex-shrink:0;"></span>'
        f'<span style="color:#444;">{FHSZ_LABELS[k]}</span></div>'
        for k in sorted(FHSZ_COLORS)
    )

    return f"""
<div id="map-legend" style="
    position: fixed;
    bottom: 26px; right: 10px;
    z-index: 9999;
    width: 200px;
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 13px 14px;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 11px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.11);
    line-height: 1.4;
">
  <div style="font-weight:700; font-size:12px; color:#212529; margin-bottom:10px;
              border-bottom:1px solid #f1f3f5; padding-bottom:7px;">Legend</div>

  <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:6px;">Evacuation Routes</div>
  {route_tier_items}
  <div style="font-size:10px; color:#adb5bd; margin-top:2px; margin-bottom:10px;">
    Darker = at or above v/c {vc_threshold:.2f}
  </div>

  <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:6px;">Traffic Load (background)</div>
  {traffic_items}
  <div style="margin-bottom:10px;"></div>

  <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:6px;">Fire Hazard Zones</div>
  {fhsz_items}

  <div style="margin-top:10px; border-top:1px solid #f1f3f5; padding-top:8px;
              font-size:9px; color:#adb5bd;">AB 747 Fire Evac Capacity Analysis</div>
</div>
"""


# ---------------------------------------------------------------------------
# Demo panel (left sidebar — dropdown + project card)
# ---------------------------------------------------------------------------

def _build_demo_panel_html(
    projects: list,
    demo_title: str,
    config: dict,
    proj_js_names: list,
    map_js_name: str,
) -> str:
    """
    Fixed top-left panel for the demo map.

    Structure:
      ┌─ Header (title + collapse) ────────────────────┐
      │  [▼ Dropdown: select project          ]        │
      ├─ Body (project card for selected project) ──────┤
      │  [TIER BADGE]  Name / address                  │
      │  Standards checklist (Std 1–4)                 │
      │  Impact metrics                                │
      │  Determination reason (truncated)              │
      └────────────────────────────────────────────────┘

    All project detail cards are pre-rendered as hidden divs; JS shows the
    active one.  selectProject(idx) also calls map.addLayer / removeLayer.
    """
    import json

    vc_threshold  = config.get("vc_threshold", 0.80)
    unit_threshold = config.get("unit_threshold", 50)
    proj_js_array = json.dumps(proj_js_names)

    # ── Dropdown options ──────────────────────────────────────────────────
    tier_abbr_map = {
        "DISCRETIONARY":           "DISC",
        "CONDITIONAL MINISTERIAL": "COND",
        "MINISTERIAL":             "MIN",
    }
    options_html = ""
    for i, p in enumerate(projects):
        tier  = p.determination or "UNKNOWN"
        abbr  = tier_abbr_map.get(tier, tier[:4])
        label = f"{p.project_name or f'Project {i+1}'}  ·  {abbr}  ({p.dwelling_units} units)"
        options_html += f'<option value="{i}">{label}</option>\n'

    # ── Per-project detail cards (hidden by default, shown by JS) ─────────
    detail_cards_html = ""
    for i, p in enumerate(projects):
        detail_cards_html += _build_project_detail_div(
            i, p, config, vc_threshold, unit_threshold
        )

    # ── Full panel HTML + JS ──────────────────────────────────────────────
    return f"""
<div id="demo-panel" style="
    position: fixed;
    top: 10px; left: 10px;
    z-index: 9999;
    width: 308px;
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.13);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px;
    overflow: hidden;
">

  <!-- ── Header ─────────────────────────────────────────────────────── -->
  <div style="
      background: #f8f9fa;
      padding: 10px 13px 9px;
      border-bottom: 1px solid #dee2e6;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      cursor: pointer;
      user-select: none;
  " onclick="toggleDemoPanel()">
    <div style="flex:1; min-width:0;">
      <div style="font-size:10px; color:#868e96; text-transform:uppercase;
                  letter-spacing:0.6px; margin-bottom:2px;">
        Fire Evacuation Analysis
      </div>
      <div style="font-size:13px; font-weight:700; color:#212529;
                  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
        {demo_title}
      </div>
    </div>
    <button id="demo-toggle-btn"
            style="background:none; border:none; cursor:pointer;
                   font-size:14px; color:#adb5bd; padding:0 0 0 8px;
                   line-height:1; margin-top:2px; flex-shrink:0;">▼</button>
  </div>

  <!-- ── Body ───────────────────────────────────────────────────────── -->
  <div id="demo-panel-body" style="overflow:hidden;">

    <!-- Dropdown project selector -->
    <div style="padding:10px 13px 8px; border-bottom:1px solid #f1f3f5;">
      <label style="font-size:10px; color:#868e96; text-transform:uppercase;
                    letter-spacing:0.5px; display:block; margin-bottom:5px;">
        Select Project
      </label>
      <select id="proj-dropdown"
              onchange="selectProject(this.selectedIndex)"
              style="width:100%; padding:7px 10px;
                     border:1px solid #ced4da; border-radius:7px;
                     font-family:inherit; font-size:12px; color:#212529;
                     background:white; cursor:pointer;
                     box-shadow:0 1px 3px rgba(0,0,0,0.06);">
        {options_html}
      </select>
    </div>

    <!-- Project detail cards (one shown at a time) -->
    <div style="max-height:calc(90vh - 130px); overflow-y:auto;">
      {detail_cards_html}
    </div>

  </div>
</div>

<script>
(function () {{

  var PROJECT_LAYERS = {proj_js_array};
  var MAP_NAME = '{map_js_name}';

  // ── Show one project, hide all others ──────────────────────────────
  window.selectProject = function (idx) {{
    var mapObj = window[MAP_NAME];
    if (!mapObj) return;

    // Map layer visibility
    PROJECT_LAYERS.forEach(function (varName, i) {{
      var layer = window[varName];
      if (!layer) return;
      if (i === idx) {{
        if (!mapObj.hasLayer(layer)) mapObj.addLayer(layer);
      }} else {{
        if (mapObj.hasLayer(layer)) mapObj.removeLayer(layer);
      }}
    }});

    // Project card visibility
    document.querySelectorAll('.proj-detail-card').forEach(function (el, i) {{
      el.style.display = (i === idx) ? 'block' : 'none';
    }});

    // Keep dropdown in sync (called from JS too, not just onchange)
    var dd = document.getElementById('proj-dropdown');
    if (dd && dd.selectedIndex !== idx) dd.selectedIndex = idx;
  }};

  // ── Collapse / expand ──────────────────────────────────────────────
  window.toggleDemoPanel = function () {{
    var body = document.getElementById('demo-panel-body');
    var btn  = document.getElementById('demo-toggle-btn');
    body.style.display = (body.style.display === 'none') ? 'block' : 'none';
    btn.textContent    = (body.style.display === 'none') ? '▶' : '▼';
  }};

  // ── Init: show only project 0 ──────────────────────────────────────
  setTimeout(function () {{ window.selectProject(0); }}, 0);

}})();
</script>
"""


def _build_project_detail_div(
    idx: int,
    project,
    config: dict,
    vc_threshold: float,
    unit_threshold: int,
) -> str:
    """
    Pre-rendered hidden card for one project.  JS toggles display:block/none.
    """
    tier         = project.determination or "UNKNOWN"
    det_color    = _TIER_CSS_COLOR.get(tier, "#555")
    bg_color     = _TIER_BG_COLOR.get(tier, "#fafafa")
    border_color = _TIER_BORDER_COLOR.get(tier, "#dee2e6")
    route_color  = _TIER_ROUTE_COLOR.get(tier, "#7f7f7f")

    n_srv  = len(project.serving_route_ids or [])
    n_flg  = len(project.flagged_route_ids or [])
    in_fz  = project.in_fire_zone
    fz_str = f"Zone {project.fire_zone_level}" if in_fz else "Not in FHSZ"
    fz_color = "#c0392b" if in_fz else "#27ae60"

    # Standards checklist
    def std_row(label, triggered, detail=""):
        chip_bg    = "#fde8e8" if triggered else "#e8f5e9"
        chip_color = "#c0392b" if triggered else "#27ae60"
        chip_text  = "YES" if triggered else "NO"
        return (
            f'<div style="display:flex; justify-content:space-between; '
            f'align-items:center; padding:4px 0; border-bottom:1px solid #f8f9fa;">'
            f'<div>'
            f'<span style="color:#444; font-size:11px;">{label}</span>'
            + (f'<span style="color:#adb5bd; font-size:10px;"> — {detail}</span>' if detail else '')
            + f'</div>'
            f'<span style="padding:2px 8px; border-radius:9px; font-size:10px; '
            f'font-weight:700; background:{chip_bg}; color:{chip_color}; '
            f'flex-shrink:0; margin-left:8px;">{chip_text}</span>'
            f'</div>'
        )

    standards_html = (
        std_row("Std 1 · Citywide FHSZ",
                project.in_fire_zone or n_srv > 0,
                "city has FHSZ zones")
        + std_row("Std 2 · Size threshold",
                  project.meets_size_threshold,
                  f"{project.dwelling_units} of {unit_threshold} units")
        + std_row("Std 3 · Serving routes",
                  n_srv > 0,
                  f"{n_srv} segment(s) within {project.search_radius_miles} mi")
        + std_row("Std 4 · Capacity exceeded",
                  project.exceeds_capacity_threshold,
                  f"v/c ≥ {vc_threshold:.2f} on {n_flg} route(s)")
    )

    # Determination reason — first two sentences
    reason = project.determination_reason or ""
    sentences = [s.strip() for s in reason.split(".") if s.strip()]
    reason_short = ". ".join(sentences[:2]) + ("." if sentences else "")

    display = "block" if idx == 0 else "none"

    return f"""
<div class="proj-detail-card" style="display:{display}; padding:0;">

  <!-- Tier badge header -->
  <div style="background:{bg_color}; padding:11px 13px 10px;
              border-bottom:1px solid {border_color};">
    <div style="font-size:16px; font-weight:800; color:{det_color};
                letter-spacing:-0.3px;">
      {tier}
    </div>
    <div style="font-size:11px; color:#444; margin-top:1px; font-weight:500;">
      {project.project_name or 'Proposed Project'}
    </div>
    {f'<div style="font-size:10px; color:#666; margin-top:1px;">{project.address}</div>' if project.address else ''}
  </div>

  <!-- Quick info strip -->
  <div style="display:flex; gap:0; border-bottom:1px solid #f1f3f5;">
    <div style="flex:1; padding:8px 13px; border-right:1px solid #f1f3f5;">
      <div style="font-size:10px; color:#adb5bd; text-transform:uppercase;
                  letter-spacing:0.4px;">Units</div>
      <div style="font-size:16px; font-weight:700; color:#212529;">
        {project.dwelling_units}
      </div>
    </div>
    <div style="flex:1; padding:8px 13px; border-right:1px solid #f1f3f5;">
      <div style="font-size:10px; color:#adb5bd; text-transform:uppercase;
                  letter-spacing:0.4px;">Peak vph</div>
      <div style="font-size:16px; font-weight:700; color:{route_color};">
        {project.project_vehicles_peak_hour:.0f}
      </div>
    </div>
    <div style="flex:1; padding:8px 13px;">
      <div style="font-size:10px; color:#adb5bd; text-transform:uppercase;
                  letter-spacing:0.4px;">Fire zone</div>
      <div style="font-size:12px; font-weight:600; color:{fz_color}; margin-top:2px;">
        {fz_str}
      </div>
    </div>
  </div>

  <!-- Standards checklist -->
  <div style="padding:10px 13px 4px;">
    <div style="font-size:10px; color:#adb5bd; text-transform:uppercase;
                letter-spacing:0.5px; margin-bottom:6px;">Standards</div>
    {standards_html}
  </div>

  <!-- Serving route impact -->
  <div style="padding:8px 13px; border-top:1px solid #f1f3f5;">
    <div style="font-size:10px; color:#adb5bd; text-transform:uppercase;
                letter-spacing:0.5px; margin-bottom:5px;">Route Impact</div>
    <div style="display:flex; gap:16px; font-size:11px; color:#555;">
      <div>{n_srv} serving segments</div>
      <div style="color:{'#c0392b' if n_flg > 0 else '#27ae60'};">
        {n_flg} at v/c ≥ {vc_threshold:.2f}
      </div>
    </div>
    <div style="font-size:10px; color:#adb5bd; margin-top:3px;">
      Click any route on the map for baseline → proposed v/c detail
    </div>
  </div>

  <!-- Determination reason -->
  <div style="padding:8px 13px 12px; border-top:1px solid #f1f3f5;">
    <div style="font-size:10px; color:#adb5bd; text-transform:uppercase;
                letter-spacing:0.5px; margin-bottom:5px;">Basis</div>
    <div style="font-size:10px; color:#555; line-height:1.55;
                font-style:italic;">
      {reason_short[:240]}
    </div>
  </div>

</div>
"""


# ---------------------------------------------------------------------------
# Demo project marker popup
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

    # Short determination reason (first sentence only)
    reason_short = (project.determination_reason or "").split(".")[0] + "."

    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif; '
        'font-size:12px; min-width:270px; max-width:310px; line-height:1.5;">'

        # Tier badge header
        f'<div style="background:{bg_color}; margin:-14px -16px 12px; '
        f'padding:10px 14px; border-bottom:1px solid #dee2e6; '
        f'border-radius:8px 8px 0 0;">'
        f'<div style="font-size:15px; font-weight:700; color:{det_color};">{det}</div>'
        f'<div style="font-size:11px; color:#444; margin-top:1px;">'
        f'{project.project_name or "Project"}'
        f'</div>'
        f'</div>'

        # Project details
        f'<div style="font-size:11px; color:#555; margin-bottom:10px;">'
        f'{project.address or ""}'
        f'<br>{project.dwelling_units} dwelling units'
        f' &nbsp;·&nbsp; {project.location_lat:.4f}, {project.location_lon:.4f}'
        f'<br>Fire zone: {in_zone}'
        f'</div>'

        # Standards table
        '<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">'
        + std_row("Std 2 · Size", project.meets_size_threshold,
                  f"{project.dwelling_units} units")
        + std_row("Std 3 · Routes", bool(n_srv), f"{n_srv} segs")
        + std_row("Std 4 · Capacity", project.exceeds_capacity_threshold,
                  f"{n_flg} flagged")
        + '</table>'

        # Impact line
        f'<div style="font-size:11px; color:#444; border-top:1px solid #f1f3f5; '
        f'padding-top:8px; margin-top:4px;">'
        f'Peak vehicles generated: '
        f'<strong style="color:{proj_color};">'
        f'{project.project_vehicles_peak_hour:.0f} vph</strong>'
        f'</div>'

        # Short reason
        f'<div style="font-size:10px; color:#868e96; margin-top:6px; '
        f'font-style:italic; line-height:1.4;">'
        f'{reason_short[:180]}'
        f'</div>'

        '</div>'
    )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _to_int_safe(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0

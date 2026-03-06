"""
Evaluation map: single-project interactive Folium map.

Entry point: create_evaluation_map()

UX: city-planner workflow — one clear answer (ministerial/discretionary),
standards checklist panel, unified serving/flagged route layers, eye-toggle legend.
"""
import logging
from pathlib import Path

import folium
import geopandas as gpd
from shapely.geometry import mapping

from models.project import Project

from .themes import (
    LOS_COLORS, FHSZ_COLORS, FHSZ_LABELS,
    _TIER_MARKER_COLOR, _TIER_CSS_COLOR, _TIER_BG_COLOR, _TIER_BORDER_COLOR,
    SERVING_ROUTE_COLOR, FLAGGED_ROUTE_COLOR,
)
from .helpers import (
    _osmid_set, _osmid_matches, _to_int_safe,
    _highway_weight, _add_zoom_weight_scaler, _build_global_styles,
    _brief_filename,
)
from .popups import _build_route_impact_popup, _build_project_popup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audit extraction helper
# ---------------------------------------------------------------------------

def _extract_audit_data(project: Project, audit: dict | None) -> dict:
    """Pull per-scenario data from audit into a flat structure."""
    serving_set = _osmid_set(project.serving_route_ids)
    flagged_set = _osmid_set(project.flagged_route_ids)

    # Defaults (no audit)
    std1_triggered: bool = bool(project.in_fire_zone or serving_set)
    wildland_serving_set: set = serving_set
    wildland_flagged_set: set = flagged_set
    already_failing_list: list = []
    local5_serving_set: set = set()
    local5_flagged_set: set = set()
    local5_applicable: bool = False
    local5_n_serving: int = 0

    if audit:
        w = audit.get("scenarios", {}).get("wildland_ab747", {})
        w_steps = w.get("steps", {})

        s1 = w_steps.get("step1_applicability", {})
        std1_triggered = s1.get("city_in_fhsz", std1_triggered)

        s3w = w_steps.get("step3_routes", {})
        wildland_osmids = [r["osmid"] for r in s3w.get("serving_routes", [])]
        if wildland_osmids:
            wildland_serving_set = _osmid_set(wildland_osmids)

        s5w = w_steps.get("step5_ratio_test", {})
        wildland_flagged_set = _osmid_set(s5w.get("flagged_route_ids", []))
        already_failing_list = s5w.get("already_failing_at_baseline", [])

        ld = audit.get("scenarios", {}).get("local_density_sb79", {})
        local5_applicable = ld.get("tier", "NOT_APPLICABLE") != "NOT_APPLICABLE"
        if local5_applicable:
            ld_steps = ld.get("steps", {})
            s3ld = ld_steps.get("step3_routes", {})
            s5ld = ld_steps.get("step5_ratio_test", {})
            local5_serving_set = _osmid_set(
                [r["osmid"] for r in s3ld.get("serving_routes", [])]
            )
            local5_flagged_set = _osmid_set(s5ld.get("flagged_route_ids", []))
            local5_n_serving = s3ld.get("serving_route_count", 0)

    return {
        "std1_triggered":        std1_triggered,
        "wildland_serving_set":  wildland_serving_set,
        "wildland_flagged_set":  wildland_flagged_set,
        "already_failing_set":   _osmid_set(already_failing_list),
        "already_failing_count": len(already_failing_list),
        "local5_serving_set":    local5_serving_set,
        "local5_flagged_set":    local5_flagged_set,
        "local5_applicable":     local5_applicable,
        "local5_n_serving":      local5_n_serving,
        # unified flagged = wildland ∪ local5
        "all_flagged_set":       wildland_flagged_set | local5_flagged_set,
    }


# ---------------------------------------------------------------------------
# Route layer builder
# ---------------------------------------------------------------------------

def _add_serving_routes(
    roads_wgs84: gpd.GeoDataFrame,
    osmid_set: set,
    all_flagged_set: set,
    already_failing_set: set,
    project_vph_per_route: float,
    vc_threshold: float,
    feature_group: folium.FeatureGroup,
) -> None:
    """Add serving route features to a FeatureGroup using unified colors."""
    if not osmid_set or "osmid" not in roads_wgs84.columns:
        return
    mask = roads_wgs84["osmid"].apply(lambda o: _osmid_matches(o, osmid_set))
    for _, row in roads_wgs84[mask].iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        osmid_val       = row.get("osmid")
        is_flagged      = _osmid_matches(osmid_val, all_flagged_set)
        is_pre_congested = _osmid_matches(osmid_val, already_failing_set)

        name_str     = str(row.get("name", "Unnamed") or "Unnamed")
        vc_base      = float(row.get("vc_ratio", 0) or 0)
        los          = str(row.get("los", "?"))
        cap          = float(row.get("capacity_vph", 1) or 1)
        demand_base  = float(row.get("baseline_demand_vph", 0) or 0)
        demand_prop  = demand_base + project_vph_per_route
        vc_proposed  = demand_prop / cap if cap > 0 else vc_base

        color  = FLAGGED_ROUTE_COLOR if is_flagged else SERVING_ROUTE_COLOR
        weight = 5 if is_flagged else 3

        popup_html = _build_route_impact_popup(
            name_str, los, cap, demand_base, demand_prop,
            vc_base, vc_proposed, vc_threshold, project_vph_per_route,
            is_flagged, already_failing=is_pre_congested,
        )
        if is_flagged:
            tip_pfx = "⚠ FLAGGED"
        elif is_pre_congested:
            tip_pfx = "ℹ pre-congested"
        else:
            tip_pfx = "→"
        tip = f"{tip_pfx} {name_str} | LOS {los} | v/c {vc_base:.3f}"

        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _, c=color, w=weight: {
                "color": c, "weight": w, "opacity": 1.0,
            },
            popup=folium.Popup(popup_html, max_width=360),
            tooltip=tip,
        ).add_to(feature_group)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def create_evaluation_map(
    project: Project,
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    config: dict,
    output_path: Path,
    audit: dict = None,
) -> Path:
    """Generate an interactive Folium HTML map for a project evaluation."""
    lat, lon       = project.location_lat, project.location_lon
    vc_threshold   = config.get("vc_threshold", 0.95)
    radius_miles   = config.get("evacuation_route_radius_miles", 0.5)
    ld_radius      = config.get("local_density", {}).get("radius_miles", 0.25)

    ad = _extract_audit_data(project, audit)
    num_serving = max(len(project.serving_route_ids or []), 1)
    project_vph_per_route = project.project_vehicles_peak_hour / num_serving

    roads_wgs84 = roads_gdf.to_crs("EPSG:4326")

    m = folium.Map(location=[lat, lon], zoom_start=14, tiles="CartoDB positron")

    # ── Layer 1: City Boundary ────────────────────────────────────────────
    boundary_layer = folium.FeatureGroup(name="City Boundary", show=True)
    boundary_wgs84 = boundary_gdf.to_crs("EPSG:4326")
    for _, row in boundary_wgs84.iterrows():
        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _: {
                "fillColor": "none", "color": "#1a6eb5",
                "weight": 2, "dashArray": "8 5", "fillOpacity": 0,
            },
            tooltip="City Boundary",
        ).add_to(boundary_layer)
    boundary_layer.add_to(m)

    # ── Layer 2: FHSZ Fire Zones (Std 1) ─────────────────────────────────
    fhsz_layer = folium.FeatureGroup(name="Std 1 · FHSZ Fire Zones", show=True)
    if not fhsz_gdf.empty and "HAZ_CLASS" in fhsz_gdf.columns:
        fhsz_wgs84 = fhsz_gdf.to_crs("EPSG:4326")
        for _, row in fhsz_wgs84.iterrows():
            haz   = _to_int_safe(row.get("HAZ_CLASS", 0))
            color = FHSZ_COLORS.get(haz, "#ffeda0")
            label = FHSZ_LABELS.get(haz, f"Zone {haz}")
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _, c=color: {
                    "fillColor": c, "color": c, "weight": 1, "fillOpacity": 0.30,
                },
                tooltip=label,
            ).add_to(fhsz_layer)
    fhsz_layer.add_to(m)

    # ── Layer 3: All Roads (LOS background) — off by default ─────────────
    all_roads_layer = folium.FeatureGroup(name="Road Network (LOS)", show=False)
    if "los" in roads_wgs84.columns:
        for _, row in roads_wgs84.iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            los   = str(row.get("los", "C"))
            color = LOS_COLORS.get(los, "#aaaaaa")
            name_str = str(row.get("name", "Unnamed") or "Unnamed")
            vc    = row.get("vc_ratio", 0)
            cap   = row.get("capacity_vph", 0)
            weight = max(_highway_weight(row.get("highway", "")) * 0.40, 1.0)
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _, c=color, w=weight: {
                    "color": c, "weight": w, "opacity": 0.50,
                },
                tooltip=f"{name_str} | LOS {los} | v/c {vc:.2f} | {cap:.0f} vph cap",
            ).add_to(all_roads_layer)
    all_roads_layer.add_to(m)

    # ── Layer 4: Wildland Serving Routes (Std 3) — steel blue ────────────
    serving_wildland_group = folium.FeatureGroup(
        name=f"Std 3 · Wildland routes ({radius_miles} mi)", show=True
    )
    _add_serving_routes(
        roads_wgs84, ad["wildland_serving_set"], ad["all_flagged_set"],
        ad["already_failing_set"], project_vph_per_route, vc_threshold,
        serving_wildland_group,
    )
    serving_wildland_group.add_to(m)

    # ── Layer 5: Flagged Routes glow overlay (Std 4) ─────────────────────
    flagged_group = folium.FeatureGroup(
        name="Std 4 · Flagged routes (v/c exceeded)", show=True
    )
    if ad["all_flagged_set"] and "osmid" in roads_wgs84.columns:
        flg_mask = roads_wgs84["osmid"].apply(
            lambda o: _osmid_matches(o, ad["all_flagged_set"])
        )
        for _, row in roads_wgs84[flg_mask].iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            name_str = str(row.get("name", "Unnamed") or "Unnamed")
            vc  = float(row.get("vc_ratio", 0) or 0)
            los = str(row.get("los", "F"))
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _: {
                    "color": FLAGGED_ROUTE_COLOR, "weight": 14, "opacity": 0.20,
                },
                tooltip=f"⚠ CAPACITY EXCEEDED: {name_str} | LOS {los} | v/c {vc:.3f}",
            ).add_to(flagged_group)
    flagged_group.add_to(m)

    # ── Layer 6: Local Egress Routes (Std 5) — same serving color ────────
    serving_local5_group = folium.FeatureGroup(
        name=f"Std 5 · Local routes ({ld_radius} mi)",
        show=ad["local5_applicable"],
    )
    if ad["local5_applicable"] and ad["local5_serving_set"]:
        _add_serving_routes(
            roads_wgs84, ad["local5_serving_set"], ad["all_flagged_set"],
            ad["already_failing_set"], project_vph_per_route, vc_threshold,
            serving_local5_group,
        )
    serving_local5_group.add_to(m)

    # ── Layer 7: Search Radius Buffer ─────────────────────────────────────
    buffer_layer = folium.FeatureGroup(
        name=f"Search Radius ({radius_miles} mi)", show=True
    )
    folium.Circle(
        location=[lat, lon], radius=radius_miles * 1609.344,
        color="#6c757d", weight=1.5, fill=True,
        fill_color="#adb5bd", fill_opacity=0.07, dash_array="10 5",
        tooltip=f"Evacuation route search radius — {radius_miles} mi",
    ).add_to(buffer_layer)
    buffer_layer.add_to(m)

    # ── Layer 8: Project Marker ───────────────────────────────────────────
    det = project.determination or "UNKNOWN"
    project_layer = folium.FeatureGroup(name="Project Marker", show=True)
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(
            _build_project_popup(project, ad["wildland_serving_set"], vc_threshold),
            max_width=300,
        ),
        tooltip=f"Project · {det}",
        icon=folium.Icon(
            color=_TIER_MARKER_COLOR.get(det, "gray"), icon="home", prefix="fa"
        ),
    ).add_to(project_layer)
    project_layer.add_to(m)

    # ── Fixed HTML panels ──────────────────────────────────────────────────
    js_names = {
        "map":              m.get_name(),
        "fhsz":             fhsz_layer.get_name(),
        "serving_wildland": serving_wildland_group.get_name(),
        "flagged":          flagged_group.get_name(),
        "serving_local5":   serving_local5_group.get_name(),
    }

    m.get_root().html.add_child(folium.Element(
        _build_project_card_html(project, ad, config)
    ))
    m.get_root().html.add_child(folium.Element(
        _build_legend_html(config, ad, js_names)
    ))
    m.get_root().html.add_child(folium.Element(_build_global_styles()))
    _add_zoom_weight_scaler(m, ref_zoom=14)

    folium.LayerControl(collapsed=True).add_to(m)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    logger.info(f"Map saved: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Project Card panel — standards checklist
# ---------------------------------------------------------------------------

def _build_project_card_html(project: Project, ad: dict, config: dict) -> str:
    det          = project.determination or "UNKNOWN"
    det_color    = _TIER_CSS_COLOR.get(det, "#555555")
    bg_color     = _TIER_BG_COLOR.get(det, "#fafafa")
    border_color = _TIER_BORDER_COLOR.get(det, "#dee2e6")
    display_name = project.project_name or "Proposed Project"
    vc_threshold = config.get("vc_threshold", 0.95)
    unit_thresh  = project.size_threshold_used or config.get("unit_threshold", 50)
    radius_mi    = getattr(project, "search_radius_miles", None) or config.get(
        "evacuation_route_radius_miles", 0.5
    )

    def info_row(label: str, value: str, color: str = "#222") -> str:
        return (
            f'<div style="display:flex; justify-content:space-between; '
            f'align-items:baseline; margin-bottom:3px;">'
            f'<span style="color:#6c757d; font-size:11px;">{label}</span>'
            f'<span style="color:{color}; font-weight:500; font-size:11px; text-align:right; '
            f'max-width:160px; overflow:hidden; text-overflow:ellipsis; '
            f'white-space:nowrap;">{value}</span>'
            f'</div>'
        )

    def std_row(icon: str, label: str, detail: str = "", note: str = "") -> str:
        icon_color = "#27ae60" if icon == "✓" else "#adb5bd"
        html = (
            f'<div style="display:flex; align-items:flex-start; '
            f'margin-bottom:6px; gap:6px;">'
            f'<span style="font-size:13px; line-height:1.35; flex-shrink:0; '
            f'color:{icon_color};">{icon}</span>'
            f'<div style="flex:1;">'
            f'<div style="font-size:11px; color:#333;">{label}</div>'
        )
        if detail:
            html += (
                f'<div style="font-size:10px; color:#868e96; margin-top:1px;">'
                f'{detail}</div>'
            )
        if note:
            html += (
                f'<div style="font-size:10px; color:#6c757d; margin-top:3px; '
                f'font-style:italic; line-height:1.4;">{note}</div>'
            )
        html += '</div></div>'
        return html

    # Standard states
    std1_ok  = ad["std1_triggered"]
    std2_ok  = project.meets_size_threshold
    n_wld    = len(project.serving_route_ids or [])
    std3_ok  = n_wld > 0
    std4_ok  = project.exceeds_capacity_threshold   # True = flagged = discretionary trigger
    n_flagged = len(project.flagged_route_ids or [])
    n_already = ad["already_failing_count"]
    local5_ok = ad["local5_applicable"]
    local5_triggered = bool(ad["local5_flagged_set"])
    n_local5  = ad["local5_n_serving"]

    # Std 4 explanatory note when not triggered
    std4_note = ""
    if std2_ok and std3_ok and not std4_ok:
        if n_already > 0:
            std4_note = (
                f"No serving route was pushed across v/c {vc_threshold:.2f} "
                f"by this project. ({n_already} routes already failing at "
                f"baseline — pre-existing congestion.)"
            )
        else:
            std4_note = (
                f"No serving route crosses v/c {vc_threshold:.2f} with this project."
            )

    std4_icon   = "✓" if std4_ok else "✗"
    std4_label  = (
        f"Std 4  {n_flagged} route(s) flagged"
        if std4_ok
        else f"Std 4  0 routes flagged"
    )
    std4_detail = f"v/c {vc_threshold:.2f} threshold — marginal causation test"

    if local5_ok:
        std5_icon   = "✓" if local5_triggered else "✗"
        std5_label  = f"Std 5  {n_local5} local segment(s)"
        std5_detail = f"within 0.25 mi of project site"
    else:
        std5_icon   = "—"
        std5_label  = "Std 5  Local density"
        std5_detail = "disabled (not enabled in config)"

    std5_icon_color = "#adb5bd"   # always muted for disabled/not triggered

    def std5_row_html() -> str:
        ic = std5_icon_color
        return (
            f'<div style="display:flex; align-items:flex-start; '
            f'margin-bottom:6px; gap:6px;">'
            f'<span style="font-size:13px; line-height:1.35; flex-shrink:0; '
            f'color:{ic};">{std5_icon}</span>'
            f'<div style="flex:1;">'
            f'<div style="font-size:11px; color:{"#333" if local5_ok else "#adb5bd"};">'
            f'{std5_label}</div>'
            f'<div style="font-size:10px; color:#868e96; margin-top:1px;">'
            f'{std5_detail}</div>'
            f'</div></div>'
        )

    standards_html = (
        std_row("✓" if std1_ok else "✗",
                "Std 1  City in FHSZ zone",
                "City contains FHSZ zones" if std1_ok else "No FHSZ zones in city")
        + std_row("✓" if std2_ok else "✗",
                  f"Std 2  {project.dwelling_units} ≥ {unit_thresh} units",
                  f"{project.dwelling_units} units vs {unit_thresh} threshold")
        + std_row("✓" if std3_ok else "✗",
                  f"Std 3  {n_wld} serving routes found",
                  f"within {radius_mi} mi of project site")
        + std_row(std4_icon, std4_label, std4_detail, note=std4_note)
        + std5_row_html()
    )

    # Determination pill
    det_pill = (
        f'<div style="margin:10px 0 14px; padding:8px 12px; border-radius:8px; '
        f'background:{bg_color}; border:1.5px solid {border_color}; text-align:center;">'
        f'<div style="font-size:9px; color:#868e96; text-transform:uppercase; '
        f'letter-spacing:0.6px; margin-bottom:3px;">Determination</div>'
        f'<div style="font-size:15px; font-weight:800; color:{det_color}; '
        f'line-height:1.2;">{det}</div>'
        f'</div>'
    )

    project_info = (
        info_row("Project", display_name[:30])
        + (info_row("Address", project.address[:30]) if project.address else "")
        + (info_row("APN", project.apn) if project.apn else "")
        + info_row("Units", str(project.dwelling_units))
        + info_row("Location",
                   f"{project.location_lat:.4f}, {project.location_lon:.4f}")
        + info_row("Peak vehicles added",
                   f"{project.project_vehicles_peak_hour:.0f} vph",
                   SERVING_ROUTE_COLOR)
    )

    return f"""
<div id="proj-card" style="
    position: fixed; top: 10px; left: 10px; z-index: 9999;
    width: 295px; background: white;
    border: 1px solid {border_color}; border-left: 4px solid {det_color};
    border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.13);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px; overflow: hidden;
">
  <div id="proj-card-header" style="
      background: {bg_color}; padding: 11px 14px 10px; cursor: pointer;
      display: flex; justify-content: space-between; align-items: flex-start;
      border-bottom: 1px solid {border_color}; user-select: none;
  " onclick="toggleProjCard()">
    <div>
      <div style="font-size:10px; color:#868e96; text-transform:uppercase;
                  letter-spacing:0.6px; margin-bottom:2px;">Fire Evacuation Analysis</div>
      <div style="font-size:15px; font-weight:700; color:{det_color}; line-height:1.2;">
        {det}
      </div>
      <div style="font-size:10px; color:#555; margin-top:3px;">{display_name[:28]}</div>
    </div>
    <button id="proj-toggle-btn" style="
        background:none; border:none; cursor:pointer; font-size:14px;
        color:#868e96; padding:0 0 0 8px; line-height:1; margin-top:2px;">▼</button>
  </div>

  <div id="proj-card-body" style="padding: 13px 14px; display:block;">
    {det_pill}
    <div style="margin-bottom:11px;">{project_info}</div>
    <div style="border-top:1px solid #f1f3f5; padding-top:11px;">
      <div style="font-weight:600; font-size:10px; color:#868e96;
                  text-transform:uppercase; letter-spacing:0.6px; margin-bottom:9px;">
        Standards Evaluation
      </div>
      {standards_html}
    </div>
    <a href="{_brief_filename(project.location_lat, project.location_lon, project.dwelling_units)}"
       target="_blank"
       style="display:block; text-align:center; margin-top:12px; padding:7px 10px;
              background:#f0f4f8; border:1px solid #ccd6e0; border-radius:6px;
              font-size:11px; font-weight:600; color:#1c4a6e; text-decoration:none;
              letter-spacing:0.2px;">
      View Determination Brief &rarr;
    </a>
  </div>
</div>

<script>
function toggleProjCard() {{
    var body = document.getElementById('proj-card-body');
    var btn  = document.getElementById('proj-toggle-btn');
    if (body.style.display === 'none') {{
        body.style.display = 'block'; btn.textContent = '▼';
    }} else {{
        body.style.display = 'none'; btn.textContent = '▶';
    }}
}}
</script>
"""


# ---------------------------------------------------------------------------
# Legend panel — eye toggles per standard
# ---------------------------------------------------------------------------

def _build_legend_html(config: dict, ad: dict, js_names: dict) -> str:
    vc_threshold = config.get("vc_threshold", 0.95)
    radius_miles = config.get("evacuation_route_radius_miles", 0.5)
    ld_radius    = config.get("local_density", {}).get("radius_miles", 0.25)

    map_js  = js_names["map"]
    fhsz_js = js_names["fhsz"]
    wld_js  = js_names["serving_wildland"]
    flg_js  = js_names["flagged"]
    ld_js   = js_names["serving_local5"]

    local5_applicable = ad["local5_applicable"]
    std1_icon = "✓" if ad["std1_triggered"] else "✗"
    std3_icon = "✓" if ad["wildland_serving_set"] else "✗"
    std4_icon = "✓" if ad["wildland_flagged_set"] else "✗"
    std5_icon = "✓" if ad["local5_flagged_set"] else ("—" if not local5_applicable else "✗")

    fhsz_items = "".join(
        f'<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:13px; height:13px; '
        f'background:{FHSZ_COLORS[k]}; opacity:0.65; border-radius:2px; '
        f'border:1px solid rgba(0,0,0,0.1);"></span>'
        f'<span style="color:#444;">{FHSZ_LABELS[k]}</span>'
        f'</div>'
        for k in sorted(FHSZ_COLORS)
    )

    def eye_btn(onclick_js: str) -> str:
        return (
            f'<button onclick="{onclick_js}" title="Toggle layer" style="'
            f'background:none; border:none; cursor:pointer; font-size:13px; '
            f'padding:0 2px; line-height:1; color:#555; vertical-align:middle; '
            f'flex-shrink:0;">👁</button>'
        )

    def dash_cell() -> str:
        return (
            '<span style="color:#adb5bd; font-size:12px; padding:0 4px; '
            'flex-shrink:0;">—</span>'
        )

    def route_row(color: str, label: str, onclick_js: str) -> str:
        return (
            f'<div style="display:flex; align-items:center; '
            f'justify-content:space-between; margin-bottom:5px;">'
            f'<div style="display:flex; align-items:center; gap:7px;">'
            f'<span style="display:inline-block; width:28px; height:5px; '
            f'background:{color}; border-radius:2px; flex-shrink:0;"></span>'
            f'<span style="color:#333; font-size:11px;">{label}</span>'
            f'</div>'
            f'{eye_btn(onclick_js)}'
            f'</div>'
        )

    def std_row_legend(icon: str, label: str, toggle_btn_html: str) -> str:
        icon_color = "#27ae60" if icon == "✓" else "#adb5bd"
        return (
            f'<div style="display:flex; align-items:center; '
            f'justify-content:space-between; margin-bottom:4px; gap:4px;">'
            f'<span style="color:{icon_color}; font-size:11px; '
            f'flex-shrink:0; width:14px;">{icon}</span>'
            f'<span style="color:#444; flex:1; font-size:11px;">{label}</span>'
            f'{toggle_btn_html}'
            f'</div>'
        )

    std5_toggle = (
        eye_btn(f"toggleLayer('{ld_js}')") if local5_applicable else dash_cell()
    )

    return f"""
<div id="map-legend" style="
    position: fixed; bottom: 26px; right: 10px; z-index: 9999;
    width: 215px; background: white; border: 1px solid #dee2e6;
    border-radius: 10px; padding: 13px 14px;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 11px; box-shadow: 0 4px 16px rgba(0,0,0,0.11); line-height: 1.4;
">
  <div style="font-weight:700; font-size:12px; color:#212529; margin-bottom:10px;
              border-bottom:1px solid #f1f3f5; padding-bottom:7px;">
    Evacuation Standards
  </div>

  {route_row(SERVING_ROUTE_COLOR, "Serving routes",
             f"toggleAllServing('{wld_js}', '{ld_js}')")}
  {route_row(FLAGGED_ROUTE_COLOR, "Flagged routes",
             f"toggleLayer('{flg_js}')")}

  <div style="border-top:1px solid #f1f3f5; margin:8px 0;"></div>

  {std_row_legend(std1_icon, "Std 1 · FHSZ zone",
                  eye_btn(f"toggleLayer('{fhsz_js}')"))}
  {std_row_legend("—", "Std 2 · Scale", dash_cell())}
  {std_row_legend(std3_icon, f"Std 3 · Wildland ({radius_miles} mi)",
                  eye_btn(f"toggleLayer('{wld_js}')"))}
  {std_row_legend(std4_icon, "Std 4 · V/C threshold",
                  eye_btn(f"toggleLayer('{flg_js}')"))}
  {std_row_legend(std5_icon, f"Std 5 · Local ({ld_radius} mi)", std5_toggle)}

  <div style="border-top:1px solid #f1f3f5; margin-top:10px; padding-top:10px;">
    <div style="font-weight:600; font-size:10px; color:#868e96;
                text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">
      Fire Hazard Zones
    </div>
    {fhsz_items}
  </div>

  <div style="margin-top:10px; border-top:1px solid #f1f3f5; padding-top:8px;
              font-size:9px; color:#adb5bd;">
    v/c threshold: {vc_threshold:.2f} &nbsp;|&nbsp; Fire Evac Analysis
  </div>
</div>

<script>
(function () {{
  var MAP_JS = '{map_js}';

  window.toggleLayer = function (jsName) {{
    var mapObj = window[MAP_JS];
    if (!mapObj) return;
    var layer = window[jsName];
    if (!layer) return;
    if (mapObj.hasLayer(layer)) {{
      mapObj.removeLayer(layer);
    }} else {{
      mapObj.addLayer(layer);
    }}
  }};

  // Toggle all serving layers together (Std 3 wildland + Std 5 local).
  // State follows the wildland group.
  window.toggleAllServing = function (wldJs, ld5Js) {{
    var mapObj = window[MAP_JS];
    if (!mapObj) return;
    var wld = window[wldJs];
    var ld5 = window[ld5Js];
    var isOn = wld && mapObj.hasLayer(wld);
    if (isOn) {{
      if (wld) mapObj.removeLayer(wld);
      if (ld5) mapObj.removeLayer(ld5);
    }} else {{
      if (wld) mapObj.addLayer(wld);
      if (ld5) mapObj.addLayer(ld5);
    }}
  }};
}})();
</script>
"""

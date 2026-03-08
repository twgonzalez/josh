"""
Demo map: multi-project comparison interactive Folium map.

Entry point: create_demo_map()

Standard 5 (local density) support:
  - Pass `audits` list from evaluate_project() to include Std 5 tier in
    per-project detail cards.
  - Standard 5 map layers are not shown separately; wildland routes are the
    primary display layer.
"""
import json
import logging
import math
from collections import defaultdict
from pathlib import Path

import folium
import geopandas as gpd
from shapely.geometry import Point, mapping

from models.project import Project

from .themes import (
    FHSZ_COLORS, FHSZ_LABELS,
    _TIER_MARKER_COLOR, _TIER_CSS_COLOR, _TIER_BG_COLOR,
    _TIER_ROUTE_COLOR, _TIER_ROUTE_COLOR_FLAGGED,
    _SERVING_ROUTE_NEUTRAL_COLOR, _SERVING_ROUTE_NEUTRAL_WEIGHT, _SERVING_ROUTE_NEUTRAL_OPACITY,
    _FLAGGED_ROUTE_WEIGHT, _FLAGGED_ROUTE_OPACITY,
    _TRAFFIC_BG_BUCKETS,
    _vc_background_color, _normal_traffic_vc, _vc_heatmap_color,
)
from .helpers import (
    _osmid_set, _osmid_matches, _to_int_safe,
    _highway_weight,
    _add_zoom_weight_scaler, _build_global_styles,
    _brief_filename,
)
from .popups import _build_route_impact_popup, _build_demo_project_popup, _build_heatmap_route_popup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evacuation capacity heatmap layer
# ---------------------------------------------------------------------------

def _build_capacity_heatmap_layer(
    roads_gdf: gpd.GeoDataFrame,
    config: dict,
) -> folium.FeatureGroup:
    """
    Build a FeatureGroup containing all evacuation route segments colored by v/c
    ratio using the _VC_RAMP scale. Add to the map BEFORE per-project layers so
    per-project flagged routes render on top.
    """
    fg = folium.FeatureGroup(name="Evacuation Capacity", show=True)

    if "is_evacuation_route" not in roads_gdf.columns or "vc_ratio" not in roads_gdf.columns:
        logger.warning("Heatmap: missing is_evacuation_route or vc_ratio column — skipping.")
        return fg

    evac_mask = roads_gdf["is_evacuation_route"].fillna(False).astype(bool)
    evac_routes = roads_gdf[evac_mask]

    for _, row in evac_routes.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue

        vc = float(row.get("vc_ratio", 0) or 0)
        color, opacity = _vc_heatmap_color(vc)

        name_raw = row.get("name", "Unnamed") or "Unnamed"
        if isinstance(name_raw, list):
            name_str = name_raw[0] if name_raw else "Unnamed"
        else:
            name_str = str(name_raw)
        if name_str in ("nan", "None", ""):
            name_str = "Unnamed"

        los         = str(row.get("los", "?") or "?")
        cap         = float(row.get("capacity_vph", 1) or 1)
        demand_base = float(row.get("baseline_demand_vph", 0) or 0)
        vc_threshold = config.get("vc_threshold", 0.95)

        tooltip_text = f"{name_str} | v/c {vc:.3f} | LOS {los}"
        popup_html   = _build_heatmap_route_popup(
            name_str, los, cap, demand_base, vc, vc_threshold,
        )

        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _, c=color, o=opacity: {
                "color": c, "weight": 3, "opacity": o,
            },
            tooltip=tooltip_text,
            popup=folium.Popup(popup_html, max_width=340),
        ).add_to(fg)

    logger.info(f"Heatmap: {evac_mask.sum()} evacuation route segments rendered.")
    return fg


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def create_demo_map(
    projects: list,
    roads_gdf: gpd.GeoDataFrame,
    fhsz_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    config: dict,
    output_path: Path,
    demo_title: str = "Fire Evacuation Impact Analysis",
    audits: list[dict] | None = None,
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
      6. Per-project local5 FeatureGroup (hidden; shown when Scenario B selected)

    Pass `audits` (list returned by evaluate_project()) to enable Standard 5.

    Returns the path to the saved HTML file.
    """
    if not projects:
        raise ValueError("No projects to display.")

    vc_threshold   = config.get("vc_threshold", 0.80)
    unit_threshold = config.get("unit_threshold", 15)
    radius_miles = config.get("evacuation_route_radius_miles", 0.5)
    radius_meters = radius_miles * 1609.344
    ld_radius = config.get("local_density", {}).get("radius_miles", 0.25)
    ld_radius_m = ld_radius * 1609.344

    all_lats = [p.location_lat for p in projects]
    all_lons = [p.location_lon for p in projects]
    center_lat = (min(all_lats) + max(all_lats)) / 2
    center_lon = (min(all_lons) + max(all_lons)) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )
    map_js_name = m.get_name()
    roads_wgs84 = roads_gdf.to_crs("EPSG:4326")

    # ── Layer 1: FHSZ Fire Zones ───────────────────────────────────────────
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

    # ── Layer 2: City-wide evacuation capacity background ──────────────────
    bg_buckets: dict = defaultdict(list)
    has_vc = "vc_ratio" in roads_wgs84.columns
    for _, row in roads_wgs84.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        if has_vc:
            vc = float(row.get("vc_ratio", 0) or 0)
        else:
            road_type = str(row.get("road_type") or "two_lane")
            vc = _normal_traffic_vc(road_type)
        color  = _vc_background_color(vc)
        weight = max(_highway_weight(row.get("highway")) * 0.25, 0.5)
        bg_buckets[(color, weight)].append(mapping(row.geometry))

    for (color, weight), geoms in bg_buckets.items():
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
                "color": c, "weight": w, "opacity": 0.20,
            },
            smooth_factor=2,
        ).add_to(m)

    # ── Layer 3: City Boundary ─────────────────────────────────────────────
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

    # ── Layer 4: Evacuation Capacity Heatmap ──────────────────────────────
    heatmap_fg = _build_capacity_heatmap_layer(roads_wgs84, config)
    heatmap_fg.add_to(m)
    heatmap_js_name = heatmap_fg.get_name()

    # ── Per-project FeatureGroups ──────────────────────────────────────────
    proj_js_names: list[str] = []

    # Per-project Standard 5 data (populated from audits if available)
    proj_ld_data: list[dict] = []

    for i, project in enumerate(projects):
        tier         = project.determination or "UNKNOWN"
        marker_color = _TIER_MARKER_COLOR.get(tier, "gray")
        route_color  = _TIER_ROUTE_COLOR.get(tier, "#7f7f7f")
        route_flagged_color = _TIER_ROUTE_COLOR_FLAGGED.get(tier, "#555")
        serving_set  = _osmid_set(project.serving_route_ids)
        flagged_set  = _osmid_set(project.flagged_route_ids)

        # Worst-case marginal impact: full project load tested on each route independently.
        # Matches the ratio_test() methodology in agents/scenarios/base.py.
        # DO NOT divide by num_serving — that would contradict the determination engine.
        project_vph_per_rt = project.project_vehicles_peak_hour

        # ── Extract Standard 5 data from audit ──────────────────────────
        if audits and i < len(audits):
            ld = audits[i].get("scenarios", {}).get("local_density_sb79", {})
        else:
            ld = {}
        ld_tier      = ld.get("tier", "NOT_APPLICABLE")
        ld_step3     = ld.get("steps", {}).get("step3_routes", {})
        ld_step5     = ld.get("steps", {}).get("step5_ratio_test", {})
        ld_serving_set = _osmid_set([r["osmid"] for r in ld_step3.get("serving_routes", [])])
        ld_flagged_set = _osmid_set(ld_step5.get("flagged_route_ids", []))
        ld_n_serving   = ld_step3.get("serving_route_count", len(ld_serving_set))
        ld_n_flagged   = len(ld_flagged_set)
        ld_triggered   = ld.get("triggered", False)
        proj_ld_data.append({
            "tier": ld_tier,
            "triggered": ld_triggered,
            "n_serving": ld_n_serving,
            "n_flagged": ld_n_flagged,
        })

        # ── Worst-case route for popup inline display ─────────────────────
        # Wildland (Std 4): find the flagged route with highest proposed v/c
        worst_wildland_route: "dict | None" = None
        if flagged_set and "osmid" in roads_wgs84.columns:
            is_flagged_mask = roads_wgs84["osmid"].apply(
                lambda o: _osmid_matches(o, flagged_set)
            )
            flagged_roads = roads_wgs84[is_flagged_mask]
            if not flagged_roads.empty:
                cap_s = flagged_roads["capacity_vph"].fillna(1).clip(lower=0.001)
                dem_s = flagged_roads["baseline_demand_vph"].fillna(0)
                pvc_s = (dem_s + project_vph_per_rt) / cap_s
                best_idx = pvc_s.idxmax()
                row_w = flagged_roads.loc[best_idx]
                cap_w = float(row_w.get("capacity_vph", 1) or 1)
                dem_w = float(row_w.get("baseline_demand_vph", 0) or 0)
                worst_wildland_route = {
                    "name": str(row_w.get("name", "Unnamed") or "Unnamed"),
                    "baseline_vc": dem_w / max(cap_w, 0.001),
                    "proposed_vc": (dem_w + project_vph_per_rt) / max(cap_w, 0.001),
                }

        # Local density (Std 5): pull worst route from audit route_details
        worst_local_route: "dict | None" = None
        ld_route_details = ld_step5.get("route_details", [])
        caused = [r for r in ld_route_details if r.get("project_causes_exceedance")]
        if caused:
            worst_ld = max(caused, key=lambda r: r.get("proposed_vc", 0))
            worst_local_route = {
                "name": str(worst_ld.get("name") or worst_ld.get("osmid", "Unnamed")),
                "baseline_vc": float(worst_ld.get("baseline_vc", 0)),
                "proposed_vc": float(worst_ld.get("proposed_vc", 0)),
            }

        # Store worst routes in proj_ld_data for sidebar detail card
        proj_ld_data[-1]["worst_wildland"] = worst_wildland_route
        proj_ld_data[-1]["worst_local"]    = worst_local_route

        # ── Wildland project FeatureGroup ────────────────────────────────
        proj_group = folium.FeatureGroup(
            name=f"{project.project_name or f'Project {i+1}'} — {tier}",
            show=(i == 0),
        )
        proj_js_names.append(proj_group.get_name())

        # Search radius (dashed circle, tier color)
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

        # Impact zone: KLD evacuation demand within search radius
        if "vc_ratio" in roads_wgs84.columns:
            lat_rad    = math.radians(project.location_lat)
            radius_deg = radius_meters / (111139.0 * math.cos(lat_rad))
            proj_buf   = Point(
                project.location_lon, project.location_lat
            ).buffer(radius_deg)
            impact_mask      = roads_wgs84.geometry.intersects(proj_buf)
            impact_roads_gdf = roads_wgs84[impact_mask]

            iz_buckets: dict = defaultdict(list)
            for _, row in impact_roads_gdf.iterrows():
                if row.geometry is None or row.geometry.is_empty:
                    continue
                vc        = float(row.get("vc_ratio", 0) or 0)
                iz_color  = _vc_background_color(vc)
                iz_weight = max(_highway_weight(row.get("highway")) * 0.30, 0.6)
                iz_buckets[(iz_color, iz_weight)].append(mapping(row.geometry))

            for (iz_color, iz_weight), geoms in iz_buckets.items():
                fc = {
                    "type": "FeatureCollection",
                    "features": [
                        {"type": "Feature", "geometry": g, "properties": {}}
                        for g in geoms
                    ],
                }
                folium.GeoJson(
                    fc,
                    style_function=lambda _, c=iz_color, w=iz_weight: {
                        "color": c, "weight": w, "opacity": 0.55,
                    },
                ).add_to(proj_group)

        # Serving routes (wildland — one GeoJson per segment for popup support)
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
                seg_color   = route_flagged_color if is_flagged else _SERVING_ROUTE_NEUTRAL_COLOR
                weight      = _FLAGGED_ROUTE_WEIGHT if is_flagged else _SERVING_ROUTE_NEUTRAL_WEIGHT
                opacity     = _FLAGGED_ROUTE_OPACITY if is_flagged else _SERVING_ROUTE_NEUTRAL_OPACITY

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
                if is_flagged:
                    tip = (
                        f"⚠ causes exceedance — {name_str} "
                        f"| {vc_base:.3f} → {vc_proposed:.3f} v/c"
                    )
                else:
                    tip = f"serving route — {name_str} | baseline v/c {vc_base:.3f}"
                folium.GeoJson(
                    mapping(row.geometry),
                    style_function=lambda _, c=seg_color, w=weight, o=opacity: {
                        "color": c, "weight": w, "opacity": o,
                    },
                    popup=folium.Popup(popup_html, max_width=360),
                    tooltip=tip,
                ).add_to(proj_group)

        # Project marker (wildland group — visible in Scenario A)
        folium.Marker(
            location=[project.location_lat, project.location_lon],
            popup=folium.Popup(
                _build_demo_project_popup(
                    project, route_color, vc_threshold, unit_threshold,
                    worst_wildland_route=worst_wildland_route,
                    worst_local_route=worst_local_route,
                    ld_tier=ld_tier,
                    ld_triggered=ld_triggered,
                ),
                max_width=320,
            ),
            tooltip=f"{project.project_name} · {tier}",
            icon=folium.Icon(color=marker_color, icon="home", prefix="fa"),
        ).add_to(proj_group)

        proj_group.add_to(m)

    # ── Fixed panels ───────────────────────────────────────────────────────
    m.get_root().html.add_child(folium.Element(_build_brand_header_html()))
    m.get_root().html.add_child(folium.Element(
        _build_demo_panel_html(
            projects, demo_title, config,
            proj_js_names=proj_js_names,
            map_js_name=map_js_name,
            proj_ld_data=proj_ld_data,
        )
    ))
    m.get_root().html.add_child(folium.Element(
        _build_demo_legend_html(config, map_js_name=map_js_name, heatmap_js_name=heatmap_js_name)
    ))
    m.get_root().html.add_child(folium.Element(_build_global_styles()))
    _add_zoom_weight_scaler(m, ref_zoom=13)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    logger.info(f"Demo map saved: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Brand header (top bar)
# ---------------------------------------------------------------------------

def _build_brand_header_html() -> str:
    """Full-width fixed header with JOSH product branding and CSA org identity."""
    return """
<div id="josh-header" style="
    position: fixed;
    top: 0; left: 0; right: 0;
    z-index: 10001;
    height: 54px;
    background: #1c4a6e;
    border-bottom: 3px solid #154e80;
    display: flex;
    align-items: center;
    padding: 0 18px;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    box-shadow: 0 3px 18px rgba(0,0,0,0.50);
    gap: 0;
    user-select: none;
">

  <!-- CSA seal mark (pine tree + water waves) -->
  <div style="
      width: 38px; height: 38px;
      border-radius: 50%;
      border: 1.5px solid rgba(196,168,130,0.50);
      background: rgba(196,168,130,0.07);
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
  ">
    <svg width="24" height="24" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polygon points="14,4 22,17 6,17" fill="#c4a882" opacity="0.88"/>
      <rect x="12.5" y="17" width="3" height="4.5" fill="#c4a882" opacity="0.88"/>
      <path d="M4 23 Q7.5 21 11 23 Q14.5 25 18 23 Q21.5 21 25 23"
            stroke="#c4a882" stroke-width="1.3" fill="none" opacity="0.60"
            stroke-linecap="round"/>
    </svg>
  </div>

  <!-- CSA org name -->
  <div style="margin-left: 11px; flex-shrink: 0; line-height: 1.3;">
    <div style="font-size: 8px; color: #c4a882; letter-spacing: 2px;
                text-transform: uppercase; font-weight: 700;">CALIFORNIA</div>
    <div style="font-size: 8px; color: #c4a882; letter-spacing: 2px;
                text-transform: uppercase; font-weight: 700;">STEWARDSHIP ALLIANCE</div>
  </div>

  <!-- Vertical divider -->
  <div style="
      width: 1px; height: 32px;
      background: rgba(255,255,255,0.13);
      margin: 0 20px;
      flex-shrink: 0;
  "></div>

  <!-- JOSH product identity -->
  <div style="display: flex; align-items: center; gap: 15px; flex-shrink: 0;">

    <!-- Logotype -->
    <div style="
        font-size: 27px; font-weight: 900; color: #ffffff;
        letter-spacing: 1px; line-height: 1;
        text-shadow: 0 1px 6px rgba(0,0,0,0.4);
    ">JOSH</div>

    <!-- Inner divider -->
    <div style="width:1px; height:26px; background:rgba(255,255,255,0.13); flex-shrink:0;"></div>

    <!-- Full name + sub-label -->
    <div style="line-height: 1.35;">
      <div style="font-size: 11.5px; font-weight: 600; color: #e8ddd0;
                  letter-spacing: 0.15px;">
        Jurisdictional Objective Standards for Housing
      </div>
      <div style="font-size: 9px; color: #93b8d5; letter-spacing: 0.4px; margin-top: 2px;">
        Fire Evacuation Capacity Analysis &nbsp;&middot;&nbsp; AB 747
      </div>
    </div>
  </div>

  <!-- Spacer -->
  <div style="flex: 1;"></div>

  <!-- Right: version badge -->
  <div style="
      font-size: 9px; color: #7aadc9;
      letter-spacing: 1px; text-transform: uppercase;
      font-weight: 600; text-align: right; flex-shrink: 0;
  ">BETA</div>

</div>
"""


# ---------------------------------------------------------------------------
# Demo panel (left sidebar)
# ---------------------------------------------------------------------------

def _build_demo_panel_html(
    projects: list,
    demo_title: str,
    config: dict,
    proj_js_names: list,
    map_js_name: str,
    proj_ld_data: list[dict] | None = None,
) -> str:
    """Fixed top-left panel for the demo map — project selector + detail cards."""
    vc_threshold  = config.get("vc_threshold", 0.95)
    unit_threshold = config.get("unit_threshold", 50)
    proj_js_array = json.dumps(proj_js_names)

    tier_abbr_map = {
        "DISCRETIONARY":           "DISC",
        "CONDITIONAL MINISTERIAL": "COND",
        "MINISTERIAL":             "MIN",
    }

    # ── Dropdown options ──────────────────────────────────────────────────
    options_html = ""
    for i, p in enumerate(projects):
        tier  = p.determination or "UNKNOWN"
        abbr  = tier_abbr_map.get(tier, tier[:4])
        label = f"{p.project_name or f'Project {i+1}'}  ·  {abbr}  ({p.dwelling_units} units)"
        options_html += f'<option value="{i}">{label}</option>\n'

    # ── Per-project detail cards ──────────────────────────────────────────
    detail_cards_html = ""
    for i, p in enumerate(projects):
        ld = (proj_ld_data[i] if proj_ld_data and i < len(proj_ld_data) else {})
        detail_cards_html += _build_project_detail_div(
            i, p, config, vc_threshold, unit_threshold,
            ld_tier=ld.get("tier", "NOT_APPLICABLE"),
            ld_triggered=ld.get("triggered", False),
            ld_n_serving=ld.get("n_serving", 0),
            ld_n_flagged=ld.get("n_flagged", 0),
            worst_wildland_route=ld.get("worst_wildland"),
            worst_local_route=ld.get("worst_local"),
        )

    return f"""
<div id="demo-panel" style="
    position: fixed;
    top: 68px; left: 10px;
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

  <!-- ── Header ──────────────────────────────────────────────────────── -->
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
        Project Evaluation
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

  <!-- ── Body ────────────────────────────────────────────────────────── -->
  <div id="demo-panel-body" style="overflow:hidden;">

    <!-- Project dropdown selector -->
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

  window.selectProject = function (idx) {{
    var mapObj = window[MAP_NAME];
    if (!mapObj) return;

    PROJECT_LAYERS.forEach(function (varName, i) {{
      var layer = window[varName];
      if (!layer) return;
      if (i === idx) {{
        if (!mapObj.hasLayer(layer)) mapObj.addLayer(layer);
      }} else {{
        if (mapObj.hasLayer(layer)) mapObj.removeLayer(layer);
      }}
    }});

    document.querySelectorAll('.proj-detail-card').forEach(function (el, i) {{
      el.style.display = (i === idx) ? 'block' : 'none';
    }});

    var dd = document.getElementById('proj-dropdown');
    if (dd && dd.selectedIndex !== idx) dd.selectedIndex = idx;
  }};

  // ── Collapse / expand ────────────────────────────────────────────────
  window.toggleDemoPanel = function () {{
    var body = document.getElementById('demo-panel-body');
    var btn  = document.getElementById('demo-toggle-btn');
    body.style.display = (body.style.display === 'none') ? 'block' : 'none';
    btn.textContent    = (body.style.display === 'none') ? '▶' : '▼';
  }};

  // ── Init: show only project 0 (poll until Leaflet map is ready) ──────
  (function initSelect() {{
    var mapObj = window[MAP_NAME];
    if (!mapObj) {{ setTimeout(initSelect, 50); return; }}
    window.selectProject(0);
  }})();

}})();
</script>
"""


# ---------------------------------------------------------------------------
# Per-project detail card
# ---------------------------------------------------------------------------

def _build_project_detail_div(
    idx: int,
    project,
    config: dict,
    vc_threshold: float,
    unit_threshold: int,
    ld_tier: str = "NOT_APPLICABLE",
    ld_triggered: bool = False,
    ld_n_serving: int = 0,
    ld_n_flagged: int = 0,
    worst_wildland_route: "dict | None" = None,
    worst_local_route: "dict | None" = None,
) -> str:
    """Pre-rendered hidden card for one project. JS toggles display:block/none."""
    tier         = project.determination or "UNKNOWN"
    det_color    = _TIER_CSS_COLOR.get(tier, "#555")
    bg_color     = _TIER_BG_COLOR.get(tier, "#fafafa")
    border_color = {"DISCRETIONARY": "#e8b4b0", "CONDITIONAL MINISTERIAL": "#f5d49a", "MINISTERIAL": "#a8d5b8"}.get(tier, "#dee2e6")
    route_color  = _TIER_ROUTE_COLOR.get(tier, "#7f7f7f")

    in_fz    = project.in_fire_zone
    fz_str   = f"Zone {project.fire_zone_level}" if in_fz else "Not in FHSZ"
    fz_color = "#c0392b" if in_fz else "#27ae60"

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

  <!-- Brief link -->
  <div style="padding:10px 13px 13px;">
    <a href="{_brief_filename(project.location_lat, project.location_lon, project.dwelling_units)}"
       target="_blank"
       style="display:block; text-align:center; padding:8px 10px;
              background:#f0f4f8; border:1px solid #ccd6e0; border-radius:6px;
              font-size:11px; font-weight:600; color:#1c4a6e; text-decoration:none;
              letter-spacing:0.2px;">
      View Determination Brief &rarr;
    </a>
  </div>

</div>
"""


# ---------------------------------------------------------------------------
# Demo legend (bottom-right)
# ---------------------------------------------------------------------------

def _build_demo_legend_html(
    config: dict,
    map_js_name: str = "",
    heatmap_js_name: str = "",
) -> str:
    vc_threshold = config.get("vc_threshold", 0.80)

    route_tier_items = (
        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:28px; height:5px; '
        f'background:{_TIER_ROUTE_COLOR["DISCRETIONARY"]}; border-radius:2px; flex-shrink:0;"></span>'
        '<span style="color:#444;">Discretionary (DISC)</span></div>'

        '<div style="display:flex; align-items:center; gap:7px; margin-bottom:4px;">'
        f'<span style="display:inline-block; width:28px; height:5px; '
        f'background:{_TIER_ROUTE_COLOR["CONDITIONAL MINISTERIAL"]}; border-radius:2px; flex-shrink:0;"></span>'
        '<span style="color:#444;">Cond. Ministerial (COND)</span></div>'

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
              letter-spacing:0.5px; margin-bottom:6px;">Evacuation Capacity (v/c)</div>
  {traffic_items}
  <div style="font-size:10px; color:#adb5bd; margin-top:2px; margin-bottom:10px;">
    KLD AB 747 max demand · impact zone bolder
  </div>

  <div style="font-weight:600; font-size:10px; color:#868e96; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:6px;">Fire Hazard Zones</div>
  {fhsz_items}

  <!-- Base Layer toggle -->
  <div style="margin-top:12px; border-top:1px solid #dee2e6; padding-top:10px;">
    <div style="font-size:11px; font-weight:600; color:#495057; margin-bottom:6px;
                text-transform:uppercase; letter-spacing:0.05em;">
      Base Layer
    </div>
    <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:12px;">
      <input type="checkbox" id="heatmapToggle" checked
             onchange="toggleHeatmap(this.checked)">
      Evacuation Capacity
    </label>
    <div style="margin-top:6px; height:8px; border-radius:4px;
                background: linear-gradient(to right, #adb5bd, #ffc107, #fd7e14, #dc3545);
                opacity:0.85;">
    </div>
    <div style="display:flex; justify-content:space-between; font-size:10px;
                color:#868e96; margin-top:2px;">
      <span>LOS A–D</span><span>LOS E</span><span>LOS F</span>
    </div>
  </div>

  <div style="margin-top:10px; border-top:1px solid #f1f3f5; padding-top:8px;
              font-size:9px; color:#adb5bd;">JOSH &middot; California Stewardship Alliance</div>
</div>

<script>
(function () {{
  var MAP_NAME      = '{map_js_name}';
  var HEATMAP_NAME  = '{heatmap_js_name}';

  window.toggleHeatmap = function (visible) {{
    var mapObj = window[MAP_NAME];
    var layer  = window[HEATMAP_NAME];
    if (!mapObj || !layer) return;
    if (visible) {{
      if (!mapObj.hasLayer(layer)) mapObj.addLayer(layer);
    }} else {{
      if (mapObj.hasLayer(layer)) mapObj.removeLayer(layer);
    }}
  }};
}})();
</script>
"""

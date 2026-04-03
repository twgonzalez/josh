# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

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
import requests
from folium.plugins import AntPath
from shapely.geometry import Point, mapping
from shapely.ops import unary_union

from models.project import Project

from .themes import (
    FHSZ_COLORS, FHSZ_LABELS,
    _TIER_MARKER_COLOR, _TIER_CSS_COLOR, _TIER_BG_COLOR,
    _TIER_ROUTE_COLOR, _TIER_ROUTE_COLOR_FLAGGED,
    _SERVING_ROUTE_NEUTRAL_COLOR, _SERVING_ROUTE_NEUTRAL_WEIGHT, _SERVING_ROUTE_NEUTRAL_OPACITY,
    _FLAGGED_ROUTE_WEIGHT, _FLAGGED_ROUTE_OPACITY,
    _TRAFFIC_BG_BUCKETS, _EFFECTIVE_CAPACITY_RAMP,
    _vc_background_color, _normal_traffic_vc,
    _effective_capacity_heatmap_color,
)
from .helpers import (
    _osmid_set, _osmid_matches, _to_int_safe,
    _highway_weight,
    _add_zoom_weight_scaler, _build_global_styles,
    _brief_filename,
)
from .popups import _build_route_delta_t_popup, _build_demo_project_popup, _build_heatmap_route_popup

logger = logging.getLogger(__name__)

_TIER_ACTION_LABELS = {
    "DISCRETIONARY":           "Planning Commission review required — public hearing",
    "MINISTERIAL WITH STANDARD CONDITIONS": "Staff approval — standard conditions apply automatically; no public hearing",
    "MINISTERIAL":             "Over-the-counter permit — no discretionary review",
}


# ---------------------------------------------------------------------------
# Evacuation capacity heatmap layer
# ---------------------------------------------------------------------------

def _build_capacity_heatmap_layer(
    roads_gdf: gpd.GeoDataFrame,
    config: dict,
) -> tuple[folium.FeatureGroup, list[str]]:
    """
    Build a FeatureGroup containing all evacuation route segments colored by
    effective_capacity_vph using the _EFFECTIVE_CAPACITY_RAMP scale.

    v3.0 ΔT Standard: low effective capacity (bottleneck danger) = red/prominent;
    high effective capacity (ample headroom) = gray/subdued.

    Returns (FeatureGroup, list_of_geojson_var_names).  The caller must inject
    popup-binding JS for the returned var names (see _inject_popup_binders).

    Performance: segments are grouped into ≤4 FeatureCollection GeoJson layers
    (one per capacity tier) instead of one L.geoJson() per segment.  This
    reduces the HTML from ~7 MB to ~0.5 MB for the heatmap layer alone.
    Per-segment popups are preserved via a post-creation JS bindPopup pass.
    """
    fg = folium.FeatureGroup(name="Evacuation Capacity", show=True)

    if "is_evacuation_route" not in roads_gdf.columns:
        logger.warning("Heatmap: missing is_evacuation_route column — skipping.")
        return fg, []

    has_eff_cap = "effective_capacity_vph" in roads_gdf.columns
    if not has_eff_cap:
        logger.warning(
            "Heatmap: effective_capacity_vph column not found — "
            "falling back to capacity_vph. Run 'analyze --refresh' to populate."
        )

    _zone_labels = {
        "vhfhsz":        "Very High FHSZ",
        "high_fhsz":     "High FHSZ",
        "moderate_fhsz": "Moderate FHSZ",
        "non_fhsz":      "Non-FHSZ",
    }

    evac_mask   = roads_gdf["is_evacuation_route"].fillna(False).astype(bool)
    evac_routes = roads_gdf[evac_mask]

    # ── Bucket segments by (color, opacity) — max 4 tiers from _EFFECTIVE_CAPACITY_RAMP
    # Each bucket becomes ONE L.geoJson() call with a FeatureCollection.
    # Per-segment tooltip + popup_html stored as feature properties.
    buckets: dict = defaultdict(list)

    for _, row in evac_routes.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue

        hcm_cap = float(row.get("capacity_vph", 1) or 1)
        eff_cap = float(row.get("effective_capacity_vph", hcm_cap) or hcm_cap) \
                  if has_eff_cap else hcm_cap

        color, opacity = _effective_capacity_heatmap_color(eff_cap)

        name_raw = row.get("name", "Unnamed") or "Unnamed"
        name_str = (name_raw[0] if isinstance(name_raw, list) and name_raw
                    else str(name_raw))
        if name_str in ("nan", "None", ""):
            name_str = "Unnamed"

        fhsz_zone  = str(row.get("fhsz_zone", "non_fhsz") or "non_fhsz")
        hazard_deg = float(row.get("hazard_degradation", 1.0) or 1.0)
        vc_base    = float(row.get("vc_ratio", 0) or 0)
        los        = str(row.get("los", "?") or "?")
        zone_label = _zone_labels.get(fhsz_zone, fhsz_zone)
        road_type  = str(row.get("road_type", "") or "")
        lane_count = int(row.get("lane_count", 0) or 0)
        speed_limit = int(row.get("speed_limit", 0) or 0)

        tooltip_text = f"{name_str} | {eff_cap:.0f} vph eff cap | {zone_label}"
        popup_html   = _build_heatmap_route_popup(
            name_str, eff_cap, hcm_cap, fhsz_zone, hazard_deg, vc_base, los,
            road_type=road_type, lane_count=lane_count, speed_limit=speed_limit,
        )

        buckets[(color, opacity)].append({
            "type": "Feature",
            "geometry": mapping(row.geometry),
            "properties": {
                "tooltip": tooltip_text,
                "popup_html": popup_html,
            },
        })

    gj_names: list[str] = []
    for (color, opacity), features in sorted(buckets.items()):
        fc = {"type": "FeatureCollection", "features": features}
        gj = folium.GeoJson(
            fc,
            style_function=lambda _, c=color, o=opacity: {
                "color": c, "weight": 3, "opacity": o,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["tooltip"],
                labels=False,
                style=(
                    "font-family: system-ui, sans-serif; font-size: 11px; "
                    "padding: 3px 8px; white-space: nowrap;"
                ),
            ),
            smooth_factor=1.5,
        )
        gj.add_to(fg)
        gj_names.append(gj.get_name())

    logger.info(f"Heatmap: {evac_mask.sum()} evacuation route segments rendered.")
    return fg, gj_names


# ---------------------------------------------------------------------------
# Post-creation popup binding
# ---------------------------------------------------------------------------

def _inject_popup_binders(
    m: folium.Map,
    gj_names: list[str],
    max_width: int = 340,
) -> None:
    """
    Inject a <script> block that binds per-feature popup HTML stored in the
    'popup_html' GeoJSON property.  Must be called AFTER all layers are added
    to the map so the generated script tag runs after Folium's _add(data) calls.

    Each name in gj_names is the Leaflet JS variable name returned by
    folium.GeoJson(...).get_name().  That variable is a global because Folium
    emits plain (non-strict, non-IIFE) <script> blocks.
    """
    if not gj_names:
        return
    lines = []
    for name in gj_names:
        lines.append(f"""
(function () {{
  var gj = window['{name}'];
  if (!gj || !gj.eachLayer) {{ return; }}
  gj.eachLayer(function (lyr) {{
    var props = lyr.feature && lyr.feature.properties;
    if (props && props.popup_html) {{
      lyr.bindPopup(props.popup_html, {{ maxWidth: {max_width} }});
    }}
  }});
}})();""")
    m.get_root().html.add_child(folium.Element(
        "<script>" + "\n".join(lines) + "\n</script>"
    ))


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
    evacuation_paths: list | None = None,
    graph_json_path: Path | None = None,
    params_json_path: Path | None = None,
    city_config: dict | None = None,
    data_dir: Path | None = None,
) -> Path:
    """
    Generate a multi-project comparison map — v3.0 ΔT Standard.

    Visual hierarchy (bottom → top):
      1. CartoDB Positron base
      2. FHSZ fire zones (light fill)
      3. Traffic background — all roads, thin, pastel-colored by v/c (informational)
      4. City boundary (dashed)
      5. Evacuation Capacity heatmap — all evac routes colored by effective_capacity_vph
      6. Per-project FeatureGroup (serving routes + marker + search radius)
         — only ONE visible at a time, controlled by panel dropdown
         — includes controlling evacuation path corridor (dashed) from buffer to bottleneck

    Pass `audits` (list returned by evaluate_project()) to include SB 79 transit
    flag in per-project detail cards.

    Returns the path to the saved HTML file.
    """
    if not projects:
        raise ValueError("No projects to display.")

    vc_threshold   = config.get("vc_threshold", 0.95)   # informational only
    unit_threshold = config.get("unit_threshold", 15)
    radius_miles   = config.get("evacuation_route_radius_miles", 0.5)
    radius_meters  = radius_miles * 1609.344

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
                "color": "#1a6eb5",
                "weight": 2, "dashArray": "8 5",
                "fill": False,
                "interactive": False,
            },
        ).add_to(m)

    # ── Layer 4: Evacuation Capacity Heatmap ──────────────────────────────
    heatmap_fg, _heatmap_gj_names = _build_capacity_heatmap_layer(roads_wgs84, config)
    heatmap_fg.add_to(m)
    heatmap_js_name = heatmap_fg.get_name()

    # ── Per-project FeatureGroups ──────────────────────────────────────────
    proj_js_names: list[str] = []
    # Accumulate GeoJson var names that need post-creation popup binding.
    # _inject_popup_binders() is called once at the end (after all layers added).
    _all_popup_gj_names: list[str] = list(_heatmap_gj_names)

    # Per-project Standard 5 data (populated from audits if available)
    proj_ld_data: list[dict] = []

    # Population-level path lookup (used as fallback for path_id_to_osmids below)
    _population_path_osmids: dict[str, list[str]] = {
        str(getattr(_ep, "path_id", "")): list(getattr(_ep, "path_osmids", []))
        for _ep in (evacuation_paths or [])
        if getattr(_ep, "path_osmids", [])
    }

    for i, project in enumerate(projects):
        # v3.4: Build path_id → path_osmids from this project's ΔT results.
        # Project-origin Dijkstra paths carry their own path_osmids in delta_t_results,
        # so the flow-trace visualization works without the population paths list.
        # Falls back to population paths lookup for any path_ids not found here.
        path_id_to_osmids: dict[str, list[str]] = {
            r["path_id"]: r.get("path_osmids", [])
            for r in (project.delta_t_results or [])
            if r.get("path_osmids")
        }
        # Merge in population paths for any missing path_ids (backward compat)
        for pid, osmids in _population_path_osmids.items():
            if pid not in path_id_to_osmids:
                path_id_to_osmids[pid] = osmids

        tier         = project.determination or "UNKNOWN"
        marker_color = _TIER_MARKER_COLOR.get(tier, "gray")
        route_color  = _TIER_ROUTE_COLOR.get(tier, "#7f7f7f")
        route_flagged_color = _TIER_ROUTE_COLOR_FLAGGED.get(tier, "#555")
        serving_set  = _osmid_set(project.serving_route_ids)
        # v3.0: derive flagged segments from ΔT results (bottleneck osmids of flagged paths)
        _flagged_osmids = [
            str(r.get("bottleneck_osmid", ""))
            for r in (project.delta_t_results or [])
            if r.get("flagged")
        ]
        flagged_set  = _osmid_set(_flagged_osmids)

        # ── Extract Standard 5 audit (informational — SB 79 transit flag) ──────
        if audits and i < len(audits):
            ld = audits[i].get("scenarios", {}).get("sb79_transit", {})
        else:
            ld = {}
        ld_tier      = ld.get("tier", "NOT_APPLICABLE")
        ld_triggered = ld.get("triggered", False)
        proj_ld_data.append({
            "tier":      ld_tier,
            "triggered": ld_triggered,
            "n_serving": 0,
            "n_flagged": 0,
        })

        # ── Worst-case ΔT path for popup inline display (v3.0) ───────────────
        # Use project.delta_t_results (set by Agent 3 WildlandScenario).
        # Show the flagged path with highest ΔT, or the highest ΔT path overall.
        worst_wildland_route: "dict | None" = None
        ctrl_osmid: str = ""    # controlling bottleneck osmid for ⚠ icon lookup
        ctrl_path_id: str = ""  # controlling path_id for corridor lookup
        if project.delta_t_results:
            flagged_dts = [r for r in project.delta_t_results if r.get("flagged")]
            best_dt     = (
                max(flagged_dts, key=lambda r: r.get("delta_t_minutes", 0))
                if flagged_dts else
                max(project.delta_t_results, key=lambda r: r.get("delta_t_minutes", 0))
            )
            ctrl_osmid    = str(best_dt.get("bottleneck_osmid", ""))
            ctrl_path_id  = str(best_dt.get("path_id", ""))
            worst_wildland_route = {
                "name":              str(best_dt.get("bottleneck_name", "") or "Bottleneck segment"),
                "delta_t_minutes":   best_dt.get("delta_t_minutes",  0.0),
                "threshold_minutes": best_dt.get("threshold_minutes", 10.0),
                "flagged":           best_dt.get("flagged", False),
            }

        # Store worst path in proj_ld_data for sidebar (unused by current sidebar card
        # implementation, but preserved for future use).
        proj_ld_data[-1]["worst_wildland"] = worst_wildland_route
        proj_ld_data[-1]["worst_local"]    = None   # SB 79 has no route details

        # ── Build bottleneck osmid → ΔT result map for serving route popups ──
        # Key: str(bottleneck_osmid). Value: worst ΔT result for that segment.
        bottleneck_dt_map: dict[str, dict] = {}
        for r in (project.delta_t_results or []):
            bn = str(r.get("bottleneck_osmid", ""))
            if bn and (bn not in bottleneck_dt_map or
                       r.get("delta_t_minutes", 0) > bottleneck_dt_map[bn].get("delta_t_minutes", 0)):
                bottleneck_dt_map[bn] = r

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

        # Impact zone: all roads within search radius, muted background highlight
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

        # ── Network reachability zone (v3.3) ─────────────────────────────────
        # Roads reachable from the project's egress via actual road network.
        # I-5 and other barriers appear as natural gaps — no trans-barrier segments.
        # Replaces the Euclidean dashed circle as the proximity indicator.
        reachable_set = _osmid_set(getattr(project, "reachable_network_osmids", []))
        if reachable_set and "osmid" in roads_wgs84.columns:
            reach_mask  = roads_wgs84["osmid"].apply(lambda o: _osmid_matches(o, reachable_set))
            reach_roads = roads_wgs84[reach_mask]
            reach_geoms = [
                mapping(row.geometry) for _, row in reach_roads.iterrows()
                if row.geometry is not None and not row.geometry.is_empty
            ]
            if reach_geoms:
                folium.GeoJson(
                    {"type": "FeatureCollection",
                     "features": [{"type": "Feature", "geometry": g, "properties": {}}
                                  for g in reach_geoms]},
                    style_function=lambda _, c=route_color: {
                        "color": c, "weight": 3, "opacity": 0.22,
                    },
                    tooltip=f"{project.project_name} — network reachable zone",
                ).add_to(proj_group)

        # ── Evacuation flow traces — all serving paths (v3.3) ────────────────
        # Full route for every serving EvacuationPath, colored by ΔT severity.
        # Green = within threshold, orange = >70% of threshold, red = exceeded.
        # Renders below serving-route highlights so the bottleneck stands out.
        _FLOW_GREEN  = "#2e7d32"
        _FLOW_ORANGE = "#e65100"
        _FLOW_RED    = "#b71c1c"

        exit_osmids_drawn: set[str] = set()  # avoid duplicate exit markers

        for dt_result in (project.delta_t_results or []):
            pid      = str(dt_result.get("path_id", ""))
            dt_min   = float(dt_result.get("delta_t_minutes", 0))
            thresh   = float(dt_result.get("threshold_minutes", 6.0)) or 6.0
            flagged  = dt_result.get("flagged", False)
            bn_name  = str(dt_result.get("bottleneck_name", "") or "bottleneck")
            exit_oid = str(dt_result.get("exit_segment_osmid", ""))

            severity = dt_min / thresh
            if flagged or severity >= 1.0:
                flow_color, flow_w, flow_op = _FLOW_RED,    3.5, 0.75
            elif severity >= 0.70:
                flow_color, flow_w, flow_op = _FLOW_ORANGE, 2.5, 0.65
            else:
                flow_color, flow_w, flow_op = _FLOW_GREEN,  2.0, 0.50

            if pid not in path_id_to_osmids:
                continue
            path_osmid_set = set(path_id_to_osmids[pid])

            # Prefer the exact WGS84 coordinate chain stored in delta_t_results
            # (computed from graph node positions in wildland.py — unambiguous).
            # Fall back to the osmid-chain approach only for legacy paths that
            # predate path_wgs84_coords storage.
            _direct_coords = dt_result.get("path_wgs84_coords", [])

            if len(_direct_coords) >= 2:
                # v3.4+: use exact node coordinates — one AntPath, no gaps,
                # no osmid-ambiguity (a single way ID can match many road segments).
                ant_chains: list[list[list[float]]] = [_direct_coords]
            else:
                # Legacy fallback: reconstruct from osmid → geometry lookup.
                path_osmids_ordered = path_id_to_osmids.get(pid, [])
                path_rows = roads_wgs84[
                    roads_wgs84["osmid"].apply(lambda o: _osmid_matches(o, path_osmid_set))
                ]
                osmid_to_seg_geom: dict[str, object] = {}
                for _, _row in path_rows.iterrows():
                    _oid = _row.get("osmid")
                    if _oid is None or _row.geometry is None:
                        continue
                    _strs = ([str(o) for o in _oid] if isinstance(_oid, list)
                             else [str(_oid)])
                    for _s in _strs:
                        if _s not in osmid_to_seg_geom:
                            osmid_to_seg_geom[_s] = _row.geometry

                _GAP_DEG      = 0.0005
                proj_ref      = Point(project.location_lon, project.location_lat)
                prev_exit_pt  = proj_ref
                ant_chains    = []
                current_chain: list[list[float]] = []

                for _oid_str in path_osmids_ordered:
                    _sg = osmid_to_seg_geom.get(_oid_str)
                    if _sg is None or _sg.is_empty:
                        if len(current_chain) >= 2:
                            ant_chains.append(current_chain)
                        current_chain = []
                        continue
                    _raw = list(_sg.coords)
                    if len(_raw) < 2:
                        continue
                    _pt_a = Point(_raw[0])
                    _pt_b = Point(_raw[-1])
                    _ordered = _raw if prev_exit_pt.distance(_pt_a) <= prev_exit_pt.distance(_pt_b) \
                               else list(reversed(_raw))
                    _entry = Point(_ordered[0])
                    if current_chain:
                        _last = current_chain[-1]
                        if math.hypot(_entry.y - _last[0], _entry.x - _last[1]) > _GAP_DEG:
                            if len(current_chain) >= 2:
                                ant_chains.append(current_chain)
                            current_chain = []
                    for _i, (_lon, _lat) in enumerate(_ordered):
                        if _i == 0 and current_chain:
                            _last = current_chain[-1]
                            if abs(_lat - _last[0]) < 1e-7 and abs(_lon - _last[1]) < 1e-7:
                                continue
                        current_chain.append([_lat, _lon])
                    if _ordered:
                        prev_exit_pt = Point(_ordered[-1])
                if len(current_chain) >= 2:
                    ant_chains.append(current_chain)

            tip = (
                f"{'⚠ FLAGGED' if flagged else '✓ OK'} — {bn_name} | "
                f"ΔT {dt_min:.1f} min / {thresh:.1f} min threshold | "
                f"animated dashes flow project → exit"
            )

            # One AntPath per connected sub-chain.  Slow animation (2 s flagged,
            # 3 s ok) so flow direction is easy to read at a glance.
            _ant_weight = flow_w + 2.0
            _ant_delay  = 2000 if flagged else 3000
            for _chain in ant_chains:
                if len(_chain) >= 2:
                    AntPath(
                        locations=_chain,
                        color=flow_color,
                        pulse_color="rgba(255,255,255,0.95)",
                        weight=_ant_weight,
                        delay=_ant_delay,
                        dash_array=[10, 18],
                        tooltip=tip,
                    ).add_to(proj_group)

            # Exit point marker (triangle flag at city-boundary exit)
            if exit_oid and exit_oid not in exit_osmids_drawn:
                exit_mask = roads_wgs84["osmid"].astype(str).str.contains(exit_oid, regex=False)
                exit_rows = roads_wgs84[exit_mask]
                if not exit_rows.empty:
                    exit_geom = exit_rows.iloc[0].geometry
                    if exit_geom is not None and not exit_geom.is_empty:
                        try:
                            exit_pt = exit_geom.interpolate(1.0, normalized=True)
                        except Exception:
                            exit_pt = exit_geom.centroid
                        exit_html = (
                            '<div style="width:18px;height:18px;line-height:18px;'
                            'text-align:center;font-size:13px;'
                            'background:white;border-radius:50%;'
                            'border:2px solid #1565c0;color:#1565c0;">⚑</div>'
                        )
                        folium.Marker(
                            location=[exit_pt.y, exit_pt.x],
                            icon=folium.DivIcon(html=exit_html, icon_size=(18, 18), icon_anchor=(9, 9)),
                            tooltip="City exit point",
                        ).add_to(proj_group)
                        exit_osmids_drawn.add(exit_oid)

        # Serving routes — batched by (color, weight, opacity) into 2 GeoJson
        # layers per project (flagged + neutral).  Popup HTML stored as feature
        # property and bound post-creation via _inject_popup_binders().
        if serving_set and "osmid" in roads_wgs84.columns:
            serving_mask   = roads_wgs84["osmid"].apply(
                lambda o: _osmid_matches(o, serving_set)
            )
            serving_subset = roads_wgs84[serving_mask]

            serving_buckets: dict = defaultdict(list)

            for _, row in serving_subset.iterrows():
                if row.geometry is None or row.geometry.is_empty:
                    continue
                osmid_val  = row.get("osmid")
                is_flagged = _osmid_matches(osmid_val, flagged_set)
                seg_color  = route_flagged_color if is_flagged else _SERVING_ROUTE_NEUTRAL_COLOR
                weight     = _FLAGGED_ROUTE_WEIGHT if is_flagged else _SERVING_ROUTE_NEUTRAL_WEIGHT
                opacity    = _FLAGGED_ROUTE_OPACITY if is_flagged else _SERVING_ROUTE_NEUTRAL_OPACITY

                name_raw = row.get("name", "Unnamed") or "Unnamed"
                name_str = (name_raw[0] if isinstance(name_raw, list) and name_raw
                            else str(name_raw))
                if name_str in ("nan", "None", ""):
                    name_str = "Unnamed"

                hcm_cap    = float(row.get("capacity_vph", 1) or 1)
                eff_cap    = float(row.get("effective_capacity_vph", hcm_cap) or hcm_cap)
                fhsz_zone  = str(row.get("fhsz_zone", "non_fhsz") or "non_fhsz")
                hazard_deg = float(row.get("hazard_degradation", 1.0) or 1.0)
                road_type_s  = str(row.get("road_type", "") or "")
                lane_count_s = int(row.get("lane_count", 0) or 0)
                speed_lim_s  = int(row.get("speed_limit", 0) or 0)

                osmid_strs = (
                    [str(osmid_val)] if not isinstance(osmid_val, list)
                    else [str(o) for o in osmid_val]
                )
                dt_result = next(
                    (bottleneck_dt_map[s] for s in osmid_strs if s in bottleneck_dt_map),
                    None,
                )

                popup_html = _build_route_delta_t_popup(
                    name_str, eff_cap, hcm_cap, fhsz_zone, hazard_deg,
                    dt_result, is_flagged,
                    road_type=road_type_s, lane_count=lane_count_s, speed_limit=speed_lim_s,
                )

                if is_flagged and dt_result:
                    tip = (
                        f"⚠ ΔT exceeded — {name_str} "
                        f"| {dt_result['delta_t_minutes']:.2f} min "
                        f"> {dt_result['threshold_minutes']:.2f} min"
                    )
                elif is_flagged:
                    tip = f"⚠ ΔT exceeded — {name_str} | bottleneck segment"
                else:
                    tip = f"serving route — {name_str} | {eff_cap:.0f} vph eff cap"

                serving_buckets[(seg_color, weight, opacity)].append({
                    "type": "Feature",
                    "geometry": mapping(row.geometry),
                    "properties": {
                        "tooltip": tip,
                        "popup_html": popup_html,
                    },
                })

            _serving_gj_names: list[str] = []
            for (seg_color, weight, opacity), features in serving_buckets.items():
                fc = {"type": "FeatureCollection", "features": features}
                gj = folium.GeoJson(
                    fc,
                    style_function=lambda _, c=seg_color, w=weight, o=opacity: {
                        "color": c, "weight": w, "opacity": o,
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=["tooltip"],
                        labels=False,
                        style=(
                            "font-family: system-ui, sans-serif; font-size: 11px; "
                            "padding: 3px 8px; white-space: nowrap;"
                        ),
                    ),
                    smooth_factor=1.5,
                )
                gj.add_to(proj_group)
                _serving_gj_names.append(gj.get_name())

            _all_popup_gj_names.extend(_serving_gj_names)

        # ── Bottleneck concentric rings — one set per unique flagged bottleneck ──
        # Three concentric CircleMarkers + filled center dot placed at the midpoint
        # of each flagged bottleneck road segment.  Fixed pixel radii so the rings
        # stay the same visual size at any zoom level.  Replaces the single warning
        # triangle — all constraint surfaces are shown, not just the worst-ΔT path.
        if tier != "MINISTERIAL" and "osmid" in roads_wgs84.columns:
            _drawn_bns: set[str] = set()   # deduplicate by bottleneck osmid
            for _dt_r in (project.delta_t_results or []):
                if not _dt_r.get("flagged"):
                    continue
                _bn_osmid = str(_dt_r.get("bottleneck_osmid", ""))
                if not _bn_osmid or _bn_osmid in _drawn_bns:
                    continue
                _drawn_bns.add(_bn_osmid)

                _dt_min   = float(_dt_r.get("delta_t_minutes", 0))
                _thresh   = float(_dt_r.get("threshold_minutes", 6.0)) or 6.0
                _severity = _dt_min / _thresh
                # Severe (ΔT > 2× threshold) → deep red; otherwise project red/orange
                if _severity >= 2.0:
                    _rc = "#7f0000"
                elif _severity >= 1.0:
                    _rc = "#b71c1c"
                else:
                    _rc = "#e65100"

                # Road midpoint from roads_wgs84 geometry
                _bn_mask = roads_wgs84["osmid"].astype(str).str.contains(
                    _bn_osmid, regex=False
                )
                _bn_rows = roads_wgs84[_bn_mask]
                if _bn_rows.empty:
                    continue
                _bn_geom = _bn_rows.iloc[0].geometry
                if _bn_geom is None or _bn_geom.is_empty:
                    continue
                try:
                    _mid = _bn_geom.interpolate(0.5, normalized=True)
                except Exception:
                    _mid = _bn_geom.centroid

                _bn_name = str(_dt_r.get("bottleneck_name", "") or "Bottleneck")
                _bn_tip  = (
                    f"Bottleneck — {_bn_name} | "
                    f"ΔT {_dt_min:.1f} min / {_thresh:.1f} min threshold"
                )

                # Three rings: outer → inner, fading opacity inward → out
                for _r_px, _op in ((22, 0.25), (14, 0.50), (7, 0.80)):
                    folium.CircleMarker(
                        location=[_mid.y, _mid.x],
                        radius=_r_px,
                        color=_rc,
                        weight=1.2,
                        fill=False,
                        opacity=_op,
                        tooltip=_bn_tip,
                    ).add_to(proj_group)
                # Solid center dot
                folium.CircleMarker(
                    location=[_mid.y, _mid.x],
                    radius=3,
                    color=_rc,
                    weight=0,
                    fill=True,
                    fill_color=_rc,
                    fill_opacity=0.90,
                    tooltip=_bn_tip,
                ).add_to(proj_group)

        # Project marker (wildland group — visible in Scenario A)
        folium.Marker(
            location=[project.location_lat, project.location_lon],
            popup=folium.Popup(
                _build_demo_project_popup(
                    project, route_color, vc_threshold, unit_threshold,
                    worst_wildland_route=worst_wildland_route,
                    worst_local_route=None,   # SB 79 has no route details
                    ld_tier=ld_tier,
                    ld_triggered=ld_triggered,
                ),
                max_width=360,
            ),
            tooltip=f"{project.project_name} · {tier}",
            icon=folium.Icon(color=marker_color, icon="home", prefix="fa"),
        ).add_to(proj_group)

        # Additional egress point markers — city-planner-defined secondary exits.
        # Drawn as small circle markers distinct from the primary home pin.
        for _aep in getattr(project, "additional_egress_points", []):
            _aep_lat   = float(_aep.get("lat", 0))
            _aep_lon   = float(_aep.get("lon", 0))
            _aep_label = _aep.get("label", "Additional egress")
            _aep_note  = _aep.get("note", "")
            _aep_tip   = f"{_aep_label}" + (f" — {_aep_note}" if _aep_note else "")
            # Outer ring + filled centre — visually paired with primary pin color
            # but smaller and with an "egress-only" visual language.
            folium.CircleMarker(
                location=[_aep_lat, _aep_lon],
                radius=10,
                color=marker_color,
                weight=2,
                fill=False,
                opacity=0.85,
                tooltip=_aep_tip,
            ).add_to(proj_group)
            folium.CircleMarker(
                location=[_aep_lat, _aep_lon],
                radius=4,
                color=marker_color,
                weight=0,
                fill=True,
                fill_color=marker_color,
                fill_opacity=0.90,
                tooltip=_aep_tip,
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
    # Bind per-feature popup HTML stored in GeoJSON properties.
    # Runs after all Folium _add(data) calls have populated the layer trees.
    _inject_popup_binders(m, _all_popup_gj_names, max_width=340)
    _add_zoom_weight_scaler(m, ref_zoom=13)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    logger.info(f"Demo map saved: {output_path}")

    # ── What-if bundle injection (feat/whatif-browser) ────────────────────
    # Inline graph.json, parameters.json, fhsz GeoJSON, and the JS engine into
    # the saved HTML so the file is fully self-contained (works from file://).
    if graph_json_path and graph_json_path.exists() and params_json_path and params_json_path.exists():
        _inject_whatif_bundle(output_path, graph_json_path, params_json_path, fhsz_gdf)
        logger.info("  What-if bundle injected into demo map.")
    else:
        logger.info("  Skipping what-if bundle (graph.json or parameters.json not found).")

    # ── Brief modal injection ──────────────────────────────────────────────
    # Replace external brief file links with inline srcdoc modals so the
    # "View Determination Brief" button works when opened from file://.
    _inject_brief_modals(output_path)

    # ── "What Happened" layer ──────────────────────────────────────────────
    # City-specific historical overlay: fire perimeter, road diet annotation,
    # Grand Jury timeline, and JOSH infrastructure verdict. Opt-in via
    # city_config.what_happened.enabled. Currently used for Paradise, CA.
    if city_config and data_dir:
        _inject_what_happened_layer(output_path, city_config, data_dir)

    return output_path


# ---------------------------------------------------------------------------
# What-if browser bundle injection (feat/whatif-browser)
# ---------------------------------------------------------------------------

def _inject_whatif_bundle(
    html_path: Path,
    graph_json_path: Path,
    params_json_path: Path,
    fhsz_gdf: gpd.GeoDataFrame,
) -> None:
    """
    Read the saved demo_map.html, inject the what-if JS engine + data bundle,
    and write the file back.  All three data sources are inlined as JS globals
    so the file remains standalone (no fetch() calls, works from file://).

    Injected globals:
      JOSH_GRAPH   — graph.json contents  (nodes, edges, exit_nodes)
      JOSH_PARAMS  — parameters.json contents
      JOSH_FHSZ    — fhsz GeoJSON FeatureCollection

    The engine (static/whatif_engine.js) is also inlined and reads these globals
    on first evaluateProject() call.
    """
    import json as _json
    from pathlib import Path as _Path

    # Load data files
    graph_data   = _json.loads(graph_json_path.read_text())
    params_data  = _json.loads(params_json_path.read_text())
    fhsz_geojson = _json.loads(fhsz_gdf.to_crs("EPSG:4326").to_json())

    # Locate engine source
    engine_path = _Path(__file__).parent.parent.parent / "static" / "whatif_engine.js"
    engine_js   = engine_path.read_text() if engine_path.exists() else "// engine not found"

    # Build injection block
    data_block = f"""
<script id="josh-whatif-data">
const JOSH_GRAPH  = {_json.dumps(graph_data,  separators=(',',':'))};
const JOSH_PARAMS = {_json.dumps(params_data, separators=(',',':'))};
const JOSH_FHSZ   = {_json.dumps(fhsz_geojson, separators=(',',':'))};
</script>
<script id="josh-whatif-engine">
{engine_js}
</script>
<script id="josh-whatif-ui">
{_build_whatif_ui_js()}
</script>
{_build_whatif_ui_html()}
"""

    # Inject before </body>
    html = html_path.read_text(encoding="utf-8")
    if "</body>" in html:
        html = html.replace("</body>", data_block + "\n</body>", 1)
    else:
        html += data_block
    html_path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Determination brief inline modal (fixes file:// link blocking)
# ---------------------------------------------------------------------------

def _inject_brief_modals(html_path: Path) -> None:
    """
    Replace "View Determination Brief" external-file links with an inline
    <iframe srcdoc> modal so the button works when the demo map is opened
    from file:// (Safari and Chrome both block file://→file:// navigation
    via target="_blank").

    Scans the saved HTML for href="brief_v3_*.html" links, reads each brief
    file from the same directory, and injects:
      - A modal overlay with a full-height <iframe id="josh-brief-frame">
      - A <script> with the brief data keyed by filename + joshBrief.show()
      - A DOM-ready click interceptor that overrides the <a href> clicks

    The brief HTML is set via frame.srcdoc (JS property, not HTML attribute)
    so no escaping is needed.  srcdoc renders the complete document inline —
    no external file access, works from file:// on all browsers.
    """
    import re as _re

    html = html_path.read_text(encoding="utf-8")
    output_dir = html_path.parent

    # Find all brief filenames referenced in the HTML
    filenames = _re.findall(r'href="(brief_v3_[^"]+\.html)"', html)
    if not filenames:
        return  # no briefs in this map

    # Read each brief file; skip missing ones silently
    brief_data: dict[str, str] = {}
    for fname in dict.fromkeys(filenames):  # deduplicate, preserve order
        path = output_dir / fname
        if path.exists():
            brief_data[fname] = path.read_text(encoding="utf-8")

    if not brief_data:
        logger.warning("_inject_brief_modals: brief files not found in %s", output_dir)
        return

    # Build JS object literal: { "filename": <brief HTML string>, ... }
    # Use json.dumps for each value so special chars / newlines are escaped.
    entries = ",\n".join(
        f"  {json.dumps(fname)}: {json.dumps(content)}"
        for fname, content in brief_data.items()
    )
    brief_data_js = "{\n" + entries + "\n}"

    injection = f"""
<div id="josh-brief-modal" style="
    display:none; position:fixed; inset:0; z-index:30000;
    background:rgba(0,0,0,0.55); overflow:hidden;">
  <div style="
      position:absolute; inset:40px 60px;
      background:#fff; border-radius:8px;
      display:flex; flex-direction:column;
      box-shadow:0 8px 40px rgba(0,0,0,0.4);
      overflow:hidden;">
    <div style="
        display:flex; align-items:center; justify-content:space-between;
        padding:11px 16px; border-bottom:1px solid #dee2e6;
        background:#1c4a6e; flex-shrink:0;">
      <span style="
          font-family:system-ui,sans-serif; font-weight:600;
          font-size:13px; color:#fff; letter-spacing:0.02em;">
        Determination Brief
      </span>
      <button onclick="document.getElementById('josh-brief-modal').style.display='none'"
              style="background:none;border:none;font-size:20px;cursor:pointer;
                     color:rgba(255,255,255,0.75);line-height:1;padding:0;">&#10005;</button>
    </div>
    <iframe id="josh-brief-frame"
            style="flex:1;border:none;width:100%;background:#fff;"
            src="about:blank"></iframe>
  </div>
</div>

<script id="josh-brief-modals">
(function () {{
  var _BRIEFS = {brief_data_js};

  window.joshBrief = {{
    show: function (filename) {{
      var html = _BRIEFS[filename];
      if (!html) {{ console.warn('joshBrief: no data for', filename); return; }}
      var frame = document.getElementById('josh-brief-frame');
      frame.srcdoc = html;
      document.getElementById('josh-brief-modal').style.display = 'block';
    }}
  }};

  // Intercept brief link clicks — override href navigation with inline modal.
  // Runs on DOMContentLoaded (brief links are pre-rendered in the HTML body).
  document.addEventListener('DOMContentLoaded', function () {{
    document.querySelectorAll('a[href^="brief_v3_"]').forEach(function (link) {{
      link.addEventListener('click', function (e) {{
        e.preventDefault();
        window.joshBrief.show(link.getAttribute('href'));
      }});
    }});
    // Close on backdrop click
    document.getElementById('josh-brief-modal').addEventListener('click', function (e) {{
      if (e.target === this) this.style.display = 'none';
    }});
  }});
}})();
</script>
"""

    if "</body>" in html:
        html = html.replace("</body>", injection + "\n</body>", 1)
    else:
        html += injection
    html_path.write_text(html, encoding="utf-8")
    logger.info("  Brief modals injected (%d briefs).", len(brief_data))


def _build_whatif_ui_html() -> str:
    """
    Fixed sidebar panel for the what-if project input form.
    Styled to match the existing JOSH control panel aesthetic (dark header,
    white body, same font stack).
    """
    return """
<div id="josh-whatif-panel" style="
    position: fixed;
    bottom: 32px;
    right: 16px;
    width: 300px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.22);
    z-index: 10000;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
    overflow: hidden;
    display: none;
">
  <div style="background:#1c4a6e;color:#fff;padding:10px 14px;display:flex;align-items:center;gap:8px;cursor:move;" id="josh-whatif-drag-handle">
    <span style="font-size:15px;">&#9654;</span>
    <span style="font-weight:600;font-size:13px;letter-spacing:0.02em;">What-If Analysis</span>
    <span style="margin-left:auto;cursor:pointer;font-size:16px;opacity:0.7;" onclick="joshWhatIf.closePanel();" title="Close">&#10005;</span>
  </div>
  <div style="padding:12px 14px;">
    <div id="josh-whatif-instructions" style="color:#555;font-size:12px;margin-bottom:10px;line-height:1.5;">
      Set units &amp; stories, then drop a pin.
    </div>
    <div style="display:flex;gap:8px;margin-bottom:8px;">
      <label style="flex:1;">
        <div style="font-size:11px;color:#777;margin-bottom:3px;">Units</div>
        <input id="josh-wi-units" type="number" min="1" max="999" value="50" style="width:100%;box-sizing:border-box;border:1px solid #ccc;border-radius:4px;padding:5px 7px;font-size:13px;">
      </label>
      <label style="flex:1;">
        <div style="font-size:11px;color:#777;margin-bottom:3px;">Stories</div>
        <input id="josh-wi-stories" type="number" min="0" max="60" value="4" style="width:100%;box-sizing:border-box;border:1px solid #ccc;border-radius:4px;padding:5px 7px;font-size:13px;">
      </label>
    </div>
    <div id="josh-whatif-result" style="display:none;margin-top:10px;border-top:1px solid #eee;padding-top:10px;"></div>
    <div style="margin-top:10px;display:flex;gap:6px;">
      <button id="josh-wi-btn-pin" onclick="joshWhatIf.startDropPin()" style="
          flex:1;background:#1c4a6e;color:#fff;border:none;border-radius:5px;
          padding:7px 0;font-size:12px;cursor:pointer;font-weight:600;">
        &#x2316; Drop Pin
      </button>
      <button id="josh-wi-btn-clear" onclick="joshWhatIf.clearWhatIf()" style="
          flex:0 0 auto;background:#f5f5f5;color:#555;border:1px solid #ccc;
          border-radius:5px;padding:7px 10px;font-size:12px;cursor:pointer;
          display:none;">
        &#x2715; Clear
      </button>
    </div>
    <div style="margin-top:10px;color:#999;font-size:10px;line-height:1.4;border-top:1px solid #f0f0f0;padding-top:8px;" id="josh-wi-disclaimer">
      What-if estimates only &mdash; not a legal determination.<br>
      Run <code>main.py evaluate</code> for a binding audit trail.
    </div>
  </div>
</div>

<style>
.josh-wi-tooltip {
  font-family: system-ui, sans-serif;
  font-size: 11px;
  padding: 4px 8px;
  background: rgba(28,74,110,0.92);
  color: #fff;
  border: none;
  border-radius: 4px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  white-space: nowrap;
}
.josh-wi-tooltip::before { display: none; }
</style>

<button id="josh-whatif-open-btn" onclick="joshWhatIf.openPanel()" style="
    position: fixed;
    bottom: 32px;
    right: 16px;
    z-index: 10000;
    background: #1c4a6e;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 9px 15px;
    font-family: system-ui, sans-serif;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 3px 12px rgba(0,0,0,0.25);
    letter-spacing: 0.01em;
">&#43; What-If Project</button>
"""


def _build_whatif_ui_js() -> str:
    """
    JavaScript controller for the what-if panel.

    UX state machine:
      IDLE        — no pin; "Drop Pin" button only
      AWAITING    — crosshair cursor, one-time map click listener; "Cancel" button
      PIN PLACED  — draggable pin on map; inputs auto-re-evaluate (300ms debounce);
                    "Drop New Pin" + "✕ Clear" buttons

    Dragging: L.marker with DivIcon (dashed circle) instead of L.circleMarker,
    which has no drag support.  On dragend, routes redraw and result updates.

    Auto re-evaluate: input event listeners on Units + Stories.  If a pin is
    placed (_lat !== null), changes trigger a 300ms debounced re-evaluate so the
    result is always live — no "stale result" state.
    """
    return r"""
(function () {
  const TIER_COLOR = {
    'MINISTERIAL':                         '#27ae60',
    'MINISTERIAL WITH STANDARD CONDITIONS': '#e67e22',
    'DISCRETIONARY':                        '#e74c3c',
  };
  const TIER_LABEL = {
    'MINISTERIAL':                         'Ministerial',
    'MINISTERIAL WITH STANDARD CONDITIONS': 'Ministerial w/ Conditions',
    'DISCRETIONARY':                        'Discretionary',
  };
  const ZONE_LABEL = {
    'vhfhsz':        'Very High FHSZ',
    'high_fhsz':     'High FHSZ',
    'moderate_fhsz': 'Moderate FHSZ',
    'non_fhsz':      'Non-FHSZ',
  };

  // ── Module state ────────────────────────────────────────────────────────────
  let _dropPinActive = false;
  let _markers       = [];        // all map layers owned by the what-if UI
  let _wiMarker      = null;      // the draggable L.marker (kept separate for setIcon/drag)
  let _mapObj        = null;
  let _origCursor    = '';
  let _lat           = null;      // last placed pin latitude  (null = no pin)
  let _lng           = null;      // last placed pin longitude
  let _debounce      = null;      // setTimeout handle for input debounce

  // ── Map discovery ───────────────────────────────────────────────────────────
  function _getMap() {
    if (_mapObj) return _mapObj;
    for (const k in window) {
      if (window[k] && window[k]._leaflet_id && window[k].getCenter) {
        _mapObj = window[k]; return _mapObj;
      }
    }
    const el = document.querySelector('.folium-map');
    if (el && el._leaflet_id) { _mapObj = window['map_' + el._leaflet_id] || null; }
    return _mapObj;
  }

  // ── DivIcon factory — dashed circle with "?" label, colour-coded by tier ─────
  // Uses L.divIcon instead of L.circleMarker so the marker is draggable.
  // 28px gives a comfortable drag target and stands out on a busy street map.
  // The "?" reinforces the exploratory / what-if nature of the pin.
  function _wiIcon(color) {
    return L.divIcon({
      className: '',   // suppress Leaflet's default white square
      html: `<div style="
        width: 28px; height: 28px;
        border: 2.5px dashed ${color};
        border-radius: 50%;
        background: ${color};
        opacity: 0.75;
        box-sizing: border-box;
        display: flex; align-items: center; justify-content: center;
        font-family: system-ui, sans-serif;
        font-size: 14px; font-weight: 700;
        color: #fff;
        text-shadow: 0 1px 2px rgba(0,0,0,0.4);
        cursor: grab;
      ">?</div>`,
      iconSize:   [28, 28],
      iconAnchor: [14, 14],   // centred on the click/drag point
    });
  }

  // ── Panel open ──────────────────────────────────────────────────────────────
  function openPanel() {
    document.getElementById('josh-whatif-open-btn').style.display = 'none';
    document.getElementById('josh-whatif-panel').style.display    = 'block';
  }

  // ── State transitions ───────────────────────────────────────────────────────

  /** Enter AWAITING state: crosshair cursor, one-time click listener. */
  function startDropPin() {
    const map = _getMap();
    if (!map) { alert('Map not ready \u2014 please wait a moment and try again.'); return; }
    _dropPinActive = true;
    _origCursor = map.getContainer().style.cursor;
    map.getContainer().style.cursor = 'crosshair';
    document.getElementById('josh-whatif-instructions').textContent =
      'Click the map to place a pin\u2026';
    const btn = document.getElementById('josh-wi-btn-pin');
    btn.textContent = '\u2716 Cancel';
    btn.onclick = cancelDropPin;
    map.once('click', _onMapClick);
  }

  /** Cancel AWAITING state without placing a pin. */
  function cancelDropPin() {
    const map = _getMap();
    if (map) {
      map.getContainer().style.cursor = _origCursor;
      map.off('click', _onMapClick);
    }
    _dropPinActive = false;
    _restoreIdleOrPinnedButton();
    document.getElementById('josh-whatif-instructions').textContent =
      _lat !== null
        ? 'Drag pin or adjust inputs to update.'
        : 'Set units & stories, then drop a pin.';
  }

  /**
   * Restore the Drop Pin button to the correct label for the current state:
   *   - PIN PLACED → "Drop New Pin" (re-enter AWAITING to relocate)
   *   - IDLE       → "Drop Pin"
   */
  function _restoreIdleOrPinnedButton() {
    const btn = document.getElementById('josh-wi-btn-pin');
    if (_lat !== null) {
      btn.textContent = '\u2316 Drop New Pin';
    } else {
      btn.textContent = '\u2316 Drop Pin';
    }
    btn.onclick = startDropPin;
  }

  // ── Map click handler (AWAITING → PIN PLACED) ───────────────────────────────
  function _onMapClick(e) {
    _dropPinActive = false;
    const map = _getMap();
    if (map) map.getContainer().style.cursor = _origCursor;
    _placePin(e.latlng.lat, e.latlng.lng);
  }

  /** Place (or replace) the draggable marker and evaluate. */
  function _placePin(lat, lng) {
    // Remove existing pin + routes; keep nothing from prior evaluation
    _clearAll();
    const map = _getMap();
    _lat = lat;
    _lng = lng;

    if (map) {
      _wiMarker = L.marker([lat, lng], {
        icon: _wiIcon('#e67e22'),   // neutral orange while evaluating
        draggable: true,
        zIndexOffset: 500,
      }).addTo(map);
      _wiMarker.on('dragstart', _onDragStart);
      _wiMarker.on('dragend',   _onDragEnd);
      _markers.push(_wiMarker);
    }

    _evaluateAt(lat, lng);
  }

  // ── Drag handlers ───────────────────────────────────────────────────────────

  function _onDragStart() {
    // Dim result and clear old routes while the pin is moving
    const el = document.getElementById('josh-whatif-result');
    if (el) el.style.opacity = '0.3';
    document.getElementById('josh-whatif-instructions').textContent = 'Moving pin\u2026';
    _clearRoutes();
  }

  function _onDragEnd(e) {
    _lat = e.target.getLatLng().lat;
    _lng = e.target.getLatLng().lng;
    _evaluateAt(_lat, _lng);
  }

  // ── Route line color ramp ───────────────────────────────────────────────────
  // Mirrors the AntPath ramp used for official project routes:
  //   < 40% threshold  → green  (ample capacity)
  //   40–75%           → yellow (moderate load)
  //   75–100%          → orange (approaching threshold)
  //   > 100% (flagged) → red    (exceeds threshold)
  function _routeColor(delta_t, threshold) {
    const ratio = threshold > 0 ? delta_t / threshold : 1;
    if (ratio > 1.0)  return '#e74c3c';   // red    — flagged
    if (ratio > 0.75) return '#e67e22';   // orange — approaching
    if (ratio > 0.40) return '#f1c40f';   // yellow — moderate
    return '#27ae60';                      // green  — ample
  }

  // ── Core evaluation ─────────────────────────────────────────────────────────

  /**
   * Run WhatIfEngine.evaluateProject() for the current inputs at (lat, lng),
   * redraw route polylines, update the pin icon colour, and render the result.
   * Called from: initial pin placement, drag end, debounced input change.
   */
  function _evaluateAt(lat, lng) {
    const units   = parseInt(document.getElementById('josh-wi-units').value,   10) || 1;
    const stories = parseInt(document.getElementById('josh-wi-stories').value, 10) || 0;

    let result;
    try {
      result = WhatIfEngine.evaluateProject(lat, lng, units, stories);
    } catch (err) {
      document.getElementById('josh-whatif-instructions').textContent =
        'Error: ' + err.message;
      const el = document.getElementById('josh-whatif-result');
      if (el) el.style.opacity = '1';
      return;
    }

    const map       = _getMap();
    const tierColor = TIER_COLOR[result.tier] || '#888';

    // Update pin icon to tier colour
    if (_wiMarker) _wiMarker.setIcon(_wiIcon(tierColor));

    // Clear stale routes (pin is kept via _wiMarker exclusion in _clearRoutes)
    _clearRoutes();

    if (map) {
      for (const path of result.paths) {
        if (!path.path_coords || path.path_coords.length < 2) continue;
        const lineColor = _routeColor(path.delta_t_minutes, path.threshold_minutes);

        // Full route — thin dashed line
        const routeLine = L.polyline(path.path_coords, {
          color:     lineColor,
          weight:    3,
          opacity:   0.75,
          dashArray: path.flagged ? null : '6,4',
        });
        routeLine.bindTooltip(
          `Evacuation route \u00b7 \u0394T ${path.delta_t_minutes.toFixed(2)} min ` +
          `(threshold ${path.threshold_minutes.toFixed(2)} min)` +
          (path.flagged ? ' \u26a0 EXCEEDS THRESHOLD' : ''),
          { sticky: true, className: 'josh-wi-tooltip' }
        );
        routeLine.addTo(map);
        _markers.push(routeLine);

        // Bottleneck segment — thick highlight
        if (path.bottleneck_coords && path.bottleneck_coords.length === 2) {
          const bnLine = L.polyline(path.bottleneck_coords, {
            color: lineColor, weight: 8, opacity: 0.9,
          });
          bnLine.bindTooltip(
            `Bottleneck \u00b7 ${path.bottleneckOsmid} \u00b7 ${path.bottleneckEffCapVph.toFixed(0)} vph`,
            { sticky: true, className: 'josh-wi-tooltip' }
          );
          bnLine.addTo(map);
          _markers.push(bnLine);
        }
      }
    }

    // Restore result opacity (may have been dimmed during drag)
    const resultEl = document.getElementById('josh-whatif-result');
    if (resultEl) resultEl.style.opacity = '1';

    _renderResult(result);
    _restoreIdleOrPinnedButton();
    // Show the Clear button now that a pin is placed
    document.getElementById('josh-wi-btn-clear').style.display = '';
    document.getElementById('josh-whatif-instructions').textContent =
      'Drag pin or adjust inputs to update.';
  }

  // ── Result renderer ─────────────────────────────────────────────────────────
  function _renderResult(result) {
    const color      = TIER_COLOR[result.tier] || '#888';
    const tierLabel  = TIER_LABEL[result.tier] || result.tier;
    const zoneLabel  = ZONE_LABEL[result.hazard_zone] || result.hazard_zone;
    const maxDT      = result.max_delta_t_minutes;
    const threshold  = result.paths.length > 0 ? result.paths[0].threshold_minutes : null;
    const flaggedCnt = result.paths.filter(p => p.flagged).length;

    let pathRows = '';
    for (const p of result.paths) {
      const dtColor = p.flagged ? '#e74c3c' : '#27ae60';
      pathRows += `<tr>
        <td style="padding:2px 6px;font-size:11px;color:#555;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${p.bottleneckOsmid}">${p.bottleneckOsmid}</td>
        <td style="padding:2px 6px;font-size:11px;text-align:right;color:${dtColor};font-weight:${p.flagged?'700':'400'};">${p.delta_t_minutes.toFixed(2)}</td>
        <td style="padding:2px 6px;font-size:11px;text-align:right;color:#999;">${p.threshold_minutes.toFixed(2)}</td>
      </tr>`;
    }

    const builtAt    = result.built_at ? result.built_at.slice(0, 10) : '?';
    const threshDisp = threshold !== null ? threshold.toFixed(2) : '\u2014';

    const el = document.getElementById('josh-whatif-result');
    el.style.display = 'block';
    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${color};border:2px dashed ${color};opacity:0.9;flex-shrink:0;"></span>
        <span style="font-weight:700;font-size:13px;color:${color};">${tierLabel}</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:11px;color:#555;margin-bottom:8px;">
        <div>Zone: <b>${zoneLabel}</b></div>
        <div>Vehicles: <b>${result.project_vehicles.toFixed(0)} vph</b></div>
        <div>Max &Delta;T: <b style="color:${threshold !== null && maxDT > threshold ? '#e74c3c' : '#333'};">${maxDT.toFixed(2)} min</b></div>
        <div>Threshold: <b>${threshDisp} min</b></div>
        <div>Paths: <b>${result.serving_paths_count}</b></div>
        <div>Flagged: <b style="color:${flaggedCnt > 0 ? '#e74c3c' : '#27ae60'};">${flaggedCnt}</b></div>
      </div>
      ${pathRows ? `
      <div style="font-size:10px;color:#aaa;margin-bottom:2px;">Bottleneck &nbsp; &Delta;T &nbsp; Limit (min)</div>
      <table style="width:100%;border-collapse:collapse;">
        <tbody>${pathRows}</tbody>
      </table>` : '<div style="font-size:11px;color:#aaa;">No serving paths found.</div>'}
      <div style="margin-top:8px;font-size:10px;color:#bbb;">
        Data: OSM ${builtAt} &middot; v${result.parameters_version}
      </div>
    `;
  }

  // ── Clear helpers ───────────────────────────────────────────────────────────

  /** Remove only route polylines; keep _wiMarker (used during drag + input re-eval). */
  function _clearRoutes() {
    const map = _getMap();
    _markers = _markers.filter(m => {
      if (m === _wiMarker) return true;   // keep the pin
      try { map && map.removeLayer(m); } catch (_) {}
      return false;
    });
  }

  /** Remove everything — pin, routes, and all state. Returns to IDLE. */
  function _clearAll() {
    const map = _getMap();
    for (const m of _markers) { try { map && map.removeLayer(m); } catch (_) {} }
    _markers  = [];
    _wiMarker = null;
  }

  /** Public clear: full reset to IDLE state. */
  function clearWhatIf() {
    clearTimeout(_debounce);
    _clearAll();
    _lat = null;
    _lng = null;
    const resultEl = document.getElementById('josh-whatif-result');
    resultEl.style.display  = 'none';
    resultEl.style.opacity  = '1';
    resultEl.innerHTML      = '';
    document.getElementById('josh-wi-btn-clear').style.display = 'none';
    document.getElementById('josh-whatif-instructions').textContent =
      'Set units & stories, then drop a pin.';
    _restoreIdleOrPinnedButton();
  }

  // ── Input auto-re-evaluate ──────────────────────────────────────────────────
  // Attach listeners once the DOM is ready.  Only fires when a pin is placed.
  document.addEventListener('DOMContentLoaded', () => {
    ['josh-wi-units', 'josh-wi-stories'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('input', () => {
        if (_lat === null) return;          // no pin yet — do nothing
        clearTimeout(_debounce);
        document.getElementById('josh-whatif-instructions').textContent = 'Updating\u2026';
        _debounce = setTimeout(() => _evaluateAt(_lat, _lng), 300);
      });
    });
  });

  /** Close the panel and restore the open button. Cancels any active drop-pin mode. */
  function closePanel() {
    cancelDropPin();
    document.getElementById('josh-whatif-panel').style.display    = 'none';
    document.getElementById('josh-whatif-open-btn').style.display = '';
  }

  window.joshWhatIf = { openPanel, closePanel, startDropPin, cancelDropPin, clearWhatIf };
})();
"""


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
        "MINISTERIAL WITH STANDARD CONDITIONS": "STD",
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
    top: 68px; right: 10px;
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

  // ── Init: show only project 0 ─────────────────────────────────────
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
    """Pre-rendered hidden card for one project. JS toggles display:block/none.

    v3.1: ΔT gauge replaces three-column strip; what-if analysis collapsible;
    data-* attributes enable client-side recalculation.
    """
    tier         = project.determination or "UNKNOWN"
    det_color    = _TIER_CSS_COLOR.get(tier, "#555")
    bg_color     = _TIER_BG_COLOR.get(tier, "#fafafa")
    border_color = {
        "DISCRETIONARY":           "#e8b4b0",
        "MINISTERIAL WITH STANDARD CONDITIONS": "#f5d49a",
        "MINISTERIAL":             "#a8d5b8",
    }.get(tier, "#dee2e6")

    display      = "block" if idx == 0 else "none"
    action_label = _TIER_ACTION_LABELS.get(tier, "")

    # ── Config values ────────────────────────────────────────────────────
    max_share_v_cfg = config.get("max_project_share", 0.05)
    safe_egress_cfg = config.get("safe_egress_window", {})

    # ── Hazard zone / mob rate ────────────────────────────────────────────
    hazard_zone = getattr(project, "hazard_zone", "non_fhsz") or "non_fhsz"
    mob_rate    = config.get("mobilization_rate", 0.90)  # NFPA 101 design basis, constant
    mob_pct     = f"{mob_rate:.0%}"

    _zone_labels = {
        "vhfhsz":        "VHFHSZ",
        "high_fhsz":     "High FHSZ",
        "moderate_fhsz": "Mod. FHSZ",
        "non_fhsz":      "Non-FHSZ",
    }
    hz_label = _zone_labels.get(hazard_zone, hazard_zone)

    # Config-derived fallback threshold
    safe_window_cfg_val = float(safe_egress_cfg.get(hazard_zone, 120.0))
    threshold_cfg_val   = safe_window_cfg_val * max_share_v_cfg

    # ── ΔT summary from per-path results ─────────────────────────────────
    dt_results = project.delta_t_results or []
    size_met   = project.meets_size_threshold

    if dt_results and size_met:
        max_dt      = max(r.get("delta_t_minutes", 0) for r in dt_results)
        best_result = max(dt_results, key=lambda r: r.get("delta_t_minutes", 0))
        threshold   = best_result.get("threshold_minutes", threshold_cfg_val)
        safe_window = best_result.get("safe_egress_window_minutes", safe_window_cfg_val)
        max_share_v = best_result.get("max_project_share", max_share_v_cfg)
        exceeded    = any(r.get("flagged") for r in dt_results)

        dt_color        = "#c0392b" if exceeded else "#27ae60"
        indicator_color = dt_color
        if threshold > 0:
            gauge_pct    = min((max_dt / (2 * threshold)) * 100.0, 105.0)
            gauge_numtxt = f"{max_dt:.2f} min / {threshold:.2f} min limit"
        else:
            gauge_pct    = 0.0
            gauge_numtxt = "—"
    else:
        threshold       = threshold_cfg_val
        safe_window     = safe_window_cfg_val
        max_share_v     = max_share_v_cfg
        dt_color        = "#adb5bd"
        indicator_color = "#adb5bd"
        gauge_pct       = 0.0
        gauge_numtxt    = "—"

    # ── Controlling finding line ──────────────────────────────────────────
    if not size_met:
        finding_text = (
            f"{project.dwelling_units} units — below {unit_threshold}-unit threshold"
        )
    elif dt_results and worst_wildland_route:
        nm     = (worst_wildland_route.get("name") or "bottleneck segment")[:38]
        dt_wc  = worst_wildland_route.get("delta_t_minutes", 0)
        thr_wc = worst_wildland_route.get("threshold_minutes", threshold)
        if worst_wildland_route.get("flagged"):
            ratio        = dt_wc / max(thr_wc, 0.001)
            finding_text = f"{nm}: ΔT {dt_wc:.2f} min — {ratio:.1f}× the {thr_wc:.2f}-min limit"
        else:
            rem          = thr_wc - dt_wc
            pct          = (dt_wc / max(thr_wc, 0.001)) * 100
            finding_text = f"All paths within limit · {nm}: {dt_wc:.2f} min ({pct:.0f}% used, {rem:.2f} left)"
    else:
        finding_text = ""

    finding_html = (
        f'<div style="font-size:10px; color:#555; padding:5px 13px 5px; '
        f'border-bottom:1px solid #f1f3f5; background:#fafbfc; '
        f'line-height:1.35; font-style:italic;">{finding_text}</div>'
    ) if finding_text else ""

    # Egress label for formula strip
    egress_str = (
        f" + {project.egress_minutes:.1f} min egress (NFPA 101)"
        if project.egress_minutes > 0 else ""
    )

    return f"""
<div class="proj-detail-card" style="display:{display}; padding:0;">

  <!-- Tier badge header -->
  <div style="background:{bg_color}; padding:11px 13px 10px;
              border-bottom:1px solid {border_color};">
    <div style="font-size:16px; font-weight:800; color:{det_color};
                letter-spacing:-0.3px;">
      {tier}
    </div>
    <div style="font-size:10px; color:{det_color}; margin-top:3px;
                font-weight:600; opacity:0.85; font-style:italic;">
      {action_label}
    </div>
    <div style="font-size:11px; color:#444; margin-top:4px; font-weight:500;">
      {project.project_name or 'Proposed Project'}
    </div>
    {f'<div style="font-size:10px; color:#666; margin-top:1px;">{project.address}</div>' if project.address else ''}
  </div>

  <!-- Controlling finding -->
  {finding_html}

  <!-- ΔT Gauge strip: Units | Gauge bar -->
  <div style="display:flex; gap:0; border-bottom:1px solid #f1f3f5; align-items:stretch;">

    <!-- Left: Units -->
    <div style="width:72px; flex-shrink:0; padding:11px 0 11px 13px;
                border-right:1px solid #f1f3f5;">
      <div style="font-size:10px; color:#adb5bd; text-transform:uppercase;
                  letter-spacing:0.4px; margin-bottom:2px;">Units</div>
      <div style="font-size:16px; font-weight:700; color:#212529;">
        {project.dwelling_units}
      </div>
    </div>

    <!-- Right: Gauge -->
    <div style="flex:1; padding:11px 14px 11px 12px; min-width:0;">

      <!-- Header row -->
      <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
        <div style="font-size:10px; color:#adb5bd; text-transform:uppercase; letter-spacing:0.4px;">
          <span title="Marginal evacuation clearance time">&Delta;T</span>
        </div>
        <div style="font-size:9px; color:#adb5bd; text-align:right; line-height:1.3;">
          Limit
          <div style="font-size:8px; color:#c8cbd0;">
            {safe_window:.0f} min &times; {max_share_v*100:.0f}%
          </div>
        </div>
      </div>

      <!-- Bar -->
      <div style="position:relative; height:12px; border-radius:6px;
                  overflow:visible; margin-top:2px; margin-bottom:5px; margin-right:10px;">
        <div style="position:absolute; left:0; top:0; width:100%; height:100%;
                    background:#d4edda; border-radius:6px;"></div>
        <div style="position:absolute; left:50%; top:0; right:0; height:100%;
                    background:#f8d7da; border-radius:0 6px 6px 0;"></div>
        <!-- Threshold tick at 50% -->
        <div style="position:absolute; left:50%; top:-2px; width:2px; height:16px;
                    background:#6c757d; z-index:4; transform:translateX(-50%);"></div>
        <!-- Indicator dot -->
        <div style="position:absolute; left:{gauge_pct:.1f}%; top:50%;
                    transform:translate(-50%,-50%); width:12px; height:12px;
                    border-radius:50%; background:{indicator_color};
                    border:2px solid white; box-shadow:0 1px 4px rgba(0,0,0,0.35);
                    z-index:5;">
        </div>
      </div>

      <!-- Numeric text -->
      <div style="font-size:9px; color:{dt_color}; font-weight:600;">
        {gauge_numtxt}
      </div>
    </div>
  </div>

  <!-- Formula strip -->
  <div style="padding:6px 13px 5px; border-bottom:1px solid #f1f3f5;
              font-size:10px; color:#868e96; display:flex; gap:14px; align-items:center;">
    <span>
      <strong style="color:#555;">{project.dwelling_units} units</strong>
      &times; 2.5 veh/unit
      &times; <span title="Evacuation rate — Zhao et al. 2022 GPS data (44M records, Kincade Fire)">{mob_pct} evac. rate</span>
      = {project.project_vehicles_peak_hour:.0f} vph{egress_str}
    </span>
    <span style="margin-left:auto; flex-shrink:0;">{hz_label}</span>
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
    """
    Minimal legend for the demo map — v3.4 ΔT Standard.

    Shows only:
      1. Project determination tier dot-key (3 items)
      2. Evacuation capacity pill toggle + gradient bar
      3. Footer
    All technical details (vph buckets, FHSZ zones, footnotes) are accessible
    via marker popups and are omitted here per city attorney / planner UX.
    """
    tier_items = (
        '<div style="display:flex; align-items:center; gap:8px; margin-bottom:5px;">'
        f'<span style="display:inline-block; width:11px; height:11px; border-radius:50%; '
        f'background:{_TIER_CSS_COLOR["DISCRETIONARY"]}; flex-shrink:0;"></span>'
        '<span style="color:#343a40;">Discretionary</span></div>'

        '<div style="display:flex; align-items:center; gap:8px; margin-bottom:5px;">'
        f'<span style="display:inline-block; width:11px; height:11px; border-radius:50%; '
        f'background:{_TIER_CSS_COLOR["MINISTERIAL WITH STANDARD CONDITIONS"]}; flex-shrink:0;"></span>'
        '<span style="color:#343a40;">Ministerial w/ Standard Conditions</span></div>'

        '<div style="display:flex; align-items:center; gap:8px; margin-bottom:2px;">'
        f'<span style="display:inline-block; width:11px; height:11px; border-radius:50%; '
        f'background:{_TIER_CSS_COLOR["MINISTERIAL"]}; flex-shrink:0;"></span>'
        '<span style="color:#343a40;">Ministerial</span></div>'
    )

    return f"""
<div id="map-legend" style="
    position: fixed;
    bottom: 26px; left: 10px;
    z-index: 9999;
    width: 195px;
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 13px 14px;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 11px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.11);
    line-height: 1.4;
">
  <!-- Evacuation capacity toggle + gradient -->
  <div>
    <div style="display:flex; align-items:center; gap:9px; margin-bottom:7px;">
      <!-- Pill toggle -->
      <input type="checkbox" id="heatmapToggle" checked style="display:none;">
      <div id="heatmapPill"
           onclick="var cb=document.getElementById('heatmapToggle'); cb.checked=!cb.checked; toggleHeatmap(cb.checked);"
           style="width:34px; height:18px; border-radius:9px; background:#27ae60;
                  position:relative; cursor:pointer; flex-shrink:0;
                  transition:background 0.2s;">
        <div id="heatmapKnob"
             style="position:absolute; width:13px; height:13px; background:white;
                    border-radius:50%; top:2.5px; left:18px;
                    transition:left 0.2s; box-shadow:0 1px 3px rgba(0,0,0,0.25);"></div>
      </div>
      <span style="font-size:11px; color:#495057; font-weight:500;">Evac. Layer</span>
    </div>
    <!-- Gradient: red (severe) → orange → yellow → gray (ample) -->
    <div style="height:7px; border-radius:4px;
                background: linear-gradient(to right, #dc3545, #fd7e14, #ffc107, #adb5bd);
                opacity:0.85;">
    </div>
    <div style="display:flex; justify-content:space-between; font-size:10px;
                color:#868e96; margin-top:3px;">
      <span>Severe</span><span>Ample</span>
    </div>
  </div>

  <div style="margin-top:10px; border-top:1px solid #f1f3f5; padding-top:8px;
              font-size:9px; color:#adb5bd;">CSF v3.4 &middot; California Stewardship Alliance</div>
</div>

<script>
(function () {{
  var MAP_NAME      = '{map_js_name}';
  var HEATMAP_NAME  = '{heatmap_js_name}';

  window.toggleHeatmap = function (visible) {{
    var pill = document.getElementById('heatmapPill');
    var knob = document.getElementById('heatmapKnob');
    if (pill) pill.style.background  = visible ? '#27ae60' : '#adb5bd';
    if (knob) knob.style.left        = visible ? '18px'   : '2px';

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


# ---------------------------------------------------------------------------
# "What Happened" historical overlay — Camp Fire retroactive annotation
# ---------------------------------------------------------------------------

def _fetch_fire_perimeter(what_happened: dict, data_dir: Path) -> dict:
    """
    Fetch and cache the Camp Fire burn perimeter GeoJSON from CAL FIRE FRAP.

    Downloads the full California fire perimeters dataset from the CNRA Open
    Data portal, filters to the target fire by FIRE_NAME + YEAR_, converts to
    EPSG:4326, and caches the result as data/{city}/fire_perimeter.geojson.
    The cache has no expiry — historical fire perimeters never change.

    First run downloads the full statewide dataset (~30–60 s). Subsequent runs
    load from cache instantly.

    Returns a GeoJSON FeatureCollection dict, or {} on failure.
    """
    cache_path = data_dir / "fire_perimeter.geojson"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except Exception:
            pass

    api_url   = what_happened.get("fire_perimeter_api", "")
    fire_name = what_happened.get("fire_perimeter_name", "")
    fire_year = int(what_happened.get("fire_perimeter_year", 2018))

    if not api_url:
        logger.warning("  fire_perimeter_api not set in city config — skipping perimeter.")
        return {}

    try:
        logger.info(
            f"  Fetching fire perimeter from ArcGIS FeatureServer "
            f"({fire_name} {fire_year}) — first run only, will be cached..."
        )
        resp = requests.get(
            api_url,
            params={
                "where": "1=1",
                "outFields": "*",
                "f": "geojson",
                "outSR": "4326",
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        features = result.get("features", [])
        if not features:
            logger.warning(f"  No features returned from {api_url}")
            return {}
        cache_path.write_text(json.dumps(result))
        logger.info(
            f"  Fire perimeter cached: {len(features)} feature(s) "
            f"({fire_name} {fire_year}) → {cache_path.name}"
        )
        return result
    except Exception as exc:
        logger.warning(f"  Fire perimeter fetch failed: {exc}")
    return {}


def _inject_what_happened_layer(
    html_path: Path,
    city_config: dict,
    data_dir: Path,
) -> None:
    """
    Inject the "What Happened" toggle layer into the saved demo map HTML.

    Adds:
      • A 🔥 "What Happened" button (top-right of map)
      • A slide-in dark panel (left) with timeline + JOSH road-diet verdict
      • Fire burn perimeter polygon (semi-transparent red)
      • Road diet Polyline annotation on Skyway (orange dashed)
      • Fire ignition point marker

    Activated by city_config.what_happened.enabled = true.
    """
    wh = city_config.get("what_happened", {})
    if not wh.get("enabled"):
        return

    perimeter  = _fetch_fire_perimeter(wh, data_dir)
    road_diet  = wh.get("road_diet", {})
    timeline   = wh.get("timeline", [])
    fire_name  = wh.get("fire_name", "Fire")
    fire_date  = wh.get("fire_date", "")
    fatalities = wh.get("fatalities", 0)
    ignition   = wh.get("ignition_point", {})

    rd_polyline      = road_diet.get("polyline", [])
    rd_label         = road_diet.get("label", "Road Diet")
    rd_before_lanes  = road_diet.get("before_lanes", 4)
    rd_after_lanes   = road_diet.get("after_lanes", 2)
    rd_before_cap    = road_diet.get("before_effective_capacity_vph", 0)
    rd_after_cap     = road_diet.get("after_effective_capacity_vph", 0)
    rd_removed       = road_diet.get("capacity_removed_vph", 0)
    rd_dt            = road_diet.get("delta_t_min", 0)
    rd_threshold     = road_diet.get("threshold_min", 0)
    rd_result        = road_diet.get("josh_result", "DISCRETIONARY")
    rd_note          = road_diet.get("josh_note", "")
    rd_desc          = road_diet.get("description", "")

    # Build timeline HTML rows
    type_icons = {
        "warning":   ("⚠", "#e67e22"),
        "dismissal": ("✗", "#c0392b"),
        "action":    ("→", "#8e44ad"),
        "fire":      ("🔥", "#e74c3c"),
        "outcome":   ("✦", "#7f8c8d"),
    }
    timeline_rows = ""
    for item in timeline:
        icon, color = type_icons.get(item.get("type", ""), ("•", "#aaa"))
        timeline_rows += f"""
        <div class="josh-wh-tl-row">
          <div class="josh-wh-tl-icon" style="color:{color}">{icon}</div>
          <div class="josh-wh-tl-body">
            <div class="josh-wh-tl-year">{item.get('year','')}</div>
            <div class="josh-wh-tl-event">{item.get('event','')}</div>
          </div>
        </div>"""

    html_panel = f"""
<div id="josh-wh-panel">
  <div class="josh-wh-hdr">
    <div>
      <div class="josh-wh-fire-name">{fire_name.upper()}</div>
      <div class="josh-wh-fire-date">{fire_date}</div>
    </div>
    <div class="josh-wh-fatalities">{fatalities}<span class="josh-wh-killed">killed</span></div>
    <button class="josh-wh-close" onclick="joshWH.hide()">✕</button>
  </div>
  <div class="josh-wh-body">

    <div class="josh-wh-section-label">HOW WE GOT HERE</div>
    <div class="josh-wh-timeline">{timeline_rows}</div>

    <div class="josh-wh-section-label" style="margin-top:18px">WHAT JOSH WOULD HAVE SAID</div>
    <div class="josh-wh-verdict">
      <div class="josh-wh-vd-title">{rd_label}</div>
      <div class="josh-wh-vd-desc">{rd_desc}</div>
      <table class="josh-wh-vd-table">
        <tr>
          <td>Before ({rd_before_lanes} lanes)</td>
          <td class="josh-wh-vd-val">{rd_before_cap:,} vph effective</td>
        </tr>
        <tr>
          <td>After ({rd_after_lanes} lanes)</td>
          <td class="josh-wh-vd-val">{rd_after_cap:,} vph effective</td>
        </tr>
        <tr class="josh-wh-vd-sep">
          <td>Capacity removed</td>
          <td class="josh-wh-vd-val">{rd_removed:,} vph</td>
        </tr>
        <tr class="josh-wh-vd-highlight">
          <td>ΔT impact</td>
          <td class="josh-wh-vd-val">{rd_dt} min</td>
        </tr>
        <tr>
          <td>VHFHSZ threshold</td>
          <td class="josh-wh-vd-val">{rd_threshold} min</td>
        </tr>
      </table>
      <div class="josh-wh-vd-badge">▶ {rd_result}</div>
      <div class="josh-wh-vd-note">{rd_note}</div>
    </div>

    <div class="josh-wh-attribution">
      Sources: NIST TN 2252 (NETTRA) · Butte County Grand Jury 2008–2009
      · CAL FIRE FRAP · Cal OES After Action Report
    </div>
  </div>
</div>

<button id="josh-wh-btn" onclick="joshWH.toggle()" title="Show Camp Fire context">
  🔥 What Happened
</button>
"""

    css = """
<style id="josh-wh-css">
#josh-wh-panel {
  display: none;
  position: fixed;
  top: 60px; left: 10px; bottom: 10px;
  width: 340px;
  background: rgba(18,18,20,0.96);
  color: #f0ece4;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.55);
  z-index: 9500;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 12px;
}
#josh-wh-panel.josh-wh-hidden { display: none !important; }
.josh-wh-hdr {
  background: #8B1A1A;
  padding: 14px 16px 12px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-shrink: 0;
}
.josh-wh-fire-name {
  font-size: 15px; font-weight: 700; letter-spacing: .08em;
  color: #fff;
}
.josh-wh-fire-date { font-size: 11px; color: rgba(255,255,255,.7); margin-top: 2px; }
.josh-wh-fatalities {
  font-size: 26px; font-weight: 700; color: #fff; line-height: 1;
  text-align: right;
}
.josh-wh-killed { display: block; font-size: 10px; font-weight: 400; color: rgba(255,255,255,.65); letter-spacing: .05em; }
.josh-wh-close {
  background: none; border: none; color: rgba(255,255,255,.6);
  font-size: 16px; cursor: pointer; padding: 0 0 0 10px; line-height: 1;
  flex-shrink: 0; align-self: flex-start;
}
.josh-wh-close:hover { color: #fff; }
.josh-wh-body {
  overflow-y: auto; padding: 14px 16px 16px; flex: 1;
}
.josh-wh-section-label {
  font-size: 9px; letter-spacing: .18em; color: #E85D04;
  font-weight: 700; margin-bottom: 10px;
}
.josh-wh-timeline { display: flex; flex-direction: column; gap: 8px; }
.josh-wh-tl-row { display: flex; gap: 9px; align-items: flex-start; }
.josh-wh-tl-icon { font-size: 13px; flex-shrink: 0; width: 16px; text-align: center; margin-top: 1px; }
.josh-wh-tl-body { flex: 1; }
.josh-wh-tl-year { font-size: 10px; color: #E85D04; font-weight: 600; margin-bottom: 1px; }
.josh-wh-tl-event { font-size: 11px; color: #d8d2c8; line-height: 1.4; }
.josh-wh-verdict {
  background: rgba(255,255,255,.05);
  border-left: 3px solid #E85D04;
  border-radius: 4px;
  padding: 12px 12px 10px;
}
.josh-wh-vd-title { font-size: 12px; font-weight: 700; color: #fff; margin-bottom: 4px; }
.josh-wh-vd-desc { font-size: 11px; color: #a09890; line-height: 1.4; margin-bottom: 10px; }
.josh-wh-vd-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
.josh-wh-vd-table td { padding: 3px 0; font-size: 11px; color: #c8c0b4; }
.josh-wh-vd-table td.josh-wh-vd-val { text-align: right; color: #f0ece4; }
.josh-wh-vd-sep td { border-top: 1px solid rgba(255,255,255,.1); padding-top: 6px; }
.josh-wh-vd-highlight td { color: #E85D04 !important; font-weight: 700; font-size: 12px; }
.josh-wh-vd-badge {
  background: #8B1A1A; color: #fff;
  font-size: 11px; font-weight: 700; letter-spacing: .06em;
  padding: 5px 10px; border-radius: 4px;
  display: inline-block; margin-bottom: 8px;
}
.josh-wh-vd-note { font-size: 10px; color: #888; line-height: 1.5; }
.josh-wh-attribution {
  margin-top: 16px; font-size: 9px; color: #555;
  line-height: 1.5; border-top: 1px solid rgba(255,255,255,.08);
  padding-top: 10px;
}
#josh-wh-btn {
  position: fixed;
  top: 80px; right: 328px;
  z-index: 9400;
  background: #8B1A1A;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 600;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.4);
  letter-spacing: .03em;
  transition: background .15s;
}
#josh-wh-btn:hover { background: #a52020; }
#josh-wh-btn.active { background: #5a0f0f; }
</style>
"""

    js = f"""
<script id="josh-wh-script">
(function() {{
  var PERIMETER   = {json.dumps(perimeter,       separators=(',',':'))};
  var RD_COORDS   = {json.dumps(rd_polyline,     separators=(',',':'))};
  var IGNITION    = {json.dumps(ignition,         separators=(',',':'))};
  var _visible    = false;
  var _layers     = [];

  function _getMap() {{
    for (var k in window) {{
      try {{
        if (window[k] && window[k]._leaflet_id && window[k].getCenter) return window[k];
      }} catch(e) {{}}
    }}
    return null;
  }}

  function _buildLayers(map) {{
    // 1. Burn perimeter
    if (PERIMETER && PERIMETER.features && PERIMETER.features.length) {{
      var perimLayer = L.geoJSON(PERIMETER, {{
        style: function() {{
          return {{
            color: '#8B1A1A', weight: 2, opacity: 0.85,
            fillColor: '#c0392b', fillOpacity: 0.18,
          }};
        }},
      }}).bindPopup(
        '<div style="font-family:system-ui;font-size:12px;line-height:1.5">'
        + '<b style="color:#8B1A1A">Camp Fire Burn Perimeter</b><br>'
        + 'November 8, 2018 · 153,336 acres<br>'
        + '<span style="color:#888">Source: CAL FIRE FRAP</span>'
        + '</div>'
      );
      _layers.push(perimLayer);
    }}

    // 2. Road diet annotation on Skyway
    if (RD_COORDS && RD_COORDS.length > 1) {{
      var rdLayer = L.polyline(RD_COORDS, {{
        color: '#E85D04', weight: 7, opacity: 0.9,
        dashArray: '12 6',
        lineCap: 'round',
      }}).bindPopup(
        '<div style="font-family:system-ui;font-size:12px;line-height:1.6;max-width:280px">'
        + '<b style="color:#E85D04">Skyway Road Diet (~2014)</b><br>'
        + 'Narrowed from <b>4 travel lanes → 2 lanes</b><br>'
        + '<br>'
        + '<b style="color:#8B1A1A">2008:</b> Grand Jury recommended <em>widening</em> Skyway<br>'
        + '<b style="color:#8B1A1A">2009:</b> County dismissed recommendations<br>'
        + '<b style="color:#8B1A1A">~2014:</b> Town narrowed it anyway<br>'
        + '<br>'
        + '<table style="width:100%;font-size:11px;border-collapse:collapse">'
        + '<tr><td>Before (4 lanes)</td><td style="text-align:right"><b>665 vph</b> effective</td></tr>'
        + '<tr><td>After (2 lanes)</td><td style="text-align:right"><b>551 vph</b> effective</td></tr>'
        + '<tr style="border-top:1px solid #eee"><td>ΔT impact</td>'
        + '<td style="text-align:right;color:#E85D04"><b>12.4 min</b> vs 2.25 min threshold</td></tr>'
        + '</table>'
        + '<div style="margin-top:8px;background:#8B1A1A;color:#fff;padding:4px 8px;'
        + 'border-radius:3px;font-size:11px;font-weight:700;display:inline-block">'
        + '▶ DISCRETIONARY under JOSH</div>'
        + '</div>',
        {{ maxWidth: 300 }}
      );
      _layers.push(rdLayer);
    }}

    // 3. Ignition point
    if (IGNITION && IGNITION.lat && IGNITION.lon) {{
      var igIcon = L.divIcon({{
        html: '<div style="font-size:22px;line-height:1;filter:drop-shadow(0 1px 3px rgba(0,0,0,.5))">🔥</div>',
        className: '',
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      }});
      var igLayer = L.marker([IGNITION.lat, IGNITION.lon], {{ icon: igIcon }})
        .bindPopup(
          '<div style="font-family:system-ui;font-size:12px;line-height:1.5">'
          + '<b>🔥 Camp Fire Ignition Point</b><br>'
          + (IGNITION.label || '') + '<br>'
          + '<span style="color:#888;font-size:11px">Camp Creek Rd / Poe Dam, Pulga CA</span>'
          + '</div>'
        );
      _layers.push(igLayer);
    }}
  }}

  function _show() {{
    var map = _getMap();
    if (!map) return;
    if (_layers.length === 0) _buildLayers(map);
    _layers.forEach(function(l) {{ if (!map.hasLayer(l)) l.addTo(map); }});
    document.getElementById('josh-wh-panel').classList.remove('josh-wh-hidden');
    document.getElementById('josh-wh-btn').classList.add('active');
    _visible = true;
  }}

  function _hide() {{
    var map = _getMap();
    if (map) _layers.forEach(function(l) {{ if (map.hasLayer(l)) map.removeLayer(l); }});
    document.getElementById('josh-wh-panel').classList.add('josh-wh-hidden');
    document.getElementById('josh-wh-btn').classList.remove('active');
    _visible = false;
  }}

  window.joshWH = {{
    toggle: function() {{ _visible ? _hide() : _show(); }},
    hide:   _hide,
    show:   _show,
  }};

  // Start hidden — panel has display:flex by default in CSS so we need to
  // immediately add the hidden class once DOM is ready.
  document.addEventListener('DOMContentLoaded', function() {{
    var panel = document.getElementById('josh-wh-panel');
    if (panel) panel.classList.add('josh-wh-hidden');
  }});
}})();
</script>
"""

    injection = css + "\n" + html_panel + "\n" + js
    html = html_path.read_text(encoding="utf-8")
    # Use rfind to target the real page </body>, not one embedded inside
    # the _BRIEFS JS string blob added by _inject_brief_modals.
    idx = html.rfind("</body>")
    if idx == -1:
        html += injection
    else:
        html = html[:idx] + injection + "\n</body>" + html[idx + len("</body>"):]
    html_path.write_text(html, encoding="utf-8")
    logger.info("  'What Happened' layer injected into demo map.")

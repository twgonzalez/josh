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
) -> folium.FeatureGroup:
    """
    Build a FeatureGroup containing all evacuation route segments colored by
    effective_capacity_vph using the _EFFECTIVE_CAPACITY_RAMP scale.

    v3.0 ΔT Standard: low effective capacity (bottleneck danger) = red/prominent;
    high effective capacity (ample headroom) = gray/subdued.

    Coloring is inverted vs. v2.0 v/c ramp: the map now highlights constrained
    roads (potential evacuation bottlenecks) rather than congested roads.

    Add to the map BEFORE per-project layers so per-project flagged routes
    render on top.
    """
    fg = folium.FeatureGroup(name="Evacuation Capacity", show=True)

    if "is_evacuation_route" not in roads_gdf.columns:
        logger.warning("Heatmap: missing is_evacuation_route column — skipping.")
        return fg

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

    for _, row in evac_routes.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue

        # Primary metric: effective_capacity_vph (HCM × hazard degradation factor)
        hcm_cap   = float(row.get("capacity_vph", 1) or 1)
        if has_eff_cap:
            eff_cap = float(row.get("effective_capacity_vph", hcm_cap) or hcm_cap)
        else:
            eff_cap = hcm_cap

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
    evacuation_paths: list | None = None,
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

        # Serving routes (wildland — one GeoJson per segment for popup support)
        if serving_set and "osmid" in roads_wgs84.columns:
            serving_mask   = roads_wgs84["osmid"].apply(
                lambda o: _osmid_matches(o, serving_set)
            )
            serving_subset = roads_wgs84[serving_mask]

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

                # v3.0: effective capacity and hazard zone
                hcm_cap    = float(row.get("capacity_vph", 1) or 1)
                eff_cap    = float(row.get("effective_capacity_vph", hcm_cap) or hcm_cap)
                fhsz_zone  = str(row.get("fhsz_zone", "non_fhsz") or "non_fhsz")
                hazard_deg = float(row.get("hazard_degradation", 1.0) or 1.0)
                road_type_s  = str(row.get("road_type", "") or "")
                lane_count_s = int(row.get("lane_count", 0) or 0)
                speed_lim_s  = int(row.get("speed_limit", 0) or 0)

                # Look up ΔT result for this bottleneck segment (if any)
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

                folium.GeoJson(
                    mapping(row.geometry),
                    style_function=lambda _, c=seg_color, w=weight, o=opacity: {
                        "color": c, "weight": w, "opacity": o,
                    },
                    popup=folium.Popup(popup_html, max_width=360),
                    tooltip=tip,
                ).add_to(proj_group)

        # ── Controlling bottleneck ⚠ icon (static — always visible when project selected) ──
        # SVG warning triangle (yellow fill, black stroke) at the midpoint of the
        # worst-ΔT bottleneck segment. Shown/hidden with the FeatureGroup automatically.
        # Bug fix: roads osmid column stores list values as strings like "[123, 456]",
        # so use str.contains() instead of _osmid_matches() for reliable lookup.
        if (tier != "MINISTERIAL"
                and ctrl_osmid
                and "osmid" in roads_wgs84.columns):
            ctrl_mask = roads_wgs84["osmid"].astype(str).str.contains(
                ctrl_osmid, regex=False
            )
            ctrl_rows = roads_wgs84[ctrl_mask]
            if not ctrl_rows.empty:
                ctrl_geom = ctrl_rows.iloc[0].geometry
                if ctrl_geom is not None and not ctrl_geom.is_empty:
                    try:
                        mid = ctrl_geom.interpolate(0.5, normalized=True)
                    except Exception:
                        mid = ctrl_geom.centroid
                    icon_html = (
                        '<div style="width:22px;height:20px;">'
                        '<svg viewBox="0 0 22 20" width="22" height="20"'
                        ' xmlns="http://www.w3.org/2000/svg">'
                        '<polygon points="11,2 21,19 1,19"'
                        ' fill="#FFD700" stroke="black" stroke-width="1.5"'
                        ' stroke-linejoin="round"/>'
                        '<text x="11" y="16" text-anchor="middle"'
                        ' font-size="11" font-family="sans-serif"'
                        ' font-weight="bold" fill="black">!</text>'
                        '</svg></div>'
                    )
                    folium.Marker(
                        location=[mid.y, mid.x],
                        icon=folium.DivIcon(
                            html=icon_html,
                            icon_size=(22, 20),
                            icon_anchor=(11, 10),
                        ),
                        tooltip="Controlling bottleneck segment",
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
    Minimal legend for the demo map — v3.2 ΔT Standard.

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
    bottom: 26px; right: 10px;
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
              font-size:9px; color:#adb5bd;">CSF v3.2 &middot; California Stewardship Alliance</div>
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

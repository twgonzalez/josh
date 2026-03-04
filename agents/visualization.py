"""
Agent 6: Visualization

Generates interactive Folium maps for project evaluations.

Map layers:
- City boundary
- FHSZ fire hazard zones (colored by class)
- Road network (all roads, colored by LOS)
- Evacuation routes (highlighted)
- Serving routes for the project (highlighted differently)
- Project location marker
- 0.5-mile search buffer
"""
import logging
from pathlib import Path

import folium
import geopandas as gpd
from shapely.geometry import Point, mapping

from models.project import Project

logger = logging.getLogger(__name__)

# LOS color scale (green → yellow → orange → red)
LOS_COLORS = {
    "A": "#2ca02c",   # green
    "B": "#98df8a",   # light green
    "C": "#ffbb78",   # light orange
    "D": "#ff7f0e",   # orange
    "E": "#d62728",   # red
    "F": "#8c0000",   # dark red
}

FHSZ_COLORS = {
    1: "#ffeda0",  # Moderate — yellow
    2: "#fc8d59",  # High — orange
    3: "#d7301f",  # Very High — red
}

FHSZ_LABELS = {
    1: "Zone 1 (Moderate)",
    2: "Zone 2 (High)",
    3: "Zone 3 (Very High)",
}


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

    # Center map on the project
    m = folium.Map(
        location=[lat, lon],
        zoom_start=14,
        tiles="OpenStreetMap",
    )

    # --- Layer: City Boundary ---
    boundary_layer = folium.FeatureGroup(name="City Boundary", show=True)
    boundary_wgs84 = boundary_gdf.to_crs("EPSG:4326")
    for _, row in boundary_wgs84.iterrows():
        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _: {
                "fillColor": "none",
                "color": "#1f77b4",
                "weight": 2,
                "dashArray": "6 4",
                "fillOpacity": 0,
            },
            tooltip="City Boundary",
        ).add_to(boundary_layer)
    boundary_layer.add_to(m)

    # --- Layer: FHSZ Zones ---
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
                    "fillOpacity": 0.35,
                },
                tooltip=label,
            ).add_to(fhsz_layer)
    fhsz_layer.add_to(m)

    # --- Layer: All Roads (colored by LOS) ---
    all_roads_layer = folium.FeatureGroup(name="Road Network (LOS)", show=False)
    roads_wgs84 = roads_gdf.to_crs("EPSG:4326")
    if "los" in roads_wgs84.columns:
        for _, row in roads_wgs84.iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            los = str(row.get("los", "C"))
            color = LOS_COLORS.get(los, "#7f7f7f")
            name_str = str(row.get("name", "Unnamed road") or "Unnamed road")
            vc = row.get("vc_ratio", 0)
            cap = row.get("capacity_vph", 0)
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _, c=color: {
                    "color": c,
                    "weight": 2,
                    "opacity": 0.6,
                },
                tooltip=f"{name_str} | LOS {los} | v/c={vc:.2f} | cap={cap:.0f}vph",
            ).add_to(all_roads_layer)
    all_roads_layer.add_to(m)

    # --- Layer: Evacuation Routes ---
    evac_layer = folium.FeatureGroup(name="Evacuation Routes", show=True)
    evac_routes = roads_wgs84[roads_wgs84.get("is_evacuation_route", False) == True]
    for _, row in evac_routes.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        los = str(row.get("los", "C"))
        color = LOS_COLORS.get(los, "#7f7f7f")
        name_str = str(row.get("name", "Unnamed") or "Unnamed")
        vc = row.get("vc_ratio", 0)
        conn = row.get("connectivity_score", 0)
        folium.GeoJson(
            mapping(row.geometry),
            style_function=lambda _, c=color: {
                "color": c,
                "weight": 4,
                "opacity": 0.9,
            },
            tooltip=f"[EVAC] {name_str} | LOS {los} | v/c={vc:.2f} | connectivity={conn}",
        ).add_to(evac_layer)
    evac_layer.add_to(m)

    # --- Layer: Serving Routes (within 0.5 mi of project) ---
    serving_layer = folium.FeatureGroup(name="Serving Routes (project area)", show=True)
    serving_ids = set(project.serving_route_ids or [])
    if serving_ids and "is_evacuation_route" in roads_wgs84.columns:
        serving_routes = roads_wgs84[roads_wgs84.index.isin(serving_ids)]
        for _, row in serving_routes.iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            name_str = str(row.get("name", "Unnamed") or "Unnamed")
            vc = row.get("vc_ratio", 0)
            los = str(row.get("los", "C"))
            cap = row.get("capacity_vph", 0)
            folium.GeoJson(
                mapping(row.geometry),
                style_function=lambda _: {
                    "color": "#9467bd",   # purple = serving routes
                    "weight": 5,
                    "opacity": 1.0,
                },
                tooltip=f"[SERVING] {name_str} | LOS {los} | v/c={vc:.2f} | cap={cap:.0f}vph",
            ).add_to(serving_layer)
    serving_layer.add_to(m)

    # --- Layer: 0.5-mile Search Buffer ---
    radius_miles = config.get("evacuation_route_radius_miles", 0.5)
    radius_meters = radius_miles * 1609.34
    buffer_layer = folium.FeatureGroup(name=f"{radius_miles}-mile Search Radius", show=True)
    folium.Circle(
        location=[lat, lon],
        radius=radius_meters,
        color="#7f7f7f",
        weight=1.5,
        fill=True,
        fill_color="#c7c7c7",
        fill_opacity=0.08,
        dash_array="8 4",
        tooltip=f"Evacuation route search radius ({radius_miles} mi)",
    ).add_to(buffer_layer)
    buffer_layer.add_to(m)

    # --- Layer: Project Marker ---
    det = project.determination or "UNKNOWN"
    marker_color = "red" if det == "DISCRETIONARY" else "green"
    std1 = "YES" if project.in_fire_zone else "NO"
    std2 = "YES" if project.meets_size_threshold else "NO"
    std4 = "YES" if project.exceeds_capacity_threshold else "NO"

    popup_html = f"""
    <div style="font-family: monospace; font-size: 12px; min-width: 220px;">
      <b style="font-size: 14px; color: {'#d62728' if det == 'DISCRETIONARY' else '#2ca02c'}">
        {det}
      </b><br><br>
      <b>Location:</b> {lat:.4f}, {lon:.4f}<br>
      <b>Units:</b> {project.dwelling_units}<br>
      <b>Name:</b> {project.project_name or '—'}<br><br>
      <b>Standard 1 (Fire Zone):</b> {std1}<br>
      <b>Standard 2 (Size):</b> {std2}<br>
      <b>Standard 4 (Capacity):</b> {std4}<br><br>
      <b>Serving Routes:</b> {len(serving_ids)}<br>
      <b>Peak Vehicles:</b> {project.project_vehicles_peak_hour:.0f} vph
    </div>
    """

    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"Project: {det}",
        icon=folium.Icon(
            color=marker_color,
            icon="home",
            prefix="fa",
        ),
    ).add_to(m)

    # --- Legend ---
    legend_html = _build_legend_html(project, config)
    m.get_root().html.add_child(folium.Element(legend_html))

    # --- Layer Control ---
    folium.LayerControl(collapsed=False).add_to(m)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    logger.info(f"Map saved: {output_path}")
    return output_path


def _to_int_safe(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _build_legend_html(project: Project, config: dict) -> str:
    vc_threshold = config.get("vc_threshold", 0.80)
    det = project.determination or "UNKNOWN"
    det_color = "#d62728" if det == "DISCRETIONARY" else "#2ca02c"

    los_items = "".join(
        f'<div><span style="display:inline-block;width:16px;height:6px;background:{c};margin-right:6px;"></span>{grade}</div>'
        for grade, c in LOS_COLORS.items()
    )
    fhsz_items = "".join(
        f'<div><span style="display:inline-block;width:14px;height:14px;background:{c};opacity:0.6;margin-right:6px;border:1px solid #aaa;"></span>{label}</div>'
        for zone, (c, label) in {k: (FHSZ_COLORS[k], FHSZ_LABELS[k]) for k in FHSZ_COLORS}.items()
    )

    return f"""
    <div style="
        position: fixed;
        bottom: 30px; right: 10px;
        background: white;
        border: 1px solid #ccc;
        border-radius: 6px;
        padding: 12px 16px;
        font-family: monospace;
        font-size: 12px;
        z-index: 9999;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.15);
        min-width: 180px;
    ">
      <b style="font-size:13px;">Determination</b><br>
      <span style="color:{det_color}; font-weight:bold; font-size:14px;">{det}</span>
      <hr style="margin:8px 0;">
      <b>LOS (v/c ratio)</b>
      {los_items}
      <div style="margin-top:4px; color:#666; font-size:11px;">threshold: {vc_threshold:.2f}</div>
      <hr style="margin:8px 0;">
      <b>FHSZ Zones</b>
      {fhsz_items}
      <hr style="margin:8px 0;">
      <div><span style="display:inline-block;width:30px;height:4px;background:#9467bd;margin-right:6px;"></span>Serving routes</div>
      <div><span style="display:inline-block;width:30px;height:4px;background:#1f77b4;margin-right:6px;border-top:2px dashed #1f77b4;border-bottom:none;background:none;"></span>City boundary</div>
      <div style="margin-top:6px; color:#888; font-size:10px;">Fire Evac Capacity Analysis</div>
    </div>
    """

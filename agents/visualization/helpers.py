# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Shared utility functions used by both evaluation and demo maps.

Imports from themes only.
"""
import folium

from .themes import _HIGHWAY_WEIGHT, _HIGHWAY_WEIGHT_DEFAULT, _VC_WEIGHT_MULTIPLIER


# ---------------------------------------------------------------------------
# OSMid matching
# ---------------------------------------------------------------------------

def _brief_filename(lat: float, lon: float, units: int) -> str:
    """Return the filename (not path) of the determination brief for a project."""
    lat_str = f"{lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{lon:.4f}".replace(".", "_").replace("-", "n")
    return f"brief_v3_{lat_str}_{lon_str}_{units}u.html"


def _osmid_set(ids) -> set:
    """
    Flatten a list of osmids (each may be an int, string, or list) into a flat
    set that includes both raw and string representations.
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


def _to_int_safe(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Highway weight helpers
# ---------------------------------------------------------------------------

def _highway_weight(highway_val) -> float:
    """Return a line weight for an OSM highway value (which may be a list)."""
    if isinstance(highway_val, list):
        highway_val = highway_val[0] if highway_val else ""
    return _HIGHWAY_WEIGHT.get(str(highway_val or ""), _HIGHWAY_WEIGHT_DEFAULT)


def _traffic_weight(highway_val, vc_color: str) -> float:
    """
    Combine road-class base weight with a v/c congestion multiplier.
    Result is rounded to 0.5 px increments to keep (color, weight) bucket
    count low while still showing clear width differences.
    """
    base = _highway_weight(highway_val)
    mult = _VC_WEIGHT_MULTIPLIER.get(vc_color, 1.0)
    raw  = base * mult
    return round(raw * 2) / 2


# ---------------------------------------------------------------------------
# Zoom weight scaler (JS injection)
# ---------------------------------------------------------------------------

def _add_zoom_weight_scaler(m: "folium.Map", ref_zoom: int) -> None:
    """
    Inject JavaScript that scales all Leaflet path line weights proportionally
    as the user zooms in/out.

    At ref_zoom the weights equal their static (Python-side) values.
    Each zoom level above ref_zoom multiplies weights by 2**0.65 ≈ 1.57×.
    Weights are clamped to [0.3, 30] px.
    """
    map_var = m.get_name()
    js = f"""<script>
(function () {{
  function eachPath(layer, cb) {{
    if (layer && layer._layers) {{
      Object.values(layer._layers).forEach(function (sub) {{ eachPath(sub, cb); }});
    }} else if (layer && (layer._path ||
                          (layer.options && layer.options.weight !== undefined &&
                           typeof layer.setStyle === 'function'))) {{
      cb(layer);
    }}
  }}

  function applyScale(map, scale) {{
    map.eachLayer(function (layer) {{
      eachPath(layer, function (path) {{
        if (path._baseWeight === undefined) {{
          path._baseWeight = (path.options && path.options.weight) || 1;
        }}
        var w = Math.max(0.3, Math.min(path._baseWeight * scale, 30));
        path.setStyle({{ weight: w }});
      }});
    }});
  }}

  function getScale(zoom) {{
    var s = Math.pow(2, (zoom - {ref_zoom}) * 0.65);
    return Math.max(0.2, Math.min(s, 12));
  }}

  function init() {{
    var map = window['{map_var}'];
    if (!map) {{ setTimeout(init, 50); return; }}

    var _scaleTimer = null;
    map.on('zoomend', function () {{
      clearTimeout(_scaleTimer);
      _scaleTimer = setTimeout(function () {{
        applyScale(map, getScale(map.getZoom()));
      }}, 80);
    }});

    applyScale(map, getScale(map.getZoom()));
  }}

  if (document.readyState === 'complete') {{
    init();
  }} else {{
    window.addEventListener('load', init);
  }}
}})();
</script>"""
    m.get_root().html.add_child(folium.Element(js))


# ---------------------------------------------------------------------------
# Global Leaflet CSS overrides
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

  /* ---- Push top Leaflet controls below the JOSH brand header ---- */
  .leaflet-top {
    top: 58px !important;
  }
</style>
"""

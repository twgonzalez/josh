# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Browser Data Bundle Exporter (Phase 1 — feat/whatif-browser)

Generates the three static files needed by the client-side what-if engine:

  output/{city}/graph.json        — compact road graph with pre-resolved capacity data
  output/{city}/parameters.json   — flattened runtime parameters for JS consumption
  output/{city}/test_vectors.json — Python-authoritative evaluation results for the
                                    anti-divergence test suite (tests/test_whatif_engine.js)

All capacity values (eff_cap_vph, fhsz_zone, hazard_degradation) are pre-resolved in
Python so the JS engine has zero HCM lookup logic to implement.  Routing speed is taken
from speed_defaults[highway_type] exactly as wildland.py does — not from the OSM maxspeed
tag — ensuring identical travel_time_s in both the Python and JS Dijkstra.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_PARAMETERS_VERSION = "3.4"
_MPH_TO_MPS = 0.44704  # exact, same constant used in wildland.py

# ---------------------------------------------------------------------------
# Algorithm-critical JS strings (co-generated alongside Python source)
#
# Each constant mirrors the Python function(s) cited in its header comment.
# When the Python algorithm changes in a way that affects the JS payload,
# update the corresponding constant HERE — in the same file, same PR.
#
# The generator export_whatif_engine_js() reads static/whatif_utils.js
# (drift-free utilities) and concatenates these blocks inside a JS IIFE,
# writing the result to static/whatif_engine.js.
#
# IIFE layout of the generated file:
#   [HEADER]  — generated notice, JSDoc, IIFE open, module state
#   [INIT]    — init(), _ensureReady()
#   [UTILS]   — verbatim content of static/whatif_utils.js
#   [CLASSIFY_FHSZ]
#   [DIJKSTRA]
#   [IDENTIFY_SERVING_PATHS]
#   [COMPUTE_DELTA_T]
#   [DETERMINE_TIER]
#   [EVALUATE_PROJECT]
#   [EXPORTS]  — return statement + CommonJS export
# ---------------------------------------------------------------------------

# ── IIFE header + module state ────────────────────────────────────────────────
_JS_IIFE_HEADER = """\
// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

// ============================================================================
// GENERATED FILE — DO NOT EDIT
// Source:   agents/export.py  (algorithm JS strings)
//           static/whatif_utils.js  (drift-free utilities)
// Regenerate:  uv run python main.py analyze --city "Berkeley"
// ============================================================================

/**
 * JOSH What-If Evaluation Engine (feat/whatif-browser)
 *
 * Pure JavaScript implementation of the JOSH v3.4 ΔT evacuation clearance
 * algorithm.  Mirrors agents/scenarios/wildland.py + agents/scenarios/base.py
 * exactly — same Dijkstra weights, same deduplication logic, same ΔT formula.
 *
 * The algorithm sections of this file are defined as Python string constants
 * in agents/export.py, directly adjacent to the Python source they mirror.
 * Utility functions (MinHeap, haversine, etc.) live in static/whatif_utils.js
 * and contain no algorithm constants — they cannot drift from Python.
 *
 * Entry point:  WhatIfEngine.evaluateProject(lat, lon, units, stories)
 * No external dependencies.  Works from file:// (all data inlined into HTML).
 */

const WhatIfEngine = (() => {
  // ── Module-level state (initialised once from globals) ─────────────────────
  let _graph     = null;   // parsed graph.json
  let _params    = null;   // parsed parameters.json
  let _fhsz      = null;   // parsed fhsz GeoJSON FeatureCollection
  let _adjacency = null;   // Map<nodeId, [{v, osmid, len_m, speed_mph, ...}]>
  let _nodeMap   = null;   // Map<nodeId, {lon, lat}>
  let _exitSet   = null;   // Set<nodeId>
  let _ready     = false;

  // MPH → m/s conversion — exact, matches wildland.py _MPH_TO_MPS
  const MPH_TO_MPS    = 0.44704;
  const EARTH_RADIUS_M = 6_371_000;

"""

# ── Init + _ensureReady ───────────────────────────────────────────────────────
_JS_INIT = """\
  // ── Init ─────────────────────────────────────────────────────────────────────

  /**
   * Initialise the engine from the three global data objects.
   * Called automatically on first evaluateProject() call, or explicitly by tests.
   */
  function init(graph, params, fhsz) {
    _graph = graph;
    _params = params;
    _fhsz = fhsz;
    _nodeMap = new Map();
    for (const n of _graph.nodes) {
      _nodeMap.set(n.id, { lon: n.lon, lat: n.lat });
    }
    _adjacency = _buildAdjacency(_graph.edges);
    _exitSet = new Set(_graph.exit_nodes);
    _ready = true;
  }

  function _ensureReady() {
    if (!_ready) {
      if (typeof JOSH_GRAPH !== "undefined" &&
          typeof JOSH_PARAMS !== "undefined" &&
          typeof JOSH_FHSZ   !== "undefined") {
        init(JOSH_GRAPH, JOSH_PARAMS, JOSH_FHSZ);
      } else {
        throw new Error("WhatIfEngine: JOSH_GRAPH / JOSH_PARAMS / JOSH_FHSZ not loaded");
      }
    }
  }

"""

# ── FHSZ classification ───────────────────────────────────────────────────────
# Mirrors: agents/scenarios/wildland.py _classify_fhsz_zone()
# Algorithm constants encoded here: HAZ_CLASS threshold values (3 → vhfhsz,
# 2 → high_fhsz, 1 → moderate_fhsz).  If CAL FIRE changes HAZ_CLASS encoding,
# update BOTH this constant AND wildland.py _classify_fhsz_zone().
_JS_CLASSIFY_FHSZ = """\
  // ── FHSZ classification ───────────────────────────────────────────────────────
  // Mirrors: agents/scenarios/wildland.py _classify_fhsz_zone()
  // HAZ_CLASS thresholds: 3 → vhfhsz, 2 → high_fhsz, 1 → moderate_fhsz.

  /**
   * Return "vhfhsz" | "high_fhsz" | "moderate_fhsz" | "non_fhsz".
   * Iterates FHSZ features sorted by HAZ_CLASS descending — most severe zone wins.
   */
  function classifyFhsz(lat, lon) {
    if (!_fhsz || !_fhsz.features) return "non_fhsz";
    const sorted = [..._fhsz.features].sort(
      (a, b) => (b.properties?.HAZ_CLASS ?? 0) - (a.properties?.HAZ_CLASS ?? 0)
    );
    for (const feat of sorted) {
      if (_pointInFeature(lon, lat, feat)) {
        const haz = feat.properties?.HAZ_CLASS ?? 0;
        if (haz >= 3) return "vhfhsz";
        if (haz === 2) return "high_fhsz";
        if (haz === 1) return "moderate_fhsz";
      }
    }
    return "non_fhsz";
  }

"""

# ── Full Dijkstra from origin ─────────────────────────────────────────────────
# Mirrors: agents/scenarios/wildland.py Pass 1 Dijkstra
#   weight = travel_time_s = length / (speed_mph × MPH_TO_MPS)
# Algorithm constant: MPH_TO_MPS = 0.44704.  Speed comes from graph.json
# (pre-resolved from speed_defaults[highway_type] by export_graph_json —
# NOT from OSM maxspeed), matching wildland.py exactly.
_JS_DIJKSTRA = """\
  // ── Full Dijkstra from origin ─────────────────────────────────────────────────
  // Mirrors: agents/scenarios/wildland.py Pass 1 Dijkstra
  // Weight: travel_time_s = len_m / (speed_mph × MPH_TO_MPS).
  // Speed is from graph.json speed_defaults — NOT OSM maxspeed — matching wildland.py.

  /**
   * Run Dijkstra from startNode to all reachable exit nodes, weighted by
   * travel_time_s.  Returns Map<exitNodeId, {cost_s, path_edges, path_nodes, path_coords}>.
   */
  function _dijkstraFromOrigin(startNode) {
    const INF = Infinity;
    const dist = new Map([[startNode, 0]]);
    const prev = new Map();   // nodeId → {from: nodeId, edge: edgeAttrs}
    const heap = new MinHeap();
    heap.push(0, startNode);

    while (heap.size > 0) {
      const [cost, u] = heap.pop();
      if (cost > (dist.get(u) ?? INF)) continue;
      for (const edge of (_adjacency.get(u) ?? [])) {
        const spd_mps = edge.speed_mph * MPH_TO_MPS;
        const tt      = spd_mps > 0 ? edge.len_m / spd_mps : edge.len_m;
        const newCost = cost + tt;
        if (newCost < (dist.get(edge.v) ?? INF)) {
          dist.set(edge.v, newCost);
          prev.set(edge.v, { from: u, edge });
          heap.push(newCost, edge.v);
        }
      }
    }

    // Reconstruct paths for all reachable exit nodes
    const results = new Map();
    for (const exitNode of _exitSet) {
      if (!dist.has(exitNode)) continue;
      const pathNodes = [];
      const pathEdges = [];
      let cur = exitNode;
      while (prev.has(cur)) {
        const { from, edge } = prev.get(cur);
        pathEdges.unshift(edge);
        pathNodes.unshift(cur);
        cur = from;
      }
      pathNodes.unshift(startNode);

      const pathCoords = pathNodes
        .map(id => { const p = _nodeMap.get(id); return p ? [p.lat, p.lon] : null; })
        .filter(c => c !== null);

      results.set(exitNode, {
        cost_s:      dist.get(exitNode),
        path_edges:  pathEdges,
        path_nodes:  pathNodes,
        path_coords: pathCoords,   // [[lat, lon], ...]
      });
    }
    return results;
  }

"""

# ── Serving path identification ───────────────────────────────────────────────
# Mirrors: agents/scenarios/wildland.py identify_routes()
# Algorithm constants encoded here:
#   max_path_length_ratio — from params (no hardcoded value; read from _params)
#   Bottleneck = argmin(eff_cap_vph) on path edges
#   Dedup: per unique bottleneck osmid, keep highest-capacity path
# CRITICAL: Python routes to ALL exit nodes.  The 0.5-mile radius is only for
# the visualization overlay.  Do NOT reintroduce the reachable-exit filter here.
_JS_IDENTIFY_SERVING_PATHS = """\
  // ── Serving path identification ───────────────────────────────────────────────
  // Mirrors: agents/scenarios/wildland.py identify_routes()
  // Routes to ALL exit nodes (no radius filter on exits — matches Python).
  // max_path_length_ratio filter, bottleneck = argmin(eff_cap_vph), dedup by osmid.

  /**
   * Identify EvacuationPath objects for a project at (lat, lon).
   * Returns array of path objects with bottleneck + coord data for rendering.
   */
  function identifyServingPaths(lat, lon) {
    const maxRatio = _params.max_path_length_ratio;

    const origin = nearestNode(lat, lon);
    if (origin === null) return [];

    // Dijkstra to ALL exit nodes — mirrors wildland.py (no radius filter on exits)
    const dijkstra = _dijkstraFromOrigin(origin);

    const candidates = [];
    for (const [exitNode, info] of dijkstra) {
      if (!_exitSet.has(exitNode)) continue;
      candidates.push({ exitNode, cost_s: info.cost_s, path_edges: info.path_edges,
                        path_coords: info.path_coords });
    }
    if (candidates.length === 0) return [];

    // max_path_length_ratio filter — keep only paths within ratio × fastest
    const minCost   = Math.min(...candidates.map(c => c.cost_s));
    const maxAllowed = minCost * maxRatio;
    const filtered  = candidates.filter(c => c.cost_s <= maxAllowed);

    // Bottleneck = edge with minimum eff_cap_vph.
    // Dedup: per unique bottleneck osmid, keep the path with highest bottleneck cap.
    const bottleneckMap = new Map(); // osmid → best candidate
    for (const cand of filtered) {
      if (cand.path_edges.length === 0) continue;
      let bn = cand.path_edges[0];
      for (const e of cand.path_edges) {
        if (e.eff_cap_vph < bn.eff_cap_vph) bn = e;
      }
      const existing = bottleneckMap.get(bn.osmid);
      if (!existing || bn.eff_cap_vph > existing.bottleneck.eff_cap_vph) {
        bottleneckMap.set(bn.osmid, {
          exitNode:       cand.exitNode,
          cost_s:         cand.cost_s,
          path_edges:     cand.path_edges,
          path_coords:    cand.path_coords ?? [],
          bottleneck:     bn,
          bottleneck_idx: cand.path_edges.indexOf(bn),
        });
      }
    }

    return Array.from(bottleneckMap.values()).map((c, i) => {
      const bi = c.bottleneck_idx;
      const bnCoords = (bi >= 0 && bi < c.path_coords.length - 1)
        ? [c.path_coords[bi], c.path_coords[bi + 1]]
        : [];
      return {
        pathId:               `project_origin_${c.exitNode}_${i}`,
        exitNodeId:           c.exitNode,
        bottleneckOsmid:      c.bottleneck.osmid,
        bottleneckEffCapVph:  c.bottleneck.eff_cap_vph,
        bottleneckFhszZone:   c.bottleneck.fhsz_zone,
        cost_s:               c.cost_s,
        path_edges:           c.path_edges,
        path_coords:          c.path_coords,
        bottleneck_coords:    bnCoords,
      };
    });
  }

"""

# ── ΔT calculation ────────────────────────────────────────────────────────────
# Mirrors: agents/scenarios/base.py compute_delta_t()
# Algorithm constants: ALL read from _params at runtime — no hardcoded values.
#   project_vehicles = units × vehicles_per_unit × mobilization_rate  (NFPA 101 constant)
#   egress_minutes   = 0 if stories < threshold; else min(stories × mps, max_min)
#   ΔT per path      = (project_vehicles / bottleneck_eff_cap_vph) × 60 + egress_minutes
#   threshold        = safe_egress_window[hazard_zone] × max_project_share
#   flagged          = ΔT > threshold
_JS_COMPUTE_DELTA_T = """\
  // ── ΔT calculation ────────────────────────────────────────────────────────────
  // Mirrors: agents/scenarios/base.py compute_delta_t()
  // All constants read from _params — no hardcoded values here.
  //   project_vehicles = units × vehicles_per_unit × mobilization_rate
  //   egress_minutes   = 0 if stories < threshold; else min(stories × mps, max_min)
  //   ΔT               = (project_vehicles / bottleneck_eff_cap_vph) × 60 + egress_minutes
  //   threshold        = safe_egress_window[hazard_zone] × max_project_share

  function computeDeltaT(servingPaths, units, stories, hazardZone) {
    const p = _params;
    const projectVehicles = units * p.vehicles_per_unit * p.mobilization_rate;

    const ep = p.egress_penalty;
    const egressMinutes =
      stories < ep.threshold_stories
        ? 0
        : Math.min(stories * ep.minutes_per_story, ep.max_minutes);

    const threshold = p.safe_egress_window[hazardZone] * p.max_project_share;

    return servingPaths.map(path => {
      const delta_t = (projectVehicles / path.bottleneckEffCapVph) * 60 + egressMinutes;
      return {
        pathId:              path.pathId,
        bottleneckOsmid:     path.bottleneckOsmid,
        bottleneckFhszZone:  path.bottleneckFhszZone,
        bottleneckEffCapVph: path.bottleneckEffCapVph,
        delta_t_minutes:     delta_t,
        threshold_minutes:   threshold,
        flagged:             delta_t > threshold,
        project_vehicles:    projectVehicles,
        egress_minutes:      egressMinutes,
        path_coords:         path.path_coords     ?? [],
        bottleneck_coords:   path.bottleneck_coords ?? [],
      };
    });
  }

"""

# ── Tier determination ────────────────────────────────────────────────────────
# Mirrors: agents/objective_standards.py (most-restrictive-wins logic)
# Algorithm constant: unit_threshold read from _params.
# Tier strings must match Python Determination enum values exactly.
_JS_DETERMINE_TIER = """\
  // ── Tier determination ────────────────────────────────────────────────────────
  // Mirrors: agents/objective_standards.py most-restrictive-wins logic.
  // Tier strings must match Python Determination enum values EXACTLY.

  function _determineTier(units, deltaResults) {
    const p = _params;
    if (units < p.unit_threshold) return "MINISTERIAL";
    if (deltaResults.some(d => d.flagged)) return "DISCRETIONARY";
    return "MINISTERIAL WITH STANDARD CONDITIONS";
  }

"""

# ── Top-level evaluateProject ─────────────────────────────────────────────────
# Mirrors: agents/objective_standards.py evaluate() orchestration.
# Sorts results by bottleneck_osmid for stable ordering matching test vectors.
_JS_EVALUATE_PROJECT = """\
  // ── Top-level evaluateProject ─────────────────────────────────────────────────
  // Mirrors: agents/objective_standards.py evaluate() orchestration.

  /**
   * Evaluate a hypothetical project at (lat, lon).
   * @param {number} lat     WGS84 latitude
   * @param {number} lon     WGS84 longitude
   * @param {number} units   Dwelling units
   * @param {number} stories Above-grade stories (NFPA 101 egress penalty)
   * @returns {Object}       Evaluation result
   */
  function evaluateProject(lat, lon, units, stories) {
    _ensureReady();

    const hazardZone    = classifyFhsz(lat, lon);
    const servingPaths  = identifyServingPaths(lat, lon);
    const deltaResults  = computeDeltaT(servingPaths, units, stories, hazardZone);
    const tier          = _determineTier(units, deltaResults);

    // Sort by bottleneck osmid for stable ordering (matches test vectors)
    deltaResults.sort((a, b) => a.bottleneckOsmid.localeCompare(b.bottleneckOsmid));

    const maxDeltaT = deltaResults.length > 0
      ? Math.max(...deltaResults.map(d => d.delta_t_minutes))
      : 0;

    return {
      tier,
      hazard_zone:          hazardZone,
      project_vehicles:     deltaResults[0]?.project_vehicles ?? 0,
      serving_paths_count:  deltaResults.length,
      paths:                deltaResults,
      max_delta_t_minutes:  maxDeltaT,
      built_at:             _graph?.built_at ?? "unknown",
      parameters_version:   _params?.parameters_version ?? "unknown",
    };
  }

"""

# ── IIFE exports + CommonJS wrapper ──────────────────────────────────────────
_JS_IIFE_FOOTER = """\
  // ── Module exports ────────────────────────────────────────────────────────────
  return {
    init,
    evaluateProject,
    // Expose internals for testing
    _internal: {
      classifyFhsz,
      nearestNode,
      reachableNodes,
      identifyServingPaths,
      computeDeltaT,
      haversineMeters,
    },
  };
})();

// CommonJS export for Node.js test runner
if (typeof module !== "undefined" && module.exports) {
  module.exports = { WhatIfEngine };
}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_graph_json(
    graph_path: Path,
    exit_nodes_path: Path,
    roads_gdf,
    config: dict,
    city_config: dict,
    output_dir: Path,
) -> Path:
    """
    Write output/{city}/graph.json — compact adjacency list with pre-resolved
    capacity and routing attributes.

    Node format:  {"id": int, "lon": float, "lat": float}
    Edge format:  {"u": int, "v": int, "osmid": str, "len_m": float,
                   "speed_mph": float, "eff_cap_vph": float,
                   "fhsz_zone": str, "haz_deg": float}

    Speed is resolved from config["speed_defaults"][highway_type] — identical to the
    travel_time_s computation in wildland.py.  eff_cap_vph and fhsz_zone are joined
    from roads_gdf on osmid.
    """
    try:
        import osmnx as ox
        from pyproj import Transformer
    except ImportError as e:
        raise ImportError(f"export_graph_json requires osmnx + pyproj: {e}") from e

    graph_path = Path(graph_path)
    if not graph_path.exists():
        logger.warning(f"export_graph_json: graph not found at {graph_path} — skipping")
        return None

    logger.info(f"Exporting graph.json from {graph_path.name}...")
    G = ox.load_graphml(graph_path)

    graph_crs = G.graph.get("crs", "EPSG:26910")
    to_wgs84 = Transformer.from_crs(graph_crs, "EPSG:4326", always_xy=True)

    speed_defaults: dict = config.get("speed_defaults", {})

    # ── Build osmid → capacity/zone lookup from roads_gdf ────────────────────
    osmid_to_eff_cap: dict[str, float] = {}
    osmid_to_zone: dict[str, str] = {}
    osmid_to_haz_deg: dict[str, float] = {}

    for _, row in roads_gdf.iterrows():
        oid = row.get("osmid")
        if oid is None:
            continue
        eff = float(row.get("effective_capacity_vph", row.get("capacity_vph", 1000.0)))
        zone = str(row.get("fhsz_zone", "non_fhsz"))
        haz_deg = float(row.get("hazard_degradation", 1.0))
        for o in (oid if isinstance(oid, list) else [oid]):
            key = str(o)
            if eff > osmid_to_eff_cap.get(key, -1):
                osmid_to_eff_cap[key] = eff
                osmid_to_zone[key] = zone
                osmid_to_haz_deg[key] = haz_deg

    # ── Nodes ─────────────────────────────────────────────────────────────────
    nodes: list[dict] = []
    for node_id, ndata in G.nodes(data=True):
        x = float(ndata.get("x", 0))
        y = float(ndata.get("y", 0))
        lon, lat = to_wgs84.transform(x, y)
        nodes.append({"id": int(node_id), "lon": round(lon, 7), "lat": round(lat, 7)})

    # ── Edges ─────────────────────────────────────────────────────────────────
    edges: list[dict] = []
    for u, v, edata in G.edges(data=True):
        raw_osmid = edata.get("osmid")
        if raw_osmid is None:
            continue
        osmid_str = str(raw_osmid[0] if isinstance(raw_osmid, list) else raw_osmid)

        hw = edata.get("highway", "residential")
        hw_str = hw[0] if isinstance(hw, list) else str(hw)

        # Speed: config speed_defaults[highway_type] only — same as wildland.py.
        # The OSM maxspeed tag is intentionally ignored here; wildland.py ignores it too.
        speed_mph = float(speed_defaults.get(hw_str, 25))

        len_m = float(edata.get("length", 0) or 0)
        eff_cap = osmid_to_eff_cap.get(osmid_str, 1000.0)
        zone = osmid_to_zone.get(osmid_str, "non_fhsz")
        haz_deg = osmid_to_haz_deg.get(osmid_str, 1.0)

        edges.append({
            "u": int(u),
            "v": int(v),
            "osmid": osmid_str,
            "len_m": round(len_m, 1),
            "speed_mph": speed_mph,
            "eff_cap_vph": round(eff_cap, 1),
            "fhsz_zone": zone,
            "haz_deg": round(haz_deg, 4),
        })

    # ── Exit nodes ────────────────────────────────────────────────────────────
    exit_nodes: list = []
    exit_nodes_path = Path(exit_nodes_path)
    if exit_nodes_path.exists():
        try:
            exit_nodes = json.loads(exit_nodes_path.read_text())
        except Exception as e:
            logger.warning(f"Could not load exit_nodes.json ({e})")

    output = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "parameters_version": _PARAMETERS_VERSION,
        "nodes": nodes,
        "edges": edges,
        "exit_nodes": exit_nodes,
    }

    out_path = Path(output_dir) / "graph.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, separators=(",", ":")))
    size_kb = out_path.stat().st_size // 1024
    logger.info(f"  graph.json → {out_path} ({size_kb} KB, {len(nodes)} nodes, {len(edges)} edges)")
    return out_path


def export_parameters_json(config: dict, city_config: dict, output_dir: Path) -> Path:
    """
    Write output/{city}/parameters.json — flattened subset of parameters.yaml
    containing only the values the JS what-if engine needs.

    The JS engine loads this file at runtime so it never has hardcoded constants.
    Regenerate the demo map after any parameters.yaml change.
    """
    evac_cfg = config.get("evacuation", {})

    hazard_factors = config.get("hazard_degradation", {}).get("factors", {})
    safe_egress = config.get("safe_egress_window", {})
    egress_penalty = config.get("egress_penalty", {})

    params = {
        "parameters_version": _PARAMETERS_VERSION,
        "unit_threshold": int(config.get("unit_threshold", 15)),
        "mobilization_rate": float(config.get("mobilization_rate", 0.90)),
        "vehicles_per_unit": float(config.get("vehicles_per_unit", 2.5)),
        "serving_route_radius_miles": float(evac_cfg.get("serving_route_radius_miles", 0.5)),
        "max_path_length_ratio": float(evac_cfg.get("max_path_length_ratio", 2.0)),
        "hazard_degradation": {
            "vhfhsz": float(hazard_factors.get("vhfhsz", 0.35)),
            "high_fhsz": float(hazard_factors.get("high_fhsz", 0.50)),
            "moderate_fhsz": float(hazard_factors.get("moderate_fhsz", 0.75)),
            "non_fhsz": float(hazard_factors.get("non_fhsz", 1.00)),
        },
        "safe_egress_window": {
            "vhfhsz": float(safe_egress.get("vhfhsz", 45)),
            "high_fhsz": float(safe_egress.get("high_fhsz", 90)),
            "moderate_fhsz": float(safe_egress.get("moderate_fhsz", 120)),
            "non_fhsz": float(safe_egress.get("non_fhsz", 120)),
        },
        "max_project_share": float(config.get("max_project_share", 0.05)),
        "egress_penalty": {
            "threshold_stories": int(egress_penalty.get("threshold_stories", 4)),
            "minutes_per_story": float(egress_penalty.get("minutes_per_story", 1.5)),
            "max_minutes": float(egress_penalty.get("max_minutes", 12)),
        },
        "fhsz_trigger_zones": list(
            config.get("fhsz", {}).get("trigger_zones", [2, 3])
        ),
    }

    out_path = Path(output_dir) / "parameters.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(params, indent=2))
    logger.info(f"  parameters.json → {out_path}")
    return out_path


def export_fhsz_json(fhsz_gdf, output_dir: Path) -> Path:
    """
    Write output/{city}/fhsz.json — FHSZ GeoJSON in WGS84, used by the test suite.
    The demo map inlines this data directly; this file is only needed for Node.js tests.
    """
    out_path = Path(output_dir) / "fhsz.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    geojson = fhsz_gdf.to_crs("EPSG:4326").to_json()
    out_path.write_text(geojson)
    logger.info(f"  fhsz.json → {out_path}")
    return out_path


def export_test_vectors(
    evaluated_projects: list,
    audits: list[dict],
    output_dir: Path,
) -> Path:
    """
    Write output/{city}/test_vectors.json — Python-authoritative evaluation results
    used by tests/test_whatif_engine.js to catch JS/Python divergence.

    One vector per evaluated project.  Each vector records:
      - input:    the project inputs (lat, lon, units, stories)
      - expected: the authoritative Python outputs (tier, hazard_zone, paths with ΔT)

    The JS test suite (node --test tests/test_whatif_engine.js) loads this file and
    asserts that the JS engine produces matching results within DELTA_T_TOLERANCE = 0.1 min.
    """
    vectors = []
    for project, audit in zip(evaluated_projects, audits):
        wildland = audit.get("scenarios", {}).get("wildland_ab747", {})
        steps = wildland.get("steps", {})
        step5 = steps.get("step5_delta_t", {})
        # Audit key is "path_results" (per agents/scenarios/base.py).
        # Filter to primary origin only — JS only models the project's nearest-node
        # origin (no additional_egress_points).  Paths from secondary egress origins
        # (origin_block_group != "project_origin") would inflate path count and cause
        # false test failures.
        path_results = [
            p for p in step5.get("path_results", [])
            if p.get("origin_block_group", "project_origin") == "project_origin"
        ]

        # Normalise per-path outputs to only what JS can compute
        paths = []
        for dtr in path_results:
            paths.append({
                "bottleneck_osmid": str(dtr.get("bottleneck_osmid", "")),
                "delta_t_minutes": round(float(dtr.get("delta_t_minutes", 0)), 4),
                "threshold_minutes": round(float(dtr.get("threshold_minutes", 0)), 4),
                "flagged": bool(dtr.get("flagged", False)),
            })

        # Sort paths by bottleneck_osmid for stable comparison order
        paths.sort(key=lambda p: p["bottleneck_osmid"])

        hazard_zone = str(
            steps.get("step1_applicability", {})
            .get("fire_zone_severity_modifier", {})
            .get("hazard_zone", "non_fhsz")
        )
        project_vehicles = float(
            steps.get("step4_demand", {}).get("project_vehicles_peak_hour", 0)
        )

        vectors.append({
            "name": str(getattr(project, "project_name", "")),
            "input": {
                "lat": float(project.location_lat),
                "lon": float(project.location_lon),
                "units": int(project.dwelling_units),
                "stories": int(getattr(project, "stories", 0)),
            },
            "expected": {
                "tier": str(project.determination),
                "hazard_zone": hazard_zone,
                "project_vehicles": project_vehicles,
                "serving_paths_count": len(paths),
                "paths": paths,
            },
        })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters_version": _PARAMETERS_VERSION,
        "vectors": vectors,
    }

    out_path = Path(output_dir) / "test_vectors.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    logger.info(f"  test_vectors.json → {out_path} ({len(vectors)} vectors)")
    return out_path


def export_whatif_engine_js() -> Path:
    """
    Generate static/whatif_engine.js from two sources:

      1. static/whatif_utils.js  — hand-written, drift-free utility functions
                                   (MinHeap, Haversine, ray-casting, adjacency builder,
                                    nearestNode, reachableNodes).  No algorithm constants.
      2. Algorithm JS strings    — defined as Python constants directly above in THIS file,
                                   adjacent to the Python functions they mirror.

    The generated file is a self-contained IIFE exposing WhatIfEngine.  It is identical
    in behaviour to the hand-written version it replaces, but now the algorithm sections
    live in Python source (export.py) next to the Python code they mirror, making it
    structurally impossible to update one without seeing the other.

    Call this from the analyze command after export_graph_json/export_parameters_json.
    Regenerate after ANY change to parameters.yaml that affects algorithm logic.

    Returns the path to the written file (static/whatif_engine.js).
    """
    static_dir = Path(__file__).parent.parent / "static"
    utils_path = static_dir / "whatif_utils.js"
    engine_path = static_dir / "whatif_engine.js"

    if not utils_path.exists():
        raise FileNotFoundError(
            f"export_whatif_engine_js: missing {utils_path}\n"
            "Ensure static/whatif_utils.js is committed to the repository."
        )

    # Read utils source and strip the file-level JSDoc block (copyright + module
    # description) so the generated file has one clean header at the top.
    # Everything after the closing " */" of the JSDoc is the actual code.
    utils_raw = utils_path.read_text(encoding="utf-8")
    utils_lines = utils_raw.splitlines(keepends=True)
    doc_end = 0
    for i, line in enumerate(utils_lines):
        if line.strip() == "*/":
            doc_end = i + 1
            break
    utils_body = "".join(utils_lines[doc_end:])

    # Assemble the generated file
    parts = [
        _JS_IIFE_HEADER,
        _JS_INIT,
        "  // ── Utilities (from static/whatif_utils.js) ────────────────────────────────\n",
        _indent_js(utils_body, "  "),
        "\n",
        _JS_CLASSIFY_FHSZ,
        _JS_DIJKSTRA,
        _JS_IDENTIFY_SERVING_PATHS,
        _JS_COMPUTE_DELTA_T,
        _JS_DETERMINE_TIER,
        _JS_EVALUATE_PROJECT,
        _JS_IIFE_FOOTER,
    ]

    engine_path.write_text("".join(parts), encoding="utf-8")
    size_kb = engine_path.stat().st_size // 1024
    logger.info(f"  whatif_engine.js → {engine_path} ({size_kb} KB, generated)")
    return engine_path


def _indent_js(source: str, prefix: str) -> str:
    """Indent every non-blank line of JS source by prefix (for IIFE embedding)."""
    lines = []
    for line in source.splitlines(keepends=True):
        if line.strip():
            lines.append(prefix + line)
        else:
            lines.append(line)
    return "".join(lines)

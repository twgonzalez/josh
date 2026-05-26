// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

// ============================================================================
// GENERATED FILE — DO NOT EDIT
// Source:   agents/export.py  (export_app_js)
//           static/whatif_engine.js  (embedded verbatim)
// Regenerate:  uv run python build.py map --city "Berkeley"
// ============================================================================

// ── Schema compatibility check ────────────────────────────────────────────────
// Multi-hazard schema v2 is the only supported runtime schema. Warns on any
// other value so silent drift on a future schema bump is caught loudly.
(function () {
  var d = window.JOSH_DATA;
  if (!d) { console.warn('JOSH app.js: window.JOSH_DATA not found'); return; }
  if (d.schema_version !== 2) {
    console.warn(
      'JOSH app.js: unsupported schema_version (got ' + d.schema_version + ', expected 2). ' +
      'Regenerate analysis_map.html with a matching pipeline version.'
    );
  }
})();

// ── WhatIfEngine IIFE (legacy — from static/whatif_engine.js) ─────────────────

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
 * Pure JavaScript implementation of the JOSH v4.0 ΔT evacuation clearance
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
  let _edgeMap   = null;   // Map<osmid_str, edge> — for bottleneck lookup + AntPath overlay
  let _exitSet   = null;   // Set<nodeId>
  let _ready     = false;

  // MPH → m/s conversion — exact, matches wildland.py _MPH_TO_MPS
  const MPH_TO_MPS    = 0.44704;
  const EARTH_RADIUS_M = 6_371_000;

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
    _edgeMap = new Map();
    for (const e of _graph.edges) _edgeMap.set(e.osmid, e);
    _exitSet = new Set(_graph.exit_nodes);
    _ready = true;
  }

  function _ensureReady() {
    if (!_ready) {
      var d = window.JOSH_DATA;
      if (d && d.graph && d.parameters && d.fhsz) {
        init(d.graph, d.parameters, d.fhsz);
      } else {
        throw new Error(
          "WhatIfEngine: window.JOSH_DATA not loaded. " +
          "Ensure JOSH_DATA is inlined before app.js."
        );
      }
    }
  }

  // ── Utilities (from static/whatif_utils.js) ────────────────────────────────

  // ── Min-heap (binary heap) for Dijkstra ───────────────────────────────────────
  // Pure data structure — no algorithm parameters.

  class MinHeap {
    constructor() { this._h = []; }
    push(cost, id) {
      this._h.push([cost, id]);
      this._bubbleUp(this._h.length - 1);
    }
    pop() {
      const top = this._h[0];
      const last = this._h.pop();
      if (this._h.length > 0) { this._h[0] = last; this._siftDown(0); }
      return top;
    }
    get size() { return this._h.length; }
    _bubbleUp(i) {
      while (i > 0) {
        const p = (i - 1) >> 1;
        if (this._h[p][0] <= this._h[i][0]) break;
        [this._h[p], this._h[i]] = [this._h[i], this._h[p]];
        i = p;
      }
    }
    _siftDown(i) {
      const n = this._h.length;
      while (true) {
        let m = i;
        const l = 2 * i + 1, r = 2 * i + 2;
        if (l < n && this._h[l][0] < this._h[m][0]) m = l;
        if (r < n && this._h[r][0] < this._h[m][0]) m = r;
        if (m === i) break;
        [this._h[m], this._h[i]] = [this._h[i], this._h[m]];
        i = m;
      }
    }
  }

  // ── Haversine distance ─────────────────────────────────────────────────────────
  // Pure geometry — no algorithm parameters.
  // Used for nearest-node lookup and radius cutoffs.

  /** Haversine distance in metres between two WGS84 points. */
  function haversineMeters(lat1, lon1, lat2, lon2) {
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * Math.PI / 180) *
      Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLon / 2) ** 2;
    return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(a));
  }

  // ── Point-in-polygon (ray-casting) ────────────────────────────────────────────
  // Pure geometry — handles GeoJSON Polygon and MultiPolygon with holes.

  /**
   * Ray-casting point-in-polygon test for a single GeoJSON ring
   * (array of [lon, lat] coordinate pairs).
   */
  function _pointInRing(lon, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1];
      const xj = ring[j][0], yj = ring[j][1];
      const intersect =
        yi > lat !== yj > lat &&
        lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
      if (intersect) inside = !inside;
    }
    return inside;
  }

  /** Test a [lon, lat] point against a GeoJSON Feature (Polygon or MultiPolygon). */
  function _pointInFeature(lon, lat, feature) {
    const geom = feature.geometry;
    if (!geom) return false;
    if (geom.type === "Polygon") {
      if (!_pointInRing(lon, lat, geom.coordinates[0])) return false;
      for (let h = 1; h < geom.coordinates.length; h++) {
        if (_pointInRing(lon, lat, geom.coordinates[h])) return false;
      }
      return true;
    }
    if (geom.type === "MultiPolygon") {
      for (const poly of geom.coordinates) {
        if (!_pointInRing(lon, lat, poly[0])) continue;
        let inHole = false;
        for (let h = 1; h < poly.length; h++) {
          if (_pointInRing(lon, lat, poly[h])) { inHole = true; break; }
        }
        if (!inHole) return true;
      }
    }
    return false;
  }

  // ── Graph adjacency builder ────────────────────────────────────────────────────
  // Builds undirected adjacency list — mirrors nx.to_undirected() in wildland.py.
  // No algorithm constants: just graph topology.

  /**
   * Build undirected adjacency list from edges array.
   * Map<nodeId, Array<{v, osmid, len_m, speed_mph, eff_cap_vph, fhsz_zone, haz_deg}>>
   */
  function _buildAdjacency(edges) {
    const adj = new Map();
    const addEdge = (from, to, attrs) => {
      if (!adj.has(from)) adj.set(from, []);
      adj.get(from).push({ v: to, ...attrs });
    };
    for (const e of edges) {
      const attrs = {
        osmid:        e.osmid,
        len_m:        e.len_m,
        speed_mph:    e.speed_mph,
        eff_cap_vph:  e.eff_cap_vph,
        fhsz_zone:    e.fhsz_zone,
        haz_deg:      e.haz_deg,
      };
      addEdge(e.u, e.v, attrs);
      addEdge(e.v, e.u, attrs);  // undirected — mirrors nx.to_undirected()
    }
    return adj;
  }

  // ── Nearest node ───────────────────────────────────────────────────────────────
  // Uses module-level _nodeMap (set during init).
  // Mirrors ox.distance.nearest_nodes() in wildland.py.

  /**
   * Find the graph node closest to (lat, lon) by Haversine distance.
   * Linear scan — Berkeley has ~8K nodes, runs in < 5 ms.
   */
  function nearestNode(lat, lon) {
    let bestId = null, bestDist = Infinity;
    for (const [id, pos] of _nodeMap) {
      const d = haversineMeters(lat, lon, pos.lat, pos.lon);
      if (d < bestDist) { bestDist = d; bestId = id; }
    }
    return bestId;
  }

  // ── Reachable nodes (radius-cutoff Dijkstra) ───────────────────────────────────
  // Uses module-level _adjacency (set during init).
  // Mirrors nx.single_source_dijkstra_path_length(..., weight="length") in wildland.py.
  // No algorithm constants — radius is passed as a parameter from params at call site.

  /**
   * Return Set of node IDs reachable from startNode within radiusMeters,
   * weighted by edge length (len_m).
   */
  function reachableNodes(startNode, radiusMeters) {
    const dist = new Map([[startNode, 0]]);
    const heap = new MinHeap();
    heap.push(0, startNode);
    while (heap.size > 0) {
      const [cost, u] = heap.pop();
      if (cost > dist.get(u)) continue;
      if (cost > radiusMeters) continue;
      for (const edge of (_adjacency.get(u) ?? [])) {
        const newCost = cost + edge.len_m;
        if (newCost <= radiusMeters && newCost < (dist.get(edge.v) ?? Infinity)) {
          dist.set(edge.v, newCost);
          heap.push(newCost, edge.v);
        }
      }
    }
    return new Set(dist.keys());
  }

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

      // Build pathCoords from full edge geometry (mirrors wildland.py AntPath fix).
      // For each edge: extract geom [[lat,lon],...], detect direction, chain segments.
      // Fallback to node endpoints when edge.geom is absent.
      const pathCoords = [];
      for (let _gi = 0; _gi < pathEdges.length; _gi++) {
        const _ge = pathEdges[_gi];
        if (!_ge.geom || _ge.geom.length === 0) {
          // No geometry — fall back to node endpoint positions
          if (_gi === 0) { const _s = _nodeMap.get(pathNodes[0]); if (_s) pathCoords.push([_s.lat, _s.lon]); }
          const _d = _nodeMap.get(pathNodes[_gi + 1]);
          if (_d) pathCoords.push([_d.lat, _d.lon]);
          continue;
        }
        // Direction check: compare geom endpoints to source node (Euclidean, lat/lon space)
        const _src = _nodeMap.get(pathNodes[_gi]);
        let _gc = _ge.geom;
        if (_src) {
          const _d0 = (_gc[0][0] - _src.lat) ** 2 + (_gc[0][1] - _src.lon) ** 2;
          const _dN = (_gc[_gc.length - 1][0] - _src.lat) ** 2 + (_gc[_gc.length - 1][1] - _src.lon) ** 2;
          if (_dN < _d0) _gc = [..._gc].reverse();
        }
        // Chain: skip first point on non-first segments (avoids duplicate junction points)
        const _gStart = pathCoords.length > 0 ? 1 : 0;
        for (let _gj = _gStart; _gj < _gc.length; _gj++) pathCoords.push(_gc[_gj]);
      }
      // Edge case: single-node path or all edges had no geometry
      if (pathCoords.length === 0 && pathNodes.length > 0) {
        const _fn = _nodeMap.get(pathNodes[0]); if (_fn) pathCoords.push([_fn.lat, _fn.lon]);
      }

      results.set(exitNode, {
        cost_s:      dist.get(exitNode),
        path_edges:  pathEdges,
        path_nodes:  pathNodes,
        path_coords: pathCoords,   // [[lat, lon], ...]
      });
    }
    return results;
  }

  // ── Serving path identification ───────────────────────────────────────────────
  // Mirrors: agents/scenarios/wildland.py identify_routes()
  // Routes to ALL exit nodes (no radius filter on exits — matches Python).
  // max_path_length_ratio filter + per-path bottleneck = argmin(eff_cap_vph).
  // All viable routes returned — no per-bottleneck deduplication (user controls
  // visibility via sidebar toggles).

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

    // Identify bottleneck per path (no dedup — all viable routes are returned).
    // v4.13 parity fix: skip edges with eff_cap_vph<=0 (no roads_gdf row match).
    // Python wildland.py uses `or float('inf')` to skip the same edges; both
    // engines therefore agree on which edges are bottleneck candidates.
    // Previously JS treated missing edges as 1000 vph (would pick them as
    // bottleneck) while Python skipped them — root cause of the divergence.
    return filtered.map((cand, i) => {
      if (cand.path_edges.length === 0) return null;
      const validEdges = cand.path_edges.filter(e => +(e.eff_cap_vph || 0) > 0);
      if (validEdges.length === 0) return null;
      let bn = validEdges[0];
      for (const e of validEdges) {
        if (e.eff_cap_vph < bn.eff_cap_vph) bn = e;
      }
      const path_coords = cand.path_coords ?? [];
      const bi = cand.path_edges.indexOf(bn);
      const bnCoords = (bi >= 0 && bi < path_coords.length - 1)
        ? [path_coords[bi], path_coords[bi + 1]]
        : [];
      return {
        pathId:                    `project_origin_${cand.exitNode}_${i}`,
        exitNodeId:                cand.exitNode,
        bottleneckOsmid:           bn.osmid,
        bottleneckEffCapVph:       bn.eff_cap_vph,
        bottleneckFhszZone:        bn.fhsz_zone,
        bottleneck_name:           bn.name        ?? '',
        bottleneck_road_type:      bn.road_type   ?? '',
        bottleneck_lanes:          bn.lanes        ?? 0,
        bottleneck_speed:          bn.speed_mph   ?? 0,
        hazard_degradation_factor: bn.haz_deg     ?? 1.0,
        bottleneck_cap_src:        bn.cap_src     ?? 'hcm',
        bottleneck_cap_reason:     bn.cap_reason  ?? null,
        bottleneck_cap_source_doc: bn.cap_source_doc ?? null,
        cost_s:                    cand.cost_s,
        path_edges:                cand.path_edges,
        path_coords:               path_coords,
        bottleneck_coords:         bnCoords,
      };
    }).filter(Boolean);
  }

  // ── ΔT calculation ────────────────────────────────────────────────────────────
  // Mirrors: agents/scenarios/base.py compute_delta_t()
  // All constants read from _params — no hardcoded values here.
  //   project_vehicles = units × vehicles_per_unit × behavioral_mobilization
  //   egress_minutes   = 0 if stories < threshold; else min(stories × mps, max_min)
  //   ΔT               = (project_vehicles / bottleneck_eff_cap_vph) × 60 + egress_minutes
  //   threshold        = safe_egress_window[hazard_zone] × max_project_share

  function computeDeltaT(servingPaths, units, stories, hazardZone) {
    const p = _params;
    const projectVehicles = units * p.vehicles_per_unit * p.behavioral_mobilization;

    const ep = p.egress_penalty;
    const egressMinutes =
      stories < ep.threshold_stories
        ? 0
        : Math.min(stories * ep.minutes_per_story, ep.max_minutes);

    const threshold = p.safe_egress_window[hazardZone] * p.max_project_share;

    return servingPaths.map(path => {
      const delta_t = (projectVehicles / path.bottleneckEffCapVph) * 60 + egressMinutes;
      return {
        pathId:                    path.pathId,
        cost_s:                    path.cost_s ?? 0,
        bottleneckOsmid:           path.bottleneckOsmid,
        bottleneckFhszZone:        path.bottleneckFhszZone,
        bottleneckEffCapVph:       path.bottleneckEffCapVph,
        bottleneck_name:           path.bottleneck_name           ?? '',
        bottleneck_road_type:      path.bottleneck_road_type      ?? '',
        bottleneck_lanes:          path.bottleneck_lanes          ?? 0,
        bottleneck_speed:          path.bottleneck_speed          ?? 0,
        hazard_degradation_factor: path.hazard_degradation_factor ?? 1.0,
        bottleneck_cap_src:        path.bottleneck_cap_src        ?? 'hcm',
        bottleneck_cap_reason:     path.bottleneck_cap_reason     ?? null,
        bottleneck_cap_source_doc: path.bottleneck_cap_source_doc ?? null,
        delta_t_minutes:           delta_t,
        threshold_minutes:         threshold,
        flagged:                   delta_t > threshold,
        project_vehicles:          projectVehicles,
        egress_minutes:            egressMinutes,
        path_coords:               path.path_coords      ?? [],
        bottleneck_coords:         path.bottleneck_coords ?? [],
      };
    });
  }

  // ── Tier determination ────────────────────────────────────────────────────────
  // Mirrors: agents/objective_standards.py most-restrictive-wins logic.
  // Tier strings must match Python Determination enum values EXACTLY.

  function _determineTier(units, deltaResults) {
    const p = _params;
    if (units < p.unit_threshold) return "MINISTERIAL";
    if (deltaResults.some(d => d.flagged)) return "DISCRETIONARY";
    return "MINISTERIAL WITH STANDARD CONDITIONS";
  }

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

// Browser: expose on window so other <script> blocks (sidebar.js, etc.) can reach it.
// const/let at the top level of a <script> are NOT added to window automatically.
if (typeof window !== "undefined") window.WhatIfEngine = WhatIfEngine;

// CommonJS export for Node.js test runner
if (typeof module !== "undefined" && module.exports) {
  module.exports = { WhatIfEngine };
}

// ────────────────────────────────────────────────────────────────────────────

// ── Hooks registry (multi-hazard, JS-side) — static/hooks.js ────────────────

// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH Hook Registry — JavaScript side (runtime hazard transforms).
 *
 * Per docs/plan-multihazard-stage-1-hooks.md §3. Mirror of
 * agents/scenarios/hooks_py.py — same API shape (register/call/has/clear),
 * different side of the pipeline:
 *
 *   Python (build time):  post_fetch, augment_graph
 *   JS (runtime):         classify, degradation, egress_window, build_result
 *
 * UMD: works in browser (`window.Hooks`) and node (`require('./hooks')`).
 *
 * Usage (per-hazard transform module):
 *
 *   var Hooks = (typeof window !== 'undefined' ? window.Hooks : require('./hooks'));
 *   Hooks.register('flood.degradation', function (edge, zone, features, params) {
 *     ...
 *     return factor;
 *   });
 *
 * Usage (engine dispatcher):
 *
 *   var hookName = cfg.hooks.classify || 'default.classify';
 *   var zone = Hooks.call(hookName, point, features, cfg);
 *
 * Defaults are registered under `default.*` names by static/transforms/_defaults.js,
 * which must be loaded before any hazard_engine.js code runs (concatenation order
 * in app.js bundle handles this; tests must require() defaults explicitly).
 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.Hooks = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // Phase prefix → expected arity (positional parameters). Mirrors the Python
  // _EXPECTED_ARITY in agents/scenarios/hooks_py.py. Used at register() time
  // to catch the most common bug class (wrong signature).
  //
  // FIVE hookable phases: post_fetch + augment_graph (Python pipeline-time);
  // classify + degradation + egress_window (JS runtime). `build_result` is
  // NOT a hook — it's engine-internal, driven by HazardConfig.result_extras
  // (declarative DSL).
  var EXPECTED_ARITY = Object.freeze({
    'post_fetch':    2,   // (features, params)
    'augment_graph': 3,   // (graph, features, params)
    'classify':      3,   // (point, features, cfg)
    'degradation':   4,   // (edge, zone, features, params)
    'egress_window': 4,   // (point, zone, features, params)
    'default':       null // default.* hooks bypass arity check (vary by phase)
  });

  // Module-level registry. Keyed by `{phase}.{name}` (e.g. "flood.degradation",
  // "default.classify").
  var _registry = Object.create(null);

  function register(name, fn) {
    if (typeof name !== 'string' || name.length === 0) {
      throw new Error('Hooks.register: name must be a non-empty string');
    }
    if (typeof fn !== 'function') {
      throw new Error('Hooks.register: fn must be a function (got ' + typeof fn + ')');
    }

    // Idempotent: re-registering the SAME function under the SAME name is a no-op.
    // Required so test modules can re-import transform files without raising.
    var existing = _registry[name];
    if (existing === fn) return fn;
    if (existing !== undefined) {
      throw new Error(
        'Hooks.register: ' + name + ' already registered by a different function'
      );
    }

    // Phase-prefix arity check (skipped for default.* — those vary by phase
    // and live in _defaults.js where they're checked individually).
    var prefix = name.split('.', 1)[0];
    if (prefix !== 'default') {
      var expected = EXPECTED_ARITY[prefix];
      if (expected !== undefined && expected !== null && fn.length !== expected) {
        throw new Error(
          'Hooks.register: ' + name + ' expected arity ' + expected +
          ' (phase=' + prefix + '), got ' + fn.length
        );
      }
    }

    _registry[name] = fn;
    return fn;
  }

  function call(name /*, ...args */) {
    var fn = _registry[name];
    if (fn === undefined) {
      throw new Error(
        'Hooks.call: no hook registered under ' + name +
        '. Available: ' + Object.keys(_registry).sort().join(', ')
      );
    }
    var args = Array.prototype.slice.call(arguments, 1);
    return fn.apply(null, args);
  }

  function has(name) {
    return Object.prototype.hasOwnProperty.call(_registry, name);
  }

  function allRegistered() {
    return Object.keys(_registry).slice().sort();
  }

  /**
   * Reset the registry. TEST-ONLY — production code never calls this.
   * Required for test isolation when transform modules register hooks at
   * import time (re-importing across tests would otherwise leak state).
   */
  function clear() {
    _registry = Object.create(null);
  }

  return {
    register: register,
    call: call,
    has: has,
    allRegistered: allRegistered,
    clear: clear,
    EXPECTED_ARITY: EXPECTED_ARITY
  };
}));

// ────────────────────────────────────────────────────────────────────────────

// ── Default hook impls — static/transforms/_defaults.js ─────────────────────

// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * Default hook implementations — JOSH multi-hazard runtime phases.
 *
 * Per docs/plan-multihazard-stage-1-hooks.md §8. Registered under `default.*`
 * names so the engine can resolve `cfg.hooks.classify || 'default.classify'`
 * uniformly — one code path whether the hazard overrides or not.
 *
 * Implements the 3 RUNTIME hook phases that have defaults (JS-side):
 *   default.classify       — sjoin + classify_strategy lookup
 *   default.degradation    — zone-table lookup
 *   default.egress_window  — zone-table lookup
 *
 * The 2 BUILD-TIME phases (post_fetch, augment_graph) live in Python; no JS
 * default needed because features come pre-fetched + pre-augmented in
 * JOSH_DATA.
 *
 * `build_result` is NOT a hook — it's engine-internal and driven by the
 * declarative `result_extras` DSL on each HazardConfig. See
 * hazard_engine.js _resolveResultExtra.
 *
 * Loaded by static/hazard_engine.js bundle BEFORE the engine itself runs.
 * In tests, require this module before calling HazardEngine.init().
 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory(require('../hooks'));
  } else {
    factory(root.Hooks);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (Hooks) {
  'use strict';

  // ─── Point-in-polygon (ray casting on GeoJSON) ──────────────────────────────
  // Pure geometry — no algorithm parameters. Lives here (not whatif_utils.js)
  // because the engine is self-contained UMD; whatif_utils.js is a concatenation
  // fragment for the legacy whatif_engine.js.

  function _pointInRing(lng, lat, ring) {
    // Ray casting algorithm. Ring is array of [lng, lat] pairs.
    var inside = false;
    var n = ring.length;
    for (var i = 0, j = n - 1; i < n; j = i++) {
      var xi = ring[i][0], yi = ring[i][1];
      var xj = ring[j][0], yj = ring[j][1];
      var intersect = ((yi > lat) !== (yj > lat)) &&
        (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  function _pointInPolygon(lng, lat, geometry) {
    // GeoJSON Polygon: { type: 'Polygon', coordinates: [outerRing, ...holes] }
    // GeoJSON MultiPolygon: { type: 'MultiPolygon', coordinates: [poly1, poly2, ...] }
    if (!geometry || !geometry.coordinates) return false;
    if (geometry.type === 'Polygon') {
      var polys = [geometry.coordinates];
    } else if (geometry.type === 'MultiPolygon') {
      polys = geometry.coordinates;
    } else {
      return false;
    }
    for (var p = 0; p < polys.length; p++) {
      var rings = polys[p];
      if (rings.length === 0) continue;
      if (!_pointInRing(lng, lat, rings[0])) continue;
      // Inside outer ring — check holes
      var inHole = false;
      for (var h = 1; h < rings.length; h++) {
        if (_pointInRing(lng, lat, rings[h])) { inHole = true; break; }
      }
      if (!inHole) return true;
    }
    return false;
  }

  /**
   * Return all features whose geometry contains the point.
   * @param {number} lng - longitude
   * @param {number} lat - latitude
   * @param {object} featureCollection - GeoJSON FeatureCollection
   * @returns {Array<object>} matching features
   */
  function _featuresContaining(lng, lat, featureCollection) {
    if (!featureCollection || !Array.isArray(featureCollection.features)) {
      return [];
    }
    var hits = [];
    for (var i = 0; i < featureCollection.features.length; i++) {
      var feat = featureCollection.features[i];
      if (_pointInPolygon(lng, lat, feat.geometry)) {
        hits.push(feat);
      }
    }
    return hits;
  }

  // ─── default.classify ────────────────────────────────────────────────────────
  // Signature: (point, features, cfg) → zone_str
  //   point: { lat, lng }
  //   features: GeoJSON FeatureCollection (hazard polygons)
  //   cfg: HazardConfig
  // Default behavior: sjoin (point-in-polygon) + cfg.classify_strategy lookup.
  //   'most_severe' (default): pick the polygon with max(zone_attribute) when
  //                            point falls in multiple — matches wildland.py's
  //                            max(HAZ_CLASS) behavior.
  //   'first_hit':             pick the first hit (whichever the index returns
  //                            first).
  //   'all':                   currently same as first_hit (placeholder).

  Hooks.register('default.classify', function defaultClassify(point, features, cfg) {
    var defaultZone = cfg.default_zone || 'outside';
    var hits = _featuresContaining(point.lng, point.lat, features);
    if (hits.length === 0) return defaultZone;

    var zmap = cfg.zone_map || {};
    var zoneAttr = cfg.zone_attribute;
    if (!zoneAttr) {
      // No zone discrimination configured — single-zone hazard
      return hits[0].properties && hits[0].properties[zoneAttr] != null
        ? String(hits[0].properties[zoneAttr])
        : 'in_zone';
    }

    if (cfg.classify_strategy === 'first_hit' || cfg.classify_strategy === 'all') {
      var rawFirst = hits[0].properties ? hits[0].properties[zoneAttr] : null;
      return rawFirst == null ? defaultZone : (zmap[String(rawFirst)] || defaultZone);
    }

    // 'most_severe' (default) — pick max numeric value of zone_attribute
    var mostSevereRaw = null;
    var mostSevereNum = -Infinity;
    for (var i = 0; i < hits.length; i++) {
      var raw = hits[i].properties ? hits[i].properties[zoneAttr] : null;
      if (raw == null) continue;
      var n = parseInt(raw, 10);
      if (!isNaN(n) && n > mostSevereNum) {
        mostSevereNum = n;
        mostSevereRaw = raw;
      }
    }
    if (mostSevereRaw == null) return defaultZone;
    return zmap[String(mostSevereRaw)] || defaultZone;
  });

  // ─── default.degradation ─────────────────────────────────────────────────────
  // Signature: (edge, zone, features, params) → factor in [0, 1]
  //   edge: graph edge object (engine passes the edge it's currently weighing)
  //   zone: the project's classified zone (constant per-evaluation)
  //   features: hazard polygons (unused by default; needed by flood hook)
  //   params: cfg.runtime_extras + cfg.degradation table
  // Default behavior: lookup degradation_by_zone[zone].
  //
  // Note: this is the SIMPLEST degradation model — the same factor applied to
  // every edge given the project's zone. More sophisticated hazards (flood)
  // register their own hook that varies per-edge.

  Hooks.register('default.degradation', function defaultDegradation(edge, zone, features, params) {
    var table = params && params.degradation_by_zone;
    if (!table) return 1.0;
    var factor = table[zone];
    return (factor === undefined || factor === null) ? 1.0 : factor;
  });

  // ─── default.egress_window ──────────────────────────────────────────────────
  // Signature: (point, zone, features, params) → minutes
  // Default behavior: lookup safe_egress_window_by_zone[zone]. Falls back to 120
  // (FEMA standard) if zone not in table.

  Hooks.register('default.egress_window', function defaultEgressWindow(point, zone, features, params) {
    var table = params && params.safe_egress_window_by_zone;
    if (!table) return 120.0;
    var mins = table[zone];
    return (mins === undefined || mins === null) ? 120.0 : mins;
  });

  // ─── Exports (for tests + engine introspection) ─────────────────────────────
  // Geometry helpers exported so hazard_engine.js can reuse them (point-in-polygon
  // is needed for both default.classify and the engine's result_extras resolver).

  return {
    _pointInPolygon: _pointInPolygon,
    _featuresContaining: _featuresContaining
  };
}));

// ────────────────────────────────────────────────────────────────────────────

// ── HazardEngine IIFE (multi-hazard) — static/hazard_engine.js ──────────────

// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH Hazard Engine — JavaScript runtime evaluator.
 *
 * Per docs/plan-multihazard-stage-1-hooks.md §8. Generic multi-hazard ΔT
 * engine that consumes window.JOSH_DATA (graph + hazard_configs +
 * hazard_polygons + parameters) and evaluates projects across every
 * configured hazard.
 *
 * Replaces static/whatif_engine.js (the per-project Python pre-bake +
 * anti-divergence path). Engine is now the only production evaluator;
 * Python's role narrows to build-time data prep (locked decision #12).
 *
 * Architecture:
 *   - 6 hook phases (post_fetch + augment_graph in Python at pipeline time;
 *     classify + degradation + egress_window + build_result in JS at runtime).
 *   - compute_delta_t is intentionally un-hookable — it carries the audit
 *     trail dict the brief renderer reads and never varies by hazard.
 *   - Tsunami short-circuit: dispositive_at_standard_3 → DISCRETIONARY at
 *     Standard 3, skip ΔT (locked decision #2).
 *
 * Public API:
 *   HazardEngine.init()                         — bootstrap from window.JOSH_DATA
 *   HazardEngine.evaluateProject(project)       — main entry; returns
 *                                                  { results: {hazard_id: HazardResult},
 *                                                    controlling_hazard: string|null,
 *                                                    tier: string }
 *
 * UMD: works in browser (window.HazardEngine) and node (require()).
 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory(require('./hooks'));
  } else {
    root.HazardEngine = factory(root.Hooks);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (Hooks) {
  'use strict';

  // ─── Constants ──────────────────────────────────────────────────────────────
  var MPH_TO_MPS = 0.44704;          // exact — matches wildland.py _MPH_TO_MPS
  var SECONDS_PER_HOUR = 3600;

  // ─── Module state (populated by init()) ─────────────────────────────────────
  var _graph = null;          // JOSH_DATA.graph
  var _params = null;         // JOSH_DATA.parameters
  var _polygons = null;       // JOSH_DATA.hazard_polygons
  var _configs = null;        // JOSH_DATA.hazard_configs
  var _adjacency = null;      // Map<nodeId, [{v, edge}]>
  var _nodeMap = null;        // Map<nodeId, {lat, lon}>
  var _edgeMap = null;        // Map<osmid_str, edge>
  var _exitSet = null;        // Set<nodeId>
  var _ready = false;

  // ─── Public API ─────────────────────────────────────────────────────────────

  function init(joshData) {
    var d = joshData || (typeof window !== 'undefined' ? window.JOSH_DATA : null);
    if (!d) {
      throw new Error('HazardEngine.init: no JOSH_DATA available');
    }
    if (!d.graph || !d.parameters) {
      throw new Error('HazardEngine.init: JOSH_DATA missing graph or parameters');
    }
    _graph = d.graph;
    _params = d.parameters;
    _polygons = d.hazard_polygons || {};
    _configs = d.hazard_configs || {};

    _nodeMap = new Map();
    for (var i = 0; i < _graph.nodes.length; i++) {
      var n = _graph.nodes[i];
      _nodeMap.set(n.id, { lat: n.lat, lon: n.lon });
    }

    _adjacency = _buildAdjacency(_graph.edges);
    _edgeMap = new Map();
    for (var j = 0; j < _graph.edges.length; j++) {
      var e = _graph.edges[j];
      if (e.osmid != null) _edgeMap.set(String(e.osmid), e);
    }

    _exitSet = new Set(_graph.exit_nodes || []);

    _validateHookReferences(_configs);
    _ready = true;
  }

  function _validateHookReferences(configs) {
    var missing = [];
    for (var hid in configs) {
      if (!Object.prototype.hasOwnProperty.call(configs, hid)) continue;
      var cfg = configs[hid];
      var hooks = cfg.hooks || {};
      for (var phase in hooks) {
        if (!Object.prototype.hasOwnProperty.call(hooks, phase)) continue;
        var name = hooks[phase];
        if (!Hooks.has(name)) {
          missing.push(hid + '.' + phase + ' → ' + name);
        }
      }
    }
    if (missing.length > 0) {
      throw new Error(
        'HazardEngine.init: HazardConfig references missing hooks:\n  ' +
        missing.join('\n  ')
      );
    }
  }

  function _ensureReady() {
    if (!_ready) init();
  }

  /**
   * Evaluate a project across every configured hazard.
   *
   * @param {object} project - { id, lat, lng, units, stories, additional_egress_points? }
   * @returns {object} { results: {hazard_id: HazardResult},
   *                     controlling_hazard: string|null,
   *                     tier: 'DISCRETIONARY'|'MINISTERIAL_WITH_STANDARD_CONDITIONS'|'MINISTERIAL' }
   */
  function evaluateProject(project) {
    _ensureReady();
    if (!project || project.lat == null || project.lng == null || project.units == null) {
      throw new Error('HazardEngine.evaluateProject: project requires lat, lng, units');
    }

    // Standard 1 — size gate. If project below threshold, short-circuit to MINISTERIAL.
    var unitThreshold = (_params && _params.unit_threshold) || 15;
    if (project.units < unitThreshold) {
      return {
        results: {},
        controlling_hazard: null,
        tier: 'MINISTERIAL',
        reason: 'size_gate_not_met'
      };
    }

    var results = {};
    for (var hazardId in _configs) {
      if (!Object.prototype.hasOwnProperty.call(_configs, hazardId)) continue;
      var cfg = _configs[hazardId];
      var features = (_polygons[hazardId] && _polygons[hazardId].feature_collection) || null;
      results[hazardId] = _evaluateSingleHazard(project, hazardId, cfg, features);
    }

    var controlling = _pickControlling(results);
    var tier = _tierFromResults(results);

    // Mark the controlling result
    for (var hid in results) {
      if (Object.prototype.hasOwnProperty.call(results, hid)) {
        results[hid].controls = (hid === controlling);
      }
    }

    return {
      results: results,
      controlling_hazard: controlling,
      tier: tier
    };
  }

  // ─── Per-hazard evaluation (the 5-step algorithm) ───────────────────────────

  function _evaluateSingleHazard(project, hazardId, cfg, features) {
    // Phase 3: classify
    var zone = _classify(project, features, cfg);

    // Tsunami short-circuit — locked decision #2
    if (cfg.dispositive_at_standard_3 && zone !== 'outside') {
      return _buildDispositiveResult(hazardId, zone, cfg, features, project);
    }

    // Phase 5a: egress window → threshold
    var maxProjectShare = (_params && _params.max_project_share) || 0.05;
    var windowMin = _egressWindow(project, zone, features, cfg);
    var threshold = windowMin * maxProjectShare;

    // Per-hazard graph reweighting + Dijkstra
    var degradedEdges = _applyDegradation(features, cfg, zone);
    var paths = _dijkstraToExits(project, degradedEdges);

    if (paths.length === 0) {
      // No path to any exit. Build a degenerate result that flags as failed.
      return _buildBlockedResult(hazardId, zone, cfg, threshold);
    }

    // Sort paths worst-first (max delta_t) so paths[0] is the "controlling" path
    var projectVehicles = _computeProjectVehicles(project, cfg.mobilization);
    var egressMinutes = _computeEgressPenalty(project, _params);
    for (var i = 0; i < paths.length; i++) {
      paths[i].project_vehicles = projectVehicles;
      paths[i].delta_t = _computeDeltaT(projectVehicles, paths[i].bottleneck_eff_cap_vph, egressMinutes);
    }
    paths.sort(function (a, b) { return b.delta_t - a.delta_t; });

    // build_result is engine-internal (NOT a hook). Constructs the BaseResult
    // fields then applies declarative result_extras from cfg.
    return _buildResult(hazardId, zone, paths, paths[0].delta_t, threshold, cfg, features, project);
  }

  // ─── Phase dispatchers (hook if registered, else default) ───────────────────

  function _classify(project, features, cfg) {
    var hookName = (cfg.hooks && cfg.hooks.classify) || 'default.classify';
    var point = { lat: project.lat, lng: project.lng };
    return Hooks.call(hookName, point, features, cfg);
  }

  function _egressWindow(project, zone, features, cfg) {
    var hookName = (cfg.hooks && cfg.hooks.egress_window) || 'default.egress_window';
    var point = { lat: project.lat, lng: project.lng };
    var params = _mergedParams(cfg);
    return Hooks.call(hookName, point, zone, features, params);
  }

  function _degradationFor(edge, zone, features, cfg) {
    var hookName = (cfg.hooks && cfg.hooks.degradation) || 'default.degradation';
    var params = _mergedParams(cfg);
    return Hooks.call(hookName, edge, zone, features, params);
  }

  function _mergedParams(cfg) {
    var p = {};
    p.degradation_by_zone = cfg.degradation || {};
    p.safe_egress_window_by_zone = cfg.safe_egress_window || {};
    if (cfg.runtime_extras) {
      for (var k in cfg.runtime_extras) {
        if (Object.prototype.hasOwnProperty.call(cfg.runtime_extras, k)) {
          p[k] = cfg.runtime_extras[k];
        }
      }
    }
    return p;
  }

  // ─── Per-hazard graph reweighting ───────────────────────────────────────────
  //
  // Returns a Map<edgeKey, {degradation, base_capacity_vph, eff_cap_vph}> capturing
  // the per-edge hazard-aware capacity. Dijkstra uses travel_time_s (unaffected
  // by hazard) for routing weight; the result is used at bottleneck-pick time
  // to compute ΔT.
  //
  // Edge key: `${u}->${v}` (graph is directed by OSMnx convention).

  function _applyDegradation(features, cfg, zone) {
    // STAGE 1 NOTE: For wildfire, graph.json has pre-baked per-edge `eff_cap_vph`
    // (legacy wildland.py bake — pipeline already applied FHSZ degradation per edge).
    // When the hazard registers no degradation hook AND edges have pre-baked
    // eff_cap_vph, use it directly — avoids double-application.
    //
    // STAGE 3+ NOTE: This won't scale to multi-hazard as-is. When flood ships,
    // each hazard will need either:
    //   (a) per-hazard pre-baked eff_cap fields in graph.json (eff_cap_vph_wildfire,
    //       eff_cap_vph_flood, etc.), OR
    //   (b) base_capacity_vph in graph.json + engine multiplies by cfg.degradation
    //       per-zone at runtime.
    // Either path is a Phase D pipeline change. For Stage 1, the wildfire-only
    // case uses the legacy pre-baked field.
    var degraded = new Map();
    var hasHook = !!(cfg.hooks && cfg.hooks.degradation);

    for (var i = 0; i < _graph.edges.length; i++) {
      var edge = _graph.edges[i];
      var factor, effCap, passable;

      if (hasHook) {
        // Hazard has custom per-edge logic (e.g. flood BFE filter at Stage 3).
        // Hook return value of 0 means the edge is physically impassable
        // (network-cutting semantics — locked decision #6 2B class).
        factor = _degradationFor(edge, zone, features, cfg);
        var baseCap = edge.base_capacity_vph || edge.eff_cap_vph || 0;
        effCap = baseCap * factor;
        passable = factor > 0;
      } else if (edge.eff_cap_vph != null) {
        // Stage 1 wildfire (pre-baked path): use the pipeline's eff_cap_vph.
        // ALL edges are passable for Dijkstra routing — matches legacy
        // nx.shortest_path which weights paths by travel_time, NOT capacity.
        // 0-cap edges (missing data / unmapped) are routed through but
        // excluded from bottleneck selection in _findBottleneck.
        // This is the "capacity-degrading" 2A class per locked decision #6.
        effCap = edge.eff_cap_vph;
        factor = effCap > 0 ? (edge.haz_deg != null ? edge.haz_deg : 1.0) : 0;
        passable = true;
      } else {
        // No pre-bake, no hook — apply per-zone factor to base capacity
        factor = (cfg.degradation && cfg.degradation[zone]) || 1.0;
        var baseCap2 = edge.base_capacity_vph || edge.capacity_vph || 0;
        effCap = baseCap2 * factor;
        passable = factor > 0;
      }

      degraded.set(_edgeKey(edge.u, edge.v), {
        degradation: factor,
        eff_cap_vph: effCap,
        passable: passable
      });
    }
    return degraded;
  }

  function _edgeKey(u, v) { return String(u) + '->' + String(v); }

  // ─── Dijkstra ───────────────────────────────────────────────────────────────

  function _dijkstraToExits(project, degradedEdges) {
    var startNode = _nearestNode(project.lat, project.lng);
    if (startNode == null) return [];

    var dist = new Map();
    var prev = new Map();
    var pq = new _MinHeap();
    dist.set(startNode, 0);
    pq.push(0, startNode);

    while (pq.size > 0) {
      var top = pq.pop();
      var d = top[0];
      var u = top[1];
      if (d > (dist.get(u) || Infinity)) continue;

      var neighbors = _adjacency.get(u) || [];
      for (var i = 0; i < neighbors.length; i++) {
        var nbr = neighbors[i];
        var edge = nbr.edge;
        var ek = _edgeKey(edge.u, edge.v);
        var degInfo = degradedEdges.get(ek);
        if (!degInfo || !degInfo.passable) continue;

        var travelTimeS = _edgeTravelTime(edge);
        if (travelTimeS <= 0) continue;
        var alt = d + travelTimeS;
        if (alt < (dist.get(nbr.v) || Infinity)) {
          dist.set(nbr.v, alt);
          prev.set(nbr.v, { u: u, edge: edge });
          pq.push(alt, nbr.v);
        }
      }
    }

    // Reconstruct paths to each exit node
    var paths = [];
    var exitsArray = Array.from(_exitSet);
    for (var k = 0; k < exitsArray.length; k++) {
      var exitNode = exitsArray[k];
      if (exitNode === startNode) continue;
      if (!dist.has(exitNode)) continue;
      var pathEdges = _reconstructPath(prev, startNode, exitNode);
      if (pathEdges.length === 0) continue;

      var bottleneck = _findBottleneck(pathEdges, degradedEdges);
      paths.push({
        travel_time_s: dist.get(exitNode),
        exit_node_id: exitNode,
        path_edges: pathEdges,
        bottleneck_osmid: bottleneck.osmid,
        bottleneck_name: bottleneck.name,
        bottleneck_eff_cap_vph: bottleneck.eff_cap_vph,
        bottleneck_degradation: bottleneck.degradation,
        bottleneck_edge: bottleneck.edge,           // for cross-street enrichment
        path_wgs84_coords: _pathToWgs84(pathEdges)
      });
    }

    // Filter: User Equilibrium semantics — drop paths > 3.5× fastest exit time
    if (paths.length === 0) return [];
    var minTt = Infinity;
    for (var p = 0; p < paths.length; p++) minTt = Math.min(minTt, paths[p].travel_time_s);
    var maxPathRatio = (_params && _params.max_path_length_ratio) || 3.5;
    return paths.filter(function (path) {
      return path.travel_time_s <= minTt * maxPathRatio;
    });
  }

  function _edgeTravelTime(edge) {
    // Accept both `len_m` (canonical graph.json field) and `length_m` (alt).
    var lenM = edge.len_m != null ? edge.len_m : (edge.length_m || edge.length || 0);
    var spdMph = edge.speed_mph || edge.speed_limit || 25;
    var spdMps = spdMph * MPH_TO_MPS;
    return spdMps > 0 ? (lenM / spdMps) : 0;
  }

  function _reconstructPath(prev, start, end) {
    var edges = [];
    var cur = end;
    while (cur !== start) {
      var step = prev.get(cur);
      if (!step) return [];   // unreachable
      edges.unshift(step.edge);
      cur = step.u;
    }
    return edges;
  }

  function _findBottleneck(pathEdges, degradedEdges) {
    // Three-pass bottleneck identification matching legacy wildland.py:
    //   Pass 1: find minimum eff_cap_vph among non-zero-cap edges.
    //   Pass 2: find the FIRST osmid with that min cap (legacy `min()` picks
    //           first; multiple osmids can tie at the min for non-FHSZ paths
    //           where every two-lane @25mph hits 1125).
    //   Pass 3: find the LAST edge (u/v) whose osmid matches that first osmid
    //           (legacy stores osmid_to_uv[oid] = (u,v) on every iter, so
    //           multi-segment ways like Marin Ave end with last-segment u/v).
    // Cross-street enrichment runs at that last segment's nodes.
    var minCap = Infinity;
    for (var i = 0; i < pathEdges.length; i++) {
      var degInfo1 = degradedEdges.get(_edgeKey(pathEdges[i].u, pathEdges[i].v));
      if (degInfo1 && degInfo1.eff_cap_vph > 0 && degInfo1.eff_cap_vph < minCap) {
        minCap = degInfo1.eff_cap_vph;
      }
    }
    if (minCap === Infinity) {
      return {
        osmid: null, name: '(no bottleneck)', eff_cap_vph: 0, degradation: 1.0, edge: null
      };
    }

    var firstOsmid = null;
    for (var j = 0; j < pathEdges.length; j++) {
      var degInfo2 = degradedEdges.get(_edgeKey(pathEdges[j].u, pathEdges[j].v));
      if (degInfo2 && degInfo2.eff_cap_vph === minCap) {
        firstOsmid = pathEdges[j].osmid;
        break;
      }
    }

    var bottleneckEdge = null;
    for (var k = 0; k < pathEdges.length; k++) {
      if (pathEdges[k].osmid === firstOsmid) bottleneckEdge = pathEdges[k];
    }
    if (!bottleneckEdge) {
      return {
        osmid: null, name: '(no bottleneck)', eff_cap_vph: 0, degradation: 1.0, edge: null
      };
    }

    var degInfo3 = degradedEdges.get(_edgeKey(bottleneckEdge.u, bottleneckEdge.v));
    return {
      osmid: bottleneckEdge.osmid,
      name: bottleneckEdge.name || bottleneckEdge.bottleneck_name || '(unnamed)',
      eff_cap_vph: degInfo3 ? degInfo3.eff_cap_vph : minCap,
      degradation: degInfo3 ? degInfo3.degradation : 1.0,
      edge: bottleneckEdge
    };
  }

  function _pathToWgs84(pathEdges) {
    // Concatenate edge geometries into a single polyline.
    // graph.json stores per-edge geometry under `geom` as [[lat, lon], ...].
    // Falls back to node endpoints when geom is missing/null.
    var coords = [];
    for (var i = 0; i < pathEdges.length; i++) {
      var edge = pathEdges[i];
      var geom = edge.geom || edge.geometry_wgs84;
      if (Array.isArray(geom) && geom.length > 0) {
        for (var j = 0; j < geom.length; j++) {
          if (i > 0 && j === 0) continue;   // skip duplicate join points
          coords.push(geom[j]);
        }
      } else {
        var uNode = _nodeMap.get(edge.u);
        var vNode = _nodeMap.get(edge.v);
        if (i === 0 && uNode) coords.push([uNode.lat, uNode.lon]);
        if (vNode) coords.push([vNode.lat, vNode.lon]);
      }
    }
    return coords;
  }

  // ─── ΔT formula (un-hookable) ───────────────────────────────────────────────

  function _computeProjectVehicles(project, mobilization) {
    var vpu = (_params && _params.vehicles_per_unit) || 1.9;
    return project.units * vpu * mobilization;
  }

  function _computeEgressPenalty(project, params) {
    var ep = (params && params.egress_penalty) || {};
    var thresholdStories = ep.threshold_stories || 4;
    if (!project.stories || project.stories < thresholdStories) return 0;
    var minutesPerStory = ep.minutes_per_story || 1.5;
    var maxMinutes = ep.max_minutes || 12;
    return Math.min(project.stories * minutesPerStory, maxMinutes);
  }

  function _computeDeltaT(projectVehicles, effCapVph, egressMinutes) {
    if (effCapVph <= 0) return Infinity;
    return (projectVehicles / effCapVph) * 60 + egressMinutes;
  }

  // ─── Dispositive + blocked result constructors ──────────────────────────────

  function _buildDispositiveResult(hazardId, zone, cfg, features, project) {
    // BaseResult fields. Hazard-specific extras (in_cgs_tha, eva_type,
    // delta_t_informational, etc.) come from cfg.result_extras via the
    // declarative DSL — same pattern as non-dispositive build_result.
    var result = {
      type: hazardId,
      controls: true,        // dispositive always controls
      flagged: true,
      zone: zone,
      zone_label: (cfg.zone_labels && cfg.zone_labels[zone])
        || (cfg.labels && cfg.labels[zone])
        || zone,
      route_coords: null
    };
    _applyResultExtras(result, cfg, zone, features, project);
    return result;
  }

  function _buildBlockedResult(hazardId, zone, cfg, threshold) {
    // No path to any exit (e.g. flood removed every road). Treat as DISCRETIONARY.
    var result = {
      type: hazardId,
      controls: false,
      flagged: true,
      zone: zone,
      zone_label: (cfg.zone_labels && cfg.zone_labels[zone])
        || (cfg.labels && cfg.labels[zone])
        || zone,
      degradation: (cfg.degradation && cfg.degradation[zone]) || 1.0,
      egress_window_min: (cfg.safe_egress_window && cfg.safe_egress_window[zone]) || 120,
      threshold: threshold,
      delta_t: Infinity,
      bottleneck: { name: '(no viable path)', eff_cap_vph: 0, vehicles: 0 },
      route_coords: null
    };
    _applyResultExtras(result, cfg, zone, null);
    return result;
  }

  // ─── _buildResult (engine-internal — NOT a hook) ────────────────────────────
  //
  // Constructs the universal BaseResult fields, then applies declarative
  // result_extras from cfg to populate variant-specific fields. See
  // docs/plan-multihazard-stage-1-hooks.md §5 for the DSL spec.

  function _buildResult(hazardId, zone, paths, deltaT, threshold, cfg, features, project) {
    var bottleneck = _buildBottleneckFromPaths(paths);
    var routeCoords = (paths && paths.length > 0) ? _pathToCoords(paths[0]) : null;

    var result = {
      type: hazardId,
      controls: false,            // set later by _pickControlling
      flagged: deltaT > threshold,
      zone: zone,
      zone_label: (cfg.zone_labels && cfg.zone_labels[zone])
        || (cfg.labels && cfg.labels[zone])
        || zone,
      degradation: (cfg.degradation && cfg.degradation[zone]) != null
        ? cfg.degradation[zone] : 1.0,
      egress_window_min: (cfg.safe_egress_window && cfg.safe_egress_window[zone]) != null
        ? cfg.safe_egress_window[zone] : 120,
      threshold: _round2(threshold),
      delta_t: _round2(deltaT),
      bottleneck: bottleneck,
      route_coords: routeCoords
    };

    _applyResultExtras(result, cfg, zone, features, project);
    return result;
  }

  function _buildBottleneckFromPaths(paths) {
    if (!paths || paths.length === 0) {
      return { name: '(no path)', eff_cap_vph: 0, vehicles: 0 };
    }
    var worst = paths[0];     // engine sorts paths worst-first before calling
    var name = worst.bottleneck_name || '(unknown)';
    // Cross-street enrichment — produces "Marin Avenue at Shattuck Avenue / The Circle"
    // matching the legacy wildland.py _get_cross_streets behavior. The brief
    // renderer + golden files expect this composite form for legal traceability.
    if (worst.bottleneck_edge) {
      var crosses = _crossStreetsAt(worst.bottleneck_edge);
      // Sort alphabetically — u/v direction is non-deterministic under
      // undirected routing, so we need a stable order to match goldens.
      var names = [crosses.a, crosses.b].filter(function (s) { return !!s; }).sort();
      if (names.length === 2) {
        name = name + ' at ' + names[0] + ' / ' + names[1];
      } else if (names.length === 1) {
        name = name + ' at ' + names[0];
      }
    }
    return {
      name: name,
      eff_cap_vph: Math.round(worst.bottleneck_eff_cap_vph || 0),
      vehicles: Math.round(worst.project_vehicles || 0)
    };
  }

  /**
   * Find the most common cross-street name at each endpoint of an edge,
   * excluding the edge's own name. Mirrors wildland.py _get_cross_streets.
   */
  function _crossStreetsAt(edge) {
    var ownName = edge.name || '';
    function bestCrossAtNode(nodeId) {
      var counts = Object.create(null);
      var neighbors = _adjacency.get(nodeId) || [];
      // Also check reverse edges (engine's adjacency is directed; cross-streets
      // are direction-agnostic)
      for (var i = 0; i < _graph.edges.length; i++) {
        var e = _graph.edges[i];
        if (e.u !== nodeId && e.v !== nodeId) continue;
        var nm = e.name;
        if (!nm || nm === ownName) continue;
        counts[nm] = (counts[nm] || 0) + 1;
      }
      var best = null;
      var bestCount = 0;
      var keys = Object.keys(counts).sort();   // alphabetical tiebreak
      for (var j = 0; j < keys.length; j++) {
        if (counts[keys[j]] > bestCount) {
          best = keys[j];
          bestCount = counts[keys[j]];
        }
      }
      return best || '';
    }
    return {
      a: bestCrossAtNode(edge.u),
      b: bestCrossAtNode(edge.v)
    };
  }

  function _pathToCoords(path) {
    return path && Array.isArray(path.path_wgs84_coords) ? path.path_wgs84_coords : null;
  }

  // ─── result_extras DSL interpreter ──────────────────────────────────────────
  //
  // Iterates cfg.result_extras and populates result[fieldName] for each entry.
  // The `from:` type discriminator picks the resolver function.

  function _applyResultExtras(result, cfg, zone, features, project, telemetry) {
    var extras = (cfg && cfg.result_extras) || {};
    var ctx = {
      zone: zone,
      features: features,
      point: project ? { lat: project.lat, lng: project.lng } : null,
      cfg: cfg,
      telemetry: telemetry || {}
    };
    for (var fieldName in extras) {
      if (!Object.prototype.hasOwnProperty.call(extras, fieldName)) continue;
      result[fieldName] = _resolveResultExtra(extras[fieldName], ctx);
    }
  }

  function _resolveResultExtra(spec, ctx) {
    switch (spec.from) {
      case 'zone_lookup': {
        var v = spec.table ? spec.table[ctx.zone] : undefined;
        return v !== undefined ? v : (spec.on_missing !== undefined ? spec.on_missing : null);
      }
      case 'containing_feature_attribute': {
        if (!ctx.point || !ctx.features) return spec.on_outside || null;
        var hits = _featuresContaining(ctx.point.lng, ctx.point.lat, ctx.features);
        if (hits.length === 0) return spec.on_outside !== undefined ? spec.on_outside : null;
        var props = hits[0].properties || {};
        var attrVal = props[spec.attribute];
        return attrVal !== undefined ? attrVal : null;
      }
      case 'all_containing_features': {
        if (!ctx.point || !ctx.features) return [];
        var matches = _featuresContaining(ctx.point.lng, ctx.point.lat, ctx.features);
        return matches.map(function (f) {
          var out = {};
          var p = f.properties || {};
          for (var key in spec.project) {
            if (Object.prototype.hasOwnProperty.call(spec.project, key)) {
              out[key] = p[spec.project[key]];
            }
          }
          return out;
        });
      }
      case 'nearest_feature_attribute': {
        // Implemented in Stage 8 (GasHazmatAdapter) — requires nearest-feature
        // distance computation against LineString geometries.
        throw new Error(
          'result_extras.from=nearest_feature_attribute not implemented yet '
          + '(lands in Stage 8 with GasHazmatAdapter)'
        );
      }
      case 'in_zone':
        return ctx.zone != null && ctx.zone !== 'outside';
      case 'literal':
        return spec.value;
      case 'runtime_extras':
        return (ctx.cfg.runtime_extras || {})[spec.key];
      case 'engine_telemetry':
        return (ctx.telemetry || {})[spec.key];
      default:
        throw new Error(
          'result_extras: unknown from=' + JSON.stringify(spec.from)
          + ' (valid: zone_lookup, containing_feature_attribute, '
          + 'all_containing_features, nearest_feature_attribute, in_zone, '
          + 'literal, runtime_extras, engine_telemetry)'
        );
    }
  }

  // ─── Numeric formatting helpers ─────────────────────────────────────────────

  function _round2(n) {
    if (n == null || !isFinite(n)) return n;
    return Math.round(n * 100) / 100;
  }

  // ─── Geometry helpers (mirrors _defaults.js for engine self-containment) ────

  function _pointInRing(lng, lat, ring) {
    var inside = false;
    var n = ring.length;
    for (var i = 0, j = n - 1; i < n; j = i++) {
      var xi = ring[i][0], yi = ring[i][1];
      var xj = ring[j][0], yj = ring[j][1];
      var intersect = ((yi > lat) !== (yj > lat)) &&
        (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  function _pointInPolygon(lng, lat, geometry) {
    if (!geometry || !geometry.coordinates) return false;
    var polys;
    if (geometry.type === 'Polygon') polys = [geometry.coordinates];
    else if (geometry.type === 'MultiPolygon') polys = geometry.coordinates;
    else return false;
    for (var p = 0; p < polys.length; p++) {
      var rings = polys[p];
      if (rings.length === 0) continue;
      if (!_pointInRing(lng, lat, rings[0])) continue;
      var inHole = false;
      for (var h = 1; h < rings.length; h++) {
        if (_pointInRing(lng, lat, rings[h])) { inHole = true; break; }
      }
      if (!inHole) return true;
    }
    return false;
  }

  function _featuresContaining(lng, lat, featureCollection) {
    if (!featureCollection || !Array.isArray(featureCollection.features)) return [];
    var hits = [];
    for (var i = 0; i < featureCollection.features.length; i++) {
      var feat = featureCollection.features[i];
      if (_pointInPolygon(lng, lat, feat.geometry)) hits.push(feat);
    }
    return hits;
  }

  // ─── Controlling hazard + tier ──────────────────────────────────────────────

  function _pickControlling(results) {
    // Locked decision #7: worst-case single hazard drives tier.
    // (a) any dispositive result controls automatically
    // (b) otherwise pick max(delta_t / threshold)
    var dispositive = null;
    var worstRatio = -1;
    var worstHazard = null;
    for (var hid in results) {
      if (!Object.prototype.hasOwnProperty.call(results, hid)) continue;
      var r = results[hid];
      if (r.dispositive) {
        dispositive = hid;
        continue;
      }
      if (r.threshold && r.delta_t != null && isFinite(r.delta_t)) {
        var ratio = r.delta_t / r.threshold;
        if (ratio > worstRatio) {
          worstRatio = ratio;
          worstHazard = hid;
        }
      }
    }
    return dispositive || worstHazard;
  }

  function _tierFromResults(results) {
    var anyFlagged = false;
    var anyApplicable = false;
    for (var hid in results) {
      if (!Object.prototype.hasOwnProperty.call(results, hid)) continue;
      var r = results[hid];
      if (r.flagged) anyFlagged = true;
      if (!r.excluded) anyApplicable = true;
    }
    if (anyFlagged) return 'DISCRETIONARY';
    if (anyApplicable) return 'MINISTERIAL_WITH_STANDARD_CONDITIONS';
    return 'MINISTERIAL';
  }

  // ─── Graph helpers ──────────────────────────────────────────────────────────

  function _buildAdjacency(edges) {
    // Build UNDIRECTED adjacency — matches legacy wildland.py which calls
    // G.to_undirected() before Dijkstra. graph.json stores both directions
    // for ~84% of edges; the remainder (one-way streets, dead-ends) only have
    // one direction listed but need to be traversable both ways for routing
    // parity with the legacy pipeline. Dedupe via (u,v) pair tracking so
    // already-bidirectional edges aren't doubled.
    var adj = new Map();
    var seen = new Set();
    for (var i = 0; i < edges.length; i++) {
      var e = edges[i];
      var fwdKey = e.u + '->' + e.v;
      var revKey = e.v + '->' + e.u;
      if (!seen.has(fwdKey)) {
        if (!adj.has(e.u)) adj.set(e.u, []);
        adj.get(e.u).push({ v: e.v, edge: e });
        seen.add(fwdKey);
      }
      if (!seen.has(revKey)) {
        if (!adj.has(e.v)) adj.set(e.v, []);
        adj.get(e.v).push({ v: e.u, edge: e });
        seen.add(revKey);
      }
    }
    return adj;
  }

  function _nearestNode(lat, lng) {
    // Haversine-equivalent for nearest-node — at latitudes far from the
    // equator, naive planar (lat² + lng²) gives wrong answers because 1° lng
    // is physically shorter than 1° lat by cos(lat). At Berkeley (37.86° N),
    // cos ≈ 0.79 — naive planar would prefer nodes off in lng over lat by ~26%,
    // picking a different starting node than the legacy OSMnx projected-meters
    // path. Use latitude-scaled planar (sufficient for nearest-node within a city).
    var coslat = Math.cos(lat * Math.PI / 180);
    var best = null;
    var bestD = Infinity;
    var nodes = _graph.nodes;
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      var dLat = n.lat - lat;
      var dLng = (n.lon - lng) * coslat;
      var d = dLat * dLat + dLng * dLng;
      if (d < bestD) { bestD = d; best = n.id; }
    }
    return best;
  }

  // ─── Min-heap (binary) ──────────────────────────────────────────────────────

  function _MinHeap() {
    this._h = [];
  }
  _MinHeap.prototype = {
    push: function (cost, id) {
      this._h.push([cost, id]);
      this._bubbleUp(this._h.length - 1);
    },
    pop: function () {
      var top = this._h[0];
      var last = this._h.pop();
      if (this._h.length > 0) { this._h[0] = last; this._siftDown(0); }
      return top;
    },
    get size() { return this._h.length; },
    _bubbleUp: function (i) {
      var h = this._h;
      while (i > 0) {
        var p = (i - 1) >> 1;
        if (h[p][0] <= h[i][0]) break;
        var tmp = h[p]; h[p] = h[i]; h[i] = tmp;
        i = p;
      }
    },
    _siftDown: function (i) {
      var h = this._h;
      var n = h.length;
      while (true) {
        var m = i;
        var l = 2 * i + 1, r = 2 * i + 2;
        if (l < n && h[l][0] < h[m][0]) m = l;
        if (r < n && h[r][0] < h[m][0]) m = r;
        if (m === i) break;
        var tmp = h[m]; h[m] = h[i]; h[i] = tmp;
        i = m;
      }
    }
  };

  // ─── Exports ────────────────────────────────────────────────────────────────

  return {
    init: init,
    evaluateProject: evaluateProject,
    // Test/debug introspection — not part of the production API contract
    _state: function () {
      return {
        ready: _ready,
        node_count: _graph ? _graph.nodes.length : 0,
        edge_count: _graph ? _graph.edges.length : 0,
        exit_count: _exitSet ? _exitSet.size : 0,
        hazard_count: _configs ? Object.keys(_configs).length : 0
      };
    },
    _reset: function () { _ready = false; _graph = _params = _polygons = _configs = null; }
  };
}));

// ────────────────────────────────────────────────────────────────────────────

// ── Brief modal overlay injector ─────────────────────────────────────────────

(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var _tmp = document.createElement('div');
    _tmp.innerHTML = `<div id="josh-brief-modal" style="
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
</div>`;
    document.body.appendChild(_tmp.firstElementChild);
  });
})();

// ────────────────────────────────────────────────────────────────────────────

// ── Brief modal controller ───────────────────────────────────────────────────

(function () {
  window.joshBrief = {
    // show(html, filename)  — sidebar.js / BriefRenderer path: html is the full HTML
    //                         string generated on-the-fly; filename is for future use.
    // show(filename)         — legacy pipeline path: filename is a key in
    //                         JOSH_DATA.briefs (pre-baked HTML).
    // Both calling conventions are supported so existing brief_v3_*.html links
    // (which call show(filename)) continue to work alongside the on-demand path.
    show: function (htmlOrKey, _filename) {
      var html;
      if (htmlOrKey && htmlOrKey.trimStart().startsWith('<')) {
        // Direct HTML string — from sidebar.js _openBrief() via BriefRenderer.render()
        html = htmlOrKey;
      } else {
        // Filename key — look up pre-baked HTML in JOSH_DATA.briefs
        var briefs = window.JOSH_DATA && window.JOSH_DATA.briefs;
        html = briefs && briefs[htmlOrKey];
      }
      if (!html) { console.warn('joshBrief: no brief HTML for', htmlOrKey); return; }
      var frame = document.getElementById('josh-brief-frame');
      frame.srcdoc = html;
      document.getElementById('josh-brief-modal').style.display = 'block';
    }
  };

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('a[href^="brief_v3_"]').forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        window.joshBrief.show(link.getAttribute('href'));
      });
    });
    var modal = document.getElementById('josh-brief-modal');
    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === this) this.style.display = 'none';
      });
    }
  });
})();

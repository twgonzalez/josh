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

// CommonJS export for Node.js test runner
if (typeof module !== "undefined" && module.exports) {
  module.exports = { WhatIfEngine };
}

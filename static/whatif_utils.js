// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH What-If Engine — Drift-Free Utilities
 *
 * SOURCE FILE — included verbatim into static/whatif_engine.js by
 * agents/export.export_whatif_engine_js().  Do NOT edit whatif_engine.js
 * directly; regenerate it via:
 *
 *   uv run python main.py analyze --city "Berkeley"
 *
 * These functions encode NO algorithm constants (no thresholds, no
 * mobilization rates, no speed defaults).  They are pure geometry,
 * data structures, and graph utilities that cannot drift from Python
 * regardless of parameter changes.
 *
 * Functions that reference _nodeMap / _adjacency expect those module-level
 * variables to be in scope — they are declared in the IIFE header emitted
 * by export_whatif_engine_js().
 *
 * Functions that reference MPH_TO_MPS / EARTH_RADIUS_M expect those constants
 * to be in scope — they are also declared in the IIFE header:
 *   const MPH_TO_MPS     = 0.44704;
 *   const EARTH_RADIUS_M = 6_371_000;
 */

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

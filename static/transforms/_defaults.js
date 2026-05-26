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

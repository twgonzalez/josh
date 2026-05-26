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

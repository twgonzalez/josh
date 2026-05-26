// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH Sidebar — Phase 2
 *
 * Fixed left sidebar (320px) that is the single entry point for all project work.
 * Replaces the what-if FAB + floating panel, the Saved Analyses FAB + panel,
 * and the top-right Folium-generated official project panel.
 *
 * Persistence: FSAPI per-project JSON files + IndexedDB file-handle storage.
 * Fallback for non-FSAPI browsers: <input type=file> open + Blob download save.
 *
 * Projects from JOSH_DATA.projects (pipeline seeds) and browser-created projects
 * are identical in the UI — same full feature set: AntPath routes, detail card,
 * determination brief.
 *
 * Architecture:
 *   window.joshSidebar = { init, onPinPlaced, getProjects, selectProject }
 *   Results normalized to file-format schema (snake_case) on analysis.
 *   Map bridge calls (_drawRoutes, _enterPinMode) are no-ops until Phase 3 wires
 *   window._joshMap into the page.
 *
 * Run tests: node --test tests/test_sidebar.js
 *
 * Phase 4 additions:
 *   - Dirty tracking: _dirtyIds Set, _markDirty/_markClean, ● Save indicator
 *   - Session restore banner: _renderRestoreBanner + _setRestoreBanner export
 */

(function () {
  'use strict';

  // ── Constants ─────────────────────────────────────────────────────────────────
  const SCHEMA_V   = 1;
  const SIDEBAR_W  = 320;
  const IDB_NAME   = 'josh_sidebar_v1';
  const IDB_STORE  = 'handles';

  // ── Data accessors ─────────────────────────────────────────────────────────────
  function _jd()        { return (typeof window !== 'undefined' && window.JOSH_DATA) || {}; }
  function _citySlug()  { return _jd().city_slug  || 'city'; }
  function _cityName()  { return _jd().city_name  || 'City'; }
  function _paramsVer() { return (_jd().parameters || {}).parameters_version || _jd().parameters_version || ''; }
  function _joshVer()   { return _jd().josh_version || ''; }
  function _params()    { return _jd().parameters || {}; }

  // ── State ─────────────────────────────────────────────────────────────────────
  let _projects        = [];    // normalized project objects (see file format, spec §7)
  let _selectedId      = null;  // id of selected project (detail card + routes shown)
  let _formMode        = null;  // null | 'new' | 'edit'
  let _formProjectId   = null;  // id being edited (null for new)
  let _formLat         = null;
  let _formLng         = null;
  let _formResult      = null;  // last analysis result while form is open
  let _analyzeTimer    = null;  // debounce for form input → re-analysis
  let _deleteConfirmId = null;  // project awaiting inline delete confirmation
  let _pinMarker       = null;  // Leaflet DivIcon marker for form pin
  let _routeLayers     = [];    // active AntPath + bottleneck Leaflet layers
  let _idb             = null;  // IndexedDB connection (opened lazily)
  let _restoreBanner   = false; // whether to show session-restore banner
  let _dirtyIds        = new Set(); // ids of projects with unsaved changes (have handle, written ≠ memory)

  // v4.12 (all-viable-routes): per-project route visibility toggles.
  // Map<projectId, Set<pathId>> — pathIds present in the set are visible on the map.
  // Absence of an entry for a project = all routes ON (default state).
  // The Set is initialised the first time the user toggles a route; switching
  // projects clears the prior entry so each project starts fresh.
  const _routeToggles  = new Map();

  // v4.13 (route-display-ux): per-project "show all viable routes" toggle.
  // Map<projectId, boolean>. When absent or false, the map displays ONLY the
  // controlling (worst-case) route — the binding evidence for the determination.
  // When true, all viable routes draw as thin context lines with the controlling
  // route still distinguished by weight + gold halo.  Per-route eye toggles only
  // affect map rendering when this flag is true.  Switching projects resets.
  const _showAllRoutes = new Map();

  // ── Route toggle helpers ─────────────────────────────────────────────────────
  // _pathId/_visiblePaths centralise the snake_case/camelCase normalisation and
  // the "all-on by default" semantics so _drawRoutes and _renderDetail stay in lock-step.
  function _pathId(path) { return path && (path.path_id || path.pathId) || ''; }

  function _visiblePaths(projectId, paths) {
    const set = _routeToggles.get(projectId);
    if (!set) return paths.slice();                         // no entry → all visible
    return paths.filter(p => set.has(_pathId(p)));
  }

  // The "controlling" path is the one driving the determination — the path
  // with the highest ΔT (or the only flagged path, when only one is flagged).
  // This is the binding-evidence route under User Equilibrium semantics:
  // some evacuees will take this route and face this delay; the project's
  // contribution to that delay is what the standard measures.
  // Returns null for empty input.
  function _controllingPath(paths) {
    if (!paths || paths.length === 0) return null;
    return paths.reduce((a, b) => (
      (+(b.delta_t || b.delta_t_minutes || 0)) > (+(a.delta_t || a.delta_t_minutes || 0)) ? b : a
    ));
  }

  // ── localStorage auto-save (browser-created projects) ────────────────────────
  // Invisible per-session persistence for projects drawn in the browser.
  // Pipeline seeds come from JOSH_DATA every init and are not written here.
  // See docs/ux-spec-project-workflow-v1.md §7.
  const LS_VERSION = 1;
  function _lsKey() { return 'josh_sb_v' + LS_VERSION + '_' + _citySlug(); }

  function _saveToLocalStorage() {
    try {
      const store = (typeof localStorage !== 'undefined') ? localStorage : null;
      if (!store) return;
      const browserOnly = _projects
        .filter(p => p.source !== 'pipeline')
        .map(p => {
          // Strip runtime-only fields; _handle is non-serializable.
          const copy = {};
          for (const k in p) {
            if (k === '_handle' || k === '_stale') continue;
            copy[k] = p[k];
          }
          return copy;
        });
      store.setItem(_lsKey(), JSON.stringify({ schema_v: SCHEMA_V, projects: browserOnly }));
    } catch (_) { /* localStorage unavailable or quota exceeded — silent */ }
  }

  function _loadFromLocalStorage() {
    try {
      const store = (typeof localStorage !== 'undefined') ? localStorage : null;
      if (!store) return;
      const raw = store.getItem(_lsKey());
      if (!raw) return;
      const obj = JSON.parse(raw);
      if (!obj || (obj.schema_v || 0) > SCHEMA_V) return;
      const now = new Date().toISOString();
      for (const p of (obj.projects || [])) {
        if (_projects.find(existing => existing.id === p.id)) continue;
        _projects.push({
          id:                 p.id || _uuid(),
          schema_v:           SCHEMA_V,
          city_slug:          p.city_slug          || _citySlug(),
          josh_version:       p.josh_version       || _joshVer(),
          parameters_version: p.parameters_version || _paramsVer(),
          name:               p.name    || '',
          address:            p.address || '',
          lat:                p.lat     != null ? +p.lat : null,
          lng:                p.lng     != null ? +p.lng : null,
          units:              +(p.units   || 50),
          stories:            +(p.stories || 4),
          source:             p.source  || 'browser',
          created_at:         p.created_at  || now,
          analyzed_at:        p.analyzed_at || null,
          result:             p.result  || null,
          brief_cache:        p.brief_cache || null,
          _handle:            null,
          _stale:             false,
        });
      }
    } catch (_) { /* corrupt data — silent */ }
  }

  // ── Normalize WhatIfEngine output → file-format schema ───────────────────────
  // WhatIfEngine.evaluateProject() returns mixed camelCase/snake_case.
  // File format (spec §7) and JOSH_DATA.projects use snake_case throughout.
  // All code downstream of analysis uses the normalized form.
  function _normalizeResult(r) {
    if (!r) return null;
    const paths = (r.paths || []).map((p, idx) => ({
      path_id:                   String(p.pathId || p.path_id || ('route_' + (idx + 1))),
      route_id:                  String.fromCharCode(65 + idx),
      cost_s:                    parseFloat((+(p.cost_s || 0)).toFixed(2)),
      delta_t:                   parseFloat((p.delta_t_minutes || 0).toFixed(3)),
      flagged:                   !!p.flagged,
      bottleneck_osmid:          String(p.bottleneckOsmid || p.bottleneck_osmid || ''),
      bottleneck_name:           p.bottleneck_name || '',
      bottleneck_road_type:      p.bottleneck_road_type || '',
      bottleneck_lanes:          +(p.bottleneck_lanes || 0),
      bottleneck_speed:          +(p.bottleneck_speed || 0),
      effective_capacity_vph:    parseFloat((p.bottleneckEffCapVph || p.effective_capacity_vph || 0).toFixed(1)),
      hazard_degradation_factor: parseFloat((p.hazard_degradation_factor || 1.0).toFixed(4)),
      cap_src:                   p.bottleneck_cap_src     || p.cap_src     || 'hcm',
      cap_reason:                p.bottleneck_cap_reason  || p.cap_reason  || null,
      cap_source_doc:            p.bottleneck_cap_source_doc || p.cap_source_doc || null,
      bottleneck_cross_street_a: p.bottleneck_cross_street_a || '',
      bottleneck_cross_street_b: p.bottleneck_cross_street_b || '',
      bottleneck_distance_mi:    +(p.bottleneck_distance_mi || 0),
      bottleneck_bearing:        p.bottleneck_bearing || '',
      path_coords:               p.path_coords || p.coordinates || [],
    }));
    return {
      tier:              r.tier              || 'MINISTERIAL',
      hazard_zone:       r.hazard_zone       || 'non_fhsz',
      in_fire_zone:      !!(r.in_fire_zone   || r.hazard_zone && r.hazard_zone !== 'non_fhsz'),
      project_vehicles:  parseFloat((r.project_vehicles || 0).toFixed(1)),
      egress_minutes:    parseFloat((r.egress_minutes   || 0).toFixed(1)),
      delta_t_threshold: parseFloat((r.delta_t_threshold || (r.paths && r.paths[0] ? r.paths[0].threshold_minutes : 0) || 0).toFixed(4)),
      paths,
    };
  }

  // ── CRUD ──────────────────────────────────────────────────────────────────────
  function createProject(fields) {
    const now = new Date().toISOString();
    const p   = Object.assign({
      id:                  _uuid(),
      schema_v:            SCHEMA_V,
      city_slug:           _citySlug(),
      josh_version:        _joshVer(),
      parameters_version:  _paramsVer(),
      name:                '',
      address:             '',
      lat:                 null,
      lng:                 null,
      units:               50,
      stories:             4,
      source:              'browser',
      created_at:          now,
      analyzed_at:         null,
      result:              null,
      brief_cache:         null,
      _handle:             null,   // FileSystemFileHandle — not serialized
      _stale:              false,  // parameters_version mismatch flag
    }, fields || {});
    _projects.push(p);
    _saveToLocalStorage();
    return p;
  }

  function updateProject(id, fields) {
    const idx = _projects.findIndex(p => p.id === id);
    if (idx === -1) return null;
    _projects[idx] = Object.assign({}, _projects[idx], fields);
    if ('result' in fields) {
      _projects[idx].analyzed_at = new Date().toISOString();
    }
    _markDirty(id);   // no-op when project has no file handle
    _saveToLocalStorage();
    return _projects[idx];
  }

  // ── Dirty tracking ────────────────────────────────────────────────────────────
  function _markDirty(id) {
    // Only mark dirty when the project already has a file handle (written to disk before)
    const p = getProject(id);
    if (p && p._handle) _dirtyIds.add(id);
  }

  function _markClean(id) { _dirtyIds.delete(id); }

  function deleteProject(id) {
    _projects = _projects.filter(p => p.id !== id);
    _clearHandle(id).catch(() => {});
    _saveToLocalStorage();
  }

  function getProject(id) {
    return _projects.find(p => p.id === id) || null;
  }

  function getProjects() { return _projects.slice(); }

  // ── Analysis ──────────────────────────────────────────────────────────────────
  function _runAnalysis(id, onDone) {
    const project = getProject(id);
    if (!project || project.lat === null || project.lng === null) {
      if (onDone) onDone(null, 'No location set.');
      return;
    }
    let engineResult;
    try {
      const WE = (typeof window !== 'undefined' && window.WhatIfEngine) ||
                 (typeof WhatIfEngine !== 'undefined' && WhatIfEngine) || null;
      if (!WE) { if (onDone) onDone(null, 'WhatIfEngine not loaded.'); return; }
      engineResult = WE.evaluateProject(project.lat, project.lng, project.units, project.stories);
    } catch (e) {
      if (onDone) onDone(null, e.message);
      return;
    }
    const result = _normalizeResult(engineResult);
    updateProject(id, { result, parameters_version: _paramsVer(), brief_cache: null });
    if (onDone) onDone(result, null);
  }

  function _scheduleAnalysis(id, onDone) {
    clearTimeout(_analyzeTimer);
    _analyzeTimer = setTimeout(() => _runAnalysis(id, onDone), 300);
  }

  // ── Brief renderer ────────────────────────────────────────────────────────────
  const FHSZ_DESC  = { vhfhsz: 'Very High Fire Hazard Severity Zone', high_fhsz: 'High FHSZ', moderate_fhsz: 'Moderate FHSZ', non_fhsz: 'Not in FHSZ' };
  const FHSZ_LEVEL = { vhfhsz: 3, high_fhsz: 2, moderate_fhsz: 1, non_fhsz: 0 };
  const FHSZ_DEG   = { vhfhsz: 0.35, high_fhsz: 0.50, moderate_fhsz: 0.75, non_fhsz: 1.00 };

  // Returns the ΔT threshold for a hazard zone from live params.
  // Used as fallback when result.delta_t_threshold is 0 (pre-fix stored results).
  function _dtThreshold(hazard_zone) {
    const pr = _params();
    if (!pr || !pr.safe_egress_window) return 0;
    return (pr.safe_egress_window[hazard_zone || 'non_fhsz'] || 0) * (pr.max_project_share || 0.05);
  }

  function _buildBriefInput(project) {
    const result    = project.result || {};
    const pr        = _params();
    const hz        = result.hazard_zone || 'non_fhsz';
    const ut        = +(pr.unit_threshold    || 15);
    const maxShare  = +(pr.max_project_share || 0.05);
    const degFactor = FHSZ_DEG[hz] || 1.00;

    const lat    = +(project.lat || 0);
    const lng    = +(project.lng || 0);
    const latAbs = Math.abs(lat).toFixed(4).replace('.', '_');
    const lngAbs = Math.abs(lng).toFixed(4).replace('.', '_');
    const slug   = (project.name || '').toUpperCase()
                     .replace(/\s+/g, '-').replace(/[^A-Z0-9-]/g, '').slice(0, 20);
    const year   = new Date().getFullYear();
    const caseNum = slug
      ? `JOSH-${year}-${slug}-${lat < 0 ? 'n' : ''}${latAbs}-${lng < 0 ? 'n' : ''}${lngAbs}`
      : `JOSH-${year}-${lat < 0 ? 'n' : ''}${latAbs}-${lng < 0 ? 'n' : ''}${lngAbs}`;

    const enrichedPaths = (result.paths || []).map(function (p, idx) {
      const thrMin  = +(result.delta_t_threshold || 0) || _dtThreshold(hz);
      const safeWin = thrMin > 0 && maxShare > 0 ? thrMin / maxShare : 0;
      return {
        // path_id must be unique per route (post-dedup-removal multiple paths can
        // share a bottleneck osmid); fall back to a positional id only as last resort.
        path_id:                       String(p.path_id || p.pathId || ('route_' + (idx + 1))),
        cost_s:                        +(p.cost_s || 0),
        bottleneck_osmid:              p.bottleneck_osmid || '',
        bottleneck_name:               p.bottleneck_name  || null,
        bottleneck_fhsz_zone:          hz,
        bottleneck_hcm_capacity_vph:   0,
        bottleneck_eff_cap_vph:        +(p.effective_capacity_vph || 0),
        bottleneck_hazard_degradation: +(p.hazard_degradation_factor || degFactor),
        bottleneck_road_type:          p.bottleneck_road_type || null,
        bottleneck_speed_mph:          p.bottleneck_speed   || null,
        bottleneck_lanes:              p.bottleneck_lanes   || null,
        bottleneck_cap_src:            p.cap_src        || 'hcm',
        bottleneck_cap_reason:         p.cap_reason     || null,
        bottleneck_cap_source_doc:     p.cap_source_doc || null,
        bottleneck_cross_street_a:     p.bottleneck_cross_street_a || '',
        bottleneck_cross_street_b:     p.bottleneck_cross_street_b || '',
        bottleneck_distance_mi:        +(p.bottleneck_distance_mi || 0),
        bottleneck_bearing:            p.bottleneck_bearing || '',
        delta_t_minutes:               +(p.delta_t          || 0),
        threshold_minutes:             thrMin,
        safe_egress_window_minutes:    safeWin,
        max_project_share:             maxShare,
        flagged:                       !!p.flagged,
        project_vehicles:              +(result.project_vehicles || 0),
        egress_minutes:                +(result.egress_minutes   || 0),
      };
    });

    const fp         = enrichedPaths[0] || {};
    const topThr     = +(fp.threshold_minutes || 0);
    const topSafeWin = +(fp.safe_egress_window_minutes || 0);

    return {
      brief_input_version: 1,
      source:              project.source === 'pipeline' ? 'pipeline' : 'whatif',
      city_name:           _cityName(),
      city_slug:           _citySlug(),
      case_number:         caseNum,
      eval_date:           new Date().toISOString().slice(0, 10),
      audit_text:          _buildAuditText(project, result || {}, pr),
      audit_filename:      'audit_trail.txt',
      project: {
        name:    project.name    || '',
        address: project.address || '',
        lat,
        lon:     lng,
        units:   project.units   || 0,
        stories: project.stories || null,
        apn:     '',
      },
      analysis: {
        applicability_met:         (project.units || 0) >= ut,
        dwelling_units:            project.units  || 0,
        unit_threshold:            ut,
        fhsz_flagged:              hz !== 'non_fhsz',
        fhsz_desc:                 FHSZ_DESC[hz]  || hz,
        fhsz_level:                FHSZ_LEVEL[hz] || 0,
        hazard_zone:               hz,
        behavioral_mobilization:   +(pr.behavioral_mobilization || 0.90),
        hazard_degradation_factor: degFactor,
        serving_route_count:       (result.paths || []).length,
        route_radius_miles:        0.5,
        routes_trigger_analysis:   (result.paths || []).length > 0,
        delta_t_triggered:         result.tier === 'DISCRETIONARY',
        egress_minutes:            +(result.egress_minutes || 0),
      },
      result: {
        tier:                       result.tier || '',
        hazard_zone:                hz,
        project_vehicles:           +(result.project_vehicles || 0),
        max_delta_t_minutes:        Math.max(...(result.paths || []).map(p => +(p.delta_t || 0)), 0),
        threshold_minutes:          topThr,
        safe_egress_window_minutes: topSafeWin,
        max_project_share:          maxShare,
        serving_paths_count:        (result.paths || []).length,
        egress_minutes:             +(result.egress_minutes || 0),
        parameters_version:         project.parameters_version || '',
        analyzed_at:                project.analyzed_at || new Date().toISOString().slice(0, 10),
        determination_reason:       '',
        triggered:                  result.tier === 'DISCRETIONARY',
        paths:                      enrichedPaths,
      },
      parameters: pr,
    };
  }

  // ── Bottleneck label formatter ─────────────────────────────────────────────
  // Mirrors _format_bottleneck() in objective_standards.py.
  function _formatBottleneck(p) {
    var bnName  = p.bottleneck_name  || '';
    var crossA  = p.bottleneck_cross_street_a || '';
    var crossB  = p.bottleneck_cross_street_b || '';
    var distMi  = +(p.bottleneck_distance_mi  || 0);
    var bearing = p.bottleneck_bearing || '';
    var label;

    if (bnName) {
      if (crossA && crossB && crossA !== crossB) {
        label = bnName + ' (' + crossA + ' to ' + crossB + ')';
      } else if (crossA || crossB) {
        label = bnName + ' at ' + (crossA || crossB);
      } else {
        label = bnName;
      }
    } else {
      var osmid = p.bottleneck_osmid || '?';
      if (crossA && crossB && crossA !== crossB) {
        label = 'Unnamed road (' + crossA + ' to ' + crossB + ')';
      } else if (crossA || crossB) {
        label = 'Unnamed road at ' + (crossA || crossB);
      } else {
        label = 'osmid ' + osmid;
      }
    }

    if (distMi > 0 && bearing) {
      label += ', ' + distMi.toFixed(1) + ' mi ' + bearing;
    }
    return label;
  }

  // ── Audit trail text builder ──────────────────────────────────────────────
  // Reconstructs the full dT audit trail from project.result data.
  // Matches the Python-side generate_audit_trail() format in
  // agents/objective_standards.py so the client-side .txt download is
  // structurally identical to the pipeline-generated determination file.
  function _buildAuditText(project, result, params) {
    var hz        = result.hazard_zone  || 'non_fhsz';
    var ut        = +(params.unit_threshold    || 15);
    var vpu       = +(params.vehicles_per_unit || 1.9);
    var mob       = +(params.behavioral_mobilization || 0.90);
    var maxShare  = +(params.max_project_share || 0.05);
    var pv        = +(result.project_vehicles  || 0);
    var ep        = +(result.egress_minutes    || 0);
    var thr       = +(result.delta_t_threshold || 0) || _dtThreshold(hz);
    var safeWin   = (maxShare > 0 && thr > 0) ? thr / maxShare : 0;
    var paths     = result.paths || [];
    var tier      = (result.tier || '').toUpperCase().trim();
    var sep70     = '='.repeat(70);
    var sep40     = '-'.repeat(40);
    var sep38     = '-'.repeat(38);

    // ── Helpers ──
    function _degToZone(deg) {
      var d = +(deg != null ? deg : 1.0);
      if (Math.abs(d - 0.35) < 0.01) return 'vhfhsz';
      if (Math.abs(d - 0.50) < 0.01) return 'high_fhsz';
      if (Math.abs(d - 0.75) < 0.01) return 'moderate_fhsz';
      return 'non_fhsz';
    }
    function _hazClassInt(zone) {
      return ({ vhfhsz: 3, high_fhsz: 2, moderate_fhsz: 1 })[zone] || 0;
    }
    function _zoneDesc(hc) {
      return ({ 3: 'Zone 3 (Very High)', 2: 'Zone 2 (High)',
                1: 'Zone 1 (Moderate)', 0: 'Not in FHSZ' })[hc] || 'Not in FHSZ';
    }
    function _rtLabel(rt) {
      if (rt === 'freeway')   return 'Freeway';
      if (rt === 'multilane') return 'Multi-lane highway';
      if (rt === 'two_lane')  return 'Two-lane highway';
      return rt || '?';
    }

    // Compute max dT up front (needed in footer)
    var maxDt = 0, anyFlagged = false;
    paths.forEach(function(p) {
      var dt = +(p.delta_t || 0);
      if (dt > maxDt) maxDt = dt;
      if (p.flagged) anyFlagged = true;
    });

    var hzClass = _hazClassInt(hz);
    var applies = (project.units || 0) >= ut;
    var nFlagged = 0;
    paths.forEach(function(p) { if (p.flagged) nFlagged++; });

    var detLabel = ({
      'DISCRETIONARY':                        'DISCRETIONARY REVIEW REQUIRED',
      'MINISTERIAL WITH STANDARD CONDITIONS': 'MINISTERIAL WITH STANDARD CONDITIONS',
      'MINISTERIAL':                          'MINISTERIAL APPROVAL ELIGIBLE',
    })[tier] || tier;

    var L = [];

    // ── Document header (matches Python generate_audit_trail) ──
    L.push(sep70);
    L.push('FIRE EVACUATION CAPACITY ANALYSIS -- PROJECT DETERMINATION');
    L.push('JOSH v4.0 (dT Standard -- Constant Mobilization, NFPA 1660 / 1616)');
    L.push(sep70);
    L.push('Date:           ' + (project.analyzed_at || new Date().toISOString().slice(0, 10)));
    L.push('Project:        ' + (project.name || 'Untitled'));
    L.push('Address:        ' + (project.address || 'Not provided'));
    L.push('APN:            ' + (project.apn || 'Not provided'));
    L.push('Location:       ' +
           (project.lat != null ? (+project.lat).toFixed(4) : '?') + ', ' +
           (project.lng != null ? (+project.lng).toFixed(4) : '?'));
    L.push('Dwelling Units: ' + (project.units || 0));
    L.push('Stories:        ' + (project.stories || 0));
    L.push('');

    // ── Algorithm ──
    L.push('ALGORITHM');
    L.push(sep40);
    L.push('  Universal 5-Step Evacuation Capacity Algorithm v4.0 (dT Standard -- constant mobilization)');
    L.push('  Each scenario applies: (1) applicability check, (2) scale gate,');
    L.push('  (3) route identification (EvacuationPath objects with bottleneck tracking),');
    L.push('  (4) demand calculation (mobilization rate 0.90 x vpu x units -- NFPA 1660 (2024) / NFPA 1616 (2020) community mass-evacuation design basis),');
    L.push('  (5) dT test (project_vehicles / bottleneck_effective_capacity x 60 + egress).');
    L.push('  Reference: AB 747 (California Government Code Sec.65302.15)');

    // ── Scenario header ──
    L.push('');
    L.push(sep70);
    L.push('SCENARIO: WILDLAND_AB747');
    L.push('  Legal Basis: AB 747 (California Government Code Sec.65302.15) -- General Plan Safety Element');
    L.push('    mandatory update for evacuation route capacity analysis;');
    L.push('    HCM 2022 (Highway Capacity Manual, 7th Edition, Transportation Research Board) -- effective capacity;');
    L.push('    NFPA 1660 (2024) / NFPA 1616 (2020) -- community mass-evacuation design basis, 0.90 mobilization constant;');
    L.push('    NFPA 101 (Life Safety Code, 2024 CA edition) -- building egress penalty for stories >= 4 only;');
    L.push('    NIST TN 2135 (Maranghides et al., 2021) -- safe egress windows by hazard zone;');
    L.push('    Composite hazard-degradation factor (HCM Ch. 11 weather CAF + NIST TN 2135 + Kincade/Glass Fire empirical refs)');
    L.push('      -- independent traffic-engineering review pending (Fire Science Consulting LLC, May 2026)');
    L.push('  Result: ' + tier + '  |  Triggered: ' + (anyFlagged ? 'YES' : 'NO'));
    L.push(sep70);

    // ── STEP 1: Applicability (Standard 3: FHSZ Modifier) ──
    L.push('');
    L.push('  STEP 1 -- APPLICABILITY CHECK (Standard 3: FHSZ Modifier)');
    L.push('  ' + sep38);
    L.push('  Method: Always applicable; site FHSZ check via GIS point-in-polygon');
    L.push('  Result: APPLICABLE');
    L.push('  Standard 3 (FHSZ): ' + _zoneDesc(hzClass) +
           ' [HAZ_CLASS=' + hzClass + ']  hazard_zone=' + hz +
           '  (' + (result.in_fire_zone ? 'IN FIRE ZONE' : 'not in FHSZ') + ')');
    L.push('  Mobilization Rate: ' + mob.toFixed(2) +
           ' (NFPA 1660 / 1616 community mass-evacuation design basis -- constant; Census ACS B25044 zero-vehicle adjustment)');

    // ── STEP 2: Scale gate (Standard 1) ──
    L.push('');
    L.push('  STEP 2 -- SCALE GATE (Standard 1)');
    L.push('  ' + sep38);
    L.push('  ' + (project.units || 0) + ' ' + (applies ? '>=' : '<') + ' ' + ut +
           ' -> ' + (applies ? 'TRIGGERED' : 'not triggered'));
    L.push('  (' + (project.units || 0) + ' units vs. ' + ut + ' threshold)');

    if (tier === 'MINISTERIAL' && !applies) {
      L.push('  -> Determination: MINISTERIAL (below scale threshold)');
      // Skip Steps 3-5, go straight to final determination
    } else {
      // ── STEP 3: Route identification (Standard 2) ──
      L.push('');
      L.push('  STEP 3 -- ROUTE IDENTIFICATION (Standard 2)');
      L.push('  ' + sep38);
      L.push('  Method: Project-origin Dijkstra (v4.0, travel-time weight) -- fastest path to each');
      L.push('    regional-network exit node; bottleneck = argmin(eff_cap_vph) on path edges');
      L.push('  Radius: 0.5 miles (804.7 m)');
      L.push('  Serving EvacuationPaths identified: ' + paths.length);
      paths.forEach(function (p) {
        var label  = _formatBottleneck(p);
        var zone   = _degToZone(p.hazard_degradation_factor);
        var deg    = +(p.hazard_degradation_factor != null ? p.hazard_degradation_factor : 1.0);
        var effCap = +(p.effective_capacity_vph || 0);
        L.push('    - ' + label + ': eff_cap=' + effCap.toFixed(0) +
               ' vph, fhsz=' + zone + ', deg=' + deg.toFixed(2) +
               ' (informational)');
      });

      // ── STEP 4: Demand calculation ──
      L.push('');
      L.push('  STEP 4 -- DEMAND CALCULATION');
      L.push('  ' + sep38);
      L.push('  Formula: ' + (project.units || 0) + ' x ' + vpu.toFixed(1) + ' x ' + mob.toFixed(2));
      L.push('  Hazard Zone: ' + hz);
      L.push('  Mobilization Rate: ' + mob.toFixed(2) + ' (NFPA 1660 / 1616 community mass-evacuation design basis, constant)');
      L.push('  Project vehicles (peak hour): ' + pv.toFixed(1) + ' vph');
      L.push('  Source (vehicles/unit): U.S. Census ACS B25044');
      L.push('  Source (mobilization): NFPA 1660 (Standard for Emergency, Continuity, and Crisis Management, 2024 ed.)');
      L.push('                         consolidates NFPA 1616 (Mass Evacuation, Sheltering, and Re-entry Programs, 2020 ed.)');
      L.push('                         0.90 = full-evacuation design basis adjusted for ~10% zero-vehicle HHs (Census ACS B25044)');

      // ── STEP 5: dT test (Standard 4) ──
      L.push('');
      L.push('  STEP 5 -- dT TEST (Standard 4)');
      L.push('  ' + sep38);
      L.push('  Method: dT = (project_vehicles / bottleneck_effective_capacity) x 60 + egress');
      L.push('  Hazard Zone: ' + hz);
      L.push('  Mobilization Rate: ' + mob.toFixed(2) + ' (NFPA 1660 / 1616 community mass-evacuation design basis, constant)');
      L.push('  Project Vehicles: ' + pv.toFixed(1) + ' vph');
      L.push('  Egress Penalty: ' + ep.toFixed(1) + ' min (NFPA 101 Life Safety Code, 2024 CA ed., Ch. 7 + IBC 2024 Ch. 10; applies to buildings >= 4 stories)');
      L.push('  Safe Egress Window: ' + safeWin.toFixed(0) + ' min (' + hz + ', NIST TN 2135)');
      L.push('  Max Project Share:  ' + (maxShare * 100).toFixed(0) + '%');
      L.push('  dT Threshold:       ' + thr.toFixed(2) + ' min (' +
             safeWin.toFixed(0) + ' min window x ' + (maxShare * 100).toFixed(0) + '%, NIST TN 2135)');
      L.push('  Paths Evaluated: ' + paths.length);
      L.push('  Max dT: ' + maxDt.toFixed(2) + ' min');
      L.push('  Triggered: ' + (anyFlagged ? 'YES -- DISCRETIONARY' : 'NO'));
      L.push('');
      L.push('  Per-Path Results (all evaluated paths -- no deduplication):');

      paths.forEach(function (p) {
        var bnLabel = _formatBottleneck(p);
        var flagLine = p.flagged
          ? ' *** dT EXCEEDS THRESHOLD -- DISCRETIONARY ***'
          : ' [within threshold]';
        var zone   = _degToZone(p.hazard_degradation_factor);
        var hazCls = _hazClassInt(zone);
        var deg    = +(p.hazard_degradation_factor != null ? p.hazard_degradation_factor : 1.0);
        var effCap = +(p.effective_capacity_vph || 0);
        var hcmCap = deg > 0 ? Math.round(effCap / deg) : effCap;
        var dt     = +(p.delta_t || 0);
        var rtLbl  = _rtLabel(p.bottleneck_road_type);

        // Path context line
        L.push('    Path ' + (p.route_id || '?'));
        // Bottleneck + flag
        L.push('    Bottleneck: ' + bnLabel + flagLine);
        // Road detail
        var roadInfo = '      Road: ' + rtLbl;
        if (p.bottleneck_speed) roadInfo += '  |  Speed: ' + p.bottleneck_speed + ' mph';
        if (p.bottleneck_lanes) roadInfo += '  |  Lanes: ' + p.bottleneck_lanes;
        roadInfo += '  |  HAZ_CLASS: ' + hazCls + ' (' + zone + ')';
        L.push(roadInfo);
        // Capacity source line
        if (p.cap_src === 'city_override') {
          var rawCap = deg > 0 ? (effCap / deg).toFixed(0) : effCap.toFixed(0);
          L.push('      Capacity: ' + rawCap + ' vph  [city-provided]');
          if (p.cap_source_doc) L.push('      Source:   ' + p.cap_source_doc);
          if (p.cap_reason)     L.push('      Reason:   ' + p.cap_reason);
          L.push('      Effective cap: ' + effCap.toFixed(0) + ' vph' +
                 '  (' + rawCap + ' vph city-provided x ' + deg.toFixed(2) +
                 ' ' + zone + ' degradation)');
        } else {
          L.push('      HCM cap: ' + hcmCap + ' vph  x degradation ' + deg.toFixed(2) +
                 ' (' + zone + ')  = eff cap ' + effCap.toFixed(0) + ' vph');
        }
        // dT formula
        L.push('      dT = (' + pv.toFixed(1) + ' vph / ' + effCap.toFixed(0) +
               ' vph) x 60 + ' + ep.toFixed(1) + ' min egress = ' + dt.toFixed(2) + ' min' +
               '  (threshold: ' + thr.toFixed(2) + ' min (' +
               safeWin.toFixed(0) + ' min x ' + (maxShare * 100).toFixed(0) + '%))');
        L.push('');
      });

      L.push('');
      L.push('  -> Scenario Tier: ' + tier);
    }

    // ── FINAL DETERMINATION (matches Python generate_audit_trail) ──
    L.push('');
    L.push(sep70);
    L.push('FINAL DETERMINATION');
    L.push(sep70);
    L.push('  RESULT: ' + detLabel);
    L.push('');
    L.push('  PARAMETERS APPLIED');
    L.push('  ' + sep38);
    L.push('  Hazard Zone:        ' + hz);
    L.push('  Behavioral Mobilization: ' + mob.toFixed(2) +
           ' (NFPA 1660 (2024) / NFPA 1616 (2020) community mass-evacuation design basis)');
    L.push('  Vehicles per Unit:  1.9 (U.S. Census ACS B25044, CA statewide all-HH average)');
    L.push('  Egress Penalty:     ' + ep.toFixed(1) + ' min (NFPA 101 Life Safety Code, 2024 CA ed. + IBC 2024 Ch. 10 -- ' +
           (project.stories || 0) + ' stories)');
    L.push('  Safe Egress Window: ' + safeWin.toFixed(0) + ' min (' + hz + ', per NIST TN 2135)');
    L.push('  Max Project Share:  ' + (maxShare * 100).toFixed(0) + '%');
    L.push('  dT Threshold:       ' + thr.toFixed(2) + ' min (' +
           safeWin.toFixed(0) + ' x ' + (maxShare * 100).toFixed(0) + '%)');
    L.push('  Max dT (project):   ' + maxDt.toFixed(2) + ' min');
    L.push('');
    L.push('  Determination Tier:');
    // Tier explanation (matches Python tier_explanation dict)
    if (tier === 'DISCRETIONARY') {
      L.push('    DISCRETIONARY REVIEW REQUIRED');
      L.push('');
      L.push('  At least one scenario triggered DISCRETIONARY: the project meets the');
      L.push('  dwelling unit size threshold and at least one serving path\'s dT exceeds');
      L.push('  the applicable threshold for the project\'s hazard zone.');
      L.push('');
      L.push('  dT = (project_vehicles / bottleneck_effective_capacity) x 60 + egress_penalty');
      L.push('  The baseline state of the road is irrelevant -- projects in already-failing');
      L.push('  zones are tested equally (key v3.0 correction from v2.0 marginal causation test).');
      L.push('');
      L.push('  NOTE: Fire zone location (Standard 3) affects mobilization rate and dT threshold;');
      L.push('  it does not independently gate the determination.');
    } else if (tier === 'MINISTERIAL WITH STANDARD CONDITIONS') {
      L.push('    MINISTERIAL WITH STANDARD CONDITIONS');
      L.push('');
      L.push('  The project meets the dwelling unit size threshold and all serving paths\' dT');
      L.push('  are within the applicable threshold for the project\'s hazard zone.');
      L.push('  Approved ministerially. The following pre-adopted, objective conditions apply');
      L.push('  automatically: PRC Sec.4291 defensible space (if FHSZ); AB 1600 evacuation');
      L.push('  infrastructure impact fee (if fee schedule adopted); emergency vehicle access');
      L.push('  per local fire code; WUI building standards compliance (if FHSZ).');
    } else {
      L.push('    MINISTERIAL APPROVAL ELIGIBLE');
      L.push('');
      L.push('  Project is below the dwelling unit size threshold (Standard 1 not met).');
      L.push('  No evacuation capacity analysis is required.');
    }
    L.push('');
    L.push('  Scenario Tier Summary:');
    L.push('    wildland_ab747: ' + tier);
    L.push('');
    L.push('  This determination is based solely on objective, verifiable criteria.');
    L.push('  No professional discretion was applied. All calculations are reproducible.');
    L.push('  See legal.md for full legal basis and defense reference.');
    L.push('');
    L.push('  SCOPE AND LIMITATIONS');
    L.push('  ' + sep38);
    L.push('  Civilian outbound capacity only. JOSH measures the dT contribution of');
    L.push('  civilian vehicles exiting the project on its serving evacuation routes.');
    L.push('  Concurrent emergency apparatus inbound access, required by CCR 1273.00');
    L.push('  of the 2025 California Wildland-Urban Interface Code (CWUIC) adopted by');
    L.push('  the State Fire Marshal, requires separate analysis that is outside the');
    L.push('  scope of this determination.');
    L.push('');
    L.push('  Consistent with CWUIC Appendix C Sec. C101.6, dT is an initial idealized');
    L.push('  order-of-magnitude clearance estimate intended as a screening tool that');
    L.push('  triggers further review under the Housing Accountability Act safety');
    L.push('  exception (Gov. Code Sec.65589.5(j)(1)). It is not a substitute for a full');
    L.push('  community evacuation study and is not a standalone permit-denial instrument.');
    L.push('');
    L.push('  Methodology open items (independent traffic-engineering review by Fire');
    L.push('  Science Consulting LLC, May 2026): hazard-degradation factor empirical');
    L.push('  derivation; CWUIC road-geometry pre-check (Secs. 403.1, 403.3); shadow-');
    L.push('  evacuation and cumulative route capacity tracking; dt(egress) for low-rise');
    L.push('  (IBC 2024 Ch. 10 + SFPE Handbook Ch. 64).');
    L.push(sep70);

    return L.join('\n');
  }

  function _downloadDetermination(project) {
    if (!project.result) {
      _showError('No analysis result \u2014 run the evaluation first.'); return;
    }
    var text = _buildAuditText(project, project.result || {}, _params());
    var blob = new Blob([text], { type: 'text/plain' });
    var url  = URL.createObjectURL(blob);
    var a    = document.createElement('a');
    a.href     = url;
    a.download = (project.name || 'determination').toLowerCase()
      .replace(/[^a-z0-9_-]/g, '_') + '_determination.txt';
    a.click();
    URL.revokeObjectURL(url);
  }

  function _openBrief(project) {
    if (typeof window === 'undefined' || !window.BriefRenderer) {
      _showError('Brief renderer not loaded — try reloading the page.'); return;
    }
    if (!window.joshBrief) {
      _showError('Brief modal not available — try reloading the page.'); return;
    }
    // Use cached HTML if available and result not stale
    let html = project.brief_cache;
    if (!html) {
      try {
        const briefInput = _buildBriefInput(project);
        html = window.BriefRenderer.render(briefInput);
        updateProject(project.id, { brief_cache: html });
      } catch (e) {
        _showError('Could not generate brief: ' + e.message); return;
      }
    }
    const caseNum  = _buildBriefInput(project).case_number || 'brief';
    const filename = caseNum.toLowerCase().replace(/[^a-z0-9_-]/g, '_') + '.html';
    window.joshBrief.show(html, filename);
  }

  // ── FSAPI — FSAPI detection ───────────────────────────────────────────────────
  const _hasFSAPI = (function () {
    try { return typeof window !== 'undefined' && typeof window.showOpenFilePicker === 'function'; }
    catch (_) { return false; }
  }());

  // ── IndexedDB handle storage ──────────────────────────────────────────────────
  function _openIdb() {
    if (_idb) return Promise.resolve(_idb);
    return new Promise((resolve, reject) => {
      if (typeof indexedDB === 'undefined') { reject(new Error('no IndexedDB')); return; }
      const req = indexedDB.open(IDB_NAME, 1);
      req.onupgradeneeded = e => {
        e.target.result.createObjectStore(IDB_STORE);
      };
      req.onsuccess = e => { _idb = e.target.result; resolve(_idb); };
      req.onerror   = e => reject(e.target.error);
    });
  }

  async function _storeHandle(id, handle) {
    try {
      const db    = await _openIdb();
      const tx    = db.transaction(IDB_STORE, 'readwrite');
      tx.objectStore(IDB_STORE).put(handle, id);
      await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = e => rej(e.target.error); });
    } catch (e) { /* IndexedDB unavailable on file:// in some browsers — silent */ }
  }

  async function _clearHandle(id) {
    try {
      const db = await _openIdb();
      const tx = db.transaction(IDB_STORE, 'readwrite');
      tx.objectStore(IDB_STORE).delete(id);
    } catch (_) {}
  }

  async function _loadAllHandles() {
    try {
      const db  = await _openIdb();
      const tx  = db.transaction(IDB_STORE, 'readonly');
      const store = tx.objectStore(IDB_STORE);
      const result = new Map();
      await new Promise((res, rej) => {
        const req = store.openCursor();
        req.onsuccess = e => {
          const cursor = e.target.result;
          if (!cursor) { res(); return; }
          result.set(cursor.key, cursor.value);
          cursor.continue();
        };
        req.onerror = e => rej(e.target.error);
      });
      return result;
    } catch (_) { return new Map(); }
  }

  // ── Serialize / deserialize (per-project file format, spec §7) ───────────────
  function _serialize(project) {
    const out = {
      schema_v:           SCHEMA_V,
      city_slug:          project.city_slug   || _citySlug(),
      josh_version:       project.josh_version || _joshVer(),
      parameters_version: project.parameters_version || _paramsVer(),
      name:               project.name    || '',
      address:            project.address || '',
      lat:                project.lat,
      lng:                project.lng,
      units:              project.units,
      stories:            project.stories,
      source:             project.source  || 'browser',
      created_at:         project.created_at  || new Date().toISOString(),
      analyzed_at:        project.analyzed_at || null,
      result:             project.result  || null,
      brief_cache:        project.brief_cache || null,
    };
    return JSON.stringify(out, null, 2);
  }

  function _deserialize(json) {
    let obj;
    try { obj = JSON.parse(json); }
    catch (e) { throw new Error('Invalid JSON: ' + e.message); }

    if (!obj.schema_v || obj.schema_v > SCHEMA_V) {
      throw new Error('Unsupported schema_v: ' + obj.schema_v);
    }
    const mySlug = _citySlug();
    if (mySlug && mySlug !== 'city' && obj.city_slug && obj.city_slug !== mySlug) {
      throw new Error('city_slug mismatch: file is for "' + obj.city_slug + '", this map is "' + mySlug + '"');
    }

    // Stale detection: result parameters_version vs current
    const stale = !!(obj.result && obj.parameters_version &&
                     _paramsVer() && obj.parameters_version !== _paramsVer());

    return Object.assign({
      id:                 _uuid(),
      schema_v:           SCHEMA_V,
      city_slug:          obj.city_slug   || mySlug,
      josh_version:       obj.josh_version || '',
      parameters_version: obj.parameters_version || '',
      name:               obj.name    || '',
      address:            obj.address || '',
      lat:                obj.lat     != null ? +obj.lat : null,
      lng:                obj.lng     != null ? +obj.lng : null,
      units:              +(obj.units   || 50),
      stories:            +(obj.stories || 4),
      source:             obj.source   || 'browser',
      created_at:         obj.created_at  || new Date().toISOString(),
      analyzed_at:        obj.analyzed_at || null,
      result:             obj.result  || null,
      brief_cache:        obj.brief_cache || null,
      _handle:            null,
      _stale:             stale,
    });
  }

  // ── File I/O ──────────────────────────────────────────────────────────────────
  async function openFile() {
    if (_hasFSAPI) {
      try {
        const handles = await window.showOpenFilePicker({
          multiple: true,
          types: [{ description: 'JOSH Project', accept: { 'application/json': ['.json'] } }],
        });
        let firstId = null;
        for (const handle of handles) {
          const id = await _loadFromHandle(handle);
          if (id && !firstId) firstId = id;
        }
        if (firstId) selectProject(firstId);
        _render();
      } catch (e) {
        if (e.name !== 'AbortError') _showError('Could not open file: ' + e.message);
      }
    } else {
      _inputFileLoad();
    }
  }

  async function _loadFromHandle(handle) {
    try {
      const file    = await handle.getFile();
      const text    = await file.text();
      const project = _deserialize(text);
      // Dedup: replace existing project with same id if already in list
      const existIdx = _projects.findIndex(p => p.id === project.id);
      project._handle = handle;
      if (existIdx !== -1) { _projects[existIdx] = project; }
      else                  { _projects.push(project); }
      await _storeHandle(project.id, handle);
      if (project._stale) {
        _runAnalysis(project.id, async () => {
          await _writeToHandle(project.id);
          _render();
        });
      }
      return project.id;
    } catch (e) {
      _showError('Could not load file: ' + e.message);
      return null;
    }
  }

  async function _writeToHandle(id) {
    const project = getProject(id);
    if (!project || !project._handle) return false;
    try {
      const writable = await project._handle.createWritable();
      await writable.write(_serialize(project));
      await writable.close();
      _markClean(id);  // disk matches memory — no unsaved changes
      return true;
    } catch (_) { return false; }
  }

  async function saveFile(id) {
    const project = getProject(id);
    if (!project) return;
    if (project._handle) {
      const ok = await _writeToHandle(id);
      if (ok) return;
    }
    await saveAsFile(id);
  }

  async function saveAsFile(id) {
    const project = getProject(id);
    if (!project) return;
    const filename = _citySlug() + '_' + _slugify(project.name || project.id) + '.json';
    if (_hasFSAPI) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName: filename,
          types: [{ description: 'JOSH Project', accept: { 'application/json': ['.json'] } }],
        });
        updateProject(id, {});  // bump analyzed_at if needed
        const project2 = getProject(id);
        project2._handle = handle;
        await _writeToHandle(id);
        await _storeHandle(id, handle);
      } catch (e) {
        if (e.name !== 'AbortError') _blobDownload(_serialize(project), filename);
      }
    } else {
      _blobDownload(_serialize(project), filename);
    }
  }

  function _blobDownload(text, filename) {
    if (typeof document === 'undefined') return;
    const blob = new Blob([text], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function _inputFileLoad() {
    if (typeof document === 'undefined') return;
    const inp    = document.createElement('input');
    inp.type     = 'file';
    inp.accept   = '.json';
    inp.multiple = true;
    inp.onchange = () => {
      let firstId = null;
      Array.from(inp.files || []).forEach(file => {
        const reader   = new FileReader();
        reader.onload  = e => {
          try {
            const project = _deserialize(e.target.result);
            const existIdx = _projects.findIndex(p => p.id === project.id);
            if (existIdx !== -1) _projects[existIdx] = project;
            else _projects.push(project);
            if (!firstId) { firstId = project.id; selectProject(firstId); }
            _render();
          } catch (err) { _showError(err.message); }
        };
        reader.readAsText(file);
      });
    };
    inp.click();
  }

  // ── YAML export ───────────────────────────────────────────────────────────────
  function _yamlStr(s) {
    const str = String(s || '');
    if (/[:#\[\]{}&*?|<>=!%@`,'"]/.test(str) || str.trim() !== str) {
      return '"' + str.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
    }
    return str;
  }

  function _toYaml() {
    const slug  = _citySlug();
    const name  = _cityName();
    const lines = [];
    lines.push('# ' + name + ' demo projects — exported from JOSH Sidebar');
    lines.push('# To use: copy to josh-pipeline/projects/' + slug + '_demo.yaml');
    lines.push('# Then run: JOSH_DIR=/path/to/josh uv run python acquire.py run --city "' + name + '"');
    lines.push('');
    lines.push('projects:');
    const pinned = _projects.filter(p => p.lat !== null && p.lng !== null);
    if (pinned.length === 0) lines.push('  # (no projects with coordinates)');
    for (const p of pinned) {
      lines.push('  - name: ' + _yamlStr(p.name || 'Untitled'));
      if (p.address) lines.push('    address: ' + _yamlStr(p.address));
      lines.push('    lat: ' + (+p.lat).toFixed(7));
      lines.push('    lon: ' + (+p.lng).toFixed(7));
      lines.push('    units: ' + (p.units || 50));
      lines.push('    stories: ' + (p.stories || 4));
      lines.push('');
    }
    return lines.join('\n');
  }

  function exportYaml() {
    _blobDownload(_toYaml(), _citySlug() + '_demo.yaml');
  }

  // ── Map bridge (no-ops until Phase 3 wires window._joshMap) ──────────────────
  function _getMap() {
    if (typeof window === 'undefined') return null;
    return window._joshMap || null;
  }

  function _clearRoutes() {
    const map = _getMap();
    if (map) {
      _routeLayers.forEach(l => { try { map.removeLayer(l); } catch (_) {} });
      // Hide all Folium project FeatureGroups (pipeline projects carry folium_fg_name).
      // This ensures no stale route layer persists when switching projects or clearing.
      if (typeof window !== 'undefined') {
        _projects.forEach(p => {
          if (p.folium_fg_name && window[p.folium_fg_name]) {
            try { map.removeLayer(window[p.folium_fg_name]); } catch (_) {}
          }
        });
      }
      // v4.12 (all-viable-routes): restore citywide heatmap opacity.
      // _drawRoutes dims overlayPane so per-project routes pop out of the heatmap;
      // we put it back here so the heatmap is at full intensity when no project
      // is selected (heatmap is the focus when no route detail is shown).
      const overlayPane = map.getPane && map.getPane('overlayPane');
      if (overlayPane) overlayPane.style.opacity = '';
    }
    _routeLayers = [];
  }

  // v4.12 (all-viable-routes): dedicated pane for per-project AntPaths +
  // bottleneck overlays.  Placed above the standard overlayPane (400) so
  // routes render above the citywide heatmap, AND so the heatmap can be
  // dimmed via overlayPane opacity without affecting the routes.
  // Idempotent — runs once per page load.
  //
  // NOTE on AntPath + pane: the leaflet-ant-path plugin does NOT propagate
  // the `pane` option to its internal sub-polylines, so its SVG paths
  // would otherwise render in the (dimmed) overlayPane.  We work around
  // this by providing an explicit `renderer` attached to joshRoutes — the
  // sub-polylines inherit the renderer's pane regardless of what the
  // plugin does with the `pane` option.  The renderer is cached on the
  // map so we reuse a single SVG element for all routes.
  function _ensureRoutePane(map) {
    if (!map || !map.createPane) return;
    if (map.getPane('joshRoutes')) return;
    const pane = map.createPane('joshRoutes');
    pane.style.zIndex = 650;          // above overlayPane (400) and markerShadow (500); below marker (600)
    pane.style.pointerEvents = 'auto'; // routes remain tooltip-clickable
  }

  // Returns the shared joshRoutes SVG renderer for this map, creating it
  // lazily on first use.  Passing this as `renderer:` to L.polyline or
  // L.antPath forces the sub-paths into the joshRoutes pane regardless of
  // whether the plugin honors the `pane` option.
  function _routeRenderer(map) {
    if (!map || typeof window.L === 'undefined') return null;
    if (!map._joshRouteRenderer) {
      map._joshRouteRenderer = window.L.svg({ pane: 'joshRoutes' });
      map._joshRouteRenderer.addTo(map);
    }
    return map._joshRouteRenderer;
  }

  // Map a JOSH determination tier → Leaflet AwesomeMarkers color keyword.
  // Must mirror agents/visualization/demo.py _tier_to_marker_color() so that
  // runtime markers drawn for browser/.json-loaded projects match the pre-baked
  // Folium markers used by pipeline projects.
  function _tierToMarkerColor(tier) {
    if (tier === 'MINISTERIAL')                        return 'green';
    if (tier === 'MINISTERIAL WITH STANDARD CONDITIONS') return 'orange';
    if (tier === 'DISCRETIONARY')                       return 'red';
    return 'gray';
  }

  // Build a Leaflet L.circle mirroring the dashed search-radius circle
  // Folium bakes into each pipeline project's FeatureGroup.  Radius is
  // `parameters.serving_route_radius_miles` (default 0.5 mi) converted to
  // meters.  Used for browser / reloaded / opened-from-.json projects that
  // have no Folium FG.
  function _buildRuntimeRadiusCircle(project) {
    if (typeof window === 'undefined' || !window.L) return null;
    if (project.lat == null || project.lng == null) return null;
    try {
      const params       = (_jd() && _jd().parameters) || {};
      const radiusMiles  = +(params.serving_route_radius_miles || 0.5);
      const radiusMeters = radiusMiles * 1609.344;
      const tier  = (project.result && project.result.tier) || '';
      const color = TIER_COLOR[tier] || '#7f7f7f';
      return window.L.circle([project.lat, project.lng], {
        radius:      radiusMeters,
        color:       color,
        weight:      1.5,
        fill:        true,
        fillColor:   color,
        fillOpacity: 0.04,
        dashArray:   '8 4',
        interactive: false,
      });
    } catch (_) {
      return null;
    }
  }

  // Build a Leaflet L.marker using the same AwesomeMarkers icon Folium bakes
  // into analysis_map.html for pipeline projects.  Used for browser projects
  // (created via + New, reloaded from localStorage, or opened from a .json
  // file) — they have no folium_fg_name, so without this runtime marker no
  // home icon would render on the map when they're selected.
  function _buildRuntimeHomeMarker(project) {
    if (typeof window === 'undefined' || !window.L || !window.L.AwesomeMarkers) return null;
    if (project.lat == null || project.lng == null) return null;
    try {
      const tier  = (project.result && project.result.tier) || '';
      const icon  = window.L.AwesomeMarkers.icon({
        markerColor: _tierToMarkerColor(tier),
        iconColor:   'white',
        icon:        'home',
        prefix:      'fa',
        extraClasses: 'fa-rotate-0',
      });
      const tooltip = (project.name || 'Untitled') + (tier ? ' · ' + tier : '');
      return window.L.marker([project.lat, project.lng], { icon, zIndexOffset: 400 })
        .bindTooltip(tooltip, { sticky: true });
    } catch (_) {
      return null;
    }
  }

  function _drawRoutes(id) {
    _clearRoutes();
    const project = getProject(id);
    if (!project || !project.result) return;
    const map = _getMap();
    if (!map) return;
    // v4.12 (all-viable-routes): dim the citywide heatmap and render project
    // routes in a dedicated pane above it.  Without this, routes 3+ at the
    // tail of the opacity hierarchy vanish into the ~8K heatmap polylines.
    _ensureRoutePane(map);
    const overlayPane = map.getPane('overlayPane');
    if (overlayPane) overlayPane.style.opacity = '0.2';
    // Show the Folium FeatureGroup baked for this project (search radius + route GeoJSON).
    // Pipeline projects carry folium_fg_name → sidebar.js just toggles the pre-baked layer.
    // Browser / reloaded / opened-from-.json projects have no Folium FG — they fall
    // through to the runtime-marker branch below so their home icon still renders.
    const hasFoliumFg = !!(
      project.folium_fg_name &&
      typeof window !== 'undefined' &&
      window[project.folium_fg_name]
    );
    if (hasFoliumFg) {
      try { map.addLayer(window[project.folium_fg_name]); } catch (_) {}
    } else {
      // Runtime search-radius circle + home marker for browser projects.
      // Tracked in _routeLayers so _clearRoutes() removes them on deselect
      // or project switch.  Circle is added first so the home marker renders
      // on top of it in z-order.
      const radiusCircle = _buildRuntimeRadiusCircle(project);
      if (radiusCircle) {
        radiusCircle.addTo(map);
        _routeLayers.push(radiusCircle);
      }
      const homeMarker = _buildRuntimeHomeMarker(project);
      if (homeMarker) {
        homeMarker.addTo(map);
        _routeLayers.push(homeMarker);
      }
    }
    const bkMap = _jd().graph ? (function () {
      const m = new Map();
      (_jd().graph.edges || []).forEach(e => m.set(String(e.osmid), e));
      return m;
    }()) : new Map();

    // v4.13 (route-display-ux): routes are evidence of evacuee behavior under
    // User Equilibrium, not a menu of options.  Default view surfaces only the
    // controlling (worst-case) route — the binding evidence for the
    // determination.  "Show all viable routes" reveals the others as faint
    // navy context lines (uniform color: context routes are inputs, not
    // alternatives).
    //
    // The controlling route uses red/green to communicate the determination
    // viscerally: red when it exceeds the ΔT threshold (flagged →
    // DISCRETIONARY-binding), green when it passes (CONDITIONAL-binding).
    // Per-route color is safe ONLY on the controlling route because no menu
    // of options is visible — the route shown IS the determination.
    // See docs/JOSH_Legal_Defensibility_Memo.md §3.6, §8.6.
    const NAVY    = '#1c4a6e';   // context routes — neutral supporting evidence
    const FAIL    = '#e74c3c';   // controlling route when flagged
    const PASS    = '#27ae60';   // controlling route when within threshold
    const allPaths   = (project.result.paths || []).slice().sort(
      (a, b) => (+(a.cost_s || 0)) - (+(b.cost_s || 0))
    );
    const controllingPath = _controllingPath(allPaths);
    const showAll         = _showAllRoutes.get(id) === true;
    // When showAll: per-route toggles filter the context routes.  When !showAll:
    // only the controlling route renders regardless of any per-route toggles.
    const contextPaths = showAll
      ? _visiblePaths(id, allPaths).filter(p => _pathId(p) !== _pathId(controllingPath))
      : [];

    const _antPathFn = typeof window.L !== 'undefined'
      ? (window.L.antPath || (window.L.polyline && window.L.polyline.antPath))
      : null;
    // Shared renderer attached to joshRoutes pane — forces both AntPath
    // sub-polylines and the bottleneck overlay into the correct pane,
    // bypassing the leaflet-ant-path plugin's pane-option neglect.
    const routeRenderer = _routeRenderer(map);

    // ── Helper: draw one route + its bottleneck overlay ──
    function _drawOneRoute(path, opts) {
      const coords = path.path_coords || path.coordinates || [];
      if (coords.length < 2) return;
      // Main AntPath.
      if (_antPathFn) {
        const ap = _antPathFn(coords, {
          color: opts.color, weight: opts.weight, opacity: opts.opacity,
          delay: 1200, dashArray: [10, 20],
          pane: 'joshRoutes',
          renderer: routeRenderer,
        });
        const tip = (opts.label || 'Route') + '  ·  exit ' +
                    ((+(path.cost_s || 0)) / 60).toFixed(1) + ' min  ·  ΔT ' +
                    (+(path.delta_t || 0)).toFixed(2) + ' min';
        ap.bindTooltip(tip, { sticky: true });
        ap.addTo(map);
        _routeLayers.push(ap);
      }
      // Bottleneck segment overlay (same color, thicker).
      const bkEdge = bkMap.get(String(path.bottleneck_osmid || ''));
      if (bkEdge && bkEdge.geom && bkEdge.geom.length >= 2 && typeof window.L !== 'undefined') {
        const bl = window.L.polyline(bkEdge.geom, {
          color: opts.color, weight: opts.weight + 2, opacity: opts.opacity,
          pane: 'joshRoutes',
          renderer: routeRenderer,
        });
        const bnTip = (opts.label || 'Route') + ' bottleneck' +
                      (path.bottleneck_name ? ': ' + _formatBottleneck(path) : '');
        bl.bindTooltip(bnTip, { sticky: true });
        bl.addTo(map);
        _routeLayers.push(bl);
      }
    }

    // Context routes first (so they render under the controlling route).
    // Uniform navy at low opacity — supporting evidence, not focal.
    contextPaths.forEach(p => _drawOneRoute(p, {
      color: NAVY, weight: 2, opacity: 0.45, label: 'Viable route',
    }));

    // Controlling route last — prominent (thick, slightly translucent so
    // the marching ants read as a moving overlay rather than a solid stripe).
    // Opacity 0.8 matches the pre-v4.12 setting that was tuned for demo
    // visibility against the citywide basemap + dimmed heatmap.
    if (controllingPath) {
      const ctrlColor = controllingPath.flagged ? FAIL : PASS;
      _drawOneRoute(controllingPath, {
        color: ctrlColor, weight: 5, opacity: 0.8,
        label: 'Controlling route',
      });
    }

    // Pan to fit routes — include the project's own coordinates so the home
    // marker is always inside the viewport.  Fit to whatever's drawn.
    if (_routeLayers.length > 0) {
      try {
        const drawnPaths = controllingPath ? [controllingPath, ...contextPaths] : contextPaths;
        const allCoords = drawnPaths.flatMap(p => p.path_coords || p.coordinates || []);
        if (project.lat != null && project.lng != null) {
          allCoords.push([project.lat, project.lng]);
        }
        if (allCoords.length > 0) map.fitBounds(allCoords, { padding: [20, 20] });
      } catch (_) {}
    }
  }

  function _enterPinMode() {
    if (typeof window !== 'undefined') window._joshPinModeActive = true;
    const map = _getMap();
    if (map) {
      try { map.getContainer().style.cursor = 'crosshair'; } catch (_) {}
    }
  }

  function _exitPinMode() {
    if (typeof window !== 'undefined') window._joshPinModeActive = false;
    const map = _getMap();
    if (map) {
      try { map.getContainer().style.cursor = ''; } catch (_) {}
    }
  }

  function _placePinMarker(lat, lng) {
    _clearPinMarker();
    const map = _getMap();
    if (!map || typeof window.L === 'undefined') return;
    const icon = window.L.divIcon({
      className: '',
      html: '<div style="width:18px;height:18px;border-radius:50%;background:rgba(41,128,185,0.25);' +
            'border:2px dashed #2980b9;box-sizing:border-box;"></div>',
      iconSize:   [18, 18],
      iconAnchor: [9, 9],
    });
    _pinMarker = window.L.marker([lat, lng], {
      icon, draggable: true, zIndexOffset: 500,
    }).addTo(map);
    _pinMarker.on('dragend', function () {
      const ll = _pinMarker.getLatLng();
      onPinPlaced(ll.lat, ll.lng);
    });
  }

  function _clearPinMarker() {
    const map = _getMap();
    if (_pinMarker && map) {
      try { map.removeLayer(_pinMarker); } catch (_) {}
    }
    _pinMarker = null;
  }

  // ── Init ──────────────────────────────────────────────────────────────────────
  function init() {
    // Load pipeline-seeded projects from JOSH_DATA.projects (source: "pipeline")
    const seeds = _jd().projects || [];
    for (const seed of seeds) {
      const exists = _projects.find(p => p.id === seed.id);
      if (exists) continue;
      _projects.push({
        id:                  seed.id || _uuid(),
        schema_v:            SCHEMA_V,
        city_slug:           seed.city_slug  || _citySlug(),
        josh_version:        _joshVer(),
        parameters_version:  _paramsVer(),
        name:                seed.name    || '',
        address:             seed.address || '',
        lat:                 seed.lat     != null ? +seed.lat : null,
        lng:                 seed.lng     != null ? +seed.lng : null,
        units:               +(seed.units   || 50),
        stories:             +(seed.stories || 4),
        source:              'pipeline',
        created_at:          new Date().toISOString(),
        analyzed_at:         new Date().toISOString(),
        result:              seed.result  || null,
        brief_cache:         seed.brief_cache || null,
        folium_fg_name:      seed.folium_fg_name || null,
        _handle:             null,
        _stale:              false,
      });
    }

    // Restore browser-created projects from localStorage (synchronous, cheap)
    _loadFromLocalStorage();

    _render();

    // Attempt session restore from IndexedDB (async, non-blocking)
    if (_hasFSAPI) {
      _loadAllHandles().then(handles => {
        if (handles.size === 0) return;
        // Filter out handles whose IDs are already in the list (pipeline seeds)
        const newHandles = new Map([...handles].filter(([id]) =>
          !_projects.find(p => p.id === id)
        ));
        if (newHandles.size === 0) return;
        _restoreBanner = true;
        _render();
        // Store handles map for restore callback
        window._joshSidebarRestoreHandles = newHandles;
      }).catch(() => {});
    }
  }

  async function _doSessionRestore() {
    _restoreBanner = false;
    const handles = window._joshSidebarRestoreHandles || new Map();
    window._joshSidebarRestoreHandles = null;
    for (const [id, handle] of handles) {
      try {
        await handle.requestPermission({ mode: 'readwrite' });
        await _loadFromHandle(handle);
      } catch (e) {
        _showError('Could not restore ' + (handle.name || id) + ': ' + e.message);
      }
    }
    _render();
  }

  function _dismissRestore() {
    _restoreBanner = false;
    window._joshSidebarRestoreHandles = null;
    _render();
  }

  // ── onPinPlaced (called by map click handler from demo.py) ───────────────────
  function onPinPlaced(lat, lng) {
    _formLat = lat;
    _formLng = lng;
    _placePinMarker(lat, lng);
    _exitPinMode();
    // If form is open, run/schedule analysis for the form project
    if (_formMode && _formProjectId) {
      const project = getProject(_formProjectId);
      if (project) {
        updateProject(_formProjectId, { lat, lng });
        _scheduleAnalysis(_formProjectId, result => {
          _formResult = result;
          _render();
        });
      }
    }
    _render();
  }

  // ── Selection ────────────────────────────────────────────────────────────────
  function selectProject(id) {
    if (_formMode) cancelForm();
    // Reset the previously-selected project's display state so each project
    // starts fresh: per-route toggles cleared and "show all viable routes"
    // flag cleared.  All toggle state is per-session, not persisted.
    if (_selectedId && _selectedId !== id) {
      _routeToggles.delete(_selectedId);
      _showAllRoutes.delete(_selectedId);
    }
    if (_selectedId === id) {
      // Click selected row again → deselect
      _routeToggles.delete(_selectedId);
      _showAllRoutes.delete(_selectedId);
      _selectedId = null;
      _clearRoutes();
    } else {
      _selectedId = id;
      _deleteConfirmId = null;
      if (id) _drawRoutes(id);
      else _clearRoutes();
    }
    _render();
  }

  // ── Form ──────────────────────────────────────────────────────────────────────
  function openNewForm() {
    if (_formMode === 'new') return;
    cancelForm();                     // clean up any previous form state
    _formMode      = 'new';
    _selectedId    = null;
    _clearRoutes();
    _formLat       = null;
    _formLng       = null;
    _formResult    = null;
    // Create a temp project so analysis has an id to update
    const tmp = createProject({ source: 'browser' });
    _formProjectId = tmp.id;
    _enterPinMode();
    _render();
  }

  function openEditForm(id) {
    cancelForm();
    const project  = getProject(id);
    if (!project) return;
    _formMode      = 'edit';
    _formProjectId = id;
    _formLat       = project.lat;
    _formLng       = project.lng;
    _formResult    = project.result;
    if (_formLat !== null) _placePinMarker(_formLat, _formLng);
    _render();
  }

  function cancelForm() {
    if (_formMode === 'new' && _formProjectId) {
      // Remove the temp project created for the form
      deleteProject(_formProjectId);
    }
    _exitPinMode();
    _clearPinMarker();
    _clearRoutes();
    _formMode      = null;
    _formProjectId = null;
    _formLat       = null;
    _formLng       = null;
    _formResult    = null;
    _deleteConfirmId = null;
  }

  function _submitForm() {
    if (typeof document === 'undefined') return;
    const name    = (_el('josh-sb-f-name')    || {}).value || '';
    const address = (_el('josh-sb-f-addr')    || {}).value || '';
    const units   = parseInt((_el('josh-sb-f-units')  || {}).value, 10) || 50;
    const stories = parseInt((_el('josh-sb-f-stories') || {}).value, 10) || 0;
    const lat     = _formLat;
    const lng     = _formLng;

    if (lat === null) { _showError('Place a pin on the map first.'); return; }
    if (!_formProjectId) return;

    if (_formMode === 'new') {
      updateProject(_formProjectId, { name, address, units, stories, lat, lng });
      _runAnalysis(_formProjectId, result => {
        updateProject(_formProjectId, { result, brief_cache: null });
        const id = _formProjectId;
        _exitPinMode();
        _clearPinMarker();
        _formMode = null;
        _formProjectId = null;
        _formLat = _formLng = _formResult = null;
        _selectedId = id;
        _drawRoutes(id);
        _render();
      });
    } else {
      updateProject(_formProjectId, { name, address, units, stories, lat, lng, brief_cache: null });
      const id = _formProjectId;
      _exitPinMode();
      _clearPinMarker();
      _formMode = null;
      _formProjectId = null;
      _formLat = _formLng = _formResult = null;
      _selectedId = id;
      _drawRoutes(id);
      _render();
    }
  }

  // ── Delete with inline confirmation ──────────────────────────────────────────
  function _confirmDelete(id) {
    _deleteConfirmId = id;
    _render();
  }

  function _doDelete(id) {
    deleteProject(id);
    if (_selectedId === id) { _selectedId = null; _clearRoutes(); }
    _deleteConfirmId = null;
    _render();
  }

  // ── UI helpers ────────────────────────────────────────────────────────────────
  const TIER_ABBR  = { 'MINISTERIAL': 'MIN', 'MINISTERIAL WITH STANDARD CONDITIONS': 'COND', 'DISCRETIONARY': 'DISC' };
  const TIER_COLOR = { 'MINISTERIAL': '#27ae60', 'MINISTERIAL WITH STANDARD CONDITIONS': '#e67e22', 'DISCRETIONARY': '#e74c3c' };

  function _esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function _btn(bg, fg, bdr) {
    bdr = bdr || bg;
    return 'background:' + bg + ';color:' + fg + ';border:1px solid ' + bdr + ';' +
           'border-radius:4px;padding:5px 10px;font-size:12px;cursor:pointer;' +
           'font-family:system-ui,sans-serif;white-space:nowrap;';
  }

  function _inp() {
    return 'width:100%;box-sizing:border-box;border:1px solid #ccc;border-radius:4px;' +
           'padding:5px 7px;font-size:12px;font-family:system-ui,sans-serif;';
  }

  function _el(id) { return typeof document !== 'undefined' ? document.getElementById(id) : null; }

  function _sb() { return _el('josh-sidebar'); }

  function _showError(msg) {
    const sb = _sb();
    if (!sb) { console.error('[joshSidebar]', msg); return; }
    let el = _el('josh-sb-error');
    if (!el) {
      el = document.createElement('div');
      el.id = 'josh-sb-error';
      el.style.cssText = 'padding:8px 14px;color:#c0392b;font-size:11px;' +
                         'background:#fdf3f3;border-top:1px solid #f5c6c6;flex-shrink:0;';
      sb.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = '';
    clearTimeout(el._t);
    el._t = setTimeout(() => { el.style.display = 'none'; }, 5000);
  }

  function _uuid() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }

  function _slugify(s) {
    return String(s || '').toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '').slice(0, 30) || 'project';
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  function _render() {
    if (typeof document === 'undefined') return;
    const sb = _sb();
    if (!sb) return;

    sb.innerHTML = _renderHeader() + _renderRestoreBanner() + _renderList() +
                   (_formMode ? _renderForm() : _renderDetail()) + _renderFooter();

    _wireFormListeners();
  }

  function _renderHeader() {
    return '<div style="background:#1c4a6e;color:#fff;padding:12px 14px;flex-shrink:0;">' +
      '<div style="font-size:11px;opacity:0.65;margin-bottom:2px;">JOSH · Evacuation Capacity Analysis</div>' +
      '<div style="font-size:15px;font-weight:700;margin-bottom:10px;">' + _esc(_cityName()) + '</div>' +
      '<div style="display:flex;gap:6px;">' +
        '<button onclick="joshSidebar_newProject()" style="' + _btn('#2980b9','#fff') + '">+ New</button>' +
        '<button onclick="joshSidebar_openFile()" style="' + _btn('rgba(255,255,255,0.15)','#fff','rgba(255,255,255,0.3)') + '">Open\u2026</button>' +
      '</div>' +
    '</div>';
  }

  function _renderRestoreBanner() {
    if (!_restoreBanner) return '';
    return '<div style="background:#fff3cd;padding:8px 14px;font-size:11px;border-bottom:1px solid #ffc107;flex-shrink:0;">' +
      'Restore projects from last session? ' +
      '<button onclick="joshSidebar_doRestore()" style="' + _btn('#1c4a6e','#fff') + 'margin-right:4px;">Yes</button>' +
      '<button onclick="joshSidebar_dismissRestore()" style="' + _btn('#f5f5f5','#555','#ccc') + '">No</button>' +
    '</div>';
  }

  function _renderList() {
    const maxH = _formMode ? '30vh' : '40vh';
    let inner;
    if (_projects.length === 0) {
      inner = '<div style="padding:20px 14px;color:#aaa;font-size:12px;text-align:center;">' +
              'No projects yet.<br>Click <b>+ New</b> or <b>Open\u2026</b>.</div>';
    } else {
      inner = _projects.map(p => {
        const tier    = p.result ? p.result.tier : null;
        const abbr    = tier ? (TIER_ABBR[tier] || tier.slice(0, 4)) : '\u2014';
        const color   = tier ? (TIER_COLOR[tier] || '#888') : '#ccc';
        const sel     = p.id === _selectedId;
        const bg      = sel ? '#f0f7ff' : 'transparent';
        const dotFill = tier ? color : (p.lat !== null ? '#aaa' : '#ddd');
        const dot     = sel
          ? '<svg width="10" height="10" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5" fill="' + dotFill + '"/></svg>'
          : '<svg width="10" height="10" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="none" stroke="' + dotFill + '" stroke-width="1.5"/></svg>';
        return '<div onclick="joshSidebar_select(\'' + p.id + '\')" style="' +
          'display:flex;align-items:center;gap:6px;padding:7px 12px 7px 14px;' +
          'border-bottom:1px solid #f0f0f0;cursor:pointer;background:' + bg + ';">' +
          '<span style="flex-shrink:0;">' + dot + '</span>' +
          '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;" ' +
            'title="' + _esc(p.name || '\u2014') + '">' +
            (p.name ? _esc(p.name) : '<em style="color:#aaa">Untitled</em>') + '</span>' +
          '<span style="font-size:11px;font-weight:700;color:' + color + ';flex-shrink:0;">' + _esc(abbr) + '</span>' +
        '</div>';
      }).join('');
    }
    return '<div style="overflow-y:auto;max-height:' + maxH + ';border-bottom:1px solid #e8e8e8;flex-shrink:0;">' +
           inner + '</div>';
  }

  function _renderDetail() {
    if (!_selectedId) return '<div style="flex:1;"></div>';
    const p = getProject(_selectedId);
    if (!p) return '<div style="flex:1;"></div>';
    const r = p.result;

    let html = '<div style="flex:1;overflow-y:auto;padding:14px;">';

    // Project name
    html += '<div style="font-size:13px;font-weight:700;margin-bottom:8px;">' + _esc(p.name || 'Untitled') + '</div>';

    // Auto-save status line — only for browser-drawn projects (pipeline seeds are
    // reloaded from JOSH_DATA, not persisted in localStorage).
    if (p.source !== 'pipeline') {
      html += '<div style="font-size:11px;color:#7f8c8d;margin-bottom:8px;" ' +
              'title="This project is auto-saved to your browser\'s localStorage on every change. ' +
              'Click \u201CDownload .json\u201D below for an extra durable copy (survives a cache wipe).">' +
              '\u25cf Auto-saved to this browser</div>';
    }

    // Stale notice
    if (p._stale) {
      html += '<div style="font-size:11px;color:#856404;background:#fff3cd;padding:4px 8px;' +
              'border-radius:3px;margin-bottom:8px;">\u2139 Re-analyzed \u2014 parameters updated.</div>';
    }

    if (!r) {
      html += '<div style="color:#aaa;font-size:12px;">No analysis result yet.</div>';
    } else {
      const tier    = r.tier;
      const color   = TIER_COLOR[tier]  || '#888';
      const fhszLbl = FHSZ_DESC[r.hazard_zone] || r.hazard_zone || '';

      // Tier block
      html += '<div style="background:' + color + ';color:#fff;padding:8px 12px;border-radius:5px;' +
              'font-size:12px;font-weight:700;margin-bottom:10px;">' + _esc(tier) + '</div>';

      // FHSZ zone label
      html += '<div style="font-size:11px;color:#777;margin-bottom:8px;">' + _esc(fhszLbl) + '</div>';

      // Stats grid: units | vehicles
      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px;">' +
              '<div style="background:#f5f7fa;border-radius:6px;padding:8px 10px;text-align:center;">' +
                '<div style="font-size:22px;font-weight:700;color:#1c4a6e;line-height:1.1;">' + _esc(String(p.units)) + '</div>' +
                '<div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.04em;margin-top:3px;">units</div>' +
              '</div>' +
              '<div style="background:#f5f7fa;border-radius:6px;padding:8px 10px;text-align:center;">' +
                '<div style="font-size:22px;font-weight:700;color:#1c4a6e;line-height:1.1;">' + _esc(String(r.project_vehicles)) + '</div>' +
                '<div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.04em;margin-top:3px;">vehicles</div>' +
              '</div>' +
              '</div>';

      if (r.egress_minutes > 0) {
        html += '<div style="font-size:11px;color:#777;margin-bottom:8px;">' +
                r.egress_minutes.toFixed(1) + ' min egress penalty</div>';
      }

      // v4.13 (route-display-ux): the binding-evidence route is the focus.
      // The educational note paraphrases JOSH_Legal_Defensibility_Memo.md \u00a78.6:
      // routes are paths evacuees self-select, not options the project picks.
      if ((r.paths || []).length === 0) {
        html += '<div style="font-size:12px;color:#e74c3c;margin-bottom:8px;">' +
                'No evacuation routes found near this location.</div>';
      } else {
        const sortedPaths     = (r.paths || []).slice().sort(
          (a, b) => (+(a.cost_s || 0)) - (+(b.cost_s || 0))
        );
        const controllingPath = _controllingPath(sortedPaths);
        const controllingId   = _pathId(controllingPath);
        const toggleSet       = _routeToggles.get(_selectedId);
        const totalCount      = sortedPaths.length;
        const showAll         = _showAllRoutes.get(_selectedId) === true;

        // \u2500\u2500 Educational note (legal framing \u2014 see memo \u00a73.6, \u00a78.6) \u2500\u2500
        html += '<div style="font-size:11px;color:#465464;background:#eef2f7;' +
                'border-left:3px solid #1c4a6e;padding:8px 10px;border-radius:0 4px 4px 0;' +
                'margin-bottom:8px;line-height:1.45;">' +
                '<div style="font-weight:600;color:#1c4a6e;margin-bottom:2px;">' +
                  'About these routes' +
                '</div>' +
                'Routes shown are paths evacuees may self-select during an ' +
                'evacuation (User Equilibrium). The determination uses the ' +
                '<strong>worst-case route</strong> because some evacuees will ' +
                'take it \u2014 slower routes do not "fix" faster ones.' +
                '</div>';

        // \u2500\u2500 Route list header \u2500\u2500
        html += '<div style="display:flex;align-items:baseline;justify-content:space-between;' +
                'margin-bottom:6px;">' +
                '<span style="font-size:10px;color:#888;text-transform:uppercase;' +
                  'letter-spacing:0.04em;">Evacuation Routes (' + totalCount + ')</span>';

        // "Show all viable routes" toggle \u2014 visible only when > 1 route
        if (totalCount > 1) {
          html += '<button onclick="joshSidebar_toggleShowAll(\'' + _esc(_selectedId) + '\')" ' +
                  'style="background:none;border:1px solid #ccd6e0;color:#1c4a6e;' +
                    'border-radius:4px;padding:3px 8px;font-size:10px;cursor:pointer;' +
                    'text-transform:uppercase;letter-spacing:0.04em;font-weight:600;">' +
                  (showAll ? 'Hide context routes' : 'Show all ' + totalCount + ' routes') +
                  '</button>';
        }
        html += '</div>';

        // \u2500\u2500 Route cards \u2500\u2500
        let visibleCount = showAll ? 0 : 1; // controlling always visible in default
        sortedPaths.forEach((path, idx) => {
          const pid          = _pathId(path) || ('route_' + (idx + 1));
          const isControlling = pid === controllingId;
          // Effective visibility on the map:
          //   default view (showAll=false): only controlling route is drawn
          //   showAll view: per-route toggles apply; controlling always drawn
          const isOn = isControlling || (showAll && (!toggleSet || toggleSet.has(pid)));
          if (isOn && !isControlling) visibleCount++;
          const exitMin  = (+(path.cost_s || 0)) / 60;
          // Card chrome.  The controlling card carries the determination color
          // (red flagged / green within-threshold) so the sidebar matches the
          // red/green marching ants on the map.  Non-controlling cards use a
          // neutral gray edge \u2014 they're supporting evidence, not focal.
          const ctrlColor   = path.flagged ? '#e74c3c' : '#27ae60';
          const borderColor = isControlling ? ctrlColor : '#cfd6df';
          const dtColor     = isControlling ? ctrlColor : '#1c4a6e';
          const cardOpacity = isOn ? '1' : '0.45';

          html += '<div style="margin-bottom:6px;padding:8px 10px;background:#fafafa;border-radius:6px;' +
                  'border-left:3px solid ' + borderColor + ';opacity:' + cardOpacity + ';' +
                  'display:flex;gap:8px;align-items:flex-start;">' +
            '<div style="flex:1;min-width:0;">' +
              '<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:2px;flex-wrap:wrap;">' +
                '<span style="font-size:11px;font-weight:600;color:#555;text-transform:uppercase;' +
                  'letter-spacing:0.04em;">Route ' + (idx + 1) + '</span>';
          if (isControlling) {
            html += '<span style="display:inline-block;font-size:9px;font-weight:700;' +
                    'background:' + ctrlColor + ';color:#fff;border-radius:3px;padding:1px 5px;' +
                    'letter-spacing:0.06em;">CONTROLLING</span>';
          }
          html +=  '<span style="font-size:11px;color:#888;">' + exitMin.toFixed(1) + ' min exit</span>' +
              '</div>' +
              '<div style="display:flex;align-items:baseline;gap:4px;margin-bottom:' +
                (path.bottleneck_name ? '4px' : '0') + ';">' +
                '<span style="font-size:18px;font-weight:700;color:' + dtColor + ';line-height:1;">\u0394T ' +
                  (+(path.delta_t || 0)).toFixed(2) + '</span>' +
                '<span style="font-size:11px;font-weight:600;color:#666;">min</span>' +
              '</div>';
          if (path.bottleneck_name) {
            var bnDesc = _formatBottleneck(path);
            html += '<div style="font-size:11px;color:#777;">' +
                    'Bottleneck: ' + _esc(bnDesc) + '</div>';
          }
          html += '</div>';     // /flex-1 inner column

          // Per-route eye toggle \u2014 only meaningful when "Show all" is on.
          // In default view the controlling route is always shown; toggling
          // individual routes has no effect on the map, so disable the button.
          if (showAll && !isControlling) {
            const eyeIcon  = isOn
              ? '<span style="color:#1c4a6e;font-size:13px;line-height:1;">\u25cf</span>'
              : '<span style="color:#aaa;font-size:13px;line-height:1;">\u25cb</span>';
            const eyeTitle = isOn ? 'Hide this route on map' : 'Show this route on map';
            html += '<button onclick="joshSidebar_toggleRoute(\'' + _esc(_selectedId) + '\',\'' + _esc(pid) + '\')" ' +
              'title="' + eyeTitle + '" ' +
              'style="flex-shrink:0;background:none;border:1px solid #ddd;border-radius:4px;' +
                'padding:4px 7px;cursor:pointer;align-self:flex-start;">' +
              eyeIcon +
              '</button>';
          }
          html += '</div>';
        });

        // Status footer \u2014 what's on the map vs total
        if (showAll) {
          const totalVisible = 1 + (toggleSet ? sortedPaths.filter(p =>
            _pathId(p) !== controllingId && toggleSet.has(_pathId(p))
          ).length : (sortedPaths.length - 1));
          html += '<div style="font-size:11px;color:#555;margin:6px 0 10px;padding:6px 10px;' +
                  'background:#f0f4f8;border:1px solid #d6e0eb;border-radius:4px;line-height:1.4;">' +
                  'Showing <strong>' + totalVisible + '</strong> of <strong>' + totalCount + '</strong> routes ' +
                  '(controlling + context).<br>' +
                  '<span style="color:#777;">Determination uses all ' + totalCount + ' routes.</span></div>';
        } else {
          html += '<div style="font-size:11px;color:#777;margin:6px 0 10px;padding:6px 10px;' +
                  'background:#f8f9fa;border-radius:4px;line-height:1.4;">' +
                  'Showing controlling route. Determination evaluated <strong>' + totalCount + '</strong> viable routes.' +
                  '</div>';
        }
      }

      // View Report button
      html += '<button onclick="joshSidebar_openBrief(\'' + _selectedId + '\')" ' +
              'style="width:100%;margin-bottom:6px;' + _btn('#1c4a6e','#fff') + '">View Report</button>';

      // Download PDF button
      html += '<button onclick="joshSidebar_downloadDetermination(\'' + _selectedId + '\')" ' +
              'style="width:100%;margin-bottom:6px;' + _btn('#f5f5f5','#1c4a6e','#ccc') + '">Download Determination</button>';
    }

    // Edit / Delete
    if (_deleteConfirmId === _selectedId) {
      html += '<div style="font-size:12px;margin-top:6px;padding:8px;background:#fff3f3;border-radius:4px;">' +
              'Delete <b>' + _esc(p.name || 'Untitled') + '</b>?' +
              ' <button onclick="joshSidebar_doDelete(\'' + _selectedId + '\')" style="' + _btn('#e74c3c','#fff') + 'margin:0 4px;">Yes</button>' +
              '<button onclick="joshSidebar_cancelDelete()" style="' + _btn('#f5f5f5','#555','#ccc') + '">Cancel</button>' +
              '</div>';
    } else {
      html += '<div style="display:flex;gap:6px;margin-top:6px;">' +
              '<button onclick="joshSidebar_edit(\'' + _selectedId + '\')" style="flex:1;' + _btn('#f5f5f5','#555','#ccc') + '">Edit</button>' +
              '<button onclick="joshSidebar_confirmDelete(\'' + _selectedId + '\')" style="flex:1;' + _btn('#f5f5f5','#e74c3c','#ccc') + '">Delete</button>' +
              '</div>';
    }

    html += '</div>';
    return html;
  }

  function _renderForm() {
    const project    = _formProjectId ? getProject(_formProjectId) : null;
    const heading    = _formMode === 'edit' ? 'Edit Project' : 'New Project';
    const nameVal    = project ? _esc(project.name || '') : '';
    const addrVal    = project ? _esc(project.address  || '') : '';
    const unitsVal   = project ? (project.units   || 50)  : 50;
    const storiesVal = project ? (project.stories || 4)   : 4;
    const hasPin     = _formLat !== null;
    const coordText  = hasPin
      ? _formLat.toFixed(5) + '\u00b0 N, ' + Math.abs(_formLng).toFixed(5) + '\u00b0 W'
      : 'Click map to locate';

    let html = '<div style="flex:1;overflow-y:auto;padding:14px;">';
    html += '<div style="font-size:13px;font-weight:700;margin-bottom:12px;">' + heading + '</div>';

    // Name
    html += '<label style="display:block;margin-bottom:10px;">' +
            '<div style="font-size:11px;color:#777;margin-bottom:3px;">Name (optional)</div>' +
            '<input id="josh-sb-f-name" value="' + nameVal + '" placeholder="Project name" style="' + _inp() + '"></label>';

    // Address
    html += '<label style="display:block;margin-bottom:10px;">' +
            '<div style="font-size:11px;color:#777;margin-bottom:3px;">Address (optional)</div>' +
            '<input id="josh-sb-f-addr" value="' + addrVal + '" placeholder="123 Main St" style="' + _inp() + '"></label>';

    // Units + Stories
    html += '<div style="display:flex;gap:8px;margin-bottom:10px;">' +
            '<label style="flex:1;">' +
              '<div style="font-size:11px;color:#777;margin-bottom:3px;">Units</div>' +
              '<input id="josh-sb-f-units" type="number" min="1" max="9999" value="' + unitsVal + '" style="' + _inp() + '"></label>' +
            '<label style="flex:1;">' +
              '<div style="font-size:11px;color:#777;margin-bottom:3px;">Stories</div>' +
              '<input id="josh-sb-f-stories" type="number" min="0" max="60" value="' + storiesVal + '" style="' + _inp() + '"></label>' +
            '</div>';

    // Location
    html += '<div style="margin-bottom:12px;">' +
            '<div style="font-size:11px;color:#777;margin-bottom:4px;">Location</div>' +
            '<div id="josh-sb-f-coords" style="font-size:12px;color:' + (hasPin ? '#2c3e50' : '#aaa') + ';margin-bottom:6px;">' +
            _esc(coordText) + (hasPin ? ' <button onclick="joshSidebar_rePin()" style="' + _btn('#f5f5f5','#555','#ccc') + 'padding:2px 6px;font-size:11px;">Move</button>' : '') +
            '</div>' +
            (!hasPin ? '<div style="font-size:11px;color:#2980b9;">\u25ba Click anywhere on the map to place pin.</div>' : '') +
            '</div>';

    // Inline result preview
    if (_formResult) {
      const tier  = _formResult.tier;
      const color = TIER_COLOR[tier] || '#888';
      html += '<div style="background:' + color + ';color:#fff;padding:6px 10px;border-radius:4px;' +
              'font-size:12px;font-weight:700;margin-bottom:8px;">' + _esc(tier) + '</div>';
      (_formResult.paths || []).forEach(path => {
        const ok    = !path.flagged;
        const dClr  = ok ? '#27ae60' : '#e74c3c';
        html += '<div style="font-size:12px;color:' + dClr + ';margin-bottom:4px;">' +
                'Route ' + _esc(path.route_id) + ': ' + path.delta_t.toFixed(2) + ' min ' +
                (ok ? '\u2713' : '\u25b2') + '</div>';
      });
    } else if (hasPin) {
      html += '<div style="font-size:11px;color:#aaa;margin-bottom:8px;">Analyzing\u2026</div>';
    }

    // Actions
    html += '<div style="display:flex;gap:6px;margin-top:4px;">' +
            '<button onclick="joshSidebar_submitForm()" style="flex:1;' + _btn('#1c4a6e','#fff') + '">Save</button>' +
            '<button onclick="joshSidebar_cancelForm()" style="flex:1;' + _btn('#f5f5f5','#555','#ccc') + '">Cancel</button>' +
            '</div>';

    html += '</div>';
    return html;
  }

  function _renderFooter() {
    const p = _selectedId ? getProject(_selectedId) : null;
    if (!p || !p.result) return '';
    // Single download button — explicit backup/export that survives a cache wipe.
    // Pipeline-seeded projects are reproducible from the YAML source, so the download
    // is primarily useful for browser-drawn projects; show it for all for consistency.
    // Admin YAML export lives at window.joshSidebar._toYaml() for console use.
    return '<div style="padding:10px 14px;border-top:1px solid #eee;flex-shrink:0;">' +
      '<button onclick="joshSidebar_saveAs(\'' + _selectedId + '\')" ' +
      'title="Download a JSON backup of this project (for archive / email / re-import)" ' +
      'style="width:100%;' + _btn('#1c4a6e','#fff') + '">Download .json</button>' +
    '</div>';
  }

  // ── Wire live listeners on form inputs ────────────────────────────────────────
  // Every form input persists to project state on every keystroke so that a
  // subsequent _render() (triggered by onPinPlaced, the analysis debounce, or
  // any other cause) re-renders the form from up-to-date project state instead
  // of wiping in-progress user input. Only units/stories trigger re-analysis;
  // name/address persist silently without re-rendering.
  function _wireFormListeners() {
    if (!_formMode || !_formProjectId) return;

    // Name and address — persist on every keystroke, no re-render, no re-analysis.
    ['josh-sb-f-name', 'josh-sb-f-addr'].forEach(elId => {
      const el = _el(elId);
      if (!el) return;
      el.addEventListener('input', () => {
        if (!_formProjectId) return;
        const name    = (_el('josh-sb-f-name') || {}).value || '';
        const address = (_el('josh-sb-f-addr') || {}).value || '';
        updateProject(_formProjectId, { name, address });
      });
    });

    // Units and stories — persist, then debounced re-analysis + re-render.
    ['josh-sb-f-units', 'josh-sb-f-stories'].forEach(elId => {
      const el = _el(elId);
      if (!el) return;
      el.addEventListener('input', () => {
        if (!_formProjectId) return;
        const units   = parseInt((_el('josh-sb-f-units')   || {}).value, 10) || 50;
        const stories = parseInt((_el('josh-sb-f-stories') || {}).value, 10) || 0;
        updateProject(_formProjectId, { units, stories });
        if (_formLat !== null) {
          _scheduleAnalysis(_formProjectId, result => {
            _formResult = result;
            _render();
          });
        }
      });
    });
  }

  // ── Global onclick handlers (inline HTML attributes → window globals) ─────────
  if (typeof document !== 'undefined') {
    window.joshSidebar_newProject     = () => openNewForm();
    window.joshSidebar_openFile       = () => openFile();
    window.joshSidebar_select         = id => selectProject(id);
    window.joshSidebar_edit           = id => openEditForm(id);
    window.joshSidebar_confirmDelete  = id => _confirmDelete(id);
    window.joshSidebar_cancelDelete   = ()  => { _deleteConfirmId = null; _render(); };
    window.joshSidebar_doDelete       = id => _doDelete(id);
    window.joshSidebar_openBrief      = id => { const p = getProject(id); if (p) _openBrief(p); };
    window.joshSidebar_downloadDetermination = id => { const p = getProject(id); if (p) _downloadDetermination(p); };
    window.joshSidebar_submitForm     = () => _submitForm();
    window.joshSidebar_cancelForm     = () => { cancelForm(); _render(); };
    window.joshSidebar_rePin          = () => _enterPinMode();
    window.joshSidebar_save           = id => saveFile(id).then(() => _render());
    window.joshSidebar_saveAs         = id => saveAsFile(id).then(() => _render());
    window.joshSidebar_exportYaml     = () => exportYaml();
    window.joshSidebar_doRestore      = () => _doSessionRestore();
    window.joshSidebar_dismissRestore = () => _dismissRestore();
    // v4.12 (all-viable-routes): per-route map visibility toggle.
    // First toggle for a project seeds the Set with every path id, then flips the
    // requested one — keeps "absent entry = all on" invariant after explicit interaction.
    window.joshSidebar_toggleRoute    = (projectId, pathId) => {
      if (!_routeToggles.has(projectId)) {
        const proj = _projects.find(p => p.id === projectId);
        const allIds = new Set(((proj && proj.result && proj.result.paths) || [])
          .map(p => _pathId(p)).filter(Boolean));
        _routeToggles.set(projectId, allIds);
      }
      const set = _routeToggles.get(projectId);
      if (set.has(pathId)) set.delete(pathId);
      else                  set.add(pathId);
      _drawRoutes(projectId);
      _render();
    };
    // v4.13 (route-display-ux): toggle the per-project "show all viable routes"
    // flag.  Default state (false) draws only the controlling route on the map;
    // true draws every viable route as context with the controlling route still
    // distinguished by weight + gold halo.
    window.joshSidebar_toggleShowAll  = (projectId) => {
      const cur = _showAllRoutes.get(projectId) === true;
      _showAllRoutes.set(projectId, !cur);
      _drawRoutes(projectId);
      _render();
    };
  }

  // ── DOMContentLoaded — inject sidebar div ─────────────────────────────────────
  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
      if (_el('josh-sidebar')) return;  // already injected by demo.py
      const sb = document.createElement('div');
      sb.id = 'josh-sidebar';
      sb.style.cssText =
        'position:fixed;top:0;left:0;width:' + SIDEBAR_W + 'px;height:100vh;' +
        'background:#fff;box-shadow:2px 0 12px rgba(0,0,0,0.12);' +
        'display:flex;flex-direction:column;overflow:hidden;' +
        'font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;z-index:1000;';
      document.body.appendChild(sb);
      init();
    });
  }

  // ── Public API ────────────────────────────────────────────────────────────────
  if (typeof window !== 'undefined') {
    // _toYaml is exposed for the admin "promote to pipeline source" workflow:
    //   window.joshSidebar._toYaml()  → returns a YAML snippet suitable for pasting
    //   into josh-pipeline/projects/{city}_demo.yaml so the next Python rebuild
    //   bakes this project into the seeded list. Not a finding-generation step —
    //   the JS engine is already authoritative. See
    //   ~/.claude/plans/spicy-prancing-backus.md §1.
    window.joshSidebar = { init, onPinPlaced, getProjects, selectProject, _toYaml };
  }

  // CommonJS export for Node.js test runner
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      createProject,
      updateProject,
      deleteProject,
      getProject,
      getProjects,
      _normalizeResult,
      _serialize,
      _deserialize,
      _toYaml,
      _buildBriefInput,
      _citySlug,
      _paramsVer,
      _resetState() {
        _projects        = [];
        _selectedId      = null;
        _formMode        = null;
        _formProjectId   = null;
        _formLat         = null;
        _formLng         = null;
        _formResult      = null;
        _deleteConfirmId = null;
        _restoreBanner   = false;
        _dirtyIds        = new Set();
        _routeToggles.clear();
        _showAllRoutes.clear();
        // Clear localStorage for this city to avoid test cross-pollination.
        try {
          const store = (typeof localStorage !== 'undefined') ? localStorage : null;
          if (store) store.removeItem(_lsKey());
        } catch (_) {}
      },
      // localStorage test hooks
      _saveToLocalStorage,
      _loadFromLocalStorage,
      _lsKey,
      // Phase 4 test helpers
      _renderRestoreBanner,
      _setRestoreBanner(val) { _restoreBanner = !!val; },
      _markDirty,
      _markClean,
      _getDirtyIds()  { return _dirtyIds; },
      // v4.12 (all-viable-routes): route toggle test hooks
      _pathId,
      _visiblePaths,
      _routeToggles,
      _toggleRoute(projectId, pathId) {
        if (!_routeToggles.has(projectId)) {
          const proj = _projects.find(p => p.id === projectId);
          const allIds = new Set(((proj && proj.result && proj.result.paths) || [])
            .map(p => _pathId(p)).filter(Boolean));
          _routeToggles.set(projectId, allIds);
        }
        const set = _routeToggles.get(projectId);
        if (set.has(pathId)) set.delete(pathId);
        else                  set.add(pathId);
      },
      // v4.13 (route-display-ux): controlling-path + show-all toggle test hooks
      _controllingPath,
      _showAllRoutes,
      _toggleShowAll(projectId) {
        const cur = _showAllRoutes.get(projectId) === true;
        _showAllRoutes.set(projectId, !cur);
      },
    };
  }

})();

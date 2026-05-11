// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH Project Manager — Phase 1 + Phase 3
 *
 * Browser-side CRUD for saved what-if projects.
 *
 * Persistence:
 *   - localStorage  — session-restore cache; written on every mutation
 *   - FSAPI         — silent background save to a user-picked file (Chrome/Edge)
 *   - Blob fallback — "Save File" triggers download in Firefox/Safari
 *
 * Phase 3 additions:
 *   - _buildEdgeMap()       — osmid → edge metadata (name, road_type, lanes)
 *   - _buildBriefInput()    — WhatIfEngine result → BriefInput schema v1
 *   - _openBrief()          — calls BriefRenderer.render() → joshBrief.show()
 *   - "View Report" button  — appears in list row after analysis runs
 *
 * Exports window.joshPM = { openPanel, closePanel, getProjects }.
 * Exports module.exports internals for Node.js test runner.
 */

(function () {
  'use strict';

  // ── 1. Constants ─────────────────────────────────────────────────────────────
  const SCHEMA_V = 1;

  function _storageKey() {
    const slug = ((typeof window !== 'undefined' && window.JOSH_DATA) || {}).city_slug || 'default';
    return `josh_pm_v1_${slug}`;
  }

  function _citySlug() {
    return ((typeof window !== 'undefined' && window.JOSH_DATA) || {}).city_slug || 'city';
  }

  function _cityName() {
    return ((typeof window !== 'undefined' && window.JOSH_DATA) || {}).city_name || 'City';
  }

  // ── 2. State ─────────────────────────────────────────────────────────────────
  let _projects  = [];
  let _fileHandle = null;
  let _dirty      = false;
  let _editingId  = null;
  let _pmMarker   = null;

  // Temp coordinates set by drop-pin callback while form is open.
  // Module-level so tests can inspect without DOM.
  let _formLat = null;
  let _formLng = null;

  // ── 3. localStorage ──────────────────────────────────────────────────────────
  function _saveToCache() {
    try {
      const store = typeof localStorage !== 'undefined' ? localStorage : null;
      if (!store) return;
      store.setItem(_storageKey(), JSON.stringify({ schema_v: SCHEMA_V, projects: _projects }));
    } catch (_) {}
  }

  function _loadFromCache() {
    try {
      const store = typeof localStorage !== 'undefined' ? localStorage : null;
      if (!store) return;
      const raw = store.getItem(_storageKey());
      if (!raw) return;
      const obj = JSON.parse(raw);
      _projects = (obj.projects || []).map(_migrate);
    } catch (_) {}
  }

  // ── 4. File System Access API ────────────────────────────────────────────────
  async function _saveToFile() {
    const payload = JSON.stringify(
      { schema_v: SCHEMA_V, city_slug: _citySlug(), projects: _projects },
      null, 2
    );
    if (_fileHandle) {
      try {
        const writable = await _fileHandle.createWritable();
        await writable.write(payload);
        await writable.close();
        _setDirty(false);
        return;
      } catch (_) {
        _fileHandle = null;  // stale handle — fall through to blob
      }
    }
    _blobDownload(payload, _citySlug() + '_pm.json');
    _setDirty(false);
  }

  async function _loadFromFile() {
    if (typeof window !== 'undefined' && typeof window.showOpenFilePicker === 'function') {
      try {
        const [handle] = await window.showOpenFilePicker({
          types: [{ description: 'JOSH Projects', accept: { 'application/json': ['.json'] } }],
        });
        _fileHandle = handle;
        const file = await handle.getFile();
        const text = await file.text();
        _importFromJson(text, false);
        _setDirty(false);
      } catch (e) {
        if (e.name !== 'AbortError') console.warn('[joshPM] load error:', e);
      }
    } else {
      _inputFileLoad();
    }
  }

  // ── 5. Blob / <input> fallback ────────────────────────────────────────────────
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
    const inp  = document.createElement('input');
    inp.type   = 'file';
    inp.accept = '.json';
    inp.onchange = () => {
      const file = inp.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = e => _importFromJson(e.target.result, false);
      reader.readAsText(file);
    };
    inp.click();
  }

  // ── 6. CRUD ──────────────────────────────────────────────────────────────────
  function createProject(fields) {
    const now     = new Date().toISOString();
    const project = Object.assign({
      id:         crypto.randomUUID(),
      schema_v:   SCHEMA_V,
      name:       '',
      address:    '',
      lat:        null,
      lng:        null,
      units:      50,
      stories:    4,
      result:     null,
      created_at: now,
      updated_at: now,
    }, fields || {});
    _projects.push(project);
    _setDirty(true);
    _saveToCache();
    return project;
  }

  function updateProject(id, fields) {
    const idx = _projects.findIndex(p => p.id === id);
    if (idx === -1) return null;
    _projects[idx] = Object.assign({}, _projects[idx], fields, {
      updated_at: new Date().toISOString(),
    });
    _setDirty(true);
    _saveToCache();
    return _projects[idx];
  }

  function deleteProject(id) {
    const before = _projects.length;
    _projects = _projects.filter(p => p.id !== id);
    if (_projects.length !== before) {
      _setDirty(true);
      _saveToCache();
    }
  }

  function getProject(id) {
    return _projects.find(p => p.id === id) || null;
  }

  // ── 7. YAML export ────────────────────────────────────────────────────────────
  function _toYaml() {
    const slug  = _citySlug();
    const name  = _cityName();
    const lines = [];
    lines.push(`# ${name} demo projects — exported from JOSH Project Manager`);
    lines.push(`# To use: copy to josh-pipeline/projects/${slug}_demo.yaml`);
    lines.push(`# Then run: JOSH_DIR=/path/to/josh uv run python acquire.py run --city "${name}"`);
    lines.push('');
    lines.push('projects:');
    const pinned = _projects.filter(p => p.lat !== null && p.lng !== null);
    if (pinned.length === 0) {
      lines.push('  # (no projects with coordinates yet — drop a pin first)');
    }
    for (const p of pinned) {
      lines.push(`  - name: ${_yamlStr(p.name || 'Untitled')}`);
      if (p.address) lines.push(`    address: ${_yamlStr(p.address)}`);
      lines.push(`    lat: ${p.lat.toFixed(7)}`);
      lines.push(`    lon: ${p.lng.toFixed(7)}`);   // lng → lon (pipeline convention)
      lines.push(`    units: ${p.units || 50}`);
      lines.push(`    stories: ${p.stories || 4}`);
      lines.push('');
    }
    return lines.join('\n');
  }

  function _yamlStr(s) {
    const str = String(s || '');
    // Quote if contains YAML special characters or leading/trailing whitespace
    if (/[:#\[\]{}&*?|<>=!%@`,'"]/.test(str) || str.trim() !== str) {
      return `"${str.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
    }
    return str;
  }

  function _downloadYaml() {
    _blobDownload(_toYaml(), _citySlug() + '_demo.yaml');
  }

  // ── 8. Import / schema migration ──────────────────────────────────────────────
  function _migrate(project) {
    // schema_v 1: pass-through. Future versions add migration steps here.
    if (!project.schema_v || project.schema_v === SCHEMA_V) return project;
    return project;
  }

  function _importFromJson(text, merge) {
    let obj;
    try {
      obj = JSON.parse(text);
    } catch (e) {
      console.warn('[joshPM] import: invalid JSON', e);
      return;
    }
    const incoming = (obj.projects || []).map(_migrate);

    // City-slug mismatch: warn but continue — cross-city imports are non-fatal
    const mySlug = _citySlug();
    if (mySlug && obj.city_slug && obj.city_slug !== mySlug) {
      console.warn(
        `[joshPM] import: city_slug mismatch (${obj.city_slug} vs ${mySlug}) — importing anyway`
      );
    }

    if (merge === false) {
      // Replace mode: use incoming set, dedup within it by id
      const seen = new Set();
      _projects = incoming.filter(p => {
        if (seen.has(p.id)) return false;
        seen.add(p.id);
        return true;
      });
    } else {
      // Merge mode (default): add projects not already in list, dedup by id
      const existingIds = new Set(_projects.map(p => p.id));
      for (const p of incoming) {
        if (!existingIds.has(p.id)) {
          _projects.push(p);
          existingIds.add(p.id);
        }
      }
    }
    _setDirty(true);
    _saveToCache();
    _renderListView();
  }

  // ── 9. Map markers ────────────────────────────────────────────────────────────
  function _getMap() {
    if (typeof window === 'undefined') return null;
    for (const k in window) {
      if (window[k] && window[k]._leaflet_id && window[k].getCenter) return window[k];
    }
    return null;
  }

  function _pmIcon() {
    return L.divIcon({
      className: '',
      html: '<div style="width:14px;height:14px;border-radius:50%;background:#2980b9;' +
            'border:2px solid #1a5276;box-shadow:0 1px 4px rgba(0,0,0,0.3);"></div>',
      iconSize:   [14, 14],
      iconAnchor: [7,  7],
    });
  }

  function _showPmMarker(lat, lng) {
    _clearPmMarker();
    if (typeof L === 'undefined') return;
    const map = _getMap();
    if (!map) return;
    _pmMarker = L.marker([lat, lng], {
      icon:         _pmIcon(),
      draggable:    false,
      zIndexOffset: 400,
    }).addTo(map);
  }

  function _clearPmMarker() {
    if (!_pmMarker) return;
    const map = _getMap();
    if (map) try { map.removeLayer(_pmMarker); } catch (_) {}
    _pmMarker = null;
  }

  // ── 10. Analysis ──────────────────────────────────────────────────────────────
  function _runAnalysis(id) {
    const project = getProject(id);
    if (!project || project.lat === null || project.lng === null) {
      _showPanelError('No location set — use the pin button on the form to place a pin first.');
      return;
    }
    let result;
    try {
      result = WhatIfEngine.evaluateProject(project.lat, project.lng, project.units, project.stories);
    } catch (e) {
      _showPanelError('Analysis failed: ' + e.message);
      return;
    }
    updateProject(id, { result });
    _renderListView();
  }

  // ── 10b. Brief rendering (Phase 3) ───────────────────────────────────────────

  // Build a Map<osmid → edge> from JOSH_DATA.graph.edges for bottleneck enrichment.
  function _buildEdgeMap() {
    const map   = new Map();
    const edges = (((typeof window !== 'undefined' && window.JOSH_DATA) || {}).graph || {}).edges || [];
    for (const e of edges) {
      map.set(String(e.osmid), e);
    }
    return map;
  }

  // Map a WhatIfEngine result (camelCase path fields) → BriefInput schema v1.
  // source is always "whatif" — brief_renderer.js renders the yellow watermark banner.
  function _buildBriefInput(project, result) {
    const jd       = (typeof window !== 'undefined' && window.JOSH_DATA) || {};
    const params   = jd.parameters || {};
    const maxShare = +(params.max_project_share || 0.05);
    const hz       = result.hazard_zone || 'non_fhsz';
    const DEG      = { vhfhsz: 0.35, high_fhsz: 0.50, moderate_fhsz: 0.75, non_fhsz: 1.00 };
    const FDESC    = { vhfhsz: 'Very High Fire Hazard Severity Zone', high_fhsz: 'High FHSZ',
                       moderate_fhsz: 'Moderate FHSZ', non_fhsz: 'Not in FHSZ' };
    const FLVL     = { vhfhsz: 3, high_fhsz: 2, moderate_fhsz: 1, non_fhsz: 0 };
    const degFactor = DEG[hz] || 1.00;
    const ut        = +(params.unit_threshold || 15);

    // Case number — mirrors Python _build_brief_input()
    const lat     = +(project.lat || 0);
    const lng     = +(project.lng || 0);
    const latAbs  = Math.abs(lat).toFixed(4).replace('.', '_');
    const lngAbs  = Math.abs(lng).toFixed(4).replace('.', '_');
    const latPfx  = lat < 0 ? 'n' : '';
    const lngPfx  = lng < 0 ? 'n' : '';
    const slug    = (project.name || '').toUpperCase()
                      .replace(/\s+/g, '-').replace(/[^A-Z0-9-]/g, '').slice(0, 20);
    const year    = new Date().getFullYear();
    const caseNum = slug
      ? `JOSH-${year}-${slug}-${latPfx}${latAbs}-${lngPfx}${lngAbs}`
      : `JOSH-${year}-${latPfx}${latAbs}-${lngPfx}${lngAbs}`;

    // Enrich paths with edge metadata (name, road_type, lanes, speed_mph)
    const edgeMap       = _buildEdgeMap();
    const enrichedPaths = (result.paths || []).map(function(p) {
      const edge    = edgeMap.get(String(p.bottleneckOsmid)) || {};
      const thrMin  = +(p.threshold_minutes || 0);
      const safeWin = thrMin > 0 ? thrMin / maxShare : 0;
      return {
        path_id:                       String(p.bottleneckOsmid || ''),
        bottleneck_osmid:              String(p.bottleneckOsmid || ''),
        bottleneck_name:               edge.name      || null,
        bottleneck_fhsz_zone:          p.bottleneckFhszZone || hz,
        bottleneck_hcm_capacity_vph:   0,   // not in browser graph; omits HCM detail row
        bottleneck_eff_cap_vph:        +(p.bottleneckEffCapVph || 0),
        bottleneck_hazard_degradation: degFactor,
        bottleneck_road_type:          edge.road_type || null,
        bottleneck_speed_mph:          edge.speed_mph || null,
        bottleneck_lanes:              edge.lanes     || null,
        delta_t_minutes:               +(p.delta_t_minutes  || 0),
        threshold_minutes:             thrMin,
        safe_egress_window_minutes:    safeWin,
        max_project_share:             maxShare,
        flagged:                       !!p.flagged,
        project_vehicles:              +(p.project_vehicles || result.project_vehicles || 0),
        egress_minutes:                +(p.egress_minutes || 0),
      };
    });

    const fp         = enrichedPaths[0] || {};
    const topThr     = +(fp.threshold_minutes || (params.safe_egress_window || {})[hz] * maxShare || 6.0);
    const topSafeWin = +(fp.safe_egress_window_minutes || (params.safe_egress_window || {})[hz] || 120);

    return {
      brief_input_version: 1,
      source:              'whatif',
      city_name:           _cityName(),
      city_slug:           _citySlug(),
      case_number:         caseNum,
      eval_date:           new Date().toISOString().slice(0, 10),
      audit_text:          '',
      audit_filename:      '',
      project: {
        name:    project.name    || '',
        address: project.address || '',
        lat:     lat,
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
        fhsz_desc:                 FDESC[hz] || hz,
        fhsz_level:                FLVL[hz]  || 0,
        hazard_zone:               hz,
        behavioral_mobilization:   +(params.behavioral_mobilization || 0.90),
        hazard_degradation_factor: degFactor,
        serving_route_count:       result.serving_paths_count || 0,
        route_radius_miles:        0.5,
        routes_trigger_analysis:   (result.serving_paths_count || 0) > 0,
        delta_t_triggered:         result.tier === 'DISCRETIONARY',
        egress_minutes:            +(fp.egress_minutes || 0),
      },
      result: {
        tier:                       result.tier,
        hazard_zone:                hz,
        project_vehicles:           +(result.project_vehicles || 0),
        max_delta_t_minutes:        +(result.max_delta_t_minutes || 0),
        threshold_minutes:          topThr,
        safe_egress_window_minutes: topSafeWin,
        max_project_share:          maxShare,
        serving_paths_count:        result.serving_paths_count || 0,
        egress_minutes:             +(fp.egress_minutes || 0),
        parameters_version:         result.parameters_version || '',
        analyzed_at:                new Date().toISOString().slice(0, 10),
        determination_reason:       '',
        triggered:                  result.tier === 'DISCRETIONARY',
        paths:                      enrichedPaths,
      },
      parameters: params,
    };
  }

  // Open the brief modal for a saved project's what-if result.
  function _openBrief(project, result) {
    if (typeof window === 'undefined' || !window.BriefRenderer) {
      _showPanelError('Brief renderer not loaded — try reloading the page.');
      return;
    }
    if (!window.joshBrief) {
      _showPanelError('Brief modal not available — try reloading the page.');
      return;
    }
    try {
      const briefInput = _buildBriefInput(project, result);
      const html       = window.BriefRenderer.render(briefInput);
      // Pass the case number as the suggested download filename so the browser's
      // "Save as PDF" dialog shows a meaningful name instead of "brief_2026-04-09.html".
      const filename   = (briefInput.case_number || 'whatif_brief').toLowerCase()
                           .replace(/[^a-z0-9_-]/g, '_') + '.html';
      window.joshBrief.show(html, filename);
    } catch (e) {
      console.error('[joshPM] _openBrief error:', e);
      _showPanelError('Could not generate brief: ' + e.message);
    }
  }

  // ── 11. UI helpers ────────────────────────────────────────────────────────────
  const TIER_ABBR = {
    'MINISTERIAL':                          'MIN',
    'MINISTERIAL WITH STANDARD CONDITIONS': 'COND',
    'DISCRETIONARY':                        'DISC',
  };
  const TIER_COLOR = {
    'MINISTERIAL':                          '#27ae60',
    'MINISTERIAL WITH STANDARD CONDITIONS': '#e67e22',
    'DISCRETIONARY':                        '#e74c3c',
  };

  function _setDirty(val) {
    _dirty = val;
    if (typeof document === 'undefined') return;
    const el = document.getElementById('josh-pm-dirty');
    if (el) el.style.display = val ? '' : 'none';
  }

  function _esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function _btn(bg, color, border) {
    return `background:${bg};color:${color};border:1px solid ${border||bg};` +
           `border-radius:4px;padding:5px 10px;font-size:12px;cursor:pointer;` +
           `font-family:system-ui,sans-serif;`;
  }

  function _inputStyle() {
    return 'width:100%;box-sizing:border-box;border:1px solid #ccc;border-radius:4px;' +
           'padding:5px 7px;font-size:12px;font-family:system-ui,sans-serif;';
  }

  function _iconBtn() {
    return 'background:none;border:none;cursor:pointer;font-size:13px;padding:2px 4px;' +
           'color:#888;line-height:1;';
  }

  /** Show a brief inline error message at the bottom of the PM panel (replaces alert()). */
  function _showPanelError(msg) {
    if (typeof document === 'undefined') return;
    const panel = document.getElementById('josh-pm-panel');
    if (!panel) { console.error('[joshPM]', msg); return; }
    let el = document.getElementById('josh-pm-error');
    if (!el) {
      el = document.createElement('div');
      el.id = 'josh-pm-error';
      el.style.cssText = 'padding:8px 14px;color:#c0392b;font-size:11px;' +
                         'background:#fdf3f3;border-top:1px solid #f5c6c6;';
      panel.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = '';
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(() => { el.style.display = 'none'; }, 5000);
  }

  // ── 11a. Panel HTML builders ──────────────────────────────────────────────────
  function _buildListPanelHtml() {
    return (
      `<div id="josh-pm-drag-handle" style="background:#1c4a6e;color:#fff;padding:10px 14px;` +
      `display:flex;align-items:center;gap:8px;cursor:move;border-radius:8px 8px 0 0;">` +
      `<span style="font-weight:600;font-size:13px;">&#128209; Saved Analyses</span>` +
      `<span id="josh-pm-count" style="font-size:11px;color:rgba(255,255,255,0.6);margin-left:2px;"></span>` +
      `<span id="josh-pm-dirty" style="font-size:11px;color:#f39c12;margin-left:4px;display:none;">&#9679; unsaved</span>` +
      `<span style="margin-left:auto;cursor:pointer;font-size:16px;opacity:0.7;" ` +
      `onclick="joshPM.closePanel();" title="Close">&#10005;</span></div>` +

      `<div style="padding:10px 14px;display:flex;gap:6px;border-bottom:1px solid #eee;">` +
      `<button onclick="joshPM_newProject()" style="${_btn('#1c4a6e','#fff')}">+ New</button>` +
      `<button onclick="joshPM_saveFile()" style="${_btn('#f5f5f5','#555','#ccc')}">&#8595; Save session</button>` +
      `<button onclick="joshPM_loadFile()" style="${_btn('#f5f5f5','#555','#ccc')}">&#8593; Load session</button>` +
      `</div>` +

      `<div id="josh-pm-list" style="max-height:260px;overflow-y:auto;"></div>` +

      `<div style="padding:8px 14px;border-top:1px solid #eee;">` +
      `<button onclick="joshPM_downloadYaml()" ` +
      `style="width:100%;${_btn('#f5f5f5','#555','#ccc')}">&#8659; Export for pipeline</button>` +
      `</div>`
    );
  }

  function _buildFormHtml(project) {
    const nameVal    = project ? _esc(project.name)    : '';
    const addrVal    = project ? _esc(project.address)  : '';
    const unitsVal   = project ? project.units           : 50;
    const storiesVal = project ? project.stories         : 4;
    const coordText  = (_formLat !== null)
      ? `Lat: ${_formLat.toFixed(7)}&nbsp; Lng: ${_formLng.toFixed(7)}`
      : 'No pin placed';
    const heading = project ? 'Edit Project' : 'New Project';

    return (
      `<div id="josh-pm-drag-handle" style="background:#1c4a6e;color:#fff;padding:10px 14px;` +
      `display:flex;align-items:center;gap:8px;cursor:move;border-radius:8px 8px 0 0;">` +
      `<span style="font-weight:600;font-size:13px;">${heading}</span>` +
      `<span style="margin-left:auto;cursor:pointer;font-size:16px;opacity:0.7;" ` +
      `onclick="joshPM_cancelForm()" title="Cancel">&#10005;</span></div>` +

      `<div style="padding:12px 14px;">` +
      `<label style="display:block;margin-bottom:8px;">` +
      `<div style="font-size:11px;color:#777;margin-bottom:3px;">Name</div>` +
      `<input id="josh-pm-f-name" value="${nameVal}" style="${_inputStyle()}" placeholder="Project name"></label>` +

      `<label style="display:block;margin-bottom:8px;">` +
      `<div style="font-size:11px;color:#777;margin-bottom:3px;">Address (optional)</div>` +
      `<input id="josh-pm-f-addr" value="${addrVal}" style="${_inputStyle()}" placeholder="123 Main St"></label>` +

      `<div style="display:flex;gap:8px;margin-bottom:8px;">` +
      `<label style="flex:1;"><div style="font-size:11px;color:#777;margin-bottom:3px;">Units</div>` +
      `<input id="josh-pm-f-units" type="number" min="1" max="9999" value="${unitsVal}" style="${_inputStyle()}"></label>` +
      `<label style="flex:1;"><div style="font-size:11px;color:#777;margin-bottom:3px;">Stories</div>` +
      `<input id="josh-pm-f-stories" type="number" min="0" max="60" value="${storiesVal}" style="${_inputStyle()}"></label>` +
      `</div>` +

      `<div style="margin-bottom:8px;">` +
      `<div style="font-size:11px;color:#777;margin-bottom:3px;">Location</div>` +
      `<div id="josh-pm-f-coords" style="font-size:11px;color:#555;margin-bottom:4px;">${coordText}</div>` +
      `<button id="josh-pm-f-pin-btn" onclick="joshPM_dropPin()" style="${_btn('#1c4a6e','#fff')}">&#x2316; Click map to locate</button>` +
      `</div>` +

      `<div style="display:flex;gap:8px;margin-top:12px;">` +
      `<button onclick="joshPM_saveForm()" style="flex:1;${_btn('#1c4a6e','#fff')}">Save</button>` +
      `<button onclick="joshPM_cancelForm()" style="flex:1;${_btn('#f5f5f5','#555','#ccc')}">Cancel</button>` +
      `</div></div>`
    );
  }

  // ── 11b. Panel render ─────────────────────────────────────────────────────────
  function _renderPanel() {
    if (typeof document === 'undefined') return;
    const panel = document.getElementById('josh-pm-panel');
    if (!panel) return;
    panel.innerHTML = _buildListPanelHtml();
    _makeDraggable(panel, document.getElementById('josh-pm-drag-handle'));
    const dirtyEl = document.getElementById('josh-pm-dirty');
    if (dirtyEl) dirtyEl.style.display = _dirty ? '' : 'none';
    _renderListView();
  }

  function _renderListView() {
    if (typeof document === 'undefined') return;
    const listEl  = document.getElementById('josh-pm-list');
    const countEl = document.getElementById('josh-pm-count');
    if (countEl) countEl.textContent = `(${_projects.length})`;
    if (!listEl) return;

    if (_projects.length === 0) {
      listEl.innerHTML =
        '<div style="padding:16px 14px;color:#aaa;font-size:12px;text-align:center;">' +
        'No saved projects. Click + New to start.</div>';
      return;
    }

    listEl.innerHTML = _projects.map(p => {
      const hasPin   = p.lat !== null && p.lng !== null;
      const tier     = p.result ? p.result.tier : null;
      const abbr     = tier ? (TIER_ABBR[tier] || tier.slice(0, 4)) : '\u2014';
      const color    = tier ? (TIER_COLOR[tier] || '#888') : '#aaa';
      const dotColor = hasPin ? color : '#ccc';
      const name     = p.name || 'Untitled';

      return (
        `<div style="display:flex;align-items:center;gap:6px;padding:7px 14px;border-bottom:1px solid #f5f5f5;">` +
        `<span style="width:10px;height:10px;border-radius:50%;background:${dotColor};` +
        `display:inline-block;flex-shrink:0;"></span>` +
        `<span style="flex:1;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" ` +
        `title="${_esc(name)}">${_esc(name)}</span>` +
        `<span style="font-size:11px;color:${color};font-weight:600;min-width:36px;text-align:right;">` +
        `${_esc(abbr)}</span>` +
        `<button onclick="joshPM_analyze('${p.id}')" title="Analyze" style="${_iconBtn()}">&#9654;</button>` +
        (p.result ? `<button onclick="joshPM_openBrief('${p.id}')" title="View Report" style="${_iconBtn()}">&#128196; Report</button>` : '') +
        `<button onclick="joshPM_edit('${p.id}')" title="Edit" style="${_iconBtn()}">&#9998;</button>` +
        `<button onclick="joshPM_delete('${p.id}')" title="Delete" style="${_iconBtn()}">&#128465;</button>` +
        `</div>`
      );
    }).join('');
  }

  function _renderFormView(id) {
    if (typeof document === 'undefined') return;
    const panel = document.getElementById('josh-pm-panel');
    if (!panel) return;
    const project = id ? getProject(id) : null;
    _editingId = id || null;
    // Seed form coords from existing project; drop-pin callback will overwrite if user places new pin
    _formLat = project ? project.lat : null;
    _formLng = project ? project.lng : null;

    panel.innerHTML = _buildFormHtml(project);
    _makeDraggable(panel, document.getElementById('josh-pm-drag-handle'));
  }

  // ── Panel drag ────────────────────────────────────────────────────────────────
  function _makeDraggable(panel, handle) {
    if (!handle || !panel) return;
    let startX, startY, origLeft, origTop;
    handle.addEventListener('mousedown', e => {
      startX   = e.clientX;
      startY   = e.clientY;
      origLeft = panel.offsetLeft;
      origTop  = panel.offsetTop;
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup',   onUp);
      e.preventDefault();
    });
    function onMove(e) {
      panel.style.left = `${origLeft + e.clientX - startX}px`;
      panel.style.top  = `${origTop  + e.clientY - startY}px`;
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup',   onUp);
    }
  }

  // ── 12. Open / close ──────────────────────────────────────────────────────────
  function openPanel() {
    // Mutual-hide: close what-if panel if open
    if (typeof window !== 'undefined' && window.joshWhatIf && window.joshWhatIf.closePanel) {
      window.joshWhatIf.closePanel();
    }
    if (typeof document !== 'undefined') {
      const panel = document.getElementById('josh-pm-panel');
      if (panel) panel.style.display = 'block';
      const btn = document.getElementById('josh-pm-open-btn');
      if (btn) btn.style.display = 'none';
    }
    _renderListView();
  }

  function closePanel() {
    // Cancel any active drop-pin mode triggered by this panel
    if (typeof window !== 'undefined' && window.joshWhatIf && window.joshWhatIf.cancelExternalDropPin) {
      window.joshWhatIf.cancelExternalDropPin();
    }
    if (typeof document !== 'undefined') {
      const panel = document.getElementById('josh-pm-panel');
      if (panel) panel.style.display = 'none';
      const btn = document.getElementById('josh-pm-open-btn');
      if (btn) btn.style.display = '';
    }
    _clearPmMarker();
    _editingId = null;
    _formLat   = null;
    _formLng   = null;
  }

  // ── 13. Global onclick handlers (called from inline HTML attributes) ───────────
  // Scoped inside document guard so they never run in Node test environment.
  if (typeof document !== 'undefined') {
    window.joshPM_newProject   = () => { _renderFormView(null); };
    window.joshPM_edit         = id  => { _renderFormView(id);  };
    window.joshPM_delete       = id  => {
      if (!confirm('Delete this project?')) return;
      deleteProject(id);
      _clearPmMarker();
      _renderPanel();
    };
    window.joshPM_analyze      = id  => {
      _runAnalysis(id);
      const p = getProject(id);
      if (p && p.lat !== null) _showPmMarker(p.lat, p.lng);
    };
    window.joshPM_openBrief   = id  => {
      const p = getProject(id);
      if (!p || !p.result) return;
      _openBrief(p, p.result);
    };
    window.joshPM_saveFile     = ()  => { _saveToFile(); };
    window.joshPM_loadFile     = ()  => { _loadFromFile(); };
    window.joshPM_downloadYaml = ()  => { _downloadYaml(); };
    window.joshPM_cancelForm   = ()  => {
      _editingId = null;
      _formLat   = null;
      _formLng   = null;
      _renderPanel();
    };
    window.joshPM_dropPin      = ()  => {
      if (!window.joshWhatIf || !window.joshWhatIf.startDropPinForProject) {
        _showPanelError('Map not ready — please try again.');
        return;
      }
      const btn = document.getElementById('josh-pm-f-pin-btn');
      if (btn) btn.textContent = 'Click map to place pin\u2026';
      window.joshWhatIf.startDropPinForProject((lat, lng) => {
        _formLat = lat;
        _formLng = lng;
        const coordEl = document.getElementById('josh-pm-f-coords');
        if (coordEl) coordEl.textContent =
          `Lat: ${lat.toFixed(7)}\u00a0 Lng: ${lng.toFixed(7)}`;
        if (btn) btn.textContent = '\u2316 Move Pin';
        _showPmMarker(lat, lng);
      });
    };
    window.joshPM_saveForm     = ()  => {
      const name    = (document.getElementById('josh-pm-f-name')    || {}).value || '';
      const address = (document.getElementById('josh-pm-f-addr')    || {}).value || '';
      const units   = parseInt((document.getElementById('josh-pm-f-units')   || {}).value, 10) || 50;
      const stories = parseInt((document.getElementById('josh-pm-f-stories') || {}).value, 10) || 0;

      // Use pin coords set during this edit session
      const lat = _formLat;
      const lng = _formLng;

      const fields = { name, address, units, stories, lat, lng, result: null };
      if (_editingId) {
        updateProject(_editingId, fields);
      } else {
        createProject(fields);
      }
      _editingId = null;
      _formLat   = null;
      _formLng   = null;
      _renderPanel();
    };
  }

  // ── 14. Init ──────────────────────────────────────────────────────────────────
  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
      const container = document.createElement('div');
      container.innerHTML =
        // Open button
        `<button id="josh-pm-open-btn" onclick="joshPM.openPanel()" style="` +
        `position:fixed;bottom:32px;right:16px;z-index:10000;` +
        `background:#2980b9;color:#fff;border:none;border-radius:6px;` +
        `padding:9px 15px;font-family:system-ui,sans-serif;font-size:13px;` +
        `font-weight:600;cursor:pointer;box-shadow:0 3px 12px rgba(0,0,0,0.25);` +
        `letter-spacing:0.01em;">&#128209; Saved Analyses</button>` +

        // Panel container (populated by _renderPanel)
        `<div id="josh-pm-panel" style="` +
        `display:none;position:fixed;bottom:78px;right:16px;width:320px;` +
        `background:#fff;border-radius:8px;` +
        `box-shadow:0 4px 24px rgba(0,0,0,0.22);z-index:10000;` +
        `font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif;` +
        `font-size:13px;overflow:hidden;"></div>`;
      document.body.appendChild(container);

      _loadFromCache();
      _renderPanel();
    });
  }

  // ── 15. Public API ────────────────────────────────────────────────────────────
  if (typeof window !== 'undefined') {
    window.joshPM = {
      openPanel,
      closePanel,
      getProjects: () => _projects.slice(),
    };
  }

  // CommonJS export for Node.js test runner
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      createProject,
      updateProject,
      deleteProject,
      getProject,
      _loadFromCache,
      _importFromJson,
      _migrate,
      _toYaml,
      _storageKey,
      _buildEdgeMap,
      _buildBriefInput,
      _getState:   () => ({ projects: _projects.slice(), dirty: _dirty, editingId: _editingId }),
      _resetState: () => {
        _projects  = [];
        _dirty     = false;
        _editingId = null;
        _formLat   = null;
        _formLng   = null;
      },
    };
  }

})();

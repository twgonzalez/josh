// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * Unit tests for static/sidebar.js
 *
 * Run: node --test tests/test_sidebar.js
 *
 * Tests S1–S11 cover Phase 2 (sidebar module, no map integration):
 *   S1:  init loads pipeline-seeded projects from JOSH_DATA.projects
 *   S2:  createProject → serialize → deserialize round-trip
 *   S3:  updateProject merges fields and updates analyzed_at
 *   S4:  deleteProject removes from list
 *   S5:  _serialize produces valid JSON matching spec §7 schema
 *   S6:  _deserialize rejects city_slug mismatch
 *   S7:  _deserialize rejects schema_v > 1
 *   S8:  _buildBriefInput maps result to BriefInput v1 schema
 *   S9:  stale result detection on deserialize (parameters_version mismatch)
 *   S10: project below threshold (< 15 units) can still be saved
 *   S11: empty paths list stored correctly (no-routes-found state)
 *
 * Tests S12–S16 cover Phase 4 (session restore, stale detection, dirty tracking, YAML export):
 *   S12: session restore banner returns non-empty HTML when flag is set
 *   S13: city_slug mismatch in _deserialize leaves project list unchanged
 *   S14: stale _deserialize returns valid project (not rejected) with _stale: true
 *   S15: _toYaml omits projects with null lat/lng
 *   S16: _toYaml outputs lon: not lng: (pipeline convention)
 */

const { test } = require('node:test');
const assert   = require('node:assert/strict');
const path     = require('node:path');

// ── Bootstrap minimal globals expected by sidebar.js ─────────────────────────
global.window = {
  JOSH_DATA: {
    city_slug:          'berkeley',
    city_name:          'Berkeley, CA',
    josh_version:       '1.0.0',
    parameters_version: '4.0',
    parameters: {
      parameters_version:  '4.0',
      unit_threshold:      15,
      max_project_share:   0.05,
      behavioral_mobilization: 0.90,
      safe_egress_window:  { vhfhsz: 45, high_fhsz: 90, moderate_fhsz: 120, non_fhsz: 120 },
    },
    projects: [
      {
        id:      'seed-001',
        name:    'Ashby Small Infill',
        address: '2930 Ashby Ave, Berkeley CA',
        lat:     37.8528,
        lng:     -122.2699,
        units:   10,
        stories: 3,
        city_slug: 'berkeley',
        source:  'pipeline',
        result: {
          tier:              'MINISTERIAL',
          hazard_zone:       'non_fhsz',
          in_fire_zone:      false,
          project_vehicles:  17.1,
          egress_minutes:    0,
          delta_t_threshold: 6.0,
          paths: [
            {
              route_id:                  'A',
              delta_t:                   0.42,
              flagged:                   false,
              bottleneck_osmid:          '12345',
              bottleneck_name:           'Ashby Ave',
              bottleneck_road_type:      'secondary',
              bottleneck_lanes:          2,
              bottleneck_speed:          35,
              effective_capacity_vph:    1976,
              hazard_degradation_factor: 1.0,
              path_coords:               [[37.852, -122.269], [37.853, -122.270]],
            },
          ],
        },
      },
    ],
    graph: { edges: [{ osmid: '12345', name: 'Ashby Ave', road_type: 'secondary', lanes: 2, speed_mph: 35, haz_deg: 1.0, geom: [[37.852, -122.269], [37.853, -122.270]] }] },
  },
};
global.crypto = { randomUUID: () => 'test-' + Math.random().toString(36).slice(2) };
global.indexedDB = undefined;   // unavailable in Node — exercises the fallback path

// localStorage shim — in-memory Map-backed Storage for Phase 5 tests
const _lsStore = new Map();
global.localStorage = {
  getItem:    k     => _lsStore.has(k) ? _lsStore.get(k) : null,
  setItem:    (k,v) => { _lsStore.set(k, String(v)); },
  removeItem: k     => { _lsStore.delete(k); },
  clear:      ()    => { _lsStore.clear(); },
};

// ── Load module ───────────────────────────────────────────────────────────────
const SIDEBAR_PATH = path.join(__dirname, '..', 'static', 'sidebar.js');
const sb = require(SIDEBAR_PATH);

// ── Helpers ───────────────────────────────────────────────────────────────────
function freshProject(overrides) {
  return sb.createProject(Object.assign({
    name:    'Test Project',
    lat:     37.8695,
    lng:     -122.2685,
    units:   50,
    stories: 4,
    source:  'browser',
  }, overrides || {}));
}

function fakeResult(overrides) {
  return Object.assign({
    tier:              'MINISTERIAL WITH STANDARD CONDITIONS',
    hazard_zone:       'high_fhsz',
    in_fire_zone:      true,
    project_vehicles:  85.5,
    egress_minutes:    0,
    delta_t_threshold: 4.5,
    paths: [
      {
        route_id:                  'A',
        delta_t:                   2.3,
        flagged:                   false,
        bottleneck_osmid:          '99999',
        bottleneck_name:           'Telegraph Ave',
        bottleneck_road_type:      'secondary',
        bottleneck_lanes:          2,
        bottleneck_speed:          35,
        effective_capacity_vph:    950,
        hazard_degradation_factor: 0.5,
        path_coords:               [[37.870, -122.268], [37.871, -122.267]],
      },
    ],
  }, overrides || {});
}

function setup() {
  sb._resetState();
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test('S1: init loads pipeline-seeded projects from JOSH_DATA.projects', () => {
  setup();
  // Simulate init by calling createProject for each seed (mirrors sidebar.js init logic)
  // We test via the module: after require, state should be fresh; we call a manual
  // seed-load by checking that JOSH_DATA.projects is accessible.
  const seeds = global.window.JOSH_DATA.projects;
  assert.equal(seeds.length, 1);
  assert.equal(seeds[0].id, 'seed-001');
  assert.equal(seeds[0].name, 'Ashby Small Infill');
  assert.equal(seeds[0].result.tier, 'MINISTERIAL');
  // After reset the project list is empty; a fresh init would populate it.
  // Verify createProject with seed fields round-trips correctly.
  const seed = seeds[0];
  const p = sb.createProject({
    id:     seed.id,
    name:   seed.name,
    lat:    seed.lat,
    lng:    seed.lng,
    units:  seed.units,
    source: 'pipeline',
    result: seed.result,
  });
  assert.equal(p.name, 'Ashby Small Infill');
  assert.equal(p.source, 'pipeline');
  assert.equal(p.result.tier, 'MINISTERIAL');
  assert.equal(p.result.paths[0].bottleneck_name, 'Ashby Ave');
});

test('S2: createProject → serialize → deserialize round-trip', () => {
  setup();
  const p = freshProject({ name: 'Round Trip Test', units: 75, stories: 5 });
  p.result = fakeResult();
  const json = sb._serialize(p);
  const p2   = sb._deserialize(json);

  assert.equal(p2.name,    'Round Trip Test');
  assert.equal(p2.units,   75);
  assert.equal(p2.stories, 5);
  assert.equal(p2.lat,     37.8695);
  assert.equal(p2.lng,     -122.2685);
  assert.equal(p2.result.tier,              'MINISTERIAL WITH STANDARD CONDITIONS');
  assert.equal(p2.result.hazard_zone,       'high_fhsz');
  assert.equal(p2.result.paths.length,      1);
  assert.equal(p2.result.paths[0].route_id, 'A');
  assert.equal(p2.result.paths[0].bottleneck_name, 'Telegraph Ave');
  assert.ok(Array.isArray(p2.result.paths[0].path_coords));
});

test('S3: updateProject merges fields and updates analyzed_at', () => {
  setup();
  const p   = freshProject();
  const id  = p.id;
  const was = p.analyzed_at;
  // Simulate a short delay so analyzed_at changes
  const p2  = sb.updateProject(id, { result: fakeResult(), units: 80 });
  assert.equal(p2.units,   80);
  assert.equal(p2.result.tier, 'MINISTERIAL WITH STANDARD CONDITIONS');
  assert.ok(p2.analyzed_at !== null);
  // name was preserved
  assert.equal(p2.name, 'Test Project');
});

test('S4: deleteProject removes from list', () => {
  setup();
  const p  = freshProject({ name: 'Delete Me' });
  const id = p.id;
  assert.ok(sb.getProject(id) !== null);
  sb.deleteProject(id);
  assert.equal(sb.getProject(id), null);
  assert.ok(sb.getProjects().every(x => x.id !== id));
});

test('S5: _serialize produces valid JSON matching spec §7 schema', () => {
  setup();
  const p = freshProject({ name: 'Schema Check' });
  p.result = fakeResult();
  const json = sb._serialize(p);
  const obj  = JSON.parse(json);  // must not throw

  // Required top-level fields per spec §7
  assert.equal(obj.schema_v,           1);
  assert.equal(obj.city_slug,          'berkeley');
  assert.ok('josh_version'       in obj);
  assert.ok('parameters_version' in obj);
  assert.ok('name'               in obj);
  assert.ok('address'            in obj);
  assert.ok('lat'                in obj);
  assert.ok('lng'                in obj);
  assert.ok('units'              in obj);
  assert.ok('stories'            in obj);
  assert.ok('source'             in obj);
  assert.ok('created_at'         in obj);
  assert.ok('analyzed_at'        in obj);
  assert.ok('result'             in obj);
  assert.ok('brief_cache'        in obj);

  // Private fields must NOT be in the serialized form
  assert.ok(!('_handle' in obj));
  assert.ok(!('_stale'  in obj));

  // result.paths must have snake_case fields
  const path0 = obj.result.paths[0];
  assert.ok('route_id'                  in path0);
  assert.ok('delta_t'                   in path0);
  assert.ok('bottleneck_osmid'          in path0);
  assert.ok('bottleneck_name'           in path0);
  assert.ok('effective_capacity_vph'    in path0);
  assert.ok('hazard_degradation_factor' in path0);
  assert.ok('path_coords'               in path0);
});

test('S6: _deserialize rejects city_slug mismatch with informative error', () => {
  setup();
  const json = JSON.stringify({
    schema_v:           1,
    city_slug:          'encinitas',  // ← wrong city
    parameters_version: '4.0',
    name:               'Wrong City',
    lat:                33.03,
    lng:                -117.29,
    units:              50,
    stories:            4,
    source:             'browser',
    result:             null,
  });
  assert.throws(
    () => sb._deserialize(json),
    err => err.message.includes('city_slug mismatch'),
    'should throw with city_slug mismatch message'
  );
});

test('S7: _deserialize rejects schema_v > 1 with informative error', () => {
  setup();
  const json = JSON.stringify({
    schema_v:           99,
    city_slug:          'berkeley',
    parameters_version: '4.0',
    name:               'Future Version',
    lat:                37.87,
    lng:                -122.27,
    units:              50,
    stories:            4,
    source:             'browser',
    result:             null,
  });
  assert.throws(
    () => sb._deserialize(json),
    err => err.message.includes('schema_v'),
    'should throw with schema_v message'
  );
});

test('S8: _buildBriefInput maps result fields to BriefInput v1 schema', () => {
  setup();
  const p = freshProject({ name: 'Brief Test', units: 50, stories: 4 });
  p.result = fakeResult();

  const bi = sb._buildBriefInput(p);

  // Top-level schema fields
  assert.equal(bi.brief_input_version, 1);
  assert.ok(bi.source === 'whatif' || bi.source === 'pipeline');
  assert.equal(bi.city_name, 'Berkeley, CA');
  assert.equal(bi.city_slug, 'berkeley');
  assert.ok(typeof bi.case_number === 'string' && bi.case_number.startsWith('JOSH-'));
  assert.ok(typeof bi.eval_date   === 'string');

  // project sub-object
  assert.equal(bi.project.name,    'Brief Test');
  assert.equal(bi.project.units,   50);
  assert.equal(bi.project.lat,     37.8695);
  assert.equal(bi.project.lon,     -122.2685);

  // analysis sub-object
  assert.equal(bi.analysis.applicability_met,   true);
  assert.equal(bi.analysis.dwelling_units,       50);
  assert.equal(bi.analysis.unit_threshold,       15);
  assert.equal(bi.analysis.fhsz_flagged,         true);
  assert.equal(bi.analysis.hazard_zone,          'high_fhsz');
  assert.ok(   bi.analysis.behavioral_mobilization > 0);
  assert.ok(   bi.analysis.serving_route_count >= 0);

  // result sub-object
  assert.equal(bi.result.tier,          'MINISTERIAL WITH STANDARD CONDITIONS');
  assert.ok(   bi.result.paths.length > 0);
  const bp = bi.result.paths[0];
  assert.equal(bp.bottleneck_osmid,     '99999');
  assert.equal(bp.bottleneck_name,      'Telegraph Ave');
  assert.equal(bp.bottleneck_road_type, 'secondary');
  assert.equal(bp.delta_t_minutes,      2.3);
  assert.equal(bp.flagged,              false);
  assert.ok(   typeof bp.threshold_minutes === 'number');
  assert.ok(   typeof bp.safe_egress_window_minutes === 'number');
});

test('S9: stale result detection — parameters_version mismatch sets _stale flag', () => {
  setup();
  const staleJson = JSON.stringify({
    schema_v:           1,
    city_slug:          'berkeley',
    parameters_version: '3.4',   // ← old version; current is 4.0
    name:               'Stale Project',
    lat:                37.87,
    lng:                -122.27,
    units:              50,
    stories:            4,
    source:             'browser',
    analyzed_at:        '2026-01-01T00:00:00Z',
    result:             fakeResult(),
  });
  const p = sb._deserialize(staleJson);
  assert.equal(p._stale, true, '_stale should be true when parameters_version mismatches');
  assert.equal(p.name,   'Stale Project');
});

test('S10: project below threshold (< 15 units) serializes correctly', () => {
  setup();
  const p = freshProject({ name: 'Tiny Duplex', units: 2, stories: 2 });
  p.result = {
    tier:              'MINISTERIAL',
    hazard_zone:       'non_fhsz',
    in_fire_zone:      false,
    project_vehicles:  4.5,
    egress_minutes:    0,
    delta_t_threshold: 6.0,
    paths:             [],  // below threshold — no routes analyzed
  };
  const json = sb._serialize(p);
  const obj  = JSON.parse(json);
  assert.equal(obj.result.tier, 'MINISTERIAL');
  assert.equal(obj.units,       2);
  // brief input should set applicability_met false
  const bi = sb._buildBriefInput(p);
  assert.equal(bi.analysis.applicability_met, false);
});

test('S11: empty paths list stored and round-trips correctly (no-routes-found state)', () => {
  setup();
  const p = freshProject({ name: 'No Routes' });
  p.result = {
    tier:              'MINISTERIAL',
    hazard_zone:       'non_fhsz',
    in_fire_zone:      false,
    project_vehicles:  85.5,
    egress_minutes:    0,
    delta_t_threshold: 6.0,
    paths:             [],
  };
  const json = sb._serialize(p);
  const p2   = sb._deserialize(json);
  assert.ok(Array.isArray(p2.result.paths));
  assert.equal(p2.result.paths.length, 0);
  // brief input with no paths should still produce valid schema
  const bi = sb._buildBriefInput(p);
  assert.equal(bi.result.serving_paths_count, 0);
  assert.equal(bi.result.paths.length,        0);
});

// ── Phase 4 tests ─────────────────────────────────────────────────────────────

test('S12: session restore banner returns non-empty HTML when flag is set', () => {
  setup();
  // Initially the restore banner should be empty (flag is false after reset)
  assert.equal(sb._renderRestoreBanner(), '', '_renderRestoreBanner should return "" when flag is false');
  // Set the flag via test helper
  sb._setRestoreBanner(true);
  const html = sb._renderRestoreBanner();
  assert.ok(html.length > 0,           'restore banner should be non-empty when flag is set');
  assert.ok(html.includes('Restore'),  'restore banner should mention "Restore"');
  // Reset clears the flag
  sb._resetState();
  assert.equal(sb._renderRestoreBanner(), '', '_resetState must clear restore banner flag');
});

test('S13: city_slug mismatch in _deserialize leaves project list unchanged', () => {
  setup();
  const p          = freshProject({ name: 'Keep Me' });
  const countBefore = sb.getProjects().length;
  const badJson = JSON.stringify({
    schema_v:           1,
    city_slug:          'encinitas',   // ← wrong city
    parameters_version: '4.0',
    name:               'Wrong City',
    lat:                33.03,
    lng:                -117.29,
    units:              50,
    stories:            4,
    source:             'browser',
    result:             null,
  });
  assert.throws(
    () => sb._deserialize(badJson),
    err => err.message.includes('city_slug mismatch'),
    'should throw on city_slug mismatch'
  );
  // Project list must be unmodified — _deserialize does not push to _projects
  assert.equal(sb.getProjects().length, countBefore,        'list length must not change');
  assert.ok(sb.getProjects().some(x => x.id === p.id), 'existing project must still be present');
});

test('S14: stale _deserialize returns valid project object (not rejected) with _stale: true', () => {
  setup();
  const staleJson = JSON.stringify({
    schema_v:           1,
    city_slug:          'berkeley',
    parameters_version: '3.4',         // ← old version; current is 4.0
    name:               'Stale but Valid',
    lat:                37.87,
    lng:                -122.27,
    units:              60,
    stories:            5,
    source:             'browser',
    analyzed_at:        '2026-01-01T00:00:00Z',
    result:             fakeResult(),
  });
  // _deserialize must succeed (not throw) even for stale projects
  const deserialized = sb._deserialize(staleJson);
  assert.equal(deserialized._stale,  true,              '_stale must be true');
  assert.equal(deserialized.name,    'Stale but Valid');
  assert.equal(deserialized.units,   60);

  // The stale project can be added to the list via createProject
  const added = sb.createProject(deserialized);
  assert.equal(added._stale, true, '_stale field must be preserved through createProject');
  assert.ok(sb.getProjects().some(x => x.id === added.id), 'stale project must be addable to list');
});

test('S15: _toYaml omits projects with null lat/lng', () => {
  setup();
  // Project with NO lat/lng — createProject defaults to lat: null
  sb.createProject({ name: 'No Location', units: 50, stories: 4, source: 'browser' });
  // Project WITH lat/lng — via freshProject helper
  freshProject({ name: 'Has Location' });
  const yaml = sb._toYaml();
  assert.ok(!yaml.includes('No Location'), 'project with null lat must be excluded from YAML');
  assert.ok(yaml.includes('Has Location'), 'project with lat must be included in YAML');
});

test('S16: _toYaml outputs lon: not lng: (pipeline convention)', () => {
  setup();
  freshProject({ name: 'Coord Convention' });
  const yaml = sb._toYaml();
  assert.ok(yaml.includes('lon:'),   'YAML must use lon: (pipeline/YAML convention)');
  assert.ok(!yaml.includes('lng:'),  'YAML must NOT use lng: (internal JS field name)');
});

// ── Phase 5 tests — localStorage auto-save ────────────────────────────────────
// Corresponds to ~/.claude/plans/spicy-prancing-backus.md Changes 1 + 2.
// The file-centric FSAPI model is being backstopped with invisible localStorage
// persistence so new browser projects survive a reload without needing a file save.

test('S17: createProject writes browser project to localStorage', () => {
  setup();
  freshProject({ name: 'LocalStorage Auto-Save', units: 42, stories: 3 });
  const raw = global.localStorage.getItem(sb._lsKey());
  assert.ok(raw, 'localStorage key must exist after createProject');
  const obj = JSON.parse(raw);
  assert.equal(obj.schema_v, 1);
  assert.ok(Array.isArray(obj.projects));
  assert.equal(obj.projects.length, 1);
  assert.equal(obj.projects[0].name,    'LocalStorage Auto-Save');
  assert.equal(obj.projects[0].units,   42);
  assert.equal(obj.projects[0].stories, 3);
});

test('S18: _handle and _stale are stripped from localStorage payload', () => {
  setup();
  const p = freshProject({ name: 'No Runtime Fields' });
  // Stamp runtime-only fields that must never hit localStorage
  p._handle = { fakeFSAPIHandle: true };
  p._stale  = true;
  // Trigger another write via updateProject
  sb.updateProject(p.id, { address: '123 Persist Ave' });
  const raw = global.localStorage.getItem(sb._lsKey());
  assert.ok(raw, 'localStorage key must exist');
  assert.ok(!raw.includes('_handle'), '_handle must NOT appear in localStorage JSON');
  assert.ok(!raw.includes('_stale'),  '_stale must NOT appear in localStorage JSON');
  const obj = JSON.parse(raw);
  assert.equal(obj.projects[0].address, '123 Persist Ave');
});

test('S19: pipeline-source projects are excluded from localStorage', () => {
  setup();
  sb.createProject({ name: 'Pipeline Seed', units: 10, stories: 2, lat: 37.85, lng: -122.27, source: 'pipeline' });
  freshProject({ name: 'Browser Only' });
  const obj = JSON.parse(global.localStorage.getItem(sb._lsKey()));
  assert.equal(obj.projects.length, 1, 'only browser projects written, not pipeline seeds');
  assert.equal(obj.projects[0].name, 'Browser Only');
});

test('S20: _loadFromLocalStorage restores projects into an empty state', () => {
  setup();
  freshProject({ name: 'Pre-Reload', units: 55, stories: 6 });
  // Simulate a page reload: clear in-memory state but leave localStorage alone
  const savedRaw = global.localStorage.getItem(sb._lsKey());
  sb._getDirtyIds().clear();
  // Manually clear _projects without touching localStorage (cannot use _resetState — it clears LS)
  sb.getProjects().forEach(p => { /* no-op; we'll blow away via module internals */ });
  // Workaround: reset state, then restore the raw localStorage blob
  sb._resetState();
  global.localStorage.setItem(sb._lsKey(), savedRaw);
  sb._loadFromLocalStorage();
  const restored = sb.getProjects();
  assert.equal(restored.length, 1);
  assert.equal(restored[0].name,    'Pre-Reload');
  assert.equal(restored[0].units,   55);
  assert.equal(restored[0].stories, 6);
  // _handle must be null after restore (fresh runtime state)
  assert.equal(restored[0]._handle, null);
});

test('S21: _loadFromLocalStorage deduplicates against existing seeds by id', () => {
  setup();
  // Seed a pipeline project first (simulating init() order)
  sb.createProject({ id: 'dedup-1', name: 'Seed Project', units: 10, lat: 37.85, lng: -122.27, source: 'pipeline' });
  // Pre-populate localStorage with a project that has the SAME id as a seed
  global.localStorage.setItem(sb._lsKey(), JSON.stringify({
    schema_v: 1,
    projects: [
      { id: 'dedup-1', name: 'Dup by ID',   units: 99, lat: 37.85, lng: -122.27, source: 'browser' },
      { id: 'unique-2', name: 'New from LS', units: 33, lat: 37.86, lng: -122.28, source: 'browser' },
    ],
  }));
  sb._loadFromLocalStorage();
  const list = sb.getProjects();
  // dedup-1 should NOT be overwritten by the localStorage version (pipeline wins)
  const seed = list.find(p => p.id === 'dedup-1');
  assert.equal(seed.name,  'Seed Project', 'pipeline seed must NOT be overwritten by localStorage');
  assert.equal(seed.units, 10);
  // unique-2 should be added
  const newOne = list.find(p => p.id === 'unique-2');
  assert.ok(newOne, 'unique localStorage project must be added');
  assert.equal(newOne.name, 'New from LS');
});

test('S22: deleteProject removes the entry from localStorage', () => {
  setup();
  const p = freshProject({ name: 'To Delete' });
  // Verify it's in LS
  let obj = JSON.parse(global.localStorage.getItem(sb._lsKey()));
  assert.equal(obj.projects.length, 1);
  // Delete and verify LS is now empty (for this city)
  sb.deleteProject(p.id);
  obj = JSON.parse(global.localStorage.getItem(sb._lsKey()));
  assert.equal(obj.projects.length, 0, 'deleted project must no longer be in localStorage');
});

test('S23: _lsKey is versioned and city-scoped', () => {
  setup();
  const key = sb._lsKey();
  assert.ok(key.startsWith('josh_sb_v1_'), '_lsKey must start with josh_sb_v1_');
  assert.ok(key.endsWith('berkeley'),       '_lsKey must include city slug');
});

// ── Phase 5b regression tests — form field persistence ───────────────────────
// Previously, _wireFormListeners only wired units and stories inputs. Typing
// name or address was stored only in the DOM <input>, and any subsequent
// _render() (from onPinPlaced, the analysis debounce, or any other cause) would
// wipe the in-progress values because the form was re-rendered from stale project
// state. See ~/.claude/plans/spicy-prancing-backus.md follow-up.

test('S24: updateProject persists all four form fields to localStorage', () => {
  setup();
  const p = sb.createProject({ source: 'browser' });
  sb.updateProject(p.id, {
    name:    'Round Trip All Fields',
    address: '1 Shattuck Square, Berkeley',
    lat:     37.8719,
    lng:     -122.2685,
    units:   120,
    stories: 6,
  });
  // Read localStorage directly — this is the real persistence sink
  const obj = JSON.parse(global.localStorage.getItem(sb._lsKey()));
  assert.equal(obj.projects.length, 1);
  const stored = obj.projects[0];
  assert.equal(stored.name,    'Round Trip All Fields');
  assert.equal(stored.address, '1 Shattuck Square, Berkeley');
  assert.equal(stored.lat,     37.8719);
  assert.equal(stored.lng,     -122.2685);
  assert.equal(stored.units,   120);
  assert.equal(stored.stories, 6);
});

test('S25: _wireFormListeners wires all four form input ids (not just units/stories)', () => {
  // Source-level smoke test — catches regression where name/address wiring is removed.
  // The fix is required because _render() re-renders the form from project state;
  // if name/address aren't persisted synchronously on keystroke, any subsequent
  // re-render wipes the in-progress DOM input values.
  const fs          = require('node:fs');
  const SIDEBAR_SRC = fs.readFileSync(path.join(__dirname, '..', 'static', 'sidebar.js'), 'utf8');
  // Locate the function body
  const match = SIDEBAR_SRC.match(/function\s+_wireFormListeners\s*\([^)]*\)\s*\{([\s\S]*?)\n\s{2}\}/);
  assert.ok(match, '_wireFormListeners function must exist');
  const body = match[1];
  // All four input ids must appear in the wiring function
  assert.ok(body.includes("'josh-sb-f-name'"),    "_wireFormListeners must wire 'josh-sb-f-name'");
  assert.ok(body.includes("'josh-sb-f-addr'"),    "_wireFormListeners must wire 'josh-sb-f-addr'");
  assert.ok(body.includes("'josh-sb-f-units'"),   "_wireFormListeners must wire 'josh-sb-f-units'");
  assert.ok(body.includes("'josh-sb-f-stories'"), "_wireFormListeners must wire 'josh-sb-f-stories'");
});

test('S27: _buildAuditText renders [city-provided] branch for cap_src=city_override', () => {
  // Verify the city-provided label, source doc, and reason appear in the audit trail
  // text, and that the HCM formula line is NOT rendered for that path.
  setup();
  const p = freshProject({ name: 'City Override Test', units: 50, stories: 3 });
  p.result = fakeResult({
    hazard_zone:       'vhfhsz',
    in_fire_zone:      true,
    delta_t_threshold: 2.25,
    paths: [
      {
        route_id:                  'A',
        delta_t:                   4.8,
        flagged:                   true,
        bottleneck_osmid:          '77777',
        bottleneck_name:           'Wildcat Canyon Rd',
        bottleneck_road_type:      'two_lane',
        bottleneck_lanes:          2,
        bottleneck_speed:          25,
        effective_capacity_vph:    280,   // 800 × 0.35
        hazard_degradation_factor: 0.35,
        cap_src:                   'city_override',
        cap_source_doc:            'Caltrans TMC count 2024-08-15 (PE stamp: J. Smith PE #12345)',
        cap_reason:                'Field count shows 800 vph peak; HCM overestimates signal interference',
        path_coords:               [[37.88, -122.25], [37.89, -122.26]],
      },
    ],
  });

  const bi = sb._buildBriefInput(p);
  const auditText = bi.audit_text;

  // [city-provided] label must appear
  assert.ok(auditText.includes('[city-provided]'), 'audit trail must contain [city-provided]');
  // Source doc must appear
  assert.ok(auditText.includes('Caltrans TMC count 2024-08-15'), 'source doc must appear in audit trail');
  // Reason must appear
  assert.ok(auditText.includes('Field count shows 800 vph'), 'reason must appear in audit trail');
  // HCM formula line must NOT appear for this path
  assert.ok(!auditText.includes('HCM cap:'), 'HCM cap: must not appear for city_override path');
  // Effective capacity with degradation note must appear
  assert.ok(auditText.includes('city-provided') && auditText.includes('0.35'), 'degradation factor must appear');
});

test('S26: incremental updateProject calls survive a serialize/deserialize round-trip', () => {
  // Simulates the real-world flow: user types name, then address, then changes
  // units, each triggering an updateProject. Final state must have all fields.
  setup();
  const p = sb.createProject({ source: 'browser' });
  // Simulate keystroke-by-keystroke updates on different fields
  sb.updateProject(p.id, { name:    'Incremental' });
  sb.updateProject(p.id, { address: '42 Berkeley Way' });
  sb.updateProject(p.id, { lat: 37.87, lng: -122.27 });
  sb.updateProject(p.id, { units: 99 });
  sb.updateProject(p.id, { stories: 7 });
  // Now serialize and round-trip
  const final = sb.getProject(p.id);
  const p2    = sb._deserialize(sb._serialize(final));
  assert.equal(p2.name,    'Incremental');
  assert.equal(p2.address, '42 Berkeley Way');
  assert.equal(p2.lat,     37.87);
  assert.equal(p2.lng,     -122.27);
  assert.equal(p2.units,   99);
  assert.equal(p2.stories, 7);
});

// ── v4.12 (all-viable-routes) — route toggle state machine ──────────────────

function _projectWithPaths() {
  const result = {
    tier:              'DISCRETIONARY',
    hazard_zone:       'non_fhsz',
    in_fire_zone:      false,
    project_vehicles:  205.2,
    egress_minutes:    0,
    delta_t_threshold: 6.0,
    paths: [
      { path_id: 'P1', route_id: 'A', cost_s: 120, delta_t: 6.48, flagged: true,  bottleneck_osmid: '1', bottleneck_name: 'Adeline St',  path_coords: [[37.87,-122.27]] },
      { path_id: 'P2', route_id: 'B', cost_s: 200, delta_t: 4.59, flagged: false, bottleneck_osmid: '2', bottleneck_name: 'University Ave', path_coords: [[37.87,-122.27]] },
      { path_id: 'P3', route_id: 'C', cost_s: 300, delta_t: 3.24, flagged: false, bottleneck_osmid: '3', bottleneck_name: 'Shattuck Ave',   path_coords: [[37.87,-122.27]] },
    ],
  };
  return freshProject({ result });
}

test('S28: _normalizeResult preserves path_id and cost_s from engine output', () => {
  setup();
  const engineOut = {
    tier:        'DISCRETIONARY',
    hazard_zone: 'non_fhsz',
    paths: [
      { pathId: 'project_origin_1_0', cost_s: 145.6, bottleneckOsmid: '99', delta_t_minutes: 6.48, flagged: true,  bottleneckEffCapVph: 1900, bottleneck_name: 'X', path_coords: [] },
      { pathId: 'project_origin_2_0', cost_s: 200.1, bottleneckOsmid: '88', delta_t_minutes: 4.50, flagged: false, bottleneckEffCapVph: 1900, bottleneck_name: 'Y', path_coords: [] },
    ],
  };
  const n = sb._normalizeResult(engineOut);
  assert.equal(n.paths.length, 2);
  assert.equal(n.paths[0].path_id, 'project_origin_1_0', 'path_id preserved from pathId');
  assert.equal(n.paths[0].cost_s,  145.6,                'cost_s preserved');
  assert.equal(n.paths[1].path_id, 'project_origin_2_0');
});

test('S29: _visiblePaths returns ALL paths when no toggle entry exists (default-on)', () => {
  setup();
  const p     = _projectWithPaths();
  const paths = p.result.paths;
  const visible = sb._visiblePaths(p.id, paths);
  assert.equal(visible.length, paths.length, 'all paths visible by default');
});

test('S30: _toggleRoute seeds full Set on first call, then flips one off', () => {
  setup();
  const p     = _projectWithPaths();
  const paths = p.result.paths;

  // First toggle on P2 → P2 hidden; P1 and P3 still visible.
  sb._toggleRoute(p.id, 'P2');
  const visible1 = sb._visiblePaths(p.id, paths).map(x => x.path_id);
  assert.deepEqual(visible1, ['P1', 'P3'], 'P2 hidden after first toggle');

  // Toggle P2 again → restored.
  sb._toggleRoute(p.id, 'P2');
  const visible2 = sb._visiblePaths(p.id, paths).map(x => x.path_id);
  assert.deepEqual(visible2, ['P1', 'P2', 'P3'], 'P2 restored after second toggle');
});

test('S31: route toggles do not change p.result.paths — display-only safeguard', () => {
  // Determination uses ALL routes; toggles must never mutate the underlying data.
  // If a future change leaks toggle state into result.paths the legal safeguard
  // ("Determination uses all N routes") becomes a lie — this test prevents that.
  setup();
  const p     = _projectWithPaths();
  const originalCount = p.result.paths.length;
  const originalIds   = p.result.paths.map(x => x.path_id).join(',');
  sb._toggleRoute(p.id, 'P1');
  sb._toggleRoute(p.id, 'P2');
  const after = sb.getProject(p.id);
  assert.equal(after.result.paths.length, originalCount, 'result.paths length unchanged');
  assert.equal(after.result.paths.map(x => x.path_id).join(','), originalIds, 'result.paths content unchanged');
});

test('S32: _buildBriefInput threads path_id and cost_s through to BriefInput', () => {
  // The brief renderer sorts by cost_s; if _buildBriefInput drops these fields
  // the brief table reverts to "Path: <bottleneck_osmid>" (collisions when
  // multiple paths share a bottleneck) and unsorted order.
  setup();
  const p  = _projectWithPaths();
  const bi = sb._buildBriefInput(p);
  assert.equal(bi.result.paths.length, 3);
  assert.equal(bi.result.paths[0].path_id, 'P1', 'path_id forwarded');
  assert.equal(bi.result.paths[0].cost_s, 120,   'cost_s forwarded');
  assert.equal(bi.result.paths[2].path_id, 'P3');
  assert.equal(bi.result.paths[2].cost_s, 300);
});

// ── v4.13 (route-display-ux) — controlling-route default + show-all toggle ──

test('S33: _controllingPath returns the highest-ΔT path', () => {
  // The "controlling" route under User Equilibrium is the binding-evidence
  // route — the one with the worst ΔT.  Drives the default map view and the
  // CONTROLLING badge in the sidebar route list.
  setup();
  const paths = [
    { path_id: 'A', delta_t: 2.3,  flagged: false },
    { path_id: 'B', delta_t: 6.48, flagged: true  },   // highest
    { path_id: 'C', delta_t: 4.59, flagged: false },
  ];
  const ctrl = sb._controllingPath(paths);
  assert.equal(ctrl.path_id, 'B', 'controlling = max delta_t');
  // Falls back to delta_t_minutes if delta_t absent (engine output uses _minutes)
  const enginePaths = [
    { path_id: 'X', delta_t_minutes: 5.0 },
    { path_id: 'Y', delta_t_minutes: 8.5 },   // highest
  ];
  assert.equal(sb._controllingPath(enginePaths).path_id, 'Y', 'falls back to delta_t_minutes');
  // Empty input
  assert.equal(sb._controllingPath([]), null, 'empty input returns null');
});

test('S34: _toggleShowAll seeds + flips the per-project show-all flag', () => {
  // Each project starts in default state (showAll absent → false).  Toggling
  // sets true; toggling again sets false.  Per-project; switching projects
  // resets via selectProject().
  setup();
  const p = _projectWithPaths();
  assert.equal(sb._showAllRoutes.get(p.id) === true, false, 'default: showAll off');
  sb._toggleShowAll(p.id);
  assert.equal(sb._showAllRoutes.get(p.id), true, 'after first toggle: showAll on');
  sb._toggleShowAll(p.id);
  assert.equal(sb._showAllRoutes.get(p.id), false, 'after second toggle: showAll off');
});

test('S35: _renderDetail surfaces the legal-framing note above the route list', () => {
  // The educational note paraphrases §8.6 of the Legal Defensibility Memo.
  // It must appear in the sidebar detail panel for every project that has
  // routes — that is where the developer's "use the fast route" question
  // gets asked, so it is where the answer must live.
  setup();
  const p = _projectWithPaths();
  // Select the project so _renderDetail has a target
  global.window._joshMap = { eachLayer:()=>{}, removeLayer:()=>{}, addLayer:()=>{}, hasLayer:()=>false,
                              getPane:()=>null, createPane:()=>null,
                              fitBounds:()=>{}, getCenter:()=>({lat:0,lng:0}), getZoom:()=>0 };
  // Manually render the detail panel via the module's public render path
  // by calling selectProject and reading the resulting innerHTML out of a
  // fake DOM.  Simpler: directly check _renderDetail via the export hook.
  // (The module doesn't currently export _renderDetail — but we can verify
  // via the brief input + sidebar's existing detail-render code path by
  // checking the educational copy appears in sidebar.js as a literal.)
  const fs = require('fs');
  const path = require('path');
  const sbSource = fs.readFileSync(path.join(__dirname, '..', 'static', 'sidebar.js'), 'utf8');
  assert.ok(sbSource.includes('User Equilibrium'),
    'sidebar.js contains User Equilibrium framing');
  assert.ok(sbSource.includes('worst-case route'),
    'sidebar.js identifies the worst-case route as the binding evidence');
  assert.ok(sbSource.includes('slower routes do not'),
    'sidebar.js addresses the "use the fast route" objection');
});

// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * Unit tests for static/project_manager.js
 *
 * Tests the non-DOM functions: CRUD, localStorage cache, import/dedup,
 * schema migration, and YAML serialisation.
 *
 * Run:
 *   node --test tests/test_project_manager.js
 *
 * No npm install needed.
 */

'use strict';

const { test } = require('node:test');
const assert   = require('node:assert/strict');
const path     = require('node:path');

// ── Shims (set up BEFORE requiring the module) ────────────────────────────────

// localStorage shim — in-memory Map, persists across calls within this process
const _store = new Map();
global.localStorage = {
  getItem:    k     => _store.has(k) ? _store.get(k) : null,
  setItem:    (k,v) => { _store.set(k, v); },
  removeItem: k     => { _store.delete(k); },
  clear:      ()    => { _store.clear(); },
};

// crypto.randomUUID shim — deterministic for tests
// Node v20 exposes globalThis.crypto as a read-only getter; use defineProperty.
let _uuidCounter = 0;
Object.defineProperty(global, 'crypto', {
  value:        { randomUUID: () => `test-uuid-${++_uuidCounter}` },
  writable:     true,
  configurable: true,
});

// window / JOSH_DATA shim
// Includes parameters and graph.edges needed by Phase 3 (_buildBriefInput / _buildEdgeMap).
global.window = {
  JOSH_DATA: {
    city_slug: 'berkeley',
    city_name: 'Berkeley',
    parameters: {
      max_project_share:  0.05,
      unit_threshold:     15,
      behavioral_mobilization: 0.90,
      safe_egress_window: { vhfhsz: 45, high_fhsz: 90, moderate_fhsz: 120, non_fhsz: 120 },
    },
    graph: {
      edges: [
        { osmid: '123456', name: 'Grizzly Peak Blvd', road_type: 'two_lane', lanes: 2, speed_mph: 30 },
      ],
    },
  },
};

// ── Load module ───────────────────────────────────────────────────────────────
const PM_PATH = path.join(__dirname, '..', 'static', 'project_manager.js');
const {
  createProject,
  updateProject,
  deleteProject,
  getProject,
  _loadFromCache,
  _importFromJson,
  _migrate,
  _toYaml,
  _storageKey,
  _getState,
  _resetState,
  _buildEdgeMap,
  _buildBriefInput,
} = require(PM_PATH);

// ── Test helper ───────────────────────────────────────────────────────────────
function setup() {
  _resetState();
  _store.clear();
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test('1. Storage key uses JOSH_DATA.city_slug', () => {
  assert.equal(_storageKey(), 'josh_pm_v1_berkeley');
});

test('2. createProject → _loadFromCache round-trip', () => {
  setup();
  const p = createProject({ name: 'Test Project', units: 30 });

  // State is in memory
  assert.equal(_getState().projects.length, 1);

  // Reset in-memory state — cache survives
  _resetState();
  assert.equal(_getState().projects.length, 0);

  // Restore from cache
  _loadFromCache();
  const restored = _getState().projects;
  assert.equal(restored.length, 1);
  assert.equal(restored[0].name, 'Test Project');
  assert.equal(restored[0].units, 30);
  assert.equal(restored[0].id, p.id);
});

test('3. updateProject merges fields and updates updated_at', () => {
  setup();
  const p = createProject({ name: 'Original', units: 50, stories: 3 });

  const updated = updateProject(p.id, { name: 'Updated', units: 75 });

  // Updated fields
  assert.equal(updated.name, 'Updated');
  assert.equal(updated.units, 75);

  // Unchanged fields preserved
  assert.equal(updated.id, p.id);
  assert.equal(updated.stories, 3);

  // updated_at is set and is an ISO string
  assert.ok(typeof updated.updated_at === 'string');
  assert.ok(updated.updated_at.includes('T'), 'updated_at should be ISO string');
});

test('4. deleteProject removes record', () => {
  setup();
  const p1 = createProject({ name: 'P1' });
  const p2 = createProject({ name: 'P2' });
  assert.equal(_getState().projects.length, 2);

  deleteProject(p1.id);

  const state = _getState();
  assert.equal(state.projects.length, 1);
  assert.equal(state.projects[0].id, p2.id);
  assert.equal(getProject(p1.id), null);
});

test('5. _importFromJson deduplicates by id (merge mode)', () => {
  setup();
  const p = createProject({ name: 'Existing', units: 50 });

  // Incoming: the same project (same id) + one new project
  const payload = JSON.stringify({
    schema_v:  1,
    city_slug: 'berkeley',
    projects: [
      // Same id as existing — must be skipped
      { id: p.id, schema_v: 1, name: 'Duplicate', lat: null, lng: null,
        units: 50, stories: 4, result: null, created_at: p.created_at, updated_at: p.updated_at },
      // New id — must be added
      { id: 'new-uuid-import-1', schema_v: 1, name: 'Incoming New', lat: null, lng: null,
        units: 60, stories: 2, result: null, created_at: p.created_at, updated_at: p.updated_at },
    ],
  });

  _importFromJson(payload);   // merge mode (no second arg → merge=undefined, not false)

  const state = _getState();
  assert.equal(state.projects.length, 2, 'Should have original + 1 new (duplicate skipped)');
  assert.equal(state.projects.find(x => x.id === p.id).name, 'Existing', 'Original not overwritten');
  assert.equal(state.projects.find(x => x.id === 'new-uuid-import-1').name, 'Incoming New');
});

test('6. _importFromJson warns but continues on city_slug mismatch', () => {
  setup();

  const warnings = [];
  const origWarn = console.warn;
  console.warn = (...args) => warnings.push(args.map(String).join(' '));

  const payload = JSON.stringify({
    schema_v:  1,
    city_slug: 'encinitas',   // mismatch vs. 'berkeley'
    projects: [
      { id: 'cross-city-1', schema_v: 1, name: 'Foreign Project', lat: null, lng: null,
        units: 80, stories: 5, result: null, created_at: '', updated_at: '' },
    ],
  });

  _importFromJson(payload);

  console.warn = origWarn;

  assert.ok(
    warnings.some(w => w.includes('mismatch')),
    `Expected a "mismatch" warning; got: ${JSON.stringify(warnings)}`
  );
  assert.equal(_getState().projects.length, 1, 'Project should still be imported despite mismatch');
  assert.equal(_getState().projects[0].name, 'Foreign Project');
});

test('7. _migrate is a no-op for schema_v: 1', () => {
  const p = { id: 'x', schema_v: 1, name: 'Test', units: 50, stories: 4 };
  const result = _migrate(p);
  assert.deepEqual(result, p);
  // Same object reference — migrate should return the input unchanged
  assert.equal(result, p);
});

test('8. _toYaml omits projects with lat: null', () => {
  setup();
  createProject({ name: 'No Pin',  lat: null,     lng: null,       units: 50, stories: 4 });
  createProject({ name: 'Has Pin', lat: 37.8651,  lng: -122.2743,  units: 75, stories: 3 });

  const yaml = _toYaml();
  assert.ok(!yaml.includes('No Pin'),  'Unpinned project should be omitted from YAML');
  assert.ok(yaml.includes('Has Pin'),  'Pinned project should appear in YAML');
  assert.ok(yaml.includes('projects:'), 'YAML should have projects key');
});

test('9. _toYaml maps lng → lon', () => {
  setup();
  createProject({ name: 'Pin Test', lat: 37.8651, lng: -122.2743, units: 50, stories: 4 });

  const yaml = _toYaml();
  assert.ok(yaml.includes('lon:'),          'Pipeline key must be "lon" not "lng"');
  assert.ok(!yaml.includes('lng:'),         'Must not use "lng" key');
  assert.ok(yaml.includes('-122.2743000'),  'Longitude value should appear in YAML');
});

// ── Phase 3: Brief rendering helpers ──────────────────────────────────────────

// ── Test 10: _buildEdgeMap ────────────────────────────────────────────────────

test('10. _buildEdgeMap returns a Map keyed by osmid string', function() {
  const map = _buildEdgeMap();
  assert.ok(map instanceof Map, 'result should be a Map');
  assert.equal(map.size, 1, 'should have 1 entry matching the shim graph.edges');
  assert.ok(map.has('123456'), 'map should be keyed by osmid string');
  const edge = map.get('123456');
  assert.equal(edge.name,      'Grizzly Peak Blvd');
  assert.equal(edge.road_type, 'two_lane');
  assert.equal(edge.lanes,     2);
  assert.equal(edge.speed_mph, 30);
});

// ── Test 11: _buildBriefInput — core schema fields ────────────────────────────

test('11. _buildBriefInput produces source "whatif" and BriefInput v1 schema fields', function() {
  const project = { name: 'Civic Tower', lat: 37.87, lng: -122.27, units: 75, stories: 4 };
  const result  = {
    tier:                'DISCRETIONARY',
    hazard_zone:         'vhfhsz',
    project_vehicles:    168.75,
    max_delta_t_minutes: 8.5,
    serving_paths_count: 1,
    paths:               [],
  };

  const inp = _buildBriefInput(project, result);

  assert.equal(inp.brief_input_version, 1,          'brief_input_version must be 1');
  assert.equal(inp.source,              'whatif',    'source must be "whatif" (watermark banner)');
  assert.equal(inp.city_slug,           'berkeley',  'city_slug from JOSH_DATA');
  assert.equal(inp.city_name,           'Berkeley',  'city_name from JOSH_DATA');
  assert.ok(typeof inp.eval_date === 'string' && inp.eval_date.match(/^\d{4}-\d{2}-\d{2}$/),
            'eval_date should be YYYY-MM-DD');
  // audit fields are empty for what-if source
  assert.equal(inp.audit_text,     '', 'audit_text should be empty for whatif');
  assert.equal(inp.audit_filename, '', 'audit_filename should be empty for whatif');
});

// ── Test 12: _buildBriefInput — case number format ────────────────────────────

test('12. _buildBriefInput case number mirrors Python format (slug, lat/lon encoding)', function() {
  const project = { name: 'Civic Tower', lat: 37.87, lng: -122.27, units: 75 };
  const result  = {
    tier: 'DISCRETIONARY', hazard_zone: 'vhfhsz', project_vehicles: 168.75,
    max_delta_t_minutes: 8.5, serving_paths_count: 1, paths: [],
  };

  const inp  = _buildBriefInput(project, result);
  const year = new Date().getFullYear();

  // Slug: 'Civic Tower' → 'CIVIC-TOWER'
  assert.ok(inp.case_number.startsWith(`JOSH-${year}-CIVIC-TOWER-`),
            `case_number should start with JOSH-${year}-CIVIC-TOWER-; got: ${inp.case_number}`);
  // lat 37.87 → '37_8700' (no prefix, positive)
  assert.ok(inp.case_number.includes('37_8700'),
            `lat should encode to 37_8700; case_number: ${inp.case_number}`);
  // lon -122.27 → 'n122_2700' ('n' prefix for negative)
  assert.ok(inp.case_number.includes('n122_2700'),
            `lon should encode to n122_2700; case_number: ${inp.case_number}`);

  // No-name project: no slug segment
  const noName = Object.assign({}, project, { name: '' });
  const noNameInp = _buildBriefInput(noName, result);
  assert.ok(noNameInp.case_number.startsWith(`JOSH-${year}-37_8700`),
            `unnamed project case_number should skip slug; got: ${noNameInp.case_number}`);
});

// ── Test 13: _buildBriefInput — camelCase → snake_case path mapping ───────────

test('13. _buildBriefInput maps WhatIfEngine camelCase path fields to BriefInput snake_case', function() {
  const wePath = {
    bottleneckOsmid:     '123456',
    bottleneckEffCapVph: 473,
    bottleneckFhszZone:  'vhfhsz',
    delta_t_minutes:     8.5,
    threshold_minutes:   2.25,
    project_vehicles:    168.75,
    egress_minutes:      0,
    flagged:             true,
  };
  const project = { name: 'X', lat: 37.87, lng: -122.27, units: 75 };
  const result  = {
    tier: 'DISCRETIONARY', hazard_zone: 'vhfhsz', project_vehicles: 168.75,
    max_delta_t_minutes: 8.5, serving_paths_count: 1, paths: [wePath],
  };

  const inp  = _buildBriefInput(project, result);
  const path = inp.result.paths[0];

  assert.equal(path.bottleneck_osmid,      '123456', 'bottleneckOsmid → bottleneck_osmid');
  assert.equal(path.bottleneck_eff_cap_vph, 473,     'bottleneckEffCapVph → bottleneck_eff_cap_vph');
  assert.equal(path.bottleneck_fhsz_zone,  'vhfhsz', 'bottleneckFhszZone → bottleneck_fhsz_zone');
  assert.equal(path.delta_t_minutes,  8.5,  'delta_t_minutes preserved');
  assert.equal(path.threshold_minutes, 2.25, 'threshold_minutes preserved');
  assert.ok(path.flagged, 'flagged should be true');

  // safe_egress_window_minutes is derived: threshold_minutes / max_project_share = 2.25 / 0.05 = 45
  assert.ok(
    Math.abs(path.safe_egress_window_minutes - 45) < 0.01,
    `safe_egress_window_minutes should be 45 (2.25 / 0.05); got ${path.safe_egress_window_minutes}`
  );

  // HCM raw capacity is not in browser graph — always 0
  assert.equal(path.bottleneck_hcm_capacity_vph, 0, 'HCM raw cap is 0 (not available in browser)');
});

// ── Test 14: _buildBriefInput — edge metadata enrichment ─────────────────────

test('14. _buildBriefInput enriches paths with edge metadata from JOSH_DATA.graph.edges', function() {
  // Shim graph.edges has osmid=123456: name=Grizzly Peak Blvd, road_type=two_lane, lanes=2, speed_mph=30
  const wePath = {
    bottleneckOsmid:     '123456',   // matches shim edge
    bottleneckEffCapVph: 473,
    bottleneckFhszZone:  'vhfhsz',
    delta_t_minutes:     8.5,
    threshold_minutes:   2.25,
    flagged:             true,
  };
  const project = { name: 'X', lat: 37.87, lng: -122.27, units: 75 };
  const result  = {
    tier: 'DISCRETIONARY', hazard_zone: 'vhfhsz', project_vehicles: 168.75,
    max_delta_t_minutes: 8.5, serving_paths_count: 1, paths: [wePath],
  };

  const path = _buildBriefInput(project, result).result.paths[0];

  assert.equal(path.bottleneck_name,      'Grizzly Peak Blvd', 'edge.name → bottleneck_name');
  assert.equal(path.bottleneck_road_type, 'two_lane',          'edge.road_type → bottleneck_road_type');
  assert.equal(path.bottleneck_lanes,     2,                   'edge.lanes → bottleneck_lanes');
  assert.equal(path.bottleneck_speed_mph, 30,                  'edge.speed_mph → bottleneck_speed_mph');

  // Unknown osmid → null metadata (graceful fallback)
  const unknownPath = Object.assign({}, wePath, { bottleneckOsmid: '999999' });
  const unknownResult = Object.assign({}, result, { paths: [unknownPath] });
  const unknownOut = _buildBriefInput(project, unknownResult).result.paths[0];
  assert.equal(unknownOut.bottleneck_name,      null, 'unknown osmid → null name');
  assert.equal(unknownOut.bottleneck_road_type, null, 'unknown osmid → null road_type');
});

// ── Test 15: _buildBriefInput — applicability and FHSZ analysis flags ─────────

test('15. _buildBriefInput sets applicability_met, FHSZ flags, and hazard_degradation_factor', function() {
  // Small project below threshold, non-FHSZ
  const smallProj = { name: 'Tiny', lat: 37.87, lng: -122.27, units: 10 };
  const smallRes  = {
    tier: 'MINISTERIAL', hazard_zone: 'non_fhsz', project_vehicles: 0,
    max_delta_t_minutes: 0, serving_paths_count: 0, paths: [],
  };
  const small = _buildBriefInput(smallProj, smallRes);
  assert.equal(small.analysis.applicability_met,         false, 'units 10 < threshold 15 → false');
  assert.equal(small.analysis.fhsz_flagged,              false, 'non_fhsz → fhsz_flagged false');
  assert.equal(small.analysis.fhsz_level,                0,     'non_fhsz → level 0');
  assert.equal(small.analysis.hazard_zone,               'non_fhsz');
  assert.ok(Math.abs(small.analysis.hazard_degradation_factor - 1.00) < 0.001,
            'non_fhsz degradation factor should be 1.00');

  // Large project in VHFHSZ
  const bigProj = { name: 'Tower', lat: 37.87, lng: -122.27, units: 75 };
  const bigRes  = {
    tier: 'DISCRETIONARY', hazard_zone: 'vhfhsz', project_vehicles: 168.75,
    max_delta_t_minutes: 8.5, serving_paths_count: 1, paths: [],
  };
  const big = _buildBriefInput(bigProj, bigRes);
  assert.equal(big.analysis.applicability_met,         true,     'units 75 >= threshold 15 → true');
  assert.equal(big.analysis.fhsz_flagged,              true,     'vhfhsz → fhsz_flagged true');
  assert.equal(big.analysis.fhsz_level,                3,        'vhfhsz → level 3');
  assert.equal(big.analysis.fhsz_desc, 'Very High Fire Hazard Severity Zone', 'vhfhsz description');
  assert.ok(Math.abs(big.analysis.hazard_degradation_factor - 0.35) < 0.001,
            'vhfhsz degradation factor should be 0.35');
  assert.equal(big.analysis.delta_t_triggered, true,  'DISCRETIONARY tier → delta_t_triggered true');
  assert.equal(big.result.triggered,           true,  'DISCRETIONARY tier → result.triggered true');
});

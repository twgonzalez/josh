// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * Unit tests for static/brief_renderer.js
 *
 * Run:
 *   node --test tests/test_brief_renderer.js
 *
 * No prerequisites — all fixtures are inline JSON.
 * Tests validate that BriefRenderer.render(briefInput) produces correct HTML
 * for all three determination tiers and all key UI elements.
 */

'use strict';

const { test } = require('node:test');
const assert   = require('node:assert/strict');
const path     = require('node:path');

const BR = require(path.join(__dirname, '..', 'static', 'brief_renderer.js'));

// ── Shared fixture helpers ─────────────────────────────────────────────────────

function makeProject(overrides) {
  return Object.assign({
    name:    '',
    address: '100 Test Street',
    lat:     37.87,
    lon:     -122.27,
    units:   75,
    stories: 2,
    apn:     '',
  }, overrides);
}

function makeParameters(overrides) {
  return Object.assign({
    unit_threshold:     15,
    vehicles_per_unit:       1.9,
    behavioral_mobilization: 0.90,
    hazard_degradation: { vhfhsz: 0.35, high_fhsz: 0.50, moderate_fhsz: 0.75, non_fhsz: 1.00 },
    safe_egress_window: { vhfhsz: 45, high_fhsz: 90, moderate_fhsz: 120, non_fhsz: 120 },
    max_project_share:  0.05,
    egress_penalty:     { threshold_stories: 4, minutes_per_story: 1.5, max_minutes: 12 },
  }, overrides);
}

function makePath(overrides) {
  return Object.assign({
    path_id:                       'P1',
    bottleneck_osmid:              '123456',
    bottleneck_name:               'Grizzly Peak Blvd',
    bottleneck_fhsz_zone:          'vhfhsz',
    bottleneck_hcm_capacity_vph:   1350,
    bottleneck_eff_cap_vph:        473,
    bottleneck_hazard_degradation: 0.35,
    bottleneck_road_type:          'two_lane',
    bottleneck_speed_mph:          30,
    bottleneck_lanes:              2,
    delta_t_minutes:               8.50,
    threshold_minutes:             2.25,
    safe_egress_window_minutes:    45.0,
    max_project_share:             0.05,
    flagged:                       true,
    project_vehicles:              168.75,
    egress_minutes:                0.0,
  }, overrides);
}

function makeResult(tier, paths, overrides) {
  var flagged = paths.filter(function(p) { return p.flagged; });
  return Object.assign({
    tier:                       tier,
    hazard_zone:                'vhfhsz',
    project_vehicles:           168.75,
    max_delta_t_minutes:        paths.length ? Math.max.apply(null, paths.map(function(p){ return p.delta_t_minutes; })) : 0,
    threshold_minutes:          2.25,
    safe_egress_window_minutes: 45.0,
    max_project_share:          0.05,
    serving_paths_count:        paths.length,
    egress_minutes:             0.0,
    parameters_version:         '4.0',
    analyzed_at:                '2026-04-09',
    determination_reason:       tier === 'DISCRETIONARY'
      ? 'One or more serving evacuation paths exceed the ΔT threshold.'
      : 'All serving evacuation paths are within the ΔT threshold.',
    triggered:                  flagged.length > 0,
    paths:                      paths,
  }, overrides);
}

function makeAnalysis(applicabilityMet, fhszFlagged, overrides) {
  return Object.assign({
    applicability_met:         applicabilityMet,
    dwelling_units:            applicabilityMet ? 75 : 10,
    unit_threshold:            15,
    fhsz_flagged:              fhszFlagged,
    fhsz_desc:                 fhszFlagged ? 'Very High Fire Hazard Severity Zone' : 'Not in FHSZ',
    fhsz_level:                fhszFlagged ? 3 : 0,
    hazard_zone:               fhszFlagged ? 'vhfhsz' : 'non_fhsz',
    behavioral_mobilization:   0.90,
    hazard_degradation_factor: fhszFlagged ? 0.35 : 1.00,
    serving_route_count:       applicabilityMet ? 2 : 0,
    route_radius_miles:        0.5,
    routes_trigger_analysis:   applicabilityMet,
    delta_t_triggered:         false,
    egress_minutes:            0.0,
  }, overrides);
}

function makeInput(tier, paths, project, analysis, overrides) {
  return Object.assign({
    brief_input_version: 1,
    source:              'pipeline',
    city_name:           'Berkeley',
    city_slug:           'berkeley',
    case_number:         'JOSH-2026-37_8700-n122_2700',
    eval_date:           '2026-04-09',
    audit_text:          '',
    audit_filename:      'determination_37_8700_n122_2700_75u.txt',
    project:             project || makeProject(),
    analysis:            analysis,
    result:              makeResult(tier, paths),
    parameters:          makeParameters(),
  }, overrides);
}

// ── Test 1: Ministerial (below size threshold) ─────────────────────────────────

test('T1 — MINISTERIAL: below size threshold renders correctly', function() {
  var proj  = makeProject({ units: 10 });
  var an    = makeAnalysis(false, false);
  var inp   = makeInput('MINISTERIAL', [], proj, an, {
    result: makeResult('MINISTERIAL', [], { hazard_zone: 'non_fhsz', project_vehicles: 0, max_delta_t_minutes: 0 }),
  });

  var html = BR.render(inp);

  // Tier pill
  assert.ok(html.includes('MINISTERIAL<br>APPROVAL ELIGIBLE'), 'tier pill label');
  // Size gate detail
  assert.ok(html.includes('below the 15-unit threshold') || html.includes('&lt;&nbsp; 15-unit threshold'), 'below threshold copy');
  // Applicability row chip
  assert.ok(html.includes('BELOW THRESHOLD'), 'A row chip');
  // No ΔT route table rendered (CSS class exists but the <table> element should not)
  assert.ok(!html.includes("<table class='route-table'>"), 'no route table element for ministerial');
  // Conditions
  assert.ok(html.includes('qualifies for ministerial approval'), 'ministerial conditions');
  // No what-if banner
  assert.ok(!html.includes('What-If Estimate'), 'no whatif banner for pipeline source');
});

// ── Test 2: Ministerial with Standard Conditions (FHSZ, within threshold) ─────

test('T2 — MINISTERIAL WITH STANDARD CONDITIONS: FHSZ flagged, paths within threshold', function() {
  var path1 = makePath({ delta_t_minutes: 1.5, flagged: false });
  var an    = makeAnalysis(true, true, { delta_t_triggered: false });
  var inp   = makeInput('MINISTERIAL WITH STANDARD CONDITIONS', [path1], null, an, {
    result: makeResult('MINISTERIAL WITH STANDARD CONDITIONS', [path1], { triggered: false }),
  });

  var html = BR.render(inp);

  // Tier pill label
  assert.ok(html.includes('MINISTERIAL W/<br>STANDARD CONDITIONS'), 'tier pill label');
  // Criterion A chip
  assert.ok(html.includes('IN SCOPE'), 'A row in-scope chip');
  // Criterion B chip — FHSZ
  assert.ok(html.includes('VERY HIGH FHSZ'), 'B row FHSZ chip');
  // Criterion C chip — within threshold
  assert.ok(html.includes('WITHIN THRESHOLD'), 'C row within-threshold chip');
  // Conditions: ministerial approved with conditions; FHSZ level >= 2 → defensible space
  assert.ok(html.includes('approved ministerially'), 'conditional ministerial conditions');
  assert.ok(html.includes('Defensible space compliance'), 'FHSZ conditions for level 3');
  // No what-if banner
  assert.ok(!html.includes('What-If Estimate'), 'no whatif banner');
});

// ── Test 3: Discretionary (single flagged path) ────────────────────────────────

test('T3 — DISCRETIONARY: single flagged path renders controlling finding', function() {
  var path1 = makePath();  // delta_t=8.5, threshold=2.25, flagged=true
  var an    = makeAnalysis(true, true, { delta_t_triggered: true });
  var inp   = makeInput('DISCRETIONARY', [path1], null, an, {
    result: makeResult('DISCRETIONARY', [path1]),
  });

  var html = BR.render(inp);

  // Tier pill
  assert.ok(html.includes('DISCRETIONARY<br>REVIEW REQUIRED'), 'tier pill label');
  // Criterion C chip
  assert.ok(html.includes('EXCEEDS THRESHOLD'), 'C row exceeds chip');
  // Controlling finding callout — bottleneck name
  assert.ok(html.includes('Grizzly Peak Blvd'), 'bottleneck name in controlling finding');
  // Controlling badge in route table
  assert.ok(html.includes('CONTROLLING'), 'CONTROLLING badge in route table');
  // Conditions: requires discretionary review
  assert.ok(html.includes('requires discretionary review'), 'discretionary conditions');
  // Legal authority section present
  assert.ok(html.includes('Legal Authority'), 'Legal Authority section header');
  // Appeal rights present
  assert.ok(html.includes('Appeal Rights'), 'Appeal Rights section header');
});

// ── Test 4: Discretionary with multiple paths (omitted-paths notice) ───────────

test('T4 — DISCRETIONARY: paths beyond display limit shows omission notice', function() {
  // 1 flagged + 6 within-threshold paths → 5 within-threshold omitted (only 3 near-threshold shown)
  var flaggedPath = makePath({ path_id: 'P1', delta_t_minutes: 8.50, flagged: true });
  // Near-threshold paths (> 70% of 2.25 = 1.575)
  var nearPaths = [1,2,3].map(function(i) {
    return makePath({ path_id: 'P'+(i+1), delta_t_minutes: 1.80, flagged: false });
  });
  // Far-under-threshold paths — will be omitted
  var farPaths = [4,5,6,7].map(function(i) {
    return makePath({ path_id: 'P'+(i+4), delta_t_minutes: 0.30, flagged: false });
  });
  var allPaths = [flaggedPath].concat(nearPaths).concat(farPaths);
  var an       = makeAnalysis(true, true, { delta_t_triggered: true });
  var inp      = makeInput('DISCRETIONARY', allPaths, null, an, {
    result: makeResult('DISCRETIONARY', allPaths),
  });

  var html = BR.render(inp);

  assert.ok(html.includes('DISCRETIONARY<br>REVIEW REQUIRED'), 'tier label');
  assert.ok(html.includes('additional path(s) within threshold'), 'omission notice');
  assert.ok(html.includes('omitted for brevity'), 'omission reason text');
});

// ── Test 5: What-If banner ─────────────────────────────────────────────────────

test('T5 — source=whatif shows banner; source=pipeline does not', function() {
  var path1 = makePath();
  var an    = makeAnalysis(true, true, { delta_t_triggered: true });
  var base  = makeInput('DISCRETIONARY', [path1], null, an, {
    result: makeResult('DISCRETIONARY', [path1]),
  });

  // source = 'whatif'
  var whatifInp = Object.assign({}, base, { source: 'whatif' });
  var htmlWhatif = BR.render(whatifInp);
  assert.ok(htmlWhatif.includes('What-If Estimate'), 'whatif banner present');
  assert.ok(htmlWhatif.includes('whatif-banner'), 'whatif banner CSS class');

  // source = 'pipeline'
  var htmlPipeline = BR.render(base);
  assert.ok(!htmlPipeline.includes('What-If Estimate'), 'no whatif banner for pipeline');
});

// ── Test 6: Case number slug from project name ─────────────────────────────────

test('T6 — project name produces slug in case number', function() {
  var proj = makeProject({ name: 'Silvergate Development', units: 148 });
  var an   = makeAnalysis(true, true, { delta_t_triggered: true });
  var inp  = makeInput('DISCRETIONARY', [makePath()], proj, an, {
    case_number: 'JOSH-2026-SILVERGATE-DEVELOP-37_8700-n122_2700',
    result: makeResult('DISCRETIONARY', [makePath()]),
  });

  var html = BR.render(inp);

  // Case number appears in header
  assert.ok(html.includes('JOSH-2026-SILVERGATE-DEVELOP-37_8700-n122_2700'), 'case number in header');
  // Project name appears in header
  assert.ok(html.includes('Silvergate Development'), 'project name in header');
});

// ── Test 7: HCM detail rendered in route table bottleneck cell ─────────────────

test('T7 — bottleneck HCM detail (road type, speed, lanes, degradation) in route table', function() {
  var path1 = makePath({
    bottleneck_road_type:          'two_lane',
    bottleneck_speed_mph:          30,
    bottleneck_lanes:              2,
    bottleneck_hcm_capacity_vph:   1350,
    bottleneck_eff_cap_vph:        473,
    bottleneck_hazard_degradation: 0.35,
  });
  var an  = makeAnalysis(true, true, { delta_t_triggered: true });
  var inp = makeInput('DISCRETIONARY', [path1], null, an, {
    result: makeResult('DISCRETIONARY', [path1]),
  });

  var html = BR.render(inp);

  // HCM string: "HCM 1,350 × 0.35 = 473 vph" (using narrow spaces/× unicode)
  assert.ok(html.includes('1,350') || html.includes('1350'), 'HCM raw capacity');
  assert.ok(html.includes('0.35'), 'hazard degradation factor');
  assert.ok(html.includes('473'), 'effective capacity');
  // Road type abbreviation
  assert.ok(html.includes('Two-lane') || html.includes('two_lane'), 'road type in table');
  // Speed
  assert.ok(html.includes('30'), 'speed in table');
});

// ── Test 8: Egress penalty display ────────────────────────────────────────────

test('T8 — egress penalty shown when egress_minutes > 0', function() {
  var proj = makeProject({ units: 75, stories: 6 });
  var path1 = makePath({ egress_minutes: 9.0 });
  var an    = makeAnalysis(true, true, { delta_t_triggered: true, egress_minutes: 9.0 });
  var result = makeResult('DISCRETIONARY', [path1], {
    egress_minutes: 9.0,
    max_delta_t_minutes: 8.50,
  });
  var inp = Object.assign(makeInput('DISCRETIONARY', [path1], proj, an), { result: result });

  var html = BR.render(inp);

  // Egress penalty label appears in C row detail
  assert.ok(html.includes('Building egress'), 'egress penalty label');
  assert.ok(html.includes('9.0 min') || html.includes('+9.0'), 'egress minutes value');
  // Core formula shows egress_penalty line
  assert.ok(html.includes('egress_penalty'), 'egress_penalty in formula');
  assert.ok(!html.includes('egress_penalty = 0'), 'no "= 0" line when penalty applies');
});

// ── Test 9: Audit trail collapsible block ─────────────────────────────────────

test('T9 — audit_text produces collapsible <details> block; empty audit_text omits it', function() {
  var path1      = makePath();
  var an         = makeAnalysis(true, true, { delta_t_triggered: true });
  var baseResult = makeResult('DISCRETIONARY', [path1]);

  // With audit trail
  var withAudit = Object.assign(makeInput('DISCRETIONARY', [path1], null, an, { result: baseResult }), {
    audit_text:     'JOSH Audit Trail v4.0\nProject: Test\nΔT = 8.50 min',
    audit_filename: 'determination_37_8700_n122_2700_75u.txt',
  });
  var htmlWith = BR.render(withAudit);
  assert.ok(htmlWith.includes('<details'), 'details block present when audit_text set');
  assert.ok(htmlWith.includes('determination_37_8700_n122_2700_75u.txt'), 'audit filename in summary');
  assert.ok(htmlWith.includes('JOSH Audit Trail v4.0'), 'audit text content embedded');

  // Without audit trail
  var noAudit = Object.assign(makeInput('DISCRETIONARY', [path1], null, an, { result: baseResult }), {
    audit_text:     '',
    audit_filename: 'determination_37_8700_n122_2700_75u.txt',
  });
  var htmlNo = BR.render(noAudit);
  // No <details> block when audit_text is empty
  var detailsInLegal = htmlNo.indexOf('<details');
  assert.ok(detailsInLegal === -1, 'no details block when audit_text is empty');
});

// ── Test 10: Cross-street bottleneck labels ──────────────────────────────────

test('T10 — cross-street bottleneck: two cross streets renders "Name (A to B), dist mi bearing"', function() {
  var path1 = makePath({
    bottleneck_name:             'Grizzly Peak Blvd',
    bottleneck_cross_street_a:   'Centennial Dr',
    bottleneck_cross_street_b:   'Euclid Ave',
    bottleneck_distance_mi:      0.3,
    bottleneck_bearing:          'NW',
    delta_t_minutes:             8.50,
    flagged:                     true,
  });
  var an  = makeAnalysis(true, true, { delta_t_triggered: true });
  var inp = makeInput('DISCRETIONARY', [path1], null, an);

  var html = BR.render(inp);

  // Controlling finding callout should use cross-street label
  assert.ok(html.includes('Grizzly Peak Blvd (Centennial Dr to Euclid Ave)'), 'cross-street pair in controlling callout');
  assert.ok(html.includes('0.3 mi NW'), 'distance+bearing in controlling callout');

  // Route table bottleneck cell should also use cross-street label
  assert.ok(html.includes('Centennial Dr to Euclid Ave'), 'cross-street pair in route table');
});

test('T11 — cross-street bottleneck: single cross street renders "Name at Cross"', function() {
  var path1 = makePath({
    bottleneck_name:             'Oxford St',
    bottleneck_cross_street_a:   'Cedar St',
    bottleneck_cross_street_b:   '',
    bottleneck_distance_mi:      0.1,
    bottleneck_bearing:          'E',
    delta_t_minutes:             8.50,
    flagged:                     true,
  });
  var an  = makeAnalysis(true, true, { delta_t_triggered: true });
  var inp = makeInput('DISCRETIONARY', [path1], null, an);

  var html = BR.render(inp);

  assert.ok(html.includes('Oxford St at Cedar St'), 'single cross street uses "at"');
  assert.ok(html.includes('0.1 mi E'), 'distance+bearing present');
});

test('T12 — cross-street bottleneck: no cross streets falls back to name only', function() {
  var path1 = makePath({
    bottleneck_name:             'Highway 13',
    bottleneck_cross_street_a:   '',
    bottleneck_cross_street_b:   '',
    bottleneck_distance_mi:      0.0,
    bottleneck_bearing:          '',
    delta_t_minutes:             8.50,
    flagged:                     true,
  });
  var an  = makeAnalysis(true, true, { delta_t_triggered: true });
  var inp = makeInput('DISCRETIONARY', [path1], null, an);

  var html = BR.render(inp);

  // Name appears without cross-street decoration
  assert.ok(html.includes('Highway 13'), 'bottleneck name present');
  // Should NOT contain cross-street patterns — "Name (CrossA to CrossB)" or "Name at Cross"
  assert.ok(!html.includes('Highway 13 (Centennial'), 'no cross-street parens');
  assert.ok(!html.includes('Highway 13 at '), 'no "at" when no cross streets');
  // Should NOT contain "Unnamed road" since we have a name
  assert.ok(!html.includes('Unnamed road'), 'no unnamed road when name is present');
});

test('T13 — cross-street bottleneck: unnamed road with cross streets', function() {
  var path1 = makePath({
    bottleneck_name:             '',
    bottleneck_osmid:            '999888',
    bottleneck_cross_street_a:   'Main St',
    bottleneck_cross_street_b:   'Oak Ave',
    bottleneck_distance_mi:      0.2,
    bottleneck_bearing:          'S',
    delta_t_minutes:             8.50,
    flagged:                     true,
  });
  var an  = makeAnalysis(true, true, { delta_t_triggered: true });
  var inp = makeInput('DISCRETIONARY', [path1], null, an);

  var html = BR.render(inp);

  assert.ok(html.includes('Unnamed road (Main St to Oak Ave)'), 'unnamed road with cross streets');
  assert.ok(html.includes('0.2 mi S'), 'distance+bearing for unnamed road');
});

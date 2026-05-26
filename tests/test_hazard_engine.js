// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * HazardEngine — Berkeley golden-file parity tests.
 *
 * The legal artifact of record: the engine's output must match the hand-verified
 * expected outputs in tests/golden/berkeley/*.expected.json field-by-field.
 * If a test fails, the engine has a bug — fix the engine, not the golden file.
 *
 * Test data:
 *   - tests/golden/berkeley/*.expected.json — 6 expected outputs (4 wildfire-evaluated +
 *     2 below-threshold)
 *   - output/berkeley/graph.json            — OSMnx graph with pre-baked wildfire eff_cap
 *   - output/berkeley/fhsz.json             — CAL FIRE FHSZ polygons
 *   - output/berkeley/parameters.json       — runtime parameters
 *   - config/hazards/wildfire.yaml          — loaded via Python subprocess for single
 *                                              source of truth
 *
 * Per docs/plan-multihazard-stage-1-hooks.md §10. Run:
 *   node --test tests/test_hazard_engine.js
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const REPO_ROOT = path.resolve(__dirname, '..');

// Bootstrap engine module graph
require(path.join(REPO_ROOT, 'static', 'hooks.js'));
require(path.join(REPO_ROOT, 'static', 'transforms', '_defaults.js'));
const HazardEngine = require(path.join(REPO_ROOT, 'static', 'hazard_engine.js'));

// ─── Load Berkeley fixture data ─────────────────────────────────────────────

function loadJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(REPO_ROOT, rel), 'utf8'));
}

function loadWildfireConfigViaPython() {
  // Single source of truth: invoke Python to load + validate the YAML and emit
  // its to_js_payload() as JSON. This catches YAML drift at test time.
  const out = execFileSync('uv', [
    'run', 'python', '-c',
    'import json, sys; sys.path.insert(0, "."); ' +
    'from agents.scenarios.hazard_config import HazardConfig; ' +
    'cfg = HazardConfig.from_yaml("config/hazards/wildfire.yaml"); ' +
    'print(json.dumps(cfg.to_js_payload()))'
  ], { cwd: REPO_ROOT, encoding: 'utf8' });
  return JSON.parse(out);
}

const graph = loadJson('output/berkeley/graph.json');
const params = loadJson('output/berkeley/parameters.json');
const fhszGeo = loadJson('output/berkeley/fhsz.json');
const wildfireCfg = loadWildfireConfigViaPython();

// Construct JOSH_DATA fixture matching what would ship in analysis_map.html
const joshDataFixture = {
  schema_version: 2,
  graph: graph,
  parameters: params,
  hazard_polygons: {
    wildfire: {
      feature_collection: fhszGeo,
      zone_attribute: wildfireCfg.zone_attribute,
      zone_map: wildfireCfg.zone_map,
      palette: wildfireCfg.palette,
      labels: wildfireCfg.labels,
      legend_label: wildfireCfg.legend_label
    }
  },
  hazard_configs: {
    wildfire: wildfireCfg
  }
};

// One-time engine init for the whole test file
HazardEngine.init(joshDataFixture);

// ─── Test helpers ───────────────────────────────────────────────────────────

/**
 * Normalize the engine's HazardEngine.evaluateProject() output to the shape
 * the golden files use. Strips fields that are intentionally not validated
 * (route_coords — per-edge geometry; verified separately via Playwright smokes).
 */
function _normalizeActual(actual) {
  const out = {
    schema_version: 2,
    controlling_hazard: actual.controlling_hazard,
    tier: actual.tier,
    hazard_results: []
  };
  // The engine returns results keyed by hazard_id; golden expects array.
  // Order: alphabetical by hazard_id for determinism.
  const keys = Object.keys(actual.results || {}).sort();
  for (const k of keys) {
    const r = actual.results[k];
    const cleaned = Object.assign({}, r);
    delete cleaned.route_coords;
    out.hazard_results.push(cleaned);
  }
  return out;
}

function _normalizeExpected(expected) {
  const out = {
    schema_version: expected.schema_version || 2,
    controlling_hazard: expected.controlling_hazard,
    tier: expected.tier,
    hazard_results: []
  };
  for (const r of (expected.hazard_results || [])) {
    const cleaned = Object.assign({}, r);
    delete cleaned.route_coords;
    out.hazard_results.push(cleaned);
  }
  return out;
}

// ─── Golden runner ──────────────────────────────────────────────────────────

const goldenDir = path.join(__dirname, 'golden', 'berkeley');
const goldenFiles = fs.readdirSync(goldenDir)
  .filter(f => f.endsWith('.expected.json'))
  .sort();

for (const file of goldenFiles) {
  test(`golden: ${file}`, () => {
    const spec = JSON.parse(fs.readFileSync(path.join(goldenDir, file), 'utf8'));
    const project = {
      id: spec.project.id,
      lat: spec.project.lat,
      lng: spec.project.lng,
      units: spec.project.units,
      stories: spec.project.stories
    };

    const actual = HazardEngine.evaluateProject(project);
    const normalizedActual = _normalizeActual(actual);
    const normalizedExpected = _normalizeExpected(spec.expected);

    assert.deepStrictEqual(
      normalizedActual,
      normalizedExpected,
      `Golden file mismatch for ${file}.\n` +
      `Expected:\n${JSON.stringify(normalizedExpected, null, 2)}\n` +
      `Actual:\n${JSON.stringify(normalizedActual, null, 2)}`
    );
  });
}

// ─── Engine-level sanity checks ─────────────────────────────────────────────

test('engine bootstrap: state populated from JOSH_DATA fixture', () => {
  const s = HazardEngine._state();
  assert.equal(s.ready, true);
  assert.ok(s.node_count > 2000, 'expected >2000 nodes in Berkeley graph');
  assert.ok(s.edge_count > 5000, 'expected >5000 edges in Berkeley graph');
  assert.ok(s.exit_count >= 1, 'expected at least 1 exit node');
  assert.equal(s.hazard_count, 1, 'expected exactly 1 hazard config (wildfire)');
});

test('wildfire config loaded via Python passes schema validation', () => {
  assert.equal(wildfireCfg.hazard_id, 'wildfire');
  assert.equal(wildfireCfg.mobilization, 0.90);
  assert.equal(wildfireCfg.dispositive_at_standard_3, false);
  assert.equal(wildfireCfg.degradation.vhfhsz, 0.35);
  assert.deepEqual(wildfireCfg.hooks, {});
  assert.ok(wildfireCfg.result_extras.fhsz_haz_class);
  assert.equal(wildfireCfg.result_extras.fhsz_haz_class.from, 'zone_lookup');
});

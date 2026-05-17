// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * Unit tests for static/hazard_polygon_layer.js
 *
 * Stage 0 Step 3 verification per docs/plan-multihazard-stage-0.md §6.3.
 * Run: node --test tests/test_hazard_polygon_layer.js
 *
 * Browser-side verification is intentionally skipped at Step 3 — the module
 * is not yet wired into the production map. Step 8 (Hazard Layers panel)
 * runs the visual-parity check when the factory replaces Folium FHSZ rendering.
 */

'use strict';

const test   = require('node:test');
const assert = require('node:assert/strict');

const HazardPolygonLayer = require('../static/hazard_polygon_layer.js');

// ── Test fixtures ───────────────────────────────────────────────────────────

// A minimal Leaflet stub. L.geoJSON captures the (data, options) it was called
// with and returns a layer-like object that records bindTooltip calls.
function makeLeafletStub() {
  const calls = [];
  return {
    calls,
    geoJSON(data, options) {
      // Simulate Leaflet's behavior: invoke onEachFeature for each feature so
      // tests can assert tooltips were bound.
      const bound = [];
      const features = (data && data.features) || [];
      features.forEach(function (feature) {
        const featureLayer = {
          feature,
          tooltipText: null,
          tooltipOpts: null,
          bindTooltip(text, opts) {
            this.tooltipText = text;
            this.tooltipOpts = opts;
            return this;
          }
        };
        if (typeof options.onEachFeature === 'function') {
          options.onEachFeature(feature, featureLayer);
        }
        bound.push(featureLayer);
      });
      const layer = {
        data,
        options,
        // Apply style to each feature (Leaflet does this internally; we
        // expose the resolved styles for test assertions).
        resolvedStyles: features.map(function (f) {
          return typeof options.style === 'function' ? options.style(f) : options.style;
        }),
        boundFeatures: bound
      };
      calls.push({ data, options, layer });
      return layer;
    }
  };
}

// Berkeley-shaped FHSZ feature collection (one tiny triangle per zone).
const FHSZ_FIXTURE = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { HAZ_CLASS: 3 },
      geometry: { type: 'Polygon', coordinates: [[[-122.25,37.88],[-122.24,37.88],[-122.24,37.89],[-122.25,37.88]]] }
    },
    {
      type: 'Feature',
      properties: { HAZ_CLASS: 2 },
      geometry: { type: 'Polygon', coordinates: [[[-122.26,37.87],[-122.25,37.87],[-122.25,37.88],[-122.26,37.87]]] }
    },
    {
      type: 'Feature',
      properties: { HAZ_CLASS: 1 },
      geometry: { type: 'Polygon', coordinates: [[[-122.27,37.86],[-122.26,37.86],[-122.26,37.87],[-122.27,37.86]]] }
    }
  ]
};

const WILDFIRE_RECORD = Object.freeze({
  feature_collection: FHSZ_FIXTURE,
  zone_attribute: 'HAZ_CLASS',
  zone_map: { '3': 'vhfhsz', '2': 'high_fhsz', '1': 'moderate_fhsz' },
  palette: {
    vhfhsz: '#d62728',
    high_fhsz: '#fc8d59',
    moderate_fhsz: '#ffeda0'
  },
  labels: {
    vhfhsz: 'CAL FIRE FHSZ — Very High Fire Hazard (VHFHSZ)',
    high_fhsz: 'CAL FIRE FHSZ — High Fire Hazard',
    moderate_fhsz: 'CAL FIRE FHSZ — Moderate Fire Hazard'
  },
  legend_label: 'Wildfire (FHSZ)'
});

// FEMA NFHL-shaped fixture — proves the factory is hazard-agnostic.
const FLOOD_FIXTURE = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { FLD_ZONE: 'AE', BFE_FT: 14.5 },
      geometry: { type: 'Polygon', coordinates: [[[-122.32,37.86],[-122.30,37.86],[-122.30,37.88],[-122.32,37.86]]] }
    },
    {
      type: 'Feature',
      properties: { FLD_ZONE: 'X', BFE_FT: null },
      geometry: { type: 'Polygon', coordinates: [[[-122.28,37.85],[-122.27,37.85],[-122.27,37.86],[-122.28,37.85]]] }
    }
  ]
};

const FLOOD_RECORD = Object.freeze({
  feature_collection: FLOOD_FIXTURE,
  zone_attribute: 'FLD_ZONE',
  zone_map: { AE: 'ae', A: 'a', AO: 'ao', VE: 've', X: 'x' },
  palette: { ae: '#1f77b4', a: '#1f77b4', x: 'transparent' },
  labels: { ae: 'FEMA NFHL — Zone AE', x: 'FEMA NFHL — Zone X (unshaded)' },
  legend_label: 'Flood (FEMA NFHL)'
});

// ── Module surface ──────────────────────────────────────────────────────────

test('module exports expected surface', () => {
  assert.equal(typeof HazardPolygonLayer.create, 'function');
  assert.equal(typeof HazardPolygonLayer.resolveZone, 'function');
  assert.equal(typeof HazardPolygonLayer.styleForFeature, 'function');
  assert.equal(typeof HazardPolygonLayer.tooltipForFeature, 'function');
  assert.equal(typeof HazardPolygonLayer.validateRecord, 'function');
  assert.equal(typeof HazardPolygonLayer.DEFAULT_STYLE, 'object');
  assert.equal(HazardPolygonLayer.FALLBACK_COLOR, '#cccccc');
});

test('DEFAULT_STYLE matches Folium production baseline (fillOpacity 0.20, weight 0.5)', () => {
  // Locked rationale: visual parity with current Folium FHSZ rendering at
  // analysis_map.py:280. Changing these defaults would drift the baseline.
  assert.equal(HazardPolygonLayer.DEFAULT_STYLE.fillOpacity, 0.20);
  assert.equal(HazardPolygonLayer.DEFAULT_STYLE.weight, 0.5);
});

// ── resolveZone ─────────────────────────────────────────────────────────────

test('resolveZone — wildfire HAZ_CLASS 3 → vhfhsz', () => {
  const f = WILDFIRE_RECORD.feature_collection.features[0]; // HAZ_CLASS = 3
  assert.equal(HazardPolygonLayer.resolveZone(WILDFIRE_RECORD, f), 'vhfhsz');
});

test('resolveZone — coerces numeric raw to string when looking up zone_map', () => {
  // FHSZ feature has HAZ_CLASS: 3 (integer); zone_map keys are strings ('3').
  // resolveZone must String(raw) before lookup.
  const f = WILDFIRE_RECORD.feature_collection.features[0];
  assert.equal(typeof f.properties.HAZ_CLASS, 'number');
  assert.equal(HazardPolygonLayer.resolveZone(WILDFIRE_RECORD, f), 'vhfhsz');
});

test('resolveZone — flood FLD_ZONE "AE" → ae (hazard-agnostic shape)', () => {
  const f = FLOOD_RECORD.feature_collection.features[0]; // FLD_ZONE = 'AE'
  assert.equal(HazardPolygonLayer.resolveZone(FLOOD_RECORD, f), 'ae');
});

test('resolveZone — unknown zone returns null (not exception)', () => {
  const f = {
    type: 'Feature',
    properties: { HAZ_CLASS: 99 },  // not in zone_map
    geometry: { type: 'Point', coordinates: [0, 0] }
  };
  assert.equal(HazardPolygonLayer.resolveZone(WILDFIRE_RECORD, f), null);
});

test('resolveZone — missing properties returns null', () => {
  assert.equal(HazardPolygonLayer.resolveZone(WILDFIRE_RECORD, null), null);
  assert.equal(HazardPolygonLayer.resolveZone(WILDFIRE_RECORD, {}), null);
  assert.equal(HazardPolygonLayer.resolveZone(WILDFIRE_RECORD, { properties: {} }), null);
});

// ── styleForFeature ─────────────────────────────────────────────────────────

test('styleForFeature — VHFHSZ feature returns palette color + default style', () => {
  const f = WILDFIRE_RECORD.feature_collection.features[0]; // vhfhsz
  const s = HazardPolygonLayer.styleForFeature(WILDFIRE_RECORD, f);
  assert.equal(s.fillColor, '#d62728');     // vhfhsz palette
  assert.equal(s.color,     '#d62728');     // stroke = fill (no override)
  assert.equal(s.fillOpacity, 0.20);
  assert.equal(s.weight, 0.5);
});

test('styleForFeature — unknown zone gets FALLBACK_COLOR, never throws', () => {
  const f = {
    type: 'Feature',
    properties: { HAZ_CLASS: 99 },
    geometry: { type: 'Polygon', coordinates: [] }
  };
  const s = HazardPolygonLayer.styleForFeature(WILDFIRE_RECORD, f);
  assert.equal(s.fillColor, '#cccccc');
});

test('styleForFeature — record.style.fillOpacity overrides default', () => {
  const customRecord = Object.assign({}, WILDFIRE_RECORD, {
    style: { fillOpacity: 0.45 }
  });
  const f = WILDFIRE_RECORD.feature_collection.features[0];
  const s = HazardPolygonLayer.styleForFeature(customRecord, f);
  assert.equal(s.fillOpacity, 0.45);
  assert.equal(s.weight, 0.5);  // unchanged
});

test('styleForFeature — record.style.color overrides stroke (not fill)', () => {
  const customRecord = Object.assign({}, WILDFIRE_RECORD, {
    style: { color: '#000000' }
  });
  const f = WILDFIRE_RECORD.feature_collection.features[0];
  const s = HazardPolygonLayer.styleForFeature(customRecord, f);
  assert.equal(s.color, '#000000');         // stroke override
  assert.equal(s.fillColor, '#d62728');     // fill still from palette
});

// ── tooltipForFeature ───────────────────────────────────────────────────────

test('tooltipForFeature — known zone uses labels map', () => {
  const f = WILDFIRE_RECORD.feature_collection.features[0]; // vhfhsz
  const t = HazardPolygonLayer.tooltipForFeature(WILDFIRE_RECORD, f);
  assert.equal(t, 'CAL FIRE FHSZ — Very High Fire Hazard (VHFHSZ)');
});

test('tooltipForFeature — unknown zone falls back to "<legend_label> — <raw>"', () => {
  const f = {
    type: 'Feature',
    properties: { HAZ_CLASS: 99 },
    geometry: { type: 'Polygon', coordinates: [] }
  };
  const t = HazardPolygonLayer.tooltipForFeature(WILDFIRE_RECORD, f);
  assert.equal(t, 'Wildfire (FHSZ) — 99');
});

test('tooltipForFeature — missing label for known zone uses fallback', () => {
  const recordMissingLabel = Object.assign({}, WILDFIRE_RECORD, { labels: {} });
  const f = WILDFIRE_RECORD.feature_collection.features[0]; // vhfhsz
  const t = HazardPolygonLayer.tooltipForFeature(recordMissingLabel, f);
  // Fallback uses raw value from feature.properties[zone_attribute]
  assert.equal(t, 'Wildfire (FHSZ) — 3');
});

// ── validateRecord ──────────────────────────────────────────────────────────

test('validateRecord — accepts a valid record (no throw)', () => {
  assert.doesNotThrow(function () {
    HazardPolygonLayer.validateRecord(WILDFIRE_RECORD);
  });
});

test('validateRecord — rejects missing feature_collection', () => {
  assert.throws(
    function () { HazardPolygonLayer.validateRecord({
      zone_attribute: 'HAZ_CLASS', legend_label: 'Wildfire'
    }); },
    /feature_collection must be a GeoJSON FeatureCollection/
  );
});

test('validateRecord — rejects feature_collection of wrong type', () => {
  assert.throws(
    function () { HazardPolygonLayer.validateRecord({
      feature_collection: { type: 'Feature', properties: {} },
      zone_attribute: 'HAZ_CLASS', legend_label: 'Wildfire'
    }); },
    /feature_collection must be a GeoJSON FeatureCollection/
  );
});

test('validateRecord — rejects missing zone_attribute', () => {
  assert.throws(
    function () { HazardPolygonLayer.validateRecord({
      feature_collection: FHSZ_FIXTURE, legend_label: 'Wildfire'
    }); },
    /zone_attribute must be a string/
  );
});

test('validateRecord — rejects missing legend_label', () => {
  assert.throws(
    function () { HazardPolygonLayer.validateRecord({
      feature_collection: FHSZ_FIXTURE, zone_attribute: 'HAZ_CLASS'
    }); },
    /legend_label must be a string/
  );
});

test('validateRecord — null/undefined throws with clear message', () => {
  assert.throws(
    function () { HazardPolygonLayer.validateRecord(null); },
    /record must be an object/
  );
});

// ── create — end-to-end with Leaflet stub ───────────────────────────────────

test('create — requires a usable L (Leaflet) argument', () => {
  assert.throws(
    function () { HazardPolygonLayer.create(null, WILDFIRE_RECORD); },
    /L \(Leaflet\) is required/
  );
  assert.throws(
    function () { HazardPolygonLayer.create({}, WILDFIRE_RECORD); },
    /L \(Leaflet\) is required/
  );
});

test('create — wildfire record produces a L.geoJSON layer with correct styling per feature', () => {
  const stub = makeLeafletStub();
  const layer = HazardPolygonLayer.create(stub, WILDFIRE_RECORD);
  assert.equal(stub.calls.length, 1, 'L.geoJSON called exactly once');
  assert.equal(layer.data, FHSZ_FIXTURE);
  assert.equal(layer.resolvedStyles.length, 3);

  // Feature 0: HAZ_CLASS=3 → vhfhsz → #d62728
  assert.equal(layer.resolvedStyles[0].fillColor, '#d62728');
  assert.equal(layer.resolvedStyles[0].fillOpacity, 0.20);
  assert.equal(layer.resolvedStyles[0].weight, 0.5);
  // Feature 1: HAZ_CLASS=2 → high_fhsz → #fc8d59
  assert.equal(layer.resolvedStyles[1].fillColor, '#fc8d59');
  // Feature 2: HAZ_CLASS=1 → moderate_fhsz → #ffeda0
  assert.equal(layer.resolvedStyles[2].fillColor, '#ffeda0');
});

test('create — flood record (FLD_ZONE) renders correctly via same factory', () => {
  // Proves hazard-agnostic: factory works for non-wildfire hazards without
  // any hazard_id branching in the module.
  const stub = makeLeafletStub();
  const layer = HazardPolygonLayer.create(stub, FLOOD_RECORD);
  assert.equal(stub.calls.length, 1);
  assert.equal(layer.resolvedStyles.length, 2);

  // Feature 0: FLD_ZONE='AE' → ae → #1f77b4
  assert.equal(layer.resolvedStyles[0].fillColor, '#1f77b4');
  // Feature 1: FLD_ZONE='X' → x → 'transparent'
  assert.equal(layer.resolvedStyles[1].fillColor, 'transparent');
});

test('create — binds tooltip to each feature using labels map', () => {
  const stub = makeLeafletStub();
  const layer = HazardPolygonLayer.create(stub, WILDFIRE_RECORD);
  assert.equal(layer.boundFeatures.length, 3);
  assert.equal(layer.boundFeatures[0].tooltipText, 'CAL FIRE FHSZ — Very High Fire Hazard (VHFHSZ)');
  assert.equal(layer.boundFeatures[1].tooltipText, 'CAL FIRE FHSZ — High Fire Hazard');
  assert.equal(layer.boundFeatures[2].tooltipText, 'CAL FIRE FHSZ — Moderate Fire Hazard');
  assert.deepEqual(layer.boundFeatures[0].tooltipOpts, { sticky: true });
});

test('create — empty feature collection produces empty layer (no error)', () => {
  const stub = makeLeafletStub();
  const emptyRecord = Object.assign({}, WILDFIRE_RECORD, {
    feature_collection: { type: 'FeatureCollection', features: [] }
  });
  const layer = HazardPolygonLayer.create(stub, emptyRecord);
  assert.equal(layer.resolvedStyles.length, 0);
  assert.equal(layer.boundFeatures.length, 0);
});

test('create — does NOT add the layer to a map (caller responsibility)', () => {
  // Locked decision per plan §6.3 Step 3 PAUSE: factory returns layer
  // un-added; layer panel toggle owns map.addLayer / removeLayer.
  const stub = makeLeafletStub();
  const layer = HazardPolygonLayer.create(stub, WILDFIRE_RECORD);
  // The stub layer never had .addedToMap set anywhere — factory must not
  // have called addTo() on it.
  assert.equal(layer.addedToMap, undefined);
});

// ── Negative cases that previously caused production-style bugs ─────────────

test('regression: feature.properties[zone_attribute] missing → fallback, never crash', () => {
  // Real-world: NPMS pipeline data has features lacking MAOP_PSIG. Factory
  // must degrade gracefully to FALLBACK_COLOR + fallback tooltip text.
  const stub = makeLeafletStub();
  const sparseFixture = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { /* HAZ_CLASS intentionally absent */ },
      geometry: { type: 'Polygon', coordinates: [] }
    }]
  };
  const sparseRecord = Object.assign({}, WILDFIRE_RECORD, {
    feature_collection: sparseFixture
  });
  const layer = HazardPolygonLayer.create(stub, sparseRecord);
  assert.equal(layer.resolvedStyles[0].fillColor, '#cccccc');
  assert.equal(layer.boundFeatures[0].tooltipText, 'Wildfire (FHSZ) — unknown');
});

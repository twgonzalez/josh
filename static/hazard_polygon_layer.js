// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH Hazard Polygon Layer — Multi-Hazard Stage 0
 *
 * UMD module: works in browser and Node.
 *
 * Browser:  window.HazardPolygonLayer.create(L, record) → L.geoJSON layer
 * Node test: require('./static/hazard_polygon_layer.js') → same object
 *
 * Renders one hazard's polygon feature collection as a Leaflet GeoJSON layer.
 * The factory is hazard-agnostic — every hazard works the same way by
 * supplying a `record` with feature_collection + zone_attribute + zone_map +
 * palette + labels.
 *
 * This module is added in Stage 0 Step 3 [PAUSE] per
 * docs/plan-multihazard-stage-0.md §6.3. It is NOT wired into the production
 * map until Stage 0 Step 8 (Hazard Layers panel). Step 3 ships the module
 * with unit tests; Folium-baked FHSZ rendering continues unchanged until then.
 *
 * Locked design decisions (2026-05-17, plan §6.3 Step 3 PAUSE):
 *   • L (Leaflet) is a parameter, not imported — testable in Node with a stub.
 *   • No onClick / onHover callbacks (current production has none; YAGNI).
 *   • No tooltipTemplate function — static labels map per zone.
 *   • Default style matches Folium baseline: fillOpacity 0.20, weight 0.5.
 *   • No legend_priority — stacking controlled by caller's add-order.
 *   • Returns layer NOT added to map — caller does map.addLayer() / removeLayer().
 *   • palette and labels are split maps (not folded into one zones record),
 *     so palette can be reused independently by bar chart, brief cells, etc.
 */

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.HazardPolygonLayer = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // Default style matches current Folium FHSZ rendering at analysis_map.py:280
  // (fillOpacity 0.20, weight 0.5, stroke color = fill color).
  var DEFAULT_STYLE = Object.freeze({
    fillOpacity: 0.20,
    weight: 0.5,
    color: null   // null → use the per-zone palette color for stroke
  });

  var FALLBACK_COLOR = '#cccccc';
  var FALLBACK_LABEL_FN = function (record, rawZone) {
    return record.legend_label + ' — ' + (rawZone == null ? 'unknown' : String(rawZone));
  };

  /**
   * Resolve a feature's normalized zone id from raw properties + zone_map.
   * Returns the zone id (e.g. 'vhfhsz') or null if the feature has no
   * value at zone_attribute or the value isn't in zone_map.
   * Exported for testability.
   */
  function resolveZone(record, feature) {
    if (!record || !feature || !feature.properties) return null;
    var raw = feature.properties[record.zone_attribute];
    if (raw == null) return null;
    var key = String(raw);
    var zmap = record.zone_map || {};
    return Object.prototype.hasOwnProperty.call(zmap, key) ? zmap[key] : null;
  }

  /**
   * Compute the Leaflet path style for a feature, given a record.
   * Used by L.geoJSON style fn. Exported for testability.
   */
  function styleForFeature(record, feature) {
    var zone = resolveZone(record, feature);
    var palette = record.palette || {};
    var color = (zone && palette[zone]) || FALLBACK_COLOR;
    var styleOverrides = record.style || {};
    var fillOpacity = styleOverrides.fillOpacity != null
      ? styleOverrides.fillOpacity : DEFAULT_STYLE.fillOpacity;
    var weight = styleOverrides.weight != null
      ? styleOverrides.weight : DEFAULT_STYLE.weight;
    var stroke = styleOverrides.color != null ? styleOverrides.color : color;
    return {
      fillColor: color,
      color: stroke,
      weight: weight,
      fillOpacity: fillOpacity
    };
  }

  /**
   * Compute the tooltip text for a feature, given a record.
   * Uses record.labels[zone] when available; otherwise a fallback that names
   * the hazard and shows the raw zone value.
   * Exported for testability.
   */
  function tooltipForFeature(record, feature) {
    var zone = resolveZone(record, feature);
    var labels = record.labels || {};
    if (zone && Object.prototype.hasOwnProperty.call(labels, zone)) {
      return labels[zone];
    }
    var raw = (feature && feature.properties)
      ? feature.properties[record.zone_attribute]
      : null;
    return FALLBACK_LABEL_FN(record, raw);
  }

  /**
   * Validate a record before passing to L.geoJSON.
   * Throws Error with a specific message if required fields are missing.
   * Exported for testability.
   */
  function validateRecord(record) {
    if (!record || typeof record !== 'object') {
      throw new Error('HazardPolygonLayer: record must be an object');
    }
    if (!record.feature_collection || record.feature_collection.type !== 'FeatureCollection') {
      throw new Error('HazardPolygonLayer: record.feature_collection must be a GeoJSON FeatureCollection');
    }
    if (!record.zone_attribute || typeof record.zone_attribute !== 'string') {
      throw new Error('HazardPolygonLayer: record.zone_attribute must be a string');
    }
    if (!record.legend_label || typeof record.legend_label !== 'string') {
      throw new Error('HazardPolygonLayer: record.legend_label must be a string');
    }
    // zone_map / palette / labels are optional — fallbacks apply when missing.
  }

  /**
   * Build a Leaflet GeoJSON layer for one hazard.
   *
   * @param {object} L — Leaflet namespace (window.L in browser; stubbed in tests).
   * @param {object} record — hazard polygon record per JOSH_DATA.hazard_polygons[id] schema:
   *     feature_collection: GeoJSON FeatureCollection (required)
   *     zone_attribute:     string property name carrying the zone discriminator (required)
   *     zone_map:           { [raw_value]: normalized_zone_id } (optional)
   *     palette:            { [normalized_zone_id]: hex_color } (optional)
   *     labels:             { [normalized_zone_id]: tooltip_string } (optional)
   *     legend_label:       string for hazard panel chip (required)
   *     style:              optional overrides — { fillOpacity?, weight?, color? }
   * @param {object} options — optional:
   *     renderer:           Leaflet renderer instance (L.canvas() or L.svg()).
   *                         REQUIRED when adding to a map created with
   *                         `preferCanvas: true` (e.g. all Folium-built JOSH
   *                         maps) — without this, vector layers silently
   *                         fall back to SVG and render nothing on the
   *                         canvas-preferred overlay pane.
   * @returns {object} Leaflet L.geoJSON layer (NOT yet added to a map).
   *                   Caller invokes map.addLayer(layer) / map.removeLayer(layer).
   */
  function create(L, record, options) {
    if (!L || typeof L.geoJSON !== 'function') {
      throw new Error('HazardPolygonLayer: L (Leaflet) is required and must expose L.geoJSON');
    }
    validateRecord(record);
    options = options || {};

    var geoJsonOptions = {
      style: function (feature) {
        return styleForFeature(record, feature);
      },
      onEachFeature: function (feature, lyr) {
        if (typeof lyr.bindTooltip === 'function') {
          lyr.bindTooltip(tooltipForFeature(record, feature), { sticky: true });
        }
      }
    };
    if (options.renderer) {
      geoJsonOptions.renderer = options.renderer;
    }

    var layer = L.geoJSON(record.feature_collection, geoJsonOptions);
    return layer;
  }

  return {
    create: create,
    // Exported for unit tests + advanced consumers (e.g. brief cells, bar chart
    // could reuse styleForFeature to colorize zone chips).
    resolveZone: resolveZone,
    styleForFeature: styleForFeature,
    tooltipForFeature: tooltipForFeature,
    validateRecord: validateRecord,
    DEFAULT_STYLE: DEFAULT_STYLE,
    FALLBACK_COLOR: FALLBACK_COLOR
  };
}));

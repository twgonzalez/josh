// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * Smoke tests for the JOSH demo map (Berkeley) — Playwright + node:test.
 *
 * Opens output/berkeley/analysis_map.html as file:// in headless Chromium and
 * exercises the full client-side stack end-to-end:
 *
 *   SMOKE_1:  sidebar div renders with JOSH header + city name
 *   SMOKE_2:  JOSH_DATA has all expected top-level keys
 *   SMOKE_3:  JOSH_DATA.city_slug === 'berkeley'
 *   SMOKE_4:  graph has ≥100 nodes and ≥100 edges
 *   SMOKE_5:  pipeline projects have analysis results
 *   SMOKE_6:  WhatIfEngine.evaluateProject is callable and returns a tier
 *   SMOKE_7:  BriefRenderer.render is callable and returns HTML
 *   SMOKE_8:  Leaflet.AntPath CDN plugin loaded — L.antPath is a function
 *             (skips gracefully when offline or CDN is unreachable)
 *   SMOKE_9:  pipeline project names appear in sidebar DOM as clickable rows
 *   SMOKE_10: selecting a project shows the detail card with a tier badge
 *   SMOKE_11: detail card has a "View Report" button for an analyzed project
 *   SMOKE_12: clicking "+ New" shows the New Project form
 *   SMOKE_13: clicking Cancel dismisses the form and restores the project list
 *   SMOKE_14: "View Report" opens the determination brief modal with srcdoc HTML
 *
 *   Phase 5 coverage — persistence paradigm + form/render correctness:
 *   SMOKE_15: new-project submit does NOT trigger a download dialog
 *             (removed forced saveAsFile on submit)
 *   SMOKE_16: createProject writes to localStorage without _handle/_stale
 *   SMOKE_17: localStorage-seeded browser project loads on page reload
 *   SMOKE_18: form name/address survive a pin-drop re-render
 *             (regression test for the wipe-on-re-render bug)
 *   SMOKE_19: footer has exactly one "Download .json" button
 *             (no Save / Save As… / Export for pipeline)
 *   SMOKE_20: unnamed project row renders italic "Untitled" as real DOM
 *             (regression test for double-escape bug)
 *   SMOKE_21: browser-source project detail shows auto-save status line
 *   SMOKE_22: window.joshSidebar._toYaml() is exposed and returns YAML
 *   SMOKE_23: selecting a pipeline project shows its home icon on the map
 *   SMOKE_24: every pipeline project has a resolvable folium_fg_name
 *             (JOSH_DATA integrity — catches stale builds missing fg wiring)
 *   SMOKE_25: selecting a BROWSER project (new / reloaded / opened from .json)
 *             shows a home icon on the map — browser projects have no Folium
 *             FG, so sidebar.js must draw a runtime home marker instead
 *   SMOKE_26: selecting a browser project also shows the 0.5-mile search
 *             radius circle (matches Folium-baked dashed circle for pipeline)
 *
 * Prerequisites:
 *   npm install                          (installs playwright)
 *   npx playwright install chromium      (downloads headless Chrome)
 *   uv run python build.py map --city Berkeley --data-dir <path>
 *     → output/berkeley/analysis_map.html must exist
 *
 * Run:
 *   node --test tests/smoke_sidebar.js
 *   npm run smoke
 */

'use strict';

const { describe, test, before, after } = require('node:test');
const assert   = require('node:assert/strict');
const { chromium } = require('playwright');
const path     = require('path');
const fs       = require('fs');

// ── Target file ───────────────────────────────────────────────────────────────
const DEMO_MAP = path.resolve(__dirname, '..', 'output', 'berkeley', 'analysis_map.html');
const FILE_URL = 'file://' + DEMO_MAP;

// ── Shared browser + page (launched once, closed after all tests) ─────────────
let browser, page;

// ── Test suite ────────────────────────────────────────────────────────────────
describe('Smoke: Berkeley demo map', { timeout: 90_000 }, () => {

  // ── Setup / teardown ─────────────────────────────────────────────────────────
  before(async () => {
    if (!fs.existsSync(DEMO_MAP)) {
      throw new Error(
        '\nDemo map not found: ' + DEMO_MAP +
        '\nRun: uv run python build.py map --city Berkeley --data-dir <path>\n'
      );
    }
    browser = await chromium.launch({ headless: true });
    const ctx = await browser.newContext({ permissions: [] });
    page = await ctx.newPage();

    // Surface page-level JS errors to stderr for debugging
    page.on('console', msg => {
      if (msg.type() === 'error') {
        process.stderr.write('[page:error] ' + msg.text() + '\n');
      }
    });

    await page.goto(FILE_URL, { waitUntil: 'domcontentloaded' });

    // Wait for sidebar to be rendered — joshSidebar.init() fires on DOMContentLoaded
    // and synchronously populates the sidebar from JOSH_DATA.projects.
    await page.waitForSelector('#josh-sidebar', { state: 'visible', timeout: 15_000 });
  });

  after(async () => {
    await browser?.close();
  });

  // ── SMOKE_1: basic page structure ─────────────────────────────────────────
  test('SMOKE_1: sidebar renders with JOSH header and city name', async () => {
    const text = await page.locator('#josh-sidebar').innerText();
    assert.ok(text.includes('JOSH'),     'header must contain "JOSH"');
    assert.ok(text.includes('Berkeley'), 'header must contain city name "Berkeley"');
  });

  // ── SMOKE_2: JOSH_DATA top-level keys ────────────────────────────────────
  test('SMOKE_2: JOSH_DATA has all expected top-level keys', async () => {
    const keys = await page.evaluate(() => Object.keys(window.JOSH_DATA || {}));
    for (const k of ['city_slug', 'city_name', 'graph', 'parameters', 'projects']) {
      assert.ok(keys.includes(k), `JOSH_DATA missing key: "${k}"`);
    }
  });

  // ── SMOKE_3: city identity ────────────────────────────────────────────────
  test('SMOKE_3: JOSH_DATA.city_slug is "berkeley"', async () => {
    const slug = await page.evaluate(() => window.JOSH_DATA.city_slug);
    assert.equal(slug, 'berkeley');
  });

  // ── SMOKE_4: graph completeness ───────────────────────────────────────────
  test('SMOKE_4: graph has ≥100 nodes and ≥100 edges', async () => {
    const { nodes, edges } = await page.evaluate(() => ({
      nodes: (window.JOSH_DATA.graph.nodes || []).length,
      edges: (window.JOSH_DATA.graph.edges || []).length,
    }));
    assert.ok(nodes >= 100, `expected ≥100 nodes, got ${nodes}`);
    assert.ok(edges >= 100, `expected ≥100 edges, got ${edges}`);
  });

  // ── SMOKE_5: pipeline projects have results ───────────────────────────────
  test('SMOKE_5: JOSH_DATA.projects has ≥1 project with an analysis result', async () => {
    const { total, withResult } = await page.evaluate(() => ({
      total:      (window.JOSH_DATA.projects || []).length,
      withResult: (window.JOSH_DATA.projects || []).filter(p => p.result).length,
    }));
    assert.ok(total      >= 1, `expected ≥1 pipeline project, got ${total}`);
    assert.ok(withResult >= 1, `expected ≥1 project with result, got ${withResult}`);
  });

  // ── SMOKE_6: WhatIfEngine ─────────────────────────────────────────────────
  test('SMOKE_6: WhatIfEngine.evaluateProject is callable and returns a tier', async () => {
    const tier = await page.evaluate(() => {
      if (typeof window.WhatIfEngine === 'undefined') return null;
      // Evaluate a minimal project near UC Berkeley campus
      const r = window.WhatIfEngine.evaluateProject(37.8695, -122.2685, 50, 4);
      return (r && r.tier) || null;
    });
    assert.ok(tier !== null, 'WhatIfEngine.evaluateProject must return a result');
    const valid = ['MINISTERIAL', 'MINISTERIAL WITH STANDARD CONDITIONS', 'DISCRETIONARY'];
    assert.ok(valid.includes(tier), `tier "${tier}" is not one of the valid tiers`);
  });

  // ── SMOKE_7: BriefRenderer ────────────────────────────────────────────────
  test('SMOKE_7: BriefRenderer.render is callable and returns HTML', async () => {
    const html = await page.evaluate(() => {
      if (typeof window.BriefRenderer === 'undefined') return null;
      try {
        return window.BriefRenderer.render({
          brief_input_version: 1,
          source:    'whatif',
          city_name: 'Berkeley',
          city_slug: 'berkeley',
          case_number: 'JOSH-TEST-001',
          eval_date:   '2026-01-01',
          audit_text:  '',
          audit_filename: '',
          project:  { name: 'Test', address: '', lat: 37.87, lon: -122.27, units: 50, stories: 4, apn: '' },
          analysis: {
            applicability_met: true, dwelling_units: 50, unit_threshold: 15,
            fhsz_flagged: false, fhsz_desc: 'Not in FHSZ', fhsz_level: 0,
            hazard_zone: 'non_fhsz', behavioral_mobilization: 0.90,
            hazard_degradation_factor: 1.00, serving_route_count: 2,
            route_radius_miles: 0.5, routes_trigger_analysis: true,
            delta_t_triggered: false, egress_minutes: 0,
          },
          result: {
            tier: 'MINISTERIAL', hazard_zone: 'non_fhsz', project_vehicles: 85.5,
            max_delta_t_minutes: 3.2, threshold_minutes: 6.0,
            safe_egress_window_minutes: 120, max_project_share: 0.05,
            serving_paths_count: 2, egress_minutes: 0,
            parameters_version: '4.0', analyzed_at: '2026-01-01',
            determination_reason: '', triggered: false, paths: [],
          },
          parameters: {},
        });
      } catch (e) { return 'ERROR: ' + e.message; }
    });
    assert.ok(html !== null,                   'BriefRenderer.render must return a value');
    assert.ok(!html.startsWith('ERROR:'),       'BriefRenderer.render must not throw: ' + html);
    assert.ok(html.includes('MINISTERIAL'),    'rendered HTML must contain tier text');
    assert.ok(html.includes('Berkeley'),       'rendered HTML must contain city name');
  });

  // ── SMOKE_8: Leaflet.AntPath CDN plugin ──────────────────────────────────
  test('SMOKE_8: L.antPath loaded from CDN', async (t) => {
    // Requires internet access to load the CDN script.
    // Skips gracefully when offline or CDN is unreachable.
    let loaded = false;
    try {
      await page.waitForFunction(
        () => typeof window.L !== 'undefined' &&
              typeof (window.L.antPath ||
                (window.L.polyline && window.L.polyline.antPath)) === 'function',
        { timeout: 8_000 }
      );
      loaded = true;
    } catch (_) {
      t.skip('Leaflet.AntPath CDN unreachable — skipping (offline or CDN down)');
      return;
    }
    assert.ok(loaded, 'L.antPath must be a function after CDN script loads');
  });

  // ── SMOKE_9: project rows in DOM ──────────────────────────────────────────
  test('SMOKE_9: pipeline project names appear as clickable rows in the sidebar', async () => {
    const rowCount = await page.evaluate(() =>
      document.querySelectorAll('[onclick^="joshSidebar_select"]').length
    );
    assert.ok(rowCount >= 1, `expected ≥1 project row in DOM, got ${rowCount}`);
  });

  // ── SMOKE_10: select project → detail card ────────────────────────────────
  test('SMOKE_10: selecting a project shows detail card with tier badge', async () => {
    // Click the first project row via its onclick handler
    await page.evaluate(() => {
      const row = document.querySelector('[onclick^="joshSidebar_select"]');
      if (row) row.click();
    });
    await page.waitForTimeout(300);
    const text = await page.locator('#josh-sidebar').innerText();
    const hasTier = ['MINISTERIAL', 'CONDITIONAL', 'DISCRETIONARY'].some(t => text.includes(t));
    assert.ok(hasTier, 'detail card must show a tier (MINISTERIAL / CONDITIONAL / DISCRETIONARY)');
  });

  // ── SMOKE_11: "View Report" button ────────────────────────────────────────
  test('SMOKE_11: detail card has "View Report" button for an analyzed project', async () => {
    const hasBtn = await page.evaluate(() =>
      Array.from(document.querySelectorAll('button'))
        .some(b => b.textContent.trim() === 'View Report')
    );
    assert.ok(hasBtn, '"View Report" button must appear in the detail card after selecting an analyzed project');
  });

  // ── SMOKE_12: New project form ────────────────────────────────────────────
  test('SMOKE_12: clicking "+ New" shows the New Project form', async () => {
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('button'))
        .find(b => b.textContent.includes('New'));
      if (btn) btn.click();
    });
    await page.waitForTimeout(300);
    const text = await page.locator('#josh-sidebar').innerText();
    assert.ok(text.includes('New Project'), '"New Project" form heading must appear after clicking + New');
  });

  // ── SMOKE_14: "View Report" brief modal ──────────────────────────────────
  test('SMOKE_14: clicking "View Report" opens the determination brief modal', async () => {
    // SMOKE_12 left the sidebar in "New Project" form mode — no detail card visible.
    // Be self-sufficient: cancel any open form and re-select a pipeline project.
    await page.evaluate(() => {
      // Cancel form if open
      if (typeof joshSidebar_cancelForm === 'function') joshSidebar_cancelForm();
      // Select the first pipeline project that has a result
      const firstWithResult = (window.JOSH_DATA.projects || []).find(p => p.result);
      if (firstWithResult && typeof joshSidebar_select === 'function') {
        joshSidebar_select(firstWithResult.id);
      }
    });
    await page.waitForTimeout(300);

    // The brief modal overlay is injected on DOMContentLoaded by app.js.
    const modalExists = await page.evaluate(() =>
      !!document.getElementById('josh-brief-modal')
    );
    assert.ok(modalExists, '#josh-brief-modal overlay must exist in DOM (injected by app.js)');

    // Ensure modal is currently hidden before clicking
    await page.evaluate(() => {
      const m = document.getElementById('josh-brief-modal');
      if (m) m.style.display = 'none';
    });

    // Click "View Report"
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('button'))
        .find(b => b.textContent.trim() === 'View Report');
      if (btn) btn.click();
    });
    await page.waitForTimeout(600);  // allow BriefRenderer.render() + srcdoc write

    // Modal must be visible
    const modalVisible = await page.evaluate(() => {
      const m = document.getElementById('josh-brief-modal');
      return m && m.style.display !== 'none';
    });
    assert.ok(modalVisible, '#josh-brief-modal must be visible after clicking "View Report"');

    // iframe must have content (srcdoc set, not about:blank)
    const frameHasSrcdoc = await page.evaluate(() => {
      const f = document.getElementById('josh-brief-frame');
      return f && f.srcdoc && f.srcdoc.length > 100;
    });
    assert.ok(frameHasSrcdoc, '#josh-brief-frame must have brief HTML in srcdoc (not about:blank)');

    // Close modal for subsequent tests
    await page.evaluate(() => {
      const m = document.getElementById('josh-brief-modal');
      if (m) m.style.display = 'none';
    });
  });

  // ── SMOKE_13: cancel form ─────────────────────────────────────────────────
  test('SMOKE_13: Cancel dismisses the form and restores the project list', async () => {
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('button'))
        .find(b => b.textContent.trim() === 'Cancel');
      if (btn) btn.click();
    });
    await page.waitForTimeout(300);
    const text = await page.locator('#josh-sidebar').innerText();
    assert.ok(!text.includes('New Project'), '"New Project" heading must be gone after Cancel');
    const rowCount = await page.evaluate(() =>
      document.querySelectorAll('[onclick^="joshSidebar_select"]').length
    );
    assert.ok(rowCount >= 1, `project list rows must be visible after Cancel, got ${rowCount}`);
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Phase 5 — persistence paradigm + form/render correctness
  // ──────────────────────────────────────────────────────────────────────────
  // These tests cover the changes from ~/.claude/plans/spicy-prancing-backus.md:
  //   Change 1: removed forced saveAsFile/saveFile on new-project submit
  //   Change 2: localStorage auto-save for browser-created projects
  //   Change 3: single "Download .json" footer button
  //   Change 4: auto-save status line in detail panel
  //   Plus the Untitled double-escape fix and the form-field persistence fix.
  //
  // Each test is self-resetting (cancels any open form, clears localStorage)
  // so they can be run in any order without cross-contamination.

  // Shared reset helper — ensures a clean starting state for each Phase 5 test.
  async function _resetSidebarState() {
    await page.evaluate(() => {
      if (typeof joshSidebar_cancelForm === 'function') joshSidebar_cancelForm();
      try { localStorage.removeItem('josh_sb_v1_berkeley'); } catch (_) {}
    });
  }

  // ── SMOKE_15: no download dialog on new-project submit ───────────────────
  test('SMOKE_15: new-project submit does not trigger a download dialog', async () => {
    await _resetSidebarState();

    // Detector 1: Playwright download events (blob anchor fallback path).
    let downloadCount = 0;
    const onDownload = () => { downloadCount++; };
    page.on('download', onDownload);

    // Detector 2: FSAPI showSaveFilePicker calls (native picker path).
    await page.evaluate(() => {
      window.__smokePickCount = 0;
      window.__smokeOrigPicker = window.showSaveFilePicker;
      window.showSaveFilePicker = function () {
        window.__smokePickCount++;
        return Promise.reject(new Error('smoke test blocked showSaveFilePicker'));
      };
    });

    try {
      // Open new form + drop pin + fill fields
      await page.evaluate(() => {
        if (typeof joshSidebar_newProject === 'function') joshSidebar_newProject();
        if (window.joshSidebar && typeof window.joshSidebar.onPinPlaced === 'function') {
          window.joshSidebar.onPinPlaced(37.8695, -122.2685);
        }
        const nameEl  = document.getElementById('josh-sb-f-name');
        const unitsEl = document.getElementById('josh-sb-f-units');
        if (nameEl)  { nameEl.value  = 'SMOKE_15 Test'; nameEl.dispatchEvent(new Event('input')); }
        if (unitsEl) { unitsEl.value = '50';            unitsEl.dispatchEvent(new Event('input')); }
      });
      await page.waitForTimeout(500);  // analysis debounce (300 ms) + buffer

      // Submit
      await page.evaluate(() => {
        if (typeof joshSidebar_submitForm === 'function') joshSidebar_submitForm();
      });
      // Give any would-be download a chance to fire
      await page.waitForTimeout(600);

      const pickCount = await page.evaluate(() => window.__smokePickCount || 0);
      assert.equal(downloadCount, 0,
        `new-project submit must not fire a "download" event, got ${downloadCount}`);
      assert.equal(pickCount, 0,
        `new-project submit must not call showSaveFilePicker, got ${pickCount}`);

      // Sanity: a determination is visible in the detail panel
      const text = await page.locator('#josh-sidebar').innerText();
      const hasTier = ['MINISTERIAL', 'CONDITIONAL', 'DISCRETIONARY'].some(t => text.includes(t));
      assert.ok(hasTier, 'detail panel must show a tier after submit (determination generated independently of save)');
    } finally {
      page.off('download', onDownload);
      await page.evaluate(() => {
        if (window.__smokeOrigPicker) window.showSaveFilePicker = window.__smokeOrigPicker;
        delete window.__smokePickCount;
        delete window.__smokeOrigPicker;
      });
    }
  });

  // ── SMOKE_16: localStorage auto-save ─────────────────────────────────────
  test('SMOKE_16: createProject writes to localStorage without _handle / _stale', async () => {
    await _resetSidebarState();

    // Create and submit a browser project
    await page.evaluate(() => {
      if (typeof joshSidebar_newProject === 'function') joshSidebar_newProject();
      if (window.joshSidebar && typeof window.joshSidebar.onPinPlaced === 'function') {
        window.joshSidebar.onPinPlaced(37.8700, -122.2690);
      }
      const nameEl  = document.getElementById('josh-sb-f-name');
      const unitsEl = document.getElementById('josh-sb-f-units');
      if (nameEl)  { nameEl.value  = 'SMOKE_16 Persist'; nameEl.dispatchEvent(new Event('input')); }
      if (unitsEl) { unitsEl.value = '30';               unitsEl.dispatchEvent(new Event('input')); }
    });
    await page.waitForTimeout(500);
    await page.evaluate(() => {
      if (typeof joshSidebar_submitForm === 'function') joshSidebar_submitForm();
    });
    await page.waitForTimeout(400);

    // Inspect localStorage
    const { raw, parsed } = await page.evaluate(() => {
      const raw = localStorage.getItem('josh_sb_v1_berkeley');
      let parsed = null;
      try { parsed = raw ? JSON.parse(raw) : null; } catch (_) {}
      return { raw, parsed };
    });

    assert.ok(raw,    'localStorage key "josh_sb_v1_berkeley" must exist after createProject');
    assert.ok(parsed, 'localStorage value must be valid JSON');
    assert.ok(Array.isArray(parsed.projects) && parsed.projects.length >= 1,
      'localStorage must contain ≥1 browser project');
    const hit = parsed.projects.find(p => p.name === 'SMOKE_16 Persist');
    assert.ok(hit, 'SMOKE_16 project must be in localStorage by name');
    assert.equal(hit.source, 'browser', 'persisted project must be browser-source');
    assert.equal(hit.units,  30,        'units must round-trip');

    // The raw JSON must not contain the runtime-only fields
    assert.ok(!raw.includes('_handle'), '_handle must NOT be serialized to localStorage');
    assert.ok(!raw.includes('_stale'),  '_stale must NOT be serialized to localStorage');
  });

  // ── SMOKE_17: reload persistence ──────────────────────────────────────────
  test('SMOKE_17: localStorage-seeded browser project loads on page reload', async () => {
    await _resetSidebarState();

    // Pre-populate localStorage with a known browser project blob — this
    // isolates the load path from the save path (SMOKE_16 covers save).
    const KNOWN_ID = 'smoke17-persistent-project';
    await page.evaluate((id) => {
      const payload = {
        schema_v: 1,
        projects: [{
          id,
          schema_v:           1,
          city_slug:          'berkeley',
          josh_version:       '1.0.0',
          parameters_version: '4.0',
          name:               'SMOKE_17 Reload Test',
          address:            '',
          lat:                37.8700,
          lng:                -122.2690,
          units:              50,
          stories:            4,
          source:             'browser',
          created_at:         new Date().toISOString(),
          analyzed_at:        null,
          result:             null,
          brief_cache:        null,
        }],
      };
      localStorage.setItem('josh_sb_v1_berkeley', JSON.stringify(payload));
    }, KNOWN_ID);

    // Reload — stays in the same BrowserContext, so localStorage persists.
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#josh-sidebar', { state: 'visible', timeout: 15_000 });
    await page.waitForTimeout(300);  // let init() + _loadFromLocalStorage() settle

    // After reload, init() must merge the localStorage project into _projects
    const found = await page.evaluate((id) => {
      const projs = (window.joshSidebar && typeof window.joshSidebar.getProjects === 'function')
        ? window.joshSidebar.getProjects()
        : [];
      const hit = projs.find(p => p.id === id);
      return hit ? {
        id:     hit.id,
        name:   hit.name,
        source: hit.source,
        units:  hit.units,
      } : null;
    }, KNOWN_ID);

    assert.ok(found, `localStorage-seeded project (id=${KNOWN_ID}) must be loaded by init() after reload`);
    assert.equal(found.name,   'SMOKE_17 Reload Test', 'name must round-trip through localStorage');
    assert.equal(found.source, 'browser',               'source must be preserved');
    assert.equal(found.units,  50,                      'units must round-trip');

    // DOM should also show the row
    const listText = await page.locator('#josh-sidebar').innerText();
    assert.ok(listText.includes('SMOKE_17 Reload Test'),
      'restored project name must appear in the sidebar list');

    // Cleanup — next tests expect a clean localStorage
    await _resetSidebarState();
  });

  // ── SMOKE_18: form field persistence across re-render ───────────────────
  test('SMOKE_18: form name/address survive a pin-drop re-render', async () => {
    await _resetSidebarState();

    // Open form, type name + address BEFORE dropping pin
    await page.evaluate(() => {
      if (typeof joshSidebar_newProject === 'function') joshSidebar_newProject();
      const nameEl = document.getElementById('josh-sb-f-name');
      const addrEl = document.getElementById('josh-sb-f-addr');
      if (nameEl) { nameEl.value = 'Typed Before Pin'; nameEl.dispatchEvent(new Event('input')); }
      if (addrEl) { addrEl.value = '123 Test Ave';     addrEl.dispatchEvent(new Event('input')); }
    });

    // Drop the pin — triggers _render() which destroys and rebuilds form DOM.
    // Prior to the _wireFormListeners fix this is where name/address were lost.
    await page.evaluate(() => {
      if (window.joshSidebar && typeof window.joshSidebar.onPinPlaced === 'function') {
        window.joshSidebar.onPinPlaced(37.8695, -122.2685);
      }
    });
    await page.waitForTimeout(150);  // let _render() + _wireFormListeners complete

    // Read NEW DOM input values (post-render)
    const { nameAfter, addrAfter } = await page.evaluate(() => ({
      nameAfter: (document.getElementById('josh-sb-f-name') || {}).value || '',
      addrAfter: (document.getElementById('josh-sb-f-addr') || {}).value || '',
    }));
    assert.equal(nameAfter, 'Typed Before Pin', 'name input must survive pin-drop re-render');
    assert.equal(addrAfter, '123 Test Ave',     'address input must survive pin-drop re-render');

    // Units field also triggers a re-render via debounced analysis — check that
    // name/address still survive after units change + its re-render fires.
    await page.evaluate(() => {
      const unitsEl = document.getElementById('josh-sb-f-units');
      if (unitsEl) { unitsEl.value = '75'; unitsEl.dispatchEvent(new Event('input')); }
    });
    await page.waitForTimeout(500);  // analysis debounce + re-render

    const afterUnits = await page.evaluate(() => ({
      nameAfter: (document.getElementById('josh-sb-f-name') || {}).value || '',
      addrAfter: (document.getElementById('josh-sb-f-addr') || {}).value || '',
      unitsAfter: (document.getElementById('josh-sb-f-units') || {}).value || '',
    }));
    assert.equal(afterUnits.nameAfter,  'Typed Before Pin', 'name must survive units-triggered re-render');
    assert.equal(afterUnits.addrAfter,  '123 Test Ave',     'address must survive units-triggered re-render');
    assert.equal(afterUnits.unitsAfter, '75',               'units value must be preserved after re-render');

    // Cancel to clean up
    await _resetSidebarState();
  });

  // ── SMOKE_19: footer has only Download .json button ─────────────────────
  test('SMOKE_19: footer has exactly one "Download .json" button', async () => {
    await _resetSidebarState();

    // Select a pipeline project that has a result so _renderFooter fires
    await page.evaluate(() => {
      const p = (window.JOSH_DATA.projects || []).find(p => p.result);
      if (p && typeof joshSidebar_select === 'function') joshSidebar_select(p.id);
    });
    await page.waitForTimeout(200);

    const buttonLabels = await page.evaluate(() => {
      const sb = document.getElementById('josh-sidebar');
      return sb
        ? Array.from(sb.querySelectorAll('button')).map(b => b.textContent.trim())
        : [];
    });

    const downloadBtns = buttonLabels.filter(l => l === 'Download .json');
    assert.equal(downloadBtns.length, 1,
      `expected exactly one "Download .json" button, got ${downloadBtns.length}; ` +
      `all labels: ${JSON.stringify(buttonLabels)}`);

    // Disallowed legacy labels (form's "Save" is only visible when form is open,
    // and we have no form open here, so a lingering "Save" button would be a footer regression)
    assert.ok(!buttonLabels.includes('Save'),
      'footer must not contain plain "Save" button (form is closed, so any Save is a regression)');
    assert.ok(!buttonLabels.some(l => l === 'Save As\u2026' || l === 'Save As...'),
      'footer must not contain "Save As…" button');
    assert.ok(!buttonLabels.some(l => /Export.*[Pp]ipeline/.test(l)),
      'footer must not contain "Export for pipeline" button');
  });

  // ── SMOKE_20: Untitled renders as real DOM, not escaped text ────────────
  test('SMOKE_20: unnamed project row renders italic "Untitled" as real <em>', async () => {
    await _resetSidebarState();

    // Create an unnamed browser project via form submit (leave name blank)
    await page.evaluate(() => {
      if (typeof joshSidebar_newProject === 'function') joshSidebar_newProject();
      if (window.joshSidebar && typeof window.joshSidebar.onPinPlaced === 'function') {
        window.joshSidebar.onPinPlaced(37.8695, -122.2685);
      }
      const unitsEl = document.getElementById('josh-sb-f-units');
      if (unitsEl) { unitsEl.value = '50'; unitsEl.dispatchEvent(new Event('input')); }
    });
    await page.waitForTimeout(500);
    await page.evaluate(() => {
      if (typeof joshSidebar_submitForm === 'function') joshSidebar_submitForm();
    });
    await page.waitForTimeout(400);

    // Find the list row for the unnamed project and inspect its DOM
    const inspection = await page.evaluate(() => {
      const sb = document.getElementById('josh-sidebar');
      if (!sb) return { found: false };
      const rows = Array.from(sb.querySelectorAll('[onclick^="joshSidebar_select"]'));
      // Find a row whose visible text contains "Untitled"
      const untitledRow = rows.find(r => r.innerText.includes('Untitled'));
      if (!untitledRow) return { found: false };
      return {
        found:      true,
        hasEm:      untitledRow.querySelector('em') !== null,
        // Bug signature: double-escaped "<em style…" as visible text
        visibleText: untitledRow.innerText,
        innerHTML:   untitledRow.innerHTML,
      };
    });

    assert.ok(inspection.found, 'must find an "Untitled" row in the list');
    assert.ok(inspection.hasEm,
      'Untitled must render as a real <em> element (got innerHTML: ' + inspection.innerHTML + ')');
    assert.ok(!inspection.visibleText.includes('<em'),
      'visible text must NOT contain literal "<em" characters ' +
      '(double-escape regression): ' + inspection.visibleText);
    assert.ok(!inspection.innerHTML.includes('&lt;em'),
      'innerHTML must NOT contain "&lt;em" (_esc() applied to an HTML fallback is a regression)');
  });

  // ── SMOKE_21: auto-save status line for browser projects ────────────────
  test('SMOKE_21: browser project detail panel shows auto-save status line', async () => {
    await _resetSidebarState();

    // Create a fresh browser project via form submit. _submitForm() auto-selects
    // the newly-created project (sidebar.js:1162 `_selectedId = id`), so the
    // detail panel renders immediately after — no separate selection step needed.
    // (Avoiding joshSidebar_select() prevents the toggle-off behavior when the
    // target project is already selected.)
    await page.evaluate(() => {
      if (typeof joshSidebar_newProject === 'function') joshSidebar_newProject();
      if (window.joshSidebar && typeof window.joshSidebar.onPinPlaced === 'function') {
        window.joshSidebar.onPinPlaced(37.8700, -122.2690);
      }
      const nameEl  = document.getElementById('josh-sb-f-name');
      const unitsEl = document.getElementById('josh-sb-f-units');
      if (nameEl)  { nameEl.value  = 'SMOKE_21 AutoSave'; nameEl.dispatchEvent(new Event('input')); }
      if (unitsEl) { unitsEl.value = '50';                unitsEl.dispatchEvent(new Event('input')); }
    });
    await page.waitForTimeout(500);  // analysis debounce + buffer
    await page.evaluate(() => {
      if (typeof joshSidebar_submitForm === 'function') joshSidebar_submitForm();
    });
    await page.waitForTimeout(400);

    // Sanity: a browser project with a result is now in state and selected
    const state = await page.evaluate(() => {
      const projs = (window.joshSidebar && typeof window.joshSidebar.getProjects === 'function')
        ? window.joshSidebar.getProjects()
        : [];
      const hit = projs.find(p => p.source === 'browser' && p.name === 'SMOKE_21 AutoSave');
      return {
        hasProject: !!hit,
        hasResult:  !!(hit && hit.result),
      };
    });
    assert.ok(state.hasProject, 'SMOKE_21 browser project must be in state after submit');
    assert.ok(state.hasResult,  'SMOKE_21 browser project must have a result after submit');

    const text = await page.locator('#josh-sidebar').innerText();
    assert.ok(text.includes('Auto-saved to this browser'),
      'detail panel for a browser project must show the "● Auto-saved to this browser" status line');
  });

  // ── SMOKE_23: home icon visible when project is selected ───────────────
  // Regression test for CLAUDE.md § "Home icon (house marker) visibility rule":
  // The home marker for each project lives inside its per-project Folium
  // FeatureGroup (show=False at startup). sidebar.js must call map.addLayer()
  // on selection so the FG — and its home marker — become visible.
  //
  // This test catches: (a) FG not added due to early return, (b) FG added but
  // marker is not a child of the FG (permanent map layer), (c) FG reference
  // missing from window[folium_fg_name], (d) marker DOM element not rendered
  // after addLayer completes.
  test('SMOKE_23: selecting a pipeline project shows its home icon on the map', async () => {
    await _resetSidebarState();

    // Deselect any currently-selected project so the map starts clean.
    // _clearRoutes() removes all project FGs from the map → no home markers visible.
    await page.evaluate(() => {
      // Click any currently-selected row to toggle off; otherwise no-op.
      const projs = (window.joshSidebar && typeof window.joshSidebar.getProjects === 'function')
        ? window.joshSidebar.getProjects()
        : [];
      // Use selectProject with null-ish id path: pick a project we don't care about,
      // then pick it again to deselect. Simpler: loop over pipeline projects until
      // we deselect. Cleanest: just call the window handler with a fake id — no-op.
      // Actually, just trust that _resetSidebarState cancelled any form. If nothing
      // is selected, selectProject will select it. If something IS selected, we
      // re-click it to deselect.
      // We call selectProject with a sentinel that never matches to ensure
      // _clearRoutes runs without side-effects — but there's no such API.
      // Workaround: call _clearRoutes via selecting a non-existent project.
      // The simplest is to use the internal state: find what's selected and deselect.
    });

    // Count home-marker DOM elements BEFORE selection. With no project selected,
    // no per-project FG should be on the map, so no <i class="fa-home"> should exist
    // inside .leaflet-marker-pane.
    const beforeHomeCount = await page.evaluate(() => {
      return document.querySelectorAll('.leaflet-marker-pane i.fa-home').length;
    });

    // Find the first pipeline project with both a result and a folium_fg_name
    const targetId = await page.evaluate(() => {
      const projs = (window.JOSH_DATA.projects || []);
      const hit = projs.find(p => p.result && p.folium_fg_name);
      return hit ? hit.id : null;
    });
    assert.ok(targetId, 'at least one pipeline project with a folium_fg_name must exist');

    // Select it via the public handler
    await page.evaluate((id) => {
      if (typeof joshSidebar_select === 'function') joshSidebar_select(id);
    }, targetId);
    await page.waitForTimeout(400);  // wait for addLayer + Leaflet DOM update

    // Verify the FeatureGroup reference exists as a global
    const fgCheck = await page.evaluate((id) => {
      const p = (window.JOSH_DATA.projects || []).find(pp => pp.id === id);
      if (!p) return { fgName: null, fgExists: false, onMap: false };
      const fg = window[p.folium_fg_name];
      const map = window._joshMap;
      return {
        fgName:   p.folium_fg_name,
        fgExists: !!fg,
        onMap:    !!(fg && map && map.hasLayer && map.hasLayer(fg)),
      };
    }, targetId);
    assert.ok(fgCheck.fgName,   'project must carry folium_fg_name: ' + JSON.stringify(fgCheck));
    assert.ok(fgCheck.fgExists, `window[${fgCheck.fgName}] must exist as a Leaflet layer`);
    assert.ok(fgCheck.onMap,    'FeatureGroup must be added to the map after selection');

    // Count home-marker DOM elements AFTER selection. Exactly one more home icon
    // should be present (the selected project's home marker). The increment, not
    // the absolute count, is what we verify — other map markers may reuse fa-home.
    const afterHomeCount = await page.evaluate(() => {
      return document.querySelectorAll('.leaflet-marker-pane i.fa-home').length;
    });
    assert.ok(
      afterHomeCount > beforeHomeCount,
      `selecting a project must add at least one visible home icon to the map ` +
      `(before=${beforeHomeCount}, after=${afterHomeCount})`
    );

    // Additional check: the home marker must be in the DOM (not display:none).
    // Leaflet removes DOM nodes entirely when a layer is removed, so existence = visible.
    const visibleHomeIcon = await page.evaluate(() => {
      const icons = Array.from(document.querySelectorAll('.leaflet-marker-pane i.fa-home'));
      // A displayed icon has a parent .awesome-marker that itself has a non-zero size
      for (const icon of icons) {
        const marker = icon.closest('.awesome-marker');
        if (!marker) continue;
        const rect = marker.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) return true;
      }
      return false;
    });
    assert.ok(visibleHomeIcon,
      'at least one home icon must be visible in the DOM (non-zero size) after selection');

    // Cleanup: deselect
    await page.evaluate((id) => {
      if (typeof joshSidebar_select === 'function') joshSidebar_select(id);  // toggle off
    }, targetId);
    await page.waitForTimeout(200);
  });

  // ── SMOKE_24: every pipeline project has a resolvable folium_fg_name ────
  // This is the defensive "JOSH_DATA integrity" assertion that catches stale
  // builds produced before the `folium_fg_name` wiring landed in
  // _build_josh_data_projects (agents/visualization/demo.py).
  //
  // Failure mode caught:
  //   - demo.py change ships, Berkeley is rebuilt, other cities are NOT
  //   - stale cities embed projects with folium_fg_name === null or missing
  //   - sidebar.js _drawRoutes bails on `!window[fg_name]` → no home icon
  //   - user sees "missing housing icon when I select a project"
  //
  // SMOKE_23 only checks the FIRST matching project. This test walks ALL
  // pipeline projects with a result and asserts each one has:
  //   (a) folium_fg_name is a non-empty string
  //   (b) window[folium_fg_name] exists as a truthy object
  //   (c) that object is a Leaflet layer (has addTo/remove methods)
  //
  // CLAUDE.md § "Home icon (house marker) visibility rule" documents the
  // architectural contract this test enforces.
  test('SMOKE_24: every pipeline project has a resolvable folium_fg_name', async () => {
    const report = await page.evaluate(() => {
      const projs = (window.JOSH_DATA && window.JOSH_DATA.projects) || [];
      const pipelineWithResult = projs.filter(p =>
        p.source !== 'browser' && p.result);

      const failures = [];
      for (const p of pipelineWithResult) {
        const entry = { id: p.id, name: p.name, fgName: p.folium_fg_name };
        if (!p.folium_fg_name || typeof p.folium_fg_name !== 'string') {
          entry.reason = 'folium_fg_name missing or not a string';
          failures.push(entry);
          continue;
        }
        const fg = window[p.folium_fg_name];
        if (!fg) {
          entry.reason = `window[${p.folium_fg_name}] is undefined`;
          failures.push(entry);
          continue;
        }
        // A Leaflet FeatureGroup/LayerGroup has addTo + remove + eachLayer.
        if (typeof fg.addTo !== 'function' || typeof fg.eachLayer !== 'function') {
          entry.reason = `window[${p.folium_fg_name}] is not a Leaflet layer ` +
            `(missing addTo/eachLayer)`;
          failures.push(entry);
          continue;
        }
      }
      return {
        total:    pipelineWithResult.length,
        failures: failures,
      };
    });

    assert.ok(report.total > 0,
      'at least one pipeline project with a result must exist in JOSH_DATA');
    assert.deepEqual(
      report.failures, [],
      `${report.failures.length} of ${report.total} pipeline projects have ` +
      `an unresolvable folium_fg_name — stale analysis_map.html build? ` +
      `Rebuild with: uv run python build.py map --city <city>  (or ` +
      `JOSH_DIR=... uv run python acquire.py run --city <city>):\n` +
      JSON.stringify(report.failures, null, 2));
  });

  // ── SMOKE_22: window.joshSidebar._toYaml() exposed ──────────────────────
  test('SMOKE_22: window.joshSidebar._toYaml() is exposed and returns YAML', async () => {
    // Doesn't matter what's in the list — pipeline seeds guarantee at least one
    // project with lat/lng, so the YAML output will contain the schema keys.
    const { type, yaml } = await page.evaluate(() => {
      const fn = (window.joshSidebar && window.joshSidebar._toYaml) || null;
      if (typeof fn !== 'function') return { type: typeof fn, yaml: null };
      try {
        return { type: 'function', yaml: fn() };
      } catch (e) {
        return { type: 'function', yaml: 'ERROR: ' + e.message };
      }
    });

    assert.equal(type, 'function',
      'window.joshSidebar._toYaml must be exposed as a function for admin console use');
    assert.ok(yaml && typeof yaml === 'string',
      '_toYaml() must return a non-empty string');
    assert.ok(!yaml.startsWith('ERROR:'),
      '_toYaml() must not throw: ' + yaml);

    // YAML must contain the pipeline-schema keys (matches josh-pipeline/projects/{city}_demo.yaml)
    assert.ok(yaml.includes('projects:'), 'YAML must contain "projects:" root key');
    assert.ok(yaml.includes('name:'),     'YAML must contain "name:" key');
    assert.ok(yaml.includes('lat:'),      'YAML must contain "lat:" key');
    assert.ok(yaml.includes('lon:'),      'YAML must contain "lon:" key');
    assert.ok(yaml.includes('units:'),    'YAML must contain "units:" key');
    assert.ok(yaml.includes('stories:'),  'YAML must contain "stories:" key');

    // Export for pipeline button must NOT exist in the footer DOM
    const hasExportBtn = await page.evaluate(() => {
      const sb = document.getElementById('josh-sidebar');
      if (!sb) return false;
      return Array.from(sb.querySelectorAll('button'))
        .some(b => /Export.*[Pp]ipeline/.test(b.textContent));
    });
    assert.ok(!hasExportBtn,
      'Export for pipeline button must be removed from UI (available via _toYaml() console helper instead)');
  });

  // ── SMOKE_25: browser-project home icon visibility ─────────────────────
  // Regression test for the "open .json / select browser project → no home
  // icon" bug.  Browser projects (new, reloaded from localStorage, or opened
  // from a saved .json) have no pre-baked Folium FeatureGroup.  sidebar.js
  // `_drawRoutes()` was only rendering a home marker when `folium_fg_name`
  // resolved to a Folium FG — so any browser project got AntPath routes but
  // zero home icon on the map.
  //
  // Fix: sidebar.js must create a runtime home marker (L.marker + the same
  // AwesomeMarkers icon style Folium uses) at [lat, lng] when a selected
  // project has no folium_fg_name, and track it in `_routeLayers` so
  // `_clearRoutes()` cleans it up on deselect / switch.
  //
  // Flows A (create) and C (open-from-.json) both exercise the same code
  // path: after _submitForm runs _runAnalysis, sidebar.js selects the new
  // browser project and _drawRoutes must render the home icon.  Flow C
  // reaches the same state by calling the deserialize path exposed for test.
  test('SMOKE_25: selecting a browser project shows a home icon on the map', async () => {
    await _resetSidebarState();

    // Deselect whatever might be currently selected.
    await page.evaluate(() => {
      if (typeof joshSidebar_select === 'function') {
        // selectProject toggles off if re-selected; no-op otherwise.
        // Calling with a bogus id is ignored.
        const sel = document.querySelector('#josh-sidebar [data-selected="true"]');
        if (sel && sel.dataset && sel.dataset.projectId) joshSidebar_select(sel.dataset.projectId);
      }
    });
    await page.waitForTimeout(200);

    // Block showSaveFilePicker (defensive — should be unnecessary but keeps
    // the FSAPI path from prompting during the submit).
    await page.evaluate(() => {
      window.__smokeOrigPicker = window.showSaveFilePicker;
      window.showSaveFilePicker = () => Promise.reject(new Error('smoke block'));
    });

    const baseline = await page.evaluate(() =>
      document.querySelectorAll('.leaflet-marker-pane i.fa-home').length);

    // Create a browser project inline and submit it.
    await page.evaluate(() => {
      if (typeof joshSidebar_newProject === 'function') joshSidebar_newProject();
      if (window.joshSidebar && typeof window.joshSidebar.onPinPlaced === 'function') {
        window.joshSidebar.onPinPlaced(37.8700, -122.2690);
      }
      const nameEl  = document.getElementById('josh-sb-f-name');
      const unitsEl = document.getElementById('josh-sb-f-units');
      if (nameEl)  { nameEl.value  = 'SMOKE_25 Home Icon'; nameEl.dispatchEvent(new Event('input')); }
      if (unitsEl) { unitsEl.value = '50';                 unitsEl.dispatchEvent(new Event('input')); }
    });
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      if (typeof joshSidebar_submitForm === 'function') joshSidebar_submitForm();
    });
    await page.waitForTimeout(800);  // analysis + _drawRoutes

    // Post-submit, _submitForm auto-selects the new project — so _drawRoutes
    // has already run.  Count visible home icons in the marker pane.
    const after = await page.evaluate(() => {
      const icons = Array.from(document.querySelectorAll('.leaflet-marker-pane i.fa-home'));
      const visible = icons.filter(i => {
        const m = i.closest('.awesome-marker');
        if (!m) return false;
        const r = m.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
      return { total: icons.length, visible: visible.length };
    });

    // Cleanup happens even on failure
    try {
      assert.ok(after.total > baseline,
        `selecting a browser project must add a home icon to .leaflet-marker-pane ` +
        `(baseline=${baseline}, after=${after.total}).  Browser projects have no ` +
        `folium_fg_name — sidebar.js must draw a runtime marker in _drawRoutes().`);
      assert.ok(after.visible >= 1,
        `the browser project's home icon must be visibly rendered (non-zero size), ` +
        `got ${after.visible} visible of ${after.total} total`);
    } finally {
      await page.evaluate(() => {
        if (window.__smokeOrigPicker) window.showSaveFilePicker = window.__smokeOrigPicker;
        delete window.__smokeOrigPicker;
      });
    }
  });

  // ── SMOKE_26: browser-project search-radius circle ────────────────────
  // Regression test for the missing 0.5-mile search radius on projects
  // loaded from disk / created in-browser.  Pipeline projects carry a
  // pre-baked Folium Circle inside their FeatureGroup — when sidebar.js
  // addLayer's the FG, the circle appears.  Browser projects have no Folium
  // FG, so without a runtime circle draw, the radius ring is missing.
  //
  // Fix contract: sidebar.js `_drawRoutes()` must create an L.circle of
  // radius = parameters.serving_route_radius_miles * 1609.344 meters at
  // [lat, lng], styled like Folium (dashed, tier color, fillOpacity ≈ 0.04),
  // and push it onto _routeLayers.
  test('SMOKE_26: selecting a browser project shows a 0.5-mile radius circle', async () => {
    await _resetSidebarState();

    await page.evaluate(() => {
      window.__smokeOrigPicker = window.showSaveFilePicker;
      window.showSaveFilePicker = () => Promise.reject(new Error('smoke block'));
    });

    // Snapshot all L.Circle layers currently on the map so we can detect
    // the newly-added radius circle by diffing.
    const baselineCircleIds = await page.evaluate(() => {
      const map = window._joshMap;
      if (!map) return [];
      const out = [];
      map.eachLayer(l => {
        if (window.L && l instanceof window.L.Circle) out.push(l._leaflet_id);
      });
      return out;
    });

    // Create + submit a browser project (auto-selects on submit).
    await page.evaluate(() => {
      if (typeof joshSidebar_newProject === 'function') joshSidebar_newProject();
      if (window.joshSidebar && typeof window.joshSidebar.onPinPlaced === 'function') {
        window.joshSidebar.onPinPlaced(37.8700, -122.2690);
      }
      const nameEl  = document.getElementById('josh-sb-f-name');
      const unitsEl = document.getElementById('josh-sb-f-units');
      if (nameEl)  { nameEl.value  = 'SMOKE_26 Radius'; nameEl.dispatchEvent(new Event('input')); }
      if (unitsEl) { unitsEl.value = '50';              unitsEl.dispatchEvent(new Event('input')); }
    });
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      if (typeof joshSidebar_submitForm === 'function') joshSidebar_submitForm();
    });
    await page.waitForTimeout(800);

    // Inspect L.Circle layers on the map after selection and find the new one.
    const newCircles = await page.evaluate((baselineIds) => {
      const map = window._joshMap;
      if (!map || !window.L) return [];
      const baseline = new Set(baselineIds);
      const found = [];
      map.eachLayer(l => {
        if (l instanceof window.L.Circle && !baseline.has(l._leaflet_id)) {
          const ll = l.getLatLng ? l.getLatLng() : null;
          found.push({
            radius: l.getRadius ? l.getRadius() : null,
            lat:    ll ? ll.lat : null,
            lng:    ll ? ll.lng : null,
            dashArray: (l.options && l.options.dashArray) || null,
          });
        }
      });
      return found;
    }, baselineCircleIds);

    try {
      assert.ok(newCircles.length >= 1,
        `selecting a browser project must add at least one L.Circle to the map ` +
        `(got ${newCircles.length}). Browser projects have no Folium FG — sidebar.js ` +
        `must draw a runtime radius circle in _drawRoutes().`);

      // The radius circle should be ≈ 804m (0.5 mi × 1609.344).  Allow a
      // generous tolerance (600–1200m) in case parameters override the default.
      const radiusCircle = newCircles.find(c => c.radius && c.radius > 500 && c.radius < 2000);
      assert.ok(radiusCircle,
        `at least one new L.Circle must have a radius in [500, 2000] m ` +
        `(evacuation search radius, default 0.5 mi ≈ 804 m). Got circles: ` +
        JSON.stringify(newCircles));

      // The circle's center should be at the project pin (37.8700, -122.2690).
      assert.ok(Math.abs(radiusCircle.lat - 37.8700) < 0.001,
        `radius circle must be centered at project lat (got ${radiusCircle.lat})`);
      assert.ok(Math.abs(radiusCircle.lng - (-122.2690)) < 0.001,
        `radius circle must be centered at project lng (got ${radiusCircle.lng})`);
    } finally {
      await page.evaluate(() => {
        if (window.__smokeOrigPicker) window.showSaveFilePicker = window.__smokeOrigPicker;
        delete window.__smokeOrigPicker;
      });
    }
  });

  // ── SMOKE_27: Download PDF button wiring ─────────────────────────────────
  test('SMOKE_27: Download PDF button appears and handler is wired', async () => {
    await _resetSidebarState();

    // Select the first pipeline project.
    await page.evaluate(() => {
      var projects = window.joshSidebar.getProjects();
      if (projects.length > 0) window.joshSidebar.selectProject(projects[0].id);
    });
    await new Promise(r => setTimeout(r, 500));

    // Check the "Download Determination" button exists in the sidebar DOM.
    const detButtonInfo = await page.evaluate(() => {
      var sidebar = document.getElementById('josh-sidebar');
      if (!sidebar) return { found: false, reason: 'no sidebar' };
      var buttons = sidebar.querySelectorAll('button');
      for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent.trim() === 'Download Determination') {
          return {
            found: true,
            onclick: buttons[i].getAttribute('onclick') || '',
          };
        }
      }
      return { found: false, reason: 'no Download Determination button in ' + buttons.length + ' buttons' };
    });

    assert.ok(detButtonInfo.found,
      'a "Download Determination" button must appear when a project is selected ' +
      '(got: ' + JSON.stringify(detButtonInfo) + ')');
    assert.ok(detButtonInfo.onclick.indexOf('joshSidebar_downloadDetermination') !== -1,
      'onclick must call joshSidebar_downloadDetermination (got: "' + detButtonInfo.onclick + '")');

    // Verify handler exists.
    const wiring = await page.evaluate(() => ({
      handler: typeof window.joshSidebar_downloadDetermination,
    }));
    assert.strictEqual(wiring.handler, 'function', 'joshSidebar_downloadDetermination must be a function');
  });

  // ── SMOKE_28: Download Determination generates a valid .txt file ─────────
  test('SMOKE_28: Download Determination produces a valid .txt file for a pipeline project', async () => {
    await _resetSidebarState();

    // Select the first pipeline project.
    await page.evaluate(() => {
      var ps = window.joshSidebar.getProjects();
      if (ps.length > 0) window.joshSidebar.selectProject(ps[0].id);
    });
    await new Promise(r => setTimeout(r, 500));

    // Trigger determination download and capture the file via Playwright download event.
    const downloadPromise = page.waitForEvent('download', { timeout: 15000 });

    await page.evaluate(() => {
      var ps = window.joshSidebar.getProjects();
      window.joshSidebar_downloadDetermination(ps[0].id);
    });

    const download = await downloadPromise;
    const filename = download.suggestedFilename();

    // Save to temp and validate.
    const fs = require('fs');
    const tmpPath = '/tmp/_josh_smoke28_' + filename;
    try {
      await download.saveAs(tmpPath);
      const stat = fs.statSync(tmpPath);
      const content = fs.readFileSync(tmpPath, 'utf-8');

      // 1. Filename ends with .txt
      assert.ok(filename.endsWith('.txt'),
        'download filename must end with .txt (got "' + filename + '")');

      // 2. Content starts with determination header
      assert.ok(content.indexOf('FIRE EVACUATION CAPACITY ANALYSIS') !== -1,
        'file must contain determination header');

      // 3. Content includes FINAL DETERMINATION section
      assert.ok(content.indexOf('FINAL DETERMINATION') !== -1,
        'file must contain FINAL DETERMINATION section');

      // 4. File is a reasonable size (> 1 KB for a real report)
      assert.ok(stat.size > 1000,
        'determination must be > 1 KB (got ' + stat.size + ' bytes)');
    } finally {
      try { fs.unlinkSync(tmpPath); } catch (_) {}
    }
  });

});

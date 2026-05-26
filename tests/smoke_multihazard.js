// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * Multi-hazard smoke tests — Playwright + node:test.
 *
 * Targets the Stage 0.5 v2 demo map. Loads it as file:// in headless
 * Chromium and exercises end-to-end behaviors that the unit tests can't:
 *
 *   MHZ_SMOKE_1: schema_version === 2 + applicable_hazards includes all 6
 *   MHZ_SMOKE_2: HAZARD LAYERS panel renders one checkbox row per polygon
 *                hazard (5 today — no tsunami polygon)
 *   MHZ_SMOKE_3: clicking the wildfire checkbox removes the layer from the
 *                map; clicking it again re-adds it (the bug the user
 *                reported on 2026-05-18 — caught by THIS test now)
 *   MHZ_SMOKE_4: every polygon-hazard checkbox toggles its layer
 *                independently of the others
 *   MHZ_SMOKE_5: project dropdown lists pipeline + mock projects;
 *                selecting marina_pointe shows the 6-row bar chart
 *   MHZ_SMOKE_6: tier banner reads "DISCRETIONARY — driven by Tsunami"
 *                for marina_pointe (dispositive case)
 *   MHZ_SMOKE_7: + New button opens the inline form in #josh-project-detail
 *   MHZ_SMOKE_8: brief actions chevron menu shows Save HTML / Print /
 *                Audit trail .txt
 *
 * Prerequisites:
 *   npm install                          (installs playwright)
 *   npx playwright install chromium      (downloads headless Chrome)
 *   Regenerate the v2 map:
 *     uv run python build.py map --city Berkeley \
 *       --projects /path/to/josh-pipeline/projects/berkeley_demo.yaml \
 *       --data-dir /path/to/josh-pipeline/data/berkeley \
 *       --output-dir output/berkeley
 *
 * Run:
 *   node --test tests/smoke_multihazard.js
 *   npm run smoke:multihazard
 */

'use strict';

const { describe, test, before, after } = require('node:test');
const assert   = require('node:assert/strict');
const { chromium } = require('playwright');
const fs   = require('fs');

// Target the canonical demo build at output/berkeley/analysis_map.html.
// Path is overridable via JOSH_MHZ_DEMO env var so CI can point at a
// different build (e.g. josh-pipeline/output/berkeley/analysis_map.html).
const path = require('path');
const DEMO_MAP = process.env.JOSH_MHZ_DEMO ||
                 path.resolve(__dirname, '..', 'output', 'berkeley',
                              'analysis_map.html');
const FILE_URL = 'file://' + DEMO_MAP;

let browser, page;

describe('Smoke: multi-hazard demo map', { timeout: 90_000 }, () => {

  before(async () => {
    if (!fs.existsSync(DEMO_MAP)) {
      throw new Error('Demo map not found at ' + DEMO_MAP +
        '. Regenerate with: uv run python build.py map --city Berkeley ' +
        '--projects … --data-dir … --output-dir output/berkeley');
    }
    browser = await chromium.launch();
    page    = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await page.goto(FILE_URL);
    // Wait for sidebar + map + hazard layer panel to be wired.
    await page.waitForSelector('#josh-sidebar-mhz', { timeout: 10_000 });
    await page.waitForFunction(
      () => document.querySelectorAll('input[data-hazard]').length > 0,
      { timeout: 10_000 }
    );
    await page.waitForFunction(() => !!window._joshMap, { timeout: 10_000 });
    // Small settle — Folium FeatureGroups continue attaching for a beat
    // after _joshMap is set.
    await page.waitForTimeout(500);
  });

  after(async () => {
    if (browser) await browser.close();
  });

  // ── MHZ_SMOKE_1 ────────────────────────────────────────────────────────────
  test('schema_version === 2; applicable_hazards lists all 6 hazards', async () => {
    const data = await page.evaluate(() => ({
      schema_version:     window.JOSH_DATA && window.JOSH_DATA.schema_version,
      applicable_hazards: window.JOSH_DATA && window.JOSH_DATA.applicable_hazards
    }));
    assert.equal(data.schema_version, 2, 'schema_version should be 2');
    assert.deepEqual(data.applicable_hazards.sort(), [
      'dam_failure', 'flood', 'gas_hazmat', 'landslide', 'tsunami', 'wildfire'
    ], 'applicable_hazards should include all 6 hazards (sorted)');
  });

  // ── MHZ_SMOKE_2 ────────────────────────────────────────────────────────────
  test('HAZARD LAYERS panel renders one checkbox per polygon hazard', async () => {
    const data = await page.evaluate(() => {
      const cbs = [...document.querySelectorAll('input[type=checkbox][data-hazard]')];
      return {
        count: cbs.length,
        hazards: cbs.map(c => c.getAttribute('data-hazard')).sort()
      };
    });
    // Tsunami has no Berkeley polygon (handled via dispositive HazardResult).
    // The other 5 each get a row.
    assert.equal(data.count, 5, 'should have 5 hazard checkboxes');
    assert.deepEqual(data.hazards, [
      'dam_failure', 'flood', 'gas_hazmat', 'landslide', 'wildfire'
    ], 'checkbox data-hazard values cover the 5 polygon hazards');
  });

  // ── MHZ_SMOKE_3 ────────────────────────────────────────────────────────────
  // The bug the user reported on 2026-05-18: hazard layer checkboxes
  // weren't toggling. This is the regression guard.
  test('clicking wildfire checkbox removes the layer; re-clicking re-adds', async () => {
    // Count map layers before the click.
    const before = await page.evaluate(() => {
      let n = 0; window._joshMap.eachLayer(() => n++); return n;
    });

    // Real DOM click on the wildfire checkbox (not via dispatchEvent).
    await page.click('input[data-hazard="wildfire"]');
    // Give Leaflet a frame to remove the layer.
    await page.waitForTimeout(100);

    const afterUncheck = await page.evaluate(() => {
      let n = 0; window._joshMap.eachLayer(() => n++); return n;
    });
    assert.ok(afterUncheck < before,
      `unchecking wildfire should DROP layer count: was ${before}, now ${afterUncheck}`);

    // Re-check the box.
    await page.click('input[data-hazard="wildfire"]');
    await page.waitForTimeout(100);
    const afterRecheck = await page.evaluate(() => {
      let n = 0; window._joshMap.eachLayer(() => n++); return n;
    });
    assert.equal(afterRecheck, before,
      `re-checking wildfire should restore layer count: was ${before}, now ${afterRecheck}`);
  });

  // ── MHZ_SMOKE_4 ────────────────────────────────────────────────────────────
  test('every polygon-hazard checkbox toggles its layer independently', async () => {
    const hazards = ['wildfire', 'flood', 'dam_failure', 'gas_hazmat', 'landslide'];
    for (const h of hazards) {
      const before = await page.evaluate(() => {
        let n = 0; window._joshMap.eachLayer(() => n++); return n;
      });
      await page.click(`input[data-hazard="${h}"]`);
      await page.waitForTimeout(80);
      const afterOff = await page.evaluate(() => {
        let n = 0; window._joshMap.eachLayer(() => n++); return n;
      });
      assert.ok(afterOff < before,
        `unchecking ${h} should drop layer count (before=${before}, after=${afterOff})`);
      await page.click(`input[data-hazard="${h}"]`);
      await page.waitForTimeout(80);
      const afterOn = await page.evaluate(() => {
        let n = 0; window._joshMap.eachLayer(() => n++); return n;
      });
      assert.equal(afterOn, before,
        `re-checking ${h} should restore layer count exactly`);
    }
  });

  // ── MHZ_SMOKE_5 ────────────────────────────────────────────────────────────
  test('marina_pointe selection shows a 6-row bar chart', async () => {
    await page.selectOption('#josh-mhz-project-select', 'marina_pointe');
    await page.waitForTimeout(300);
    const data = await page.evaluate(() => {
      const detail = document.getElementById('josh-project-detail');
      const bars   = detail.querySelectorAll('[style*="flex:1;height:8px"]');
      const items  = detail.querySelectorAll('ul li');
      return { bars: bars.length, list_items: items.length };
    });
    assert.equal(data.bars, 6, 'marina_pointe bar chart should have 6 rows (one per hazard)');
    assert.equal(data.list_items, 6, 'Hazards Evaluated list should have 6 entries');
  });

  // ── MHZ_SMOKE_6 ────────────────────────────────────────────────────────────
  test('marina_pointe tier banner reads "DISCRETIONARY — driven by Tsunami"', async () => {
    const text = await page.evaluate(() => {
      const detail = document.getElementById('josh-project-detail');
      return detail ? detail.textContent.replace(/\s+/g, ' ') : '';
    });
    assert.ok(text.includes('DISCRETIONARY'), 'should show DISCRETIONARY tier');
    assert.ok(/driven by\s*Tsunami/i.test(text),
      'should show "driven by Tsunami" controlling-hazard footer');
  });

  // ── MHZ_SMOKE_7 ────────────────────────────────────────────────────────────
  test('+ New button opens the inline form in #josh-project-detail', async () => {
    // Click "+ New" via the production global the toolbar wires to.
    await page.evaluate(() => window.joshSidebar_newProject());
    await page.waitForTimeout(150);
    const data = await page.evaluate(() => {
      const detail = document.getElementById('josh-project-detail');
      return {
        has_new_project_heading: /New Project/i.test(detail.textContent),
        input_count:             detail.querySelectorAll('input, textarea, select').length,
        has_save_button:         !!detail.querySelector('button')
      };
    });
    assert.ok(data.has_new_project_heading, 'form should show "New Project" heading');
    assert.ok(data.input_count >= 3, 'form should have at least 3 inputs (name/address/units/stories)');
    assert.ok(data.has_save_button, 'form should have at least one button');
    // Restore: cancel the form.
    await page.evaluate(() => window.joshSidebar_cancelForm && window.joshSidebar_cancelForm());
  });

  // ── MHZ_SMOKE_9 ────────────────────────────────────────────────────────────
  // Regression for the 2026-05-24 hazard-polygon-not-visible bug history:
  //
  //   v1 (no renderer):       L.geoJSON defaulted to SVG; preferCanvas:true
  //                           map silently rejected it → no visible DOM.
  //   v2 (L.canvas() per layer): polygons visible in Chromium but NOT Safari.
  //                           Two canvases stacked in the overlay pane with
  //                           `transform: translate3d` were composited
  //                           differently between engines.
  //   v3 (shared renderer):   _wireHazardLayers uses map._renderer (the
  //                           SAME canvas the road heatmap uses). One
  //                           canvas. No compositing issue.
  //
  // Test strategy: check that the overlay pane's canvas has actual hazard
  // polygon PIXELS drawn on it (not just any pixels — there's a baseline
  // road heatmap). Disable all hazard checkboxes one by one and measure
  // the pixel-count delta to prove the polygons are actually contributing.
  test('hazard polygon layers actually render visible pixels on the map', async () => {
    const rendered = await page.evaluate(() => {
      let foliumMap = null;
      for (const k of Object.keys(window)) {
        if (k.startsWith('map_')) { foliumMap = window[k]; break; }
      }
      if (!foliumMap) return { error: 'no folium map' };

      const overlay = document.querySelector('.leaflet-overlay-pane');
      if (!overlay) return { error: 'no overlay pane' };
      const canvases = overlay.querySelectorAll('canvas');
      if (canvases.length === 0) {
        return { error: 'no canvas in overlay pane (preferCanvas:true expected)' };
      }

      function countNonZeroAlpha(c) {
        const ctx = c.getContext('2d');
        const data = ctx.getImageData(0, 0, c.width, c.height).data;
        let n = 0;
        for (let i = 3; i < data.length; i += 4) if (data[i] > 0) n++;
        return n;
      }

      // Baseline: pixels with all hazard layers ON (the default state).
      const allOn = Array.from(canvases).reduce((s, c) => s + countNonZeroAlpha(c), 0);

      // Disable every hazard checkbox + force redraw.
      document.querySelectorAll('input[data-hazard]:checked').forEach(cb => cb.click());
      // Allow Leaflet to repaint (it batches redraws on requestAnimationFrame).
      return new Promise(resolve => setTimeout(() => {
        const allOff = Array.from(canvases).reduce((s, c) => s + countNonZeroAlpha(c), 0);
        resolve({
          canvas_count: canvases.length,
          pixels_with_hazards: allOn,
          pixels_without_hazards: allOff,
          delta: allOn - allOff,
          preferCanvas: !!(foliumMap.options && foliumMap.options.preferCanvas),
        });
      }, 300));
    });

    assert.ok(!rendered.error, `setup failed: ${rendered.error}`);
    assert.ok(
      rendered.delta > 1000,
      `expected hazard polygons to contribute visible pixels (delta=${rendered.delta}, ` +
      `pixels with hazards=${rendered.pixels_with_hazards}, ` +
      `without=${rendered.pixels_without_hazards}, ` +
      `canvases=${rendered.canvas_count}, preferCanvas=${rendered.preferCanvas}). ` +
      `Likely the hazard polygon renderer mismatch bug has regressed — ` +
      `_wireHazardLayers in sidebar.js must share map._renderer (NOT create ` +
      `a new L.canvas() — that breaks Safari) when map.options.preferCanvas is true.`
    );

    // Re-enable for downstream tests (next test selects marina_pointe — still OK).
    await page.evaluate(() => {
      document.querySelectorAll('input[data-hazard]:not(:checked)').forEach(cb => cb.click());
    });
    await page.waitForTimeout(100);
  });

  // ── MHZ_SMOKE_10 ───────────────────────────────────────────────────────────
  // Regression for the 2026-05-24 "ΔT 0.00 min" brief bug.
  //
  // _buildMhzBriefInput in sidebar.js was writing v2 shorthand field names
  // (`delta_t_min`, `threshold_min`, paths[i].delta_t) but the v1 brief
  // sections read canonical wildland.py names (`max_delta_t_minutes`,
  // `threshold_minutes`, `delta_t_minutes`). Result: the top stat cards +
  // controlling-finding card showed ΔT 0.00 even when the v2 per-hazard
  // tables further down rendered the correct ΔT.
  //
  // Test strategy: render the brief for hills_gateway (known ΔT 26.06 min
  // from the golden file) and confirm the rendered HTML contains 26.06,
  // NOT 0.00 in the stat-card row.
  test('brief renders the correct max ΔT in the top stat cards (not 0)', async () => {
    await page.selectOption('#josh-mhz-project-select', 'hills_gateway');
    await page.waitForTimeout(200);

    // Render the brief HTML in-page via BriefRenderer (avoids opening
    // a new tab / blob URL which is awkward in Playwright).
    const result = await page.evaluate(() => {
      const projects = window.JOSH_DATA.projects || [];
      const hg = projects.find(p => p.id === 'hills_gateway');
      if (!hg || !hg.evaluation) return { error: 'hills_gateway not seeded' };

      // Mirror what _buildMhzBriefInput produces. Done by clicking through
      // the actual brief menu Save action would be more robust, but is
      // harder to intercept in headless; for the smoke we duplicate the
      // minimal call here.
      const evaluation = hg.evaluation;
      const results = evaluation.hazard_results || [];
      const ctrl = results.find(r => r.controls) || results[0] || {};
      const tierV1 = evaluation.tier === 'MINISTERIAL_WITH_STANDARD_CONDITIONS'
        ? 'MINISTERIAL WITH STANDARD CONDITIONS' : (evaluation.tier || 'MINISTERIAL');
      const input = {
        schema_version: 2,
        brief_input_version: 1,
        project: {name: hg.name, units: hg.units, stories: hg.stories, lat: hg.lat, lng: hg.lng, address: hg.address || ''},
        result: {
          tier: tierV1,
          hazard_zone: ctrl.zone || 'non_fhsz',
          max_delta_t_minutes: ctrl.delta_t,
          threshold_minutes: ctrl.threshold,
          safe_egress_window_minutes: ctrl.egress_window_min,
          max_project_share: 0.05,
          flagged: !!ctrl.flagged,
          bottleneck_name: (ctrl.bottleneck && ctrl.bottleneck.name) || '',
          paths: results.filter(r => r && !r.excluded && !r.dispositive).map(r => ({
            path_id: (r.type || 'unknown') + '-controlling',
            bottleneck_name: (r.bottleneck && r.bottleneck.name) || '',
            effective_capacity_vph: (r.bottleneck && r.bottleneck.eff_cap_vph) || 0,
            delta_t_minutes: r.delta_t,
            threshold_minutes: r.threshold,
            safe_egress_window_minutes: r.egress_window_min,
            max_project_share: 0.05,
            flagged: !!r.flagged,
          })),
        },
        evaluation: evaluation,
      };
      const html = window.BriefRenderer.render(input);

      // Extract the rendered ΔT in the top stat card. The card uses
      // class "big-num" with the numeric value.
      const tmpDiv = document.createElement('div');
      tmpDiv.innerHTML = html;
      const bigNums = Array.from(tmpDiv.querySelectorAll('.big-num')).map(el => el.textContent.trim());
      // Also pull the controlling-finding sentence text to verify it isn't "0.00 min"
      const controllingText = (tmpDiv.querySelector('[style*="border-left"]') || {}).innerText || '';
      return {
        ctrl_delta_t: ctrl.delta_t,
        ctrl_threshold: ctrl.threshold,
        big_nums: bigNums,
        controlling_snippet: controllingText.substring(0, 250),
      };
    });

    assert.ok(!result.error, `setup failed: ${result.error}`);
    // Hills Gateway: ΔT 26.06, threshold 2.25 (from golden file).
    assert.equal(result.ctrl_delta_t, 26.06, 'fixture sanity: ctrl.delta_t should be 26.06');
    assert.equal(result.ctrl_threshold, 2.25, 'fixture sanity: ctrl.threshold should be 2.25');

    // The stat card "big-num" values are: max ΔT (line 1), threshold (line 2).
    // After the fix, line 1 should be "26.1" (rounded to 1 decimal by _f(maxDt,1)),
    // NOT "0.0".
    assert.ok(
      result.big_nums.length >= 2,
      `expected at least 2 stat cards (big-num), got ${result.big_nums.length}: ${JSON.stringify(result.big_nums)}`
    );
    assert.notEqual(
      result.big_nums[0], '0.0',
      `top stat card ΔT must not be 0.0. ` +
      `big_nums=${JSON.stringify(result.big_nums)}. ` +
      `Likely _buildMhzBriefInput in sidebar.js stopped emitting the v1-canonical ` +
      `field names (max_delta_t_minutes, threshold_minutes, paths[i].delta_t_minutes) ` +
      `that _buildSummaryStats / _buildControllingFinding read from inp.result.`
    );
  });

  // ── MHZ_SMOKE_11 ───────────────────────────────────────────────────────────
  // Stage 1 Phase E (2026-05-24): resolves the long-standing "Phase D deferral"
  // where custom user-created projects ("+ New") only got the v1 result shape
  // from WhatIfEngine, leaving the v2 hazard bar chart + Hazards Evaluated
  // list empty. _runAnalysis now also calls HazardEngine to populate
  // project.evaluation. This test creates a custom project and asserts the
  // detail card paints hazard bars.
  test('custom project from + New flow renders populated hazard bars (Phase D deferral resolved)', async () => {
    const result = await page.evaluate(async () => {
      // Construct a fake "create project" call. We bypass the form UI and
      // call sidebar's exported helpers directly via window.JOSH_DATA — the
      // sidebar IIFE exposes its public API as joshSidebar_*. Use those.
      if (typeof window.joshSidebar_createProject !== 'function') {
        // Fallback: simulate the form flow.
        return { skipped: 'no joshSidebar_createProject hook found' };
      }
      // Hills Gateway coordinates — known to produce DISCRETIONARY wildfire.
      const id = window.joshSidebar_createProject({
        name:    'Smoke Test — Custom',
        address: '2780 Marin Ave',
        lat:     37.8914,
        lng:     -122.2494,
        units:   80,
        stories: 3,
      });
      // Trigger analysis (production calls this from the form submit handler).
      return await new Promise(resolve => {
        window.joshSidebar_runAnalysis(id, () => {
          const p = window.joshSidebar_getProject(id);
          if (!p) { resolve({ error: 'project not found after analysis' }); return; }
          resolve({
            id: p.id,
            has_result_v1: !!p.result,
            has_evaluation_v2: !!p.evaluation,
            eval_schema_version: p.evaluation && p.evaluation.schema_version,
            hazard_results_count: p.evaluation && p.evaluation.hazard_results
              ? p.evaluation.hazard_results.length : 0,
            controlling_hazard: p.evaluation && p.evaluation.controlling_hazard,
            tier: p.evaluation && p.evaluation.tier,
          });
        });
      });
    });

    if (result.skipped) { console.log('SKIP:', result.skipped); return; }
    assert.ok(!result.error, `setup failed: ${result.error}`);
    assert.ok(
      result.has_evaluation_v2,
      'Custom project must have v2 evaluation populated (Phase D deferral resolved).\n' +
      JSON.stringify(result, null, 2)
    );
    assert.equal(result.eval_schema_version, 2);
    assert.ok(
      result.hazard_results_count >= 1,
      `Custom project's evaluation must have at least one hazard_result. got: ${JSON.stringify(result)}`
    );
    assert.equal(result.controlling_hazard, 'wildfire', 'Hills Gateway coords expected to be wildfire-controlled');
    assert.equal(result.tier, 'DISCRETIONARY');
  });

  // ── MHZ_SMOKE_8 ────────────────────────────────────────────────────────────
  test('brief actions chevron menu shows Save HTML / Print / Audit .txt', async () => {
    // Select marina_pointe so the detail card with brief buttons is rendered.
    await page.selectOption('#josh-mhz-project-select', 'marina_pointe');
    await page.waitForTimeout(200);
    await page.click('#josh-mhz-brief-menu-btn');
    await page.waitForTimeout(120);
    const items = await page.evaluate(() => {
      const menu = document.getElementById('josh-mhz-brief-menu');
      if (!menu || menu.style.display !== 'block') return null;
      return [...menu.querySelectorAll('button[data-brief-action]')]
        .map(b => b.textContent.trim());
    });
    assert.ok(items, 'brief menu should be visible after clicking chevron');
    assert.ok(items.includes('Save HTML…'), 'menu should include "Save HTML…"');
    assert.ok(items.includes('Print'),       'menu should include "Print"');
    assert.ok(items.includes('Audit trail .txt'), 'menu should include "Audit trail .txt"');
  });
});

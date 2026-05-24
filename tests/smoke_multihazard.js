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

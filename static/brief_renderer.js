// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH Brief Renderer — Phase 2
 *
 * UMD module: works in browser and Node.
 *
 * Browser:  window.BriefRenderer = { render(briefInput) → htmlString }
 * Node CLI: node static/brief_renderer.js  (reads BriefInput JSON from stdin, writes HTML to stdout)
 * Node test: require('./static/brief_renderer.js')  → same object as window.BriefRenderer
 *
 * BriefInput contract: brief_input_version: 1
 *   See docs/plan-project-manager-v2.md §"The BriefInput Contract" for full schema.
 *
 * This is the SINGLE SOURCE OF TRUTH for brief HTML.
 * Do NOT edit agents/visualization/brief_v3.py templates — that file is now a thin adapter.
 */

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
    // CLI mode: read BriefInput JSON from stdin, write HTML to stdout
    if (require.main === module) {
      var _raw = '';
      process.stdin.resume();
      process.stdin.setEncoding('utf8');
      process.stdin.on('data', function (d) { _raw += d; });
      process.stdin.on('end', function () {
        process.stdout.write(module.exports.render(JSON.parse(_raw)));
      });
    }
  } else {
    root.BriefRenderer = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // ── Color and label constants ──────────────────────────────────────────────
  var TIER_COLOR = {
    'DISCRETIONARY':                         '#c0392b',
    'MINISTERIAL WITH STANDARD CONDITIONS':  '#d67c00',
    'MINISTERIAL':                           '#27ae60',
  };
  var TIER_BG = {
    'DISCRETIONARY':                         '#fdf2f2',
    'MINISTERIAL WITH STANDARD CONDITIONS':  '#fffbf0',
    'MINISTERIAL':                           '#f0faf4',
  };
  var TIER_BORDER = {
    'DISCRETIONARY':                         '#e8b4b0',
    'MINISTERIAL WITH STANDARD CONDITIONS':  '#f5d49a',
    'MINISTERIAL':                           '#a8d5b8',
  };
  var ZONE_LABEL = {
    vhfhsz:        'Very High FHSZ',
    high_fhsz:     'High FHSZ',
    moderate_fhsz: 'Moderate FHSZ',
    non_fhsz:      'Non-FHSZ',
  };
  var RT_ABBR  = { freeway: 'Fwy',      multilane: 'Multi-lane', two_lane: 'Two-lane' };
  var RT_LABEL = { freeway: 'Freeway',  multilane: 'Multi-lane', two_lane: 'Two-lane' };
  var DEG_FACTOR = { vhfhsz: 0.35, high_fhsz: 0.50, moderate_fhsz: 0.75, non_fhsz: 1.00 };

  // ── Formatting helpers ─────────────────────────────────────────────────────
  // Defensive ΔT-on-a-path read. _buildBriefInput in sidebar.js normalizes
  // path objects to carry `delta_t_minutes`, but pipeline-baked path objects
  // (and any other ingestion path) may carry `delta_t` instead. Reading both
  // keys prevents a silent 0.00 in the controlling-finding text when a caller
  // hands in a path with the unnormalized schema.
  function _pdt(p) {
    if (!p) return 0;
    if (p.delta_t_minutes !== undefined && p.delta_t_minutes !== null) return +p.delta_t_minutes || 0;
    if (p.delta_t         !== undefined && p.delta_t         !== null) return +p.delta_t         || 0;
    return 0;
  }
  function _tc(tier)      { return TIER_COLOR[tier]  || '#555'; }
  function _tbg(tier)     { return TIER_BG[tier]     || '#f8f9fa'; }
  function _tbd(tier)     { return TIER_BORDER[tier] || '#dee2e6'; }
  function _zl(hz)        { return ZONE_LABEL[hz]    || hz || ''; }
  function _f(v, dec)     { return (+(v || 0)).toFixed(dec === undefined ? 2 : dec); }
  function _comma(v)      { return Math.round(+(v || 0)).toLocaleString(); }
  function _or(a, b)      { return (a !== undefined && a !== null) ? a : b; }
  function _esc(s)        {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  // Bottleneck label: cross streets + distance, or fallback to name/osmid
  function _fmtBn(p) {
    var nm = p.bottleneck_name || '';
    var cA = p.bottleneck_cross_street_a || '';
    var cB = p.bottleneck_cross_street_b || '';
    var d  = +(p.bottleneck_distance_mi || 0);
    var b  = p.bottleneck_bearing || '';
    var label;
    if (nm) {
      if (cA && cB && cA !== cB) label = nm + ' (' + cA + ' to ' + cB + ')';
      else if (cA || cB) label = nm + ' at ' + (cA || cB);
      else label = nm;
    } else {
      var oid = p.bottleneck_osmid || '—';
      if (cA && cB && cA !== cB) label = 'Unnamed road (' + cA + ' to ' + cB + ')';
      else if (cA || cB) label = 'Unnamed road at ' + (cA || cB);
      else label = 'osmid ' + oid;
    }
    if (d > 0 && b) label += ', ' + d.toFixed(1) + ' mi ' + b;
    return label;
  }
  function _badge(n, derived) {
    var cls = derived ? 'legal-num-badge derived' : 'legal-num-badge';
    return '<span class="' + cls + '">' + n + '</span>';
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  function render(inp) {
    inp = inp || {};
    var r   = inp.result   || {};
    var tier = (r.tier || 'MINISTERIAL').toUpperCase().trim();

    var body = [
      _buildPrintCss(),
      _buildScreenCss(tier),
      _buildWhatIfBanner(inp),
      '<body>',
      _buildHeader(inp),
      '<main>',
      _buildSummaryStats(inp, tier),
      _buildControllingFinding(inp, tier),
      _buildStandardsAnalysis(inp, tier),
      _buildDeterminationBox(inp, tier),
      _buildConditions(inp, tier),
      _buildLegalAuthority(inp, tier),
      _buildScopeAndLimitations(inp),
      _buildAppealRights(inp),
      '</main>',
      _buildFooter(),
      '</body>',
    ].join('\n');

    return _wrapHtml(inp.city_name || 'City', inp.case_number || '', body);
  }

  // ── HTML skeleton ──────────────────────────────────────────────────────────

  function _wrapHtml(cityName, caseNum, body) {
    return '<!DOCTYPE html>\n<html lang="en">\n<head>\n' +
      '  <meta charset="UTF-8">\n' +
      '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n' +
      '  <title>Determination Letter \u2014 ' + _esc(caseNum) + '</title>\n' +
      '  <style>\n' +
      '    *, *::before, *::after { box-sizing: border-box; }\n' +
      '    body {\n' +
      '      margin: 0; padding: 0;\n' +
      "      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;\n" +
      '      background: #f8f9fa;\n' +
      '      color: #212529;\n' +
      '      font-size: 14px;\n' +
      '      line-height: 1.55;\n' +
      '    }\n' +
      '    main {\n' +
      '      max-width: 860px;\n' +
      '      margin: 0 auto;\n' +
      '      padding: 28px 24px 48px;\n' +
      '    }\n' +
      '    h2.section-label {\n' +
      '      font-size: 11px;\n' +
      '      font-weight: 700;\n' +
      '      letter-spacing: 1.4px;\n' +
      '      text-transform: uppercase;\n' +
      '      color: #c0392b;\n' +
      '      margin: 32px 0 14px;\n' +
      '      padding-bottom: 8px;\n' +
      '      border-bottom: 2px solid #e9ecef;\n' +
      '    }\n' +
      '  details summary::marker { display: none; }\n' +
      '  details summary::-webkit-details-marker { display: none; }\n' +
      '  </style>\n' +
      '</head>\n' + body + '\n</html>';
  }

  // ── Print CSS ──────────────────────────────────────────────────────────────

  function _buildPrintCss() {
    return '<style>\n' +
      '@media print {\n' +
      '  body { background: #fff !important; font-size: 12px; }\n' +
      '  main { padding: 0 !important; max-width: 100% !important; }\n' +
      '  .no-print { display: none !important; }\n' +
      '  .brief-header {\n' +
      '    -webkit-print-color-adjust: exact;\n' +
      '    print-color-adjust: exact;\n' +
      '  }\n' +
      '  .stat-card, .standard-row, .determination-box, .conditions-box,\n' +
      '  .legal-authority-box, .appeal-box {\n' +
      '    -webkit-print-color-adjust: exact;\n' +
      '    print-color-adjust: exact;\n' +
      '    break-inside: avoid;\n' +
      '  }\n' +
      '  .conditions-section { page-break-before: always; }\n' +
      '  @page {\n' +
      '    size: letter;\n' +
      '    margin: 0.75in 0.75in 0.85in;\n' +
      '    @bottom-center {\n' +
      '      content: "JOSH \u00b7 California Stewardship Alliance \u00b7 Determination Brief \u00b7 Page " counter(page);\n' +
      '      font-size: 9px;\n' +
      '      color: #868e96;\n' +
      '    }\n' +
      '  }\n' +
      '}\n' +
      '</style>';
  }

  // ── Screen CSS ─────────────────────────────────────────────────────────────

  function _buildScreenCss(tier) {
    var tc = _tc(tier);
    var bg = _tbg(tier);
    var bd = _tbd(tier);
    return '<style>\n' +
      '.brief-header {\n' +
      '  background: #1c4a6e;\n' +
      '  color: #fff;\n' +
      '  padding: 28px 36px;\n' +
      '}\n' +
      '.stat-cards {\n' +
      '  display: grid;\n' +
      '  grid-template-columns: 1fr 1fr 2fr;\n' +
      '  gap: 14px;\n' +
      '  margin-bottom: 8px;\n' +
      '}\n' +
      '.stat-card {\n' +
      '  background: #fff;\n' +
      '  border: 1px solid #dee2e6;\n' +
      '  border-radius: 6px;\n' +
      '  padding: 18px 16px;\n' +
      '  text-align: center;\n' +
      '}\n' +
      '.stat-card .big-num {\n' +
      '  font-size: 38px;\n' +
      '  font-weight: 800;\n' +
      '  line-height: 1;\n' +
      '  margin-bottom: 6px;\n' +
      '}\n' +
      '.stat-card .label {\n' +
      '  font-size: 10px;\n' +
      '  font-weight: 700;\n' +
      '  letter-spacing: 1.2px;\n' +
      '  text-transform: uppercase;\n' +
      '  color: #868e96;\n' +
      '}\n' +
      '.tier-pill {\n' +
      '  display: inline-block;\n' +
      '  font-size: 22px;\n' +
      '  font-weight: 800;\n' +
      '  letter-spacing: 0.5px;\n' +
      '  color: ' + tc + ';\n' +
      '  background: ' + bg + ';\n' +
      '  border: 2px solid ' + bd + ';\n' +
      '  border-radius: 8px;\n' +
      '  padding: 10px 20px;\n' +
      '  margin-top: 4px;\n' +
      '  line-height: 1.2;\n' +
      '}\n' +
      '.criteria-badge {\n' +
      '  display: inline-flex;\n' +
      '  align-items: center;\n' +
      '  justify-content: center;\n' +
      '  width: 26px; height: 26px;\n' +
      '  border-radius: 4px;\n' +
      '  font-size: 12px;\n' +
      '  font-weight: 800;\n' +
      '  flex-shrink: 0;\n' +
      '  color: #fff;\n' +
      '}\n' +
      '.standard-row {\n' +
      '  background: #fff;\n' +
      '  border: 1px solid #dee2e6;\n' +
      '  border-radius: 6px;\n' +
      '  padding: 14px 16px;\n' +
      '  margin-bottom: 8px;\n' +
      '}\n' +
      '.standard-row-header {\n' +
      '  display: flex;\n' +
      '  align-items: center;\n' +
      '  gap: 12px;\n' +
      '}\n' +
      '.standard-title {\n' +
      '  flex: 1;\n' +
      '  font-size: 13px;\n' +
      '  font-weight: 600;\n' +
      '  color: #212529;\n' +
      '}\n' +
      '.standard-sub {\n' +
      '  font-size: 11px;\n' +
      '  color: #868e96;\n' +
      '  margin-top: 1px;\n' +
      '}\n' +
      '.result-chip {\n' +
      '  font-size: 10px;\n' +
      '  font-weight: 700;\n' +
      '  letter-spacing: 0.8px;\n' +
      '  text-transform: uppercase;\n' +
      '  padding: 3px 10px;\n' +
      '  border-radius: 20px;\n' +
      '  white-space: nowrap;\n' +
      '}\n' +
      '.chip-pass      { background: #e8f5e9; color: #27ae60; }\n' +
      '.chip-fail      { background: #fdf2f2; color: #c0392b; }\n' +
      '.chip-triggered { background: #fff3cd; color: #856404; }\n' +
      '.chip-na        { background: #f1f3f5; color: #868e96; }\n' +
      '.chip-scope     { background: #e7f1ff; color: #1a56db; }\n' +
      '.chip-controlling {\n' +
      '  background: #c0392b;\n' +
      '  color: #fff;\n' +
      '  font-size: 9px;\n' +
      '  font-weight: 800;\n' +
      '  letter-spacing: 0.8px;\n' +
      '  text-transform: uppercase;\n' +
      '  padding: 2px 7px;\n' +
      '  border-radius: 20px;\n' +
      '  white-space: nowrap;\n' +
      '}\n' +
      '.detail-block {\n' +
      '  margin-top: 12px;\n' +
      '  padding: 12px 14px;\n' +
      '  background: #f8f9fa;\n' +
      '  border-radius: 5px;\n' +
      '  border-left: 3px solid #dee2e6;\n' +
      '  font-size: 12px;\n' +
      '}\n' +
      '.route-table {\n' +
      '  width: 100%;\n' +
      '  border-collapse: collapse;\n' +
      '  font-size: 11px;\n' +
      '  margin-top: 8px;\n' +
      '}\n' +
      '.route-table th {\n' +
      '  text-align: left;\n' +
      '  font-weight: 700;\n' +
      '  color: #495057;\n' +
      '  padding: 4px 8px;\n' +
      '  border-bottom: 1px solid #dee2e6;\n' +
      '  background: #f1f3f5;\n' +
      '}\n' +
      '.route-table td {\n' +
      '  padding: 5px 8px;\n' +
      '  border-bottom: 1px solid #f1f3f5;\n' +
      '  color: #343a40;\n' +
      '}\n' +
      '.route-table tr:last-child td { border-bottom: none; }\n' +
      '.route-table tr.row-controlling { background: #fff8f8; }\n' +
      '.determination-box {\n' +
      '  border-left: 4px solid ' + tc + ';\n' +
      '  background: ' + bg + ';\n' +
      '  border-radius: 0 6px 6px 0;\n' +
      '  padding: 18px 20px;\n' +
      '  margin-bottom: 12px;\n' +
      '}\n' +
      '.determination-box .action-label {\n' +
      '  font-size: 11px;\n' +
      '  font-weight: 800;\n' +
      '  letter-spacing: 1.2px;\n' +
      '  text-transform: uppercase;\n' +
      '  color: ' + tc + ';\n' +
      '  margin-bottom: 8px;\n' +
      '}\n' +
      '.conditions-box {\n' +
      '  background: #fff;\n' +
      '  border: 1px solid #dee2e6;\n' +
      '  border-radius: 6px;\n' +
      '  padding: 18px 20px;\n' +
      '  margin-bottom: 8px;\n' +
      '}\n' +
      '.conditions-box ol {\n' +
      '  margin: 10px 0 0;\n' +
      '  padding-left: 22px;\n' +
      '}\n' +
      '.conditions-box li {\n' +
      '  margin-bottom: 6px;\n' +
      '  font-size: 13px;\n' +
      '}\n' +
      '.legal-authority-box {\n' +
      '  background: #fff;\n' +
      '  border: 1px solid #dee2e6;\n' +
      '  border-radius: 6px;\n' +
      '  padding: 16px 20px;\n' +
      '  font-size: 12px;\n' +
      '  color: #495057;\n' +
      '}\n' +
      '.legal-table {\n' +
      '  width: 100%;\n' +
      '  border-collapse: collapse;\n' +
      '  margin-top: 10px;\n' +
      '  font-size: 11px;\n' +
      '}\n' +
      '.legal-table th {\n' +
      '  text-align: left;\n' +
      '  font-weight: 700;\n' +
      '  color: #343a40;\n' +
      '  padding: 5px 8px;\n' +
      '  border-bottom: 2px solid #dee2e6;\n' +
      '  background: #f8f9fa;\n' +
      '}\n' +
      '.legal-table td {\n' +
      '  padding: 5px 8px;\n' +
      '  border-bottom: 1px solid #f1f3f5;\n' +
      '  vertical-align: top;\n' +
      '}\n' +
      '.legal-table tr.derived-row td {\n' +
      '  background: #fffbec;\n' +
      '  font-weight: 600;\n' +
      '  border-bottom: 1px solid #f1c40f44;\n' +
      '}\n' +
      '.legal-num-badge {\n' +
      '  display: inline-flex;\n' +
      '  align-items: center;\n' +
      '  justify-content: center;\n' +
      '  width: 20px; height: 20px;\n' +
      '  border-radius: 50%;\n' +
      '  font-size: 10px;\n' +
      '  font-weight: 800;\n' +
      '  color: #fff;\n' +
      '  background: #495057;\n' +
      '  flex-shrink: 0;\n' +
      '}\n' +
      '.legal-num-badge.derived { background: #e67e22; }\n' +
      '.appeal-box {\n' +
      '  background: #fff;\n' +
      '  border: 1px solid #dee2e6;\n' +
      '  border-radius: 6px;\n' +
      '  padding: 16px 20px;\n' +
      '  font-size: 13px;\n' +
      '  color: #495057;\n' +
      '}\n' +
      '.brief-footer {\n' +
      '  text-align: center;\n' +
      '  font-size: 10px;\n' +
      '  color: #adb5bd;\n' +
      '  letter-spacing: 0.8px;\n' +
      '  padding: 18px 0 8px;\n' +
      '  border-top: 1px solid #dee2e6;\n' +
      '  margin-top: 36px;\n' +
      '}\n' +
      '.whatif-banner {\n' +
      '  background: #fff3cd;\n' +
      '  border-bottom: 2px solid #ffc107;\n' +
      '  padding: 10px 24px;\n' +
      '  font-family: system-ui, sans-serif;\n' +
      '  font-size: 12px;\n' +
      '  font-weight: 700;\n' +
      '  color: #856404;\n' +
      '  letter-spacing: 0.3px;\n' +
      '}\n' +
      '</style>';
  }

  // ── What-If banner ─────────────────────────────────────────────────────────

  function _buildWhatIfBanner(inp) {
    if ((inp.source || '') !== 'whatif') return '';
    return '<div class="whatif-banner no-print">' +
      '&#9888; What-If Estimate \u2014 For planning purposes only. ' +
      'Not an official determination. Export and stamp with city letterhead before filing.' +
      '</div>';
  }

  // ── Header ─────────────────────────────────────────────────────────────────

  function _buildHeader(inp) {
    var proj    = inp.project  || {};
    var r       = inp.result   || {};
    var city    = inp.city_name || 'City';
    var caseNum = inp.case_number || '';
    var date    = inp.eval_date   || '';
    var units   = proj.units  || 0;
    var name    = proj.name   || '';
    var addr    = proj.address || '';
    var apn     = proj.apn    || '';

    var projLine = name || (units + '-unit project at (' + _f(proj.lat,4) + ', ' + _f(proj.lon,4) + ')');
    if (addr) projLine = (name ? name + ' \u2014 ' : '') + addr;
    var apnLine = apn ? 'APN: ' + _esc(apn) + ' &nbsp;&middot;&nbsp;' : '';
    var unitsLabel = units + ' dwelling unit' + (units !== 1 ? 's' : '');

    return '<header class="brief-header no-print-border">\n' +
      '  <div style="max-width:860px; margin:0 auto;">\n' +
      '    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:24px; flex-wrap:wrap; margin-bottom:18px;">\n' +
      '      <div>\n' +
      '        <div style="font-size:10px; letter-spacing:2px; text-transform:uppercase; color:#a8c8e8; font-weight:600; margin-bottom:6px;">California Stewardship Alliance</div>\n' +
      '        <div style="font-size:24px; font-weight:800; color:#fff; line-height:1.2; margin-bottom:4px;">City of ' + _esc(city) + ' \u2014 Planning Department</div>\n' +
      '        <div style="font-size:13px; color:#c8dff0; font-weight:500;">Fire Evacuation Capacity Determination &nbsp;&middot;&nbsp; AB 747 &nbsp;&middot;&nbsp; Gov. Code &sect;65302.15</div>\n' +
      '      </div>\n' +
      '      <div style="text-align:right; font-size:11px; color:#a8c8e8; line-height:1.8; flex-shrink:0;">\n' +
      '        <div style="font-weight:700; color:#fff; font-size:12px;">' + _esc(caseNum) + '</div>\n' +
      '        <div>' + apnLine + 'Issued: ' + _esc(date) + '</div>\n' +
      '        <div>' + units + ' dwelling units</div>\n' +
      '      </div>\n' +
      '    </div>\n' +
      '    <div style="border-top:1px solid rgba(255,255,255,0.18); padding-top:14px;">\n' +
      '      <div style="font-size:10px; letter-spacing:1.5px; text-transform:uppercase; color:#a8c8e8; font-weight:600; margin-bottom:4px;">Project</div>\n' +
      '      <div style="font-size:20px; font-weight:800; color:#fff; line-height:1.2;">' + _esc(projLine) + '</div>\n' +
      '      <div style="font-size:15px; font-weight:700; color:#c8dff0; margin-top:6px; letter-spacing:0.3px;">' + unitsLabel + '</div>\n' +
      '    </div>\n' +
      '  </div>\n' +
      '</header>';
  }

  // ── Summary stats ──────────────────────────────────────────────────────────

  function _buildSummaryStats(inp, tier) {
    var r = inp.result || {};
    var tierLabelMap = {
      'DISCRETIONARY':                        'DISCRETIONARY<br>REVIEW REQUIRED',
      'MINISTERIAL WITH STANDARD CONDITIONS': 'MINISTERIAL W/<br>STANDARD CONDITIONS',
      'MINISTERIAL':                          'MINISTERIAL<br>APPROVAL ELIGIBLE',
    };
    var tierLabel = tierLabelMap[tier] || tier;

    if (tier === 'MINISTERIAL') {
      return '<div class="stat-cards" style="margin-top:20px; grid-template-columns:1fr;">\n' +
        '  <div class="stat-card" style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:24px 16px;">\n' +
        '    <div class="tier-pill">' + tierLabel + '</div>\n' +
        '  </div>\n' +
        '</div>';
    }

    var maxDt    = +(r.max_delta_t_minutes || 0);
    var paths    = r.paths || [];
    var threshold = paths.length ? +(paths[0].threshold_minutes || r.threshold_minutes || 6.0) : +(r.threshold_minutes || 6.0);
    var dtColor  = (tier === 'DISCRETIONARY') ? '#c0392b' : '#27ae60';

    return '<div class="stat-cards" style="margin-top:20px;">\n' +
      '  <div class="stat-card">\n' +
      '    <div class="big-num" style="color:' + dtColor + ';">' + _f(maxDt,1) + '</div>\n' +
      '    <div class="label">Max &Delta;T (min)</div>\n' +
      '  </div>\n' +
      '  <div class="stat-card">\n' +
      '    <div class="big-num" style="color:#495057;">' + _f(threshold,2) + '</div>\n' +
      '    <div class="label">Threshold (min)</div>\n' +
      '  </div>\n' +
      '  <div class="stat-card" style="display:flex; flex-direction:column; align-items:center; justify-content:center;">\n' +
      '    <div class="tier-pill">' + tierLabel + '</div>\n' +
      '  </div>\n' +
      '</div>';
  }

  // ── Controlling finding ────────────────────────────────────────────────────

  function _buildControllingFinding(inp, tier) {
    var tc  = _tc(tier);
    var bg  = _tbg(tier);
    var r   = inp.result || {};
    var an  = inp.analysis || {};
    var p   = inp.parameters || {};
    var paths = r.paths || [];

    var ut        = +(p.unit_threshold || 15);
    var maxDt     = +(r.max_delta_t_minutes || 0);
    var hazardZone = r.hazard_zone || an.hazard_zone || 'non_fhsz';
    var hzLabel   = _zl(hazardZone);

    var threshold, safeWindow, maxShare;
    if (paths.length) {
      threshold  = +(paths[0].threshold_minutes         || r.threshold_minutes || 6.0);
      safeWindow = +(paths[0].safe_egress_window_minutes || r.safe_egress_window_minutes || 120);
      maxShare   = +(paths[0].max_project_share          || r.max_project_share || 0.05);
    } else {
      threshold  = +(r.threshold_minutes || 6.0);
      safeWindow = +(r.safe_egress_window_minutes || 120);
      maxShare   = +(r.max_project_share || 0.05);
    }

    var text;
    if (tier === 'MINISTERIAL') {
      var units = +(an.dwelling_units || (inp.project || {}).units || 0);
      text = '<strong>Size threshold not met.</strong> ' +
        'The project (' + units + ' units) is below the ' + ut + '-unit threshold. ' +
        'Evacuation clearance analysis is not required. Approval is ministerial.';
    } else if (tier === 'DISCRETIONARY') {
      var flagged = paths.filter(function(p) { return p.flagged; });
      if (flagged.length) {
        var worst = flagged.reduce(function(a, b) { return _pdt(b) > _pdt(a) ? b : a; });
        var nm    = _fmtBn(worst);
        var dt    = _pdt(worst);
        var thr   = +(worst.threshold_minutes || threshold);
        var ratio = dt / Math.max(thr, 0.001);
        var excess = dt - thr;
        text = '<strong>Controlling finding:</strong> ' + _esc(nm) + ' adds <strong>' + _f(dt,2) + ' min</strong>' +
          ' of marginal evacuation clearance time \u2014 <strong>' + _f(ratio,1) + '&times;</strong> the ' +
          _f(thr,2) + '-min threshold (' + _f(safeWindow,0) + ' min &times; ' + Math.round(maxShare*100) + '%, ' +
          hzLabel + ', NIST TN 2135). Exceeds threshold by <strong>' + _f(excess,2) + ' min</strong>.';
      } else {
        text = '<strong>\u0394T threshold exceeded</strong> on one or more serving evacuation paths.';
      }
    } else {
      // MINISTERIAL WITH STANDARD CONDITIONS
      if (paths.length) {
        var worst2    = paths.reduce(function(a, b) { return _pdt(b) > _pdt(a) ? b : a; });
        var nm2       = _fmtBn(worst2);
        var dt2       = _pdt(worst2);
        var thr2      = +(worst2.threshold_minutes || threshold);
        var remaining = thr2 - dt2;
        var pctUsed   = (dt2 / Math.max(thr2, 0.001)) * 100;
        text = '<strong>All serving paths are within the \u0394T threshold.</strong> ' +
          'Most constrained path: ' + _esc(nm2) + ' at ' + _f(dt2,2) + ' min ' +
          '(' + _f(pctUsed,0) + '% of the ' + _f(thr2,2) + '-min limit, <strong>' + _f(remaining,2) + ' min remaining</strong>).';
      } else {
        text = '<strong>All serving paths are within the \u0394T threshold.</strong>';
      }
    }

    return '<div style="border-left:4px solid ' + tc + '; background:' + bg + '; ' +
      'border-radius:0 6px 6px 0; padding:12px 16px; margin:16px 0 0; ' +
      'font-size:13px; color:#212529; line-height:1.6;">' +
      '<span style="font-size:10px; font-weight:700; letter-spacing:1.2px; ' +
      'text-transform:uppercase; color:' + tc + '; display:block; margin-bottom:5px;">Controlling Finding</span>' +
      text + '</div>';
  }

  // ── Analysis: A / B / C ────────────────────────────────────────────────────

  function _buildStandardsAnalysis(inp, tier) {
    var an    = inp.analysis  || {};
    var r     = inp.result    || {};
    var p     = inp.parameters || {};
    var paths = r.paths || [];

    var hazardZone = r.hazard_zone || an.hazard_zone || 'non_fhsz';
    var hzLabel    = _zl(hazardZone);
    var ut         = +(p.unit_threshold || 15);

    // ── Criterion A: Applicability Threshold ─────────────────────────────────
    var applicabilityMet = an.applicability_met !== undefined ? an.applicability_met : (tier !== 'MINISTERIAL');
    var du               = +(an.dwelling_units || (inp.project||{}).units || 0);
    var condNote         = '';
    if (applicabilityMet && tier === 'MINISTERIAL WITH STANDARD CONDITIONS') {
      condNote = ' Since this project meets the applicability threshold, the evacuation clearance' +
        ' analysis (Criteria B and C) applies. If all criteria are met, pre-adopted' +
        ' standard conditions apply automatically \u2014 see <em>Required Next Steps</em>.';
    }
    var s1Chip, s1ChipCls;
    if (!applicabilityMet) { s1Chip = 'BELOW THRESHOLD'; s1ChipCls = 'chip-na'; }
    else if (tier === 'MINISTERIAL WITH STANDARD CONDITIONS') { s1Chip = 'IN SCOPE \u2014 CONDITIONS APPLY'; s1ChipCls = 'chip-scope'; }
    else { s1Chip = 'IN SCOPE'; s1ChipCls = 'chip-scope'; }

    var s1Detail = applicabilityMet
      ? '<div class="detail-block">' + du + ' dwelling units proposed &nbsp;&ge;&nbsp; ' + ut + '-unit threshold.' +
        ' Project size threshold: ' + ut + ' dwelling units' +
        ' (ITE Trip Generation de minimis; SB 330, Gov. Code &sect;65913.4).' + condNote + '</div>'
      : '<div class="detail-block">' + du + ' dwelling units proposed &nbsp;&lt;&nbsp; ' + ut + '-unit threshold \u2014' +
        ' project is below the ITE de minimis for measurable evacuation impact.' +
        ' Evacuation clearance analysis is not required.</div>';

    var rows = [_analysisRow('A', applicabilityMet ? '#1a56db' : '#6c757d',
      'Applicability Threshold',
      'Minimum ' + ut + ' dwelling units \u2014 integer comparison, no discretion',
      s1Chip, s1ChipCls, s1Detail)];

    // ── Criterion B: Site Parameters ─────────────────────────────────────────
    var fhszFlagged = an.fhsz_flagged !== undefined ? an.fhsz_flagged : (hazardZone !== 'non_fhsz');
    var fhszDesc    = an.fhsz_desc  || (fhszFlagged ? hzLabel : 'Not in FHSZ');
    var fhszLevel   = +(an.fhsz_level || 0);
    var mobRate     = +(an.behavioral_mobilization || p.behavioral_mobilization || 0.90);
    var degFactor   = +(an.hazard_degradation_factor || (p.hazard_degradation||{})[hazardZone] || DEG_FACTOR[hazardZone] || 1.00);

    var s3Chip, s3ChipCls, s3BadgeColor, s3Detail;
    if (!applicabilityMet) {
      s3Chip = 'PENDING'; s3ChipCls = 'chip-na'; s3BadgeColor = '#adb5bd'; s3Detail = '';
    } else if (fhszFlagged) {
      s3Chip = hzLabel.toUpperCase(); s3ChipCls = 'chip-triggered'; s3BadgeColor = '#c0392b';
      s3Detail = '<div class="detail-block" style="border-left-color:#c0392b;">' +
        '<strong>Project site:</strong> ' + _esc(fhszDesc) + ' (source: CAL FIRE OSFM)<br>' +
        '<strong>CAL FIRE HAZ_CLASS:</strong> ' + fhszLevel + ' \u2014' +
        ' <code>' + hazardZone + '</code>; road capacity reduced to ' + _f(degFactor,2) + '&times; HCM base' +
        ' (composite engineering-judgment factor anchored against HCM 2022 Ch. 11 weather CAF framework + NIST TN 2135 Camp Fire empirical observations; independent traffic-engineering review pending).<br>' +
        '<strong>\u0394T threshold:</strong> reduced proportionally (shorter safe egress window applies; see Clearance Analysis below).<br>' +
        '<strong>Mobilization rate:</strong> ' + _f(mobRate,2) + ' (NFPA 1660 / 1616 community mass-evacuation design basis, constant \u2014 unaffected by FHSZ zone; ~10% zero-vehicle HH per Census ACS B25044).' +
        '</div>';
    } else {
      s3Chip = 'NON-FHSZ'; s3ChipCls = 'chip-na'; s3BadgeColor = '#6c757d';
      s3Detail = '<div class="detail-block">' +
        'Project site is not within a designated fire hazard severity zone' +
        ' (<strong>CAL FIRE HAZ_CLASS: 0</strong>, <code>non_fhsz</code>).' +
        ' No road capacity degradation applied (factor = 1.00&times;).' +
        ' Standard 120-min safe egress window applies.<br>' +
        '<strong>Mobilization rate:</strong> ' + _f(mobRate,2) + ' (NFPA 1660 / 1616 community mass-evacuation design basis, constant).' +
        '</div>';
    }
    rows.push(_analysisRow('B', s3BadgeColor,
      'Site Parameters',
      'CAL FIRE FHSZ classification \u2014 sets road capacity degradation factor and \u0394T threshold for clearance analysis',
      s3Chip, s3ChipCls, s3Detail));

    // ── Criterion C: Evacuation Clearance Analysis ────────────────────────────
    var deltaTriggered  = r.triggered !== undefined ? r.triggered : (tier === 'DISCRETIONARY');
    var routeCount      = +(an.serving_route_count  || r.serving_paths_count || paths.length || 0);
    var routeRadius     = +(an.route_radius_miles   || 0.5);
    var routesTrigger   = an.routes_trigger_analysis !== undefined ? an.routes_trigger_analysis : (routeCount > 0);
    var egresMin        = +(r.egress_minutes || an.egress_minutes || 0);
    var maxDt           = +(r.max_delta_t_minutes || 0);
    var safeWindow      = +(r.safe_egress_window_minutes || (paths.length ? paths[0].safe_egress_window_minutes : 120) || 120);
    var maxShare        = +(r.max_project_share || (paths.length ? paths[0].max_project_share : 0.05) || 0.05);
    var maxThreshold    = +(r.threshold_minutes || (paths.length ? paths[0].threshold_minutes : 6.0) || 6.0);
    var projVph         = +(r.project_vehicles || 0);

    var s24Chip, s24ChipCls, s24BadgeColor;
    if (!applicabilityMet) {
      s24Chip = 'NOT REQUIRED'; s24ChipCls = 'chip-na'; s24BadgeColor = '#adb5bd';
    } else if (deltaTriggered) {
      s24Chip = 'EXCEEDS THRESHOLD'; s24ChipCls = 'chip-fail'; s24BadgeColor = '#c0392b';
    } else if (routesTrigger) {
      s24Chip = 'WITHIN THRESHOLD'; s24ChipCls = 'chip-pass'; s24BadgeColor = '#27ae60';
    } else {
      s24Chip = 'NO ROUTES'; s24ChipCls = 'chip-na'; s24BadgeColor = '#6c757d';
    }

    var mergedTableHtml = '';
    if (applicabilityMet) {
      var derivBlock = '<div style="font-size:11px; background:#f0f4f8; border:1px solid #ccd6e0; ' +
        'border-radius:4px; padding:7px 10px; margin-bottom:8px; line-height:1.8;">' +
        '<strong>\u0394T threshold:</strong> ' +
        _f(safeWindow,0) + ' min safe egress window (NIST TN 2135, ' + hzLabel + ') ' +
        '&times; ' + Math.round(maxShare*100) + '% max project share ' +
        '= <strong>' + _f(maxThreshold,2) + ' min</strong></div>';

      var egresNote = egresMin > 0
        ? "<span style='color:#6f42c1;font-weight:600'>Building egress: +" + _f(egresMin,1) + " min (NFPA 101 Life Safety Code, 2024 CA ed., Ch. 7 + IBC 2024 Ch. 10, stories &ge; 4)</span> &nbsp;|&nbsp; "
        : '';

      if (paths.length) {
        // v4.12 (all-viable-routes): the brief is a legal document — list every viable
        // route, no truncation.  Sort by exit travel time (fastest first) so the table
        // order matches the sidebar's "User Equilibrium" ordering.
        var sortedPaths   = paths.slice().sort(function(a, b) {
          return (+(a.cost_s || 0)) - (+(b.cost_s || 0));
        });
        var displayPaths  = sortedPaths;

        // Controlling path = highest ΔT (the binding constraint for the determination)
        var controllingPath = paths.reduce(function(a, b) {
          return _pdt(b) > _pdt(a) ? b : a;
        });
        var controllingId   = controllingPath.path_id;
        var controllingBnNm = _fmtBn(controllingPath);
        var controllingDt   = _pdt(controllingPath);

        // Summary line — single-glance answer to "how bad is this?"
        // v4.13: ΔT color is red when the controlling route is flagged, green
        // when it passes — matches the red/green marching ants on the
        // interactive map so the brief and the map tell the same visual story.
        var summaryLine = '<div style="font-size:12px; margin-bottom:6px; color:#212529;">' +
          '<strong>' + paths.length + ' route' + (paths.length === 1 ? '' : 's') + ' evaluated</strong>; ' +
          'controlling &Delta;T = <strong style="color:' +
            (controllingPath.flagged ? '#c0392b' : '#27ae60') + '">' +
            _f(controllingDt, 2) + ' min</strong> on ' +
          '<em>' + _esc(controllingBnNm) + '</em>.</div>';

        // v4.13 (route-display-ux): legal framing paragraph above the route
        // table — paraphrases JOSH_Legal_Defensibility_Memo.md §8.6.  Pre-empts
        // the "use the green route" objection in the same document where the
        // route table appears as evidence.
        var legalFraming = '<div style="font-size:11px;color:#465464;background:#eef2f7;' +
          'border-left:3px solid #1c4a6e;padding:8px 10px;border-radius:0 4px 4px 0;' +
          'margin-bottom:8px;line-height:1.45;">' +
          '<strong style="color:#1c4a6e;">About the route list.</strong> ' +
          'The routes listed below are paths evacuees may self-select during an ' +
          'evacuation (User Equilibrium). The determination uses the ' +
          '<strong>controlling (worst-case) route</strong> because some ' +
          'evacuees will take it &mdash; slower routes do not "fix" faster ones. ' +
          'See §3.6 and §8.6 of the Legal Defensibility Memo for the ' +
          'full methodology.</div>';

        var tableRows = displayPaths.map(function(rr) {
          var pid    = rr.path_id || '\u2014';
          var bname  = _fmtBn(rr);
          var effCap = +(rr.bottleneck_eff_cap_vph || rr.bottleneck_effective_capacity_vph || 0);
          var dt     = _pdt(rr);
          var thr    = +(rr.threshold_minutes || maxThreshold);
          var flg    = !!rr.flagged;
          var margin = dt - thr;
          var isCtrl = (pid === controllingId);

          // Capacity subtitle for bottleneck cell
          var bRt   = rr.bottleneck_road_type  || '';
          var bSpd  = +(rr.bottleneck_speed_mph  || 0);
          var bLns  = +(rr.bottleneck_lanes       || 0);
          var bHcm  = +(rr.bottleneck_hcm_capacity_vph || 0);
          var bDeg  = +(rr.bottleneck_hazard_degradation || degFactor);
          var bCapSrc = rr.bottleneck_cap_src || 'hcm';
          var rtParts = [];
          if (RT_ABBR[bRt]) rtParts.push(RT_ABBR[bRt]);
          if (bSpd) rtParts.push(bSpd + '\u202fmph');
          if (bLns) rtParts.push(bLns + '\u202fln');
          var capStr;
          if (bCapSrc === 'city_override') {
            var rawCap = bDeg > 0 ? Math.round(effCap / bDeg) : effCap;
            capStr = _comma(rawCap) + '\u202fvph\u202f[city-provided]\u202f\u00d7\u202f' + _f(bDeg,2) + '\u202f=\u202f' + _comma(effCap) + '\u202fvph';
          } else {
            capStr = bHcm ? 'HCM\u202f' + _comma(bHcm) + '\u202f\u00d7\u202f' + _f(bDeg,2) + '\u202f=\u202f' + _comma(effCap) + '\u202fvph' : '';
          }
          var subtitleParts = [rtParts.join(' \u00b7 ')];
          if (capStr) subtitleParts.push(capStr);
          var bnSubtitle = subtitleParts.filter(Boolean).join('  \u2192  ');
          var bnameCell = bnSubtitle
            ? _esc(bname) + '<br><span style="font-size:9px;color:#868e96;font-weight:normal">' + _esc(bnSubtitle) + '</span>'
            : _esc(bname);

          // v4.13 (route-display-ux): only the CONTROLLING row carries
          // pass/fail color (red flagged / green within-threshold), matching
          // the red/green marching ants on the interactive map.  Non-controlling
          // rows are neutral \u2014 the determination is project-level, not
          // route-level, and per-row color would invite the alternative-route
          // objection (see Legal Defensibility Memo \u00a78.6).
          var ctrlBadgeColor = flg ? '#e74c3c' : '#27ae60';
          var dtColor     = isCtrl ? ctrlBadgeColor : '#495057';
          var marginColor = isCtrl ? ctrlBadgeColor : '#6c757d';
          var marginStr   = flg ? '+' + _f(margin,2) : '\u2212' + _f(Math.abs(margin),2);

          var costMin = (+(rr.cost_s || 0)) / 60;
          var rowCls = isCtrl ? 'row-controlling' : '';
          var pidCell = isCtrl
            ? "<td style='font-size:10px;color:#868e96'>" + _esc(pid) + "<br>" +
                "<span style='display:inline-block;font-size:9px;font-weight:700;" +
                "background:" + ctrlBadgeColor + ";color:#fff;border-radius:3px;padding:1px 5px;" +
                "letter-spacing:0.06em;margin-top:2px;'>CONTROLLING</span></td>"
            : "<td style='font-size:10px;color:#868e96'>" + _esc(pid) + "</td>";
          return "<tr class='" + rowCls + "'>" +
            pidCell +
            "<td>" + bnameCell + "</td>" +
            "<td style='font-size:10px'>" + _esc(hzLabel) + "</td>" +
            "<td style='font-weight:600'>" + _comma(effCap) + "</td>" +
            "<td style='color:#495057'>" + (costMin > 0 ? _f(costMin,1) : '\u2014') + "</td>" +
            "<td style='font-weight:" + (isCtrl ? '700' : '500') + ";color:" + dtColor + "'>" + _f(dt,2) + "</td>" +
            "<td style='color:#868e96'>" + _f(thr,2) + "</td>" +
            "<td style='font-weight:" + (isCtrl ? '600' : '500') + ";color:" + marginColor + "'>" + marginStr + "</td>" +
            "</tr>";
        }).join('');

        mergedTableHtml = derivBlock +
          legalFraming +
          summaryLine +
          "<div style='font-size:11px;color:#6c757d;margin-bottom:4px;'>" +
          egresNote + "Project vehicles: <strong>" + _f(projVph,0) + "</strong>" +
          " (units &times; 1.9 vpu &times; 0.90 mobilization; NFPA 1660 / 1616 community mass-evacuation design basis, Census ACS B25044 zero-vehicle adjustment)." +
          " Effective capacity = HCM 2022 raw &times; " + _f(degFactor,2) + " composite hazard-degradation factor." +
          " Routes sorted fastest exit first (User Equilibrium ordering).</div>" +
          "<table class='route-table'><thead><tr>" +
          "<th>Path</th><th>Bottleneck Segment</th><th>FHSZ Zone</th>" +
          "<th>Eff. Cap (vph)</th><th>Exit (min)</th><th>&#916;T (min)</th><th>Threshold</th>" +
          "<th>Margin</th></tr></thead><tbody>" + tableRows + "</tbody></table>";
      } else {
        mergedTableHtml = derivBlock +
          "<div style='color:#6c757d;'>" + routeCount +
          ' evacuation route segment' + (routeCount !== 1 ? 's' : '') + ' identified within ' + routeRadius +
          ' miles. No path \u0394T results available.</div>';
      }
    }

    var s24DetailBorder = deltaTriggered ? '#c0392b' : (!applicabilityMet ? '#dee2e6' : '#27ae60');
    var s24Detail = applicabilityMet
      ? '<div class="detail-block" style="border-left-color:' + s24DetailBorder + ';">' +
          (applicabilityMet ? routeCount + ' serving route segment' + (routeCount !== 1 ? 's' : '') + ' within ' + routeRadius + ' mi (OSM evacuation route network).' : '') +
          mergedTableHtml + '</div>'
      : '';

    rows.push(_analysisRow('C', s24BadgeColor,
      'Evacuation Clearance Analysis',
      'Route identification (0.5 mi radius) + per-path \u0394T test \u2014 this is the operative determination step',
      s24Chip, s24ChipCls, s24Detail));

    // ── SB 79 Disclosure ─────────────────────────────────────────────────────
    var sb79Chip = applicabilityMet ? 'INFORMATIONAL' : 'NOT REQUIRED';
    rows.push(_disclosureRow(
      'SB 79 Transit Proximity',
      'Transit stop within 0.5 mi \u2014 does not affect this determination',
      sb79Chip));

    return '<h2 class="section-label">Analysis</h2>\n' + rows.join('');
  }

  function _analysisRow(letter, badgeColor, title, subtitle, chipText, chipCls, detailHtml) {
    return '<div class="standard-row">\n' +
      '  <div class="standard-row-header">\n' +
      '    <span class="criteria-badge" style="background:' + badgeColor + ';">' + letter + '</span>\n' +
      '    <div style="flex:1;">\n' +
      '      <div class="standard-title">' + title + '</div>\n' +
      '      <div class="standard-sub">' + subtitle + '</div>\n' +
      '    </div>\n' +
      '    <span class="result-chip ' + chipCls + '">' + chipText + '</span>\n' +
      '  </div>\n' +
      '  ' + detailHtml + '\n' +
      '</div>\n';
  }

  function _disclosureRow(title, subtitle, chipText) {
    return '<div class="standard-row" style="border-left:3px solid #dee2e6; background:#fafafa;">\n' +
      '  <div class="standard-row-header">\n' +
      '    <div style="flex:1;">\n' +
      '      <div class="standard-title" style="color:#6c757d;">' + title + '</div>\n' +
      '      <div class="standard-sub">' + subtitle + '</div>\n' +
      '    </div>\n' +
      '    <span class="result-chip chip-na">' + chipText + '</span>\n' +
      '  </div>\n' +
      '</div>\n';
  }

  // ── Determination box ──────────────────────────────────────────────────────

  function _buildDeterminationBox(inp, tier) {
    var tc     = _tc(tier);
    var bd     = _tbd(tier);
    var r      = inp.result || {};
    var reason = r.determination_reason || '';

    var scRows = '';
    var wildlandTier = r.tier;
    if (wildlandTier) {
      var wColor = _tc(wildlandTier);
      scRows += '<div style="font-size:11px;margin-bottom:3px;">Wildland Evacuation Analysis: <strong style="color:' + wColor + '">' + wildlandTier + '</strong></div>';
      scRows += '<div style="font-size:11px;margin-bottom:3px;">SB 79 Transit Proximity (Informational): <strong style="color:#868e96">NOT APPLICABLE</strong></div>';
    }
    if (scRows) {
      scRows = '<div style="margin-top:10px; padding-top:10px; border-top:1px solid ' + bd + ';">' + scRows + '</div>';
    }

    return '<h2 class="section-label">Determination</h2>\n' +
      '<div class="determination-box">\n' +
      '  <div class="action-label">DETERMINATION &nbsp;&rarr;</div>\n' +
      '  <div style="font-size:13px; color:#212529; line-height:1.6;">' + (reason || '(See analysis above.)') + '</div>\n' +
      '  ' + scRows + '\n' +
      '</div>';
  }

  // ── Conditions ─────────────────────────────────────────────────────────────

  function _buildConditions(inp, tier) {
    var an   = inp.analysis || {};
    var fzLv = +(an.fhsz_level || 0);
    var r    = inp.result || {};
    var p    = inp.parameters || {};

    var body;
    if (tier === 'MINISTERIAL') {
      body = _conditionsMinisterial();
    } else if (tier === 'MINISTERIAL WITH STANDARD CONDITIONS') {
      body = _conditionsConditional(fzLv);
    } else {
      body = _conditionsDiscretionary(inp, tier);
    }

    return '<h2 class="section-label conditions-section">Required Next Steps</h2>\n' +
      '<div class="conditions-box">' + body + '</div>';
  }

  function _conditionsMinisterial() {
    return '<p style="margin:0 0 10px;">' +
      'This project <strong>qualifies for ministerial approval</strong> under Government Code \u00a765589.4' +
      ' and the adopted AB 747 objective standards. No discretionary review is required. No public hearing is required.' +
      '</p>' +
      '<ol>' +
      '<li>Submit building permit application to the Building &amp; Safety Division per normal procedures.</li>' +
      '<li>Standard fire and life safety plan check applies (Health &amp; Safety Code \u00a713108).</li>' +
      '<li>No CEQA review is required for ministerial approvals (Pub. Resources Code \u00a721080(b)(1)).</li>' +
      '<li>Applicant shall not reduce the width or lane count of any identified evacuation route during construction.</li>' +
      '</ol>';
  }

  function _conditionsConditional(fzLevel) {
    var fhszConditions = '';
    if (fzLevel >= 2) {
      fhszConditions =
        '<li><strong>Defensible space compliance \u2014 PRC \u00a74291.</strong>' +
        ' The project site is located within a Very High or High Fire Hazard Severity Zone.' +
        ' Prior to permit issuance, the applicant shall submit documentation to the Fire Marshal' +
        ' confirming that all structures will maintain the 100-foot defensible space clearance' +
        ' zones required under Public Resources Code \u00a74291.</li>' +
        '<li><strong>WUI building standards compliance \u2014 CBC Chapter 7A / SFM Chapter 12-7A.</strong>' +
        ' All new structures shall comply with wildland-urban interface fire area construction' +
        ' requirements applicable to the project\u2019s FHSZ classification, including ignition-resistant' +
        ' building materials, ember-resistant vents, and deck/eave construction standards.</li>';
    }
    return '<p style="margin:0 0 12px;">' +
      'This project is <strong>approved ministerially</strong>. The following pre-adopted, objective' +
      ' conditions apply automatically by operation of law and local ordinance. No discretionary review' +
      ' or public hearing is required. (Gov. Code \u00a765589.4)' +
      '</p>' +
      '<ol>' + fhszConditions +
      '<li><strong>Evacuation infrastructure impact fee \u2014 AB 1600 (Gov. Code \u00a766000 et seq.).</strong>' +
      ' If the city has adopted an evacuation infrastructure impact fee schedule pursuant to the' +
      ' Mitigation Fee Act (AB 1600), the applicable fee is due at building permit issuance.</li>' +
      '<li><strong>Emergency vehicle access \u2014 local fire code (IFC \u00a7503).</strong>' +
      ' The project shall maintain minimum fire apparatus access road width, vertical clearance,' +
      ' and turning radii as required by the adopted local fire code throughout construction and operation.</li>' +
      '</ol>';
  }

  function _conditionsDiscretionary(inp, tier) {
    var r          = inp.result    || {};
    var paths      = r.paths       || [];
    var maxDt      = +(r.max_delta_t_minutes || 0);
    var threshold  = +(r.threshold_minutes || (paths.length ? paths[0].threshold_minutes : 6.0) || 6.0);
    var hazardZone = r.hazard_zone || 'non_fhsz';
    var flaggedPs  = paths.filter(function(p) { return p.flagged; });

    var pathNote = '';
    if (flaggedPs.length) {
      var parts = flaggedPs.slice(0,3).map(function(p) {
        var pid   = p.path_id || '\u2014';
        var bname = _fmtBn(p);
        var dt    = _pdt(p);
        var thr   = +(p.threshold_minutes || threshold);
        return 'Path ' + pid + ' \u2014 bottleneck: ' + _esc(bname) + ' (\u0394T ' + _f(dt,1) + ' min vs ' + _f(thr,2) + '-min threshold)';
      });
      var nMore = flaggedPs.length - parts.length;
      var routeList = parts.join('; ');
      if (nMore > 0) routeList += '; and ' + nMore + ' more paths';
      pathNote = '<p style="margin:10px 0 0; font-size:12px; color:#495057;">' +
        '<strong>\u0394T exceedance identified on ' + flaggedPs.length + ' path(s):</strong> ' + routeList + '</p>';
    }

    return '<p style="margin:0 0 10px;">' +
      'This project <strong>requires discretionary review</strong> under AB 747' +
      ' (Gov. Code \u00a765302.15). The objective standards analysis has determined that this project' +
      ' would add more than ' + _f(threshold,2) + ' minutes of marginal evacuation clearance time (\u0394T)' +
      ' on one or more serving evacuation paths in hazard zone <code>' + hazardZone + '</code>' +
      ' (maximum \u0394T: ' + _f(maxDt,2) + ' min vs. ' + _f(threshold,2) + '-min threshold).' +
      '</p>' +
      pathNote +
      '<ol>' +
      '<li><strong>Environmental Impact Report (EIR)</strong> required under CEQA' +
      ' (Pub. Resources Code \u00a721100) \u2014 evacuation clearance time impact must be analyzed' +
      ' as a significant transportation impact.</li>' +
      '<li><strong>Evacuation Clearance Time Analysis:</strong> Applicant shall commission' +
      ' a study conforming to the JOSH v4.0 \u0394T methodology (AB 747 / Gov. Code \u00a765302.15),' +
      ' analyzing marginal evacuation clearance time on all serving paths within 0.5 miles,' +
      ' using NFPA 1660 / 1616 community mass-evacuation design basis mobilization rate (0.90 constant) and HCM 2022' +
      ' hazard-degraded capacity factors (HCM Ch. 11 weather CAF framework with WUI fire-condition composite adjustment).</li>' +
      '<li><strong>Public Hearing</strong> before the Planning Commission is required prior to any' +
      ' project approval (Gov. Code \u00a765905).</li>' +
      '<li><strong>Fire Department Review:</strong> Submit project plans to the Fire Marshal for' +
      ' review of evacuation access, egress widths, and compliance with Fire Code \u00a7503.</li>' +
      '<li><strong>Mitigation Measures or Project Redesign:</strong> Applicant must demonstrate' +
      ' \u2014 through the clearance time analysis \u2014 either (a) that mitigation measures reduce \u0394T' +
      ' below ' + _f(threshold,2) + ' minutes on all serving paths, or (b) that the project scope' +
      ' (units, stories, or both) is reduced to fall within the \u0394T threshold, to qualify for ministerial review.</li>' +
      '<li>Approval is not ministerial until the \u0394T exceedance is mitigated or the project' +
      ' is redesigned to fall within the \u0394T threshold on all serving evacuation paths.</li>' +
      '</ol>';
  }

  // ── Legal Authority ────────────────────────────────────────────────────────

  function _buildLegalAuthority(inp, tier) {
    var r   = inp.result    || {};
    var an  = inp.analysis  || {};
    var p   = inp.parameters || {};
    var paths = r.paths || [];

    var hazardZone  = r.hazard_zone || an.hazard_zone || 'non_fhsz';
    var hzLabel     = _zl(hazardZone);
    var fhszDesc    = an.fhsz_desc || (hazardZone !== 'non_fhsz' ? hzLabel : 'Not in FHSZ');
    var ut          = +(p.unit_threshold || 15);
    var vpu         = +(p.vehicles_per_unit || 1.9);
    var mobRate     = +(p.behavioral_mobilization || 0.90);
    var maxShare    = +(p.max_project_share || 0.05);
    var egCfg       = p.egress_penalty || {};
    var egrThr      = +(egCfg.threshold_stories || 4);
    var egrMps      = +(egCfg.minutes_per_story || 1.5);
    var egrMax      = +(egCfg.max_minutes || 12);
    var safeEgrMap  = p.safe_egress_window || {};
    var safeWindow  = +(r.safe_egress_window_minutes || safeEgrMap[hazardZone] || paths.length && paths[0].safe_egress_window_minutes || 120);
    var threshold   = +(r.threshold_minutes || paths.length && paths[0].threshold_minutes || safeWindow * maxShare);
    var maxDt       = +(r.max_delta_t_minutes || 0);
    var projVph     = +(r.project_vehicles || 0);
    var egresMin    = +(r.egress_minutes || an.egress_minutes || 0);
    var degFactor   = +(an.hazard_degradation_factor || (p.hazard_degradation||{})[hazardZone] || DEG_FACTOR[hazardZone] || 1.00);
    var units       = +(an.dwelling_units || (inp.project||{}).units || 0);

    // Controlling path
    var effCapCtrl   = 0;
    var ctrlRoadName = '\u2014';
    var ctrlRoadType = '';
    var ctrlSpeed    = 0;
    var ctrlLanes    = 0;
    var hcmRawCtrl   = 0;
    if (paths.length) {
      var worst = paths.reduce(function(a, b) { return _pdt(b) > _pdt(a) ? b : a; });
      effCapCtrl   = +(worst.bottleneck_eff_cap_vph || worst.bottleneck_effective_capacity_vph || 0);
      ctrlRoadName = _fmtBn(worst);
      hcmRawCtrl   = +(worst.bottleneck_hcm_capacity_vph || 0);
      ctrlRoadType = worst.bottleneck_road_type || '';
      ctrlSpeed    = +(worst.bottleneck_speed_mph || 0);
      ctrlLanes    = +(worst.bottleneck_lanes     || 0);
    }
    var ctrlRtLabel  = RT_LABEL[ctrlRoadType] || ctrlRoadType;
    var ctrlHcmParts = ctrlRtLabel ? [ctrlRtLabel] : [];
    if (ctrlSpeed) ctrlHcmParts.push(ctrlSpeed + ' mph');
    if (ctrlLanes) ctrlHcmParts.push(ctrlLanes + ' lanes');
    var ctrlHcmDetail = ctrlHcmParts.join(', ');

    // Audit trail — generated client-side by sidebar._buildAuditText(); open by default
    var auditBlock = '';
    if (inp.audit_text) {
      auditBlock = '<details class="no-print" style="margin-top:4px;">' +
        '<summary style="cursor:pointer; font-size:11px; color:#1a56db; font-family:monospace;' +
        ' background:#f1f3f5; padding:3px 8px; border-radius:3px; display:inline-block;' +
        ' user-select:none; list-style:none;">&#9654; ' + _esc(inp.audit_filename || 'audit_trail.txt') + '</summary>' +
        '<pre style="margin:8px 0 0; padding:10px 12px; background:#f8f9fa; border:1px solid #dee2e6;' +
        ' border-radius:4px; font-size:10px; line-height:1.5; overflow-x:auto;' +
        ' white-space:pre-wrap; word-break:break-word; color:#212529;">' + _esc(inp.audit_text) + '</pre>' +
        '</details>';
    }

    var egresLine = egresMin > 0
      ? 'egress_penalty = min(stories &times; ' + egrMps + ', ' + egrMax + ') = ' + _f(egresMin,1) + ' min (NFPA 101 Life Safety Code, 2024 CA ed. + IBC 2024 Ch. 10)<br>'
      : 'egress_penalty = 0 (building &lt; ' + egrThr + ' stories)<br>';

    return '<h2 class="section-label">Legal Authority</h2>\n' +
      '<div class="legal-authority-box">\n' +
      '  <p style="margin:0 0 12px; font-size:12px; color:#495057;">' +
      '    Every numerical value in this determination is derived mechanically from the authorities below.' +
      '    No engineering judgment was exercised. The same methodology is applied uniformly to all projects under AB 747.' +
      '  </p>\n' +
      '  <table class="legal-table">\n' +
      '    <thead><tr><th style="width:28px;">#</th><th>Authority</th><th>Published / Adopted</th><th>Parameter</th><th>Value Applied</th></tr></thead>\n' +
      '    <tbody>\n' +
      '      <tr><td>' + _badge(1) + '</td><td><strong>AB 747</strong>, Gov. Code \u00a765302.15</td><td>2021 Ch. 394</td><td>Analysis mandate</td><td>\u2014</td></tr>\n' +
      '      <tr><td>' + _badge(2) + '</td><td><strong>CAL FIRE OSFM FHSZ</strong> (state-adopted SRA map)</td><td>Current SRA designation</td>' +
      '<td>Hazard zone</td><td><code>' + hazardZone + '</code> \u2014 ' + _esc(fhszDesc) + '</td></tr>\n' +
      '      <tr><td>' + _badge(3) + '</td><td><strong>NIST TN 2135</strong> (Maranghides et al., Camp Fire)</td><td>2021</td>' +
      '<td>Safe egress window (' + hzLabel + ')</td><td><strong>' + _f(safeWindow,0) + ' min</strong></td></tr>\n' +
      '      <tr><td>' + _badge(4) + '</td><td>Standard engineering significance criterion</td><td>\u2014</td>' +
      '<td>Maximum project share of egress window</td><td><strong>' + Math.round(maxShare*100) + '%</strong></td></tr>\n' +
      '      <tr class="derived-row"><td>' + _badge('\u2192', true) + '</td><td colspan="2"><em>Derived from \u2462 \u00d7 \u2463</em></td>' +
      '<td>\u0394T threshold for this location</td><td><strong>' + _f(safeWindow,0) + ' &times; ' + _f(maxShare,2) + ' = ' + _f(threshold,2) + ' min</strong></td></tr>\n' +
      '      <tr><td>' + _badge(5) + '</td><td><strong>HCM 2022</strong> Exhibit 12-7 (TRB 7th Ed.)</td><td>TRB 2022</td>' +
      '<td>Road HCM base capacity (controlling: ' + _esc(ctrlRoadName) +
      (ctrlHcmDetail ? '<br><span style="font-size:10px;color:#6c757d">' + _esc(ctrlHcmDetail) + '</span>' : '') +
      ')</td><td><strong>' + _comma(hcmRawCtrl) + ' vph</strong></td></tr>\n' +
      '      <tr><td>' + _badge(6) + '</td><td><strong>Composite hazard-degradation factor</strong> — anchored against HCM 2022 Ch. 11 weather CAF framework + NIST TN 2135 Camp Fire empirical observations; independent traffic-engineering review pending (FSC May 2026)</td><td>TRB 2022 / NIST 2021 / FSC 2026</td>' +
      '<td>Hazard capacity degradation (' + hzLabel + ')</td><td><strong>' + _f(degFactor,2) + '&times;</strong></td></tr>\n' +
      '      <tr class="derived-row"><td>' + _badge('\u2192', true) + '</td><td colspan="2"><em>Derived from \u2464 \u00d7 \u2465</em></td>' +
      '<td>Effective bottleneck capacity</td><td><strong>' + _comma(effCapCtrl) + ' vph</strong></td></tr>\n' +
      '      <tr><td>' + _badge(7) + '</td><td><strong>NFPA 1660</strong> Standard for Emergency, Continuity, and Crisis Management (2024 ed.; consolidates <strong>NFPA 1616</strong> Mass Evacuation, Sheltering, and Re-entry Programs, 2020 ed.)</td><td>NFPA 2024 / 2020</td>' +
      '<td>Community mass-evacuation mobilization rate (design basis)</td><td><strong>' + _f(mobRate,2) + ' (constant)</strong></td></tr>\n' +
      '      <tr><td>' + _badge(8) + '</td><td><strong>U.S. Census ACS B25044</strong></td><td>2020 5-yr</td>' +
      '<td>Zero-vehicle household adjustment (~10%)</td><td>Incorporated in NFPA 1660 / 1616 mobilization constant</td></tr>\n' +
      '      <tr class="derived-row"><td>' + _badge('\u2192', true) + '</td><td colspan="2"><em>Formula result</em></td>' +
      '<td>\u0394T (marginal evacuation clearance time)</td><td><strong>' + _f(maxDt,2) + ' min</strong>' +
      (maxDt > 0 ? ' vs. ' + _f(threshold,2) + '-min limit' : '') + '</td></tr>\n' +
      '    </tbody>\n' +
      '  </table>\n' +
      '  <div style="margin-top:14px; font-size:11px; font-weight:700; letter-spacing:0.8px; text-transform:uppercase; color:#495057; margin-bottom:6px;">Core Formula</div>\n' +
      '  <div style="font-family:monospace; font-size:11px; background:#f1f3f5; padding:8px 12px; border-radius:4px; color:#212529; margin-bottom:12px; line-height:1.9;">' +
      '&#916;T = (project_vehicles / bottleneck_effective_capacity_vph) &times; 60 + egress_penalty<br>' +
      'project_vehicles = ' + units + ' units &times; ' + vpu + ' vpu &times; ' + _f(mobRate,2) + ' (NFPA 1660 / 1616 mobilization constant) = <strong>' + _f(projVph,0) + ' vph</strong><br>' +
      egresLine +
      'Flagged when &#916;T &gt; ' + _f(threshold,2) + ' min (threshold = ' + _f(safeWindow,0) + ' min &times; ' + Math.round(maxShare*100) + '%)' +
      '</div>\n' +
      '  <p style="margin:0 0 10px; font-size:11px; color:#6c757d; font-style:italic;">' +
      '    This determination applies the above authorities mechanically. No engineering judgment was exercised.' +
      '    The same methodology is applied uniformly to all projects under AB 747.' +
      '  </p>\n' +
      auditBlock + '\n' +
      '</div>';
  }

  // ── Scope & Limitations ───────────────────────────────────────────────────
  // Per the Fire Science Consulting LLC review of May 2026 (Ziazi & Simeoni),
  // every JOSH determination should explicitly acknowledge the 2025 California
  // Wildland-Urban Interface Code (CWUIC) and scope ΔT as a screening tool —
  // consistent with CWUIC Appendix C §C101.6 — rather than a standalone permit-
  // denial instrument. The concurrent inbound emergency-apparatus access
  // requirement of CCR 1273.00 is acknowledged but not modeled by the ΔT engine
  // (which evaluates civilian outbound capacity only).

  function _buildScopeAndLimitations(inp) {
    return '<h2 class="section-label">Scope &amp; Limitations</h2>\n' +
      '<div class="legal-authority-box" style="border-left:3px solid #c8951a; background:#fffbec;">\n' +
      '  <p style="margin:0 0 10px; font-size:12px; color:#212529; line-height:1.6;">' +
      '    <strong>Civilian outbound capacity only.</strong> JOSH measures the ΔT contribution of civilian vehicles ' +
      '    exiting the project on its serving evacuation routes. <strong>Concurrent emergency apparatus inbound access</strong>, ' +
      '    required by CCR 1273.00 of the <strong>2025 California Wildland-Urban Interface Code (CWUIC)</strong> ' +
      '    adopted by the State Fire Marshal, requires <strong>separate analysis</strong> that is outside the ' +
      '    scope of this determination.' +
      '  </p>\n' +
      '  <p style="margin:0 0 10px; font-size:12px; color:#212529; line-height:1.6;">' +
      '    <strong>Screening tool, not denial instrument.</strong> Consistent with <strong>CWUIC Appendix C ' +
      '    §C101.6</strong>, ΔT provides an initial idealized order-of-magnitude clearance estimate intended ' +
      '    to <em>trigger further review</em> under the Housing Accountability Act safety exception ' +
      '    (Gov. Code §65589.5(j)(1)). It is <strong>not a substitute</strong> for a full community evacuation ' +
      '    study and is not a standalone permit-denial instrument.' +
      '  </p>\n' +
      '  <p style="margin:0 0 0; font-size:11px; color:#6c757d; font-style:italic;">' +
      '    Methodology open items (independent traffic-engineering review by Fire Science Consulting LLC, ' +
      '    May 2026): hazard-degradation factor empirical derivation; CWUIC road-geometry pre-check ' +
      '    (CWUIC §§403.1, 403.3 — 20-ft / 26-ft minimums); shadow-evacuation and cumulative route ' +
      '    capacity tracking; δt(egress) for low-rise (IBC 2024 Ch. 10 + SFPE Handbook Ch. 64).' +
      '  </p>\n' +
      '</div>';
  }

  // ── Appeal rights ──────────────────────────────────────────────────────────

  function _buildAppealRights(inp) {
    var city = inp.city_name || 'City';
    return '<h2 class="section-label">Appeal Rights</h2>\n' +
      '<div class="appeal-box">\n' +
      '  <p style="margin:0 0 10px;">This determination is the result of an objective, algorithmic analysis under adopted city standards.' +
      ' All inputs, calculations, and threshold comparisons are recorded in the attached audit trail and are fully reproducible.</p>\n' +
      '  <p style="margin:0 0 10px;">An applicant who disagrees with this determination may appeal within <strong>10 business days</strong>' +
      ' of the date of this letter to the City of ' + _esc(city) + ' Planning Commission. The appeal must identify a specific factual error' +
      ' in the data inputs or threshold parameters. Engineering judgment is not a basis for appeal \u2014 these are objective standards.</p>\n' +
      '  <p style="margin:0;">For questions, contact the Planning Department. Reference the case number on this letter.</p>\n' +
      '</div>';
  }

  // ── Footer ─────────────────────────────────────────────────────────────────

  function _buildFooter() {
    return '<div class="brief-footer no-print">' +
      'JOSH &nbsp;&middot;&nbsp; Jurisdictional Objective Standards for Housing' +
      ' &nbsp;&middot;&nbsp; California Stewardship Alliance' +
      ' &nbsp;&middot;&nbsp; v4.0 &nbsp;&middot;&nbsp; AB 747 &nbsp;&middot;&nbsp; Gov. Code &sect;65302.15' +
      '</div>';
  }

  return { render: render };

}));

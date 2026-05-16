# JOSH Design Tokens

**Last updated:** 2026-05-16
**Source of truth:** `static/sidebar.js` + `static/brief_renderer.js` (inline CSS in the production JS bundles).

This reference exists so multi-hazard frontend work can compose against production styling without re-reading the JS bundles. Tokens here are extracted verbatim from those files — do not introduce new tokens here unless they also exist in (or are added to) the production source.

If a token here drifts from production, the production source wins; update this doc to match.

---

## Typography

| Token | Value | Used for |
|---|---|---|
| `--josh-font` | `system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` | All UI text |
| body font-size | `14px` / line-height `1.55` | Brief, sidebar |
| sidebar font-size | `13px` | `#josh-sidebar` (inline style) |
| section label | `11px` / weight `700` / letter-spacing `1.4px` / uppercase | `h2.section-label` in brief |
| stat big-num | `38px` / weight `800` in brief; `22px` / `700` in sidebar mini-stats | Tier callouts, project unit counts |
| label uppercase | `10px` / weight `700` / letter-spacing `1.2px` | Stat-card labels |

---

## Core palette

| Token | Hex | Used for |
|---|---|---|
| `--josh-navy` | `#1c4a6e` | `.brief-header`, sidebar header bar, big stat numbers, primary buttons |
| `--josh-red` | `#c0392b` | Section labels, DISCRETIONARY tier, accent borders |
| `--josh-orange` | `#d67c00` | MINISTERIAL_WITH_STANDARD_CONDITIONS tier |
| `--josh-green` | `#27ae60` | MINISTERIAL tier, pass chips |
| `--josh-text` | `#212529` | Body text |
| `--josh-muted` | `#868e96` | Secondary text, labels, table headers |
| `--josh-bg` | `#f8f9fa` | Page background, detail blocks, table header bg |
| `--josh-surface` | `#fff` | Cards, modals |
| `--josh-border` | `#dee2e6` | Card borders, table borders |
| `--josh-border-light` | `#e9ecef` | Section dividers, soft separators |
| `--josh-stat-bg` | `#f5f7fa` | Sidebar mini-stat cards |

---

## Tier palette

Per `brief_renderer.js` `TIER_COLOR` / `TIER_BG` / `TIER_BORDER`:

| Tier | bg | border | text |
|---|---|---|---|
| `DISCRETIONARY` | `#fdf2f2` | `#e8b4b0` | `#c0392b` |
| `MINISTERIAL WITH STANDARD CONDITIONS` | `#fffbf0` | `#f5d49a` | `#d67c00` |
| `MINISTERIAL` | `#f0faf4` | `#a8d5b8` | `#27ae60` |

Pattern: filled tier-bg surface with matching border (often `border-left: 4px` for inline tier lines, `border: 2px` for the brief's `.tier-pill`) and tier-fg for text.

---

## Result chips

Per `brief_renderer.js` `.chip-*` classes (used for per-standard pass/fail/scope/etc. in the brief):

| Chip | bg | text | Used for |
|---|---|---|---|
| `--chip-pass` | `#e8f5e9` | `#27ae60` | "PASS", "OK" results |
| `--chip-fail` | `#fdf2f2` | `#c0392b` | "FAIL" results |
| `--chip-triggered` | `#fff3cd` | `#856404` | Warning / triggered conditions |
| `--chip-na` | `#f1f3f5` | `#868e96` | Not-applicable |
| `--chip-scope` | `#e7f1ff` | `#1a56db` | Informational, "info only" pills |
| `.chip-controlling` | `#c0392b` (solid) | `#fff` (uppercase, tracked) | The multi-hazard controlling-hazard badge |

Pattern: `padding: 3px 10px`, `border-radius: 20px`, `text-transform: uppercase`, `letter-spacing: 0.06em`, `font-size: 10px`, `font-weight: 700`.

---

## Component patterns

### `.brief-header`
Navy header bar at top of the brief. `background: #1c4a6e; color: #fff; padding: 28px 36px;`. The multi-hazard modal mirrors this with `.modal-header`.

### `.stat-card`
White card with `border: 1px solid #dee2e6; border-radius: 6px; padding: 18px 16px; text-align: center;`. Houses big numbers and labels.

### `.tier-pill`
Inline tier badge. `display: inline-block; font-size: 22px; font-weight: 800; border-radius: 8px; padding: 10px 20px;` with tier-colored bg + 2px border.

### `.criteria-badge`
Square colored badge for A/B/C/D in the brief. `width/height: 26px; border-radius: 4px; color: #fff; font-size: 12px; font-weight: 800;`. Background set inline per criterion (typically `--josh-red` in the multi-hazard context).

### `.standard-row`
White rounded card. `background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 14px 16px; margin-bottom: 8px;`.

### `.detail-block`
Soft callout block. `background: #f8f9fa; border-radius: 5px; border-left: 3px solid #dee2e6; padding: 12px 14px; font-size: 12px;`. Used for the brief's "Hazards Excluded" section and any other informational callouts.

### Sidebar mini-stats
`background: #f5f7fa; border-radius: 6px; padding: 8px 10px; text-align: center;` with big nums `22px / 700 / #1c4a6e` and uppercase labels `10px / 700 / #888 / letter-spacing 0.04em`.

### Buttons
Production button style is small and understated: `border-radius: 4px; padding: 5px 10px; font-size: 12px; font-family: system-ui;`. Primary action buttons use `--josh-navy` fill with white text and uppercase tracked label.

### Inputs
`border: 1px solid #ccc; border-radius: 4px; padding: 5px 7px; font-size: 12px; font-family: system-ui;`. Focus state: `box-shadow: 0 0 0 2px rgba(28,74,110,0.18);` against the navy.

---

## Radii

| Token | Value | Used for |
|---|---|---|
| `--radius-sm` | `4px` | Buttons, inputs, small chips, `.criteria-badge` |
| `--radius-md` | `6px` | Cards, panels, mini-stats |
| `--radius-lg` | `8px` | Modal, `.tier-pill`, determination box |
| `--radius-pill` | `20px` | Result chips |

---

## Hazard polygon palette (multi-hazard locked)

Per `docs/multihazard_first_principles.md` §7.2. Locked — do not change without updating that doc and `docs/multihazard_status.md`.

| Hazard | Stroke / fill | Pattern |
|---|---|---|
| Wildfire | `#d62728` | Solid (existing FHSZ sub-zone palette already in production) |
| Flood (AE / A / AH) | `#1f77b4` | Solid, low opacity |
| Flood (VE coastal) | `#1f77b4` | Diagonal hatch |
| Tsunami | `#17becf` | Solid |
| Dam failure | `#9467bd` | Solid |
| Gas / hazmat (PIR) | `#bcbd22` + `#000` | Yellow/black diagonal hazard stripe |
| Landslide | `#8c564b` | Solid |
| Earthquake (informational) | `#7f7f7f` on `#d8d8d8` | Diagonal hatch, low opacity, **no AntPath option** |

---

## Where these tokens currently live in code

- **`static/brief_renderer.js`** — `_buildScreenCss()` and `_wrapHtml()` define `--josh-bg`, `--josh-text`, tier colors, chip palette, all brief component styles. `TIER_COLOR`, `TIER_BG`, `TIER_BORDER` maps near top.
- **`static/sidebar.js`** — inline `cssText` strings throughout `_buttonStyle()`, `_inputStyle()`, `_renderHeader()`, project card and stat-mini renderers. The sidebar font/size is set on `#josh-sidebar` directly (`13px` / `system-ui`).
- **Folium-baked HTML** (e.g. `output/berkeley/analysis_map.html`) — adds Leaflet plugin CSS (popup chrome, layer control, scale, marker clusters, AntPath). This is *not* JOSH-specific styling; it's third-party CSS that the JOSH UI lives on top of.

A future cleanup task could consolidate the tokens above into a single `static/josh-tokens.css` and remove the duplication between `sidebar.js` and `brief_renderer.js`. Not urgent — the duplication is small (≈30 lines per file) and each is the local truth for its own bundle.

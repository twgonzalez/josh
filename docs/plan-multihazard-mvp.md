# JOSH Multi-Hazard MVP — Implementation Plan

**Status:** Draft for review
**Date:** May 2026
**Author:** Multi-hazard work scaffold (companion to status doc + first-principles memo)

This plan defines the staged path from "wildfire-only JOSH + multi-hazard mockup" to "production-ready multi-hazard MVP." It assumes the architecture, decisions, and visual contract already locked in:

- `docs/multihazard_first_principles.md` — architecture (4-function HazardAdapter, two hazard classes)
- `docs/multihazard_status.md` — 8 locked decisions + current phase
- `docs/josh-design-tokens.md` — production design tokens used by Phase 7 UI
- `output/mockup/multihazard_on_berkeley.html` (branch `feature/multi-hazard`) — visual contract for the new UX

---

## 1. MVP Scope (user-confirmed 2026-05-16)

| Dimension | Decision |
|---|---|
| **Hazards** | Wildfire (refactor) + Flood + Tsunami + Dam failure + Gas/hazmat + Landslide. **Earthquake is out of scope entirely** — it does not impact ΔT and is not part of the multi-hazard determination. |
| **Frontend** | Migrate to right-side inspector panel per the mockup. Single-project dropdown, no marker popups, per-hazard ΔT bar chart, hazard scenario radio, A/B/C brief. |
| **Compatibility** | Feature-flagged. Per-city `multihazard: true` in `cities/{city}.yaml`. Wildfire-only cities keep working unchanged. |
| **Cities** | Berkeley (primary) + Encinitas (validates portability — coastal, has real tsunami + flood). |
| **Determination logic** | Worst-case single hazard drives tier; all hazards reported; controlling hazard named. Tsunami in-zone is dispositive at Standard 3. |

**Out of MVP scope** (deferred to follow-on):
- **Earthquake** — out of scope entirely; revisit only if a future legal mandate requires it
- Compound scenarios (fire-following-earthquake, tsunami-post-EQ, post-fire debris flow)
- Pedestrian evacuation model for near-field tsunami
- USGS NSHM probabilistic PGA raster
- Cities beyond Berkeley + Encinitas (Del Mar, Solana Beach, RSF FPD remain wildfire-only until promoted)

---

## 1.5 The mockup is DIRECTIONAL only

`output/mockup/multihazard_on_berkeley.html` shows the **shape** of the multi-hazard UX — hazard layers, per-hazard ΔT bars, dropdown selector, scenario radio, A/B/C brief. It is a hand-baked HTML overlay against the production Berkeley map; it is **not a complete UX specification**.

The following production features exist today, are not represented in the mockup, and **must be preserved through the MVP**:

| Feature | Where it lives today | MVP requirement |
|---|---|---|
| **Custom (browser-created) projects** | `static/sidebar.js` form + `WhatIfEngine` evaluation | Must work for multi-hazard projects too — what-if engine accepts a `hazard` parameter (or evaluates all applicable hazards per project) |
| **AntPath marching ants** | `static/sidebar.js` `_renderRoutes()` — animated dashed polylines | Per-hazard routes (`hazard_results[i].route_coords`) must render as marching ants when that scenario is selected |
| **Audit trail .txt download** | `static/sidebar.js` `_buildAuditText()` + `_downloadDetermination()` | Must produce per-hazard sections (Standard 3 zone classification per hazard, Standard 4 ΔT per hazard, controlling hazard line) |
| **Brief HTML save / print / PDF** | `static/brief_renderer.js` + browser print | Must render A/B/C with per-hazard tables, controlling row highlighted, print-friendly layout preserved |
| **Project CRUD (add / edit / delete)** | `static/sidebar.js` + FSAPI persistence (`window.showSaveFilePicker`) | All CRUD operations must round-trip the new `hazard_results` schema |
| **YAML export of project list** | `static/sidebar.js` YAML serializer | Must include per-project hazard inputs (any user-specified per-hazard parameters) |
| **Project re-analysis indicator** | `static/sidebar.js` "ℹ Re-analyzed — parameters updated" chip | Must fire when ANY adapter's parameters change (not just wildfire) |
| **Standard 1 size gate (`units >= 15`)** | `static/sidebar.js` + brief renderer | Unchanged — applies regardless of hazard |
| **Standard 2 route detection** | `agents/scenarios/wildland.py` Dijkstra | Per-hazard routing — same algorithm, hazard-specific graph |
| **Standard 5 SB 79 transit informational** | `agents/scenarios/sb79.py` | Unchanged — runs alongside hazard analysis |
| **Egress penalty for stories ≥ 4** | All scenarios | Unchanged — applies to every ΔT regardless of hazard |
| **Project pin home-icon visibility rule** | `static/sidebar.js` — pin shown only when project selected | Unchanged — applies to per-project FeatureGroups |
| **OSMnx edge geometry (real route curves, not straight lines)** | `agents/scenarios/wildland.py` `path_wgs84_coords` | Per-hazard routes must use real edge geometry, not node-endpoint-only |
| **Tier badge layout in brief** | `static/brief_renderer.js` `_buildTierBadgeBlock` | Tier badge + stat-cards + criteria badges preserved, with controlling-hazard naming added |

**MVP rule:** if a production feature isn't explicitly redesigned in this plan, it must continue to work end-to-end. Every stage PR runs the full existing test suite (see §13) and must pass without modification unless the change is explicitly scoped.

The mockup is the **visual contract** for the *new* surfaces only (hazard layer panel, ΔT bar chart, scenario radio, A/B/C per-hazard tables). For everything else, production today IS the spec.

---

## 2. Branch & merge strategy

```
main ─────────────────────────────────────────────────────────────────  (untouched)
        │
        └─ feature/multi-hazard ──┬─ feature/mhz-stage-0-baseline
                                  ├─ feature/mhz-stage-1-adapter
                                  ├─ feature/mhz-stage-2-schema
                                  ├─ feature/mhz-stage-3-flood
                                  ├─ feature/mhz-stage-4-frontend
                                  ├─ feature/mhz-stage-5-determination
                                  ├─ feature/mhz-stage-6-tsunami
                                  ├─ feature/mhz-stage-7-dam
                                  ├─ feature/mhz-stage-8-gas
                                  ├─ feature/mhz-stage-9-landslide
                                  ├─ feature/mhz-stage-10-encinitas
                                  └─ feature/mhz-stage-11-promote
                                                │
                                                ▼
                                    (final MVP replaces main when complete)
```

**Strict no-main-merges rule.** `feature/multi-hazard` is the long-lived umbrella branch and **nothing lands on `main` until the entire MVP is complete and ready to fully replace what's on main today**.

- **`feature/multi-hazard`** is the integration branch. Each stage's branch merges into it via PR.
- **Stage branches** are short-lived; PR review by user before merging up to `feature/multi-hazard`.
- **`main` stays untouched** for the duration of the MVP. The current wildfire-only system on main continues to ship to clients unchanged.
- **Final replacement:** when Stages 0–12 are all complete, validated on Berkeley + Encinitas, and methodology memos are signed off, `feature/multi-hazard` replaces `main` in a single coordinated operation (either fast-forward merge, branch swap, or PR with explicit go/no-go review — decision deferred to that point).
- Each stage PR updates `docs/multihazard_status.md` per the convention in §10 of that doc.
- CI runs anti-divergence + brief golden tests on every stage branch.

**Practical consequences:**
- Demo / preview deployments off `feature/multi-hazard` use a separate output directory (e.g. `output/multihazard/` or a preview subdomain) to avoid clobbering production output on main.
- The current `output/berkeley/analysis_map.html` on main does NOT get rebuilt with multi-hazard data until the final replacement. New multi-hazard builds write to `output/multihazard/berkeley/...` on the feature branch.
- This protects clients running production wildfire-only against any partial / in-progress multi-hazard state, and gives the MVP an integration runway without time pressure on each stage merge.

---

## 3. Stage 0 — Baseline merge ✅ ready

**Scope:** Merge the scaffold + mockup that already exists into main, so the workplan has a stable foundation.

**Already done** (committed on `feature/multi-hazard`):
- `docs/multihazard_first_principles.md` (architecture memo)
- `docs/multihazard_status.md` (locked decisions table)
- `docs/josh-design-tokens.md` (production tokens reference)
- `docs/multi_hazard_spec.md` (deprecation banner at top)
- `docs/plan-ab747-multihazard-research.md` (PIR-constant fix)
- `output/mockup/multihazard_on_berkeley.html` (working visual contract)
- `CLAUDE.md` pointer block (local-only, not gitignored content)
- `.claude/agents/multihazard-architect.md` (supervising agent definition)

**Acceptance:**
- [ ] `feature/multi-hazard` reviewed and confirmed as the umbrella branch (renamed from chip-created `claude/magical-blackburn-f0c875` 2026-05-16)
- [ ] Uncommitted main-side scaffold (status doc + first-principles + deprecation banner + this plan) committed onto `feature/multi-hazard` (NOT `main`)
- [ ] Status doc updated with merge confirmation
- [ ] Mockup file made discoverable from CLAUDE.md or a README on the feature branch
- [ ] `main` remains untouched

**Effort:** S (under a day)

**Risks:**
- The mockup file is 11.8MB. Consider gitignoring it or moving it to a release artifact rather than tracking in git long-term.

---

## 4. Stage 1 — `HazardAdapter` abstraction + `WildfireAdapter` refactor

**Scope:** Define the 4-function `HazardAdapter` protocol and refactor existing wildfire logic into it. Zero behavior change — pure structural refactor to enable stages 2+.

**Deliverables:**
- `agents/scenarios/base.py` — new `HazardAdapter` Protocol/ABC with the 4 methods (`classify`, `degradation`, `egress_window_min`, `mobilization`)
- `agents/scenarios/wildfire.py` — `WildfireAdapter` implementing the protocol, wrapping current `wildland.py` logic
- `static/whatif_utils.js` extended with a JS-side `HazardAdapter` shape (object with same 4 methods)
- `static/whatif_engine.js` regenerated to call `adapter.degradation(edge, zone)` etc. instead of inlining wildfire logic
- `tests/test_hazard_adapter_contract.py` — contract test that every adapter must pass (Python)
- `tests/test_whatif_engine.js` updated — runs the same contract against the JS adapter
- Anti-divergence test confirms WildfireAdapter Python output matches JS output bit-for-bit (no regression vs current `tests/test_whatif_engine.js`)

**Files touched:**
- New: `agents/scenarios/base.py` (or extend existing), `agents/scenarios/wildfire.py`, `tests/test_hazard_adapter_contract.py`
- Modified: `agents/scenarios/wildland.py` (now delegates to `WildfireAdapter`), `agents/export.py` (export adapter reference into JS engine source), `static/whatif_utils.js`
- Regenerated (not edited): `static/whatif_engine.js`, `static/v1/app.js`

**Dependencies:** none (kicks off the implementation work)

**Acceptance:**
- [ ] `WildfireAdapter` passes contract test
- [ ] All existing `tests/test_whatif_engine.js` pass with no diff in test vectors
- [ ] `tests/test_brief_renderer.js` and `tests/test_sidebar.js` pass unchanged
- [ ] Berkeley map regenerated and compared to current — every ΔT value identical
- [ ] No production behavior change visible to end users

**Effort:** M (3–5 days)

**Risks:**
- The current wildfire logic is spread across `wildland.py`, `objective_standards.py`, and inlined in `whatif_engine.js`. Refactor must preserve every numeric output. Snapshot test the current Berkeley `JOSH_DATA.briefs` and `analysis_map.html` ΔT values as the regression bar.

**Implements locked decisions:** #6 (4-function interface).

---

## 5. Stage 2 — `JOSH_DATA` schema v2 + feature flag

**Scope:** Extend the on-disk and in-browser data schema to carry multi-hazard fields, behind a per-city feature flag. No new hazards yet — schema is forward-compatible.

**Deliverables:**
- `JOSH_DATA.schema_version` bumped to `2`
- New fields on the data root: `applicable_hazards: string[]`, `hazard_polygons: { [hazard]: GeoJSON }`
- New fields per project: `hazard_results: HazardResult[]`, `controlling_hazard: string`
- `HazardResult` shape defined in TS-ish notation in `docs/multihazard_first_principles.md` §8.4 — write the canonical schema into a new `docs/josh-data-schema-v2.md`
- `agents/export.py` writes the new schema when `city.multihazard == True`; else writes v1 unchanged
- City config reads: `cities/{city}.yaml` gains optional `multihazard: bool` (default `false`)
- Browser engine (`static/whatif_engine.js`) reads `schema_version` and rejects with a clear console warning on mismatch — no silent corruption

**Files touched:**
- New: `docs/josh-data-schema-v2.md`, `agents/scenarios/multihazard.py` (orchestrator stub — receives adapter list, no logic yet)
- Modified: `agents/export.py`, `agents/visualization/analysis_map.py`, every city config schema validator, `static/whatif_utils.js` (schema check helper)
- Regenerated: `static/whatif_engine.js`, `static/v1/app.js`

**Dependencies:** Stage 1 complete (needs `HazardAdapter` to define `hazard_results` shape)

**Acceptance:**
- [ ] `cities/berkeley.yaml` with `multihazard: false` produces byte-identical `JOSH_DATA` to current (regression-tested via JSON diff)
- [ ] `cities/berkeley.yaml` with `multihazard: true` produces v2 schema with only `WildfireAdapter` results populated, `hazard_polygons.flood = {}`, etc.
- [ ] JS engine emits a console warning if v2 data loads in a browser running v1 code (forward-compatibility safeguard)
- [ ] `tests/test_whatif_engine.js` covers both schemas

**Effort:** M (3–5 days)

**Risks:**
- Schema versioning is one-way. Adding fields is fine; removing or renaming is not. Make the v2 schema as future-proof as possible — name fields after their conceptual role, not the hazard.
- The existing `JOSH_DATA.briefs` pre-baked HTML strings need a plan: either (a) remove them entirely and rely on `BriefRenderer.render()` at view time, or (b) bake one brief per hazard combination. Pick (a) for simplicity unless brief HTML production becomes too slow.

**Implements locked decisions:** #7 (controlling hazard structure), #8 (A/B/C/D format requires schema support).

---

## 6. Stage 3 — `FloodAdapter` (network-cutting reference impl)

**Scope:** First new hazard. Exercises every architectural element that wildfire doesn't: network-cutting via factor=0, BFE-elevation exit filter, depth-dependent degradation. Validates the abstraction before scaling out to other hazards.

**Deliverables:**
- `agents/scenarios/flood.py` — `FloodAdapter` per first-principles memo §3 row
- `josh-pipeline/agents/data_acquisition.py` — `fetch_nfhl_zones(city)` returning `S_FLD_HAZ_AR` GeoJSON for the city boundary
- `josh-pipeline/agents/data_acquisition.py` — `fetch_dem(city)` for USGS 3DEP elevation (10m raster, cached)
- Per-segment elevation sampling in the graph build (joins to DEM at edge midpoints; sets `node_elevation_ft` on each graph node)
- Exit-node validity filter: drops nodes where `node_elev < BFE + 0.5 ft` inside SFHA polygons
- Per-edge degradation factor lookup keyed off FEMA zone (AE/A/AH=0.20, AO=0.35, VE=0.00, X=1.00)
- `data/{city}/flood_sfha.geojson` and `flood_dem.tif` cached with 90-day TTL per existing policy
- `cities/berkeley.yaml` gains `multihazard: true` for testing
- Browser side: JS `FloodAdapter` in `static/whatif_engine.js` (regenerated from `agents/export.py`)

**Files touched:**
- New: `agents/scenarios/flood.py`, `josh-pipeline/agents/data_acquisition.py` flood fetchers, `tests/test_flood_adapter.py`
- Modified: `agents/scenarios/multihazard.py` (registers `FloodAdapter`), `agents/export.py` (emits flood JS), `cities/berkeley.yaml`, `josh-pipeline/cities/berkeley.yaml`
- Pipeline data: `data/berkeley/flood_sfha.geojson`, `data/berkeley/flood_dem.tif` (gitignored, 90-day cache)

**Dependencies:** Stages 1 + 2 complete

**Acceptance:**
- [ ] `uv run python build.py analyze --city "Berkeley"` succeeds with `multihazard: true`
- [ ] Generated `JOSH_DATA.hazard_polygons.flood` contains real FEMA NFHL features for Berkeley (verify against `msc.fema.gov` viewer for spot-check)
- [ ] For at least one Berkeley project, the flood `ΔT` differs from the wildfire `ΔT` (proves the adapter is doing different work)
- [ ] Anti-divergence test: Python `FloodAdapter.degradation(edge, zone)` matches JS to 6 decimal places for 1000 random edges
- [ ] Brief modal renders Section B and C rows for flood with real values
- [ ] Manual visual review: open Berkeley map with multihazard=true, confirm flood polygons visible, hazard checkbox toggles, brief shows flood data

**Effort:** L (1–2 weeks)

**Risks:**
- USGS 3DEP DEM download is large (≈1GB raw for Berkeley quadrangle). Decision: store as cached COG (cloud-optimized GeoTIFF) and crop to city boundary before persistence. Cache size budget per city: 200MB.
- LIDAR-derived DTM is more accurate than 3DEP 10m for shallow flooding. Document this as a known limitation; LIDAR upgrade is a follow-on.
- Bridges crossing SFHA on elevated structure must NOT trigger the BFE filter. Honor OSM `bridge=yes` tag (already in the graph for production wildfire routing).

**Implements locked decisions:** #5 (FloodAdapter first), #6 (4-function works for network-cutting).

---

## 7. Stage 4 — Frontend Phase 7 (right-sidebar migration)

**Scope:** Move the sidebar from production left-side to the mockup's right-side inspector pattern. Add the multi-hazard UX elements (hazard layer panel, dropdown, per-hazard ΔT bar chart, scenario radio, A/B/C/D brief) into real production code.

**Deliverables:**
- `static/sidebar.js` heavily revised:
  - `#josh-sidebar` repositioned `right: 0` (CSS already keyed off inline style; change pipeline-emitted style block)
  - New `_renderHazardLayerPanel()` function (toggles hazard polygon FeatureGroups on the map)
  - `_renderProjectList` replaced with `_renderProjectDropdown` — same data, different control
  - `_renderProjectDetail` augmented with: `_renderDeltaTBarChart(project)`, `_renderHazardScenarioRadio(project)`, `_renderHazardsEvaluatedList(project)`
  - Marker click handler updated: no popup, just `selectProject(id)`
- `static/brief_renderer.js` extended:
  - New `_buildSectionBPerHazard(hazardResults)` and `_buildSectionCPerHazard(hazardResults)` table builders
  - New `_buildSectionDExcluded(excludedHazards)` block
  - Determination card refactor: names controlling hazard, uses tier-pill pattern
- `agents/visualization/analysis_map.py` — emits the right-side sidebar position for multihazard=true cities
- `tests/test_brief_renderer.js` extended: vectors covering 1-hazard, 2-hazard, 3-hazard (with informational)
- `tests/test_sidebar.js` extended: dropdown change, hazard checkbox toggle, scenario radio change

**Files touched:**
- Modified: `static/sidebar.js`, `static/brief_renderer.js`, `static/whatif_utils.js`, `agents/visualization/analysis_map.py`, `agents/visualization/popup.py` (if exists — remove popup logic)
- Modified tests: `tests/test_brief_renderer.js`, `tests/test_sidebar.js`
- Regenerated: `static/v1/app.js`

**Dependencies:** Stages 1, 2, 3 complete (needs real flood data flowing through schema)

**Acceptance:**
- [ ] Berkeley map with `multihazard: true` renders right-side sidebar with all mockup elements visible
- [ ] All existing tests pass (no regression on wildfire-only Berkeley with `multihazard: false`)
- [ ] Visual diff against `output/mockup/multihazard_on_berkeley.html` — same colors, same layout, same component patterns
- [ ] Marker click selects project; no popup opens
- [ ] Brief modal renders A/B/C/D with controlling-hazard row highlighted, opens above `#josh-header`
- [ ] Hazard scenario radio swaps the visible AntPath (uses per-hazard `route_coords` from `hazard_results`)
- [ ] Test coverage ≥ 80% for new render functions in sidebar.js

**Effort:** L (1–2 weeks)

**Risks:**
- The sidebar.js file is 2200+ lines of dense, working production code. Diff size for this stage will be large; consider sub-staging (4a: layer panel, 4b: dropdown, 4c: ΔT chart, 4d: brief renderer A/B/C/D).
- Right-side sidebar may conflict with Leaflet's default zoom/layer-control positioning. Confirm Leaflet `topright` and `bottomright` controls don't collide with the panel.
- Mobile/narrow-viewport behavior — production currently doesn't handle this; add a `@media (max-width: 768px)` rule to make the sidebar a bottom drawer? Or defer to a follow-on.

**Implements:** the chip-approved right-side / dropdown / no-popup UX patterns recorded in `multihazard_first_principles.md` §7.3.

---

## 8. Stage 5 — Multi-hazard determination logic + Berkeley feature-flag flip

**Scope:** Wire the worst-case-single-hazard tier logic; flip Berkeley's `multihazard: true` on main; promote MVP behind feature flag.

**Deliverables:**
- `agents/scenarios/multihazard.py` `evaluate_multihazard(project, adapters, graph, parameters)` per first-principles memo §5.3 pseudocode
- `controlling = max(results.values(), key=lambda r: r.delta_t / r.threshold)`
- Determination tier mapping:
  - any `r.delta_t > r.threshold` → DISCRETIONARY (with controlling hazard named)
  - all pass + size gate met → MINISTERIAL WITH STANDARD CONDITIONS
  - size gate not met → MINISTERIAL
- JS-side mirror in `static/whatif_engine.js` (regenerated)
- Anti-divergence test covers the determination logic specifically
- Berkeley pipeline now produces multi-hazard `JOSH_DATA` with flood data alongside wildfire
- One pipeline command produces the Berkeley demo end-to-end

**Files touched:**
- Modified: `agents/scenarios/multihazard.py` (orchestrator with real logic), `agents/objective_standards.py` (delegates to multihazard evaluator when flag set), `static/whatif_engine.js` (regenerated), `cities/berkeley.yaml` (flag flipped on)
- New: `tests/test_multihazard_determination.py`

**Dependencies:** Stages 1–4

**Acceptance:**
- [ ] Re-running `acquire.py run --city "Berkeley"` produces a multi-hazard map with at least one project where the tier is driven by flood, not wildfire (assuming Berkeley has enough SFHA exposure — if not, document and fall back to test-only)
- [ ] Determination letter for each Berkeley project names the controlling hazard
- [ ] Tier distribution across all Berkeley projects matches the manually-computed expected distribution from a spreadsheet sanity-check
- [ ] Anti-divergence: Python and JS produce identical controlling-hazard selection for 100 randomized synthetic projects
- [ ] `feature/mhz-stage-5-determination` PR merged into `feature/multi-hazard` (NOT `main`). Multi-hazard reaches the umbrella branch behind the per-city flag.

**Effort:** M (3–5 days)

**Risks:**
- Berkeley may have no SFHA-exposed projects, in which case flood is always non-controlling and we can't validate the controlling-hazard-flips logic in a real city. Mitigation: hand-add a fake project in `projects/berkeley_demo.yaml` near Aquatic Park / marina (real SFHA AE zone) to exercise the flow. Document this as "demo project" with disclaimer.

**Implements locked decisions:** #7 (worst-case single hazard, all reported, controlling named).

---

## 9. Stages 6–9 — Remaining hazard adapters (parallel-safe)

Each stage adds one adapter using the same template as `FloodAdapter`. These can be done in parallel by different sessions / contributors, but each must merge into `feature/multi-hazard` independently.

### Stage 6 — `TsunamiAdapter` (Standard-3-dispositive)

**Scope:** Tsunami is the special case — in-zone triggers DISCRETIONARY at Standard 3 alone, Standard 4 ΔT reported as informational only (locked decision #2).

**Deliverables:**
- `agents/scenarios/tsunami.py` — `TsunamiAdapter` per first-principles memo §3
- Pipeline fetcher for CGS Tsunami Hazard Area (item `2769c700c0694548b5435a60ff52b807` on ArcGIS)
- `evaluate_multihazard` extended to honor `adapter.is_dispositive_at_standard_3` flag — when true and zone-classify returns in-zone, force DISCRETIONARY without running Standard 4
- Brief modal renders tsunami row in Section B but skips the ΔT calculation row in Section C, showing instead "Dispositive at Standard 3 — in CGS Tsunami Hazard Area"
- `data/encinitas/tsunami_zone.geojson` cached

**Effort:** M (3–5 days)

**Acceptance:**
- [ ] Test fixture: project at coastal Encinitas address (in CGS THA) → tier = DISCRETIONARY, controlling hazard = Tsunami, no ΔT shown
- [ ] Same project not in THA but ≤ 1km away → tier driven by other hazards, ΔT computed normally

### Stage 7 — `DamFailureAdapter`

**Scope:** DSOD inundation polygons + EAP arrival-time defaults.

**Deliverables:**
- `agents/scenarios/dam_failure.py` — `DamFailureAdapter` (binary zone, per-dam egress window)
- Pipeline fetcher: download DSOD shapefile from Berkeley GeoData mirror; spatial join to find dams affecting the city
- `dam_arrival_times.yaml` template + Berkeley-specific values (manually curated from EAPs for San Pablo Dam, Briones, Lafayette upstream of Berkeley)
- Egress window default fallback: 30 min (<5 mi), 120 min (5–50 mi) per first-principles memo §3

**Effort:** L (1–2 weeks — EAP data acquisition is manual)

### Stage 8 — `GasHazmatAdapter`

**Scope:** NPMS pipelines + PIR buffer (using **0.69** constant, decision #3).

**Deliverables:**
- `agents/scenarios/gas_hazmat.py` — `GasHazmatAdapter`
- Pipeline fetcher: NPMS Public Viewer scrape OR PIMMA-account API (if obtained)
- PIR computation: `0.69 × sqrt(P_psig × D_in^2)` ft, buffered around pipeline centerlines
- Default PIR of 660 ft when MAOP/diameter not available (HCA Method 2 conservative fallback)

**Effort:** L (1–2 weeks — PHMSA data access is the blocker)

**Risks:**
- NPMS public viewer is rate-limited and doesn't expose MAOP/diameter. If PIMMA account isn't available, this adapter ships with a uniform 660 ft PIR and documents the limitation.

### Stage 9 — `LandslideAdapter`

**Scope:** Storm-triggered debris flow only. USGS post-fire products + CGS EILZ.

**Deliverables:**
- `agents/scenarios/landslide.py` — deterministic 0.50 factor for segments in EILZ + post-fire DF basins
- 60-min egress window (NWS debris flow warning lead time minus realistic mobilization lag)
- Pipeline fetcher: USGS post-fire DF hazard layers (per burn scar within 50 mi of city) + CGS EILZ

**Effort:** M (3–5 days)

**Risks:**
- USGS post-fire products are per-fire-event and have a TTL (~3 years after burn). Need cache-invalidation logic tied to burn date.

---

## 10. Stage 10 — Encinitas onboarding

**Scope:** Validate the architecture on a second city with different hazard exposure.

**Deliverables:**
- `cities/encinitas.yaml` with `multihazard: true`
- Pipeline run for Encinitas: wildfire (already done) + flood (San Elijo Lagoon SFHA) + tsunami (CGS THA covers the coastal strip) + dam (Lake Hodges upstream) + landslide (CGS EILZ in coastal bluffs)
- Gas/hazmat: skip if Encinitas has no NPMS transmission lines within the boundary (check first)
- Encinitas demo map output: `output/encinitas/analysis_map.html` regenerated with multi-hazard
- Visual review against Berkeley demo — confirm right-sidebar + brief + polygons look right with different geography

**Files touched:**
- Modified: `cities/encinitas.yaml`, `josh-pipeline/cities/encinitas.yaml`, `projects/encinitas_demo.yaml` (may need to hand-add an in-THA project)
- New data: `data/encinitas/{flood_sfha,tsunami_zone,dam_inundation,landslide_zone}.geojson`

**Dependencies:** Stages 1–9 complete (every adapter must work)

**Acceptance:**
- [ ] At least one Encinitas project is tsunami-controlled (in THA)
- [ ] At least one Encinitas project is flood-controlled (in San Elijo SFHA)
- [ ] Determination letters render correctly for both
- [ ] No code changes needed — this is pure config + data acquisition. If code changes ARE needed, treat as a Stage 1–9 regression and fix there.

**Effort:** M (3–5 days)

**Implements:** the portability claim. If Stage 10 surfaces architectural changes, the MVP isn't actually ready.

---

## 11. Stage 11 — Methodology memos + legal review

**Scope:** Document the methodology decisions for legal defensibility. Required before any client deliverable references the multi-hazard determination.

**Deliverables:**
- `docs/methodology/flood_methodology_statement.md` — following the `mobilization_rate_methodology_statement.md` template
- `docs/methodology/tsunami_methodology_statement.md`
- `docs/methodology/dam_failure_methodology_statement.md`
- `docs/methodology/gas_hazmat_methodology_statement.md`
- `docs/methodology/landslide_methodology_statement.md`
- Per-hazard mobilization memos (Phase 2 from research plan) — 5 memos
- Updated `docs/JOSH_PE_Technical_Brief.md` with multi-hazard methodology section
- Updated `docs/JOSH_Legal_Defensibility_Memo.md` covering each hazard's statutory basis
- Statutory gap analysis matrix (§65302(g) vs. JOSH coverage) — `docs/multihazard_statutory_gap.md`

**Effort:** L (2–3 weeks — these are research deliverables, not code)

**Dependencies:** Stages 6–9 (each adapter's parameters must be settled before its memo can lock them)

**Acceptance:**
- [ ] Each methodology memo cites specific authoritative sources (FEMA, USGS, CGS, PHMSA, NIST, NOAA per the first-principles memo §10)
- [ ] PE Technical Brief includes per-hazard PE-stamped methodology sign-off
- [ ] Legal Defensibility Memo covers the controlling-hazard determination logic specifically

---

## 12. Stage 12 — Promote multi-hazard from flag to default

**Scope:** Multi-hazard becomes the default for all new cities; existing wildfire-only cities are migrated one at a time on their next pipeline run.

**Deliverables:**
- `cities/*.yaml` default changes to `multihazard: true`
- Migration guide: `docs/multihazard_migration.md` — explains what cities need to add (hazard data fetchers, project YAML updates if any)
- Per-city checklist for Del Mar, Solana Beach, RSF FPD
- Final regression: all 5 active cities regenerated with multi-hazard, every existing wildfire ΔT value unchanged (since wildfire logic is unchanged from Stage 1)
- Status doc updated: "Multi-hazard MVP complete"

**Dependencies:** Stages 1–11 complete; Encinitas demo published; PE methodology memos signed off

**Acceptance:**
- [ ] All 5 cities ship multi-hazard determinations
- [ ] No wildfire-only code paths remain (feature flag removed from `agents/objective_standards.py`)
- [ ] `cities/*.yaml` schema documentation updated to reflect that `multihazard` is no longer optional

**Effort:** M (3–5 days assuming no surprises from Stages 1–11)

---

## 13. Testing strategy (cross-cutting)

### 13.1 The existing production test suite is the integration baseline

The four files below are the authoritative behavioral contract for everything the current production system does. **Every stage PR must keep all four green**. Any change to an existing test requires explicit reviewer sign-off and a snapshot/baseline update; new tests get added freely.

| Test file | What it covers today | MVP relationship |
|---|---|---|
| **`tests/test_whatif_engine.js`** | Anti-divergence: Python `WildlandScenario` vs JS `WhatIfEngine` produce identical ΔT outputs for the same project inputs. Reads `tests/test_vectors.json` generated by `build.py analyze`. | Extend test_vectors.json to include per-hazard inputs; every adapter gets its own anti-divergence sweep. JS engine must accept `hazard` parameter and return identical results to Python per-hazard. |
| **`tests/test_brief_renderer.js`** | Brief HTML correctness for all 3 tiers, including stat-cards, criteria badges, route tables, tier-pill rendering, print CSS. | Extend with multi-hazard test vectors: 1-hazard / 2-hazard / N-hazard cases. **Stage 0 baseline:** snapshot every existing brief output before any code changes; that becomes the wildfire-only regression bar. |
| **`tests/test_sidebar.js`** | Project CRUD (add/edit/delete), BriefInput mapping (sidebar → BriefRenderer), audit trail text generation, FSAPI persistence round-trip, YAML export, dirty-state tracking. | Extend to cover per-hazard data flowing through CRUD: a project's `hazard_results[]` round-trips through FSAPI save/load; audit trail produces per-hazard sections; YAML export preserves hazard inputs. |
| **`tests/test_project_manager.js`** | Legacy project manager (superseded by sidebar.js for active projects). | Keep passing unchanged unless a stage explicitly migrates one of its capabilities into sidebar.js. |

**Pre-Stage-1 baseline snapshot.** Before any Stage 1 code touches production code paths, run all four test suites and snapshot:
- `tests/snapshots/baseline/test_vectors.json` (current Berkeley what-if outputs)
- `tests/snapshots/baseline/briefs/{project}.html` (current brief HTML per Berkeley project)
- `tests/snapshots/baseline/audit/{project}.txt` (current audit trail per Berkeley project)
- `tests/snapshots/baseline/sidebar_state.json` (current sidebar state after seed-project hydration)

Stage 1's HazardAdapter refactor must reproduce these snapshots byte-for-byte (modulo timestamps). If any output drifts, the refactor is incorrect — fix the refactor, do not update the snapshot.

### 13.2 Contract tests per adapter
Every `HazardAdapter` subclass passes a generic contract test (`tests/test_hazard_adapter_contract.py`):
- `classify(point)` returns a string from a documented set of zone names
- `degradation(edge, zone)` returns a float in [0, 1]
- `egress_window_min(zone)` returns a positive number
- `mobilization(zone)` returns a float in [0, 1]
- Behavior is deterministic (call twice with same inputs → same outputs)
- All four methods callable on a hand-rolled fixture without external data (so contract tests run offline)

### 13.3 Anti-divergence tests (extends test_whatif_engine.js)
For each adapter, extend the existing anti-divergence pattern: Python writes `tests/test_vectors_{hazard}.json` during `build.py analyze`; JS test loads it and confirms its computation matches per row. Tolerance: 1e-6 for floats, exact for strings. **The pattern is already in use for wildfire — every new adapter follows the same template, no new test infrastructure needed.**

### 13.4 Brief golden-file tests (extends test_brief_renderer.js)
New test vectors added per stage:
- After Stage 1: wildfire-only-via-new-adapter (must match Stage 0 baseline byte-for-byte)
- After Stage 3: wildfire + flood (both applicable, both with results)
- After Stage 6: tsunami in-zone (Section B row present, Section C row replaced with "Dispositive at Standard 3")
- After Stage 9: every adapter applicable (Encinitas-like maximal case)
- Controlling-hazard switches under what-if parameter changes (verifies the determination logic in the renderer)

### 13.5 Visual regression
After each stage, regenerate Berkeley (+ Encinitas from Stage 10) maps; visually diff against the previous stage's screenshots using `mcp__Claude_Preview__preview_screenshot`. Stage owners commit baseline screenshots into `docs/screenshots/stage-N/`. Diff threshold: ≤ 1% pixel change without explicit reviewer note.

### 13.6 Determination snapshots
For Berkeley's 4 seeded projects, snapshot the tier + controlling hazard + ΔT per hazard in `tests/snapshots/berkeley_determinations.json`. Every stage compares against this; any unintentional change requires explicit snapshot update + reviewer approval. Same pattern for Encinitas from Stage 10.

### 13.7 Test-run convention
The status quo for running JS tests is:
```bash
node --test tests/test_whatif_engine.js
node --test tests/test_brief_renderer.js
node --test tests/test_sidebar.js
node --test tests/test_project_manager.js
```
Stage PRs must include a CI configuration that runs all four on every push. Python tests follow the existing `uv run pytest` convention.

---

## 14. Documentation deliverables (cross-cutting)

Per stage, the PR description includes:
- Which locked decisions it implements
- Status doc checkbox flipped
- Migration notes for downstream code if API changed
- Screenshot or recorded interaction if frontend-touching

At MVP completion:
- `docs/multihazard_status.md` final state: phase = "Complete", all decisions enacted
- `docs/multihazard_first_principles.md` updated with any architectural learnings
- `docs/josh-design-tokens.md` updated with any new tokens introduced
- `CLAUDE.md` multi-hazard pointer updated from "active" to "shipped — see X"

---

## 15. Effort summary

| Stage | Effort | Calendar (1 person, focused) |
|---|---|---|
| 0 — Baseline merge | S | 1 day |
| 1 — HazardAdapter refactor | M | 1 week |
| 2 — Schema v2 + flag | M | 1 week |
| 3 — FloodAdapter | L | 2 weeks |
| 4 — Frontend right-sidebar | L | 2 weeks (sub-stage if too big) |
| 5 — Determination + flip | M | 1 week |
| 6 — TsunamiAdapter | M | 1 week |
| 7 — DamFailureAdapter | L | 2 weeks |
| 8 — GasHazmatAdapter | L | 2 weeks |
| 9 — LandslideAdapter | M | 1 week |
| 10 — Encinitas | M | 1 week |
| 11 — Methodology memos | L | 3 weeks |
| 12 — Promotion | M | 1 week |
| **Total** | | **~18 weeks (4.5 months)** |

Parallelizable: Stages 6–9 (adapters) can run concurrently after Stage 5. Stage 11 (memos) can start as each adapter ships. With 2 contributors, MVP could complete in 3 months. With 1 contributor and other priorities, 5–6 months is realistic.

---

## 16. Risks & open questions

### 16.1 Data acquisition is the long pole
NPMS (gas), DSOD (dam), USGS 3DEP (flood DEM) all require either screen-scrapers or special access. Recommend starting the data-access work in parallel with Stage 1, not waiting until each adapter's stage.

### 16.2 Frontend stage size
Stage 4 is the biggest single piece of work (sidebar.js + brief_renderer.js are both 2000+ lines, both heavily modified). Sub-stage breakdown if needed:
- 4a: Layer panel + hazard polygon layer toggling
- 4b: Dropdown selector + no-popup behavior
- 4c: Per-hazard ΔT bar chart + scenario radio
- 4d: Brief renderer A/B/C/D

### 16.3 Test vectors
Anti-divergence relies on having a "ground truth" — but for multi-hazard, the Python and JS implementations are both being written. Pick one as authoritative (recommend Python) and snapshot its output as the JS test vector.

### 16.4 Backwards compatibility timeline
If a client running production wildfire-only code is on a fixed cadence, the feature flag lets us stage carefully. But once Stage 12 promotes multi-hazard to default, the wildfire-only code paths get deleted. Make sure no client has a contract pinning them to the wildfire-only output before promoting.

---

## 17. What we still need before kicking off Stage 1

1. **User sign-off on this plan** — confirm scope, branch strategy, effort estimates are acceptable
2. **Stage 0 acceptance** — confirm the existing 8 commits on `feature/multi-hazard` represent the baseline; main remains untouched
3. **Status doc update** — add a "MVP plan" row pointing at this doc; flip the "next up" list to mirror Stage 1 first task
4. **Snapshot the current Berkeley determinations** as the regression baseline for Stage 1

---

## 18. Reference documents

- `docs/multihazard_first_principles.md` — architecture
- `docs/multihazard_status.md` — locked decisions + current phase
- `docs/plan-ab747-multihazard-research.md` — research plan (parent of this implementation plan)
- `docs/josh-design-tokens.md` — production design tokens
- `docs/multi_hazard_spec.md` — deprecated (banner at top)
- `output/mockup/multihazard_on_berkeley.html` — visual contract for Stage 4
- `.claude/agents/multihazard-architect.md` — supervising agent for executing this plan

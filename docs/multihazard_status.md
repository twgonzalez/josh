# Multi-Hazard Extension — Status

**Last updated:** 2026-05-17
**Phase:** Stage 0.5 — Production parity + all-6-hazards mock UI. Phase A (flag removal) ✅ shipped; Phase B (CRUD migration) + Phase C (all 6 hazards) in flight.
**Supervising agent:** `.claude/agents/multihazard-architect.md`
**MVP plan:** `docs/plan-multihazard-mvp.md`
**Active stage:** Stage 0.5 (3 phases: A=flag removal, B=CRUD migration, C=all-6-hazards mocks)
**Schema contract:** `docs/josh-data-schema-v2.md` (Stage 1+ gospel)

This document is the single source of truth for where the multi-hazard work stands. Any session working on multi-hazard items must read this first and update it before closing the work.

---

## How to use this doc

1. **Starting a new session?** Read this file, then `docs/multihazard_first_principles.md`, then the relevant block of `docs/plan-ab747-multihazard-research.md`. That's the canonical reading order.
2. **About to make a change?** Check the Locked Decisions table below. If your change would violate one of them, stop and confirm with the user before proceeding.
3. **Finishing a piece of work?** Update this doc as part of the same PR: flip the checkbox, move the "In-flight" entry to "Completed," log any new decisions in the table.
4. **Need orchestration?** Invoke the supervising agent with `Agent(subagent_type: "multihazard-architect", ...)` and it will read this doc, pick the next workplan item, and dispatch.

---

## Locked decisions

These were settled in conversation and are binding unless the user explicitly overrides them. New sessions inherit these — do not re-litigate.

| # | Decision | Rationale | Source |
|---|----------|-----------|--------|
| 1 | **Earthquake is OUT OF SCOPE entirely.** Not part of the multi-hazard determination, the brief, the audit trail, the map UI, or the data schema. No polygon overlay, no Section D, no MMI label, no PE-stamped overlay treatment. | Earthquake has no pre-event clearance window; the ΔT framework doesn't fit. The earlier "informational overlay" treatment was removed because it adds UI complexity without changing any tier determination — clean separation is preferable. Earthquake site assessment continues to live under its own statutory regime (PRC §§2621, 2690) outside JOSH. KLD Engineering's 2024 Berkeley AB 747 report sets precedent for this scope-out. | `docs/multihazard_first_principles.md` §2 note, §6 rec. #2 |
| 2 | **Treat tsunami "in CGS Tsunami Hazard Area" as dispositive at Standard 3 → DISCRETIONARY.** Standard 4 ΔT is reported as informational only for tsunami. | 15-minute design window × 5% project share = 45-second ΔT threshold. Any non-trivial in-zone project fails Standard 4 deterministically, providing zero gradation. Vehicle ΔT is also not the right life-safety model for near-field tsunami — USGS Pedestrian Evacuation Analyst is the appropriate parallel framework. | `docs/multihazard_first_principles.md` §3, §6 rec. #3 |
| 3 | **PIR constant = 0.69, not 0.004.** Canonical formula: `PIR (ft) = 0.69 × √(P_psig × D_in²)` per PHMSA TTO-13 (2005) and 49 CFR §192.903. | The `0.004` value in `plan-ab747-multihazard-research.md` §5D is incorrect — produces a buffer ~170× too small. **Fix in the plan doc before any pipeline data work begins.** | `docs/multihazard_first_principles.md` §3 footnote, §6 rec. #4 |
| 4 | **Mobilization stays ≥ 0.90 for every hazard.** Design-for-what-should-happen argument. Tsunami = 1.00, dam = 0.95, gas = 0.95, all others = 0.90. | Roads fail under high-mobilization events, not low. A planning standard calibrated to observed non-compliance only "passes" when residents disobey the order — not a life-safety standard. Generalizes the wildfire mobilization argument across hazards. | `docs/multihazard_first_principles.md` §4 |
| 5 | **Build `FloodAdapter` first.** It exercises every new architectural element (network-cutting, BFE-elevation exit filter, depth-dependent degradation) against the most mature regulatory data (FEMA NFHL). | If FloodAdapter works end-to-end, the remaining hazards are parameter swaps against the same code paths. Validates the `HazardAdapter` abstraction before scaling out. | `docs/multihazard_first_principles.md` §6 rec. #1 |
| 6 | **4-function `HazardAdapter` interface** (not 5 as in the plan's §7.1). | Exit-node validity is a Boolean projection of degradation — an exit is invalid iff every incident edge has capacity 0, which Dijkstra discovers automatically. Collapses the plan's 5-function form. | `docs/multihazard_first_principles.md` §1, §5.1 |
| 7 | **Worst-case single hazard drives the tier; all applicable hazards reported.** Plan §9 policy decision #3. | More transparent than controlling-only output. Controlling hazard MUST be named in the determination letter — a tier with no stated cause is the failure mode that invites legal challenge. | `docs/multihazard_first_principles.md` §5.3, §8.1 |
| 8 | **Determination output format expands A/B/C → A/B/C/D.** B and C become per-hazard tables; D = "Hazards Excluded" (informational overlays). | Per-hazard transparency in the brief; preserves the legal posture of fully algorithmic determinations. | `docs/multihazard_first_principles.md` §8.2 |
| 9 | **Multi-hazard sidebar sits on the right side of the map** (inspector pattern), not the left. Flag-gated — production wildfire-only cities keep the left sidebar. Move Leaflet zoom control to `topleft` to free the right edge. | The mockup keeps the sidebar on the left because it overlays production; the inspector pattern in `multihazard_first_principles.md` §7.3 specifies right. Confirmed by user 2026-05-17 during Stage 0 planning. | `docs/multihazard_first_principles.md` §7.3; `docs/plan-multihazard-stage-0.md` §7.1 |
| 10 | **Stage 0 is a UI-first prototype phase, not a baseline merge.** Build the production sidebar + brief renderer against a normalized mock fixture (`static/multihazard_fixtures.js`) **before** any Python adapter code. Schema is ratified by working JS code, then handed to Stage 1 Python as the regression target. | The prior 1-day "merge the scaffold" framing would have let Stage 1 design data shapes around the mockup's hardcoded `wf:`/`fl:` keys and the production FHSZ-specific coupling. Front-loading the schema decisions under mock data avoids paying refactor cost again at Stage 3 (FloodAdapter). | `docs/plan-multihazard-stage-0.md` §1, §4 |
| 11 | **`HazardResult` is a tagged union with one named variant per hazard.** `WildfireResult`, `FloodResult`, `TsunamiResult`, `DamFailureResult`, `GasHazmatResult`, `LandslideResult` each have explicit hazard-specific fields; `type` is the discriminator. Renderers dispatch via `switch (result.type)` with 6 cases in exactly 4 named functions: `_renderHazardBarRow`, `_renderHazardListItem`, `BriefRenderer._renderBRow`, `BriefRenderer._renderCRow`. No flag-based hidden dispatch (no `if r.dispositive` on a generic shape — `dispositive: true` is structurally part of `TsunamiResult` only). No `result.type === 'X'` checks outside the 4 switch sites. | With 6 finite hazards each carrying genuinely different physics (flood needs BFE + node elevation; dam needs per-feature arrival times; gas needs computed PIR buffer; tsunami is dispositive), a semi-abstract schema (uniform shape + optional fields) hides where the hazard logic lives without saving any real code. Explicit tagged unions buy debuggability + type safety + grep-ability at the bounded cost of 6 switch cases per consumer. The 4-function `HazardAdapter` interface (decision #6) still holds at the orchestrator call sites — but the *return types* are hazard-specific. | `docs/plan-multihazard-stage-0.md` §4.0, §4.2, §4.2.1 |

---

## Phase progress

Mirrors `docs/plan-ab747-multihazard-research.md` §8. Update as work lands.

### Phase 1 — Statutory and regulatory research
- [x] First-principles architecture memo (`docs/multihazard_first_principles.md`)
- [x] Per-hazard metrics research (flood, tsunami, dam, gas, landslide, earthquake) — synthesized into the memo
- [x] KLD Berkeley precedent for earthquake scope-out
- [ ] Statutory gap analysis matrix (§65302(g) vs. current JOSH coverage)
- [ ] OPR Technical Advisory scope confirmation (fire-only vs. multi-hazard)
- [ ] Legal defensibility memo: which hazards require quantitative ΔT vs. narrative
- [ ] Precedent review: cities challenged on multi-hazard Safety Element adequacy

### Phase 2 — Mobilization rate research
- [ ] Flood compliance literature review → memo
- [ ] Tsunami compliance literature review → memo (covers near-field design basis)
- [ ] Gas/hazmat compliance literature review → memo
- [ ] Dam failure compliance literature review → memo
- [ ] Landslide / debris flow compliance literature review → memo
- [ ] Unified mobilization framework document (extends `docs/mobilization_rate_methodology_statement.md`)

### Phase 3 — Per-hazard data and parameter research
- [x] Flood (NFHL API, depth-capacity curves, egress window) — synthesized in memo §3
- [x] Tsunami (CGS THA, Cascadia timing) — synthesized in memo §3
- [x] Dam failure (DSOD inundation, EAP arrival times) — synthesized in memo §3
- [x] Gas/hazmat (PIR formula confirmed at 0.69) — synthesized in memo §3
- [x] Landslide (USGS post-fire, CGS EILZ) — synthesized in memo §3
- [x] Earthquake (HAZUS, NBI, ShakeOut — confirmed scope-out is correct) — synthesized in memo §3
- [ ] Per-adapter data acquisition prototypes in `josh-pipeline`

### Phase 4 — Architecture and prototype
- [ ] `HazardAdapter` abstract base class (4-function interface per decision #6) — Stage 1
- [ ] `WildfireAdapter` refactor (existing logic moved into adapter pattern) — Stage 1
- [ ] Exit-node validity filter (generalized — falls out of `degradation == 0` per decision #6) — Stage 3
- [ ] `FloodAdapter` prototype (first new hazard; validates architecture per decision #5) — Stage 3
- [ ] Multi-hazard determination logic (`evaluate_multihazard()`) — Stage 5
- [x] **Updated `JOSH_DATA` schema for multi-hazard results** ✅ Stage 0 — see `docs/josh-data-schema-v2.md`
- [ ] `WhatIfEngine` accepts `hazard` parameter — Stage 1 (deferred from Stage 0; mock fixture drives UI today)

### Phase 5 — Parameter documentation and legal review
- [ ] Methodology statement per hazard (template: `docs/mobilization_rate_methodology_statement.md`)
- [ ] Validation prompt per hazard (template: WPI validation prompt structure)
- [ ] Updated PE Technical Brief covering multi-hazard methodology
- [ ] Updated Legal Defensibility Memo

### Phase 6 — Remaining adapters and testing
- [ ] `TsunamiAdapter` (Standard-3-dispositive per decision #2)
- [ ] `DamFailureAdapter`
- [ ] `GasHazmatAdapter` (PIR = 0.69 per decision #3)
- [ ] `LandslideAdapter` (storm-triggered only)
- [ ] Anti-divergence tests per adapter (JS + Python parity)
- [ ] Multi-hazard demo map for a city with ≥ 2 applicable hazards

### Phase 7 — Visualization and reports (added in `multihazard_first_principles.md` §7–8)
- [x] **Hazard palette implementation** ✅ Stage 0 — `agents/visualization/themes.py` (WILDFIRE/FLOOD constants)
- [x] **Hazard layer panel in `static/sidebar.js`** ✅ Stage 0 Step 8
- [x] **Per-project hazard bar chart in sidebar evaluation card** ✅ Stage 0 Steps 12-13
- [x] **Hazard scenario selector (radio group → swaps visible AntPath)** ✅ Stage 0 Steps 18-20
- [ ] Per-hazard route pre-baking in `agents/export.py` — Stage 3+ (mock route_coords drive Stage 0)
- [ ] Popup HTML per-hazard table — deferred; right sidebar replaces popup workflow (locked decision #9)
- [x] **`BriefRenderer` A/B/C/D template; per-hazard tables; controlling-hazard highlight** ✅ Stage 0 Steps 21-23
- [ ] `_buildAuditText()` rewritten for per-hazard sections — Stage 4+ (production CRUD deferred from Stage 0)
- [x] **`BriefInput` schema expanded (`hazard_results[]`, `controlling_hazard`)** ✅ Stage 0 — `docs/josh-data-schema-v2.md` §5,§7
- [x] **`tests/test_brief_renderer.js` covers 1/2/3-hazard cases** ✅ Stage 0 Step 24 (3 v2 vectors, 20 tests total)
- [ ] `tests/test_whatif_engine.js` covers per-hazard parity — Stage 1+ (anti-divergence vs Python adapters)

---

## Recently completed (this session)

| Item | Outcome | Date |
|---|---|---|
| PIR constant fix in `plan-ab747-multihazard-research.md` §5D (decision #3) | Replaced `0.004` with `0.69` (per PHMSA TTO-13, 2005; 49 CFR §192.903). Inline note flags the prior incorrect value. | 2026-05-16 |
| Stage 0 expanded into UI-first prototype plan | `docs/plan-multihazard-stage-0.md` — 28-step incremental build sequence; locks right-side sidebar (decision #9); adds tsunami-dispositive mock fixture to validate decision #2 rendering before TsunamiAdapter ships. Supersedes the 1-day baseline-merge framing in `plan-multihazard-mvp.md` §3. | 2026-05-17 |
| Schema design pivot: tagged-union per-hazard result types (decision #11) | After surfacing the per-hazard data requirements (BFE for flood, per-feature arrival times for dam, computed PIR for gas, dispositive for tsunami, TTL for landslide), reversed earlier "fully abstract renderer" stance. Plan §4.0 now documents per-hazard data requirements; §4.2 rewrites `hazard_results[]` as discriminated union; §4.2.1 documents the 4-switch-site renderer rule; §6.3 steps 12/13/15/17/22 updated to switch-based per-case implementation order. | 2026-05-17 |
| **Stage 0 — UI prototype with mock data — COMPLETE** ✅ | All 28 steps shipped on `feature/multi-hazard`. 22 commits. Production v1 byte-identical to baseline (flag off). v2 mode delivers: right sidebar, Hazard Layers panel + JS polygon rendering, project dropdown, marker-popup suppression, detail card with stat cards + tier banner + per-hazard ΔT bar chart + Hazards Evaluated list + scenario radio + Open Brief button, mock fixtures (4 real + 2 hand-crafted: cedar_st_bayfront_mock flood-controlling, marina_pointe tsunami-dispositive), narrow-viewport bottom drawer. Brief renderer: v1/v2 schema branching + per-hazard B/C tables + Section D excluded + controlling-hazard footer with dispositive variant. Canonical schema doc `docs/josh-data-schema-v2.md` ratified. **All 107 JS tests pass** (27 hazard_polygon_layer + 80 production including 3 new v2 brief vectors). | 2026-05-17 |
| **Stage 0.5 Phase A — flag removal** ✅ | Retires the `multihazard: bool` city-config field. Pipeline always emits v2 schema + hazard_polygons; sidebar.js always injects the right-side multi-hazard shell; legacy Folium FHSZ render block deleted; app.js schema check tightened to v2-only; left-sidebar div no longer emitted by Python. v1 brief input shape retained inside `brief_renderer.js` only so the 17 v1 brief tests stay green — no runtime path passes v1 input. All 110 JS tests pass. | 2026-05-17 |
| **Stage 0.5 Phase B (first cut) — CRUD migration** ✅ | Production CRUD now drives the multi-hazard right sidebar. `_sb()` points at `#josh-sidebar-mhz`; `_render()` writes to scoped containers (project-panel for dropdown + `+ New`/`Open…` toolbar, project-detail for form OR multi-hazard detail card). `_renderProjectDropdownPanel` reads from `_projects` (production state). `init()` runs at sidebar-inject time, populating `_projects` from JOSH_DATA seeds + localStorage; preserves `evaluation` + `is_mock` fields on each project. Detail card gains Edit/Delete buttons above Open Brief (hidden for pipeline + mock projects). Form renders inline with map-click pin placement. **Deferred (Phase B polish):** brief actions chevron menu (Save HTML/Print/Audit .txt), re-analyzed indicator chip, FSAPI restore banner. | 2026-05-17 |
| **Stage 0.5 Phase C — all 6 hazards lit up** ✅ | Themes.py vocab for dam_failure (purple) / gas_hazmat (burnt-orange) / landslide (brown). Three new mock polygons in `JOSH_DATA.hazard_polygons`: San Pablo Dam inundation across W. Berkeley flats; PG&E I-80 PIR buffer strip; CGS EILZ across the Berkeley hills. `marina_pointe` extended from 3 to 6 hazard_results (tsunami still controls; 3 new are informational). `_renderHazardBarRow` + `_renderHazardListItem` switch cases for the 3 new types delegate to the standard renderer — hazard-specific data (joined dam names, "In PIR (660 ft) — natural gas", EILZ label) baked into shared fields per the Phase C PAUSE design picks. Visual stress test confirms the 6-row bar chart + 6-row Hazards Evaluated list fit within sidebar vertical budget. All 110 JS tests pass. | 2026-05-17 |

## In-flight

Work currently dispatched but not yet landed. Each entry: title, owner (session/agent/PR), what's being produced, when dispatched.

| Item | Owner | Producing | Dispatched |
|---|---|---|---|
| WhatIfEngine hazard parameter design doc | Chip | `docs/plan-whatif-multihazard-param.md` | 2026-05-16 |

> **Mockup status:** the standalone UI/UX mockup gate (`output/mockup/multihazard_on_berkeley.html`) is **superseded** by Stage 0 implementation (`docs/plan-multihazard-stage-0.md`). The mockup remains the visual contract reference; further frontend approval happens incrementally as Stage 0 steps land, not at a single checkpoint.

---

## MVP scope (locked 2026-05-16, see `plan-multihazard-mvp.md` §1)

- **Hazards:** Wildfire (refactor) + Flood + Tsunami + Dam + Gas/hazmat + Landslide. **Earthquake is out of scope entirely** (no overlay, no UI, no schema).
- **Frontend:** Migrate to right-side inspector panel per mockup. The mockup is **directional only** — many production features (custom projects, marching ants, audit trails, brief PDF/print, project CRUD, FSAPI, YAML export, etc.) are not represented in it but must be preserved through the MVP. See `plan-multihazard-mvp.md` §1.5.
- **Compatibility:** Feature-flagged via per-city `multihazard: true` in `cities/{city}.yaml`.
- **Cities:** Berkeley + Encinitas in MVP demo.
- **Branch:** `feature/multi-hazard` long-lived umbrella; stage branches merge into it. **Nothing lands on `main` until the entire MVP is complete and ready to fully replace what's on main today.**
- **Test suite as integration guide:** the four existing production test files (`tests/test_whatif_engine.js`, `test_brief_renderer.js`, `test_sidebar.js`, `test_project_manager.js`) must stay green through every stage PR. See `plan-multihazard-mvp.md` §13.

## Next up

**Active stage: 0 (UI-first prototype with mock data).** Dispatch in step order per
`docs/plan-multihazard-stage-0.md` §6.3. The supervising agent picks up the lowest-numbered
unstarted step.

### Stage 0 step queue (next ≈ 14 working days)

1. **Step 1 — Baseline snapshot.** Capture current Berkeley pipeline outputs into `tests/snapshots/baseline/`. Regression bar for every later step.
2. **Step 2 — `multihazard` flag plumbing + `schema_version: 2` emit.** No visible change.
3. **Step 3 — `HazardPolygonLayer` JS module.** Refactor existing FHSZ render to use it; no behavior change.
4. **Step 4 — Emit `JOSH_DATA.hazard_polygons.wildfire`.** Renderer reads new path when flag on.
5. **Step 5 — Mock flood polygon to `hazard_polygons.flood`.** Bayfront fake visible via legacy layer control.
6. **Step 6 — Hide left sidebar; show empty right shell when flag on.**
7. **Step 7 — Move Leaflet zoom to topleft when flag on.**
8. **Step 8 — Hazard Layers panel (replaces Folium auto-control).**
9. **Step 9 — Project dropdown panel.**
10. **Step 10 — Suppress marker popups; click → `selectProject(id)`.**
11. **Step 11 — Load `static/multihazard_fixtures.js`; merge `hazard_results[]` onto projects.**
12. **Step 12 — Project detail card + per-hazard ΔT bar chart (wildfire only).**
13. **Step 13 — Extend fixture with flood `hazard_results[]` for all 6 real projects.**
14. **Step 14 — Tier banner with controlling-hazard footer.**
15. **Step 15 — Hazards Evaluated list.**
16. **Step 16 — Inject `cedar_street_infill` (flood-controlling) mock project.**
17. **Step 17 — Inject `marina_pointe` (tsunami-dispositive) + `_renderDispositive` treatment.**
18. **Step 18 — Hazard scenario radio (no behavior yet).**
19. **Step 19 — Stub mock `route_coords` per hazard in fixture.**
20. **Step 20 — Wire scenario change → re-`_drawRoutes()`.**
21. **Step 21 — `BriefRenderer` schema branching (v1 path unchanged).**
22. **Step 22 — Section B/C per-hazard tables.**
23. **Step 23 — Section D excluded hazards + determination footer.**
24. **Step 24 — Brief renderer tests for v2 cases.**
25. **Step 25 — Narrow-viewport media query.**
26. **Step 26 — Leaflet attribution placement check.**
27. **Step 27 — Write `docs/josh-data-schema-v2.md`.**
28. **Step 28 — Status doc updates + Stage 0 PR review.**

See `docs/plan-multihazard-stage-0.md` §6.3 for full per-step scope, files touched, and
verification criteria. §6.4 has the dependency graph and parallelization opportunities.

### Stages 1–12 (after Stage 0 closes)

The original MVP stage order remains the umbrella plan — see `docs/plan-multihazard-mvp.md` for full detail:

1. **Stage 1 — HazardAdapter abstraction + WildfireAdapter refactor.** Python adapter ABC; target schema = the ratified Stage 0 fixture shape.
2. **Stage 2 — JOSH_DATA schema v2 + feature flag.** (Largely consumed by Stage 0; remaining work is hardening the flag for non-Berkeley cities.)
3. **Stage 3 — FloodAdapter.** First real hazard data; inherits `cedar_street_infill` fixture as regression target.
4. **Stage 4 — Frontend Phase 7.** (Largely consumed by Stage 0; remaining work is replacing mock fixtures with adapter output.)
5. **Stage 5 — Multi-hazard determination logic + Berkeley flag flip.**
6. **Stages 6–9 — Tsunami, Dam, Gas, Landslide adapters** (parallelizable). Stage 6 inherits `marina_pointe` fixture as regression target.
7. **Stage 10 — Encinitas onboarding.**
8. **Stage 11 — Methodology memos.**
9. **Stage 12 — Promote multi-hazard from flag to default.**

The supervising agent dispatches these. See `.claude/agents/multihazard-architect.md`.

---

## PR convention

Every PR for multi-hazard work must:

1. Update this file (`docs/multihazard_status.md`) in the same PR — flip the relevant checkbox, move "In-flight" to "Completed," log any new locked decisions.
2. Reference the locked-decision number(s) it relies on or extends in the PR description.
3. If introducing a new decision (one that future sessions should respect), add a row to the Locked Decisions table with rationale and source.

This is enforceable as a PR review checklist item but not by hook today — until enforcement is automated, it's a convention the supervising agent verifies.

---

## Related documents

- `docs/plan-multihazard-stage-0.md` — **active stage plan** (28-step UI-first prototype with mock data)
- `docs/plan-multihazard-mvp.md` — umbrella implementation plan (12 stages, ~18 weeks, MVP definition)
- `docs/plan-ab747-multihazard-research.md` — research plan (the territory)
- `docs/multihazard_first_principles.md` — architecture memo (the map)
- `docs/josh-design-tokens.md` — production design tokens for Phase 7 UI
- `docs/mobilization_rate_methodology_statement.md` — template for per-hazard mobilization memos
- `output/mockup/multihazard_on_berkeley.html` — visual contract (superseded by Stage 0 implementation; retained as reference)
- `.claude/agents/multihazard-architect.md` — supervising agent definition
- `CLAUDE.md` — entry-point pointer

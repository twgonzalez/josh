# Multi-Hazard Extension — Status

**Last updated:** 2026-05-16
**Phase:** Pre-MVP (scaffold + mockup complete; MVP implementation plan ready in `docs/plan-multihazard-mvp.md`; awaiting Stage 0 merge)
**Supervising agent:** `.claude/agents/multihazard-architect.md`
**MVP plan:** `docs/plan-multihazard-mvp.md`

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
- [ ] `HazardAdapter` abstract base class (4-function interface per decision #6)
- [ ] `WildfireAdapter` refactor (existing logic moved into adapter pattern)
- [ ] Exit-node validity filter (generalized — falls out of `degradation == 0` per decision #6)
- [ ] `FloodAdapter` prototype (first new hazard; validates architecture per decision #5)
- [ ] Multi-hazard determination logic (`evaluate_multihazard()`)
- [ ] Updated `JOSH_DATA` schema for multi-hazard results
- [ ] `WhatIfEngine` accepts `hazard` parameter — see in-flight task spawn below

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
- [ ] Hazard palette implementation (`agents/visualization/`)
- [ ] Hazard layer panel in `static/sidebar.js`
- [ ] Per-project hazard bar chart in sidebar evaluation card
- [ ] Hazard scenario selector (radio group → swaps visible AntPath)
- [ ] Per-hazard route pre-baking in `agents/export.py`
- [ ] Popup HTML per-hazard table
- [ ] `BriefRenderer` A/B/C/D template; per-hazard tables; controlling-hazard highlight
- [ ] `_buildAuditText()` rewritten for per-hazard sections
- [ ] `BriefInput` schema expanded (`hazardResults[]`, `controllingHazard`, `excludedHazards`)
- [ ] `tests/test_brief_renderer.js` covers 1/2/3-hazard cases
- [ ] `tests/test_whatif_engine.js` covers per-hazard parity

---

## Recently completed (this session)

| Item | Outcome | Date |
|---|---|---|
| PIR constant fix in `plan-ab747-multihazard-research.md` §5D (decision #3) | Replaced `0.004` with `0.69` (per PHMSA TTO-13, 2005; 49 CFR §192.903). Inline note flags the prior incorrect value. | 2026-05-16 |

## In-flight

Work currently dispatched but not yet landed. Each entry: title, owner (session/agent/PR), what's being produced, when dispatched.

| Item | Owner | Producing | Dispatched |
|---|---|---|---|
| WhatIfEngine hazard parameter design doc | Chip | `docs/plan-whatif-multihazard-param.md` | 2026-05-16 |
| Multi-hazard UI/UX mockup (Phase 7 gate — user-requested checkpoint) | Chip | `output/mockup/multihazard_mockup.html` | 2026-05-16 |

> **User gate:** the UI/UX mockup is an explicit user-approval checkpoint. No further frontend work (sidebar, popup, brief renderer, AntPath, etc.) ships until the user reviews and approves the mockup.

---

## MVP scope (locked 2026-05-16, see `plan-multihazard-mvp.md` §1)

- **Hazards:** Wildfire (refactor) + Flood + Tsunami + Dam + Gas/hazmat + Landslide. **Earthquake is out of scope entirely** (no overlay, no UI, no schema).
- **Frontend:** Migrate to right-side inspector panel per mockup. The mockup is **directional only** — many production features (custom projects, marching ants, audit trails, brief PDF/print, project CRUD, FSAPI, YAML export, etc.) are not represented in it but must be preserved through the MVP. See `plan-multihazard-mvp.md` §1.5.
- **Compatibility:** Feature-flagged via per-city `multihazard: true` in `cities/{city}.yaml`.
- **Cities:** Berkeley + Encinitas in MVP demo.
- **Branch:** `feature/multi-hazard` long-lived umbrella; stage branches merge into it. **Nothing lands on `main` until the entire MVP is complete and ready to fully replace what's on main today.**
- **Test suite as integration guide:** the four existing production test files (`tests/test_whatif_engine.js`, `test_brief_renderer.js`, `test_sidebar.js`, `test_project_manager.js`) must stay green through every stage PR. See `plan-multihazard-mvp.md` §13.

## Next up (MVP stage order — see `plan-multihazard-mvp.md` for full detail)

1. **Stage 0 — Baseline merge.** Land the existing scaffold + mockup on main (worktree `claude/magical-blackburn-f0c875` + uncommitted main-side docs).
2. **Stage 1 — HazardAdapter abstraction + WildfireAdapter refactor.** Pure structural refactor, zero behavior change. Effort: M.
3. **Stage 2 — JOSH_DATA schema v2 + feature flag.** Forward-compatible schema bump behind per-city flag.
4. **Stage 3 — FloodAdapter.** First new hazard. Validates network-cutting + BFE exit filter against real FEMA NFHL data.
5. **Stage 4 — Frontend right-sidebar migration.** sidebar.js + brief_renderer.js extended per the mockup visual contract.
6. **Stage 5 — Multi-hazard determination logic + Berkeley feature-flag flip.** First main-line merge of multi-hazard.
7. **Stages 6–9 — Remaining adapters** (Tsunami, Dam, Gas, Landslide — parallelizable).
8. **Stage 10 — Encinitas onboarding.** Validates portability.
9. **Stage 11 — Methodology memos.** Per-hazard memos, legal defensibility, PE technical brief update.
10. **Stage 12 — Promote multi-hazard from flag to default.** All cities migrate; feature flag retired.

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

- `docs/plan-multihazard-mvp.md` — **implementation plan** (12 stages, ~18 weeks, MVP definition)
- `docs/plan-ab747-multihazard-research.md` — research plan (the territory)
- `docs/multihazard_first_principles.md` — architecture memo (the map)
- `docs/josh-design-tokens.md` — production design tokens for Phase 7 UI
- `docs/mobilization_rate_methodology_statement.md` — template for per-hazard mobilization memos
- `output/mockup/multihazard_on_berkeley.html` — visual contract for Stage 4 frontend (on worktree branch `claude/magical-blackburn-f0c875` until Stage 0 merges)
- `.claude/agents/multihazard-architect.md` — supervising agent definition
- `CLAUDE.md` — entry-point pointer

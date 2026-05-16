# Plan: Route Display UX Redesign

**Status:** Ready to implement
**Version:** v1
**Date:** 2026-05-15
**Author:** Thomas Gonzalez
**Depends on:** `feat/all-viable-routes` branch (engine + brief data layer)
**Related:** [JOSH_Legal_Defensibility_Memo.md §3.6, §8.6](JOSH_Legal_Defensibility_Memo.md)

---

## Background

The all-viable-routes feature (branch `feat/all-viable-routes`) surfaces every
viable evacuation route a project's evacuees might self-select. Under the
User Equilibrium methodology adopted by the legal framework, this is the
correct engine output — every route is evidence of evacuee behavior, and the
worst-case route binds the determination.

The current UI undermines the legal premise it's built on. Two user concerns
identified post-implementation:

1. **Overlapping routes are visually confusing.** Routes share segments at
   the bottleneck. Stacking 13 lines at varying opacities produces a busy
   visual that's hard for a council member or developer to parse.

2. **Per-route green/red coloring invites the alternative-route argument.**
   When the developer sees a route colored green ("passes"), they reach for
   the obvious objection: "Use the green route." That objection is precisely
   what the methodology rejects — the legal memo §8.6 dismantles it at length.
   The UI is inviting the very argument the memo defeats.

These are not engine bugs. The engine correctly implements User Equilibrium
— it returns every viable route, and the determination uses the worst as the
binding constraint. The data layer is right. The visual layer is the
problem.

This plan redesigns the route display to match the methodology's framing:
**routes are evidence, not options; one route binds; the others are context.**

---

## Methodology

### The principle from adjacent fields

This is a "binding constraint + context" visualization problem. Every safety
analysis tradition handles it the same way:

- **Fault tree / FMEA:** highlight the limiting failure mode; show
  contributors as faint structure.
- **Traffic engineering studies:** highlight the bottleneck corridor; show
  alternatives only when discussing system capacity.
- **Floodplain mapping:** worst-case extent prominent, secondary scenarios as
  overlays.
- **Medical imaging:** the diagnostic finding is focal; surrounding tissue is
  faint context.

The pattern is **one focal element + faint context**, with the focal element
clearly labeled as the binding case. Not "all candidates as equals" with
individual pass/fail color codes.

### What the legal framework says routes are

From `JOSH_Legal_Defensibility_Memo.md` §3.6:

> The sidebar's per-route toggle list lets reviewers hide routes on the
> interactive map for clarity; the determination always uses the full set.

And §8.6:

> Under User Equilibrium, drivers self-select the route they perceive as
> fastest. Evacuees distribute across all viable routes. Some take the slow
> route. *Their* evacuation delay is what the ΔT calculation measures.

Routes are: (a) **evidence** of evacuee behavior, (b) **inputs** to the
determination, and (c) for the planner, **inspection targets** to verify
the analysis. Routes are *not*: alternatives the developer can select, or
options the city is offering. The UI must communicate (a), (b), (c) and
must not communicate the other framing.

### Three coordinated design changes

#### 1. Default view: only the controlling route is drawn on the map.

The route with the highest ΔT — the binding constraint for the
determination — renders prominently. All other viable routes are not drawn
by default. A sidebar header toggle ("Show all viable routes (13)") reveals
the others on demand.

**Why:** Removes the visual clutter that makes overlapping routes confusing.
Anchors the map in the legal-record artifact: the controlling route is *the
thing the determination is about*. The other 12 are inspection targets, not
default content.

#### 2. Color semantics move from route to project.

Routes are drawn in a single neutral color (`#1c4a6e`, the existing JOSH
brand navy used in the tier banner background and sidebar dot for selected
projects). The controlling route is distinguished by *thickness and a gold
halo*, not by color. Pass/fail color (red/orange/green) lives where it
belongs: on the project tier banner.

**Why:** A developer cannot point at a "green route" and argue "use that one"
when no route is colored green. The determination is project-level, so
pass/fail color is project-level. The visual hierarchy still surfaces the
controlling route (thicker, haloed) without implying the other routes are
"failing."

#### 3. Educational note above the route list, sourced from §8.6.

A persistent two-sentence note at the top of the sidebar route panel:

> *Routes shown are paths evacuees may self-select during an evacuation
> (User Equilibrium). The determination uses the worst-case route because
> some evacuees will take it — slower routes do not "fix" faster ones.*

Optionally followed by a "Learn more" link to a /docs anchor that opens
§3.6 + §8.6 in a modal or new tab.

**Why:** Answers the developer's question where the question gets asked.
Pre-empts the alternative-route objection in the UI itself, not in a separate
legal document. Validates the question without losing the answer.

---

## Resolved Design Decisions

The conversation that produced this plan resolved several open questions.
Recorded here so the implementation isn't revisited.

| Decision | Choice |
|---|---|
| Default visibility | Only the controlling route. Other 12 hidden behind toggle. |
| Controlling-route visual | Gold/amber halo (underlying wider polyline at lower opacity) + main route at full thickness in navy. |
| Per-route color | Removed. All routes uniform navy (`#1c4a6e`). |
| Project tier color | Unchanged. Still red (DISCRETIONARY) / orange (CONDITIONAL) / green (MINISTERIAL) on the tier banner. |
| Sidebar toggle list | Kept. Per-route eye toggles still work, but routes are hidden by default — toggles act on whichever routes are currently in scope. |
| Brief table | Drop per-row color. Keep CONTROLLING row class. Add framing paragraph above table. |
| State persistence | Per-session, per-project (like `_routeToggles`). Each project starts in default view; switching projects resets. |

---

## Scope of Changes

### `static/sidebar.js`

| Change | Lines |
|---|---|
| New state variable: `const _showAllRoutes = new Map();` (per-project). | 1 |
| New helper: `_controllingPath(paths)` — returns `max(paths, key=delta_t)`. | ~6 |
| `_drawRoutes()`: replace per-route opacity hierarchy with controlling-route + halo + optional context routes. Drop the `pathColor = ok ? '#27ae60' : '#e74c3c'` line; use uniform navy. | ~25 |
| `_drawRoutes()`: when `_showAllRoutes.get(projectId)` is true, draw non-controlling routes in same navy at lower opacity (0.45) and weight 2. Halo only on controlling route. | (covered above) |
| `_renderDetail()`: add educational note block above the route list. Two short sentences + optional info icon. | ~12 |
| `_renderDetail()`: add the "Show all viable routes (N)" toggle at the route-list header. Calls a new `joshSidebar_toggleShowAll(projectId)`. | ~10 |
| `_renderDetail()`: route cards: remove per-card color border. All cards neutral; controlling card distinguished by a thin gold left border + "CONTROLLING ROUTE" badge. | ~15 |
| New global: `window.joshSidebar_toggleShowAll = id => { ... }`. | ~6 |
| `selectProject()`: clear `_showAllRoutes.delete(prior)` on switch. | 1 |
| `_resetState()`: also clear `_showAllRoutes`. | 1 |
| Module export: add `_showAllRoutes`, `_controllingPath` for tests. | ~3 |

**Approximate total:** ~80 lines changed, ~10 lines deleted (the old
green/red color computation and the old opacity-by-index logic).

### `static/brief_renderer.js`

| Change | Lines |
|---|---|
| Above the route table (Criterion C), insert a framing paragraph: "Routes shown are paths evacuees may self-select. The determination uses the worst-case route because some evacuees will take it. Slower routes do not 'fix' faster ones. See §3.6 Route Selection Methodology." (Wording subject to a final pass.) | ~6 |
| Route table rows: drop per-row text color tied to `flagged` for ΔT and Margin columns. Keep the colors only on the CONTROLLING row. All other rows render in neutral dark gray. | ~8 |
| The "Result" status column wording: change "EXCEEDS" / "within" to "controlling" / "—" — both factually accurate, neither implying route-level pass/fail. (Open question: keep both wordings as a tooltip for power users?) | ~6 |
| Summary line above table (already exists in v4.12): unchanged. | 0 |

**Approximate total:** ~20 lines changed.

### `static/whatif_engine.js` and `agents/export.py` JS string

No change. The engine is correct — it returns all viable routes with
correct ΔT and bottleneck identification. The redesign is purely
presentational.

### `agents/visualization/demo.py`

No change. JOSH_DATA already contains everything the redesign needs
(path_id, cost_s, delta_t, flagged, bottleneck details, path_coords).

### Tests

| File | Change |
|---|---|
| `tests/test_sidebar.js` | Add S33–S35: `_controllingPath()` selects max-ΔT path; `_showAllRoutes` toggle state machine; educational note presence in `_renderDetail()` output. ~30 lines. |
| `tests/test_brief_renderer.js` | Add T15: framing paragraph appears above Criterion C table; T16: per-row colors removed except for CONTROLLING row. ~20 lines. |
| `tests/test_whatif_engine.js` | No change — engine behavior unchanged. |
| `tests/test_project_manager.js` | No change. |

### Documentation

| File | Change |
|---|---|
| `CLAUDE.md` | "Brief / popup labeling convention" section: note that routes display in uniform color; pass/fail is project-level only. |
| `docs/JOSH_v341_Specification.md` "Viable Route Methodology" section | Add a "Display Conventions" subsection noting the controlling-route-first default and the educational framing. Keeps the legal text and the UI in sync. |
| `docs/JOSH_Fire_Chief_Guide.md` "Reviewing the route list" paragraph (added in v4.12) | Update to reflect the new default view; note that "Show all viable routes" is for inspection, not for menu of options. |

---

## Implementation Order

1. **State + helper** — add `_showAllRoutes`, `_controllingPath`, exports.
2. **`_renderDetail()` route panel** — educational note, "Show all routes"
   toggle, neutral route cards with CONTROLLING badge on the binding route.
3. **`_drawRoutes()`** — draw only controlling route by default; halo;
   conditional render of context routes when `_showAllRoutes` is on.
4. **`_clearRoutes()` / `selectProject()`** — state cleanup on project
   switch.
5. **`brief_renderer.js`** — framing paragraph + neutral row colors.
6. **Tests** — S33–S35 in sidebar; T15–T16 in brief renderer.
7. **Regenerate Berkeley** to inline updated sidebar.js and brief_renderer.js
   into analysis_map.html.
8. **Visual verification** in browser preview: default state shows one
   prominent route; "Show all" reveals 12 faint context routes; brief
   renders framing paragraph + neutral table.
9. **Regenerate the 4 josh-pipeline cities** via `acquire.py run`.
10. **Doc passes** — CLAUDE.md, spec, fire chief guide.

Branch name: `feat/route-display-ux`.

---

## What Does NOT Change

- **Engine behavior.** Still returns every viable route. Still computes ΔT
  per route. Still identifies bottleneck per route. Still flags
  DISCRETIONARY when any viable route's ΔT exceeds threshold.
- **Brief content.** Every route still appears in the Criterion C table.
  The legal record retains full disclosure of the evidence base (§9
  Strengthening the Record requires it). Only the *visual treatment* of the
  rows changes.
- **JOSH_DATA schema.** No new fields, no changed fields. Backward-compatible
  with any seeded project data.
- **Determination logic.** Identical. The tier is computed exactly as before.
- **CDN versioning.** `app.js` major version stays at `v1`.
- **AB 747 report.** Unaffected (it never showed per-project route detail).

---

## Risk Inventory

| Risk | Mitigation |
|---|---|
| User loses access to all-routes view by default; planners may need it for inspection. | The "Show all viable routes (N)" toggle is the explicit affordance. Tests verify it works. Position prominently at the top of the route list, not buried. |
| Educational note feels paternalistic or like a disclaimer. | Wording draft is tight (two sentences, no hedging language). Final wording requires an editorial pass against §8.6 to ensure parallel structure. |
| Color contrast issue: navy on white basemap or against the dimmed (0.2 opacity) heatmap. | The visibility fix from `28e5d8a` (custom Leaflet pane above heatmap, heatmap dimmed) preserves contrast. Halo on controlling route adds outline-style contrast independent of basemap color. |
| The CONTROLLING badge in the route card duplicates the gold halo on the map. | Intentional. Multiple signals reinforce that one route is the binding evidence. Removing redundancy here would weaken the visual link between sidebar and map. |
| Fire chiefs presenting the map may want all routes shown for AB 747 / SB 99 narrative. | "Show all" is one click. Fire chief can flip it before the meeting. Document the workflow in the Fire Chief Guide. |
| Brief loses pass/fail row color → developer can't see at a glance which routes individually exceed. | The ΔT column and the row-level CONTROLLING badge surface this information; only the *coloring* is neutralized. Power users reading the table for evidence still see the numbers. Casual readers don't get the wrong frame. |

---

## Success Criteria

After the redesign ships:

- **Default state per project on map:** one prominent navy route with gold
  halo (the controlling route). No other route lines visible. Project pin
  visible. Heatmap dimmed (from v4.12.1 fix).
- **"Show all viable routes (13)" toggle:** when activated, reveals 12 thin
  faint navy lines under/around the controlling route. The controlling
  route remains visually dominant.
- **Sidebar route panel:** educational note visible at the top. Below it,
  the route list shows all routes (sorted fastest first) with neutral
  cards; the CONTROLLING ROUTE card has a thin gold left border and a small
  badge. ΔT values and bottleneck names render as before.
- **Brief Criterion C:** framing paragraph appears above the table.
  Controlling row is highlighted. Other rows render in neutral coloring.
  Every route still listed (no truncation).
- **Tests:** all 75+ existing JS tests pass. S33–S35 and T15–T16 added and
  green.
- **No console errors** in browser preview at all five city demo maps.

---

## Open Questions

1. **Exact wording of the educational note.** Current draft: "Routes shown
   are paths evacuees may self-select during an evacuation (User
   Equilibrium). The determination uses the worst-case route because some
   evacuees will take it — slower routes do not 'fix' faster ones." Final
   wording should match §8.6's tone. Worth a 5-minute editorial pass before
   implementation.

2. **"Learn more" link target.** Options:
   - Modal that opens §3.6 + §8.6 excerpts inline (no nav).
   - External link to the full legal memo PDF (host on JOSH static).
   - In-app docs viewer (more infrastructure).
   - No link; just the note text.
   - Recommendation: start with no link; if user feedback suggests need, add
     a modal in a follow-up.

3. **Gold halo color.** `#f59e0b` (amber 500) reads as "attention" without
   tier-color collision. `#d97706` (amber 600) is darker, more authoritative.
   `#fbbf24` (amber 400) is lighter, may not contrast against navy
   sufficiently. Recommendation: `#f59e0b`. Worth checking against a few
   real city basemaps before locking.

4. **"Result" column wording in brief table.** Current proposal:
   "controlling" / "—". Alternative: drop the column entirely, leave only
   the badge on the controlling row. The column is informationally redundant
   with the highlighted row. Recommendation: drop the column; cleaner table.

5. **Should the educational note also appear in the brief?** The brief is a
   legal document; the framing in §8.6 is already in the legal memo it cites.
   But a one-line summary in Criterion C could help readers who don't
   cross-reference. Recommendation: yes, include as the framing paragraph
   already proposed above the table.

These are all 5-minute decisions; flag them at implementation time.

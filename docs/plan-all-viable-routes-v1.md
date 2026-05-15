# Plan: All Viable Evacuation Routes

**Status:** Fully resolved — ready to implement  
**Version:** v1  
**Date:** 2026-05-15  
**Author:** Thomas Gonzalez

---

## Background

### The Fire Chief's Request

In a meeting with the City of Encinitas, the fire chief raised the concern that JOSH's
shortest-path algorithm may not reflect routes the fire department would prescribe during
a structured evacuation. He asked whether JOSH could support custom prescribed routes.

### Why Prescribed Routes Are the Wrong Solution

The prescribed-route approach assumes **System Optimum** traffic assignment — a central
authority directs all vehicles to specific routes and has the operational capacity to
enforce those assignments at every decision point.

A city-wide wildfire evacuation operates under **User Equilibrium** — drivers self-select
the fastest available route based on real-time conditions, local knowledge, and what they
can observe. The Camp Fire (Paradise, CA 2018), the canonical event behind JOSH's safe
egress window parameters (NIST TN 2135), demonstrated that:

- Prescribed routes were rendered irrelevant within minutes as fire behavior outpaced
  the department's ability to staff intersections
- Residents simultaneously self-evacuated via all available arterials
- People died on routes the department would not have prescribed because those were the
  routes they could see and reach

Supporting prescribed routes would also introduce hidden discretion into an objective
standards methodology — the determination would depend on an assumption about fire
department operational capacity that cannot be verified or codified in statute.

The assistant city manager's alternative framing — *"map ALL evacuation routes from a
project"* — is the correct response. It makes no assumption about traffic management
capability, models actual evacuee behavior (fastest available path), and is more legally
defensible for an objective standards context.

### Current Algorithm Behavior

JOSH already runs Dijkstra from the project origin to **every** identified boundary exit
node. Two post-processing steps then reduce the full candidate set before ΔT evaluation:

1. **Travel time filter** (`_filter_by_travel_time`): drops paths slower than
   `max_path_length_ratio × fastest_exit_time`. Currently `2.0` — keeps only paths
   within 2× the fastest exit.
2. **Bottleneck deduplication** (`_dedup_by_label`): keeps only the fastest path per
   unique bottleneck road (by name + cross-streets). Eliminates redundant paths through
   the same constraint.

After both filters, a typical project yields 2–5 serving paths. The goal of this plan
is to surface the full viable set — likely 8–15 routes per project — by raising the
ratio to 3.5 and removing deduplication entirely from the engine.

---

## Methodology: Defining "Viable"

A viable evacuation route is one a rational evacuee might realistically choose under
emergency conditions. The operative criterion is travel time relative to the fastest
available exit: a route that takes 3× as long as the fastest exit is unlikely to be
chosen by any evacuee who has access to multiple options. A route at 1.5× might be
chosen by a driver whose neighborhood entry feeds naturally onto it.

The `max_path_length_ratio` parameter encodes this policy judgment. It is not a filter
on which routes exist — it is a filter on which routes are plausible under User
Equilibrium assignment. **Resolved: default set to `3.5`** — captures routes up to 3.5×
the fastest exit time, which includes realistic divergent routes without returning paths
no evacuee would rationally choose.

**Deduplication is removed from the engine entirely.** Bottleneck dedup was a display
optimization, not an analytical requirement. All routes passing the ratio filter are
returned. Which routes are visible on the map is a user decision made via per-route
toggles in the sidebar — the user IS the dedup mechanism. The `_dedup_by_label()`
function is deleted from both the Python pipeline and the JS engine. No configuration
parameter is needed.

---

## Scope of Changes

### Configuration

| File | Change |
|---|---|
| `config/parameters.yaml` | Change `max_path_length_ratio` from `2.0` to `3.5` |

`max_path_length_ratio` is already present at line 260 of `parameters.yaml` and already
flows through the full Python → JSON → JS pipeline. No new parameters, no new plumbing
— one value change.

### Python Backend

| File | Lines | Change |
|---|---|---|
| `agents/scenarios/wildland.py` | 793–805 | Delete `_dedup_by_label()` function entirely |
| `agents/scenarios/wildland.py` | ~318 | Remove the `_dedup_by_label()` call from `evaluate()` |

`_filter_by_travel_time()` (lines 715–733) requires no change — it already reads
`max_path_length_ratio` from config and will automatically apply the new 3.5 default.
No other Python changes are needed.

### JavaScript Engine (Generated)

`static/whatif_engine.js` is **generated** — never edit it directly. All algorithm
changes go into the JS string constant `_JS_IDENTIFY_SERVING_PATHS` in `agents/export.py`
(lines 276–366). `build.py analyze` regenerates `whatif_engine.js` from that string.

| File | Lines | Change |
|---|---|---|
| `agents/export.py` | 316–336 | Remove the dedup block from `_JS_IDENTIFY_SERVING_PATHS` entirely |
| `static/whatif_engine.js` | all | **Regenerated** by `build.py analyze` — do not edit |

No export changes needed for `parameters.json` — `deduplicate_by_bottleneck` is no
longer a parameter.

### Map Rendering and UX

#### Synchronized map + sidebar (resolved 2026-05-15)

The map and sidebar are **synchronized**: the map renders only the routes whose toggle
is ON in the sidebar. Toggling a route card off removes its AntPath from the map
immediately; toggling it back on adds it. The map never shows routes that aren't
reflected in the sidebar.

#### Route toggle list

The sidebar detail panel shows **all routes as a scrollable toggle list**, ordered
**fastest travel time first** (shortest exit time at top). This matches User Equilibrium
logic — the routes most evacuees will actually take are prominent; rarer divergent
routes fall below. All routes are toggled ON by default.

Each route card has an eye icon toggle on the right edge. Clicking it hides that route
from the map and dims the card. The toggle state is per-project, stored in
`_routeToggles` (a `Map<projectId, Set<pathId>>`) — switching to a different project
resets all toggles to ON.

```
┌──────────────────────────────────────┐
│ 👁  Route 1   5.3 min  ▲ 38.77 min  │  ← fastest exit first; eye = toggled on
│     Sage Canyon Drive · VHFHSZ      │
├──────────────────────────────────────┤
│ 👁  Route 2   6.3 min  ▲ 38.77 min  │
│     Sage Canyon Drive · VHFHSZ      │
├──────────────────────────────────────┤
│ 👁  Route 3   7.8 min  ▲ 38.77 min  │
│     Sage Canyon Drive · VHFHSZ      │
├──────────────────────────────────────┤
│ 🚫  Route 4   7.8 min  ▲ 38.77 min  │  ← toggled off; card dimmed; route hidden
│     Sage Canyon Drive · VHFHSZ      │
└──────────────────────────────────────┘
  Showing 3 of 12 routes
  Determination uses all 12 routes
```

The "Determination uses all N routes" note is always visible when any route is toggled
off. This is a legal safeguard — the user must not be able to hide a route and then
believe the determination only considered the visible ones.

**Route card fields (both columns):**
- Left: exit travel time (min) — the sort key; tells the fire chief how fast this route is
- Right: ΔT (min) + pass/fail indicator — the analytical result

#### Map visual hierarchy — opacity by list position

All routes use the **same green/red pass/fail color semantics**. Rank is encoded via
opacity and weight keyed to list position (fastest = brightest), not to ΔT. This
matches the sort order — the routes that matter most to the fire chief (most likely
to be used) read most clearly.

| List position | Weight | Opacity | Purpose |
|---|---|---|---|
| 1st | 4 | 0.85 | Most likely route — reads clearly |
| 2nd | 3 | 0.60 | Supporting context |
| 3rd+ | 2 | 0.35 | Additional routes — present but subordinate |

Bottleneck overlay segments follow the same opacity as their parent route.

When a route is toggled off, its layer is removed and remaining visible routes re-rank
by their new list positions. If route 1 is hidden, route 2 becomes position 1 and
renders at weight 4/opacity 0.85.

#### Implementation — new state and rendering changes

| File | Lines | Change |
|---|---|---|
| `static/sidebar.js` | module top | Add `const _routeToggles = new Map()` state variable; add `joshSidebar_toggleRoute(projectId, pathId)` global handler |
| `static/sidebar.js` | ~1104 `_drawRoutes()` | Filter `project.result.paths` to only toggled-on paths; sort by `cost_s` ascending; apply opacity/weight by resulting array index |
| `static/sidebar.js` | ~1327 `selectProject()` | On project switch, delete prior project's entry from `_routeToggles` (reset all to ON) |
| `static/sidebar.js` | ~1559 `_renderDetail()` | Sort paths by `cost_s` ascending; render each as a card with eye toggle; show "Showing X of Y" count; show "Determination uses all Y routes" when any are toggled off; call `_drawRoutes()` on each toggle |
| `static/brief_renderer.js` | Criterion C section | Summary line: "N routes evaluated; worst-case ΔT = X.XX min on [Road Name]"; full route table below sorted by travel time — all routes, no truncation (legal document) |

### Tests

| File | Lines | Change |
|---|---|---|
| `tests/test_whatif_engine.js` | 35 | Raise `PATH_COUNT_TOLERANCE` from `2` to `4–5` — larger route set (up to 32 paths) means minor graph traversal differences between Python/JS may produce small count variation at the margin |
| `tests/test_whatif_engine.js` | 73 | Verify `matchPaths()` ΔT tolerance still holds across larger path sets — no logic change expected, but must confirm |
| `tests/test_brief_renderer.js` | — | Add test cases covering briefs with 5+ serving routes in Criterion C |
| `tests/test_vectors.json` | all | **Regenerated** by `build.py analyze` after parameter change |

### Documentation

| File | Change |
|---|---|
| `CLAUDE.md` | Key Parameters table: update `max_path_length_ratio` from `2.0` to `3.5`. Objective Standards section (Standard 2): note that routes returned are all paths within `max_path_length_ratio` of the fastest exit, with no deduplication. |
| `docs/JOSH_v341_Specification.md` | Add section: "Viable Route Methodology" — define viable route, cite UE basis, explain ratio parameter, note that more routes = more conservative ΔT determination |
| `docs/JOSH_Legal_Defensibility_Memo.md` | Add subsection: "Route Selection Methodology" — UE vs. SO framing, Camp Fire evidence, no traffic-management assumption required |
| `docs/JOSH_Fire_Chief_Guide.md` | Update to explain JOSH maps all viable routes; note that road capacity corrections via `_road_overrides.yaml` (width, access type, speed) are the correct mechanism for encoding local knowledge about specific roads |

---

## Regeneration Sequence

After all code and config changes are complete, run in order:

```bash
# 1. Rebuild graph + regenerate whatif_engine.js + test_vectors.json
uv run python build.py analyze --city "Berkeley" \
  --data-dir /path/to/josh-pipeline/data/berkeley

# 2. Anti-divergence and unit tests
node --test tests/test_whatif_engine.js
node --test tests/test_brief_renderer.js
node --test tests/test_sidebar.js
node --test tests/test_project_manager.js

# 3. Regenerate all city demo maps
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Berkeley"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Encinitas"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Del Mar"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Solana Beach"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "rsf_fire"
```

---

## What Does NOT Change

- **ΔT determination logic** — still flags DISCRETIONARY if **any** serving path exceeds
  the threshold. More routes evaluated = more conservative analysis, not less.
- **Bottleneck identification per path** — still finds minimum-capacity segment on each route.
- **`JOSH_DATA` schema** — `serving_paths` array gets more entries per project. No
  breaking change to the data format; no CDN major version bump required.
- **HCM capacity calculations** — no change to road capacity, degradation factors, or ΔT formula.

---

## Ratio Default: Resolved at 3.5

`max_path_length_ratio` is set to **3.5**. This captures routes up to 3.5× the fastest
exit travel time — a range that includes all realistic divergent routes under User
Equilibrium assignment while excluding paths that no rational evacuee would choose.

The Sage Canyon analysis (see Empirical Finding below) showed that for single-access
projects, the ratio has no effect on the route set's analytical content (all routes share
one bottleneck regardless of how far the ratio extends). The 3.5 default is calibrated
for multi-access projects where genuinely different corridors exist — it is wide enough
to capture a slower but geographically distinct escape route while avoiding the visual
noise of routes at 4× or beyond.

---

## Empirical Finding: Sage Canyon (Encinitas)

Analysis run 2026-05-15 against the live Encinitas graph at ratio 2.0.

**The fire chief's prescribed route (north on El Camino Real → Encinitas Blvd → I-5)
maps to exit node 291697218 at (33.0452, −117.2861), ratio 1.74.** It is already found
by the algorithm and already inside the current 2.0 limit. It is not visible on the map
because dedup collapses all paths to 1.

**Root cause:** Sage Canyon Drive is the bottleneck on every single one of the 32
candidate paths (effective capacity 394 vph, VHFHSZ degradation). The project has
single-access egress — all evacuees traverse the same degraded two-lane segment before
reaching El Camino Real regardless of which direction they ultimately exit the city.
Dedup correctly identifies this shared constraint and retains only the fastest path.

**Implication:** For single-access projects, the ratio change has no visible effect on
dedup-on output (all routes share one bottleneck). The `deduplicate_by_bottleneck: false`
flag is the key change that surfaces the fire chief's route. The ratio change matters
most for multi-access projects where genuinely different bottlenecks exist on different
egress corridors.

**ΔT is unaffected by route direction:** Whether evacuees go north to Encinitas Blvd or
south to Manchester Ave, the binding constraint is the same road (Sage Canyon Drive,
394 vph). The 38.77-min ΔT holds for all 32 candidate routes.

---

## Resolved Decisions

All design questions are closed. Summary for reference:

| Question | Decision |
|---|---|
| Ratio default | `3.5` |
| Dedup | Removed from engine entirely — user controls visibility via toggles |
| Map/sidebar sync | Synchronized — map shows only toggled-on routes |
| Sort order | Fastest travel time first (User Equilibrium logic) |
| Route visibility default | All routes toggled ON |
| Visual hierarchy | Opacity by list position: 0.85 / 0.60 / 0.35; pass/fail color preserved |
| Determination safeguard | "Determination uses all N routes" shown when any route toggled off |
| Brief display | Summary line + complete route table, sorted by travel time; no truncation |

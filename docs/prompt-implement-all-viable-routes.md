# Implementation Prompt: All Viable Evacuation Routes

Use this prompt to start a new Claude Code session that implements the all-viable-routes
feature. The full design spec is in `docs/plan-all-viable-routes-v1.md` — read it first.
This prompt provides the architectural context needed to execute without gaps.

---

## What You Are Building

JOSH currently finds all Dijkstra shortest paths from a project to every boundary exit
node, then filters them down to 2–5 routes via (a) a 2× travel time ratio filter and
(b) bottleneck deduplication. The result: the fire chief's preferred route is often
algorithmically present but invisible on the map.

This feature:
1. Raises the ratio filter from `2.0` to `3.5` (more routes pass through)
2. Removes bottleneck deduplication entirely from both Python and JS engines
3. Adds a per-route eye-icon toggle list to the sidebar so the user controls which
   routes are visible on the map
4. Synchronizes the map to the sidebar — only toggled-on routes render as AntPaths

The ΔT determination logic does NOT change. All routes are always evaluated for ΔT
regardless of toggle state. Toggles are purely a display mechanism.

Full design rationale, mockups, and resolved decisions: `docs/plan-all-viable-routes-v1.md`

---

## Architecture Reminders

- `static/whatif_engine.js` is **GENERATED** — never edit it directly. Edit the JS
  string constant `_JS_IDENTIFY_SERVING_PATHS` in `agents/export.py` (around line 276),
  then run `build.py analyze` to regenerate.
- `static/v1/app.js` is also **GENERATED** by `build.py demo` — do not edit.
- All algorithm changes must be mirrored in both Python (`agents/scenarios/wildland.py`)
  and the JS string in `agents/export.py` to keep the anti-divergence tests passing.
- Run `node --test tests/test_whatif_engine.js` after any engine change to verify parity.

---

## Implementation Order

Work through these steps in sequence. Each step is independently testable.

### Step 1 — config/parameters.yaml

File: `config/parameters.yaml`, line ~260

Change `max_path_length_ratio` from `2.0` to `3.5`. That is the only config change.
Do NOT add a `deduplicate_by_bottleneck` parameter — that concept was superseded by
the user toggle design.

### Step 2 — Python: remove _dedup_by_label()

File: `agents/scenarios/wildland.py`

- Delete the `_dedup_by_label()` function (lines 793–805)
- Remove its call site in `evaluate()` (around line 318)
- `_filter_by_travel_time()` (lines 715–733) requires no change — it already reads
  `max_path_length_ratio` from config and will pick up the new 3.5 value automatically

### Step 3 — JS engine: remove dedup block

File: `agents/export.py`, string constant `_JS_IDENTIFY_SERVING_PATHS` (around line 276)

Inside the JS string, find the dedup block (around lines 316–336 of the string) that
builds a `bottleneckMap` and keeps only one path per unique bottleneck osmid. Delete
that block entirely. The function should return all candidates that passed the ratio
filter, unsorted (the sidebar will sort by `cost_s`).

Do NOT touch the ratio filter logic — that stays, just with the new 3.5 value flowing
in from `_params.max_path_length_ratio`.

After editing `export.py`, regenerate `whatif_engine.js`:

```bash
uv run python build.py analyze --city "Berkeley" \
  --data-dir /path/to/josh-pipeline/data/berkeley
```

### Step 4 — Run anti-divergence tests

```bash
node --test tests/test_whatif_engine.js
```

Expect `PATH_COUNT_TOLERANCE` failures — the test at line 35 currently allows ±2 paths.
Raise it to `5` to accommodate the larger route sets. Re-run until green. If ΔT values
diverge (not just counts), there is a real Python/JS parity bug — fix it before
proceeding.

### Step 5 — sidebar.js: route toggle list

File: `static/sidebar.js`

This is the largest change. Make these additions/modifications:

**a) New state variable** (module top, near other `const _xxx` declarations):
```javascript
const _routeToggles = new Map(); // Map<projectId, Set<pathId>>
```

**b) New global handler** (near the bottom where other `window.joshSidebar_*` are
registered, around line 1803):
```javascript
window.joshSidebar_toggleRoute = (projectId, pathId) => {
  if (!_routeToggles.has(projectId)) {
    // First toggle for this project — initialise with all paths ON, then flip the one
    const proj = _projects.find(p => p.id === projectId);
    const allIds = new Set((proj?.result?.paths || []).map(p => p.path_id || p.pathId));
    _routeToggles.set(projectId, allIds);
  }
  const set = _routeToggles.get(projectId);
  if (set.has(pathId)) set.delete(pathId);
  else set.add(pathId);
  _drawRoutes(projectId);
  _render();
};
```

**c) selectProject() reset** (around line 1327): when switching to a new project, delete
the prior project's toggle state so it resets to all-ON:
```javascript
// at the top of selectProject(), before the existing logic:
if (_selectedId && _selectedId !== id) _routeToggles.delete(_selectedId);
```

**d) _drawRoutes() update** (around line 1104):

- Get the project's paths
- Sort by `cost_s` ascending (fastest travel time first)
- Filter to only paths whose `path_id`/`pathId` is in `_routeToggles.get(projectId)`,
  OR if there is no entry in `_routeToggles` for this project, treat all paths as ON
- Assign opacity/weight by resulting array index:
  - index 0: weight 4, opacity 0.85
  - index 1: weight 3, opacity 0.60
  - index 2+: weight 2, opacity 0.35
- Apply the same opacity to the bottleneck overlay segment for each path
- The rest of the AntPath rendering logic (color, delay, dashArray, tooltip) is
  unchanged — color still comes from `path.flagged`

**e) _renderDetail() route list update** (around line 1616):

Replace the existing `forEach` route card loop with a new version that:

- Sorts paths by `cost_s` ascending before rendering
- Checks `_routeToggles` to determine if each path is currently ON (default: ON if no
  entry exists for this project)
- Renders an eye icon button on the right edge of each card:
  - Eye open (👁 or unicode `\u{1F441}`, or a simple "●") when ON
  - Eye closed / slash (or "○") when OFF
  - `onclick="joshSidebar_toggleRoute('${p.id}', '${path.path_id || path.pathId}')"`
  - Dimmed card style (`opacity: 0.4`) when toggled OFF
- Route card shows two data points: exit travel time (from `path.cost_s`, in minutes)
  on the left, ΔT + pass/fail on the right
- After the route list, if any routes are toggled off, show:
  ```
  Showing X of Y routes · Determination uses all Y routes
  ```
  This note must appear whenever the visible count is less than the total — it is a
  legal safeguard and must not be omitted.

### Step 6 — brief_renderer.js: Criterion C update

File: `static/brief_renderer.js`

In the Criterion C section, update the route list display:
- Add a summary line at the top: "N routes evaluated; worst-case ΔT = X.XX min on
  [bottleneck road name]"
- The full route table below lists ALL routes (no truncation — brief is a legal document)
- Sort the table by travel time ascending (fastest first), matching the sidebar order

### Step 7 — Test suite updates

```bash
node --test tests/test_brief_renderer.js
node --test tests/test_sidebar.js
```

Add test cases to `tests/test_brief_renderer.js` covering briefs where Criterion C has
5+ serving routes — verify the summary line renders and all routes appear in the table.

Update `tests/test_whatif_engine.js` line 35: `PATH_COUNT_TOLERANCE` from `2` to `5`
(if not already done in Step 4).

### Step 8 — Documentation updates

**`CLAUDE.md`** — Key Parameters table: change `max_path_length_ratio` row from `2.0`
to `3.5`. In the Objective Standards section (Standard 2), add a note that routes
returned are all paths within `max_path_length_ratio` of the fastest exit with no
deduplication.

**`docs/JOSH_v341_Specification.md`** — Add a section "Viable Route Methodology":
define viable route, cite User Equilibrium basis, explain ratio parameter, note that
more routes = more conservative ΔT determination (any flagged path triggers
DISCRETIONARY).

**`docs/JOSH_Legal_Defensibility_Memo.md`** — Add subsection "Route Selection
Methodology": UE vs. SO framing, Camp Fire evidence, no traffic-management assumption.

**`docs/JOSH_Fire_Chief_Guide.md`** — Update to explain JOSH now maps all viable routes
with individual toggles; note that road capacity corrections via `_road_overrides.yaml`
are the correct mechanism for encoding local knowledge about specific roads.

### Step 9 — Regenerate all city demo maps

```bash
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Berkeley"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Encinitas"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Del Mar"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Solana Beach"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "rsf_fire"
```

Run all tests after regeneration:
```bash
node --test tests/test_whatif_engine.js
node --test tests/test_brief_renderer.js
node --test tests/test_sidebar.js
node --test tests/test_project_manager.js
```

---

## What Does NOT Change

- ΔT formula, HCM capacity calculations, FHSZ degradation factors
- Bottleneck identification per path (min-capacity edge on each route)
- Tier determination logic (DISCRETIONARY if ANY path ΔT > threshold)
- `JOSH_DATA` schema — `serving_paths` array gets more entries; no breaking change;
  no CDN major version bump needed
- `path_wgs84_coords` geometry — AntPath coordinate quality unchanged

---

## Key Files Quick Reference

| File | Role |
|---|---|
| `config/parameters.yaml:260` | `max_path_length_ratio` — change to `3.5` |
| `agents/scenarios/wildland.py:715` | `_filter_by_travel_time()` — no change needed |
| `agents/scenarios/wildland.py:793` | `_dedup_by_label()` — delete entirely |
| `agents/export.py:276` | `_JS_IDENTIFY_SERVING_PATHS` — remove dedup block |
| `static/whatif_engine.js` | GENERATED — do not edit; regenerated by `build.py analyze` |
| `static/sidebar.js:1104` | `_drawRoutes()` — add toggle filter + opacity hierarchy |
| `static/sidebar.js:1327` | `selectProject()` — reset toggle state on project switch |
| `static/sidebar.js:1559` | `_renderDetail()` — replace route card loop with toggle list |
| `static/brief_renderer.js` | Criterion C — summary line + full sorted table |
| `tests/test_whatif_engine.js:35` | `PATH_COUNT_TOLERANCE` — raise to `5` |

# Plan: Engine Parity Fix + `demo.py` Rename

**Status:** Ready to implement
**Version:** v1
**Date:** 2026-05-15
**Author:** Thomas Gonzalez

---

## Background

Two unrelated cleanups grouped because they're both low-risk and most efficient
to ship together against the `feat/all-viable-routes` baseline.

### Part A — Engine parity bug

During the v4.12 all-viable-routes work we discovered that the Python and JS ΔT
engines pick different bottleneck osmids on the same physical path, sometimes
producing different tier determinations. Root cause is **not** algorithmic — both
engines use the same undirected graph and the same travel-time weights and
produce identical paths and identical total travel times. The disagreement is in
how each engine looks up `eff_cap_vph` per edge:

- [agents/scenarios/segment_index.py:85](../agents/scenarios/segment_index.py:85)
  `SegmentIndex.eff_cap()` returns `0.0` for missing osmids; the bottleneck
  argmin in `agents/scenarios/wildland.py` applies `eff_cap(o) or 9999`, pushing
  missing osmids to the back of selection.
- [agents/export.py:613](../agents/export.py:613) `export_graph_json` defaults
  missing osmids to `1000.0`. JS edges carry `eff_cap_vph=1000` and the JS
  bottleneck argmin picks them.
- Both modules max-merge eff_cap when an OSMnx edge inherits multiple osmids,
  but the keys-set differs because OSMnx's per-edge multi-osmid lists do not
  always have full counterpart rows in `roads.gpkg`.

The all-viable-routes branch masks the divergence by tuning Downtown Mid-Rise to
120 units (matching prior commit `42c7014`). That's a fixture trick, not a fix.

### Part B — `demo.py` rename

The most consequential rendering module in the repo is named
[agents/visualization/demo.py](../agents/visualization/demo.py) (2,500+ lines)
and its CLI entry point is `build.py demo`. Both names misrepresent the
artifact, which CLAUDE.md explicitly calls *"the primary stakeholder-facing UX —
the interactive multi-project comparison map used for demos, city attorney
review, and planning presentations"*. New contributors read "demo" and assume
throwaway experimental code; the truth is the opposite.

---

## Methodology

### Part A: parity fix — three changes, ranked by importance

**Decisions:**

1. **Bake `eff_cap_vph` directly onto OSMnx graph edges in `capacity_analysis.py`.**
   Eliminate `SegmentIndex` entirely. Both engines then read per-edge cap from
   the single source-of-truth artifact (`G[u][v][k]['eff_cap_vph']` in Python,
   `edge.eff_cap_vph` in JS via graph.json). No osmid-keyed side table. No
   max/min merge semantics to disagree on.

2. **One default semantics for missing cap.** Both engines skip edges with
   unknown cap from bottleneck consideration. Python already does this via the
   `or 9999` pattern; JS adopts the same skip. No 1000-vph silent fallback in
   `export_graph_json`. If a graph edge has no cap row, it shouldn't be the
   bottleneck; that's the conservative choice.

3. **Tighten `matchPaths()` to fail on bottleneck-set disjoint.** Today it logs
   a `NOTE` and silently proceeds when Python and JS pick non-overlapping
   bottleneck sets. That's how today's divergence hid for months. After the
   fix, the test asserts that the two engines agree on the bottleneck osmid
   set for every path (within `PATH_COUNT_TOLERANCE`).

**Out of scope for this plan:**
- Refactoring the dual-engine architecture into a single JS engine called via
  Node subprocess. The dual-implementation cross-check is a legal correctness
  property; we keep it.
- Per-edge capacity attributes beyond `eff_cap_vph` (hazard_degradation, road
  type, etc.) — those already round-trip correctly because they're keyed in the
  same dict-by-osmid lookup that we're replacing for eff_cap. They can move to
  per-edge in a follow-up if useful.

### Part B: rename

**Decisions:**

| From | To | Reason |
|---|---|---|
| `agents/visualization/demo.py` | `agents/visualization/analysis_map.py` | Matches output filename `analysis_map.html`; describes the artifact, not its origin story. |
| `build.py demo` CLI subcommand | `build.py map` | Short, snake_case-compatible, consistent with `analyze` / `evaluate` / `report`. |
| `def demo(...)` (the Click command function) | `def map(...)` | Mechanical follow-through. |
| `_make_browser_projects()` in demo.py | `_serialize_seeded_projects()` | "browser" framing is incidental; the function serializes seeded projects for JOSH_DATA. |

**Out of scope:**
- Renaming `josh-pipeline/projects/{city}_demo.yaml` to drop `_demo`. Bigger
  blast radius (touches josh-pipeline tracked outputs and external doc refs);
  lower payoff. Leave for a separate cleanup.
- Renaming `build.py evaluate` (per CLAUDE.md the legacy command is slated for
  removal anyway).
- Hidden aliases. `build.py demo` will not be kept as a backwards-compat
  alias — the rename is a clean break. `josh-pipeline/acquire.py` is updated
  in the same PR so the canonical chain keeps working.

---

## Scope of Changes — Part A (Parity Fix)

### `agents/capacity_analysis.py`

| Change | Lines |
|---|---|
| Where `roads_gdf` is finalized with `effective_capacity_vph` per row, also write each row's `eff_cap_vph` onto every corresponding OSMnx edge attribute via `G[u][v][k]['eff_cap_vph']`. | ~10 |
| Same for `fhsz_zone`, `hazard_degradation`, `bottleneck_road_type`, lanes, speed — write per-edge attributes so downstream consumers don't need a side table. | ~15 |
| Persist enriched graph to `data/{city}/graph.graphml` (already saved; just ensure new attrs are included). | 0–2 |

### `agents/scenarios/wildland.py`

| Change | Lines |
|---|---|
| `_identify_and_enrich()` (~lines 736–790): replace `segment_index.eff_cap(osmid)` lookups with `G[u][v][k].get('eff_cap_vph', 0)`. The osmid → SegmentInfo indirection goes away. | ~20 |
| Remove `segment_index = SegmentIndex(roads_gdf)` construction at the top of `identify_routes`. | ~3 |
| The bottleneck argmin pattern stays — `min(..., key=lambda e: e.get('eff_cap_vph') or float('inf'))` — but the `or 9999` becomes `or float('inf')` for clarity. | 1 |

### `agents/scenarios/segment_index.py`

| Change | Lines |
|---|---|
| **Delete the file.** Nothing left in the repo references it after wildland.py is updated. | -86 |

### `agents/export.py`

| Change | Lines |
|---|---|
| `export_graph_json` (~lines 562–615): keep the `osmid_to_*` dicts for **non-cap** attributes (name, road_type, etc.) but read `eff_cap_vph`, `fhsz_zone`, `hazard_degradation` from per-edge attributes set in capacity_analysis. | ~15 |
| Change missing-cap default at line 613 from `1000.0` to `0.0` so the edge serialization carries "unknown" rather than "1000 vph fabricated". | 1 |
| `_JS_IDENTIFY_SERVING_PATHS` JS string: in the bottleneck argmin (~lines 318–328 of the string), skip edges with `eff_cap_vph <= 0`: `if (e.eff_cap_vph > 0 && (bn.eff_cap_vph === 0 \|\| e.eff_cap_vph < bn.eff_cap_vph)) bn = e;` | ~3 |

### `static/whatif_engine.js`

GENERATED. Regenerated by `build.py analyze` after `agents/export.py` change. No
manual edit.

### `tests/test_whatif_engine.js`

| Change | Lines |
|---|---|
| `matchPaths()` (lines 73–110): change `console.log(NOTE)` for a missing bottleneck on a flagged Python path to `assert.fail()`. After the parity fix, this should never fire on Berkeley fixtures. | ~5 |
| Add a new test verifying the bottleneck osmid **sets** match: for every test_vectors vector, `new Set(jsPaths.map(p=>p.bottleneckOsmid))` symmetric-difference Python's set has cardinality ≤ `PATH_COUNT_TOLERANCE`. | ~15 |
| `PATH_COUNT_TOLERANCE` stays at 5 (the v4.12 value). | 0 |

### Test vectors regeneration

| File | Change |
|---|---|
| `output/berkeley/test_vectors.json` | regenerated by `build.py demo` after the engine fix |
| `josh-pipeline/projects/berkeley_demo.yaml` Downtown Mid-Rise | **REVERT** units 120 → 85. After the parity fix, both engines agree at 85u (Python's `1000718782` lookup now returns same value as JS's lookup; bottleneck is `1000718782` with eff_cap≈1900 in both; ΔT≈4.59 < 6.0 threshold; tier = CONDITIONAL). This restores the originally-intended tipping-point test case. |

### Documentation

| File | Change |
|---|---|
| `CLAUDE.md` | Note in "Architecture: Pipeline vs Client" section that `eff_cap_vph` is a graph edge attribute baked by `capacity_analysis.py`. Remove any reference to `SegmentIndex`. |
| `docs/JOSH_v341_Specification.md` §4.8 | Add one line: "Edge capacities are written to the OSMnx graph per-edge; both Python and JS engines read from the same per-edge attribute." |

---

## Scope of Changes — Part B (Rename)

### Code changes (3 files)

| File | Change |
|---|---|
| `agents/visualization/demo.py` | `git mv agents/visualization/demo.py agents/visualization/analysis_map.py` |
| `build.py` | `from agents.visualization.demo import ...` → `from agents.visualization.analysis_map import ...`. Rename `@cli.command()` function `def demo(...)` → `def map(...)`. Update help text. |
| `josh-pipeline/acquire.py:406` | Change subprocess arg `"demo"` → `"map"`. |

### Function rename inside the new `analysis_map.py`

| Function | Rename |
|---|---|
| `_make_browser_projects()` | `_serialize_seeded_projects()` |

(Call sites are all internal to the same file — single Edit replaces every
occurrence.)

### Documentation + comment updates

These are string-only; they don't affect runtime behavior but need to stay
current.

| File | Change |
|---|---|
| `README.md` (csf-josh) | `build.py demo` → `build.py map`. |
| `josh-pipeline/README.md` | Same. |
| `CLAUDE.md` "Run Commands" section | Same; also note the file rename. |
| `docs/JOSH_v341_Specification.md` | Same. |
| `docs/city_onboarding.md` | Same. |
| `tests/smoke_sidebar.js` (error messages) | Same. |
| `tests/test_whatif_engine.js` (error messages, lines 11, 19, 50) | Same; also change `main.py` → `build.py` where stale. |
| `agents/export.py` (JS string regeneration headers) | Same string in the `// Regenerate: ...` comments. |
| `static/v1/app.js` (auto-regenerated) | Picks up the new comment from export.py automatically. |
| All `josh-pipeline/projects/{city}_demo.yaml` header comments line 4 | `main.py demo` → `build.py map`. Stale references to `main.py` get corrected to `build.py` in the same pass. |

The YAML files themselves keep their `_demo.yaml` suffix for this PR (rename out
of scope; see Part B Out of Scope above).

---

## Implementation Order

Execute Part A and Part B in sequence to keep each diff narrow and reviewable:

### Phase 1 — Part A (parity fix)

1. Edit `agents/capacity_analysis.py` to write per-edge eff_cap onto the OSMnx graph.
2. Edit `agents/scenarios/wildland.py` to read per-edge eff_cap; remove `SegmentIndex` use.
3. Delete `agents/scenarios/segment_index.py` (and update any imports — there's exactly one in wildland.py and one in tests).
4. Edit `agents/export.py`: change graph.json eff_cap default + JS bottleneck-skip semantics.
5. Run `uv run python build.py analyze --city "Berkeley" --data-dir <path>` to regenerate `whatif_engine.js`.
6. Revert `josh-pipeline/projects/berkeley_demo.yaml` Downtown Mid-Rise to 85u.
7. Run `uv run python build.py demo --city "Berkeley" ...` to regenerate `test_vectors.json` + `analysis_map.html`.
8. Tighten `tests/test_whatif_engine.js` (hard-fail on bottleneck set disjoint; add new bottleneck-osmid-set test).
9. Run all four JS test suites + Python wildland tests; confirm green.
10. Regenerate all 5 active cities via `josh-pipeline/acquire.py run`.

**Commit** as one logical change (parity fix). Branch name suggestion:
`fix/eval-parity-per-edge-cap`.

### Phase 2 — Part B (rename)

1. `git mv agents/visualization/demo.py agents/visualization/analysis_map.py`.
2. Update import in `build.py`.
3. Rename Click subcommand `demo` → `map` in `build.py`.
4. Update `josh-pipeline/acquire.py:406` subprocess arg.
5. Rename internal `_make_browser_projects` → `_serialize_seeded_projects` inside the new file.
6. Doc/comment sweep — every file in the table above.
7. Run all tests (no behavior change; tests should pass without regeneration).
8. Smoke-test the full pipeline against one city to confirm `build.py map` works end-to-end.

**Commit** as a second logical change (mechanical rename). Branch name
suggestion: `chore/rename-demo-to-analysis-map`.

---

## What Does NOT Change

- **Algorithm.** ΔT formula, HCM capacity table, FHSZ degradation factors, Dijkstra
  weights — none change.
- **Dual-engine architecture.** Python and JS engines stay independent
  implementations. `test_whatif_engine.js` keeps cross-validating them. The
  bug fix tightens, not weakens, the parity guarantee.
- **`JOSH_DATA` schema.** Adding per-edge `eff_cap_vph` is purely additive on
  the Python side; JS already reads `edge.eff_cap_vph` from graph.json.
- **AB 747 report.** Reads `roads_gdf` directly + the citywide population paths
  from `evacuation_paths.json`. Both unchanged by this work.
- **All other CLI subcommands** (`analyze`, `evaluate`, `report`). Names and
  behavior unchanged.
- **CDN versioning.** No JOSH_DATA schema break, so `app.js` major version
  stays at `v1`.

---

## Risk Inventory

| Risk | Mitigation |
|---|---|
| Per-edge attributes don't round-trip through OSMnx GraphML save/load. | The OSMnx graphml writer preserves arbitrary edge attributes. Sanity-check by reloading the saved graph and asserting `eff_cap_vph` is present on a sample edge. |
| Downtown Mid-Rise still diverges at 85u after the per-edge cap fix. | If so, the bug is deeper than the missing-osmid default — investigate before merging. The plan asserts both engines should now agree on a path-by-path basis. If they don't, hold and re-diagnose. |
| Tightened `matchPaths` exposes other latent divergences on Berkeley fixtures. | Treat as discoveries, not blockers — fix per case before merge. The existing 6 Berkeley fixtures cover all three tiers; if the test fails on a fixture other than Downtown, that's a separate divergence we want to know about. |
| Rename misses a doc reference. | The doc references in the table above were enumerated by `grep`. Any straggler shows up as "command not found" at runtime — harmless, easy to fix in a follow-up PR. |
| `josh-pipeline/acquire.py` updated in the same PR — coordinating two repos. | The change in josh-pipeline is one string. Update both in lockstep; commit both before regenerating output. |

---

## Regeneration Sequence

After Phase 1 changes:

```bash
# 1. Rebuild graph + regenerate whatif_engine.js + test_vectors.json
uv run python build.py analyze --city "Berkeley" \
  --data-dir /path/to/josh-pipeline/data/berkeley

uv run python build.py demo --city "Berkeley" \
  --data-dir /path/to/josh-pipeline/data/berkeley \
  --projects /path/to/josh-pipeline/projects/berkeley_demo.yaml

# 2. Anti-divergence and unit tests
node --test tests/test_whatif_engine.js
node --test tests/test_brief_renderer.js
node --test tests/test_sidebar.js
node --test tests/test_project_manager.js
uv run python -m unittest tests.test_wildland_dedup

# 3. Regenerate all city demo maps
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Berkeley"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Encinitas"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Del Mar"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "Solana Beach"
JOSH_DIR=/path/to/josh uv run python acquire.py run --city "rsf_fire"
```

After Phase 2 (rename), substitute `build.py map` for `build.py demo` in step 1.

---

## Success Criteria

**Part A:**
- `node --test tests/test_whatif_engine.js` passes with `matchPaths` in
  hard-fail mode on the existing Berkeley fixtures.
- Downtown Mid-Rise at **85 units** produces tier `MINISTERIAL WITH STANDARD
  CONDITIONS` in **both** engines, with identical bottleneck osmid sets.
- `SegmentIndex` no longer appears anywhere in the codebase.
- No new dependencies; pipeline runtime unchanged within ±5%.

**Part B:**
- `build.py map --help` works; `build.py demo --help` returns "no such command".
- `JOSH_DIR=... uv run python acquire.py run --city "Berkeley"` runs end-to-end
  without changes (acquire.py updated to call `build.py map`).
- All four JS test suites + Python wildland tests pass without regeneration.

---

## Open Questions

None identified. All design decisions are resolved.

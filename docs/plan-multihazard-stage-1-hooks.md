# Stage 1 — JS-Only Hazard Engine + YAML Project Loader

**Status:** Locked architecture; v3.1 amendment in effect (Phase A + Phase B implemented under v3.1)
**Date:** 2026-05-24
**Revision history:**
- v1 (2026-05-24): Python config + hook registry proposal
- v2 (2026-05-24): Architect-reviewed Python plan with 7 fixes
- v3 (2026-05-24): JS-only evaluation engine; Python narrows to build-time data prep; demo projects become YAML loaded by JS at runtime; golden-file regression replaces anti-divergence
- **v3.1 (2026-05-24, current):** `build_result` promoted from hook phase to engine-internal driven by `result_extras` declarative DSL. Hook system drops from 6 phases to 5. See AMENDMENT block below.

**Supersedes:** the class-per-hazard Stage 1 scope in `docs/plan-multihazard-mvp.md` §4
**Locks:** decision #12 in `docs/multihazard_status.md` (5-phase hook registry + `result_extras` DSL)
**Companion docs:** `docs/multihazard_first_principles.md`, `docs/josh-data-schema-v2.md`, `docs/multihazard_status.md`

---

## v3.1 AMENDMENT (2026-05-24, late afternoon)

After implementing Phase B under v3 (six hook phases), user pushback on the "wildfire is structurally unique" framing of `fhsz_haz_class` led to a re-examination of every hazard's variant-specific fields. Result: **every hazard follows the same pattern** — proximity to source → ranked severity → audit-relevant raw fields preserved on the variant. Wildfire isn't special; it's the simplest example of the universal pattern.

This collapsed `build_result` from a hook phase into engine-internal logic driven by a declarative DSL.

**Changes from v3 to v3.1:**

| Aspect | v3 (planned) | v3.1 (implemented) |
|---|---|---|
| Hook phases | 6 (`post_fetch`, `augment_graph`, `classify`, `degradation`, `egress_window`, `build_result`) | **5** (drop `build_result`) |
| Variant-field construction | Per-hazard `build_result` hook (~30-50 lines/hazard) | Declarative `result_extras` block in YAML + engine interpreter (~70 lines total) |
| Per-hazard JS files needed for variant fields | 5 (wildfire, flood, dam, gas, landslide) | 0 (all declarative) |
| Wildfire hook count | 1 (build_result) | **0** (truly zero hooks — uses result_extras only) |
| Total LOC for build_result work at end state | ~250 lines | ~70 lines |

**New YAML field:** `result_extras` on each `HazardConfig`. Each key is a field name to populate on the `HazardResult` variant; each value is `{from: <type>, ...spec}` describing how to derive it. Supported `from:` types:

| `from:` type | Resolves to | Used by |
|---|---|---|
| `zone_lookup` | Constant per-zone value from `table` map | Wildfire `fhsz_haz_class` |
| `containing_feature_attribute` | Attribute X from the polygon containing the project | Flood `bfe_ft`, tsunami `eva_type`, landslide `zone_type` + `burn_year` |
| `all_containing_features` | Array of projected attributes across all polygons containing the project | Dam `dams_affecting` |
| `nearest_feature_attribute` | Attribute from the nearest feature (LineString proximity) | Gas `pir_ft`, `operator`, `product` (Stage 8) |
| `in_zone` | Boolean: `zone !== 'outside'` | Tsunami `in_cgs_tha` |
| `literal` | Static constant value | Tsunami `dispositive: true` |
| `runtime_extras` | `cfg.runtime_extras[key]` | Tsunami `delta_t_informational` |
| `engine_telemetry` | Per-phase telemetry counter | Flood `flooded_exit_nodes_dropped` |

**Files edited in v3.1:**
- `agents/scenarios/hazard_config.py` — added `result_extras` field + validator
- `agents/scenarios/hooks_py.py` — removed `build_result` from `_EXPECTED_ARITY`
- `static/hooks.js` — removed `build_result` from `EXPECTED_ARITY`
- `static/transforms/_defaults.js` — removed `default.build_result` registration + `_WILDFIRE_HAZ_CLASS` constant
- `static/hazard_engine.js` — added `_buildResult` + `_resolveResultExtra` + `_applyResultExtras` internal methods; removed `build_result` hook dispatch
- `config/hazards/wildfire.yaml` — added `result_extras: fhsz_haz_class: {from: zone_lookup, table: ...}`
- `tests/test_hazard_config.py` — added 11 `TestResultExtrasValidation` cases (45 total)
- `tests/test_hooks.js` — removed build_result arity test, added "build_result is NOT a hookable phase" sentinel test (19 total)

**Sections of this doc that need a v3.1 lens when reading:**
- §2 "six hook points" → now **five**; `build_result` row is engine-internal driven by `result_extras`
- §6 YAML examples for flood/dam/gas/landslide → `hooks.build_result` references should be removed; per-hazard variant fields move to `result_extras` blocks
- §7 transform module sketches → flood/dam/gas/landslide `build_result` functions are NOT created (engine handles via DSL); only `augment_graph`, `degradation`, `classify`, `egress_window` transforms remain
- §8 engine sketch → `_buildResult` is engine-internal; no `Hooks.call('...build_result', ...)` dispatch
- §13 open questions Q1 → resolved "5 hooks not 6"

**Why v3.1 is strictly better than v3:**
1. Fewer phases = smaller hook API surface
2. Per-hazard variant knowledge lives in YAML (reviewer-accessible) instead of code
3. Wildfire truly has zero hooks — matches the "simplest case" mental model
4. Adding a new hazard with conventional variant fields = YAML only, no JS
5. Bounded extensibility: 8 `from:` types cover every variant field across 6 hazards in scope

The body of this plan below is preserved as-is for historical reference. Stages 3–9 implementation should follow v3.1 (this amendment + adjusted reading of the body).

---


This document defines Stage 1 as a **JS-only evaluation engine** with a hook
registry, plus a YAML project loader. The Python engine designed in v2 is
eliminated; the same pattern moves to JS. Python's role narrows to its irreducible
job: GeoPandas/OSMnx data preparation at build time.

**Scope boundary:** this revises the Python backend abstraction (eliminating it
in favor of a JS engine) AND eliminates the per-project Python evaluation step.
The locked JS-side tagged-union schema (decision #11), the `HazardResult` variant
shapes (`docs/josh-data-schema-v2.md` §5), the four-switch-site renderer rule, the
brief A/B/C/D structure, and the controlling-hazard determination logic all stand
unchanged.

---

## 1. Motivation

Three architectural observations from the 2026-05-24 conversation:

1. **The Python evaluation engine is duplicative.** `wildland.py` and
   `whatif_engine.js` independently implement the same Dijkstra + ΔT algorithm,
   kept in sync via `test_vectors.json` anti-divergence. This is a discipline
   mechanism for a duplicated codebase — eliminate the duplication and the
   discipline becomes unnecessary.

2. **Python can't do everything JS does — but JS can do everything Python does
   at runtime.** Python's irreducible role is GeoPandas/OSMnx/rasterio: building
   the network graph, spatial joining FHSZ polygons to roads, computing HCM
   capacity per edge. None of that can run in a browser. But once the graph is
   built and the per-edge data is baked, the runtime work (Dijkstra from a point
   to exits, ΔT, tier) is all already in JS.

3. **The Phase D deferral resolves automatically under JS-only.** Today seeded
   projects get pre-baked v2 results from Python while browser-created custom
   projects get only v1 results from JS — the v1→v2 translation has been
   deferred since Stage 0.5. If JS is the only evaluator, seeded and custom
   projects use literally the same code path; there's no translation needed.

**Quantitative argument:**

| Approach | Stage 1 new code | End-state code | Notes |
|---|---|---|---|
| Class-per-hazard (original plan) | ~200 Python lines | ~900 Python lines | + anti-divergence harness |
| Python hooks (v2 of this plan) | ~400 Python lines | ~635 Python lines | + anti-divergence harness + Stage 5 cutover |
| **JS hooks (this plan)** | ~450 JS + ~80 Python lines | ~600 JS + ~120 Python lines | golden-file regression; no Stage 5 cutover; Phase D resolved |

JS-only ships marginally more total lines than v2 but eliminates the entire
anti-divergence/parity-test scaffolding and the Stage 5 cutover. Net complexity
is lower.

---

## 2. The six hook points (in JS)

Same factoring as v2; implementation moves from Python to JS. Hazards override
only where they have non-default behavior.

```
   PIPELINE PHASE                       DEFAULT BEHAVIOR             OVERRIDDEN BY
   ──────────────                       ────────────────             ─────────────

   1. post_fetch(features, params)      features unchanged           landslide (TTL drop)
      → features                                                     gas (PIR buffer compute)
      [build time — Python]                                          [Python pipeline]

   2. augment_graph(graph, features,    no-op                        flood (DEM join +
      params) → graph                                                 BFE freeboard mark)
      [build time — Python]                                          [Python pipeline]

   3. classify(point, features, cfg)    sjoin → max-severity zone   dam (per-feature
      → zone_str                        per cfg.classify_strategy    lookup with names)
      [runtime — JS]                                                 [JS hook]

   4. degradation(edge, zone,           cfg.degradation[zone]        flood (bridge +
      features, params) → float                                       flooded-node check)
      [runtime — JS]                                                 [JS hook]

   5. egress_window(point, zone,        cfg.safe_egress_window[zone] dam (min of
      features, params) → float                                       arrival_time across
      [runtime — JS]                                                  affecting dams)
                                                                     [JS hook]

   6. build_result(hazard_id, zone,     Generic builder that fills   flood (adds bfe_ft)
      paths, delta_t, threshold,        common fields only           dam (adds dams_
      cfg, features) → HazardResult                                    affecting array)
      [runtime — JS]                                                 gas (adds pir_ft,
                                                                       operator, product)
                                                                     [JS hooks]
```

**Phases 1–2 run in Python at pipeline time** because they require GeoPandas
(spatial joins) and rasterio (DEM sampling) that JS can't do. The outputs are
serialized to JOSH_DATA and consumed by JS at runtime.

**Phases 3–6 run in JS at runtime** because they require per-project evaluation
that depends on user-selected scenario, custom what-if parameters, and project
location (none of which Python knows at build time).

**Total hook overrides across 6 hazards: 10.** The other 26 (6 phases × 6 hazards
− 10) use defaults. Wildfire and tsunami register zero hooks; landslide registers
one; flood/dam/gas register three each.

**`compute_delta_t` is intentionally un-hookable** — same reason as v2: it carries
the audit-trail dict read by the brief renderer, and no hazard in scope needs to
override it.

---

## 3. Registry contract (JS)

```javascript
// static/hooks.js
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.Hooks = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var _registry = Object.create(null);

  function register(name, fn) {
    if (typeof name !== 'string' || !name) {
      throw new Error('Hooks.register: name must be a non-empty string');
    }
    if (typeof fn !== 'function') {
      throw new Error('Hooks.register: fn must be a function');
    }
    // Idempotent: re-registering the SAME function under the SAME name is a no-op
    var existing = _registry[name];
    if (existing === fn) return fn;
    if (existing !== undefined) {
      throw new Error(
        'Hooks.register: ' + name + ' already registered by a different function'
      );
    }
    _registry[name] = fn;
    return fn;
  }

  function call(name) {
    var fn = _registry[name];
    if (fn === undefined) {
      throw new Error('Hooks.call: no hook registered under ' + name);
    }
    return fn.apply(null, Array.prototype.slice.call(arguments, 1));
  }

  function has(name) {
    return Object.prototype.hasOwnProperty.call(_registry, name);
  }

  function allRegistered() {
    return Object.keys(_registry).slice().sort();
  }

  // Test-only — production code never calls this.
  function clear() {
    _registry = Object.create(null);
  }

  return { register: register, call: call, has: has, allRegistered: allRegistered, clear: clear };
}));
```

**Validation discipline:** the engine's `validateHookReferences(configs)` function
walks every loaded `HazardConfig.hooks` and asserts every named hook exists in
the registry. Bad references fail loudly at engine init.

**Bundle order:** `static/v1/app.js` (the CDN bundle) concatenates in this order:
`hooks.js` → `transforms/*.js` (which register on import) → `hazard_engine.js`
(which calls `validateHookReferences` at first `evaluateProject` call).

---

## 4. Hook signatures (JSDoc-typed)

JS doesn't have Python's `Protocol` type, but JSDoc + a runtime
arity check at `register()` time gives 90% of the benefit.

```javascript
// static/hooks.js — appended to the module

/**
 * @typedef {function(GeoJSON, Object): GeoJSON} PostFetchHook
 * @typedef {function(Graph, GeoJSON, Object): Graph} AugmentGraphHook
 * @typedef {function(Point, GeoJSON, HazardConfig): string} ClassifyHook
 * @typedef {function(Edge, string, GeoJSON, Object): number} DegradationHook
 * @typedef {function(Point, string, GeoJSON, Object): number} EgressWindowHook
 * @typedef {function(string, string, Path[], number, number, HazardConfig, GeoJSON): HazardResult} BuildResultHook
 */

var EXPECTED_ARITY = {
  'post_fetch':    2, 'augment_graph': 3,
  'classify':      3, 'degradation':   4,
  'egress_window': 4, 'build_result':  7,
};

// Inside register(), after the existing checks:
var prefix = name.split('.')[0];
var expected = EXPECTED_ARITY[prefix];
if (expected !== undefined && fn.length !== expected) {
  throw new Error(
    'Hooks.register: ' + name + ' expected arity ' + expected +
    ' (phase=' + prefix + '), got ' + fn.length
  );
}
```

Static type checking lives in the JSDoc comments; runtime arity checking catches
the most common bug class at registration.

---

## 5. Config schema (YAML in source, JSON in JOSH_DATA)

Hazard configs live as YAML in `config/hazards/{hazard_id}.yaml`. At pipeline
time, `agents/export.py` loads them, validates with a Python dataclass, converts
to JSON, and inlines into `JOSH_DATA.hazard_configs[hazard_id]`.

### 5.1 Python-side loader (build time only)

```python
# agents/scenarios/hazard_config.py — Python build-time validator
from dataclasses import dataclass, field
from typing import Literal
import yaml

HazardId = Literal['wildfire','flood','tsunami','dam_failure','gas_hazmat','landslide']
ClassifyStrategy = Literal['most_severe', 'first_hit', 'all']

@dataclass
class DataSourceSpec:
    type:           Literal['arcgis_rest','geojson_file','composite','npms','dsod']
    cache_key:      str
    url:            str | None = None
    file:           str | None = None
    sources:        list = field(default_factory=list)
    cache_ttl_days: int = 90

@dataclass
class HazardConfig:
    hazard_id:                 HazardId
    data_source:               DataSourceSpec
    mobilization:              float
    dispositive_at_standard_3: bool  = False
    zone_attribute:     str | None        = None
    zone_map:           dict[str, str]    = field(default_factory=dict)
    degradation:        dict[str, float]  = field(default_factory=dict)
    safe_egress_window: dict[str, float]  = field(default_factory=dict)
    classify_strategy: ClassifyStrategy = 'most_severe'
    palette:            dict[str, str]   = field(default_factory=dict)
    labels:             dict[str, str]   = field(default_factory=dict)
    legend_label:       str              = ''
    hooks:              dict[str, str]   = field(default_factory=dict)
    runtime_extras:     dict             = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Locked decision #4 — mobilization floor
        if not (0.90 <= self.mobilization <= 1.0):
            raise ValueError(
                f"hazard {self.hazard_id}: mobilization {self.mobilization} "
                f"outside [0.90, 1.00] — violates NFPA 101 design floor"
            )
        # Dispositive hazards must not define zone tables
        if self.dispositive_at_standard_3 and (self.degradation or self.safe_egress_window):
            raise ValueError(
                f"hazard {self.hazard_id}: dispositive_at_standard_3=True but "
                f"degradation/safe_egress_window tables are non-empty"
            )

    @classmethod
    def from_yaml(cls, path: str) -> 'HazardConfig':
        with open(path) as f:
            raw = yaml.safe_load(f)
        raw['data_source'] = DataSourceSpec(**raw['data_source'])
        return cls(**raw)

    def to_js_payload(self) -> dict:
        """Strip Python-only fields; emit shape consumed by JS engine."""
        from dataclasses import asdict
        d = asdict(self)
        # Drop data_source — pipeline-only; JS doesn't need to know the URL
        d.pop('data_source', None)
        return d
```

### 5.2 JS-side runtime — JOSH_DATA shape

```javascript
window.JOSH_DATA.hazard_configs = {
  wildfire: {
    hazard_id: 'wildfire',
    mobilization: 0.90,
    dispositive_at_standard_3: false,
    zone_attribute: 'HAZ_CLASS',
    zone_map: { '3': 'vhfhsz', '2': 'high_fhsz', '1': 'moderate_fhsz' },
    degradation:        { vhfhsz: 0.35, high_fhsz: 0.50, moderate_fhsz: 0.75, non_fhsz: 1.00 },
    safe_egress_window: { vhfhsz: 45,   high_fhsz: 90,   moderate_fhsz: 120,  non_fhsz: 120 },
    classify_strategy: 'most_severe',
    palette: {...}, labels: {...}, legend_label: 'Wildfire (FHSZ)',
    hooks: {},      // no overrides — all defaults
    runtime_extras: {},
  },
  flood: {...},     // see §6
  tsunami: {...},   // see §6
  // dam_failure, gas_hazmat, landslide — same shape
};
```

**No Pydantic dependency** (architect fix from v2 carries forward — plain dataclass).

---

## 6. Worked YAML examples

Same as v2 — the YAML structure is unchanged. See `docs/plan-multihazard-stage-1-hooks.md` v2 in git history for the full set. Key examples:

### 6.1 Wildfire (`config/hazards/wildfire.yaml`)

```yaml
hazard_id: wildfire
data_source:
  type: arcgis_rest
  url: "https://egis.fire.ca.gov/arcgis/rest/services/FHSZ_SRA_LRA_Combined/MapServer/0"
  cache_key: fhsz.geojson
mobilization: 0.90
dispositive_at_standard_3: false
zone_attribute: HAZ_CLASS
zone_map: {"3": vhfhsz, "2": high_fhsz, "1": moderate_fhsz}
degradation:        {vhfhsz: 0.35, high_fhsz: 0.50, moderate_fhsz: 0.75, non_fhsz: 1.00}
safe_egress_window: {vhfhsz: 45,   high_fhsz: 90,   moderate_fhsz: 120,  non_fhsz: 120}
classify_strategy: most_severe
palette: {vhfhsz: "#d7301f", high_fhsz: "#fc8d59", moderate_fhsz: "#ffeda0", non_fhsz: transparent}
labels:  {vhfhsz: "CAL FIRE FHSZ — Very High", ...}
legend_label: "Wildfire (FHSZ)"
# no hooks — all defaults
```

### 6.2 Flood — three hook overrides (one Python, two JS)

```yaml
hazard_id: flood
data_source: {type: arcgis_rest, url: "https://hazards.fema.gov/...", cache_key: flood_sfha.geojson}
mobilization: 0.90
zone_attribute: FLD_ZONE
zone_map: {AE: ae, A: a, AO: ao, VE: ve, X: x}
degradation:        {ae: 0.20, a: 0.20, ao: 0.35, ve: 0.00, x: 1.00}
safe_egress_window: {ae: 180, a: 180, ao: 180, ve: 360, x: 120}
palette: {...}, labels: {...}, legend_label: "Flood (FEMA NFHL)"
hooks:
  augment_graph: flood.augment_graph     # Python (DEM join) — runs at build time
  degradation:   flood.degradation       # JS — runs at runtime
  build_result:  flood.build_result      # JS — runs at runtime
runtime_extras: {bfe_clearance_ft: 0.5, dem_cache_key: flood_dem.tif}
```

**Hooks split across Python (build time) and JS (runtime).** The hook name's
phase prefix determines which side runs it:
- `post_fetch`, `augment_graph` → Python (pipeline phase)
- `classify`, `degradation`, `egress_window`, `build_result` → JS (runtime phase)

Both sides have their own registry; both register hooks under the same names so
the YAML reads consistently.

---

## 7. Transform module sketches

### 7.1 Python-side (build time) — `agents/scenarios/transforms/flood.py`

```python
# Python — runs during build.py analyze, augments graph.json before serialization
from agents.scenarios.hooks_py import register
import rasterio

@register("flood.augment_graph")
def flood_augment_graph(graph, features, params):
    """Sample DEM at each graph node; mark below-BFE nodes as impassable_for=['flood']."""
    dem = rasterio.open(params["dem_path"])
    bfe_clearance_ft = params["bfe_clearance_ft"]
    for node_id, attrs in graph.nodes(data=True):
        attrs["elevation_ft"] = _sample_dem(dem, attrs["x"], attrs["y"])
        # ... BFE check + impassable marking
    return graph
```

```python
# agents/scenarios/transforms/gas.py — Python (build time, computes PIR polygons)
@register("gas.compute_pir_polygons")
def gas_compute_pir_polygons(centerlines_gdf, params):
    # 0.69 * sqrt(MAOP * D²) buffer per centerline
    ...
```

```python
# agents/scenarios/transforms/landslide.py — Python (build time, TTL filter)
@register("landslide.drop_expired_post_fire")
def drop_expired_post_fire(features, params):
    # Drop post-fire DF features where burn_year < current_year - 3
    ...
```

### 7.2 JS-side (runtime) — `static/transforms/flood.js`

```javascript
// JS — runs during WhatIfEngine evaluation, per project
(function () {
  'use strict';
  var Hooks = (typeof window !== 'undefined' ? window.Hooks : require('../hooks'));

  Hooks.register('flood.degradation', function (edge, zone, features, params) {
    if (edge.bridge === 'yes') return 1.0;
    var uImpassable = (edge.u_attrs && edge.u_attrs.impassable_for || []).indexOf('flood') >= 0;
    var vImpassable = (edge.v_attrs && edge.v_attrs.impassable_for || []).indexOf('flood') >= 0;
    if (uImpassable || vImpassable) return 0.0;
    return params.degradation_by_zone[zone] || 1.0;
  });

  Hooks.register('flood.build_result', function (hazardId, zone, paths, deltaT,
                                                  threshold, cfg, features) {
    return {
      type: 'flood',
      zone: zone,
      zone_label: cfg.labels[zone] || zone,
      bfe_ft: _bfeForZone(zone, features),
      flooded_exit_nodes_dropped: _countFloodedDropped(features),
      degradation: cfg.degradation[zone] || 1.0,
      egress_window_min: cfg.safe_egress_window[zone] || 120,
      threshold: threshold,
      delta_t: deltaT,
      bottleneck: _buildBottleneck(paths),
      route_coords: paths[0] ? _pathToCoords(paths[0]) : null,
      controls: false,
      flagged: deltaT > threshold,
    };
  });
}());
```

```javascript
// static/transforms/dam.js — JS (runtime, per-feature window selection)
Hooks.register('dam.classify', function (point, features, cfg) { ... });
Hooks.register('dam.egress_window', function (point, zone, features, params) {
  // min(arrival_time_min) across features containing point
  ...
});
Hooks.register('dam.build_result', function (...) { /* adds dams_affecting array */ });
```

```javascript
// static/transforms/gas.js — JS (runtime, build_result with operator/product)
Hooks.register('gas.build_result', function (...) {
  /* adds pir_ft, operator, product fields */
});
```

---

## 8. Engine sketch — `static/hazard_engine.js`

Replaces the current `static/whatif_engine.js`. Generic engine, reads
`JOSH_DATA.hazard_configs` and dispatches to hooks where present.

```javascript
// static/hazard_engine.js (replaces whatif_engine.js)
(function (root, factory) {
  // UMD boilerplate
  if (typeof module !== 'undefined' && module.exports) module.exports = factory();
  else root.HazardEngine = factory();
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var Hooks; // late-bound to window.Hooks or require('./hooks')

  function init() {
    Hooks = (typeof window !== 'undefined' ? window.Hooks : require('./hooks'));
    _validateHookReferences(window.JOSH_DATA.hazard_configs);
  }

  function evaluateProject(project, options) {
    options = options || {};
    var configs = window.JOSH_DATA.hazard_configs;
    var graph   = window.JOSH_DATA.graph;
    var params  = window.JOSH_DATA.parameters;

    var results = {};
    for (var hazardId in configs) {
      if (!Object.prototype.hasOwnProperty.call(configs, hazardId)) continue;
      var cfg = configs[hazardId];
      var features = window.JOSH_DATA.hazard_polygons[hazardId].feature_collection;

      // Phase 3: classify (default = sjoin + max-severity)
      var zone = _classify(project.point, features, cfg);

      // Tsunami short-circuit
      if (cfg.dispositive_at_standard_3 && zone !== 'outside') {
        results[hazardId] = _buildDispositiveResult(hazardId, zone, cfg);
        continue;
      }

      // Per-hazard degraded graph (uses Python-baked per-edge zone classification)
      var degradedGraph = _applyDegradation(graph, features, cfg, zone);

      // Phase 5: egress window → ΔT threshold
      var window_min = _egressWindow(project.point, zone, features, cfg);
      var threshold = window_min * params.max_project_share;

      // Dijkstra + ΔT — hazard-agnostic
      var paths = _dijkstraToExits(degradedGraph, project.point);
      var deltaT = _computeDeltaT(project, paths, cfg.mobilization, params);

      // Phase 6: build_result
      results[hazardId] = _buildResult(hazardId, zone, paths, deltaT, threshold, cfg, features);
    }

    var controlling = _pickControlling(results);
    for (var hid in results) results[hid].controls = (hid === controlling);
    return { results: results, controlling_hazard: controlling };
  }

  // ─── Phase dispatchers: hook if registered, default otherwise ───────────

  function _classify(point, features, cfg) {
    var name = cfg.hooks.classify;
    if (name) return Hooks.call(name, point, features, cfg);
    return _defaultClassify(point, features, cfg);
  }

  function _defaultClassify(point, features, cfg) {
    var hits = _pointInPolygonFeatures(point, features);
    if (hits.length === 0) return 'outside';
    if (cfg.classify_strategy === 'first_hit') {
      var raw = hits[0].properties[cfg.zone_attribute];
      return cfg.zone_map[String(raw)] || 'outside';
    }
    // Default 'most_severe' — matches wildland.py max(HAZ_CLASS)
    var mostSevere = null;
    for (var i = 0; i < hits.length; i++) {
      var v = hits[i].properties[cfg.zone_attribute];
      if (v == null) continue;
      var n = parseInt(v, 10);
      if (mostSevere === null || (!isNaN(n) && n > mostSevere)) mostSevere = n;
    }
    return cfg.zone_map[String(mostSevere)] || 'outside';
  }

  function _buildResult(hazardId, zone, paths, deltaT, threshold, cfg, features) {
    var name = cfg.hooks.build_result;
    if (name) return Hooks.call(name, hazardId, zone, paths, deltaT, threshold, cfg, features);
    return _defaultBuildResult(hazardId, zone, paths, deltaT, threshold, cfg, features);
  }

  // ... analogous dispatchers for degradation, egress_window

  return { init: init, evaluateProject: evaluateProject };
}));
```

**Compatibility note:** `HazardEngine.evaluateProject(project, options)` is the new
API. The current `WhatIfEngine.evaluateProject(lat, lon, units, stories)` API is
preserved as a thin wrapper that constructs a project object and calls the new
engine — no breaking change to `sidebar.js` callers in Stage 1.

---

## 9. Per-project YAML — sidebar consumption

Today `JOSH_DATA.projects[*]` carries pre-baked `evaluation` blobs. Under JS-only:
projects carry **inputs only**; the sidebar evaluates them on load.

### 9.1 What ships in JOSH_DATA

```javascript
window.JOSH_DATA.projects = [
  {
    id: 'hills_gateway',
    name: 'Hills Gateway Apartments',
    address: '2700 Hillegass Ave, Berkeley CA',
    lat: 37.8585,
    lng: -122.2547,
    units: 48,
    stories: 3,
    folium_fg_name: 'project_hills_gateway',
    source: 'seeded',         // 'seeded' | 'mock' | 'user'
    // NOTE: no `evaluation` field — JS computes it at load time
  },
  // ... 5 more projects
];
```

### 9.2 Sidebar load-time evaluation

```javascript
// static/sidebar.js — load-time hook
function _hydrateSeededProjects() {
  HazardEngine.init();
  for (var i = 0; i < _projects.length; i++) {
    var p = _projects[i];
    if (p.evaluation) continue;  // user-edited projects keep their stored eval
    var result = HazardEngine.evaluateProject({
      point: { lat: p.lat, lng: p.lng },
      units: p.units,
      stories: p.stories,
      additional_egress_points: p.additional_egress_points || [],
    });
    p.evaluation = {
      schema_version: 2,
      controlling_hazard: result.controlling_hazard,
      tier: _tierFromResults(result.results),
      hazard_results: Object.values(result.results),
    };
  }
  _render();
}
```

Performance budget: Berkeley graph ~12k edges; Dijkstra in JS ~30–80 ms per project;
6 projects × 6 hazards × Dijkstra ≈ 1.5 sec worst case if naively serialized. **Acceptable
without optimization for Stage 1**; if it becomes a problem, dropdown renders immediately
with "evaluating…" placeholders and results fill in async.

### 9.3 Project YAML files

Berkeley's existing `josh-pipeline/projects/berkeley_demo.yaml` is the source. At
build time, `agents/visualization/analysis_map.py` reads it, validates against
the schema, converts to JSON, and inlines into `JOSH_DATA.projects[]`. No
evaluation results are baked in.

**Phase D resolved:** browser-created custom projects use the exact same code
path as seeded projects (`HazardEngine.evaluateProject`) — no translation layer
needed.

---

## 10. Golden-file regression testing (replaces anti-divergence)

`tests/test_whatif_engine.js` (the existing anti-divergence test against
`test_vectors.json`) is replaced by `tests/test_hazard_engine.js` running against
hand-computed golden files.

### 10.1 Golden file shape

```javascript
// tests/golden/berkeley/hills_gateway.expected.json
{
  "project": {
    "id": "hills_gateway",
    "lat": 37.8585, "lng": -122.2547,
    "units": 48, "stories": 3
  },
  "expected": {
    "controlling_hazard": "wildfire",
    "tier": "DISCRETIONARY",
    "hazard_results": [
      {
        "type": "wildfire",
        "zone": "vhfhsz",
        "degradation": 0.35,
        "egress_window_min": 45,
        "threshold": 2.25,
        "delta_t": 11.8,       // hand-computed: (48 * 2.5 * 0.90 / 551) * 60
        "bottleneck": {
          "name": "Foothill Blvd at Marin Ave",
          "eff_cap_vph": 551,  // 1575 * 0.35
          "vehicles": 108
        },
        "controls": true,
        "flagged": true
      }
    ]
  },
  "_provenance": {
    "computed_by": "twgonzalez",
    "computed_date": "2026-05-24",
    "methodology": "Hand-computed from HCM 2022 Table 12-22 + parameters.yaml v4.11",
    "verified_against_spreadsheet": "docs/golden_verification_berkeley.xlsx"
  }
}
```

### 10.2 Test runner

```javascript
// tests/test_hazard_engine.js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

// Bootstrap JOSH_DATA, Hooks, transforms, engine
require('../static/hooks');
require('../static/transforms/flood');
require('../static/transforms/dam');
require('../static/transforms/gas');
const HazardEngine = require('../static/hazard_engine');
global.window = { JOSH_DATA: require('../output/berkeley/josh_data_fixture.json') };

const goldenDir = path.join(__dirname, 'golden', 'berkeley');

for (const file of fs.readdirSync(goldenDir)) {
  if (!file.endsWith('.expected.json')) continue;
  test(`golden: ${file}`, () => {
    const spec = JSON.parse(fs.readFileSync(path.join(goldenDir, file), 'utf-8'));
    HazardEngine.init();
    const got = HazardEngine.evaluateProject({ point: spec.project, ...spec.project });
    assert.deepStrictEqual(_normalize(got), _normalize(spec.expected));
  });
}
```

### 10.3 Coverage

6 golden files for Stage 1 (Berkeley's 4 seeded + 2 mock projects):
- `hills_gateway.expected.json` — wildfire DISCRETIONARY
- `downtown_mid_rise.expected.json` — wildfire MINISTERIAL_WITH_CONDITIONS
- `claremont_hills_terrace.expected.json` — wildfire DISCRETIONARY
- `cedar_street_infill.expected.json` — non-FHSZ, MINISTERIAL_WITH_CONDITIONS
- `cedar_st_bayfront_mock.expected.json` — flood-controlling (mock; flood adapter not yet real)
- `marina_pointe.expected.json` — tsunami-dispositive (mock)

For the 2 mock projects, the golden file documents the *expected mock behavior*;
when the real adapter ships (Stage 3 for flood, Stage 6 for tsunami), the mock
file is replaced with hand-computed real-data expectations.

### 10.4 Why golden files beat anti-divergence

| Today (anti-divergence) | Golden files |
|---|---|
| Python output is "truth"; JS compared to Python | Hand-computed spec is "truth"; engine compared to spec |
| Bug in Python silently appears in JS test pass | Bug in engine fails the golden test |
| Adding a hazard requires generating new test_vectors.json from Python | Adding a hazard requires hand-computing the expected output (forced methodology verification) |
| Reviewer cannot easily inspect why a test passes | Reviewer can read the golden file's expected values + provenance |
| No legal artifact — just engine-vs-engine | Each golden file is a hand-verified legal artifact with provenance |

---

## 11. Stage 1 deliverables

**New files (JS side):**
- `static/hooks.js` (~70 lines) — UMD registry
- `static/hazard_engine.js` (~400 lines) — generic engine with 6 phase dispatchers + defaults
- `static/transforms/flood.js` (~80 lines) — JS-side hooks (degradation, build_result)
- `static/transforms/dam.js` (~70 lines) — JS-side hooks (classify, egress_window, build_result)
- `static/transforms/gas.js` (~50 lines) — JS-side hook (build_result)
- `static/transforms/_defaults.js` (~80 lines) — default classify, degradation, egress_window, build_result registered as `default.*`

**New files (Python side):**
- `agents/scenarios/hazard_config.py` (~110 lines) — dataclass, YAML loader, to_js_payload
- `agents/scenarios/hooks_py.py` (~40 lines) — Python registry (only used for build-time hooks)
- `agents/scenarios/transforms/__init__.py` (imports submodules)
- `agents/scenarios/transforms/flood.py` (~80 lines) — augment_graph hook
- `agents/scenarios/transforms/gas.py` (~60 lines) — compute_pir_polygons hook
- `agents/scenarios/transforms/landslide.py` (~30 lines) — drop_expired_post_fire hook
- `config/hazards/wildfire.yaml` (~30 lines)

**New test files:**
- `tests/test_hooks.js` (~50 lines) — JS registry contract
- `tests/test_hazard_config.py` (~80 lines) — Python dataclass validation
- `tests/test_hazard_engine.js` (~150 lines) — golden-file regression runner
- `tests/golden/berkeley/*.expected.json` (6 files, hand-computed)

**Modified files:**
- `agents/export.py` — load YAMLs via `HazardConfig.from_yaml`; emit `JOSH_DATA.hazard_configs`;
  remove project evaluation pre-baking; replace `export_whatif_engine_js` with
  `bundle_hazard_engine_js` (concatenates `hooks.js` + transforms + engine)
- `agents/visualization/analysis_map.py` — `_build_josh_data_projects` ships inputs only,
  no `evaluation` field
- `static/sidebar.js` — add `_hydrateSeededProjects()` that calls `HazardEngine.evaluateProject`
  on every project at load; route to `HazardEngine` instead of `WhatIfEngine`
- `agents/scenarios/wildland.py` — eventually deleted in Stage 12; for Stage 1, marked
  deprecated but kept callable so existing test_whatif_engine.js still passes during transition

**Retired:**
- `tests/test_vectors.json` — no longer generated (no Python evaluation engine)
- `agents/export.py:export_test_vectors` — removed
- The Python ↔ JS algorithm-string anti-divergence pattern — replaced by golden-file
  regression

**Untouched files** (the win):
- `agents/scenarios/sb79_transit.py` — unchanged
- `agents/capacity_analysis.py` — unchanged (still builds graph + bakes capacity)
- `static/brief_renderer.js` — unchanged (still reads HazardResult tagged-union)
- `static/hazard_polygon_layer.js` — unchanged (still renders polygons)
- `static/whatif_utils.js` — unchanged (MinHeap, haversine still used)
- All Playwright smoke tests — unchanged

**Acceptance criteria:**
1. `config/hazards/wildfire.yaml` loads and validates via `HazardConfig.from_yaml()`
2. `JOSH_DATA.hazard_configs.wildfire` matches the YAML byte-for-byte (modulo `data_source` removal)
3. `tests/test_hooks.js` proves JS registry: idempotent register, clear isolation, missing-hook detection
4. `tests/test_hazard_engine.js` golden tests pass for all 6 Berkeley projects (4 real + 2 mock)
5. **Output `JOSH_DATA.projects[*]` ships without `evaluation` field; sidebar.js hydrates at load time**
6. **All 6 seeded projects render with correct tier badges within 1.5 sec of map load** (no perceptible regression vs. today's pre-baked path)
7. All 8 Playwright smokes pass byte-for-byte (no UI changes visible)
8. **Phase D resolved:** custom projects created via `+ New` show populated hazard panels (same code path as seeded)
9. Existing `tests/test_brief_renderer.js` (20 tests), `test_sidebar.js` (35), `test_project_manager.js` (15), `test_hazard_polygon_layer.js` (27) all pass unchanged

---

## 12. Migration sequence (simpler than v2)

```
   Stage 1: build JS engine + hooks + transforms + golden files; ship              ◀── THIS PLAN
            production hydration via HazardEngine. Phase D resolves.
            wildland.py kept as legacy callable; no parallel runtime path.

   Stage 3: add flood.yaml + flood Python transform (augment_graph for DEM/BFE)
            + flood JS transforms (degradation, build_result) + golden files for
            in-SFHA projects. Address load-phase factoring gap.

   Stage 5: (no cutover needed — engine has been production since Stage 1)
            Berkeley flips wildfire-only flag → multi-hazard true; flood
            results appear in briefs.

   Stages 6–9: tsunami / dam / gas / landslide YAMLs + transforms.

   Stage 12: delete wildland.py and any remaining Python evaluation code.
            HazardEngine is the only path.
```

**No bit-rot risk** because there's no parallel Python production path. The
engine is production from Stage 1.

---

## 13. Comparison vs. v2 (Python-engine plan)

| Dimension | v2 (Python hooks) | v3 (JS-only, this plan) |
|---|---|---|
| **Stage 1 new code** | ~625 Python | ~530 JS + ~280 Python = ~810 total |
| **Per-hazard add** | ~25 YAML + 0–80 Python transform | ~25 YAML + 0–80 JS transform (+ 0–80 Python for hazards needing build-time transforms) |
| **End-state 6-hazard backend** | ~635 Python | ~600 JS + ~200 Python = ~800 total |
| **Anti-divergence test suite** | ~150 lines + maintenance | Removed |
| **Stage 5 cutover** | Required | Not needed |
| **Phase D translation work** | Required at Stage 3+ | Resolved automatically |
| **New files Stage 1** | ~12 | ~14 |
| **JS engine refactor** | Deferred to Stage 3 | Done in Stage 1 |
| **Load-time performance** | Pre-baked, instant | ~1.5 sec hydration on Berkeley (acceptable) |
| **Legal defensibility artifact** | Two implementations agree | Hand-computed golden files with provenance (stronger) |
| **First-pass mental load** | Python engine + JS engine + parity test | One engine, JS, with config + hooks |

Net code is slightly higher (~+165 lines including the new JS engine work) but
the anti-divergence machinery, Stage 5 cutover, and Phase D translation are all
eliminated. **The architectural payoff is the elimination of duplicated work**,
not raw line count.

---

## 14. Locked decisions impacted

| # | Decision | Status under v3 |
|---|---|---|
| 1 | Earthquake out of scope | **Unchanged.** |
| 2 | Tsunami dispositive at Standard 3 | **Unchanged.** Encoded in `tsunami.yaml`. |
| 3 | PIR constant = 0.69 | **Unchanged.** `gas_hazmat.yaml` runtime_extras. |
| 4 | Mobilization ≥ 0.90 floor | **Unchanged.** Enforced by `HazardConfig.__post_init__`. |
| 5 | Build FloodAdapter first | **Reframed (was reframed in v2 too).** Build flood YAML + transforms first (Stage 3). |
| 6 | 4-function HazardAdapter interface | **Superseded by #12.** |
| 7 | Worst-case single hazard drives tier | **Unchanged.** `_pickControlling` logic identical. |
| 8 | A/B/C/D determination format | **Unchanged.** Frontend only. |
| 9 | Right-side sidebar | **Unchanged.** Frontend only. |
| 10 | Stage 0 UI-first prototype phase | **Unchanged.** Complete. |
| 11 | Tagged-union `HazardResult` | **Unchanged.** JS `build_result` hooks construct variants. |
| 12 | Config + hook registry (was v2 wording: "Python engine") | **Revised wording.** Engine moves Python → JS; YAML configs loaded by Python at build time, inlined as JSON in JOSH_DATA, consumed by JS engine. 6-phase hooks split: phases 1–2 in Python (build time), phases 3–6 in JS (runtime). Anti-divergence retired in favor of golden-file regression. |

---

## 15. Open questions — resolved

| # | Question | Resolution |
|---|---|---|
| 1 | 5 vs 6 hooks? | 6 phases (build_result added in v2; carries forward). |
| 2 | classify_strategy default | `most_severe` (matches wildland.py). Configurable per hazard. |
| 3 | Typed runtime_extras? | No — start with `dict`/`object`. Add per-hazard typed submodels later if needed. |
| 4 | Hook namespace collision in tests | Resolved by idempotent `register` + `clear()` in both Python and JS registries. |
| 5 | Migration sequencing / bit-rot | Resolved — no parallel runtime path. Engine is production from Stage 1. |
| 6 | themes.py fate | Keep as compat shim through Stage 5; vocab moves to YAML configs; delete in Stage 12. |
| 7 | YAML location | `josh/config/hazards/` — methodology lives in the engine repo. |
| 8 | Test pattern replacing anti-divergence | Golden-file regression (hand-computed expected outputs with provenance). |
| 9 | Performance of load-time evaluation | Acceptable for Stage 1; ~1.5 sec worst-case on Berkeley. Async progressive rendering reserved for if it becomes a problem. |

---

## 16. Net plan

Stage 1 acceptance is: **the production analysis map evaluates every project in JS
at load time, produces results that match hand-computed golden files for Berkeley's
4 seeded + 2 mock projects, ships without Python evaluation pre-baking, and resolves
the Phase D custom-project gap as a free side effect.**

The hook + config + golden-file pattern lays the foundation for Stages 3–9 to
ship adapters as YAML + transforms only, with no engine code changes.

---

## 17. Related documents

- `docs/multihazard_first_principles.md` §1 (the 4-input insight this plan operationalizes)
- `docs/multihazard_status.md` (locked decisions table; #12 revised)
- `docs/plan-multihazard-mvp.md` §4 (the class-per-hazard Stage 1 plan this supersedes)
- `docs/josh-data-schema-v2.md` (the JS-side schema; unchanged)
- `static/multihazard_fixtures.js` (regression target; superseded by `tests/golden/berkeley/`)

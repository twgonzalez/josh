# Stage 0 — UI Prototype with Mock Data (expanded)

**Status:** Draft for review
**Date:** 2026-05-17
**Parent plan:** `docs/plan-multihazard-mvp.md` §3
**Locked decisions in scope:** #6 (4-fn adapter), #7 (controlling hazard), #8 (A/B/C/D brief)

---

## 1. Why Stage 0 is being expanded

The MVP plan today defines Stage 0 as a one-day "merge the scaffold + mockup" formality.
That formulation is correct for branch hygiene but **does not actually validate the
multi-hazard UX before we start refactoring production Python**. The risk:

- Stage 1 (`HazardAdapter` refactor) will design data shapes around assumptions baked into
  the mockup's hardcoded `HZD = { wf: {...}, fl: {...} }` fixture (see
  `output/mockup/multihazard_on_berkeley.html:5065`). That fixture is **not normalized** —
  it keys per-hazard at the JS literal level, so adding tsunami means adding a `ts:` key.
- The current production `JOSH_DATA` schema bakes wildfire-FHSZ-specific terms into every
  layer: `JOSH_DATA.fhsz` (singleton), `parameters.hazard_degradation.{vhfhsz,high_fhsz,…}`
  (FHSZ-named keys), `graph.edges[].fhsz_zone`, `path.bottleneckFhszZone`, `_classifyFhsz()`
  hard-coded to `HAZ_CLASS`. If Stage 1 inherits these names, we will pay refactor cost
  again at Stage 3 (FloodAdapter).
- The mockup is a 11.8 MB visual contract. It demonstrates layout and the per-hazard ΔT
  bar chart pattern, but it never **drives the production sidebar with normalized
  mock data**. We don't actually know yet whether the production `sidebar.js` and
  `brief_renderer.js` can render a multi-hazard project until we try.

**Goal of the expanded Stage 0:** get the production sidebar + brief renderer rendering
a multi-hazard project from a normalized mock fixture, with **zero changes** to the Python
pipeline or any adapter logic. Once that works, Stage 1 has a known, tested target schema
to refactor Python against.

---

## 2. Definition of done

Stage 0 is complete when **all** of these are true:

1. A new JS module `static/multihazard_fixtures.js` exports a normalized mock multi-hazard
   payload for Berkeley's existing 6 projects, plus 1 hand-crafted in-SFHA project.
2. `static/sidebar.js` renders that payload — hazard layer panel, project dropdown,
   per-hazard ΔT bar chart, hazard scenario radio, Hazards Evaluated list — driven by
   the normalized schema (no hardcoded `wf:`/`fl:` keys, no FHSZ-only assumptions).
3. `static/brief_renderer.js` renders Section B and Section C as per-hazard tables and
   highlights the controlling hazard row.
4. The map renders ≥ 2 hazard polygon layers (real Berkeley FHSZ + faked Berkeley flood
   SFHA) via a generic `HazardPolygonLayer` abstraction — no FHSZ-specific Leaflet code path.
5. AntPath route geometry swaps when the hazard scenario radio changes (using
   mock-different routes per hazard, since real per-hazard routing is Stage 3).
6. The four existing test suites (`test_whatif_engine.js`, `test_brief_renderer.js`,
   `test_sidebar.js`, `test_project_manager.js`) all stay green. New tests added for the
   new render paths.
7. A normalization decision doc (`docs/josh-data-schema-v2.md`, stub from §6 of this plan)
   captures the schema choices made under mock data, ready for Stage 2 to formalize.
8. `multihazard: true` feature flag in `cities/berkeley.yaml` activates the mock UI;
   `false` (or absent) is byte-identical to today's production map.
9. `main` remains untouched. All work lands on `feature/multi-hazard` substages.

Explicitly **out of scope** for Stage 0:
- Any change to Python adapter code, `agents/scenarios/`, or `agents/objective_standards.py`
- Real hazard data acquisition (FEMA NFHL, CGS, DSOD, NPMS — all Stage 3+)
- `HazardAdapter` Python ABC (Stage 1)
- Brief PDF / print / save (preserve existing behavior, do not extend)
- Audit trail `.txt` per-hazard sections (Stage 4+ — preserve existing single-hazard output)

---

## 3. What the production payload looks like today

Inspected directly. The fields below are the FHSZ-specific coupling points that Stage 0
must normalize.

### 3.1 Top-level `JOSH_DATA`

```js
JOSH_DATA = {
  graph:      { nodes: [...], edges: [...] },  // OSMnx export
  parameters: { hazard_degradation: {...}, safe_egress_window: {...}, ... },
  fhsz:       { type: "FeatureCollection", features: [...] },  // SINGLETON, top-level
  projects:   [ { id, name, lat, lng, units, stories, folium_fg_name, ... } ],
  briefs:     { [project_id]: html_string }  // pre-baked
}
```

**Coupling:** `fhsz` is a hardcoded root key. There is no slot for any other hazard polygon
layer. `briefs[id]` is pre-baked HTML — incompatible with per-hazard rendering.

### 3.2 Per-edge graph data (from `agents/export.py:614`)

```python
edge_record = {
    "u": ..., "v": ..., "key": ...,
    "length_m": ..., "speed_kph": ..., "lanes": ...,
    "fhsz_zone": "vhfhsz" | "high_fhsz" | "moderate_fhsz" | "non_fhsz",
    "haz_deg": 0.35,
    "eff_cap_vph": 551.0,
    "wgs84_coords": [...],
}
```

**Coupling:** every edge carries one `fhsz_zone` string and one `haz_deg` factor.
Multi-hazard needs per-hazard zone/degradation per edge.

### 3.3 Parameters block (`agents/export.py:702`)

```python
{
  "hazard_degradation": { "vhfhsz": 0.35, "high_fhsz": 0.50, "moderate_fhsz": 0.75, "non_fhsz": 1.00 },
  "safe_egress_window": { "vhfhsz": 45,   "high_fhsz": 90,   "moderate_fhsz": 120,  "non_fhsz": 120  },
  "max_project_share":  0.05,
  "fhsz_trigger_zones": [2, 3],
}
```

**Coupling:** keys are FHSZ zone names. Tsunami parameter set can't slot in without
either namespace collision or schema-level discrimination.

### 3.4 Per-project evaluation result (from `static/sidebar.js:184` and `whatif_engine.js`)

```js
{
  hazard_zone:               "vhfhsz",         // single hazard
  hazard_degradation_factor: 0.35,
  in_fire_zone:              true,
  paths: [
    {
      bottleneck_fhsz_zone:          "vhfhsz",
      bottleneck_hazard_degradation: 0.35,
      delta_t:                       11.8,
      ...
    }
  ],
  fhsz_flagged:              true,
  fhsz_desc:                 "Very High Fire Hazard Severity Zone",
  fhsz_level:                3,
}
```

**Coupling:** result shape is mono-hazard. There is no `hazard_results[]` collection,
no `controlling_hazard`, no per-hazard threshold.

### 3.5 FHSZ classification function (`agents/export.py:154`, JS mirror)

```js
function classifyFhsz(lat, lon) {
  if (!_fhsz || !_fhsz.features) return "non_fhsz";
  const sorted = [..._fhsz.features].sort((a,b) => HAZ_CLASS_b - HAZ_CLASS_a);
  for (const f of sorted) {
    if (pointInPolygon([lon,lat], f.geometry)) {
      if (haz >= 3) return "vhfhsz";
      if (haz === 2) return "high_fhsz";
      if (haz === 1) return "moderate_fhsz";
    }
  }
}
```

**Coupling:** assumes feature property is `HAZ_CLASS`, integer 1–3. FEMA NFHL uses
`FLD_ZONE` string ("AE", "AO", "VE"). CGS Tsunami uses `Eva_Type`. Function shape can
generalize but must be polymorphic over `{zone_attribute, zone_map}`.

### 3.6 Polygon rendering (`agents/visualization/analysis_map.py:273`)

```python
if not fhsz_gdf.empty and "HAZ_CLASS" in fhsz_gdf.columns:
    for row in fhsz_wgs84.iterrows():
        color = FHSZ_COLORS.get(haz, "#ffeda0")
        folium.GeoJson(...)
```

**Coupling:** hardcoded `HAZ_CLASS` column check, hardcoded `FHSZ_COLORS`/`FHSZ_LABELS`
import from `themes.py`. There is no abstraction over hazard polygon layers.

---

## 4. Normalization targets (the new mock-data schema)

These are the shapes Stage 0 will encode in `static/multihazard_fixtures.js` and consume
in `sidebar.js` / `brief_renderer.js`. They are **proposed** here — the final canonical
form lands in `docs/josh-data-schema-v2.md` at the end of Stage 0 (see §6.h).

**Design principle (locked decision #11, see status doc):** with six finite hazards each
carrying genuinely different physics, schema and renderer use **explicit tagged-union
result types** with a hazard-specific shape per type. Uniformity is preserved where the
data really is uniform (polygon layer records, project-level fields, the orchestrator's
`HazardAdapter` interface from decision #6). Hazard-specific behavior lives in exactly
one named switch case per consumer — no semi-abstractions that hide where the hazard
logic is. This buys debuggability + type safety at the cost of one renderer switch case
per hazard. With 6 cases total, that cost is bounded.

### 4.0 Per-hazard data requirements

Each hazard's data requirements documented explicitly. Adapters consume the corresponding
columns; renderers consume the corresponding `HazardResult` variant in §4.2.

| Hazard | Source authority | Polygon feature properties (required) | Graph node attrs | Adapter parameters |
|---|---|---|---|---|
| **Wildfire** | CAL FIRE OSFM FHSZ | `HAZ_CLASS` (int 1–3) | — | `degradation_by_zone`, `safe_egress_window_by_zone`, `mobilization=0.90` |
| **Flood** | FEMA NFHL | `FLD_ZONE` (string: AE/A/AO/VE/X), `BFE_FT` (float, nullable in X) | `elevation_ft` (USGS 3DEP DEM 10 m) | `degradation_by_zone`, `safe_egress_window=180`, `bfe_clearance_ft=0.5`, `mobilization=0.90` |
| **Tsunami** | CGS Tsunami Hazard Area (item 2769c700c0694548b5435a60ff52b807) | `Eva_Type` (string) | — | `dispositive_at_standard_3=true`, `egress_window_informational=15` (USGS Cascadia near-field) |
| **Dam failure** | DSOD inundation polygons + per-dam EAPs | `DAM_NAME` (string), `ARRIVAL_TIME_MIN` (int — from EAP) | — | `degradation_in_zone`, `mobilization=0.95`, fallback `arrival_time_min=30` (<5 mi) / `120` (5–50 mi) |
| **Gas/hazmat** | NPMS pipelines + JOSH-computed PIR buffer | On pipeline segments: `OPERATOR`, `PRODUCT`, `MAOP_PSIG` (nullable), `DIAM_IN` (nullable) | — | `pir_constant=0.69` (PHMSA TTO-13, per locked decision #3), `default_pir_ft=660`, `degradation_in_pir`, `mobilization=0.95` |
| **Landslide** | USGS post-fire DF hazard + CGS EILZ | `ZONE_TYPE` (`post_fire_df`\|`eilz`), `BURN_YEAR` (int, nullable for EILZ) | — | `degradation_in_zone=0.50`, `safe_egress_window=60` (NWS DF warning lead time), `mobilization=0.90`, `post_fire_ttl_years=3` |

Notes on per-hazard quirks:
- **Flood** is the only hazard requiring a graph-node attribute (`elevation_ft`) beyond
  what the standard OSMnx export carries. The pipeline (Stage 3) must join DEM samples to
  graph nodes at acquisition time.
- **Dam failure** is the only hazard where the egress window is feature-level (per-dam),
  not zone-level. The `egress_window_min` field on `DamFailureResult` is the worst-case
  across all affecting dams.
- **Gas/hazmat** is the only hazard whose polygon is **computed** by the pipeline (PIR
  buffer around centerlines), not downloaded. The `feature_collection` in `hazard_polygons.gas_hazmat`
  is still GeoJSON polygons — the computation is invisible to the renderer.
- **Tsunami** is the only hazard with `dispositive_at_standard_3=true`. Its
  `TsunamiResult` shape lacks `delta_t` and `threshold` (those are not computed); only
  `delta_t_informational` is shown, in a footnote in brief Section C.
- **Landslide** is the only hazard with a TTL — post-fire DF products expire ~3 years
  after burn. Polygons drop out of `feature_collection` when `current_year - BURN_YEAR > 3`
  for `ZONE_TYPE='post_fire_df'`.

### 4.1 Top-level multi-hazard extension

```js
JOSH_DATA = {
  // ── unchanged ──────────────────────────────────────────────────────
  graph: { ... },
  parameters: { ... },
  projects: [ ... ],

  // ── DEPRECATED, kept for v1-fallback only when multihazard flag is off ──
  fhsz: { ... },           // existing FHSZ FeatureCollection
  briefs: { [id]: html },  // pre-baked single-hazard HTML

  // ── NEW (only present when city.multihazard === true) ──────────────
  schema_version: 2,
  applicable_hazards: ["wildfire", "flood"],       // city-level list
  hazard_polygons: {
    wildfire: {
      feature_collection: GeoJSON,
      zone_attribute: "HAZ_CLASS",
      zone_map: { "3": "vhfhsz", "2": "high_fhsz", "1": "moderate_fhsz" },
      legend_label: "Wildfire (FHSZ)",
      palette: { vhfhsz: "#d62728", high_fhsz: "#ff7f0e", moderate_fhsz: "#fdae61", non_fhsz: "transparent" }
    },
    flood: {
      feature_collection: GeoJSON,
      zone_attribute: "FLD_ZONE",
      zone_map: { "AE": "ae", "A": "a", "AO": "ao", "VE": "ve" },
      legend_label: "Flood (FEMA NFHL — faked)",
      palette: { ae: "#1f77b4", a: "#1f77b4", ao: "#3399cc", ve: "#08306b" }
    }
    // future: tsunami, dam_failure, gas_hazmat, landslide
  },

  hazard_parameters: {
    wildfire: {
      degradation:        { vhfhsz: 0.35, high_fhsz: 0.50, moderate_fhsz: 0.75, non_fhsz: 1.00 },
      safe_egress_window: { vhfhsz: 45,   high_fhsz: 90,   moderate_fhsz: 120,  non_fhsz: 120  },
      mobilization:       0.90,
      dispositive_at_standard_3: false
    },
    flood: {
      degradation:        { ae: 0.20, a: 0.20, ao: 0.35, ve: 0.00, x: 1.00 },
      safe_egress_window: { ae: 180, a: 180, ao: 180, ve: 60, x: 180 },
      mobilization:       0.90,
      dispositive_at_standard_3: false
    }
    // tsunami will be { dispositive_at_standard_3: true } — implements locked decision #2
  }
}
```

**Why this shape:**
- `hazard_polygons[hazardId]` is a uniform record — every hazard works the same way.
  No singleton, no top-level key per hazard.
- `zone_attribute` + `zone_map` makes the classifier polymorphic. Adding a hazard means
  adding an entry, not touching `_classifyFhsz` logic.
- `hazard_parameters[hazardId]` namespaces all parameter dicts. No name collisions.
- `dispositive_at_standard_3` slot lets Stage 6 (Tsunami) ship without retrofitting.

### 4.2 Per-project hazard results — tagged union

```ts
// Discriminated union — each variant is an explicit named shape with hazard-specific fields.
type HazardResult =
  | WildfireResult | FloodResult | TsunamiResult
  | DamFailureResult | GasHazmatResult | LandslideResult;

// Common base — every variant carries these fields.
interface BaseResult {
  type:      HazardId;                    // the discriminator — switch on this
  controls:  boolean;                     // is the controlling hazard for the project
  flagged:   boolean;                     // delta_t > threshold (false for dispositive types)
  excluded?: { reason: string };          // present iff hazard inapplicable to this site
}

interface WildfireResult extends BaseResult {
  type:           'wildfire';
  zone:           'vhfhsz' | 'high_fhsz' | 'moderate_fhsz' | 'non_fhsz';
  zone_label:     string;                 // display only — "Very High FHSZ"
  fhsz_haz_class: 1 | 2 | 3;              // CAL FIRE source encoding
  degradation:    number;                 // hazard_parameters.wildfire.degradation[zone]
  egress_window_min: number;
  threshold:      number;                 // window × max_project_share
  delta_t:        number;
  bottleneck:     { name: string; eff_cap_vph: number; vehicles: number };
  route_coords:   Array<[number, number]>;
}

interface FloodResult extends BaseResult {
  type:           'flood';
  zone:           'ae' | 'a' | 'ao' | 've' | 'x';
  zone_label:     string;
  bfe_ft:         number | null;          // null in X
  flooded_exit_nodes_dropped: number;     // telemetry — non-zero proves BFE filter ran
  degradation:    number;
  egress_window_min: number;
  threshold:      number;
  delta_t:        number;
  bottleneck:     { name: string; eff_cap_vph: number; vehicles: number };
  route_coords:   Array<[number, number]>;
}

interface TsunamiResult extends BaseResult {
  type:           'tsunami';
  in_cgs_tha:     boolean;
  eva_type:       string | null;          // CGS Eva_Type attribute, null if not in zone
  dispositive:    true;                   // structurally true — no `false` variant exists
  delta_t_informational: number;          // never compared to a threshold; shown as footnote
  route_coords:   null;                   // no route computed under dispositive logic
  // intentionally absent: delta_t, threshold, bottleneck (not part of tsunami semantics)
}

interface DamFailureResult extends BaseResult {
  type:           'dam_failure';
  zone:           'in_inundation' | 'outside';
  dams_affecting: Array<{ name: string; arrival_time_min: number }>;
  egress_window_min: number;              // = min(d.arrival_time_min) across affecting dams
  degradation:    number;
  threshold:      number;
  delta_t:        number;
  bottleneck:     { name: string; eff_cap_vph: number; vehicles: number };
  route_coords:   Array<[number, number]>;
}

interface GasHazmatResult extends BaseResult {
  type:           'gas_hazmat';
  in_pir:         boolean;
  pir_ft:         number;                 // 0.69 × √(MAOP × DIAM²); fallback 660
  operator:       string | null;
  product:        'natural_gas' | 'hazardous_liquid' | 'unknown';
  degradation:    number;
  egress_window_min: number;
  threshold:      number;
  delta_t:        number;
  bottleneck:     { name: string; eff_cap_vph: number; vehicles: number };
  route_coords:   Array<[number, number]>;
}

interface LandslideResult extends BaseResult {
  type:           'landslide';
  zone_type:      'post_fire_df' | 'eilz' | 'none';
  burn_year:      number | null;          // post-fire only; null for EILZ
  degradation:    number;
  egress_window_min: number;
  threshold:      number;
  delta_t:        number;
  bottleneck:     { name: string; eff_cap_vph: number; vehicles: number };
  route_coords:   Array<[number, number]>;
}

// Project envelope wraps a heterogeneous list:
project.evaluation = {
  schema_version:     2,
  applicability:      { units_meet_threshold: true, units: 48, threshold: 15 },
  controlling_hazard: 'wildfire' | 'flood' | 'tsunami' | 'dam_failure' | 'gas_hazmat' | 'landslide' | null,
  hazard_results:     HazardResult[],     // mixed-type list — switch on r.type in consumers
  tier:               'DISCRETIONARY' | 'MINISTERIAL_WITH_STANDARD_CONDITIONS' | 'MINISTERIAL'
};
```

**Why this shape:**
- **Tagged union**, not generic record with optional fields. Each variant lists exactly
  the fields that hazard needs; absent fields are absent, not nullable. A `TsunamiResult`
  with `dispositive: true` is structurally guaranteed to not have a `delta_t` field —
  the type system (in TypeScript / JSDoc) flags any consumer that tries to read it.
- **`type` is the discriminator.** Renderers `switch (r.type)`. The 6 cases are
  exhaustive (TypeScript would enforce this; we get the same via convention + tests).
- **No flag-based hidden dispatch.** Earlier draft had `dispositive: boolean` as a
  Boolean flag on a generic shape. That was the semi-abstraction this design rejects.
  Now `dispositive` is structurally part of `TsunamiResult` only; no other variant has
  the field. Adding a future dispositive hazard means adding a new variant, not flipping
  a flag on a generic shape.
- **Excluded hazards** carry `excluded: { reason: string }`. When present, all other
  fields except `type` and `controls: false` are absent. Renderer treats it as a
  Section D row.

### 4.2.1 Renderer rule (single-switch-site discipline)

```
RULE: Every hazard-specific UI behavior lives in exactly one named switch case
      over `result.type`, in exactly one renderer function per surface. No flag-based
      hidden dispatch. No "if r.dispositive" guards on generic shapes.
```

The four switch sites:

1. `_renderHazardBarRow(result)` in `sidebar.js` — bar chart row. 6 cases.
2. `_renderHazardListItem(result)` in `sidebar.js` — Hazards Evaluated bullet. 6 cases.
3. `BriefRenderer._renderBRow(result)` — Section B row. 6 cases.
4. `BriefRenderer._renderCRow(result)` — Section C row. 6 cases (tsunami renders "Dispositive at Standard 3" instead of the ΔT computation).

A pre-merge review grep should confirm no `result.type === 'X'` checks outside these four
functions. If a fifth consumer needs hazard-specific behavior, it gets a fifth named
switch site — never an inline conditional.

### 4.3 Mock fixture format

`static/multihazard_fixtures.js` exports one object per Berkeley project, plus two
hand-crafted controlling-hazard fixtures (flood and tsunami) to exercise every branch
of the controlling/dispositive logic in mock data before any adapter ships:

```js
window.JOSH_MOCK_MULTIHAZARD = {
  // ── 6 real Berkeley projects — wildfire-controlling, mirrors current pipeline output ──
  hills_gateway: {
    controlling_hazard: 'wildfire',
    tier: 'DISCRETIONARY',
    hazard_results: [
      {
        type: 'wildfire', controls: true, flagged: true,
        zone: 'vhfhsz', zone_label: 'Very High FHSZ', fhsz_haz_class: 3,
        degradation: 0.35, egress_window_min: 45, threshold: 2.25, delta_t: 11.8,
        bottleneck: { name: 'Spruce St at Marin Ave', eff_cap_vph: 551, vehicles: 108 },
        route_coords: [/* real wildfire AntPath for this project */]
      },
      {
        type: 'flood', controls: false, flagged: false,
        zone: 'x', zone_label: 'X (unshaded)', bfe_ft: null,
        flooded_exit_nodes_dropped: 0,
        degradation: 1.00, egress_window_min: 180, threshold: 9.00, delta_t: 1.1,
        bottleneck: { name: 'Spruce St at Marin Ave', eff_cap_vph: 1575, vehicles: 108 },
        route_coords: [/* mock-different from wildfire route — slight offset */]
      }
    ]
  },
  claremont_hills_terrace: { /* same shape, wildfire VHFHSZ controls */ },
  downtown_mid_rise:       { /* wildfire moderate, passes; flood passes */ },
  university_park:         { ... },
  westbrae_commons:        { ... },
  ashby_corridor:          { ... },

  // ── Hand-crafted: flood controlling ──
  // Bayfront / Cedar St corridor near I-80 — wildfire passes, flood AE bottleneck fails
  // Exercises locked decision #7 (worst-case single hazard drives tier) under non-wildfire
  cedar_street_infill: {
    controlling_hazard: 'flood',
    tier: 'DISCRETIONARY',
    hazard_results: [
      {
        type: 'wildfire', controls: false, flagged: false,
        zone: 'moderate_fhsz', zone_label: 'Moderate FHSZ', fhsz_haz_class: 1,
        degradation: 0.75, egress_window_min: 120, threshold: 6.00, delta_t: 2.1,
        bottleneck: { name: 'Cedar St at MLK Way', eff_cap_vph: 980, vehicles: 47 },
        route_coords: [/* mock */]
      },
      {
        type: 'flood', controls: true, flagged: true,
        zone: 'ae', zone_label: 'AE', bfe_ft: 14.5,
        flooded_exit_nodes_dropped: 3,
        degradation: 0.20, egress_window_min: 180, threshold: 9.00, delta_t: 14.2,
        bottleneck: { name: 'Cedar St at I-80 underpass', eff_cap_vph: 304, vehicles: 47 },
        route_coords: [/* mock — different route avoiding flooded nodes */]
      },
      {
        type: 'tsunami', controls: false, flagged: false,
        excluded: { reason: 'Project location is inland; not in CGS Tsunami Hazard Area.' }
      }
    ]
  },

  // ── Hand-crafted: tsunami dispositive at Standard 3 ──
  // Coastal Marina-adjacent project in CGS Tsunami Hazard Area
  // Exercises locked decision #2 (tsunami in-zone → DISCRETIONARY at Std 3, ΔT informational)
  marina_pointe: {
    controlling_hazard: 'tsunami',
    tier: 'DISCRETIONARY',
    hazard_results: [
      {
        type: 'wildfire', controls: false, flagged: false,
        zone: 'non_fhsz', zone_label: 'Not in FHSZ', fhsz_haz_class: 0,
        degradation: 1.00, egress_window_min: 120, threshold: 6.00, delta_t: 3.4,
        bottleneck: { name: 'University Ave at Frontage Rd', eff_cap_vph: 1700, vehicles: 240 },
        route_coords: [/* mock */]
      },
      {
        type: 'flood', controls: false, flagged: false,
        zone: 'ae', zone_label: 'AE', bfe_ft: 10.2,
        flooded_exit_nodes_dropped: 1,
        degradation: 0.20, egress_window_min: 180, threshold: 9.00, delta_t: 6.1,
        bottleneck: { name: 'University Ave at Frontage Rd', eff_cap_vph: 340, vehicles: 240 },
        route_coords: [/* mock */]
      },
      {
        type: 'tsunami', controls: true, flagged: true,
        in_cgs_tha: true, eva_type: 'Tsunami Inundation Zone',
        dispositive: true,
        delta_t_informational: 18.4,   // shown only as footnote in brief Section C
        route_coords: null              // dispositive — no route computed
      }
    ]
  }
};
```

**Why both hand-crafted fixtures matter for Stage 0:**
- The flood case proves the **controlling hazard can be non-wildfire** in the renderer
  before any FloodAdapter ships (Stage 3).
- The tsunami case proves the **`dispositive: true` rendering path** works — Section C
  shows "Dispositive at Standard 3 — in CGS Tsunami Hazard Area" instead of a ΔT row,
  with the informational ΔT relegated to a footnote. This validates decision #2's
  rendering implications before any TsunamiAdapter ships (Stage 6).

The hand-crafted fixtures are deleted in their respective stages (cedar_street_infill
in Stage 3 when FloodAdapter takes over; marina_pointe in Stage 6 when TsunamiAdapter
takes over).

When `multihazard: true` is set in `cities/berkeley.yaml`, the pipeline emits
`window.JOSH_DATA.applicable_hazards`, `hazard_polygons`, `hazard_parameters`. The mock
fixture file is loaded **after** `JOSH_DATA` and **merges** `mock.hazard_results` onto
each project (the production seeded project — same coordinates, mock evaluation result).
The merge is feature-flagged by `JOSH_DATA.schema_version === 2`; v1 fallback is a no-op.

---

## 5. Exact UI/UX changes (mapped to production code)

These are the surfaces `sidebar.js` and `brief_renderer.js` need to grow. Each row notes
where production code lives today and what the mockup demands.

| # | Surface | Production today | Mockup contract | Sub-stage |
|---|---|---|---|---|
| 1 | **Hazard layer panel** (checkbox list) | None — Folium emits a layer control in `topright` for FHSZ + project FGs | Right-sidebar `mhz-panel` with one row per hazard, colored swatch, label, toggle layer visibility | **0b** |
| 2 | **Project dropdown** (replaces Folium popup) | `_renderProjectList` (sidebar.js:~3700) — list of cards | `<select class="mhz-proj-select">` rendered from `JOSH_DATA.projects` | **0c** |
| 3 | **No marker popup** | Folium GeoJson popups bound per project marker | Marker click → `selectProject(id)`, no popup | **0c** |
| 4 | **Project detail card** (name, address, meta line, stat cards) | `_renderProjectDetail` renders this; stat cards already exist | Mockup uses `mhz-stat-row` with `units` + `stories` big numbers; layout differs from production | **0d** |
| 5 | **Tier banner with "driven by X"** | Tier pill, no controlling-hazard line | `mhz-tier` with `<span class="driven">driven by Wildfire</span>` | **0d** |
| 6 | **Per-hazard ΔT bar chart** | None — single ΔT shown in audit trail/brief | `mhz-dt-row` × N: label + horizontal track + bar (fail/pass/controls state) + value/threshold. Implemented as `_renderHazardBarRow(result)` with a `switch (result.type)` — 6 cases per §4.2.1 | **0d** |
| 7 | **Hazard scenario radio** | None | `mhz-scen` panel: "Controlling (default)" + one radio per applicable hazard; changes the visible AntPath | **0e** |
| 8 | **Hazards Evaluated list** | None | `<ul class="mhz-hz-list">` with dot + name + zone + ΔT + "controls" badge | **0d** |
| 9 | **Open Brief button** | Existing | Existing — wire through to A/B/C brief renderer | **0d** |
| 10 | **Brief Section B (per-hazard)** | Single FHSZ row | Table: Hazard / Zone / Degradation / Egress window / ΔT threshold. `BriefRenderer._renderBRow(result)` is a `switch (result.type)` with 6 cases per §4.2.1 (tsunami row omits degradation/threshold columns) | **0f** |
| 11 | **Brief Section C (per-hazard)** | Per-route table (within single hazard) | Table: Hazard / Bottleneck / Eff capacity / Project veh / ΔT / Threshold / Result. `BriefRenderer._renderCRow(result)` is a `switch (result.type)` with 6 cases. Tsunami case renders "Dispositive at Standard 3 — in CGS Tsunami Hazard Area" instead of the ΔT row, with `delta_t_informational` as a footnote; controlling row highlighted | **0f** |
| 12 | **Brief Section D (excluded hazards)** — informational | None | `_renderSectionDExcluded(results)` iterates `hazard_results.filter(r => r.excluded)` (each excluded result carries `excluded: { reason: string }` per §4.2). Bullet list: hazard display name + reason. Implements locked decision #8 | **0f** |
| 13 | **Determination footer with controlling hazard** | Tier + reason (single hazard) | `mhz-det` block: tier text + "controlling hazard" reason line | **0f** |
| 14 | **Hazard polygon Leaflet rendering** | `analysis_map.py:273` hardcoded FHSZ GeoJson | `HazardPolygonLayer` factory: takes `hazard_polygons[hazardId]` + builds a `L.geoJSON` with per-feature `zone` style | **0b** |
| 15 | **AntPath route swap on scenario change** | `_drawRoutes()` in sidebar.js renders controlling routes | Same renderer, but uses `hazard_results[scenarioIdx].route_coords` if present, else controlling-hazard fallback | **0e** |
| 16 | **Right-side sidebar position** (per first-principles memo §7.3 inspector pattern) | Left sidebar fixed | Right sidebar fixed (`right: 0`). The mockup keeps it on the left because it overlays production; Stage 0 migrates to the right. | **0g** |

### 5.1 Surface preservation requirements (no regression)

Per `plan-multihazard-mvp.md` §1.5, the following production features must continue to
work end-to-end when `multihazard: true`:

- Custom (browser-created) projects via the existing form
- AntPath marching ants animation (no styling change)
- Audit trail `.txt` download (Stage 0 keeps single-hazard output; per-hazard sections in Stage 4+)
- Brief HTML save / print / PDF
- Project CRUD + FSAPI persistence + YAML export
- Re-analyze indicator
- Home-icon visibility rule (pin shown only when project selected)
- OSMnx edge geometry for routes
- Standard 5 SB 79 informational flag

Stage 0 implementation strategy for these: every existing render function gets an
**early-return / shape-check** at the top — if `JOSH_DATA.schema_version !== 2`, fall
through to existing behavior unchanged. New render paths run only behind the flag.

---

## 6. Sub-stage breakdown

| # | Sub-stage | Output | Effort | Depends on |
|---|---|---|---|---|
| **0a** | **Baseline snapshot** | `tests/snapshots/baseline/{test_vectors.json, briefs/*.html, audit/*.txt, sidebar_state.json}` captured from current Berkeley pipeline. Becomes the no-regression bar for every later sub-stage. | S (½ day) | none |
| **0b** | **`HazardPolygonLayer` rendering abstraction** | New JS module `static/hazard_polygon_layer.js`. Refactor `analysis_map.py:273` FHSZ block to emit `JOSH_DATA.hazard_polygons.wildfire` (when flag on) or the legacy `JOSH_DATA.fhsz` (when flag off). Layer panel toggles call this. | M (2 days) | 0a |
| **0c** | **Project dropdown + no-popup mode** | Mock-flag-only: when `schema_version === 2`, replace `_renderProjectList` rendering with a `<select>`. Suppress marker popups when flag is set. Existing CRUD form stays. | M (2 days) | 0b |
| **0d** | **Mock fixture + project detail card with ΔT bar chart + Hazards Evaluated** | `static/multihazard_fixtures.js` written (6 real Berkeley projects + 2 hand-crafted: `cedar_street_infill` flood-controlling, `marina_pointe` tsunami-dispositive). New render functions in `sidebar.js`: `_renderHazardBarRow` (switch on `result.type`, 6 cases — wildfire / flood / tsunami / dam_failure / gas_hazmat / landslide), `_renderHazardListItem` (same switch shape for the Hazards Evaluated list), `_renderTierWithControlling`. Tsunami's dispositive treatment lives inside `_renderHazardBarRow`'s `case 'tsunami':` — no separate render function. | L (3 days) | 0c |
| **0e** | **Hazard scenario radio + AntPath swap** | `_renderHazardScenarioRadio` in sidebar.js; on change, re-`_drawRoutes()` from `hazard_results[i].route_coords`. Mock fixture stubs different route_coords per hazard (different colors / subtly different geometry for visual proof). | M (2 days) | 0d |
| **0f** | **Brief renderer A/B/C/D per-hazard** | `brief_renderer.js` gets `_renderBRow(result)` and `_renderCRow(result)` — each a `switch (result.type)` with 6 cases per §4.2.1. Section B/C tables iterate `hazard_results[]` and call the row renderer per result. Tsunami's case in `_renderCRow` returns the "Dispositive at Standard 3 — in CGS Tsunami Hazard Area" row with `delta_t_informational` as a footnote. New `_renderSectionDExcluded(results)` iterates `results.filter(r => r.excluded)`. Determination footer names controlling hazard. | L (3 days) | 0d |
| **0g** | **Right-side sidebar layout** | CSS swap from `left: 0` to `right: 0` (only when flag set). Confirm Leaflet `topright`/`bottomright` controls don't collide. Add narrow-viewport `@media` rule. | S (1 day) | 0e + 0f |
| **0h** | **Schema doc + Stage 1 handoff** | Write `docs/josh-data-schema-v2.md` capturing the final shapes from §4 as ratified by working code. Update `multihazard_status.md` Phase 4 checkboxes. PR description for the Stage 0 → `feature/multi-hazard` merge. | S (1 day) | 0b–0g all merged |

**Total effort: ~14 working days (~3 weeks calendar).** This is meaningfully larger than
the original Stage 0 (1 day), but it front-loads the schema decisions and validates the
UX with zero adapter code.

### 6.1 Sub-stage branch & merge convention

Each sub-stage gets its own branch off `feature/multi-hazard`:

```
feature/multi-hazard
  ├─ feature/mhz-stage-0a-snapshot-baseline
  ├─ feature/mhz-stage-0b-polygon-layer-abstraction
  ├─ feature/mhz-stage-0c-dropdown-no-popup
  ├─ feature/mhz-stage-0d-detail-card
  ├─ feature/mhz-stage-0e-scenario-radio
  ├─ feature/mhz-stage-0f-brief-renderer
  ├─ feature/mhz-stage-0g-right-sidebar
  └─ feature/mhz-stage-0h-schema-doc
```

Each PR merges into `feature/multi-hazard`. None merge into `main` (per the §2 no-main-merges
rule). All four existing test suites must stay green on every sub-stage PR.

### 6.2 Sub-stage acceptance criteria

| Sub-stage | Concrete acceptance |
|---|---|
| 0a | Snapshot files exist; diff against fresh pipeline run is empty (no drift) |
| 0b | Berkeley map with `multihazard: false` is byte-identical to baseline. With `true`, wildfire layer renders via new abstraction; one stub flood polygon visible. Layer panel checkboxes toggle visibility. |
| 0c | Dropdown selects projects; marker click selects without popup; CRUD form still adds projects |
| 0d | All 6 real Berkeley projects show 2-row ΔT bar chart from mock data. `cedar_street_infill` shows flood as controlling; `marina_pointe` shows tsunami as controlling with "Dispositive at Std 3" treatment (no ΔT bar, special badge). Tier banner names controlling hazard in all cases. |
| 0e | Scenario radio swaps visible AntPath. Switching to "Controlling" restores the canonical route. Tsunami scenario on `marina_pointe` shows no route (dispositive — no ΔT routing performed) with explanatory caption. |
| 0f | Brief modal opens with A/B/C/D sections. Controlling row highlighted. Excluded list renders. Tsunami row in Section C on `marina_pointe` renders "Dispositive at Standard 3 — in CGS Tsunami Hazard Area" instead of ΔT computation, with informational ΔT in footnote. |
| 0g | Right-side layout active when flag set. Leaflet zoom moved to `topleft`; attribution doesn't overlap sidebar. Narrow viewport (< 768 px) renders sensibly (bottom drawer or full-width overlay). |
| 0h | `josh-data-schema-v2.md` published. Status doc Phase 4 box checked. PR opened for merge into `feature/multi-hazard`. |

### 6.3 Step-by-step build sequence

This is the granular, in-order list of PR-sized increments. Each step is scoped to leave
the app in a known-working state for **both** flag values (`multihazard: false` →
production unchanged; `multihazard: true` → new behavior up to whatever step has shipped).
Steps within a sub-stage may share a branch and merge as one PR; the numbering is the
**build order**, not necessarily one-PR-per-step.

**Conventions:**
- Every step adds OR preserves byte-identical output when the flag is off.
- "Verify" = the single thing a developer should check before declaring the step done.
  Beyond the one-line check, the four existing test suites must still pass.
- "Flag-gated" = the new behavior runs only when `JOSH_DATA.schema_version === 2`.
- The first sub-stage that puts new UI on the right side is 0c; until then, the
  production left sidebar is the visible surface and the new schema is data-only.

**Human-in-the-loop annotations.** Every step is tagged with one of four levels (locked
2026-05-17):

| Level | Operational meaning |
|---|---|
| **[AUTO]** | Execute, commit, one-line update, move to next step. No human gate. |
| **[REVIEW]** | Execute, then produce **screenshot + one-sentence "what to check"**. Wait for one-word go (or short redirect) before next step. |
| **[PAUSE]** | **Propose specifics before writing code** (factory signature, copy choices, layout, color, design call). Get vote. Then implement, screenshot, sign-off, next step. |
| **[HARD STOP]** | Stage gate. Full review of accumulated state. Explicit go/no-go before exiting Stage 0. |

The 8 PAUSE points cluster around three risk categories: (1) abstraction signatures —
Steps 3, 27; (2) first-instance UI design — Steps 6, 8, 12, 22; (3) first non-wildfire
behaviors lighting up — Steps 16, 17. Mistakes at PAUSE points compound through every
later step that inherits the wrong shape.

#### Sub-stage 0a — Baseline snapshot

**Step 1 [AUTO] — Capture regression baseline.** Run `acquire.py run --city "Berkeley"` against
current main; copy `JOSH_DATA.briefs[id]`, current audit `.txt`, current test_vectors.json,
and a serialized sidebar state into `tests/snapshots/baseline/`. Commit.
*Files:* `tests/snapshots/baseline/*` (new).
*Verify:* re-run the pipeline; diff against committed snapshot is empty.

#### Sub-stage 0b — Polygon abstraction + schema flag (data only, no visible UI change)

**Step 2 [REVIEW] — Add `multihazard` flag plumbing + `schema_version` emit.** `cities/berkeley.yaml`
gains optional `multihazard: bool` (default `false`). `agents/export.py` emits
`JOSH_DATA.schema_version = 2` when flag is on; otherwise omits the key entirely.
*Files:* `agents/export.py`, `cities/berkeley.yaml`, `cities/{others}.yaml` (default false).
*Verify:* with flag false, `JOSH_DATA` JSON byte-identical to baseline. With flag true,
only `schema_version: 2` appears at the top level — nothing else changes yet.

**Step 3 [PAUSE] — Build `HazardPolygonLayer` JS module.** New file `static/hazard_polygon_layer.js`
exports a factory `createHazardPolygonLayer({feature_collection, zone_attribute, zone_map, palette, legend_label})` returning a Leaflet GeoJSON layer. Refactor the existing
Folium FHSZ render block (`analysis_map.py:273`) to use this factory under the hood.
No schema change yet — still reads `JOSH_DATA.fhsz`.
*Files:* `static/hazard_polygon_layer.js` (new), `agents/visualization/analysis_map.py`.
*Verify:* Berkeley map renders FHSZ polygons identically to baseline (visual diff).

**Step 4 [AUTO] — Emit `JOSH_DATA.hazard_polygons.wildfire`.** When flag is on, `agents/export.py`
emits the new shape alongside the legacy `JOSH_DATA.fhsz`. Renderer reads
`hazard_polygons.wildfire` when v2; falls back to `JOSH_DATA.fhsz` when v1.
*Files:* `agents/export.py`, `agents/visualization/analysis_map.py`.
*Verify:* flag on/off — FHSZ polygons render identically in both modes.

**Step 5 [REVIEW] — Add mock flood polygon to `JOSH_DATA.hazard_polygons.flood`.** Behind the flag,
emit a small hand-crafted SFHA polygon (bayfront / Strawberry Creek corridor) per the
mockup's `FLOOD_GJ` fixture. Wire it through the `HazardPolygonLayer` factory. Visible
via Folium's existing auto-generated layer control until step 8 replaces it.
*Files:* `agents/export.py`, `agents/visualization/analysis_map.py`.
*Verify:* flag on — blue SFHA blob visible near bayfront; flag off — only FHSZ visible.

#### Sub-stage 0c — Right sidebar shell + dropdown + no-popup

**Step 6 [PAUSE] — Hide left sidebar; show right sidebar shell when flag is on.** Inject a new
right-side `#josh-sidebar-mhz` div when `JOSH_DATA.schema_version === 2`; hide the
existing left `#josh-sidebar`. The right shell contains only a header at this step —
no panels yet.
*Files:* `static/sidebar.js`, `agents/visualization/analysis_map.py`.
*Verify:* flag on — left empty, right header only. Flag off — production left sidebar
intact.

**Step 7 [REVIEW] — Move Leaflet zoom control to `topleft` when flag is on.** Now that the right
edge is occupied, push the zoom control to the (now-empty) top-left. Verify attribution
control at bottom-right doesn't overlap the sidebar by adjusting its margin if needed.
*Files:* `agents/visualization/analysis_map.py` (or `helpers.py`).
*Verify:* flag on — zoom appears top-left, attribution legible below sidebar.

**Step 8 [PAUSE] — Hazard Layers panel.** Add `mhz-panel` "Hazard Layers" to the right sidebar.
Iterate `JOSH_DATA.hazard_polygons` and render one checkbox row per hazard (legend label
from the polygon record). Each checkbox toggles `map.addLayer/removeLayer` on the
corresponding `HazardPolygonLayer`. Hide Folium's auto-generated layer control when flag
is on.
*Files:* `static/sidebar.js`, `agents/visualization/analysis_map.py`.
*Verify:* flag on — two checkboxes (Wildfire, Flood); toggling each shows/hides the
right polygon layer.

**Step 9 [REVIEW] — Project dropdown panel.** Add `mhz-panel` "Project" with a `<select>` populated
from `JOSH_DATA.projects` (sorted by name). Selecting a project sets the selected ID
state but renders nothing further yet — the detail card lands in step 11.
*Files:* `static/sidebar.js`.
*Verify:* flag on — dropdown lists all 6 Berkeley projects; selection updates state
(check via console). Flag off — production project list unchanged.

**Step 10 [REVIEW] — Suppress marker popups; click → `selectProject(id)`.** Marker click handler
in the multihazard flag path calls `selectProject(id)` instead of opening a Folium popup.
Map pans to the project location.
*Files:* `static/sidebar.js`, `agents/visualization/analysis_map.py`.
*Verify:* flag on — clicking any marker selects in dropdown; no popup opens. Flag off —
popups still work.

#### Sub-stage 0d — Mock fixture + detail card

**Step 11 [AUTO] — Load `static/multihazard_fixtures.js`; merge `hazard_results[]` onto projects.**
Create the fixture file with wildfire-only `hazard_results[]` for each of the 6 Berkeley
projects (each result a `WildfireResult` per §4.2). Loader merges fixture data onto
`JOSH_DATA.projects[i].evaluation` when flag is on. Loader also validates each result's
`type` field against the 6-hazard whitelist; rejects unknown types with a console error
(prevents schema drift from going unnoticed).
*Files:* `static/multihazard_fixtures.js` (new), `static/sidebar.js`.
*Verify:* flag on — `window.JOSH_DATA.projects[0].evaluation.hazard_results[0].type === 'wildfire'`;
loader rejects a fixture entry with `type: 'invalid'` via console error.

**Step 12 [PAUSE] — Project detail card + per-hazard ΔT bar chart (wildfire case only).** New
`_renderProjectDetail()` renders the selected project's name, address, units, stories
into the right sidebar. New `_renderHazardBarRow(result)` is a `switch (result.type)` with
the **wildfire case implemented** and the other 5 cases stubbed to `return ''` (empty
row — will fail loudly later when hit). The bar chart iterates `hazard_results[]` and
calls `_renderHazardBarRow` per result.
*Files:* `static/sidebar.js`.
*Verify:* selecting a project shows its details and one wildfire bar with the right
fail/pass coloring. The 5 unimplemented switch cases are reachable but harmless (empty
rows; assert via console that they aren't being hit yet).

**Step 13 [REVIEW] — Implement the `flood` case in `_renderHazardBarRow`; extend fixture with `FloodResult` entries for all 6 real projects.** Add the `case 'flood':` branch with bar
rendering (zone label, degradation, threshold, ΔT, fail/pass coloring). Extend fixture
so each of the 6 real Berkeley projects has a `FloodResult` (all passing — wildfire
remains controlling). Bar chart now shows two rows per project.
*Files:* `static/sidebar.js` (switch case), `static/multihazard_fixtures.js`.
*Verify:* all 6 projects show 2-row bar charts (wildfire variable, flood always pass).

**Step 14 [REVIEW] — Tier banner with controlling-hazard footer.** `_renderTierWithControlling()`
reads `evaluation.tier` + `evaluation.controlling_hazard` and renders "DISCRETIONARY —
driven by Wildfire" pattern. Place above the bar chart. Reads `controlling_hazard` as a
string (e.g. `'wildfire'`) and maps to display label via a `HAZARD_DISPLAY_NAMES` const
in `static/whatif_utils.js`.
*Files:* `static/sidebar.js`, `static/whatif_utils.js`.
*Verify:* all 6 projects show their tier with "driven by Wildfire" footer.

**Step 15 [REVIEW] — Hazards Evaluated list.** `_renderHazardListItem(result)` is a `switch (result.type)` with the **wildfire and flood cases implemented** (other 4 cases stubbed
`return ''`). The list iterates `hazard_results[]`. Each row: hazard color dot + display
name + zone label + ΔT + "controls" badge for the controlling hazard.
*Files:* `static/sidebar.js`.
*Verify:* list shows two rows per project; wildfire row badged "controls" on all 6.

**Step 16 [PAUSE] — Inject `cedar_street_infill` (flood-controlling) mock project.** Add the
hand-crafted project to `JOSH_DATA.projects` (mock-only injection when flag is on) plus
its `hazard_results` to the fixture. The fixture includes a `tsunami` result with
`excluded: { reason: 'Project location is inland; not in CGS Tsunami Hazard Area.' }`.
Project dropdown now shows 7 items.
*Files:* `static/multihazard_fixtures.js`, `static/sidebar.js` (merge logic).
*Verify:* selecting cedar_street_infill — tier "DISCRETIONARY — driven by Flood"; bar
chart shows flood row in fail state with "controls" badge; wildfire row passing. The
excluded tsunami result is filtered out of the bar chart (excluded results don't render
here; they belong to Section D in the brief, step 23).

**Step 17 [PAUSE] — Inject `marina_pointe` + implement `tsunami` case in `_renderHazardBarRow`
and `_renderHazardListItem`.** Add the marina project. Implement the `case 'tsunami':`
branches in both switches: bar chart row shows no bar — just the hazard label and a
"Dispositive at Std 3" badge in place of the value. Hover tooltip shows
`result.delta_t_informational` italicized as "informational only". List item shows the
same badge in place of the ΔT cell.
*Files:* `static/multihazard_fixtures.js`, `static/sidebar.js` (two switch cases).
*Verify:* selecting marina_pointe — tier "DISCRETIONARY — driven by Tsunami", tsunami
row in bar chart shows the dispositive badge and no bar; hovering shows informational ΔT.
List item row shows badge correctly. Wildfire and flood rows still render normally.

#### Sub-stage 0e — Scenario radio + AntPath swap

**Step 18 [REVIEW] — Hazard scenario radio (no behavior change yet).** `_renderHazardScenarioRadio()`
renders "Controlling (default)" plus one radio per applicable hazard. Initially the
change handler is a no-op stub.
*Files:* `static/sidebar.js`.
*Verify:* radio renders correctly for 2-hazard projects (real Berkeley) and 3-hazard
projects (marina_pointe).

**Step 19 [AUTO] — Stub `route_coords` per hazard in fixture.** For each hazard result, add a
`route_coords` list. Wildfire gets the real route. Flood gets the same route with a
small geometric offset (just enough to be visually distinguishable on map). Tsunami on
marina_pointe gets `null` (dispositive — no route).
*Files:* `static/multihazard_fixtures.js`.
*Verify:* `evaluation.hazard_results[i].route_coords` contains expected shapes.

**Step 20 [REVIEW] — Wire scenario change → re-`_drawRoutes()`.** Scenario radio change reads
`hazard_results[scenarioIdx].route_coords` and re-renders the AntPath layer. "Controlling"
falls back to the controlling hazard's route. Dispositive tsunami case: hide the AntPath
and show an explanatory caption ("Dispositive at Standard 3 — no route computed").
*Files:* `static/sidebar.js`.
*Verify:* on a 2-hazard project, scenario radio swaps the visible AntPath; on
marina_pointe, tsunami scenario hides the AntPath and shows the caption.

#### Sub-stage 0f — Brief renderer A/B/C/D

**Step 21 [AUTO] — `BriefRenderer` schema branching.** `BriefRenderer.render(input)` inspects
`input.schema_version`; v1 renders exactly as today, v2 branches into the new path
(stubbed at this step — renders the existing template, no new sections).
*Files:* `static/brief_renderer.js`.
*Verify:* with v1 input, brief HTML is byte-identical to `tests/snapshots/baseline/briefs/`.
With v2 input, brief opens without error (content same as v1 for now).

**Step 22 [PAUSE] — Section B/C per-hazard tables (3 switch cases each).** v2 path adds
`_renderBRow(result)` and `_renderCRow(result)`, each a `switch (result.type)` with **wildfire / flood / tsunami cases implemented** (the other 3 cases stubbed `return ''`).
Both functions iterate `hazard_results.filter(r => !r.excluded)` and emit a `<tr>` per
result. Section B columns: Hazard / Zone / Degradation / Egress window / ΔT threshold.
Section C columns: Hazard / Bottleneck / Eff cap / Veh / ΔT / Threshold / Result.
Tsunami's `_renderCRow` case returns a row spanning the ΔT/Threshold/Result columns with
"Dispositive at Standard 3 — in CGS Tsunami Hazard Area"; `delta_t_informational` shown
italicized in a footnote below the table.
*Files:* `static/brief_renderer.js`.
*Verify:* opening brief for hills_gateway shows 2-row tables; cedar_street_infill shows
2-row tables (excluded tsunami filtered out of B/C, surfaces in D — step 23);
marina_pointe shows 3-row tables with tsunami row showing dispositive treatment + footnote.

**Step 23 [REVIEW] — Section D excluded hazards + determination footer.** New
`_renderSectionDExcluded(results)` iterates `results.filter(r => r.excluded)` and renders
a bullet list: hazard display name + `r.excluded.reason`. Determination footer reads
`controlling_hazard` and the corresponding result; renders "DISCRETIONARY — controlled by
Wildfire: VHFHSZ ΔT 11.8 min exceeds 2.25 min threshold." For tsunami dispositive case,
footer reads "DISCRETIONARY — controlled by Tsunami: project in CGS Tsunami Hazard Area
(dispositive at Standard 3)."
*Files:* `static/brief_renderer.js`.
*Verify:* cedar_street_infill brief shows Section D listing "Tsunami — Project location
is inland; not in CGS Tsunami Hazard Area." marina_pointe shows tsunami-controlled
determination footer. All others have empty Section D and wildfire-controlled footer.

**Step 24 [AUTO] — Brief renderer tests.** Add three vectors to `tests/test_brief_renderer.js`:
(a) wildfire-only-v2 (real Berkeley project under v2 schema), (b) cedar_street_infill
(wildfire + flood + excluded tsunami), (c) marina_pointe (wildfire + flood + tsunami
dispositive). Each vector asserts specific DOM presence — Section B `<tr>` count, Section
C `<tr>` count, Section D bullet count, controlling-hazard text in footer, dispositive
badge presence (no full HTML diff — too brittle).
*Files:* `tests/test_brief_renderer.js`.
*Verify:* `node --test tests/test_brief_renderer.js` passes including new cases. The
existing v1 vectors also pass unchanged. Snapshot from §0a (baseline) confirms zero
drift on v1 path.

#### Sub-stage 0g — Right-side polish

**Step 25 [REVIEW] — Narrow-viewport media query.** Add `@media (max-width: 768px)` rule: right
sidebar becomes a bottom drawer at narrow widths. Folium map remains usable above the
drawer.
*Files:* `static/sidebar.js` (CSS in the injected style block).
*Verify:* resizing Chrome to 600 px wide — sidebar moves to bottom drawer; map fills
the rest of the viewport.

**Step 26 [REVIEW] — Leaflet attribution placement check.** At standard 1280 px viewport, confirm
attribution control is fully readable below the sidebar's bottom edge. Adjust margin if
needed.
*Files:* `agents/visualization/analysis_map.py` (or CSS in the layout block).
*Verify:* attribution legible at 1280 px and 1920 px; no overlap.

#### Sub-stage 0h — Schema doc + handoff

**Step 27 [PAUSE] — Write `docs/josh-data-schema-v2.md`.** Capture the final ratified shapes from
§4 of this plan — every field, every type, every optional-vs-required call documented.
This becomes the canonical contract for Stage 1.
*Files:* `docs/josh-data-schema-v2.md` (new).
*Verify:* schema doc matches what `static/multihazard_fixtures.js` actually emits.

**Step 28 [HARD STOP] — Status doc updates + Stage 1 readiness review.** Flip the Phase 4 + Phase 7
checkboxes in `multihazard_status.md` that Stage 0 work demonstrates. Move the
"Stage 0 baseline merge" line out of "Next up" into "Recently completed". Open PR
checklist for the umbrella merge.
*Files:* `docs/multihazard_status.md`, this plan doc (mark as "executed").
*Verify:* status doc accurately reflects what shipped; supervising agent can pick up
Stage 1 from the updated "Next up" list.

### 6.4 Dependency graph

```
Step 1 (snapshot) ──┐
                    ▼
Step 2 (flag) ── 3 (HazardPolygonLayer) ── 4 (emit wildfire poly) ── 5 (emit flood poly)
                                                                       │
                                                                       ▼
                                              Step 6 (right shell) ── 7 (zoom move)
                                                                       │
                                                                       ▼
                                              Step 8 (layer panel) ── 9 (dropdown) ── 10 (no-popup)
                                                                       │
                                                                       ▼
                                              Step 11 (load fixture) ── 12 (detail + bar chart)
                                                                       │
                                                                       ▼
                                              Step 13 (flood data) ── 14 (tier footer) ── 15 (hz list)
                                                                       │
                                                                       ▼
                                              Step 16 (cedar) ── 17 (marina + dispositive)
                                                                       │
                                                                       ▼
                                              Step 18 (radio) ── 19 (mock routes) ── 20 (swap)
                                                                       │
                                                                       ▼
                                              Step 21 (br v1/v2 branch) ── 22 (B/C) ── 23 (D + footer) ── 24 (tests)
                                                                       │
                                                                       ▼
                                              Step 25 (narrow viewport) ── 26 (attribution)
                                                                       │
                                                                       ▼
                                              Step 27 (schema doc) ── 28 (status + PR)
```

**Parallelization opportunities:**
- Steps 1 and 2 are independent (snapshot is data-only; flag is code-only)
- Steps 6 and 7 can ship as one PR (layout-only)
- Steps 25 and 26 can ship as one PR (polish-only)
- Step 24 (brief renderer tests) can be written in parallel with steps 22 and 23 if a
  second contributor is available

**No-skip rule:** steps must merge in numerical order. Skipping ahead risks landing on
schema decisions that haven't been ratified by working UI yet — the whole point of the
expanded Stage 0 is to **let working UI ratify the schema**, not the other way around.

---

## 7. Risks and decisions to surface

### 7.1 Right-side sidebar — Leaflet control collision

**Decision locked (2026-05-17, user):** sidebar moves to `right: 0` per
`multihazard_first_principles.md` §7.3 inspector pattern. The mockup's left position
was an overlay artifact only.

Risk in sub-stage 0g: Leaflet's default `topright` zoom control and `bottomright`
attribution control will collide with a right-side sidebar. Mitigations:
- Move zoom control to `topleft` (free now that production sidebar moves off the left)
- Confirm attribution stays inside the map pane below the sidebar's bottom edge
- Test at narrow viewport (< 768 px): sidebar collapses to a bottom drawer or full-width
  overlay; map controls reposition to the visible edge

### 7.2 The pre-baked `briefs[id]` HTML string in JOSH_DATA

Production today bakes per-project brief HTML into `JOSH_DATA.briefs[id]` at pipeline time.
Multi-hazard makes this incompatible — pre-baking N hazard combinations × N projects is
expensive and stale-prone. Stage 0 keeps `briefs[id]` for v1 fallback. Behind the flag,
brief HTML is generated entirely client-side from `BriefRenderer.render()` against the
mock `hazard_results[]`. **Decision pre-implied; called out for visibility.** Aligns with
`plan-multihazard-mvp.md` §5 risk note: pick (a) "remove and render at view time."

### 7.3 Mock route_coords vs real per-hazard routing

Stage 0 mock fixtures stub `route_coords` per hazard (just the existing wildfire route
with slight color/style differences). Real per-hazard routing requires the FloodAdapter
to actually cut edges (Stage 3). Sub-stage 0e renders whatever `route_coords` are in the
fixture — when Stage 3 lands, the fixture file is deleted and real data takes over.

### 7.4 What if the mockup's UX patterns don't survive contact with real data?

This is the explicit purpose of expanded Stage 0. If 0d/0e/0f surface UX problems (e.g.
ΔT bar chart breaks at 6 hazards, dropdown can't scale to 50 projects, brief tables are
too wide on print), we revise *now*, before Python adapter code is written. Any divergence
from the mockup gets documented in 0h's schema doc as a ratified design decision.

### 7.5 The mockup file is 11.8 MB

Keep it on the feature branch but consider gitignoring it post-Stage-0 in favor of a
release-artifact upload. Decision deferred to 0h (status-doc-update sub-stage). Not
load-bearing for Stage 0 work.

---

## 8. What Stage 0 hands off to Stage 1

When Stage 0 closes, Stage 1 (`HazardAdapter` refactor) starts with:

1. **A working multi-hazard sidebar and brief renderer** — Python's job becomes
   "produce data in this schema," not "design the schema."
2. **A normalized `JOSH_DATA` schema** documented in `docs/josh-data-schema-v2.md`,
   ratified against working JS code.
3. **A mock fixture file** that defines exactly what each Python adapter needs to output.
   The fixture file becomes the Python regression target: `WildfireAdapter` must
   produce results that **byte-match** the mock fixture for Berkeley's 6 projects (the
   hand-crafted flood-controlled `cedar_street_infill` is dropped from the fixture once
   `FloodAdapter` lands in Stage 3).
4. **No production regression** — every Berkeley project with `multihazard: false`
   renders identical to today.

Stage 1's acceptance now reads: "build Python `HazardAdapter` abstraction such that
running `agents/scenarios/wildfire.py:WildfireAdapter` against Berkeley produces JSON
that matches the wildfire entries in `static/multihazard_fixtures.js`."

Stage 3 (FloodAdapter) inherits the `cedar_street_infill` fixture as a target. Stage 6
(TsunamiAdapter) inherits `marina_pointe`. Each hand-crafted fixture is deleted from the
mock file when its real adapter ships; Berkeley pipeline then produces those entries from
real data.

---

## 9. Out of Stage 0 scope (deferred to later)

- Real FEMA NFHL data acquisition (Stage 3)
- Real per-hazard Dijkstra (Stage 3 onwards)
- `HazardAdapter` Python ABC and `WildfireAdapter` (Stage 1)
- Anti-divergence tests against multi-hazard (Stage 1 adds infrastructure; Stage 3+ adds vectors)
- Audit trail per-hazard sections (Stage 4)
- Encinitas multi-hazard data (Stage 10)
- Methodology memos (Stage 11)

---

## 10. Reference

- `docs/plan-multihazard-mvp.md` — parent plan (Stage 0 currently §3)
- `docs/multihazard_first_principles.md` — architecture memo (§7.3 right-inspector,
  §8 brief A/B/C/D)
- `docs/multihazard_status.md` — locked decisions (especially #6, #7, #8)
- `output/mockup/multihazard_on_berkeley.html` — visual contract (will be superseded by
  working Stage 0 implementation)
- `agents/export.py:97–177` — current `_classifyFhsz` and `JOSH_DATA.fhsz` plumbing
  (Stage 0 normalizes both)
- `agents/visualization/analysis_map.py:273` — current FHSZ polygon rendering (Stage 0 §0b)
- `static/sidebar.js` — primary refactor target across sub-stages 0c–0g
- `static/brief_renderer.js` — primary refactor target for sub-stage 0f

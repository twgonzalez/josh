# JOSH_DATA schema v2 — Multi-Hazard

**Status:** Canonical (ratified by working Stage 0 implementation, 2026-05-17)
**Supersedes:** v1 (wildfire-only) — see §11 Migration
**Authoritative example:** [`static/multihazard_fixtures.js`](../static/multihazard_fixtures.js)
**Locked decisions:** see `docs/multihazard_status.md` (especially #6, #7, #8, #9, #10, #11)

This document is the contract Stage 1+ Python adapters MUST satisfy. The Stage 0
JS-only implementation already consumes shapes defined here (via fixtures); when
Stage 1 lands `WildfireAdapter` and Stage 3+ lands real per-hazard adapters, they
must produce JSON matching these shapes exactly.

---

## 1. Overview

JOSH_DATA is the per-city data payload inlined into `output/{city}/analysis_map.html`
as `window.JOSH_DATA`. v2 extends v1 with multi-hazard fields under an explicit
schema-version discriminator.

```js
window.JOSH_DATA = {
  schema_version: 2,       // 1 (legacy wildfire-only) | 2 (multi-hazard)
  ...
}
```

**When v2 applies:** the city config has `multihazard: true`. The pipeline emits
v2 (`schema_version: 2`) and the browser activates the right-side multi-hazard
sidebar (`static/sidebar.js`). When the flag is absent or false, v1 is emitted
and production behavior is preserved.

**Why a tagged union for hazard results** (locked decision #11): with six finite
hazards each carrying genuinely different physics (BFE-elevation for flood,
per-feature arrival times for dam, computed PIR buffers for gas, dispositive
semantics for tsunami), a semi-abstract schema (uniform shape + optional fields)
hides where the hazard-specific logic lives without saving any real code. The
discriminated union buys debuggability, type safety, and grep-ability at the
bounded cost of 6 explicit switch cases per consumer.

---

## 2. Top-level JOSH_DATA v2 fields

The v2 root is a superset of v1. All v1 fields below remain present; the **new**
v2 fields are flagged in the comment column.

```ts
interface JoshDataV2 {
  // ── v1 keys (preserved) ──────────────────────────────────────────────────
  schema_version: 2;                       // discriminator (== 2 for v2)
  app_js_version: string;                  // e.g. "v1" — bumped on
                                           // backward-incompatible schema breaks
  city_name:      string;
  city_slug:      string;
  graph:          GraphPayload;            // OSMnx export (nodes + edges)
  parameters:     ParametersPayload;       // legacy per-zone parameter dict
  fhsz:           GeoJsonFeatureCollection;// legacy FHSZ singleton (DEPRECATED
                                           // for v2 consumers — see §3.1)
  briefs:         { [project_id: string]: string }; // pre-baked v1 HTML;
                                           // empty {} in v2 (rendered live)
  projects:       ProjectV2[];             // shape changes per §7

  // ── v2 NEW keys ──────────────────────────────────────────────────────────
  applicable_hazards:  HazardId[];         // city-level list of evaluated hazards;
                                           // e.g. ["wildfire","flood"]
  hazard_polygons: {                       // §3
    [hazardId: HazardId]: HazardPolygonRecord
  };
  hazard_parameters: {                     // §4 — NOT YET EMITTED IN STAGE 0
    [hazardId: HazardId]: HazardParametersRecord
  };
}

type HazardId =
  | 'wildfire'
  | 'flood'
  | 'tsunami'
  | 'dam_failure'
  | 'gas_hazmat'
  | 'landslide';
```

**Field-by-field:**

| Field | v1 | v2 | Notes |
|---|---|---|---|
| `schema_version` | `1` | `2` | Required. Browser engine warns on unsupported values. |
| `applicable_hazards` | — | string[] | Required. City-level applicability filter; UI iterates this to render hazard layer checkboxes (Step 8). |
| `hazard_polygons` | — | dict | Required when v2. §3. |
| `hazard_parameters` | — | dict | **Planned (Stage 1+)** — not currently emitted by the Stage 0 pipeline. §4. |
| `fhsz` | dict | dict (DEPRECATED) | Retained for v1 fallback. v2 consumers should read `hazard_polygons.wildfire.feature_collection` instead. Removed in a future major version. |
| `briefs` | dict | `{}` | v2 renders briefs live via `BriefRenderer.render()` (Step 21+) — no pre-baking. |

---

## 3. `hazard_polygons` record

One uniform record per hazard. The record carries everything the polygon layer
factory (`static/hazard_polygon_layer.js`) needs to render the hazard onto the
map, plus the metadata (palette + labels) reused by the bar chart and brief
cells.

```ts
interface HazardPolygonRecord {
  feature_collection: GeoJsonFeatureCollection; // hazard polygons (real or mock)
  zone_attribute:     string;       // GeoJSON property key holding the zone
                                    // discriminator (e.g. "HAZ_CLASS",
                                    // "FLD_ZONE", "Eva_Type")
  zone_map:           { [raw_value: string]: string };
                                    // raw feature property value → normalized
                                    // zone id (e.g. "3" → "vhfhsz")
  palette:            { [normalized_zone_id: string]: string };
                                    // zone id → hex color (or "transparent")
                                    // Iteration order is severity-descending;
                                    // _pickHazardSwatchColor uses the first
                                    // non-transparent value as the panel color.
  labels:             { [normalized_zone_id: string]: string };
                                    // zone id → tooltip text shown on hover
  legend_label:       string;       // hazard chip label (e.g. "Wildfire (FHSZ)")
}
```

### 3.1 Wildfire (real data)

```js
hazard_polygons.wildfire = {
  feature_collection: { /* CAL FIRE FHSZ GeoJSON, same as legacy JOSH_DATA.fhsz */ },
  zone_attribute: 'HAZ_CLASS',     // integer 1–3 per CAL FIRE encoding
  zone_map: { '3': 'vhfhsz', '2': 'high_fhsz', '1': 'moderate_fhsz' },
  palette: {
    vhfhsz:        '#d7301f',      // red
    high_fhsz:     '#fc8d59',      // orange
    moderate_fhsz: '#ffeda0',      // yellow
    non_fhsz:      'transparent'
  },
  labels: {
    vhfhsz:        'CAL FIRE FHSZ — Very High Fire Hazard (VHFHSZ)',
    high_fhsz:     'CAL FIRE FHSZ — High Fire Hazard',
    moderate_fhsz: 'CAL FIRE FHSZ — Moderate Fire Hazard',
    non_fhsz:      'Not in FHSZ'
  },
  legend_label: 'Wildfire (FHSZ)'
};
```

### 3.2 Flood (mock in Stage 0; real in Stage 3)

```js
hazard_polygons.flood = {
  feature_collection: { /* Stage 0: hand-crafted bayfront mock. Stage 3+:
                          FEMA NFHL S_FLD_HAZ_AR layer clipped to city boundary. */ },
  zone_attribute: 'FLD_ZONE',
  zone_map: { 'AE': 'ae', 'A': 'a', 'AO': 'ao', 'VE': 've', 'X': 'x' },
  palette: {
    ae: '#1f77b4', a: '#1f77b4', ao: '#3399cc', ve: '#08306b', x: 'transparent'
  },
  labels: {
    ae: 'FEMA NFHL — Zone AE (1% annual flood, BFE shown)',
    a:  'FEMA NFHL — Zone A (1% annual flood)',
    ao: 'FEMA NFHL — Zone AO (shallow flooding)',
    ve: 'FEMA NFHL — Zone VE (coastal high hazard)',
    x:  'FEMA NFHL — Zone X (outside SFHA)'
  },
  legend_label: 'Flood (FEMA NFHL — mock)'  // " — mock" reminder drops in Stage 3
};
```

### 3.3 Feature properties carried within `feature_collection`

Each hazard's GeoJSON features carry additional per-feature properties consumed
by its adapter. The schema does not enforce these — they live inside
`feature.properties` and are documented in §6 (per-hazard data requirements).

---

## 4. `hazard_parameters` record (Stage 1+ — NOT YET EMITTED)

**Status:** planned. Stage 0's pipeline emits `hazard_polygons` only; per-hazard
adapter parameters are still read from the legacy `JOSH_DATA.parameters` dict.
Stage 1 (HazardAdapter Python refactor) emits this dict per the shape below;
the JS engine reads from `hazard_parameters[hazard_id]` rather than the legacy
zone-keyed `parameters.hazard_degradation`.

```ts
interface HazardParametersRecord {
  // Per-zone numeric parameters. Tsunami sets these to {} when
  // dispositive_at_standard_3 is true.
  degradation:               { [zone_id: string]: number };  // 0..1
  safe_egress_window:        { [zone_id: string]: number };  // minutes
  mobilization:              number;                         // 0..1, NFPA 101 ≥ 0.90
  dispositive_at_standard_3: boolean;                        // true for tsunami only
  // Hazard-specific extras (optional; documented in §6):
  bfe_clearance_ft?:         number;  // flood only
  pir_constant?:             number;  // gas_hazmat only (PHMSA 0.69)
  default_pir_ft?:           number;  // gas_hazmat only (660 ft fallback)
  post_fire_ttl_years?:      number;  // landslide only
}
```

### 4.1 Wildfire example

```js
hazard_parameters.wildfire = {
  degradation:        { vhfhsz: 0.35, high_fhsz: 0.50, moderate_fhsz: 0.75, non_fhsz: 1.00 },
  safe_egress_window: { vhfhsz: 45,   high_fhsz: 90,   moderate_fhsz: 120,  non_fhsz: 120 },
  mobilization:       0.90,
  dispositive_at_standard_3: false
};
```

### 4.2 Tsunami example

```js
hazard_parameters.tsunami = {
  degradation:        {},  // not used when dispositive
  safe_egress_window: {},
  mobilization:       1.00,
  dispositive_at_standard_3: true
};
```

---

## 5. `HazardResult` — discriminated union

The most important type in this schema. **Six concrete variants**, discriminated
by `type`. Renderers `switch (result.type)` in exactly four named functions (§9).
Each variant lists exactly the fields it carries; absent fields are absent
(not nullable). Adding a future hazard means adding a new variant plus four
switch cases — never adding flags or optional fields to a generic shape.

```ts
type HazardResult =
  | WildfireResult
  | FloodResult
  | TsunamiResult
  | DamFailureResult
  | GasHazmatResult
  | LandslideResult;
```

### 5.1 Shared base

Every variant carries these fields:

```ts
interface BaseResult {
  type:      HazardId;       // the discriminator — switch on this
  controls:  boolean;        // is the controlling hazard for the project
  flagged:   boolean;        // delta_t > threshold (false for dispositive types)
  excluded?: {               // present iff hazard inapplicable to this site
    reason: string;          // human-readable rationale shown in brief Section D
  };
}
```

When `excluded` is present, **all other fields except `type` are absent**. The
renderer filters excluded results out of bar charts / Hazards Evaluated lists
(they only surface in brief Section D).

### 5.2 `WildfireResult`

```ts
interface WildfireResult extends BaseResult {
  type:              'wildfire';
  zone:              'vhfhsz' | 'high_fhsz' | 'moderate_fhsz' | 'non_fhsz';
  zone_label:        string;             // display: "Very High FHSZ" etc.
  fhsz_haz_class:    0 | 1 | 2 | 3;      // CAL FIRE source encoding (0 = non_fhsz)
  degradation:       number;             // hazard_parameters.wildfire.degradation[zone]
  egress_window_min: number;             // minutes
  threshold:         number;             // egress_window_min × max_project_share
  delta_t:           number;             // minutes
  bottleneck:        Bottleneck;
  route_coords:      LatLng[] | null;    // null = fall back to controlling Folium FG
}
```

### 5.3 `FloodResult`

```ts
interface FloodResult extends BaseResult {
  type:              'flood';
  zone:              'ae' | 'a' | 'ao' | 've' | 'x';
  zone_label:        string;
  bfe_ft:            number | null;      // null in X; required for AE/A/AO/VE
  flooded_exit_nodes_dropped: number;    // telemetry — non-zero proves BFE filter ran
  degradation:       number;
  egress_window_min: number;
  threshold:         number;
  delta_t:           number;
  bottleneck:        Bottleneck;
  route_coords:      LatLng[] | null;
}
```

### 5.4 `TsunamiResult`

Special — dispositive at Standard 3 per locked decision #2. Lacks `delta_t`,
`threshold`, `bottleneck` (they aren't computed).

```ts
interface TsunamiResult extends BaseResult {
  type:                  'tsunami';
  in_cgs_tha:            boolean;        // in CGS Tsunami Hazard Area
  eva_type:              string | null;  // CGS Eva_Type attribute (null when out)
  dispositive:           true;           // structurally true — no "false" variant
  delta_t_informational: number;         // never compared to threshold;
                                         // shown as footnote in brief Section C
  route_coords:          null;           // dispositive — no route computed
  // intentionally absent: delta_t, threshold, bottleneck, degradation,
  // egress_window_min — not part of tsunami semantics.
}
```

### 5.5 `DamFailureResult`

```ts
interface DamFailureResult extends BaseResult {
  type:               'dam_failure';
  zone:               'in_inundation' | 'outside';
  dams_affecting:     Array<{ name: string; arrival_time_min: number }>;
  egress_window_min:  number;            // = min(d.arrival_time_min) across dams
  degradation:        number;
  threshold:          number;
  delta_t:            number;
  bottleneck:         Bottleneck;
  route_coords:       LatLng[] | null;
}
```

### 5.6 `GasHazmatResult`

```ts
interface GasHazmatResult extends BaseResult {
  type:              'gas_hazmat';
  in_pir:            boolean;
  pir_ft:            number;             // 0.69 × √(MAOP × DIAM²); fallback 660
  operator:          string | null;
  product:           'natural_gas' | 'hazardous_liquid' | 'unknown';
  degradation:       number;
  egress_window_min: number;
  threshold:         number;
  delta_t:           number;
  bottleneck:        Bottleneck;
  route_coords:      LatLng[] | null;
}
```

### 5.7 `LandslideResult`

```ts
interface LandslideResult extends BaseResult {
  type:              'landslide';
  zone_type:         'post_fire_df' | 'eilz' | 'none';
  burn_year:         number | null;      // post-fire only; null for EILZ
  degradation:       number;
  egress_window_min: number;
  threshold:         number;
  delta_t:           number;
  bottleneck:        Bottleneck;
  route_coords:      LatLng[] | null;
}
```

### 5.8 Shared sub-types

```ts
interface Bottleneck {
  name:        string;       // e.g. "Marin Avenue at Shattuck Avenue / The Circle"
  eff_cap_vph: number;       // effective capacity in vehicles per hour
  vehicles:    number;       // project_vehicles (units × vpu × mobilization)
}

type LatLng = [number, number];   // [latitude, longitude] in WGS84
```

---

## 6. Per-hazard data requirements

Each hazard's adapter consumes the polygon feature properties + graph node
attributes listed below. Required = adapter cannot function without it.
Optional = adapter degrades gracefully when missing.

| Hazard | Source authority | Polygon feature properties (required) | Graph node attrs | Adapter parameters |
|---|---|---|---|---|
| Wildfire | CAL FIRE OSFM FHSZ | `HAZ_CLASS` (int 1–3) | — | `degradation_by_zone`, `safe_egress_window_by_zone`, `mobilization=0.90` |
| Flood | FEMA NFHL | `FLD_ZONE` (string), `BFE_FT` (float, nullable in X) | `elevation_ft` (USGS 3DEP DEM 10 m) | `degradation_by_zone`, `safe_egress_window=180`, `bfe_clearance_ft=0.5`, `mobilization=0.90` |
| Tsunami | CGS Tsunami Hazard Area (item 2769c700c0694548b5435a60ff52b807) | `Eva_Type` (string) | — | `dispositive_at_standard_3=true`, `egress_window_informational=15` (USGS Cascadia near-field) |
| Dam failure | DSOD inundation + per-dam EAPs | `DAM_NAME` (string), `ARRIVAL_TIME_MIN` (int — from EAP) | — | `degradation_in_zone`, `mobilization=0.95`, fallback `arrival_time_min=30` (<5 mi) / `120` (5–50 mi) |
| Gas/hazmat | NPMS pipelines + JOSH-computed PIR buffer | On pipeline segments: `OPERATOR`, `PRODUCT`, `MAOP_PSIG` (nullable), `DIAM_IN` (nullable) | — | `pir_constant=0.69` (locked decision #3), `default_pir_ft=660`, `degradation_in_pir`, `mobilization=0.95` |
| Landslide | USGS post-fire DF + CGS EILZ | `ZONE_TYPE` (`post_fire_df`\|`eilz`), `BURN_YEAR` (int, nullable for EILZ) | — | `degradation_in_zone=0.50`, `safe_egress_window=60` (NWS DF warning lead time), `mobilization=0.90`, `post_fire_ttl_years=3` |

### 6.1 Per-hazard quirks

- **Flood** is the only hazard requiring a graph-node attribute
  (`elevation_ft`) beyond what the standard OSMnx export carries. The pipeline
  (Stage 3) joins DEM samples to graph nodes at acquisition time.
- **Dam failure** is the only hazard where the egress window is feature-level
  (per-dam), not zone-level. `egress_window_min` on `DamFailureResult` is the
  worst-case across all affecting dams.
- **Gas/hazmat** is the only hazard whose polygon is **computed** by the pipeline
  (PIR buffer around centerlines), not downloaded.
- **Tsunami** is the only hazard with `dispositive_at_standard_3=true`. Its
  `TsunamiResult` lacks `delta_t`, `threshold`, and `bottleneck`.
- **Landslide** is the only hazard with a TTL — post-fire DF products expire
  ~3 years after burn. Polygons drop out of `feature_collection` when
  `current_year - BURN_YEAR > 3` for `ZONE_TYPE='post_fire_df'`.

---

## 7. Per-project evaluation block

Each project in `JOSH_DATA.projects[]` carries an `evaluation` field under v2:

```ts
interface ProjectV2 {
  // v1 fields (preserved): id, name, address, lat, lng, units, stories,
  // folium_fg_name, source, etc.
  id:       string;
  name:     string;
  address:  string;
  lat:      number;
  lng:      number;
  units:    number;
  stories:  number;
  folium_fg_name?: string;  // present for pipeline-baked projects; absent for
                            // browser-injected mock projects (Stage 0)
  is_mock?: boolean;        // sentinel for Stage 0 mock-project footnote in
                            // the detail card; absent (or false) for real projects

  // v2 new field:
  evaluation: ProjectEvaluation;
}

interface ProjectEvaluation {
  schema_version:     2;
  controlling_hazard: HazardId | null;   // null if size gate not met
  tier:               | 'DISCRETIONARY'
                      | 'MINISTERIAL_WITH_STANDARD_CONDITIONS'
                      | 'MINISTERIAL';
  hazard_results:     HazardResult[];    // mixed-type list — see §5
}
```

`controlling_hazard` is the result with the highest `delta_t / threshold` ratio
among non-dispositive results, OR the dispositive hazard (tsunami) if any
dispositive in-zone result exists. Locked decision #7: worst-case single
hazard drives the tier; all applicable hazards reported; controlling hazard
named in the determination letter.

---

## 8. Excluded results

A hazard explicitly inapplicable to a project (e.g. inland project + tsunami)
is represented as a `BaseResult` with only `type` and `excluded` set:

```js
{
  type: 'tsunami',
  excluded: { reason: 'Project location is inland; not in CGS Tsunami Hazard Area.' }
}
```

The renderer:
- **Filters out** excluded results from the per-hazard bar chart (`_renderHazardBarRow`)
- **Filters out** excluded results from the Hazards Evaluated list (`_renderHazardListItem`)
- **Surfaces** excluded results in brief Section D ("Hazards Excluded")

`controls` and `flagged` default to `false` for excluded results; consumers should not
depend on their values.

---

## 9. Renderer rule (single-switch-site discipline)

> **RULE.** Every hazard-specific UI behavior lives in exactly **one named switch case
> over `result.type`**, in exactly **one renderer function per surface**. No flag-based
> hidden dispatch. No `if r.dispositive` guards on a generic shape. No `result.type === 'X'`
> checks outside the named switch sites.

The four switch sites (locked decision #11):

| # | Function | File | Cases |
|---|---|---|---|
| 1 | `_renderHazardBarRow(result)` | `static/sidebar.js` | 6 |
| 2 | `_renderHazardListItem(result)` | `static/sidebar.js` | 6 |
| 3 | `_buildSectionBV2(evaluation)` row builder | `static/brief_renderer.js` | 6 |
| 4 | `_buildSectionCV2(evaluation)` row builder | `static/brief_renderer.js` | 6 |

**Pre-merge review grep:** every `result.type === 'X'` (or `r.type === 'X'`)
check outside these four sites is a code smell. Adding earthquake later (if
ever) means adding one new variant + 4 switch cases. Bounded cost; grep-able;
type-safe.

---

## 10. `applicable_hazards` and `excluded_hazards`

Two related but distinct concepts:

- **`JOSH_DATA.applicable_hazards`** (city-level): list of hazards the city
  has chosen to evaluate. Drives the Hazard Layers panel checkbox iteration
  (§ Step 8) and which adapters Stage 5+ orchestrator runs.
- **Per-project excluded results** (§8): individual hazards from
  `applicable_hazards` that a specific site is exempt from (e.g. inland project
  + tsunami). Drives brief Section D.

A hazard NOT in `applicable_hazards` is invisible to the renderer — no row in
the bar chart, no entry in any list. A hazard in `applicable_hazards` that is
excluded for a specific project STILL shows in Section D with the exclusion
reason.

---

## 11. Migration: v1 deprecated, v2 is the future

v1 (wildfire-only) is **deprecated** as of Stage 0 close. v2 is the canonical
schema going forward. Cities migrate when their pipeline run sets
`multihazard: true` in `cities/{city}.yaml`; Stage 12 of the MVP plan promotes
the flag to default and removes the v1 code paths from the JS engine.

**During the transition** (Stages 1–11 of the MVP plan):

- v1 cities continue to render via `static/app.js` v1 schema check (warns on
  schema_version not in {1, 2}).
- v2 cities render the multi-hazard right sidebar + per-hazard bar chart +
  v2 brief (Section B/C/D + controlling footer).
- The legacy `JOSH_DATA.fhsz` and `JOSH_DATA.briefs` keys remain present in
  v2 output for fallback consumers, but are not read by the v2 JS engine.

**Stage 1+ work**: Python adapters must produce JSON matching §5 variants
exactly. The `static/multihazard_fixtures.js` file is the regression target
for Berkeley's seeded projects. Until each adapter ships, its hand-crafted
fixture entry is the source of truth.

---

## 12. Authoritative example

The single authoritative example of every shape in this document is the
Stage 0 mock fixture file:

> [`static/multihazard_fixtures.js`](../static/multihazard_fixtures.js)

It carries:
- 4 real Berkeley projects (`hills_gateway`, `downtown_mid_rise`,
  `claremont_hills_terrace`, `cedar_street_infill`) with wildfire + flood
  HazardResults
- 1 hand-crafted flood-controlling mock (`cedar_st_bayfront_mock`) with
  wildfire pass + flood fail + excluded tsunami
- 1 hand-crafted tsunami-dispositive mock (`marina_pointe`) with wildfire,
  flood, and tsunami (dispositive)

When Stage 1+ Python adapters land, this fixture file is deleted in pieces:
the wildfire entries vanish when `WildfireAdapter` lands; `cedar_st_bayfront_mock`
vanishes when `FloodAdapter` lands; `marina_pointe` vanishes when
`TsunamiAdapter` lands. The schema documented here remains stable.

---

## 13. Related documents

- [`docs/plan-multihazard-stage-0.md`](plan-multihazard-stage-0.md) — Stage 0
  implementation plan; §4 is the schema rationale.
- [`docs/plan-multihazard-mvp.md`](plan-multihazard-mvp.md) — umbrella MVP plan;
  §1.5 lists surface-preservation requirements; §13 lists tests.
- [`docs/multihazard_status.md`](multihazard_status.md) — locked decisions table.
- [`docs/multihazard_first_principles.md`](multihazard_first_principles.md) —
  architecture memo.
- [`static/multihazard_fixtures.js`](../static/multihazard_fixtures.js) —
  authoritative example data.
- [`static/sidebar.js`](../static/sidebar.js) — switch sites #1 + #2.
- [`static/brief_renderer.js`](../static/brief_renderer.js) — switch sites #3 + #4.
- [`static/hazard_polygon_layer.js`](../static/hazard_polygon_layer.js) —
  hazard-agnostic Leaflet polygon factory.

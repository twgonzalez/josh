# Multi-Hazard Extension of JOSH ΔT — First-Principles Architecture

**Date:** May 2026
**Status:** Draft architecture memo — companion to [`plan-ab747-multihazard-research.md`](./plan-ab747-multihazard-research.md)
**Audience:** Project team, peer-review engineers, city attorney pre-read

---

## 1. The reductive insight

The JOSH wildfire ΔT formula is hazard-agnostic:

```
ΔT = (units × vpu × mobilization / bottleneck_capacity_vph) × 60 + egress_penalty
```

It doesn't know fire from flood. Five inputs vary by hazard, and at the deepest level only **four are independent** — exit-node validity is a Boolean projection of degradation (an exit is invalid iff every edge that touches it has capacity 0):

| Input | Role in formula | Source per hazard |
|---|---|---|
| Zone classification | Indexes the three lookup tables below | One GIS polygon per hazard |
| Degradation factor | Per-edge capacity multiplier ∈ [0, 1] | Published curve or regulatory polygon |
| Egress window | ΔT threshold = window × `max_project_share` | Published warning/event timing |
| Mobilization rate | Vehicle release fraction ∈ [0, 1] | Compliance literature → design floor |
| (Exit validity) | Derived: edge unreachable ⇔ degradation = 0 | Not a separate input |

This is the entire interface. Wildfire ships with **one polygon set + three numbers per zone**. Every other hazard ships the same shape: one polygon + three numbers.

---

## 2. Two classes of hazard

Once the inputs are factored this way, the in-scope hazards split into two architectural classes.

### 2A. Capacity-degrading (the wildfire archetype)
- Roads in zone keep working at reduced capacity; the network stays connected.
- All exits remain valid; the hazard makes traffic worse, not absent.
- **Members:** wildfire, landslide (deterministic 0.50 form).

### 2B. Network-cutting
- Roads inside the zone polygon are **gone** (factor = 0); exit nodes inside the zone are invalid.
- The hazard removes part of the network before the surge starts; the surge runs on what's left.
- **Members:** flood, tsunami, dam failure, gas/hazmat pipeline (PIR exclusion zone).

The unifying observation: **2A and 2B are the same architecture** because "factor = 0 → edge unreachable → incident nodes invalid as exits" makes exit validity a derived property of the same degradation table. One adapter interface covers both classes.

**Note on earthquake / seismic hazard:** out of scope entirely. Earthquake has no pre-event window — the question is post-event network resilience over hours to days, not pre-event clearance time. The ΔT framework does not apply; the research synthesized in this memo concluded that scoping it out matches the prevailing engineering practice (e.g. the City of Berkeley AB 747 report by KLD Engineering, 2024). Earthquake does not enter the multi-hazard determination, the brief, the audit trail, the map UI, or the data schema.

---

## 3. The hazard metrics table

For each hazard JOSH should support, the four independent inputs:

| Hazard | Zone source | Degradation factor | Egress window | Mobilization |
|---|---|---|---|---|
| **Wildfire** *(shipped)* | CAL FIRE FHSZ (`HHZ_ref_FHSZ` + LRA fallbacks) | 0.35 (VHFHSZ) / 0.50 (high) / 0.75 (moderate) | 45 / 90 / 120 min | 0.90 |
| **Flood** | FEMA NFHL `S_FLD_HAZ_AR` (SFHA + BFE) | 0.20 (AE/A/AH) / 0.35 (AO) / 0.00 (VE); Pregnolato 2017 depth curve when per-segment depth known | 30 (flash) / 180 (riverine) / 360 (coastal) min | 0.90 |
| **Tsunami** | CGS Tsunami Hazard Area (2021 revision) | 0.00 inside / 1.00 outside (binary) | 15 min (near-field design basis) | 1.00 |
| **Dam failure** | DSOD inundation polygons (SB 92 / WC §6161) + NID for federal dams | 0.00 inside / 1.00 outside (binary) | Per-EAP arrival time; default 30 min (<5 mi), 120 min (5–50 mi) | 0.95 |
| **Gas/hazmat pipeline** | NPMS centerlines buffered by PIR (49 CFR §192.903) | 0.00 inside PIR / 0.50 within PIR + 500 ft / 1.00 outside | 10 min | 0.95 |
| **Landslide / debris flow** | USGS post-fire debris flow basins; CGS EILZ (PRC §2690) | 0.50 zonal (deterministic) | 60 min | 0.90 |

### Footnotes on the table

- **Tsunami.** At a 15-minute window and 5% project share, the ΔT threshold is **45 seconds**. Any non-trivial project in zone fails Standard 4 deterministically. The more legally defensible position is to treat "in CGS Tsunami Hazard Area" as **dispositive under Standard 3** (DISCRETIONARY) and report Standard 4 ΔT as informational. Vehicle ΔT is also not the right life-safety model for near-field tsunami — USGS Pedestrian Evacuation Analyst is the appropriate parallel framework, because vehicle congestion was a major Tohoku 2011 fatality driver.
- **Flood — exits get cut before the surge.** This is the major architectural difference from wildfire. The Dijkstra graph must be re-weighted per scenario (impassable edges removed), not the same graph for every hazard. The BFE-elevation exit filter is the canonical form of this: drop any node whose ground elevation is below `BFE + 0.5 ft` freeboard inside an SFHA polygon.
- **Gas/hazmat PIR constant.** The canonical formula is `PIR (ft) = 0.69 × √(P_psig × D_in²)` (PHMSA TTO-13, 2005; 49 CFR §192.903). The `0.004` value in `plan-ab747-multihazard-research.md` §5D is **incorrect** and produces a buffer ~170× too small. Correct before any pipeline data work begins.
- **Dam failure.** DSOD inundation polygons are accessible via Berkeley GeoData mirror or county OES republished services; the DSOD viewer does not expose a public ArcGIS REST endpoint. EAP arrival-time tables are PDF-only and not machine-readable — JOSH must maintain a manually-curated `dam_arrival_times.yaml` keyed on DSOD dam ID, with conservative distance-band defaults for the unparsed case.
- **Landslide.** Pre-event applicability is limited to storm-triggered debris flow over USGS post-fire burn-scar layers (Montecito 2018 / Thomas Fire archetype). Earthquake-triggered landslides are co-seismic and out of scope (see §2 note on earthquake).

---

## 4. The mobilization argument generalizes

Every recommended value above is **≥ 0.90**. This is intentional and reflects a single design argument that already underpins the wildfire methodology:

> Mobilization rates in JOSH are not empirical compliance estimates. They are NFPA 101–style **design surges** intended to capture the dangerous case where compliance is high and the network is overwhelmed. A planning standard calibrated to observed non-compliance would only "pass" review when residents disobey the order — that is not a life-safety standard.

This generalizes across hazards because the underlying physics is the same: **roads fail under high-mobilization events, not low.** Empirical compliance (0.46–0.80 typical for hurricane evacuations; ~0.47 GPS-observed for Kincade Fire) tells us what residents do; the design rate tells us what the network must handle if they do the right thing.

Where the recommended value rises above 0.90 (tsunami 1.00, dam 0.95, gas 0.95), it reflects that the cue is unambiguous and sensory (ground shake, visible inundation, explosion + odorant), the consequence of under-evacuation is categorical, and empirical compliance in the literature is already near unity.

See [`mobilization_rate_methodology_statement.md`](./mobilization_rate_methodology_statement.md) for the full argument in the wildfire context. Per-hazard mobilization memos following the same template are a Phase 2 deliverable.

---

## 5. Architectural changes to JOSH

Implementing the table above requires four changes to `josh` and one per-hazard addition to `josh-pipeline`.

### 5.1 `HazardAdapter` interface (4 functions)

A 4-function interface (the plan's §7.1 5-function form collapses to this once exit validity is recognized as derived):

```python
class HazardAdapter(Protocol):
    name: str

    def classify(self, point_wgs84: tuple[float, float]) -> str:
        """Return the hazard zone for a project location (or 'none')."""

    def degradation(self, edge: RoadSegment, zone: str) -> float:
        """Per-edge capacity multiplier in [0, 1]. 0 → edge removed for this scenario."""

    def egress_window_min(self, zone: str) -> float:
        """Minutes available between event onset and life-safety threshold."""

    def mobilization(self, zone: str) -> float:
        """Vehicle-release fraction in [0, 1]. Design surge, not observed compliance."""
```

`WildfireAdapter` is a refactor of existing logic; the architecture is validated by `FloodAdapter` as the first new implementation.

### 5.2 Per-scenario graph re-weighting

The graph is not rebuilt per hazard — it is re-weighted. For each scenario:

```python
for edge in graph.edges:
    zone   = adapter.classify(edge.midpoint)
    factor = adapter.degradation(edge, zone)
    edge.effective_capacity_vph = edge.base_capacity_vph * factor
    edge.passable = factor > 0   # impassable edges dropped from Dijkstra
```

Dijkstra runs against `effective_capacity_vph`. Impassable edges are excluded by the routing weight — the existing wildfire mechanism applied to a broader set of zones. Exit nodes whose only incident edges are impassable become unreachable automatically; no separate exit-filter pass is needed.

### 5.3 Multi-hazard determination

```python
def evaluate_multihazard(project, adapters, graph, parameters):
    results = {h: evaluate_single_hazard(project, a, graph, parameters)
               for h, a in adapters.items()}
    controlling = max(results.values(), key=lambda r: r.delta_t / r.threshold)
    return MultiHazardDetermination(controlling=controlling, all_results=results)
```

Worst-case single hazard drives the tier; all applicable hazards are reported in the determination letter for transparency. (Plan §9 policy decision #3 — recommendation: report all, controlling drives tier.)

### 5.4 Per-hazard data acquisition (josh-pipeline)

Each adapter needs one GIS layer + a static parameter set. All plug into the existing 90-day cache TTL and `metadata.yaml` audit trail.

| Adapter | Data source | Cache target |
|---|---|---|
| `FloodAdapter` | FEMA NFHL ArcGIS REST `S_FLD_HAZ_AR` + USGS 3DEP DEM | `data/{city}/flood_sfha.geojson` + `flood_dem.tif` |
| `TsunamiAdapter` | CGS Tsunami Hazard Area FeatureServer (item `2769c700c0694548b5435a60ff52b807`) | `data/{city}/tsunami_zone.geojson` |
| `DamFailureAdapter` | DSOD statewide shapefile (Berkeley mirror) + NID federal | `data/{city}/dam_inundation.geojson` + manual `dam_arrival_times.yaml` |
| `GasHazmatAdapter` | NPMS PIMMA centerlines + locally-computed PIR buffer | `data/{city}/pipeline_pir.geojson` |
| `LandslideAdapter` | USGS post-fire DF basins + CGS EILZ | `data/{city}/landslide_zone.geojson` |

### 5.5 What does *not* change

- The ΔT formula itself.
- The Dijkstra routing algorithm.
- HCM 2022 base capacity calculations.
- The `objective_standards.py` determination logic (Standards 1, 2, 4, 5 are hazard-agnostic; Standard 3 generalizes from "in_fire_zone" to "in any applicable hazard zone").
- The brief renderer's A/B/C presentation layer — only the labels and underlying values change per hazard.

This is the strongest argument that the abstraction is the right one: most of JOSH's existing code is already hazard-agnostic and was simply parameterized on wildfire-only inputs.

---

## 6. Recommendations

1. **Build `FloodAdapter` first.** It exercises every new architectural element (network-cutting, BFE-elevation exit filter, depth-dependent degradation) and uses the most mature regulatory dataset (FEMA NFHL has been federal regulatory law since 1968). If FloodAdapter works end-to-end, the remaining hazards are parameter swaps against the same code paths.
2. **Earthquake is out of scope entirely.** Not included in the ΔT framework, the brief, the audit trail, the map UI, or the data schema. The ΔT framework doesn't apply to a post-event hazard with no pre-event clearance window; force-fitting it would invite challenge under SB 330's objective-standard mandate and likely violates Business & Professions Code §6735 (engineering practice act) without a PE stamp. **Precedent:** KLD Engineering's 2024 AB 747 report for the City of Berkeley — the most-cited recent AB 747 implementation in California — also treats earthquake as out-of-scope for evacuation conclusions. JOSH matches the prevailing engineering practice.
3. **Treat tsunami in-zone as dispositive at Standard 3.** A 45-second ΔT threshold means any non-trivial in-zone project fails Standard 4 deterministically, providing zero gradation. The legally defensible posture is "in CGS Tsunami Hazard Area → DISCRETIONARY" with Standard 4 ΔT reported as informational only. This matches how the Coastal Commission already treats tsunami-zone development.
4. **Fix the PIR constant in the plan** (`0.004` → `0.69`) before any pipeline data work begins. The wrong constant produces a buffer ~170× too small.
5. **Hold mobilization at 0.90 or above for every hazard.** Apply the design-for-what-should-happen argument across the board. Per-hazard mobilization memos (Phase 2) document the literature support; none of them justify a value below 0.90.

---

## 7. Visualization and UX

The map UI (`output/{city}/analysis_map.html` + `static/v1/app.js`) currently shows one hazard layer (FHSZ) and one ΔT result per project. Multi-hazard requires three changes — they are additive, not a rewrite.

### 7.1 Design principles

1. **Per-city, not per-app.** The map only shows hazards that have data for that city. Berkeley shows fire (+ potentially flood near the marina); Encinitas shows fire + tsunami + flood. The pipeline knows which adapters returned non-empty zones; it should serialize that list into `JOSH_DATA.applicable_hazards` so the UI doesn't render empty legend entries.
2. **Decouple hazard layers from project paths.** Hazard polygons are city-wide context; project AntPaths are per-project routing. Toggle them in separate sidebar groups so a user can show "all hazard layers + one project's paths" or "no polygons + all projects' paths" without coupling.
3. **Default to the controlling hazard.** When a project is selected, the visible AntPath, the popup tier, and the brief default to the worst-case hazard. A "compare across hazards" affordance is the secondary path, not the primary one.
4. **Reserve color families per hazard.** Color is the fastest disambiguator on a map with five polygon layers.

### 7.2 Hazard palette

Each hazard gets a distinct family so a glance at the map identifies what's shown. Saturation encodes severity within a family (matching how FHSZ moderate/high/very-high already work):

| Hazard | Color family | Polygon fill | AntPath line |
|---|---|---|---|
| Wildfire | red/orange | FHSZ existing palette | `#d62728` (current) |
| Flood | blue | SFHA AE/A solid `#1f77b4`; VE pattern fill | `#1f77b4` |
| Tsunami | teal | `#17becf` solid | `#17becf` |
| Dam failure | purple | `#9467bd` solid | `#9467bd` |
| Gas/hazmat (PIR) | yellow/black hazard stripe | `#bcbd22` with diagonal hatch | `#bcbd22` |
| Landslide / debris flow | brown | `#8c564b` solid | `#8c564b` |

### 7.3 Sidebar additions

**Approved UX patterns (May 2026, after mockup review with the user):**

- **Sidebar placement: right side, ~360px.** Inspector pattern (Figma / browser devtools idiom), not a navigation pattern (Google Maps results). Also avoids occluding the SW-trending evacuation routes in the existing Berkeley data. Departs from the production wildfire-only `analysis_map.html` left sidebar.
- **Single-project dropdown selector.** The panel shows one project at a time, selected via a dropdown at the top of the project section. Production's stacked card list is replaced because (a) projects are never compared side-by-side — each receives an independent determination, and (b) the per-project ΔT bar chart, hazard scenario selector, and hazards-evaluated list need vertical space that a card stack would waste on non-selected projects. Marker click on the map syncs the dropdown to that project (parallel spatial entry point preserved).
- **No marker popups.** Clicking a project marker **selects** the project (highlights marker, draws AntPath, populates the right panel) but does **not** open a popup. Popups sit on top of the project marker — exactly where the evacuation route originates — and occlude the route. All per-hazard ΔT data and the "Open Brief" affordance live in the right panel.

These three patterns are demonstrated in `output/mockup/multihazard_mockup.html` (on branch `claude/magical-blackburn-f0c875` until merged). That file is the **visual contract** for the production frontend — design tokens, chrome, and component patterns there should match production (`static/sidebar.js` + `static/brief_renderer.js`), and Phase 7 implementation should reproduce the mockup's visual structure.

Three new affordances in `static/sidebar.js`:

1. **Hazard layer panel** (collapsed by default). One checkbox per applicable hazard, each toggling a Folium FeatureGroup containing that hazard's polygon overlay. Independent of project selection.
2. **Per-project hazard breakdown** in the evaluation card. Replace the single ΔT readout with a small horizontal bar chart: one bar per applicable hazard, x-axis = ΔT/threshold ratio, bars > 1.0 colored red (failing). The controlling bar is outlined. Hover surfaces the absolute ΔT, threshold, zone, and bottleneck segment for that hazard.
3. **Hazard scenario selector** (radio group): "Controlling (default)" / one entry per hazard. Changing the selector swaps the visible AntPath for that project to the route that hazard's degraded graph produces. This is how a planner explores why flood routing differs from fire routing for the same project.

### 7.4 AntPath behavior

The current model is one AntPath per project (the worst-case wildfire route). The multi-hazard model is one **canonical AntPath per project** (the controlling hazard's route) with an optional **comparison overlay** when the scenario selector is on a specific hazard.

Implementation note: per-hazard routing means up to `N_projects × N_hazards` AntPaths must exist in `JOSH_DATA` for the seeded projects. Pre-baking all of them at `demo` time is straightforward (Dijkstra is fast); inlining them all in the HTML is the only cost, and it's a few KB per path. Browser-created projects compute routes on demand via `whatif_engine.js`, which means the WhatIfEngine itself must accept a `hazard` parameter.

### 7.5 Marker selection state (was: popup template)

**Revised May 2026:** the wildfire-only production uses Folium-baked popups that open when a project marker is clicked. The multi-hazard UX drops popups (see §7.3 — they occlude the AntPath origin). Marker click now:

1. Highlights the selected marker (3px navy outer ring per the mockup's `.josh-pin.selected` rule).
2. Draws the controlling-hazard AntPath from that project.
3. Syncs the right-panel dropdown to the selected project; populates panel content (per-hazard ΔT bar chart, hazards-evaluated list, scenario selector, Open Brief button).

The right-panel content fully replaces the popup. The single most important UX requirement carries forward unchanged: the **controlling hazard must be named** wherever the tier is shown (panel tier line, brief modal determination block, audit trail line). A determination of DISCRETIONARY with no stated cause is the failure mode that invites legal challenge.

### 7.6 What this changes in the file map

| File | Change |
|---|---|
| `agents/visualization/demo.py` | Add hazard polygon FeatureGroups; emit `JOSH_DATA.applicable_hazards` |
| `agents/visualization/popup.py` (or equivalent) | Add per-hazard ΔT table to popup HTML |
| `agents/export.py` | Pre-bake per-hazard routes into `JOSH_DATA.projects[*].hazard_results` |
| `static/sidebar.js` | New hazard-layer panel; per-project hazard bar chart; scenario selector |
| `static/whatif_engine.js` *(generated)* | Accept `hazard` param; route against that adapter's degraded graph |
| `static/v1/app.js` *(generated CDN bundle)* | Includes the above |

The Folium-baked layers are pipeline outputs; the sidebar/engine changes are CDN-deliverable, so feature improvements reach existing cities without a full rebuild.

---

## 8. Reports and determinations

The determination letter, audit trail, and brief HTML all currently assume one hazard. Three changes generalize them.

### 8.1 The tier statement is unchanged

`DISCRETIONARY / CONDITIONAL MINISTERIAL / MINISTERIAL` keep their current meaning. The change is **what causes the tier**, not what the tier says. The letter must now state the controlling hazard:

> *Determination: DISCRETIONARY. Controlling hazard: 100-year SFHA flood (ΔT 12.4 min exceeds 9.0 min threshold). Wildfire ΔT 1.8 min within VHFHSZ 2.25 min threshold.*

### 8.2 The A/B/C presentation expands

Current brief template (`static/brief_renderer.js`):

- **A. Applicability Threshold** — size gate (units ≥ 15). Hazard-agnostic. **Unchanged.**
- **B. Site Parameters** — FHSZ zone + degradation factor + threshold. **Becomes a per-hazard table.** One row per applicable hazard with columns: zone classification, degradation factor, safe egress window, derived ΔT threshold.
- **C. Evacuation Clearance Analysis** — routes + ΔT. **Becomes a per-hazard table.** One row per hazard with columns: bottleneck segment, effective capacity, project vehicles, ΔT, threshold, pass/fail. The controlling row is visually highlighted (border + "controls determination" label).

Where a hazard is dispositive at Standard 3 (e.g. tsunami: in-zone → automatic DISCRETIONARY), Section C's row for that hazard shows the dispositive note in place of the ΔT calculation — it remains within the determination, not excluded from it.

### 8.3 The audit trail .txt expands

`_buildAuditText()` in `static/sidebar.js` currently produces a single linear narrative ending in one ΔT calculation. Multi-hazard form:

```
=== Project: Acme Apartments ===
Address: 1234 Foothill Blvd, Berkeley CA
Units: 48 | Stories: 3 | Egress points: 1

Standard 1 (Applicability): MET — 48 units ≥ 15.

Standard 2 (Evacuation Routes): 3 viable exits identified within
  3.5× fastest-exit ratio. [routes listed]

=== Hazard Evaluation ===

[Hazard: Wildfire]
  Standard 3 (Hazard Classification): VHFHSZ (CAL FIRE FHSZ HAZ_CLASS=3)
  Standard 4 (ΔT Test):
    Bottleneck: Foothill Blvd at Marin Ave (1,575 pc/h base × 0.35 = 551 vph)
    Project vehicles: 48 × 2.5 × 0.90 = 108
    ΔT: 108 / 551 × 60 = 11.8 min
    Threshold (VHFHSZ, 45-min window × 5%): 2.25 min
    Result: FAIL (11.8 > 2.25)

[Hazard: Flood]
  Standard 3 (Hazard Classification): outside SFHA (Zone X)
  Standard 4 (ΔT Test): N/A (no applicable hazard zone)

=== Controlling Hazard: Wildfire ===
=== Standard 5 (SB 79): not applicable (>0.5 mi from major transit) ===
=== Determination: DISCRETIONARY ===
```

This format keeps the existing single-hazard structure for cities where only one hazard applies (no awkward empty sections), but generalizes cleanly when more do.

### 8.4 BriefInput schema additions

`BriefRenderer.render(briefInput)` takes a single `briefInput` today. The schema needs three new fields:

```js
briefInput = {
  // existing fields unchanged
  project: { ... },
  standards: { ... },

  // new — array of per-hazard results
  hazardResults: [
    { hazard: "wildfire", zone: "VHFHSZ", deltaT: 11.8, threshold: 2.25,
      bottleneck: {...}, controls: true },
    { hazard: "flood", zone: "none", deltaT: null, threshold: null, applicable: false },
    // Dispositive-at-Standard-3 example (tsunami in-zone):
    { hazard: "tsunami", zone: "THA", dispositive: true, controls: true,
      reason: "In CGS Tsunami Hazard Area — automatic DISCRETIONARY" }
  ],
  controllingHazard: "wildfire"      // shorthand for the renderer
};
```

The renderer iterates `hazardResults` to build sections B and C; reads `controllingHazard` to set the tier rationale line. A row with `dispositive: true` renders a special Section C note in place of the ΔT calculation.

### 8.5 What this changes in the file map

| File | Change |
|---|---|
| `agents/scenarios/` | New `evaluate_multihazard()` orchestrator that calls each adapter and picks the controlling hazard |
| `agents/export.py` | Serialize per-hazard results into `JOSH_DATA.projects[*].hazard_results` |
| `static/sidebar.js` | `_buildAuditText()` rewritten for per-hazard sections; `_buildBriefInput()` populates new schema fields |
| `static/brief_renderer.js` | A/B/C/D template; per-hazard tables for B and C; controlling-hazard highlight |
| `tests/test_brief_renderer.js` | New test vectors covering 1-hazard, 2-hazard, 3-hazard-with-informational cases |
| `tests/test_whatif_engine.js` | Anti-divergence per hazard (Python vs JS for each adapter) |

### 8.6 The legal posture is unchanged

The tier definitions, the no-discretion principle, and the objective-standard framing all carry forward. What changes is that "the ΔT test" is now plural — once per applicable hazard — and the worst-case result drives the tier. This is the most defensible form because (a) it is fully algorithmic, (b) it surfaces every applicable hazard transparently in the determination, and (c) the controlling-hazard rule has clear precedent in floodplain ordinance practice and CEQA cumulative impact analysis.

---

## 9. Out of scope for this memo

- **Statutory gap analysis** — whether §65302(g) requires quantitative ΔT for non-fire hazards or only narrative assessment. Recommend a separate legal memo before any new adapter ships to a client deliverable.
- **Compound scenarios** (e.g. post-fire debris flow on a same-year burn scar). The plan recommends worst-case single hazard; this memo concurs. Compound modeling is a future extension.
- **Pedestrian evacuation for tsunami.** The right framework for near-field tsunami is USGS Pedestrian Evacuation Analyst, not vehicle ΔT. If pedestrian analysis is in scope for JOSH, it is a separate scenario subclass with its own model (travel time at 1.1–1.79 m/s walking speed against the 15-min window).
- **Local distribution gas pipelines.** Not in NPMS (CPUC GO 112-F jurisdiction); not publicly mapped. JOSH's `GasHazmatAdapter` covers transmission only.
- **Implementation timeline / phasing.** See [`plan-ab747-multihazard-research.md`](./plan-ab747-multihazard-research.md) §8.

---

## 10. Sources by hazard

**Wildfire (shipped):**
- CAL FIRE Office of the State Fire Marshal FHSZ: `https://osfm.fire.ca.gov/divisions/community-wildfire-preparedness-and-mitigation/wildland-hazards-building-codes/fire-hazard-severity-zones-maps/`
- NIST TN 2135 (Camp Fire timeline)

**Flood:**
- FEMA NFHL: `https://www.fema.gov/flood-maps/national-flood-hazard-layer` ; REST: `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer`
- Pregnolato et al. (2017), *Transportation Research Part D* 55:67–81 — depth-disruption curve
- NWS Flash Flood Lead-Time KPI: `https://performance.commerce.gov/KPI-NOAA/NOAA-Severe-weather-warnings-for-flash-floods-Lead/efvm-b4dk`
- USGS 3DEP: `https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer`

**Tsunami:**
- CGS Tsunami Hazard Area (2021): `https://www.conservation.ca.gov/cgs/tsunami/maps`
- Cal OES Cascadia fact sheet (2023): `https://www.caloes.ca.gov/wp-content/uploads/Preparedness/Documents/CalOES_FactSheet_Cascadia_v2023_06_22-final.pdf`
- USGS Pedestrian Evacuation Analyst: `https://www.usgs.gov/software/pedestrian-evacuation-analyst-tool`
- Mas, Suppasri, Imamura — Tohoku 2011 evacuation behavior

**Dam failure:**
- California Water Code §§6160–6161 (SB 92, 2017)
- DSOD inundation map portal: `https://water.ca.gov/Programs/All-Programs/Division-of-Safety-of-Dams/Inundation-Maps`
- DSOD jurisdictional dam REST: `https://gis.water.ca.gov/arcgis/rest/services/Structure/i17_California_Jurisdictional_Dams/MapServer`
- USBR RCEM (warning-diffusion curves): `https://www.usbr.gov/ssle/damsafety/documents/RCEM-Methodology2015.pdf`
- FEMA/USACE National Inventory of Dams: `https://nid.sec.usace.army.mil/`

**Gas/hazmat pipeline:**
- 49 CFR §192.903 (PIR + HCA): `https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-D/part-192/subpart-O/section-192.903`
- PHMSA TTO-13 PIR final report (2005): `https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/docs/technical-resources/pipeline/gas-transmission-integrity-management/65311/tto13potentialimpactradiusfinalreportjune2005.pdf`
- NPMS Public Viewer: `https://pvnpms.phmsa.dot.gov/PublicViewer/`
- NTSB PAR-11/01 (San Bruno, 2011): `https://www.ntsb.gov/investigations/accidentreports/reports/par1101.pdf`

**Landslide / debris flow:**
- USGS Post-Fire Debris Flow Hazard Assessments: `https://landslides.usgs.gov/hazards/postfire_debrisflow/`
- CGS Seismic Hazard Zones (EILZ): `https://maps.conservation.ca.gov/cgs/shz/`
- USGS OFR 2018-1119 (Montecito): `https://pubs.usgs.gov/of/2018/1119/`
- Staley et al. (2017), *Geomorphology* — post-fire DF logistic regression: `https://doi.org/10.1016/j.geomorph.2016.10.019`

**Earthquake (out of scope, reference for the scope-out decision only):**
- KLD Engineering, P.C. — *City of Berkeley: Evacuation Route Safety, Capacity, and Viability Analysis — AB 747 Report* (Rev. 3, February 2024). Cited as precedent for scoping earthquake out of evacuation determinations.
- PRC §§2621, 2690 (Alquist-Priolo + Seismic Hazard Mapping Act) — provide the separate statutory regime for seismic site evaluation, governed by independent PE-stamped assessment outside JOSH.

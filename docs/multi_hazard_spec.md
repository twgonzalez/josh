# Feature Spec: Multi-Hazard Evacuation Scenario Support

**Status:** Approved for implementation — phased sprints
**Prepared:** 2026-03-27 · JOSH v3.4

---

## Background

AB 747 (Gov. Code §65302.15) requires Safety Elements to evaluate evacuation route viability
"under a range of emergency scenarios," not just wildfire. The KLD Engineering Berkeley study
modeled seven hazard types but deferred city-wide clearance time and SB 99 analysis to
separate studies. JOSH currently covers wildfire only.

This spec adds flood, tsunami, liquefaction, earthquake-induced landslide, deep-seated
landslide susceptibility, and earthquake ground shaking as additional evacuation scenarios —
each implemented as a new `EvacuationScenario` subclass following the existing architecture.

---

## Architecture: Why New Hazards Are Cheap to Add

The JOSH scenario framework (`agents/scenarios/base.py`) is already designed for this.
Every new hazard requires only three steps:

1. **Fetch the zone data** — copy the `fetch_fhsz_zones()` pattern in `data_acquisition.py`
   (~60 lines). All four "drop-in" hazards use the same ArcGIS REST API pattern FHSZ uses.
2. **Define degradation factors** — add entries to `config/parameters.yaml` under
   `hazard_degradation.factors` and `safe_egress_window`. ΔT thresholds auto-derive at runtime.
3. **Write a scenario subclass** — inherit from `EvacuationScenario`, implement
   `check_applicability()` (zone lookup) and `identify_routes()` (reuse WildlandScenario
   routing). Register in `agents/objective_standards.py` (one line).

The ΔT engine, most-restrictive-wins logic, audit trail, determination letter, and AB 747
report sections all work without modification.

---

## Data Sources

All layers are free public APIs — no API key required for any of them.

| Hazard | Agency | API Endpoint | Coverage |
|--------|--------|-------------|----------|
| Wildfire (current) | CAL FIRE | `egis.fire.ca.gov/arcgis/rest/services/FRAP/HHZ_ref_FHSZ/MapServer/0` | Statewide |
| FEMA Flood Zones | FEMA NFIP | `hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28` | Nationwide |
| Tsunami Inundation | CGS / Cal OES | `services.gis.ca.gov/arcgis/rest/services/Oceans/Tsunami/MapServer/0` | CA coastal |
| Liquefaction Zones | CGS (SHMA) | `gis.conservation.ca.gov/server/rest/services/CGS_Earthquake_Hazard_Zones/SHP_Liquefaction_Zones/MapServer` | Partial CA |
| EQ-Induced Landslide | CGS (SHMA) | `gis.conservation.ca.gov/server/rest/services/CGS_Earthquake_Hazard_Zones/SHP_Landslide_Zones/MapServer` | Partial CA |
| Landslide Susceptibility | CGS Map Sheet 58 | `gis.conservation.ca.gov/server/rest/services/CGS/MS58_LandslideSusceptibility_Classes/MapServer/0` | Statewide raster |
| Earthquake Shaking | USGS ShakeMap | Scenario-specific download (HayWired M7.0 for Bay Area; ShakeOut M7.8 for SoCal) | Region-specific |

---

## Hazard-by-Hazard Details

### Sprint 1 — Flood + Tsunami (~1 week total)

These are **drop-in** integrations. The API pattern is identical to FHSZ — copy `fetch_fhsz_zones()`,
change the URL, normalize the zone field. No new code architecture required.

#### FEMA Flood Zones (NFHL Layer 28)

**Data source:** FEMA National Flood Hazard Layer
**Endpoint:** `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query`
**Key field:** `FLD_ZONE` (string) + `SFHA_TF` (T/F)

Zone classification mapping:

| FEMA Zone | Risk | JOSH Class | Degradation Factor | Safe Egress Window |
|-----------|------|-----------|-------------------|-------------------|
| A, AE, A1–A30, AO, AH | High (100-yr / 1% annual) | `flood_high` | 0.40 | 60 min |
| VE, V, V1–V30 | Coastal high hazard + wave action | `flood_coastal` | 0.25 | 45 min |
| X (shaded) | Moderate (500-yr / 0.2% annual) | `flood_moderate` | 0.75 | 90 min |
| X (unshaded), D | Minimal / undetermined | `non_flood` | 1.00 | 120 min |

**Degradation factor basis:**
- `flood_high` 0.40: FHWA Hydraulic Engineering Circular 17 (HEC-17) — road overtopping
  reduces travel speed to 5–10 mph; at 3–4 lanes/hr that is roughly 35–45% of base capacity.
- `flood_coastal` 0.25: Wave action and debris make coastal routes partially impassable;
  lower than standard flood per FHWA Emergency Transportation Operations guide.
- `flood_moderate` 0.75: Shallow flooding possible; speed reduction comparable to FHSZ
  Moderate (light visibility degradation).

**Safe egress window basis:**
- `flood_high` 60 min: FEMA NFIP standard for rapid-onset flood events; National Weather
  Service Flash Flood Emergency alert-to-impact timeline (typically 30–90 min depending on
  watershed); conservative midpoint used.
- `flood_coastal` 45 min: Matches VHFHSZ wildfire window; coastal flood events (king tides
  plus storm surge) can develop within 30–60 min of peak warning.

**New files:**
- `data/{city}/flood_zones.geojson` — cached NFHL Layer 28 features
- `agents/scenarios/flood.py` — `FloodScenario` class

**New config (`parameters.yaml`):**

```yaml
flood:
  api_base: "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
  layer: 28
  sfha_zones: ["A", "AE", "AO", "AH", "VE", "V"]   # SFHA_TF = True zones

hazard_degradation:
  factors:
    # ... existing wildfire factors ...
    flood_high: 0.40
    flood_coastal: 0.25
    flood_moderate: 0.75
    non_flood: 1.00

safe_egress_window:
  # ... existing wildfire windows ...
  flood_high: 60
  flood_coastal: 45
  flood_moderate: 90
  non_flood: 120
```

---

#### Tsunami Inundation

**Data source:** CGS / Cal OES Tsunami Inundation Maps
**Endpoint:** `https://services.gis.ca.gov/arcgis/rest/services/Oceans/Tsunami/MapServer/0/query`
**Key field:** Binary polygon (in/out). All features within the polygon are inundation zone.
**Inland cities:** Query returns zero features → `tsunami_zone = False` → no impact.

Zone classification mapping (binary):

| Condition | JOSH Class | Degradation Factor | Safe Egress Window |
|-----------|-----------|-------------------|-------------------|
| Within inundation polygon | `tsunami_inundation` | 0.20 | 30 min |
| Outside polygon | `non_tsunami` | 1.00 | N/A |

**Degradation factor basis:**
- `tsunami_inundation` 0.20: Post-2011 Tōhoku field surveys showed near-complete road
  closure in inundation zones during the wave sequence (Suppasri et al., 2013, *Natural
  Hazards*); 0.20 represents one-way single-lane emergency-vehicle access on elevated
  sections only.
- Safe egress window 30 min: NOAA Pacific Tsunami Warning Center warning-to-impact for
  near-source California Cascadia Subduction Zone scenario (NOAA NTHMP, 2013).
  National-source tsunamis (Chile, Alaska) have longer windows; near-source is the binding case.

**Legal note:** CGS explicitly states tsunami maps are evacuation planning tools only, not
regulatory documents. Unlike FHSZ (which has statutory authority under PRC 4201–4204), a
tsunami overlay in JOSH determination letters should be labeled "informational" rather than
used as a determination threshold until a city adopts the layer by ordinance.

**New files:**
- `data/{city}/tsunami_zones.geojson` — cached CGS tsunami inundation polygon
- `agents/scenarios/tsunami.py` — `TsunamiScenario` class

---

### Sprint 2 — Seismic Zones (~1 week total)

These also use the `gis.conservation.ca.gov` server (same as future Sprint 1 APIs), but have
**coverage gaps** — not every California county has been formally mapped under the Seismic
Hazard Mapping Act (SHMA). Unmapped areas must be treated as "not evaluated," not "safe."

#### Liquefaction Susceptibility Zones (CGS SHMA)

**Data source:** CGS Seismic Hazards Program — Liquefaction Zones of Required Investigation
**Endpoint:** `https://gis.conservation.ca.gov/server/rest/services/CGS_Earthquake_Hazard_Zones/SHP_Liquefaction_Zones/MapServer/0/query`
**Key field:** Binary in/out polygon (zone type is "Liquefaction" or overlap with landslide)

Zone classification:

| Condition | JOSH Class | Degradation Factor | Safe Egress Window |
|-----------|-----------|-------------------|-------------------|
| Within mapped liquefaction zone | `liquefaction` | 0.45 | 30 min |
| Outside zone (mapped area) | `non_liquefaction` | 1.00 | N/A |
| Unmapped area | `seismic_unevaluated` | 0.70 | 60 min |

**Degradation factor basis:**
- `liquefaction` 0.45: Caltrans *Seismic Design Criteria* + USGS post-Loma Prieta (1989)
  data showing lateral spreading closed or severely restricted 40–60% of road capacity in
  mapped liquefaction zones (Holzer & Youd, 2007, *Earthquake Spectra*).
- `seismic_unevaluated` 0.70: Conservative placeholder for unmapped areas. Not a studied
  value — calibration required by city's geotechnical consultant before adoption. Disclosed
  in report methodology section.

**Coverage gap handling:** Check for `data/{city}/seismic_unevaluated.geojson` (downloaded
from the CGS `SHP_Unevaluated_Areas` FeatureServer layer). If a project falls outside both
the mapped zone and the evaluated area, apply the `seismic_unevaluated` factor and flag in
the audit trail: *"Project location is outside CGS SHMA evaluated area. Factor 0.70 applied
as conservative planning estimate pending formal evaluation."*

**New files:**
- `data/{city}/liquefaction_zones.geojson`
- `data/{city}/seismic_unevaluated.geojson` — unevaluated area boundary (for gap detection)
- `agents/scenarios/liquefaction.py` — `LiquefactionScenario` class

---

#### Earthquake-Induced Landslide Zones (CGS SHMA)

**Data source:** CGS Seismic Hazards Program — Earthquake-Induced Landslide Zones
**Endpoint:** `https://gis.conservation.ca.gov/server/rest/services/CGS_Earthquake_Hazard_Zones/SHP_Landslide_Zones/MapServer/0/query`
**Coverage:** Same SHMA coverage gaps as liquefaction above (same evaluation program).

Zone classification:

| Condition | JOSH Class | Degradation Factor | Safe Egress Window |
|-----------|-----------|-------------------|-------------------|
| Within mapped landslide zone | `eq_landslide` | 0.50 | 30 min |
| Outside zone (mapped area) | `non_eq_landslide` | 1.00 | N/A |
| Unmapped area | `seismic_unevaluated` | 0.70 | 60 min |

**Degradation factor basis:**
- `eq_landslide` 0.50: HCM weather/incident composite + post-Northridge (1994) blockage
  data (Parise & Jibson, 2000, *Engineering Geology*) showing ~50% of routes in mapped zones
  experienced at least one blockage event in the 6-hour post-event window.

**Note:** Liquefaction and earthquake landslide zones often overlap (CGS maps them together).
The scenario classes can share the same `seismic_unevaluated` zone check. The most-restrictive-
wins logic in `objective_standards.py` automatically handles both scenarios without special cases.

**New files:**
- `data/{city}/eq_landslide_zones.geojson`
- `agents/scenarios/eq_landslide.py` — `EqLandslideScenario` class

---

### Sprint 3 — Earthquake Shaking (~2–3 weeks)

This is qualitatively different from Sprints 1 and 2. There is **no single statewide polygon
layer** for earthquake ground shaking analogous to FHSZ. Viable approaches, in order of
complexity:

#### Option A: Region-specific scenario (recommended for Phase 1)

Download a fixed design-basis scenario ShakeMap for each supported region and store it as a
static local layer. Examples:

| Region | Scenario | Source | MMI Contour Format |
|--------|----------|--------|-------------------|
| Bay Area | HayWired M7.05 (Hayward Fault) | USGS ScienceBase `5994b635e4b0fe2b9fe91587` | GeoJSON contours |
| Greater LA | ShakeOut M7.8 (San Andreas Fault) | USGS Scenarios Catalog | GeoJSON contours |
| San Diego | Rose Canyon M6.9 | USGS / CGS | GeoJSON contours |
| Central Valley | Calaveras M6.8 | USGS | GeoJSON contours |

The ShakeMap GeoJSON contours contain MMI values as polygon features. Bin MMI into
degradation zones:

| MMI | Shaking Description | JOSH Class | Degradation Factor | Safe Egress Window |
|-----|---------------------|-----------|-------------------|-------------------|
| ≥ IX (Violent) | Near-total structural damage | `eq_violent` | 0.20 | 30 min |
| VII–VIII (Very Strong / Severe) | Structural damage in buildings | `eq_severe` | 0.40 | 45 min |
| V–VI (Moderate / Strong) | Felt strongly; minor damage | `eq_moderate` | 0.70 | 60 min |
| < V | Weak / not felt | `non_eq` | 1.00 | N/A |

**Degradation factor basis:** Caltrans *Seismic Design Criteria* + ASCE 7-22 + post-Northridge
and Loma Prieta bridge closure data. KLD Engineering Berkeley report used MMI 8 (severe) and
MMI 9 (violent) for the HayWired scenario — JOSH uses the same classification.

**city_config key** to select the regional scenario:
```yaml
# config/cities/berkeley.yaml
earthquake_scenario: "haywired_m7"   # → loads data/haywired_m7_shakemap.geojson
```

Shared scenario shapefiles stored in `data/scenarios/` (not city-specific) to avoid
re-downloading for every Bay Area city.

#### Option B: USGS NSHM probabilistic PGA raster (future)

Download the 2023 USGS National Seismic Hazard Model PGA raster (2% in 50 years), bin
continuous PGA values into the degradation zones above using rasterio point queries. Requires
`rasterio` as a new dependency. Fully statewide but needs additional methodology work to
relate PGA → MMI → road capacity reduction.

**New files:**
- `data/scenarios/haywired_m7_shakemap.geojson` — Bay Area scenario (shared)
- `data/scenarios/shakeout_m78_shakemap.geojson` — SoCal scenario (shared)
- `agents/scenarios/earthquake.py` — `EarthquakeScenario` class
- `config/parameters.yaml` — `earthquake_scenarios:` dict mapping scenario keys to file paths

---

### Deep-Seated Landslide Susceptibility (CGS Map Sheet 58) — Optional

**Data source:** CGS Map Sheet 58
**Endpoint:** `https://gis.conservation.ca.gov/server/rest/services/CGS/MS58_LandslideSusceptibility_Classes/MapServer/0`
**Format:** Classified raster (0–10 susceptibility classes) — requires `rasterio` point query,
not `gpd.sjoin()`.

This layer provides **statewide coverage** (unlike the SHMA liquefaction/landslide polygon
zones) and is useful for non-seismic landslide risk in areas with steep terrain and saturated
soils (e.g., atmospheric river events). However:
- CGS explicitly notes it is "not appropriate for evaluation at any specific site"
- It does not cover shallow landslides or debris flows
- The 0–10 scale needs binning into degradation zones with a separate methodology rationale

**Recommendation:** Implement after Sprint 3 if cities in steep terrain areas (Marin, Santa
Cruz mountains, Big Sur) request it. Not needed for flat or valley-floor cities.

---

## Implementation Template

Each new scenario follows this pattern:

```python
# agents/scenarios/flood.py

# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

from agents.scenarios.base import EvacuationScenario, Tier, ScenarioResult
from agents.scenarios.wildland import WildlandScenario   # reuse routing logic

class FloodScenario(EvacuationScenario):

    @property
    def name(self) -> str:
        return "flood_nfhl"

    @property
    def legal_basis(self) -> str:
        return (
            "FEMA National Flood Insurance Program (NFIP); "
            "Gov. Code §65302.15(d) — range of emergency scenarios"
        )

    @property
    def unit_threshold(self) -> int:
        return int(self.config.get("unit_threshold", 15))

    @property
    def fallback_tier(self) -> Tier:
        return Tier.MINISTERIAL_WITH_STANDARD_CONDITIONS

    def check_applicability(self, project, context) -> tuple[bool, dict]:
        """
        Step 1: Point-in-polygon test against FEMA NFHL flood zones.
        Sets project.flood_zone = "flood_high" | "flood_coastal" |
                                   "flood_moderate" | "non_flood"
        """
        flood_gdf = context.get("flood_zones")
        if flood_gdf is None or len(flood_gdf) == 0:
            return False, {"reason": "No flood zone data available for this city"}
        # ... gpd.sjoin() point-in-polygon, zone lookup ...

    def identify_routes(self, project, roads_gdf, context) -> tuple[list, dict]:
        """
        Step 3: Reuse WildlandScenario routing with flood-degraded capacity.
        Roads in flood zones already have effective_capacity_vph computed
        using the flood hazard_degradation factor (applied by capacity_analysis).
        """
        # delegate to wildland routing — same graph, same Dijkstra
        wildland = WildlandScenario(self.config, self.city_config)
        return wildland.identify_routes(project, roads_gdf, context)
```

**Registration (agents/objective_standards.py):**

```python
from agents.scenarios.flood import FloodScenario
from agents.scenarios.tsunami import TsunamiScenario

scenarios = [
    WildlandScenario(config, city_config),
    FloodScenario(config, city_config),     # Sprint 1
    TsunamiScenario(config, city_config),   # Sprint 1 — no-ops for inland cities
    Sb79TransitScenario(config, city_config),
]
```

---

## Impact on Capacity Analysis (Agent 2)

The road capacity degradation is computed **once** per road segment in `capacity_analysis.py`,
not inside the scenario class. Each segment can only have one `hazard_degradation` factor
applied at a time (the current wildfire factor).

For multi-hazard, there are two design options:

**Option A — Worst-case single factor (recommended for Phase 1):**
Apply the most restrictive degradation factor across all active hazards to each road segment.
Simple, conservative, legally defensible.

```python
# In _apply_hazard_degradation():
factors = []
if fhsz_zone != "non_fhsz":
    factors.append(config["hazard_degradation"]["factors"][fhsz_zone])
if flood_zone != "non_flood":
    factors.append(config["hazard_degradation"]["factors"][flood_zone])
# ... etc.
degradation = min(factors) if factors else 1.00
```

**Option B — Per-scenario routing (future, more accurate):**
Run separate Dijkstra passes per scenario, each with a different road capacity set. Each
scenario gets its own `EvacuationPath` list with scenario-specific bottleneck capacity.
More complex, but allows a road that is safe from flood but blocked by liquefaction to be
modeled accurately. Requires separate `effective_capacity_vph_{scenario}` columns in `roads_gdf`.

---

## AB 747 Report Integration

The `ab747_report.py` Section I ("Viability Scenarios") already has a placeholder that says
"other hazards deferred." Once scenarios are implemented, Section I should expand to a table:

| Scenario | Data Source | Zone Type | Degradation | City Status |
|----------|-------------|-----------|-------------|-------------|
| Wildfire | CAL FIRE FHSZ | 658 segments in FHSZ | 0.35–0.75 | ✅ Analyzed |
| Flood (SFHA) | FEMA NFHL | 0 segments in SFHA | — | ✅ No SFHA segments |
| Tsunami | CGS | 0 segments in inundation zone | — | ✅ Inland city — no exposure |
| Liquefaction | CGS SHMA | Unevaluated — Alameda Co. mapping pending | — | ⚠️ Pending CGS mapping |
| Earthquake (HayWired M7.0) | USGS ShakeMap | 1,247 segments in MMI VII+ | 0.40–0.60 | ✅ Analyzed |

---

## Verification

After Sprint 1 (Flood + Tsunami):

```bash
# Berkeley has no FEMA SFHA zones (hills city, no floodplain)
# Expected: FloodScenario returns NOT_APPLICABLE
uv run python main.py evaluate --city "Berkeley" --lat 37.87 --lon -122.27 --units 75
# Audit trail should show: flood_nfhl: NOT_APPLICABLE (no SFHA segments)

# Encinitas has FEMA AE flood zones near San Elijo Lagoon
# Expected: FloodScenario returns analysis for projects near lagoon
uv run python main.py evaluate --city "Encinitas" --lat 33.02 --lon -117.26 --units 40
# Audit trail should show: flood_nfhl: flood_high zone, effective capacity reduced

# Test tsunami — Berkeley is inland
uv run python main.py analyze --city "Berkeley"
# Expected: tsunami_zones.geojson has zero features; TsunamiScenario skips

# Test tsunami — Santa Cruz is coastal
uv run python main.py analyze --city "Santa Cruz"
# Expected: tsunami_zones.geojson has features along coastal routes
```

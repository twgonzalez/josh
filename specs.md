> **ARCHIVED — v2.0 (v/c ratio framework).** This document is superseded by
> [`docs/JOSH_v3_Specification.md`](docs/JOSH_v3_Specification.md) (v3.1 ΔT standard, current).

# Fire Evacuation Capacity Analysis System — Specification

**Version:** 2.0 (revised to align with KLD Engineering AB 747 methodology)
**Authority:** California Assembly Bill 747 (Gov. Code §65302.15), AB 1600, SB 79
**Reference study:** KLD Engineering, P.C., *Evacuation Route Safety, Capacity, and Viability Analysis — AB 747 Requirement*, City of Berkeley, March 7, 2024 (KLD TR-1381)

---

## Project Purpose

AI agent system that analyzes fire evacuation route capacity for **any California city** to:

1. Establish **objective development standards** (ministerial vs. discretionary review)
2. Generate **impact fee nexus studies** (AB 1600 compliant)
3. Enable **what-if analysis** for proposed developments

This is a legally-focused system. All standards must be objective (no engineering judgment, no discretion).

---

## Core Design Principles

### 1. Citywide Scope — Not Fire-Zone-Only

AB 747 §65302.15 requires cities to analyze evacuation routes "under a **range of emergency scenarios**." A fire can start anywhere — not only in a mapped FHSZ zone. Therefore:

- **All city residents and employees** are potential evacuees, regardless of their proximity to FHSZ zones.
- **All roadways** in the city are candidate evacuation routes.
- Evacuation demand is assigned to every road segment based on the population within a quarter-mile buffer (matching the KLD/Berkeley methodology).
- FHSZ zone location is a **severity modifier** within the determination, not a gate.

### 2. Demand Sources (All City-Wide)

Per the KLD Berkeley study, evacuation demand has three components:

| Population | Vehicle rate | Mobilization | Peak demand |
|---|---|---|---|
| Residents (Census ACS HUs × avg vehicles/HU) | city-specific (default 2.5) | 57% of households per peak hour | **resident_vph** |
| Employees (Census LEHD in-commuters) | 1 vehicle/employee | 100% in first hour (daytime) | **employee_vph** |
| Students (major universities only, city config) | 1 vehicle/student with car | 100% in first hour (session) | **student_vph** |

**Demand formula per road segment (two outputs — different uses):**

```
# 1. baseline_demand_vph — used for Standard 4 v/c ratio test (catchment-based)
#    Source: network path analysis; counts only HUs whose shortest evacuation path
#    traverses this segment (more precise than a flat buffer).
baseline_demand_vph = catchment_housing_units × vehicles_per_unit × resident_mobilization
  where:
    catchment_housing_units = HUs in block groups whose Dijkstra path crosses this segment
    vehicles_per_unit       = 2.5 (Census ACS default)
    resident_mobilization   = 0.57 (KLD Engineering AB 747 study, Figure 12)

# 2. evacuation_demand_vph — informational; citywide planning reference (KLD buffer model)
#    NOT used for Standard 4. Stored for comparison to KLD study outputs.
evacuation_demand_vph = resident_vph + employee_vph + student_vph
  where:
    resident_vph = housing_units_in_buffer × vehicles_per_unit × resident_mobilization
    employee_vph = employees_in_buffer × 1.0 × employee_mobilization
    student_vph  = student_vehicles_in_buffer × 1.0 × student_mobilization
  buffer_radius  = 0.25 miles (quarter-mile, matching KLD methodology)
```

**Scenario variants (min / max demand):**

| Scenario | Employee fraction | Student fraction | When applicable |
|---|---|---|---|
| Maximum (daytime, school in session) | 1.00 | 1.00 | Worst-case planning |
| Minimum (nighttime, school out) | 0.10 | 0.00 | Baseline / overnight |

System always uses **maximum demand** for development impact determination (conservative).

### 3. Evacuation Route Identification

All road segments in the city network are evaluated. Evacuation routes are identified via:

1. **Origin points:** Centroid of every Census block group within city boundary (all groups, not just FHSZ zones)
2. **Destination points:** All road exits at the city boundary along major evacuation routes
3. **Method:** Network shortest path (Dijkstra) from every origin to every exit
4. **Connectivity score:** Number of origin-destination paths traversing each segment
5. **Designation threshold:** Segments used by ≥ 1 O-D path = evacuation route

This matches the KLD study's "network analyst shortest path" approach. The resulting connectivity map identifies the arterial backbone (high score = many households depend on this segment) as well as local residential feeders (low score = few dependencies).

### 4. Capacity Standards (HCM 2022)

Unchanged from KLD study — capacity is a function of lanes × per-lane rate:

| Road Type | Per-lane capacity (pc/h) | Notes |
|---|---|---|
| Freeway | 2,250 | Conservative; KLD uses same |
| Multilane highway / arterial | 1,900 | Per KLD for free-speeds 45–70 mph |
| Two-lane ≤ 20 mph | 900 | |
| Two-lane 25 mph | 1,125 | |
| Two-lane 30 mph | 1,350 | |
| Two-lane 35 mph | 1,575 | |
| Two-lane ≥ 40 mph | 1,700 | |

Lane counts: from OSM data (field-verified where possible). Estimated where missing.

### 5. V/C Ratio and LOS

```
v/c_ratio = baseline_demand_vph / capacity_vph

LOS A: v/c 0.00–0.10
LOS B: v/c 0.10–0.20
LOS C: v/c 0.20–0.40
LOS D: v/c 0.40–0.60
LOS E: v/c 0.60–0.95
LOS F: v/c 0.95+
```

### 6. Determination Logic (Revised — Three Tiers)

The fire zone location is a **severity modifier**, not an entry gate. Any project that pushes serving routes over the v/c threshold triggers DISCRETIONARY review, regardless of whether the project site is in an FHSZ zone. This reflects AB 747's citywide scope.

```
DISCRETIONARY REVIEW REQUIRED:
  IF size_met (units ≥ threshold)
  AND capacity_exceeded (marginal causation: baseline_vc < 0.95 AND proposed_vc ≥ 0.95
                         on any serving route)
  → Requires full CEQA + fire safety review (AB 747, AB 1600)

  Note: Routes already failing at baseline (vc ≥ 0.95) are recorded in the audit trail
  but do NOT trigger DISCRETIONARY — the project did not cause that failure.

  Severity modifier (fire_zone_modifier = TRUE if project in FHSZ Zone 2/3):
  → Triggers additional fire-specific conditions and higher-priority mitigation
  → Does NOT by itself trigger DISCRETIONARY

CONDITIONAL MINISTERIAL:
  IF city_has_fhsz (Standard 1 citywide)
  AND size_met
  AND NOT capacity_exceeded
  → Ministerial with mandatory evacuation conditions
  → Legal basis: General Plan Safety Element + AB 1600 nexus

MINISTERIAL:
  IF NOT size_met OR city has no FHSZ zones
  → No evacuation conditions required
```

**Standard 4 (capacity test) project impact calculation:**

```
project_vph = dwelling_units × vehicles_per_unit × resident_mobilization

# Worst-case marginal impact test: each serving route is independently evaluated
# against the project's FULL peak-hour vehicle load (not divided by n_routes).
# This tests whether any single route would be pushed over the threshold if it
# absorbed all project vehicles — conservative but legally defensible.
vehicles_per_route = project_vph   # NOT divided by count(serving_routes)

For each serving route:
  proposed_demand = baseline_demand_vph + vehicles_per_route
  proposed_vc = proposed_demand / capacity_vph

  # Marginal causation test (CEQA significance):
  flagged = (baseline_vc < vc_threshold) AND (proposed_vc >= vc_threshold)
  # Routes already failing (baseline_vc >= vc_threshold) are recorded but NOT flagged.
```

---

## Data Sources

| Dataset | Source | API / URL | Format | City-specific config |
|---|---|---|---|---|
| FHSZ Zones | CAL FIRE OSFM ArcGIS REST | `https://gis.data.cnra.ca.gov/...` | GeoJSON | None (statewide layer) |
| Road Network | OpenStreetMap via OSMnx | OSMnx library | GeoPackage | `osmnx_place` |
| City Boundary | U.S. Census TIGER | Census API | GeoJSON | `state_fips`, `county_fips` |
| Census Housing Units | Census ACS 5-Year B25001 | `api.census.gov` | JSON | `state_fips`, `county_fips` |
| Census Vehicles per HU | Census ACS 5-Year B25044 | `api.census.gov` | JSON | same |
| Census Population | Census ACS 5-Year B01003 | `api.census.gov` | JSON | same |
| Employee Demand | Census LEHD OnTheMap or ACS B08301 | OnTheMap API | CSV/JSON | `lehd_available` flag |
| University Students | City config (enrollment × vehicle rate) | manual entry | YAML | `universities[]` |
| Block Group Geometry | Census Cartographic Boundary (500k) | `www2.census.gov/geo/tiger/GENZ` | Shapefile | `state_fips` |

**Fallback hierarchy for employee demand (if LEHD unavailable):**
1. ACS B08301 (workers by transportation mode) — provides in-commuter count
2. City-provided jobs data
3. Estimate: `city_population × employment_rate × commute_in_fraction` (configured in city YAML)

---

## System Architecture

### Agent 1: Data Acquisition

**Inputs:** city name, state, city config YAML
**Outputs cached to `data/{city}/`:**

```
boundary.geojson        — city boundary polygon (Census TIGER)
fhsz.geojson            — FHSZ zones clipped to city bbox
roads.gpkg              — OSM road network (layer: "roads")
block_groups.geojson    — Census block groups with attributes:
                            housing_units_in_city   (area-weighted clip to boundary)
                            housing_units_in_fhsz   (area-weighted FHSZ intersection)
                            population              (B01003, area-weighted)
                            vehicles_per_hu         (B25044, city avg)
                            employee_count          (LEHD or estimate)
                            student_count           (university config, by block group proximity)
metadata.yaml           — source URLs, download dates, vintage (audit trail)
```

**Key functions:**
- `acquire_data()` — orchestrates all downloads, caches with 90-day TTL
- `fetch_census_housing_units()` — ACS B25001 + B25044 + B01003 joined to block group geometry
- `fetch_employee_demand()` — LEHD OnTheMap or ACS B08301 fallback
- `fetch_census_block_groups()` — downloads cb_{year}_{state_fips}_bg_500k.zip, clips to city
- `_compute_fhsz_housing_units()` — area-weighted intersection for FHSZ HUs

### Agent 2: Capacity Analysis

**Inputs:** roads_gdf, fhsz_gdf, boundary_gdf, block_groups_gdf, config, city_config
**Outputs:** roads_gdf with added columns per segment:

```
capacity_vph            — HCM 2022 per road type × lanes
road_type               — freeway / multilane / two_lane
lane_count              — from OSM or estimated
speed_limit             — from OSM or estimated
lane_count_estimated    — boolean flag
speed_estimated         — boolean flag
baseline_demand_vph     — resident_vph + employee_vph + student_vph (quarter-mile buffer)
resident_demand_vph     — resident component
employee_demand_vph     — employee component
student_demand_vph      — student component (if applicable)
catchment_hu            — housing units within quarter-mile buffer
catchment_employees     — employees within quarter-mile buffer
demand_scenario         — "maximum" | "minimum"
demand_source           — "census_buffer" | "aadt_based" | "road_class_estimated"
vc_ratio                — baseline_demand_vph / capacity_vph
los                     — A–F per HCM LOS table
is_evacuation_route     — boolean: segment used by ≥1 O-D path from any block group centroid
connectivity_score      — count of O-D paths traversing this segment (all block groups)
```

**Pipeline (in order):**
1. `_apply_hcm_capacity()` — HCM 2022 capacity by road type
2. `_identify_evacuation_routes()` — Dijkstra from ALL block group centroids to all exits
3. `_apply_buffer_demand()` — quarter-mile buffer spatial join, compute demand components
4. `_apply_baseline_demand()` — dispatches: AADT > census_buffer > road_class fallback
5. `_compute_vc_los()` — v/c ratio and LOS assignment

**`_apply_buffer_demand()` detail:**
```python
# For each road segment:
buffer = segment.geometry.buffer(402)  # 0.25 miles in analysis CRS
bg_in_buffer = block_groups_proj[block_groups_proj.intersects(buffer)]
catchment_hu = bg_in_buffer['housing_units_in_city'].sum()
catchment_emp = bg_in_buffer['employee_count'].sum()
catchment_stu = bg_in_buffer['student_count'].sum()

resident_vph  = catchment_hu * vehicles_per_unit * resident_mobilization   # 0.57
employee_vph  = catchment_emp * 1.0 * employee_mobilization                # 1.00 (max), 0.10 (min)
student_vph   = catchment_stu * student_vehicle_rate * student_mobilization # 1.00 (max), 0.00 (min)
baseline_demand_vph = resident_vph + employee_vph + student_vph
```

**`_identify_evacuation_routes()` detail:**
- Origins: centroid of each block group (all 100+ in city — not FHSZ only)
- Exits: road segments at city boundary on roads of class primary/secondary/trunk/motorway
- Build OSM graph → add virtual sink node connected to all exits
- Dijkstra from each origin centroid to sink
- Accumulate path counts and HU weights per edge
- Segments with connectivity_score ≥ 1 → is_evacuation_route = True

### Agent 3: Objective Standards Engine

**Inputs:** project location, units, roads_gdf (with capacity columns), fhsz_gdf, config
**Outputs:** Project object with determination + full audit dict

**Standards:**

| Standard | Check | Method | Gate for tier? |
|---|---|---|---|
| Std 1: Project Size | units ≥ unit_threshold | integer comparison | Gates all standards (universal scale gate) |
| Std 2: Evac Routes | Evac routes within 0.5 mi of project | buffer + intersect | Informs Std 4 |
| Std 3: FHSZ Modifier | Is project in FHSZ Zone 2/3? | GIS point-in-polygon | Activates surge multiplier in Std 4 |
| Std 4: Evac Capacity | Project causes route to cross v/c 0.95? | HCM marginal causation | Gates DISCRETIONARY |
| Std 5: Local Capacity | Project causes local street to cross v/c 0.95? | HCM v/c, no surge | Supplemental — escalates to DISCRETIONARY |

**Determination logic (100% algorithmic):**
```
IF size_met AND capacity_exceeded (Std 4 or Std 5):
    tier = DISCRETIONARY
    # Std 3 (FHSZ) activates surge multiplier in Std 4 — not an independent gate

ELIF size_met:
    tier = CONDITIONAL MINISTERIAL   # universal — all cities, not FHSZ-gated

ELSE:
    tier = MINISTERIAL
```

**Audit trail must record:**
- All six check results with input values
- Per-route: baseline demand, vehicles added, proposed demand, proposed v/c, flagged?
- Tier triggered and legal basis citation
- All parameter values used (thresholds, rates, factors)

### Agent 4: Impact Fee Nexus Calculator (AB 1600)

Unchanged from v1.0 spec. Operates on routes where:
- `baseline_vc >= vc_threshold` OR cumulative proposed v/c exceeds threshold

### Agent 5: What-If Analysis Engine

Unchanged from v1.0 spec. Add:
- SB 79 transit proximity check: flag if project within 0.5 mi of Tier 1/2 transit stop
- Minimum/maximum demand scenario toggle (daytime vs. nighttime)

### Agent 6: Visualization

- Map 1: FHSZ zones + evacuation route network (all routes, colored by LOS)
- Map 2: Congestion heatmap (citywide, matching KLD Figure 24/25 style)
- Map 3: Project impact — before/after on serving routes
- Legend: three-tier determination colors (DISCRETIONARY=red, CONDITIONAL=orange, MINISTERIAL=green)
- Route line weight = connectivity_score (thicker = more households depend on route)

### Agent 7: Report Generation

Unchanged from v1.0 spec.

---

## City Configuration (`config/cities/{city_slug}.yaml`)

Every city must have a config file with these keys:

```yaml
# Identity
city_name: "Berkeley"
state: "CA"
osmnx_place: "Berkeley, California, USA"

# Census geography
state_fips: "06"
county_fips: "001"

# Projection (UTM zone for the city)
analysis_crs: "EPSG:26910"   # UTM Zone 10N for Northern California

# Demand parameters (override global defaults if city-specific data available)
vehicles_per_unit: 2.5       # Census ACS B25044 city average; override if known
resident_mobilization: 0.57  # Peak hour fraction; from Berkeley study; citywide default
employee_mobilization: 1.00  # 100% in first hour (daytime max scenario)
employee_mobilization_night: 0.10  # nighttime/weekend fraction
employment_rate: 0.62        # Used to estimate employees if LEHD unavailable
commute_in_fraction: 0.45    # Fraction of city jobs filled by in-commuters (if LEHD unavailable)

# Universities / major institutions (student vehicle demand)
universities:
  - name: "UC Berkeley"
    enrollment: 45057         # Total enrollment 2019-2020
    student_vehicle_rate: 0.08  # Fraction of students with cars (campus-specific)
    location_lat: 37.8724
    location_lon: -122.2595

# Data quality flags
lehd_available: false         # Set true if LEHD OnTheMap data was downloaded
aadt_available: false         # Set true if Caltrans AADT counts were matched

# Determination thresholds (override global defaults if city adopts different values)
# vc_threshold: 0.80          # Uncomment to override
# unit_threshold: 50          # Uncomment to override
```

---

## Global Parameters (`config/parameters.yaml`)

```yaml
# HCM 2022 Capacity
hcm_capacity:
  freeway: 2250
  multilane: 1900
  two_lane_by_speed:
    20: 900
    25: 1125
    30: 1350
    35: 1575
    40: 1700

# LOS thresholds (v/c)
los_thresholds:
  A: 0.10
  B: 0.20
  C: 0.40
  D: 0.60
  E: 0.95

# Determination thresholds (global defaults; overridable per city)
vc_threshold: 0.95    # Exact HCM 2022 LOS E/F boundary (not the KLD study's 0.80)
unit_threshold: 50

determination_tiers:
  discretionary:
    unit_threshold: 50
    vc_threshold: 0.95    # Marginal causation: project causes baseline_vc < 0.95 → proposed_vc ≥ 0.95
    legal_basis: "AB 747 (Gov. Code §65302.15) and HCM 2022 v/c capacity threshold — project causes a serving evacuation route to cross the LOS E/F boundary"
  conditional_ministerial:
    unit_threshold: 50
    legal_basis: "General Plan Safety Element consistency and AB 1600 nexus"
  ministerial:
    legal_basis: "Project below applicable significance threshold"

# Demand model
demand:
  buffer_radius_miles: 0.25        # Quarter-mile buffer (matches KLD methodology)
  resident_mobilization: 0.57      # Peak hour fraction from Berkeley mobilization study
  employee_mobilization_day: 1.00  # 100% in first hour (daytime maximum)
  employee_mobilization_night: 0.10
  vehicles_per_unit: 2.5           # Default; overridden by city config or ACS B25044
  employee_vehicle_occupancy: 1.0  # 1 employee per vehicle
  scenario: "maximum"              # "maximum" | "minimum"

# Evacuation route identification
evacuation:
  origin: "all_block_groups"       # Use ALL block group centroids (not FHSZ-only)
  exit_road_classes:               # OSM highway types that count as city exits
    - motorway
    - trunk
    - primary
    - secondary
  serving_route_radius_miles: 0.5  # Standard 3 buffer for project evaluation

# Census
census:
  acs_year: 2022
  tables:
    housing_units: "B25001_001E"
    vehicles: "B25044_001E"
    population: "B01003_001E"
  api_base: "https://api.census.gov/data"

# Caching
cache_ttl_days: 90
```

---

## Key Parameters Abstracted from Berkeley AB 747 Study

The following parameters are directly sourced from or validated against the KLD Engineering study and should be treated as the canonical reference for California cities until a city-specific study is available:

| Parameter | Value | Source in KLD study |
|---|---|---|
| Resident mobilization (peak hour) | **0.57** | Figure 12 — 57% of residents mobilize between 45–105 min post-order |
| Employee mobilization (daytime) | **1.00** | "100% for employees and commuting students in first hour" |
| Employee mobilization (nighttime) | **0.10** | "only about 10% of employees may be present on weekends and evening" |
| Employee vehicle occupancy | **1.0** | "1 employee per vehicle" assumption |
| Demand buffer radius | **0.25 miles** | "resident and employee datapoints within a quarter mile buffer" |
| Freeway capacity | **2,250 pc/h/lane** | Table 2 / HCM Chapter 12 (conservative) |
| Multilane capacity | **1,900 pc/h/lane** | "conservative estimate of 1,900 pc/h" |
| V/C threshold | **0.95** | Exact HCM 2022 LOS E/F boundary — more permissive of infill than the KLD study's 0.80 mid-LOS-E value, and more defensible against HCD challenge as a categorical prohibition |
| Network origin type | **Block group centroids** | "centroid of each Census block group" |
| Route selection | **All shortest paths to all exits** | "shortest path from each centroid to each exit" |
| Connectivity score | **O-D path count per segment** | "total number of O-D paths that traversed each segment" |

Cities that have their own AB 747 study should override these with study-specific values in their city YAML.

---

## Validation Against Berkeley Study

After implementing the corrected demand model, system outputs should approximate the KLD Berkeley results:

| Metric | KLD study result | System target |
|---|---|---|
| Route capacity on major arterials | 3,800–9,500 vph | Match (same HCM table) |
| Route capacity on 2-lane hills roads | 900–1,125 vph | Match |
| Baseline congestion on major arterials | LOS E–F (max demand) | System should show LOS E–F |
| Most viable routes | University Ave, Adeline, Shattuck, Sacramento, San Pablo | Highest connectivity scores |
| Hills roads (Park Hills, Overlook) | High safety risk, low connectivity | Lower connectivity vs. arterials |

The key validation test: with the quarter-mile buffer demand model applied to all city residents, **major Berkeley arterials should show v/c ≥ 0.60 (LOS E) at maximum demand**, not v/c = 0.028 as the prior FHSZ-only model produced.

---

## Implementation Phases

### Phase 1 (COMPLETE): MVP — Agents 1–3, FHSZ-only demand

Binary ministerial/discretionary, FHSZ-path-only demand. Verified end-to-end on Berkeley.

### Phase 2a (COMPLETE): Three-tier determination + census HU download

Three-tier logic (DISCRETIONARY / CONDITIONAL / MINISTERIAL). Census ACS B25001 housing units downloaded per city. Block group weighted origins (FHSZ HUs only — now superseded by Phase 2b scope).

### Phase 2b (NEXT): Corrected citywide demand model

**Scope:**

1. **`agents/data_acquisition.py`**: Add `fetch_employee_demand()` using Census LEHD OnTheMap API or ACS B08301 fallback. Add `fetch_student_demand()` reading university config. Store `employee_count` and `student_count` columns in block_groups.geojson.

2. **`agents/capacity_analysis.py`**: Replace FHSZ-path network approach with quarter-mile buffer spatial join. `_apply_buffer_demand()` replaces `_identify_evacuation_routes()` demand step. Route identification still uses Dijkstra but from ALL block group centroids, not just FHSZ ones. Add `resident_demand_vph`, `employee_demand_vph`, `student_demand_vph`, `demand_scenario` columns.

3. **`agents/objective_standards.py`**: Remove fire zone modifier as gate for DISCRETIONARY. New logic: `disc_size_met AND capacity_exceeded` → DISCRETIONARY. Fire zone modifier recorded in audit trail as severity modifier; drives condition language but not tier gate.

4. **`config/parameters.yaml`**: Add `demand` block with buffer radius, employee mobilization rates, scenario parameter.

5. **`config/cities/*.yaml`**: Add employee demand parameters (employment_rate, commute_in_fraction, universities list).

6. **Validation test**: Berkeley maximum demand should produce LOS E–F on Shattuck, University, Telegraph, Sacramento — matching the KLD study's Figure 24 results.

### Phase 3 (FUTURE): Agents 4–7 + web UI

Impact fee nexus (AB 1600), Flask what-if web app, Word/PDF reports, SB 79 transit proximity flag.

---

## File Structure

```
agents/
  data_acquisition.py   # Agent 1: FHSZ, roads, boundary, Census ACS, LEHD employees
  capacity_analysis.py  # Agent 2: HCM capacity, buffer demand, all-origin route ID
  objective_standards.py # Agent 3: three-tier determination (capacity gates DISC, not fire zone)
  visualization.py      # Agent 6: Folium maps with LOS coloring

models/
  road_network.py       # RoadSegment dataclass
  project.py            # Project dataclass (determination_tier field)

config/
  parameters.yaml       # Global HCM, LOS, demand, census parameters
  cities/
    berkeley.yaml       # Berkeley-specific config (state_fips, universities, etc.)
    [city_slug].yaml    # Pattern for any additional city

data/{city}/            # Cached source data (git-ignored, 90-day TTL)
  fhsz.geojson
  roads.gpkg
  boundary.geojson
  block_groups.geojson  # HUs + employees + students by block group
  metadata.yaml         # Audit trail: sources, URLs, download dates

output/{city}/          # Results (git-ignored)
  routes.csv            # Evacuation routes with v/c, LOS, demand components
  determination_{id}.txt
  map_{id}.html
```

---

## Legal Notes

- All four standards are **100% algorithmic** — zero discretion allowed.
- The shift from "fire zone gates DISCRETIONARY" to "capacity impact gates DISCRETIONARY" is legally strengthened, not weakened: it aligns with the official city AB 747 study's finding that **all Berkeley roads are stressed** during citywide evacuation, and any large project adding vehicles to already-failing routes has a measurable, documentable impact.
- FHSZ severity modifier still has legal significance: it triggers fire-specific conditions, AB 747 fire safety review language, and potentially higher-tier mitigation requirements — it just no longer determines whether review is discretionary at all.
- Every determination letter must cite: AB 747 (§65302.15), city's own AB 747 study (if available), HCM 2022 capacity table, Census data vintage, and parameter values used.

# JOSH — Fire Evacuation Capacity Analysis System

**Version:** 3.2 (ΔT Standard — Constant Mobilization, NFPA 101)
**Date:** March 2026
**Authority:** California Government Code §65302(g)(4), §65302.15 (AB 747), §65589.5 (HAA), AB 1600, SB 79
**Reference Studies:**
- KLD Engineering, P.C., *Evacuation Route Safety, Capacity, and Viability Analysis — AB 747 Requirement*, City of Berkeley, March 7, 2024 (KLD TR-1381)
- Maranghides, A., et al. (2021). *A Case Study of the Camp Fire — Fire Progression Timeline.* NIST Technical Note 2135.
- Maranghides, A., et al. (2023). *A Case Study of the Camp Fire — NETTRA.* NIST Technical Note 2252.
- NFPA 101. *Life Safety Code.* National Fire Protection Association.
- Zhao, X., et al. (2022). *Estimating wildfire evacuation decision and departure timing using large-scale GPS data.* Transportation Research Part C. (retained for planning-level analysis; no longer the mobilization source)
- Wong, S.D., Broader, J.C., Shaheen, S.A. (2020). *Review of California wildfire evacuations from 2017 to 2019.* UC Institute of Transportation Studies. (planning reference only)
- Rohaert, A., et al. (2025). *The impact of wildfire smoke on traffic evacuation dynamics.* Safety Science 186:106812.
- Link, E.D. & Maranghides, A. (NIST). *Burnover events identified during the 2018 Camp Fire.*
- FHWA. *Guide for Highway Capacity and Operations Analysis of ATDM Strategies* — Appendices A and C (HCM weather and incident capacity adjustment factors).

---

## 1. Project Purpose

Open-source Python pipeline that analyzes fire evacuation route capacity for any California city to:

1. Enable **what-if analysis** for proposed developments (ministerial vs. discretionary under current General Plan)
2. Establish **objective development standards** adoptable in Safety Elements
3. Generate **impact fee nexus studies** (AB 1600 compliant)

This is a legally-focused system. All standards must be objective — no engineering judgment, no discretion at the project level.

---

## 2. Core Metric: ΔT (Marginal Evacuation Time)

### 2.1 The Single Question

**How many minutes does this project add to evacuation clearance time on the most constrained serving route?**

This is a life safety question — not a traffic efficiency question, not a CEQA environmental impact question. It is measured in the units that matter: time. Time is what determines whether people escape a wildfire, an earthquake, or a flood.

### 2.2 The Formula

```
ΔT = (project_vehicles / C_bottleneck) × 60 + T_egress

Where:
  project_vehicles = units × vehicles_per_unit × 0.90
  C_bottleneck     = min(effective_capacity_vph) along serving route
  T_egress         = building egress penalty (minutes, 0 for low-rise)
```

**Mobilization is 0.90 — constant for all projects, all zones (NFPA 101 design basis).**

FHSZ affects the road (through `hazard_degradation` on road capacity). It does not affect mobilization. Mobilization is a constant: 0.90, consistent with the NFPA 101 design basis for full building evacuation, adjusted for zero-vehicle households per Census B25044.

**Result:** A single number, in minutes, per serving route.

### 2.3 Determination Logic

```
IF ΔT > max_marginal_minutes(hazard_zone) AND units ≥ unit_threshold:
    tier = DISCRETIONARY

ELIF units ≥ unit_threshold:
    tier = CONDITIONAL MINISTERIAL

ELSE:
    tier = MINISTERIAL
```

One test. Every project. Every zone. No branching on baseline conditions. No marginal causation conditional.

**Note (v3.1):** `max_marginal_minutes` is no longer a static config value. It is derived at runtime as `safe_egress_window(hazard_zone) × max_project_share`. See §3.6 for derivation, sources, and legal significance of the non-round threshold values.

### 2.4 Why ΔT Replaces V/C Marginal Causation

The v2.0 spec used a marginal causation test:

```
# v2.0 (REPLACED):
flagged = (baseline_vc < 0.95) AND (proposed_vc >= 0.95)
```

This had a structural defect: any project in a zone where routes already exceeded v/c 0.95 was automatically exempt from capacity review, because the baseline precondition was never met. The most dangerous areas received the least scrutiny.

ΔT eliminates this defect. The test references only the project's own contribution — measured in time — against the road's physical capacity. The baseline state is irrelevant to the project-level determination. Whether a zone is already congested or empty, the project adds the same number of minutes. The standard applies uniformly.

### 2.5 Relationship Between ΔT and V/C

V/C is a special case of the time-based framework where mobilization is instantaneous, buildings have no egress delay, and the safe egress window is assumed to be exactly 60 minutes. ΔT generalizes V/C into the dimension that actually matters for life safety: minutes of additional clearance time.

V/C and LOS are retained in the system as informational outputs for KLD study validation and planning context. They are not used in the determination logic.

---

## 3. Parameter Sources and Legal Defensibility

Every parameter in the system traces to a published source. No parameter requires city-level policy adoption to justify its use.

### 3.1 Road Capacity — HCM 2022

Source: Highway Capacity Manual, 7th Edition (2022), Transportation Research Board, National Academies of Sciences, Engineering, and Medicine.

| Road Type | Per-lane capacity (pc/h) | HCM Reference |
|---|---|---|
| Freeway | 2,250 | Ch. 12, Exhibit 12-6 |
| Multilane highway / arterial | 1,900 | Ch. 12, Exhibit 12-7 |
| Two-lane ≤ 20 mph | 900 | Ch. 15 |
| Two-lane 25 mph | 1,125 | Ch. 15 |
| Two-lane 30 mph | 1,350 | Ch. 15 |
| Two-lane 35 mph | 1,575 | Ch. 15 |
| Two-lane ≥ 40 mph | 1,700 | Ch. 15 |

Lane counts: from OSM data. Estimated where missing (flagged in output).

**Legal status:** HCM is THE national standard for highway capacity analysis. It has been published by the Transportation Research Board (a unit of the National Academies) since 1950 and is relied upon by every state DOT, FHWA, and traffic engineering practice in the country. It qualifies as an "objective, identified written public health or safety standard" under Gov. Code §65589.5(j)(2) without question.

### 3.2 Mobilization Rate — 0.90 (Constant)

Source: NFPA 101 (Life Safety Code) design basis.

NFPA 101 designs building exits for 100% occupant evacuation. Fire marshals do not size exits for partial evacuation — they size exits for everyone. This standard applies the same principle to the roads serving those buildings.

The 0.90 factor accounts for approximately 10% of households with zero vehicles, as measured by Census ACS Table B25044. Cities may override this with their city-specific zero-vehicle rate from B25044.

**The mobilization rate does not vary by hazard zone. FHSZ affects the road (through the hazard degradation factor in §3.3). It does not affect the people. The project's residents are the project's residents regardless of where the project is located.**

**Legal status:** NFPA 101 is the national fire protection standard adopted by reference in every state building code. Designing building exits for 100% occupant load is the codified standard. Extending this principle to the road is an application of fire code design logic, not a discretionary policy choice. A developer's expert would need to argue that roads serving buildings should be sized for fewer occupants than the buildings themselves — a position directly contradicted by NFPA 101.

**Relationship to GPS behavioral studies:** Zhao et al. (2022) and Wong et al. (2020) document observed compliance rates (~47% during actual wildfires). These studies are valid for planning-level analysis but are the wrong source for a project-level design standard. Observed rates measure behavioral patterns during past events — not a design standard for emergency infrastructure. Fire marshals do not size stairwells for 47% of occupants. Roads should not be sized that way either. These studies remain cited for planning context but are no longer the source of record for mobilization rate in the project-level determination.

### 3.3 Hazard-Aware Capacity Degradation — HCM Composite Factors

**This is the only place the FHSZ designation affects the project-level determination.** It adjusts the road's capacity. It does not adjust the project's vehicle generation (which is constant at `units × 2.5 × 0.90`).

A road segment physically located within a fire hazard zone will not operate at full HCM capacity during the wildfire that triggers the evacuation. The degradation factors are composites of published HCM capacity adjustment factors for conditions that are documented consequences of Cal Fire FHSZ designations.

| Hazard Zone | Factor | HCM Derivation |
|---|---|---|
| VHFHSZ | 0.35 | Visibility <0.25 mi (~11% reduction, HCM Exhibit 10-15) × one lane blocked by counterflow EVs (65% reduction on 2-lane, HCM Exhibit 10-17). Composite: 0.89 × 0.35 = 0.31, rounded up to 0.35 |
| High FHSZ | 0.50 | Moderate smoke visibility (~10%) × shoulder incident (~5%). Composite rounded down to 0.50 to account for compound effects |
| Moderate FHSZ | 0.75 | Light smoke possible. HCM visibility 0.5-1 mi: ~10% |
| Non-FHSZ | 1.00 | No fire-related degradation |

**Effective capacity per segment:**

```
effective_capacity_vph = hcm_capacity_vph × lanes × hazard_degradation(fhsz_zone)
```

**Why these factors are conservative (in the developer's favor):** During the 2018 Camp Fire, three of five evacuation roads were closed entirely (degradation factor = 0.0). The NIST case study documented 23 life-threatening entrapment and burnover events, 12 on primary egress arteries, with 300-500 civilians trapped. In five cases, evacuating traffic was completely stopped by gridlock or obstructions before the fire arrived. A 0.35 factor for VHFHSZ assumes the road continues to function at more than one-third capacity during an active wildfire — an assumption that observed conditions demonstrate is generous.

**The HCM framework:** The HCM provides capacity adjustments for weather conditions (Chapter 11, Exhibit 10-15) and incidents (Exhibit 10-17). These are the same adjustment mechanisms used in every traffic impact study in the country. Applying them to wildfire conditions along FHSZ-designated road segments is a direct extension of the published methodology — not an invention.

**Cal Fire FHSZ designations:** Made under Gov. Code §51175-51189 based on objective criteria (fuel loading, terrain slope, fire weather, fire history). They are state findings, not city opinions. Applying them as the basis for capacity degradation connects a state hazard determination to a national capacity standard. A developer challenging the degradation factor must challenge either Cal Fire's hazard designation or the HCM's capacity adjustment framework — both of which predate the application.

**Legal status:** Each component (HCM weather factors, HCM incident factors, Cal Fire FHSZ) is independently published and authoritative. The composition is arithmetic. The result is more favorable to the developer than observed real-world conditions.

### 3.4 Vehicles Per Household

Source: Census ACS 5-Year, Table B25044.

Default: 2.5. Overridden by city-specific ACS data when available.

### 3.5 Building Egress Penalty

Source: NFPA 101 (Life Safety Code), International Building Code (IBC).

```
IF project_stories >= threshold_stories:
    T_egress = min(stories × minutes_per_story, max_minutes)
ELSE:
    T_egress = 0
```

| Parameter | Default | Source |
|---|---|---|
| threshold_stories | 4 | NFPA 101 high-rise threshold (75 ft) |
| minutes_per_story | 1.5 | NFPA 101 stair descent + IBC garage egress |
| max_minutes | 12 | Cap at 8-story equivalent |

**Design levers available to the developer:** The egress penalty is a function of building design — number of stairwells, stair width, number of garage exits, driveway throat width. A developer can reduce T_egress by adding stairwells, widening stairs, providing multiple garage exits on different street frontages. The standard identifies a measurable constraint that the developer controls. This is critical for HAA compliance — the standard enables mitigation, not just denial.

### 3.6 ΔT Thresholds — Derived from Safe Egress Windows

The ΔT thresholds are not independent policy values. They are derived from two inputs:

**Safe egress windows by hazard zone** — the time available from first warning to when the hazard makes the area lethal or evacuation routes impassable:

| Zone | Window | Source |
|---|---|---|
| VHFHSZ | 45 min | NIST TN 2135: Camp Fire spot fires to fire front = 40 min + 5 min for modern WEA |
| High FHSZ | 90 min | Fire spread 1-2 mph vs 3-5 mph VHFHSZ; ~2× window |
| Moderate FHSZ | 120 min | Lower intensity, greater distance from ignition |
| Non-FHSZ | 120 min | Standard FEMA emergency planning window |

**Maximum project share** — the maximum fraction of the safe egress window any single project may consume: **5%**

This produces the thresholds by arithmetic:

| Zone | Window | × Share | = Threshold |
|---|---|---|---|
| VHFHSZ | 45 min | × 5% | = 2.25 min |
| High FHSZ | 90 min | × 5% | = 4.50 min |
| Moderate FHSZ | 120 min | × 5% | = 6.00 min |
| Non-FHSZ | 120 min | × 5% | = 6.00 min |

The 5% value is the single policy parameter the city adopts. It is justified as:
(a) the standard engineering significance threshold, and (b) structurally permissive — at 5%, a road can absorb approximately 20 projects before new development alone exhausts the safe window.

Cities override the safe egress windows in their city YAML if they have city-specific fire behavior data. The system computes thresholds at runtime from `safe_egress_window × max_project_share`.

**Non-round numbers are a feature:** The 2.25-minute and 4.50-minute thresholds signal "calculated" rather than "chosen." A developer challenging the threshold must challenge the NIST source data or the 5% engineering significance standard — not a policy choice by staff.

**Justification without Safety Element adoption:** The ΔT number itself constitutes substantial evidence of a "specific adverse impact" under §65589.5(j)(1). The thresholds structure ministerial processing but are not strictly necessary for the legal finding. "This project adds 23 minutes to evacuation clearance in a VHFHSZ zone where residents have 45 minutes to escape" is evidence regardless of whether a threshold has been formally adopted.

### 3.7 Unit Threshold

Default: **15 units**. Legally defensible as an administrative proportionality threshold — below 15 units, the ΔT contribution on most road types is under 1 minute (de minimis). Cities can adjust.

This is NOT a safety threshold. A 14-unit project in a failing zone is not categorically safe. It is an administrative threshold: below 15 units, the project's evacuation impact is small enough that ministerial processing is proportionate to the risk. This distinction must be explicit in the determination letter.

---

## 4. Data Sources

| Dataset | Source | Format | City-specific config |
|---|---|---|---|
| FHSZ Zones | CAL FIRE OSFM ArcGIS REST | GeoJSON | None (statewide) |
| Road Network | OpenStreetMap via OSMnx | GeoPackage | `osmnx_place` |
| City Boundary | U.S. Census TIGER | GeoJSON | `state_fips`, `county_fips` |
| Census Housing Units | Census ACS 5-Year B25001 | JSON | `state_fips`, `county_fips` |
| Census Vehicles/HU | Census ACS 5-Year B25044 | JSON | same |
| Census Population | Census ACS 5-Year B01003 | JSON | same |
| Employee Demand | Census LEHD or ACS B08301 | CSV/JSON | `lehd_available` flag |
| University Students | City config | YAML | `universities[]` |
| Block Group Geometry | Census TIGER/GENZ 500k | Shapefile | `state_fips` |
| Entitled Projects | JOSH internal ledger | JSON | Per city |

**Fallback hierarchy for employee demand:**
1. LEHD OnTheMap (in-commuter count by block group)
2. ACS B08301 (workers by transportation mode)
3. City-provided jobs data
4. Estimate: `city_population × employment_rate × commute_in_fraction`

---

## 5. System Architecture

### 5.1 Agent 1: Data Acquisition

**Inputs:** city name, state, city config YAML
**Outputs cached to `data/{city}/`:**

```
boundary.geojson         — city boundary polygon
fhsz.geojson            — FHSZ zones clipped to city bbox
roads.gpkg              — OSM road network
block_groups.geojson    — Census block groups with attributes:
                            housing_units_in_city
                            housing_units_in_fhsz
                            population
                            vehicles_per_hu
                            employee_count
                            student_count
                            fhsz_zone (VHFHSZ / High / Moderate / None)
metadata.yaml           — source URLs, download dates, vintage
```

**Key functions:**
- `acquire_data()` — orchestrates all downloads, caches with 90-day TTL
- `fetch_census_housing_units()` — ACS B25001 + B25044 + B01003
- `fetch_employee_demand()` — LEHD or fallback
- `fetch_census_block_groups()` — downloads, clips to city
- `_compute_fhsz_housing_units()` — area-weighted intersection

No changes from v2.0.

### 5.2 Agent 2: Capacity Analysis

**Inputs:** roads_gdf, fhsz_gdf, boundary_gdf, block_groups_gdf, config, city_config
**Outputs:** roads_gdf with added columns per segment, plus path-level bottleneck data

**New/modified columns per segment:**

```
capacity_vph             — raw HCM 2022 capacity (lanes × per-lane rate)
fhsz_zone               — FHSZ designation of this segment (spatial join)
hazard_degradation       — degradation factor for segment's FHSZ zone
effective_capacity_vph   — capacity_vph × hazard_degradation
road_type                — freeway / multilane / two_lane
lane_count               — from OSM or estimated
speed_limit              — from OSM or estimated
lane_count_estimated     — boolean flag
speed_estimated          — boolean flag
baseline_demand_vph      — catchment-based demand (Dijkstra routing)
vc_ratio                 — baseline_demand_vph / capacity_vph (informational)
los                      — A-F per HCM LOS table (informational)
is_evacuation_route      — boolean
connectivity_score       — count of O-D paths traversing this segment
```

**New: path-level output (stored separately):**

```
path_id                  — unique identifier (origin_bg → exit)
origin_block_group       — Census block group GEOID
exit_segment_id          — road segment at city boundary
bottleneck_segment_id    — segment with min(effective_capacity_vph) on path
bottleneck_capacity_vph  — the min effective capacity along this path
path_demand_vehicles     — total vehicles routed through this path's bottleneck
path_clearance_minutes   — path_demand_vehicles / bottleneck_capacity_vph × 60
```

**Pipeline (in order):**

1. `_apply_hcm_capacity()` — raw HCM capacity by road type and lanes
2. `_apply_hazard_degradation()` — **NEW**: spatial join road segments to FHSZ zones; multiply capacity by degradation factor to get effective_capacity_vph
3. `_identify_evacuation_routes()` — Dijkstra from ALL block group centroids to all exits. **MODIFIED**: during path traversal, record `bottleneck_segment_id` and `bottleneck_capacity_vph = min(effective_capacity_vph)` per path
4. `_apply_catchment_demand()` — assign demand to segments based on which housing units route through them (Dijkstra catchment model, not quarter-mile buffer)
5. `_compute_vc_los()` — v/c ratio and LOS assignment (informational, not used in determination)

**`_apply_hazard_degradation()` detail:**

```python
hazard_factors = config['hazard_degradation']['factors']
# Spatial join: for each road segment, find FHSZ zone it intersects
roads_proj['fhsz_zone'] = spatial_join(roads_proj, fhsz_gdf)
roads_proj['hazard_degradation'] = roads_proj['fhsz_zone'].map(hazard_factors).fillna(1.0)
roads_proj['effective_capacity_vph'] = roads_proj['capacity_vph'] * roads_proj['hazard_degradation']
```

**Bottleneck tracking during Dijkstra (modification to existing route identification):**

```python
# During path traversal from origin to exit:
for path in dijkstra_paths:
    segments = get_path_segments(path)
    bottleneck_idx = segments['effective_capacity_vph'].idxmin()
    path_record = {
        'path_id': f"{origin_bg}_{exit_id}",
        'bottleneck_segment_id': bottleneck_idx,
        'bottleneck_capacity_vph': segments.loc[bottleneck_idx, 'effective_capacity_vph'],
    }
```

This is computationally trivial — one `min()` reduction per path during a traversal that already occurs.

### 5.3 Agent 3: Objective Standards Engine

**Inputs:** project location, units, stories, roads_gdf (with capacity columns), path data, fhsz_gdf, entitled_projects_ledger, config
**Outputs:** Project object with determination + full audit dict

**Standards:**

| Standard | Check | Method | Role |
|---|---|---|---|
| Std 1: Project Size | units ≥ unit_threshold | Integer comparison | Gates all standards |
| Std 2: Serving Routes | Evacuation routes within buffer of project | Buffer + intersect | Identifies routes for Std 4 |
| Std 3: FHSZ Zone | What FHSZ zone is the project in? | Point-in-polygon | Sets road capacity degradation + ΔT threshold (NOT mobilization) |
| Std 4: ΔT Capacity | Does project ΔT exceed threshold on any serving route? | ΔT computation | Gates DISCRETIONARY |
| Std 5: SB 79 Flag | Is project within 0.5 mi of Tier 1/2 transit? | Buffer + intersect | Informational flag |

**Determination logic (100% algorithmic):**

```python
def determine(project, serving_routes, fhsz_gdf, entitled_ledger, config):
    # ── INPUTS ──
    hazard_zone = get_fhsz_zone(project.location, fhsz_gdf)
    mobilization = config.get('mobilization_rate', 0.90)  # NFPA 101 design basis, constant
    vehicles_per_unit = config['vehicles_per_unit']
    # threshold derived at runtime (not a static config value)
    safe_window = config['safe_egress_window'][hazard_zone]
    max_project_share = config['max_project_share']
    max_marginal = safe_window * max_project_share
    unit_threshold = config['unit_threshold']  # default: 15

    # ── COMPUTE PROJECT VEHICLES ──
    project_vehicles = project.units * vehicles_per_unit * mobilization

    # ── COMPUTE EGRESS PENALTY ──
    egress_minutes = 0
    if project.stories >= config['egress_penalty']['threshold_stories']:
        egress_minutes = min(
            project.stories * config['egress_penalty']['minutes_per_story'],
            config['egress_penalty']['max_minutes']
        )

    # ── TEST EACH SERVING ROUTE ──
    capacity_exceeded = False
    route_results = []

    for route in serving_routes:
        # Include entitled-but-unbuilt projects in baseline
        entitled_vehicles = get_entitled_demand(route, entitled_ledger, config)
        adjusted_bottleneck = route.bottleneck_capacity_vph  # road capacity is fixed

        delta_t = (project_vehicles / route.bottleneck_capacity_vph) * 60 + egress_minutes

        flagged = delta_t > max_marginal

        route_results.append({
            'route_id': route.path_id,
            'bottleneck_segment': route.bottleneck_segment_id,
            'bottleneck_capacity_vph': route.bottleneck_capacity_vph,
            'project_vehicles': project_vehicles,
            'egress_minutes': egress_minutes,
            'delta_t_minutes': delta_t,
            'safe_egress_window_minutes': safe_window,
            'max_project_share': max_project_share,
            'threshold_minutes': max_marginal,  # now derived, was static
            'hazard_zone': hazard_zone,
            'flagged': flagged,
        })

        if flagged:
            capacity_exceeded = True

    # ── DETERMINE TIER ──
    if capacity_exceeded and project.units >= unit_threshold:
        tier = 'DISCRETIONARY'
    elif project.units >= unit_threshold:
        tier = 'CONDITIONAL_MINISTERIAL'
    else:
        tier = 'MINISTERIAL'

    return {
        'tier': tier,
        'project_units': project.units,
        'project_stories': project.stories,
        'hazard_zone': hazard_zone,
        'mobilization_rate': mobilization,
        'route_results': route_results,
        'capacity_exceeded': capacity_exceeded,
        'legal_basis': get_legal_basis(tier, hazard_zone),
    }
```

### 5.4 Entitled Projects Ledger

**New component.** JOSH maintains a per-city ledger of projects that have received entitlement but are not yet reflected in Census baseline data.

```
data/{city}/entitled_projects.json

[
  {
    "project_id": "ENT-2025-042",
    "location": {"lat": 33.0392, "lon": -117.2919},
    "units": 45,
    "stories": 3,
    "entitled_date": "2025-06-15",
    "status": "entitled",  // entitled | under_construction | completed | withdrawn
    "serving_routes": ["path_47_exit_12", "path_47_exit_15"],
    "delta_t_at_entitlement": 5.7,
    "notes": "Clark Avenue project"
  }
]
```

Entitled projects are included in planning-level cumulative analysis but do NOT alter the project-level ΔT computation. The ΔT test is purely a function of the project's own vehicles and the road's physical capacity. The ledger provides visibility into cumulative zone loading for the planner's contextual awareness and for periodic Safety Element review.

**Cumulative display (informational, not used in determination):**

```
Zone cumulative ΔT from entitled projects: 14.2 minutes
Zone baseline clearance (Census): 79.3 minutes
Zone clearance with entitled projects: 93.5 minutes
This project would add: 5.7 minutes → total 99.2 minutes
```

### 5.5 Agent 4: Impact Fee Nexus Calculator (AB 1600)

The ΔT metric provides a direct nexus for impact fees. The project's time contribution quantifies its proportional share of the infrastructure cost needed to maintain evacuation capacity.

```
project_share = project_delta_t / total_zone_clearance_time
fee = project_share × estimated_infrastructure_cost
```

Infrastructure cost estimates come from the city's CIP or from standard road improvement cost databases.

### 5.6 Agent 5: What-If Analysis Engine

**Inputs:** project location (lat/lon), unit count, stories, city
**Outputs:** determination + contextual analysis

**Output format:**

```
═══════════════════════════════════════════════════════
JOSH Evacuation Capacity Analysis
City: Encinitas, CA | Date: 2026-03-08
═══════════════════════════════════════════════════════

PROJECT
  Location:    33.0392, -117.2919 (Clark Avenue)
  Units:       45
  Stories:     3
  Hazard Zone: VHFHSZ (Cal Fire designation)

PARAMETERS APPLIED
  Mobilization rate:   0.90 (NFPA 101 design basis, constant)
  Vehicles/unit:       2.5 (Census ACS B25044)
  Egress penalty:      0 min (below 4-story threshold)
  Safe egress window:  45 min (VHFHSZ, per NIST TN 2135)
  Max project share:   5%
  ΔT threshold:        2.25 min (45 × 5%)
  Project vehicles:    101.3

SERVING ROUTE ANALYSIS
  Route 1: Quail Gardens Dr → Leucadia Blvd exit
    Bottleneck:        Quail Gardens seg 4472 (2-lane, 30 mph)
    Raw capacity:      1,350 vph
    FHSZ degradation:  ×0.35 (VHFHSZ segment)
    Effective capacity: 472 vph
    Project ΔT:        12.9 min + 0 egress = 12.9 min
    Threshold:         2.25 min (45 min window × 5%)
    ▶ FLAGGED — exceeds threshold by 10.65 min

  Route 2: Encinitas Blvd → I-5 exit
    Bottleneck:        Encinitas Blvd seg 2201 (4-lane, 35 mph)
    Raw capacity:      6,300 vph
    FHSZ degradation:  ×0.50 (High FHSZ segment)
    Effective capacity: 3,150 vph
    Project ΔT:        1.9 min + 0 egress = 1.9 min
    Threshold:         2.25 min (45 min window × 5%)
    ○ NOT FLAGGED

ZONE CONTEXT (informational)
  Baseline demand on Route 1:  892 vehicles (Census)
  Entitled projects on Route 1: 3 projects, 87 units, cumulative ΔT 11.1 min
  Baseline clearance:          113.4 min
  With entitled + this project: 135.2 min
  Zone ECR (informational):    estimated >1.0

DETERMINATION
  ▶ DISCRETIONARY
  Capacity exceeded: Route 1 (ΔT 10.7 min > 3.0 min threshold)

LEGAL BASIS
  Gov. Code §65589.5(j)(1)(A): Specific adverse impact on public safety.
  Based on: HCM 2022 capacity standards, Cal Fire FHSZ designation
  (Gov. Code §51175), AB 747 evacuation methodology (Gov. Code §65302.15),
  empirical mobilization rates (Zhao et al. 2022, Transp. Research Part C).

MITIGATION PATHWAYS
  To bring ΔT below 3.0 min on Route 1, developer could:
  - Reduce to ~12 units (ΔT = 2.9 min)
  - Provide second access road to Route 2 (shifts bottleneck)
  - Fund widening of Quail Gardens Dr bottleneck segment
  - Provide emergency-only secondary egress

═══════════════════════════════════════════════════════
```

**SB 79 scenario output (non-fire zone):**

```
PROJECT
  Location:    33.0521, -117.2614 (transit-adjacent)
  Units:       200
  Stories:     7
  Hazard Zone: Non-FHSZ
  SB 79 Flag:  Yes (within 0.5 mi of Coaster station)

PARAMETERS APPLIED
  Mobilization rate:   0.90 (NFPA 101 design basis, constant)
  Vehicles/unit:       2.5
  Egress penalty:      10.5 min (7 stories × 1.5 min/story)
  Safe egress window:  120 min (Non-FHSZ, FEMA standard)
  Max project share:   5%
  ΔT threshold:        6.0 min (120 × 5%)
  Project vehicles:    450.0

SERVING ROUTE ANALYSIS
  Route 1: Vulcan Ave → Leucadia Blvd
    Bottleneck:        Vulcan Ave seg 1102 (2-lane, 25 mph)
    Effective capacity: 1,125 vph (no degradation)
    Project ΔT:        24.0 min + 10.5 egress = 34.5 min
    Threshold:         6.0 min (120 min window × 5%)
    ▶ FLAGGED

DETERMINATION
  ▶ DISCRETIONARY
  Capacity exceeded: Route 1 (ΔT 34.5 min > 6.0 min threshold)

MITIGATION PATHWAYS
  - Add stairwells to reduce egress from 10.5 to ~5 min
  - Add second garage exit to different street
  - Reduce units to ~20 (ΔT ≈ 6.0 min with current design)
  - Redesign garage with dual exits on Vulcan + Coast Hwy
```

### 5.7 Agent 6: Visualization

- Map 1: FHSZ zones + evacuation route network colored by effective capacity
- Map 2: Bottleneck heatmap (thicker lines = lower effective capacity relative to demand)
- Map 3: Project impact — ΔT per serving route, with bottleneck segment highlighted
- Map 4: Entitled projects overlay — cumulative zone loading
- Legend: three-tier determination colors (DISCRETIONARY=red, CONDITIONAL=orange, MINISTERIAL=green)
- Route line weight = connectivity_score

### 5.8 Agent 7: Report Generation

Determination letters must cite:
- AB 747 (Gov. Code §65302.15)
- HCM 2022 edition and specific exhibits used
- Cal Fire FHSZ designation and Gov. Code §51175
- Census data vintage (ACS year)
- Mobilization rate source (NFPA 101 design basis, 0.90 constant; Census ACS B25044 zero-vehicle adjustment)
- Degradation factor derivation (HCM exhibits composited)
- All parameter values used
- Complete ΔT computation showing inputs and result
- Mitigation pathways available to the developer

---

## 6. Configuration

### 6.1 Global Parameters (`config/parameters.yaml`)

```yaml
# ═══════════════════════════════════════════════
# JOSH v3.4 — Global Parameters
# ═══════════════════════════════════════════════

# HCM 2022 Capacity (per lane, pc/h)
hcm_capacity:
  freeway: 2250
  multilane: 1900
  two_lane_by_speed:
    20: 900
    25: 1125
    30: 1350
    35: 1575
    40: 1700

# Mobilization rate — constant for all projects, all zones
# Source: NFPA 101 design basis (100% evacuation)
# Adjusted for ~10% zero-vehicle HHs (Census ACS B25044)
mobilization_rate: 0.90

# Hazard-aware road capacity degradation
# Source: HCM composite — visibility (Exhibit 10-15) + incident (Exhibit 10-17)
# Validated against: NIST Camp Fire burnover study (Link & Maranghides)
hazard_degradation:
  enabled: true
  factors:
    vhfhsz: 0.35
    high_fhsz: 0.50
    moderate_fhsz: 0.75
    non_fhsz: 1.00
  derivation: >
    VHFHSZ: visibility <0.25mi (0.89) × 1-lane blocked on 2-lane (0.35) = 0.31,
    rounded to 0.35 (conservative in developer's favor).
    High FHSZ: moderate smoke (0.90) × shoulder incident (0.95) = 0.855,
    rounded to 0.50 for compound effects.
    Moderate FHSZ: light smoke (0.90), rounded to 0.75.

# Safe egress windows by hazard zone (minutes)
# Source: NIST TN 2135 (Camp Fire timeline), TN 2252 (NETTRA), TN 2262 (ESCAPE)
safe_egress_window:
  vhfhsz: 45         # NIST Camp Fire: spot fires to fire front = 40 min
                      # + 5 min for modern WEA alert systems (not available in 2018)
  high_fhsz: 90      # Fire spread ~1-2 mph vs 3-5 mph VHFHSZ; ~2× window
  moderate_fhsz: 120  # Lower intensity, greater distance from typical ignition
  non_fhsz: 120      # General emergency planning window (FEMA standard)

# Maximum project share of safe egress window
# Single policy value — all zone thresholds derived from this × safe_egress_window
max_project_share: 0.05  # 5% — standard engineering significance threshold
                         # Derived thresholds: vhfhsz=2.25 min, high=4.50 min,
                         #                     moderate=6.00 min, non=6.00 min

# Project size threshold
unit_threshold: 15

# Vehicles per housing unit
vehicles_per_unit: 2.5    # Census ACS B25044 default; overridden per city

# Building egress penalty (NFPA 101 / IBC)
egress_penalty:
  threshold_stories: 4
  minutes_per_story: 1.5
  max_minutes: 12

# Demand model
demand:
  origin: "all_block_groups"
  model: "dijkstra_catchment"    # Changed from buffer to catchment
  scenario: "maximum"

# LOS thresholds (informational only — not used in determination)
los_thresholds:
  A: 0.10
  B: 0.20
  C: 0.40
  D: 0.60
  E: 0.95

# Evacuation route identification
evacuation:
  exit_road_classes:
    - motorway
    - trunk
    - primary
    - secondary
  serving_route_radius_miles: 0.5

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

### 6.2 City Configuration (`config/cities/{city_slug}.yaml`)

```yaml
# Identity
city_name: "Encinitas"
state: "CA"
osmnx_place: "Encinitas, California, USA"

# Census geography
state_fips: "06"
county_fips: "073"

# Projection
analysis_crs: "EPSG:26911"   # UTM Zone 11N for Southern California

# Overrides (city-specific data)
# vehicles_per_unit: 2.3     # Uncomment if city ACS differs from default
# unit_threshold: 15          # Uncomment to override

# Employee demand
employment_rate: 0.62
commute_in_fraction: 0.40
lehd_available: false

# Universities / major institutions
universities: []

# Data quality flags
aadt_available: false
```

---

## 7. Legal Framework

### 7.1 The Standard in One Sentence

No project may add more than [X] minutes to evacuation clearance time on any serving route, where [X] is set by the hazard severity of the project's location and all inputs are derived from published national standards and state hazard designations.

### 7.2 Statutory Authority

**Gov. Code §65302(g)(4):** Requires the Safety Element to identify "residential developments in any hazard area identified pursuant to Section 51178" (FHSZ zones) and to address evacuation route adequacy.

**Gov. Code §65302.15 (AB 747):** Requires Safety Elements to "identify residential developments in any hazard area that do not have at least two emergency evacuation routes." Establishes evacuation route analysis as a Safety Element obligation — not a CEQA obligation.

**Gov. Code §65589.5 (HAA):** Allows denial or conditioning of housing projects based on "a specific, adverse impact upon the public health or safety" that is "significant, quantifiable, direct, and unavoidable, based on objective, identified written public health or safety standards, policies, or conditions as they existed on the date the application was deemed complete."

**Gov. Code §51175-51189:** Establishes Cal Fire FHSZ designations as state findings based on objective fire behavior criteria.

### 7.3 Why ΔT Satisfies the HAA

The HAA's §65589.5(j)(2) requires that any safety-based denial or condition be supported by a finding that is "significant, quantifiable, direct, and unavoidable, based on objective, identified written public health or safety standards."

ΔT satisfies each element:

**Significant:** The project adds X minutes to evacuation clearance for Y households in a state-designated hazard zone. In a VHFHSZ zone where fires move at documented speeds, X additional minutes of clearance time translates directly to additional households unable to evacuate before the fire arrives.

**Quantifiable:** ΔT is a number, computed from public data, independently verifiable. Any engineer running the same inputs gets the same result.

**Direct:** The project's vehicles enter the road network. The road takes longer to clear. The causal chain is mechanical — vehicles ÷ capacity = time. There is no speculative or attenuated causation.

**Unavoidable:** Unless the project reduces units, modifies building design (reducing egress time), or improves road capacity, the time impact persists.

**Based on objective, identified written public health or safety standards:** HCM 2022 (published by TRB/National Academies, relied upon by every state DOT), Census ACS data (federal statistical agency), Cal Fire FHSZ designations (state law, Gov. Code §51175), NFPA 101/IBC (national fire and building codes), and peer-reviewed empirical evacuation research. All published. All predate any specific application.

### 7.4 Why This Is Not a CEQA Analysis

This distinction is load-bearing.

**CEQA asks:** Does this project cause a significant adverse environmental impact? Under CEQA's marginal causation framework, a developer can argue: "My 45 units add a small increment to an already-failing road — I didn't cause the failure."

**The Safety Element asks:** Is this area safe for additional human habitation under emergency conditions? This is not an incremental question. It is a condition-based finding about whether the infrastructure can support the proposed population.

ΔT is designed for the Safety Element framework, not the CEQA framework. It measures the project's contribution to evacuation time — a physical quantity — without requiring allocation of blame for existing conditions. The fire doesn't distinguish between the 400th car and the 401st. They all need to get through the bottleneck.

By operating in the Safety Element domain (Gov. Code §65302(g)) rather than the CEQA domain (Pub. Resources Code §21000 et seq.), the standard avoids the marginal causation trap that renders CEQA traffic analysis ineffective for evacuation capacity questions.

### 7.5 Anticipated Challenges and Defenses

**"The ΔT thresholds are arbitrary."**

Defense: The thresholds are not chosen — they are derived. Each threshold equals the safe egress window for the hazard zone (from the NIST Camp Fire case study) multiplied by 5% (the maximum project share). The 2.25-minute threshold for VHFHSZ is 5% of 45 minutes. The 45 minutes comes from NIST Technical Note 2135, which documented that spot fires reached Paradise 40 minutes before the fire front arrived. A developer arguing the threshold should be higher must argue either that fires are slower than the Camp Fire (contradicting NIST) or that a single project should consume more than 5% of the available escape time. The 5% figure is the standard engineering significance threshold and allows approximately 20 projects before new development alone exhausts the window — a permissive, not restrictive, standard.

The non-round threshold values (2.25 min, 4.50 min) are a legal feature, not a defect. They signal "calculated" rather than "chosen." A court reviewing 2.25 minutes sees the mathematical product of a NIST-documented safe window and a standard engineering threshold — not a policy number someone picked. To challenge the threshold, a developer must challenge one of those two inputs. Neither challenge is tenable.

Even without adopted thresholds: the ΔT number itself constitutes substantial evidence of a "specific adverse impact" under §65589.5(j)(1). A staff report documenting "this project adds 10.7 minutes to evacuation clearance on a single-access road serving 347 households in a VHFHSZ zone where residents have 45 minutes to escape" does not require a bright-line threshold to support a safety finding.

**"The degradation factors are speculative."**

Defense: Each factor is derived from published HCM capacity adjustment tables for visibility impairment and lane blockage — the same tables used in every traffic study in the country. The compound conditions (smoke + counterflow + debris) are documented consequences of Cal Fire's own FHSZ designation. The factors are conservative in the developer's favor: observed conditions during the Camp Fire showed complete road closure (factor = 0.0) on 60% of evacuation routes, not the 0.35 this standard assumes.

**"This is a disguised growth control that violates the HAA."**

Defense: The standard does not prohibit development. It identifies a measurable safety impact and quantifies mitigation pathways. A developer can reduce units, redesign building egress, provide secondary access, or fund road improvements. If the impact is mitigated below threshold, the project is approved. This is the HAA working as designed — the city identifies a specific impact, the developer mitigates it, housing gets built.

Furthermore, most urban infill sites — the development pattern the state favors — are on arterials with high capacity and low FHSZ exposure. Those projects show ΔT well under any threshold. The projects flagged are those in canyons, on ridgelines, at the end of single-access roads in fire zones — exactly where AB 747 directs cities to scrutinize evacuation capacity.

**"The 90% mobilization rate is too high — observed rates from wildfires are much lower."**

Defense: Observed rates from GPS studies (Zhao et al. 2022) show approximately 47% compliance during actual wildfires. But observed rates measure behavioral patterns during past events — they are not a design standard. NFPA 101 designs building exits for 100% occupant evacuation. Fire marshals do not size exits assuming half the people will stay. The 90% rate applies this same design principle to the road. The 10% reduction accounts for households with no vehicle (Census B25044). The standard designs for the emergency that requires evacuation, not for the average case.

**"My parcel is at the edge of the zone — the zone-level FHSZ designation unfairly penalizes me."**

Defense: FHSZ designations are made by Cal Fire under Gov. Code §51175 based on objective fire behavior criteria. They are state findings. A developer who believes their parcel is incorrectly designated can petition Cal Fire for reclassification. The city applies the designation as published. Furthermore, the ΔT test is sensitive to the specific bottleneck on the project's serving route, not to a zone average — a parcel near a high-capacity exit will show a lower ΔT than one at the end of a canyon road, even if both are in the same FHSZ zone.

**"The building egress penalty wasn't designed for area-wide evacuation."**

Defense: NFPA 101 provides the codified methodology for computing occupant egress time from buildings. The physical reality — how long it takes people to descend stairs and exit a garage — does not change because the triggering event is a wildfire rather than a building fire. The standard uses NFPA 101 for what it objectively measures (egress time), applied to its obvious implication for evacuation timing. The developer can reduce the penalty through building design — more stairwells, wider stairs, multiple garage exits. This gives the developer control over the constraint.

### 7.6 Record Requirements

Every determination must be supported by a record that includes:

1. Complete ΔT computation with all inputs and intermediate values
2. Source citation for each parameter (HCM exhibit, Census table, FHSZ map, journal article)
3. Map showing project location, serving routes, and bottleneck segments
4. Hazard zone designation with Cal Fire FHSZ reference
5. Entitled projects included in cumulative context display
6. Mitigation pathways identified for the developer
7. Parameter values used (mobilization rate, degradation factor, threshold)

This record enables independent verification and provides the "substantial evidence" basis for any legal challenge.

---

## 8. Validation

### 8.1 Berkeley Validation (KLD Cross-Check)

After implementing the corrected model, system outputs should approximate KLD Berkeley results:

| Metric | KLD study result | JOSH target |
|---|---|---|
| Route capacity on major arterials | 3,800-9,500 vph | Match (same HCM table) |
| Route capacity on 2-lane hills roads | 900-1,125 vph | Match |
| Baseline congestion on major arterials | LOS E-F (max demand) | LOS E-F (informational) |
| Most viable routes | University, Adeline, Shattuck, Sacramento, San Pablo | Highest connectivity scores |
| Hills roads | High safety risk, low connectivity | Lower connectivity, high ΔT |

### 8.2 Scenario Validation

The system must produce correct results for these test cases:

| Scenario | Vehicles | Road | ΔT | Threshold | Expected Result |
|---|---|---|---|---|---|
| 15 units, 4-lane arterial, non-FHSZ | 15×2.5×0.90=33.75 | 3,800 vph | 0.5 min | 6.0 min | CONDITIONAL MINISTERIAL |
| 45 units, 2-lane canyon, VHFHSZ (472 vph degraded) | 45×2.5×0.90=101.3 | 472 vph | 12.9 min | 2.25 min | DISCRETIONARY |
| 200-unit 7-story, 2-lane collector, non-FHSZ | 200×2.5×0.90=450 | 1,350 vph | 20.0+10.5=30.5 min | 6.0 min | DISCRETIONARY |
| 75 units, 5-story, non-FHSZ, 2-lane 20 mph (Berkeley hills) | 75×2.5×0.90=168.75 | 1,125 vph | 9.0+7.5=16.5 min | 6.0 min | **DISCRETIONARY** (regression test) |
| 50 units in zone where all routes already at LOS F | — | bottleneck_capacity_vph | computed | zone threshold | DISCRETIONARY (no baseline precondition) |

**Berkeley 75-unit regression test:** Under v3.1 (mobilization 0.25 for non-FHSZ), this project generated only 47 vehicles → ΔT 2.5 min → CONDITIONAL MINISTERIAL. But 75 units on a 2-lane 20 mph road in the Berkeley hills, at end of single-access corridor, cannot safely evacuate. Under v3.4 (mobilization 0.90), the project generates 168.75 vehicles → ΔT 16.5 min → DISCRETIONARY. This is the correct result.

The last scenario is the v2.0 regression test: ΔT references only the project's vehicles and the road's physical capacity. The baseline state (already at LOS F) is irrelevant. The project is evaluated.

---

## 9. Implementation Phases

### Phase 1 (COMPLETE): MVP — Agents 1-3, FHSZ-only demand

Binary ministerial/discretionary. Verified on Berkeley.

### Phase 2a (COMPLETE): Three-tier determination + Census HU download

Three-tier logic. Census ACS B25001 housing units.

### Phase 2b (COMPLETE): Corrected citywide demand model

Quarter-mile buffer demand. Citywide block group origins.

### Phase 3 (CURRENT): ΔT Standard Implementation

**Scope:**

1. `agents/capacity_analysis.py`: Add `_apply_hazard_degradation()` step. Modify `_identify_evacuation_routes()` to track bottleneck per path. Switch from buffer demand to Dijkstra catchment demand.

2. `agents/objective_standards.py`: Replace v/c marginal causation logic with ΔT computation. Add FHSZ-based mobilization rate lookup. Add egress penalty computation. Remove `baseline_vc < 0.95` precondition.

3. `config/parameters.yaml`: Add mobilization_rates, hazard_degradation, max_marginal_minutes, egress_penalty blocks.

4. `models/project.py`: Add `stories` field. Add `delta_t_minutes` to route results.

5. `data/{city}/entitled_projects.json`: New file. JOSH ledger for entitled-but-unbuilt projects.

6. `agents/visualization.py`: Color routes by effective capacity and ΔT. Highlight bottleneck segments.

### Phase 4 (FUTURE): Web UI + Reports

Flask what-if app, Word/PDF determination reports, AB 1600 fee calculator.

---

## 10. File Structure

```
agents/
  data_acquisition.py    # Agent 1: FHSZ, roads, boundary, Census, LEHD
  capacity_analysis.py   # Agent 2: HCM capacity, hazard degradation,
                         #          Dijkstra routing with bottleneck tracking,
                         #          catchment demand
  objective_standards.py # Agent 3: ΔT determination (replaces v/c marginal)
  fee_calculator.py      # Agent 4: AB 1600 impact fee nexus
  what_if.py             # Agent 5: What-if analysis engine
  visualization.py       # Agent 6: Folium maps
  report_generator.py    # Agent 7: Determination letters

models/
  road_network.py        # RoadSegment dataclass (+ effective_capacity_vph)
  evacuation_path.py     # NEW: EvacuationPath dataclass (bottleneck tracking)
  project.py             # Project dataclass (+ stories, delta_t fields)

config/
  parameters.yaml        # Global: HCM, mobilization, degradation, thresholds
  cities/
    berkeley.yaml
    encinitas.yaml
    [city_slug].yaml

data/{city}/
  fhsz.geojson
  roads.gpkg
  boundary.geojson
  block_groups.geojson
  evacuation_paths.json  # NEW: path-level bottleneck data
  entitled_projects.json # NEW: JOSH entitled project ledger
  metadata.yaml

output/{city}/
  routes.csv
  determination_{id}.json
  determination_{id}.txt
  map_{id}.html
```

---

## 11. Change Log from v2.0

| Component | v2.0 | v3.0 | Rationale |
|---|---|---|---|
| Core metric | V/C ratio per segment | ΔT minutes per serving route | Time is the dimension that matters for life safety |
| Determination test | `baseline_vc < 0.95 AND proposed_vc >= 0.95` | `delta_t > max_marginal_minutes` | Eliminates structural defect where failing zones escaped review |
| Baseline dependency | Required — test only fires if project pushes past 0.95 | None — test references only project vehicles and road capacity | Uniform standard regardless of zone condition |
| Mobilization rate | 0.57 fixed (KLD) | Tiered by FHSZ zone (0.25-0.75) | GPS-empirical data shows compliance varies by proximity to hazard |
| Road capacity | Raw HCM | HCM × hazard degradation factor | Roads in fire zones don't operate at full capacity during fires |
| Building egress | Not modeled | NFPA 101 / IBC penalty for high-rise | SB 79 projects create surge delay from building egress |
| Demand model | Quarter-mile buffer (KLD methodology) | Dijkstra catchment | More accurate — counts only HUs whose path traverses segment |
| Bottleneck | Per-segment v/c | Per-path min(effective_capacity) | Binding constraint is weakest link on the path, not each segment independently |
| Entitled projects | Not tracked | JOSH ledger | Cumulative visibility without altering project-level test |
| Legal framing | CEQA marginal causation (traffic impact) | Safety Element condition-based finding (life safety) | Avoids marginal causation trap; aligns with AB 747 intent |

# JOSH v3.4.1 — Configurable Parameters Specification

**Version:** 3.4.1 (Configurable Parameter Architecture — City-Adjustable Defaults)
**Date:** May 2026
**Supersedes:** JOSH v3.4 Specification (March 2026)
**Authority:** California Government Code §65302(g)(4), §65302.15 (AB 747), §65589.5 (HAA)

---

## 1. Purpose of This Version

JOSH v3.4.1 formalizes the configurable parameter architecture that has always existed in the codebase but was not fully documented as a city-facing design feature. Two substantive changes accompany this documentation:

1. **`vehicles_per_unit` corrected to 1.9** — the actual California statewide all-household average from Census ACS B25044, replacing the prior 2.5 figure which was not supported by the cited source.

2. **Mobilization split into two explicit factors** — `vehicles_per_unit` (a Census measurement) and `behavioral_mobilization` (a conservative design release factor anchored to California WUI stated-intent literature), each with its own source and its own city override path.

Everything else in v3.4 is unchanged. The determination logic, routing algorithm, egress penalty, hazard degradation formula, and threshold derivation are identical.

---

## 2. Design Philosophy: Conservative Defaults, Local Override

### 2.1 The Core Commitment

**JOSH defaults to the most life-safety-protective value for every configurable parameter.** When evidence is incomplete or a range of values is defensible, the system resolves ambiguity in favor of the stricter standard — the one that results in more projects receiving discretionary review, not fewer.

This is deliberate and explicit. The default configuration is designed for a city council or attorney who wants to say: *"We applied the most protective standard the literature supports. If any input is wrong, it errs toward safety."*

### 2.2 Why Cities Override

Cities override defaults for three legitimate reasons:

**Local data is better than the statewide default.** A city may have Census data showing its households own 2.2 vehicles on average, not 1.9. A city in the Berkeley hills may have documented fire spread timelines that differ from the Camp Fire. A rural city may have formally adopted evacuation routes that JOSH should use instead of the OSM-derived graph. In each case, the local data is more accurate, and more accurate inputs produce more defensible determinations.

**Local conditions are less hazardous than the statewide assumption.** A city with a Cal Fire–certified WEA system, mandatory evacuation pre-plans, and wide two-lane arterials may have a longer effective escape window than the VHFHSZ default of 45 minutes assumes. Using 45 minutes for such a city is conservative — not wrong — but the city may prefer to use its documented local conditions.

**The city chooses to be more conservative than the default.** Nothing prohibits a city from setting `max_project_share` to 3% instead of 5%, or `behavioral_mobilization` to 1.00 instead of 0.90. Stricter defaults are always available.

### 2.3 What Cities Are Not Doing

A city that adjusts a JOSH parameter is not inventing a new methodology. It is selecting a locally-appropriate value for an established input in an established formula. The formula structure, the data sources, the routing algorithm, and the determination logic belong to JOSH. The city is adjusting the dials, not rebuilding the instrument.

This distinction is legally significant: a developer challenging a determination based on locally-adjusted parameters must challenge the city's factual basis for the adjustment — not the underlying methodology, which remains unchanged.

### 2.4 The Conservative Default Direction for Each Category

| Category | Conservative direction | Effect on determinations |
|----------|----------------------|--------------------------|
| `vehicles_per_unit` | Higher | More project vehicles → higher ΔT → more discretionary |
| `behavioral_mobilization` | Higher | More vehicles on road → higher ΔT → more discretionary |
| `hazard_degradation` factors | Lower | Less road capacity → higher ΔT → more discretionary |
| `safe_egress_window` | Shorter | Tighter threshold → more discretionary |
| `max_project_share` | Lower (smaller %) | Tighter threshold → more discretionary |
| `hcm_capacity` base values | Lower | Less road capacity → higher ΔT → more discretionary |
| `egress_penalty.minutes_per_story` | Higher | Higher ΔT for tall buildings → more discretionary |
| `evacuation.max_path_length_ratio` | Higher | More routes examined → finds worse bottlenecks → more conservative |
| `unit_threshold` | Lower | More projects analyzed → more protective |

---

## 3. Formula — What Changed from v3.4

### 3.1 v3.4 Formula

```
project_vehicles = units × vehicles_per_unit × mobilization_rate

Where:
  vehicles_per_unit  = 2.5   (Census ACS B25044 — cited but not supported)
  mobilization_rate  = 0.90  (design basis — conflated vehicle non-ownership
                               and behavioral compliance into one factor)
```

**Problem:** `vehicles_per_unit = 2.5` is not the California ACS B25044 statewide average. It overstates vehicle ownership. `mobilization_rate = 0.90` conflated two separate factors — vehicle non-ownership (a Census measurement) and behavioral non-compliance (an emergency-response rate) — without separately citing each.

### 3.2 v3.4.1 Formula

```
project_vehicles = units × vehicles_per_unit × behavioral_mobilization

Where:
  vehicles_per_unit       = 1.9   (Census ACS B25044, California statewide
                                    all-household average, including zero-vehicle HH)
  behavioral_mobilization = 0.90  (conservative design release factor;
                                    upper bound of CA WUI stated-intent literature,
                                    Roberson et al. 2012)
```

**Why the split matters:** `vehicles_per_unit = 1.9` is a Census measurement. It already reflects the distribution of vehicle ownership, including the ~9–10% of California households with zero vehicles. Because zero-vehicle households are already embedded in the 1.9 average, the mobilization factor no longer needs to account for them. `behavioral_mobilization = 0.90` now represents only the behavioral question: of the vehicles a project generates, what fraction actually reach the road during an evacuation?

**The two factors have different city override paths.** `vehicles_per_unit` is updated by pulling local ACS B25044 data — a Census query, not a policy decision. `behavioral_mobilization` requires documented evidence from evacuation planning research or local fire history.

### 3.3 Numerical Impact

| Formula | Effective veh/unit | Example: 45-unit project |
|---------|--------------------|--------------------------|
| v3.4 (2.5 × 0.90) | 2.25 | 101 vehicles |
| v3.4.1 (1.9 × 0.90) | 1.71 | 77 vehicles |

The v3.4.1 default produces approximately 24% fewer project vehicles. Projects that were borderline discretionary under v3.4 may shift to conditional ministerial under v3.4.1. This is the correct direction: the prior formula overstated vehicle demand.

### 3.4 Informational: Vehicle Ownership Rate

The system calculates and reports `vehicle_ownership_rate = 1 − zero_vehicle_fraction` from ACS B25044 in the audit trail as an informational figure. It is **not** a formula multiplier. Since `vehicles_per_unit = 1.9` already reflects the all-household average, applying `vehicle_ownership_rate` again as a multiplier would double-deduct the zero-vehicle population.

```
Audit trail reports (informational only):
  vehicles_per_unit:      1.9   (ACS B25044, all HH average)
  vehicle_ownership_rate: 0.91  (ACS B25044, 1 − zero_vehicle_fraction)
  behavioral_mobilization: 0.90 (Roberson 2012 / conservative design release factor)
  ─────────────────────────────────────────────────────────────────
  effective_vehicles/unit: 1.71 = 1.9 × 0.90
```

---

## 4. Complete Parameter Reference

Every parameter is documented with: its default value, the source that justifies the default, what "more conservative" means for that parameter, and the city override path.

---

### 4.1 Vehicle Demand Parameters

#### `vehicles_per_unit`

| Field | Value |
|-------|-------|
| **Default** | 1.9 |
| **Type** | Float |
| **Units** | Vehicles per occupied housing unit |
| **Source** | U.S. Census Bureau, ACS 5-Year Estimates, Table B25044 (Vehicles Available by Tenure), California statewide |
| **Conservative direction** | Higher |
| **Override** | City-specific ACS B25044 query (see §6) |

**What the default represents:** The ACS B25044 California statewide average of vehicles available per occupied housing unit, across all households including those with zero vehicles. This is a directly measured Census statistic for the state. It is not a planning assumption or an ITE trip generation rate.

**Why 1.9, not 2.5:** ACS B25044 data for California shows approximately 9–10% zero-vehicle households and an overall weighted average of 1.85–1.95 vehicles per occupied unit (2022 5-year estimates). The prior 2.5 figure was not reproducible from the cited source.

**How to compute the city-specific value:**

```python
# ACS B25044 query (performed automatically when acs_year is set):
vehicles_total = B25044_003E + B25044_004E + B25044_005E + B25044_006E \
               + B25044_010E + B25044_011E + B25044_012E + B25044_013E
# (owner-occupied: 1 + 2 + 3 + 4+ veh; renter-occupied: 1 + 2 + 3 + 4+ veh)
# Weighted by actual unit counts, not a simple average of subcategories.

housing_units_occupied = B25003_001E
vehicles_per_unit = vehicles_total / housing_units_occupied
```

Cities with high car ownership (e.g., auto-dependent suburbs with large garages) may have local values of 2.0–2.3. Cities with strong transit access (SF, Berkeley) may have values of 1.4–1.7. The override replaces the statewide 1.9 with the locally-measured number.

**Note:** A city that increases `vehicles_per_unit` above 1.9 based on local ACS data is making the standard *more conservative* (harder for projects). A city that decreases it below 1.9 based on local ACS data is making it *less conservative* but more accurate for that locality.

---

#### `behavioral_mobilization`

| Field | Value |
|-------|-------|
| **Default** | 0.90 |
| **Type** | Float (0.0–1.00) |
| **Units** | Fraction of a project's vehicles that reach the road during evacuation |
| **Source** | Roberson et al. (2012), *Journal of Emergency Management* 10(5) — California WUI stated compliance intent; Zhao et al. (2022), *Transportation Research Part D* — GPS-observed Kincade Fire compliance; Wu et al. (2022), *Int. J. Disaster Risk Reduction* — GPS-observed Kincade Fire compliance; California OPR Draft Evacuation Planning Technical Advisory (2024) |
| **Conservative direction** | Higher (1.00 = all vehicles mobilize) |
| **Override** | Documented local evidence: adopted evacuation plan compliance rate, local fire history study, or licensed transportation engineer study |

**What this factor represents:** Of the vehicles a project generates — the `units × vehicles_per_unit` figure — what fraction actually appear on the road when an evacuation order is issued? This is a behavioral question. It accounts for:

- Residents not home when the order is issued (at work, school, running errands)
- Residents already away from the property with their vehicle
- Households that own two cars but depart together in one
- The small fraction that refuse to comply with mandatory evacuation orders

**What this factor does not represent:** Zero-vehicle households. Those households are already reflected in `vehicles_per_unit = 1.9` (the all-household average). They do not appear in this factor.

**Source basis:** Roberson et al. (2012) surveyed residents in a Southern California High Fire Hazard Area and found that 82.6% stated they would "likely" or "for sure" evacuate under a mandatory evacuation order, with approximately 10% stating they would not comply. The 0.90 design value sits at the upper bound of this stated-compliance range.

GPS-based observational studies of actual California WUI fires document substantially lower observed compliance: Zhao et al. (2022) and Wu et al. (2022) both analyzed GPS data from the 2019 Kincade Fire and found approximately 46–48% compliance across evacuation zones. JOSH deliberately uses 0.90 — roughly twice the GPS-observed average — because the ΔT standard is sizing roads for a credible high-demand scenario, not predicting historical average behavior. California OPR's Draft Evacuation Planning Technical Advisory supports using documented, reasoned planning assumptions, including conservative upper-bound values, in evacuation clearance-time analysis.

**Conservative design note:** A lower mobilization value (e.g., the GPS-observed ~0.47) would reduce calculated project-vehicle demand, lower ΔT, and push more projects toward ministerial approval. The conservative direction is higher, not lower. **NFPA 1660:2024 (consolidating NFPA 1616:2020 mass-evacuation framework)** — the operative community-scale standard — reinforces this orientation by sizing community evacuation programs for the full calculated demand, not for the fraction historically observed to evacuate during past events. NFPA 101 (building egress) applies the same full-load design principle at the building scale and is cited as analogical reasoning. If the analogy is pressed to its limit, both NFPA 1660 / 1616 and NFPA 101 point toward 1.00 (full demand); the 0.90 value specifically derives from the California WUI stated-intent literature (Roberson 2012) — the empirical California validation point for the design value selected.

**Override range:** 0.75 (cities with documented lower compliance, non-mandatory orders, or transit-dependent populations) to 1.00 (maximum conservatism, or cities with documented near-universal car-dependent populations under mandatory order). A city should not use values below 0.75 for discretionary project review without substantial documented justification. The minimum defensible value is the GPS-observed California WUI range (~0.47–0.55); a city using values in that range should document that it is designing for observed average behavior rather than a conservative upper-bound scenario.

---

### 4.2 Road Capacity — HCM 2022 Base Values

#### `hcm_capacity`

| Field | Value |
|-------|-------|
| **Source** | Highway Capacity Manual, 7th Edition (2022), Transportation Research Board |
| **Conservative direction** | Lower base capacity values |
| **Override** | Licensed PE certification required |

**Default values (all HCM Exhibit references, HCM 7th Ed.):**

| Road type | Default (pc/h/lane) | HCM Reference |
|-----------|--------------------:|---------------|
| Freeway | 2,250 | Ch. 12, Exhibit 12-6 |
| Multilane highway/arterial | 1,900 | Ch. 12, Exhibit 12-7 |
| Two-lane, ≤ 20 mph | 900 | Ch. 15 |
| Two-lane, 25 mph | 1,125 | Ch. 15 |
| Two-lane, 30 mph | 1,350 | Ch. 15 |
| Two-lane, 35 mph | 1,575 | Ch. 15 |
| Two-lane, ≥ 40 mph | 1,700 | Ch. 15 |

**When to override:** A city that has conducted a calibrated HCM analysis for a specific corridor (e.g., a bottleneck road subject to grade, horizontal curvature, or access point density adjustments) may substitute the calibrated capacity value for that segment's `hcm_capacity` entry. This requires a PE-stamped traffic study. The override applies to the named road segment only; all other segments retain HCM defaults.

**What "conservative" means here:** Lower capacity values produce higher ΔT (the bottleneck becomes more binding), which is the more protective direction. HCM values are already theoretical maximums; most roads operate below these values under normal conditions. Applying the full HCM value is itself conservative in the developer's favor.

---

#### `lane_defaults`

Default lane counts by OSM highway type, used when OSM does not tag a `lanes` value:

| OSM type | Default lanes |
|----------|:-------------:|
| motorway | 3 |
| trunk | 2 |
| primary | 2 |
| secondary | 2 |
| tertiary | 1 |
| residential | 1 |

**Override:** Cities may provide field-measured lane counts for specific road segments via the `road_overrides` section of the city config. This is the most common real-world override — OSM lane tags are frequently missing for local streets. A higher lane count reduces ΔT (more conservative toward the developer); a lower lane count increases ΔT (more conservative toward life safety). The default of 1 lane for residential streets is conservative toward life safety.

---

#### `speed_defaults`

Default posted speed limits by OSM highway type, used when OSM does not tag `maxspeed`:

| OSM type | Default (mph) |
|----------|:-------------:|
| motorway | 65 |
| trunk | 55 |
| primary | 45 |
| secondary | 35 |
| tertiary | 25 |
| residential | 25 |
| living_street | 15 |

Speed limit determines which HCM two-lane capacity entry applies. A lower inferred speed produces lower capacity, which increases ΔT. Defaults are set at typical California posted limits; cities may override for roads with non-standard speed limits.

---

#### `width_speed_inference`

When neither `maxspeed` nor a city override is available, road width (from OSM `width` tag, in meters) is used to infer a conservative speed tier. This applies only to roads classified as two-lane (tertiary, residential) without a speed tag.

| Width threshold | Inferred speed | Basis |
|----------------|:--------------:|-------|
| < 4.57 m (< 15 ft) | 10 mph | Alley / single-track access |
| < 6.10 m (< 20 ft) | 15 mph | Below IFC §503 one-way minimum |
| < 7.32 m (< 24 ft) | 20 mph | Narrow two-way |
| ≥ 7.32 m | speed_defaults | Standard residential |

**Source:** International Fire Code §503 fire apparatus access road minimums (20 ft one-way, 26 ft two-way); AASHTO geometric design guidelines. A road narrower than the IFC minimum fire apparatus access width is assumed to operate at a reduced speed regardless of posting, because the physical geometry constrains throughput.

**Override:** Cities may disable width-speed inference and supply explicit speeds via `road_overrides`.

---

### 4.3 Road Classification

#### `road_type_mapping`

Determines which HCM capacity table applies to each road segment. OSM `highway` tags are mapped to HCM road types:

| HCM type | OSM tags (default) |
|----------|--------------------|
| freeway | motorway, motorway_link, trunk, trunk_link |
| multilane | primary, primary_link, secondary, secondary_link |
| two_lane | tertiary, tertiary_link, residential, living_street, unclassified, road |

**Override:** A city may reclassify specific OSM highway types. The most common legitimate override is reclassifying a `secondary` road as `two_lane` when the road is physically a single-lane rural collector — OSM tags do not always match HCM classification.

**Note:** Reclassifying a road to a lower-capacity HCM type (e.g., `multilane` → `two_lane`) reduces that road's capacity, which is the more conservative direction for life safety.

---

### 4.4 Hazard Degradation Factors

#### `hazard_degradation`

| Field | Value |
|-------|-------|
| **Source** | Composite engineering-judgment factor anchored against the HCM 2022 Chapter 11 weather Capacity Adjustment Factor framework (Exhibit 11-20) and validated against NIST TN 2135 Camp Fire empirical observations, Rohaert et al. (2023) Kincade Fire traffic dynamics, and Wetterberg et al. (2022) smoke-visibility driving-speed empirical data. *Citation note (May 2026): Earlier docs cited HCM Exhibits 10-15 (Lane Closure Severity Index for work zones) and 10-17 (a photograph) as the direct source; those exhibits contain no fire/smoke/visibility capacity values. The attribution has been corrected; the values themselves stand as conservative composite engineering-judgment scaling pending independent traffic-engineering review (Fire Science Consulting LLC review, May 2026; open item on the JOSH Methodology Roadmap).* |
| **Conservative direction** | Lower factor (more capacity lost) |
| **Override** | PE certification required; override must cite documented local fire conditions and empirical evacuation traffic data |

**Default factors (composite engineering judgment):**

| Zone | Factor | Derivation |
|------|:------:|------------|
| VHFHSZ | **0.35** | Severe smoke visibility loss + counterflow emergency vehicle obstruction on two-lane roads; informed by NIST TN 2135 burnover analysis (3 of 5 evacuation routes closed entirely in the Camp Fire). 0.35 is conservative relative to the HCM Ch. 11 Ex. 11-20 worst-case weather CAF (heavy snow, 0.72–0.80) on the engineering judgment that WUI fire conditions exceed any HCM-calibrated weather scenario. |
| High FHSZ | **0.50** | Moderate smoke + intermittent shoulder incidents. Composite rounded for compound effects; bounded above by the VHFHSZ factor. |
| Moderate FHSZ | **0.75** | Light smoke possible; minimal direct fire-front exposure. |
| Non-FHSZ | **1.00** | No fire-related degradation. |

**Conservative design note:** The 0.35 VHFHSZ factor is already more generous than observed Camp Fire conditions: three of five evacuation routes were closed entirely during the Camp Fire (factor = 0.00). Using 0.35 assumes roads continue to function at more than one-third capacity during an active VHFHSZ fire — a concession to the developer. Cities with documented historical road closures during local fires may justify lower factors.

**Override procedure:** A city-specific degradation factor for a given zone requires a PE-stamped engineering report citing:
1. The specific HCM exhibits and factors applied
2. The local fire condition data supporting departure from the default composite
3. The resulting factor and its derivation

Factors may only be overridden for an entire FHSZ zone, not for individual road segments. Segment-level capacity adjustments are handled via `hcm_capacity` road overrides.

---

### 4.5 Safe Egress Windows

#### `safe_egress_window`

| Field | Value |
|-------|-------|
| **Source** | NIST Technical Note 2135 (Camp Fire timeline, 2021); NIST TN 2252 (NETTRA, 2023); NIST TN 2262 (ESCAPE, 2023/2025) |
| **Conservative direction** | Shorter window (tighter threshold) |
| **Override** | Council resolution required; must cite local fire behavior data or documented WEA/alert system improvement |

**Default windows:**

| Zone | Window | Source |
|------|:------:|--------|
| VHFHSZ | **45 min** | NIST TN 2135: Camp Fire spot fires to fire front = 40 min (documented) + 5 min for modern WEA alert systems not available in 2018 |
| High FHSZ | **90 min** | Fire spread 1–2 mph vs. 3–5 mph in VHFHSZ; approximately 2× the VHFHSZ window |
| Moderate FHSZ | **120 min** | Lower fire intensity, greater distance from typical ignition points |
| Non-FHSZ | **120 min** | FEMA standard emergency planning window for no-notice events |

**What the VHFHSZ window represents:** The NIST Camp Fire documentation shows fire-front arrival at Paradise approximately 40 minutes after spot fires were first observed in the community. The +5 minutes represents a modern WEA system benefit not available in 2018. The 45-minute window is therefore the *best case* for VHFHSZ conditions with current alert technology — not a comfortable average. Cities should be cautious about increasing it.

**Legitimate reasons to extend the VHFHSZ window:**
- A city has a Cal Fire–certified community alert system with documented notification times shorter than 5 minutes
- Local topography and fuel load have been assessed to produce materially slower fire spread than the Camp Fire
- The city has a formally adopted pre-evacuation trigger system (i.e., evacuation begins before visible flame)

**Legitimate reasons to shorten the VHFHSZ window:**
- Local fire history documents shorter warning-to-hazard timelines
- The city's road network includes significant topographic constraints that delay egress independent of capacity

**Effect of window changes on thresholds:** Thresholds are computed at runtime as `safe_egress_window × max_project_share`. Changing the window changes the threshold proportionally. A longer window produces a more permissive threshold; a shorter window is more protective.

---

### 4.6 Policy Threshold

#### `max_project_share`

| Field | Value |
|-------|-------|
| **Default** | 0.05 (5%) |
| **Type** | Float (0.0–1.0) |
| **Units** | Fraction of safe egress window one project may consume |
| **Source** | Standard engineering de minimis significance threshold |
| **Conservative direction** | Lower (smaller share = stricter threshold) |
| **Override** | Council resolution required |

**What this parameter is:** The single policy value the city formally adopts. Everything else in the JOSH formula is derived from published sources. This is the one number that represents the city's judgment about how much of the available escape time any single project may consume.

**Why 5%:** At 5%, the safe egress window can accommodate approximately 20 equal-sized projects before new development alone exhausts it. Five percent is the standard engineering significance threshold used across traffic engineering, structural analysis, hydraulic design, and environmental impact assessment.

**Derived thresholds (at default 5%):**

| Zone | Window | × 5% | ΔT Threshold |
|------|:------:|:-----:|:------------:|
| VHFHSZ | 45 min | 0.05 | **2.25 min** |
| High FHSZ | 90 min | 0.05 | **4.50 min** |
| Moderate FHSZ | 120 min | 0.05 | **6.00 min** |
| Non-FHSZ | 120 min | 0.05 | **6.00 min** |

**Non-round thresholds are a feature:** The 2.25-minute threshold is not a round number chosen by staff — it is the arithmetic output of 45 × 0.05. A developer challenging the threshold must contest the NIST timeline or the 5% engineering standard. Neither is a discretionary city choice.

**Override range:** Cities may set `max_project_share` between 0.01 (1%, very restrictive) and 0.10 (10%, more permissive). Values above 5% require explicit council findings explaining why projects should be permitted to consume more than the engineering de minimis standard of the available escape time.

---

### 4.7 Building Egress Penalty

#### `egress_penalty`

| Field | Value |
|-------|-------|
| **Source** | NFPA 101 Life Safety Code (2024 California edition), Chapter 7; International Building Code (IBC) 2024, Chapter 10 — Means of Egress, adopted by reference in the California Building Code. *(This is the legitimate use of NFPA 101 in JOSH — building egress, distinct from the community mass-evacuation mobilization rate sourced to NFPA 1660 / 1616.)* |
| **Conservative direction** | Higher minutes per story, lower threshold stories |
| **Override** | Applicant-provided NFPA 101 egress calculation (PE-stamped) |

**Default schedule:**

| Parameter | Default | Source |
|-----------|:-------:|--------|
| `threshold_stories` | 4 | NFPA 101 (2024 CA ed.) high-rise threshold (75 ft) |
| `minutes_per_story` | 1.5 | NFPA 101 stair descent rate + IBC 2024 Ch. 10 garage egress time |
| `max_minutes` | 12 | Cap at 8-story equivalent |

**Formula:**

```
T_egress = 0                              if project_stories < threshold_stories
T_egress = min(stories × 1.5, 12)        if project_stories ≥ threshold_stories
```

**Override paths:**

*City override:* A city may lower `threshold_stories` to 3 or 2 based on documented local building stock characteristics (e.g., a city where three-story condominiums are the predominant new housing type and stair egress time is a documented constraint).

*Applicant override:* A developer may substitute a project-specific NFPA 101 egress calculation prepared by a licensed fire protection engineer. The PE-stamped calculation replaces the default schedule for that project only and must be submitted with the application.

**Developer design levers:** `T_egress` is a function of building design decisions the developer controls: number of stairwells, stair width, number of parking garage vehicle exits, driveway throat configuration. A developer can reduce `T_egress` below the default by providing additional egress capacity. This is the primary mitigation pathway for tall projects that would otherwise exceed the ΔT threshold.

---

### 4.8 Route Identification Parameters

#### `evacuation.serving_route_radius_miles`

| Field | Value |
|-------|-------|
| **Default** | 0.5 miles |
| **Conservative direction** | Larger radius (examines more routes, finds worse bottlenecks) |
| **Override** | City engineer determination |

The system identifies evacuation routes that originate within this radius of the project site. 0.5 miles represents a reasonable walking/driving radius for the first portion of an evacuation trip; all roads a project could plausibly use to begin an evacuation are captured.

**Override:** Cities with widely-spaced road networks (rural or hillside topographies) may increase this to 1.0 or 1.5 miles to ensure all relevant serving routes are captured.

---

#### `evacuation.max_path_length_ratio`

| Field | Value |
|-------|-------|
| **Default** | 3.5 (raised from 2.0 in v4.12) |
| **Conservative direction** | Higher (examines more paths, more potential bottlenecks found) |
| **Override** | City engineer determination |

Paths whose travel time exceeds 3.5× the fastest-exit travel time are excluded from analysis. This filter represents the assumption that rational evacuees take the fastest route to safety under User Equilibrium assignment; paths more than 3.5× the optimal travel time would not be chosen when faster alternatives exist.

**Why 3.5 (raised from 2.0 in v4.12 "all-viable-routes"):** The earlier 2.0 default was paired with per-bottleneck deduplication — the engine returned only the fastest path per unique bottleneck road. The deduplication step has been removed, and the ratio raised to 3.5, so that all viable divergent routes surface for review. The legal determination always uses every path returned; the sidebar's per-route toggle list is purely a display control and never affects the ΔT determination.

**Override:** Cities with no-outlet subdivisions or extreme topographic constraints may lower this ratio (e.g. to 2.5) to focus on genuinely available routes. Cities with very complex multi-route networks may raise it (e.g. to 4.0) to surface more routes for review. Lower values produce *less* conservative analysis (fewer paths considered → fewer chances to find a flagged bottleneck), so changes downward warrant explicit engineer determination.

---

### Viable Route Methodology

**Definition.** A *viable route* is a Dijkstra shortest-path from the project location (or any additional egress origin) to any boundary exit node, whose travel time is within `max_path_length_ratio` of the fastest available exit. Viability is purely a User Equilibrium choice criterion — it answers "which routes would a rational evacuee actually use?" and excludes paths so slow that no evacuee would prefer them over a faster alternative.

**No prescribed routes; no traffic-management assumption.** JOSH does not model System Optimum traffic assignment (where a central authority directs vehicles to specific routes and has the operational capacity to enforce assignment at every decision point). The Camp Fire (Paradise, CA, 2018) — the canonical event behind JOSH's `safe_egress_window` parameters (NIST TN 2135) — demonstrated that prescribed routes were rendered irrelevant within minutes as fire behavior outpaced staffing. Residents self-evacuated via every available arterial. Adopting User Equilibrium is the legally defensible position for an objective standards methodology: it makes no assumption about fire department operational capacity that would be unverifiable in statute.

**More routes = more conservative ΔT determination.** The ΔT determination flags `DISCRETIONARY` if *any* viable route exceeds the threshold. Returning more routes increases the chance that a flagged path is found; it never reduces it. Removing the dedup step is therefore monotonically conservative — it cannot mask a hazard.

**User control over display, not over determination.** The sidebar (`static/sidebar.js`) shows the full viable set as a sorted list (fastest-exit-first, matching User Equilibrium ordering). The map's default view shows only the controlling (worst-case) route — the binding evidence for the determination. A "Show all viable routes (N)" toggle in the sidebar route header reveals the other routes as thin context lines under the controlling route. Hiding any route does not exclude it from the determination — a persistent footer note ("Determination uses all N routes") is a legal safeguard that must remain visible whenever a route is hidden.

**Engine parity (v4.13).** Effective road capacity (`eff_cap_vph`) is baked per-edge onto the OSMnx routing graph by `agents/capacity_analysis.py::bake_capacity_onto_graph` as a one-time enrichment. Both engines — Python (`agents/scenarios/wildland.py`) and JavaScript (`static/whatif_engine.js` via `output/{city}/graph.json`) — read `eff_cap_vph` directly from the edge attribute. This eliminates the parallel osmid-keyed lookups that produced silent tier divergence in v4.12 (Python returned `0` for missing osmids, JS defaulted to `1000`; same path, different bottleneck). The `agents/scenarios/segment_index.py` osmid-side-table is removed; the `tests/test_whatif_engine.js matchPaths()` anti-divergence guard hard-fails when bottleneck osmid sets disagree (was a silent log).

### Display Conventions (v4.13)

The visual design follows the "binding constraint + faint context" pattern used in adjacent safety-analysis disciplines (fault-tree, traffic-engineering studies, floodplain mapping). The default presentation is:

- **Controlling route:** drawn in JOSH brand navy (`#1c4a6e`) at weight 5, opacity 0.95, with a wider gold (`#f59e0b`) halo underneath. Tagged with a "CONTROLLING ROUTE" badge in the sidebar.
- **Context routes (when "Show all" is on):** drawn in the same navy at weight 2, opacity 0.45, no halo. Visible but subordinate.
- **Project tier color** (red DISCRETIONARY, orange CONDITIONAL, green MINISTERIAL) appears on the determination banner and tier chip only — never on individual route lines. The determination is project-level; individual route lines do not carry pass/fail color.
- **Brief renderer (`brief_renderer.js`):** Criterion C opens with a framing paragraph paraphrasing §8.6 of the Legal Defensibility Memo, followed by the full route table. The CONTROLLING row is highlighted with a gold badge. Non-controlling rows render in neutral text color (no per-row pass/fail color); the table omits a per-row "Result" status column because the CONTROLLING badge supplies all needed visual status.

These conventions exist to align the visual presentation with the methodology's legal premise: routes are evidence of evacuee behavior under User Equilibrium, not a menu of options the developer can select between. Per-route pass/fail color would invite the alternative-route argument (which §8.6 dismantles formally); the unified-color design ensures the UI does not undermine the legal framework it sits within.

---

#### `evacuation.exit_highway_types`

| Field | Value |
|-------|-------|
| **Default** | motorway, motorway_link, trunk, trunk_link, primary, primary_link |
| **Conservative direction** | Including lower-classification roads as exits (finds fewer exit nodes, forces longer paths) |
| **Override** | City engineer determination, based on formally adopted evacuation route network |

Exit nodes are the points where JOSH considers a vehicle to have "escaped" to the regional network. By default, exit nodes are road-network nodes connected to major regional roads. This reflects the assumption that entering the freeway, a state highway, or a major arterial constitutes effective regional handoff.

**Override for cities with no freeway access:** Cities where secondary roads are the primary evacuation corridors (no freeway or trunk highway is reachable) should add `secondary` and `secondary_link` to this list. Without this override, the system may find no exit nodes and fall back to all boundary nodes — which may or may not be appropriate.

**Override for cities with formally adopted evacuation routes:** A city that has adopted specific evacuation routes in its Safety Element may provide a `custom_exit_nodes.json` file that supersedes the OSM-derived exit node identification entirely. This is the highest-quality override available for route identification.

---

#### `evacuation.exit_nodes_override`

| Field | Value |
|-------|-------|
| **Default** | None (OSM-derived) |
| **Type** | Path to GeoJSON file |
| **Override** | City engineer, based on formally adopted evacuation route network |

When provided, this file replaces the OSM-derived exit node calculation entirely. The file should contain point features representing the formal evacuation route exits adopted in the city's Safety Element or evacuation plan. This is the most defensible form of route identification — it uses the city's own adopted network rather than an algorithm applied to community-mapped data.

---

### 4.9 Project Applicability

#### `unit_threshold`

| Field | Value |
|-------|-------|
| **Default** | 15 units |
| **Source** | ITE Trip Generation de minimis level; SB 330 (Gov. Code §65905.5) class anchor |
| **Conservative direction** | Lower (more projects analyzed) |
| **Override** | Council resolution |

**What this is:** An administrative proportionality threshold. Projects below 15 units receive ministerial approval without a ΔT calculation. Projects at or above 15 units receive the full analysis.

**What this is not:** A safety threshold. A 14-unit project in a VHFHSZ zone with a failing road is not categorically safe. The threshold reflects the judgment that below 15 units, the ΔT contribution is small enough on most road types that the administrative burden of full analysis is disproportionate to the additional risk captured. This must be stated explicitly in determination letters.

**Override:** Cities may lower this threshold to 10 or even 5 units in VHFHSZ areas. Lowering the threshold increases the number of projects subject to full analysis. Raising the threshold above 15 requires specific findings about why smaller projects should be exempt.

---

#### `fhsz.trigger_zones`

| Field | Value |
|-------|-------|
| **Default** | [2, 3] (High and Very High FHSZ) |
| **Conservative direction** | Include zone 1 (Moderate FHSZ) |
| **Override** | Council resolution |

Projects in trigger zones receive FHSZ-degraded road capacity analysis. Projects outside trigger zones are analyzed with no capacity degradation (factor = 1.00) and the non-FHSZ egress window.

**Override:** Adding zone 1 (Moderate FHSZ) to trigger zones causes the ΔT analysis to apply the moderate degradation factor (0.75) and the 120-minute egress window to affected projects. Cities with significant development pressure in Moderate FHSZ areas may choose this override.

---

## 5. Complete City Config File Reference

The city config file at `config/cities/{city_slug}.yaml` overrides specific parameters for a named city. Any parameter not listed in the city config retains its value from `config/parameters.yaml`.

**File format:**

```yaml
# ============================================================
# JOSH City Configuration — [City Name], CA
# Version: 3.4.1
# Contact: [City Planning Department]
# Last updated: YYYY-MM-DD
# ============================================================

city:
  name: "City Name"
  state: "CA"
  state_fips: "06"
  county_fips: "XXXXX"
  osmnx_place: "City Name, California, USA"

# ── VEHICLE DEMAND ──────────────────────────────────────────
# Source: ACS B25044, [city name] 5-Year Estimates, [year]
# Computed: vehicles_total / occupied_housing_units = [computed value]
# If not overriding, system uses California statewide default (1.9)
# vehicles_per_unit: 1.9   # <- uncomment and set to local value

# Source for behavioral_mobilization override: [cite document]
# behavioral_mobilization: 0.90  # <- uncomment to override

# ── SAFE EGRESS WINDOWS ─────────────────────────────────────
# Override requires council resolution citing specific local fire data.
# safe_egress_window:
#   vhfhsz: 45          # minutes — default per NIST TN 2135
#   high_fhsz: 90
#   moderate_fhsz: 120
#   non_fhsz: 120

# ── POLICY THRESHOLD ────────────────────────────────────────
# Override requires council resolution.
# max_project_share: 0.05   # 5% — standard engineering significance

# ── UNIT THRESHOLD ──────────────────────────────────────────
# unit_threshold: 15

# ── HAZARD DEGRADATION ──────────────────────────────────────
# Override requires PE-stamped engineering report.
# hazard_degradation:
#   factors:
#     vhfhsz: 0.35
#     high_fhsz: 0.50
#     moderate_fhsz: 0.75
#     non_fhsz: 1.00

# ── ROAD CAPACITY OVERRIDES ─────────────────────────────────
# Use for specific corridors with PE-verified geometry.
# road_overrides:
#   - osm_name: "Canyon Road"
#     lanes: 1
#     speed_mph: 20
#     hcm_capacity: 900
#     notes: "PE study [PE name], [date]: narrow road, 18 ft paved width"

# ── ROUTE IDENTIFICATION ─────────────────────────────────────
# evacuation:
#   serving_route_radius_miles: 0.5
#   max_path_length_ratio: 2.0
#   exit_highway_types:
#     - motorway
#     - motorway_link
#     - trunk
#     - trunk_link
#     - primary
#     - primary_link
#   exit_nodes_override: null  # path to custom GeoJSON, if formally adopted

# ── EGRESS PENALTY ──────────────────────────────────────────
# egress_penalty:
#   threshold_stories: 4
#   minutes_per_story: 1.5
#   max_minutes: 12

# ── CENSUS CONFIGURATION ────────────────────────────────────
census:
  acs_year: 2022

# ── DATA NOTES ──────────────────────────────────────────────
# notes: |
#   [Date]: vehicles_per_unit updated to [value] from ACS [year] 5-year estimates.
#   ACS query performed by [name], [title], [date].
```

---

## 6. Override Governance

Not every override carries the same evidentiary burden. The table below defines the minimum process for each override category.

| Override | Who can authorize | Evidence required | Process |
|----------|-------------------|-------------------|---------|
| `vehicles_per_unit` | City staff | ACS B25044 query for the city, documented | Staff report; no council action |
| `behavioral_mobilization` | City staff + PE | Peer-reviewed WUI evacuation literature or local study | PE-signed memo in project file |
| `unit_threshold` (lower) | City staff | None; more conservative | Staff report |
| `unit_threshold` (raise) | Council resolution | Specific findings re: proportionality | Council action |
| `safe_egress_window` (shorten) | City staff | None; more conservative | Staff report |
| `safe_egress_window` (extend) | Council resolution | Local fire behavior data, cited | Council action |
| `max_project_share` (lower) | City staff | None; more conservative | Staff report |
| `max_project_share` (raise) | Council resolution | Engineering findings | Council action |
| `hazard_degradation` factors (lower) | City staff | None; more conservative | Staff report |
| `hazard_degradation` factors (raise) | PE certification | PE-stamped engineering report citing HCM | PE report in city file |
| `road_overrides` (lane count, speed) | City engineer | Field measurement or PE study | City engineer memo |
| `hcm_capacity` segment override | PE certification | PE-stamped traffic study | PE report in city file |
| `road_type_mapping` change | City engineer | Physical road characteristics | City engineer memo |
| `evacuation.exit_nodes_override` | Council resolution | Formally adopted evacuation network | Safety Element or EVP |
| Applicant egress penalty override | Applicant | PE-stamped NFPA 101 egress study | Submitted with application |

**General rule:** Any override that makes the standard *more conservative* (harder for projects) may be made by staff without council action. Any override that makes the standard *less conservative* (easier for projects) requires council action and documented findings.

---

## 7. What the Audit Trail Records for Every Run

When any parameter is overridden from the JOSH default, the audit trail produced with each determination includes:

```
PARAMETER CONFIGURATION — [City Name] v3.4.1
─────────────────────────────────────────────────────────
Source: config/parameters.yaml (JOSH default)
Override: config/cities/[city].yaml (city-specific)

  vehicles_per_unit:       1.87  ← CITY OVERRIDE
    Source: ACS B25044, [City], 2022 5-Year Estimates
    JOSH default:          1.90

  behavioral_mobilization: 0.90  (JOSH default, Roberson 2012 / conservative design)

  safe_egress_window:
    vhfhsz:  45 min        (JOSH default, NIST TN 2135)
    high:    90 min        (JOSH default)
    moderate: 120 min      (JOSH default)

  max_project_share:       0.05  (JOSH default, 5%)

  hazard_degradation:
    vhfhsz: 0.35           (JOSH default, HCM composite)
    high:   0.50           (JOSH default)

[...]

  effective_vehicles/unit: 1.683 = 1.87 × 0.90
```

This gives any reviewing engineer — or any developer's attorney — full visibility into which values came from JOSH defaults and which came from city overrides, along with the source for each.

---

## 8. What Cities Are Saying When They Use JOSH

### 8.1 Without any override

"We apply the California Stewardship JOSH system with all default parameters. Our calculation uses the NIST-documented Camp Fire escape window, HCM 2022 road capacities with Cal Fire FHSZ degradation, ACS B25044 statewide vehicle ownership data, and a 90% behavioral mobilization rate derived from California WUI stated-intent literature (Roberson et al. 2012) — a conservative design value approximately twice the GPS-observed compliance rate documented in California wildfire studies. No parameter was chosen by city staff. The system's defaults represent the most protective values the published literature supports."

### 8.2 With a local ACS override

"We apply the JOSH system with one locally-calibrated parameter: vehicles per housing unit, updated to [value] from our city's ACS B25044 5-year estimates [year]. This local figure is more accurate for our housing stock than the California statewide default. All other parameters remain at JOSH defaults."

### 8.3 With a council-adopted extended egress window

"The City Council adopted Resolution [number] extending the VHFHSZ safe egress window from 45 to [N] minutes, based on [specific local fire behavior study / WEA system certification / other evidence]. The resolution is supported by [PE report / Cal Fire assessment / other]. All other parameters remain at JOSH defaults."

In each case, the determination letter recites the specific parameters used and their sources. A developer challenging any parameter must challenge either the JOSH default (a published national standard) or the city's documented local override (a factual record). Neither is a discretionary city judgment.

---

## 9. The Full List of City-Adjustable Parameters

The following is the complete inventory of every parameter a city may adjust in v3.4.1, organized by the effect of adjustment on determination outcomes.

### 9.1 Parameters Affecting Project Vehicle Count

| Parameter | Key | Default | Direction for stricter standard |
|-----------|-----|---------|--------------------------------|
| Vehicles per household | `vehicles_per_unit` | 1.9 | Higher |
| Emergency mobilization rate | `behavioral_mobilization` | 0.90 | Higher |

### 9.2 Parameters Affecting Road Capacity

| Parameter | Key | Default | Direction for stricter standard |
|-----------|-----|---------|--------------------------------|
| VHFHSZ degradation factor | `hazard_degradation.vhfhsz` | 0.35 | Lower |
| High FHSZ degradation factor | `hazard_degradation.high_fhsz` | 0.50 | Lower |
| Moderate FHSZ degradation factor | `hazard_degradation.moderate_fhsz` | 0.75 | Lower |
| Lane count (per road/type) | `lane_defaults` / `road_overrides` | By type | Lower |
| Speed limit (per road) | `speed_defaults` / `road_overrides` | By type | Lower |
| HCM base capacity (per road type) | `hcm_capacity` | By type | Lower |
| Road type classification | `road_type_mapping` | OSM → HCM | Lower-capacity type |
| Width-speed inference tiers | `width_speed_inference` | IFC-based | Lower speed per tier |

### 9.3 Parameters Affecting the ΔT Threshold

| Parameter | Key | Default | Direction for stricter standard |
|-----------|-----|---------|--------------------------------|
| VHFHSZ escape window | `safe_egress_window.vhfhsz` | 45 min | Shorter |
| High FHSZ escape window | `safe_egress_window.high_fhsz` | 90 min | Shorter |
| Moderate FHSZ escape window | `safe_egress_window.moderate_fhsz` | 120 min | Shorter |
| Non-FHSZ escape window | `safe_egress_window.non_fhsz` | 120 min | Shorter |
| Max project share of window | `max_project_share` | 5% | Lower % |

### 9.4 Parameters Affecting Building Egress Penalty

| Parameter | Key | Default | Direction for stricter standard |
|-----------|-----|---------|--------------------------------|
| High-rise threshold (stories) | `egress_penalty.threshold_stories` | 4 | Lower |
| Egress time per story | `egress_penalty.minutes_per_story` | 1.5 min | Higher |
| Maximum egress penalty | `egress_penalty.max_minutes` | 12 min | Higher |

### 9.5 Parameters Affecting Which Projects Are Analyzed

| Parameter | Key | Default | Direction for stricter standard |
|-----------|-----|---------|--------------------------------|
| Minimum project size | `unit_threshold` | 15 units | Lower |
| FHSZ zones triggering analysis | `fhsz.trigger_zones` | [2,3] | Include zone 1 |

### 9.6 Parameters Affecting Route Identification

| Parameter | Key | Default | Direction for stricter standard |
|-----------|-----|---------|--------------------------------|
| Search radius from project | `evacuation.serving_route_radius_miles` | 0.5 mi | Larger |
| Path length filter | `evacuation.max_path_length_ratio` | 2.0× | Higher |
| Exit node road types | `evacuation.exit_highway_types` | Major roads | Add lower types |
| Custom exit nodes | `evacuation.exit_nodes_override` | None | Formally adopted network |

---

## 10. Migration from v3.4

### 10.1 Code changes required

**`config/parameters.yaml`**
- Replace `mobilization_rate: 0.90` with `behavioral_mobilization: 0.90`
- Replace `vehicles_per_unit: 2.5` with `vehicles_per_unit: 1.9`
- Update block comment for `behavioral_mobilization` to cite NFPA 1660:2024 / NFPA 1616:2020 community mass-evacuation design basis (primary source), with Roberson et al. (2012) for empirical California validation and GPS contrast (Zhao/Wu 2022) as the observed-behavior reference. *(Previous drafts of this migration note cited FHWA or NFPA 101 — both attributions have been corrected per the Fire Science Consulting LLC review of May 2026.)*

**`agents/scenarios/base.py`, `agents/capacity_analysis.py`, `agents/objective_standards.py`**
- Replace `config.get("mobilization_rate", 0.90)` with `config.get("behavioral_mobilization", 0.90)`
- Replace `config.get("vehicles_per_unit", 2.5)` with `config.get("vehicles_per_unit", 1.9)`
- Update audit trail string to show two-factor breakdown

**`static/sidebar.js`, `static/brief_renderer.js`**
- Update JS fallback defaults: `|| 2.5` → `|| 1.9`
- Update JS fallback defaults: `mobilization_rate` → `behavioral_mobilization` key name

**All city config files**
- Review any `vehicles_per_unit` overrides — overrides above 1.9 are now the conservative direction and should be retained; overrides below 1.9 should be documented as locally-calibrated ACS values

### 10.2 No change to determination logic

The determination logic, routing algorithm, FHSZ degradation framework, egress penalty formula, and threshold derivation are unchanged. A project that was Ministerial under v3.4 may become Ministerial under v3.4.1 (some borderline Discretionary projects will shift given the lower vehicle count), but no project that was Ministerial under v3.4 will become Discretionary under v3.4.1. The change to `vehicles_per_unit` reduces ΔT values proportionally; it does not change the sign of any comparison.

### 10.3 Previously generated determinations

Determinations issued under v3.4 should be noted in the city's project file as having used `vehicles_per_unit = 2.5`. When a project is re-analyzed under v3.4.1, the audit trail will show the updated parameters. Cities should adopt a local administrative policy on whether to re-run pending applications under v3.4.1.

---

## 11. References

1. Transportation Research Board. *Highway Capacity Manual, 7th Edition (HCM 2022).* National Academies of Sciences, Engineering, and Medicine, 2022.
2. Maranghides, A., et al. *A Case Study of the Camp Fire — Fire Progression Timeline.* NIST Technical Note 2135. NIST, 2021.
3. Maranghides, A., et al. *A Case Study of the Camp Fire — NETTRA.* NIST Technical Note 2252. NIST, 2023.
4. Maranghides, A., et al. *A Case Study of the Camp Fire — ESCAPE.* NIST Technical Note 2262r1. NIST, March 2025. [Supersedes TN 2262, August 2023, which has been officially withdrawn.]
5. NFPA 1660. *Standard for Emergency, Continuity, and Crisis Management: Preparedness, Response, and Recovery.* National Fire Protection Association, 2024 edition. *(Operative source for the JOSH 0.90 community mass-evacuation mobilization rate; consolidates NFPA 1616.)*
5a. NFPA 1616. *Standard on Mass Evacuation, Sheltering, and Re-entry Programs.* National Fire Protection Association, 2020 edition. *(Predecessor to NFPA 1660.)*
6. NFPA 101. *Life Safety Code.* National Fire Protection Association, 2024 California edition. *(Operative source for the building-egress penalty for stories ≥ 4 only; supporting analogical reasoning for the mobilization rate.)*
6a. International Code Council. *International Building Code (IBC), Chapter 10: Means of Egress.* 2024 edition.
7. U.S. Census Bureau. *American Community Survey 5-Year Estimates.* Tables B25001, B25044. Census.gov.
8. California Department of Forestry and Fire Protection (Cal Fire). *Fire Hazard Severity Zone Maps.* Pursuant to Government Code §51175–51189.
9. Federal Highway Administration (FHWA). *Guide for Highway Capacity and Operations Analysis of ATDM Strategies.* Appendices A and C (HCM weather and incident capacity adjustment factors). [Background reference for HCM weather CAF framework; not the direct source for the composite JOSH hazard-degradation factors. Earlier versions of JOSH documentation cited FHWA Emergency Transportation Operations for the mobilization rate; that attribution was imprecise and has been corrected — the mobilization rate is now sourced to NFPA 1660 / NFPA 1616 per the Fire Science Consulting LLC review of May 2026.]

12. Roberson, B.S., Peterson, D., and Parsons, R.W. *Attitudes on wildfire evacuation: Exploring the intended evacuation behavior of residents living in two Southern California communities.* J. Emergency Management 10(5), 335-347, 2012. *(Empirical California validation of the 0.90 mobilization rate magnitude.)*

13. California State Fire Marshal. *2025 California Wildland-Urban Interface Code (CWUIC).* California Building Standards Commission, 2025 (adopting IWUIC 2024 with California amendments). *(Operative California WUI code; CCR 1273.00 concurrent civilian/apparatus access requirement; CWUIC Appendix C §C101.6 screening-tool framing.)*

14. Fire Science Consulting LLC (Ziazi, R., and Simeoni, A.). *JOSH ΔT Methodology: Standards Citation Analysis — Preliminary Technical Assessment.* Prepared for California Stewardship Alliance, May 26, 2026.
10. Federal Emergency Management Agency (FEMA). *Comprehensive Preparedness Guide 101, Version 2.0.* FEMA, 2010.
11. Link, E.D. & Maranghides, A. *Burnover Events Identified During the 2018 Camp Fire.* NIST, 2022.
12. KLD Engineering, P.C. *Evacuation Route Safety, Capacity, and Viability Analysis — AB 747 Requirement.* City of Berkeley, TR-1381. March 7, 2024.
13. Boeing, G. *OSMnx: New Methods for Acquiring, Constructing, Analyzing, and Visualizing Complex Street Networks.* Computers, Environment and Urban Systems, 65, 126–139, 2017.
14. International Fire Code (IFC). §503, Fire Apparatus Access Roads. International Code Council.
15. American Association of State Highway and Transportation Officials (AASHTO). *A Policy on Geometric Design of Highways and Streets.* Current edition.
16. Roberson, C., Dionne, C., Demeter, N., and Balch, R. (2012). "Attitudes on wildfire evacuation: Exploring the intended evacuation behavior of residents living in two Southern California communities." *Journal of Emergency Management*, 10(5), 335–346. [Primary source for behavioral_mobilization = 0.90: 82.6% stated likely/sure evacuation under mandatory order in CA High Fire Hazard Area.]
17. Zhao, X., Xu, Y., Lovreglio, R., Kuligowski, E., Nilsson, D., Cova, T., Wu, A., and Yan, X. (2022). "Estimating wildfire evacuation decision and departure timing using large-scale GPS data." *Transportation Research Part D*, 107, 103277. https://doi.org/10.1016/j.trd.2022.103277 [GPS-observed compliance ~46% in 2019 Kincade Fire; supports conservative framing of 0.90 design value.]
18. Wu, A., Yan, X., Kuligowski, E., Lovreglio, R., Nilsson, D., Cova, T., Xu, Y., and Zhao, X. (2022). "Wildfire evacuation decision modeling using GPS data." *International Journal of Disaster Risk Reduction*, 83, 103424. https://doi.org/10.1016/j.ijdrr.2022.103424 [GPS-observed mean block-group compliance 47.6% in 2019 Kincade Fire.]
19. California Governor's Office of Planning and Research (OPR). *Draft Evacuation Planning Technical Advisory.* State of California, 2024. [Supports use of documented planning assumptions in California evacuation clearance-time analysis.]

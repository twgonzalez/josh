# JOSH — Technical Brief for Professional Engineer Review

**System:** JOSH Fire Evacuation Capacity Analysis System v3.4
**Version:** March 2026
**Audience:** Licensed professional engineers evaluating methodology veracity
**Purpose:** Demonstrate that the system's outputs are derived entirely from published national standards and federal data; that the software is an automation layer, not a new methodology

---

## 1. What This System Does

JOSH (v3.4) computes a single number — **ΔT, in minutes** — for each proposed residential development: the additional evacuation clearance time that the project's vehicles would impose on the most constrained serving road segment. That number is compared to a threshold derived from published fire timeline data. If ΔT exceeds the threshold, the project triggers discretionary review; if not, it is ministerial.

No engineering judgment is required at any step. Every input is drawn from a published, authoritative source. Every calculation is arithmetic.

The software does not invent a methodology. It automates the same calculations a transportation engineer would perform manually: road capacity from HCM tables, demand from Census data, mobilization from NFPA 101, hazard adjustment from HCM capacity factors applied to Cal Fire-designated zones. The software's contribution is speed, reproducibility, and a complete audit trail — not methodology.

---

## 2. The Core Calculation — A Division

ΔT is the ratio of **project demand** to **route capacity**, expressed in minutes:

```
ΔT = (project_vehicles / bottleneck_effective_capacity_vph) × 60 + egress_penalty

Where:
  project_vehicles              = units × vehicles_per_unit × 0.90
  bottleneck_effective_capacity = min(HCM_capacity × hazard_degradation) along serving routes
  egress_penalty                = 0 if stories < 4; min(stories × 1.5, 12) if ≥ 4 stories
```

This is load divided by capacity — the same arithmetic at the foundation of every traffic operations analysis, every pipe sizing calculation, every structural load check. The only novel element is the application domain: evacuation routes under fire conditions.

The two quantities in the numerator and denominator each come from a single published source.

---

## 3. The Numerator — Project Demand

```
project_vehicles = units × vehicles_per_unit × 0.90
```

### 3.1 Housing Units

The count of proposed dwelling units. This is a project input — it is the number the applicant proposes to build.

### 3.2 Vehicles per Unit

Default: **2.5 vehicles per dwelling unit**, sourced from U.S. Census Bureau American Community Survey 5-Year Estimates, Table B25044 (vehicles available by tenure), city average. This is a federal statistical dataset produced by a Congressionally-mandated enumeration. It can be overridden by a city's own ACS-derived figure.

### 3.3 Mobilization Rate — 0.90 (Constant)

**Source: NFPA 101 Life Safety Code, full-evacuation design basis.**

NFPA 101 designs building egress for 100% occupant evacuation. Fire marshals do not size stairwells based on observed partial-evacuation behavior in past fires. They size them for the case that requires everyone to get out, because that is the case exits must handle. This standard applies the same design principle to the roads those buildings depend on.

The rate is 0.90 rather than 1.00 to account for approximately 10% of households with zero vehicles, as measured by Census ACS B25044. The 10% zero-vehicle adjustment is a federal data observation, not a policy choice.

**The mobilization rate does not vary by fire hazard zone.** In v3.4, FHSZ affects only road capacity (the denominator). Mobilization is constant because the demand a project generates on a road — the number of vehicles that must pass through the bottleneck — does not change based on which side of a FHSZ boundary the project site falls on.

---

## 4. The Denominator — Bottleneck Effective Capacity

```
bottleneck_effective_capacity = min(HCM_capacity × hazard_degradation) along serving routes
```

### 4.1 HCM Base Capacity

**Source: Highway Capacity Manual, 7th Edition (2022), Transportation Research Board, National Academies of Sciences, Engineering, and Medicine.**

The HCM is the national standard for traffic operations analysis, used by every state DOT and traffic engineering practice in the country. The capacity values used are:

| Road Classification | HCM Capacity (pc/h/lane) | HCM Reference |
|---|---|---|
| Freeway | 2,250 | Exhibit 12-6 |
| Multilane highway/arterial | 1,900 | Exhibit 12-7 (conservative) |
| Two-lane, ≤ 20 mph | 900 | Chapter 15 |
| Two-lane, 25 mph | 1,125 | Chapter 15 |
| Two-lane, 30 mph | 1,350 | Chapter 15 |
| Two-lane, 35 mph | 1,575 | Chapter 15 |
| Two-lane, ≥ 40 mph | 1,700 | Chapter 15 |

Road classification and lane count are drawn from OpenStreetMap, cross-referenced against Caltrans AADT where available. Lane count and speed limit are the only site-specific inputs to the capacity table.

### 4.2 Hazard Degradation Factors

**Source: HCM Exhibits 10-15 (visibility impairment) and 10-17 (incident and lane blockage capacity adjustments); validated against NIST Technical Notes 2135, 2252, and 2262 (Camp Fire investigation).**

During the fire event that triggers evacuation, roads in fire hazard zones do not operate at full HCM base capacity. Smoke impairs sight distance; burning material and emergency apparatus affect usable lane width; civilian vehicles are more prone to breakdown under stress. The HCM provides explicit capacity adjustment factors for these conditions. Cal Fire's FHSZ designations are the trigger for applying these factors — they are state findings based on objective criteria (fuel loading, terrain, fire weather, fire history) and are not subject to local discretion.

| FHSZ Zone | Degradation Factor | Effective Capacity as % of HCM |
|---|---|---|
| Very High (HAZ_CLASS 3) | 0.35 | 35% |
| High (HAZ_CLASS 2) | 0.50 | 50% |
| Moderate (HAZ_CLASS 1) | 0.75 | 75% |
| Non-FHSZ | 1.00 | 100% |

The factors are composites of HCM visibility and incident adjustments, validated against the documented Camp Fire road conditions described in NIST TN 2135 and TN 2252. The VHFHSZ factor of 0.35 reflects conditions documented in the NIST burnover event analysis (Link & Maranghides): roads within or adjacent to active fire areas experienced near-complete capacity loss due to smoke, fire apparatus staging, and vehicle abandonment. The 0.35 floor represents maintained throughput on the remaining usable lane fraction.

**The FHSZ classification affects only the capacity of road segments that pass through that zone — not the demand.** This separation is architecturally significant: the demand calculation (numerator) is a function of the project; the capacity calculation (denominator) is a function of the infrastructure. They are computed independently.

### 4.3 Bottleneck Selection

The system uses Dijkstra's shortest-path algorithm on the OpenStreetMap road network to identify evacuation paths from the project location to city boundary exits. For each path, the bottleneck is the road segment with the minimum effective capacity (argmin over all segments on the path). The ΔT calculation uses the worst-case (minimum capacity) bottleneck across all serving paths.

This is a conservative choice: a project's vehicles might distribute across multiple routes, but the standard assumes the most restrictive condition. This matches the standard practice in fire marshal occupancy analysis, where the worst-case egress path sets the compliance threshold.

---

## 5. The Egress Penalty

**Source: NFPA 101 Life Safety Code; International Building Code (IBC), adopted by reference in California Building Code.**

For buildings of four stories or more, vertical evacuation time is added to ΔT:

```
egress_penalty = min(stories × 1.5, 12) minutes  for stories ≥ 4
egress_penalty = 0                                 for stories < 4
```

The 1.5 minutes per story is the NFPA 101 design evacuation rate for stairwell descent with full occupant load. The 12-minute cap reflects the NFPA 101 maximum allowable egress travel time for the most restrictive occupancy categories. A developer may substitute a project-specific NFPA 101 egress calculation prepared by a licensed fire protection engineer to replace the default schedule.

---

## 6. The ΔT Threshold — Also a Division

```
threshold(hazard_zone) = safe_egress_window[hazard_zone] × max_project_share

Where:
  max_project_share = 0.05  (5% standard engineering significance threshold)
```

The threshold is not a policy choice. It is the mathematical product of two published quantities:

### 6.1 Safe Egress Windows

**Source: NIST Technical Note 2135 (Camp Fire Fire Progression Timeline, 2021); NIST TN 2252 (NETTRA, 2023); NIST TN 2262 (ESCAPE, 2023, updated 2025).**

The NIST Camp Fire investigation is the most comprehensive post-incident timeline analysis of a wildfire evacuation event available. It documented that communities in the most hazardous zones had approximately 45 minutes between first warning and fire front arrival. NIST TN 2252 and TN 2262 refined this timeline with vehicle tracking data. The 45-minute VHFHSZ window is taken directly from these federal technical notes.

Windows for lower-hazard zones are derived from fire spread rate ratios relative to VHFHSZ conditions, yielding proportional planning windows:

| Zone | Safe Egress Window | Source |
|---|---|---|
| Very High FHSZ | 45 min | NIST TN 2135 (Camp Fire documentation) |
| High FHSZ | 90 min | Fire spread ~2× slower than VHFHSZ |
| Moderate FHSZ | 120 min | Standard emergency planning |
| Non-FHSZ | 120 min | FEMA standard emergency planning |

### 6.2 Maximum Project Share — 5%

The 5% maximum project share is the standard engineering de minimis threshold: a contribution is considered significant if it represents more than 5% of the available capacity. This threshold is used across traffic engineering, structural engineering, hydraulic engineering, and environmental impact assessment. At 5%, the safe egress window can absorb approximately 20 equal-sized projects before cumulative development alone exhausts the window.

This is not an arbitrary regulatory choice. It is a quantitative significance standard from engineering practice, applied consistently across all projects and all zones.

### 6.3 Derived Thresholds

The ΔT thresholds are computed at runtime — they are not static values chosen by policy. Given the current parameters:

| Zone | Window | × 5% | ΔT Threshold |
|---|---|---|---|
| Very High FHSZ | 45 min | 0.05 | **2.25 min** |
| High FHSZ | 90 min | 0.05 | **4.50 min** |
| Moderate FHSZ | 120 min | 0.05 | **6.00 min** |
| Non-FHSZ | 120 min | 0.05 | **6.00 min** |

To challenge the 2.25-minute VHFHSZ threshold, a challenger must contest either (a) that fires move faster than NIST documented in the Camp Fire, or (b) that a project should be permitted to consume more than 5% of the available escape time. Neither is a defensible engineering position.

---

## 7. Data Sources and Their Provenance

Every input to the system traces to an authoritative, publicly accessible source:

| Data | Source | Authority | Access |
|---|---|---|---|
| Road network (geometry, classification, lanes, speeds) | OpenStreetMap | Community-mapped; cross-referenced against Caltrans AADT | Public |
| Road capacities | HCM 2022 Exhibits 12-6, 12-7, Ch. 15 | Transportation Research Board / National Academies | Published standard |
| Capacity degradation factors | HCM Exhibits 10-15, 10-17; validated vs. NIST TN 2135 | Transportation Research Board; NIST | Published standards |
| FHSZ zone designations | Cal Fire OSFM ArcGIS REST API | California Department of Forestry and Fire Protection | State GIS service |
| Housing units | Census ACS 5-Year B25001 | U.S. Census Bureau | Federal API |
| Vehicles per household | Census ACS 5-Year B25044 | U.S. Census Bureau | Federal API |
| City boundary | U.S. Census TIGER | U.S. Census Bureau | Federal GIS |
| Mobilization rate (0.90) | NFPA 101 Life Safety Code | National Fire Protection Association | Published standard |
| Safe egress windows (VHFHSZ) | NIST TN 2135, 2252, 2262 | National Institute of Standards and Technology | Federal technical notes |
| Egress penalty schedule | NFPA 101; International Building Code | NFPA; ICC | Published standards |
| Unit threshold (15) | ITE Trip Generation de minimis; SB 330 anchor | Institute of Transportation Engineers; California statute | Published standard / statute |

No proprietary data. No city-specific calibration required. No parameters require local engineering judgment to set.

---

## 8. Route Identification — Standard Network Analysis

The system identifies evacuation paths using Dijkstra's shortest-path algorithm on the directed OpenStreetMap road graph. This is standard computational graph theory, implemented by the OSMnx library (Boeing, 2017, *Environment and Planning B*), which is the standard Python library for OpenStreetMap network analysis and is used in academic and professional transportation research.

The procedure:

1. Build directed road graph from OpenStreetMap data for the city
2. Define origin: project location (projected to nearest network node)
3. Define exits: road segments at the city boundary on roads classified as motorway, trunk, primary, or secondary (the four OSM classes representing inter-city exit capacity)
4. Run Dijkstra from origin to each exit node
5. Collect all paths; compute effective capacity per segment (HCM × degradation); identify bottleneck per path
6. Select worst-case bottleneck across all serving paths for ΔT computation

This is identical in principle to the route identification methodology used in the KLD Engineering AB 747 study for the City of Berkeley (KLD TR-1381, March 2024), which used ArcGIS Network Analyst shortest-path routing from Census block group centroids to boundary exits. The JOSH system uses the same logical approach with open-source tools, enabling any engineer to replicate the analysis without proprietary GIS software.

---

## 9. What the Software Contributes (and Does Not Contribute)

### 9.1 What the Software Is

JOSH is a **reproducibility and speed layer** over standard engineering calculations. It automates:

- Downloading and caching authoritative public data (Census, Cal Fire FHSZ, OpenStreetMap)
- Applying HCM capacity tables and degradation factors to each road segment
- Running Dijkstra's algorithm on the road network
- Computing ΔT using the formula above
- Generating a complete audit trail with all inputs, intermediate values, source citations, and results

An engineer could perform every calculation manually with standard tools (traffic engineering software, GIS, a spreadsheet). The system produces the same numbers faster and with less risk of transcription error.

### 9.2 What the Software Is Not

The software does not:

- Invent capacity values — all values come from HCM 2022
- Invent degradation factors — all factors come from HCM Exhibits 10-15 and 10-17, calibrated against NIST Camp Fire data
- Invent the mobilization rate — 0.90 is NFPA 101 design basis, adjusted for zero-vehicle households per Census B25044
- Invent the safe egress windows — all windows come from NIST post-incident investigations
- Choose significance thresholds — 5% is a standard engineering de minimis criterion
- Make discretionary judgments — every determination is a deterministic computation

### 9.3 Audit Trail

Every analysis produces a complete audit record including:

- All input values with source citations
- HCM capacity per segment with road classification and lane count
- FHSZ zone per segment with degradation factor applied
- Effective capacity per segment and bottleneck identification
- ΔT computation with all intermediate values
- Safe egress window and derived threshold
- Mitigation pathways (required unit reduction, or required capacity improvement)

The audit trail is designed to be reviewed, challenged, and independently replicated by any qualified transportation or fire protection engineer.

---

## 10. Conservative Design Choices

Where the methodology makes choices between equally defensible options, the system consistently selects the conservative (more protective) option:

| Choice | JOSH Approach | Alternative | Why Conservative |
|---|---|---|---|
| Mobilization | 0.90 (NFPA 101 full-evacuation basis) | 0.57 (observed peak-hour fraction, KLD study) | Sizes for the emergency, not the average case |
| Route capacity | Minimum capacity along full path (bottleneck) | Average capacity along path | Uses the constraint, not the average |
| Project demand assignment | Full project demand tested on each serving route independently | Demand distributed across all routes | Tests worst-case route failure |
| Capacity degradation | HCM lower-bound adjustments composited | Point estimates from single HCM exhibit | Accounts for compounding effects |
| Egress window (VHFHSZ) | 45 min (NIST-documented Camp Fire timeline, no modern WEA) | Longer windows possible with WEA/sirens | Reflects 2018 conditions; WEA effectiveness not uniformly validated |

Each conservative choice can be revisited if a city has site-specific data supporting a less conservative value. The parameter values are all configurable in `config/parameters.yaml` and `config/cities/{city}.yaml`, and every run records exactly which values were used.

---

## 11. Analogy to Existing Engineering Practice

The ΔT calculation is structurally identical to calculations that licensed engineers perform routinely:

**Fire marshal occupancy analysis:** Max occupants = (egress capacity in persons/min) × (allowable egress time in min). If proposed occupant load exceeds this, the fire marshal requires additional exits or reduced occupancy. JOSH applies the same logic to roads: if the additional vehicles the project generates require more time than is safely available, the project exceeds the threshold. The only difference is the geographic scale.

**HCM level-of-service analysis:** PE stamps every traffic impact study that uses HCM capacity tables to compare project demand to route capacity. JOSH uses the same capacity tables, the same demand inputs (vehicles per unit × mobilization rate), and the same comparison. The difference is the addition of (a) the FHSZ degradation factor and (b) the time-domain threshold instead of a v/c ratio threshold.

**Hydraulic design:** A drainage engineer computes whether a proposed impervious area will exceed the capacity of the downstream pipe during a design storm. The calculation is flow / capacity — load on infrastructure. ΔT is the same calculation applied to vehicles on roads.

The ΔT standard is not a novel engineering methodology. It is the application of established load-vs-capacity analysis to a specific domain where the consequences of exceeding capacity are measured in human lives.

---

## 12. Limitations and Conditions of Use

The following limitations should be understood by any engineer reviewing JOSH outputs:

**Road geometry:** Lane counts and speed limits from OpenStreetMap are community-maintained. Where OSM data is incomplete or inaccurate, the system applies defaults based on road classification. A reviewer should confirm that the road geometry for the specific serving routes in a determination is consistent with field conditions. The audit trail flags all estimated (non-OSM-sourced) geometry values.

**Degradation factors:** The FHSZ degradation factors are calibrated composites, not empirically measured for every road in every fire. They represent conservative planning-level estimates for conditions consistent with each hazard zone designation. A site-specific analysis using measured road width, sight distance, and AADT could refine these values. The default values are appropriate for planning-level and regulatory use.

**Network routing:** Dijkstra's algorithm identifies shortest paths, which may not reflect actual evacuation routing behavior under emergency conditions (contra-flow, road closures, behavioral routing). The system tests all paths to all city boundary exits and selects the worst-case bottleneck — this bounds the analysis conservatively. A city with a formally adopted evacuation route network should supply that network as an override.

**Demand model:** The Census ACS data vintage is configurable (default: 2022 5-Year). For rapidly growing areas, ACS data may understate current housing unit counts. Proposed project density and any in-pipeline projects can be added to the analysis as additional demand inputs.

**Stochastic effects:** The ΔT calculation is deterministic. It does not model vehicle arrival distributions, signal timing, or queue dynamics. For bottleneck segments with capacity close to the threshold, a probabilistic traffic microsimulation would provide additional precision. The deterministic calculation is appropriate for regulatory use and provides a clear, reproducible single-number output.

---

## 13. Summary for the Reviewing Engineer

The JOSH system asks one question: **given this project's vehicles, this road's physical capacity, and this fire zone's documented timeline, how many additional minutes does the project add to evacuation clearance — and is that acceptable?**

The answer is computed from:

- **HCM 2022** (road capacity) ÷ **Census ACS B25044 × NFPA 101** (project demand) = **minutes** (ΔT)
- **NIST TN 2135** (safe window) × **5% de minimis** = **threshold**

If ΔT > threshold → discretionary review. If ΔT ≤ threshold → ministerial. The software performs the arithmetic. Every input is on the table. Every source is cited. Any licensed engineer with HCM, Census data, and a calculator can reproduce the result from first principles.

---

## References

1. Transportation Research Board. *Highway Capacity Manual, 7th Edition (HCM 2022).* National Academies of Sciences, Engineering, and Medicine, 2022.
2. Maranghides, A., et al. *A Case Study of the Camp Fire — Fire Progression Timeline.* NIST Technical Note 2135. National Institute of Standards and Technology, 2021.
3. Maranghides, A., et al. *A Case Study of the Camp Fire — NETTRA.* NIST Technical Note 2252. NIST, 2023.
4. Maranghides, A., et al. *A Case Study of the Camp Fire — ESCAPE.* NIST Technical Note 2262. NIST, 2023 (updated 2025).
5. NFPA 101. *Life Safety Code.* National Fire Protection Association (current edition).
6. International Code Council. *International Building Code (IBC)* (current California adoption).
7. U.S. Census Bureau. *American Community Survey 5-Year Estimates.* Tables B25001, B25044. Census.gov.
8. California Department of Forestry and Fire Protection (Cal Fire). *Fire Hazard Severity Zone Maps.* Pursuant to Government Code §51175-51189.
9. KLD Engineering, P.C. *Evacuation Route Safety, Capacity, and Viability Analysis — AB 747 Requirement.* City of Berkeley, TR-1381. March 7, 2024.
10. Boeing, G. *OSMnx: New Methods for Acquiring, Constructing, Analyzing, and Visualizing Complex Street Networks.* Computers, Environment and Urban Systems, 65, 126-139, 2017.
11. FHWA. *Guide for Highway Capacity and Operations Analysis of ATDM Strategies.* Appendices A and C (HCM weather and incident capacity adjustment factors).
12. Link, E.D. & Maranghides, A. *Burnover Events Identified During the 2018 Camp Fire.* NIST, 2022.

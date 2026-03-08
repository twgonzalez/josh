# Fire Evacuation Capacity Analysis — Legal Basis and Algorithmic Defense

**System:** Fire Evacuation Capacity Analysis System
**Version:** 2.0 (multi-scenario)
**Jurisdiction:** California (adaptable to other states with equivalent statutes)
**Audience:** City attorneys, planning directors, and technical experts

---

## 1. What This System Does

This system answers one question: *Does this proposed housing project require discretionary review, or can it be approved ministerially?*

It does so by applying city-adopted thresholds to city-adopted formulas using publicly verifiable data. The same inputs always produce the same result. No city official exercises judgment — the algorithm decides.

**Outputs:**
- A three-tier determination: **DISCRETIONARY** / **CONDITIONAL MINISTERIAL** / **MINISTERIAL**
- A complete audit trail of every input, calculation, and output
- A step-by-step record for each scenario evaluated

**Not outputs:**
- Engineering judgment
- Discretionary findings
- CEQA significance determinations (outputs may inform one, but do not constitute one)

---

## 2. The Five-Step Algorithm

Every project evaluation runs the same five steps in order. Steps and logic are identical across all scenarios — only the parameter values differ, and those are adopted by the city before any project is submitted.

This matters legally: a challenger cannot point to a code path where one project received different logical treatment than another.

---

### Step 1 — Does this scenario apply?

> *Is this hazard scenario relevant to this project and this city?*

The check is a fixed geographic or categorical test (details in §4 and §5). It returns yes or no. If no, the scenario returns **NOT_APPLICABLE** and stops — the project is not penalized, the scenario simply doesn't apply.

**Discretion: zero.**

---

### Step 2 — Is the project large enough?

> *Does the project meet the minimum size threshold?*

```
dwelling_units >= unit_threshold   (integer comparison; default: 15)
```

If the project is below the threshold, it receives **MINISTERIAL** treatment for this scenario. No capacity analysis is run. This prevents regulatory burden on small infill projects whose vehicle contribution is statistically indistinguishable from background traffic variation.

**Discretion: zero.**

---

### Step 3 — Which roads are analyzed?

> *What road segments serve this project for evacuation purposes?*

The system draws a buffer of a city-adopted radius around the project and intersects it with the scenario-specific road filter (evacuation routes for Scenario A; local streets for Scenario B). The result is a list of road segment IDs.

**Discretion: zero.** Buffer radius and road type filter are city-adopted parameters.

---

### Step 4 — How many vehicles does the project add?

> *What is the project's peak-hour vehicle load?*

```
project_vph = dwelling_units × vehicles_per_unit × peak_hour_mobilization
            = dwelling_units × 2.5 × 0.57
```

Both factors come from external published sources:
- **2.5 vehicles/unit** — U.S. Census American Community Survey
- **0.57 mobilization rate** — KLD Engineering TR-1381, Berkeley AB 747 Study (March 2024, Figure 12)[^1]

**What the mobilization rate measures:** Not everyone evacuates the moment an order is issued — people take time to become aware, gather belongings, and get into their cars. Evacuation demand builds gradually, peaks, then tapers as most people have already left. The mobilization rate is the fraction of housing units generating vehicle trips during the *single worst hour* of the evacuation — the peak of that demand curve. A rate of 0.57 means 57 out of every 100 housing units are actively generating a trip simultaneously at that peak. Using 100% would be unrealistically conservative; using the empirically measured peak is the technically correct approach. A **higher** rate produces more vehicles per project and a stricter standard; a **lower** rate produces fewer vehicles and a more permissive standard.

**City-specific values:** Berkeley's 0.57 is derived from observed traffic counts during actual California wildfire evacuations. Other cities set their own factor based on available local data, using one of four documented sourcing options — from a local empirical study (strongest) to the OPR AB 747 state guidance range (0.40–0.75) to a conservative default with mandatory disclosure in every brief. The chosen value, its source, and a plain-English explanation are recorded in the city config and appear in every determination audit trail.[^1]

**Discretion: zero.**

---

### Step 5 — Does the project cause a route to fail?

> *Does adding this project's vehicles push any serving route over the capacity threshold?*

A route is flagged only when the project *itself* causes the crossing — not when the route was already failing before the project arrived:

```
FLAGGED when:  baseline_vc < 0.95  AND  proposed_vc >= 0.95

where: proposed_vc = (baseline_demand + project_vph) / capacity_vph
```

The full project vehicle load is tested against each serving route independently (worst-case marginal impact — the load is *not* divided by the number of routes).

Routes already failing at baseline are recorded in the audit trail but do **not** trigger DISCRETIONARY — the project didn't cause that failure.

**Discretion: zero.** Arithmetic comparison against a city-adopted threshold.

#### Why marginal causation (not baseline exceedance)?

Standard CEQA methodology: a project's impact is significant only when *the project itself* causes an adverse change. Flagging projects because roads were already congested would function as a categorical ban on infill — HCD would likely find this invalid under the Housing Accountability Act. The marginal test flags only the specific project that tips a route into failure.

#### Why 0.95?

0.95 is the precise LOS E/F boundary in HCM 2022 — the industry standard for road capacity analysis cited in Caltrans guidance, CEQA technical studies, and federal transportation planning. Using the exact published breakpoint ties the threshold to an established technical reference rather than a value chosen by the city. It is also the most permissive defensible threshold available at this level of service, making it harder to characterize as a categorical prohibition on infill.

---

### Aggregation — Most Restrictive Tier Wins

When multiple scenarios are evaluated, the most restrictive result controls:

```
DISCRETIONARY (3) > CONDITIONAL MINISTERIAL (2) > MINISTERIAL (1)
NOT_APPLICABLE is excluded from aggregation
```

A project receives ministerial approval only if no applicable scenario triggers a more restrictive tier. This mirrors how CEQA applies the most restrictive threshold across impact categories.

---

## 3. Why This Is Legally Defensible

### 3.1 It Is an Objective Standard

California law defines objective standards as those that involve "no personal or subjective judgment by a public official" (Gov. Code §65913.4, SB 35). The same definition governs AB 2011, SB 9, AB 2097, SB 79, and the broader ministerial/discretionary framework.

This system qualifies because every step is:
- **Quantitative** — v/c ratio, unit count, radius in miles
- **Free of judgment** — HCM formulas are arithmetic
- **Uniformly applied** — same algorithm, same parameters for every project

### 3.2 Uniform Application Is Provable, Not Just Asserted

Parameters are adopted by the city (a legislative act), not chosen by staff (an administrative act). The source code is the standard. Two projects with identical inputs will always produce identical outputs.

### 3.3 The Technical Basis Is Established

HCM 2022 capacity values are cited in Caltrans guidance, CEQA technical studies, and federal transportation planning — they are not the city's invention. The KLD Engineering mobilization rate (57%) is from an AB 747 study conducted for Berkeley by a licensed traffic engineering firm. Both are publicly available and independently verifiable.

### 3.4 The Audit Trail Is Complete and Reproducible

Every output includes a machine-generated record of all inputs, intermediate calculations, formulas, and parameter citations. A challenger can independently reproduce the result. An unreproducible result would be discretionary — this one is not.

### 3.5 Fire Zone Is Not the Gate

A project doesn't need to sit inside a fire hazard zone to affect evacuation capacity. FHSZ residents evacuating through a downtown arterial are affected equally regardless of where the project sits. The road math decides — not the fire zone designation.

Fire zone location is recorded as a **severity modifier** (it affects required conditions, not the tier). A small project in Zone 3 may still receive ministerial approval; a large project outside any fire zone may still trigger discretionary review.

---

## 4. Scenario A — Wildland Evacuation (Standards 1–4)

**Legal basis:** AB 747 — California Government Code §65302.15
**Effective:** January 1, 2022
**Mandate:** Local agencies with territory in Very High Fire Hazard Severity Zones must analyze evacuation route capacity and adopt objective development standards.

### Parameters

| Step | Standard | Parameter | Value | Source |
|------|----------|-----------|-------|--------|
| Step 2 | Standard 1 | Unit threshold | 15 dwelling units | ITE de minimis (15 units × 2.5 × 0.57 = 21.4 peak-hour trips); SB 330 (Gov. Code §65905.5) statutory scale anchor |
| Step 3 | Standard 2 | Route type | `is_evacuation_route == True` | Network analysis: all city block group centroids → city exits |
| Step 3 | Standard 2 | Search radius | 0.5 miles | City-adopted objective standard |
| Step 1 | Standard 3 | Project in FHSZ | GIS point-in-polygon | CAL FIRE FHSZ, HAZ_CLASS ≥ 2 — activates surge multiplier in Standard 4 |
| Step 5 | Standard 4 | V/C threshold | 0.95 | HCM 2022 exact LOS E/F boundary |

### Three-Tier Output

| Tier | When | Legal Basis |
|------|------|-------------|
| **DISCRETIONARY** | Scale met (Std 1) AND project causes a route to cross v/c 0.95 (Std 4) | AB 747 + HCM 2022 |
| **CONDITIONAL MINISTERIAL** | Scale met (Std 1) but no capacity exceedance — applies universally | General Plan Safety Element + AB 1600 nexus |
| **MINISTERIAL** | Project is below scale threshold (Std 1 not met) | Project below significance threshold |

---

## 5. Scenario B — Local Capacity Test (Standard 5 — SB 79)

**Status:** Active (`local_density.enabled: true` in `config/parameters.yaml`)

**Legal basis:**
- Gov. Code §65302(g) — General Plan Safety Element (evacuation route capacity)
- California Fire Code §503 — fire apparatus access road capacity
- SB 79 (2025) — cities may impose objective, non-discretionary health and safety standards on by-right projects if the standard is quantitative, uniformly applied, and adopted before the project application is submitted

### What This Scenario Asks

*Can the immediate neighborhood's residents and the proposed project's occupants simultaneously evacuate through the local street network in a structure fire or neighborhood emergency?*

This is distinct from Scenario A (citywide wildland routes). A project could pass Scenario A and fail Standard 5 — e.g., if local streets near the project are already saturated with nearby density.

### Parameters

| Step | Parameter | Value | Source |
|------|-----------|-------|--------|
| Step 1 | Applicability | `local_density.enabled == true` | Structure fires occur anywhere, not just FHSZ |
| Step 2 | Unit threshold | 15 dwelling units | Consistent with Scenario A (ITE de minimis; SB 330 statutory anchor) |
| Step 3 | Route type | Multilane and two-lane roads (freeways excluded) | Local egress roads only |
| Step 3 | Search radius | 0.25 miles | KLD Engineering quarter-mile methodology |
| Step 5 | V/C threshold | 0.95 | HCM 2022 exact LOS E/F boundary |

### Before Standard 5 Can Be Applied

The city must:
1. Adopt the standard in the General Plan Safety Element or Zoning Code **before** any SB 79 project application is submitted.
2. Set `local_density.enabled: true` in `config/parameters.yaml`.
3. Reference the technical methodology and parameter values in the adopting staff report.

The city attorney must confirm adoption timing satisfies SB 79's prior-adoption requirement.

---

## 6. Common Legal Challenges and Responses

### "This is discretionary, not objective."
Every step is arithmetic against a city-adopted threshold. Step 1 queries a polygon dataset. Step 2 is `units >= 15`. Step 3 is a GIS buffer. Step 4 is multiplication. Step 5 is `demand / capacity >= 0.95`. No city official exercises judgment at any step. The standard satisfies Gov. Code §65913.4.

### "The parameters are arbitrary."
No parameter was invented for this system:
- **0.95** — Exact LOS E/F boundary in HCM 2022, cited in Caltrans guidance and federal transportation planning.
- **15 units** — The minimum size at which peak-hour load (`15 × 2.5 × 0.57 = 21.4 vph`) exceeds the ITE Trip Generation Handbook de minimis of 10–15 peak-hour trips commonly applied in California traffic studies — the point at which a project's contribution is statistically distinguishable from background traffic variation. Statutory anchor: California's Housing Crisis Act (SB 330, Gov. Code §65905.5) applies heightened review protections to projects of 10+ units, establishing legislative recognition that 10+ unit projects have material scale; 15 is the first integer above the ITE de minimis that falls squarely within that class. Projects below 15 units — including all SB 9 duplexes and most ADUs — receive ministerial approval without analysis.
- **2.5 vehicles/unit** — U.S. Census ACS, the standard source for all trip generation studies.
- **0.57 mobilization rate** — The fraction of housing units generating vehicle trips simultaneously during the peak hour of evacuation, measured from observed traffic data during actual California wildfire evacuations. Source: KLD Engineering TR-1381, Berkeley AB 747 Study, March 2024, Figure 12. Other cities adopt their own factor using four documented sourcing options; the OPR AB 747 state guidance range is 0.40–0.75.[^1]
- **0.25-mile radius** — KLD Engineering quarter-mile buffer methodology (same study).

Every parameter has a published external source. The city adopts these values — it does not invent them.

### "This standard was applied retroactively."
Correct to flag — and this system does not do that. Outputs include the evaluation date. The adoption ordinance establishes the adoption date. The sequence (adoption → application → evaluation) is verifiable from the record.

### "The project isn't in a fire zone — evacuation standards don't apply."
Gov. Code §65302.15 requires analysis of citywide evacuation route capacity, not just routes within FHSZ boundaries. Any project anywhere in the city adds vehicles to the shared evacuation network. The capacity impact is measured, not presumed.

### "The data sources are unreliable."
All sources are published government datasets:
- **FHSZ** — CAL FIRE Office of State Fire Marshal ArcGIS REST API
- **Road network** — OpenStreetMap (used by Caltrans, FEMA, and state agencies)
- **Block groups / housing units** — U.S. Census Bureau TIGER/Line, ACS Table B25001
- **Employment** — U.S. Census LEHD LODES8

All data is cached with download timestamps. The `metadata.yaml` file in each city's data directory records the source URL and download date for every file. Cache TTL is 90 days.

### "Two projects got different results — this is inconsistent."
Consistent application means the same algorithm with the same parameters. Different results are correct when projects differ in size, location, or when the road network has changed between evaluations. The audit trail for each project is independently reproducible — show both trails and the difference in inputs explains the difference in results.

---

## 7. Prior Adoption Requirement

**This is the city attorney's responsibility, not this system's.**

For any standard produced by this system to withstand challenge, the city must:

1. Adopt the standard in an ordinance amending the General Plan Safety Element or Zoning Code.
2. Adopt it **before** the first project application to which the standard is applied.
3. Reference in the ordinance: the technical methodology (this system), the specific parameter values adopted, and the legal authority (AB 747 for Scenario A; Gov. Code §65302(g) + Fire Code §503 + SB 79 for Scenario B).
4. Direct staff to use this system for all evaluations and attach the full audit trail to every determination.

This system generates the audit trail for steps 3 and 4. Steps 1 and 2 are the city attorney's and council's work.

---

## 8. Key Statutes and Technical References

### California Statutes

| Statute | Subject | Relevance |
|---------|---------|-----------|
| Gov. Code §65302.15 | General Plan Safety Element — evacuation route capacity | AB 747 mandate; legal basis for Scenario A |
| Gov. Code §65302(g) | General Plan Safety Element — evacuation routes | Legal basis for Scenario B |
| Gov. Code §65913.4 | Objective standards definition (SB 35) | Defines "objective standard" for all ministerial approval laws |
| California Fire Code §503 | Fire apparatus access road capacity | Legal basis for local egress capacity standard |
| SB 79 (2025) | Transit-adjacent by-right housing | Objective health and safety standard carve-out for Scenario B |
| AB 1600 (Gov. Code §66000+) | Impact fee nexus | Basis for CONDITIONAL MINISTERIAL conditions |

### Technical References

| Document | Parameters Derived |
|----------|--------------------|
| Highway Capacity Manual, 7th Ed. (HCM 2022) | `capacity_vph` by road type; `vc_threshold = 0.95` (exact LOS E/F boundary) |
| KLD Engineering TR-1381, Berkeley AB 747 Study (March 2024) | `peak_hour_mobilization = 0.57`; `buffer_radius = 0.25 mi`; `employee_mobilization_day = 1.00` |
| U.S. Census ACS Table B25001 | Housing unit base; `vehicles_per_unit = 2.5` |
| U.S. Census LEHD LODES8 | Employee demand base |
| CAL FIRE FHSZ dataset (OSFM) | Scenario A applicability gate; fire zone severity modifier |

---

## 9. Parameter Table

All parameters live in `config/parameters.yaml` or `config/cities/{city}.yaml`. The city adopts these values; the algorithm is fixed.

| Parameter | Default | Config Key | Source | Adopted By |
|-----------|---------|------------|--------|------------|
| Unit threshold | 15 units | `determination_tiers.discretionary.unit_threshold` | ITE de minimis (21.4 vph); SB 330 (Gov. Code §65905.5) scale anchor | City council |
| V/C threshold | 0.95 | `determination_tiers.discretionary.vc_threshold` | HCM 2022 exact LOS E/F boundary | City council |
| Vehicles per unit | 2.5 | `vehicles_per_unit` | U.S. Census ACS | U.S. Census (city inherits) |
| Peak-hour mobilization | 0.57 | `peak_hour_mobilization` | KLD Engineering AB 747 study | City council |
| AADT peak-hour factor | 0.10 | `aadt_peak_hour_factor` | Standard traffic engineering practice | City council |
| Evacuation route radius | 0.5 mi | `evacuation_route_radius_miles` | City-adopted standard | City council |
| FHSZ trigger zones | [2, 3] | `fhsz.trigger_zones` | CAL FIRE zone classification | State (CAL FIRE) |
| Buffer demand radius | 0.25 mi | `demand.buffer_radius_miles` | KLD Engineering AB 747 methodology | City council |
| Employee mobilization (day) | 1.00 | `demand.employee_mobilization_day` | KLD Engineering AB 747 methodology | City council |
| Cache TTL | 90 days | `cache_ttl_days` | Operational parameter | City IT / planning dept. |
| Std 5 unit threshold | 15 units | `local_density.unit_threshold` | Consistent with Scenario A (ITE de minimis; SB 330 anchor) | City council |
| Std 5 V/C threshold | 0.95 | `local_density.vc_threshold` | HCM 2022 exact LOS E/F boundary | City council |
| Std 5 local radius | 0.25 mi | `local_density.radius_miles` | KLD Engineering quarter-mile | City council |
| Std 5 transit buffer | 2,640 ft | `local_density.transit_buffer_feet` | SB 79 — 0.5-mile transit definition | State (SB 79) |

---

## 10. Audit Trail

Every `evaluate` command produces `output/{city}/determination_{lat}_{lon}.txt`. This file is the legal record.

**Contents:**
1. **Project identification** — date, location, dwelling units, APN
2. **System identification** — version, algorithm name, legal.md reference
3. **Per-scenario record** — for each scenario:
   - Legal basis and tier result
   - Step 1: applicability check inputs and output
   - Step 2: unit count vs. threshold
   - Step 3: routes identified (radius, count, per-route v/c and LOS)
   - Step 4: demand calculation (formula + factor sources)
   - Step 5: per-route baseline and proposed v/c, flagged routes
4. **Final determination** — most restrictive tier, per-scenario summary, aggregation logic

**Sufficient for:**
- Planning commission staff reports
- Administrative appeal records
- Judicial review (Code of Civil Procedure §1094.5 mandamus standard)
- AB 1600 nexus documentation

The audit trail is machine-generated by the same code that produces the determination. It cannot be edited without re-running the algorithm.

---

[^1]: Cities set their own peak-hour mobilization factor using four documented legal defensibility options: **(A)** a local empirical study derived from observed evacuation traffic data (strongest — Berkeley's 0.57 uses this); **(B)** transfer from a comparable city's documented evacuation event, with geographic and demographic comparability on the record; **(C)** the OPR AB 747 state guidance range (0.40–0.75), selecting a conservative value within the range; or **(D)** a conservative default with mandatory disclosure language in every determination brief. The selected option, its full citation, and a plain-English explanation are recorded in the city config fields `mobilization_source`, `mobilization_citation`, and `mobilization_note`, and appear in every audit trail output. See `docs/city_onboarding.md` §2 — *Peak-Hour Mobilization Factor* for the complete sourcing protocol and YAML configuration templates.

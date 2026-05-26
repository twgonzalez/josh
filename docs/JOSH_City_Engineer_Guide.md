# City Engineer's Verification and Conditions Guide

California Stewardship — May 2026

**Prepared for city engineers responsible for verifying JOSH determinations, reviewing road classification inputs, and specifying road improvement conditions of approval**

------

## What This Guide Is For

JOSH produces a deterministic result from a deterministic formula. The city engineer's role is not to approve or reject the result — it is to verify that the inputs are correct and, where a project requires a road improvement condition, to specify what that improvement must achieve and how it will be confirmed.

This guide covers three engineering tasks. First: input verification — confirming that the road classification, lane count, speed, and FHSZ designation used in the analysis accurately reflect field conditions. Second: independent result verification — confirming the ΔT calculation by hand from the audit trail. Third: conditions of approval — specifying, bonding, and confirming road improvements that bring a Discretionary project into compliance with the standard.

A fourth topic — physical site access under IFC §503 — is addressed separately at the end of this guide. It is currently outside the ΔT calculation but is the engineering question most often raised alongside it.

The full methodology is documented in the Professional Engineer Technical Brief. This guide assumes familiarity with the HCM 2022 (Highway Capacity Manual, 7th Edition), NFPA 1660:2024 / NFPA 1616:2020 (community mass-evacuation framework, the operative source for the JOSH mobilization rate), NFPA 101 (Life Safety Code, 2024 California edition — used for the high-rise building-egress penalty only), the 2025 California Wildland-Urban Interface Code (CWUIC), and Cal Fire FHSZ designation criteria. It focuses on what the city engineer needs to do on a per-project basis rather than why the methodology works.

------

## The Verification Checklist

For each project that triggers the analysis, the city engineer should confirm the following before the determination is finalized:

1. **Road classification** — Does the highway type assigned to the bottleneck segment match the road's actual functional classification and physical characteristics?
2. **Lane count** — Is the lane count confirmed from city records or field observation, or is it estimated from the highway type?
3. **Speed limit** — Is the posted speed limit consistent with the value in the analysis?
4. **FHSZ assignment** — Does the project site parcel fall in the correct fire hazard zone? Is the bottleneck road segment correctly identified as passing through or outside that zone?
5. **Egress penalty** — Is the story count in the analysis consistent with the submitted plans?
6. **ΔT arithmetic** — Does the hand calculation match the JOSH output?

Items 1 through 3 require cross-checking the JOSH road inputs against city GIS data, official street classifications, and, for critical determinations, field observation. Items 4 through 6 are desk checks against the Cal Fire FHSZ viewer and the submitted application.

If any input is wrong, request a road data correction (described below) before the determination is finalized. Do not adjust inputs on a per-project basis — corrections must apply uniformly to all future analyses.

------

## Road Classification — The Most Important Input

The bottleneck's effective capacity is the product of its HCM base capacity and the applicable FHSZ degradation factor. The HCM base capacity is determined entirely by the road's highway type, lane count, and speed limit. Getting these right is the single most important verification step.

### How JOSH classifies roads

JOSH reads road network data from OpenStreetMap using the OSM `highway` tag. The tag values map to HCM road types as follows:

| OSM Tag | HCM Road Type | Base Capacity (pc/h/ln) |
|---|---|---|
| `motorway`, `trunk` | Freeway | 2,250 |
| `primary`, `secondary` | Multilane | 1,900 |
| `tertiary`, `residential`, `unclassified` | Two-lane (speed-dependent) | 900–1,700 |

For two-lane roads, the posted speed limit controls which row of the HCM two-lane capacity table applies:

| Posted Speed | Base Capacity (pc/h, both directions) |
|---|---|
| ≤ 20 mph | 900 |
| 25 mph | 1,125 |
| 30 mph | 1,350 |
| 35 mph | 1,575 |
| ≥ 40 mph | 1,700 |

The degradation factor for fire conditions, applied to all road segments that pass through or adjacent to a designated fire hazard zone, reduces effective capacity:

| FHSZ Designation | Degradation Factor | Effective Capacity Multiplier |
|---|---|---|
| Very High (VHFHSZ) | 0.35 | 35% of base |
| High | 0.50 | 50% of base |
| Moderate | 0.75 | 75% of base |
| None | 1.00 | 100% of base |

These factors are **composite engineering-judgment values** anchored against the HCM 2022 Chapter 11 weather Capacity Adjustment Factor framework (Exhibit 11-20, worst-case weather CAFs) and empirically validated against NIST Technical Note 2135 (Camp Fire timeline reconstruction, documented road burnovers on 3 of 5 evacuation routes), Rohaert et al. (2023) Kincade Fire traffic dynamics, and Wetterberg et al. (2022) smoke-visibility driving-speed empirical data. The underlying derivation is subject to independent traffic-engineering review (Fire Science Consulting LLC, Ziazi & Simeoni, May 2026; open item on the JOSH Methodology Roadmap). Earlier JOSH documentation cited HCM Exhibits 10-15 (Lane Closure Severity Index for work zones) and 10-17 (a photograph) as the direct source; those exhibits contain no fire, smoke, or visibility capacity values, and the attribution has been corrected. The composite scaling and the FHSZ-segment trigger are unchanged; only the citation is corrected.

### Common classification errors to check

**Over-classification of private roads.** Private roads in covenant communities, gated subdivisions, and fire district service areas are frequently tagged as `primary` or `secondary` in OSM — reflecting their physical scale rather than their functional classification. A private two-lane road serving a residential subdivision is a local collector, not a multilane arterial. Over-classification inflates the bottleneck capacity and may produce a passing result on a road that would fail under correct classification.

**Under-classification of improved arterials.** City-improved arterials that predate OSM coverage can be tagged as `tertiary` or `residential` when they physically operate as multilane collectors. Under-classification deflates capacity and may produce a failing result that does not reflect the road's actual throughput.

**Estimated lane counts.** Where OSM does not record an explicit lane count, JOSH infers lane count from the highway type (one lane per direction for two-lane roads, two lanes per direction for multilane). For roads where the actual lane count differs from the default — divided one-lane arterials, reversible lanes, bus-only lanes — the engineer should verify lane count from city striping records or field observation and request a correction if needed.

**Speed limit errors.** OSM speed data is incomplete in many jurisdictions. JOSH applies a speed estimate based on highway type where no speed tag is present. For two-lane roads, the difference between a 25 mph and 35 mph speed limit is a 40% difference in base capacity (1,125 vs. 1,575 pc/h). For bottleneck segments in a VHFHSZ zone, that difference propagates through the degradation factor and can be determinative.

### How to request a correction

Flag the error to the planning department with a written description of the discrepancy, the field-verified correct value, and the source (city GIS, signed plans, field observation, posted speed). Road data corrections are applied in the JOSH road override file for the city and take effect for all future analyses. They are not retroactive to already-issued determinations unless a project is re-analyzed.

Corrections are not made on a project-specific basis. A correction that applies only to one project's analysis is not a data correction — it is a discretionary adjustment, which the standard does not permit.

### Setting road capacity directly (`capacity_vph`)

In some cases, adjusting HCM inputs (lane count, speed limit, road type) is not sufficient to reflect actual road conditions. When a PE-stamped field count or a Caltrans TMC report establishes a bottleneck capacity that the HCM formula cannot reproduce — for example, because of unmodeled signal phasing, weave sections, or incident management — the city engineer may set `capacity_vph` directly in the road override file.

**When to use.** Use `capacity_vph` when you have a PE-stamped traffic study or agency count report that documents the actual peak-hour throughput on the bottleneck segment and that throughput differs materially from the HCM formula result. The standard example is a Caltrans TMC count showing sustained throughput below the HCM two-lane capacity due to a signalized intersection upstream of the segment.

**How to use.** Add `capacity_vph`, `reason`, and `source` to the segment's override entry in the city road override YAML, keyed by the OSM way ID (`osmid`). Both `reason` and `source` are required — an entry without them is invalid and will be skipped with a logged warning. Cite the PE stamp, report date, and agency in the `source` field:

```yaml
road_overrides:
  - osmid: "987654321"
    capacity_vph: 800
    reason: >
      Bottleneck confirmed at 800 vph by Caltrans peak-hour count (2024-08-15).
      HCM formula overestimates due to unmodeled signal interference.
    source: "Caltrans TMC count report 2024-08-15 (PE stamp: J. Smith, PE #12345)"
```

**What it does NOT do.** `capacity_vph` does not bypass FHSZ hazard degradation. The city-provided capacity is still multiplied by the FHSZ degradation factor to yield effective capacity. If the field count was conducted under fire-weather conditions and already reflects degraded throughput, document this in the `reason` field so the record is clear — but the degradation factor still applies.

**Audit trail.** The determination report will show `[city-provided]` in place of the HCM formula breakdown for that bottleneck, and will cite the source document. This is the authoritative record that a PE-verified value was used in place of the HCM formula.

------

## Verifying the ΔT Calculation by Hand

The JOSH audit trail contains every value needed to reproduce the ΔT result independently. The calculation is five arithmetic operations:

```
project_vehicles     = units × 1.9 × 0.90
bottleneck_capacity  = HCM_base_capacity × degradation_factor
delta_T_road         = (project_vehicles ÷ bottleneck_capacity) × 60
egress_penalty       = 0 if stories < 4; min(stories × 1.5, 12) if stories ≥ 4
ΔT                   = delta_T_road + egress_penalty
```

A five-row spreadsheet is sufficient. The audit trail states the unit count, the bottleneck road type, the posted speed, the FHSZ zone, and the story count. Cross-reference each against the classification tables above. If the hand calculation matches the audit trail result within rounding, the output is verified.

**What the two demand parameters represent.** The 1.9 factor is the Census ACS B25044 California statewide average vehicles per housing unit across *all* occupied households, including zero-vehicle households. Those households contribute zero vehicles to the numerator of that average, so they are already reflected in the 1.9 figure — no additional adjustment for zero-car households is applied. The 0.90 factor is the **community mass-evacuation mobilization rate sourced to NFPA 1660 (2024) / NFPA 1616 (2020)** — the national fire-protection standard for community-scale mass evacuation. The 0.90 magnitude is derived from the standard's full-evacuation design basis adjusted from 100% for the ~10% zero-vehicle household share in Census ACS B25044, with empirical California validation per Roberson et al. (2012). The two parameters cover separate concerns — vehicle ownership and community-scale evacuation design — and their product, 1.71 effective vehicles per unit, is the design demand rate. If a city overrides `vehicles_per_unit` with local ACS B25044 data to reflect a higher or lower vehicle ownership rate, `behavioral_mobilization` should not also be adjusted to account for zero-car households. Each parameter has one job. *(Earlier versions of this guide cited FHWA Emergency Transportation Operations as the source of the 0.90 figure; that attribution was imprecise and has been corrected per the Fire Science Consulting LLC review of May 2026.)*

### Example verification

A 60-unit, 5-story project on a two-lane, 30 mph road in a VHFHSZ zone:

```
project_vehicles     = 60 × 1.9 × 0.90                     = 102.6 vehicles
HCM base capacity    = 1,350 pc/h (two-lane, 30 mph)
degradation factor   = 0.35 (VHFHSZ)
bottleneck_capacity  = 1,350 × 0.35                         = 472.5 vph
delta_T_road         = (102.6 ÷ 472.5) × 60                 = 13.0 minutes
egress_penalty       = min(5 × 1.5, 12)                     = 7.5 minutes
ΔT                   = 13.0 + 7.5                           = 20.5 minutes
Threshold (VHFHSZ)   = 45 × 0.05                            = 2.25 minutes
Result               = DISCRETIONARY (20.5 > 2.25)
```

If the JOSH audit trail shows a materially different result and the inputs are consistent, contact the JOSH support contact to investigate. Rounding differences of less than 0.1 minutes are expected and do not require a correction.

------

## Conditions of Approval — Road Improvements

When a project is Discretionary because ΔT exceeds the threshold, the developer may elect to fund a road improvement to bring the bottleneck capacity up to the level required for a Conditional Ministerial determination. The city engineer's role is to specify what the improvement must achieve, confirm that it is physically achievable, and establish the bonding and inspection requirements.

### Calculating the required capacity

The required bottleneck effective capacity is the capacity at which the project's ΔT would equal the threshold:

```
required_capacity = (project_vehicles ÷ threshold_minutes) × 60
```

For the example above:

```
required_capacity = (102.6 ÷ 2.25) × 60 = 2,736 vph
```

The existing effective capacity is 472.5 vph (1,350 × 0.35). The gap is 2,263.5 vph. That gap cannot be closed by a road improvement alone at a 35% fire-condition degradation factor — the base capacity required to deliver 2,736 effective vph in a VHFHSZ zone would be 2,736 ÷ 0.35 = 7,817 pc/h, which exceeds freeway capacity. In this case, the road improvement path is not viable and the developer's only options are a unit reduction or a second independent egress route.

For a more constrained example — a 20-unit project in a VHFHSZ zone with ΔT = 4.0 minutes:

```
project_vehicles     = 20 × 1.9 × 0.90          = 34.2 vehicles
threshold            = 2.25 minutes
required_capacity    = (34.2 ÷ 2.25) × 60       = 912 vph
existing capacity    = 472.5 vph (1,350 × 0.35)
required base cap    = 912 ÷ 0.35               = 2,606 pc/h
```

A two-lane road cannot achieve 2,606 pc/h base capacity at any speed. But a multilane road (1,900 pc/h × 2 lanes = 3,800 pc/h base) would deliver 3,800 × 0.35 = 1,330 vph effective — above the 912 vph required. So widening the bottleneck from a two-lane to a four-lane cross-section would bring the project within the threshold.

### Specifying the improvement

The condition of approval must state:

1. The specific road segment to be improved (by official street name, from-to limits, and APN or parcel reference)
2. The physical improvement required (lane addition, shoulder widening, intersection modification — with reference to city engineering standards for lane width, pavement section, and striping)
3. The basis for the required improvement (the capacity calculation above, stated in the condition)
4. The timing requirement: **improvement must be complete, inspected, and accepted by the city before any building permit is issued for the project** — not before occupancy, not conditioned on future completion
5. The bonding requirement: the developer posts a performance bond covering the full estimated cost of the improvement at the time of project approval
6. The post-improvement re-analysis requirement: after the improvement is accepted, JOSH re-analyzes the project using the updated road data, and the Conditional Ministerial determination is issued only if the revised ΔT is within the threshold

Do not accept deferred improvement conditions. A road improvement that is conditioned on future construction creates an enforcement problem and does not protect the city's legal position — the determination is issued before the safety constraint is resolved.

### Improvement that benefits the public record

State in the condition and in the staff report that the road improvement will benefit all existing residents who depend on that route — not only the project's future occupants. This is both accurate and legally significant: it establishes that the developer's required contribution directly reduces evacuation risk for the existing community, which strengthens the nexus required for an AB 1600 impact fee analysis if the city later pursues that path.

------

## Physical Site Access — IFC §503

The ΔT calculation measures evacuation capacity at the network level — the road from the project to safety. It does not measure site-level access — the road from the street to the building's front door. These are two different constraints, and both matter.

The International Fire Code §503 establishes minimum standards for fire apparatus access roads:

| Condition | IFC §503 Minimum |
|---|---|
| One-way access road | 20 ft clear width |
| Two-way access road | 26 ft clear width |
| Dead-end road, no turnaround | Maximum 150 ft length serving > N units (city-adopted N) |
| Single access point | Flag for large projects per city-adopted threshold |

These are not JOSH standards — they are adopted fire code requirements that apply independently of the ΔT analysis. However, they become relevant alongside the ΔT analysis for projects that are large or on constrained access roads.

The city engineer should flag IFC §503 concerns alongside the JOSH determination when:

- The project's access road is below the minimum clear width for its traffic direction configuration
- The project is at the end of a dead-end street with no approved turnaround
- The project has a single access point and is above the city's threshold for requiring a secondary access

Road width data can be collected in city road surveys and recorded in the city's road override file for JOSH. Width data stored there is available for Standard 6 analysis when that methodology is formalized. In the interim, IFC §503 review proceeds through the normal fire code plan check process — the city engineer and fire marshal jointly review access road plans against the adopted fire code requirements.

Document IFC §503 concerns in the engineering conditions of approval separately from the JOSH determination. They are governed by different standards and should not be conflated in the record.

------

## Multi-Egress Projects

The current JOSH methodology identifies all evacuation paths within a 0.5-mile radius of the project and reports ΔT for each path independently. The binding result is the worst-case path. This is a conservative approach: it does not give credit for the fact that a project with two independent egress routes will split its vehicles across both routes during an evacuation.

Where a project has two genuinely independent egress routes — routes that reach different segments of the evacuation network through different road segments — the engineer should document both routes in the review notes. If the methodology is later updated to account for proportional vehicle splitting across independent routes, the documentation will support a re-analysis without requiring a new application.

For purposes of the current standard, the worst-case single-path result governs. The developer cannot argue that multi-egress credit applies unless the methodology explicitly permits it. If the developer raises this argument, note it in the record and refer to planning staff for a legal response.

A second driveway onto the same street is not a second egress route. Two connections to the same road segment produce the same bottleneck — they do not split the vehicle load across independent paths.

------

## When to Flag a Result for Manual Review

Flag the following conditions to planning staff before the determination is finalized:

**Road classification mismatch.** The bottleneck road is classified differently in JOSH than in the city's official GIS or functional classification map. Common in covenant communities, fire districts, and areas with recent road reclassifications.

**Estimated lane count or speed.** The audit trail shows that lane count or speed was estimated from the highway type rather than confirmed from a tagged value. For any determination that is Conditional Ministerial with ΔT close to the threshold, estimated values should be field-verified before issuance.

**Project address near a major network barrier.** Sites within 0.5 miles of a freeway, river, railroad, or other barrier may route through a different set of roads depending on which side of the barrier the geocoded address falls. Verify that the project location in the analysis matches the actual site entry point.

**FHSZ boundary near the site.** Where a parcel straddles or is immediately adjacent to an FHSZ boundary, a small error in the parcel geocode can change the zone assignment and therefore the threshold. Confirm the zone against the Cal Fire FHSZ viewer using the parcel APN.

**Very large projects near the threshold.** A project of 100 or more units with ΔT within 0.5 minutes of the threshold warrants input verification before the determination is finalized. The arithmetic is correct if the inputs are correct, but a misclassified lane count or speed limit at this scale can move the result across the threshold.

------

## Configuration & Overrides — What the City Engineer Can Set

JOSH provides four documented override surfaces. The road network override file (Surface 3 below) is the one most directly under the city engineer's authority and the most frequently used. The other three surfaces are described here for completeness so you understand the full picture when a developer, planner, or attorney asks "can the city change X?"

The IT Implementation Guide contains the same reference table from the IT perspective. This version frames the overrides around the engineering judgment they require.

### Override Surface Summary

| # | Surface | Engineer's role | Used for |
|---|---|---|---|
| **1** | Global parameter overrides | Reviewer / PE supporter | Adjust national-standard defaults (vehicles per unit, mobilization, hazard degradation) when documented local evidence supports a different value |
| **2** | City geographic configuration | Reviewer | Define boundary source, FHSZ data source, explicit evacuation exit nodes |
| **3** | Road network overrides | **Primary author** | Correct OSM classification errors, record physical road data, set PE-stamped direct capacity values |
| **4** | Project-level overrides | Reviewer of applicant-submitted egress studies | Project-specific PE-stamped applicant egress overrides |

**Override file paths:**

1. `config/cities/{city}.yaml` &mdash; the `overrides:` block at the bottom of the city config
2. `config/cities/{city}.yaml` &mdash; the top-level keys (`place_fips`, `fhsz_local_file`, `boundary_file`, `known_exit_nodes`, etc.)
3. `config/private/cities/{city}_road_overrides.yaml`
4. `config/projects/{city}_demo.yaml` &mdash; or a per-project YAML

### (1) Global Parameter Overrides — When the Engineer Supports

The city engineer rarely *authors* a parameter override, but a planning department or city attorney often *requires the engineer to support* one. The engineering question for each:

| Parameter | Default | Engineering review required |
|---|---|---|
| `vehicles_per_unit` | `1.9` (Census ACS B25044, CA statewide) | Confirm local ACS B25044 figure is current and that the difference from statewide is material (typically > 0.1 vph). |
| `behavioral_mobilization` | `0.90` (NFPA 1660 / 1616 community mass-evacuation design basis) | If the city seeks to lower this (less conservative), require PE-stamped supporting evidence: an adopted evacuation plan with a modeled compliance rate, a post-event traffic study, or a licensed transportation engineer's finding. Earlier docs cited FHWA Emergency Transportation Operations — that attribution has been corrected per the May 2026 FSC review; the rate itself (0.90) is unchanged. |
| `hazard_degradation.factors.{zone}` | `0.35 / 0.50 / 0.75` (composite engineering judgment; pending FSC review) | If the city seeks to *raise* a factor (less capacity loss = less conservative), require a PE-stamped engineering report citing the specific HCM 2022 Ch. 11 weather CAFs and the local fire-condition data supporting departure from the conservative composite. |
| `unit_threshold` | `15` (ITE de minimis / SB 330 anchor) | Lower thresholds may be adopted by staff without PE review. Raising requires PE certification (documented reason why projects below the city's adopted threshold should escape analysis). |
| `egress_penalty.threshold_stories` | `4` (NFPA 101 high-rise threshold, 75 ft) | A city with predominantly three-story new construction may lower this to 3 with documented building-stock characteristics. |
| `evacuation.exit_highway_types` | `[motorway, motorway_link, trunk, trunk_link, primary, primary_link]` | For cities without freeway access, the engineer designates the secondary or major-arterial road types that constitute the regional evacuation network. |
| `evacuation.max_path_length_ratio` | `3.5` (User Equilibrium cap) | Engineering judgment: a jurisdiction with documented multi-route compliance during past events may justify a different cap. PE certification recommended. |

**Override direction principle:** Any override that makes the standard *more conservative* (harder for projects to pass) may be applied by city staff without council action. Any override that makes the standard *less conservative* requires PE-stamped supporting evidence or formal council adoption.

### (2) City Geographic Configuration

The engineer's role here is generally to verify that the GIS sources are authoritative for the jurisdiction:

| Field | Engineering verification |
|---|---|
| `place_fips` | Confirm the Census PLACE code matches the jurisdiction (incorporated cities only). |
| `fhsz_local_file` / `fhsz_fallback_api` | For LRA jurisdictions, confirm the FHSZ data source is the authoritative county GIS or Cal Fire FRAP statewide layer clipped to the city boundary. Cal Fire's standard API returns SRA zones only and is insufficient for incorporated LRA cities. |
| `boundary_file` | For fire districts and other non-municipal jurisdictions, confirm the boundary GeoJSON is from the county LAFCO or equivalent authoritative GIS source. |
| `known_exit_nodes` | For clipped networks, identify primary regional exits (freeway ramps, trunk highway crossings) and verify OSM node IDs against the OSM iD editor. Each entry should include a comment with lat/lon and the road name. |

### (3) Road Network Overrides — The Engineer's Primary Authority

This is the override surface the city engineer authors directly. Every entry corrects an OSM classification error or records PE-verified physical or capacity data. Overrides apply uniformly to all future analyses — they are NOT project-specific (a project-specific adjustment would be a discretionary act, which the standard does not permit).

| Override field | Matches by | Effect | What the engineer must verify |
|---|---|---|---|
| `highway` | `name` or `osmid` | Reclassify OSM highway tag; the engine auto-re-derives road type and lane count | The road's actual functional classification (covenant road tagged primary, etc.) from city GIS or functional classification map |
| `lanes` | `name` or `osmid` | Set explicit lane count; clears the "estimated" flag | Lane count from city striping records or field observation |
| `speed` | `name` or `osmid` | Set posted speed limit (mph); clears the "estimated" flag | Posted speed limit |
| `width_ft` | `osmid` | Record physical road width in feet (audit-trail field; pending Standard 6 use) | Field measurement or signed plans |
| `access_type` | `osmid` | Record access classification: `dead_end` / `single_access` / `one_way` / `two_way` | Field observation or COA-mandated restriction |
| `capacity_vph` | `osmid` | **Set bottleneck capacity directly**, bypassing HCM. Effective capacity = `capacity_vph` × FHSZ degradation factor still applies. | **PE-stamped** field count or agency traffic study (e.g., Caltrans TMC report) showing peak-hour throughput that the HCM formula cannot reproduce. `reason` AND `source` (PE stamp, agency, report date) are both required — missing either is skipped with a logged warning. See "Setting road capacity directly" earlier in this guide for the detailed protocol. |
| `reason` | All entries | Required text field documenting why the override exists | The engineer's documented basis |
| `source` | Required for `capacity_vph` | Citation: PE stamp, report date, agency | The supporting document |
| `osm_correction_pending: true` | Optional flag | Indicates the correction should also be submitted upstream to OpenStreetMap | Engineer's assessment of whether the OSM data is wrong (vs. a correction that requires local knowledge not in OSM) |

**Audit trail.** Every overridden segment gains two columns in `roads.gpkg`: `highway_original` (the original OSM tag before correction) and `override_reason` (the reason string from the YAML). The number of corrected segments is logged at `analyze` time and recorded in `data/{city}/metadata.yaml` under `roads_overrides`.

**When to fix OSM upstream vs. use an override.** Fix in OSM first when the tag is clearly wrong (e.g., a residential cul-de-sac tagged as `primary`) — mark with `osm_correction_pending: true` in the YAML. Use overrides for corrections that require local knowledge not in OSM (physical widths, gated access, COA-mandated restrictions), or where OSM edits may be reverted. Never use overrides to tune ΔT results — only to correct factual OSM errors or add physically-verified data.

### (4) Project-Level Overrides — Applicant PE-Stamped Egress

When a project's egress penalty calculation governs the ΔT result and the developer submits a PE-stamped NFPA 101 egress study showing that the project-specific egress time is shorter than the default schedule (1.5 min/story up to 12 min cap), the applicant calculation may substitute for the default for that one project. The city engineer reviews the submitted egress study against NFPA 101 (Life Safety Code, 2024 California edition, Ch. 7) and IBC 2024 Ch. 10 (Means of Egress).

This is the only project-level override the city engineer typically encounters. All other project fields (`name`, `lat`, `lon`, `units`, `stories`, `geocode_address`) are factual inputs from the application, not engineering overrides.

### What Cannot Be Overridden

The following are not configurable — they are first-principles engineering or legal constants:

- The ΔT formula itself (`(project_vehicles / bottleneck_capacity) × 60 + egress_penalty`)
- The HCM 2022 base-capacity table (Ch. 12, Ch. 15) — these are the published national standard
- The 5% derivation of zone thresholds from `safe_egress_window × max_project_share`
- The User Equilibrium routing semantics (Dijkstra to all exit nodes, 3.5× cap) — adopted as the only objective routing rule consistent with HAA §65589.5(d)(5)

If a developer or attorney argues that one of these should change for their project, the engineer's answer is: that is a methodology amendment, not a project-specific adjustment, and the standard does not permit per-project changes. Document the request in the record and refer to planning staff for a legal response.

------

## Summary: The Engineer's Role in Each Determination

| Determination | Engineer Action |
|---|---|
| **Ministerial** (below 15 units) | No engineering review required under this standard. Normal fire code and engineering plan check applies. |
| **Conditional Ministerial** (passes ΔT) | Verify road classification, lane count, speed, and FHSZ zone against city records. Confirm ΔT arithmetic. Sign off on the determination or flag corrections before issuance. |
| **Discretionary** (fails ΔT) | Same verification as above. If the developer elects a road improvement path: calculate required capacity, confirm physical achievability, draft improvement condition with timing, bonding, and re-analysis requirements. |
| **Any determination** | Review for IFC §503 site access concerns. Document separately from JOSH determination. |

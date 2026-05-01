# City Engineer's Verification and Conditions Guide

California Stewardship Fund — May 2026

**Prepared for city engineers responsible for verifying JOSH determinations, reviewing road classification inputs, and specifying road improvement conditions of approval**

------

## What This Guide Is For

JOSH produces a deterministic result from a deterministic formula. The city engineer's role is not to approve or reject the result — it is to verify that the inputs are correct and, where a project requires a road improvement condition, to specify what that improvement must achieve and how it will be confirmed.

This guide covers three engineering tasks. First: input verification — confirming that the road classification, lane count, speed, and FHSZ designation used in the analysis accurately reflect field conditions. Second: independent result verification — confirming the ΔT calculation by hand from the audit trail. Third: conditions of approval — specifying, bonding, and confirming road improvements that bring a Discretionary project into compliance with the standard.

A fourth topic — physical site access under IFC §503 — is addressed separately at the end of this guide. It is currently outside the ΔT calculation but is the engineering question most often raised alongside it.

The full methodology is documented in the Professional Engineer Technical Brief. This guide assumes familiarity with the HCM 2022, NFPA 101, and Cal Fire FHSZ designation criteria, and focuses on what the city engineer needs to do on a per-project basis rather than why the methodology works.

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

These factors are drawn from HCM 2022 Exhibits 10-15 and 10-17 (capacity reduction for smoke-reduced visibility, incidents, and lane blockage during emergency conditions), composited against the NIST Camp Fire operational findings for VHFHSZ conditions.

### Common classification errors to check

**Over-classification of private roads.** Private roads in covenant communities, gated subdivisions, and fire district service areas are frequently tagged as `primary` or `secondary` in OSM — reflecting their physical scale rather than their functional classification. A private two-lane road serving a residential subdivision is a local collector, not a multilane arterial. Over-classification inflates the bottleneck capacity and may produce a passing result on a road that would fail under correct classification.

**Under-classification of improved arterials.** City-improved arterials that predate OSM coverage can be tagged as `tertiary` or `residential` when they physically operate as multilane collectors. Under-classification deflates capacity and may produce a failing result that does not reflect the road's actual throughput.

**Estimated lane counts.** Where OSM does not record an explicit lane count, JOSH infers lane count from the highway type (one lane per direction for two-lane roads, two lanes per direction for multilane). For roads where the actual lane count differs from the default — divided one-lane arterials, reversible lanes, bus-only lanes — the engineer should verify lane count from city striping records or field observation and request a correction if needed.

**Speed limit errors.** OSM speed data is incomplete in many jurisdictions. JOSH applies a speed estimate based on highway type where no speed tag is present. For two-lane roads, the difference between a 25 mph and 35 mph speed limit is a 40% difference in base capacity (1,125 vs. 1,575 pc/h). For bottleneck segments in a VHFHSZ zone, that difference propagates through the degradation factor and can be determinative.

### How to request a correction

Flag the error to the planning department with a written description of the discrepancy, the field-verified correct value, and the source (city GIS, signed plans, field observation, posted speed). Road data corrections are applied in the JOSH road override file for the city and take effect for all future analyses. They are not retroactive to already-issued determinations unless a project is re-analyzed.

Corrections are not made on a project-specific basis. A correction that applies only to one project's analysis is not a data correction — it is a discretionary adjustment, which the standard does not permit.

------

## Verifying the ΔT Calculation by Hand

The JOSH audit trail contains every value needed to reproduce the ΔT result independently. The calculation is five arithmetic operations:

```
project_vehicles     = units × 2.5 × 0.90
bottleneck_capacity  = HCM_base_capacity × degradation_factor
delta_T_road         = (project_vehicles ÷ bottleneck_capacity) × 60
egress_penalty       = 0 if stories < 4; min(stories × 1.5, 12) if stories ≥ 4
ΔT                   = delta_T_road + egress_penalty
```

A five-row spreadsheet is sufficient. The audit trail states the unit count, the bottleneck road type, the posted speed, the FHSZ zone, and the story count. Cross-reference each against the classification tables above. If the hand calculation matches the audit trail result within rounding, the output is verified.

### Example verification

A 60-unit, 5-story project on a two-lane, 30 mph road in a VHFHSZ zone:

```
project_vehicles     = 60 × 2.5 × 0.90                     = 135 vehicles
HCM base capacity    = 1,350 pc/h (two-lane, 30 mph)
degradation factor   = 0.35 (VHFHSZ)
bottleneck_capacity  = 1,350 × 0.35                         = 472.5 vph
delta_T_road         = (135 ÷ 472.5) × 60                   = 17.1 minutes
egress_penalty       = min(5 × 1.5, 12)                     = 7.5 minutes
ΔT                   = 17.1 + 7.5                           = 24.6 minutes
Threshold (VHFHSZ)   = 45 × 0.05                            = 2.25 minutes
Result               = DISCRETIONARY (24.6 > 2.25)
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
required_capacity = (135 ÷ 2.25) × 60 = 3,600 vph
```

The existing effective capacity is 472.5 vph (1,350 × 0.35). The gap is 3,127.5 vph. That gap cannot be closed by a road improvement alone at a 35% fire-condition degradation factor — the base capacity required to deliver 3,600 effective vph in a VHFHSZ zone would be 3,600 ÷ 0.35 = 10,286 pc/h, which exceeds freeway capacity. In this case, the road improvement path is not viable and the developer's only options are a unit reduction or a second independent egress route.

For a more constrained example — a 20-unit project in a VHFHSZ zone with ΔT = 4.0 minutes:

```
project_vehicles     = 20 × 2.5 × 0.90          = 45 vehicles
threshold            = 2.25 minutes
required_capacity    = (45 ÷ 2.25) × 60         = 1,200 vph
existing capacity    = 472.5 vph (1,350 × 0.35)
required base cap    = 1,200 ÷ 0.35             = 3,429 pc/h
```

A two-lane road cannot achieve 3,429 pc/h base capacity at any speed. But a multilane road (1,900 pc/h × 2 lanes = 3,800 pc/h base) would deliver 3,800 × 0.35 = 1,330 vph effective — above the 1,200 vph required. So widening the bottleneck from a two-lane to a four-lane cross-section would bring the project within the threshold.

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

## Summary: The Engineer's Role in Each Determination

| Determination | Engineer Action |
|---|---|
| **Ministerial** (below 15 units) | No engineering review required under this standard. Normal fire code and engineering plan check applies. |
| **Conditional Ministerial** (passes ΔT) | Verify road classification, lane count, speed, and FHSZ zone against city records. Confirm ΔT arithmetic. Sign off on the determination or flag corrections before issuance. |
| **Discretionary** (fails ΔT) | Same verification as above. If the developer elects a road improvement path: calculate required capacity, confirm physical achievability, draft improvement condition with timing, bonding, and re-analysis requirements. |
| **Any determination** | Review for IFC §503 site access concerns. Document separately from JOSH determination. |

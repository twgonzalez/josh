# City Planner's Implementation Guide

California Stewardship — May 2026

**Prepared for planning staff responsible for day-to-day project review under the JOSH ΔT Evacuation Capacity Standard**

------

## What This Guide Is For

This guide is written for the planning staff who will use JOSH in daily project review: the planner at the counter answering questions from applicants, the senior planner writing staff reports, and the planning director explaining a determination to a developer's attorney.

It does not repeat the methodology. That is documented in the Professional Engineer Technical Brief. It does not repeat the legal framework. That is documented in the Legal Defensibility Memorandum. This guide assumes both are in the record, and answers the questions that come up between receiving an application and issuing a determination: What projects trigger this analysis? What do I say at the pre-application meeting? How do I write the staff report finding? What do I say when the developer pushes back?

The core calculation is one number — ΔT, expressed in minutes — representing how much additional time this project adds to evacuation clearance on its most constrained serving route. The city's standard is that no single project may consume more than a fixed share of the escape window documented for the project's fire hazard zone. If ΔT is within the threshold, the project is approved at the ministerial or conditional ministerial tier. If ΔT exceeds the threshold, the project requires discretionary review.

------

## The Three Determinations at a Glance

Every project that triggers the analysis receives one of three determinations. The determination is produced automatically by the JOSH system based on the ΔT calculation. The planner does not make a judgment call — the planner applies the standard, and the standard produces the outcome.

| Determination | When It Applies | What It Means |
|---|---|---|
| **Ministerial** | Project is below the 15-unit size threshold (Standard 1 not met) | No evacuation capacity analysis required. Standard building and fire code review proceeds normally. |
| **Conditional Ministerial** | All serving routes pass the ΔT test (ΔT ≤ threshold for the project's zone) | Project is approved at the ministerial tier, with standard safety conditions. No discretionary hearing required. |
| **Discretionary** | Any serving route fails the ΔT test (ΔT > threshold for the project's zone) | Project requires discretionary review. The developer has options to modify the project, fund a road improvement, or provide a second egress route. |

The thresholds are not judgment calls. They are derived from the escape windows documented by the National Institute of Standards and Technology in its Camp Fire investigation, multiplied by the 5% engineering significance share the city adopts by resolution:

| Zone | Escape Window | Threshold |
|---|---|---|
| Very High Fire Hazard (VHFHSZ) | 45 minutes | 2.25 minutes |
| High Fire Hazard | 90 minutes | 4.50 minutes |
| Moderate / Non-designated | 120 minutes | 6.00 minutes |

These numbers are not negotiable on a project-by-project basis. They are pre-adopted by resolution. A developer's argument that their specific project is different does not change the threshold — it changes the inputs to the calculation.

------

## Which Projects Trigger the Analysis

**Standard 1 is the size gate.** The analysis applies to any project proposing 15 or more net new residential units. Below 15 units, no evacuation capacity analysis is required under this standard. The project receives a Ministerial determination automatically.

The 15-unit threshold comes from two sources: it is the Institute of Transportation Engineers' de minimis threshold for project-generated traffic impact analysis, and it aligns with the SB 330 statutory anchor for affordable housing review timelines. It is an objective integer comparison — not an estimate, not a range.

**Count net new units, not gross.** A project that demolishes 10 existing units and builds 40 new ones has a net new unit count of 30, which triggers the analysis. A project that adds 14 units to an existing 10-unit building has a net new count of 14, which does not.

**Mixed-use projects:** Count only the residential units. Commercial square footage does not contribute to the evacuation vehicle count for purposes of this standard.

**Accessory dwelling units:** A project that proposes only ADUs under the state ADU statute is typically below the threshold. A large market-rate project that includes ADUs as part of its unit count should include them in the total.

When in doubt on counting, document your interpretation in the staff report and apply it consistently. The standard is an objective integer test — the goal is a consistent, defensible count.

------

## The Pre-Application Meeting

Most developers will ask about JOSH before they submit a formal application. The pre-application meeting is the right time to explain the standard clearly, give the developer realistic expectations, and let them make design decisions before investing in detailed plans.

**What to tell the developer at the pre-application stage:**

The city applies an objective evacuation capacity standard to residential projects of 15 or more units. The standard measures how many minutes the project adds to evacuation clearance time on the road network serving the site. That number is compared to a threshold set by the project's fire hazard zone. If the project is within the threshold, it is approved ministerially with standard conditions. If it exceeds the threshold, it goes to discretionary review.

The developer does not need to commission a study. The city runs the analysis using public data — OpenStreetMap road network, Cal Fire FHSZ designations, Census vehicle ownership data. The inputs the developer provides are: the project address, the number of units, and the number of stories.

**What a developer can ask at the pre-application stage:**

A developer can ask for a preliminary JOSH analysis before submitting. This is encouraged. Running the analysis early lets the developer understand what constraints they face and whether a design modification could bring a project within the ministerial threshold. A preliminary result is not a formal determination — it is informational, and the formal determination is issued at the application stage. Document that it is preliminary and that the formal analysis will use the submitted application data.

**What you should not say at the pre-application stage:**

Do not characterize the likely outcome as "probably fine" or "probably too big." You have not run the analysis. The number is the number — tell the developer that you will run it once the application is received, or offer a preliminary run if they have the basic project parameters. Informal characterizations create expectations that the objective standard may not confirm.

------

## Running the Analysis

The JOSH system takes three inputs from the application:

1. **Project address** — used to locate the site on the road network and identify the serving routes within a 0.5-mile radius
2. **Unit count** — the net new residential units
3. **Stories** — the height of the proposed building (relevant for the egress penalty for buildings of 4 or more stories)

The system downloads current road network data from OpenStreetMap, applies Cal Fire FHSZ designations to calculate effective road capacity, runs Dijkstra routing to identify all serving evacuation paths, and computes ΔT for each path. The binding result is the worst-case path — the highest ΔT among all routes from the project to the network boundary.

**What the system produces:**

The interactive demo map shows the evacuation route geometry, the bottleneck segment, the ΔT result, and the determination tier. The audit trail — a plain-text document — shows every input, every intermediate value, and every threshold comparison. The audit trail is the record. Print it and attach it to the staff report.

**Road data quality:** OSM road classifications are generally accurate for primary and secondary roads but can be wrong for private roads, recently reclassified streets, or unusual jurisdictions. If the developer or city engineer flags that a road in the analysis is misclassified — for example, a private covenant road tagged as a primary arterial — the city engineer can request a road data correction. Document the correction and the reason. Corrected road data applies to all future analyses in that city. Do not make project-specific road adjustments; corrections must apply uniformly.

------

## Writing the Staff Report Finding

The staff report finding does four things: states the standard, states the inputs, states the result, and states the determination. It does not characterize the project. It does not express an opinion. It applies the standard.

### Ministerial Finding (below size threshold)

> The proposed project includes [N] net new residential units, which is below the 15-unit threshold established by the City's Objective Evacuation Capacity Standard. No evacuation capacity analysis is required. The project is approved at the ministerial tier, subject to standard building, fire, and engineering conditions.

### Conditional Ministerial Finding (ΔT within threshold on all routes)

> The proposed project includes [N] net new residential units at [address]. The City applied the JOSH ΔT Evacuation Capacity Standard (City Council Resolution No. [XXX]). The analysis identified [N] serving evacuation routes within the 0.5-mile project radius. The highest ΔT result is [X.X] minutes on [Route Name], against a threshold of [X.XX] minutes for the project's [Zone] fire hazard designation. The project is within the threshold on all serving routes and is approved at the ministerial tier, subject to standard building, fire, and engineering conditions of approval.

### Discretionary Finding (ΔT exceeds threshold on one or more routes)

> The proposed project includes [N] net new residential units at [address]. The City applied the JOSH ΔT Evacuation Capacity Standard (City Council Resolution No. [XXX]). The analysis identified [N] serving evacuation routes within the 0.5-mile project radius. The highest ΔT result is [X.X] minutes on [Route Name], against a threshold of [X.XX] minutes for the project's [Zone] fire hazard designation. The project exceeds the threshold on [N] route(s). The project is referred to discretionary review pursuant to the Standard. The developer may address the finding by modifying the project design, providing a second egress route, or funding an improvement to the constraining road segment. A revised application incorporating any such modification will be subject to a new analysis under the Standard.

**What to include in the record:**

- The JOSH audit trail printout (every input, every formula, every result)
- The determination letter generated by the system
- The Cal Fire FHSZ designation for the project site (can be referenced by parcel, confirmed in the audit trail)
- The city council resolution adopting the standard (by number and date)

**What not to put in the staff report:**

Do not characterize the project as dangerous, unsafe, or irresponsible. The standard produces a tier, not a judgment about the developer. Do not speculate about what might happen in a fire. Do not compare the project to other projects by name. The record should contain the objective analysis and nothing else. Characterizations invite cross-examination on things that are not in the standard and are not your job to assess.

------

## What the Developer Can Change

When a project exceeds the threshold, the determination is not a denial — it is a statement of what the constraint is and an implicit invitation to solve it. The planner's job at this point is to explain the constraint precisely and let the developer's team decide how to address it.

There are four paths to meeting the standard. All of them are within the developer's control.

**A note on the vehicle count formula.** Project vehicles are calculated as `units × 1.9 × 0.90`. The 1.9 is the Census ACS B25044 California statewide average vehicles per housing unit, computed across *all* households — including households that own no vehicle. Those zero-car households are already reflected in the 1.9 figure (they contribute zero to the average, pulling it below the vehicle-owning-only average). The 0.90 is the **community mass-evacuation mobilization rate** sourced to **NFPA 1660:2024 (which consolidates NFPA 1616:2020 *Mass Evacuation, Sheltering, and Re-entry Programs*)** — the national fire-protection standard for community-scale mass evacuation planning. The 0.90 magnitude is derived from the standard's full-evacuation design basis, adjusted for the ~10% zero-vehicle household share documented in Census B25044, and empirically validated against Roberson et al. (2012) Southern California WUI stated-intent literature. Together, the two factors cover both the vehicle ownership dimension (captured in 1.9) and the community evacuation design dimension (captured in 0.90). Cities that override `vehicles_per_unit` with local ACS data should not also lower `behavioral_mobilization` to further account for zero-car households — that would count the same households twice. Each parameter has one job; adjusting both for the same reason understates demand.

**Reduce the unit count.** Fewer units means fewer vehicles, which means a lower ΔT. The audit trail shows the exact calculation, so the developer's engineer can work backward: given the bottleneck capacity and the threshold, how many units can this road support? The answer is arithmetic. For a project in a VHFHSZ zone with a 2.25-minute threshold and a bottleneck capacity of 472 vehicles per hour, the maximum number of vehicles that fits in the threshold is (2.25 ÷ 60) × 472 = 17.7 vehicles, which at 1.9 vehicles per unit × 90% mobilization works out to approximately 10 units. The developer may find that number unworkable for the project's financing and choose a different path.

**Provide a second egress route.** A project with two independent egress routes to different segments of the network effectively splits its vehicles across two paths. If neither path alone fails the threshold with the project's full load split proportionally, the project may pass. Document the second egress clearly — it must be a distinct route to a distinct exit, not a second driveway onto the same street. This is also subject to road data quality review by the city engineer.

**Fund a road improvement.** The bottleneck is a specific road segment with a specific effective capacity. The developer can fund a physical improvement to that segment — adding a lane, widening shoulders, removing a lane-narrowing obstruction — that raises its effective capacity. The audit trail tells the developer exactly how much additional capacity is needed. After the improvement is complete and the road data is updated, a revised application is analyzed under the improved conditions. The improvement must be funded and constructed before the project is approved — not conditioned on future construction. Coordinate with the city engineer on improvement specifications and bonding requirements.

**Redesign the building.** For projects where the egress penalty is a significant contributor to ΔT — high-rise residential with a single stairwell and a single garage exit — the developer can add stairwells, widen stair widths, or provide multiple garage exits on different streets. The **NFPA 101 Life Safety Code (2024 California edition, Ch. 7)** and **IBC 2024 Ch. 10 (Means of Egress)** govern this calculation — this is the legitimate use of NFPA 101 in the JOSH methodology (building egress, distinct from the community-scale mobilization rate sourced to NFPA 1660 / 1616). The city engineer and fire department review this component. A building redesign that reduces the egress penalty reduces ΔT. The project is then re-analyzed.

------

## Developer Objections — Staff Responses

These are the objections that appear most frequently, in roughly the order they tend to arise. The responses below are staff-level — they explain the standard without requiring a legal argument. If the developer's response to any of these is to retain outside counsel and continue pressing, escalate to the city attorney rather than continuing the exchange at staff level.

### "Your road data is wrong."

The road network data comes from OpenStreetMap, the same public database used by Google Maps, Apple Maps, and most state transportation agencies. If the developer believes a specific road segment is misclassified — for example, that a road tagged as a secondary arterial is actually a local collector — the city engineer will review the classification against the road's physical characteristics and official city designation. If the engineer confirms a correction is warranted, the city will update the road data and re-run the analysis. Road data corrections apply uniformly to all projects in the city — they are not project-specific adjustments. The developer cannot request a correction that applies only to their analysis.

### "The road is already at LOS F — my project doesn't make it worse in any meaningful way."

The standard does not measure whether the project degrades existing conditions. It measures the project's own contribution to evacuation clearance time. This is the same principle a fire marshal applies when posting a maximum occupancy limit: the question is not how crowded the room already is — the question is whether the additional occupants can get through the exits in time. Adding 101 vehicles to a 472-vehicle-per-hour road adds 12.8 minutes of clearance time regardless of what the baseline traffic level is. The fire does not care what the baseline was; it cares how long it takes the project's vehicles to clear the bottleneck.

### "This is just a CEQA end-run."

No. This standard operates under the Safety Element of the General Plan, pursuant to AB 747 (Gov. Code §65302.15), which requires Safety Elements to analyze evacuation route capacity. The Legislature placed this requirement in the Safety Element — not in CEQA, not in the Circulation Element — because evacuation capacity is a life safety question, not an environmental impact question. The Housing Accountability Act, Government Code §65589.5(j), explicitly creates an exception for safety findings based on objective written standards. This standard is adopted by city council resolution as an objective development standard. It is not a CEQA analysis and does not require a CEQA finding.

### "Other cities approve projects like this without this analysis."

AB 747 requires all California cities to incorporate evacuation capacity analysis into their Safety Elements. Cities that have not yet adopted an objective standard may be approving projects in a way that exposes them to significant legal liability if a fire causes casualties that evacuation capacity analysis would have flagged. This city has adopted the standard. The developer's experience in other jurisdictions does not govern this application.

### "The 5% threshold is arbitrary."

The 5% figure is the one policy value the city adopts by resolution. The escape windows it is applied to — 45 minutes for Very High zones, 90 minutes for High, 120 minutes for Moderate and Non — are not city decisions. They are documented in NIST Technical Note 2135, the federal government's minute-by-minute reconstruction of the 2018 Camp Fire. Five percent is the standard engineering significance threshold applied to determine whether a single project's contribution to a shared infrastructure constraint is material. The city is not required to justify a threshold of exactly 5%; it is required to adopt an objective threshold. Five percent is consistent with engineering practice and was adopted after review of the methodology by the city's legal and engineering staff.

### "My project has two access points — you should give me credit for both."

The current standard identifies all evacuation paths within a 0.5-mile radius of the project and tests each independently. Credit for two independent egress routes to genuinely different network exits is available — the project's vehicles are assessed against each route's capacity separately. If both routes independently pass the threshold with a proportionate share of the project's vehicles, the project passes. If the developer believes a second egress route exists that is not reflected in the analysis, the city engineer will review it. A second driveway onto the same street is not a second egress route for purposes of this analysis.

### "This violates the Housing Accountability Act."

The Housing Accountability Act, Government Code §65589.5(j)(1), explicitly permits a city to deny or condition a housing project based on a finding that the project would have a significant, quantifiable, direct, and unavoidable adverse impact on public health or safety, based on objective, identified written public health or safety standards. This standard satisfies all five requirements: it is significant (minutes of evacuation delay in fire conditions); quantifiable (a number, expressed in minutes); direct (a mechanical calculation with no discretionary steps); unavoidable (the developer cannot avoid generating vehicles); and objective (every input is from published national or federal sources). The city attorney has reviewed and confirmed that this standard satisfies HAA §65589.5(j). Refer the developer to the Legal Defensibility Memorandum.

------

## When to Escalate

Handle at staff level:

- Explaining how the standard works at a pre-application meeting
- Answering questions about the calculation inputs or methodology
- Explaining what options the developer has to meet the standard
- Explaining the record requirements for the staff report

Escalate to city attorney when:

- The developer's attorney sends a letter questioning the standard's legality
- The developer asserts that a specific project is categorically exempt from the standard
- The developer threatens litigation or references a court case
- A project triggers the standard and the developer refuses to engage with the modification options
- Staff is uncertain whether a particular project configuration triggers the standard at all (unusual unit counts, mixed tenure, phased projects)

The city attorney has reviewed the Legal Defensibility Memorandum and should be familiar with the standard's legal basis. Brief the attorney before the developer's letter arrives if you see a contested determination coming.

------

## Formal Adoption — What the City Needs to Do

Planning staff can use JOSH in a staff report today, under the city's existing General Plan, to support a safety finding. The calculation is substantive evidence. However, the city's legal position is significantly stronger after formal adoption by resolution.

The resolution converts the standard from ad hoc evidentiary support into a pre-adopted objective development standard — the instrument the Housing Accountability Act explicitly contemplates. Courts give pre-adopted standards the highest deference. The resolution does not require an environmental review; it is an administrative action adopting an objective methodology, not a discretionary land use decision.

The resolution needs to accomplish three things: adopt the ΔT standard as the city's objective evacuation capacity standard under AB 747; specify the 5% project share threshold (the one policy value the city enacts); and direct planning staff to apply the standard to all qualifying applications effective a specified date.

The Legal Defensibility Memorandum contains model resolution language and the complete statutory framework. The Planning Director should provide the draft resolution to the city attorney for review before it goes to council. The council action is a single-meeting item with no public notice requirement beyond the standard agenda posting.

After adoption, every determination letter the city issues will cite the resolution number and date. That citation is the link in the administrative record that connects the project-specific finding to the pre-adopted standard the court will defer to.

------

## Summary: The Planner's Checklist

For each application that may trigger the standard:

1. **Intake:** Confirm net new unit count. If ≥ 15, the analysis applies.
2. **Run JOSH:** Enter address, unit count, and stories. Attach the audit trail to the file.
3. **Identify the determination:** Ministerial (below threshold), Conditional Ministerial (passes), or Discretionary (fails).
4. **Write the finding:** Use the model language for the applicable tier. Include the audit trail, the determination letter, the FHSZ designation, and the resolution number in the record.
5. **Communicate to the applicant:** Issue the determination letter. If Discretionary, include a clear explanation of the constraint and the four modification paths.
6. **Pre-application:** Offer a preliminary analysis to any developer who asks. Mark it preliminary. Do not characterize outcomes informally.
7. **Objections:** Respond at staff level using the language above. Escalate to city attorney when legal arguments enter the conversation.
8. **Road data corrections:** Route to city engineer. Never make project-specific adjustments.

The determination is the standard applied to the inputs. The planner's job is to apply it consistently, document it completely, and explain it clearly.

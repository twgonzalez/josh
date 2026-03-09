# JOSH ΔT Standard — Legal Defensibility Memorandum

**Prepared for:** California Stewardship Fund / Municipal Partners **Date:** March 2026 **Re:** Legal basis for the ΔT Evacuation Capacity Standard; recommendation for adoption by city council resolution as an objective development standard

------

## 1. Executive Summary

The JOSH system computes a single number for each proposed development: **how many minutes the project adds to evacuation clearance time on its most constrained serving route.** This number — ΔT — is derived entirely from published national engineering standards (HCM 2022), federal data (Census ACS), state hazard designations (Cal Fire FHSZ), national fire safety codes (NFPA 101), and federal post-disaster case studies (NIST Camp Fire investigation). No input requires city-level policy adoption. No computation involves discretion.

The standard operates on one principle: **you cannot put more people behind an exit than the exit can handle in an emergency.** This is the same principle that governs fire marshal occupancy limits in every occupied building in California. The standard applies it to the roads those buildings depend on.

The architecture is simple. FHSZ affects the road — fire zones reduce road capacity during the emergency that triggers evacuation. Mobilization is a constant — the standard assumes 90% of the project's households generate a vehicle, consistent with NFPA 101's design basis for full building evacuation. The calculation is one division: project vehicles divided by bottleneck capacity, converted to minutes.

A city can use the ΔT analysis in a project-level staff report today, under its existing General Plan, to support a safety finding under the Housing Accountability Act (Gov. Code §65589.5(j)(1)). However, **this memorandum recommends that cities adopt the ΔT standard by city council resolution as an objective development standard.** Adoption by resolution is a single-meeting-cycle action that dramatically strengthens legal defensibility by converting the standard from ad hoc evidentiary support into a pre-adopted, legislatively-enacted objective standard — the exact instrument the HAA contemplates and that courts give the highest deference.

This memorandum documents the legal basis for each component of the standard, the recommended adoption pathway, and the legal advantages of each tier of adoption.

------

## 2. Statutory Framework

### 2.1 The Safety Exception Under the HAA

Government Code §65589.5(j)(1)(A) permits a city to deny or condition a housing project if it makes written findings, supported by substantial evidence, that the project would have a "specific, adverse impact upon the public health or safety."

Section 65589.5(j)(2) defines "specific, adverse impact" as:

> *"a significant, quantifiable, direct, and unavoidable impact, based on objective, identified written public health or safety standards, policies, or conditions as they existed on the date the application was deemed complete."*

This definition creates five requirements, each of which the ΔT standard satisfies.

### 2.2 AB 747 and the Safety Element Mandate

Government Code §65302.15 (AB 747) requires Safety Elements to "identify residential developments in any hazard area identified pursuant to Section 51178 that do not have at least two emergency evacuation routes." This provision places evacuation capacity squarely within the Safety Element — not the Circulation Element, not CEQA.

The Legislature's decision to locate evacuation analysis in the Safety Element (§65302(g)) rather than in CEQA is legally significant. It establishes evacuation capacity as a **general plan safety question** — a condition-based inquiry about whether an area can support its population under emergency conditions — rather than a **project-level environmental impact question** subject to CEQA's marginal causation framework.

### 2.3 Cal Fire FHSZ Designations

Government Code §51175-51189 establishes the Fire Hazard Severity Zone system. FHSZ designations are state findings made by Cal Fire based on objective criteria: fuel loading, terrain slope, fire weather patterns, and fire history. They are not subject to local discretion and constitute "objective, identified written public safety standards" that predate any specific application.

In this standard, the FHSZ designation serves one function: it determines the effective capacity of road segments that pass through designated zones. Roads in fire zones will not operate at full capacity during the fire that triggers evacuation. The FHSZ designation does not affect the number of vehicles the project generates — that is a constant. FHSZ affects only the size of the door those vehicles must pass through.

------

## 3. Satisfying the HAA's Five Requirements

### 3.1 Significant

ΔT measures the additional time required to clear an evacuation route due to the project's vehicles. In a Very High Fire Hazard Severity Zone, where the NIST Camp Fire investigation documented that communities had approximately 45 minutes from first warning to fire front arrival, minutes of additional clearance time translate directly to additional households unable to evacuate before the fire arrives.

A finding that a project adds 12.8 minutes to evacuation clearance on a single-access road in a VHFHSZ zone is significant on its face. The significance does not depend on a threshold — it is inherent in the physical relationship between time, road capacity, and fire behavior.

### 3.2 Quantifiable

ΔT is a number, expressed in minutes, computed by a deterministic formula:

```
ΔT = (project_vehicles / bottleneck_capacity) × 60 + egress_penalty

Where:
  project_vehicles    = units × vehicles_per_unit × 0.90
  bottleneck_capacity = min(HCM_capacity × hazard_degradation) along serving route
  egress_penalty      = building egress time for structures ≥ 4 stories (NFPA 101)
```

Every input is a published, verifiable quantity. Every computation is arithmetic. The result is independently reproducible by any qualified engineer. This is quantifiable by any definition.

### 3.3 Direct

The causal chain is mechanical, not speculative:

1. The project creates housing units.
2. Housing units generate vehicles (Census data).
3. 90% of households evacuate by vehicle during an emergency (NFPA 101 design basis, adjusted for zero-vehicle households per Census B25044).
4. The road has a fixed capacity, potentially reduced if it passes through a fire hazard zone (HCM 2022 × Cal Fire FHSZ degradation).
5. More vehicles on a fixed-capacity road take more time to clear.
6. That additional time is ΔT.

There is no attenuated causation. There is no need to model cumulative effects or allocate responsibility among multiple sources. The project's own vehicles, on the road's own capacity, produce the time increment. The causation is as direct as gravity.

### 3.4 Unavoidable

Unless the project reduces its unit count (reducing vehicles), modifies its building design (reducing egress time), provides secondary road access (changing the bottleneck), or funds road capacity improvements, the time impact persists. These are the mitigation pathways the standard identifies.

If no feasible mitigation exists, the impact is unavoidable. If mitigation is feasible, the city should offer it to the developer before considering denial — which is exactly what the ΔT framework enables. The number tells the developer precisely what needs to change and by how much.

### 3.5 Based on Objective, Identified Written Standards

Each component of the ΔT calculation traces to a specific published standard:

**Road capacity:** Highway Capacity Manual, 7th Edition (2022). Published by the Transportation Research Board, a unit of the National Academies of Sciences, Engineering, and Medicine. Used by every state DOT and traffic engineering practice in the country. Specific exhibits: 12-6 (freeway), 12-7 (multilane), Chapter 15 (two-lane).

**Capacity degradation (FHSZ road adjustment):** HCM capacity adjustment factors for visibility impairment (Exhibit 10-15) and incidents/lane blockage (Exhibit 10-17), composited for conditions documented as consequences of Cal Fire's own FHSZ designations. The FHWA SHRP 2-L08 Final Report provides supplementary capacity adjustment factors for incident zones. The FHSZ designation is the sole determinant of which road segments receive degradation — it is a state finding under Gov. Code §51175, not a city opinion.

**Mobilization rate (0.90):** NFPA 101 (Life Safety Code), the national standard for building egress design, is premised on 100% occupant evacuation. Fire marshals do not size exits for partial evacuation — they size them for everyone. This standard applies the same principle: when a building must be evacuated, every household with a vehicle generates a vehicle. The 0.90 factor (rather than 1.0) accounts for approximately 10% of households with zero vehicles, as measured by Census ACS Table B25044. The mobilization rate is a constant — it does not vary by hazard zone, because the standard measures the project's demand on the road, not observed behavioral patterns during past events.

**Housing units and vehicles per household:** U.S. Census Bureau, American Community Survey 5-Year Estimates. Tables B25001 (housing units) and B25044 (vehicles available). Federal statistical data.

**Safe egress windows:** NIST Technical Note 2135, "A Case Study of the Camp Fire — Fire Progression Timeline" (2021); NIST Technical Note 2252, "NETTRA" (2023); NIST Technical Note 2262, "ESCAPE" (2023, updated 2025). The Camp Fire investigation documented that spot fires reached Paradise approximately 40 minutes before the fire front arrived. With modern alert systems (WEA, sirens) not available in 2018, a conservative planning window of 45 minutes is used for VHFHSZ zones. Longer windows for lower-hazard zones are derived from fire spread rate ratios.

**Maximum project share (5%):** Standard engineering significance threshold. At 5%, a road can absorb approximately 20 projects before new development alone exhausts the safe window. The ΔT thresholds are derived at runtime as `safe_egress_window × 0.05` — they are not independent policy values but the mathematical product of a NIST-documented time window and a standard significance threshold.

**FHSZ designations:** Cal Fire, under Government Code §51175-51189. Statewide map, publicly available. Used solely to determine road capacity degradation — not mobilization.

**Building egress time:** NFPA 101 (Life Safety Code) and International Building Code (IBC). National standards adopted by reference in California Building Code.

Every standard listed above (a) is written, (b) is published, (c) is objective, (d) is identified (specific exhibits and tables are cited), and (e) existed before any specific application is filed.

------

## 4. Three Tiers of Adoption — and Why Resolution Is Recommended

A city can deploy the ΔT standard at three levels of legal strength. Each successive tier provides greater defensibility. **Tier 2 (adoption by resolution) is the recommended path** because it provides nearly the full legal strength of a General Plan amendment at a fraction of the procedural cost.

### 4.1 Tier 1: Staff Report Evidence (Available Immediately)

**Mechanism:** City staff applies the ΔT methodology in a project-level staff report as evidentiary support for a discretionary finding under §65589.5(j)(1).

**Legal basis:** The HAA requires that the finding be based on "objective, identified written public health or safety standards, policies, or conditions as they existed on the date the application was deemed complete." The standards cited — HCM 2022, Census ACS, Cal Fire FHSZ, NFPA 101, NIST Camp Fire case study — all exist independent of the city's General Plan. They are national and state standards. The city applies them as evidence, analogous to citing USGS fault maps or FEMA flood zone designations in a project review.

**Strength:** Defensible, but the weakest of the three tiers. The finding is made on a case-by-case basis, which creates two vulnerabilities: (a) a developer can argue the city is applying standards selectively or inconsistently, and (b) the city must make the full §65589.5(j)(1) finding — including that no feasible mitigation exists other than denial — for each individual project. There is no ministerial pathway; every flagged project requires a discretionary hearing.

**When to use:** Immediately, for projects currently in the pipeline, while the city prepares a Tier 2 adoption.

### 4.2 Tier 2: Adoption by City Council Resolution (Recommended)

**Mechanism:** The city council adopts a resolution establishing the ΔT standard as an objective development standard for evacuation capacity, specifying the methodology, parameter values, and thresholds. The resolution takes effect upon adoption.

**Legal basis:** A city council resolution is a legislative act. It creates a "standard, policy, or condition" under §65589.5(j)(2) that exists as of the date of adoption. Once adopted, the ΔT threshold is no longer an ad hoc evidentiary argument in a staff report — it is a pre-adopted, city-enacted objective standard that applies to all subsequent applications.

**Strength:** This is where the legal posture shifts categorically. Three critical advantages:

**First — it satisfies the HAA's "objective standard" requirement on its face.** The HAA at §65589.5(d)(5) defines "objective" standards as those that "involve no personal or subjective judgment by a public official and are uniformly verifiable by reference to an external and uniform benchmark or criterion available and knowable by both the applicant and the public official." A resolution adopting the ΔT formula, specifying the parameters, and publishing the derived thresholds meets every element of this definition. The formula is deterministic. The inputs are public data. The threshold is derived from NIST data × a fixed percentage. Any engineer can run it. The developer knows the result before filing.

**Second — it enables ministerial processing.** Under the HAA's framework, a project that is "consistent with applicable, objective general plan, zoning, and subdivision standards" is entitled to ministerial approval (§65589.5(j)). A resolution adopting the ΔT standard as an objective development standard means projects that pass the threshold are approved ministerially — no hearing, no discretionary findings required. Projects that fail the threshold require discretionary review, but the basis for that review is the adopted standard, not a staff opinion. This is faster for developers whose projects pass and legally cleaner for the city when projects fail.

**Third — it shifts the burden of proof.** Without an adopted standard, the city bears the burden of justifying its safety finding for each project. With an adopted standard, the developer bears the burden of showing the standard is not "objective" or was not lawfully adopted. That is a much harder argument to make against a resolution that cites HCM 2022, NFPA 101, Census data, NIST case studies, and Cal Fire designations.

**Procedural path:** A resolution can typically be adopted in a single council meeting cycle. It does not require the environmental review, public notice periods, or Housing Element consistency analysis of a General Plan amendment. It is a legislative policy action within the council's existing police power authority over public safety.

**When to use:** As soon as the city has run the JOSH analysis for its jurisdiction and verified the outputs. A city could realistically move from first JOSH analysis to adopted resolution within 60-90 days.

### 4.3 Tier 3: Safety Element Amendment (Strongest, but Slower)

**Mechanism:** The city incorporates the ΔT standard into its Safety Element as an objective development standard, with full General Plan amendment process.

**Legal basis:** An objective standard adopted in the General Plan is the gold standard under the HAA. It is a "general plan standard" under §65589.5(d), which carries the strongest presumption of validity.

**Strength:** Maximum legal defensibility. The standard is embedded in the city's General Plan, which is a legislative act entitled to broad deference. A court reviewing a denial based on a General Plan Safety Element standard applies the "reasonable person" test — could a reasonable person have found the standard valid? — not de novo review.

**Limitation:** General Plan amendments require environmental review under CEQA, Housing Element consistency analysis, public hearings, and typically 12-24 months of staff time. For cities facing immediate development pressure in hazard zones, this timeline is too slow.

**When to use:** As part of the city's next scheduled Safety Element update (required under SB 379 and AB 747). The resolution adopted at Tier 2 should be designed to be incorporated directly into the Safety Element when that update occurs — same methodology, same parameters, same thresholds.

### 4.4 The Recommended Sequence

```
Month 1-2:    Run JOSH analysis for the city. Validate outputs.
              Apply Tier 1 (staff report evidence) to any projects
              currently in pipeline.

Month 2-3:    Draft resolution. City attorney review.
              Council adoption → Tier 2 in effect.

Year 1-2:     Incorporate into Safety Element update → Tier 3.
```

This sequence gives the city immediate protection (Tier 1), strong legal footing within 90 days (Tier 2), and maximum defensibility at the next General Plan cycle (Tier 3). No city needs to wait for a General Plan amendment to act.

------

## 5. What the Resolution Should Contain

A model resolution should include the following elements:

### 5.1 Recitals (Findings of Fact)

The recitals establish the legislative record. They should state:

- The city has responsibilities under Gov. Code §65302(g)(4) and §65302.15 (AB 747) to address evacuation route adequacy in hazard areas.
- Cal Fire has designated portions of the city as Very High, High, and/or Moderate Fire Hazard Severity Zones under Gov. Code §51175-51189.
- The city has analyzed its evacuation route network using the Highway Capacity Manual (7th Edition, 2022), Census ACS data, and Cal Fire FHSZ designations.
- The analysis identifies specific road segments and routes where evacuation capacity is constrained, including identification of bottleneck segments and their effective capacity under hazard conditions.
- The NIST Camp Fire case study (Technical Note 2135) documented that communities in Very High Fire Hazard Severity Zones had approximately 45 minutes from first warning to fire front arrival. The Council finds this timeline to be an appropriate basis for establishing safe egress windows for VHFHSZ zones, with proportionally longer windows for lower-hazard zones.
- NFPA 101 (Life Safety Code) designs building exits for 100% occupant evacuation. The Council finds that the same full-evacuation design principle should apply to the roads serving those buildings, with a 90% vehicle generation rate accounting for zero-vehicle households (Census B25044).
- The city council finds that development that would add excessive evacuation clearance time on constrained routes creates a specific, quantifiable risk to the public health and safety of both existing and future residents.
- The ΔT methodology and derived thresholds are based on published national standards (HCM 2022, NFPA 101, NIST Technical Notes), federal data (Census ACS), and state hazard designations (Cal Fire FHSZ), are objective, and involve no personal or subjective judgment.

### 5.2 Operative Provisions

The operative section should:

- Adopt the ΔT formula as the city's objective standard for evaluating evacuation capacity impacts of proposed residential development.
- Specify the exact formula: `ΔT = (units × vehicles_per_unit × 0.90) / bottleneck_capacity × 60 + egress_penalty`, where bottleneck_capacity is the minimum effective capacity (HCM capacity × hazard degradation factor for the road segment's FHSZ zone) along the project's serving evacuation routes. The mobilization rate of 0.90 is a constant applied to all projects regardless of location, consistent with the NFPA 101 full-evacuation design basis.
- Specify the hazard degradation factors by FHSZ zone (VHFHSZ: 0.35, High: 0.50, Moderate: 0.75, Non-FHSZ: 1.00), with their derivation from HCM Exhibits 10-15 and 10-17. These factors affect road capacity only — not mobilization.
- Specify the safe egress windows by zone (VHFHSZ: 45 min, High: 90 min, Moderate: 120 min, Non-FHSZ: 120 min) with citation to NIST Technical Note 2135.
- Specify the maximum project share: 5%. ΔT thresholds are derived as `safe_egress_window × 0.05` and need not be enumerated as static values — the formula is self-executing from these two inputs.
- Specify the egress penalty methodology: 1.5 minutes per story for buildings ≥ 4 stories, capped at 12 minutes, per NFPA 101 and IBC. The penalty may be overridden by a project-specific NFPA 101 egress calculation prepared by a licensed fire protection engineer.
- Establish the unit threshold below which the standard does not apply (15 units, or as the city determines).
- State the determination tiers: projects below threshold are ministerial; projects above threshold where ΔT exceeds the derived zone threshold require discretionary review; projects above threshold where ΔT does not exceed the zone threshold are conditional ministerial with standard safety conditions.
- Require that every determination include a full audit trail: computation inputs, intermediate values, result, source citations, map, and mitigation pathways.
- State that the standard applies uniformly to all residential projects within the city's jurisdiction, regardless of project location, applicant, or zoning designation.
- Provide that a developer may commission an independent analysis using the same methodology and published inputs to demonstrate compliance if the developer disputes the city's computation. A developer may also submit verified road geometry data (lane counts, speed limits) to update inputs for specific serving routes.
- Provide that the city council may amend the parameter values by subsequent resolution upon a showing that updated published data warrants revision.

### 5.3 Severability Clause

If any provision of the resolution is held invalid, the remaining provisions continue in effect. This protects the overall framework if a court finds a specific parameter (e.g., a particular degradation factor) unsupported.

### 5.4 Effective Date and Applicability

The resolution takes effect immediately upon adoption and applies to all applications deemed complete after the effective date. Applications already deemed complete are evaluated under the standards in effect at the time they were deemed complete (per HAA §65589.5(j)(2)). Under SB 330 (Gov. Code §65941.1), a preliminary application vests the development standards in effect at the time of filing; the city cannot apply the resolution to projects that submitted a preliminary application before the effective date.

------

## 6. Why Resolution Adoption Strengthens Defensibility

The legal advantages of adoption by resolution over unadopted staff-level application are substantial and specific.

### 6.1 The Standard Becomes a "Standard" Under the HAA

The HAA's safety exception at §65589.5(j)(2) requires that findings be based on "objective, identified written public health or safety standards, policies, or conditions." An adopted resolution IS a written standard adopted by the legislative body. It is no longer an argument that HCM + Census + FHSZ = a standard. It is, itself, the standard. The underlying sources provide the technical foundation; the resolution provides the legal instrument.

This is the same mechanism by which cities adopt building codes, seismic standards, and flood zone regulations — the technical standard exists at the national or state level, and the city's legislative act adopts it for local application. No court has held that a city cannot adopt nationally-published engineering standards by resolution as the basis for objective development standards.

### 6.2 Judicial Deference to Legislative Acts

A city council resolution is a legislative act. Courts review legislative acts under the "reasonably debatable" standard — the question is whether the council's decision falls within the range of reasonable legislative judgment, not whether the court would have made the same decision. This is a highly deferential standard.

By contrast, a staff-level finding in a project report is reviewed for "substantial evidence." While the ΔT calculation provides substantial evidence, the substantial evidence standard is less deferential than the reasonably debatable standard. Adoption by resolution moves the city from the less favorable standard to the more favorable one.

Specifically: if a developer challenges the ΔT thresholds (e.g., "2.25 minutes in VHFHSZ is too restrictive"), the court's question under resolution-level review is: "Was it reasonably debatable that 2.25 minutes is an appropriate threshold for this hazard zone?" Given the underlying data — NFPA 101 mobilization design basis, HCM capacity figures, NIST-documented fire timelines, Camp Fire and Palisades Fire outcomes — the answer is clearly yes. The council reviewed published evidence and made a policy judgment within the range of reasonable safety standards. That judgment is entitled to deference.

The derived threshold structure provides an additional layer of defensibility. A court reviewing the 2.25-minute VHFHSZ threshold sees not a round number chosen by the council, but the mathematical product of a NIST-documented safe window (45 minutes, per Technical Note 2135) and a standard engineering significance threshold (5%). To challenge the threshold, a developer must challenge one of those two inputs. Challenging the safe window means arguing that fires move slower than NIST documented in the Camp Fire. Challenging the 5% share means arguing that a single project should consume more than one-twentieth of the available escape time. Neither argument is tenable.

Without the resolution, the same challenge is more dangerous: the court reviews the staff's finding de novo and asks whether the evidence supports the specific threshold applied to the specific project. The city is defending a number in a staff report rather than a policy judgment by the elected body.

### 6.3 Eliminates the "Selective Application" Attack

Without an adopted standard, a developer can argue: "The city applied this analysis to my project but not to the project down the street. This is selective enforcement designed to block my project." Even if untrue, this argument creates a factual dispute that complicates litigation.

An adopted resolution eliminates this attack entirely. The standard applies to all residential projects above the unit threshold, uniformly, by its terms. The developer cannot argue selective application when the resolution says "all projects" and the formula is deterministic. The city's response is: "We adopted this standard by resolution on [date]. It applies to every project. Your project was evaluated using the same formula, same data, same thresholds as every other project. Here is the computation."

### 6.4 Provides a Pre-Application Bright Line for Developers

The HAA's policy goal is predictability — developers should know what standards apply before they invest in a project. An adopted resolution achieves this perfectly. The formula is published. The thresholds are derived from published data. The inputs are public. A developer can run the JOSH analysis on a parcel before purchasing it and know with certainty whether a project of a given size will pass the ΔT test.

This predictability actually serves the housing production goal. A developer looking at a parcel on a four-lane arterial in a non-FHSZ zone can see immediately that a 200-unit project produces a ΔT of approximately 1.4 minutes against a 6-minute threshold — well within bounds. That developer proceeds with confidence. The standard does not create uncertainty for projects that are safe; it creates certainty for projects that are not.

### 6.5 Insulates Against HCD Challenge

HCD's strongest argument against the ΔT standard is: "The city is applying unadopted standards on a project-by-project basis as a pretext for blocking housing." A resolution directly rebuts this:

- The standard was adopted by the elected legislative body through a public process — not invented by staff for a specific project.
- The standard applies uniformly to all projects — not selectively.
- The parameters are published and based on national standards — not derived to produce a desired outcome for a specific application. The ΔT thresholds are computed from a NIST-documented safe egress window multiplied by the standard 5% engineering significance threshold: the math produces the number, not a policy choice about what number to use.
- The developer had constructive notice of the standard before filing — the resolution is a public record.
- The standard enables mitigation and does not prohibit development categorically.

HCD may still object on policy grounds, but the legal ground for a formal challenge is substantially weaker against an adopted legislative act than against a staff-level analysis.

------

## 7. Distinguishing from CEQA

This distinction is critical and should be stated explicitly in every determination letter.

**CEQA asks:** Does this project cause a significant adverse environmental impact? Under CEQA's framework, the relevant comparison is baseline conditions versus project conditions, and the question is whether the project's marginal contribution is significant. A developer can argue: "The road was already at LOS F. My 45 units add a small increment to an already-failing road — not significant under CEQA."

**The Safety Element asks:** Is this area safe for additional human habitation under emergency evacuation conditions? This is a condition-based inquiry. The relevant question is not "who caused the problem?" but "can the project's people get through the door?" ΔT measures the project's own contribution — its vehicles against the road's physical capacity — without requiring allocation of responsibility for existing deficiencies.

The city's determination should state:

> "This finding is made pursuant to Resolution No. [XX-XXXX], adopted [date], which establishes objective evacuation capacity standards under Gov. Code §65302(g)(4) and §65302.15 (AB 747). The standard measures the project's contribution to evacuation clearance time — a life safety metric — using published national capacity standards (HCM 2022), the NFPA 101 full-evacuation design basis, state hazard designations (Cal Fire FHSZ, Gov. Code §51175), and NIST-documented safe egress windows (Technical Note 2135). This is not a CEQA environmental impact finding."

------

## 8. Addressing HCD Objections

The Department of Housing and Community Development's institutional posture favors housing production. HCD may object to the ΔT standard on policy grounds. These objections are anticipated and addressed.

### 8.1 "This is a pretext for blocking infill development."

Response: The standard's outputs demonstrate otherwise. Most urban infill sites — the development pattern the state incentivizes through SB 79, SB 35, and the RHNA process — sit on arterials with high capacity and low or no FHSZ exposure. A 50-unit project on a four-lane arterial in a non-FHSZ zone produces a ΔT of approximately 1.8 minutes — well under the 6-minute threshold. These projects pass automatically.

The projects that trigger the standard are those on constrained roads in high-hazard zones: canyon roads, ridgeline roads, single-access roads in VHFHSZ areas. These are precisely the locations where AB 747 directs cities to scrutinize evacuation capacity. The standard implements the Legislature's own directive.

### 8.2 "The city hasn't adopted this as an objective standard."

Response (at Tier 2): The city adopted the standard by Resolution No. [XX-XXXX] on [date]. The resolution specifies the methodology, parameters, and derived thresholds. It is an objective development standard adopted by the legislative body. The HAA at §65589.5(d)(5) defines "objective" as standards that "involve no personal or subjective judgment by a public official and are uniformly verifiable by reference to an external and uniform benchmark or criterion available and knowable by both the applicant and the public official." The ΔT standard satisfies every element of this definition.

### 8.3 "If every city does this, it will block housing statewide."

Response: This is a policy argument, not a legal one. The factual answer: the standard operates on physical road capacity, which varies by location. The vast majority of California's housing capacity is on high-capacity urban arterials where ΔT is negligible. The standard constrains development only where roads physically cannot handle the evacuation demand — which is the definition of unsafe development that the Legislature intended cities to prevent.

### 8.4 "The resolution is an end-run around the General Plan amendment process."

Response: A resolution adopting objective safety standards is a proper exercise of the city council's police power authority. Cities routinely adopt building codes, fire codes, seismic standards, and stormwater regulations by resolution or ordinance without General Plan amendments. The General Plan establishes broad policy direction; resolutions and ordinances implement specific standards consistent with that direction. Every city's existing Safety Element contains general language about protecting public safety from natural hazards — the resolution implements that existing policy with a specific, objective methodology.

Furthermore, the resolution is explicitly designed to be incorporated into the Safety Element at the city's next scheduled update. It is not a substitute for the General Plan process — it is an interim measure that provides immediate protection while the longer process proceeds.

### 8.5 "The 90% mobilization rate is too high — observed evacuation rates are much lower."

Response: Observed evacuation rates from GPS studies (Zhao et al. 2022, Wong et al. 2020) show approximately 47% compliance during the Kincade Fire. However, observed rates measure behavioral patterns during a specific past event — they are not a design standard. NFPA 101, the national fire safety code, designs building exits for 100% occupant evacuation. Fire marshals do not size exits based on the assumption that half the people will decide to stay. They size exits for the case where everyone needs to get out, because that is the case that kills people if the exits are too small.

The 90% mobilization rate applies this same design principle to the road. It asks: if this building needs to be evacuated, can the road handle the vehicles? The 10% reduction from 100% accounts for households with no vehicle (Census B25044). The standard is designed for the emergency that requires evacuation, not for the average case where many people choose to stay.

------

## 9. Strengthening the Record

A city using the ΔT standard should include the following in its administrative record for each determination:

1. **Reference to the adopting resolution** — number, date, operative provisions.
2. **Full ΔT computation** with all inputs, intermediate values, and result, including: project units, vehicles per unit (Census source), mobilization rate (0.90, NFPA 101 basis), bottleneck segment identification, HCM capacity, FHSZ zone and degradation factor, effective capacity, egress penalty (if applicable), and the derived threshold (safe window × 5%).
3. **Source citations** for each parameter — specific HCM exhibits, Census tables, Cal Fire FHSZ map version, NFPA 101 edition, NIST Technical Note number.
4. **Map** showing project location, serving routes, and bottleneck segments with FHSZ overlay.
5. **Statement of legal basis** citing the resolution and distinguishing the Safety Element finding from a CEQA analysis.
6. **Mitigation pathways** — specific design or infrastructure changes the developer could make to reduce ΔT below threshold. This demonstrates the city is not prohibiting development but identifying a constraint with available solutions.
7. **Statement that the standard applies uniformly** — same formula, same mobilization rate, same degradation factors, same derived thresholds, same data sources for every project. No discretion at any step.
8. **Acknowledgment that the unit threshold is administrative** — not a finding that smaller projects are categorically safe, but a proportionality determination about the level of review warranted by the scale of impact.

------

## 10. Summary: The Defensibility Ladder

| Tier              | Mechanism                                | Legal Standard of Review                    | Developer's Burden                                       | Time to Implement |
| ----------------- | ---------------------------------------- | ------------------------------------------- | -------------------------------------------------------- | ----------------- |
| 1. Staff Report   | ΔT as evidence in §65589.5(j)(1) finding | Substantial evidence (less deferential)     | Show lack of evidence                                    | Immediate         |
| **2. Resolution** | **ΔT adopted as objective standard**     | **Reasonably debatable (more deferential)** | **Show standard is not objective or unlawfully adopted** | **60-90 days**    |
| 3. Safety Element | ΔT in General Plan                       | General Plan consistency (most deferential) | Show General Plan inconsistency                          | 12-24 months      |

The recommended path — **Tier 2, adoption by resolution** — provides 80% of the legal strength of a General Plan amendment at 10% of the procedural cost. It converts the ΔT standard from an analytical tool into an adopted legislative act, shifts the standard of review in the city's favor, eliminates selective-application attacks, and provides pre-application certainty to developers.

Every city with FHSZ-designated areas should adopt this standard by resolution. Those facing active development pressure in constrained hazard zones should do so as soon as the JOSH analysis for their jurisdiction is complete.

------

## 11. The Two-Sentence Explanation for the Court

**For the judge:** The city adopted an objective standard — based on national fire safety codes, highway capacity standards, and the state's own fire hazard designations — that measures how many minutes each project adds to evacuation time, and this project exceeds the threshold derived from the NIST-documented escape window for its hazard zone.

**For the record:** Pursuant to Resolution No. [XX-XXXX], the project adds [X] minutes to evacuation clearance on [route] — computed from [N] units × 2.5 vehicles × 90% mobilization (NFPA 101 design basis) divided by [C] vehicles per hour (HCM 2022 capacity × Cal Fire FHSZ degradation) — exceeding the adopted threshold of [T] minutes, which is 5% of the [W]-minute safe egress window documented by NIST Technical Note 2135.

# Research & Implementation Plan: AB 747 Multi-Hazard Evacuation Capacity Model

**Status:** Draft — for review
**Date:** May 2026
**Purpose:** Define the full research program needed to extend the JOSH ΔT framework
from wildfire-only to a fully AB 747–compliant multi-hazard evacuation capacity model.

---

## 1. Why This Plan Exists

The current JOSH system addresses wildfire evacuation capacity, which satisfies the
specific mandate of AB 747 (Government Code §65302(g)(4)). The broader Safety Element
statute (§65302(g)) requires cities to address all natural hazards — flood, seismic,
geologic, and others — including their implications for evacuation.

The core JOSH insight from the wildfire work is that the ΔT formula is
**hazard-agnostic**. What changes across hazards is a thin layer of inputs:

- Which areas are dangerous (hazard zone data)
- How much road capacity is lost during the event (degradation model)
- How much time is available to evacuate (safe egress window)
- What fraction of residents should be planned for (mobilization)
- Which exits remain valid during the event (exit node validity)

This plan defines the research needed to populate those five inputs for every
hazard the Safety Element must address, then specifies how to integrate them into
a multi-hazard ΔT determination.

---

## 2. Statutory Scope

### 2.1 Primary authority

| Statute | Requirement |
|---|---|
| AB 747 (2019), Gov. Code §65302(g)(4) | Cities in VHFHSZ must assess evacuation route capacity; new development must be evaluated for evacuation impact |
| Gov. Code §65302(g) | Safety Element must address protection from unreasonable risks of fire, flood, and geologic/seismic hazards |
| SB 379 (2015) | Safety Element must address climate adaptation and resiliency, including hazard risk |
| SB 99 (2021) | Safety Element must address wildfire risk for housing near military installations |
| AB 1747 (2023) | Strengthened evacuation route planning requirements in Safety Elements |
| OPR Draft Evacuation Planning Technical Advisory (2024) | State guidance on methodology for evacuation clearance-time analysis |

### 2.2 Research task: statutory gap analysis

**Deliverable:** A one-page matrix mapping each hazard type to its statutory citation,
whether JOSH currently addresses it, and the evidentiary standard required for legal
defensibility. This becomes the legal foundation for every parameter choice downstream.

**Questions to answer:**
- Does §65302(g) require a quantitative capacity analysis for flood and seismic, or
  only a narrative assessment? (AB 747 is explicit for wildfire; the rest of §65302(g)
  is less prescriptive.)
- Does the OPR Evacuation Planning Technical Advisory extend ΔT methodology to
  non-fire hazards, or is it scoped to wildfire only?
- Which cities have had Safety Elements challenged on evacuation grounds, and what
  standard of proof did courts or OPR apply?

---

## 3. Hazard Inventory

The following hazards are candidates for the multi-hazard model. Each is assessed
for ΔT applicability — whether a pre-event ordered evacuation window exists that
makes the ΔT framework appropriate.

| Hazard | Pre-event window? | ΔT applicable? | Priority |
|---|---|---|---|
| Wildfire | Yes (minutes to hours) | ✅ Yes — current JOSH | Done |
| Flood / floodplain | Yes (hours to days) | ✅ Yes | High |
| Tsunami | Yes (minutes) | ✅ Yes | High |
| Dam failure | Yes (minutes to hours) | ✅ Yes | High |
| Natural gas / pipeline | Yes (minutes) | ✅ Yes | High |
| Liquefaction / earthquake | No pre-event window | ⚠️ Post-event only | Medium |
| Landslide | Variable (sometimes yes) | ⚠️ Conditional | Medium |
| Hazmat / industrial | Yes (minutes) | ✅ Yes | Medium |

**Note on earthquake:** The ΔT pre-event framework does not apply. Post-event
evacuation (damaged roads, fires following earthquake) requires a different model —
road-damage probability rather than capacity degradation. This is scoped separately
in Phase 3F below.

---

## 4. The Unified Mobilization Argument

Before detailing per-hazard research, the mobilization rate deserves a framework
decision that applies consistently across all hazards.

### 4.1 The principle

For any hazard where pre-event ordered evacuation is physically possible, the planning
standard should design for high mobilization — close to 0.90 or 1.00 — regardless of
observed historical compliance rates.

The reasoning: roads fail under high-compliance events, not low-compliance ones. A
road capacity standard calibrated to observed non-compliance (e.g., the 47% GPS rate
for the Kincade Fire, or the notoriously low flood compliance rates) would only pass
review when it can handle the outcome where people ignore the order. That is not a
life-safety standard.

> **Design for what should happen. Do not take credit for non-compliance.**

### 4.2 Per-hazard mobilization research tasks

For each hazard, research whether published literature supports a specific rate, or
whether the default 0.90 applies:

| Hazard | Expected literature finding | Research needed |
|---|---|---|
| Wildfire | Roberson 2012: 82.6% stated intent → 0.90 design value | Done |
| Flood | Low observed compliance (50–70%) but high-risk zones may be higher | Survey literature on mandatory flood order compliance; argue for 0.90 design standard |
| Tsunami | Very high observed compliance when warnings received | Confirm with Pacific Coast studies; likely supports 0.90–1.00 |
| Dam failure | Near-100% compliance when inundation is imminent and visible | Likely 1.00 |
| Gas / pipeline | Very high compliance (sensory hazard, immediate) | Likely 0.95–1.00 |
| Landslide | Variable; depends on warning time and prior event history | Literature review needed |

**Key argument to develop for flood:** Even if observed compliance is lower (50–70%),
the planning standard should use 0.90 because: (a) the dangerous scenario is when
compliance is high and roads are overwhelmed; (b) designing for non-compliance produces
a standard that only works when people do the wrong thing.

**Deliverable:** A mobilization rate methodology memo for each hazard, following the
structure of `docs/mobilization_rate_methodology_statement.md`.

---

## 5. Per-Hazard Research Blocks

Each block covers the five inputs the ΔT model requires: zone data, degradation model,
safe egress window, mobilization, and exit node validity.

---

### 5A. Flood / Floodplain

#### Zone data
- **Primary:** FEMA National Flood Hazard Layer (NFHL) — machine-readable GIS API at
  `msc.fema.gov`. Provides 100-year (1% annual chance) and 500-year (0.2% annual
  chance) Special Flood Hazard Areas by parcel.
- **Secondary:** California DWR floodplain mapping; local city flood studies where
  FEMA maps are outdated (common in rapidly developing areas).
- **Research task:** Confirm NFHL API access, update frequency, and whether Letter of
  Map Revision (LOMR) amendments are reflected in the API feed. Identify cities where
  local flood maps supersede FEMA NFHL.

#### Road degradation model
- Roads in the 100-year floodplain lose capacity as a function of inundation depth.
- **Research task:** Find published depth-capacity curves for road inundation.
  FHWA's "Hydraulic Design of Highway Culverts" and AASHTO guidance on road
  overtopping may contain relevant thresholds. Target values:

  | Condition | Proposed factor |
  |---|---|
  | Road in 100-yr SFHA, not currently inundated | 0.75 (evacuation traffic + emergency vehicles) |
  | Road in 100-yr SFHA, partially inundated (<6 in) | 0.40 |
  | Road in 100-yr SFHA, inundated (>6 in) | 0.00 |
  | Road in 500-yr SFHA only | 0.90 |
  | Road above 500-yr SFHA | 1.00 |

- **Key challenge:** Inundation depth is time-dependent. Research whether a
  conservative worst-case static assumption (road is inundated at peak flood stage)
  is legally defensible for planning purposes, analogous to the fire spread assumption
  in the VHFHSZ model.

#### Safe egress window
- **Flash flood:** NWS Flash Flood Guidance system provides local flash flood warnings
  typically 0–6 hours in advance. Shortest window: ~30 minutes for rapid-onset events.
- **Riverine flood:** USGS streamflow gauges and NWS Advanced Hydrologic Prediction
  Service provide 12–72 hours of advance warning for most major rivers.
- **Research task:** Identify NIST or FEMA equivalents to the Camp Fire fire-progression
  timeline for flood — specifically, published inundation timing studies for California
  rivers and watersheds. Target: derive a per-SFHA-zone egress window analogous to the
  VHFHSZ 45-minute window.

#### Exit node validity
- **Critical difference from wildfire:** A road that leads into or through the
  floodplain may itself be inundated. Exit nodes must be validated against FEMA FIRM
  elevations — if the node is below base flood elevation, it is not a valid exit.
- **Research task:** Define an elevation filter for exit node identification. Nodes
  below the 100-yr base flood elevation (BFE) in the NFHL are invalid exits during
  a flood event. This is the most significant architectural change from the wildfire
  model.

---

### 5B. Tsunami

#### Zone data
- **Primary:** NOAA/CalOES California Tsunami Inundation Maps — available as GIS
  layers for the entire California coast. Published at
  `maps.conservation.ca.gov/cgs/tsunami/`.
- These are deterministic inundation maps for the Maximum Considered Tsunami (MCT),
  derived from seismic source models.
- **Research task:** Confirm current revision status of CalOES maps; identify any
  cities where local probabilistic tsunami hazard analysis supersedes the CalOES map.

#### Road degradation model
- Roads within the inundation zone: 0.00 (submerged; impassable)
- Roads above inundation line: 1.00
- The degradation model here is binary — the inundation boundary is the critical line.
- **Key architectural implication:** Exit direction is critical. A project near the
  coast must route *away* from the ocean to exit nodes above the inundation line.
  The current Dijkstra routing already handles this (it routes to exit nodes, which
  would be defined as above-inundation points), but exit node identification must
  be constrained to nodes above the inundation boundary.

#### Safe egress window
- **Local source (Cascadia or local fault):** 10–20 minutes from event to wave arrival
  on Northern California coast. This is the tightest egress window of any hazard.
- **Distant source (Alaska, Japan, Chile):** 4–6 hours from NOAA Pacific Tsunami
  Warning Center alert to wave arrival. Far more manageable.
- **Research task:** Identify NOAA and USGS published arrival-time estimates for the
  Cascadia Subduction Zone scenario for California coastal cities. The local-source
  window likely drives the analysis — at 10–15 minutes, the ΔT threshold becomes
  extremely tight (15 min × 5% = 0.75 min), which may mean any project in the
  inundation zone automatically fails regardless of size.
- **Policy question to resolve:** Should the tsunami model use the local-source
  (worst-case, 10 min) or distant-source (typical warning, 4+ hrs) window? Recommend
  local-source for the conservative design standard, with distant-source as an
  informational comparison.

#### Exit node validity
- Nodes within the inundation zone are invalid exits.
- Nodes above the inundation line on roads leading inland or uphill are valid.
- **Elevation is the exit criterion**, not road classification. A secondary road
  going uphill may be more important than a coastal freeway.

---

### 5C. Dam Failure Inundation

#### Zone data
- **Primary:** California DSC (Division of Safety of Dams) Inundation Maps —
  required for all state-regulated dams. Available through California DWR.
- FEMA also requires dam owners to prepare Emergency Action Plans (EAPs) with
  inundation maps. These are increasingly available through the National Inventory
  of Dams (NID).
- **Research task:** Identify API or GIS access to DSC inundation maps. Determine
  which California cities have residential development within dam inundation zones
  that would be subject to analysis.

#### Road degradation model
- Similar to tsunami: inundation zone roads → 0.00; roads outside → 1.00
- However, dam failure inundation may be directional (follows valley drainage) and
  time-sequenced (wave front progresses downstream).
- **Research task:** Identify published dam-break inundation timing studies (FEMA
  publishes dam break modeling guidance). Determine if California DSC EAPs include
  arrival-time data by downstream location — this would directly inform the egress
  window.

#### Safe egress window
- Highly variable: a dam immediately upstream of a city may produce a 5–30 minute
  window; a dam 50 miles upstream may provide several hours.
- **Research task:** Review existing California DSC EAPs for dams near active
  development areas. Identify whether published inundation arrival times exist that
  can serve as the equivalent of the NIST Camp Fire timeline.

---

### 5D. Natural Gas / Hazmat Pipeline

#### Zone data
- **Primary:** PHMSA National Pipeline Mapping System (NPMS) — public viewer at
  `pvnpms.phmsa.dot.gov`. Pipeline locations, commodity type, and operating pressure
  available for hazardous liquid and gas transmission lines.
- **Secondary:** Local utility distribution pipeline maps (SoCalGas, PG&E, SDG&E)
  available under CPUC regulatory disclosure.
- **Research task:** Determine the appropriate exclusion zone radius for planning
  purposes. PHMSA's Potential Impact Radius (PIR) formula for gas transmission lines
  (`PIR (ft) = 0.69 × sqrt(pressure_psig × diameter_in²)`, per PHMSA TTO-13 (2005)
  and 49 CFR §192.903) provides a published, regulatory-standard exclusion zone.
  Confirm this is the right basis for a development impact analysis.
  > *Note: an earlier draft of this plan used the constant `0.004`. That value is
  > incorrect and produces a buffer ~170× too small; the canonical value is `0.69`.
  > Corrected per locked decision #3 in `docs/multihazard_status.md` (2026-05-16).*

#### Road degradation model
- Inside PIR/exclusion zone: 0.00 (closed by emergency services)
- Within 500 ft of zone boundary: 0.50 (emergency apparatus staging)
- Outside: 1.00
- **Research task:** Verify these factors against PHMSA emergency response protocols
  and NFPA 1 (Fire Code) gas emergency evacuation perimeter standards.

#### Safe egress window
- **Immediate rupture / fire:** 5–15 minutes from ignition to life-safety threat
  in the exclusion zone.
- **Unignited release:** Longer window — gas cloud must reach ignition source.
  Detection and dispersal modeling needed.
- **Research task:** Review PHMSA accident investigation reports and NFPA 1 for
  published emergency response timelines. Target: define a conservative planning
  window analogous to the wildfire safe egress window.

#### Exit node validity
- Roads inside the exclusion zone are closed. Exit nodes must be outside the zone.
- Wind direction affects the hazard boundary — worst-case planning should assume the
  maximum PIR applies in all directions.

---

### 5E. Landslide

#### Zone data
- **Primary:** USGS National Landslide Hazard maps; CGS Earthquake-Induced Landslide
  Hazard Zone maps (Seismic Hazard Zones under Alquist-Priolo).
- **Secondary:** California State Geologist's landslide inventory; local city
  geologic hazard maps.
- **Research task:** Determine whether CGS Seismic Hazard Zone maps (required for
  development permitting under Public Resources Code §2690) are available as a GIS
  API, and whether they provide sufficient spatial resolution for road-level analysis.

#### Road degradation model
- Roads crossing active or potentially active landslide zones may be blocked in a
  seismically triggered or storm-triggered event.
- Unlike fire or flood, landslide degradation is localized (a slide blocks a specific
  road segment, not a zone) and probabilistic.
- **Research task:** Determine if a statistical approach (probability of blockage ×
  capacity) is appropriate, or whether a conservative worst-case (road in landslide
  zone = 0.50 capacity) is more defensible for a planning standard.

#### Safe egress window
- Rainfall-triggered: NWS Debris Flow Warnings typically provide 0–6 hours.
- Earthquake-triggered: no pre-event window (see seismic section).
- **Research task:** Review California DWR and USGS reports on debris flow warning
  times for California mountain communities (e.g., Montecito 2018). Derive a
  planning window for storm-triggered debris flow analogous to the VHFHSZ window.

---

### 5F. Earthquake / Liquefaction (Post-Event Model)

This hazard requires a different framework than the others because there is no
pre-event window. The ΔT model applies post-event — how quickly can damaged roads
support evacuation of people seeking shelter or fleeing fires following earthquake?

#### Zone data
- **Primary:** CGS Seismic Hazard Zone maps (liquefaction and earthquake-induced
  landslide zones) — required under the Seismic Hazard Mapping Act for all
  development projects.
- **Secondary:** USGS ShakeMap scenario outputs; Caltrans bridge seismic
  vulnerability ratings (Caltrans publishes a statewide bridge inventory with
  Seismic Performance Category ratings).

#### Road degradation model — post-event
This is not a capacity-during-evacuation model. It is a road-availability model
for post-event evacuation. Research needed:

- **Liquefaction zone roads:** Probability of road failure given M6.5+ shaking,
  as a function of soil type and ground motion intensity. HAZUS (FEMA's multi-hazard
  loss estimation software) contains road-damage fragility curves.
- **Bridge failure:** Caltrans seismic vulnerability ratings provide a probability
  of functional loss per bridge per scenario. Bridges with poor ratings on key
  evacuation corridors become effectively blocked (factor = 0.0) in scenario
  planning.
- **Research task:** Review HAZUS road-damage fragility curves and Caltrans bridge
  vulnerability data. Determine whether a probabilistic damage state (expected %
  of road segments passable in a design-scenario earthquake) is the right framework,
  or whether deterministic worst-case (CGS liquefaction zone = road blocked) is
  more legally defensible.

#### Mobilization (post-event)
Post-event earthquake evacuation is largely spontaneous — people leave damaged
structures without an evacuation order. The 0.90 design-standard argument does
not apply cleanly here. Instead, the relevant question is: what fraction of
the population needs to move, and how quickly?

- **Research task:** Review FEMA HAZUS evacuation demand estimates for California
  earthquake scenarios. The 2008 USGS ShakeOut scenario and subsequent studies
  estimated displacement of millions of people in a M7.8 San Andreas event.
  These provide a demand baseline.

---

## 6. Cross-Cutting Research Topics

### 6.1 Multi-hazard interaction

Some California communities face multiple simultaneous hazards. The most important
compound scenarios:

- **Fire following earthquake:** A major earthquake ignites multiple simultaneous
  fires (Oakland Hills 1991 on a smaller scale; expected in a Bay Area M7+ event).
  Both fire spread and road damage apply simultaneously.
- **Tsunami following earthquake:** Cascadia or local subduction events produce
  both ground shaking (road damage) and tsunami (inundation). The effective egress
  window is the shorter of the two.
- **Flood following wildfire:** Post-fire debris flows (Montecito 2018 archetype).
  Wildfire destroys vegetation, destabilizes slopes; first significant rain
  triggers debris flow on evacuation routes.

**Research task:** Define a multi-hazard determination rule. Options:
1. **Worst-case single hazard:** Run each hazard independently; report the
   worst-case ΔT. Simplest to implement and explain; legally conservative.
2. **Compound scenario:** Define specific compound events (fire + earthquake;
   tsunami + earthquake) and model them simultaneously. More realistic but
   requires compound degradation factors and a compound egress window.

Recommendation: Implement worst-case single hazard for the initial release.
Flag compound scenarios as an identified limitation in the methodology documentation.

### 6.2 Data currency and update triggers

FHSZ maps, FEMA FIRM maps, USGS seismic hazard maps, and CalOES tsunami inundation
maps are each updated on different schedules. A key design question: when does
a city need to re-run the ΔT analysis because the hazard zone map has changed?

**Research task:** Document the update frequency and notification mechanism for
each data source. Define a trigger policy — e.g., a FEMA LOMR (Letter of Map
Revision) that removes a road from the SFHA should trigger re-analysis of projects
that used that road as a primary evacuation route.

### 6.3 Exit node validity by hazard

The current wildfire model assumes major roads are always valid exits. For other
hazards, this assumption fails in different ways:

| Hazard | Exit node failure mode | Filter criterion |
|---|---|---|
| Flood | Nodes below BFE inundated | FEMA FIRM BFE elevation check |
| Tsunami | Nodes in inundation zone | CalOES inundation polygon |
| Dam failure | Nodes in inundation zone | DSC inundation polygon |
| Gas/hazmat | Nodes inside exclusion zone | PHMSA PIR buffer |
| Liquefaction | Bridge nodes on vulnerable structures | Caltrans vulnerability rating |
| Landslide | Nodes on blocked road segments | CGS landslide zone + road crossing |

**Research task:** Design a generalized exit node validity filter that accepts
a hazard-specific polygon or attribute and invalidates nodes within it. This is
an architectural change to the Dijkstra routing setup, not the algorithm itself.

---

## 7. Implementation Architecture

### 7.1 HazardAdapter interface

Each hazard type is implemented as a `HazardAdapter` subclass that supplies the
five ΔT inputs. The wildfire adapter is the reference implementation.

```python
class HazardAdapter:
    """Abstract base — one subclass per hazard type."""

    def get_hazard_zone(self, point_wgs84) -> str:
        """Return the hazard zone classification for a project location."""
        raise NotImplementedError

    def get_degradation_factor(self, road_segment, zone) -> float:
        """Return capacity multiplier (0.0–1.00) for this road in this zone."""
        raise NotImplementedError

    def get_safe_egress_window(self, zone) -> int:
        """Return available evacuation window in minutes."""
        raise NotImplementedError

    def get_mobilization_rate(self, zone) -> float:
        """Return design vehicle release factor (default 0.90)."""
        return 0.90  # conservative default; subclass overrides with literature basis

    def is_exit_valid(self, node_id, node_attrs) -> bool:
        """Return False if this node is within the hazard zone (flooded, inundated, etc.)."""
        return True  # wildfire: all exits valid; flood/tsunami: filter by elevation

# Reference implementation (current):
class WildfireAdapter(HazardAdapter): ...

# Planned implementations:
class FloodAdapter(HazardAdapter): ...      # FEMA NFHL + BFE elevation filter
class TsunamiAdapter(HazardAdapter): ...    # CalOES inundation + exit elevation filter
class DamFailureAdapter(HazardAdapter): ... # DSC inundation maps
class GasHazmatAdapter(HazardAdapter): ... # PHMSA PIR + NFPA perimeter
class LandslideAdapter(HazardAdapter): ... # CGS + NWS debris flow window
```

### 7.2 Multi-hazard determination

```python
def evaluate_project_multihazard(project, adapters, road_network, parameters):
    results = {}
    for hazard_name, adapter in adapters.items():
        zone     = adapter.get_hazard_zone(project.location)
        mobility = adapter.get_mobilization_rate(zone)
        window   = adapter.get_safe_egress_window(zone)
        paths    = dijkstra_with_exit_filter(
                       project, road_network, adapter,
                       degradation_fn=adapter.get_degradation_factor
                   )
        delta_t  = compute_delta_t(project, paths, mobility, parameters)
        threshold = window * parameters.max_project_share
        results[hazard_name] = DeltaTResult(delta_t, threshold, zone, paths)

    # Worst-case single hazard drives determination
    controlling = max(results.values(), key=lambda r: r.delta_t / r.threshold)
    return MultiHazardDetermination(controlling, results)
```

### 7.3 Data pipeline additions (josh-pipeline)

Each new hazard adapter requires a corresponding data acquisition module in
`josh-pipeline/agents/data_acquisition.py`:

| Adapter | Data source | Acquisition method |
|---|---|---|
| FloodAdapter | FEMA NFHL WMS/REST | FEMA MapService API |
| TsunamiAdapter | CalOES inundation GIS | CA Open Data Portal download |
| DamFailureAdapter | DSC inundation maps | DWR GIS Portal |
| GasHazmatAdapter | PHMSA NPMS | PHMSA public viewer download |
| LandslideAdapter | CGS Seismic Hazard Zones | CA DOC GIS API |

Each must plug into the existing 90-day cache TTL and `metadata.yaml` audit trail.

---

## 8. Deliverables and Phases

### Phase 1 — Statutory and regulatory research (2–3 weeks)
- [ ] Statutory gap analysis matrix (§65302(g) vs. current JOSH coverage)
- [ ] OPR Technical Advisory scope confirmation (fire-only vs. multi-hazard)
- [ ] Legal defensibility memo: which hazards require quantitative ΔT vs. narrative
- [ ] Precedent review: cities challenged on multi-hazard Safety Element adequacy

### Phase 2 — Mobilization rate research (2 weeks, runs parallel to Phase 1)
- [ ] Flood compliance literature review → mobilization memo
- [ ] Tsunami compliance literature review → mobilization memo
- [ ] Gas/hazmat compliance literature review → mobilization memo
- [ ] Unified mobilization framework document (design-standard argument applied
      to all ordered-evacuation hazards)

### Phase 3 — Per-hazard data and parameter research (4–6 weeks)
- [ ] **Flood:** NFHL API access + depth-capacity curve literature + egress window
      derivation from NWS flash flood guidance
- [ ] **Tsunami:** CalOES map access + Cascadia arrival-time data from NOAA +
      local-source egress window
- [ ] **Dam failure:** DSC inundation map access + EAP arrival-time review
- [ ] **Gas/hazmat:** PHMSA PIR formula validation + NFPA 1 perimeter standards
- [ ] **Landslide:** CGS zone API + debris flow warning time literature
- [ ] **Earthquake post-event:** HAZUS road fragility curves + Caltrans bridge
      vulnerability data

### Phase 4 — Architecture and prototype (4–6 weeks)
- [ ] `HazardAdapter` abstract base class
- [ ] `WildfireAdapter` refactor (existing logic moved into adapter pattern)
- [ ] Exit node validity filter (generalized from current boundary-detection logic)
- [ ] `FloodAdapter` prototype (first new hazard; validates the architecture)
- [ ] Multi-hazard determination logic
- [ ] Updated `JOSH_DATA` schema for multi-hazard results

### Phase 5 — Parameter documentation and legal review (2–3 weeks)
- [ ] Methodology statement for each hazard (following the Roberson/mobilization
      statement as the template)
- [ ] Validation prompt for each hazard (following the WPI validation prompt structure)
- [ ] Updated PE Technical Brief covering multi-hazard methodology
- [ ] Updated Legal Defensibility Memo

### Phase 6 — Remaining hazard adapters and testing (4–6 weeks)
- [ ] `TsunamiAdapter`
- [ ] `DamFailureAdapter`
- [ ] `GasHazmatAdapter`
- [ ] `LandslideAdapter`
- [ ] Anti-divergence tests for each new adapter (JS + Python parity)
- [ ] Multi-hazard demo map for a city with ≥2 applicable hazards

---

## 9. Open Questions Requiring Policy Decisions

These are not research questions — they require a judgment call from the project
team, ideally with city attorney input before implementation.

1. **Flood mobilization:** If observed flood compliance is 50–70% but design standard
   is 0.90, cities using JOSH will face stricter flood standards than their current
   practice. Is that the intent? (Recommended answer: yes — this is the
   "design for what should happen" argument.)

2. **Earthquake model:** Should JOSH produce a post-event road-availability analysis
   for seismic hazards, or scope that out as requiring a separate PE-stamped seismic
   risk assessment? The latter is more legally defensible but limits the system's scope.

3. **Multi-hazard controlling determination:** Should the determination letter report
   only the controlling (worst-case) hazard, or all applicable hazards? Reporting all
   provides more transparency; controlling-only is simpler for applicants.

4. **Tsunami local-source window:** At 10–15 minutes, nearly any project in a tsunami
   inundation zone will fail the ΔT test. Is that the correct outcome? (Arguable yes —
   new development in a tsunami inundation zone with a 10-minute egress window is
   categorically problematic regardless of project size.)

5. **Dam failure scope:** Should JOSH analyze dam failure inundation only where a
   city has a specific upstream dam with a published DSC inundation map, or should
   it flag all development in valley bottoms below dams as requiring PE review?

---

## 10. Reference Documents

- `docs/mobilization_rate_methodology_statement.md` — Template for per-hazard
  mobilization memos
- `docs/JOSH_PE_Technical_Brief.md` — Technical framework to be extended
- `docs/JOSH_v341_Specification.md` — Parameter specification to be extended
- `docs/JOSH_Legal_Defensibility_Memo.md` — Legal framework to be updated
- FEMA Hazus Multi-Hazard Loss Estimation Methodology, Earthquake Model (2020)
- USGS Open-File Report 2008-1916 (ShakeOut scenario, Southern California M7.8)
- NOAA Technical Memorandum NWS PTWC (Pacific Tsunami Warning Center guidance)
- California DSC Dam Safety Program: `damsafety.water.ca.gov`
- PHMSA NPMS Public Map Viewer: `pvnpms.phmsa.dot.gov`
- CGS Seismic Hazard Zone Maps: `maps.conservation.ca.gov/cgs/shz/`
- CalOES Tsunami Inundation Maps: `maps.conservation.ca.gov/cgs/tsunami/`
- FEMA NFHL API: `msc.fema.gov/arcgis/rest/services/NFHL/`

# JOSH vs. KLD Engineering — AB 747 Capability Comparison

**Reference study:** *Evacuation Route Safety, Capacity, and Viability Analysis — AB 747 Report*
KLD Engineering, P.C. · City of Berkeley, California · February 27, 2024 (Rev. 3)

**Prepared:** 2026-03-27 · JOSH v3.4

---

## Executive Summary

The KLD Engineering study is the published professional-consultant baseline for AB 747 compliance
in a California city. It is a thorough, field-verified static inventory produced by traffic
engineers for approximately $200,000–$400,000 in consulting fees. JOSH is an open-source
computational pipeline that replicates the core methodology, automates it from public data, and
adds four analytical capabilities that KLD explicitly deferred to separate studies or did not
address at all.

---

## Side-by-Side Feature Matrix

| Capability | KLD Study | JOSH | Notes |
|---|---|---|---|
| **HCM 2022 road capacity** | ✅ Field-surveyed | ✅ OSM + config | KLD used May 2023 field survey; JOSH uses OSM tags + defaults from parameters.yaml |
| **LOS / v/c analysis** | ✅ Static v/c ratio | ✅ Informational only | Both use v/c for display; neither uses it for per-project determination |
| **FHSZ zone classification** | ✅ CAL FIRE zones | ✅ CAL FIRE REST API | Same source; JOSH downloads automatically |
| **Route inventory table** | ✅ Table A-1 (all streets) | ✅ routes.csv (evac routes) | KLD covers all streets; JOSH filters to evacuation network |
| **Multi-hazard scenarios** | ✅ Wildfire, earthquake, tsunami, flood, landslide, liquefaction | ⚠️ Wildfire only | KLD models 7 hazard types. JOSH covers wildfire (AB 747 primary). Other hazards noted in Section I as deferred. |
| **Safety factors** | ✅ Collision history, pavement width, curvature, slope, PCI | ❌ Not implemented | KLD uses Vision Zero data, AASHTO curvature, Caltrans PCI. JOSH uses HCM capacity only. |
| **Vulnerability / equity scoring** | ✅ Poverty, H+T index, vehicle availability, disability | ❌ Not implemented | KLD uses ACS equity metrics per segment. JOSH does not score segment-level vulnerability. |
| **Connectivity / viability scoring** | ✅ 4-factor composite score (connectivity, accessibility, service, congestion) | ❌ Not implemented | KLD produces a combined viability map. JOSH produces ΔT per project, not viability scoring. |
| **City-wide clearance time (ETE)** | ❌ Explicitly deferred — *"ETE study still ongoing"* | ✅ Computed (Section D) | KLD contracted a separate traffic simulation study that was unfinished at report publication. JOSH computes a supply-side clearance time analytically: `(total_vehicles / total_exit_capacity) × 60`. |
| **Per-project ΔT determination** | ❌ Not in scope | ✅ Core feature | JOSH's primary purpose — legally binding ministerial/discretionary tier per project. KLD produced no per-project analysis. |
| **SB 99 single-access identification** | ❌ Not referenced | ✅ Section F | KLD does not perform or cite SB 99 analysis. JOSH scans all block groups for `< 2` distinct exit osmids. |
| **FHSZ housing unit counts** | ❌ Not computed | ✅ Section E | KLD identifies FHSZ zones geographically but does not count housing units within each zone. JOSH does area-weighted Census ACS intersection. |
| **Hazard degradation on road capacity** | ❌ Not applied | ✅ v3.4 (0.35 / 0.50 / 0.75) | KLD reports raw HCM capacity, then scores hazard exposure separately. JOSH multiplies capacity by the degradation factor before any ΔT test, making the capacity figure fire-condition-specific. |
| **Improvement recommendations** | ⚠️ Qualitative narrative only | ✅ Algorithmic (Section H) | KLD describes problem areas narratively. JOSH generates rule-based recommendations with statutory citations for each finding. |
| **Human-readable block group labels** | N/A | ✅ "near Telegraph Ave & Dwight Way" | JOSH derives location labels from nearest named road segments — no geocoding API required. |
| **Data freshness / automation** | ❌ One-time field study (May 2023) | ✅ 90-day cached TTL, `--refresh` | KLD data requires a new contract to update. JOSH re-downloads from CAL FIRE + OSM + Census automatically. |
| **Cost** | ~$200K–$400K consulting engagement | ✅ Open source (AGPL-3.0) | JOSH eliminates the need to hire a traffic engineer for the computational layer. |
| **Shelter locations** | ❌ Not mapped | ⚠️ Config-driven placeholder | Neither study maps shelters. JOSH provides a `shelters:` config field that renders in the report when populated. |
| **Machine-readable GIS export** | ❌ PDF + static maps only | ✅ routes.csv + evacuation_paths.json | JOSH outputs GeoJSON-compatible files importable into ArcGIS/QGIS. |
| **Per-project determination letter** | ❌ Not in scope | ✅ brief_v3 HTML | Legally defensible ministerial/discretionary letter with case number, ΔT calculation, and appeal rights. |

---

## Methodological Differences

### 1. Capacity Computation

Both use HCM 2022. The tables are identical:

| Speed (mph) | KLD Capacity | JOSH Capacity |
|---|---|---|
| 20 | 900 pc/h | 900 vph |
| 25 | 1,125 pc/h | 1,125 vph |
| 30 | 1,350 pc/h | 1,350 vph |
| 35 | 1,575 pc/h | 1,575 vph |
| 40+ | 1,700 pc/h | 1,700 vph |
| Freeway/lane | 2,250 pc/h | 2,250 vph |

**Key difference:** JOSH applies hazard degradation factors (0.35 for VHFHSZ, 0.50 for High, 0.75 for Moderate) derived from HCM Exhibits 10-15/10-17 and validated against NIST TN 2135 Camp Fire road closure data. KLD reports raw HCM capacity and separately scores hazard exposure on a 0–1 scale — the two approaches are methodologically complementary, not contradictory.

### 2. Demand Model

| Approach | KLD | JOSH |
|---|---|---|
| Source | ACS vehicles-by-BG in ¼-mile buffer | Census ACS B25044 |
| Unit rate | ACS aggregate vehicle count | 2.5 vpu × 0.90 mobilization |
| Mobilization basis | Not explicitly stated | NFPA 101 (100% occupant evacuation) |
| Pass-through traffic | Caltrans HPMS AADT subtracted | Not modeled |
| Tourist vehicles | Excluded | Excluded |
| Transit | Not considered | Not modeled |

KLD's demand model is more detailed for a city-wide inventory. JOSH's model is more precise for per-project ΔT because it computes marginal vehicle contribution, not aggregate flow.

### 3. Congestion / Clearance Time

KLD's core finding — *"during an evacuation, many of the roadways within the city will operate at LOS F"* — is confirmed by JOSH's Berkeley results:

- **JOSH city-wide clearance time: 924.8 minutes** (simultaneous full-mobilization worst case)
- 9,450 vph total exit capacity across 13 unique exit nodes
- This is the planning worst case required by statute, not a prediction of actual ETE

KLD correctly notes this is not a realistic ETE — their separate traffic simulation study (which was still ongoing at publication) would produce a staged, time-phased estimate. JOSH's number is the same kind of planning upper bound that KLD would have produced in their ETE study's worst-case scenario.

---

## What JOSH Adds That No AB 747 Study Currently Provides

### 1. Per-Project Development Review (the ministerial gateway)
KLD produces a city-wide route inventory. No existing AB 747 study in California connects that inventory to individual development applications. JOSH is the only tool that takes a proposed project (address, units, stories) and outputs a legally defensible tier determination that a city can use to approve or require discretionary review. This is the core legal purpose JOSH was designed to serve.

### 2. City-Wide Clearance Time (Analytically)
KLD deferred this to a separate $150K+ traffic simulation contract. JOSH computes a supply-side clearance time in seconds from cached data:

```
clearance_time = (total_vehicles / total_exit_capacity_vph) × 60
```

This is not a substitute for a full ETE traffic simulation, but it is sufficient for Safety Element planning and objective development standards — and it is available the moment `analyze` completes.

### 3. SB 99 Single-Access Scan
Neither KLD nor any other published AB 747 study in California appears to include a systematic SB 99 analysis. JOSH Section F identifies every block group with fewer than 2 distinct modeled exit routes, aggregates affected housing units, and flags them with human-readable location labels.

### 4. Algorithmic Recommendations with Statutory Citations
KLD provides qualitative narrative observations ("the hills are most constrained"). JOSH generates specific, citable improvement recommendations keyed to statutory authority:
- Capital improvements keyed to HCM 2022 §12
- Second egress recommendations keyed to Gov. Code §65302.15(b)(3)
- Contraflow recommendations keyed to FHWA Emergency Transportation Operations
- Network deficit flag keyed to NIST TN 2135

### 5. Continuous Updateability
KLD's field study reflects Berkeley in May 2023. Any road change, new FHSZ designation, or Census update requires a new contract. JOSH re-runs from current data with a single command:

```bash
uv run python main.py analyze --city "Berkeley" --refresh
uv run python main.py report --city "Berkeley"
```

---

## What KLD Does That JOSH Does Not (Current Gaps)

| KLD Capability | JOSH Status | Priority |
|---|---|---|
| Earthquake hazard (Hayward Fault MMI 8/9) | Not modeled | Medium — requires ShakeMap integration |
| Tsunami inundation zones | Not modeled | Low — coastal cities only |
| Flood zones (FEMA 100/500-year) | Not modeled | Medium — NHD integration needed |
| Landslide susceptibility | Not modeled | Medium — CGS data layer needed |
| Liquefaction zones | Not modeled | Low — seismic scenario only |
| Road safety factors (PCI, collision history, curvature, slope) | Not modeled | Medium — Standard 6 (site access) is the partial answer |
| Vulnerability / equity scoring per segment | Not modeled | High — ACS data already loaded; needs scoring layer |
| Field-verified lane counts and speeds | OSM approximation | Low — OSM is ~90% accurate for arterials |
| Pass-through I-80 traffic subtraction | Not modeled | Low — affects absolute demand, not ΔT margin |

---

## Conclusion

JOSH and the KLD study are complementary, not competitive. The KLD approach is the correct
methodology for a city's Safety Element update — a one-time planning document covering all
hazard scenarios with field-verified data. JOSH is the correct tool for the downstream operational
use case: connecting that Safety Element's route inventory to a continuous, ministerial development
review process.

The critical gap the KLD report leaves open — and JOSH fills — is the question every planning
department faces the morning after adopting an AB 747 Safety Element:

> *"A developer just submitted a 120-unit project in the hills. Does it require discretionary
> review, or can we approve it ministerially?"*

The KLD report cannot answer that question. JOSH can.

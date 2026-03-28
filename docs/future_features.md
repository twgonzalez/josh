# JOSH Future Features Index

**System:** JOSH (Jurisdictional Objective Standards for Housing) v3.4+
**Prepared:** 2026-03-28

This document is a high-level index of planned capabilities beyond the current v3.4 scope. Each entry links to a detailed specification. Features are grouped by priority and estimated effort.

---

## Status of Current v3.4 Features

The following are **complete and shipped** in v3.4:

| Feature | Description |
|---------|-------------|
| ΔT per-project determination | Ministerial / conditional / discretionary tier per AB 747 |
| AB 747 city-wide report | `main.py report --city` → `ab747_report.html` (11 sections) |
| City-wide clearance time | Supply-side analytical ETE, per FHSZ zone |
| SB 99 single-access scan | Block group exit count with human-readable street labels |
| Hazard-aware road capacity | FHSZ degradation factors (0.35 / 0.50 / 0.75) |
| FHSZ housing unit counts | Area-weighted Census ACS intersection |
| Algorithmic recommendations | 4 rule types with statutory citations |
| KLD comparison analysis | `docs/josh-vs-kld-comparison.md` |
| 90-day cached data | OSM + CAL FIRE + Census, auto-refresh |

---

## Planned Features

### 1. City Engineer Road Data Override + Interactive Map Editor

**Spec:** [`docs/road_override_spec.md`](road_override_spec.md)

**Summary:** Many roads in JOSH — especially narrow residential streets in fire-prone hillside areas — lack OSM lane count or speed data and fall back to highway-type defaults. This feature lets a city engineer correct those values using field measurements, without editing OSM.

**Two components:**

| Component | Description |
|-----------|-------------|
| `config/cities/{city}_road_overrides.yaml` | Versioned YAML keyed by OSM segment ID; stores width (m), lane count, speed limit, surveyor notes, survey date |
| `output/{city}/road_editor.html` | Standalone Leaflet map (no server needed) — click any road segment to edit values, download YAML |

**Road editor map features:**
- Color-coded by data quality: gray (measured), orange (speed estimated), yellow (lanes estimated), red (both estimated), green (has override)
- Filter buttons: All / Needs Review / Overridden
- IFC §503 tier preview (live as you type width in feet)
- Load existing YAML to pre-populate green segments
- Download YAML via browser file download (no server)

**Impact:** Directly improves ΔT accuracy for the narrow roads that matter most in wildfire evacuations. Enables legally-auditable field-correction workflow with `surveyed_by` and `survey_date` fields.

**Estimated effort:** 2–3 days

**CLI command:** `uv run python main.py road-editor --city "Berkeley"`

---

### 2. Multi-Hazard Scenario Support

**Spec:** [`docs/multi_hazard_spec.md`](multi_hazard_spec.md)

**Summary:** JOSH currently models wildfire only. California cities face five additional natural hazards that can damage or close evacuation routes: flood, tsunami, earthquake landslide, liquefaction, and ground shaking. This feature adds each hazard as a distinct scenario subclass, using the same `EvacuationScenario` pattern already in place.

**Delivery sprints:**

| Sprint | Hazards | Effort | Data Source |
|--------|---------|--------|-------------|
| **Sprint 1** | Flood inundation (100-year + 500-year), Tsunami inundation | ~1 week | FEMA NFHL ArcGIS REST API; CGS/Cal OES tsunami polygons |
| **Sprint 2** | Earthquake-induced landslide zones, Liquefaction zones | ~1 week | CGS SHMA ArcGIS REST API (same pattern as FHSZ) |
| **Sprint 3** | Earthquake ground shaking (MMI-based road failure) | 2–3 weeks | USGS ShakeMap scenario HDF5 files (per-city download) |

**Degradation factors by hazard:**

| Hazard | Zone | Road Capacity Factor | Safe Egress Window |
|--------|------|---------------------|-------------------|
| Flood | 100-year (AE/VE) | 0.00 (closed) | 120 min |
| Flood | 500-year (X-shaded) | 0.50 | 240 min |
| Tsunami | Inundation zone | 0.00 (closed) | 30 min |
| Eq. landslide | Susceptible zone | 0.60 | 45 min |
| Liquefaction | High liquefaction zone | 0.70 | 60 min |
| Eq. shaking | MMI IX+ | 0.30 (bridge failure) | 45 min |
| Eq. shaking | MMI VII–VIII | 0.60 (pavement damage) | 60 min |
| Eq. shaking | MMI V–VI | 0.85 (minor damage) | 120 min |

All factors derived from published FEMA, USGS, and AASHTO sources — see spec for full citations.

**Integration with AB 747 report:** The report's Section I (Viability Scenarios) currently contains placeholder text for non-wildfire hazards. After implementation, each hazard adds a row to the scenario table: data source, degradation method, road segments affected, revised clearance time.

**Impact:** JOSH would match or exceed the multi-hazard capability of the KLD Berkeley study, which modeled 7 hazard types — the last capability gap in `docs/josh-vs-kld-comparison.md`.

---

### 3. Physical Site Access Standard (Standard 6)

**Spec:** Pending (see `CLAUDE.md` → "Pending Methodology Work")

**Summary:** Some projects fail not on route capacity but on physical access — a 200-unit building at the end of an 18-foot dead-end road. IFC §503 (fire apparatus access) defines objective width and turnaround thresholds that apply regardless of route LOS.

**Planned rules:**

| Check | Threshold | Source |
|-------|-----------|--------|
| Road width — one-way access | < 20 ft (6.1 m) → flag | IFC §503 |
| Road width — two-way access | < 26 ft (7.9 m) → flag | IFC §503 |
| Dead-end depth | > 150 ft serving > N units → flag | IFC §503 |
| Single access point for large project | City-adopted N (configurable) | IFC + local code |

**Implementation:** New scenario subclass `agents/scenarios/site_access.py`. Uses OSM `width` tag + road geometry. Feeds into determination as Standard 6 (never reduces tier below Standard 4 result — only raises to DISCRETIONARY when IFC violation found).

**Estimated effort:** 1–2 days after road override feature ships (needs `width_meters` from overrides to be reliable).

---

### 4. Dual / Multiple Egress Accounting

**Spec:** Pending (see `CLAUDE.md` → "Pending Methodology Work")

**Summary:** Projects with two independent egress routes (e.g., Clark Avenue Apartments: primary on Union St, egress-only on Clark Ave) currently receive a worst-case single-path ΔT. A more accurate model would sum effective capacities across independent egress paths when the project has confirmed separate access points.

**Questions to resolve before implementation:**
- OSM `oneway` tag surfacing to ΔT engine
- Capacity split model vs. worst-case single path (conservative vs. realistic)
- Modeling conditions-of-approval egress restrictions via `{city}_road_overrides.yaml`

**Dependency:** Road override feature (to model COA egress restrictions that aren't in OSM).

---

### 5. Vulnerability / Equity Scoring

**Spec:** Pending

**Summary:** The KLD Berkeley study scored each route segment on ACS equity metrics: poverty rate, H+T affordability index, vehicle availability, disability prevalence. JOSH already loads Census ACS data per block group — the scoring layer is the missing piece.

**Approach:** Per-segment vulnerability score (0–1) derived from area-weighted block group ACS metrics. Rendered as an optional overlay in `ab747_report.html` Section E (Population at Risk) and in `road_editor.html` (segment tooltip).

**Data already available:** Census ACS B25044 (vehicles), B17001 (poverty), B18101 (disability) — all loadable via existing `data_acquisition.py` Census API pattern.

**Estimated effort:** 1–2 days.

---

## Capability Gap Closure Roadmap

The table below tracks JOSH's progress toward full KLD-equivalent capability:

| KLD Capability | JOSH Status | Feature |
|----------------|-------------|---------|
| HCM 2022 road capacity | ✅ Complete | — |
| FHSZ zone classification | ✅ Complete | — |
| Route inventory | ✅ Complete | — |
| City-wide clearance time | ✅ Complete (v3.4) | — |
| Per-project ΔT determination | ✅ Complete (v3.4) | — |
| SB 99 single-access scan | ✅ Complete (v3.4) | — |
| Algorithmic recommendations | ✅ Complete (v3.4) | — |
| Field-verified road data | ⚠️ OSM approximation | Road Override (#1) |
| Physical site access (IFC §503) | ❌ Not modeled | Standard 6 (#3) |
| Dual egress accounting | ❌ Not modeled | Multiple Egress (#4) |
| Vulnerability / equity scoring | ❌ Not modeled | Equity Scoring (#5) |
| Flood inundation | ❌ Not modeled | Multi-Hazard Sprint 1 (#2) |
| Tsunami inundation | ❌ Not modeled | Multi-Hazard Sprint 1 (#2) |
| Earthquake landslide zones | ❌ Not modeled | Multi-Hazard Sprint 2 (#2) |
| Liquefaction zones | ❌ Not modeled | Multi-Hazard Sprint 2 (#2) |
| Earthquake ground shaking | ❌ Not modeled | Multi-Hazard Sprint 3 (#2) |
| Road safety factors (PCI, curvature, slope) | ❌ Not modeled | Future (no spec yet) |

---

## How to Add a New Feature

1. Write a spec in `docs/{feature_name}_spec.md` following the pattern in `road_override_spec.md`
2. Add an entry to this index with a link to the spec
3. Implement on a feature branch (`feat/{feature-slug}`)
4. Update `docs/josh-vs-kld-comparison.md` to reflect the new capability
5. Add `report_version` bump in `config/parameters.yaml` → `ab747.report_version`

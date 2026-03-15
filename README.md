# JOSH — Jurisdictional Objective Standards for Housing

**Open-source Python tool for fire evacuation capacity analysis in California cities.**

JOSH is a first-principles calculator built entirely from established national and state standards — HCM 2022, NFPA 101, NIST TN 2135, Cal Fire FHSZ, and U.S. Census data. It gives cities and applicants a legally defensible, fully algorithmic determination of whether a proposed housing project triggers discretionary review under AB 747, with zero engineering judgment and a full audit trail. Every result is reproducible by any licensed engineer with a spreadsheet.

---

## What It Does

California AB 747 (Gov. Code §65302.15) requires cities to analyze fire evacuation route capacity before approving housing projects in or near fire hazard zones. JOSH automates that analysis end-to-end:

1. **Downloads** CAL FIRE FHSZ zones, the OSM road network, and Census housing data for any California city
2. **Identifies** evacuation routes and computes per-route bottleneck capacity (HCM 2022)
3. **Applies** hazard degradation to road capacity based on FHSZ zone (NIST Camp Fire / HCM composite)
4. **Runs** the ΔT test — marginal evacuation clearance time added by the proposed project (v3.2 standard)
5. **Issues** a three-tier determination: `MINISTERIAL`, `CONDITIONAL MINISTERIAL`, or `DISCRETIONARY`
6. **Generates** a full audit trail for city attorney and planning commission review

All standards are objective and algorithmic. No discretion. No professional judgment clauses.

---

## Live Demo

> **[Project home page →](https://twgonzalez.github.io/josh/)**
>
> **[Berkeley interactive demo →](https://twgonzalez.github.io/josh/berkeley/demo_map.html)**

The home page covers the methodology, legal framework, adoption pathway, and document library. The demo map evaluates six representative Berkeley projects across different FHSZ zones, unit counts, and building heights — each popup shows the full A/B/C criteria breakdown and per-route ΔT values.

---

## Legal Framework

| Statute / Standard | Role in JOSH |
|--------------------|-------------|
| AB 747 (Gov. Code §65302.15) | Requires citywide evacuation route analysis |
| ITE de minimis (trip generation) | Source of the 15-unit size threshold — projects below this generate negligible marginal traffic impact |
| SB 330 (Housing Crisis Act) | Requires development standards to be objective and non-discretionary — the reason a fixed numerical threshold must be used rather than case-by-case judgment |
| AB 1600 | Impact fee nexus study framework (Phase 2) |
| SB 79 | Transit proximity flag (informational, no tier impact) |
| NFPA 101 / IBC | Building egress penalty for structures ≥ 4 stories |
| NIST TN 2135 | Camp Fire timeline → safe egress window calibration |

---

## Determination Logic (v3.2 ΔT Standard)

```
Standard 1 — Size gate:       units ≥ 15
Standard 2 — Route ID:        buffer 0.5 mi → identify serving evacuation paths
Standard 3 — Hazard zone:     GIS point-in-polygon → CAL FIRE FHSZ
Standard 4 — ΔT test:         ΔT = (project_vehicles / bottleneck_capacity) × 60 + egress_penalty
                               project_vehicles = units × 2.5 vpu × 0.90 (NFPA 101, constant)
                               threshold: VHFHSZ=2.25 min, High=4.50 min, Mod/Non=6.00 min
Standard 5 — SB 79 transit:   informational flag only

DISCRETIONARY           — Std 1 met AND any serving path ΔT > threshold
CONDITIONAL MINISTERIAL — Std 1 met AND all paths ΔT within threshold
MINISTERIAL             — below size threshold (Std 1 not met)
```

---

## Quick Start

**Requirements:** Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/twgonzalez/josh.git
cd josh
uv sync

# Analyze a city (downloads data + computes evacuation route capacity)
uv run python main.py analyze --city "Berkeley" --state "CA"

# Evaluate a specific project
uv run python main.py evaluate --city "Berkeley" --lat 37.87 --lon -122.27 --units 75

# Generate the multi-project interactive demo map
uv run python main.py demo --city "Berkeley"
# → output/berkeley/demo_map.html
```

Data is cached in `data/{city}/` with a 90-day TTL. Use `--refresh` to force re-download.

---

## Output Files

| File | Description |
|------|-------------|
| `output/{city}/demo_map.html` | Interactive multi-project comparison map (primary stakeholder UX) |
| `output/{city}/brief_v3_*.html` | Per-project determination brief (A/B/C criteria, ΔT per path) |
| `output/{city}/determination_*.txt` | Plaintext audit trail (legal compliance, AB 1600 nexus) |
| `output/{city}/routes.csv` | Full evacuation route inventory with capacity and LOS data |

---

## Project Structure

```
agents/
  data_acquisition.py    # Stage 1: download CAL FIRE FHSZ, OSM roads, Census data
  capacity_analysis.py   # Stage 2: HCM capacity, hazard degradation, route ID
  objective_standards.py # Stage 3: ΔT determination, audit trail generation
  scenarios/             # WildlandScenario (Standards 1–4), Sb79TransitScenario (Std 5)
  visualization/         # Folium demo map, determination briefs, popups
models/                  # Project, EvacuationPath, RoadSegment dataclasses
config/
  parameters.yaml        # All thresholds (HCM tables, ΔT limits, egress penalties)
  cities/berkeley.yaml   # City-specific config and overrides
  projects/              # Demo project batches for testing
```

---

## Adding a New City

1. Create `config/cities/{city}.yaml` modeled on `config/cities/berkeley.yaml`
2. Create `config/projects/{city}_demo.yaml` with representative test projects
3. Run `uv run python main.py analyze --city "{City}" --state "CA"`

JOSH will download all required data automatically. The only required fields in the city config are `osmnx_place`, `tiger_url`, `state_fips`, `county_fips`, and `place_fips`.

---

## License

JOSH is licensed under [AGPL-3.0-or-later](LICENSE).

All contributors must agree to the [Contributor License Agreement](CONTRIBUTING.md) before their contributions can be merged.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports, city configs, and methodology improvements are especially welcome.

> Copyright (C) 2026 Thomas Gonzalez.

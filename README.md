# JOSH — Jurisdictional Objective Standards for Housing

**Open-source Python tool for fire evacuation capacity analysis in California cities.**

JOSH is a first-principles calculator built entirely from established national and state standards — HCM 2022, NFPA 101, NIST TN 2135, Cal Fire FHSZ, and U.S. Census data. It gives cities and applicants a legally defensible, fully algorithmic determination of whether a proposed housing project triggers discretionary review under AB 747, with zero engineering judgment and a full audit trail. Every result is reproducible by any licensed engineer with a spreadsheet.

---

## What It Does

California AB 747 (Gov. Code §65302.15) requires cities to analyze fire evacuation route capacity before approving housing projects in or near fire hazard zones. JOSH automates that analysis end-to-end:

1. **Downloads** CAL FIRE FHSZ zones, the OSM road network, and Census housing data for any California city
2. **Identifies** evacuation routes and computes per-route bottleneck capacity (HCM 2022)
3. **Applies** hazard degradation to road capacity based on FHSZ zone (NIST Camp Fire / HCM composite)
4. **Runs** the ΔT test — marginal evacuation clearance time added by the proposed project (v4.0 standard)
5. **Issues** a three-tier determination: `MINISTERIAL`, `CONDITIONAL MINISTERIAL`, or `DISCRETIONARY`
6. **Generates** a full audit trail for city attorney and planning commission review

All standards are objective and algorithmic. No discretion. No professional judgment clauses.

---

## Live Demo

> **[Project home page →](https://twgonzalez.github.io/josh/)**
>
> **[Berkeley interactive demo →](https://twgonzalez.github.io/josh/berkeley/analysis_map.html)**

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

## Determination Logic (v4.0 ΔT Standard)

```
Standard 1 — Size gate:       units ≥ 15
Standard 2 — Route ID:        buffer 0.5 mi → identify serving evacuation paths
Standard 3 — Hazard zone:     GIS point-in-polygon → CAL FIRE FHSZ
Standard 4 — ΔT test:         ΔT = (project_vehicles / bottleneck_capacity) × 60 + egress_penalty
                               project_vehicles = units × 1.9 vpu × 0.90 (FHWA, constant)
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
```

The live Berkeley demo is already included — open `output/berkeley/analysis_map.html` directly,
no commands required.

To run analysis for your own city, assemble a data directory (see [Data Requirements](#data-requirements) below), then:

```bash
# Build the evacuation route graph
uv run python build.py analyze --city "Encinitas" --data-dir /path/to/data/encinitas

# Evaluate a specific project
uv run python build.py evaluate --city "Encinitas" --lat 33.04 --lon -117.29 --units 80 \
  --data-dir /path/to/data/encinitas

# Generate a multi-project interactive demo map
uv run python build.py demo --city "Encinitas" \
  --data-dir /path/to/data/encinitas \
  --projects /path/to/your/projects.yaml
# → output/encinitas/analysis_map.html
```

---

## Output Files

| File | Description |
|------|-------------|
| `output/{city}/analysis_map.html` | Interactive multi-project comparison map (primary stakeholder UX) |
| `output/{city}/brief_v3_*.html` | Per-project determination brief (A/B/C criteria, ΔT per path) |
| `output/{city}/determination_*.txt` | Plaintext audit trail (legal compliance, AB 1600 nexus) |
| `output/{city}/routes.csv` | Full evacuation route inventory with capacity and LOS data |

---

## Repository Structure

This repo (`josh`, public) contains the methodology engine only:

```
agents/
  capacity_analysis.py   # Stage 2: HCM capacity, hazard degradation, route ID
  objective_standards.py # Stage 3: ΔT determination, audit trail generation
  export.py              # graph.json + whatif_engine.js serializer
  scenarios/             # WildlandScenario (Standards 1–4), Sb79TransitScenario (Std 5)
  visualization/         # Folium demo map, determination briefs, popups
  analysis/              # City-wide clearance time, SB 99 single-access scan
models/                  # Project, EvacuationPath, RoadSegment dataclasses
config/
  parameters.yaml        # CANONICAL — all thresholds (HCM tables, ΔT limits, egress penalties)
  cities/berkeley.yaml   # Schema example — city config format
build.py                 # CLI: analyze, demo, evaluate, report
static/                  # JS what-if engine (whatif_engine.js, app.js)
output/berkeley/         # Live Berkeley demo output (tracked)
tests/                   # Anti-divergence + unit tests
```

City configs and project YAMLs follow the schema in `config/cities/berkeley.yaml`
and `config/parameters.yaml`. See [Data Requirements](#data-requirements) below.

---

## Data Requirements

`build.py analyze` expects a `--data-dir` containing these files:

| File | Description | Source |
|------|-------------|--------|
| `roads.gpkg` | OSM road network (GeoPackage) | [OpenStreetMap](https://www.openstreetmap.org/) via [OSMnx](https://osmnx.readthedocs.io/) |
| `fhsz.geojson` | CAL FIRE Fire Hazard Severity Zones | [CAL FIRE OSFM ArcGIS REST API](https://egis.fire.ca.gov/arcgis/rest/services/FRAP/HAZ/) |
| `boundary.geojson` | City boundary polygon | [U.S. Census TIGER](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) via OSMnx (`ox.geocode_to_gdf`) |
| `block_groups.geojson` | Census block groups (optional — used for SB 99 single-access scan) | [Census TIGER](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) |

**Fetching with OSMnx (roads + boundary):**
```python
import osmnx as ox
G = ox.graph_from_place("Berkeley, California")
ox.save_graph_geopackage(G, filepath="data/berkeley/roads.gpkg")
boundary = ox.geocode_to_gdf("Berkeley, California")
boundary.to_file("data/berkeley/boundary.geojson", driver="GeoJSON")
```

**City config:** Copy `config/cities/berkeley.yaml` as a starting point. Set `city_name`,
`state`, `analysis_crs`, and any parameter overrides. Pass it to `build.py` via
`--city-config /path/to/your/city.yaml`.

**Projects YAML:** See `config/cities/berkeley.yaml` comments for the schema.
Each project needs `name`, `lat`, `lon`, `units`, and optionally `stories` and `address`.

## Adding a New City

1. Fetch the four data files above into `data/{city}/`
2. Copy `config/cities/berkeley.yaml` → `config/cities/{city}.yaml` and update fields
3. Create a projects YAML with your proposed developments
4. Run the pipeline:
   ```bash
   uv run python build.py analyze --city "YourCity" --data-dir data/{city} --city-config config/cities/{city}.yaml
   uv run python build.py demo --city "YourCity" --data-dir data/{city} --projects projects/{city}.yaml
   ```

---

## License

JOSH is licensed under [AGPL-3.0-or-later](LICENSE).

All contributors must agree to the [Contributor License Agreement](CONTRIBUTING.md) before their contributions can be merged.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports, city configs, and methodology improvements are especially welcome.

> Copyright (C) 2026 Thomas Gonzalez.

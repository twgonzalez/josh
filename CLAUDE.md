# Fire Evacuation Capacity Analysis System

## Project Purpose

AI agent system that analyzes fire evacuation route capacity for California cities to:
1. Establish **objective development standards** (ministerial vs. discretionary review)
2. Generate **impact fee nexus studies** (AB 1600 compliant)
3. Enable **what-if analysis** for proposed developments

This is a legally-focused system. All standards must be objective (no engineering judgment, no discretion).

## Tech Stack

- **Python 3.11** via uv (`uv run python ...`)
- **GeoPandas** — spatial operations
- **OSMnx** — road network download and analysis
- **NetworkX** — graph/routing algorithms
- **Pandas** — tabular data
- **Click + Rich** — CLI
- **PyYAML** — configuration

## Run Commands

```bash
# Analyze a city (downloads data + calculates capacity)
uv run python main.py analyze --city "Berkeley" --state "CA"

# Evaluate a specific project
uv run python main.py evaluate --city "Berkeley" --lat 37.87 --lon -122.27 --units 75

# Force refresh cached data
uv run python main.py analyze --city "Berkeley" --state "CA" --refresh

# Regenerate the primary demo map (REQUIRED after any visualization code change)
uv run python main.py demo --city "Berkeley"
# → output/berkeley/demo_map.html
```

## Primary UX Artifact

**`output/{city}/demo_map.html`** is the primary stakeholder-facing UX — the interactive
multi-project comparison map used for demos, city attorney review, and planning presentations.
This is the ONLY output file external users need to open.

**After ANY change to `agents/visualization/`**, regenerate it:
```bash
export PATH="$HOME/.local/bin:$PATH"
uv run python main.py demo --city "Berkeley"
# → output/berkeley/demo_map.html
```

The `output/` directory is git-ignored. Share `output/{city}/demo_map.html` directly with
stakeholders. Do NOT leave a stale demo map — always regenerate before sharing.

## Directory Structure

```
agents/
  data_acquisition.py   # Agent 1: fetch FHSZ, roads, boundary, traffic
  capacity_analysis.py  # Agent 2: HCM calculations, evacuation route ID
  objective_standards.py # Agent 3: ministerial/discretionary determination

models/
  road_network.py       # RoadSegment dataclass
  project.py            # Project dataclass

config/
  parameters.yaml       # All thresholds and HCM factors (never hardcode these)
  cities/
    berkeley.yaml       # City-specific config and overrides

data/{city}/            # Cached source data (git-ignored, 90-day TTL)
  fhsz.geojson
  roads.gpkg
  boundary.geojson
  metadata.yaml

output/{city}/          # Results (git-ignored)
  routes.csv
  determination_{id}.txt
```

## Key Parameters (from config/parameters.yaml)

| Parameter | Default | Source |
|-----------|---------|--------|
| `vc_threshold` | 0.95 | Exact LOS E/F boundary, HCM 2022 |
| `unit_threshold` | 15 | ITE de minimis (21.4 vph at 15 units); SB 330 statutory anchor |
| `vehicles_per_unit` | 2.5 | U.S. Census ACS |
| `peak_hour_mobilization` | 0.57 | Berkeley mobilization study |
| `aadt_peak_hour_factor` | 0.10 | Standard peak-hour conversion |
| Evacuation route radius | 0.5 miles | per Standard 3 |

## HCM 2022 Capacity Table

| Road Type | Capacity (pc/h/lane) |
|-----------|----------------------|
| Freeway | 2,250 × lanes |
| Multilane | 1,900 × lanes |
| Two-lane ≤20 mph | 900 |
| Two-lane 25 mph | 1,125 |
| Two-lane 30 mph | 1,350 |
| Two-lane 35 mph | 1,575 |
| Two-lane ≥40 mph | 1,700 |

## LOS Table (v/c → Level of Service)

| v/c Range | LOS |
|-----------|-----|
| 0.00–0.10 | A |
| 0.10–0.20 | B |
| 0.20–0.40 | C |
| 0.40–0.60 | D |
| 0.60–0.95 | E |
| 0.95+ | F |

## Objective Standards (Agent 3)

All four standards are algorithmic — zero discretion allowed. Do NOT add any "professional judgment" or "reasonable estimate" language to the standards engine.

1. **Standard 1**: GIS point-in-polygon test against FHSZ Zone 2 or 3
2. **Standard 2**: `units >= 15` (integer comparison)
3. **Standard 3**: Network analysis to find evacuation routes within 0.5 miles
4. **Standard 4**: `baseline_vc < 0.95` AND `proposed_vc >= 0.95` for any serving route — marginal causation test; project must itself cause the threshold crossing (0.95 = exact HCM LOS E/F boundary)

**Final determination:**
```
IF std1 AND std2 AND std4 → DISCRETIONARY REVIEW REQUIRED
OTHERWISE → MINISTERIAL APPROVAL ELIGIBLE
```

## Data Sources

| Dataset | Source | Format |
|---------|--------|--------|
| FHSZ Zones | CAL FIRE OSFM ArcGIS REST API | GeoJSON |
| Road Network | OpenStreetMap via OSMnx | GeoPackage |
| City Boundary | U.S. Census TIGER | GeoJSON |
| Traffic Volumes | Caltrans AADT (PeMS) — fallback: road class estimate | CSV |

## Caching Policy

All downloaded data is cached in `data/{city}/` with a 90-day TTL. Use `--refresh` to force re-download. `metadata.yaml` records source URLs and download dates for every file (required for legal audit trail).

## Current MVP Phase

Phase 1 (MVP): Agents 1–3 only. CLI output to CSV + text. No web UI, no fee calculator, no PDF reports.

Phase 2 (next): Agent 4 (impact fee calculator) + Agent 6 (Folium maps).
Phase 3 (later): Agent 5 (Flask what-if web app) + Agent 7 (Word/PDF reports).

## Pending Methodology Work

1. ✅ **Trigger fix (marginal causation)** — `ratio_test()` in `agents/scenarios/base.py`
   Changed from absolute trigger (`baseline_vc >= threshold`) to marginal test
   (`baseline_vc < threshold AND proposed_vc >= threshold`). Projects near pre-existing
   congestion are no longer automatically DISCRETIONARY; only projects that cause a
   threshold crossing are flagged.

2. ✅ **Demand model** — `agents/capacity_analysis.py` + `agents/scenarios/base.py`
   KLD buffer model preserved as `evacuation_demand_vph` (informational). `baseline_demand_vph`
   now uses catchment-based demand (network path analysis: catchment_units × vpu × mob), which
   represents realistic per-segment load. `vehicles_per_route = project_vph` (not divided by
   n_routes) implements worst-case marginal impact test. Result: DISCRETIONARY is now
   demonstrable for constrained locations (e.g., Ridge Road, Cedar Street near capacity).

3. **Physical site access standard (new Standard 6)** — no file yet
   The Clark Street (Encinitas) problem — 200 units at end of an 18' wide dead-end street —
   is not a v/c ratio problem. It is a physical access problem governed by IFC §503
   (fire apparatus access roads). Objective thresholds already exist in adopted fire code:
   - Minimum road width: 20 ft one-way, 26 ft two-way
   - Dead-end without turnaround: flag if > 150 ft serving > N units
   - Single access point: flag for large projects (city-adopted N)
   This should be a new scenario subclass (`agents/scenarios/site_access.py`) using OSM
   `width` tags and road geometry as inputs.

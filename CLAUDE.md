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
```

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
| `vc_threshold` | 0.80 | LOS E/F boundary, HCM 2022 |
| `unit_threshold` | 50 | CEQA categorical exemption |
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
2. **Standard 2**: `units >= 50` (integer comparison)
3. **Standard 3**: Network analysis to find evacuation routes within 0.5 miles
4. **Standard 4**: `baseline_vc >= 0.80` OR `proposed_vc > 0.80` for any serving route

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

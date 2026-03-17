# Fire Evacuation Capacity Analysis System

## Project Purpose

Open-source Python pipeline that analyzes fire evacuation route capacity for California cities to:
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

# Validate project coordinates against the Census geocoder (REQUIRED after adding projects)
uv run python main.py geocode --city "Berkeley"
uv run python main.py geocode --city "Berkeley" --apply   # write corrections to YAML in place
```

## Adding Projects to a Demo YAML — Coordinate Protocol

**NEVER estimate or guess lat/lon coordinates.** Wrong coordinates place pins on the
wrong road segments and produce incorrect FHSZ lookups, ΔT calculations, and route
assignments — invalidating the legal analysis.

**Required workflow when adding a new project to any `config/projects/{city}_demo.yaml`:**

1. Set the `address` field to the human-readable project address.
2. If `address` is not a clean geocodable street address (e.g. it's an intersection
   description, annotated access note, or address range), also add a `geocode_address`
   field with a clean single-address geocodable form:
   ```yaml
   address: "599 Union St (ingress/egress) / Clark Ave (egress only), Leucadia"
   geocode_address: "599 Union St, Encinitas"
   ```
3. Set `lat`/`lon` from the Census geocoder result — run:
   ```bash
   uv run python main.py geocode --city "CityName" --apply
   ```
   This calls the U.S. Census Bureau Geocoder (no API key required) and patches the
   YAML in place while preserving all comments.
4. For projects where geocoding fails (intersection descriptions with no street number),
   look up coordinates using the parcel APN in the county assessor GIS portal or
   San Diego County SANDAG parcel viewer, then run `geocode` to confirm distance is
   within 0.5 km.
5. Regenerate the demo map:
   ```bash
   uv run python main.py demo --city "CityName"
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

**Brief / popup labeling convention (user-facing):** Criteria are labeled **A** (Applicability
Threshold — size gate), **B** (Site Parameters — FHSZ zone + degradation + threshold), and
**C** (Evacuation Clearance Analysis — routes + ΔT test) in `brief_v3.py` and the demo map
popup. SB 79 transit proximity is a separate informational scenario (no badge, footnote only).
The underlying algorithm is Standards 1–5 / 5-step; A/B/C is the presentation layer used
in all user-facing outputs (determination letter, popup, briefs).

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

## Key Parameters (from config/parameters.yaml) — v3.0 ΔT Standard

| Parameter | Default | Source |
|-----------|---------|--------|
| `unit_threshold` | 15 | ITE de minimis; SB 330 statutory anchor |
| `vehicles_per_unit` | 2.5 | U.S. Census ACS B25044 |
| `mobilization_rate` | **0.90 (constant)** | **NFPA 101 design basis; ~10% zero-vehicle HHs per Census ACS B25044** |
| `hazard_degradation.vhfhsz` | 0.35 | HCM Exhibit 10-15/10-17 + NIST Camp Fire |
| `hazard_degradation.high_fhsz` | 0.50 | HCM composite |
| `hazard_degradation.moderate_fhsz` | 0.75 | HCM composite |
| `safe_egress_window.vhfhsz` | 45 min | NIST TN 2135 (Camp Fire timeline) |
| `safe_egress_window.high_fhsz` | 90 min | Fire spread ~2× VHFHSZ window |
| `safe_egress_window.moderate_fhsz` | 120 min | Standard emergency planning |
| `safe_egress_window.non_fhsz` | 120 min | FEMA standard |
| `max_project_share` | 0.05 | Standard 5% engineering significance threshold |
| Derived ΔT thresholds (v3.4) | vhfhsz=2.25, high=4.50, mod/non=6.00 min | `safe_egress_window × max_project_share` |
| `egress_penalty.threshold_stories` | 4 | NFPA 101 / IBC |
| `egress_penalty.minutes_per_story` | 1.5 | NFPA 101 |
| `egress_penalty.max_minutes` | 12 | NFPA 101 cap |
| Evacuation route radius | 0.5 miles | per Standard 2 |
| `vc_threshold` | 0.95 | Informational only — HCM LOS E/F boundary |

**v3.4 architecture:** FHSZ does ONE thing — reduces road capacity (hazard_degradation factor). Mobilization is 0.90, always. `mobilization_rates` dict removed.

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

## Objective Standards — v3.0 ΔT Standard (Agent 3)

All standards are algorithmic — zero discretion allowed. Do NOT add "professional judgment" language.

1. **Standard 1**: `units >= 15` (integer comparison — universal size gate)
2. **Standard 2**: Buffer project location 0.5 mi → filter `EvacuationPath` objects by bottleneck/exit osmid proximity
3. **Standard 3**: GIS point-in-polygon test against CAL FIRE FHSZ; sets `project.hazard_zone` string which controls mobilization_rate and ΔT threshold; `in_fire_zone=True` for HAZ_CLASS ≥ 2
4. **Standard 4 (ΔT Test)**: `ΔT = (project_vehicles / bottleneck_effective_capacity_vph) × 60 + egress_penalty`
   - `project_vehicles = units × vpu × 0.90` (mobilization constant, NFPA 101 — not zone-dependent)
   - `egress_penalty = 0` for stories < 4; `min(stories × 1.5, 12)` for ≥ 4 stories
   - Flagged when `ΔT > threshold(hazard_zone)` where `threshold = safe_egress_window × max_project_share`
   - **No baseline precondition** — routes already at LOS F are tested equally
5. **Standard 5**: SB 79 transit proximity flag — **informational only**, never raises tier

**Final determination:**
```
DISCRETIONARY           — Std 1 met AND any serving path ΔT > threshold
CONDITIONAL MINISTERIAL — Std 1 met AND all paths ΔT within threshold
MINISTERIAL             — below size threshold (Std 1 not met)
```

**ΔT engine** (`agents/scenarios/base.py`): `compute_delta_t()` iterates `list[EvacuationPath]` from Agent 2.
**Routing** (`agents/scenarios/wildland.py`): `identify_routes()` returns `EvacuationPath` objects filtered by proximity.
**Orchestration** (`agents/objective_standards.py`): most-restrictive-wins across WildlandScenario only (Sb79TransitScenario never contributes to tier).

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

## v3.4 Migration Status (branch: feat/v3-delta-t)

✅ Replaced v/c marginal causation test with ΔT (marginal evacuation clearance time).
✅ **v3.4: Mobilization is now constant 0.90 (NFPA 101 design basis). `mobilization_rates` dict removed.**
✅ **v3.4: FHSZ affects road capacity only (hazard_degradation). Not mobilization.**
✅ Hazard-aware capacity degradation applied by Agent 2 (HCM composite + NIST Camp Fire validation).
✅ Building egress penalty (NFPA 101/IBC) for buildings ≥ 4 stories.
✅ `EvacuationPath` dataclass with per-path bottleneck tracking (argmin effective_capacity_vph).
✅ `Sb79TransitScenario` replaces `LocalDensityScenario` (informational flag, no tier impact).
✅ Audit trail v3.4: shows ΔT per path, bottleneck details, hazard degradation, egress penalty.
✅ `data/{city}/evacuation_paths.json` persisted by Agent 2 after routing.

## Pending Methodology Work

1. **Demo map hand-placement of project pins** — no file yet
   The Census geocoder can silently match the wrong block of a street that crosses I-5
   or another major barrier (e.g., "599 Union St" matched the west-of-I-5 segment when
   the actual project entry is east of I-5). The fix is a click-to-place UI in the demo map:
   - Add a "drop pin" mode to `output/{city}/demo_map.html` — user clicks the map, the
     lat/lon appears in a panel and can be copied directly into the YAML
   - OR: a standalone `place_pin.html` helper (no server needed, pure Leaflet) that opens
     the city bounding box and lets the user click to get coordinates
   - Coordinates set this way should be noted in the YAML comment as "hand-placed YYYY-MM-DD"
     rather than geocoded (see Clark Avenue Apartments in encinitas_demo.yaml for the pattern)
   - The `geocode` command already detects mismatches (MISMATCH status + km distance) and
     shows the matched address string — that is the first line of defense. Hand-placement
     is the resolution when geocoder quality is insufficient.

2. **Dual / multiple egress accounting** — methodology pending
   Clark Avenue Apartments has TWO egress points:
   - 599 Union St: primary ingress/egress (two-way, 19.5 ft wide)
   - Clark Ave: egress only (one-way outbound, 19–21 ft wide)
   The current ΔT engine finds the bottleneck of the *single worst-case* EvacuationPath.
   If a project has two independent egress paths, total egress capacity may be the sum of
   both — vehicles split across routes during evacuation.
   Questions to resolve:
   - OSM `oneway` tag is already in the graph but not surfaced to the ΔT engine — needed
     to distinguish one-way egress-only from bidirectional access
   - Should ΔT sum effective capacities across all exit paths, or take worst-case single
     path? (Conservative: worst-case; realistic: proportional capacity-split model)
   - City conditions of approval (Clark Ave egress-only by COA) must be modelable via
     `{city}_road_overrides.yaml` — not just OSM tags
   TODO: after width inference ships, inspect the Clark Ave Apartments audit trail to
   verify both Union St and Clark Ave appear as separate EvacuationPath bottlenecks.

3. **Physical site access standard (new Standard 6)** — no file yet
   The Clark Street (Encinitas) problem — 200 units at end of an 18' wide dead-end street —
   is not a v/c ratio problem. It is a physical access problem governed by IFC §503
   (fire apparatus access roads). Objective thresholds already exist in adopted fire code:
   - Minimum road width: 20 ft one-way, 26 ft two-way
   - Dead-end without turnaround: flag if > 150 ft serving > N units
   - Single access point: flag for large projects (city-adopted N)
   This should be a new scenario subclass (`agents/scenarios/site_access.py`) using OSM
   `width` tags and road geometry as inputs.

## IP & Copyright Protocol

### Copyright Header Requirement

Every new .py and .html file created in this repo must begin with the
standard copyright header:

```
# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.
```

Do not create any new source file without this header. If you modify an
existing file that lacks the header, add it.

### Dual Licensing

JOSH is dual licensed. The public license is AGPL-3.0-or-later. Thomas
Gonzalez retains the right to issue commercial licenses to third parties.
Do not add any code, dependency, or library that would compromise his ability
to do so (e.g., GPL-only dependencies with no commercial exception).

### CLA

All contributors must agree to the CLA in CONTRIBUTING.md before their
contributions can be merged. Do not merge PRs from contributors who have
not explicitly accepted the CLA terms via their PR submission.

# IT Implementation Guide

California Stewardship Fund — May 2026

**Prepared for city IT departments evaluating JOSH: technical stack, open-source components, configuration reference, and the boundary between self-service and CSF-delivered implementation**

------

## What This Guide Is For

JOSH has two distinct components, and the boundary between them matters for any IT evaluation.

The **JOSH methodology engine** is open source (AGPL-3.0) at `github.com/twgonzalez/josh`. It contains the ΔT calculation algorithm, the objective standards evaluation logic, the interactive browser client, the full parameters file, and the build CLI that generates determination maps. City IT can inspect, audit, and run every line of this code.

The **city data pipeline** — the process that acquires city-specific road network data, processes FHSZ polygons, geocodes projects, and assembles the validated inputs the engine requires — is CSF's reference implementation. It is not open source. A city can build its own data pipeline to the specifications described in this guide; the JOSH engine is agnostic about how inputs are acquired as long as the data format matches. Alternatively, CSF builds and delivers the city data under engagement.

This guide documents the open-source engine in detail — stack, dependencies, configuration files, CLI, and project format — so that city IT can make an informed evaluation. It also describes, at a specification level, what a compliant data pipeline must produce, and how CSF's engagement delivers that.

------

## Technical Stack — Open-Source Engine

The JOSH engine is a Python 3.11 command-line application with a JavaScript browser client. There is no server, no database, and no cloud dependency.

### Python dependencies

| Library | Version | Role |
|---|---|---|
| **GeoPandas** | ≥ 0.14 | Spatial data manipulation — road segments as GeoDataFrames, FHSZ polygon overlay, Census boundary clipping |
| **OSMnx** | ≥ 1.9 | Downloads OpenStreetMap road network; builds and simplifies the routing graph; provides edge geometry for path coordinate extraction |
| **NetworkX** | ≥ 3.2 | Graph data structure; Dijkstra shortest-path routing for evacuation path identification |
| **Shapely** | ≥ 2.0 | Geometric operations — point-in-polygon FHSZ test, buffer generation for route radius |
| **PyProj** | ≥ 3.6 | Coordinate reference system transformations (WGS84 ↔ UTM for distance calculations) |
| **Pandas** | ≥ 2.1 | Tabular data — road segment attributes, project records, capacity calculations |
| **PyYAML** | ≥ 6.0 | Configuration file parsing — `parameters.yaml` and city config |
| **Click** | ≥ 8.1 | CLI framework for `build.py` |
| **Rich** | ≥ 13.0 | Terminal output formatting and progress display |
| **Folium** | ≥ 0.20.0 | Leaflet map generation — road network layers, project markers, AntPath route traces |
| **SciPy** | ≥ 1.11 | Spatial indexing for proximity queries |
| **Requests** | ≥ 2.31 | HTTP client for FHSZ API and Census data downloads |

All dependencies are managed by **uv**, a fast Python package manager. Running `uv sync` in the repository root creates an isolated virtual environment and installs the exact pinned versions from `uv.lock`. No system-level Python packages are touched.

### JavaScript client

The browser-side determination map is a self-contained JavaScript application embedded in the output HTML file. It has no npm build step and no external JavaScript dependencies beyond CDN-hosted libraries:

| Library | Purpose |
|---|---|
| Leaflet.js | Interactive map rendering |
| Leaflet.Antpath | Animated evacuation route traces |
| Marked.js | Markdown rendering in the brief modal |

The client code lives in `static/` and consists of three hand-written modules:

- `static/whatif_engine.js` — the JOSH ΔT algorithm in JavaScript (generated from Python source; never edited directly)
- `static/sidebar.js` — project management UI, audit trail generation, brief rendering
- `static/brief_renderer.js` — determination letter HTML generation

### Node.js (testing only)

Node.js 20+ is required to run the test suite. It is not required to generate or view determination maps. A production deployment that does not run tests does not need Node.

```bash
node --test tests/test_whatif_engine.js    # JS engine matches Python output
node --test tests/test_brief_renderer.js   # brief HTML correctness
node --test tests/test_sidebar.js          # project CRUD and audit trail
```

### Runtime environment

| Requirement | Minimum | Recommended |
|---|---|---|
| RAM | 4 GB | 8 GB |
| Storage | 2 GB free | 10 GB (multi-city cache) |
| OS | macOS, Linux, Windows (WSL2) | macOS or Linux |
| Python | 3.11 | 3.12 |
| Internet | Required for initial data download | Not required after cache is warm |

Subsequent runs use on-disk cache and require no internet connection. First-run data download for a mid-sized California city takes 2–5 minutes.

------

## Repository Structure

```
josh/
├── build.py                  # CLI entry point — analyze, demo commands
├── pyproject.toml            # Project metadata and dependency declarations
├── uv.lock                   # Pinned dependency versions (do not edit)
│
├── config/
│   ├── parameters.yaml       # Global methodology parameters (all cities)
│   └── cities/
│       └── berkeley.yaml     # City-specific configuration (schema example)
│       └── projects/
│           └── berkeley_demo.yaml  # Project inventory for Berkeley demo
│
├── agents/                   # Analysis modules
│   ├── capacity_analysis.py  # HCM capacity calculation, exit node identification
│   ├── objective_standards.py # ΔT evaluation, tier determination
│   ├── export.py             # JOSH_DATA serialization, whatif_engine.js generation
│   └── scenarios/
│       └── wildland.py       # Dijkstra routing, path geometry, ΔT engine
│   └── visualization/
│       └── demo.py           # Folium map renderer
│
├── models/
│   ├── road_network.py       # RoadSegment dataclass
│   ├── project.py            # Project dataclass
│   └── evacuation_path.py    # EvacuationPath dataclass
│
├── static/
│   ├── sidebar.js            # Primary UI — project management, audit trail, briefs
│   ├── brief_renderer.js     # Determination letter HTML renderer (UMD module)
│   ├── whatif_engine.js      # GENERATED — JS ΔT algorithm (do not edit)
│   └── v1/
│       └── app.js            # GENERATED — bundled browser client
│
├── tests/                    # Anti-divergence and unit tests
├── docs/                     # Methodology documentation (this document is here)
└── output/berkeley/          # Berkeley demonstration output (tracked in repo)
    └── demo_map.html
```

------

## The Build CLI

All analysis and map generation runs through `build.py`. There are two commands.

### `analyze` — build the routing graph and run capacity analysis

```bash
uv run python build.py analyze \
  --city "Berkeley" \
  --data-dir /path/to/data/berkeley
```

**What it does:**

1. Loads `config/parameters.yaml` and `config/cities/berkeley.yaml`
2. Reads pre-acquired city data from `--data-dir`:
   - `roads.gpkg` — validated road network with HCM classification
   - `fhsz.geojson` — city FHSZ polygons
   - `boundary.geojson` — city boundary
3. Identifies evacuation exit nodes (boundary-adjacent nodes on primary/arterial roads)
4. Computes effective capacity for every road segment (HCM base capacity × FHSZ degradation factor)
5. Exports `graph.json` and `whatif_engine.js` to `output/{city}/`

`analyze` must be run before `demo`. It produces the data the browser engine consumes.

### `demo` — generate the interactive determination map

```bash
uv run python build.py demo \
  --city "Berkeley" \
  --data-dir /path/to/data/berkeley \
  --projects config/projects/berkeley_demo.yaml
```

**What it does:**

1. Reads `graph.json` from the previous `analyze` run
2. Evaluates each project in the `--projects` YAML:
   - Geocodes to the road network
   - Runs Dijkstra routing to identify all serving evacuation paths
   - Computes ΔT and egress penalty for each path
   - Assigns determination tier (Ministerial / Conditional Ministerial / Discretionary)
3. Generates Folium map layers — road network, FHSZ overlay, project markers, AntPath route traces
4. Embeds `window.JOSH_DATA` and the browser client into a single self-contained HTML file
5. Writes `output/{city}/demo_map.html`

The output HTML file works from `file://` — no web server required to view it.

------

## The Parameters File

`config/parameters.yaml` is the canonical source for every methodology constant. It is plain text, fully commented, and includes a source citation for every value. Every city uses the same parameters file; city-specific overrides are applied in the city config (described below).

Key parameters relevant to IT review:

```yaml
parameters_version: "4.0"

unit_threshold: 15           # Size gate — projects below this receive Ministerial automatically
mobilization_rate: 0.90      # NFPA 101 design basis — constant for all zones

hazard_degradation:
  factors:
    vhfhsz: 0.35             # HCM Exhibit 10-15/10-17 composite + NIST Camp Fire
    high_fhsz: 0.50
    moderate_fhsz: 0.75
    non_fhsz: 1.00

safe_egress_window:
  vhfhsz: 45                 # NIST TN 2135 — Camp Fire timeline (minutes)
  high_fhsz: 90
  moderate_fhsz: 120
  non_fhsz: 120

max_project_share: 0.05      # 5% — the one policy value the city adopts by resolution

vehicles_per_unit: 2.5       # Census ACS Table B25044 — California average

egress_penalty:
  threshold_stories: 4       # NFPA 101 high-rise threshold
  minutes_per_story: 1.5     # NFPA 101 stair descent rate
  max_minutes: 12            # Cap

hcm_capacity:
  freeway:
    capacity_per_lane: 2250  # HCM 2022, Exhibit 12-6
  multilane:
    capacity_per_lane: 1900  # HCM 2022, Exhibit 12-7
  two_lane:
    by_speed:                # HCM 2022, Chapter 15
      20: 900
      25: 1125
      30: 1350
      35: 1575
      40: 1700

cache_ttl_days: 90           # Downloaded data cache lifetime
```

**Nothing in this file is chosen by the city.** Every value traces to a published standard or federal dataset cited in the comments. The city adopts `max_project_share: 0.05` by council resolution as the single policy value; all thresholds are computed from it at runtime.

To change a parameter for a specific city — for example, if city-specific Census data shows a different vehicle ownership rate — the override goes in the city config file, not here. The global file is not edited per city.

------

## City Configuration

Each city has a configuration file at `config/cities/{city_slug}.yaml`. This file identifies the city to the Census TIGER boundary system, configures the FHSZ data source, and provides any city-specific parameter overrides.

The Berkeley file is the canonical schema example. Annotated structure:

```yaml
city_name: "Berkeley"
state: "CA"
state_fips: "06"
county_fips: "001"           # Alameda County
place_fips: "06000"          # Berkeley Census PLACE code

# OSMnx place query — used to download the road network
osmnx_place: "Berkeley, California, USA"

# ── FHSZ Data Source ───────────────────────────────────────────────────────
# Cal Fire's standard HHZ_ref_FHSZ API returns State Responsibility Area zones
# only. Most incorporated California cities are Local Responsibility Area (LRA)
# and receive zero features from the standard API.
#
# Option A — local file (pre-downloaded GeoJSON):
fhsz_local_file: "config/cities/fhsz/berkeley_fhsz.geojson"

# Option B — alternative API (county or city GIS FeatureServer):
fhsz_fallback_api: "https://services7.arcgis.com/.../FeatureServer/0"
# JOSH tries fhsz_local_file first; falls back to fhsz_fallback_api if absent.

# ── Boundary Source ────────────────────────────────────────────────────────
# Standard cities: Census TIGER (auto-downloaded using state_fips + place_fips)
# Non-municipal jurisdictions (fire districts, special districts):
# boundary_file: "config/cities/boundaries/rsf_fire_boundary.geojson"
# When boundary_file is set, JOSH uses the pre-built GeoJSON instead of TIGER.

# ── Routing Exit Nodes ─────────────────────────────────────────────────────
# Standard cities: auto-detected from boundary-adjacent primary/arterial roads.
# Clipped-network jurisdictions (fire districts where boundary cuts roads mid-segment):
# known_exit_nodes:
#   - 49171047     # Via de la Valle → I-5 (179m inside western boundary)
#   - 3522701601   # S Rancho Santa Fe Rd → SR-56/I-15

# ── Coordinate Reference Systems ───────────────────────────────────────────
crs: "EPSG:4326"             # WGS84 — storage and output
analysis_crs: "EPSG:26910"   # UTM Zone 10N — distance calculations (meters)

# ── City-Specific Overrides ────────────────────────────────────────────────
# Leave empty to use parameters.yaml defaults.
overrides: {}
# Examples:
#   unit_threshold: 10       # Lower threshold for more constrained network
#   vehicles_per_unit: 2.3   # If local ACS B25044 differs from 2.5 default
#   safe_egress_window:      # Only if city has commissioned a fire behavior study
#     vhfhsz: 30             # with documented timelines for local terrain/wind
```

**For non-municipal jurisdictions** (fire protection districts, county service areas), three additional keys are required:

```yaml
# Pre-built district boundary GeoJSON (Census TIGER has no entry for fire districts)
boundary_file: "config/cities/boundaries/rsf_fire_boundary.geojson"

# LRA FHSZ source (SD County OES FeatureServer works for San Diego County LRA)
fhsz_fallback_api: "https://gis-public.sandiegocounty.gov/arcgis/..."

# Explicit exit node IDs — required when boundary clipping leaves primary road
# endpoints 100-500m inside the boundary, outside the default 50m proximity threshold
known_exit_nodes:
  - 49171047      # Via de la Valle, lat=32.987, lon=-117.217
  - 3522701601    # S Rancho Santa Fe Road, lat=33.034, lon=-117.235
```

------

## Project Specification

Projects are defined in YAML files — one file per city, typically maintained by planning staff. Each file has a header and a `projects` list.

```yaml
city: "Berkeley"
state: "CA"
description: "Berkeley AB 747 — Ministerial vs Discretionary Demo"

projects:

  - name: "Ashby Small Infill"
    address: "Ashby BART Station Area"
    lat: 37.8528
    lon: -122.2699
    units: 10
    stories: 2
    description: >
      10-unit project at Ashby BART — below the 15-unit size threshold.
      Qualifies for ministerial approval regardless of route conditions.
    expected_tier: "MINISTERIAL"

  - name: "Downtown Mid-Rise"
    address: "2100 Telegraph Ave, Berkeley"
    lat: 37.8654
    lon: -122.2595
    units: 75
    stories: 3
    description: >
      75-unit project on Telegraph Ave. ΔT exceeds threshold on serving
      route — single-access local street at capacity during evacuation.
    expected_tier: "DISCRETIONARY"
```

**Required fields:** `name`, `lat`, `lon`, `units`, `stories`

**Optional fields:** `address` (human-readable), `description` (appears in sidebar), `expected_tier` (used by the test suite to verify determinations haven't changed)

### Coordinate protocol

Coordinates must be verified — wrong coordinates produce wrong FHSZ lookups, wrong route assignments, and wrong ΔT results that will not survive developer scrutiny. The correct workflow:

1. Set `address` to the human-readable project address from the application.
2. Validate coordinates using the U.S. Census Bureau Geocoder (no API key required):
   ```
   https://geocoding.geo.census.gov/geocoder/
   ```
3. For addresses that the geocoder cannot resolve (intersections, address ranges, parcels without street numbers), look up coordinates from the county assessor GIS portal using the parcel APN.
4. Add a comment to the YAML entry noting the source:
   ```yaml
   lat: 33.0521   # Census geocoder match — confirmed 2026-04-15
   lon: -117.2813
   # -or-
   lat: 33.0521   # Hand-placed from SD County SANDAG parcel viewer — 2026-04-15
   lon: -117.2813
   ```

For projects with multiple access points, the coordinate should correspond to the primary vehicle egress point — the location where project vehicles enter the road network — not the building centroid.

### Geocode address vs. display address

Where the project address is an intersection description, an access note, or an address range that the geocoder cannot resolve, use a separate `geocode_address` field:

```yaml
- name: "Clark Ave Apartments"
  address: "599 Union St (ingress/egress) / Clark Ave (egress only), Leucadia"
  geocode_address: "599 Union St, Encinitas"
  lat: 33.0521
  lon: -117.2813
  units: 200
  stories: 4
```

------

## What the Engine Requires as Input

The `build.py analyze` command reads pre-processed city data from the `--data-dir` directory. This is where the boundary between the open-source engine and CSF's data pipeline lies. The engine is agnostic about how these files were produced; it requires only that they conform to the following specifications.

### `roads.gpkg` — road network GeoPackage

A GeoPackage containing road segment geometries with the following attribute columns:

| Column | Type | Description |
|---|---|---|
| `osmid` | int or list | OSM way ID |
| `highway` | str | OSM highway tag (validated and corrected) |
| `road_type` | str | Derived: `freeway`, `multilane`, or `two_lane` |
| `lanes` | int | Lane count per direction |
| `speed_kph` | float | Posted speed limit, converted to kph |
| `length` | float | Segment length in meters |
| `geometry` | LineString | Full road geometry (not just endpoints) |
| `name` | str | Street name (may be null) |
| `oneway` | bool | True if one-way |
| `highway_original` | str | Pre-override OSM tag (audit trail) |
| `override_reason` | str | Reason for any reclassification (audit trail) |

Road segments must use the OSM highway tag vocabulary. The engine maps tags to HCM road types using `road_type_mapping` in `parameters.yaml`. Segments with highway tags not in the mapping are excluded from the routing graph.

### `fhsz.geojson` — FHSZ polygons

A GeoJSON FeatureCollection in EPSG:4326 containing FHSZ polygons with a `HAZ_CLASS` attribute:

| `HAZ_CLASS` | Meaning |
|---|---|
| 1 | Moderate |
| 2 | High |
| 3 | Very High |

The engine performs a point-in-polygon test for each road segment midpoint to assign the applicable degradation factor. Segments not covered by any polygon receive `non_fhsz` (degradation factor 1.00).

For LRA jurisdictions where Cal Fire's SRA API returns no features, the GeoJSON must be sourced from the locally adopted FHSZ ordinance, a county GIS service, or a pre-downloaded and validated dataset. The source and validation date must be recorded in the city metadata.

### `boundary.geojson` — city boundary

A GeoJSON Polygon or MultiPolygon in EPSG:4326 representing the city's jurisdictional boundary. Used to clip the OSM road network to the analysis area and to identify boundary-adjacent exit nodes.

For standard cities: derived from Census TIGER PLACE boundaries.
For non-municipal jurisdictions: derived from county LAFCO MapServer or equivalent authoritative source.

### `graph.graphml` — routing graph (produced by `analyze`, consumed by `demo`)

An OSMnx-format GraphML file representing the simplified directed road network. Produced by `build.py analyze` from `roads.gpkg`; consumed by `build.py demo`. Cities do not need to produce this file — the engine generates it from the road network.

------

## Road Override Specification

OSM road classifications are frequently incorrect for private roads, covenant communities, recently reclassified streets, and fire district service areas. The engine supports a correction file — `{city}_road_overrides.yaml` — that applies validated corrections before the routing graph is built.

```yaml
road_overrides:

  # Match by road name — corrects all segments with this name
  - name: "La Granada"
    highway: "secondary"
    reason: "Internal covenant road; primary tag is an OSM error"
    osm_correction_pending: true

  # Match by OSM way ID — corrects a specific segment
  - osmid: "6024716"
    width_ft: 18
    access_type: "dead_end"
    reason: "Clark Ave — below IFC §503 20-ft minimum (City Engineering Survey 2024-03)"
    source: "City Engineering Survey 2024-03"

  # Override speed and lane count
  - name: "Linea del Cielo"
    highway: "tertiary"
    lanes: 2
    speed: 25
    reason: "Hilltop residential dead-end; secondary tag overstates capacity"
```

Every override entry requires a `reason`. Overrides are applied uniformly — they affect all future analyses for that city, not a specific project. The audit trail records which segments were overridden and why.

------

## Validation

The JOSH repository includes an anti-divergence test suite that verifies the JavaScript browser engine produces results identical to the Python reference implementation for the same inputs.

```bash
# Run the full test suite
node --test tests/test_whatif_engine.js
node --test tests/test_brief_renderer.js
node --test tests/test_sidebar.js
```

The `test_whatif_engine.js` test reads `test_vectors.json` — generated by `build.py analyze` from the Berkeley reference dataset — and confirms that the JS engine produces matching ΔT values and tier determinations. A passing test suite means the browser's real-time what-if calculations are consistent with the Python methodology.

For any city implementation, city IT should run the test suite after initial setup and after any methodology update. A failing test indicates that the browser engine and the Python engine have diverged — any determination produced during that window must be re-evaluated.

------

## Working with CSF

Building a city data pipeline — acquiring roads, resolving FHSZ data, correcting OSM classifications, validating exit nodes, and producing the `roads.gpkg` / `fhsz.geojson` / `boundary.geojson` files the engine requires — is specialist work. It requires GIS expertise, local regulatory knowledge, and a validated quality-control process. CSF has built and maintained this pipeline across multiple California cities and fire protection districts.

A CSF engagement delivers:

- **Validated city data** conforming to the input specifications above, with every road classification correction documented and defensible
- **FHSZ data resolution** for the city's specific regulatory context — SRA vs. LRA, county GIS integration, locally adopted zone mapping
- **Routing configuration** — exit node validation, boundary clipping review, path geometry verification
- **The determination map** — `output/{city}/demo_map.html`, validated against the anti-divergence test suite and ready for planning staff use
- **Administrative record documentation** — a data provenance package suitable for inclusion in the city's legal record, covering every data source, every override, and every validation step

For ongoing support — data refreshes when road networks change, methodology updates when legal standards evolve, or expert witness availability when a determination is challenged — CSF and the city can discuss what a Memorandum of Understanding would cover.

Cities that want to evaluate CSF's approach, review a sample data provenance package, or discuss what an engagement would involve are encouraged to reach out. The Berkeley demonstration map — accessible from this site — shows what a completed implementation produces.

------

## Summary: Open Source vs. CSF-Delivered

| Component | Available | Self-Service Path |
|---|---|---|
| ΔT algorithm and objective standards engine | Public repo (AGPL-3.0) | Inspect, audit, run `build.py` |
| Browser client (sidebar, brief renderer, what-if panel) | Public repo (AGPL-3.0) | Embedded in output HTML |
| `parameters.yaml` — all methodology constants | Public repo | Read, verify, submit overrides via city config |
| `build.py analyze` and `build.py demo` CLI | Public repo | Run with validated city data |
| Anti-divergence test suite | Public repo | `node --test` after setup and updates |
| City configuration file | City-maintained | Follow schema in this guide |
| Project YAML file | City-maintained | Planning staff add projects as applications arrive |
| Road network acquisition and classification | CSF pipeline | Build own pipeline per input spec above |
| FHSZ polygon acquisition and LRA resolution | CSF pipeline | Build own pipeline per input spec above |
| Exit node validation for clipped networks | CSF expertise | Follow known_exit_nodes guidance |
| Administrative record documentation | CSF engagement | City staff responsible for self-built implementation |
| Ongoing refresh and methodology updates | CSF engagement (MOU) | City IT manages update cadence |

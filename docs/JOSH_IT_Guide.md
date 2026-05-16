# IT Implementation Guide

California Stewardship — May 2026

**Prepared for city IT departments evaluating JOSH for self-hosted deployment**

------

## JOSH Is Genuinely Open Source

JOSH is open source in the functional sense, not just the legal one. The public repository at `github.com/twgonzalez/josh` includes the complete methodology engine, the full Berkeley reference dataset, and everything needed to run a real analysis and generate a real determination map without installing anything beyond standard Python tooling. No registration, no API key, no license agreement, no call home.

A city IT department that clones the repository can have a working Berkeley determination map running in under ten minutes.

That is the starting point for evaluating JOSH. Everything that follows describes what is in the box, what it takes to run it for a different city, and how California Stewardship can help if the city wants expert support for implementation.

------

## Try It Now — Berkeley Reference Dataset

The Berkeley reference dataset is committed directly to the repository. After cloning, no data download is required to run the full analysis pipeline.

```bash
# Clone the repository
git clone https://github.com/twgonzalez/josh.git
cd josh

# Install uv (Python environment manager) if not already present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all Python dependencies into an isolated environment
uv sync

# Run capacity analysis on the included Berkeley dataset
uv run python build.py analyze \
  --city "Berkeley" \
  --data-dir data/berkeley

# Generate the interactive determination map
uv run python build.py map \
  --city "Berkeley" \
  --data-dir data/berkeley \
  --projects config/projects/berkeley_demo.yaml

# Open the result
open output/berkeley/analysis_map.html   # macOS
# or: start output/berkeley/analysis_map.html  (Windows)
# or: xdg-open output/berkeley/analysis_map.html  (Linux)
```

The output is a single self-contained HTML file. It works from the file system — no web server required. Open it in any browser and it is fully functional: interactive map, project sidebar, determination briefs, downloadable audit trails, what-if analysis panel.

The included Berkeley data files are:

| File | Contents |
|---|---|
| `data/berkeley/roads.gpkg` | OpenStreetMap road network with HCM classifications |
| `data/berkeley/fhsz.geojson` | Cal Fire Fire Hazard Severity Zone polygons |
| `data/berkeley/boundary.geojson` | Berkeley city boundary (Census TIGER) |
| `data/berkeley/block_groups.geojson` | Census ACS block groups |
| `data/berkeley/graph.graphml` | Pre-built OSMnx routing graph |
| `config/cities/berkeley.yaml` | Berkeley city configuration |
| `config/projects/berkeley_demo.yaml` | Six demonstration projects |

------

## Technical Stack

### Python

JOSH requires Python 3.11 or later, managed by **uv**. Running `uv sync` creates an isolated virtual environment and installs all dependencies automatically — no system-level packages are affected.

| Library | Role |
|---|---|
| **GeoPandas** | Road network as spatial GeoDataFrames; FHSZ polygon overlay; Census boundary clipping |
| **OSMnx** | Builds and simplifies the routing graph from road network data; provides full edge geometry for route traces |
| **NetworkX** | Directed graph data structure; Dijkstra shortest-path routing for evacuation path identification |
| **Shapely** | Point-in-polygon FHSZ test per road segment; project buffer generation |
| **PyProj** | Coordinate system transforms (WGS84 ↔ UTM for metric distance calculations) |
| **Pandas** | Tabular road segment attributes; capacity calculations; project records |
| **PyYAML** | Parses `parameters.yaml` and city config files |
| **Folium** | Generates the Leaflet map — road layers, FHSZ overlay, project markers, animated route traces |
| **Click + Rich** | CLI interface and terminal output |

### JavaScript

The browser client is embedded directly in the output HTML. It has no build step. Three hand-written modules handle everything the user sees after opening the file:

| File | Role |
|---|---|
| `static/whatif_engine.js` | The JOSH ΔT algorithm in JavaScript — generated from the Python source, never edited directly |
| `static/sidebar.js` | Project management, route visualization, audit trail export, brief modal |
| `static/brief_renderer.js` | Determination letter HTML generation |

The browser client loads Leaflet, Leaflet.Antpath, and Marked from CDN. The map works offline once the file is open; CDN libraries are only needed on first load.

### Node.js (test suite only)

Node.js 20+ is required to run the anti-divergence test suite. It is not required to generate or view determination maps.

```bash
node --test tests/test_whatif_engine.js   # JS engine matches Python output exactly
node --test tests/test_brief_renderer.js  # brief HTML correctness
node --test tests/test_sidebar.js         # project CRUD and audit trail
```

### Hardware requirements

JOSH runs on any modern workstation or laptop. 8 GB RAM and a standard SSD are comfortable for any California city. First-run analysis for a mid-sized city takes 1–3 minutes; subsequent runs from cached data take under 30 seconds.

------

## Repository Structure

```
josh/
├── build.py                        # CLI — analyze and demo commands
├── config/
│   ├── parameters.yaml             # All methodology constants — annotated with citations
│   └── cities/
│       ├── berkeley.yaml           # City config schema reference
│       └── projects/
│           └── berkeley_demo.yaml  # Project inventory for the Berkeley demo
├── agents/                         # Analysis modules
│   ├── capacity_analysis.py        # HCM calculations, exit node identification
│   ├── objective_standards.py      # ΔT evaluation, tier determination
│   ├── export.py                   # JOSH_DATA serializer, whatif_engine.js generator
│   └── scenarios/wildland.py       # Dijkstra routing, path geometry, ΔT engine
│   └── visualization/demo.py       # Folium map renderer
├── models/                         # Data model dataclasses
├── static/                         # Browser client source
├── tests/                          # Anti-divergence and unit tests
├── data/berkeley/                  # Berkeley reference dataset (committed)
└── output/berkeley/                # Berkeley reference output (committed)
```

------

## The Build Commands

### `analyze` — capacity analysis

```bash
uv run python build.py analyze \
  --city "Berkeley" \
  --data-dir data/berkeley
```

Reads the city data files, runs HCM 2022 capacity calculations on every road segment, applies FHSZ degradation factors, identifies evacuation exit nodes and bottleneck paths, and exports the browser data bundle:

- `output/{city}/graph.json` — road network and capacity data for the browser engine
- `output/{city}/parameters.json` — methodology parameters
- `output/{city}/fhsz.json` — FHSZ polygons for the map overlay
- `static/whatif_engine.js` — regenerated JavaScript ΔT engine
- `output/{city}/routes.csv` — tabular evacuation route inventory

### `demo` — determination map

```bash
uv run python build.py map \
  --city "Berkeley" \
  --data-dir data/berkeley \
  --projects config/projects/berkeley_demo.yaml
```

Reads the project inventory, runs Dijkstra routing from each project site to the network boundary, computes ΔT and egress penalty, assigns determination tier, generates the Folium map with all layers and animated route traces, embeds the full JOSH_DATA bundle and browser client, and writes:

- `output/{city}/analysis_map.html` — the self-contained determination map

`analyze` must run before `demo`. After that, adding a new project only requires updating the projects YAML and re-running `demo` — the capacity analysis does not need to repeat.

### `report` — AB 747 city-wide evacuation capacity report

```bash
uv run python build.py report \
  --city "Berkeley" \
  --data-dir data/berkeley
```

Generates the city-wide evacuation capacity report required under Government Code §65302.15 (AB 747). `analyze` must run before `report` — the report reads the capacity analysis outputs along with the Census ACS block group data:

- `output/{city}/ab747_report.html` — the self-contained HTML report

The report inventories every residential block group in the city, identifies which are in FHSZ zones and lack a second independent evacuation route, and summarizes total exit capacity in vehicles per hour. It is the input to a city's AB 747 Safety Element update and the supporting document for an AB 1600 nexus study if the city pursues impact fees.

The included Berkeley data files already contain everything `report` needs:

| Additional file | Contents |
|---|---|
| `data/berkeley/block_groups.geojson` | Census ACS block groups with residential unit counts |

`analyze` and `demo` are the city-specific steps. `report` is the policy-facing output that connects the technical analysis to the Safety Element and nexus study workflows.

------

## The Parameters File

`config/parameters.yaml` contains every methodology constant. It is plain text, fully commented, and includes a source citation for every value. Nothing in this file was chosen by any city or consultant — every number traces to a published national standard or federal dataset.

```yaml
parameters_version: "4.0"

unit_threshold: 15           # Size gate — integer comparison, ITE de minimis / SB 330

behavioral_mobilization: 0.90  # FHWA Emergency Transportation Operations — mandatory
                               # evacuation compliance rate (constant, all zones)

hazard_degradation:
  factors:
    vhfhsz: 0.35             # HCM Exhibit 10-15/10-17 + NIST Camp Fire validation
    high_fhsz: 0.50
    moderate_fhsz: 0.75
    non_fhsz: 1.00

safe_egress_window:
  vhfhsz: 45                 # NIST TN 2135 — Camp Fire minute-by-minute reconstruction
  high_fhsz: 90
  moderate_fhsz: 120
  non_fhsz: 120

max_project_share: 0.05      # The single policy value the city adopts by resolution.
                             # All thresholds computed at runtime: window × 0.05

vehicles_per_unit: 1.9       # Census ACS Table B25044 — California statewide all-HH average

egress_penalty:
  threshold_stories: 4       # NFPA 101 high-rise threshold
  minutes_per_story: 1.5     # NFPA 101 stair descent rate
  max_minutes: 12            # Cap at 8-story equivalent

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
```

City-specific overrides — a different `vehicles_per_unit` from local ACS data, for instance — go in the city config file, not here. The global parameters file is shared by all cities and is not edited per project.

**How to override `vehicles_per_unit` and `behavioral_mobilization` correctly.** These two parameters cover separate concerns and should be adjusted independently:

- `vehicles_per_unit` captures the vehicle *ownership* dimension. The default 1.9 is the Census ACS B25044 California statewide all-household average, which already includes zero-vehicle households (they reduce the average by contributing zero vehicles). Override this with the city's own ACS B25044 figure if the local rate differs materially from the statewide average. Cities with high transit ridership typically have lower local averages.

- `behavioral_mobilization` captures the evacuation *compliance* dimension — the fraction of households that reach the road during a mandatory evacuation. The default 0.90 is the FHWA Emergency Transportation Operations compliance rate. Override this only with documented local evidence: an adopted evacuation plan with a modeled compliance rate, a post-event study, or a licensed transportation engineer's finding.

Do not adjust both parameters to account for the same population. Zero-vehicle households are already reflected in `vehicles_per_unit`; if you lower `vehicles_per_unit` to reflect local zero-car rates, do not also lower `behavioral_mobilization` to further account for them. That would undercount demand by applying the same deduction twice.

------

## City Configuration

Each city has a YAML config file at `config/cities/{city_slug}.yaml`. The Berkeley file is the canonical reference. Key fields:

```yaml
city_name: "Berkeley"
state: "CA"
place_fips: "06000"                  # Census PLACE code (for TIGER boundary download)
osmnx_place: "Berkeley, California, USA"

# FHSZ data source
# Option A — pre-downloaded local file:
fhsz_local_file: "config/cities/fhsz/berkeley_fhsz.geojson"
# Option B — ArcGIS FeatureServer (county GIS):
fhsz_fallback_api: "https://services7.arcgis.com/.../FeatureServer/0"

# For non-municipal jurisdictions (fire districts, special districts):
# boundary_file: "config/cities/boundaries/rsf_fire_boundary.geojson"
# known_exit_nodes:
#   - 49171047     # Via de la Valle → I-5
#   - 3522701601   # S Rancho Santa Fe Rd → SR-56

# City-specific parameter overrides (optional — leave empty for defaults)
overrides: {}
# overrides:
#   vehicles_per_unit: 1.7   # if local Census B25044 differs from 1.9 statewide
#   unit_threshold: 10       # if city adopts a lower size gate by resolution
```

------

## Project Specification

Projects are plain-text YAML, maintained by planning staff. One file per city, one entry per project:

```yaml
city: "Berkeley"
description: "Berkeley AB 747 — Ministerial vs Discretionary Demo"

projects:

  - name: "Ashby Small Infill"
    address: "Ashby BART Station Area, Berkeley"
    lat: 37.8528
    lon: -122.2699
    units: 10
    stories: 2
    description: "Below the 15-unit size threshold — Ministerial regardless of route."
    expected_tier: "MINISTERIAL"

  - name: "Hills Gateway"
    address: "Hills Gateway, Berkeley"
    lat: 37.8914
    lon: -122.2494
    units: 80
    stories: 4
    description: "VHFHSZ zone, constrained canyon road — ΔT far exceeds threshold."
    expected_tier: "DISCRETIONARY"
```

**Required fields:** `name`, `lat`, `lon`, `units`, `stories`

**Coordinates must be verified.** Wrong coordinates produce wrong FHSZ lookups, wrong route assignments, and wrong ΔT results. The workflow:

1. Start with the U.S. Census Bureau Geocoder (free, no API key): `geocoding.geo.census.gov`
2. For parcels without a clean street address, use the county assessor GIS portal with the APN
3. Note the coordinate source in a YAML comment — geocoder match, hand-placed from parcel viewer, etc.
4. For projects with multiple access points, the coordinate should be the primary vehicle egress point, not the building centroid

Where the project address is an intersection or access description that the geocoder cannot resolve, use a `geocode_address` field alongside the display address:

```yaml
- name: "Clark Ave Apartments"
  address: "599 Union St (ingress/egress) / Clark Ave (egress only)"
  geocode_address: "599 Union St, Encinitas, CA"
  lat: 33.0521
  lon: -117.2813
  units: 200
  stories: 4
```

------

## Adding a City

To add a city beyond Berkeley, three data files are needed: a road network, an FHSZ polygon layer, and a city boundary. Once those are in place, `build.py` does the rest.

**Road network (`roads.gpkg`)**

OSMnx downloads the road network from OpenStreetMap automatically given the city name or a boundary polygon. The key consideration is classification quality: OSM highway tags drive HCM capacity assignments, and tags are frequently wrong for private roads, covenant communities, recently reclassified streets, and non-standard jurisdictions. Incorrect tags inflate or deflate road capacity and can move a project across the determination threshold.

A road override file — `{city}_road_overrides.yaml` — corrects errors before the routing graph is built. Every correction requires a documented reason:

```yaml
road_overrides:
  - name: "La Granada"
    highway: "secondary"
    reason: "Internal covenant road; primary tag is an OSM error"

  - osmid: "6024716"
    width_ft: 18
    access_type: "dead_end"
    reason: "Clark Ave — below IFC §503 minimum width (City Engineering Survey 2024-03)"

  - osmid: "12345678"
    capacity_vph: 800
    reason: "Field count shows 800 vph peak throughput — HCM formula overestimates due to signal interference at Oak/Main"
    source: "Caltrans TMC count 2024-08-15 (PE stamp: J. Smith PE #12345)"
```

Supported override fields:

- `highway` — reclassify OSM highway tag; re-derives road type and lane count
- `lanes` — correct lane count (HCM input)
- `speed` — correct speed limit in mph (HCM input)
- `width_ft` — physical road width in feet (stored for future Standard 6 / IFC §503 analysis)
- `access_type` — `dead_end` | `single_access` | `one_way` | `two_way`
- `capacity_vph` — sets bottleneck capacity directly (post-HCM), in vehicles per hour. Requires `reason` and `source`. Use only when a PE-stamped field count or agency traffic study supersedes the HCM formula for a specific segment. `effective_capacity_vph` = `capacity_vph` × FHSZ degradation factor still applies.

**FHSZ polygons (`fhsz.geojson`)**

Cal Fire's standard API (`egis.fire.ca.gov`) returns State Responsibility Area zones only. Most incorporated California cities are Local Responsibility Area (LRA) and get zero features from the standard endpoint. LRA FHSZ data must come from an alternative source: a county GIS FeatureServer, a locally adopted ordinance GeoJSON, or the Cal Fire FRAP statewide shapefile clipped to the city boundary. Getting this right matters — a project whose site FHSZ zone is misidentified receives the wrong threshold.

**Boundary (`boundary.geojson`)**

Standard cities: auto-downloaded from Census TIGER using `place_fips` in the city config.
Fire protection districts and other non-municipal jurisdictions: constructed from the county LAFCO MapServer or equivalent authoritative source. For clipped-network jurisdictions, primary exit nodes must be specified explicitly in `known_exit_nodes` — see the Berkeley config for the pattern.

------

## Validation

The test suite verifies that the JavaScript browser engine produces results identical to the Python reference implementation. Run it after initial setup and after any methodology update:

```bash
node --test tests/test_whatif_engine.js    # anti-divergence: JS matches Python
node --test tests/test_brief_renderer.js   # brief HTML correctness
node --test tests/test_sidebar.js          # project management and audit trail
```

`test_whatif_engine.js` reads `output/berkeley/test_vectors.json` — generated by `analyze` — and confirms the browser engine produces matching ΔT values and tier determinations for every Berkeley project. A passing suite means the real-time what-if panel in the browser is consistent with the Python methodology.

------

## Working with California Stewardship

The methodology is public. The data is documented. The code runs. Cities that have the GIS and Python capability to work through the road classification and FHSZ resolution steps for their own jurisdiction can do so independently.

For cities that want expert support — validated road classification, LRA FHSZ data resolution, exit node configuration, administrative record documentation, or ongoing maintenance as methodology updates are released — California Stewardship delivers city implementations under engagement. Where that relationship is ongoing, a Memorandum of Understanding is the typical instrument.

To discuss what an engagement would involve, or to ask questions about self-implementation, reach out at info@californiastewardship.org. The Berkeley map linked from this site shows exactly what a completed implementation looks like.

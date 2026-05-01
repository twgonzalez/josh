# IT Implementation Guide

California Stewardship Fund — May 2026

**Prepared for city IT departments evaluating JOSH for self-hosted deployment**

------

## What This Guide Is For

JOSH is open source software. Every line of code is publicly available, auditable, and licensed under AGPL-3.0. A city IT department with standard Python and GIS tooling can deploy JOSH independently, run it against the city's own data, and produce legally defensible determination maps — without purchasing a license, subscribing to a service, or depending on any external infrastructure.

This guide explains what that looks like in practice: what the software is, what it requires, what it touches, and what it produces. It also describes how California Stewardship Fund can support cities that want help with initial setup, methodology validation, or keeping pace with legal and parameter updates — and how that engagement can be structured without creating a dependency.

------

## What JOSH Is — and What It Isn't

JOSH is a Python command-line tool. It is not a web application, a SaaS platform, a cloud service, or an AI system. It has no server component, no database, no login system, and no ongoing operational infrastructure. It runs on a workstation or laptop, downloads public data, runs a deterministic calculation, and writes a static HTML file to disk.

That HTML file is the deliverable. It is self-contained — all data and rendering code are embedded — and opens in any browser directly from the file system. No web server is required to view or distribute it. A planner can open it by double-clicking the file. A city attorney can receive it by email. A council member can view it on a tablet without an internet connection.

There is no JOSH account to create, no API key to manage, no cloud credential to rotate, and no usage data sent back to California Stewardship Fund or anyone else. The software is a pipeline that reads public data and writes a file.

------

## Technical Prerequisites

A city IT department running JOSH needs four standard tools:

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime for all analysis code |
| uv | Latest | Python environment and dependency manager |
| Node.js | 20+ | Runs the JavaScript test suite (developer verification only — not required for production use) |
| git | Any modern version | Pulls the JOSH source code and tracks city-specific configuration |

All four are available on macOS, Windows, and Linux. All four are free. No additional licenses are required.

Python library dependencies — GeoPandas, OSMnx, NetworkX, Shapely, PyYAML, Click, and Rich — are managed automatically by uv and installed into an isolated virtual environment on first run. They do not affect the system Python installation.

A machine with 8 GB of RAM and a standard SSD is adequate for any California city. The most computationally intensive step — building the OSMnx routing graph for a city — completes in under 60 seconds and its result is cached to disk for all subsequent runs.

------

## The Two-Repo Architecture

JOSH uses a two-repository structure designed to separate the public methodology from city-specific data.

**The public repository** (`github.com/twgonzalez/josh`) contains the methodology engine: the road network analysis code, the ΔT calculation, the objective standards evaluation, the map renderer, and the JavaScript client that runs in the browser. This repository is open source under AGPL-3.0. The city can fork it, inspect it, and modify it. Methodology updates from California Stewardship Fund are released here and can be pulled at the city's discretion.

**The city-private repository** contains everything specific to the city: the city configuration file, the project YAML files with applicant data, any road override corrections, and the generated output maps. This repository lives on the city's own infrastructure — a city-managed GitHub organization, a city-run GitLab instance, or any standard git host. California Stewardship Fund never has access to it unless the city explicitly shares it.

The two repositories communicate by a single environment variable: `JOSH_DIR` points the private pipeline at the local copy of the public engine. The city's operational data is always under city control.

### What the city owns and controls

| Item | Stored in | Controlled by |
|---|---|---|
| City configuration (boundary, FHSZ source, exit nodes) | City-private repo | City IT |
| Project records (applicant address, units, stories) | City-private repo | City IT / Planning |
| Road override corrections | City-private repo | City Engineer / IT |
| Generated determination maps | City-private repo | City IT |
| Downloaded data cache (OSM, FHSZ, Census) | Local disk, gitignored | City IT |
| Methodology engine and algorithm | Public repo | CSF (open source) |
| Legal parameters (ΔT thresholds, HCM table, NFPA rates) | Public repo `config/parameters.yaml` | CSF (open source, city can fork) |

The city's data never leaves city infrastructure. The methodology is public and auditable. The split is clean.

------

## What Running JOSH Looks Like

Day-to-day operation reduces to three commands, each of which a trained planner's assistant or GIS technician can run:

```bash
# Step 1 — Download and cache city data (run once, refresh every 90 days or on demand)
uv run python acquire.py --city "Encinitas"

# Step 2 — Build the routing graph and run capacity analysis
uv run python build.py analyze --city "Encinitas" --data-dir data/encinitas

# Step 3 — Generate the interactive determination map
uv run python build.py demo --city "Encinitas" \
  --data-dir data/encinitas \
  --projects projects/encinitas_demo.yaml
```

The output is a single HTML file in `output/encinitas/demo_map.html`. Open it in any browser. No server. No additional steps.

Adding a new project for review requires editing a plain-text YAML file:

```yaml
- name: "123 Ocean View Drive"
  address: "123 Ocean View Drive, Encinitas, CA"
  units: 42
  stories: 4
```

Then re-run Step 3. The new project appears on the map with its determination, audit trail, and route visualization. Total time from application intake to map update: under five minutes once the city's data is cached.

### Who runs it

JOSH does not require a dedicated GIS analyst or software engineer to operate. A planning technician or administrative analyst with basic command-line familiarity can run the standard workflow after a half-day orientation. The commands are the same every time. The only variable input is the project YAML file.

For initial setup — configuring the city YAML, identifying exit nodes for the routing algorithm, validating the FHSZ data source, and verifying the first analysis against a known project — a GIS analyst or city engineer should be involved. That setup work is a one-time effort per city.

------

## Data Sources and Security

JOSH downloads data from four public sources, all of which are free and require no API key:

| Source | What JOSH Downloads | Update Frequency |
|---|---|---|
| OpenStreetMap (via OSMnx) | Road network geometry and classification | On demand; 90-day cache TTL |
| Cal Fire OSFM ArcGIS REST API | Fire Hazard Severity Zone polygons | On demand; 90-day cache TTL |
| U.S. Census TIGER | City boundary polygon | On demand; 90-day cache TTL |
| U.S. Census Bureau Geocoder | Project coordinate validation | Per-geocode request; no cache |

JOSH does not connect to any California Stewardship Fund server. It does not send usage data, project data, applicant data, or any city information to any external party. The Census geocoder receives only a street address for coordinate validation — no name, parcel, or applicant data is transmitted.

No applicant personally identifiable information is stored in JOSH. The project YAML files contain address, unit count, and story count — the same information on the face of a building permit application. These files live in the city's private repository under city access controls.

The AGPL-3.0 license means that if the city modifies the JOSH source code and distributes the result, those modifications must also be made available under the same open license. For internal city use — running JOSH to produce determination maps for city staff — this license condition does not apply. The city can use and modify JOSH internally without any license obligation to CSF.

### Auditability

Every parameter in the JOSH methodology is in a plain-text YAML file (`config/parameters.yaml`) that city IT can inspect, print, and provide to any auditor. Every road capacity value, every degradation factor, every threshold comes from this file and traces to a published source citation documented alongside the value. There is no black box. There is no proprietary model. The city can hand the parameters file to the city attorney and say: here is every number the system uses, and here is where each one comes from.

------

## Output and Delivery

The primary output is `output/{city}/demo_map.html` — a single self-contained HTML file. It includes:

- An interactive Leaflet map with the city road network, FHSZ overlay, project markers, and evacuation route traces
- A project sidebar showing each project's ΔT result, determination tier, and route visualization
- An on-demand determination brief (generated in the browser, no server request)
- A downloadable plain-text audit trail for each project
- A what-if panel allowing planning staff to test modified unit counts or stories in real time

The file works from `file://` — a planner opens it by double-clicking. It also serves from any standard HTTP server (city intranet, SharePoint, a city-hosted GitHub Pages equivalent) without any server-side logic. It is a static file.

The city can distribute this file to city attorneys, the fire chief, council members, or applicants. It requires no JOSH installation to view.

------

## Keeping It Current

### Data refresh

Cached public data has a 90-day TTL. The city runs:

```bash
uv run python acquire.py --city "Encinitas" --refresh
```

This re-downloads road network, FHSZ, and boundary data and rebuilds the routing graph. The command takes 3–5 minutes. OSM road geometry changes slowly; for most cities, an annual refresh is sufficient unless road reclassifications or new infrastructure trigger an earlier update.

### Methodology updates

When California Stewardship Fund releases a methodology update — a parameter change, an algorithm improvement, or a legal standard revision — the update appears in the public repository as a new release. The city pulls the update using standard git:

```bash
git pull origin main
```

The city then re-runs the analysis for all active cities to regenerate determination maps under the updated methodology. The city controls when it adopts an update. It does not happen automatically. A city running a specific version of the methodology for an ongoing legal proceeding can hold that version in place by pinning to a git tag.

### Project records

Planner staff maintain the project YAML files — adding new projects as applications arrive, archiving completed ones. No database migration, no schema upgrade, no IT involvement required for routine project management. YAML files are plain text and version-controlled in git.

------

## What CSF Provides, What the City Provides

| Item | Provided by |
|---|---|
| Open source methodology engine | CSF (public repo, AGPL-3.0) |
| Legal parameters file (`config/parameters.yaml`) | CSF (public repo) |
| Methodology documentation (PE Brief, Legal Memo, this guide) | CSF |
| City configuration setup (initial) | City IT / GIS, with CSF documentation |
| Road override corrections | City Engineer, recorded by City IT |
| Project YAML maintenance | Planning Staff |
| Data refresh cadence | City IT |
| Output map hosting / distribution | City IT |
| Private city repository infrastructure | City IT |

CSF maintains the methodology. The city operates it. Neither depends on the other for day-to-day function.

------

## Working with California Stewardship Fund

A city with motivated IT staff and a GIS analyst can implement JOSH independently using this guide, the setup documentation in the public repository, and the methodology documents in the Document Library. The public repository includes a worked example for Berkeley that covers the full pipeline from initial data download through map generation. Most cities can replicate that process for their own jurisdiction in one to two focused working sessions.

For cities that want additional support, California Stewardship Fund can discuss a more structured engagement. That might include:

- Initial city configuration and validation of the first analysis against a known project or reference condition
- Review of the city's road override file to confirm classification corrections are complete and defensible
- Methodology validation for the city's specific FHSZ context, including LRA zone configuration where the standard Cal Fire API does not provide data
- Ongoing support for methodology updates — ensuring the city's implementation stays current with parameter revisions and legal standard changes
- Expert witness availability if a determination is challenged and the methodology needs to be explained in a legal proceeding

Where that level of engagement is appropriate, CSF and the city can evaluate whether a Memorandum of Understanding or a services agreement is the right instrument. An MOU typically covers the scope of CSF's support, the city's obligations for data maintenance, and the terms under which CSF can reference the city's adoption of the standard in public communications.

No engagement with CSF is required to use JOSH. The methodology is public, the code is open source, and the city's data stays under city control regardless of whether a formal relationship exists. The question is simply whether the city wants to move faster, with more confidence, and with direct access to the people who built and maintain the standard.

That is a conversation CSF is happy to have at whatever pace works for the city.

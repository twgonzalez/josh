# IT Implementation Guide

California Stewardship Fund — May 2026

**Prepared for city IT departments evaluating JOSH: what is open source, what a city implementation requires, and how to work with CSF to get it built**

------

## What This Guide Is For

JOSH has two distinct components, and understanding the distinction is the starting point for any IT evaluation.

The first component is the **JOSH methodology engine** — the open-source algorithm that computes ΔT, evaluates the objective standards, and runs in the browser as an interactive determination tool. This is publicly available under AGPL-3.0 at `github.com/twgonzalez/josh`. Any engineer can read it, audit it, and verify that it does what the methodology documents say it does.

The second component is the **city implementation** — the data acquisition, road network processing, FHSZ integration, and map generation that produces a determination map specific to a city's road network, hazard zones, and project inventory. This is specialist work. CSF maintains its own implementation and builds city maps under engagement. A city can also build its own implementation to the published specifications; this guide describes what that requires.

The methodology is open. The implementation is a service.

------

## What Is Open Source

The public JOSH repository (`github.com/twgonzalez/josh`) contains:

- The ΔT calculation algorithm and objective standards engine
- The interactive browser client — the determination map, what-if panel, audit trail generator, and brief renderer
- The legal methodology parameters (`config/parameters.yaml`) — every threshold, capacity factor, and rate, with citations to the published source for each
- The anti-divergence test suite, which verifies that the browser engine produces results identical to the reference Python implementation
- The Berkeley demonstration map, which shows the full output a city implementation produces

City IT can inspect every line of this code before any engagement with CSF. The methodology is not a black box. The parameters are not proprietary. Any qualified engineer can verify that the system does what the methodology documents say it does.

What the public repository does **not** contain is the data acquisition pipeline — the code that downloads and processes city-specific road network data, FHSZ polygons, Census boundaries, and traffic records, and assembles them into the `JOSH_DATA` bundle that the browser engine consumes. That pipeline is CSF's reference implementation. It is not open source.

------

## What a City Implementation Requires

Building a city-specific JOSH implementation involves five distinct technical workstreams. A city IT department evaluating whether to build in-house or engage CSF should understand what each requires.

### 1. Road network acquisition and classification

The JOSH engine requires a road network graph for the city's jurisdiction — every road segment with its highway classification, lane count, posted speed limit, and spatial geometry. The public source for this data is OpenStreetMap, accessed via the OSMnx Python library.

OSM data quality varies by jurisdiction. Private roads in covenant communities, recently reclassified arterials, and non-standard jurisdictions (fire protection districts, unincorporated county areas) frequently have incorrect highway tags that inflate or deflate HCM capacity estimates. A city implementation must include a validated road override process — a mechanism to correct OSM classifications against city GIS records and official functional classification maps, with documented reasons for each correction. Incorrect road classifications produce incorrect ΔT results, and those results will be challenged by applicants. The override record is part of the administrative record.

### 2. FHSZ data integration

Cal Fire's standard FHSZ API returns State Responsibility Area zones only. Cities with Local Responsibility Area designations — including most incorporated cities in Southern California — receive zero features from the standard API. A compliant city implementation must resolve LRA FHSZ data from an alternative source: a locally adopted FHSZ ordinance, a county GIS service, or a pre-downloaded and validated GeoJSON that has been confirmed against the city's officially adopted fire hazard zone designations.

Misidentifying a project site's FHSZ designation produces an incorrect threshold and potentially an incorrect determination tier. This is the data quality issue with the highest legal exposure in the implementation.

### 3. Routing graph and exit node configuration

The JOSH routing algorithm finds evacuation paths from a project site to the edge of the city's jurisdiction. For cities with standard Census TIGER boundaries, the boundary is well-defined and boundary-adjacent roads are easily identified as exit nodes. For non-municipal jurisdictions — fire protection districts, county service areas, special districts — the boundary polygon must be constructed from an authoritative non-Census source, and the primary evacuation exit nodes must be explicitly confirmed against the routing graph.

Incorrect exit node configuration causes the routing algorithm to identify the wrong evacuation paths, producing incorrect bottleneck identification and incorrect ΔT results.

### 4. JOSH_DATA assembly and map generation

The JOSH browser engine consumes a structured data bundle — `window.JOSH_DATA` — embedded in the determination map HTML. This bundle includes the road network graph, capacity parameters, FHSZ polygon data, and pre-evaluated project results. Generating this bundle requires running the full analysis pipeline against validated city data and serializing the results in the JOSH_DATA schema.

The schema version is tracked in the public repository. A city implementation must produce output conforming to the current schema version for the browser engine to load it correctly.

### 5. Ongoing maintenance

A city implementation is not a one-time build. It requires:

- **Data refresh**: Road network, FHSZ, and boundary data should be refreshed annually or whenever the city adopts a road reclassification, a boundary change, or an updated FHSZ designation. Each refresh requires re-running the full analysis and regenerating all determination maps.
- **Methodology updates**: When CSF releases an updated methodology version — revised parameters, corrected algorithms, or legal standard changes — the city must evaluate whether to adopt the update and, if so, re-run the analysis for all active projects.
- **Project record maintenance**: New projects must be added to the city's project inventory, geocoded to verified coordinates, and analyzed before a determination is issued.
- **Road override maintenance**: As the city corrects OSM road classifications, override records must be kept current and applied consistently.

------

## Validating a City Implementation

A city that builds its own implementation can verify correctness against the JOSH anti-divergence test suite, which is included in the public repository. The test suite generates known-result test vectors from the reference implementation and confirms that the browser engine produces identical results.

A city implementation that passes the anti-divergence tests and uses validated road and FHSZ input data produces results that are consistent with the published methodology. A city implementation that has not been validated against the test suite cannot claim that consistency.

CSF does not certify third-party implementations. A city that builds its own implementation is responsible for the correctness of its input data and the validity of its determinations.

------

## Working with CSF

California Stewardship Fund builds city JOSH implementations under engagement. This is the primary way cities get a determination map that is validated, legally defensible, and maintained.

A CSF-built implementation includes:

- Road network acquisition and classification validation against the city's official records
- FHSZ data resolution for the city's specific regulatory context, including LRA zone configuration
- Routing graph configuration and exit node validation
- Full analysis and JOSH_DATA bundle generation
- The interactive determination map as a deliverable, validated against the anti-divergence test suite
- Documentation of every road classification decision, data source, and override in a form suitable for inclusion in the administrative record

Where ongoing support is appropriate — annual data refreshes, methodology update adoption, expert witness availability for challenged determinations, or expansion to additional project types — CSF and the city can evaluate whether a Memorandum of Understanding or a services agreement is the right instrument.

Cities that want to evaluate CSF's implementation approach, review a sample administrative record package, or discuss what an engagement would involve are encouraged to reach out directly. The Berkeley demonstration map, accessible from this site, shows what a completed city implementation looks like.

------

## Summary: Build vs. Engage

| Question | Build In-House | Engage CSF |
|---|---|---|
| Methodology engine | Public, auditable, AGPL-3.0 | Same — all cities use the public engine |
| Road network validation | City GIS staff + engineer time | Included in engagement |
| FHSZ data resolution for LRA cities | Requires local regulatory research | Included in engagement |
| Routing configuration | Requires GIS and graph analysis expertise | Included in engagement |
| Administrative record documentation | City staff responsible | Included in engagement |
| Validation against test suite | City staff responsible | Included in engagement |
| Liability for determination correctness | City's implementation, city's responsibility | City's determination; CSF's validated data and documented methodology |
| Ongoing refresh and updates | City IT and GIS staff | Available under MOU |

The methodology is public. The standard is open. What CSF provides is the specialist implementation work that makes a city's use of that standard defensible in a legal proceeding — and the ongoing relationship that keeps it current.

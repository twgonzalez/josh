# Fire Evacuation Capacity Analysis System - Streamlined Specification

## Project Purpose
Create an AI agent system that analyzes fire evacuation route capacity for California cities to:
1. Establish **objective development standards** (ministerial vs. discretionary review)
2. Generate **impact fee nexus studies** (AB 1600 compliant)
3. Enable **what-if analysis** for proposed developments

This is a legally-focused minimum viable system. Additional analysis layers can be added later if needed for litigation or political purposes.

## Legal Requirements

### Objective Standards (California Housing Law)
Standards must be:
- Quantifiable without subjective judgment
- Verifiable by reference to external criteria
- Applied uniformly without discretion
- Documented with clear audit trail

### Impact Fee Nexus Study (AB 1600)
Must demonstrate:
- Reasonable relationship between fee and development type
- How fees will be used for improvements
- Proportionality between development impact and fee amount
- Cost estimates for necessary improvements

### What-If Analysis
Must enable:
- Instant determination for individual projects (ministerial vs. discretionary)
- Cumulative impact analysis for multiple developments
- Before/after comparison visualization
- Defensible calculations with audit trail

## System Architecture

### Agent 1: Data Acquisition Agent
**Purpose:** Fetch minimum required public datasets

**Required Data Sources:**

1. **Fire Hazard Severity Zones**
   - Source: CAL FIRE (https://osfm.fire.ca.gov/)
   - Format: Shapefile/GeoJSON
   - Content: Zone 1, 2, 3 classifications
   - Usage: Determine which areas trigger standards

2. **Road Network**
   - Source: OpenStreetMap via OSMnx library
   - Required attributes: 
     - Geometry (LineString)
     - Street name
     - Lane count (or estimate from road class)
     - Road classification (local, arterial, highway)
     - Speed limit
   - Usage: Identify evacuation routes, calculate capacity

3. **Traffic Volumes**
   - Source: State DOT (Caltrans AADT data) or local counts
   - Fallback: Estimate from road classification if unavailable
   - Format: CSV or API
   - Content: Average Annual Daily Traffic (AADT) by road segment
   - Usage: Calculate baseline demand

4. **City Boundary**
   - Source: U.S. Census TIGER/Line or local GIS
   - Format: Shapefile/GeoJSON
   - Usage: Define study area, identify exits

5. **Census Data (Optional - for fee nexus only)**
   - Source: U.S. Census API
   - Content: Population by block group
   - Usage: Estimate total evacuating population for fee calculations

**Implementation Requirements:**
- Cache all downloaded data locally with date stamps
- Document data vintage (date acquired/published)
- Handle missing data with clear logging and conservative defaults
- Store in standardized formats (GeoJSON, GeoPackage, CSV)

**Deliverable:** Validated dataset package for city with metadata file documenting sources and dates

### Agent 2: Capacity Analysis Agent
**Purpose:** Calculate objective, verifiable evacuation route capacity metrics

**Core Calculations:**

**1. Route Capacity (HCM 2022 Standards)**
```
Inputs:
- Lane count (from road network data)
- Road type (freeway, multilane, two-lane)
- Free flow speed (from speed limits)

Calculation:
- Freeway: 2,250 pc/h per lane (conservative)
- Multilane: 1,900 pc/h per lane
- Two-lane: Based on speed:
  * 20 mph or less: 900 pc/h
  * 25 mph: 1,125 pc/h
  * 30 mph: 1,350 pc/h
  * 35 mph: 1,575 pc/h
  * 40+ mph: 1,700 pc/h

Output: Total capacity in passenger cars per hour (pc/h)
```

**2. Baseline Demand**
```
Inputs:
- Traffic counts (AADT from DOT)
- Time-of-day factor (default 0.10 for peak hour if no hourly data)

Calculation:
- If hourly data available: use peak hour count
- If only AADT: peak_hour_demand = AADT × 0.10

Output: Vehicles per hour during evacuation
```

**3. Volume-to-Capacity (v/c) Ratio**
```
Calculation:
v/c ratio = baseline_demand / capacity

Output: Decimal value (e.g., 0.73)

LOS Assignment:
- v/c 0.0-0.1 = LOS A
- v/c 0.1-0.2 = LOS B
- v/c 0.2-0.4 = LOS C
- v/c 0.4-0.6 = LOS D
- v/c 0.6-0.95 = LOS E
- v/c 0.95+ = LOS F
```

**4. Evacuation Route Identification**
```
Method: Network analysis from fire zones to city exits

Process:
1. Identify all census blocks in FHSZ Zone 2 or 3
2. Find geometric centroid of each block
3. Calculate shortest path from centroid to city boundary
4. Mark all roads used in any shortest path as "evacuation routes"
5. Count frequency each road segment is used (connectivity score)

Output: 
- List of evacuation route segments
- Connectivity count per segment
```

**Implementation Requirements:**
- Use Highway Capacity Manual 2022 formulas (cite specific tables)
- Document all assumptions (default values, estimation methods)
- Store intermediate calculations for audit trail
- Flag routes where data quality is low (estimated vs. measured)

**Deliverable:** 
- Table of evacuation routes with: name, capacity, baseline demand, v/c ratio, LOS
- Map showing routes color-coded by LOS

### Agent 3: Objective Standards Engine
**Purpose:** Provide zero-discretion determination of ministerial vs. discretionary review

**Objective Standard Definition:**

**Standard 1: Fire Zone Determination**
```
Question: Is project in FHSZ Zone 2 or Zone 3?
Method: GIS point-in-polygon test
Data: CAL FIRE FHSZ map dated [specific date]
Output: Boolean (true/false)
Discretion: Zero
```

**Standard 2: Project Size Threshold**
```
Question: Does project include 50 or more dwelling units?
Method: Count units on site plan
Output: Boolean (≥50 = true, <50 = false)
Discretion: Zero
```

**Standard 3: Route Identification**
```
Question: Which evacuation routes serve this project?
Method: Network analysis - shortest path from project location to city exits
Distance: Routes within 0.5 miles via drivable path
Output: List of route segment IDs
Discretion: Zero (algorithmic)
```

**Standard 4: Capacity Threshold Test**
```
Question: Do any serving routes exceed v/c threshold?

Baseline Test:
- For each route from Standard 3
- Check if baseline v/c ≥ 0.80
- If yes, route flagged

Project Impact Test:
- Calculate project vehicles = units × 2.5 × 0.57
  * 2.5 = avg vehicles per household (Census data)
  * 0.57 = peak hour mobilization factor (Berkeley study)
- Distribute vehicles equally across serving routes
- For each route: proposed_vc = (baseline_demand + added_vehicles) / capacity
- Check if proposed_vc > 0.80
- If yes, route flagged

Output: Boolean - true if ANY route flagged in either test
Discretion: Zero (mathematical calculation)
```

**Final Determination:**
```
IF Standard 1 = true (in fire zone)
AND Standard 2 = true (≥50 units)
AND Standard 4 = true (route exceeds threshold)
THEN: DISCRETIONARY REVIEW REQUIRED

OTHERWISE: MINISTERIAL APPROVAL ELIGIBLE
```

**Implementation Requirements:**
- Every calculation must be reproducible with audit trail
- Document all parameters (thresholds, factors, formulas)
- Store both inputs and outputs for verification
- Generate compliance certificate with calculations shown
- Include data source citations with dates

**Deliverable:**
- Project evaluation report showing:
  - Each standard test with pass/fail
  - All calculations with intermediate steps
  - Final determination with legal justification
  - Data sources and dates used
  - Route-by-route impact table

### Agent 4: Impact Fee Nexus Calculator
**Purpose:** Calculate legally defensible proportionate impact fees (AB 1600 compliant)

**Nexus Study Components:**

**1. Identify Required Improvements**
```
Process:
- For each route exceeding v/c threshold under cumulative development
- Determine improvement needed to restore to v/c < 0.80
- Options:
  * Add travel lane
  * Widen roadway
  * Intersection improvements
  * Signalization upgrades

Cost Estimation:
- New lane addition: $5M - $8M per lane-mile (typical range)
- Roadway widening: $3M - $5M per mile
- Intersection upgrade: $1M - $3M per intersection
- Use local unit costs if available, otherwise regional averages

Output: List of improvements with costs
```

**2. Calculate Proportionate Share**
```
Total Improvement Cost = sum of all needed improvements

Proportionality Calculation:
- Baseline demand = current traffic on route
- New demand from development = project vehicles
- Total future demand = baseline + new demand
- Development share = new demand / total future demand

Example:
- Current traffic: 5,000 vehicles/day
- Project adds: 1,250 vehicles/day
- Total: 6,250 vehicles/day
- Project share: 1,250 / 6,250 = 20%

Fee Calculation:
Impact fee = Total improvement cost × Development share

Per-Unit Fee:
Fee per dwelling unit = Total impact fee / Number of units
```

**3. Reasonable Relationship Test**
```
Demonstrate:
1. Development creates need for improvement
   - Show v/c calculation before/after
   - Prove improvement necessary to maintain LOS

2. Fee will fund improvement that benefits development
   - List specific improvements
   - Explain how they serve new residents

3. Amount is proportional
   - Show math for proportionate share
   - Explain why this allocation is fair

4. Separate accounting
   - Confirm fees deposited in designated account
   - Annual reporting requirement
```

**Implementation Requirements:**
- Use documented, regional cost estimates
- Provide range (low/medium/high) not single number
- Show sensitivity analysis (fee if costs 20% higher/lower)
- Include inflation adjustment methodology
- Document timing of improvements vs. fee collection
- Cite comparable fee studies from other jurisdictions

**Deliverable:**
- Nexus study report (15-20 pages) including:
  - Purpose and authority
  - Improvements identified with costs
  - Proportionality calculations
  - Fee schedule by development size/location
  - Reasonable relationship findings
  - Accounting and reporting procedures
  - Appendix with cost documentation

### Agent 5: What-If Analysis Engine
**Purpose:** Enable rapid scenario testing for planning decisions

**Interactive Analysis Capabilities:**

**1. Single Project Analysis**
```
User Inputs:
- Project location (lat/lon or address)
- Number of dwelling units
- Unit type (single-family, multifamily - affects vehicle generation)

Process:
1. Identify fire zone (Standard 1)
2. Check size threshold (Standard 2)
3. Identify serving evacuation routes (Standard 3)
4. Calculate project vehicle generation
5. Distribute vehicles across routes
6. Calculate new v/c for each route
7. Apply threshold test (Standard 4)
8. Determine ministerial vs. discretionary
9. Calculate impact fee (if applicable)

Outputs:
- Clear determination: MINISTERIAL or DISCRETIONARY
- Route-by-route before/after table
- Visual map showing affected routes
- Impact fee estimate
- Compliance certificate (if ministerial)
- Required findings (if discretionary)
```

**2. Cumulative Impact Analysis**
```
User Inputs:
- List of multiple projects (location, units for each)

Process:
1. Calculate individual impact for each project
2. Sum vehicles across all projects by route
3. Calculate cumulative v/c ratios
4. Identify which routes fail under cumulative scenario
5. Compare to individual project analysis

Outputs:
- System-wide v/c changes
- Routes that fail only under cumulative scenario
- Total impact fees across all projects
- Infrastructure investment needs
- Map showing cumulative stress
```

**3. Threshold Sensitivity Testing**
```
User Inputs:
- Alternative v/c thresholds (e.g., 0.70, 0.80, 0.90)
- Alternative vehicle generation rates
- Alternative mobilization factors

Process:
Run analysis with different parameters to show:
- How many projects trigger discretionary at each threshold
- Fee revenue implications
- Infrastructure needs under different assumptions

Outputs:
- Comparison table showing effects of parameter changes
- Policy implications summary
```

**4. What-If Reversal (Capacity Planning)**
```
User Question: "How many units can we add before hitting threshold?"

Process:
- For each evacuation route
- Calculate remaining capacity: threshold_demand - baseline_demand
- Convert to units: remaining_units = remaining_capacity / (2.5 × 0.57)
- Map results

Outputs:
- "Capacity budget" map showing developable units by area
- Table of routes with remaining unit capacity
- Recommended development caps by fire zone
```

**Implementation Requirements:**
- Web-based interface (simple form inputs)
- Real-time calculation (results in <5 seconds)
- Downloadable reports (PDF)
- Save/load scenarios for comparison
- Export data tables (CSV, Excel)
- Print-friendly formatted output
- Mobile-responsive design

**Deliverable:**
- Interactive web application with:
  - Project entry form
  - Real-time map updates
  - Before/after comparison views
  - Downloadable determination letters
  - Scenario library (save for later)
  - Batch upload capability (CSV of projects)

### Agent 6: Visualization Agent
**Purpose:** Create legally sufficient maps and charts (minimal set)

**Required Visualizations:**

**Map 1: Fire Hazard Zones and Evacuation Routes**
```
Layers:
- City boundary (outline)
- FHSZ zones (colored polygons):
  * Zone 3: Dark red
  * Zone 2: Orange
  * Zone 1: Yellow
  * Non-FHSZ: Light green
- Evacuation routes (bold lines)
- City exits (marked with arrows)

Purpose: Show which areas trigger objective standards

Features:
- Toggle layers on/off
- Click zone for details
- Print to PDF at 300 DPI
```

**Map 2: Baseline Evacuation Route Capacity (LOS)**
```
Layers:
- Road network (thin gray lines)
- Evacuation routes colored by LOS:
  * LOS A-C: Green (v/c < 0.4)
  * LOS D: Yellow (v/c 0.4-0.6)
  * LOS E: Orange (v/c 0.6-0.95)
  * LOS F: Red (v/c ≥ 0.95)
- Line thickness = connectivity (thicker = more critical)

Purpose: Show baseline capacity constraints

Features:
- Click route for v/c details
- Legend with LOS definitions
- Filter by LOS category
```

**Map 3: What-If Impact Analysis**
```
Two views (side-by-side or toggle):

View A: Baseline (current conditions)
View B: With proposed development(s)

Routes color-coded by LOS (same as Map 2)

Visual indicators:
- Routes that change LOS: highlighted with border
- Project location(s): marked with pin/star
- Routes analyzed: thicker lines
- Routes unaffected: dimmed

Purpose: Show before/after for decision-makers

Features:
- Animation/fade between baseline and proposed
- Click project pin to see details
- Click route to see calculation
- Export comparison image
```

**Chart 1: Route-by-Route Comparison Table**
```
Columns:
- Route Name
- Baseline Demand (vph)
- Baseline Capacity (vph)
- Baseline v/c
- Baseline LOS
- Proposed Demand (vph)
- Proposed v/c
- Proposed LOS
- Change in v/c
- Exceeds Threshold? (Y/N)
- Status (Ministerial/Discretionary)

Features:
- Sortable columns
- Filter by status
- Highlight rows where LOS changes
- Export to CSV/Excel
```

**Chart 2: Impact Fee Summary**
```
For nexus study:

Bar chart showing:
- X-axis: Route names needing improvement
- Y-axis: Improvement cost
- Bars color-coded by improvement type (new lane, widening, etc.)
- Total cost shown at top
- Development proportionate share highlighted

Table below chart:
- Route, Improvement Description, Cost, Development Share, Fee Allocation
```

**Implementation Requirements:**
- Use Folium or Plotly for interactive web maps
- Use Matplotlib for static charts (PDF embedding)
- Consistent color schemes across all visualizations
- Include legends, scale bars, north arrows on maps
- Metadata footer (data sources, dates, disclaimers)
- Mobile-responsive for web viewing
- High-resolution export (300 DPI) for printing

**Deliverable:**
- 3 interactive web maps
- 2 data tables/charts
- All exportable to PDF/PNG
- Embeddable in reports

### Agent 7: Report Generation Agent
**Purpose:** Compile legally sufficient documentation

**Report Type 1: Objective Standards Ordinance**
```
Sections:
1. Authority and Purpose
   - AB 747 citation
   - General Plan Safety Element integration
   - Statutory compliance statement

2. Definitions
   - Fire Hazard Severity Zone
   - Evacuation route
   - Volume-to-capacity ratio
   - Level of Service
   - Ministerial vs. discretionary

3. Applicability
   - Geographic scope (FHSZ 2 and 3)
   - Project size threshold (50+ units)
   - Exemptions (if any)

4. Objective Standards (Standards 1-4 from Agent 3)
   - Each standard stated precisely
   - Calculation methods specified
   - Thresholds defined
   - Data sources cited with dates

5. Review Process
   - Submittal requirements
   - Timeline for determination (e.g., 30 days)
   - Appeal process
   - Verification procedure

6. Incorporation by Reference
   - FHSZ map dated [X]
   - Traffic data dated [X]
   - HCM 2022 capacity formulas
   - Road network data dated [X]

7. Severability and Effective Date

Format: Model ordinance ready for City Council adoption
Length: 8-12 pages
```

**Report Type 2: Impact Fee Nexus Study**
```
Sections:
1. Executive Summary
   - Fee purpose
   - Legal authority (AB 1600)
   - Recommended fee amount
   - Revenue projection

2. Legal Requirements
   - Reasonable relationship test
   - Proportionality requirement
   - Separate accounting
   - Five-year findings

3. Development Impact Analysis
   - Fire evacuation demand model
   - Routes affected by growth
   - Capacity deficiencies identified
   - Without-fee consequences

4. Required Improvements
   - Route-by-route needs
   - Improvement descriptions
   - Cost estimates (with documentation)
   - Phasing and timing

5. Fee Calculation
   - Total improvement costs
   - Growth projections
   - Proportionality analysis
   - Fee formula
   - Sensitivity analysis

6. Reasonable Relationship Findings
   - Purpose finding
   - Use finding
   - Reasonable relationship finding
   - Proportionality finding

7. Fee Administration
   - Collection procedures
   - Account management
   - Annual reporting
   - Refund provisions

8. Appendices
   - Cost documentation
   - Traffic study results
   - Map of improvement locations
   - Comparable fee analysis

Format: Professional nexus study
Length: 15-25 pages plus appendices
```

**Report Type 3: Project Determination Letter**
```
For each project analyzed:

Header:
- Project name and address
- APN
- Applicant
- Date of determination

Findings:
1. Fire Zone Status
   - Zone designation
   - Map reference
   - Finding: In/Not in FHSZ 2/3

2. Size Threshold
   - Number of units
   - Finding: Meets/Does not meet threshold

3. Evacuation Route Analysis
   - Routes identified (list)
   - Baseline v/c for each
   - Project impact calculation
   - Proposed v/c for each
   - Threshold test results

4. Determination
   - MINISTERIAL or DISCRETIONARY
   - Legal basis cited
   - Effective date

5. Impact Fee (if applicable)
   - Fee amount
   - Calculation shown
   - Payment timing

6. Conditions (if ministerial)
   - Standard conditions
   - Fire access requirements
   - Emergency evacuation plans

7. Appeal Rights
   - Process
   - Timeline
   - Contact information

Attachments:
- Route map with project location
- Calculation worksheet
- Data sources list

Format: Official city letterhead
Length: 3-5 pages
```

**Report Type 4: What-If Analysis Report**
```
For scenario testing:

Sections:
1. Scenario Description
   - Project(s) tested
   - Assumptions used
   - Analysis date

2. Baseline Conditions
   - Current v/c by route
   - Existing LOS
   - Map

3. Proposed Conditions
   - Project impacts
   - Updated v/c by route
   - New LOS
   - Map showing changes

4. Comparison Analysis
   - Routes affected
   - Magnitude of change
   - Threshold exceedances
   - Cumulative effects

5. Determinations
   - Which projects ministerial
   - Which require discretionary
   - Fee implications

6. Infrastructure Needs
   - Routes requiring improvement
   - Estimated costs
   - Funding sources

7. Recommendations
   - Policy implications
   - Timing considerations
   - Further analysis needed

Format: Staff report or technical memorandum
Length: 10-15 pages
```

**Implementation Requirements:**
- Use professional templates
- Consistent formatting and style
- Automatic page numbering, headers, footers
- Table of contents generation
- Embedded maps and charts (high resolution)
- Hyperlinked cross-references
- PDF/A format for archival
- Editable Word format for city review

**Deliverable:**
For each city:
- Draft objective standards ordinance (ready to adopt)
- Complete nexus study (AB 1600 compliant)
- Template determination letter
- Example what-if analysis report

## Data Requirements and Assumptions

### Required Parameters (City-Specific Configuration)

**Traffic Data:**
- If available: Actual traffic counts by road segment
- If unavailable: Estimation model based on:
  * Road functional class
  * Lane count
  * Speed limit
  * Land use context
  * Default factors from comparable cities

**Thresholds:**
- V/C threshold: 0.80 (default, adjustable by city)
  * Justification: LOS E/F boundary per HCM
  * Can be lowered to 0.70 for more conservative
  * Can be raised to 0.90 for less restrictive
- Unit threshold: 50 dwelling units (default, adjustable)
  * Justification: CEQA categorical exemption threshold
  * Cities can lower if desired

**Vehicle Generation:**
- Vehicles per dwelling unit: 2.5 (default)
  * Source: U.S. Census ACS
  * Override with city-specific rate if available
- Peak hour factor: 0.57 (default)
  * Source: Berkeley mobilization study
  * Conservative (highest hourly demand)

**Capacity Factors:**
- Use Highway Capacity Manual 2022 tables
- Conservative (lower-end) estimates
- Document any adjustments for local conditions

### Data Quality Standards

**Minimum Acceptable:**
- Fire zones: Official CAL FIRE FHSZ map
- Roads: OSM with lane count estimates if needed
- Traffic: State DOT counts or modeled estimates
- Boundary: Official city boundary

**Preferred:**
- Fire zones: CAL FIRE FHSZ (same)
- Roads: City GIS centerlines with surveyed lane counts
- Traffic: Recent (within 2 years) actual counts
- Speed data: Observed speeds, not just posted limits

**Documentation Requirements:**
- Date of each dataset
- Source/provider
- Method of collection
- Known limitations
- Assumptions made to fill gaps

## Deliverables Summary

**For Each City Analyzed:**

**1. Data Package**
- FHSZ zones (GeoJSON)
- Road network with attributes (GeoPackage)
- Traffic counts/estimates (CSV)
- City boundary (GeoJSON)
- Metadata file (YAML or JSON) documenting all sources and dates

**2. Analysis Outputs**
- Evacuation routes table (CSV/Excel)
- V/C calculations for all routes (CSV/Excel)
- Baseline capacity assessment (PDF report)
- 3 maps (interactive HTML + static PDF)

**3. Legal Documents**
- Draft objective standards ordinance (Word + PDF)
- Impact fee nexus study (Word + PDF)
- Fee schedule table (Excel)
- Template determination letter (Word)

**4. Web Application**
- What-if analysis tool (hosted web app or localhost)
- User interface for project entry
- Real-time map visualization
- Downloadable determination letters
- Saved scenarios library

**5. Technical Documentation**
- Methodology document explaining all calculations
- User guide for what-if tool
- Data dictionary for all outputs
- Audit trail procedures

## System Architecture Overview

**Technology Stack:**
```
Core Processing:
- Python 3.9+
- GeoPandas (spatial operations)
- NetworkX/OSMnx (network analysis)
- Pandas (data manipulation)

Web Interface:
- Flask or FastAPI (backend)
- Folium or Plotly (interactive maps)
- HTML/CSS/JavaScript (frontend)

Report Generation:
- python-docx (Word documents)
- ReportLab or WeasyPrint (PDFs)
- Jinja2 (templates)

Data Storage:
- GeoPackage or PostGIS (spatial data)
- SQLite or PostgreSQL (tabular data)
- JSON/YAML (configuration)
```

**Project Structure:**
```
fire-evacuation-analysis/
├── agents/
│   ├── data_acquisition.py
│   ├── capacity_analysis.py
│   ├── objective_standards.py
│   ├── nexus_calculator.py
│   ├── what_if_engine.py
│   ├── visualization.py
│   └── report_generator.py
├── models/
│   ├── road_network.py
│   ├── project.py
│   └── scenario.py
├── config/
│   ├── parameters.yaml
│   ├── thresholds.yaml
│   └── cities/
├── templates/
│   ├── ordinance_template.docx
│   ├── nexus_template.docx
│   └── determination_letter.docx
├── web/
│   ├── app.py
│   ├── templates/
│   └── static/
├── data/
│   └── [city_name]/
├── output/
│   └── [city_name]/
└── main.py
```

**Command-Line Interface:**
```
# Analyze a city
python main.py analyze --city "Berkeley" --state "CA"

# Run what-if analysis
python main.py whatif --city "Berkeley" --project project.json

# Generate reports only
python main.py report --city "Berkeley"

# Launch web interface
python main.py serve --city "Berkeley" --port 8000
```

## Success Criteria

**Legal Defensibility:**
- ✓ All standards verifiable without discretion
- ✓ Calculations reproducible with audit trail
- ✓ Data sources properly cited with dates
- ✓ Nexus study meets AB 1600 requirements
- ✓ Attorney review confirms objective nature

**Usability:**
- ✓ City staff can run analysis without technical expertise
- ✓ What-if tool provides answers in <10 seconds
- ✓ Reports are ready for City Council adoption
- ✓ Determination letters are legally sufficient

**Accuracy:**
- ✓ V/C calculations match HCM standards
- ✓ Network analysis correctly identifies routes
- ✓ Impact fees are proportional and defensible
- ✓ Maps are spatially accurate

**Scalability:**
- ✓ Can analyze any California city with public data
- ✓ Analysis completes in <1 day per city
- ✓ System handles cities from 10K to 1M population
- ✓ Multiple scenarios can be tested rapidly

## Validation Approach

**Test Against Berkeley Study:**
1. Run streamlined system on Berkeley
2. Compare v/c ratios to published study
3. Verify route identification matches
4. Confirm capacity calculations within 10%
5. Document any differences and justification

**Legal Review:**
1. Have attorney review objective standards
2. Confirm no discretionary elements
3. Verify nexus study meets AB 1600
4. Test determination process for consistency
5. Document attorney sign-off

**User Testing:**
1. Have city planning staff use what-if tool
2. Verify they can generate determinations
3. Confirm outputs are clear and usable
4. Collect feedback for refinements
5. Create tutorial videos if needed

## Notes for Implementation

**Critical Legal Points:**
- Every threshold, formula, and factor must be explicitly stated
- No "engineering judgment" or "professional discretion" language
- All data sources must be publicly available
- Calculations must be simple enough for non-technical verification
- Audit trail must be complete (all inputs, intermediates, outputs)

**Simplifications from Berkeley Study:**
- No comprehensive hazard analysis (earthquake, flood, etc.)
- No demographic vulnerability scoring
- No detailed safety factors (curvature, slope, pavement)
- No service infrastructure analysis
- Fewer maps (3 vs. 26)
- Shorter reports (25 pages vs. 100 pages)

**When to Add Complexity:**
- If challenged in court → add safety factors for specific routes
- If building political case → add comprehensive hazard analysis
- If regional strategy → add multi-city comparison data
- If state legislation → add statewide pattern analysis

**Extension Points (Future Phases):**
- Real-time traffic data integration
- Climate change scenario modeling
- Multi-hazard analysis (fire + earthquake + flood)
- Regional evacuation coordination
- Cost-benefit analysis for improvements
- Equity analysis (EJ communities)

The system is designed for rapid deployment and legal defensibility first, with the ability to add analytical depth later if needed for litigation or policy advocacy.
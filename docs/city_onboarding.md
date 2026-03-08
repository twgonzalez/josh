# JOSH City Onboarding Guide

**Jurisdictional Objective Standards for Housing (JOSH)**
California Stewardship Alliance — AB 747 / Gov. Code §65302.15

---

## Overview

Adding a new city to JOSH requires two things: a city configuration file
(`config/cities/{city}.yaml`) and decisions about how to source each input
parameter. This document describes every parameter, the options available,
and the legal defensibility of each option.

The hierarchy of legal defensibility, from strongest to weakest:

```
1. Local empirical study (city-commissioned, peer-reviewed)
2. Comparable city transfer (documented geographic/demographic comparability)
3. State guidance range (OPR / CAL OES published default)
4. Conservative default (with mandatory disclosure in every determination)
```

JOSH automatically includes the appropriate disclosure language in the audit
trail and determination brief based on the `mobilization_source` field in the
city config. A city that uses a conservative default will see a yellow warning
callout in every brief until a local study is adopted.

---

## Step 1 — Create the City Config File

Copy the template and fill in the required fields:

```bash
cp config/cities/berkeley.yaml config/cities/{city_slug}.yaml
```

Required fields:

```yaml
city_name: "Encinitas"
state: "CA"
state_fips: "06"
county_fips: "073"          # San Diego County
place_fips: "22230"         # Encinitas city FIPS
osmnx_place: "Encinitas, California, USA"
tiger_url: "https://www2.census.gov/geo/tiger/TIGER2023/PLACE/tl_2023_06_place.zip"
crs: "EPSG:4326"
analysis_crs: "EPSG:26911"  # UTM Zone 11N for Southern California
```

Then run the analyzer to download and cache all source data:

```bash
uv run python main.py analyze --city "Encinitas" --state "CA"
```

---

## Step 2 — Key Parameters and How to Source Them

### 2a. Peak-Hour Mobilization Factor

**What it is:** The fraction of all households in an evacuation zone that
depart in the single worst hour. Directly determines the peak vehicle load
on each evacuation route.

**Formula:** `project_vph = dwelling_units × vehicles_per_unit × mob_factor`

Set in city config:

```yaml
peak_hour_mobilization: 0.57       # the actual factor
mobilization_source: "local_study" # one of four options below
mobilization_citation: "..."       # full citation for audit trail
mobilization_note: "..."           # plain-English explanation for brief
```

#### Option A — Local Empirical Study *(strongest)*

The city commissions a traffic engineering firm to derive the factor from
observed data. This is what Berkeley did.

**How Berkeley did it:**
- KLD Engineering pulled Caltrans PeMS loop detector data from the primary
  hill corridor sensors during the 2017–2018 Northern California fire evacuations
- Combined with post-event survey data from the 1991 Oakland–Berkeley Hills Fire
  (NFPA 502 study, UC Berkeley IURD 1993), which recorded departure timing
  by hour for ~3,500 households
- Computed: `peak_hour_veh / (total_evac_zone_HUs × avg_vehicles_per_HH)` = **0.57**
- Documented in: KLD Engineering TR-1381 (March 2024), Figure 12

**Config:**
```yaml
mobilization_source: "local_study"
peak_hour_mobilization: 0.57
mobilization_citation: >
  KLD Engineering TR-1381, Berkeley AB 747 Fire Evacuation Capacity Study
  (March 2024), Figure 12. Derived from Caltrans PeMS counts on primary hill
  corridors during 2017-2018 Northern California fire evacuations, calibrated
  against 1991 Oakland-Berkeley Hills Fire post-event survey data.
mobilization_note: >
  Factor derived from observed traffic counts during actual wildfire evacuations.
  Empirical basis is the strongest standard for AB 747 legal defensibility.
```

#### Option B — Comparable City Transfer *(strong, with documentation)*

When a city has not had a major evacuation event, transfer the factor from a
comparable city whose study has been peer-reviewed, documenting the geographic
and demographic comparability.

**Encinitas example:**
The 2014 Cocos Fire (Carlsbad/San Marcos, immediately north of Encinitas)
forced evacuations across coastal North San Diego County — the same road
network type, same community density, same coastal Southern California
context. SANDAG and Cal Fire have studied that event. A transfer study would:

1. Obtain Caltrans PeMS District 11 data for SR-78, El Camino Real, and I-5
   corridor sensors for May 14–15, 2014
2. Compute the peak-hour departure fraction using Census denominators for
   the evacuated zone (Carlsbad/San Marcos block groups)
3. Document geographic comparability (coastal North SD County, similar
   median income, similar vehicle ownership rates, similar road connectivity)
4. Apply to Encinitas with a ±10% sensitivity analysis

Estimated result: **0.52–0.61** (similar to Berkeley given comparable
coastal California road network characteristics and community type)

**Config:**
```yaml
mobilization_source: "comparable_city"
peak_hour_mobilization: 0.57   # or the derived value from the Cocos analysis
mobilization_citation: >
  Transferred from Cocos Fire (2014) Carlsbad/San Marcos evacuation analysis.
  Caltrans PeMS District 11 detector data, May 14-15 2014. Comparable city
  documented: coastal North San Diego County, similar density and vehicle
  ownership (ACS 2022). See Appendix A of [study name].
mobilization_note: >
  Factor transferred from a comparable coastal San Diego County community
  evacuation event. Geographic and demographic comparability documented.
  A local empirical study using Encinitas-specific data is recommended
  before impact fee adoption.
```

#### Option C — State Guidance Range *(acceptable, requires conservative pick)*

OPR AB 747 implementing guidance publishes a default range for California
WUI communities. Citing the state's own guidance document satisfies the
"best available information" standard in Government Code §65302.15.

- Published range: **0.40–0.75** for California WUI communities
- Recommended conservative pick for fee purposes: **0.65–0.70**
- Cite: OPR AB 747 Guidance (year), Table X-X

**Config:**
```yaml
mobilization_source: "state_guidance"
peak_hour_mobilization: 0.68   # conservative end of OPR guidance range
mobilization_citation: >
  OPR AB 747 Implementation Guidance (2024), Table 3-2.
  California WUI community range: 0.40-0.75. Conservative value selected
  (0.68) for fee nexus purposes per OPR recommendation for cities without
  local empirical data.
mobilization_note: >
  Factor derived from OPR AB 747 state guidance range for California WUI
  communities. Conservative value selected. A local empirical study is
  recommended before impact fee adoption.
```

#### Option D — Conservative Default *(use with mandatory disclosure)*

When no study is available and no comparable city transfer is feasible,
use a conservative value (higher = more protective of public safety) and
disclose it explicitly in every determination.

**Config:**
```yaml
mobilization_source: "conservative_default"
peak_hour_mobilization: 0.70
mobilization_citation: "Conservative California WUI default (no local study on file)"
mobilization_note: >
  No city-specific mobilization study is available. A conservative default
  of 0.70 has been applied intentionally. This value errs toward protecting
  public safety. Commission a local AB 747 PeMS study before adopting
  impact fees. See docs/city_onboarding.md for study options.
```

JOSH will display a **yellow warning callout** in every determination brief
when `mobilization_source: conservative_default` is set.

---

### 2b. Vehicles Per Dwelling Unit

**What it is:** Average number of vehicles per household in the evacuation zone.

**Default:** 2.5 (U.S. Census ACS national average)

**Better approach (available from data already downloaded):**
JOSH downloads Census ACS block group data for every city. Table B08201
(vehicles available by household) allows computing a city-specific ratio:

```
vehicles_per_unit = sum(B08201 vehicles available) / sum(B25001 housing units)
```

This is a one-time calculation per city — not a study, just a Census query.
Results vary significantly: dense urban cities (SF: ~1.1) vs. suburban
(Fresno: ~2.7). Set the result in city config:

```yaml
vehicles_per_unit: 1.8   # city-specific from ACS calculation
```

*Note: Implementing this as an automatic calculation in Agent 1 is a
planned enhancement (Phase 3). Until then, calculate manually from Census
API and override here.*

---

### 2c. Employment and Student Demand

These affect the buffer-based background demand calculation (informational),
not the Standard 4 marginal causation test. Less legally critical but
important for citywide planning outputs.

**Employment rate** — fraction of working-age population that is employed:
```yaml
employment_rate: 0.62   # from ACS B23025 (Employment Status)
```

**Commute-in fraction** — fraction of jobs filled by workers from outside:
```yaml
commute_in_fraction: 0.45   # from Census LEHD OnTheMap
```

**Universities** — if the city has a major campus:
```yaml
universities:
  - name: "Cal State San Marcos"
    enrollment: 15000
    student_vehicle_rate: 0.35   # higher than Berkeley (less transit access)
    location_lat: 33.1283
    location_lon: -117.1563
```

*All of the above are pulled automatically from Census APIs during
`analyze` if left unset. Override only when you have more precise local data.*

---

### 2d. Unit Threshold (Standard 1 Scale Gate)

**What it is:** The minimum number of dwelling units at which a project triggers
evacuation capacity analysis. Projects below this threshold receive **MINISTERIAL**
approval automatically — no capacity analysis is run.

**Default:** 15 units (set in `config/parameters.yaml`)

**Technical basis:** 15 units × 2.5 veh/unit × 0.57 mobilization = **21.4 peak-hour
vehicles** — the first integer above the ITE Trip Generation Handbook de minimis of
10–15 peak-hour trips commonly used in California traffic studies. At this size the
project's vehicle contribution is statistically distinguishable from background
traffic variation regardless of road class.

**Statutory anchor:** California Housing Crisis Act (SB 330, Gov. Code §65905.5) applies
heightened protections to projects of 10+ units, establishing legislative recognition
that projects of that scale have material impacts. 15 sits just above the ITE de
minimis within that class.

**When to override:** Most cities should accept the 15-unit default. Consider lowering
it if your city has a severely constrained road network (e.g., hillside communities
with limited two-lane evacuation corridors) or if your city council has adopted a
lower threshold through ordinance.

**When NOT to lower it below 10:** Projects of 1–9 units are squarely in SB 9 /
single-family territory. A threshold below 10 is harder to defend against an HCD
challenge that the standard functions as a categorical prohibition on small infill.

**How to set it:**

```yaml
# config/cities/{city}.yaml
overrides:
  unit_threshold: 10   # city-specific value; must be documented in adoption ordinance
```

JOSH automatically propagates this to all scenario sub-configs (Scenario A wildland,
Scenario B local density). No other files need to change.

**Legal documentation required:** The adopted threshold must appear in:
1. The adopting ordinance amending the General Plan Safety Element or Zoning Code
2. Every determination brief (JOSH includes it automatically in the audit trail)
3. A staff report section explaining the ITE trip-generation or local study basis

**Defensibility tiers for lower thresholds:**

| Threshold | Basis | Legal comfort |
|-----------|-------|---------------|
| 15 (default) | ITE de minimis + SB 330 | Strong — two independent anchors |
| 10 | SB 330 statutory anchor | Defensible — single statutory anchor |
| < 10 | Must have local study | Requires city-specific trip-generation analysis |

If you lower the threshold below 15, add a `unit_threshold_basis` note to your city
config for the audit trail:

```yaml
overrides:
  unit_threshold: 10
unit_threshold_basis: >
  City council adopted 10-unit threshold per Resolution 2025-XX. Basis: SB 330
  (Gov. Code §65905.5) applies to 10+ unit projects; 10 × 2.5 × 0.57 = 14.25
  peak-hour vehicles, above the noise floor of daily traffic variation on
  constrained hill corridors. See Attachment B of staff report dated [date].
```

---

## Step 3 — Validate Against Known Routes

Set known evacuation routes from the city's General Plan Safety Element
or emergency management plans. JOSH will flag if these roads don't appear
in the analyzed network:

```yaml
known_evacuation_routes:
  - "Leucadia Boulevard"
  - "El Camino Real"
  - "Encinitas Boulevard"
  - "Coast Highway 101"
```

---

## Step 4 — Run and Inspect

```bash
# Full analysis
uv run python main.py analyze --city "Encinitas" --state "CA"

# Evaluate a specific project
uv run python main.py evaluate --city "Encinitas" \
  --lat 33.0369 --lon -117.2920 \
  --units 75 --name "Test Project"

# Generate the multi-project demo map
uv run python main.py demo --city "Encinitas"
```

Check that:
- Known evacuation routes appear in `output/encinitas/routes.csv`
- V/C ratios are plausible (most routes 0.60–0.90 in WUI areas)
- The determination brief shows the correct mobilization source and citation
- No yellow warning callout appears for cities with a proper study

---

## Step 5 — Before Adopting Impact Fees

Before using JOSH outputs to set AB 1600 impact fees:

1. Commission a local empirical mobilization study (or document a comparable
   city transfer per Option B above)
2. Update `mobilization_source` to `local_study` and add the full citation
3. Have a licensed traffic engineer peer-review the methodology
4. Present outputs to city council for adoption as objective standards
5. Consult city attorney on AB 1600 nexus documentation requirements

---

## Quick Reference: City Config Checklist

```yaml
# Required
city_name: ""
state: "CA"
state_fips: ""
county_fips: ""
place_fips: ""
osmnx_place: ""
analysis_crs: ""           # EPSG:26910 (NorCal) or EPSG:26911 (SoCal)

# Mobilization — choose one option; see §2a above
mobilization_source: ""    # local_study | comparable_city | state_guidance | conservative_default
peak_hour_mobilization: 0.70
mobilization_citation: ""
mobilization_note: ""

# Employment (auto-calculated if omitted)
employment_rate: 0.60
commute_in_fraction: 0.40

# Optional — for cities with major campuses
universities: []

# Optional — for validation
known_evacuation_routes: []

# Policy threshold overrides — see §2d (unit_threshold) and parameters.yaml for all options.
# Any key listed here replaces the parameters.yaml default for this city only.
# JOSH propagates unit_threshold and vc_threshold to all scenario sub-configs automatically.
overrides: {}
# overrides:
#   unit_threshold: 10   # lower than default (15); requires adoption ordinance basis
#   vc_threshold: 0.85   # more conservative than HCM 0.95; requires adoption ordinance

# Optional — documents why a non-default unit_threshold was adopted (appears in audit trail)
# unit_threshold_basis: >
#   City council Resolution XXXX-XX. Basis: [ITE trip-generation analysis / local study].
```

---

*Last updated: 2026-03-06 — California Stewardship Alliance / JOSH v2.0*

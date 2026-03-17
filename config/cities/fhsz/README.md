# config/cities/fhsz/ — Local FHSZ Files for LRA Cities

## Why This Directory Exists

The CAL FIRE HHZ_ref_FHSZ ArcGIS REST API only serves **SRA (State Responsibility
Area)** zones. Cities that are classified as **LRA (Local Responsibility Area)** —
typically incorporated municipalities — return **0 features** from the API even when
they have adopted CAL FIRE FHSZ maps.

Example: Encinitas adopted CAL FIRE FHSZ maps in 2025 for its LRA area, covering
approximately ~18% VHFHSZ, ~9% High, and ~9% Moderate zones. The API returns nothing.

When a city config contains `fhsz_local_file`, JOSH loads that file instead of
querying the API. See `agents/data_acquisition.py → fetch_fhsz_zones()`.

## How to Obtain the Shapefile

1. Go to **CAL FIRE FRAP**: https://frap.fire.ca.gov/mapping/gis-data/
2. Download the **statewide FHSZ shapefile** (look for "Fire Hazard Severity Zones"
   under the GIS Data Downloads section).
3. Open in QGIS, ArcGIS, or any GIS tool.
4. Clip to the city boundary (use the Census TIGER city boundary or the
   `data/{city}/boundary.geojson` that JOSH caches after first run).
5. Save the clipped result as **GeoJSON** (`encinitas_fhsz.geojson`, etc.).

Alternatively, some counties maintain local FHSZ layers in their GIS portals.

## Required Columns

The GeoJSON must include at least:

- `geometry` — polygon geometries in any CRS (JOSH reprojects to EPSG:4326)
- One of the following zone classification columns (JOSH auto-detects):
  - `FHSZ9` — CAL FIRE API format: `SRA_VeryHigh`, `LRA_High`, `FRA_Moderate`, etc.
  - `HAZ_CLASS` — integer: 1=Moderate, 2=High, 3=VeryHigh
  - `SRA_ZONE`, `FHSZ`, `ZONE`, `CLASS` — alternate column names also accepted

`_normalize_fhsz_column()` in `data_acquisition.py` handles all of these formats.

## Auto-Provisioning (fhsz_fallback_api)

If `fhsz_local_file` is configured but the file doesn't yet exist, JOSH will
attempt to **auto-provision** it by querying public APIs before falling back to
the CAL FIRE HHZ_ref_FHSZ service.

Set `fhsz_fallback_api` in the city YAML to point to a county GIS FeatureServer
that has full LRA+SRA FHSZ coverage:

```yaml
fhsz_local_file: "config/cities/fhsz/encinitas_fhsz.geojson"
fhsz_fallback_api: "https://gis-public.sandiegocounty.gov/arcgis/rest/services/hosted/OES_KnowYourHazards_Wildfire_1/FeatureServer/0"
```

On the next `uv run python main.py analyze --city ... --refresh`, JOSH will:
1. Query the `fhsz_fallback_api` with the city's bounding box
2. Normalize the zone column and drop "No Designation" features
3. Save the result to `fhsz_local_file`
4. On subsequent runs, load from the cached file (no re-download until `--refresh`)

If `fhsz_fallback_api` is not set or returns 0 features, JOSH falls back to
the CAL FIRE HHZ_ref_FHSZ service (which covers only forested/High+VH areas).

**Known county public FHSZ FeatureServers:**

| County | URL |
|--------|-----|
| San Diego | `https://gis-public.sandiegocounty.gov/arcgis/rest/services/hosted/OES_KnowYourHazards_Wildfire_1/FeatureServer/0` |
| Alameda   | `https://services7.arcgis.com/T3LbxamSmhpjBppB/arcgis/rest/services/Alameda_County_Local_Responsibility_Area_Fire_Hazard_Severity_Zone_/FeatureServer/0` (LRA FHSZ, Feb 24 2025 adoption; fields: FHSZ integer 1/2/3, FHSZ_Descr string) |

Add entries here as you configure additional cities.

## File Naming and Config

Store files here as `{city_slug}_fhsz.geojson`. Reference them in the city YAML:

```yaml
fhsz_local_file: "config/cities/fhsz/encinitas_fhsz.geojson"
```

The path is relative to the project root (where you run `uv run python main.py`).

## Git Policy

**GeoJSON files in this directory are NOT committed to git.** They are derived
data files that may be large and are reproducible from public CAL FIRE sources.
Add them to `.gitignore` or rely on the root `.gitignore` which excludes `data/`.

The `README.md` (this file) IS committed. Document each city's file here:

| City       | File                        | Source                        | Date Added  |
|------------|-----------------------------|-------------------------------|-------------|
| Encinitas  | `encinitas_fhsz.geojson`    | CAL FIRE FRAP statewide, clipped to city boundary | TBD |
| Berkeley   | `berkeley_fhsz.geojson`     | Alameda County LRA FHSZ FeatureServer (Feb 24 2025), clipped to city boundary | 2026-03-16 |

## Cities That Need This

Use `fhsz_local_file` for any incorporated city where the API returns 0 features.
Confirm by running `uv run python main.py analyze --city "CityName" --state "CA"`
and checking the log for `FHSZ query returned 0 features`.

Known LRA cities that adopted CAL FIRE maps and require local files:
- **Encinitas, CA** — 2025 adoption; see `encinitas_fhsz.geojson`
- **Berkeley, CA** — LRA; API returned only 15 fragments (0.03 sq km, 0.1% of city).
  True coverage is ~15–20% (VHFHSZ upper hills, High transitional, Moderate foothill).
  `berkeley_fhsz.geojson` needed — see `config/cities/berkeley.yaml` for acquisition steps.

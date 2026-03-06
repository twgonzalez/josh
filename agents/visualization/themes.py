"""
Color constants, weight tables, and pure classification helpers.

No imports from siblings. No side effects. Import freely from any module.
"""

# ---------------------------------------------------------------------------
# LOS / FHSZ color scales
# ---------------------------------------------------------------------------

# LOS color scale: green (good) → dark red (failed)
LOS_COLORS = {
    "A": "#2ca02c",
    "B": "#98df8a",
    "C": "#ffbb78",
    "D": "#ff7f0e",
    "E": "#d62728",
    "F": "#8c0000",
}

FHSZ_COLORS = {
    1: "#ffeda0",   # Moderate — yellow
    2: "#fc8d59",   # High — orange
    3: "#d7301f",   # Very High — red
}

FHSZ_LABELS = {
    1: "Zone 1 — Moderate",
    2: "Zone 2 — High",
    3: "Zone 3 — Very High",
}

# ---------------------------------------------------------------------------
# Determination tier color maps
# ---------------------------------------------------------------------------

_TIER_MARKER_COLOR = {
    "DISCRETIONARY":           "red",
    "CONDITIONAL MINISTERIAL": "orange",
    "MINISTERIAL":             "green",
}

_TIER_CSS_COLOR = {
    "DISCRETIONARY":           "#c0392b",
    "CONDITIONAL MINISTERIAL": "#d67c00",
    "MINISTERIAL":             "#27ae60",
}

_TIER_BG_COLOR = {
    "DISCRETIONARY":           "#fdf2f2",
    "CONDITIONAL MINISTERIAL": "#fffbf0",
    "MINISTERIAL":             "#f0faf4",
}

_TIER_BORDER_COLOR = {
    "DISCRETIONARY":           "#e8b4b0",
    "CONDITIONAL MINISTERIAL": "#f5d49a",
    "MINISTERIAL":             "#a8d5b8",
}

# ---------------------------------------------------------------------------
# Route color maps (demo map — keyed by tier)
# ---------------------------------------------------------------------------

# Non-flagged serving routes — neutral "analysis footprint" color.
# These roads are within the search radius and were analyzed, but do NOT cause
# an exceedance. Shown muted so flagged routes stand out clearly.
_SERVING_ROUTE_NEUTRAL_COLOR  = "#d4a017"   # muted amber
_SERVING_ROUTE_NEUTRAL_WEIGHT  = 2
_SERVING_ROUTE_NEUTRAL_OPACITY = 0.35

# Flagged route colors keyed by tier — prominently shown; project causes exceedance.
_TIER_ROUTE_COLOR_FLAGGED = {
    "DISCRETIONARY":           "#c0392b",
    "CONDITIONAL MINISTERIAL": "#e07000",
    "MINISTERIAL":             "#1a7a1a",
}
_FLAGGED_ROUTE_WEIGHT  = 7
_FLAGGED_ROUTE_OPACITY = 0.80

# Legacy: tier-keyed serving color still used for search-radius circle color.
_TIER_ROUTE_COLOR = {
    "DISCRETIONARY":           "#c0392b",
    "CONDITIONAL MINISTERIAL": "#e07000",
    "MINISTERIAL":             "#2ca02c",
}

# Standard 5 (local density) route colors — fixed, not tier-dependent
_LOCAL5_SERVING_COLOR = "#0d9488"   # teal
_LOCAL5_FLAGGED_COLOR = "#ea580c"   # orange

# Evaluation map unified route colors (single-project view)
SERVING_ROUTE_COLOR = "#4A90D9"     # steel blue — all serving routes
FLAGGED_ROUTE_COLOR = "#E84040"     # orange-red — routes project causes to cross v/c

# ---------------------------------------------------------------------------
# Traffic background bucketing
# ---------------------------------------------------------------------------

# Pastel traffic-load colors (background road layer, low opacity).
_TRAFFIC_BG_BUCKETS = [
    (0.40, "#d6d6d6"),   # uncongested — light gray
    (0.60, "#f5dfc0"),   # moderate    — light peach
    (0.80, "#f5c096"),   # heavy       — light orange
    (1.00, "#f5a0a0"),   # near-cap    — light red
    (9999, "#ee8080"),   # over-cap    — coral
]

# ---------------------------------------------------------------------------
# Highway line weights
# ---------------------------------------------------------------------------

_HIGHWAY_WEIGHT: dict = {
    "motorway":        12,
    "motorway_link":    7,
    "trunk":           11,
    "trunk_link":       6,
    "primary":          9,
    "primary_link":     5,
    "secondary":        7,
    "secondary_link":   4,
    "tertiary":         5,
    "tertiary_link":    3,
    "residential":      4,
    "living_street":    3,
    "unclassified":     3,
    "service":          2,
    "track":            2,
    "path":             1,
    "cycleway":         1,
}
_HIGHWAY_WEIGHT_DEFAULT = 3

_VC_WEIGHT_MULTIPLIER: dict = {
    "#d6d6d6": 0.6,
    "#f5dfc0": 0.85,
    "#f5c096": 1.1,
    "#f5a0a0": 1.45,
    "#ee8080": 1.9,
}

# ---------------------------------------------------------------------------
# Normal-day v/c by road class (used for fallback background)
# ---------------------------------------------------------------------------

_ROAD_CLASS_NORMAL_VC: dict = {
    "freeway":   0.65,
    "multilane": 0.50,
    "two_lane":  0.25,
}


# ---------------------------------------------------------------------------
# Pure classification helpers
# ---------------------------------------------------------------------------

def _vc_background_color(vc: float) -> str:
    """Return a muted pastel color for the road traffic background layer."""
    for threshold, color in _TRAFFIC_BG_BUCKETS:
        if vc < threshold:
            return color
    return _TRAFFIC_BG_BUCKETS[-1][1]


def _normal_traffic_vc(road_type: str) -> float:
    """Return an estimated normal-day v/c ratio for a road segment."""
    return _ROAD_CLASS_NORMAL_VC.get(str(road_type or ""), 0.25)


def _road_class_bg_color(highway_val) -> str:
    """Return a neutral gray for the city-wide road reference background."""
    if isinstance(highway_val, list):
        highway_val = highway_val[0] if highway_val else ""
    hw = str(highway_val or "")
    if hw in ("motorway", "motorway_link", "trunk", "trunk_link"):
        return "#b4b4b4"
    if hw in ("primary", "primary_link"):
        return "#bebebe"
    if hw in ("secondary", "secondary_link"):
        return "#c8c8c8"
    if hw in ("tertiary", "tertiary_link"):
        return "#d4d4d4"
    return "#dedede"

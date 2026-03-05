# New Session: Fix Demo Map Traffic Background Visual Overload

## Context
Fire Evacuation Capacity Analysis System — Phase 2b complete.
Codebase: `/Users/twgonzalez/Dropbox/Code Projects/csf/csf-fire/`
Run: `export PATH="$HOME/.local/bin:$PATH" && uv run python main.py ...`
Last commit: `8923f1e`

## Problem
The demo map traffic background layer (`create_demo_map` Layer 2) is visually
overwhelming. Because Berkeley's KLD buffer demand puts essentially every road at
LOS F (v/c >> 1.0), the entire city fills with thick coral/red lines and the map
looks like a solid red blob. Evacuation route colors (red=DISC, green=MIN) are
unreadable against the background.

See: run `uv run python main.py demo --city "Berkeley"` and open
`output/berkeley/demo_map.html` to reproduce.

## Root Cause
`_traffic_weight()` applies a 1.9× multiplier for over-capacity roads on top of
already-large base weights (primary=9, secondary=7). Since ~100% of Berkeley
roads are over-capacity in the KLD model, nearly every segment gets its maximum
weight, filling the visual field.

## Fix Needed (file: `agents/visualization.py`)

In `create_demo_map()`, the traffic background bucketing loop (around line 1050):

**Current:**
```python
weight = _traffic_weight(row.get("highway"), color)
# ... opacity: 0.32
```

**Change to** — use thin fixed weights for background, ignore congestion multiplier:
```python
weight = max(_highway_weight(row.get("highway")) * 0.25, 0.5)
# ... opacity: 0.15
```

This keeps the color-coded congestion signal while making the background subtle
enough that serving routes and FHSZ fills are legible.

## Visual Hierarchy Goal
1. CartoDB Positron base (white/gray)
2. FHSZ fire zone fills (light orange/red, 20% opacity) — barely there
3. Traffic background (very thin lines, pastel colors, 15% opacity) — road reference only
4. Serving routes (thick, tier-colored red/green/orange, 90% opacity) — PRIMARY signal
5. Project markers (pins) — on top

## What NOT to Change
- `_HIGHWAY_WEIGHT` dict or `_highway_weight()` function (used by eval map layers 3/4)
- `_traffic_weight()` function (keep it, just don't call it for the background)
- Eval map (`create_evaluation_map`) — already fixed, working well
- Demo panel dropdown, legend, project cards — all working correctly

## Test
```bash
uv run python main.py demo --city "Berkeley"
open output/berkeley/demo_map.html
```

Expected: city street grid faintly visible, FHSZ zones light fill in NE hills,
serving routes clearly legible in their tier colors.

## Also Consider
If the background is still too heavy after the weight fix, also try:
- Muting the pastel colors further (e.g. `#e8e8e8` instead of `#d6d6d6` for
  uncongested, `#f0c8c8` instead of `#ee8080` for over-capacity)
- Dropping the over-capacity bucket entirely from the background
  (since everything is over-capacity in this model, it adds no information)

## Commit When Done
```bash
git add agents/visualization.py
git commit -m "Fix demo map traffic background visual overload"
```

# JOSH Sidebar UI/UX — What-If Analysis Implementation Prompt

## Task

Implement the approved plan to overhaul the JOSH demo map sidebar (`agents/visualization/demo.py`)
with UI/UX infographics best practices and client-side what-if analysis.

**The full plan is at:**
```
/Users/twgonzalez/.claude/plans/declarative-dancing-sprout.md
```
Read it before starting. All code templates, data attributes, JS functions, and verification
steps are in that file. Do not deviate from the plan.

---

## Single File to Modify

```
agents/visualization/demo.py
```

No other files need changes. No server/backend changes. Everything runs client-side in JavaScript
embedded in the static `demo_map.html` output.

---

## Key Insight (why client-side JS works)

For a given project location, the **bottleneck effective capacity is fixed** (it's a property of
the road network, computed at analysis time by Agent 2). Only `units` and `stories` are variable.

So the ΔT formula runs entirely in browser JS:
```
egress = stories >= ep_threshold ? min(stories × ep_mps, ep_max) : 0
deltaT = (units × 2.5 × mob_rate / bottleneck_cap) × 60 + egress
tier   = units < unit_threshold ? MINISTERIAL
       : deltaT > threshold     ? DISCRETIONARY
       :                          CONDITIONAL
max_units_conditional = floor((threshold − egress) × bottleneck_cap / 60 / (2.5 × mob_rate))
```

All constants (`bottleneck_cap`, `mob_rate`, `threshold`, `ep_*`) are embedded as `data-*`
attributes on each `.proj-detail-card` div at Python render time.

---

## Prioritized Changes in `demo.py`

### 1. Data Attributes on card div — `_build_project_detail_div()` (~line 845)

Add these `data-*` attributes to the outer div:
```
data-bottleneck-cap      worst-case bottleneck_effective_capacity_vph (min across dt_results)
data-mob-rate            mobilization rate for hazard_zone
data-threshold           threshold_minutes (from dt_result or derived: safe_window × max_share)
data-unit-threshold      config unit_threshold (15)
data-safe-window         safe_egress_window_minutes
data-max-share           max_project_share (0.05)
data-initial-units       project.dwelling_units
data-initial-stories     project.stories
data-hazard-zone         project.hazard_zone string
data-ep-threshold-stories  config egress_penalty.threshold_stories (4)
data-ep-min-per-story      config egress_penalty.minutes_per_story (1.5)
data-ep-max-minutes        config egress_penalty.max_minutes (12.0)
data-size-met            "true"/"false"
```

For MINISTERIAL projects (`dt_results=[]`): `worst_cap = 0.0`; derive `threshold` from config.

### 2. Tier Action Label — `_build_project_detail_div()` (~line 847)

Add module-level dict:
```python
_TIER_ACTION_LABELS = {
    "DISCRETIONARY":           "Planning Commission review required — public hearing",
    "CONDITIONAL MINISTERIAL": "Staff approval with conditions — no public hearing",
    "MINISTERIAL":             "Over-the-counter permit — no discretionary review",
}
```

Insert italic sub-line below tier name in badge HTML.

### 3. ΔT Gauge — replaces three-column strip (~lines 863–888)

Replace the `display:flex; gap:0` three-column block (Units | Max ΔT | Limit) with:
- Left column: Units (stays, gets `id="wi-units-display-{idx}"`)
- Right: Segmented gauge bar

**Gauge design:**
- Bar represents `[0, 2×threshold]` — threshold tick always at exactly 50% width
- Green zone: left half (0 → threshold)
- Red zone: right half (threshold → 2×threshold)
- Indicator dot: `left = clamp(deltaT / (2×threshold) × 100, 0, 105)%`
- CSS `transition: left 0.15s ease` — animates on slider drag
- IDs: `wi-gauge-{idx}`, `wi-dot-{idx}`, `wi-numtext-{idx}`

Python render:
```python
if dt_results and size_met and threshold > 0:
    gauge_pct    = min((max_dt / (2 * threshold)) * 100.0, 105.0)
    gauge_numtxt = f"{max_dt:.2f} min / {threshold:.2f} min limit"
else:
    gauge_pct    = 0.0
    gauge_numtxt = "—"
```

### 4. Formula Strip Terminology — (~lines 891–896)

- `vpu` → `veh/unit`
- `mob` → `evac. rate` (with `title="Evacuation rate — Zhao et al. 2022"`)
- Add `id="wi-formula-{idx}"` wrapper for JS update
- Show `+ {egress_minutes:.1f} min egress (NFPA 101)` when egress > 0

### 5. What-If Collapsible Section — new block before brief link button

**Python compute (static mitigation path):**
- If egress alone exceeds threshold: "No unit count qualifies" message
- For DISCRETIONARY: `max_units_cond = floor((threshold - egress) × worst_cap / 60 / (2.5 × mob_rate))`
  → "Conditional path: reduce to ≤ N units"
- For CONDITIONAL: → "Headroom: N max (+X from current)"

**HTML structure:**
- Collapsible toggle header ("What-If Analysis ▶")
- Units range slider (min=1, max=max(units×3, 200), step=1, oninput=recalcDeltaT({idx}))
- Stories stepper (− / [value] / +) — buttons call stepStories({idx}, ±1)
- Live result chip (tier + ΔT + margin) — populated by JS, starts empty
- Mitigation path div — updated by JS
- Reset button

**IDs:** `wi-body-{idx}`, `wi-toggle-icon-{idx}`, `wi-units-{idx}`, `wi-units-val-{idx}`,
`wi-stories-val-{idx}`, `wi-result-{idx}`, `wi-mitigation-{idx}`

### 6. JavaScript Engine — `_build_demo_panel_html()` script block

Append inside the existing IIFE (before `}})();`):

**Four functions:**
- `toggleWhatIf(idx)` — show/hide body, flip chevron, call recalcDeltaT on first open
- `stepStories(idx, delta)` — clamp to ≥0, update display, call recalcDeltaT
- `resetWhatIf(idx)` — restore from `data-initial-units` / `data-initial-stories`, call recalcDeltaT
- `recalcDeltaT(idx)` — main engine (see plan file for full JS; ~80 lines)

The `recalcDeltaT` function updates: gauge dot position, formula strip text, result chip, and
mitigation path — all in real time as the slider moves.

---

## Verification After Implementation

```bash
export PATH="$HOME/.local/bin:$PATH"
uv run python main.py demo --city "Berkeley"
open output/berkeley/demo_map.html
```

Checkpoints:
1. **Hills Gateway** tier badge: "Planning Commission review required — public hearing"
2. **Formula**: "80 units × 2.5 veh/unit × 75% evac. rate = 150 vph"
3. **Gauge dots**: Hills Gateway far right (red) · Downtown Mid-Rise at ~21% (green) · Cedar Street ~96% (red) · Ashby: "— below size threshold"
4. **What-if Hills Gateway**: Slide 80→18 → CONDITIONAL · Slide to 14 → MINISTERIAL · Mitigation: "Conditional path: reduce to ≤ 18 units"
5. **What-if Cedar Street (6 stories)**: "No unit count qualifies — egress penalty (9.0 min) exceeds limit (6.00 min)" · Reduce to 3 stories → CONDITIONAL
6. **Reset button**: restores to original values and gauge position

---

## Previously Completed (do NOT re-implement)

Previous sessions already completed:
- `brief.py`: Controlling Finding callout, threshold derivation block, margin column, NIST TN 2135 citations
- `demo.py`: Controlling finding headline (between badge and quick-info strip), margin sub-label, threshold derivation sub-label, legend note
- `popups.py`: Threshold precision .2f, derivation footnote, NIST TN 2135 footer, margin in route lines

Demo map verified and regenerated. All 6 Berkeley projects confirmed correct.

The current task is the **sidebar What-If analysis** only — new interactive layer on top of the
existing (correct) static display.

# FHSZ Degradation Robustness Analysis

**Prepared for California Stewardship · May 2026 · Berkeley + Encinitas demo sets**

------

## Headline Finding

**Removing the FHSZ road-capacity degradation factor entirely does not change a single ΔT determination tier across either the Berkeley or Encinitas demo project sets.** All 6 currently-Discretionary projects remain Discretionary; all 3 currently-Conditional/Ministerial projects remain in tier. The factor influences the *margin* of each finding, not the finding itself.

This matters because the May 2026 Fire Science Consulting LLC review (Ziazi & Simeoni) identified the 0.35 / 0.50 / 0.75 FHSZ degradation factors as a composite engineering-judgment value pending independent traffic-engineering review. The analysis below shows that JOSH's *outputs* are robust to that pending review even before it resolves: if a future reviewer argues for a smaller factor, the affected projects would still fail their thresholds by 6–17 minutes.

------

## Berkeley — 4 demo projects

| # | Project | Site zone | Tier | Current ΔT | ΔT if FHSZ removed | Impact (min) | Impact (%) | Threshold |
|---|---|---|---|---:|---:|---:|---:|---:|
| 1 | Downtown Mid-Rise (85u, 3 stories) | non_fhsz | COND | 4.59 | 4.59 | 0.00 | 0.0% | 6.00 |
| 2 | Hills Gateway (80u, 3 stories) | **vhfhsz** | DISC | 26.06 | 9.12 | **16.94** | 65.0% | 2.25 |
| 3 | Claremont Hills Terrace (25u, 3 stories) | non_fhsz | COND | 2.28 | 2.28 | 0.00 | 0.0% | 6.00 |
| 4 | Cedar Street Infill (75u, 6 stories, +9 min egress) | non_fhsz | DISC | 15.84 | 15.84 | 0.00 | 0.0% | 6.00 |

**Berkeley totals:** 16.94 min FHSZ-attributable ΔT across 4 projects · avg 4.2 min/project · **0 tier changes.** Only Hills Gateway has FHSZ exposure on its controlling path. Cedar Street Infill is Discretionary entirely because of NFPA 101 building egress (6 stories × 1.5 min), not road degradation.

------

## Encinitas — 5 demo projects

| # | Project | Site zone | Tier | Current ΔT | ΔT if FHSZ removed | Impact (min) | Impact (%) | Threshold |
|---|---|---|---|---:|---:|---:|---:|---:|
| 1 | Clark Avenue Apartments (199u, 3 stories) | non_fhsz | DISC | 18.15 | 18.15 | 0.00 | 0.0% | 6.00 |
| 2 | Sage Canyon Apartments (120u, 5 stories) | **vhfhsz** | DISC | 38.77 | 18.44 | **20.33** | 52.4% | 2.25 |
| 3 | Quail Meadows Apartments (448u, 4 stories) | non_fhsz | DISC | 40.56 | 18.10 | **22.46** | 55.4% | 6.00 |
| 4 | Goodson Project (250u, 5 stories) | **high_fhsz** | DISC | 46.07 | 21.00 | **25.07** | 54.4% | 4.50 |
| 5 | El Camino Real Corridor (29u, 3 stories) | non_fhsz | COND | 4.47 | 1.56 | 2.91 | 65.0% | 6.00 |

**Encinitas totals:** 70.77 min FHSZ-attributable ΔT across 5 projects · avg 14.2 min/project · **0 tier changes.** Two non-FHSZ-site projects (Quail Meadows, El Camino Real Corridor) have controlling bottlenecks that route *through* FHSZ-degraded segments — the methodology correctly applies degradation per road-segment, not per project-site.

------

## Side-by-Side

| Metric | Berkeley | Encinitas |
|---|---:|---:|
| Projects analyzed | 4 | 5 |
| Discretionary projects | 2 | 4 |
| Conditional / Ministerial | 2 | 1 |
| Projects with FHSZ-degraded controlling path | 1 (25%) | 4 (80%) |
| Non-FHSZ sites with FHSZ-degraded bottleneck | 0 | 2 |
| Total FHSZ-attributable ΔT | 16.94 min | 70.77 min |
| Avg FHSZ impact / project | 4.2 min | 14.2 min |
| Max single-project FHSZ impact | 16.94 min (Hills Gateway) | 25.07 min (Goodson) |
| **Tier changes if FHSZ removed** | **0** | **0** |

------

## Five Findings for the Meeting Record

1. **The FHSZ degradation factor influences *margin*, not *outcome*.** Across 9 projects in 2 cities, removing the factor entirely would not change a single determination. This robustness is the strongest available defense against the "the city is using a contested engineering-judgment factor to fail projects" challenge. Even at the factor's most-skeptical interpretation (zero degradation), the four large Encinitas projects still exceed their thresholds by 12–17 minutes; Hills Gateway in Berkeley still exceeds by 6.9 minutes.

2. **Encinitas has approximately 4× the per-project FHSZ exposure of Berkeley.** Geography explains it. Berkeley's flatland corridors (Downtown, Cedar Street, Claremont) reach the regional network entirely through non-FHSZ roads — only the literally-in-VHFHSZ Hills Gateway project hits FHSZ-degraded bottlenecks. Encinitas's coastal canyons and inland fire zones are interleaved enough that most bottlenecks pass through FHSZ segments even when the project site itself does not.

3. **Two non-FHSZ-site Encinitas projects have FHSZ-degraded bottlenecks.** Quail Meadows (non_fhsz, 448u) and El Camino Real Corridor (non_fhsz, 29u) both route their controlling paths through FHSZ-degraded segments. If a developer argues "my site isn't in a fire zone, so why does fire degradation apply to me," the answer is: *evacuees from your project pass through fire-zone segments on the way out, and those segments will not operate at full capacity during the fire — that is the constraint the standard measures.*

4. **Building egress penalty is a *separate* tier driver from FHSZ.** Berkeley's Cedar Street Infill (75u, 6 stories) is Discretionary entirely from the 9-minute NFPA 101 egress penalty, with zero FHSZ contribution. Encinitas's Sage Canyon and Goodson Project both carry 7.5-min egress penalties (5 stories). For these projects, the mitigation path is building redesign (more stairwells, more garage exits) or unit reduction — *not* road improvement.

5. **The factor's relative impact is largest on smaller projects on FHSZ-routed corridors.** El Camino Real Corridor (29u, comfortably under threshold) shows 65% of its small ΔT attributable to FHSZ; Hills Gateway (80u, decisively over) also shows 65%. Absolute impact tracks project size — Goodson's 250 units in VHFHSZ-routed corridors yields the largest absolute impact (25.07 min). Pattern: FHSZ impact is approximately linear in `(units × project_share_in_FHSZ_routed_corridors)` once the bottleneck is FHSZ-routed.

------

## Methodology

For each project's controlling path, with current ΔT and bottleneck hazard-degradation factor `d`:

```
road_component       = ΔT_current − egress_penalty
ΔT_if_FHSZ_removed   = (road_component × d) + egress_penalty
FHSZ_impact          = ΔT_current − ΔT_if_FHSZ_removed
```

`d = 1.00` (non-FHSZ) means zero FHSZ impact. `d = 0.35` (VHFHSZ) means the road-component shrinks to 35% of its current value if degradation is removed — i.e., **65% of the road-component ΔT is the degradation factor's contribution.**

Project-site hazard zone is the zone of the project's parcel (drives the safe-egress-window threshold). The controlling-path bottleneck zone is the zone of the constraint road segment (drives the road-component degradation). The two can differ — that is why two non-FHSZ-site Encinitas projects show FHSZ-attributable impact.

Threshold values (`safe_egress_window × 5%`): VHFHSZ = 2.25 min, High FHSZ = 4.50 min, Moderate / Non-FHSZ = 6.00 min.

Source data: pipeline-generated `result.paths[]` and `result.delta_t_threshold` for each project in `output/berkeley/analysis_map.html` (regenerated May 2026) and `josh-pipeline/output/encinitas/analysis_map.html` (regenerated May 2026).

------

## Citation Context

The FHSZ degradation factor is identified as an open methodology item in the Fire Science Consulting LLC preliminary technical assessment (Ziazi & Simeoni, May 26 2026). The factor is currently sourced as composite engineering judgment anchored against HCM 2022 Ch. 11 worst-case weather Capacity Adjustment Factors (Ex. 11-20) and NIST TN 2135 Camp Fire empirical observations. Independent traffic-engineering review is pending and tracked on the JOSH Methodology Roadmap. See [JOSH_Legal_Defensibility_Memo.md §3.7](JOSH_Legal_Defensibility_Memo.md) for the full open-items list.

This robustness analysis demonstrates that the methodology's *determinations* are stable across the full range of factor values the pending review is likely to consider — from current (0.35 VHFHSZ) to no degradation at all.

> Copyright (C) 2026 Thomas Gonzalez · AGPL-3.0-or-later

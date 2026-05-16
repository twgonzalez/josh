# Multi-hazard UX mockup

`multihazard_mockup.html` is a faked-data, file://-openable prototype of the JOSH
multi-hazard analysis map. It demonstrates the locked UX patterns for the multi-hazard
extension against two illustrative projects (one wildfire-controlled, one flood-controlled)
in a fictional coastal city ("Demoville").

**Open it:** double-click the HTML file, or run `open output/mockup/multihazard_mockup.html`.
No build step, no backend, no install.

## Locked UX decisions

These are binding for the multi-hazard frontend implementation. Full rationale lives in
`docs/multi_hazard_spec.md` → "User Interface — Multi-Hazard Frontend (LOCKED)".

- **Right-side panel** (~360px). Departs from production `analysis_map.html`, which uses a
  left sidebar.
- **One project at a time**, selected via dropdown. No card stack.
- **No marker popups.** Marker click selects the project and populates the panel; popups
  would occlude the evacuation route.
- **Panel structure:** Hazard Layers (collapsed) → Project (dropdown, tier, ΔT bar chart,
  hazard scenario selector, hazards-evaluated list, Open Brief button).
- **Brief modal:** sections A / B / C / D (D = Hazards Excluded, informational only).
- **Earthquake is informational only.** Grey-hatch overlay, no ΔT bar, no AntPath option,
  Section D of the brief.
- **Controlling hazard is always named** in the tier line, hazards-evaluated list, brief
  Section C, and the determination line.

## What is faked

- Polygon coordinates (FHSZ, SFHA, liquefaction) — eyeballed, not real.
- Project locations, names, addresses — fictional.
- ΔT values, capacities, bottleneck names — illustrative.
- Route polylines — hand-drawn, no Dijkstra.

The visual patterns are the deliverable, not the data.

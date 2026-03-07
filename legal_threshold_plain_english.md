# Fire Evacuation Review — How the Logic Works

*Plain-English explanation of the legal threshold logic for city staff and planning commissioners.
For the full technical and legal citation reference, see `legal.md`.*

---

## The Core Question

When a developer proposes a new housing project, the city must answer one question:

> **Will this project make it harder for people to evacuate during a fire?**

If the answer is yes — and the project is large enough to cause a measurable difference — the project requires **discretionary review**. If not, the city must approve it as a routine ministerial matter.

This system answers that question using only objective, measurable math. No one applies judgment. The same calculation runs the same way for every project.

---

## Step 1 — Is the Project Big Enough to Matter?

Small projects don't generate enough cars to measurably change traffic on evacuation routes. A 4-unit ADU adds roughly 6 peak-hour vehicles; a 14-unit project adds roughly 20. Both are within the noise of normal daily traffic variation — the roads wouldn't know the difference.

The size threshold exists to screen out projects that are mathematically too small to affect evacuation capacity. Projects below the threshold get **ministerial approval automatically** — no traffic analysis needed.

**How the threshold is set:** The minimum project size is the number of units at which the project's peak-hour vehicle load crosses the traffic engineering *de minimis* — the level at which the impact becomes statistically distinguishable from background variation. The formula is:

```
peak-hour vehicles = units × 2.5 vehicles/unit × 0.57 evacuation mobilization rate
```

At 15 units: `15 × 2.5 × 0.57 = 21.4 peak-hour vehicles`. This exceeds the ITE Trip Generation Handbook de minimis of 10–15 peak-hour trips widely used in California traffic studies. That is the technical basis for the 15-unit threshold. The statutory anchor is California's Housing Crisis Act (SB 330), which applies heightened protections to projects of 10+ units — a legislative recognition that projects of that scale have material impacts. 15 units sits just above the ITE de minimis within that class.

---

## Step 2 — Which Roads Serve This Project?

The system identifies every evacuation route within **half a mile** of the project using a road network analysis. These are the roads residents would actually use to leave the area in a fire emergency. Only these roads are evaluated.

---

## Step 3 — Is Any Serving Road Already Near Its Limit?

Each road has a published capacity — the maximum number of vehicles per hour it can carry before traffic breaks down. That number comes from the **Highway Capacity Manual (HCM 2022)**, the national standard used by traffic engineers everywhere.

The system calculates what fraction of each road's capacity is already being used before the project is built. This is called the **volume-to-capacity ratio (v/c)**:

```
v/c ratio = current traffic volume ÷ road capacity
```

| v/c Range | Level of Service | What it means |
|-----------|-----------------|---------------|
| 0.00–0.60 | A–D | Road is operating freely |
| 0.60–0.95 | E | Road is near capacity |
| **0.95+** | **F** | **Road is at or past its limit** |

The threshold of **0.95** is not a city policy choice. It is the exact boundary defined in HCM 2022 between Level of Service E and Level of Service F — the point where traffic engineers consider a road to be operating in breakdown conditions.

---

## Step 4 — Does This Project Push Any Road Over the Limit?

The system adds the project's peak-hour vehicles to each serving road's existing load and recalculates the v/c ratio.

**The key rule is marginal causation:** the project only triggers discretionary review if it *causes* a road to cross the 0.95 threshold.

| Situation | What happens |
|-----------|--------------|
| Road is already at v/c = 0.97 (already failing) | Project did not cause that problem. No trigger. |
| Road is at v/c = 0.92; project pushes it to 0.97 | **Project caused the crossing. Triggers discretionary review.** |
| Road is at v/c = 0.92; project pushes it to 0.94 | Road stays below threshold. No trigger. |

This mirrors how courts assess causation everywhere: you are responsible for harm you caused, not harm that already existed before you arrived.

---

## The Three Outcomes

| Outcome | When it applies | What the city does |
|---|---|---|
| **Ministerial** | Project is below the size threshold — too small to cause a measurable impact | Must approve; standard conditions only |
| **Conditional Ministerial** | Project is large enough to matter, but no serving road is pushed over capacity | Must approve; may attach evacuation-related conditions |
| **Discretionary** | Project is large enough to matter AND it pushes at least one serving road from below 0.95 to at or above 0.95 | May require full discretionary review, including an EIR |

---

## Where Fire Hazard Zones Fit In

Being located inside a state-designated **Fire Hazard Severity Zone (FHSZ)** does **not** automatically require discretionary review. The fire zone shows up in the audit trail and can affect what conditions the city attaches — but it does not change the determination tier by itself.

**This is intentional and legally important.** A developer cannot be told "you're in a fire zone, so you automatically need discretionary review." That would be subjective. The only trigger for discretionary review is the project causing a road to exceed its capacity limit — which is fully objective and identical for every project everywhere in the city.

A project in a Zone 3 fire area that is small or well-served by high-capacity roads will still receive ministerial approval. A project outside any fire zone that pushes a constrained two-lane road into breakdown will trigger discretionary review. The road math is what decides — not the fire zone designation.

---

## Why This Matters Legally

California state law (**AB 747, Government Code §65302.15**) requires cities to evaluate evacuation route capacity using **objective standards** — standards that produce the same answer regardless of who runs them, with no room for staff judgment or political discretion.

This system produces a determination that:

- Uses only published data (road capacities from HCM 2022, housing unit counts from Census ACS)
- Applies identical math to every project
- Generates a full audit trail showing every input, every intermediate calculation, and every output
- Can be reproduced by any qualified engineer starting from the same inputs

That reproducibility is what makes the determination legally defensible if challenged by an applicant.

---

## Quick Reference — Key Numbers

| Parameter | Value | Source |
|-----------|-------|--------|
| Size threshold (default) | 15 units | ITE de minimis (21.4 vph); SB 330 statutory anchor |
| Evacuation mobilization rate | 0.57 | KLD Engineering Berkeley AB 747 Study (March 2024) |
| Vehicles per unit | 2.5 | U.S. Census ACS |
| Serving route radius | 0.5 miles | Standard 3 |
| v/c threshold for breakdown | 0.95 | HCM 2022, LOS E/F boundary |

---

## What the System Does NOT Do

- It does not evaluate whether a project is a good idea.
- It does not weigh aesthetics, neighborhood character, or school capacity.
- It does not predict whether a fire will actually occur.
- It does not replace the city's discretionary review process — it determines *when* that process applies.

The system's only job is to answer, objectively and consistently, whether a proposed project causes a measurable degradation in evacuation route capacity. Everything else remains within the city's normal authority.

---

*For technical citations, HCM methodology details, and legal defense language, see `legal.md`.
For scenario coverage and system architecture, see `specs.md`.*

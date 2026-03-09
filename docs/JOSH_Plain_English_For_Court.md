# How the Evacuation Capacity Standard Works

**Prepared for judicial review — plain language explanation of the methodology**

------

## The Question the Standard Answers

When a developer proposes new homes in an area prone to wildfires, earthquakes, or floods, the city must answer one question:

**If an emergency occurs and everyone has to leave, how much longer does it take because this project exists?**

The answer is a number, measured in minutes. The city calls it ΔT — the project's time contribution to evacuation.

------

## The Principle

Every occupied building in California has a sign on the wall: **Maximum Occupancy.** A fire marshal sets that number based on the size of the exits. It does not matter how nice the building is, how much the owner invested, or how many people want to get in. The exits can handle a certain number of people. Beyond that number, people die in a fire because they cannot get out.

A fire marshal does not ask who is already in the nightclub before deciding whether 50 more people can safely enter. The question is whether those 50 people can get through the doors fast enough if there is an emergency. The answer depends on the doors and the 50 people. It does not depend on who else is in the room.

An evacuation road is a door. A housing project is a group of people asking to walk through it. This standard measures whether those people can get through the door fast enough. The road either has the capacity or it does not. That is a physical fact, measured the same way a fire marshal measures exit width — from published safety standards, applied to the specific building.

The only difference is scale. Instead of a door in a nightclub, the exit is a road through a canyon. Instead of people walking through a corridor, families are driving through a bottleneck. Instead of a fire in a kitchen, the hazard is a wildfire moving through a designated fire zone. But the principle is identical: **you cannot put more people behind an exit than the exit can handle in an emergency.**

This standard measures the exit. It counts the people. It does the math. In minutes.

------

## How the Number Is Calculated

There are four steps. Each step uses only public data or published national standards. No step involves anyone's opinion.

### Step 1: Count the Cars

Every home has cars. The U.S. Census tells us how many — on average, about 2.5 vehicles per household in California.

When a building needs to be evacuated, nearly everyone leaves. The National Fire Protection Association's Life Safety Code (NFPA 101) — the same standard used to size stairwells, corridors, and emergency exits in every building in the country — is designed for 100% occupant evacuation. Fire marshals do not size exits assuming only some people will try to leave. They size exits for everyone.

This standard applies the same principle. We assume 90% of the project's households will generate a vehicle during an evacuation. The remaining 10% accounts for households with no vehicle, which the Census measures directly.

So for a proposed project of 45 homes:

```
45 homes × 2.5 vehicles × 90% = 101 vehicles
```

That is how many cars this project puts on the road during an evacuation. The number is the same regardless of where the project is located. The project's people are the project's people. What changes by location is the road — how big is the door they need to fit through.

### Step 2: Find the Weakest Link in the Road

Every car leaving the project area has to pass through the road network to reach safety. Roads have a fixed capacity — a physical limit to how many vehicles can pass through per hour. This limit is published in the Highway Capacity Manual, which is the national standard used by every state transportation department in the country. It has been published since 1950 by the Transportation Research Board, which is part of the National Academies of Sciences.

A two-lane road at 30 miles per hour can move about 1,350 vehicles per hour. A four-lane arterial can move about 3,800. A freeway lane can move about 2,250.

But here is the critical point: if the road runs through a fire hazard zone, it will not work at full capacity during the fire that causes the evacuation. There will be smoke reducing visibility. There will be fire trucks driving in the opposite direction. There may be downed trees or power lines blocking a lane. The Highway Capacity Manual publishes adjustment factors for exactly these conditions — reduced visibility, lane blockages, incidents. The state of California, through Cal Fire, publishes maps showing which areas will experience severe fire behavior. These are called Fire Hazard Severity Zone designations, and they are made under state law based on fuel, terrain, and weather data.

We combine the two: the national standard for how much road capacity is lost under adverse conditions, applied to the roads that the state has designated as being in severe fire zones. A road through a Very High Fire Hazard Severity Zone might operate at about 35% of its normal capacity during the fire. A road through a High zone might operate at 50%. A road outside any fire zone operates at full capacity.

The system examines every road between the project and safety. The road with the lowest effective capacity is the bottleneck — the weakest link. That is the number that matters, because the entire evacuation can only move as fast as the slowest segment.

This is the only place the fire hazard zone affects the calculation. The fire zone determines how big the door is. It does not change how many people need through it — that is always 90% of the project's households.

For our example: the project's only route out passes through a two-lane canyon road in a Very High fire zone.

```
Normal capacity: 1,350 vehicles per hour
Fire conditions:  × 35%
Effective capacity: 472 vehicles per hour
```

### Step 3: Account for Building Design

A family living in a single-story house walks out the front door and gets in their car in under a minute. A family on the sixth floor of an apartment building has to walk down six flights of stairs (elevators are shut down in emergencies), navigate through a corridor, enter a parking garage, and wait in a line of cars to exit through one or two driveways.

This delay is real and it is measurable. The National Fire Protection Association publishes NFPA 101, the Life Safety Code, which provides standard methods for calculating how long it takes to empty a building based on its height, number of stairwells, and exit configuration. For buildings above four stories, the system adds a time penalty: about 1.5 minutes per story, up to a maximum of 12 minutes.

For our 45-home project, which is three stories: no penalty. The homes are low-rise.

But for a seven-story, 200-unit apartment building: 7 floors × 1.5 minutes = 10.5 minutes before residents even reach their cars. That time gets added to the road clearance time.

### Step 4: Divide

Divide the project's vehicles by the bottleneck capacity. Convert to minutes. Add any building egress penalty.

For our 45-home canyon road example:

```
101 vehicles ÷ 472 vehicles per hour = 0.214 hours
0.214 hours × 60 = 12.8 minutes
Building egress penalty: 0 minutes (low-rise)
Total: 12.8 minutes
```

**This project adds 12.8 minutes to the time it takes everyone on that road to reach safety.**

------

## How the Decision Is Made

Return to the nightclub. The fire marshal does not set the same occupancy limit for every room. A room with four wide exits gets a higher number than a room with one narrow door. The limit is proportional to the exits.

The same logic applies here. The threshold — how many minutes any single project may add — is derived from one question: **how long do people have to get out?**

After the 2018 Camp Fire killed 85 people in Paradise, California, the National Institute of Standards and Technology spent years reconstructing a minute-by-minute timeline of the disaster. They documented that in the highest-hazard fire zones, residents had approximately 45 minutes from the first sign of danger to the arrival of the fire front. In lower-hazard zones, the window is longer — roughly 90 minutes in High zones and 120 minutes in Moderate or non-fire zones.

The city's standard is that no single project may consume more than 5% of this window. Five percent means a road can absorb approximately 20 projects of similar size before new development alone would fill the entire escape timeline. It is a permissive standard — one that allows substantial new development — while ensuring no single project takes a disproportionate share of the time people need to escape.

The thresholds are not chosen — they are calculated:

| Zone                  | Escape Window | × 5% | = Threshold    |
| --------------------- | ------------- | ---- | -------------- |
| Very High Fire Hazard | 45 minutes    | × 5% | = 2.25 minutes |
| High Fire Hazard      | 90 minutes    | × 5% | = 4.5 minutes  |
| Moderate Fire Hazard  | 120 minutes   | × 5% | = 6.0 minutes  |
| No fire designation   | 120 minutes   | × 5% | = 6.0 minutes  |

The escape windows come from the most detailed wildfire investigation ever conducted by any federal agency. The 5% share is the single policy value the city adopts. The thresholds are arithmetic — not judgment.

If the project's time contribution exceeds the threshold for its zone, the project requires additional review. If it does not, the project is approved with standard safety conditions.

Our canyon road project adds 12.8 minutes in a Very High zone with a 2.25-minute threshold. It exceeds the threshold by 10.55 minutes. Additional review is required.

A different project — 15 homes on a four-lane road outside any fire zone — adds 0.5 minutes against a 6-minute threshold. It passes easily. Approved.

------

## What About Areas Where the Roads Are Already Overcrowded?

This is a natural question, and the answer reveals why the standard is designed the way it is.

Return to the nightclub. Suppose the room is already over its occupancy limit — there are 400 people in a room rated for 300. A group of 50 more wants to enter. The fire marshal does not say: "Well, the room is already over capacity, so 50 more won't make a difference — let them in." The fire marshal says: "Can these 50 people get through the exits fast enough in an emergency?" The answer is about the 50 people and the exits. It is the same answer regardless of whether the room has 200 people or 400.

The standard works the same way. It measures the project's vehicles against the road's physical capacity. That calculation produces the same number whether the road is underused or gridlocked. Adding 101 vehicles to a 472-vehicle-per-hour road consumes 12.8 minutes of that road's throughput — period. The existing population is not in the formula because it does not change the project's impact on the bottleneck.

This means the standard does not prohibit building in areas that are already crowded. It limits the size of what any single project can add, proportional to the road that serves it. A 7-unit project on that same canyon road produces about 2.0 minutes — under the threshold. Approved. The developer can build. But no single project gets to consume more than 2.25 minutes — which is 5% of the 45-minute escape window that NIST documented.

This also means a developer cannot argue: "The road was already failing, so my impact does not matter." The standard does not ask who caused the existing problem. It asks whether the project's own contribution fits through the exit. The fire does not care whether the 400th car belongs to someone who moved in twenty years ago or to a new resident from this project. Every car in the queue faces the same bottleneck.

------

## What the Developer Can Do

The standard does not say "no." It says "your project puts more people behind this exit than the exit can handle in the time available — and here is what you can change to fix it."

When a nightclub exceeds occupancy, the owner has options: add an exit, widen the doors, or reduce the number of people inside. The developer has the same options, and they are all within the developer's control:

**Build fewer units.** Fewer homes means fewer cars. Our 45-unit project could be reduced to about 7 units to bring the time contribution below 2.25 minutes on that canyon road.

**Provide a second way out.** If the project connects to a second road that reaches a different exit, the vehicles split between two routes instead of all funneling through one bottleneck. The binding constraint changes.

**Widen the bottleneck.** The developer can fund improvements to the constraining road segment — adding a lane, widening shoulders, removing obstructions — which increases its capacity and reduces the time calculation.

**Redesign the building.** For tall buildings where the egress penalty is the problem, the developer can add stairwells, widen stairs, or provide multiple garage exits on different streets. A seven-story building with one stairwell and one garage exit is slow to empty. The same building with three stairwells and two garage exits on different streets is much faster. The fire code (NFPA 101) provides the math. The developer's architect controls the result.

The standard identifies a specific, measurable constraint and tells the developer exactly what number they need to hit. It enables solutions. It does not impose a blanket prohibition.

The most important option is the road improvement. The standard identifies the exact bottleneck segment — a specific stretch of road with a specific capacity. The developer can fund the improvement that fixes it: adding a lane, widening shoulders, improving an intersection. The math tells the developer exactly how much additional capacity is needed:

```
Our project needs the bottleneck to handle 101 vehicles in 2.25 minutes.
That requires: (101 ÷ 2.25) × 60 = 2,693 vehicles per hour.
The road currently handles 472 vehicles per hour.
The gap is 2,221 vehicles per hour.
```

The developer pays for the road improvement. The project is approved. And every existing household on that road is now safer than they were before the developer arrived, because the road is wider. The next fire meets a road that can actually handle the evacuation.

This is how building codes have always worked. You want to build a high-rise, you install sprinklers. You want to build homes on a constrained evacuation road, you fix the road. The cost of safe development includes the infrastructure that makes it safe.

------

## Where Every Number Comes From

No number in this system is invented by the city. Every input traces to a published source that any engineer can look up and verify:

| Input                                           | Source                                                       | Who Published It                                             |
| ----------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Road capacity (vehicles per hour per lane)      | Highway Capacity Manual, 7th Edition (2022)                  | Transportation Research Board, National Academies of Sciences |
| Capacity reduction from smoke and lane blockage | HCM Exhibits 10-15 and 10-17                                 | Same                                                         |
| Fire hazard zone designations                   | FHSZ maps under Gov. Code §51175                             | Cal Fire (State of California)                               |
| Homes and vehicles per household                | American Community Survey, Tables B25001 and B25044          | U.S. Census Bureau                                           |
| Evacuation mobilization rate (90%)              | NFPA 101 Life Safety Code design basis (100% occupant evacuation, adjusted for ~10% zero-vehicle households per Census B25044) | National Fire Protection Association                         |
| Escape windows by hazard zone                   | Camp Fire minute-by-minute timeline reconstruction           | NIST Technical Note 2135 (2021)                              |
| Building egress time                            | NFPA 101 (Life Safety Code), International Building Code     | National Fire Protection Association; International Code Council |
| Maximum project share (5%)                      | Adopted by city resolution as the standard engineering significance threshold | City Council                                                 |

If a developer hires their own engineer to run the same calculation with the same inputs, they will get the same answer. That is what makes the standard objective.

------

## Why This Is a Safety Question, Not a Traffic Question

Traffic studies ask: will this project make the evening commute worse? That is a quality-of-life question about convenience and delay.

This standard asks a different question: if there is a wildfire, earthquake, or flood, can people get out alive?

No one would call a fire marshal's occupancy limit a "traffic standard" because it affects how many people move through a corridor. It is a life safety standard. The fact that it involves counting people and measuring exits does not make it a traffic question. The same is true here. The fact that the standard involves counting vehicles and measuring road capacity does not make it a traffic question. It is a question about whether people can escape a hazard that will kill them if they cannot.

The answer depends on time. The fire is moving. The earthquake aftershock may trigger a landslide or a gas main rupture. The floodwater is rising. The question is not whether the road is pleasant to drive on. The question is whether everyone can pass through the bottleneck before the hazard arrives.

The California Legislature recognized this distinction when it passed AB 747 in 2019. That law requires cities to analyze evacuation route capacity in their Safety Element — the part of the General Plan that deals with protecting people from natural hazards. The Legislature did not put this requirement in the Circulation Element, which deals with traffic. It put it in the Safety Element, because evacuation is a life safety question.

This standard implements what the Legislature directed cities to do.

------

## A Real-World Example of Why This Matters

On the morning of November 8, 2018, a wildfire ignited in Butte County, California. Within two hours, it reached the town of Paradise — a community of 26,000 people served by a handful of two-lane roads through forested terrain.

The roads could not handle the demand. Over 20,000 people attempted to leave at the same time. Traffic stopped. People abandoned their cars and ran. The fire burned over gridlocked vehicles on the evacuation routes. Eighty-five people died. It was the deadliest wildfire in California's history.

After the fire, researchers documented that the roads out of Paradise could evacuate only about a quarter of the population within two hours. The town had known this. In 2015, it had converted one of its main roads to one-way outbound during emergencies to double capacity. It was not enough.

The question this standard answers is the same question Paradise faced: can the roads handle the people? If a city approves more homes on a road that is already at or near its evacuation capacity, and a fire comes, the additional minutes of delay are not an abstraction. They are the difference between the 400th car getting through the bottleneck and not getting through.

This standard measures that difference. In minutes. From public data. Using national standards. So that cities do not have to learn the lesson of Paradise by repeating it.

------

## Summary

The standard works in four steps:

1. **Count the cars** the project creates (Census data × 90% mobilization rate, consistent with NFPA 101's design basis for full building evacuation).
2. **Find the bottleneck** — the weakest road on the way out, adjusted for fire conditions using the state's own hazard maps and the national capacity manual.
3. **Add building egress time** for tall buildings where residents cannot reach their cars quickly (national fire code).
4. **Divide** to get minutes. Compare to the threshold — which is 5% of the escape window documented by NIST for the project's hazard zone.

One number. One comparison. Every input is public. Every calculation is arithmetic. The developer can see the result before filing an application, and the developer can change their design to meet the standard. If the project exceeds the threshold, the developer can fix the road and the project is approved.

The principle is one that every building in California already operates under: you cannot put more people behind an exit than the exit can handle in an emergency. A fire marshal enforces that principle for buildings. This standard enforces the same principle for the roads those buildings depend on.

The question for the court is not whether the city chose the right number. The question is whether the city applied a published, objective, verifiable methodology to protect the people who would live in these homes from being trapped in the next fire. The answer is documented in the record, reproducible by any engineer, and grounded in the same principle that has governed building safety for over a century: **measure the exits, count the people, do the math.**

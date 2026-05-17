7. # JOSH — Behavioral Mobilization Rate: Methodology Statement
   
   **Parameter:** `behavioral_mobilization`  
   **Value:** `0.90` (constant; all zones, all project types)  
   **Version:** JOSH v3.4.1 / v4.0  
   **Prepared for:** Worcester Polytechnic Institute methodology review  
   
   ---
   
   ## 1. What the Parameter Represents
   
   `behavioral_mobilization` is the fraction of a project's vehicles assumed to reach the road when a mandatory evacuation order is issued. It appears in the project-vehicle-demand formula:
   
   ```text
   project_vehicles = units × vehicles_per_unit × behavioral_mobilization
                    = units × 1.9 × 0.90
   ```
   
   This factor accounts for:
   
   - Residents not home when the order is issued (at work, school, running errands)
   - Households that own two vehicles but depart together in one vehicle
   - The fraction that receives the order but does not immediately comply
   
   **What this factor does not represent:** zero-vehicle households. Zero-vehicle households are already embedded in `vehicles_per_unit = 1.9`, which is the all-household weighted average from U.S. Census ACS Table B25044, including households with zero vehicles. Applying a zero-vehicle adjustment here would double-count that population.
   
   The factor is held constant across Fire Hazard Severity Zones absent documented local evidence supporting a different value. FHSZ classification affects hazard exposure and may affect route-capacity or operational assumptions, but it does not by itself establish a different project vehicle-release factor. The demand a project places on the network — the vehicles that must pass through the bottleneck — should not mechanically change solely because the project falls on one side or the other of an FHSZ boundary.
   
   ---
   
   ## 2. How the Value Is Used
   
   The formula is load divided by capacity, expressed in minutes:
   
   ```text
   ΔT = (project_vehicles / bottleneck_effective_capacity_vph) × 60 + egress_penalty
   ```
   
   `behavioral_mobilization = 0.90` is a **conservative mandatory-order design release factor**, not an empirical prediction of average observed behavior. It is intentionally set above the GPS-observed evacuation rates documented for the 2019 Kincade Fire, approximately 46–48%, in order to size evacuation capacity for a credible high-demand scenario rather than for historical average observed behavior.
   
   The conservative direction for this parameter is **higher**: a higher mobilization rate produces more project vehicles, a larger ΔT, and a more protective standard.
   
   ---
   
   ## 3. Source Basis
   
   The empirical basis for this parameter is Roberson et al. (2012), Zhao et al. (2022), and Wu et al. (2022). The California evacuation-planning guidance supports the use of documented planning assumptions in clearance-time analysis. NFPA 101 is cited only as design-philosophy context, not as numerical support for the `0.90` value.
   
   ---
   
   ### 3.1 Roberson et al. (2012) — Primary California WUI Source for High Stated Compliance Under Mandatory Orders
   
   **Full citation:**  
   Roberson, B. S., Peterson, D., and Parsons, R. W. (2012). “Attitudes on wildfire evacuation: Exploring the intended evacuation behavior of residents living in two Southern California communities.” *Journal of Emergency Management*, 10(5), 335–347. https://doi.org/10.5055/jem.2012.0111
   
   **What this source supports:**  
   Roberson et al. surveyed more than 200 residents in the Carpinteria-Summerland Fire District in Santa Barbara County, California, an area within a designated High Fire Hazard Area. Under a mandatory evacuation order scenario, **82.6%** of respondents stated they would “for sure” or “likely” evacuate. **10.3%** stated they would be unlikely to evacuate or would stay.
   
   **Characterization:**  
   California WUI stated intent under mandatory evacuation orders. The study supports a high stated willingness to evacuate under mandatory orders, while also documenting a meaningful minority of affirmative stated noncompliance.
   
   **Caveats:**
   
   - Measures stated intent, not GPS-observed behavior
   - Localized to two Southern California communities; not a statewide sample
   - Subject to social-desirability bias, because respondents may overstate compliance intent
   - Mail survey response patterns may reflect self-selection, because more safety-aware residents may be more likely to respond
   - Does not directly measure vehicle departures, vehicle occupancy, or road-network loading
   
   **Relationship to the `0.90` value:**  
   Roberson establishes that, in a California High Fire Hazard Area community, 82.6% of respondents stated they would likely or certainly evacuate under a mandatory evacuation order, while 10.3% stated they were unlikely to evacuate or would stay. JOSH rounds the complement of affirmative stated noncompliance, approximately 89.7%, to `0.90` as a conservative mandatory-order design release factor.
   
   This should not be characterized as observed compliance. It is a conservative design interpretation of stated-intent data under a mandatory-order scenario.
   
   ---
   
   ### 3.2 Zhao et al. (2022) and Wu et al. (2022) — GPS-Observed Behavior in the 2019 Kincade Fire
   
   **Full citations:**  
   
   Zhao, X., Xu, Y., Lovreglio, R., Kuligowski, E., Nilsson, D., Cova, T., Wu, A., and Yan, X. (2022). “Estimating wildfire evacuation decision and departure timing using large-scale GPS data.” *Transportation Research Part D: Transport and Environment*, 107, 103277. https://doi.org/10.1016/j.trd.2022.103277
   
   Wu, A., Yan, X., Kuligowski, E., Lovreglio, R., Nilsson, D., Cova, T., Xu, Y., and Zhao, X. (2022). “Wildfire evacuation decision modeling using GPS data.” *International Journal of Disaster Risk Reduction*, 83, 103424. https://doi.org/10.1016/j.ijdrr.2022.103424
   
   **What these sources support:**  
   Both papers analyze large-scale GPS data from the 2019 Kincade Fire in Sonoma County, California. Zhao et al. report approximately **46% overall evacuation compliance** inside warning and order zones. Wu et al. report a **mean block-group evacuation rate of 47.6%**, based on more than 44 million GPS records from over 5,000 devices.
   
   **Characterization:**  
   GPS-observed actual departure behavior in a specific California WUI fire. The observed evacuation rates are substantially below the `0.90` JOSH design value.
   
   **Caveats:**
   
   - Kincade-specific; local fire behavior, warning/order timing, geography, road network, and public perception affect rates
   - GPS device samples may not be representative of all demographic groups
   - Results depend on device detection, home-location inference, evacuation-zone assignment, and trip-classification methodology
   - Includes both warning zones and mandatory order zones; rates in mandatory-only zones may differ
   - Does not establish a statewide California WUI compliance constant
   
   **Relationship to the `0.90` value:**  
   These GPS studies do not support `0.90` as an observed behavioral rate. They support `0.90` as a conservative design assumption: using a figure roughly twice the observed Kincade Fire average ensures the road is sized for a high-demand scenario, not for historical average behavior.
   
   A standard built on the observed `0.47` would pass roads that historically handled that level of demand, leaving little or no margin for a higher-mobilization mandatory-order event that creates the relevant life-safety risk.
   
   ---
   
   ### 3.3 California Evacuation Planning Technical Advisory — Methodological Support for Documented Planning Assumptions
   
   **Full citation:**  
   California Governor's Office of Planning and Research / Governor's Office of Land Use and Climate Innovation. *Draft Evacuation Planning Technical Advisory.* State of California, 2024.
   
   **What this source supports:**  
   The California Evacuation Planning Technical Advisory supports the use of literature, past events, and informed assumptions when accounting for population evacuation behavior in evacuation clearance-time planning. It identifies factors such as evacuation compliance, vehicle ownership, transportation mode, roadway capacity, and bottlenecks as relevant to clearance-time estimates.
   
   **Characterization:**  
   State-level methodological support for using documented planning assumptions in California evacuation capacity analysis.
   
   **Relationship to the `0.90` value:**  
   This source does not specify a compliance rate. It establishes that documented, reasoned planning assumptions are legitimate inputs to clearance-time analysis. JOSH applies that permission through a conservative life-safety design assumption, documented through California WUI stated-intent literature and contrasted against observed GPS behavior.
   
   ---
   
   ### 3.4 NFPA 101 Life Safety Code — Design-Philosophy Context Only
   
   **Full citation:**  
   National Fire Protection Association. *NFPA 101: Life Safety Code.* Current edition.
   
   **What this source supports:**  
   NFPA 101 requires building egress systems to be designed around calculated occupant load rather than ordinary average occupancy. Building life-safety design does not size exit capacity based on the average fraction of occupants who happened to evacuate in prior incidents; it sizes for a design load that could plausibly occur.
   
   **Characterization:**  
   Conceptual support for the design-standard approach: life-safety systems are conventionally sized for credible high-demand scenarios rather than observed average behavior.
   
   **Relationship to the `0.90` value:**  
   NFPA 101 does not specify `0.90` or any wildfire evacuation compliance rate. It is cited only as a design-philosophy analogy. If applied strictly, the building-egress analogy could point toward `1.00` rather than `0.90`.
   
   The `0.90` value specifically derives from the California WUI stated-intent literature, particularly Roberson et al. (2012), and is contrasted against GPS-observed behavior in Zhao et al. (2022) and Wu et al. (2022). NFPA 101 is not cited as numerical support for the `0.90` figure.
   
   ---
   
   ## 4. Sources Reviewed and Not Used for the Mobilization Rate
   
   The following sources were reviewed during methodology development and are **not** cited as support for the `0.90` value.
   
   ### FHWA Emergency Transportation Operations
   
   FHWA Emergency Transportation Operations publications were reviewed for a specific wildfire mandatory-evacuation compliance figure in the 85–95% range. No such figure was found in the available FHWA ETO document set. FHWA's ETO materials are useful operational guidance, but they do not appear to establish a California wildfire mandatory-order vehicle-compliance rate.
   
   This citation has been removed from the JOSH behavioral-mobilization methodology.
   
   ### NIST Technical Note 2252 — Camp Fire NETTRA
   
   **Full citation:**  
   Maranghides, A., Link, E., Hawks, S., Brown, C., Walton, W. D., Mell, W., Milac, T., Torres, A., and Butler, K. M. (2023). *A Case Study of the Camp Fire: Notification, Evacuation, Traffic, and Temporary Refuge Areas (NETTRA).* NIST Technical Note 2252. https://doi.org/10.6028/NIST.TN.2252
   
   NIST TN 2252 is a forensic case study of the 2018 Camp Fire documenting notification, evacuation routes, traffic conditions, temporary refuge areas, rescues, and fatalities. It does not report a behavioral mobilization rate or evacuation compliance percentage.
   
   The Camp Fire resulted in 85 deaths, significant route closures, temporary refuge-area use, and widespread evacuation failure modes. It is not evidence for high mobilization compliance.
   
   NIST TN 2252 remains relevant to the JOSH methodology for WUI evacuation context and for safe-egress-window analysis, where fire-spread timeline documentation is needed. It is not cited as support for `behavioral_mobilization = 0.90`.
   
   ### Note on NIST TN 2262
   
   The original NIST Technical Note 2262, *WUI Fire Evacuation and Sheltering Considerations (ESCAPE)*, August 2023, has been officially withdrawn and superseded by NIST TN 2262r1, March 2025. JOSH references should cite the current revision.
   
   **Current citation:**  
   Maranghides, A., et al. (2025). *WUI Fire Evacuation and Sheltering Considerations (ESCAPE).* NIST Technical Note 2262r1. National Institute of Standards and Technology.
   
   ---
   
   ## 5. Summary: Why `0.90` Is the Appropriate Design Value
   
   | Source                                            | What it establishes                                          |
   | ------------------------------------------------- | ------------------------------------------------------------ |
   | Roberson et al. (2012)                            | California WUI stated intent under mandatory orders: 82.6% likely/certain evacuation; 10.3% affirmative stated noncompliance; complement of affirmative noncompliance ≈ 89.7% |
   | Zhao et al. (2022) / Wu et al. (2022)             | GPS-observed Kincade Fire evacuation behavior: approximately 46–48%; establishes that `0.90` is conservative relative to observed behavior |
   | California Evacuation Planning Technical Advisory | Supports the use of documented literature, past events, and informed assumptions in evacuation clearance-time planning |
   | NFPA 101                                          | Provides design-philosophy context only: life-safety systems are sized for credible design loads rather than observed averages |
   
   The `0.90` value is best understood as a **conservative mandatory-order design vehicle release factor**. It is anchored in California WUI stated-intent literature, particularly the approximately 89.7% complement of affirmative noncompliance reported by Roberson et al. (2012), and is intentionally higher than GPS-observed evacuation behavior in the 2019 Kincade Fire.
   
   A lower value, such as the GPS-observed `0.47`, would reduce calculated project-vehicle demand, lower ΔT, and push more projects toward ministerial approval. The conservative direction is higher, not lower. A city wishing to apply an even more protective standard could set `behavioral_mobilization = 1.00`.
   
   ---
   
   ## 6. Sensitivity
   
   The following sensitivity table illustrates the effect of alternative mobilization assumptions on a 45-unit residential project using `vehicles_per_unit = 1.9`.
   
   ```text
   base project vehicles before mobilization = 45 × 1.9 = 85.5
   ```
   
   | Mobilization rate | Basis                                                        | Effect on a 45-unit project |
   | ----------------: | ------------------------------------------------------------ | --------------------------: |
   |            `0.47` | GPS-observed mean, Zhao/Wu 2022, Kincade Fire                |     `project_vehicles = 40` |
   |            `0.55` | GPS-observed upper comparison value from later Kincade Fire analysis |     `project_vehicles = 47` |
   |           `0.826` | Roberson 2012 — stated likely/certain evacuation rate        |     `project_vehicles = 71` |
   |        **`0.90`** | **JOSH default — conservative mandatory-order design release factor** | **`project_vehicles = 77`** |
   |            `1.00` | Maximum conservatism; full vehicle release                   |     `project_vehicles = 86` |
   
   Using `0.90` instead of the observed GPS average of approximately `0.47` produces about **93% more calculated project-vehicle demand** than the GPS-observed Kincade Fire mean. This is the intended design margin.
   
   ---
   
   ## 7. Override Path
   
   A city may override `behavioral_mobilization` with documented local evidence, such as:
   
   - A formally adopted local evacuation plan with documented compliance-rate data
   - A local fire-history study with observed departure rates for the specific community
   - A licensed transportation engineer study, PE-stamped
   - A locally adopted evacuation-capacity methodology supported by substantial evidence
   
   Override values below `0.75` are treated as non-default policy exceptions requiring substantial documentation. This `0.75` threshold is an internal JOSH review-control threshold, not a literature-derived empirical boundary.
   
   The minimum empirically supported comparison value is the GPS-observed California WUI range from the Kincade Fire literature, approximately `0.47–0.55`. A city using values in that range should document that it is designing for observed average behavior rather than for a conservative upper-bound mandatory-order scenario.
   
   ---
   
   ## 8. Recommended Characterization for Legal and Academic Review
   
   For purposes of methodology review, the parameter should be characterized as follows:
   
   > `behavioral_mobilization = 0.90` is a conservative mandatory-order design release factor. It is not an observed average compliance rate. The value is anchored in California WUI stated-intent data, where Roberson et al. (2012) found 82.6% likely/certain evacuation under mandatory orders and 10.3% affirmative stated noncompliance. JOSH rounds the complement of affirmative stated noncompliance, approximately 89.7%, to `0.90`. GPS-based studies of the 2019 Kincade Fire found substantially lower observed evacuation rates, approximately 46–48%, confirming that `0.90` is conservative relative to observed behavior. The value is used to size road-network evacuation capacity for a credible high-demand life-safety scenario, not to predict average behavior.
   
   ---
   
   ## References
   
   1. Roberson, B. S., Peterson, D., and Parsons, R. W. (2012). “Attitudes on wildfire evacuation: Exploring the intended evacuation behavior of residents living in two Southern California communities.” *Journal of Emergency Management*, 10(5), 335–347. https://doi.org/10.5055/jem.2012.0111
   
   2. Zhao, X., Xu, Y., Lovreglio, R., Kuligowski, E., Nilsson, D., Cova, T., Wu, A., and Yan, X. (2022). “Estimating wildfire evacuation decision and departure timing using large-scale GPS data.” *Transportation Research Part D: Transport and Environment*, 107, 103277. https://doi.org/10.1016/j.trd.2022.103277
   
   3. Wu, A., Yan, X., Kuligowski, E., Lovreglio, R., Nilsson, D., Cova, T., Xu, Y., and Zhao, X. (2022). “Wildfire evacuation decision modeling using GPS data.” *International Journal of Disaster Risk Reduction*, 83, 103424. https://doi.org/10.1016/j.ijdrr.2022.103424
   
   4. California Governor's Office of Planning and Research / Governor's Office of Land Use and Climate Innovation. *Draft Evacuation Planning Technical Advisory.* State of California, 2024.
   
   5. National Fire Protection Association. *NFPA 101: Life Safety Code.* Current edition.
   
   6. Maranghides, A., Link, E., Hawks, S., Brown, C., Walton, W. D., Mell, W., Milac, T., Torres, A., and Butler, K. M. (2023). *A Case Study of the Camp Fire: Notification, Evacuation, Traffic, and Temporary Refuge Areas (NETTRA).* NIST Technical Note 2252. https://doi.org/10.6028/NIST.TN.2252  
      Cited for WUI evacuation context and safe-egress-window derivation only, not for mobilization rate.
   
   7. Maranghides, A., et al. (2025). *WUI Fire Evacuation and Sheltering Considerations (ESCAPE).* NIST Technical Note 2262r1. National Institute of Standards and Technology.  
      Cited as the current revision superseding the withdrawn August 2023 NIST TN 2262.

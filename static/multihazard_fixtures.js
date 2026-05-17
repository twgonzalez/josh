// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH Multi-Hazard Mock Fixtures — Stage 0
 *
 * Browser:  window.JOSH_MOCK_MULTIHAZARD = { [projectId]: ProjectFixture }
 * Node CLI: require('./static/multihazard_fixtures.js')
 *
 * Drives the multi-hazard right-sidebar UI under the multihazard:true flag
 * before any Python adapter code lands (see docs/plan-multihazard-stage-0.md
 * §4.2, §4.3). Each ProjectFixture has the discriminated-union HazardResult
 * shape locked at decision #11 (status doc).
 *
 * Step 11 [AUTO]: wildfire-only entries for the 4 real Berkeley seeded
 *   projects. Values match production pipeline output (extracted from
 *   tests/snapshots/baseline/josh_data.json projects[].result).
 * Step 13 [REVIEW]: extends each entry with a FloodResult (all passing —
 *   wildfire remains controlling for all 4 real projects).
 * Step 16 [PAUSE]: adds hand-crafted cedar_street_infill flood-controlling
 *   variant (current cedar_street_infill becomes wildfire-controlling-only
 *   per real production data).
 * Step 17 [PAUSE]: adds hand-crafted marina_pointe with tsunami dispositive.
 */

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.JOSH_MOCK_MULTIHAZARD = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // Stage 0 Step 19 helper. Generates a stub polyline from the project's
  // lat/lng going eastward — visually distinct from the production Folium
  // wildfire route (which heads to the nearest exit, typically downhill/west).
  // Real per-hazard routing lands in Stage 3 (FloodAdapter) when actual
  // network-cutting routes are computed.
  function _stubFloodRoute(lat, lng) {
    return [
      [lat,         lng],
      [lat + 0.003, lng + 0.008],
      [lat - 0.001, lng + 0.015],
      [lat - 0.002, lng + 0.022]
    ];
  }

  // Per-project fixtures keyed by project.id (the same id JOSH_DATA.projects uses).
  // Schema follows plan-multihazard-stage-0.md §4.2.
  // Production values from JOSH_DATA.projects[].result on 2026-05-17 baseline.
  return {
    // VHFHSZ project — wildfire DISCRETIONARY (delta_t 26.06 > 2.25 threshold)
    hills_gateway: {
      controlling_hazard: 'wildfire',
      tier: 'DISCRETIONARY',
      hazard_results: [
        {
          type:              'wildfire',
          controls:          true,
          flagged:           true,
          zone:              'vhfhsz',
          zone_label:        'Very High FHSZ',
          fhsz_haz_class:    3,
          degradation:       0.35,
          egress_window_min: 45,
          threshold:         2.25,
          delta_t:           26.06,
          bottleneck:        {
            name:        'Marin Avenue at Shattuck Avenue / The Circle',
            eff_cap_vph: 315,
            vehicles:    137
          },
          // route_coords stubbed in Step 19 [AUTO]; null = scenario radio
          // falls back to controlling-hazard AntPath (the production Folium
          // route still renders via per-project FeatureGroup).
          route_coords: null
        },
        {
          // Project is inland in the Berkeley hills; nowhere near the bayfront
          // SFHA. Flood is informational only, easily passes.
          type:              'flood',
          controls:          false,
          flagged:           false,
          zone:              'x',
          zone_label:        'X (outside SFHA)',
          bfe_ft:            null,
          flooded_exit_nodes_dropped: 0,
          degradation:       1.00,
          egress_window_min: 180,
          threshold:         9.00,
          delta_t:           1.0,
          bottleneck:        {
            name:        'Marin Avenue at Shattuck Avenue / The Circle',
            eff_cap_vph: 900,
            vehicles:    137
          },
          route_coords: _stubFloodRoute(37.8914, -122.2494)
        }
      ]
    },

    // Moderate FHSZ project — wildfire passes (4.59 < 6.0 threshold)
    downtown_mid_rise: {
      controlling_hazard: 'wildfire',
      tier: 'MINISTERIAL_WITH_STANDARD_CONDITIONS',
      hazard_results: [
        {
          type:              'wildfire',
          controls:          true,
          flagged:           false,
          zone:              'non_fhsz',
          zone_label:        'Not in FHSZ',
          fhsz_haz_class:    0,
          degradation:       1.00,
          egress_window_min: 120,
          threshold:         6.00,
          delta_t:           4.59,
          bottleneck:        {
            name:        'Adeline Street at Shattuck Avenue / Ward Street',
            eff_cap_vph: 1900,
            vehicles:    145
          },
          route_coords: null
        },
        {
          type:              'flood',
          controls:          false,
          flagged:           false,
          zone:              'x',
          zone_label:        'X (outside SFHA)',
          bfe_ft:            null,
          flooded_exit_nodes_dropped: 0,
          degradation:       1.00,
          egress_window_min: 180,
          threshold:         9.00,
          delta_t:           2.0,
          bottleneck:        {
            name:        'Adeline Street at Shattuck Avenue / Ward Street',
            eff_cap_vph: 1900,
            vehicles:    145
          },
          route_coords: _stubFloodRoute(37.8695, -122.2685)
        }
      ]
    },

    // Non-FHSZ small project — wildfire passes (2.28 < 6.0 threshold)
    claremont_hills_terrace: {
      controlling_hazard: 'wildfire',
      tier: 'MINISTERIAL_WITH_STANDARD_CONDITIONS',
      hazard_results: [
        {
          type:              'wildfire',
          controls:          true,
          flagged:           false,
          zone:              'non_fhsz',
          zone_label:        'Not in FHSZ',
          fhsz_haz_class:    0,
          degradation:       1.00,
          egress_window_min: 120,
          threshold:         6.00,
          delta_t:           2.28,
          bottleneck:        {
            name:        'Ridge Road at Euclid Avenue / Scenic Avenue',
            eff_cap_vph: 1125,
            vehicles:    43
          },
          route_coords: null
        },
        {
          type:              'flood',
          controls:          false,
          flagged:           false,
          zone:              'x',
          zone_label:        'X (outside SFHA)',
          bfe_ft:            null,
          flooded_exit_nodes_dropped: 0,
          degradation:       1.00,
          egress_window_min: 180,
          threshold:         9.00,
          delta_t:           0.7,
          bottleneck:        {
            name:        'Ridge Road at Euclid Avenue / Scenic Avenue',
            eff_cap_vph: 1125,
            vehicles:    43
          },
          route_coords: _stubFloodRoute(37.876, -122.26)
        }
      ]
    },

    // Hand-crafted mock project — tsunami-dispositive. Stage 0 Step 17.
    // Berkeley Marina sits inside the CGS Tsunami Hazard Area (real-world
    // boundary covers the marina + parts of W. Berkeley shoreline). The
    // dispositive-at-Standard-3 logic from locked decision #2 produces
    // DISCRETIONARY regardless of ΔT; wildfire + flood are informational.
    // Deleted in Stage 6 when TsunamiAdapter takes over.
    marina_pointe: {
      inject: true,
      project: {
        id:      'marina_pointe',
        name:    'Marina Pointe (mock)',
        address: 'Berkeley Marina, University Ave Frontage',
        lat:     37.864,
        lng:     -122.318,
        units:   100,
        stories: 4,
        is_mock: true
      },
      controlling_hazard: 'tsunami',
      tier: 'DISCRETIONARY',
      hazard_results: [
        {
          // Informational only — wildfire ΔT well under threshold (flat
          // bayfront, no FHSZ exposure).
          type:              'wildfire',
          controls:          false,
          flagged:           false,
          zone:              'non_fhsz',
          zone_label:        'Not in FHSZ',
          fhsz_haz_class:    0,
          degradation:       1.00,
          egress_window_min: 120,
          threshold:         6.00,
          delta_t:           3.4,
          bottleneck:        {
            name:        'University Avenue at Frontage Road',
            eff_cap_vph: 1700,
            vehicles:    225
          },
          route_coords: null
        },
        {
          // Informational only — flood ΔT under threshold despite AE
          // location (mock route avoids the worst-flooded segments).
          type:              'flood',
          controls:          false,
          flagged:           false,
          zone:              'ae',
          zone_label:        'AE (1% annual flood)',
          bfe_ft:            10.0,
          flooded_exit_nodes_dropped: 1,
          degradation:       0.20,
          egress_window_min: 180,
          threshold:         9.00,
          delta_t:           6.1,
          bottleneck:        {
            name:        'University Avenue at Frontage Road',
            eff_cap_vph: 340,
            vehicles:    225
          },
          route_coords: _stubFloodRoute(37.864, -122.318)
        },
        {
          // CONTROLLING. Per locked decision #2 (status doc), in-CGS-THA
          // forces DISCRETIONARY at Standard 3; ΔT is not computed against
          // a threshold (the 15-min Cascadia design window × 5% project
          // share yields a 45-second threshold — unusable as gradation).
          // delta_t_informational is shown only for context.
          type:                  'tsunami',
          controls:              true,
          flagged:               true,
          in_cgs_tha:            true,
          eva_type:              'Tsunami Inundation Zone',
          dispositive:           true,
          delta_t_informational: 18.4,
          route_coords:          null
        },
        {
          // Stage 0.5 Phase C — informational, not controlling.
          // Marina Pointe sits in San Pablo Dam's inundation pathway
          // (~45 min arrival). Two upstream dams threaten the area.
          type:              'dam_failure',
          controls:          false,
          flagged:           false,
          zone:              'in_inundation',
          zone_label:        'In inundation polygon',
          dams_affecting:    [
            { name: 'San Pablo Dam', arrival_time_min: 45 },
            { name: 'Briones Reservoir', arrival_time_min: 90 }
          ],
          degradation:       0.40,
          egress_window_min: 45,
          threshold:         2.25,  // 45 min × 0.05
          delta_t:           1.8,
          bottleneck:        {
            // Per design pick: bottleneck cell joins all affecting dam names
            // so the brief Section C row reads coherently.
            name:        'University Avenue at Frontage Road (San Pablo Dam, Briones)',
            eff_cap_vph: 680,
            vehicles:    225
          },
          route_coords: null
        },
        {
          // Stage 0.5 Phase C — informational, not controlling.
          // PG&E I-80 corridor PIR buffer clips the project lot.
          type:              'gas_hazmat',
          controls:          false,
          flagged:           false,
          in_pir:            true,
          // Per design pick: zone_label bakes the buffer radius + product in.
          zone:              'in_pir',
          zone_label:        'In PIR (660 ft) — natural gas',
          pir_ft:            660,
          operator:          'PG&E (mock)',
          product:           'natural_gas',
          degradation:       0.50,
          egress_window_min: 30,
          threshold:         1.50,  // 30 min × 0.05
          delta_t:           1.1,
          bottleneck:        {
            name:        'University Avenue at Frontage Road',
            eff_cap_vph: 850,
            vehicles:    225
          },
          route_coords: null
        },
        {
          // Stage 0.5 Phase C — informational, EILZ exposure (statewide
          // CGS layer covers low-grade slope at the marina edge).
          type:              'landslide',
          controls:          false,
          flagged:           false,
          zone_type:         'eilz',
          zone:              'eilz',
          zone_label:        'CGS EILZ (low-grade slope)',
          burn_year:         null,
          degradation:       0.85,
          egress_window_min: 60,
          threshold:         3.00,  // 60 min × 0.05
          delta_t:           1.6,
          bottleneck:        {
            name:        'University Avenue at Frontage Road',
            eff_cap_vph: 1445,
            vehicles:    225
          },
          route_coords: null
        }
      ]
    },

    // Hand-crafted mock project — flood-controlling. Stage 0 Step 16.
    // Located in the bayfront SFHA polygon emitted by Step 5; allows the
    // UI to render the non-wildfire-controlling branch before any
    // FloodAdapter ships. Deleted in Stage 3 when FloodAdapter takes over.
    //
    // `inject: true` tells _mergeMockFixturesIntoProjects to PUSH the
    // entry's `.project` into JOSH_DATA.projects (rather than merging
    // onto an existing project id). The is_mock sentinel surfaces the
    // detail-card footnote.
    cedar_st_bayfront_mock: {
      inject: true,
      project: {
        id:      'cedar_st_bayfront_mock',
        name:    'Cedar St Bayfront (mock)',
        address: 'Cedar St near I-80, West Berkeley',
        lat:     37.870,
        lng:     -122.310,
        units:   60,
        stories: 3,
        is_mock: true
      },
      controlling_hazard: 'flood',
      tier: 'DISCRETIONARY',
      hazard_results: [
        {
          // Project sits in flat western Berkeley with a multilane arterial —
          // wildfire ΔT is comfortably under threshold.
          type:              'wildfire',
          controls:          false,
          flagged:           false,
          zone:              'non_fhsz',
          zone_label:        'Not in FHSZ',
          fhsz_haz_class:    0,
          degradation:       1.00,
          egress_window_min: 120,
          threshold:         6.00,
          delta_t:           4.26,
          bottleneck:        {
            name:        'University Avenue at San Pablo Avenue',
            eff_cap_vph: 1900,
            vehicles:    135
          },
          route_coords: null
        },
        {
          // Inside the bayfront SFHA polygon (Step 5 mock). AE zone
          // degradation = 0.20 chokes the route; ΔT crashes through threshold.
          type:              'flood',
          controls:          true,
          flagged:           true,
          zone:              'ae',
          zone_label:        'AE (1% annual flood)',
          bfe_ft:            10.0,
          flooded_exit_nodes_dropped: 2,
          degradation:       0.20,
          egress_window_min: 180,
          threshold:         9.00,
          delta_t:           21.3,
          bottleneck:        {
            name:        'Cedar Street at I-80 underpass',
            eff_cap_vph: 380,
            vehicles:    135
          },
          route_coords: _stubFloodRoute(37.870, -122.310)
        },
        {
          // Excluded from analysis. Cedar St I-80 underpass is just outside
          // the CGS Tsunami Hazard Area boundary (which sits closer to the
          // marina). Surfaces in brief Section D (Step 23).
          type:     'tsunami',
          excluded: {
            reason: 'Project location is east of the CGS Tsunami Hazard Area boundary.'
          }
        }
      ]
    },

    // 6-story project — wildfire flagged via egress penalty (delta_t 15.84
    // with 9.0 min penalty for stories>=4 takes it past the 6.0 threshold)
    cedar_street_infill: {
      controlling_hazard: 'wildfire',
      tier: 'DISCRETIONARY',
      hazard_results: [
        {
          type:              'wildfire',
          controls:          true,
          flagged:           true,
          zone:              'non_fhsz',
          zone_label:        'Not in FHSZ',
          fhsz_haz_class:    0,
          degradation:       1.00,
          egress_window_min: 120,
          threshold:         6.00,
          delta_t:           15.84,        // includes +9.0 min egress penalty
          bottleneck:        {
            name:        'North Street at Jaynes Street',
            eff_cap_vph: 1125,
            vehicles:    128
          },
          route_coords: null
        },
        {
          // Same egress penalty applies in flood scenario (stories≥4), so
          // delta_t bumped a bit but still well under the 9.0 threshold.
          type:              'flood',
          controls:          false,
          flagged:           false,
          zone:              'x',
          zone_label:        'X (outside SFHA)',
          bfe_ft:            null,
          flooded_exit_nodes_dropped: 0,
          degradation:       1.00,
          egress_window_min: 180,
          threshold:         9.00,
          delta_t:           3.5,
          bottleneck:        {
            name:        'North Street at Jaynes Street',
            eff_cap_vph: 1125,
            vehicles:    128
          },
          route_coords: _stubFloodRoute(37.879, -122.278)
        }
      ]
    }
  };
}));

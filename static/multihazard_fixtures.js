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
          route_coords: null
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
          route_coords: null
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
          route_coords: null
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
          route_coords: null
        }
      ]
    }
  };
}));

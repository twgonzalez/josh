# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""EvacuationPath data model — per-path bottleneck tracking for ΔT computation."""
from dataclasses import dataclass, field


@dataclass
class EvacuationPath:
    """
    Represents one shortest-path route from an origin block group to a city exit.

    Produced by Agent 2 (_identify_evacuation_routes) during Dijkstra traversal.
    The bottleneck is the segment with minimum effective_capacity_vph along the path —
    this is the binding constraint for ΔT computation.

    All fields are set algorithmically. No subjective values allowed.
    """

    # Path identity
    path_id: str                    # "{origin_bg}_{exit_node_id}"
    origin_block_group: str         # Census GEOID of origin block group
    exit_segment_osmid: str         # osmid of road segment at city boundary

    # Bottleneck — the segment with min(effective_capacity_vph) on this path
    bottleneck_osmid: str           # osmid of the bottleneck segment
    bottleneck_name: str            # road name at bottleneck (for display)
    bottleneck_fhsz_zone: str       # FHSZ zone at bottleneck ("vhfhsz"|"high_fhsz"|"moderate_fhsz"|"non_fhsz")
    bottleneck_road_type: str       # "freeway"|"multilane"|"two_lane"
    bottleneck_hcm_capacity_vph: float   # raw HCM capacity (before degradation)
    bottleneck_hazard_degradation: float  # degradation factor applied at bottleneck
    bottleneck_effective_capacity_vph: float  # hcm_capacity × hazard_degradation

    # HCM audit fields — enable reviewer to verify HCM table lookup independently
    bottleneck_lane_count:  int = 0  # lanes at bottleneck (input to HCM capacity formula)
    bottleneck_speed_limit: int = 0  # posted speed mph at bottleneck (selects two-lane HCM row)
    bottleneck_haz_class:   int = 0  # raw CAL FIRE HAZ_CLASS integer (0=none,1=mod,2=high,3=vhfhsz)

    # Catchment demand at bottleneck (informational)
    catchment_units: float = 0.0    # housing units whose path passes through bottleneck
    baseline_demand_vph: float = 0.0  # catchment_units × vpu × 0.57 (informational)

    # Full path segment sequence — used for map visualization of the evacuation corridor
    path_osmids: list = field(default_factory=list)  # ordered osmids from origin to exit

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage and audit trail."""
        return {
            "path_id":                        self.path_id,
            "origin_block_group":             self.origin_block_group,
            "exit_segment_osmid":             self.exit_segment_osmid,
            "bottleneck_osmid":               self.bottleneck_osmid,
            "bottleneck_name":                self.bottleneck_name,
            "bottleneck_fhsz_zone":           self.bottleneck_fhsz_zone,
            "bottleneck_road_type":           self.bottleneck_road_type,
            "bottleneck_lane_count":          self.bottleneck_lane_count,
            "bottleneck_speed_limit":         self.bottleneck_speed_limit,
            "bottleneck_haz_class":           self.bottleneck_haz_class,
            "bottleneck_hcm_capacity_vph":    round(self.bottleneck_hcm_capacity_vph, 0),
            "bottleneck_hazard_degradation":  self.bottleneck_hazard_degradation,
            "bottleneck_effective_capacity_vph": round(self.bottleneck_effective_capacity_vph, 0),
            "catchment_units":                round(self.catchment_units, 0),
            "baseline_demand_vph":            round(self.baseline_demand_vph, 1),
            "path_osmids":                    self.path_osmids,
        }

# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""Road network data model."""
from dataclasses import dataclass, field
from typing import Optional
from shapely.geometry import LineString


@dataclass
class RoadSegment:
    """
    Represents a single road segment with capacity analysis attributes.

    All fields are set algorithmically — no subjective values allowed.
    Data quality is tracked to flag estimated vs. measured values in outputs.
    """

    # Identity
    segment_id: str
    name: str
    osmid: Optional[str] = None
    geometry: Optional[LineString] = None

    # Road characteristics (source data)
    highway_tag: str = "unclassified"   # OSM highway tag
    road_type: str = "two_lane"         # freeway | multilane | two_lane
    lane_count: int = 1
    speed_limit: int = 25               # mph
    length_meters: float = 0.0

    # Data quality flags
    lane_count_estimated: bool = False  # True if lane_count is estimated, not measured
    speed_estimated: bool = False       # True if speed_limit is estimated, not measured
    aadt_estimated: bool = False        # True if AADT is estimated, not measured

    # HCM 2022 Capacity (Agent 2 — Step 1)
    capacity_vph: float = 0.0           # Raw HCM capacity (before hazard degradation)

    # Hazard-aware capacity degradation (Agent 2 — Step 2)
    fhsz_zone: str = "non_fhsz"        # FHSZ zone for this segment's location
    hazard_degradation: float = 1.0     # Degradation factor from config
    effective_capacity_vph: float = 0.0  # capacity_vph × hazard_degradation

    # Demand and v/c (Agent 2 — informational)
    aadt: Optional[float] = None        # Annual Average Daily Traffic (if available)
    baseline_demand_vph: float = 0.0   # Catchment-based demand (for display)
    vc_ratio: float = 0.0              # baseline_demand_vph / capacity_vph (informational)
    los: str = ""                      # Level of Service A-F (informational)

    # Evacuation route attributes (Agent 2)
    is_evacuation_route: bool = False
    connectivity_score: int = 0        # How many O-D paths traverse this segment
    catchment_units: float = 0.0       # Housing units whose path passes through this segment

    def data_quality_flag(self) -> str:
        """Returns 'measured', 'partial', or 'estimated' based on data quality."""
        estimated_count = sum([
            self.lane_count_estimated,
            self.speed_estimated,
            self.aadt_estimated,
        ])
        if estimated_count == 0:
            return "measured"
        elif estimated_count == 3:
            return "estimated"
        return "partial"

    def to_dict(self) -> dict:
        """Serialize to dict for CSV/DataFrame output."""
        return {
            "segment_id":              self.segment_id,
            "name":                    self.name,
            "osmid":                   self.osmid,
            "highway_tag":             self.highway_tag,
            "road_type":               self.road_type,
            "lane_count":              self.lane_count,
            "speed_limit":             self.speed_limit,
            "length_meters":           round(self.length_meters, 1),
            "capacity_vph":            round(self.capacity_vph, 0),
            "fhsz_zone":               self.fhsz_zone,
            "hazard_degradation":      self.hazard_degradation,
            "effective_capacity_vph":  round(self.effective_capacity_vph, 0),
            "aadt":                    self.aadt,
            "baseline_demand_vph":     round(self.baseline_demand_vph, 1),
            "vc_ratio":                round(self.vc_ratio, 4),
            "los":                     self.los,
            "is_evacuation_route":     self.is_evacuation_route,
            "connectivity_score":      self.connectivity_score,
            "catchment_units":         round(self.catchment_units, 0),
            "data_quality":            self.data_quality_flag(),
        }

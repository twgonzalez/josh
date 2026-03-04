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

    # Capacity analysis (Agent 2)
    capacity_vph: float = 0.0           # Vehicles per hour (HCM 2022)
    aadt: Optional[float] = None        # Annual Average Daily Traffic (if available)
    baseline_demand_vph: float = 0.0   # Peak hour demand
    vc_ratio: float = 0.0              # Volume-to-capacity ratio
    los: str = ""                      # Level of Service (A-F)

    # Evacuation route attributes (Agent 2)
    is_evacuation_route: bool = False
    connectivity_score: int = 0        # How many FHSZ centroids route through this segment

    # Standards engine (Agent 3)
    exceeds_baseline_threshold: bool = False   # baseline_vc >= 0.80
    proposed_demand_vph: float = 0.0
    proposed_vc_ratio: float = 0.0
    proposed_los: str = ""
    exceeds_proposed_threshold: bool = False   # proposed_vc > 0.80

    def vc_change(self) -> float:
        """Absolute change in v/c ratio from baseline to proposed."""
        return self.proposed_vc_ratio - self.vc_ratio

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
            "segment_id": self.segment_id,
            "name": self.name,
            "osmid": self.osmid,
            "highway_tag": self.highway_tag,
            "road_type": self.road_type,
            "lane_count": self.lane_count,
            "speed_limit": self.speed_limit,
            "length_meters": round(self.length_meters, 1),
            "capacity_vph": round(self.capacity_vph, 0),
            "aadt": self.aadt,
            "baseline_demand_vph": round(self.baseline_demand_vph, 1),
            "vc_ratio": round(self.vc_ratio, 4),
            "los": self.los,
            "is_evacuation_route": self.is_evacuation_route,
            "connectivity_score": self.connectivity_score,
            "exceeds_baseline_threshold": self.exceeds_baseline_threshold,
            "proposed_demand_vph": round(self.proposed_demand_vph, 1),
            "proposed_vc_ratio": round(self.proposed_vc_ratio, 4),
            "proposed_los": self.proposed_los,
            "exceeds_proposed_threshold": self.exceeds_proposed_threshold,
            "data_quality": self.data_quality_flag(),
        }

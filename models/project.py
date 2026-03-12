"""Project data model for a proposed development."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Project:
    """
    Represents a proposed development project being evaluated.

    Inputs come from the user (location, units, stories).
    All derived fields are calculated algorithmically by Agent 3.
    """

    # User-provided inputs
    location_lat: float = 0.0
    location_lon: float = 0.0
    address: str = ""
    dwelling_units: int = 0
    stories: int = 0               # number of above-grade stories (for egress penalty)
    unit_type: str = "multifamily"  # single_family | multifamily

    # Optional project metadata
    project_name: str = ""
    apn: str = ""  # Assessor Parcel Number
    applicant: str = ""

    # Standard 3 results (FHSZ zone)
    in_fire_zone: bool = False
    fire_zone_level: int = 0          # 0=none, 1=Moderate, 2=High, 3=VeryHigh
    hazard_zone: str = "non_fhsz"    # "vhfhsz"|"high_fhsz"|"moderate_fhsz"|"non_fhsz"
    fire_zone_source_date: str = ""

    # Standard 1 results (size threshold)
    meets_size_threshold: bool = False
    unit_threshold_used: int = 15

    # Standard 2 results (serving evacuation routes)
    serving_route_ids: list = field(default_factory=list)  # osmids of serving segments
    search_radius_miles: float = 0.5

    # Standard 4 results (ΔT capacity test)
    mobilization_rate: float = 0.0        # mob rate applied (from hazard_zone lookup)
    project_vehicles_peak_hour: float = 0.0  # dwelling_units × vpu × mob
    egress_minutes: float = 0.0           # NFPA 101 building egress penalty
    delta_t_results: list = field(default_factory=list)  # per-path ΔT audit dicts
    capacity_exceeded: bool = False       # True if any path ΔT > threshold (safe_egress_window × max_project_share)

    # SB 79 transit flag (informational — does not affect tier)
    sb79_transit_flag: bool = False

    # Final determination
    determination: str = ""         # "MINISTERIAL" | "MINISTERIAL WITH STANDARD CONDITIONS" | "DISCRETIONARY"
    determination_reason: str = ""

    def vehicle_generation(self, vehicles_per_unit: float, mobilization: float) -> float:
        """Calculate project peak-hour vehicle generation."""
        return self.dwelling_units * vehicles_per_unit * mobilization

    def max_delta_t(self) -> float:
        """Return the worst-case ΔT across all serving paths (0.0 if none computed)."""
        if not self.delta_t_results:
            return 0.0
        return max((r.get("delta_t_minutes", 0.0) for r in self.delta_t_results), default=0.0)

    def flagged_path_count(self) -> int:
        """Number of serving paths where ΔT exceeds the threshold."""
        return sum(1 for r in self.delta_t_results if r.get("flagged", False))

    def to_dict(self) -> dict:
        """Serialize to dict for output."""
        return {
            "project_name":             self.project_name,
            "address":                  self.address,
            "apn":                      self.apn,
            "location_lat":             self.location_lat,
            "location_lon":             self.location_lon,
            "dwelling_units":           self.dwelling_units,
            "stories":                  self.stories,
            "unit_type":                self.unit_type,
            "in_fire_zone":             self.in_fire_zone,
            "fire_zone_level":          self.fire_zone_level,
            "hazard_zone":              self.hazard_zone,
            "meets_size_threshold":     self.meets_size_threshold,
            "serving_routes_count":     len(self.serving_route_ids),
            "mobilization_rate":        self.mobilization_rate,
            "project_vehicles_peak_hour": round(self.project_vehicles_peak_hour, 1),
            "egress_minutes":           round(self.egress_minutes, 1),
            "max_delta_t_minutes":      round(self.max_delta_t(), 2),
            "capacity_exceeded":        self.capacity_exceeded,
            "flagged_path_count":       self.flagged_path_count(),
            "determination":            self.determination,
        }

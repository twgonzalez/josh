"""Project data model for a proposed development."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Project:
    """
    Represents a proposed development project being evaluated.

    Inputs come from the user (location, units).
    All derived fields are calculated algorithmically by Agent 3.
    """

    # User-provided inputs
    location_lat: float = 0.0
    location_lon: float = 0.0
    address: str = ""
    dwelling_units: int = 0
    unit_type: str = "multifamily"  # single_family | multifamily

    # Optional project metadata
    project_name: str = ""
    apn: str = ""  # Assessor Parcel Number
    applicant: str = ""

    # Standard 3 results (FHSZ modifier)
    in_fire_zone: bool = False
    fire_zone_level: int = 0    # 0=none, 1=Zone1, 2=Zone2, 3=Zone3
    fire_zone_source_date: str = ""

    # Standard 1 results (size threshold)
    meets_size_threshold: bool = False
    unit_threshold_used: int = 15

    # Standard 2 results (serving evacuation routes)
    serving_route_ids: list = field(default_factory=list)
    search_radius_miles: float = 0.5

    # Standard 4 results (evac capacity test)
    project_vehicles_peak_hour: float = 0.0
    exceeds_capacity_threshold: bool = False
    flagged_route_ids: list = field(default_factory=list)

    # Final determination
    determination: str = ""         # "MINISTERIAL" | "CONDITIONAL MINISTERIAL" | "DISCRETIONARY"
    determination_reason: str = ""

    def vehicle_generation(self, vehicles_per_unit: float, peak_hour_factor: float) -> float:
        """Calculate project peak-hour vehicle generation."""
        return self.dwelling_units * vehicles_per_unit * peak_hour_factor

    def to_dict(self) -> dict:
        """Serialize to dict for output."""
        return {
            "project_name": self.project_name,
            "address": self.address,
            "apn": self.apn,
            "location_lat": self.location_lat,
            "location_lon": self.location_lon,
            "dwelling_units": self.dwelling_units,
            "unit_type": self.unit_type,
            "in_fire_zone": self.in_fire_zone,
            "fire_zone_level": self.fire_zone_level,
            "meets_size_threshold": self.meets_size_threshold,
            "serving_routes_count": len(self.serving_route_ids),
            "project_vehicles_peak_hour": round(self.project_vehicles_peak_hour, 1),
            "exceeds_capacity_threshold": self.exceeds_capacity_threshold,
            "determination": self.determination,
        }

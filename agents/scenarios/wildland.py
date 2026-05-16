# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Scenario A: Wildland Evacuation Capacity (Standards 1–4) — JOSH v4.0

Legal basis: AB 747 (California Government Code §65302.15), HCM 2022,
NFPA 101 (Life Safety Code) mobilization design basis.

ΔT Standard (v3.4):
  Standard 1 — Project Size:       units >= threshold (scale gate)
  Standard 2 — Evac Routes Served: network buffer → identifies serving EvacuationPaths
  Standard 3 — FHSZ Modifier:      GIS point-in-polygon; sets hazard_zone string which
                                    controls ROAD capacity degradation and ΔT threshold
                                    (FHSZ does NOT affect mobilization in v3.4)
  Standard 4 — ΔT Test:            ΔT = (project_vehicles / bottleneck_effective_capacity) × 60 + egress
                                    Project is DISCRETIONARY if ΔT > threshold for hazard_zone
                                    threshold = safe_egress_window(zone) × max_project_share

Key v3.4 changes from v3.1:
  - Mobilization rate is now constant 0.90 (NFPA 101 design basis)
  - FHSZ zone now affects ONE thing only: road capacity (hazard_degradation factor)
  - Removed tiered mob rates (Zhao et al. 2022) — behavioral observation ≠ design standard
  - Berkeley regression test: 75-unit non-FHSZ hills → DISCRETIONARY (was MINISTERIAL WITH STANDARD CONDITIONS under v3.1)

Key v3.0 changes from v2.0:
  - No baseline precondition: routes already at LOS F are tested equally
  - Hazard-aware capacity degradation (HCM composite factors) applied upstream by Agent 2
  - Building egress penalty (NFPA 101/IBC) added to ΔT for buildings ≥ 4 stories
  - Returns EvacuationPath objects (not osmid lists) from identify_routes()

Three-tier output:
  DISCRETIONARY           — size threshold met AND ΔT > threshold (safe_egress_window × max_project_share) on any serving path
  MINISTERIAL WITH STANDARD CONDITIONS — size threshold met AND ΔT within threshold on all paths
  MINISTERIAL             — below size threshold
"""
import json
import logging
import math
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import Point

from models.project import Project
from models.evacuation_path import EvacuationPath
from .base import EvacuationScenario, Tier
from agents.capacity_analysis import bake_capacity_onto_graph
from .routing import RawCandidate, CandidateWithBottleneck, EgressOrigin, GraphContext

logger = logging.getLogger(__name__)

_LEGAL_BASIS = (
    "AB 747 (California Government Code §65302.15) — General Plan Safety Element "
    "mandatory update for evacuation route capacity analysis; "
    "HCM 2022 (Highway Capacity Manual, 7th Edition) — effective capacity with hazard degradation; "
    "NFPA 101 (Life Safety Code) — 0.90 mobilization design basis (100% occupant evacuation, "
    "adjusted for ~10% zero-vehicle households per Census ACS B25044); "
    "NIST TN 2135 (Maranghides et al.) — safe egress windows by hazard zone"
)

# HAZ_CLASS integer → canonical hazard_zone key (matches safe_egress_window and hazard_degradation keys)
_HAZ_CLASS_TO_ZONE = {
    3: "vhfhsz",
    2: "high_fhsz",
    1: "moderate_fhsz",
    0: "non_fhsz",
}


_METERS_PER_MILE = 1609.344

# 8-point compass labels indexed by octant (0 = N, 1 = NE, ... 7 = NW)
_COMPASS_LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _get_cross_streets(G, u: int, v: int, segment_name: str) -> tuple[str, str]:
    """Find cross-street names at both endpoints of an edge.

    For each endpoint node, iterate incident edges, collect street names
    (excluding the bottleneck's own name), and return the best candidate.
    Returns (cross_street_a, cross_street_b) — empty string if none found.
    """
    def _best_cross(node: int) -> str:
        names: list[str] = []
        for _, nbr, data in G.edges(node, data=True):
            if isinstance(data, dict):
                nm = data.get("name", None)
            else:
                # MultiDiGraph returns keyed edges; get first
                nm = None
            if nm:
                if isinstance(nm, list):
                    nm = nm[0]
                nm = str(nm)
                if nm and nm != segment_name:
                    names.append(nm)
        if not names:
            return ""
        # Return most frequent cross street, tie-break alphabetically
        from collections import Counter
        counts = Counter(names)
        return min(counts, key=lambda n: (-counts[n], n))

    # MultiDiGraph: G.edges(node, data=True) yields (u, v, key, data) with
    # keys=True, or (u, v, data) without.  Handle both by also checking the
    # underlying adjacency directly.
    def _cross_names_at(node: int) -> list[str]:
        names: list[str] = []
        try:
            for nbr_dict in G.adj[node].values():
                for edge_data in nbr_dict.values():
                    nm = edge_data.get("name", None)
                    if nm:
                        if isinstance(nm, list):
                            nm = nm[0]
                        nm = str(nm)
                        if nm and nm != segment_name:
                            names.append(nm)
        except (AttributeError, TypeError):
            pass
        return names

    def _pick_best(names: list[str]) -> str:
        if not names:
            return ""
        from collections import Counter
        counts = Counter(names)
        return min(counts, key=lambda n: (-counts[n], n))

    cross_a = _pick_best(_cross_names_at(u))
    cross_b = _pick_best(_cross_names_at(v))
    return cross_a, cross_b


def _bottleneck_distance_bearing(
    G, u: int, v: int, proj_x: float, proj_y: float,
) -> tuple[float, str]:
    """Compute distance (miles) and compass bearing from project to bottleneck midpoint.

    Uses projected coordinates (meters) for accuracy.
    """
    ux = G.nodes[u].get("x", 0)
    uy = G.nodes[u].get("y", 0)
    vx = G.nodes[v].get("x", 0)
    vy = G.nodes[v].get("y", 0)
    mx = (ux + vx) / 2
    my = (uy + vy) / 2

    dx = mx - proj_x
    dy = my - proj_y
    dist_m = math.hypot(dx, dy)
    dist_mi = dist_m / _METERS_PER_MILE

    # Bearing: atan2(dx, dy) gives angle from north (Y-axis) clockwise
    angle = math.degrees(math.atan2(dx, dy)) % 360
    octant = int((angle + 22.5) / 45) % 8
    bearing = _COMPASS_LABELS[octant]

    return round(dist_mi, 2), bearing


class WildlandScenario(EvacuationScenario):
    """
    Evaluates wildland evacuation capacity impact (Standards 1–4) using v3.0 ΔT metric.

    Standard 1 (size) gates the analysis.
    Standard 3 (FHSZ modifier) sets project.hazard_zone which controls:
      - ΔT threshold (safe_egress_window × max_project_share by hazard zone)
      - capacity degradation factor (applied upstream in Agent 2 to road segments)
      NOTE (v3.4): FHSZ does NOT affect mobilization. Mobilization is constant 0.90 (NFPA 101).
    Standard 4 (ΔT test) uses compute_delta_t() from base class.
    """

    @property
    def name(self) -> str:
        return "wildland_ab747"

    @property
    def legal_basis(self) -> str:
        return _LEGAL_BASIS

    @property
    def unit_threshold(self) -> int:
        return int(self.config.get("unit_threshold", 15))

    @property
    def fallback_tier(self) -> Tier:
        return Tier.CONDITIONAL_MINISTERIAL

    # ------------------------------------------------------------------
    # Step 1: Applicability — always applicable; sets FHSZ hazard zone
    # ------------------------------------------------------------------

    def check_applicability(self, project: Project, context: dict) -> tuple[bool, dict]:
        """
        Standard 3 (FHSZ Modifier): Sets project.hazard_zone based on site location.

        This scenario is ALWAYS applicable — the citywide FHSZ gate was removed in v3.0.

        The GIS point-in-polygon test determines project.hazard_zone, which controls:
          - ΔT threshold via config["safe_egress_window"][hazard_zone] × config["max_project_share"]
          - road capacity degradation (applied upstream in Agent 2)
          NOTE (v3.4): FHSZ does NOT affect mobilization rate. Mobilization is constant 0.90.

        Method: GIS point-in-polygon test against CAL FIRE FHSZ zones.
        Discretion: Zero — binary spatial result with deterministic zone mapping.
        """
        fhsz_gdf = context.get("fhsz_gdf", gpd.GeoDataFrame())

        fire_zone_result, fire_zone_detail = check_fire_zone(
            (project.location_lat, project.location_lon), fhsz_gdf
        )

        # Set project fire zone fields
        project.in_fire_zone    = fire_zone_result
        project.fire_zone_level = fire_zone_detail.get("zone_level", 0)
        project.hazard_zone     = fire_zone_detail.get("hazard_zone", "non_fhsz")

        # Behavioral mobilization is constant (FHWA) — not FHSZ-dependent
        project.behavioral_mobilization = self.config.get("behavioral_mobilization", 0.90)

        return True, {
            "result":                    True,
            "method":                    "Always applicable; site FHSZ check via GIS point-in-polygon",
            "std3_fhsz_flagged":         fire_zone_result,
            "std3_zone_level":           project.fire_zone_level,
            "std3_zone_desc":            fire_zone_detail.get("zone_description", "Not in FHSZ"),
            "std3_hazard_zone":          project.hazard_zone,
            "std3_behavioral_mobilization": project.behavioral_mobilization,
            "fire_zone_severity_modifier": fire_zone_detail,
            "note": (
                f"FHSZ Zone {project.fire_zone_level} ({project.hazard_zone}) — "
                f"road capacity degradation applied; mobilization unaffected. "
                f"Behavioral mobilization {project.behavioral_mobilization:.2f} (FHWA, constant)."
                if fire_zone_result else
                f"Not in FHSZ (hazard_zone=non_fhsz) — no road degradation. "
                f"Behavioral mobilization {project.behavioral_mobilization:.2f} (FHWA, constant)."
            ),
        }

    # ------------------------------------------------------------------
    # Step 3: Route Identification — serving EvacuationPath objects
    # ------------------------------------------------------------------

    def identify_routes(
        self,
        project: Project,
        roads_gdf: gpd.GeoDataFrame,
        context: dict,
    ) -> tuple[list, dict]:
        """
        Standard 2 (Evac Routes Served): Which EvacuationPaths serve this project?

        Orchestrates the routing pipeline:
          1. Compute reachable network (graph walk or Euclidean fallback)
          2. Build segment index from roads_gdf
          3. Load graph, exit nodes, build travel-time weights
          4. Assemble egress origins (primary + additional_egress_points)
          5. Dijkstra to all exits → raw candidates
          6. Filter by travel-time ratio → bottleneck ID → cross-street enrich → dedup
          7. Build EvacuationPath objects
          8. Fallback to population paths if Dijkstra unavailable
          9. Assemble audit detail

        Returns list[EvacuationPath] for consumption by compute_delta_t().
        Discretion: Zero — algorithmic spatial query.
        """
        evac_cfg = self.config.get("evacuation", {})
        radius = evac_cfg.get(
            "serving_route_radius_miles",
            self.config.get("evacuation_route_radius_miles", 0.5),
        )
        analysis_crs = self.city_config.get("analysis_crs", "EPSG:26910")
        lat, lon = project.location_lat, project.location_lon
        project_pt = gpd.GeoDataFrame(
            {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
        ).to_crs(analysis_crs)
        radius_meters = radius * 1609.344
        proj_x = project_pt.geometry.iloc[0].x
        proj_y = project_pt.geometry.iloc[0].y

        # Phase 1: Reachable network + graph loading
        graph_path = context.get("graph_path")
        nearby_osmids, reachable_osmids, method_note, gctx = _load_graph_and_reachable(
            graph_path, proj_x, proj_y, radius, radius_meters, analysis_crs,
            roads_gdf, self.config, project.project_name,
        )
        project.serving_route_ids = list(nearby_osmids)
        project.reachable_network_osmids = list(reachable_osmids)
        project.search_radius_miles = radius

        # Phase 2: Bake per-edge capacity attributes onto the routing graph
        # so both this engine and export_graph_json (JS engine source) read
        # eff_cap_vph from G[u][v][k] directly — single source of truth.
        # See agents/capacity_analysis.py bake_capacity_onto_graph.
        if gctx is not None and gctx.G is not None:
            bake_capacity_onto_graph(gctx.G, roads_gdf)
            if gctx.G_undirected is not None:
                bake_capacity_onto_graph(gctx.G_undirected, roads_gdf)

        # Phase 3: Dijkstra routing (if graph available)
        all_evac_paths: list = context.get("evacuation_paths", [])
        project_paths: list[EvacuationPath] = []
        fallback_used = False
        max_path_ratio = float(evac_cfg.get("max_path_length_ratio", 2.0))

        if gctx is not None:
            origins = _build_egress_origins(
                project, gctx, analysis_crs,
            )
            for origin in origins:
                candidates = _dijkstra_to_exits(
                    gctx, origin, self.config.get("speed_defaults", {}),
                )
                if not candidates:
                    continue
                filtered = _filter_by_travel_time(
                    candidates, max_path_ratio, origin.label,
                )
                enriched = _identify_and_enrich(
                    filtered, gctx.G, proj_x, proj_y,
                )
                project_paths.extend(
                    _build_evac_paths(enriched, origin, gctx)
                )

            logger.info(
                f"  Project-origin Dijkstra (travel-time weight): {len(project_paths)} "
                f"viable paths for {project.project_name} "
                f"({len(origins)} egress origin(s); "
                f"ratio ≤{max_path_ratio:.1f}× fastest exit, "
                f"from {len(gctx.exit_nodes)} exits; no bottleneck dedup)"
            )

        # Phase 4: Fallback to population paths
        if project_paths:
            serving_paths = project_paths
        else:
            serving_paths, fallback_used = _fallback_to_population_paths(
                all_evac_paths, reachable_osmids, project_paths,
                lat, lon, project.project_name,
            )

        # Phase 5: Audit detail assembly
        detail = _build_audit_detail(
            serving_paths, project_paths, nearby_osmids,
            roads_gdf, lat, lon, radius, radius_meters,
            method_note, fallback_used,
        )
        return serving_paths, detail

    # ------------------------------------------------------------------
    # Override reason builders to include fire zone / ΔT context
    # ------------------------------------------------------------------

    def _reason_discretionary(self, project: Project, step5: dict) -> str:
        max_dt    = step5.get("max_delta_t_minutes", 0.0)
        threshold = step5.get("threshold_minutes", 0.0)
        hz        = step5.get("hazard_zone", "non_fhsz")
        mob       = step5.get("behavioral_mobilization", 0.90)
        n_paths   = sum(1 for r in step5.get("path_results", []) if r.get("flagged"))
        fire_note = (
            f"FHSZ Zone {project.fire_zone_level} ({hz}) — road capacity degradation applied. "
            if project.in_fire_zone else
            f"Not in FHSZ (hazard_zone={hz}) — no road degradation. "
        )
        return (
            f"Project meets the {self.unit_threshold}-unit applicability threshold and "
            f"{n_paths} serving path(s) exceed the ΔT threshold of {threshold:.2f} min "
            f"(max ΔT: {max_dt:.1f} min). "
            f"{fire_note}"
            f"Behavioral mobilization: {mob:.2f} (FHWA, constant). "
            f"Discretionary review required. Legal basis: {self.legal_basis}."
        )

    def _reason_fallback(self, project: Project, step3: dict, step5: dict) -> str:
        n_paths   = step3.get("serving_paths_count", 0)
        max_dt    = step5.get("max_delta_t_minutes", 0.0)
        threshold = step5.get("threshold_minutes", 0.0)
        hz        = step5.get("hazard_zone", "non_fhsz")
        mob       = step5.get("behavioral_mobilization", 0.90)
        fire_note = (
            f"FHSZ Zone {project.fire_zone_level} ({hz}) — road capacity degradation applied. "
            if project.in_fire_zone else
            f"Not in FHSZ (hazard_zone={hz}) — no road degradation. "
        )
        return (
            f"Project meets the {self.unit_threshold}-unit applicability threshold and "
            f"has {n_paths} serving path(s). "
            f"Max ΔT {max_dt:.1f} min within threshold ({threshold:.2f} min). "
            f"{fire_note}"
            f"Behavioral mobilization: {mob:.2f} (FHWA, constant). "
            f"Ministerial approval with standard conditions applied automatically. "
            f"Legal basis: {self.legal_basis}."
        )


# ---------------------------------------------------------------------------
# Extracted routing phases (module-level — reusable and independently testable)
# ---------------------------------------------------------------------------

_MPH_TO_MPS = 0.44704  # exact: 1 mph = 0.44704 m/s
_FREEWAY_HW = {"motorway", "motorway_link"}


def _load_graph_and_reachable(
    graph_path, proj_x, proj_y, radius, radius_meters, analysis_crs,
    roads_gdf, config, project_name,
) -> tuple[set[str], set[str], str, GraphContext | None]:
    """Load graph, compute reachable network, build GraphContext.

    Returns (nearby_osmids, reachable_osmids, method_note, graph_context).
    graph_context is None if graph is unavailable (Euclidean fallback used).
    """
    nearby_osmids: set[str] = set()
    reachable_osmids: set[str] = set()
    method_note = ""
    gctx = None

    if graph_path and Path(graph_path).exists():
        try:
            G = ox.load_graphml(graph_path)
            nearest_node = ox.distance.nearest_nodes(G, proj_x, proj_y)

            G_undir = G.to_undirected()
            reachable = nx.single_source_dijkstra_path_length(
                G_undir, nearest_node, cutoff=radius_meters, weight="length"
            )
            reachable_nodes = set(reachable.keys())

            for u, v, data in G.edges(data=True):
                oid = data.get("osmid")
                if not oid:
                    continue
                oid_strs = [str(o) for o in oid] if isinstance(oid, list) else [str(oid)]
                if u in reachable_nodes or v in reachable_nodes:
                    reachable_osmids.update(oid_strs)
                if u in reachable_nodes and v in reachable_nodes:
                    nearby_osmids.update(oid_strs)

            method_note = (
                f"Project-origin Dijkstra (v4.0, travel-time weight) — "
                f"fastest path from project site to each regional-network "
                f"exit node (motorway/trunk/primary at city boundary); "
                f"weight=length/speed_limit (seconds) per speed_defaults config; "
                f"{len(reachable_nodes)} nodes within {radius} mi network zone; "
                f"respects road barriers (I-5, rail, etc.)"
            )
            logger.info(
                f"  Network proximity: {len(reachable_nodes)} reachable nodes, "
                f"{len(nearby_osmids)} edge osmids for {project_name}"
            )

            # Load exit nodes
            exit_nodes_path = Path(str(graph_path)).parent / "exit_nodes.json"
            exit_nodes: list = []
            if exit_nodes_path.exists():
                try:
                    exit_nodes = json.loads(exit_nodes_path.read_text())
                except Exception as e:
                    logger.warning(f"  Could not load exit_nodes.json ({e})")

            if exit_nodes:
                # Build undirected graph with travel-time weights
                G_undir_full = G.to_undirected()
                speed_defaults_mph = config.get("speed_defaults", {})
                for _u, _v, _ed in G_undir_full.edges(data=True):
                    _hw = _ed.get("highway", "")
                    _hw_str = _hw[0] if isinstance(_hw, list) else str(_hw)
                    _spd_mph = speed_defaults_mph.get(_hw_str, 25)
                    _spd_mps = _spd_mph * _MPH_TO_MPS
                    _len_m = float(_ed.get("length", 0) or 0)
                    _ed["travel_time_s"] = _len_m / _spd_mps if _spd_mps > 0 else _len_m

                _graph_crs = G.graph.get("crs", "EPSG:26911")
                _to_wgs84 = Transformer.from_crs(_graph_crs, "EPSG:4326", always_xy=True)

                gctx = GraphContext(
                    G=G,
                    G_undirected=G_undir_full,
                    exit_nodes=[int(n) for n in exit_nodes],
                    nearest_node=nearest_node,
                    transformer=_to_wgs84,
                    proj_x=proj_x,
                    proj_y=proj_y,
                )
        except Exception as e:
            logger.warning(f"  Graph load failed ({e}) — falling back to population paths")

    if gctx is None and not nearby_osmids:
        # Euclidean buffer fallback
        roads_proj = roads_gdf.to_crs(analysis_crs)
        project_pt_geom = Point(proj_x, proj_y)
        buffer = project_pt_geom.buffer(radius_meters)
        if "is_evacuation_route" not in roads_proj.columns:
            evac_nearby = roads_proj[roads_proj.geometry.intersects(buffer)]
        else:
            evac_only = roads_proj[roads_proj["is_evacuation_route"] == True]
            evac_nearby = evac_only[evac_only.geometry.intersects(buffer)]
        for osmid_val in evac_nearby["osmid"].tolist():
            if isinstance(osmid_val, list):
                for o in osmid_val:
                    nearby_osmids.add(str(o))
                    reachable_osmids.add(str(o))
            else:
                nearby_osmids.add(str(osmid_val))
                reachable_osmids.add(str(osmid_val))
        method_note = "Euclidean buffer (graph unavailable — pre-v3.4 fallback)"

    return nearby_osmids, reachable_osmids, method_note, gctx


def _build_egress_origins(
    project: Project,
    gctx: GraphContext,
    analysis_crs: str,
) -> list[EgressOrigin]:
    """Build list of egress origins: primary + additional_egress_points."""
    origins: list[EgressOrigin] = [
        EgressOrigin(node_id=gctx.nearest_node, label="project_origin")
    ]
    G = gctx.G

    for _aei, _aep in enumerate(
        getattr(project, "additional_egress_points", []), 1
    ):
        try:
            _aep_pt = gpd.GeoDataFrame(
                geometry=[Point(float(_aep["lon"]), float(_aep["lat"]))],
                crs="EPSG:4326",
            ).to_crs(analysis_crs)
            _aep_x = _aep_pt.geometry.iloc[0].x
            _aep_y = _aep_pt.geometry.iloc[0].y
            _override_id = _aep.get("additional_egress_node_id")
            if _override_id is not None:
                _aep_node = int(_override_id)
                logger.info(
                    f"  Additional egress {_aei} "
                    f"({_aep.get('label', 'unlabeled')!r}): "
                    f"using explicit node_id override {_aep_node}"
                )
            else:
                _raw_node = ox.distance.nearest_nodes(G, _aep_x, _aep_y)
                _raw_hw = set()
                for _, _, _ed in G.edges(_raw_node, data=True):
                    _hw = _ed.get("highway", "")
                    _raw_hw.update(_hw if isinstance(_hw, list) else [_hw])
                _motorway_types = {"motorway", "motorway_link"}
                if _raw_hw and _raw_hw.issubset(_motorway_types):
                    _best_dist, _aep_node = float("inf"), _raw_node
                    for _cand, _cdata in G.nodes(data=True):
                        _cx = float(_cdata.get("x", 0))
                        _cy = float(_cdata.get("y", 0))
                        _d = ((_cx - _aep_x) ** 2 + (_cy - _aep_y) ** 2) ** 0.5
                        if _d >= _best_dist:
                            continue
                        _e_hw: set[str] = set()
                        for _, _, _ed in G.edges(_cand, data=True):
                            _h = _ed.get("highway", "")
                            _e_hw.update(_h if isinstance(_h, list) else [_h])
                        if not _e_hw.issubset(_motorway_types):
                            _best_dist, _aep_node = _d, _cand
                    logger.warning(
                        f"  Additional egress {_aei} "
                        f"({_aep.get('label', 'unlabeled')!r}): raw snap "
                        f"landed on motorway (node {_raw_node}); "
                        f"fell back to nearest non-motorway node {_aep_node}. "
                        f"Use additional_egress_node_id in YAML to pin explicitly."
                    )
                else:
                    _aep_node = _raw_node
            _existing_nodes = {o.node_id for o in origins}
            if _aep_node in _existing_nodes:
                logger.warning(
                    f"  Additional egress {_aei} "
                    f"({_aep.get('label', 'unlabeled')!r}) snapped to "
                    f"node {_aep_node} — same as an existing origin. "
                    f"Road is likely not in the OSM drivable graph "
                    f"(private/unmapped access road). Skipping to avoid "
                    f"duplicate paths. Add road to OSM or override the "
                    f"snap node via additional_egress_node_id in the YAML "
                    f"to model this egress independently."
                )
            else:
                origins.append(EgressOrigin(
                    node_id=_aep_node, label=f"project_egress_{_aei}",
                ))
                logger.info(
                    f"  Additional egress {_aei} "
                    f"({_aep.get('label', 'unlabeled')!r}): "
                    f"snapped to node {_aep_node}"
                )
        except Exception as _snap_err:
            logger.warning(f"  Additional egress {_aei} snap failed: {_snap_err}")

    return origins


def _dijkstra_to_exits(
    gctx: GraphContext,
    origin: EgressOrigin,
    speed_defaults_mph: dict,
) -> list[RawCandidate]:
    """Run Dijkstra from origin to all exits, build RawCandidates with geometry."""
    G = gctx.G
    G_undir = gctx.G_undirected
    to_wgs84 = gctx.transformer
    candidates: list[RawCandidate] = []

    for exit_node_id in gctx.exit_nodes:
        if exit_node_id == origin.node_id:
            continue
        try:
            path_nodes = nx.shortest_path(
                G_undir, origin.node_id, exit_node_id,
                weight="travel_time_s",
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        if len(path_nodes) < 2:
            continue

        # Freeway truncation for visualization
        _cutoff = len(path_nodes)
        for _fei, (_feu, _fev) in enumerate(zip(path_nodes[:-1], path_nodes[1:])):
            _feed = G.get_edge_data(_feu, _fev) or G.get_edge_data(_fev, _feu) or {}
            for _fekd in (_feed.values() if isinstance(_feed, dict) else [_feed]):
                if str(_fekd.get("highway", "")) in _FREEWAY_HW:
                    _cutoff = _fei + 1
                    break
            if _cutoff < len(path_nodes):
                break

        # Build WGS84 coordinate chain from edge geometries
        path_wgs84: list[list[float]] = []
        _edge_pairs = list(zip(path_nodes[:-1], path_nodes[1:]))
        for _ei, (_eu, _ev) in enumerate(_edge_pairs):
            if _ei >= _cutoff - 1:
                break
            _ed = G.get_edge_data(_eu, _ev) or G.get_edge_data(_ev, _eu)
            _kd = (next(iter(_ed.values()))
                   if isinstance(_ed, dict) else _ed) if _ed else None
            _geom = _kd.get("geometry") if _kd else None
            if _geom is not None:
                _raw = list(_geom.coords)
                _eu_x = G.nodes[_eu].get("x", 0)
                _eu_y = G.nodes[_eu].get("y", 0)
                if ((_raw[-1][0] - _eu_x)**2 + (_raw[-1][1] - _eu_y)**2
                        < (_raw[0][0] - _eu_x)**2 + (_raw[0][1] - _eu_y)**2):
                    _raw = list(reversed(_raw))
                for _ci, (_cx, _cy) in enumerate(_raw):
                    if _ci == 0 and path_wgs84:
                        continue
                    _c_lon, _c_lat = to_wgs84.transform(_cx, _cy)
                    path_wgs84.append([_c_lat, _c_lon])
            else:
                _fx = G.nodes[_eu].get("x", 0) if not path_wgs84 else None
                _fy = G.nodes[_eu].get("y", 0) if not path_wgs84 else None
                if _fx is not None:
                    _f_lon, _f_lat = to_wgs84.transform(_fx, _fy)
                    path_wgs84.append([_f_lat, _f_lon])
                _vx = G.nodes[_ev].get("x", 0)
                _vy = G.nodes[_ev].get("y", 0)
                _v_lon, _v_lat = to_wgs84.transform(_vx, _vy)
                path_wgs84.append([_v_lat, _v_lon])
        # Ensure final node is included when path wasn't truncated
        if _cutoff == len(path_nodes) and path_nodes:
            _last_nid = path_nodes[_cutoff - 1]
            _lx = G.nodes[_last_nid].get("x", 0)
            _ly = G.nodes[_last_nid].get("y", 0)
            _l_lon, _l_lat = to_wgs84.transform(_lx, _ly)
            if not path_wgs84 or path_wgs84[-1] != [_l_lat, _l_lon]:
                path_wgs84.append([_l_lat, _l_lon])

        # Build osmid sequence and travel time
        path_osmids: list[str] = []
        osmid_to_uv: dict[str, tuple[int, int]] = {}
        path_length = 0.0
        path_travel_time = 0.0
        exit_osmid = ""
        for u, v in zip(path_nodes[:-1], path_nodes[1:]):
            ed = G.get_edge_data(u, v) or G.get_edge_data(v, u)
            if ed:
                for kd in (ed.values() if isinstance(ed, dict) else [ed]):
                    oid = kd.get("osmid")
                    seg_len = float(kd.get("length", 0) or 0)
                    hw_str = str(kd.get("highway", ""))
                    spd_mph = speed_defaults_mph.get(hw_str, 25)
                    seg_tt = seg_len / (spd_mph * _MPH_TO_MPS) if spd_mph > 0 else seg_len
                    if oid:
                        oid_str = str(oid[0]) if isinstance(oid, list) else str(oid)
                        path_osmids.append(oid_str)
                        osmid_to_uv[oid_str] = (u, v)
                        path_length += seg_len
                        path_travel_time += seg_tt
                        break
            if v == exit_node_id or u == exit_node_id:
                exit_osmid = path_osmids[-1] if path_osmids else ""

        if path_osmids and path_travel_time > 0:
            candidates.append(RawCandidate(
                travel_time_s=path_travel_time,
                exit_node_id=exit_node_id,
                path_osmids=path_osmids,
                exit_osmid=exit_osmid,
                path_length_m=path_length,
                path_wgs84_coords=path_wgs84,
                osmid_to_uv=osmid_to_uv,
            ))

    return candidates


def _filter_by_travel_time(
    candidates: list[RawCandidate],
    max_ratio: float,
    origin_label: str = "",
) -> list[RawCandidate]:
    """Filter candidates to those within max_ratio × fastest travel time."""
    if not candidates:
        return []
    min_tt = min(c.travel_time_s for c in candidates)
    max_allowed = min_tt * max_ratio
    filtered = [c for c in candidates if c.travel_time_s <= max_allowed]
    excluded = len(candidates) - len(filtered)
    if excluded:
        logger.info(
            f"  Path filter ({origin_label}): {excluded} exit(s) excluded "
            f"(>{max_ratio:.1f}× fastest-exit travel time of "
            f"{min_tt/60:.1f} min); {len(filtered)} remain"
        )
    return filtered


def _edge_attrs(G, osmid: str, osmid_to_uv: dict) -> dict:
    """Return per-edge attributes baked by bake_capacity_onto_graph.

    Looks up the (u, v) for `osmid` via the path's osmid_to_uv mapping,
    then reads the edge data directly from G.  Assumes G is a MultiDiGraph
    (OSMnx default), where get_edge_data returns {key: data_dict, ...};
    yields the first key's data.  Returns {} if the edge isn't found.
    """
    uv = osmid_to_uv.get(osmid)
    if not uv:
        return {}
    u, v = uv
    ed = G.get_edge_data(u, v) or G.get_edge_data(v, u)
    if not ed:
        return {}
    return next(iter(ed.values()), {})


_ZONE_TO_HAZ_CLASS = {
    "vhfhsz": 3, "high_fhsz": 2, "moderate_fhsz": 1, "non_fhsz": 0,
}


def _identify_and_enrich(
    candidates: list[RawCandidate],
    G,
    proj_x: float,
    proj_y: float,
) -> list[CandidateWithBottleneck]:
    """Identify bottleneck (min eff_cap on path) + cross-streets/distance/bearing.

    Reads eff_cap_vph and other attrs from per-edge data baked onto G by
    bake_capacity_onto_graph().  No osmid-keyed side table.
    """
    result: list[CandidateWithBottleneck] = []
    for cand in candidates:
        # Bottleneck = the path's edge with the lowest eff_cap_vph.
        # Edges with eff_cap_vph=0 (missing roads_gdf row) are skipped via
        # `or float('inf')` so they never get picked as the bottleneck.
        def _cap(o: str) -> float:
            return float(_edge_attrs(G, o, cand.osmid_to_uv).get("eff_cap_vph", 0) or 0)

        bottleneck_osmid = min(
            cand.path_osmids,
            key=lambda o: _cap(o) or float("inf"),
            default=cand.path_osmids[0],
        )
        eff_cap = _cap(bottleneck_osmid)
        if eff_cap <= 0:
            continue

        bn_attrs = _edge_attrs(G, bottleneck_osmid, cand.osmid_to_uv)
        bn_name = str(bn_attrs.get("bottleneck_name", "") or "")
        bn_uv = cand.osmid_to_uv.get(bottleneck_osmid)
        cross_a, cross_b = "", ""
        dist_mi, bearing = 0.0, ""
        if bn_uv:
            bn_u, bn_v = bn_uv
            cross_a, cross_b = _get_cross_streets(G, bn_u, bn_v, bn_name)
            dist_mi, bearing = _bottleneck_distance_bearing(
                G, bn_u, bn_v, proj_x, proj_y,
            )

        result.append(CandidateWithBottleneck(
            travel_time_s=cand.travel_time_s,
            exit_node_id=cand.exit_node_id,
            path_osmids=cand.path_osmids,
            exit_osmid=cand.exit_osmid,
            path_length_m=cand.path_length_m,
            path_wgs84_coords=cand.path_wgs84_coords,
            osmid_to_uv=cand.osmid_to_uv,
            bottleneck_osmid=bottleneck_osmid,
            bottleneck_eff_cap=eff_cap,
            bottleneck_name=bn_name,
            cross_street_a=cross_a,
            cross_street_b=cross_b,
            distance_mi=dist_mi,
            bearing=bearing,
        ))
    return result


def _build_evac_paths(
    candidates: list[CandidateWithBottleneck],
    origin: EgressOrigin,
    gctx: GraphContext,
) -> list[EvacuationPath]:
    """Convert enriched candidates to EvacuationPath objects.

    Reads per-edge bottleneck metadata from gctx.G[u][v][k] (baked by
    bake_capacity_onto_graph).  No osmid-keyed side table.
    """
    paths: list[EvacuationPath] = []
    for cand in candidates:
        bn_attrs = _edge_attrs(gctx.G, cand.bottleneck_osmid, cand.osmid_to_uv)
        fhsz_zone = str(bn_attrs.get("fhsz_zone", "non_fhsz"))
        path_id = f"proj_{origin.node_id}_{cand.exit_node_id}"
        paths.append(EvacuationPath(
            path_id=path_id,
            origin_block_group=origin.label,
            exit_segment_osmid=cand.exit_osmid,
            travel_time_s=cand.travel_time_s,
            bottleneck_osmid=cand.bottleneck_osmid,
            bottleneck_name=cand.bottleneck_name,
            bottleneck_fhsz_zone=fhsz_zone,
            bottleneck_road_type=str(bn_attrs.get("road_type", "two_lane")),
            bottleneck_hcm_capacity_vph=float(bn_attrs.get("hcm_capacity_vph", cand.bottleneck_eff_cap) or cand.bottleneck_eff_cap),
            bottleneck_hazard_degradation=float(bn_attrs.get("hazard_degradation", 1.0)),
            bottleneck_effective_capacity_vph=cand.bottleneck_eff_cap,
            bottleneck_lane_count=int(bn_attrs.get("lane_count", 0) or 0),
            bottleneck_speed_limit=int(bn_attrs.get("speed_limit", 0) or 0),
            bottleneck_haz_class=_ZONE_TO_HAZ_CLASS.get(fhsz_zone, 0),
            bottleneck_cross_street_a=cand.cross_street_a,
            bottleneck_cross_street_b=cand.cross_street_b,
            bottleneck_distance_mi=cand.distance_mi,
            bottleneck_bearing=cand.bearing,
            path_osmids=cand.path_osmids,
            path_wgs84_coords=cand.path_wgs84_coords,
        ))
    return paths


def _fallback_to_population_paths(
    all_evac_paths: list,
    reachable_osmids: set[str],
    project_paths: list,
    lat: float,
    lon: float,
    project_name: str,
) -> tuple[list, bool]:
    """Fall back to population paths when Dijkstra paths unavailable."""
    fallback_used = False
    serving_paths = [
        p for p in all_evac_paths
        if _is_upstream_match(
            getattr(p, "path_osmids", []),
            str(getattr(p, "bottleneck_osmid", "")),
            reachable_osmids,
        )
    ]
    if not serving_paths and all_evac_paths:
        serving_paths = list(all_evac_paths)
        fallback_used = True
        logger.warning(
            f"  No project-origin paths or population paths matched for "
            f"({lat:.4f}, {lon:.4f}) — using all {len(all_evac_paths)} paths (conservative)"
        )
    elif not project_paths:
        fallback_used = True
        logger.warning(
            f"  Graph/exit nodes unavailable — using population-path upstream-entry filter "
            f"({len(serving_paths)} paths) for {project_name}"
        )
    return serving_paths, fallback_used


def _build_audit_detail(
    serving_paths: list,
    project_paths: list,
    nearby_osmids: set[str],
    roads_gdf: gpd.GeoDataFrame,
    lat: float,
    lon: float,
    radius: float,
    radius_meters: float,
    method_note: str,
    fallback_used: bool,
) -> dict:
    """Assemble the audit trail detail dict."""
    if project_paths:
        audit_osmids: set[str] = set()
        for p in project_paths:
            audit_osmids.update(str(o) for o in getattr(p, "path_osmids", []))
    else:
        audit_osmids = nearby_osmids

    roads_wgs84 = (
        roads_gdf
        if roads_gdf.crs and roads_gdf.crs.to_epsg() == 4326
        else roads_gdf.to_crs("EPSG:4326")
    )
    serving_route_details = []
    for _, row in roads_wgs84.iterrows():
        osmid_val = row.get("osmid")
        osmid_strs = (
            [str(osmid_val)]
            if not isinstance(osmid_val, list)
            else [str(o) for o in osmid_val]
        )
        if any(s in audit_osmids for s in osmid_strs):
            serving_route_details.append({
                "osmid":                  str(osmid_val),
                "name":                   row.get("name", ""),
                "fhsz_zone":              row.get("fhsz_zone", "non_fhsz"),
                "hazard_degradation":     row.get("hazard_degradation", 1.0),
                "effective_capacity_vph": round(
                    row.get("effective_capacity_vph", row.get("capacity_vph", 0)), 0
                ),
                "vc_ratio":               round(row.get("vc_ratio", 0), 4),
                "los":                    row.get("los", ""),
            })

    return {
        "project_lat":          lat,
        "project_lon":          lon,
        "radius_miles":         radius,
        "radius_meters":        round(radius_meters, 1),
        "method":               method_note,
        "serving_route_count":  len(serving_route_details),
        "serving_paths_count":  len(serving_paths),
        "fallback_all_paths":   fallback_used,
        "triggers_standard":    len(serving_paths) > 0,
        "serving_routes":       serving_route_details,
    }


# ---------------------------------------------------------------------------
# Legacy helper functions
# ---------------------------------------------------------------------------

def _is_upstream_match(
    path_osmids: list,
    bottleneck_osmid: str,
    reachable_osmids: set[str],
) -> bool:
    """
    Return True if the project can enter this EvacuationPath upstream of its bottleneck.

    A project contributes traffic to a path only if it has road access to some segment
    BEFORE (or at) the bottleneck.  Testing only the bottleneck osmid is insufficient:
    a project located downstream of the bottleneck would have no opportunity to load
    traffic onto the bottleneck segment.

    Args:
        path_osmids:      Ordered list of OSM way IDs from block-group origin to city exit.
        bottleneck_osmid: OSM way ID of the weakest-capacity segment on this path.
        reachable_osmids: All OSM edge IDs reachable from the project within the search
                          radius (either endpoint reachable — wider than nearby_osmids).

    Returns True when at least one segment in path_osmids[0 : bottleneck_pos + 1] is
    in reachable_osmids.  Returns False if bottleneck_osmid is not found in path_osmids
    (defensive: malformed path — exclude rather than include).
    """
    if not bottleneck_osmid or not path_osmids:
        return False

    # Locate the bottleneck in the ordered path
    bottleneck_pos = next(
        (i for i, o in enumerate(path_osmids) if str(o) == bottleneck_osmid),
        None,
    )
    if bottleneck_pos is None:
        return False

    # Any segment from path start up to and including the bottleneck reachable?
    pre_bottleneck = {str(o) for o in path_osmids[: bottleneck_pos + 1]}
    return bool(pre_bottleneck & reachable_osmids)


def check_fire_zone(
    location: tuple[float, float],
    fhsz_gdf: gpd.GeoDataFrame,
) -> tuple[bool, dict]:
    """
    Standard 3 (FHSZ Modifier): Is the project site in FHSZ Zone 2 or 3?

    Returns (in_trigger_zone: bool, detail: dict).
    detail["hazard_zone"] contains the canonical zone key for capacity degradation lookup.

    HAZ_CLASS mapping:
      3 → "vhfhsz" (Very High)
      2 → "high_fhsz" (High) — trigger zone
      1 → "moderate_fhsz" (Moderate)
      0 → "non_fhsz"

    in_trigger_zone is True for HAZ_CLASS >= 2 (High and Very High).
    Moderate FHSZ (HAZ_CLASS=1) sets hazard_zone="moderate_fhsz" but returns False
    (does not trigger FHSZ status; behavioral_mobilization is constant across all zones).
    Discretion: Zero — binary spatial result.
    """
    lat, lon = location
    project_pt = gpd.GeoDataFrame(
        {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
    )

    detail = {
        "input_lat":   lat,
        "input_lon":   lon,
        "method":      "GIS point-in-polygon (shapely/geopandas sjoin)",
        "data_source": "CAL FIRE FHSZ",
        "role":        "Sets hazard_zone for capacity degradation and ΔT threshold lookup",
    }

    if fhsz_gdf.empty:
        detail.update({
            "result":       False,
            "zone_level":   0,
            "hazard_zone":  "non_fhsz",
            "note":         "FHSZ data unavailable",
        })
        return False, detail

    fhsz_wgs84 = fhsz_gdf.to_crs("EPSG:4326")
    joined     = gpd.sjoin(project_pt, fhsz_wgs84, how="left", predicate="within")

    gap_resolved = False
    gap_dist_m   = None

    if joined.empty or joined["HAZ_CLASS"].isna().all():
        # Point fell in a gap between FHSZ polygons.  Apply nearest-neighbour
        # fallback: if the closest polygon boundary is within 50 m, inherit its
        # HAZ_CLASS.  CAL FIRE FHSZ tiles can have slivers and road-right-of-way
        # gaps that are artefacts of the digitising process, not genuine zone
        # boundaries.  50 m was chosen to close typical road ROW gaps (~20–30 m)
        # while still respecting real zone transitions.
        fhsz_merc  = fhsz_gdf.to_crs("EPSG:3857")
        pt_merc    = project_pt.to_crs("EPSG:3857").geometry.iloc[0]
        distances  = fhsz_merc.geometry.distance(pt_merc)
        nearest_i  = distances.idxmin()
        gap_dist_m = float(distances.loc[nearest_i])
        gap_threshold_m = 50.0

        if gap_dist_m <= gap_threshold_m:
            zone_level   = int(fhsz_gdf.loc[nearest_i, "HAZ_CLASS"])
            in_trigger   = zone_level >= 2
            hazard_zone  = _HAZ_CLASS_TO_ZONE.get(zone_level, "non_fhsz")
            gap_resolved = True
        else:
            detail.update({
                "result":           False,
                "zone_level":       0,
                "hazard_zone":      "non_fhsz",
                "zone_description": "Not in FHSZ",
                "note": f"Point not within any FHSZ polygon; nearest polygon "
                        f"{gap_dist_m:.0f} m away (>{gap_threshold_m:.0f} m threshold).",
            })
            return False, detail
    else:
        zone_level  = int(joined["HAZ_CLASS"].dropna().max())
        in_trigger  = zone_level >= 2
        hazard_zone = _HAZ_CLASS_TO_ZONE.get(zone_level, "non_fhsz")

    zone_desc = {
        0: "Not in FHSZ",
        1: "Zone 1 (Moderate)",
        2: "Zone 2 (High)",
        3: "Zone 3 (Very High)",
    }.get(zone_level, f"Zone {zone_level}")

    detail.update({
        "result":           in_trigger,
        "zone_level":       zone_level,
        "hazard_zone":      hazard_zone,
        "zone_description": zone_desc,
    })
    if gap_resolved:
        detail["note"] = (
            f"FHSZ gap resolved: point fell {gap_dist_m:.1f} m from nearest "
            f"polygon boundary (≤50 m threshold). Assigned {zone_desc} by "
            f"nearest-neighbour. CAL FIRE digitising artefact — road ROW gap."
        )
    return in_trigger, detail

# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Scenario A: Wildland Evacuation Capacity (Standards 1–4) — JOSH v3.2

Legal basis: AB 747 (California Government Code §65302.15), HCM 2022,
NFPA 101 (Life Safety Code) mobilization design basis.

ΔT Standard (v3.2):
  Standard 1 — Project Size:       units >= threshold (scale gate)
  Standard 2 — Evac Routes Served: network buffer → identifies serving EvacuationPaths
  Standard 3 — FHSZ Modifier:      GIS point-in-polygon; sets hazard_zone string which
                                    controls ROAD capacity degradation and ΔT threshold
                                    (FHSZ does NOT affect mobilization in v3.2)
  Standard 4 — ΔT Test:            ΔT = (project_vehicles / bottleneck_effective_capacity) × 60 + egress
                                    Project is DISCRETIONARY if ΔT > threshold for hazard_zone
                                    threshold = safe_egress_window(zone) × max_project_share

Key v3.2 changes from v3.1:
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
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import Point

from models.project import Project
from models.evacuation_path import EvacuationPath
from .base import EvacuationScenario, Tier

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


class WildlandScenario(EvacuationScenario):
    """
    Evaluates wildland evacuation capacity impact (Standards 1–4) using v3.0 ΔT metric.

    Standard 1 (size) gates the analysis.
    Standard 3 (FHSZ modifier) sets project.hazard_zone which controls:
      - ΔT threshold (safe_egress_window × max_project_share by hazard zone)
      - capacity degradation factor (applied upstream in Agent 2 to road segments)
      NOTE (v3.2): FHSZ does NOT affect mobilization. Mobilization is constant 0.90 (NFPA 101).
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
          NOTE (v3.2): FHSZ does NOT affect mobilization rate. Mobilization is constant 0.90.

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

        # Mobilization is constant (NFPA 101 design basis) — not FHSZ-dependent
        project.mobilization_rate = self.config.get("mobilization_rate", 0.90)

        return True, {
            "result":                    True,
            "method":                    "Always applicable; site FHSZ check via GIS point-in-polygon",
            "std3_fhsz_flagged":         fire_zone_result,
            "std3_zone_level":           project.fire_zone_level,
            "std3_zone_desc":            fire_zone_detail.get("zone_description", "Not in FHSZ"),
            "std3_hazard_zone":          project.hazard_zone,
            "std3_mobilization_rate":    project.mobilization_rate,
            "fire_zone_severity_modifier": fire_zone_detail,
            "note": (
                f"FHSZ Zone {project.fire_zone_level} ({project.hazard_zone}) — "
                f"road capacity degradation applied; mobilization unaffected. "
                f"Mobilization rate {project.mobilization_rate:.2f} (NFPA 101 design basis, constant)."
                if fire_zone_result else
                f"Not in FHSZ (hazard_zone=non_fhsz) — no road degradation. "
                f"Mobilization rate {project.mobilization_rate:.2f} (NFPA 101 design basis, constant)."
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

        Method:
          1. Buffer project location by evacuation.serving_route_radius_miles.
          2. Find all evacuation route segment osmids within the buffer.
          3. Filter context["evacuation_paths"] to those whose bottleneck_osmid
             or exit_segment_osmid is within the buffer.
          4. If no paths match proximity filter, use all paths (conservative fallback).

        Returns list[EvacuationPath] for consumption by compute_delta_t().
        Discretion: Zero — algorithmic spatial query.
        """
        evac_cfg     = self.config.get("evacuation", {})
        radius       = evac_cfg.get(
            "serving_route_radius_miles",
            self.config.get("evacuation_route_radius_miles", 0.5),
        )
        analysis_crs = self.city_config.get("analysis_crs", "EPSG:26910")

        lat, lon = project.location_lat, project.location_lon
        project_pt = gpd.GeoDataFrame(
            {"geometry": [Point(lon, lat)]}, crs="EPSG:4326"
        ).to_crs(analysis_crs)

        radius_meters = radius * 1609.344

        # ------------------------------------------------------------------
        # v3.4: Project-origin Dijkstra routing
        # Compute the shortest path from this project's driveway to every city
        # exit node.  Each computed path is, by construction, the optimal route
        # this project's residents would take to safety — no upstream-entry check
        # needed because the path always starts at the project.
        #
        # Also walk the 0.5-mi reachable network for the visualization overlay
        # (reachable_osmids), which shows what roads are within reach of the
        # project regardless of exit direction.
        #
        # Falls back to population-path upstream-entry filter if graph or exit
        # nodes are unavailable (pre-v3.4 data or analysis not yet re-run).
        # ------------------------------------------------------------------
        graph_path = context.get("graph_path")
        G = None  # loaded projected graph (reused for reachability + routing)
        nearest_node = None
        proj_x = project_pt.geometry.iloc[0].x
        proj_y = project_pt.geometry.iloc[0].y
        nearby_osmids: set[str] = set()
        reachable_osmids: set[str] = set()  # full reachable network (for viz)
        method_note = ""

        if graph_path and Path(graph_path).exists():
            try:
                G = ox.load_graphml(graph_path)
                nearest_node = ox.distance.nearest_nodes(G, proj_x, proj_y)

                # Walk the network from the project's nearest node up to radius_meters.
                # Used for the reachable-zone visualization layer on the map.
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
                    f"Project-origin Dijkstra (v3.4, travel-time weight) — "
                    f"fastest path from project site to each regional-network "
                    f"exit node (motorway/trunk/primary at city boundary); "
                    f"weight=length/speed_limit (seconds) per speed_defaults config; "
                    f"{len(reachable_nodes)} nodes within {radius} mi network zone; "
                    f"respects road barriers (I-5, rail, etc.)"
                )
                logger.info(
                    f"  Network proximity: {len(reachable_nodes)} reachable nodes, "
                    f"{len(nearby_osmids)} edge osmids for {project.project_name}"
                )
            except Exception as e:
                logger.warning(f"  Graph load failed ({e}) — falling back to population paths")
                G = None
                nearest_node = None

        if not G:
            # Euclidean buffer fallback (graph unavailable or analysis not yet re-run)
            roads_proj = roads_gdf.to_crs(analysis_crs)
            buffer     = project_pt.geometry.iloc[0].buffer(radius_meters)
            if "is_evacuation_route" not in roads_proj.columns:
                evac_nearby = roads_proj[roads_proj.geometry.intersects(buffer)]
            else:
                evac_only   = roads_proj[roads_proj["is_evacuation_route"] == True]
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

        # Update project display fields (reachable zone for map viz)
        project.serving_route_ids       = list(nearby_osmids)
        project.reachable_network_osmids = list(reachable_osmids)
        project.search_radius_miles     = radius

        # ------------------------------------------------------------------
        # Build osmid → capacity lookup from roads_gdf.
        # Used by project-origin Dijkstra to identify bottlenecks.
        # ------------------------------------------------------------------
        _ZONE_TO_HAZ_CLASS = {"vhfhsz": 3, "high_fhsz": 2, "moderate_fhsz": 1, "non_fhsz": 0}
        osmid_to_eff_cap   = {}
        osmid_to_fhsz      = {}
        osmid_to_rtype     = {}
        osmid_to_hcm       = {}
        osmid_to_deg       = {}
        osmid_to_name      = {}
        osmid_to_lanes     = {}
        osmid_to_speed     = {}
        osmid_to_haz_class = {}
        for _, row in roads_gdf.iterrows():
            oid = row.get("osmid")
            if oid is None:
                continue
            eff = float(row.get("effective_capacity_vph", row.get("capacity_vph", 1000.0)))
            fz  = str(row.get("fhsz_zone", "non_fhsz"))
            rt  = str(row.get("road_type", "two_lane"))
            hcm = float(row.get("capacity_vph", 0.0))
            dg  = float(row.get("hazard_degradation", 1.0))
            nm  = str(row.get("name", ""))
            lc  = int(row.get("lane_count", 0) or 0)
            sp  = int(row.get("speed_limit", 0) or 0)
            hc  = _ZONE_TO_HAZ_CLASS.get(fz, 0)
            for o in (oid if isinstance(oid, list) else [oid]):
                key = str(o)
                osmid_to_eff_cap[key]   = max(osmid_to_eff_cap.get(key, 0), eff)
                osmid_to_fhsz[key]      = fz
                osmid_to_rtype[key]     = rt
                osmid_to_hcm[key]       = hcm
                osmid_to_deg[key]       = dg
                osmid_to_name[key]      = nm
                osmid_to_lanes[key]     = lc
                osmid_to_speed[key]     = sp
                osmid_to_haz_class[key] = hc

        # ------------------------------------------------------------------
        # v3.4: Compute project-origin paths via Dijkstra to each exit node.
        # Deduplication: keep the shortest-distance path to each unique
        # bottleneck segment.  This prevents the same bottleneck from
        # appearing dozens of times (once per nearby exit node) while
        # preserving distinct constraints on different corridors.
        # ------------------------------------------------------------------
        all_evac_paths: list = context.get("evacuation_paths", [])
        project_paths: list[EvacuationPath] = []
        fallback_used = False

        exit_nodes_path = Path(str(graph_path)).parent / "exit_nodes.json" if graph_path else None
        exit_nodes: list = []
        if exit_nodes_path and exit_nodes_path.exists():
            try:
                exit_nodes = json.loads(exit_nodes_path.read_text())
            except Exception as e:
                logger.warning(f"  Could not load exit_nodes.json ({e})")

        # Maximum path length ratio (read from config, default 2.0).
        # Only paths within this multiple of the nearest-exit distance are included.
        # Rational evacuees take the shortest route to safety — paths more than 2×
        # optimal represent routes that would never be chosen when shorter alternatives
        # exist.  This is the legally defensible route-choice bound (config key:
        # evacuation.max_path_length_ratio).
        max_path_ratio = float(
            evac_cfg.get("max_path_length_ratio", 2.0)
        )

        if G is not None and nearest_node is not None and exit_nodes:
            G_undir_full = G.to_undirected()

            # Add travel_time_s edge weight for time-optimal Dijkstra.
            # Evacuation routing is time-critical: a 2-mile freeway (2 min) is
            # categorically faster than a 2-mile residential street (8 min).
            # Dijkstra on travel time finds the fastest escape route — the route
            # a rational evacuee actually takes and the standard traffic engineers
            # use for evacuation modeling.
            # Source: speed_defaults in config (mph); converted to m/s for SI.
            speed_defaults_mph = self.config.get("speed_defaults", {})
            _MPH_TO_MPS = 0.44704  # exact: 1 mph = 0.44704 m/s
            for _u, _v, _ed in G_undir_full.edges(data=True):
                _hw  = _ed.get("highway", "")
                _hw_str = _hw[0] if isinstance(_hw, list) else str(_hw)
                _spd_mph = speed_defaults_mph.get(_hw_str, 25)  # default: 25 mph
                _spd_mps = _spd_mph * _MPH_TO_MPS
                _len_m   = float(_ed.get("length", 0) or 0)
                _ed["travel_time_s"] = _len_m / _spd_mps if _spd_mps > 0 else _len_m

            # WGS84 transformer — converts projected node (x,y) → (lon, lat).
            # Graph CRS stored in G.graph['crs'] (e.g. 'EPSG:26911').
            # Node coords are used for the exact path coordinate chain stored
            # in EvacuationPath.path_wgs84_coords for unambiguous map rendering.
            _graph_crs  = G.graph.get("crs", "EPSG:26911")
            _to_wgs84   = Transformer.from_crs(_graph_crs, "EPSG:4326", always_xy=True)

            # ── Pass 1: compute all paths, record travel time ─────────────
            # Collect raw candidates before time-filtering or dedup.
            # weight="travel_time_s" → Dijkstra finds fastest path, not shortest.
            # Each candidate: (path_travel_time_s, exit_node_id, path_osmids,
            #                  exit_osmid, path_length_m, path_wgs84_coords)
            # travel_time_s drives routing and ratio filter; length_m is for logging.
            # path_wgs84_coords is [[lat, lon], ...] from graph node positions —
            # used directly by the demo map, bypassing osmid-to-geometry lookup.
            # ── Build egress origin list: primary + any additional_egress_points ─
            # Each origin is (graph_node_id, origin_block_group_label).
            # Additional egress points are defined by the city planner in the
            # project YAML as additional_egress: [{lat, lon, label, note}, ...].
            # Each origin runs a full independent Pass 1+2 (Dijkstra to all exits,
            # ratio filter, bottleneck dedup).  Pass 2 is intentionally scoped per
            # origin so the min_travel_time ratio bound is relative to THAT egress
            # point's fastest exit — not polluted by a faster nearby exit on a
            # different egress.  Bottleneck dedup also resets per origin so that a
            # fast primary path cannot suppress a slower additional-egress path to
            # the same bottleneck (they represent physically separate vehicle flows).
            # Methodology: full project_vehicles applied to every origin (conservative
            # — demand splitting not assumed; may be refined in a future version).
            _all_origins: list[tuple[int, str]] = [(nearest_node, "project_origin")]
            for _aei, _aep in enumerate(
                getattr(project, "additional_egress_points", []), 1
            ):
                try:
                    _aep_pt = gpd.GeoDataFrame(
                        geometry=[Point(float(_aep["lon"]), float(_aep["lat"]))],
                        crs="EPSG:4326",
                    ).to_crs(analysis_crs)
                    _aep_x    = _aep_pt.geometry.iloc[0].x
                    _aep_y    = _aep_pt.geometry.iloc[0].y
                    _aep_node = ox.distance.nearest_nodes(G, _aep_x, _aep_y)
                    _all_origins.append((_aep_node, f"project_egress_{_aei}"))
                    logger.info(
                        f"  Additional egress {_aei} "
                        f"({_aep.get('label', 'unlabeled')!r}): "
                        f"snapped to node {_aep_node}"
                    )
                except Exception as _snap_err:
                    logger.warning(
                        f"  Additional egress {_aei} snap failed: {_snap_err}"
                    )

            # ── Pass 1+2 — run independently for each egress origin ───────────
            _FREEWAY_HW = {"motorway", "motorway_link"}

            for _origin_node, _origin_bg in _all_origins:
                candidates: list[tuple] = []

                for exit_node in exit_nodes:
                    exit_node_id = int(exit_node)
                    if exit_node_id == _origin_node:
                        continue
                    try:
                        path_nodes = nx.shortest_path(
                            G_undir_full, _origin_node, exit_node_id,
                            weight="travel_time_s",
                        )
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        continue
                    if len(path_nodes) < 2:
                        continue

                    # Build WGS84 coordinate chain from node positions.
                    # Node (x, y) are in the projected CRS; _to_wgs84 converts to (lon, lat).
                    #
                    # Freeway truncation: stop at the first motorway/motorway_link edge.
                    # Once evacuees reach the freeway mainline they may go north or south —
                    # we cannot predict direction, so we animate only to the on-ramp entry
                    # point and let the map marker convey "→ freeway."  The full path
                    # (osmids, travel_time, bottleneck) is still computed below for ΔT.
                    _cutoff = len(path_nodes)          # default: include all nodes
                    for _fei, (_feu, _fev) in enumerate(zip(path_nodes[:-1], path_nodes[1:])):
                        _feed = G.get_edge_data(_feu, _fev) or G.get_edge_data(_fev, _feu) or {}
                        for _fekd in (_feed.values() if isinstance(_feed, dict) else [_feed]):
                            if str(_fekd.get("highway", "")) in _FREEWAY_HW:
                                _cutoff = _fei + 1      # include node _feu, stop before _fev
                                break
                        if _cutoff < len(path_nodes):
                            break

                    path_wgs84_local: list[list[float]] = []
                    for _nid in path_nodes[:_cutoff]:
                        _nx_x = G.nodes[_nid].get("x", 0)
                        _nx_y = G.nodes[_nid].get("y", 0)
                        _lon, _lat = _to_wgs84.transform(_nx_x, _nx_y)
                        path_wgs84_local.append([_lat, _lon])

                    path_osmids_local: list[str] = []
                    path_length       = 0.0   # metres — for logging only
                    path_travel_time  = 0.0   # seconds — drives filter + dedup
                    exit_osmid = ""
                    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
                        ed = G.get_edge_data(u, v) or G.get_edge_data(v, u)
                        if ed:
                            for kd in (ed.values() if isinstance(ed, dict) else [ed]):
                                oid     = kd.get("osmid")
                                seg_len = float(kd.get("length", 0) or 0)
                                hw_str  = str(kd.get("highway", ""))
                                spd_mph = speed_defaults_mph.get(hw_str, 25)
                                seg_tt  = seg_len / (spd_mph * _MPH_TO_MPS) if spd_mph > 0 else seg_len
                                if oid:
                                    oid_str = str(oid[0]) if isinstance(oid, list) else str(oid)
                                    path_osmids_local.append(oid_str)
                                    path_length      += seg_len
                                    path_travel_time += seg_tt
                                    break
                        if v == exit_node_id or u == exit_node_id:
                            exit_osmid = path_osmids_local[-1] if path_osmids_local else ""

                    if path_osmids_local and path_travel_time > 0:
                        candidates.append(
                            (path_travel_time, exit_node_id, path_osmids_local,
                             exit_osmid, path_length, path_wgs84_local)
                        )

                # ── Pass 2: filter by travel-time ratio, then dedup by bottleneck
                # Route-choice bound: include exits reachable within max_path_ratio ×
                # fastest-exit travel time.  A rational evacuee who can reach safety in
                # T minutes will never take a route that takes > 2T minutes when a
                # shorter alternative exists.  Using travel time (not distance) correctly
                # accounts for road class: a 2-mile freeway is faster than a 1-mile
                # residential street and should be preferred.
                if candidates:
                    min_travel_time = min(c[0] for c in candidates)   # seconds
                    max_allowed     = min_travel_time * max_path_ratio
                    filtered        = [c for c in candidates if c[0] <= max_allowed]
                    excluded        = len(candidates) - len(filtered)
                    if excluded:
                        logger.info(
                            f"  Path filter ({_origin_bg}): {excluded} exit(s) excluded "
                            f"(>{max_path_ratio:.1f}× fastest-exit travel time of "
                            f"{min_travel_time/60:.1f} min); {len(filtered)} remain"
                        )

                    seen_bottlenecks: dict[str, float] = {}  # osmid → fastest travel time (s)
                    for path_travel_time, exit_node_id, path_osmids_local, exit_osmid, path_length, path_wgs84_local in filtered:
                        bottleneck_osmid = min(
                            path_osmids_local,
                            key=lambda o: osmid_to_eff_cap.get(o, 9999),
                            default=path_osmids_local[0],
                        )
                        eff_cap = osmid_to_eff_cap.get(bottleneck_osmid, 0.0)
                        if eff_cap <= 0:
                            continue

                        # Dedup: keep only the fastest-travel-time path to each unique bottleneck.
                        # Travel time (not distance) is the dedup key because Dijkstra now routes
                        # on time — two paths to the same bottleneck may have different lengths
                        # but the faster one is the correct evacuation route to preserve.
                        prior_tt = seen_bottlenecks.get(bottleneck_osmid)
                        if prior_tt is not None and path_travel_time >= prior_tt:
                            continue
                        seen_bottlenecks[bottleneck_osmid] = path_travel_time

                        path_id = f"proj_{_origin_node}_{exit_node_id}"
                        evac_path = EvacuationPath(
                            path_id=path_id,
                            origin_block_group=_origin_bg,
                            exit_segment_osmid=exit_osmid,
                            bottleneck_osmid=bottleneck_osmid,
                            bottleneck_name=osmid_to_name.get(bottleneck_osmid, ""),
                            bottleneck_fhsz_zone=osmid_to_fhsz.get(bottleneck_osmid, "non_fhsz"),
                            bottleneck_road_type=osmid_to_rtype.get(bottleneck_osmid, "two_lane"),
                            bottleneck_hcm_capacity_vph=osmid_to_hcm.get(bottleneck_osmid, eff_cap),
                            bottleneck_hazard_degradation=osmid_to_deg.get(bottleneck_osmid, 1.0),
                            bottleneck_effective_capacity_vph=eff_cap,
                            bottleneck_lane_count=osmid_to_lanes.get(bottleneck_osmid, 0),
                            bottleneck_speed_limit=osmid_to_speed.get(bottleneck_osmid, 0),
                            bottleneck_haz_class=osmid_to_haz_class.get(bottleneck_osmid, 0),
                            path_osmids=path_osmids_local,
                            path_wgs84_coords=path_wgs84_local,
                        )
                        project_paths.append(evac_path)

            logger.info(
                f"  Project-origin Dijkstra (travel-time weight): {len(project_paths)} "
                f"unique-bottleneck paths for {project.project_name} "
                f"({len(_all_origins)} egress origin(s); "
                f"ratio ≤{max_path_ratio:.1f}× fastest exit, from {len(exit_nodes)} exits)"
            )

        if project_paths:
            serving_paths = project_paths
        else:
            # Fallback to population paths with upstream-entry filter
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
                    f"({len(serving_paths)} paths) for {project.project_name}"
                )

        # Build serving_routes list from roads_gdf for audit trail.
        # For v3.4 project-origin paths, show the union of all computed path osmids
        # (the actual segments the project would traverse to exits).
        # For fallback cases, show the nearby_osmids proximity zone.
        if project_paths:
            path_osmids_union: set[str] = set()
            for p in project_paths:
                path_osmids_union.update(str(o) for o in getattr(p, "path_osmids", []))
            audit_osmids = path_osmids_union
        else:
            audit_osmids = nearby_osmids

        roads_wgs84 = roads_gdf if roads_gdf.crs and roads_gdf.crs.to_epsg() == 4326 \
                      else roads_gdf.to_crs("EPSG:4326")
        serving_route_details = []
        for _, row in roads_wgs84.iterrows():
            osmid_val = row.get("osmid")
            osmid_strs = [str(osmid_val)] if not isinstance(osmid_val, list) \
                         else [str(o) for o in osmid_val]
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

        detail = {
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
        return serving_paths, detail

    # ------------------------------------------------------------------
    # Override reason builders to include fire zone / ΔT context
    # ------------------------------------------------------------------

    def _reason_discretionary(self, project: Project, step5: dict) -> str:
        max_dt    = step5.get("max_delta_t_minutes", 0.0)
        threshold = step5.get("threshold_minutes", 0.0)
        hz        = step5.get("hazard_zone", "non_fhsz")
        mob       = step5.get("mobilization_rate", 0.90)
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
            f"Mobilization: {mob:.2f} (NFPA 101 design basis, constant). "
            f"Discretionary review required. Legal basis: {self.legal_basis}."
        )

    def _reason_fallback(self, project: Project, step3: dict, step5: dict) -> str:
        n_paths   = step3.get("serving_paths_count", 0)
        max_dt    = step5.get("max_delta_t_minutes", 0.0)
        threshold = step5.get("threshold_minutes", 0.0)
        hz        = step5.get("hazard_zone", "non_fhsz")
        mob       = step5.get("mobilization_rate", 0.90)
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
            f"Mobilization: {mob:.2f} (NFPA 101 design basis, constant). "
            f"Ministerial approval with standard conditions applied automatically. "
            f"Legal basis: {self.legal_basis}."
        )


# ---------------------------------------------------------------------------
# Helper functions (module-level — reusable and independently testable)
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
    detail["hazard_zone"] contains the canonical zone key for mobilization_rate lookup.

    HAZ_CLASS mapping:
      3 → "vhfhsz" (Very High)
      2 → "high_fhsz" (High) — trigger zone
      1 → "moderate_fhsz" (Moderate)
      0 → "non_fhsz"

    in_trigger_zone is True for HAZ_CLASS >= 2 (High and Very High).
    Moderate FHSZ (HAZ_CLASS=1) sets hazard_zone="moderate_fhsz" but returns False
    (does not trigger FHSZ status; mobilization_rate applied via hazard_zone lookup).
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
        "role":        "Sets hazard_zone for mobilization_rate and ΔT threshold lookup",
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

    if joined.empty or joined["HAZ_CLASS"].isna().all():
        detail.update({
            "result":           False,
            "zone_level":       0,
            "hazard_zone":      "non_fhsz",
            "zone_description": "Not in FHSZ",
        })
        return False, detail

    zone_level  = int(joined["HAZ_CLASS"].dropna().max())
    in_trigger  = zone_level >= 2
    hazard_zone = _HAZ_CLASS_TO_ZONE.get(zone_level, "non_fhsz")

    detail.update({
        "result":           in_trigger,
        "zone_level":       zone_level,
        "hazard_zone":      hazard_zone,
        "zone_description": {
            0: "Not in FHSZ",
            1: "Zone 1 (Moderate)",
            2: "Zone 2 (High)",
            3: "Zone 3 (Very High)",
        }.get(zone_level, f"Zone {zone_level}"),
    })
    return in_trigger, detail

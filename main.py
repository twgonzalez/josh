# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Fire Evacuation Capacity Analysis System — CLI Entry Point

Usage:
  uv run python main.py analyze --city "Berkeley" --state "CA"
  uv run python main.py evaluate --city "Berkeley" --lat 37.87 --lon -122.27 --units 75
  uv run python main.py analyze --city "Berkeley" --state "CA" --refresh
"""
import logging
import sys
from pathlib import Path

import click
import pandas as pd
import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

console = Console()


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(city: str) -> tuple[dict, dict]:
    """Load parameters.yaml and city-specific config, applying city overrides."""
    base_dir = Path(__file__).parent

    params_path = base_dir / "config" / "parameters.yaml"
    if not params_path.exists():
        console.print(f"[red]ERROR: {params_path} not found.[/red]")
        sys.exit(1)
    with open(params_path) as f:
        config = yaml.safe_load(f)

    city_slug = city.lower().replace(" ", "_")
    city_path = base_dir / "config" / "cities" / f"{city_slug}.yaml"
    if not city_path.exists():
        console.print(f"[yellow]Warning: No city config found at {city_path}. Using defaults.[/yellow]")
        city_config = {"city_name": city, "osmnx_place": f"{city}, USA"}
    else:
        with open(city_path) as f:
            city_config = yaml.safe_load(f)

    # Apply city-specific overrides
    overrides = city_config.get("overrides") or {}
    if overrides:
        config.update(overrides)

    return config, city_config


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool):
    """Fire Evacuation Capacity Analysis System."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, show_time=False)],
    )


@cli.command()
@click.option("--city", required=True, help='City name (e.g. "Berkeley")')
@click.option("--state", default="CA", show_default=True, help="State abbreviation")
@click.option("--refresh", is_flag=True, help="Force re-download of all data (ignore cache)")
def analyze(city: str, state: str, refresh: bool):
    """
    Download data and run capacity analysis for a city.

    Outputs:
      - data/{city}/  -- cached source data
      - output/{city}/routes.csv -- evacuation routes with v/c ratios
    """
    from agents.data_acquisition import acquire_data
    from agents.capacity_analysis import analyze_capacity

    config, city_config = load_config(city)

    base_dir = Path(__file__).parent
    city_slug = city.lower().replace(" ", "_")
    data_dir = base_dir / "data" / city_slug
    output_dir = base_dir / "output" / city_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold cyan]Analyzing {city}, {state}[/bold cyan]")

    # Agent 1: Data Acquisition
    console.print("\n[bold]Step 1: Data Acquisition[/bold]")
    with console.status("Downloading/loading datasets..."):
        datasets = acquire_data(
            city=city,
            state=state,
            config=config,
            city_config=city_config,
            data_dir=data_dir,
            force_refresh=refresh,
        )

    _print_data_summary(datasets)

    # Agent 2: Capacity Analysis
    console.print("\n[bold]Step 2: Capacity Analysis[/bold]")
    block_groups_gdf = datasets.get("block_groups")
    with console.status("Running HCM calculations and route identification..."):
        roads_gdf, evacuation_paths = analyze_capacity(
            roads_gdf=datasets["roads"],
            fhsz_gdf=datasets["fhsz"],
            boundary_gdf=datasets["boundary"],
            config=config,
            city_config=city_config,
            block_groups_gdf=block_groups_gdf,
            data_dir=data_dir,
        )

    console.print(f"  {len(evacuation_paths)} bottleneck paths computed.")

    # Save results
    routes_path = output_dir / "routes.csv"
    evac_routes = roads_gdf[roads_gdf["is_evacuation_route"] == True].copy()

    output_cols = [
        "name", "highway", "road_type", "lane_count", "speed_limit",
        "capacity_vph", "fhsz_zone", "hazard_degradation", "effective_capacity_vph",
        "baseline_demand_vph", "vc_ratio", "los",
        "connectivity_score", "catchment_units", "demand_source",
        "catchment_hu", "catchment_employees",
        "resident_demand_vph", "employee_demand_vph", "student_demand_vph",
        "length_meters", "lane_count_estimated", "speed_estimated", "aadt_estimated",
    ]
    save_cols = [c for c in output_cols if c in evac_routes.columns]
    evac_routes[save_cols].to_csv(routes_path, index=False)
    console.print(f"  Routes saved to: [cyan]{routes_path}[/cyan]")

    _print_routes_table(evac_routes, config)

    console.print(
        f"\n[green bold]Analysis complete.[/green bold] "
        f"{len(evac_routes)} evacuation route segments identified."
    )


@cli.command()
@click.option("--city", required=True, help="City name (must match a prior analyze run)")
@click.option("--lat", required=True, type=float, help="Project latitude")
@click.option("--lon", required=True, type=float, help="Project longitude")
@click.option("--units", required=True, type=int, help="Number of dwelling units")
@click.option("--stories", default=0, type=int, show_default=True,
              help="Number of above-grade stories (for NFPA 101 egress penalty)")
@click.option("--name", default="", help="Project name (optional)")
@click.option("--address", default="", help="Project address (optional)")
@click.option("--apn", default="", help="Assessor Parcel Number (optional)")
def evaluate(city: str, lat: float, lon: float, units: int, stories: int,
             name: str, address: str, apn: str):
    """
    Evaluate a proposed project -- produce ministerial/discretionary determination.

    Requires a prior `analyze` run to have generated data/{city}/ files.

    Outputs:
      - output/{city}/determination_{lat}_{lon}.txt -- full audit trail
    """
    import geopandas as gpd
    from agents.objective_standards import evaluate_project, generate_audit_trail
    from models.project import Project

    config, city_config = load_config(city)

    base_dir = Path(__file__).parent
    city_slug = city.lower().replace(" ", "_")
    data_dir = base_dir / "data" / city_slug
    output_dir = base_dir / "output" / city_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    roads_path    = data_dir / "roads.gpkg"
    fhsz_path     = data_dir / "fhsz.geojson"
    boundary_path = data_dir / "boundary.geojson"

    missing = [p for p in [roads_path, fhsz_path, boundary_path] if not p.exists()]
    if missing:
        console.print(f"[red]ERROR: Missing data files: {missing}[/red]")
        console.print(f'Run first: [cyan]uv run python main.py analyze --city "{city}"[/cyan]')
        sys.exit(1)

    console.rule(f"[bold cyan]Evaluating Project in {city}[/bold cyan]")
    if name:
        console.print(f"  Project: {name}")
    console.print(f"  Location: {lat}, {lon}")
    console.print(f"  Units: {units}  Stories: {stories}")

    block_groups_path    = data_dir / "block_groups.geojson"
    evac_paths_path      = data_dir / "evacuation_paths.json"

    with console.status("Loading cached data..."):
        roads_gdf        = gpd.read_file(roads_path, layer="roads")
        fhsz_gdf         = gpd.read_file(fhsz_path)
        boundary_gdf     = gpd.read_file(boundary_path)
        block_groups_gdf = gpd.read_file(block_groups_path) if block_groups_path.exists() else None
        evacuation_paths = _load_evacuation_paths(evac_paths_path)

    # If roads don't have capacity columns yet, run capacity analysis first
    if "effective_capacity_vph" not in roads_gdf.columns or "demand_source" not in roads_gdf.columns:
        console.print("[yellow]Roads not yet analyzed — running capacity analysis...[/yellow]")
        from agents.capacity_analysis import analyze_capacity
        roads_gdf, evacuation_paths = analyze_capacity(
            roads_gdf, fhsz_gdf, boundary_gdf, config, city_config,
            block_groups_gdf=block_groups_gdf,
            data_dir=data_dir,
        )

    project = Project(
        location_lat=lat,
        location_lon=lon,
        address=address,
        dwelling_units=units,
        stories=stories,
        project_name=name,
        apn=apn,
    )

    console.print("\n[bold]Running Objective Standards Engine...[/bold]")
    project, audit = evaluate_project(
        project=project,
        roads_gdf=roads_gdf,
        fhsz_gdf=fhsz_gdf,
        config=config,
        city_config=city_config,
        evacuation_paths=evacuation_paths,
    )

    # Save audit trail
    lat_str = f"{lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{lon:.4f}".replace(".", "_").replace("-", "n")
    det_filename = f"determination_{lat_str}_{lon_str}_{units}u.txt"
    audit_path = output_dir / det_filename
    generate_audit_trail(project, audit, audit_path)

    # Save determination brief
    from agents.visualization.brief_v3 import create_determination_brief_v3

    brief_path = output_dir / f"brief_v3_{lat_str}_{lon_str}_{units}u.html"
    create_determination_brief_v3(project, audit, config, city_config, brief_path)

    _print_determination(project, audit)
    console.print(f"\n  Full audit trail: [cyan]{audit_path}[/cyan]")
    console.print(f"  Determination brief: [cyan]{brief_path}[/cyan]")
    console.print(f"  Open with: [dim]open {brief_path}[/dim]")




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_evacuation_paths(paths_file: Path) -> list:
    """Load pre-computed EvacuationPath objects from JSON, or return empty list."""
    if not paths_file.exists():
        return []
    try:
        import json
        from models.evacuation_path import EvacuationPath
        data = json.loads(paths_file.read_text())
        paths = []
        for d in data:
            try:
                paths.append(EvacuationPath(
                    path_id=d.get("path_id", ""),
                    origin_block_group=d.get("origin_block_group", ""),
                    exit_segment_osmid=d.get("exit_segment_osmid", ""),
                    bottleneck_osmid=d.get("bottleneck_osmid", ""),
                    bottleneck_name=d.get("bottleneck_name", ""),
                    bottleneck_fhsz_zone=d.get("bottleneck_fhsz_zone", "non_fhsz"),
                    bottleneck_road_type=d.get("bottleneck_road_type", "two_lane"),
                    bottleneck_hcm_capacity_vph=float(d.get("bottleneck_hcm_capacity_vph", 0)),
                    bottleneck_hazard_degradation=float(d.get("bottleneck_hazard_degradation", 1.0)),
                    bottleneck_effective_capacity_vph=float(d.get("bottleneck_effective_capacity_vph", 0)),
                    catchment_units=float(d.get("catchment_units", 0)),
                    baseline_demand_vph=float(d.get("baseline_demand_vph", 0)),
                    path_osmids=d.get("path_osmids", []),
                ))
            except Exception:
                continue
        return paths
    except Exception as e:
        logging.getLogger(__name__).debug(f"Could not load evacuation_paths.json: {e}")
        return []


# ---------------------------------------------------------------------------
# Rich output helpers
# ---------------------------------------------------------------------------

def _print_data_summary(datasets: dict):
    """Print a summary table of downloaded datasets."""
    table = Table(title="Datasets", show_header=True, header_style="bold blue")
    table.add_column("Dataset")
    table.add_column("Features", justify="right")
    table.add_column("CRS")

    for name, gdf in datasets.items():
        if gdf is None or (hasattr(gdf, "empty") and gdf.empty):
            table.add_row(name, "0", "—")
        else:
            table.add_row(name, str(len(gdf)), str(gdf.crs))
    console.print(table)


def _print_routes_table(evac_routes, config: dict):
    """Print top evacuation routes sorted by v/c ratio."""
    if evac_routes.empty:
        console.print("[yellow]No evacuation routes identified.[/yellow]")
        return

    threshold = config.get("vc_threshold", 0.95)

    table = Table(
        title="Evacuation Routes (top 20 by effective capacity, descending)",
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("Route Name", min_width=20)
    table.add_column("Type")
    table.add_column("Lanes", justify="right")
    table.add_column("Cap (vph)", justify="right")
    table.add_column("FHSZ", justify="center")
    table.add_column("Deg", justify="right")
    table.add_column("Eff Cap", justify="right")
    table.add_column("v/c", justify="right")
    table.add_column("LOS")

    if "effective_capacity_vph" in evac_routes.columns:
        sorted_routes = evac_routes.sort_values("effective_capacity_vph", ascending=True).head(20)
    else:
        sorted_routes = evac_routes.sort_values("vc_ratio", ascending=False).head(20)

    for _, row in sorted_routes.iterrows():
        vc   = row.get("vc_ratio", 0)
        los  = row.get("los", "")
        deg  = row.get("hazard_degradation", 1.0)
        fhsz = row.get("fhsz_zone", "non")
        eff  = row.get("effective_capacity_vph", row.get("capacity_vph", 0))
        style = "red" if deg < 0.5 else ("yellow" if deg < 1.0 else "green")

        table.add_row(
            str(row.get("name", ""))[:30] or "Unnamed",
            str(row.get("road_type", "")),
            str(row.get("lane_count", "")),
            f"{row.get('capacity_vph', 0):.0f}",
            fhsz[:8],
            f"[{style}]{deg:.2f}[/{style}]",
            f"{eff:.0f}",
            f"{vc:.3f}",
            los,
        )

    console.print(table)


def _print_determination(project, audit: dict):
    """Print the final determination result prominently."""
    det = project.determination
    _TIER_COLOR = {
        "DISCRETIONARY":                     "red",
        "MINISTERIAL WITH STANDARD CONDITIONS": "yellow",
        "MINISTERIAL":                       "green",
    }
    _TIER_COLOR_DIM = {
        "DISCRETIONARY":                     "red",
        "MINISTERIAL WITH STANDARD CONDITIONS": "yellow",
        "MINISTERIAL":                       "green",
        "NOT_APPLICABLE":                    "dim",
    }
    color = _TIER_COLOR.get(det, "white")

    console.print()
    console.print(Panel(
        f"[bold {color}]{det}[/bold {color}]\n\n{project.determination_reason}",
        title="[bold]Final Determination[/bold]",
        border_style=color,
    ))

    # Per-scenario results table (one row per scenario)
    table = Table(title="Scenario Results (5-Step ΔT Algorithm)", show_header=True, header_style="bold")
    table.add_column("Scenario", min_width=20)
    table.add_column("Tier")
    table.add_column("Triggered")
    table.add_column("Step Details")

    for sname, sdata in audit.get("scenarios", {}).items():
        stier     = sdata.get("tier", "")
        triggered = sdata.get("triggered", False)
        steps     = sdata.get("steps", {})
        sc        = _TIER_COLOR_DIM.get(stier, "white")

        step_parts = []
        s1 = steps.get("step1_applicability", {})
        s2 = steps.get("step2_scale", {})
        s3 = steps.get("step3_routes", {})
        s5 = steps.get("step5_delta_t", {})

        if stier == "NOT_APPLICABLE":
            note = sdata.get("reason", s1.get("note", "Not applicable"))
            step_parts.append(str(note)[:55])
        else:
            if s2:
                step_parts.append(
                    f"Size {s2.get('dwelling_units')}≥{s2.get('threshold')}: "
                    f"{'✓' if s2.get('result') else '✗'}"
                )
            if s3:
                step_parts.append(f"Paths: {s3.get('serving_paths_count', 0)}")
            if s5:
                step_parts.append(
                    f"ΔT max {s5.get('max_delta_t_minutes', 0):.1f}/{s5.get('threshold_minutes', 6.0):.2f} min"
                )
            fz = s1.get("fire_zone_severity_modifier", {})
            if fz:
                step_parts.append(f"Zone: {fz.get('hazard_zone', 'non_fhsz')}")

        table.add_row(
            sname,
            f"[{sc}]{stier}[/{sc}]",
            f"[{'red' if triggered else 'green'}]{'YES' if triggered else 'NO'}[/{'red' if triggered else 'green'}]",
            " | ".join(step_parts),
        )

    console.print(table)

    d      = audit.get("determination", {})
    max_dt = project.max_delta_t() if hasattr(project, "max_delta_t") else 0.0
    console.print(
        f"\n  [dim]Peak-hour vehicles: {project.project_vehicles_peak_hour:.1f} vph · "
        f"Hazard zone: {getattr(project, 'hazard_zone', 'non_fhsz')} · "
        f"Max ΔT: {max_dt:.2f} min · "
        f"Egress: {getattr(project, 'egress_minutes', 0):.1f} min · "
        f"Paths flagged: {project.flagged_path_count() if hasattr(project, 'flagged_path_count') else 0}[/dim]"
    )
    console.print(
        f"  [dim]Aggregation: {d.get('logic', '')}[/dim]"
    )


@cli.command()
@click.option("--city", required=True, help="City name (must match a prior analyze run)")
@click.option("--state", default="CA", show_default=True, help="State abbreviation")
@click.option(
    "--projects", "projects_file", default=None,
    help="Path to projects YAML (default: config/projects/{city}_demo.yaml)",
)
@click.option("--output", "output_name", default="demo_map", show_default=True,
              help="Output filename stem (no extension)")
def demo(city: str, state: str, projects_file: str, output_name: str):
    """
    Multi-project demo: evaluate a batch of projects and generate a comparison map.

    Loads a YAML list of projects, evaluates each against the city's evacuation
    network, prints a summary table, and saves an interactive HTML map where each
    project is a toggleable layer — useful for showing city planners the difference
    between ministerial (green) and discretionary (red) outcomes.

    Requires a prior `analyze` run to have generated data/{city}/ files.

    Example:
      uv run python main.py demo --city "Berkeley"
    """
    import geopandas as gpd
    from agents.objective_standards import evaluate_project
    from agents.visualization import create_demo_map
    from models.project import Project

    config, city_config = load_config(city)
    base_dir = Path(__file__).parent
    city_slug = city.lower().replace(" ", "_")
    data_dir = base_dir / "data" / city_slug
    output_dir = base_dir / "output" / city_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve projects file
    if projects_file is None:
        projects_file = base_dir / "config" / "projects" / f"{city_slug}_demo.yaml"
    else:
        projects_file = Path(projects_file)

    if not Path(projects_file).exists():
        console.print(f"[red]ERROR: Projects file not found: {projects_file}[/red]")
        console.print(
            f"Create a YAML at that path with a [cyan]projects:[/cyan] list, or run "
            f"with the default Berkeley demo at [cyan]config/projects/berkeley_demo.yaml[/cyan]."
        )
        sys.exit(1)

    with open(projects_file) as f:
        demo_cfg = yaml.safe_load(f)

    project_defs = demo_cfg.get("projects", [])
    demo_title = demo_cfg.get("description", f"{city} Fire Evacuation Demo")

    if not project_defs:
        console.print("[red]ERROR: No projects defined in the YAML file.[/red]")
        sys.exit(1)

    console.rule(f"[bold cyan]{demo_title}[/bold cyan]")
    console.print(f"  {len(project_defs)} project(s) to evaluate\n")

    # ── Load cached city data ──────────────────────────────────────────────
    roads_path       = data_dir / "roads.gpkg"
    fhsz_path        = data_dir / "fhsz.geojson"
    boundary_path    = data_dir / "boundary.geojson"
    block_groups_path = data_dir / "block_groups.geojson"

    missing = [p for p in [roads_path, fhsz_path, boundary_path] if not p.exists()]
    if missing:
        console.print(f"[red]ERROR: Missing data files: {[str(p) for p in missing]}[/red]")
        console.print(f'Run first: [cyan]uv run python main.py analyze --city "{city}"[/cyan]')
        sys.exit(1)

    with console.status("Loading cached data..."):
        roads_gdf      = gpd.read_file(roads_path, layer="roads")
        fhsz_gdf       = gpd.read_file(fhsz_path)
        boundary_gdf   = gpd.read_file(boundary_path)
        block_groups_gdf = (
            gpd.read_file(block_groups_path) if block_groups_path.exists() else None
        )

    # Load pre-computed evacuation paths
    evac_paths_path  = data_dir / "evacuation_paths.json"
    evacuation_paths = _load_evacuation_paths(evac_paths_path)

    # Run capacity analysis if the cached roads don't yet have effective_capacity_vph
    if "effective_capacity_vph" not in roads_gdf.columns or "demand_source" not in roads_gdf.columns:
        console.print("[yellow]Roads not yet analyzed — running capacity analysis...[/yellow]")
        from agents.capacity_analysis import analyze_capacity
        roads_gdf, evacuation_paths = analyze_capacity(
            roads_gdf, fhsz_gdf, boundary_gdf, config, city_config,
            block_groups_gdf=block_groups_gdf,
            data_dir=data_dir,
        )

    # ── Evaluate each project ──────────────────────────────────────────────
    evaluated: list[Project] = []
    audits: list[dict] = []
    _TIER_RICH = {
        "DISCRETIONARY":                     "bold red",
        "MINISTERIAL WITH STANDARD CONDITIONS": "bold yellow",
        "MINISTERIAL":                       "bold green",
    }

    for i, pdef in enumerate(project_defs, 1):
        name    = pdef.get("name", f"Project {i}")
        lat     = float(pdef["lat"])
        lon     = float(pdef["lon"])
        units   = int(pdef["units"])
        stories = int(pdef.get("stories", 0))
        address = pdef.get("address", "")

        console.print(
            f"  [{i}/{len(project_defs)}] [bold]{name}[/bold]  "
            f"({units} units, {stories} stories · {lat:.4f}, {lon:.4f})"
        )

        project = Project(
            location_lat=lat,
            location_lon=lon,
            address=address,
            dwelling_units=units,
            stories=stories,
            project_name=name,
        )
        project, audit = evaluate_project(
            project=project,
            roads_gdf=roads_gdf,
            fhsz_gdf=fhsz_gdf,
            config=config,
            city_config=city_config,
            evacuation_paths=evacuation_paths,
        )
        evaluated.append(project)
        audits.append(audit)

        det    = project.determination
        style  = _TIER_RICH.get(det, "white")
        n_srv  = len(project.serving_route_ids or [])
        n_flg  = project.flagged_path_count() if hasattr(project, "flagged_path_count") else 0
        max_dt = project.max_delta_t() if hasattr(project, "max_delta_t") else 0.0
        console.print(
            f"     [{style}]{det}[/{style}]  "
            f"[dim]{n_srv} segments · {n_flg} paths flagged · max ΔT {max_dt:.1f} min[/dim]"
        )

        # Regression check: warn if result differs from expected_tier in the YAML.
        # This catches methodology regressions without requiring a separate test suite.
        expected_tier = pdef.get("expected_tier", "").strip().upper()
        actual_tier   = det.strip().upper()
        if expected_tier and actual_tier != expected_tier:
            console.print(
                f"     [bold red]⚠ REGRESSION: expected [white]{expected_tier}[/white] "
                f"got [white]{actual_tier}[/white][/bold red]"
            )

        # Generate determination brief and audit trail so all demo links resolve.
        from agents.visualization.brief_v3 import create_determination_brief_v3
        from agents.objective_standards import generate_audit_trail
        lat_str = f"{lat:.4f}".replace(".", "_").replace("-", "n")
        lon_str = f"{lon:.4f}".replace(".", "_").replace("-", "n")
        brief_path = output_dir / f"brief_v3_{lat_str}_{lon_str}_{units}u.html"
        create_determination_brief_v3(project, audit, config, city_config, brief_path)
        audit_path = output_dir / f"determination_{lat_str}_{lon_str}_{units}u.txt"
        generate_audit_trail(project, audit, audit_path)

    # ── Summary table ──────────────────────────────────────────────────────
    console.print()
    _print_demo_summary(evaluated, config)

    # ── Generate map ───────────────────────────────────────────────────────
    console.print("\n[bold]Generating demo map...[/bold]")
    map_path = output_dir / f"{output_name}.html"
    create_demo_map(
        projects=evaluated,
        roads_gdf=roads_gdf,
        fhsz_gdf=fhsz_gdf,
        boundary_gdf=boundary_gdf,
        config=config,
        output_path=map_path,
        demo_title=demo_title,
        audits=audits,
        evacuation_paths=evacuation_paths,
    )
    console.print(f"  Map saved: [cyan]{map_path}[/cyan]")
    console.print(f"  Open with: [dim]open {map_path}[/dim]")


# ---------------------------------------------------------------------------
# Rich output helpers
# ---------------------------------------------------------------------------

def _print_demo_summary(projects: list, config: dict):
    """Print a multi-project comparison table."""
    unit_threshold = config.get("unit_threshold", 15)

    table = Table(
        title="Demo Project Summary (v3.2 ΔT Standard)",
        show_header=True,
        header_style="bold blue",
        show_lines=False,
    )
    table.add_column("Project", min_width=22)
    table.add_column("Units", justify="right")
    table.add_column("Std 1\n(size)", justify="center")
    table.add_column("Hazard\nZone", justify="center")
    table.add_column("Mob\nRate", justify="right")
    table.add_column("Peak Veh\n(vph)", justify="right")
    table.add_column("Max ΔT\n(min)", justify="right")
    table.add_column("Paths\nFlagged", justify="right")
    table.add_column("Determination")

    _TIER_COLOR = {
        "DISCRETIONARY":                     "red",
        "MINISTERIAL WITH STANDARD CONDITIONS": "yellow",
        "MINISTERIAL":                       "green",
    }

    for p in projects:
        det     = p.determination or "UNKNOWN"
        color   = _TIER_COLOR.get(det, "white")
        std1    = "[green]✓[/green]" if p.meets_size_threshold else "[dim]✗[/dim]"
        hz      = getattr(p, "hazard_zone", "non_fhsz")
        mob     = getattr(p, "mobilization_rate", 0.0)
        max_dt  = p.max_delta_t() if hasattr(p, "max_delta_t") else 0.0
        n_flagged = p.flagged_path_count() if hasattr(p, "flagged_path_count") else 0
        fzone   = (f"[red]{hz[:8]}[/red]" if p.in_fire_zone else f"[dim]{hz[:8]}[/dim]")
        table.add_row(
            str(p.project_name)[:24],
            str(p.dwelling_units),
            std1,
            fzone,
            f"{mob:.2f}",
            f"{p.project_vehicles_peak_hour:.0f}",
            f"[{'red' if n_flagged > 0 else 'green'}]{max_dt:.1f}[/{'red' if n_flagged > 0 else 'green'}]",
            str(n_flagged),
            f"[{color} bold]{det}[/{color} bold]",
        )

    console.print(table)


if __name__ == "__main__":
    cli()

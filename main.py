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
    """Load parameters.yaml and city-specific config."""
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
        roads_gdf = analyze_capacity(
            roads_gdf=datasets["roads"],
            fhsz_gdf=datasets["fhsz"],
            boundary_gdf=datasets["boundary"],
            config=config,
            city_config=city_config,
            block_groups_gdf=block_groups_gdf,
        )

    # Save results
    routes_path = output_dir / "routes.csv"
    evac_routes = roads_gdf[roads_gdf["is_evacuation_route"] == True].copy()

    output_cols = [
        "name", "highway", "road_type", "lane_count", "speed_limit",
        "capacity_vph", "baseline_demand_vph", "vc_ratio", "los",
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
@click.option("--name", default="", help="Project name (optional)")
@click.option("--address", default="", help="Project address (optional)")
@click.option("--apn", default="", help="Assessor Parcel Number (optional)")
@click.option("--map", "generate_map", is_flag=True, help="Generate interactive HTML map")
def evaluate(city: str, lat: float, lon: float, units: int,
             name: str, address: str, apn: str, generate_map: bool):
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

    # Check that analyze has been run
    roads_path = data_dir / "roads.gpkg"
    fhsz_path = data_dir / "fhsz.geojson"
    boundary_path = data_dir / "boundary.geojson"

    missing = [p for p in [roads_path, fhsz_path, boundary_path] if not p.exists()]
    if missing:
        console.print(f"[red]ERROR: Missing data files: {missing}[/red]")
        console.print(f'Run first: [cyan]uv run python main.py analyze --city "{city}"[/cyan]')
        sys.exit(1)

    console.rule(f"[bold cyan]Evaluating Project in {city}[/bold cyan]")
    console.print(f"  Location: {lat}, {lon}")
    console.print(f"  Units: {units}")

    block_groups_path = data_dir / "block_groups.geojson"

    with console.status("Loading cached data..."):
        roads_gdf = gpd.read_file(roads_path, layer="roads")
        fhsz_gdf = gpd.read_file(fhsz_path)
        boundary_gdf = gpd.read_file(boundary_path)
        block_groups_gdf = gpd.read_file(block_groups_path) if block_groups_path.exists() else None

    # If roads don't have capacity columns yet, run capacity analysis first
    if "vc_ratio" not in roads_gdf.columns or "demand_source" not in roads_gdf.columns:
        console.print("[yellow]Routes not yet analyzed -- running capacity analysis...[/yellow]")
        from agents.capacity_analysis import analyze_capacity
        roads_gdf = analyze_capacity(
            roads_gdf, fhsz_gdf, boundary_gdf, config, city_config,
            block_groups_gdf=block_groups_gdf,
        )

    project = Project(
        location_lat=lat,
        location_lon=lon,
        address=address,
        dwelling_units=units,
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
    )

    # Save audit trail
    lat_str = f"{lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{lon:.4f}".replace(".", "_").replace("-", "n")
    det_filename = f"determination_{lat_str}_{lon_str}.txt"
    audit_path = output_dir / det_filename
    generate_audit_trail(project, audit, audit_path)

    _print_determination(project, audit)
    console.print(f"\n  Full audit trail: [cyan]{audit_path}[/cyan]")

    if generate_map:
        console.print("\n[bold]Generating map...[/bold]")
        from agents.visualization import create_evaluation_map
        map_filename = f"map_{lat_str}_{lon_str}.html"
        map_path = output_dir / map_filename
        create_evaluation_map(
            project=project,
            roads_gdf=roads_gdf,
            fhsz_gdf=fhsz_gdf,
            boundary_gdf=boundary_gdf,
            config=config,
            output_path=map_path,
            audit=audit,
        )
        console.print(f"  Map saved: [cyan]{map_path}[/cyan]")
        console.print(f"  Open with: [dim]open {map_path}[/dim]")


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

    threshold = config.get("vc_threshold", 0.80)

    table = Table(
        title="Evacuation Routes (top 20 by v/c ratio)",
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("Route Name", min_width=20)
    table.add_column("Type")
    table.add_column("Lanes", justify="right")
    table.add_column("Cap (vph)", justify="right")
    table.add_column("Demand (vph)", justify="right")
    table.add_column("Catchment HU", justify="right")
    table.add_column("v/c", justify="right")
    table.add_column("LOS")
    table.add_column("Src")

    sorted_routes = evac_routes.sort_values("vc_ratio", ascending=False).head(20)

    for _, row in sorted_routes.iterrows():
        vc = row.get("vc_ratio", 0)
        los = row.get("los", "")
        vc_str = f"{vc:.3f}"
        style = "red" if vc >= threshold else ("yellow" if vc >= 0.60 else "green")
        catchment = row.get("catchment_units", 0)
        catchment_str = f"{catchment:.0f}" if catchment else "—"
        demand_src = str(row.get("demand_source", ""))
        # abbreviate demand source for display
        src_abbr = {"catchment_based": "CB", "aadt_based": "AADT", "road_class_estimated": "RC"}.get(demand_src, demand_src[:4])

        table.add_row(
            str(row.get("name", ""))[:30] or "Unnamed",
            str(row.get("road_type", "")),
            str(row.get("lane_count", "")),
            f"{row.get('capacity_vph', 0):.0f}",
            f"{row.get('baseline_demand_vph', 0):.0f}",
            catchment_str,
            f"[{style}]{vc_str}[/{style}]",
            f"[{style}]{los}[/{style}]",
            src_abbr,
        )

    console.print(table)


def _print_determination(project, audit: dict):
    """Print the final determination result prominently."""
    det = project.determination
    _TIER_COLOR = {
        "DISCRETIONARY":           "red",
        "CONDITIONAL MINISTERIAL": "yellow",
        "MINISTERIAL":             "green",
    }
    _TIER_COLOR_DIM = {
        "DISCRETIONARY":           "red",
        "CONDITIONAL MINISTERIAL": "yellow",
        "MINISTERIAL":             "green",
        "NOT_APPLICABLE":          "dim",
    }
    color = _TIER_COLOR.get(det, "white")

    console.print()
    console.print(Panel(
        f"[bold {color}]{det}[/bold {color}]\n\n{project.determination_reason}",
        title="[bold]Final Determination[/bold]",
        border_style=color,
    ))

    # Per-scenario results table (one row per scenario)
    table = Table(title="Scenario Results (5-Step Algorithm)", show_header=True, header_style="bold")
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
        s5 = steps.get("step5_ratio_test", {})

        if stier == "NOT_APPLICABLE":
            step_parts.append(s1.get("note", "Not applicable")[:55])
        else:
            if s2:
                step_parts.append(
                    f"Size {s2.get('dwelling_units')}≥{s2.get('threshold')}: "
                    f"{'✓' if s2.get('result') else '✗'}"
                )
            if s3:
                step_parts.append(f"Routes: {s3.get('serving_route_count', 0)}")
            if s5:
                step_parts.append(f"Flagged: {len(s5.get('flagged_route_ids', []))}")
            fz = s1.get("fire_zone_severity_modifier", {})
            if fz:
                step_parts.append(f"Fire zone: {fz.get('zone_description', 'N/A')}")

        table.add_row(
            sname,
            f"[{sc}]{stier}[/{sc}]",
            f"[{'red' if triggered else 'green'}]{'YES' if triggered else 'NO'}[/{'red' if triggered else 'green'}]",
            " | ".join(step_parts),
        )

    console.print(table)

    d = audit.get("determination", {})
    console.print(
        f"\n  [dim]Peak-hour vehicles: {project.project_vehicles_peak_hour:.1f} vph · "
        f"Serving routes: {len(project.serving_route_ids or [])} · "
        f"Flagged routes: {len(project.flagged_route_ids or [])}[/dim]"
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

    # Run capacity analysis if the cached roads don't yet have vc_ratio
    if "vc_ratio" not in roads_gdf.columns or "demand_source" not in roads_gdf.columns:
        console.print("[yellow]Roads not yet analyzed — running capacity analysis...[/yellow]")
        from agents.capacity_analysis import analyze_capacity
        roads_gdf = analyze_capacity(
            roads_gdf, fhsz_gdf, boundary_gdf, config, city_config,
            block_groups_gdf=block_groups_gdf,
        )

    # ── Evaluate each project ──────────────────────────────────────────────
    evaluated: list[Project] = []
    _TIER_RICH = {
        "DISCRETIONARY":           "bold red",
        "CONDITIONAL MINISTERIAL": "bold yellow",
        "MINISTERIAL":             "bold green",
    }

    for i, pdef in enumerate(project_defs, 1):
        name    = pdef.get("name", f"Project {i}")
        lat     = float(pdef["lat"])
        lon     = float(pdef["lon"])
        units   = int(pdef["units"])
        address = pdef.get("address", "")

        console.print(
            f"  [{i}/{len(project_defs)}] [bold]{name}[/bold]  "
            f"({units} units · {lat:.4f}, {lon:.4f})"
        )

        project = Project(
            location_lat=lat,
            location_lon=lon,
            address=address,
            dwelling_units=units,
            project_name=name,
        )
        project, _ = evaluate_project(
            project=project,
            roads_gdf=roads_gdf,
            fhsz_gdf=fhsz_gdf,
            config=config,
            city_config=city_config,
        )
        evaluated.append(project)

        det   = project.determination
        style = _TIER_RICH.get(det, "white")
        n_srv = len(project.serving_route_ids or [])
        n_flg = len(project.flagged_route_ids or [])
        console.print(
            f"     [{style}]{det}[/{style}]  "
            f"[dim]{n_srv} serving routes · {n_flg} flagged[/dim]"
        )

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
    )
    console.print(f"  Map saved: [cyan]{map_path}[/cyan]")
    console.print(f"  Open with: [dim]open {map_path}[/dim]")


# ---------------------------------------------------------------------------
# Rich output helpers
# ---------------------------------------------------------------------------

def _print_demo_summary(projects: list, config: dict):
    """Print a multi-project comparison table."""
    vc_threshold = config.get("vc_threshold", 0.80)
    unit_threshold = config.get("unit_threshold", 50)

    table = Table(
        title="Demo Project Summary",
        show_header=True,
        header_style="bold blue",
        show_lines=False,
    )
    table.add_column("Project", min_width=22)
    table.add_column("Units", justify="right")
    table.add_column("Std 2\n(size)", justify="center")
    table.add_column("Std 3\n(routes)", justify="center")
    table.add_column("Std 4\n(capacity)", justify="center")
    table.add_column("Fire\nZone", justify="center")
    table.add_column("Peak Veh\n(vph)", justify="right")
    table.add_column("Serving\nSegs", justify="right")
    table.add_column("Determination")

    _TIER_COLOR = {
        "DISCRETIONARY":           "red",
        "CONDITIONAL MINISTERIAL": "yellow",
        "MINISTERIAL":             "green",
    }

    for p in projects:
        det   = p.determination or "UNKNOWN"
        color = _TIER_COLOR.get(det, "white")
        std2  = "[green]✓[/green]" if p.meets_size_threshold else "[dim]✗[/dim]"
        std3  = f"[green]✓[/green]" if p.serving_route_ids else "[dim]✗[/dim]"
        std4  = "[red]✓[/red]" if p.exceeds_capacity_threshold else "[green]✗[/green]"
        fzone = (f"[red]Z{p.fire_zone_level}[/red]" if p.in_fire_zone else "[dim]—[/dim]")
        table.add_row(
            str(p.project_name)[:24],
            str(p.dwelling_units),
            std2,
            std3,
            std4,
            fzone,
            f"{p.project_vehicles_peak_hour:.0f}",
            str(len(p.serving_route_ids or [])),
            f"[{color} bold]{det}[/{color} bold]",
        )

    console.print(table)


if __name__ == "__main__":
    cli()

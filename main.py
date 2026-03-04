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
    with console.status("Running HCM calculations and route identification..."):
        roads_gdf = analyze_capacity(
            roads_gdf=datasets["roads"],
            fhsz_gdf=datasets["fhsz"],
            boundary_gdf=datasets["boundary"],
            config=config,
            city_config=city_config,
        )

    # Save results
    routes_path = output_dir / "routes.csv"
    evac_routes = roads_gdf[roads_gdf["is_evacuation_route"] == True].copy()

    output_cols = [
        "name", "highway", "road_type", "lane_count", "speed_limit",
        "capacity_vph", "baseline_demand_vph", "vc_ratio", "los",
        "connectivity_score", "length_meters",
        "lane_count_estimated", "speed_estimated", "aadt_estimated",
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
def evaluate(city: str, lat: float, lon: float, units: int,
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

    with console.status("Loading cached data..."):
        roads_gdf = gpd.read_file(roads_path, layer="roads")
        fhsz_gdf = gpd.read_file(fhsz_path)
        boundary_gdf = gpd.read_file(boundary_path)

    # If roads don't have capacity columns yet, run capacity analysis first
    if "vc_ratio" not in roads_gdf.columns:
        console.print("[yellow]Routes not yet analyzed -- running capacity analysis...[/yellow]")
        from agents.capacity_analysis import analyze_capacity
        roads_gdf = analyze_capacity(roads_gdf, fhsz_gdf, boundary_gdf, config, city_config)

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
    det_filename = f"determination_{lat}_{lon}.txt".replace("-", "n").replace(".", "_")
    audit_path = output_dir / det_filename
    generate_audit_trail(project, audit, audit_path)

    _print_determination(project, audit)
    console.print(f"\n  Full audit trail: [cyan]{audit_path}[/cyan]")


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
    table.add_column("v/c", justify="right")
    table.add_column("LOS")
    table.add_column("Connectivity", justify="right")

    sorted_routes = evac_routes.sort_values("vc_ratio", ascending=False).head(20)

    for _, row in sorted_routes.iterrows():
        vc = row.get("vc_ratio", 0)
        los = row.get("los", "")
        vc_str = f"{vc:.3f}"
        style = "red" if vc >= threshold else ("yellow" if vc >= 0.60 else "green")

        table.add_row(
            str(row.get("name", ""))[:30] or "Unnamed",
            str(row.get("road_type", "")),
            str(row.get("lane_count", "")),
            f"{row.get('capacity_vph', 0):.0f}",
            f"{row.get('baseline_demand_vph', 0):.0f}",
            f"[{style}]{vc_str}[/{style}]",
            f"[{style}]{los}[/{style}]",
            str(row.get("connectivity_score", "")),
        )

    console.print(table)


def _print_determination(project, audit: dict):
    """Print the final determination result prominently."""
    det = project.determination
    color = "red" if det == "DISCRETIONARY" else "green"

    console.print()
    console.print(Panel(
        f"[bold {color}]{det}[/bold {color}]\n\n{project.determination_reason}",
        title="[bold]Final Determination[/bold]",
        border_style=color,
    ))

    table = Table(title="Standards Results", show_header=True, header_style="bold")
    table.add_column("Standard")
    table.add_column("Result")
    table.add_column("Details")

    s = audit["determination"]
    std_rows = [
        ("Standard 1: Fire Zone", s["standard_1_triggered"],
         f"Zone: {audit['standards']['standard_1_fire_zone'].get('zone_description', '')}"),
        ("Standard 2: Size Threshold", s["standard_2_triggered"],
         f"{project.dwelling_units} units vs. {project.size_threshold_used} threshold"),
        ("Standard 4: Capacity Threshold", s["standard_4_triggered"],
         f"{project.project_vehicles_peak_hour:.1f} peak-hour vehicles"),
    ]
    for label, triggered, detail in std_rows:
        style = "red" if triggered else "green"
        table.add_row(
            label,
            f"[{style}]{'TRIGGERED' if triggered else 'not triggered'}[/{style}]",
            detail,
        )

    console.print(table)


if __name__ == "__main__":
    cli()

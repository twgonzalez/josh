# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
JOSH Build CLI — graph builder, capacity engine, demo map renderer.

Requires pre-acquired data from josh-pipeline (acquire.py).

Usage:
  uv run python build.py analyze --city "Berkeley" --data-dir /path/to/data/berkeley
  uv run python build.py demo    --city "Berkeley" --data-dir /path/to/data/berkeley
  uv run python build.py evaluate --city "Berkeley" --lat 37.87 --lon -122.27 --units 75
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

BASE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(city: str, city_config_path: Path | None = None) -> tuple[dict, dict]:
    """Load parameters.yaml and city config, applying city overrides.

    Parameters are always read from config/parameters.yaml in this repo.
    City config is read from city_config_path if provided, else from
    config/cities/{city_slug}.yaml (Berkeley schema example lives here).
    """
    params_path = BASE_DIR / "config" / "parameters.yaml"
    if not params_path.exists():
        console.print(f"[red]ERROR: {params_path} not found.[/red]")
        sys.exit(1)
    with open(params_path) as f:
        config = yaml.safe_load(f)

    city_slug = city.lower().replace(" ", "_")

    if city_config_path is None:
        city_config_path = BASE_DIR / "config" / "cities" / f"{city_slug}.yaml"

    if not city_config_path.exists():
        console.print(
            f"[yellow]Warning: No city config at {city_config_path}. Using defaults.[/yellow]"
        )
        city_config = {"city_name": city, "osmnx_place": f"{city}, USA"}
    else:
        with open(city_config_path) as f:
            city_config = yaml.safe_load(f)

    overrides = city_config.get("overrides") or {}
    if overrides:
        config.update(overrides)

    return config, city_config


def _require_data_dir(data_dir_str: str | None, city_slug: str) -> Path:
    """Validate and return the data directory, exiting with a clear error if missing."""
    if data_dir_str is None:
        console.print(
            f"[red]ERROR: --data-dir is required.[/red]\n"
            f"Acquire data first:\n"
            f"  cd josh-pipeline && uv run python acquire.py --city \"{city_slug.title()}\""
        )
        sys.exit(1)
    data_dir = Path(data_dir_str)
    if not data_dir.exists():
        console.print(
            f"[red]ERROR: data directory not found: {data_dir}[/red]\n"
            f"Acquire data first:\n"
            f"  cd josh-pipeline && uv run python acquire.py --city \"{city_slug.title()}\""
        )
        sys.exit(1)
    return data_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool):
    """JOSH — fire evacuation capacity analysis engine."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, show_time=False)],
    )


@cli.command()
@click.option("--city", required=True, help='City name (e.g. "Berkeley")')
@click.option("--state", default="CA", show_default=True, help="State abbreviation")
@click.option(
    "--data-dir", "data_dir_str", required=True,
    help="Path to pre-acquired data directory (from josh-pipeline acquire.py)",
)
@click.option(
    "--city-config", "city_config_str", default=None,
    help="Path to city config YAML (default: config/cities/{city}.yaml)",
)
@click.option(
    "--output-dir", "output_dir_str", default=None,
    help="Output directory (default: output/{city}/)",
)
def analyze(city: str, state: str, data_dir_str: str, city_config_str: str | None,
            output_dir_str: str | None):
    """
    Run capacity analysis on pre-acquired city data.

    Outputs:
      - output/{city}/routes.csv -- evacuation routes with v/c ratios
      - output/{city}/graph.json -- browser data bundle for what-if engine
      - static/whatif_engine.js  -- regenerated JS engine
    """
    from agents.capacity_analysis import analyze_capacity

    city_slug = city.lower().replace(" ", "_")
    city_config_path = Path(city_config_str) if city_config_str else None
    config, city_config = load_config(city, city_config_path)

    data_dir = _require_data_dir(data_dir_str, city_slug)
    output_dir = Path(output_dir_str) if output_dir_str else BASE_DIR / "output" / city_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold cyan]Analyzing {city}, {state}[/bold cyan]")

    # Load pre-acquired data
    roads_path       = data_dir / "roads.gpkg"
    fhsz_path        = data_dir / "fhsz.geojson"
    boundary_path    = data_dir / "boundary.geojson"
    block_groups_path = data_dir / "block_groups.geojson"

    missing = [p for p in [roads_path, fhsz_path, boundary_path] if not p.exists()]
    if missing:
        console.print(
            f"[red]ERROR: Missing data files in {data_dir}: "
            f"{[p.name for p in missing]}[/red]\n"
            f"Re-run: cd josh-pipeline && uv run python acquire.py --city \"{city}\" --refresh"
        )
        sys.exit(1)

    import geopandas as gpd
    console.print("\n[bold]Step 1: Loading Data[/bold]")
    with console.status("Loading datasets..."):
        roads_gdf      = gpd.read_file(roads_path, layer="roads")
        fhsz_gdf       = gpd.read_file(fhsz_path)
        boundary_gdf   = gpd.read_file(boundary_path)
        block_groups_gdf = (
            gpd.read_file(block_groups_path) if block_groups_path.exists() else None
        )
    _print_data_summary({
        "roads": roads_gdf, "fhsz": fhsz_gdf, "boundary": boundary_gdf,
        **({"block_groups": block_groups_gdf} if block_groups_gdf is not None else {}),
    })

    # Agent 2: Capacity Analysis
    console.print("\n[bold]Step 2: Capacity Analysis[/bold]")
    with console.status("Running HCM calculations and route identification..."):
        roads_gdf, evacuation_paths = analyze_capacity(
            roads_gdf=roads_gdf,
            fhsz_gdf=fhsz_gdf,
            boundary_gdf=boundary_gdf,
            config=config,
            city_config=city_config,
            block_groups_gdf=block_groups_gdf,
            data_dir=data_dir,
        )

    console.print(f"  {len(evacuation_paths)} bottleneck paths computed.")

    # Save routes.csv
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

    # Export browser data bundle
    from agents.export import (
        export_graph_json,
        export_parameters_json,
        export_fhsz_json,
        export_whatif_engine_js,
    )
    graph_path_cached = data_dir / "graph.graphml"
    exit_nodes_path   = data_dir / "exit_nodes.json"
    if graph_path_cached.exists():
        with console.status("Exporting browser data bundle..."):
            export_graph_json(graph_path_cached, exit_nodes_path, roads_gdf, config, city_config, output_dir)
            export_parameters_json(config, city_config, output_dir)
            export_fhsz_json(fhsz_gdf, output_dir)
            export_whatif_engine_js()
        console.print("  Browser bundle: [cyan]output/{city}/graph.json + parameters.json + fhsz.json[/cyan]")
        console.print("  JS engine:      [cyan]static/whatif_engine.js[/cyan] (regenerated)")

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
@click.option(
    "--data-dir", "data_dir_str", default=None,
    help="Path to pre-acquired data directory (default: data/{city}/)",
)
@click.option(
    "--city-config", "city_config_str", default=None,
    help="Path to city config YAML (default: config/cities/{city}.yaml)",
)
@click.option(
    "--output-dir", "output_dir_str", default=None,
    help="Output directory (default: output/{city}/)",
)
def evaluate(city: str, lat: float, lon: float, units: int, stories: int,
             name: str, address: str, apn: str,
             data_dir_str: str | None, city_config_str: str | None,
             output_dir_str: str | None):
    """
    Evaluate a proposed project — produce ministerial/discretionary determination.

    Requires a prior `analyze` run.

    Outputs:
      - output/{city}/determination_{lat}_{lon}.txt -- full audit trail
      - output/{city}/brief_v3_{lat}_{lon}_{units}u.html -- determination brief
    """
    import geopandas as gpd
    from agents.objective_standards import evaluate_project, generate_audit_trail
    from models.project import Project

    city_slug = city.lower().replace(" ", "_")
    city_config_path = Path(city_config_str) if city_config_str else None
    config, city_config = load_config(city, city_config_path)

    data_dir = (
        Path(data_dir_str) if data_dir_str else BASE_DIR / "data" / city_slug
    )
    output_dir = Path(output_dir_str) if output_dir_str else BASE_DIR / "output" / city_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    roads_path    = data_dir / "roads.gpkg"
    fhsz_path     = data_dir / "fhsz.geojson"
    boundary_path = data_dir / "boundary.geojson"

    missing = [p for p in [roads_path, fhsz_path, boundary_path] if not p.exists()]
    if missing:
        console.print(f"[red]ERROR: Missing data files: {missing}[/red]")
        console.print(f'Run first: [cyan]uv run python build.py analyze --city "{city}" --data-dir {data_dir}[/cyan]')
        sys.exit(1)

    console.rule(f"[bold cyan]Evaluating Project in {city}[/bold cyan]")
    if name:
        console.print(f"  Project: {name}")
    console.print(f"  Location: {lat}, {lon}")
    console.print(f"  Units: {units}  Stories: {stories}")

    block_groups_path = data_dir / "block_groups.geojson"
    evac_paths_path   = data_dir / "evacuation_paths.json"

    with console.status("Loading cached data..."):
        roads_gdf        = gpd.read_file(roads_path, layer="roads")
        fhsz_gdf         = gpd.read_file(fhsz_path)
        boundary_gdf     = gpd.read_file(boundary_path)
        block_groups_gdf = gpd.read_file(block_groups_path) if block_groups_path.exists() else None
        evacuation_paths = _load_evacuation_paths(evac_paths_path)

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
        graph_path=data_dir / "graph.graphml",
    )

    lat_str = f"{lat:.4f}".replace(".", "_").replace("-", "n")
    lon_str = f"{lon:.4f}".replace(".", "_").replace("-", "n")
    det_filename = f"determination_{lat_str}_{lon_str}_{units}u.txt"
    audit_path = output_dir / det_filename
    generate_audit_trail(project, audit, audit_path)

    from agents.visualization.brief_v3 import create_determination_brief_v3
    brief_path = output_dir / f"brief_v3_{lat_str}_{lon_str}_{units}u.html"
    create_determination_brief_v3(project, audit, config, city_config, brief_path)

    _print_determination(project, audit)
    console.print(f"\n  Full audit trail: [cyan]{audit_path}[/cyan]")
    console.print(f"  Determination brief: [cyan]{brief_path}[/cyan]")
    console.print(f"  Open with: [dim]open {brief_path}[/dim]")


@cli.command()
@click.option("--city", required=True, help="City name (must match a prior analyze run)")
@click.option("--state", default="CA", show_default=True, help="State abbreviation")
@click.option(
    "--projects", "projects_file", default=None,
    help="Path to projects YAML (required when --data-dir is set)",
)
@click.option("--output", "output_name", default="analysis_map", show_default=True,
              help="Output filename stem (no extension)")
@click.option(
    "--data-dir", "data_dir_str", default=None,
    help="Path to pre-acquired data directory (default: data/{city}/)",
)
@click.option(
    "--city-config", "city_config_str", default=None,
    help="Path to city config YAML (default: config/cities/{city}.yaml)",
)
@click.option(
    "--output-dir", "output_dir_str", default=None,
    help="Output directory (default: output/{city}/)",
)
def map(city: str, state: str, projects_file: str | None, output_name: str,
        data_dir_str: str | None, city_config_str: str | None,
        output_dir_str: str | None):
    """
    Multi-project map: evaluate a batch of seeded projects and generate the
    interactive comparison map (output/{city}/analysis_map.html).

    Requires a prior `analyze` run.

    Example:
      uv run python build.py map --city "Berkeley" --data-dir /path/to/data/berkeley
    """
    import geopandas as gpd
    from agents.objective_standards import evaluate_project
    from agents.visualization import create_analysis_map
    from models.project import Project

    city_slug = city.lower().replace(" ", "_")
    city_config_path = Path(city_config_str) if city_config_str else None
    config, city_config = load_config(city, city_config_path)

    data_dir = (
        Path(data_dir_str) if data_dir_str else BASE_DIR / "data" / city_slug
    )
    output_dir = Path(output_dir_str) if output_dir_str else BASE_DIR / "output" / city_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve projects file
    if projects_file is None:
        projects_file = BASE_DIR / "config" / "projects" / f"{city_slug}_demo.yaml"
    else:
        projects_file = Path(projects_file)

    if not projects_file.exists():
        console.print(f"[red]ERROR: Projects file not found: {projects_file}[/red]")
        console.print(
            "Pass --projects /path/to/{city}_demo.yaml (from josh-pipeline/projects/)."
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

    roads_path       = data_dir / "roads.gpkg"
    fhsz_path        = data_dir / "fhsz.geojson"
    boundary_path    = data_dir / "boundary.geojson"
    block_groups_path = data_dir / "block_groups.geojson"

    missing = [p for p in [roads_path, fhsz_path, boundary_path] if not p.exists()]
    if missing:
        console.print(f"[red]ERROR: Missing data files: {[str(p) for p in missing]}[/red]")
        console.print(
            f'Run first: [cyan]uv run python build.py analyze --city "{city}" --data-dir {data_dir}[/cyan]'
        )
        sys.exit(1)

    with console.status("Loading cached data..."):
        roads_gdf      = gpd.read_file(roads_path, layer="roads")
        fhsz_gdf       = gpd.read_file(fhsz_path)
        boundary_gdf   = gpd.read_file(boundary_path)
        block_groups_gdf = (
            gpd.read_file(block_groups_path) if block_groups_path.exists() else None
        )

    evac_paths_path  = data_dir / "evacuation_paths.json"
    evacuation_paths = _load_evacuation_paths(evac_paths_path)

    if "effective_capacity_vph" not in roads_gdf.columns or "demand_source" not in roads_gdf.columns:
        console.print("[yellow]Roads not yet analyzed — running capacity analysis...[/yellow]")
        from agents.capacity_analysis import analyze_capacity
        roads_gdf, evacuation_paths = analyze_capacity(
            roads_gdf, fhsz_gdf, boundary_gdf, config, city_config,
            block_groups_gdf=block_groups_gdf,
            data_dir=data_dir,
        )

    evaluated: list[Project] = []
    audits: list[dict] = []
    _TIER_RICH = {
        "DISCRETIONARY":                     "bold red",
        "MINISTERIAL WITH STANDARD CONDITIONS": "bold yellow",
        "MINISTERIAL":                       "bold green",
    }

    for i, pdef in enumerate(project_defs, 1):
        name              = pdef.get("name", f"Project {i}")
        lat               = float(pdef["lat"])
        lon               = float(pdef["lon"])
        units             = int(pdef["units"])
        stories           = int(pdef.get("stories", 0))
        address           = pdef.get("address", "")
        additional_egress = pdef.get("additional_egress", [])

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
            additional_egress_points=additional_egress,
        )
        project, audit = evaluate_project(
            project=project,
            roads_gdf=roads_gdf,
            fhsz_gdf=fhsz_gdf,
            config=config,
            city_config=city_config,
            evacuation_paths=evacuation_paths,
            graph_path=data_dir / "graph.graphml",
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

        expected_tier = pdef.get("expected_tier", "").strip().upper()
        actual_tier   = det.strip().upper()
        if expected_tier and actual_tier != expected_tier:
            console.print(
                f"     [bold red]⚠ REGRESSION: expected [white]{expected_tier}[/white] "
                f"got [white]{actual_tier}[/white][/bold red]"
            )

        from agents.visualization.brief_v3 import create_determination_brief_v3
        from agents.objective_standards import generate_audit_trail
        lat_str = f"{lat:.4f}".replace(".", "_").replace("-", "n")
        lon_str = f"{lon:.4f}".replace(".", "_").replace("-", "n")
        # Write determination txt FIRST so brief_v3.py reads current content
        audit_path = output_dir / f"determination_{lat_str}_{lon_str}_{units}u.txt"
        generate_audit_trail(project, audit, audit_path)
        brief_path = output_dir / f"brief_v3_{lat_str}_{lon_str}_{units}u.html"
        create_determination_brief_v3(project, audit, config, city_config, brief_path)

    console.print()
    _print_demo_summary(evaluated, config)

    from agents.export import export_test_vectors
    with console.status("Exporting test vectors..."):
        export_test_vectors(evaluated, audits, output_dir)
    console.print("  Test vectors: [cyan]output/{city}/test_vectors.json[/cyan]")
    console.print("  Anti-divergence: [dim]node --test tests/test_whatif_engine.js[/dim]")

    console.print("\n[bold]Generating demo map...[/bold]")
    map_path = output_dir / f"{output_name}.html"
    graph_json_path = output_dir / "graph.json"
    params_json_path = output_dir / "parameters.json"
    create_analysis_map(
        projects=evaluated,
        roads_gdf=roads_gdf,
        fhsz_gdf=fhsz_gdf,
        boundary_gdf=boundary_gdf,
        config=config,
        output_path=map_path,
        demo_title=demo_title,
        audits=audits,
        evacuation_paths=evacuation_paths,
        graph_json_path=graph_json_path if graph_json_path.exists() else None,
        params_json_path=params_json_path if params_json_path.exists() else None,
        city_config=city_config,
        data_dir=data_dir,
    )
    console.print(f"  Map saved: [cyan]{map_path}[/cyan]")
    console.print(f"  Open with: [dim]open {map_path}[/dim]")


@cli.command()
@click.option("--city", required=True, help='City name (must match a prior analyze run, e.g. "Berkeley")')
@click.option("--state", default="CA", show_default=True, help="State abbreviation")
@click.option(
    "--output", "output_name",
    default="ab747_report", show_default=True,
    help="Output filename stem (no extension)",
)
@click.option(
    "--data-dir", "data_dir_str", default=None,
    help="Path to pre-acquired data directory (default: data/{city}/)",
)
@click.option(
    "--city-config", "city_config_str", default=None,
    help="Path to city config YAML (default: config/cities/{city}.yaml)",
)
@click.option(
    "--output-dir", "output_dir_str", default=None,
    help="Output directory (default: output/{city}/)",
)
def report(city: str, state: str, output_name: str,
           data_dir_str: str | None, city_config_str: str | None,
           output_dir_str: str | None):
    """
    Generate an AB 747 (Gov. Code §65302.15) evacuation capacity report.

    Requires a prior `analyze` run.

    Outputs:
      - output/{city}/ab747_report.html
    """
    import geopandas as gpd
    from agents.visualization.ab747_report import create_ab747_report

    city_slug = city.lower().replace(" ", "_")
    city_config_path = Path(city_config_str) if city_config_str else None
    config, city_config = load_config(city, city_config_path)

    data_dir = (
        Path(data_dir_str) if data_dir_str else BASE_DIR / "data" / city_slug
    )
    output_dir = Path(output_dir_str) if output_dir_str else BASE_DIR / "output" / city_slug

    console.rule(f"[bold cyan]AB 747 Report — {city}[/bold cyan]")

    required = {
        "roads.gpkg":            data_dir / "roads.gpkg",
        "fhsz.geojson":          data_dir / "fhsz.geojson",
        "boundary.geojson":      data_dir / "boundary.geojson",
        "block_groups.geojson":  data_dir / "block_groups.geojson",
        "evacuation_paths.json": data_dir / "evacuation_paths.json",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        console.print(
            f"[red]ERROR: Missing data files: {missing}\n"
            f'Run first: uv run python build.py analyze --city "{city}" --data-dir {data_dir}[/red]'
        )
        raise SystemExit(1)

    with console.status("Loading cached data..."):
        roads_gdf        = gpd.read_file(data_dir / "roads.gpkg", layer="roads")
        fhsz_gdf         = gpd.read_file(data_dir / "fhsz.geojson")
        block_groups_gdf = gpd.read_file(data_dir / "block_groups.geojson")
        evacuation_paths = _load_evacuation_paths(data_dir / "evacuation_paths.json")

    if "effective_capacity_vph" not in roads_gdf.columns:
        from agents.capacity_analysis import analyze_capacity
        boundary_gdf = gpd.read_file(data_dir / "boundary.geojson")
        console.print("  [yellow]Capacity columns not found — re-running capacity analysis...[/yellow]")
        with console.status("Running capacity analysis..."):
            roads_gdf, evacuation_paths = analyze_capacity(
                roads_gdf=roads_gdf,
                fhsz_gdf=fhsz_gdf,
                boundary_gdf=boundary_gdf,
                config=config,
                city_config=city_config,
                block_groups_gdf=block_groups_gdf,
                data_dir=data_dir,
            )

    output_path = output_dir / f"{output_name}.html"
    with console.status("Generating AB 747 report..."):
        create_ab747_report(
            city=city_slug,
            roads_gdf=roads_gdf,
            block_groups_gdf=block_groups_gdf,
            fhsz_gdf=fhsz_gdf,
            evacuation_paths=evacuation_paths,
            config=config,
            city_config=city_config,
            output_path=output_path,
        )

    from agents.analysis import compute_clearance_time, scan_single_access_areas
    clearance = compute_clearance_time(block_groups_gdf, evacuation_paths, fhsz_gdf, config)
    sb99 = scan_single_access_areas(evacuation_paths, block_groups_gdf)

    ct = clearance.total_clearance_time_minutes
    ct_display = f"{ct:.1f} min" if ct != float("inf") else "N/A (no exit data)"
    safe_window = float(config.get("safe_egress_window", {}).get("vhfhsz", 45))
    ct_status = (
        "[red]EXCEEDS VHFHSZ window[/red]"
        if (ct != float("inf") and ct > safe_window)
        else "[green]within VHFHSZ window[/green]"
    )

    console.print(f"\n  [bold]AB 747 Report:[/bold] [cyan]{output_path}[/cyan]")
    console.print(f"  City-wide clearance time:   [bold]{ct_display}[/bold] ({ct_status})")
    console.print(f"  Total exit capacity:        {clearance.total_exit_capacity_vph:,.0f} vph")
    console.print(f"  Single-access block groups: {sb99.single_access_count} of {sb99.total_block_groups}")
    console.print(f"  Open with: [dim]open {output_path}[/dim]")


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
                    path_wgs84_coords=d.get("path_wgs84_coords", []),
                ))
            except Exception:
                continue
        return paths
    except Exception as e:
        logging.getLogger(__name__).debug(f"Could not load evacuation_paths.json: {e}")
        return []


def _print_data_summary(datasets: dict):
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
    if evac_routes.empty:
        console.print("[yellow]No evacuation routes identified.[/yellow]")
        return

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


def _print_demo_summary(projects: list, config: dict):
    unit_threshold = config.get("unit_threshold", 15)

    table = Table(
        title="Demo Project Summary (v4.0 ΔT Standard)",
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
        mob     = getattr(p, "behavioral_mobilization", 0.0)
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

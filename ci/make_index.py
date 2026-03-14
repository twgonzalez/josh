# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Generate output/berkeley/index.html — public landing page for the JOSH Berkeley demo.

Reads config/projects/berkeley_demo.yaml to build a table of the 6 demo projects
with tier badges, links to determination briefs, and links to audit trail text files.

Run via:  uv run python ci/make_index.py
Writes:   output/berkeley/index.html
"""
from pathlib import Path
import yaml

ROOT = Path(__file__).parent.parent
PROJECTS_YAML = ROOT / "config" / "projects" / "berkeley_demo.yaml"
OUTPUT_DIR = ROOT / "output" / "berkeley"

TIER_COLORS = {
    "MINISTERIAL":                        ("#1a7f3c", "#d4edda"),  # green
    "MINISTERIAL WITH STANDARD CONDITIONS": ("#856404", "#fff3cd"),  # amber
    "DISCRETIONARY":                       ("#721c24", "#f8d7da"),  # red
}
TIER_SHORT = {
    "MINISTERIAL":                        "MINISTERIAL",
    "MINISTERIAL WITH STANDARD CONDITIONS": "CONDITIONAL",
    "DISCRETIONARY":                       "DISCRETIONARY",
}


def _fmt(lat: float, lon: float) -> tuple[str, str]:
    """Return (lat_str, lon_str) matching JOSH filename convention (4 d.p.)."""
    lat_s = f"{lat:.4f}".replace(".", "_")
    lon_s = f"{lon:.4f}".replace(".", "_").replace("-", "n")
    return lat_s, lon_s


def main() -> None:
    data = yaml.safe_load(PROJECTS_YAML.read_text())
    projects = data.get("projects", [])

    rows = []
    for p in projects:
        name = p["name"]
        lat, lon = p["lat"], p["lon"]
        units = p["units"]
        stories = p.get("stories", 0)
        tier = p.get("expected_tier", "MINISTERIAL")
        desc = p.get("description", "").strip()

        lat_s, lon_s = _fmt(lat, lon)
        brief_file = f"brief_v3_{lat_s}_{lon_s}_{units}u.html"
        audit_file = f"determination_{lat_s}_{lon_s}.txt"

        fg, bg = TIER_COLORS.get(tier, ("#333", "#eee"))
        short = TIER_SHORT.get(tier, tier)

        rows.append(f"""
      <tr>
        <td style="font-weight:600">{name}</td>
        <td style="color:#555;font-size:13px">{units} units · {stories} stories</td>
        <td>
          <span style="
            display:inline-block;padding:3px 8px;border-radius:4px;
            font-size:12px;font-weight:700;letter-spacing:.04em;
            color:{fg};background:{bg};border:1px solid {fg}33">
            {short}
          </span>
        </td>
        <td style="font-size:13px;color:#555;max-width:340px">{desc[:160]}{'…' if len(desc) > 160 else ''}</td>
        <td style="white-space:nowrap">
          <a href="{brief_file}" style="color:#1a56a0;text-decoration:none;margin-right:10px">Brief</a>
          <a href="{audit_file}" style="color:#555;text-decoration:none;font-size:12px">Audit trail</a>
        </td>
      </tr>""")

    rows_html = "\n".join(rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JOSH — Berkeley Fire Evacuation Capacity Demo</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f8f9fa; color: #212529; line-height: 1.6;
    }}
    header {{
      background: #1a2b4a; color: #fff; padding: 28px 40px 24px;
      border-bottom: 4px solid #c0392b;
    }}
    header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: .02em; }}
    header p {{ font-size: 14px; color: #aab8c8; margin-top: 6px; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
    .hero {{
      background: #fff; border: 1px solid #dee2e6; border-radius: 6px;
      padding: 28px 32px; margin-bottom: 28px;
    }}
    .hero h2 {{ font-size: 17px; font-weight: 600; margin-bottom: 10px; }}
    .hero p {{ font-size: 14px; color: #444; max-width: 780px; }}
    .map-btn {{
      display: inline-block; margin-top: 18px; padding: 10px 22px;
      background: #c0392b; color: #fff; border-radius: 4px;
      text-decoration: none; font-weight: 600; font-size: 14px;
    }}
    .map-btn:hover {{ background: #a93226; }}
    table {{
      width: 100%; border-collapse: collapse;
      background: #fff; border: 1px solid #dee2e6; border-radius: 6px;
      overflow: hidden; font-size: 14px;
    }}
    thead tr {{ background: #1a2b4a; color: #fff; }}
    thead th {{
      padding: 10px 14px; text-align: left;
      font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
    }}
    tbody tr {{ border-top: 1px solid #e9ecef; }}
    tbody tr:hover {{ background: #f8f9fa; }}
    tbody td {{ padding: 12px 14px; vertical-align: top; }}
    footer {{
      margin-top: 36px; padding: 18px 0; border-top: 1px solid #dee2e6;
      font-size: 12px; color: #777; text-align: center;
    }}
  </style>
</head>
<body>

<header>
  <h1>JOSH &mdash; Fire Evacuation Capacity Analysis System</h1>
  <p>Berkeley, CA &nbsp;&bull;&nbsp; AB 747 / Government Code &sect;65302.15 &nbsp;&bull;&nbsp; v3.2 &Delta;T Standard</p>
</header>

<div class="container">
  <div class="hero">
    <h2>What is JOSH?</h2>
    <p>
      JOSH is an objective, algorithmic system that calculates whether a proposed development
      project materially degrades fire evacuation route capacity. It applies the Highway Capacity
      Manual (HCM 2022) &Delta;T method: each project&rsquo;s peak-hour vehicle demand is compared
      against the bottleneck effective capacity on all evacuation paths within 0.5 miles. If the
      marginal evacuation delay (&Delta;T) exceeds the zone-specific threshold derived from NIST
      safe-egress windows, the project requires discretionary review. All determinations are
      fully reproducible from published sources &mdash; no professional judgment, no discretion.
    </p>
    <a class="map-btn" href="demo_map.html">Open Interactive Map &rarr;</a>
  </div>

  <h3 style="font-size:15px;font-weight:600;margin-bottom:12px">Demo Projects &mdash; Three-Tier Coverage Matrix</h3>
  <table>
    <thead>
      <tr>
        <th>Project</th>
        <th>Scale</th>
        <th>Determination</th>
        <th>Key Factor</th>
        <th>Documents</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>

  <footer>
    Legal basis: AB 747 (California Government Code &sect;65302.15) &nbsp;&bull;&nbsp;
    HCM 2022 &nbsp;&bull;&nbsp; NFPA 101 &nbsp;&bull;&nbsp; NIST TN 2135 &nbsp;&bull;&nbsp;
    All calculations are objective and reproducible. No professional discretion applied.
  </footer>
</div>

</body>
</html>
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Written: {out}")


if __name__ == "__main__":
    main()

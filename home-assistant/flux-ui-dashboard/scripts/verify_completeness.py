#!/usr/bin/env python3
"""Design completeness verification — pages, subviews, and view content."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "generated" / "lovelace.flux_ui.json"


def main() -> int:
    subprocess.run(["python3", str(ROOT / "scripts" / "build_flux_ui.py")], check=True)
    config = json.loads(BUILD.read_text())["data"]["config"]
    blob = json.dumps(config)
    paths = {v["path"] for v in config.get("views", [])}
    issues: list[str] = []

    for core in ("overview", "rooms", "scenes", "lights", "cameras"):
        if core not in paths:
            issues.append(f"Missing core view: {core}")

    room_slugs = ("kitchen", "living", "entry", "master-bedroom", "hall", "garage")
    for slug in room_slugs:
        if f"room-{slug}" not in paths:
            issues.append(f"Missing room detail view: room-{slug}")
        if f"room-{slug}-grid" not in paths:
            issues.append(f"Missing room grid subview: room-{slug}-grid")
        if f"room-{slug}-camera" not in paths:
            issues.append(f"Missing room camera subview: room-{slug}-camera")

    if len(config.get("views", [])) < 23:
        issues.append(f"Expected >= 23 views (5 core + 18 room subviews), got {len(config['views'])}")

    scenes = next(v for v in config["views"] if v["path"] == "scenes")
    scenes_text = json.dumps(scenes)
    if "Quick actions" not in scenes_text:
        issues.append("Scenes view missing Quick actions section")
    if "custom:auto-entities" not in scenes_text:
        issues.append("Scenes view should auto-discover scene.* entities")

    lights = next(v for v in config["views"] if v["path"] == "lights")
    lights_text = json.dumps(lights)
    if "Kitchen" not in lights_text or "Garage" not in lights_text:
        issues.append("Lights view should include per-room light sections")
    if "Upstairs" not in lights_text:
        issues.append("Lights view should include light_groups.yaml sections")

    cameras = next(v for v in config["views"] if v["path"] == "cameras")
    cameras_text = json.dumps(cameras)
    if "custom:auto-entities" not in cameras_text and "picture-glance" not in cameras_text:
        issues.append("Cameras view should use picture-glance or auto-entities")

    living_grid = next(v for v in config["views"] if v["path"] == "room-living-grid")
    grid_text = json.dumps(living_grid)
    if '"columns": 3' not in grid_text:
        issues.append("Room grid subview should use 3-column light grid")
    if "room-living-grid" not in grid_text and "room-living-camera" not in json.dumps(
        next(v for v in config["views"] if v["path"] == "room-living")
    ):
        issues.append("Room detail subnav should link to grid/camera subviews")

    living = next(v for v in config["views"] if v["path"] == "room-living")
    if "room-living-grid" not in json.dumps(living):
        issues.append("Room detail subnav missing grid navigation path")

    if issues:
        print("Completeness verification FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(f"Completeness verification OK ({len(config['views'])} views)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

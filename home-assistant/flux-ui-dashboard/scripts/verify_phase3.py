#!/usr/bin/env python3
"""Phase 3 verification — context-aware overview + Flux reference light tiles."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "generated" / "lovelace.flux_ui.json"


def main() -> int:
    subprocess.run(["python3", str(ROOT / "scripts" / "build_flux_ui.py")], check=True)
    blob = json.loads(BUILD.read_text())["data"]["config"]
    text = json.dumps(blob)
    issues: list[str] = []

    if "Home status" not in text:
        issues.append("Missing home status section")
    if "custom:auto-entities" not in text:
        issues.append("Missing auto-entities active lights")
    overview = next(v for v in blob["views"] if v["path"] == "overview")
    fav_section = json.dumps(next(s for s in overview["sections"] if "Favourite lights" in json.dumps(s)))
    if '"template": "flux_light"' not in fav_section:
        issues.append("Favourite lights should use flux_light template tiles")
    if '"columns": 6' not in fav_section:
        issues.append("Favourite lights should use 2-column grid (columns: 6)")
    if '"columns": 2' not in fav_section:
        issues.append("Favourite lights should use inner 2-column grid like Active now")
    if "custom:mod-card" in fav_section:
        issues.append("Favourite lights should not use mod-card slider rows")
    if "show_brightness_control" in fav_section:
        issues.append("Favourite lights should not embed mushroom sliders")
    if '"action": "navigate"' in text and "#light-" in text:
        issues.append("Light tiles still navigate to bubble popups")
    if "Doors open" not in text:
        issues.append("Missing conditional open garage section")

    templates = blob.get("button_card_templates") or {}
    if "flux_room" not in templates:
        issues.append("Missing flux_room button-card template")

    rooms_view = next(v for v in blob["views"] if v["path"] == "rooms")
    rooms_text = json.dumps(rooms_view)
    if '"template": "flux_room"' not in rooms_text:
        issues.append("Rooms index should use flux_room cards")
    if '"columns": 2' not in rooms_text:
        issues.append("Rooms index should use inner 2-column grid like light tiles")
    if '"height": "148px"' not in json.dumps(templates.get("flux_room", {})):
        issues.append("flux_room template should use fixed 148px card height")
    if '"align-self": "stretch"' not in json.dumps(templates.get("flux_room", {})):
        issues.append("flux_room sensor column should stretch full card height")
    if "justify-content:space-between" not in rooms_text.replace(" ", ""):
        issues.append("Room sensor column should evenly space indicators top-to-bottom")
    if "custom_fields" not in rooms_text or "sensors" not in rooms_text:
        issues.append("Room cards should include 4-slot sensor column custom field")
    if "sensor_slots" not in rooms_text:
        issues.append("Room cards should pass sensor_slots variable")
    if '"info"' not in rooms_text:
        issues.append("Room cards should use stacked info custom field for title + subtitle")
    if "/flux-ui/room-" not in rooms_text:
        issues.append("Room index cards should navigate to /flux-ui/room-{slug} paths")

    room_views = [v for v in blob["views"] if v.get("path", "").startswith("room-")]
    if room_views:
        living = next((v for v in room_views if v["path"] == "room-living"), room_views[0])
        living_text = json.dumps(living)
        if not living.get("subview"):
            issues.append("Room detail views should be subviews")
        if living.get("back_path") != "/flux-ui/rooms":
            issues.append("Room detail views should back_path to /flux-ui/rooms")
        if '"title": "Lights"' not in living_text:
            issues.append("Room detail missing Lights section title")
        if '"template": "flux_light"' not in living_text:
            issues.append("Room detail lights should use flux_light tiles")
        if "mushroom-chips-card" not in living_text:
            issues.append("Room detail missing status/subnav chips")
        if "flux_feature" not in living_text:
            issues.append("Room detail missing feature action row")
        if "/flux-ui/room-living" not in living_text:
            issues.append("Room detail missing navigation from room index")

    # Home status chips must use Jinja2, not button-card JS
    for section in overview["sections"]:
        section_text = json.dumps(section)
        if "Home status" in section_text and "mushroom-chips-card" in section_text:
            if "[[[" in section_text:
                issues.append("Home status chips use button-card JS — need Jinja2 templates")
            break

    if len(overview["sections"]) < 6:
        issues.append(f"Overview has {len(overview['sections'])} sections, need >= 6")

    if issues:
        print("Phase 3 verification FAILED:")
        for i in issues:
            print(f"  - {i}")
        return 1

    print(f"Phase 3 verification OK ({len(overview['sections'])} overview sections)")
    print("Deploy: bash home-assistant/scripts/run_all_e2e.sh")
    print("HACS required: auto-entities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

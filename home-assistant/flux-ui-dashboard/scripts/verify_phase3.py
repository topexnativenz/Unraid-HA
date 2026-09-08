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
    has_simple_tabs = "custom:simple-tabs" in text
    has_native_tabs = "input_select.flux_ui_overview_tab" in text and not has_simple_tabs
    if not has_native_tabs and not has_simple_tabs:
        issues.append(
            "Missing ElementZoom Home/Events/Active tabs — "
            "see https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard"
        )
    if has_simple_tabs and ('"title": "Home"' not in text or '"title": "Events"' not in text):
        issues.append("simple-tabs missing Home or Events tab titles")
    if has_native_tabs and "input_select.flux_ui_overview_tab" not in text:
        issues.append("Native tabs missing input_select.flux_ui_overview_tab entity")
    if has_simple_tabs and '"title": "Active"' not in text:
        issues.append("simple-tabs missing Active tab (ElementZoom reference)")
    if has_native_tabs and '"name": "Active"' not in text:
        issues.append("Native tabs missing Active tab button")
    if "custom:auto-entities" not in text:
        issues.append("Missing auto-entities active lights (Active tab or fallback)")
    overview = next(v for v in blob["views"] if v["path"] == "overview")
    overview_text = json.dumps(overview)
    if "Favourite lights" not in overview_text:
        issues.append("Missing Favourite lights section (Home tab)")
    fav_section = overview_text
    if "custom:mushroom-light-card" not in fav_section or "show_brightness_control" not in fav_section:
        issues.append("Favourite lights should use slim mushroom dimmer rows")
    if '"action": "navigate"' in text and "#light-" in text:
        issues.append("Light tiles still navigate to bubble popups")
    if "Doors open" not in text:
        issues.append("Missing conditional open garage section (Active tab)")
    if "light.main_shed" not in text and "Main Shed" not in text:
        issues.append("Missing Main Shed light on phone dashboard")

    tabs_present = has_native_tabs or has_simple_tabs
    if tabs_present:
        if "Active now" not in text:
            issues.append("Active tab should include Active now lights section")
    elif len(overview["sections"]) < 6:
        issues.append(f"Vertical fallback overview has {len(overview['sections'])} sections, need >= 6")

    templates = blob.get("button_card_templates") or {}
    if "flux_door" not in templates:
        issues.append("Missing flux_door template for garage/shed tiles")

    rooms_view = next(v for v in blob["views"] if v["path"] == "rooms")
    rooms_text = json.dumps(rooms_view)
    if '"template": "flux_room"' not in rooms_text:
        issues.append("Rooms index should use flux_room cards")
    if '"columns": 2' not in rooms_text:
        issues.append("Rooms index should use inner 2-column grid like light tiles")
    if '"height": "186px"' not in json.dumps(templates.get("flux_room", {})):
        issues.append("flux_room template should use ElementZoom 186px card height")
    if "input_select.flux_ui_rooms_tab" not in rooms_text:
        issues.append("Rooms view missing category tab helper (packages/flux_ui_rooms.yaml)")
    if '"content": "Default"' not in rooms_text or '"content": "Others"' not in rooms_text:
        issues.append("Rooms view missing Default/Others/Outdoor category tabs")
    if '"type": "conditional"' not in rooms_text:
        issues.append("Rooms view should filter cards by category with conditional panels")
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
        if living.get("back_path") != "/flux-ui/overview":
            issues.append("Room detail views should back_path to /flux-ui/overview")
        if '"name": "Overview"' not in living_text or "arrow-left" not in living_text:
            issues.append("Room detail should show a labeled Overview back button")
        if '"navigation_path": "/flux-ui/rooms"' in living_text:
            issues.append("Room detail back control should navigate to overview, not rooms")
        if '"title": "Lights"' not in living_text:
            issues.append("Room detail missing Lights section title")
        if "custom:mushroom-light-card" not in living_text or "show_brightness_control" not in living_text:
            issues.append("Room detail lights should use slim mushroom dimmer rows")
        if "mushroom-chips-card" not in living_text:
            issues.append("Room detail missing status/subnav chips")
        if "flux_feature" not in living_text:
            issues.append("Room detail missing feature action row")
        if "flux_room_status" not in json.dumps(templates):
            issues.append("Missing flux_room_status template for room status chips")
        if "Cool (" not in living_text and "Occupied" not in living_text:
            issues.append("Room detail status row should format Occupied / Cool / Humid labels")
        if "flux_fab_group" not in json.dumps(templates):
            issues.append("Missing flux_fab_group template for light group shortcuts")
        if living.get("path") == "room-living" and "flux_fab_group" not in living_text:
            issues.append("Living room should include floating light group shortcuts")
        if "/flux-ui/room-living" not in living_text:
            issues.append("Room detail missing navigation from room index")
        if "room-living-grid" not in living_text:
            issues.append("Room detail subnav should link to grid subview")
        if "room-living-camera" not in living_text:
            issues.append("Room detail subnav should link to camera subview")

    # Home status chips must use Jinja2, not button-card JS
    for section in overview["sections"]:
        section_text = json.dumps(section)
        if "Home status" in section_text and "mushroom-chips-card" in section_text:
            if "[[[" in section_text:
                issues.append("Home status chips use button-card JS — need Jinja2 templates")
            break

    if len(overview["sections"]) < 6:
        if not tabs_present:
            issues.append(f"Overview has {len(overview['sections'])} sections, need >= 6 (or tabs layout)")
        elif len(overview["sections"]) < 3:
            issues.append(f"Overview has {len(overview['sections'])} sections, need >= 3 with tabs layout")

    if issues:
        print("Phase 3 verification FAILED:")
        for i in issues:
            print(f"  - {i}")
        return 1

    print(f"Phase 3 verification OK ({len(overview['sections'])} overview sections)")
    print("Deploy: bash home-assistant/scripts/run_all_e2e.sh")
    print("HACS required: auto-entities (optional: calendar-card-pro, simple-tabs for swipe tabs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

    room_views = [v for v in blob["views"] if v.get("path", "").startswith("room/")]
    if room_views:
        living = next((v for v in room_views if v["path"] == "room/living"), room_views[0])
        living_text = json.dumps(living)
        if '"title": "Lights"' not in living_text:
            issues.append("Room detail missing Lights section title")
        if '"template": "flux_light"' not in living_text:
            issues.append("Room detail lights should use flux_light tiles")

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

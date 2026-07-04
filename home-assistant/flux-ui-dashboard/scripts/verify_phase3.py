#!/usr/bin/env python3
"""Phase 3 verification — context-aware overview + inline light dimmers."""

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
    if "flux_light_dimmer" not in text:
        issues.append("Missing flux_light_dimmer template (inline toggle + slider)")
    if "show_brightness_control" not in text:
        issues.append("Missing inline brightness slider on light buttons")
    if '"action": "navigate"' in text and "#light-" in text:
        issues.append("Light tiles still navigate to bubble popups")
    if "Doors open" not in text:
        issues.append("Missing conditional open garage section")

    overview = next(v for v in blob["views"] if v["path"] == "overview")
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

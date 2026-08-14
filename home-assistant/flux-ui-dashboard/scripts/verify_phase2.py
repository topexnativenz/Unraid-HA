#!/usr/bin/env python3
"""Phase 2 checklist — Flux UI visual polish vs ElementZoom reference."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "generated" / "lovelace.flux_ui.json"
VERIFY = ROOT / "scripts" / "verify_flux_ui.py"

PHASE2_VIEWS = ("overview", "rooms", "scenes", "lights", "cameras")
PHASE2_NAV_LABELS = ("Home", "Rooms", "Scenes", "Camera", "More")
OPTIONAL_HACS = (
    "navbar-card",
    "bubble-card",
    "layout-card",
    "material-you-theme",
    "kiosk-mode",
)


def check_build() -> list[str]:
    issues: list[str] = []
    if not BUILD.exists():
        return ["Run build_flux_ui.py first"]
    config = json.loads(BUILD.read_text())["data"]["config"]
    blob = json.dumps(config)
    paths = {v["path"] for v in config.get("views", [])}
    for p in PHASE2_VIEWS:
        if p not in paths:
            issues.append(f"Missing view: {p}")
    if "custom:navbar-card" in blob:
        for label in PHASE2_NAV_LABELS:
            if f'"label": "{label}"' not in blob:
                issues.append(f"Navbar missing: {label}")
    else:
        for label in ("Home", "Rooms", "Scenes", "Camera"):
            if label not in blob:
                issues.append(f"Navbar fallback missing: {label}")
    if "dark-purple.webp" not in blob:
        issues.append("Wallpaper path missing from view card_mod")
    if "flux_hero" not in blob:
        issues.append("Missing flux_hero template usage")
    room_paths = [p for p in paths if p.startswith("room-")]
    if len(room_paths) < 18:
        issues.append(f"Expected room subviews (detail+grid+camera), found {len(room_paths)}")
    return issues


def check_hacs_readme() -> list[str]:
    hacs = ROOT / "hacs-frontend.yaml"
    if not hacs.exists():
        return ["Missing hacs-frontend.yaml"]
    text = hacs.read_text()
    missing = [x for x in OPTIONAL_HACS if x.replace("-", "") not in text.replace("-", "")]
    if missing:
        return [f"Document HACS deps: {', '.join(missing)}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    print("Phase 2 checklist (Flux UI vs FB post)\n")

    subprocess.run(["python3", str(ROOT / "scripts" / "build_flux_ui.py"), "--no-navbar-card"], check=True)
    build_issues = check_build()
    verify = subprocess.run(["python3", str(VERIFY)], capture_output=True, text=True)
    if verify.returncode != 0:
        build_issues.append("verify_flux_ui.py failed")

    sections = [
        ("Core views + Flux navbar routes", build_issues),
        ("HACS dependency list", check_hacs_readme()),
    ]

    failed = False
    for title, issues in sections:
        status = "OK" if not issues else "NEEDS WORK"
        print(f"[{status}] {title}")
        if issues:
            failed = True
            for i in issues:
                print(f"  - {i}")
        else:
            print("  All checks passed")
        print()

    print("Manual on Mac (cannot verify from cloud):")
    print("  - HACS: navbar-card, Material You Theme, bubble-card, kiosk-mode")
    print("  - Profile → Theme → flux-ui-md3")
    print("  - Deploy: bash home-assistant/scripts/run_all_e2e.sh")
    print("  - Navbar should show: Home | Rooms | Scenes | Camera | More")

    if args.live:
        live = subprocess.run(["python3", str(VERIFY), "--live"], capture_output=True, text=True)
        print(live.stdout)
        if live.returncode != 0:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

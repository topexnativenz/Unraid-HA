#!/usr/bin/env python3
"""Validate Flux UI build output and optionally verify live HA dashboard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
DEFAULT_JSON = ROOT / "generated" / "lovelace.flux_ui.json"


def load_entities() -> dict:
    return yaml.safe_load(ENTITIES.read_text())


def verify_build(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"Missing build output: {path}"]

    raw = json.loads(path.read_text())
    config = raw["data"]["config"]
    views = config.get("views", [])
    if len(views) != 1:
        errors.append(f"Expected 1 view, got {len(views)}")

    view = views[0]
    if view.get("path") != "overview":
        errors.append(f"Expected path 'overview', got {view.get('path')}")

    sections = view.get("sections", [])
    if len(sections) not in (4, 5):
        errors.append(f"Expected 4-5 sections, got {len(sections)}")

    entities_cfg = load_entities()
    expected_lights = {x["entity"] for x in entities_cfg["favourite_lights"]}
    found_lights: set[str] = set()
    found_gate = 0
    found_garage = 0

    blob = json.dumps(config)
    for item in entities_cfg["quick_actions"]["gate"]:
        if item["entity"] in blob:
            found_gate += 1
    for item in entities_cfg["quick_actions"]["garage"]:
        if item["state_entity"] in blob:
            found_garage += 1
    for light in expected_lights:
        if light in blob:
            found_lights.add(light)

    if found_gate != len(entities_cfg["quick_actions"]["gate"]):
        errors.append(f"Gate entities: found {found_gate}, expected {len(entities_cfg['quick_actions']['gate'])}")
    if found_garage != len(entities_cfg["quick_actions"]["garage"]):
        errors.append(f"Garage entities: found {found_garage}, expected {len(entities_cfg['quick_actions']['garage'])}")
    if found_lights != expected_lights:
        missing = expected_lights - found_lights
        errors.append(f"Missing favourite lights: {sorted(missing)}")

    if "weather.forecast_home" not in blob:
        errors.append("Missing weather.forecast_home")

    for card_type in ("custom:button-card", "flux_glass", "button_card_templates"):
        if card_type not in blob:
            errors.append(f"Missing {card_type}")

    return errors


async def verify_live(ha_url: str, token: str) -> list[str]:
    from ha_common import ws_call

    errors: list[str] = []
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/dashboards/list"}]))[0]
    paths = {d.get("url_path") for d in listed.get("result", [])}
    if "flux-ui" not in paths:
        errors.append("Dashboard flux-ui not registered")

    cfg = (await ws_call(token, ha_url, [{"type": "lovelace/config", "url_path": "flux-ui", "force": True}]))[0]
    if not cfg.get("success"):
        errors.append(f"Could not load flux-ui config: {cfg.get('error')}")
        return errors

    views = cfg["result"].get("views", [])
    if not views:
        errors.append("flux-ui has no views")
    elif views[0].get("path") != "overview":
        errors.append(f"First view path is {views[0].get('path')}, expected overview")

    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]
    urls = " ".join(r.get("url", "") for r in resources.get("result", []))
    for needle in ("mushroom", "card-mod", "button-card"):
        if needle not in urls:
            errors.append(f"Lovelace resource missing: {needle} (optional: navbar-card for bottom nav)")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--live", action="store_true", help="Verify live HA dashboard")
    parser.add_argument("--ha-url", default=None)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    errors = verify_build(args.json)
    if errors:
        print("Build verification FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"Build verification OK: {args.json}")

    if args.live:
        import asyncio

        from ha_common import DEFAULT_HA, get_token, ha_reachable

        ha_url = args.ha_url or DEFAULT_HA
        token = get_token(args.token)
        if not asyncio.run(ha_reachable(ha_url, token)):
            print(f"Live verification SKIPPED: HA unreachable at {ha_url}")
            return 2
        live_errors = asyncio.run(verify_live(ha_url, token))
        if live_errors:
            print("Live verification FAILED:")
            for e in live_errors:
                print(f"  - {e}")
            return 1
        print(f"Live verification OK: {ha_url}/flux-ui/overview")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

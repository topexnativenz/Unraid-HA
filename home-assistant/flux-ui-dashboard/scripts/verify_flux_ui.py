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
GARAGE_DIR = ROOT.parent / "garage-doors"
DEFAULT_JSON = ROOT / "generated" / "lovelace.flux_ui.json"
sys.path.insert(0, str(GARAGE_DIR))
from garage_ui_helpers import load_garage_doors  # noqa: E402


def load_entities() -> dict:
    cfg = yaml.safe_load(ENTITIES.read_text())
    cfg["quick_actions"]["garage"] = load_garage_doors()
    return cfg


def verify_build(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"Missing build output: {path}"]

    raw = json.loads(path.read_text())
    config = raw["data"]["config"]
    is_tablet = raw.get("key") == "lovelace.flux_ui_tablet" or "tablet" in path.name
    views = config.get("views", [])
    paths = {v.get("path") for v in views}
    for required in ("overview", "rooms", "scenes", "cameras", "lights"):
        if required not in paths:
            errors.append(f"Missing view: {required}")

    overview = next((v for v in views if v.get("path") == "overview"), None)
    if not overview:
        errors.append("Missing overview view")
        return errors

    overview_sections = overview.get("sections", [])
    overview_blob = json.dumps(overview)
    blob = json.dumps(config)
    usage = {
        "has_simple_tabs": "custom:simple-tabs" in overview_blob,
        "has_native_tabs": "custom:simple-tabs" not in overview_blob
        and (
            "input_select.flux_ui_overview_tab" in overview_blob
            or '"template": "flux_overview_tab"' in overview_blob
        ),
    }

    if is_tablet:
        if overview.get("type") != "sections":
            errors.append(
                "Tablet overview must use sections + layout-card "
                "(not view-type custom:grid-layout — blank/navbar-only bug)"
            )
        sections = overview.get("sections") or []
        if len(sections) < 2:
            errors.append(f"Tablet overview expected >= 2 sections, got {len(sections)}")
        for needle in (
            "custom:layout-card",
            "layout_type",
            "weather-forecast",
            "history-graph",
            "custom:simple-tabs",
            "room_selector",
            "calendar_notification",
            "simple_tab",
            "/flux-ui-tablet/overview",
            '"label": "Home"',
            '"label": "Rooms"',
            '"label": "Camera"',
            '"label": "More"',
        ):
            if needle not in blob:
                errors.append(f"Tablet build missing {needle}")
        if "custom:navbar-card" not in overview_blob and "mushroom-chips-card" not in overview_blob:
            errors.append("Tablet overview missing bottom navbar card")
        if not any(v.get("path") == "active" for v in views):
            errors.append("Tablet build missing Active activity view")
        if not any(v.get("path") == "scenes" for v in views):
            errors.append("Tablet build missing Scenes/Preset view")
    else:
        if len(overview_sections) < 6:
            if not usage["has_simple_tabs"] and not usage["has_native_tabs"] and len(overview_sections) < 6:
                errors.append(
                    f"Expected at least 6 overview sections (vertical layout), got {len(overview_sections)}"
                )
            elif usage["has_simple_tabs"] and len(overview_sections) < 3:
                errors.append(
                    f"Expected at least 3 overview sections with tabs layout, got {len(overview_sections)}"
                )
            elif usage["has_native_tabs"] and len(overview_sections) < 3:
                errors.append(
                    f"Expected at least 3 overview sections with native tabs, got {len(overview_sections)}"
                )
        if "Home status" not in blob:
            errors.append("Missing Phase 3 home status section")
        if not usage["has_simple_tabs"] and not usage["has_native_tabs"]:
            errors.append(
                "Missing ElementZoom overview tabs — expected custom:simple-tabs or native tab bar"
            )
        if usage["has_native_tabs"] and "input_select.flux_ui_overview_tab" not in overview_blob:
            errors.append(
                "Native tabs use input_select.flux_ui_overview_tab — deploy packages/flux_ui_overview.yaml"
            )

    if overview.get("theme") != "flux-ui-md3":
        errors.append(f"Expected theme 'flux-ui-md3', got {overview.get('theme')!r}")

    for view in views:
        if view.get("theme") != "flux-ui-md3":
            errors.append(f"View {view.get('path')} missing flux-ui-md3 theme")
        sections = view.get("sections") or []
        if sections:
            tail = json.dumps(sections[-1])
            if "navbar-card" not in tail and "mushroom-chips-card" not in tail:
                errors.append(f"View {view.get('path')} missing navbar section")

    if "custom:navbar-card" in blob:
        for label in ('"label": "Home"', '"label": "Rooms"', '"label": "Camera"', '"label": "More"'):
            if label not in blob:
                errors.append(f"Flux navbar missing route: {label}")
    elif "custom:mushroom-chips-card" in blob:
        for label in ("Home", "Rooms", "Scenes", "Camera"):
            if label not in blob:
                errors.append(f"Navbar fallback missing: {label}")

    templates = config.get("button_card_templates") or {}
    for name in ("flux_glass", "flux_action", "flux_light", "flux_room", "flux_feature"):
        if name not in templates:
            errors.append(f"Missing button_card template: {name}")
    if not is_tablet and usage["has_native_tabs"] and "flux_overview_tab" not in templates:
        errors.append("Missing button_card template: flux_overview_tab")
    if "flux_hero" not in templates and "flux_greeting" not in templates:
        errors.append("Missing flux_hero or flux_greeting template")

    entities_cfg = load_entities()
    expected_lights = {x["entity"] for x in entities_cfg["favourite_lights"]}
    found_lights: set[str] = set()
    found_gate = 0
    found_garage_sensors = 0

    for item in entities_cfg["quick_actions"]["gate"]:
        if item["entity"] in blob:
            found_gate += 1
    for door in entities_cfg["quick_actions"]["garage"]:
        if door["sensor"] in blob:
            found_garage_sensors += 1
    for light in expected_lights:
        if light in blob:
            found_lights.add(light)

    # Mobile overview embeds gate/garage/favourites; tablet home uses rooms/cameras instead.
    if not is_tablet:
        if found_gate != len(entities_cfg["quick_actions"]["gate"]):
            errors.append(
                f"Gate entities: found {found_gate}, expected {len(entities_cfg['quick_actions']['gate'])}"
            )
        if found_garage_sensors != len(entities_cfg["quick_actions"]["garage"]):
            errors.append(
                f"Garage Tapo sensors: found {found_garage_sensors}, "
                f"expected {len(entities_cfg['quick_actions']['garage'])}"
            )
        if found_lights != expected_lights:
            missing = expected_lights - found_lights
            errors.append(f"Missing favourite lights: {sorted(missing)}")

    if "_flux_ui" in blob:
        errors.append("Invalid lovelace root key _flux_ui — remove from build output")

    if "weather.forecast_home" not in blob:
        errors.append("Missing weather.forecast_home")

    for card_type in ("custom:button-card", "flux_hero"):
        if card_type not in blob:
            errors.append(f"Missing {card_type}")

    if "custom:navbar-card" not in blob and "custom:mushroom-chips-card" not in blob:
        errors.append("Missing bottom nav (navbar-card or mushroom-chips fallback)")

    if "kiosk_mode" not in blob or "hide_header" not in blob:
        errors.append(
            "Missing kiosk_mode mobile hide_header — install maykar/kiosk-mode via HACS"
        )

    if '"template": "flux_room"' not in blob:
        errors.append("Missing flux_room cards on Rooms view")

    if '"template": "flux_light"' not in blob:
        errors.append("Missing flux_light toggle tiles")

    if not is_tablet and '"template": "flux_door"' not in blob:
        errors.append("Missing flux_door tiles for garage/shed quick actions")

    if "states['binary_sensor." in blob and "isDoorOpen" in blob:
        errors.append(
            "Garage door JS still uses states[] lookup — rebuild with entity-bound isDoorOpen(entity)"
        )

    if "mdi:help-circle-outline" in blob:
        errors.append("Door cards still use help-circle fallback icon — redeploy latest build")

    if "_door_contact" in blob:
        errors.append(
            "Garage sensors still use legacy *_door_contact IDs — run discover_garage_doors.py --apply"
        )

    if "show_brightness_control" in blob:
        errors.append("Embedded mushroom sliders found — use flux_light tiles (tap/hold for dimmer)")

    stale_mushroom = (
        "custom:mushroom-lock-card",
        "custom:mushroom-template-card",
    )

    for card_type in stale_mushroom:
        if card_type in blob:
            errors.append(
                f"Stale Mushroom card {card_type} — pull latest branch and redeploy"
            )

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
    else:
        paths = {v.get("path") for v in views}
        for required in ("overview", "rooms", "scenes", "cameras"):
            if required not in paths:
                errors.append(f"Live flux-ui missing view: {required}")
        overview = next((v for v in views if v.get("path") == "overview"), views[0])
        sections = overview.get("sections", [])
        live_blob = json.dumps(cfg["result"])
        overview_blob = json.dumps(overview)
        usage = {
            "has_simple_tabs": "custom:simple-tabs" in overview_blob,
            "has_native_tabs": "custom:simple-tabs" not in overview_blob
            and (
                "input_select.flux_ui_overview_tab" in overview_blob
                or '"template": "flux_overview_tab"' in overview_blob
            ),
        }
        if not usage["has_simple_tabs"] and not usage["has_native_tabs"]:
            errors.append("Live flux-ui missing overview tabs")
        elif usage["has_simple_tabs"] and len(sections) < 3:
            errors.append(f"Live overview has {len(sections)} sections, need >= 3 with tabs layout")
        elif usage["has_native_tabs"] and len(sections) < 3:
            errors.append(f"Live overview has {len(sections)} sections, need >= 3 with native tabs")
        elif not usage["has_simple_tabs"] and not usage["has_native_tabs"] and len(sections) < 6:
            errors.append(f"Live overview has {len(sections)} sections (vertical layout needs >= 6)")
        if "flux_hero" not in live_blob and "flux_greeting" not in live_blob:
            errors.append("Live config missing flux hero")
        if '"label": "Rooms"' not in live_blob:
            errors.append("Live navbar missing Rooms route (old Flux/Mobile/Solar nav)")
        if "kiosk_mode" not in live_blob or "hide_header" not in live_blob:
            errors.append(
                "Live config missing kiosk_mode — redeploy after kiosk-mode resource registered"
            )

    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]
    urls = " ".join(r.get("url", "") for r in resources.get("result", []))
    if "kiosk-mode" not in urls and "kiosk_mode" not in urls:
        errors.append("Lovelace resource missing: kiosk-mode (HACS downloaded ≠ registered)")
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

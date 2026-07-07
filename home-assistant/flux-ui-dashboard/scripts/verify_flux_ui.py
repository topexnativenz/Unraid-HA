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
MEDIA_PLAYERS = ROOT / "media_players.yaml"
GARAGE_DIR = ROOT.parent / "garage-doors"
DEFAULT_JSON = ROOT / "generated" / "lovelace.flux_ui.json"
sys.path.insert(0, str(GARAGE_DIR))
from garage_ui_helpers import load_garage_doors  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from flux_media_player import MUSIC_PLAYER_HASH, SELECT_ZONE_SCRIPT  # noqa: E402
from flux_weather_panel import WEATHER_PANEL_HASH  # noqa: E402


def load_media_players() -> dict:
    if not MEDIA_PLAYERS.exists():
        return {}
    return yaml.safe_load(MEDIA_PLAYERS.read_text()) or {}


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
        for label in (
            '"label": "Home"',
            '"label": "Rooms"',
            '"label": "Weather"',
            '"label": "Camera"',
            '"label": "More"',
        ):
            if label not in blob:
                errors.append(f"Flux navbar missing route: {label}")
    elif "custom:mushroom-chips-card" in blob:
        for label in ("Home", "Rooms", "Weather", "Camera"):
            if label not in blob:
                errors.append(f"Navbar fallback missing: {label}")

    templates = config.get("button_card_templates") or {}
    for name in ("flux_glass", "flux_action", "flux_light", "flux_room", "flux_feature"):
        if name not in templates:
            errors.append(f"Missing button_card template: {name}")
    if usage["has_native_tabs"] and "flux_overview_tab" not in templates:
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

    enabled_garage = entities_cfg["quick_actions"]["garage"]

    if found_gate != len(entities_cfg["quick_actions"]["gate"]):
        errors.append(f"Gate entities: found {found_gate}, expected {len(entities_cfg['quick_actions']['gate'])}")
    if enabled_garage and found_garage_sensors != len(enabled_garage):
        errors.append(
            f"Garage Tapo sensors: found {found_garage_sensors}, "
            f"expected {len(enabled_garage)}"
        )
    if found_lights != expected_lights:
        missing = expected_lights - found_lights
        errors.append(f"Missing favourite lights: {sorted(missing)}")

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

    if "_flux_ui" in blob:
        errors.append("Invalid lovelace root key _flux_ui — remove from build output")

    weather_entity = load_entities().get("weather", "weather.metservice")
    if weather_entity not in blob:
        errors.append(f"Missing configured weather entity: {weather_entity}")

    if "/local/flux-ui/bitmoji/" not in blob:
        errors.append("Missing hero bitmoji picture path (/local/flux-ui/bitmoji/)")

    bitmoji_png = ROOT / "www" / "flux-ui" / "bitmoji" / "dave.png"
    if not bitmoji_png.exists():
        errors.append(f"Missing bitmoji asset: {bitmoji_png.name} — hero avatar will 404")

    if "custom:button-card" not in blob:
        errors.append("Missing custom:button-card")

    if '"template": "flux_greeting"' not in overview_blob and "Morning" not in overview_blob:
        errors.append("Hero card missing greeting text")

    if "/local/flux-ui/bitmoji/" not in overview_blob:
        errors.append("Hero row missing bitmoji avatar layout")

    if "'i n'" not in overview_blob or "'i l'" not in overview_blob:
        errors.append("Hero row missing avatar + greeting grid layout")

    if '"position": "absolute"' not in overview_blob[:25000] or '"right": "0"' not in overview_blob[:25000]:
        errors.append("Hero row missing right-pinned weather positioning")

    if "custom:navbar-card" not in blob and "custom:mushroom-chips-card" not in blob:
        errors.append("Missing bottom nav (navbar-card or mushroom-chips fallback)")

    if WEATHER_PANEL_HASH not in overview_blob:
        errors.append("Missing weather panel bubble popup (#weather-panel) on overview")

    for needle in (
        "custom:weather-forecast-extended-card",
        "custom:apexcharts-card",
        "custom:lunar-phase-card",
        '"title": "Radar"',
        '"title": "Lunar"',
    ):
        if needle not in overview_blob:
            errors.append(f"Weather panel missing ElementZoom component: {needle}")

    if "entity.attributes.forecasts" not in overview_blob:
        errors.append(
            "Weather charts must read forecasts from sensor.flux_ui_hourly_forecast_full"
        )

    if "sensor.flux_ui_hourly_forecast_full" not in overview_blob:
        errors.append(
            "Weather charts missing sensor.flux_ui_hourly_forecast_full entity reference"
        )

    media_cfg = load_media_players()
    media_enabled = media_cfg.get("enabled", True)
    media_players = [
        p for p in media_cfg.get("players", []) if p.get("enabled", True) and p.get("entity")
    ]
    if media_enabled and media_players:
        if MUSIC_PLAYER_HASH not in overview_blob:
            errors.append("Missing music player bubble popup (#music-player) on overview")
        if "custom:navbar-card" in overview_blob and '"media_player"' not in overview_blob:
            errors.append("Overview navbar missing media_player widget for Sonos")
        if "input_select.flux_ui_media_player" not in blob:
            errors.append(
                "Missing input_select.flux_ui_media_player — deploy packages/flux_ui_media.yaml"
            )
        if "[[[ const players" in overview_blob or "_active_entity_js" in overview_blob:
            errors.append(
                "Music player popup uses unsupported JS entity_id template — use per-zone conditional cards"
            )
        if "zone_entity" in overview_blob and "custom:mediocre-massive-media-player-card" in overview_blob:
            errors.append(
                "Mediocre card cannot use Jinja entity_id — use static entity per conditional panel"
            )
        if "custom:mediocre-massive-media-player-card" in overview_blob:
            expected_panels = len(media_players) + sum(
                1 for p in media_players if p.get("apple_tv")
            )
            if overview_blob.count('"entity_id":') < expected_panels:
                errors.append(
                    "Music player popup missing per-zone mediocre entity_id cards "
                    f"(expected {expected_panels}, includes Apple TV TV-mode panels)"
                )
            if '"{{ {{' in overview_blob or "value_template\": \"{{ {{" in overview_blob:
                errors.append(
                    "Music player TV-mode conditional has invalid nested Jinja — popup will show config errors"
                )
            if '"condition": "state"' in overview_blob and '"condition": "template"' in overview_blob:
                mp_start = overview_blob.find('"name": "Music Player"')
                mp_end = overview_blob.find('"popup_style"', mp_start)
                popup_blob = overview_blob[mp_start:mp_end] if mp_end > mp_start else ""
                if popup_blob.count('"condition": "state"') > 0 and popup_blob.count(
                    '"condition": "template"'
                ) > len(media_players):
                    errors.append(
                        "Music popup must use single combined template conditions for TV mode "
                        "(multi-condition panels break inside bubble popups)"
                    )
        if '"name": "Music Player"' in overview_blob:
            mp_start = overview_blob.find('"name": "Music Player"')
            mp_end = overview_blob.find('"popup_style"', mp_start)
            popup_blob = overview_blob[mp_start:mp_end] if mp_end > mp_start else ""
            if popup_blob and '"cards": [{"type": "custom:mushroom-chips-card"' not in popup_blob:
                errors.append("Music popup must start with a single mushroom-chips-card zone picker")
        if "/local/flux-ui/carousel-sync.js" not in blob:
            errors.append(
                "Missing carousel-sync.js module — Sonos swipe will not sync popup artwork"
            )
        if "MIN_SLOTS = 2" not in overview_blob:
            errors.append(
                "Music carousel missing MIN_SLOTS=2 visibility — idle zones will all show"
            )
        if "ACTIVE_STATES" not in overview_blob:
            errors.append("Music carousel missing ACTIVE_STATES (playing+paused) visibility")
        swipe_nav = config.get("swipe_nav") or {}
        if swipe_nav.get("enable") is not False:
            errors.append(
                "Missing swipe_nav enable:false — media carousel swipes conflict with view navigation"
            )
        if "media-player-viewport" not in blob or "touch-action: none" not in blob:
            errors.append(
                "Navbar styles missing media-player-viewport touch-action — Sonos zone swipe may fail"
            )

    if "kiosk_mode" not in blob or "hide_header" not in blob:
        errors.append(
            "Missing kiosk_mode mobile hide_header — install maykar/kiosk-mode via HACS"
        )

    if '"template": "flux_room"' not in blob:
        errors.append("Missing flux_room cards on Rooms view")

    garage_view = next((v for v in views if v.get("path") == "room-garage"), None)
    if garage_view:
        garage_sec = (garage_view.get("sections") or [{}])[0]
        if garage_sec.get("type") != "grid":
            errors.append("Room detail sections must use type: grid (not vertical-stack at section root)")
        garage_cards = garage_sec.get("cards") or []
        if garage_cards and not any(
            isinstance(c, dict) and c.get("grid_options", {}).get("columns") == 12 for c in garage_cards
        ):
            errors.append("Room detail cards missing grid_options columns:12 — layout will break in sections view")

    rooms_view = next((v for v in views if v.get("path") == "rooms"), None)
    if rooms_view:
        rooms_blob = json.dumps(rooms_view)
        if "custom:simple-tabs" not in rooms_blob:
            errors.append("Rooms view missing simple-tabs category bar (match Home tab layout)")
        if '"title": "Default"' not in rooms_blob or '"title": "Others"' not in rooms_blob:
            errors.append("Rooms view missing Default/Others/Outdoor simple-tabs")
        templates = config.get("button_card_templates") or {}
        flux_room = templates.get("flux_room", {})
        if '"height": "186px"' not in json.dumps(flux_room):
            errors.append("flux_room template missing ElementZoom 186px card height — old layout?")
        if '"title": "Rooms"' not in rooms_blob:
            errors.append("Rooms view missing centered 'Rooms' page title")
        if "mushroom-chips-card" in rooms_blob and "input_select.flux_ui_rooms_tab" in rooms_blob:
            errors.append("Rooms view uses legacy mushroom chips — rebuild with simple-tabs layout")

    if '"template": "flux_light"' not in blob:
        errors.append("Missing flux_light toggle tiles")

    if enabled_garage and '"template": "flux_door"' not in blob:
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
    )

    for card_type in stale_mushroom:
        if card_type in blob:
            errors.append(
                f"Stale Mushroom card {card_type} — pull latest branch and redeploy"
            )

    if "custom:mushroom-template-card" in blob and WEATHER_PANEL_HASH not in overview_blob:
        errors.append(
            "Stale Mushroom card custom:mushroom-template-card — pull latest branch and redeploy"
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
        if "flux_greeting" not in live_blob and "flux_hero" not in live_blob:
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

    media_cfg = load_media_players()
    expected_players = [
        p for p in media_cfg.get("players", []) if p.get("enabled", True) and p.get("name")
    ]
    if media_cfg.get("enabled", True) and expected_players:
        expected_opts = [p["name"] for p in expected_players]
        states_res = (await ws_call(token, ha_url, [{"type": "get_states"}]))[0]
        if states_res.get("success"):
            media_select = next(
                (
                    s
                    for s in states_res.get("result", [])
                    if s.get("entity_id") == "input_select.flux_ui_media_player"
                ),
                None,
            )
            if not media_select:
                errors.append(
                    "Live input_select.flux_ui_media_player missing — deploy packages/flux_ui_media.yaml"
                )
            else:
                live_opts = list(media_select.get("attributes", {}).get("options") or [])
                if live_opts != expected_opts:
                    errors.append(
                        f"Live Sonos zone names {live_opts!r} != media_players.yaml {expected_opts!r} "
                        "— run discover_sonos.py --apply or redeploy"
                    )
                current = media_select.get("state") or ""
                if current and current not in expected_opts:
                    errors.append(
                        f"input_select selection {current!r} not in Sonos zone list {expected_opts!r}"
                    )

        overview = next((v for v in views if v.get("path") == "overview"), None)
        if overview:
            overview_blob = json.dumps(overview)
            for player in expected_players:
                if player["name"] not in overview_blob:
                    errors.append(
                        f"Live dashboard missing Sonos zone {player['name']!r} — rebuild after discover_sonos --apply"
                    )

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

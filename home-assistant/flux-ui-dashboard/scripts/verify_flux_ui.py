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
from flux_media_player import MUSIC_PLAYER_HASH, is_sonos_zone  # noqa: E402
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
    for name in (
        "flux_ui_media.yaml",
        "flux_ui_overview.yaml",
        "flux_ui_rooms.yaml",
        "flux_ui_weather.yaml",
        "flux_ui_tablet_led.yaml",
    ):
        if not (ROOT / "packages" / name).exists():
            errors.append(
                f"Missing packages/{name} — wrong/old git SHA "
                "(git reset must use origin/<branch> only, no extra SHA arg)"
            )
    if not path.exists():
        return errors + [f"Missing build output: {path}"]

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
        if overview.get("type") != "panel":
            errors.append(
                "Tablet overview must use type panel + layout-card "
                "(sections views cannot fill 16:9 width)"
            )
        if len(overview.get("cards") or []) != 1:
            errors.append("Tablet panel overview must have exactly one root card")
        for needle in (
            '"type": "panel"',
            "custom:layout-card",
            "layout_type",
            '"width": "100%"',
            "weather-forecast",

            "calendar_notification",
            "simple_tab",
            '"days_to_show": 7',
            '"show_empty_days": true',
            '"refresh_interval": 360',
            '"show_countdown": false',
            '"show_progress_bar": false',
            '"today_indicator": "dot"',
            "__fluxNzClock",
            "hour12: false",
            "Pacific/Auckland",
            "weather.homemetservice",
            "100dvh",
            '"refresh_on_navigate": false',
            '"font-size": "16px"',
            "overflow: visible",
            "minmax(0, 30%)",
            "minmax(0, 24%)",
            '"align-content": "stretch"',
            '"overflow": "hidden"',
            "custom:mod-card",
            "Gates & Doors",
            '"grid-area": "mid"',
            '"grid-area": "tesla"',
            '"grid-area": "music"',
            '"grid-area": "greeting"',
            "Model X",
            "Model S",
            "camera.back_courtyard_fluent",
            "#back-courtyard",
            "custom:bubble-card",
            "is_sidebar_hidden",
            '"width_desktop": "100%"',
            "/local/flux-ui/camera-stills/",
            "input_text.flux_ui_camera_still_token",
            "script.flux_ui_camera_snapshot",
            "eufy-driveway",
            "eufy-side-of-house",
            "eufy-garage-door",
            "custom:webrtc-camera",
            "ffmpeg:",
            '"camera_view": "live"',
            "gap: 8px !important",
            "data:image/webp;base64,",
            "flux-tesla-charge-pulse",
            "touch-action: pan-y",
            ".content-container",
            "picture-entity",
            "camera_view",
            "mediocre-massive-media-player-card",
            "mushroom-chips-card",
            "aspect-ratio: 1 / 1",
            '"place-self": "start stretch"',
            '"grid-template-rows": "auto auto"',
            "height: 100% !important",
            "position: absolute !important",
            "mid mid music calendar_notification",
            "tesla tesla tesla calendar_notification",
            "Weather Forecast",
            ".loading-indicator",
            "Gates & Doors",
            "max-height: 100% !important",
            "media_player.kitchen_sonos",
            "1fr 1fr 1.05fr 1.15fr",
            "align-content: stretch",
            "max-height: none",
            '"font-size": "136px"',
            '"font-size": "30px"',
            "width:78%",
            "hourCycle: 'h23'",
            "1fr 1fr 1fr 1fr",
            '"font-size": "22px"',
            "justify-content: center !important",
            "align-items: center !important",
        ):
            if needle not in blob:
                errors.append(f"Tablet build missing {needle}")
        if "1.05fr 1.25fr" in overview_blob:
            errors.append(
                "Tablet rooms/cameras columns must be equal width (not 1.05fr 1.25fr)"
            )
        if '"rooms cameras music calendar_notification"' in overview_blob:
            errors.append(
                "Tablet must use unified mid band (mid mid), not separate rooms|cameras areas"
            )
        if '"align-content": "start"' in overview_blob and '"align-content": "stretch"' not in overview_blob:
            errors.append(
                "Tablet overview layout must use align-content: stretch on the root grid"
            )
        if "minmax(0, 1fr) minmax(0, 1fr)" in overview_blob:
            errors.append(
                "Tablet mid grid must use auto rows + 1:1 tiles, not stretched 1fr rows"
            )
        mid_idx = overview_blob.find('"grid-area": "mid"')
        if mid_idx >= 0:
            mid_slice = overview_blob[mid_idx : mid_idx + 120]
            if "start stretch" not in mid_slice:
                errors.append("Tablet mid band must use place-self start stretch (square tiles)")
        if "minmax(220px, 240px)" in overview_blob or "minmax(150px, 180px)" in overview_blob:
            errors.append(
                "Tablet Tesla row must use flexible % tracks (minmax(0, 24%)), "
                "not fixed px mins that push off-screen"
            )
        if '"font-size": "84px"' in overview_blob or '"font-size": "112px"' in overview_blob:
            errors.append("Tablet clock still uses smaller type — expect 136px time / 30px date")
        if "hour12: true" in overview_blob:
            errors.append("Tablet clock still shows 12h AM/PM — expect 24h HH:MM")
        if "mdi:thermometer-lines" in overview_blob:
            errors.append("Tablet clock corner still has weather/temp chips under the time")
        if " · ${tz}" in overview_blob or "timeZoneName" in overview_blob:
            errors.append("Tablet clock date still appends NZST/NZDT — show weekday/date only")
        if '"grid-area": "cameras"' in overview_blob or '"grid-area": "rooms"' in overview_blob:
            errors.append(
                "Tablet must use unified mid band, not separate rooms/cameras grid-areas"
            )
        if "max-height: 240px" in overview_blob or "max-height: 180px" in overview_blob:
            errors.append(
                "Tablet Tesla must use max-height 100% (cell-fit), not fixed px caps"
            )
        if "room_selector" in overview_blob:
            errors.append("Tablet overview still has room_selector filter chips")
        if '"content": "Default"' in overview_blob and '"content": "Outdoor"' in overview_blob:
            errors.append("Tablet overview still has Default/Others/Outdoor filter chips")
        if '"speaker_group"' in overview_blob:
            errors.append("Tablet music must not include speaker_group (Kitchen-only)")
        if "media_player.kitchen_sonos" not in overview_blob:
            errors.append("Tablet music must be fixed to media_player.kitchen_sonos")
        if "mediocre-chip-media-player-group-card" in overview_blob:
            errors.append(
                "Tablet music must not include zone/group chip header (stretches overview)"
            )
        if "media_player.select_source" not in overview_blob:
            errors.append("Tablet music missing in-card source selector (select_source)")
        if "mdi:import" not in overview_blob:
            errors.append("Tablet music missing always-visible Source chip")
        if "custom:mod-card" not in overview_blob:
            errors.append("Tablet music must wrap mediocre player in mod-card to hide footer")
        if "mediocre-massive-media-player-card > div > div:last-child" not in overview_blob:
            errors.append("Tablet music must hide mediocre Home/Sonos footer bar via mod-card")
        if "cameras cameras cameras calendar_notification" in overview_blob:
            errors.append("Tablet cameras must sit beside rooms as 2x2, not a full-width row")
        if "min-height: 200px" in overview_blob and "max-height: 100%" not in overview_blob:
            errors.append("Tablet Tesla band must fill its % track (max-height 100%)")
        if '"grid-area": "weather"' in blob:
            errors.append("Tablet still has standalone weather grid area — weather belongs above calendar")
        if "Software tracker" in blob or "Last charges (7 days)" in blob:
            errors.append("Tablet overview still includes broken Tesla widgets 2/3")
        if "Live overview" in overview_blob:
            errors.append("Tablet still has Home / Live overview title")
        if "/local/flux-ui/camera-stills/side_door.jpg" not in overview_blob:
            errors.append("Tablet overview missing last-stream still paths")
        if "image.side_door_event_image" in overview_blob:
            errors.append("Tablet overview still uses stale Eufy event-image entities")
        if "eufy-driveway" not in blob:
            errors.append("Tablet build missing Eufy Driveway live subview")
        if "[class*='loading']" in overview_blob:
            errors.append("Calendar card-mod must not use [class*='loading'] (hides events)")
        # Closed gate must not force a green card fill — only open gets a tint.
        if "Gate Open" in blob and "#81C784 28%" in blob:
            errors.append("Gate Closed still uses green card background — use default chrome")
        if "custom:mushroom-title-card" in overview_blob and "Gates & Doors" not in overview_blob:
            errors.append("Tablet section titles should use button-card (Fully Kiosk renders them)")
        if "mediocre-massive-media-player-card" not in overview_blob:
            errors.append(
                "Tablet music must use full mediocre-massive card (same as modal popup)"
            )
        if '"type": "custom:mediocre-media-player-card"' in overview_blob:
            errors.append("Tablet music still uses compact mediocre-media-player-card")
        locked_area_rows = (
            "greeting simple_tab music calendar_notification",
            "mid mid music calendar_notification",
            "tesla tesla tesla calendar_notification",
        )
        if any(row not in overview_blob for row in locked_area_rows):
            errors.append(
                "Tablet overview grid-template-areas changed unexpectedly"
            )
        for view in views:
            if view.get("type") != "panel":
                errors.append(f"Tablet view {view.get('path')} must be type panel (16:9)")
                break
        # Tablet has no floating bottom navbar (it covered Tesla tiles).
        if "custom:navbar-card" in overview_blob or (
            "mushroom-chips-card" in overview_blob and '"label": "Home"' in overview_blob
        ):
            errors.append("Tablet overview must not include bottom navbar card")
        if not any(v.get("path") == "active" for v in views):
            errors.append("Tablet build missing Active activity view")
        if not any(v.get("path") == "scenes" for v in views):
            errors.append("Tablet build missing Scenes/Preset view")
        living = next((v for v in views if v.get("path") == "room-living"), None)
        if living is None:
            errors.append("Tablet build missing room-living view")
        else:
            living_blob = json.dumps(living)
            if living.get("back_path") != "/flux-ui-tablet/overview":
                errors.append("Tablet room detail back_path should be /flux-ui-tablet/overview")
            if '"name": "Overview"' not in living_blob or "arrow-left" not in living_blob:
                errors.append("Tablet room detail should show a labeled Overview back button")
            if '"navigation_path": "/flux-ui-tablet/overview"' not in living_blob:
                errors.append("Tablet room Overview button should navigate to tablet overview")
            if '"navigation_path": "/flux-ui-tablet/rooms"' in living_blob:
                errors.append("Tablet room back should not navigate to rooms index")
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
        if is_tablet:
            # Tablet panel roots intentionally omit the floating bottom navbar.
            continue
        if view.get("type") == "panel":
            panel_blob = json.dumps(view.get("cards") or [])
            if "navbar-card" not in panel_blob and "mushroom-chips-card" not in panel_blob:
                errors.append(f"View {view.get('path')} missing navbar in panel root")
            continue
        sections = view.get("sections") or []
        if sections:
            tail = json.dumps(sections[-1])
            if "navbar-card" not in tail and "mushroom-chips-card" not in tail:
                errors.append(f"View {view.get('path')} missing navbar section")

    if not is_tablet and "custom:navbar-card" in blob:
        for label in ('"label": "Home"', '"label": "Rooms"', '"label": "Camera"', '"label": "More"'):
            if label not in blob:
                errors.append(f"Flux navbar missing route: {label}")
    elif not is_tablet and "custom:mushroom-chips-card" in blob:
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

    # Mobile overview embeds gate/garage/favourites; tablet home uses rooms/Tesla tiles instead.
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

    entities_cfg_weather = entities_cfg.get("weather")
    if isinstance(entities_cfg_weather, str) and entities_cfg_weather.startswith("weather."):
        if entities_cfg_weather not in blob:
            errors.append(f"Missing configured weather entity: {entities_cfg_weather}")
    elif "weather." not in blob:
        errors.append("Missing weather.* entity in build output")

    for card_type in ("custom:button-card", "flux_hero"):
        if card_type not in blob:
            errors.append(f"Missing {card_type}")

    if (
        not is_tablet
        and "custom:navbar-card" not in blob
        and "custom:mushroom-chips-card" not in blob
    ):
        errors.append("Missing bottom nav (navbar-card or mushroom-chips fallback)")

    if "kiosk_mode" not in blob or "hide_header" not in blob:
        errors.append(
            "Missing kiosk_mode mobile hide_header — install maykar/kiosk-mode via HACS"
        )

    if '"template": "flux_room"' not in blob:
        errors.append("Missing flux_room cards on Rooms view")

    if not is_tablet:
        garage_view = next((v for v in views if v.get("path") == "room-garage"), None)
        if garage_view:
            garage_sec = (garage_view.get("sections") or [{}])[0]
            if garage_sec.get("type") != "grid":
                errors.append(
                    "Room detail sections must use type: grid "
                    "(not vertical-stack at section root)"
                )
            garage_cards = garage_sec.get("cards") or []
            if garage_cards and not any(
                isinstance(c, dict) and c.get("grid_options", {}).get("columns") == 12
                for c in garage_cards
            ):
                errors.append(
                    "Room detail cards missing grid_options columns:12 — "
                    "layout will break in sections view"
                )
            garage_blob = json.dumps(garage_view)
            if '"type": "grid", "columns": 12' in garage_blob and '"grid_options"' in garage_blob:
                # Nested 12-col grids with child grid_options break iOS Companion.
                for card in garage_cards:
                    if not isinstance(card, dict) or card.get("type") != "grid":
                        continue
                    if card.get("columns") != 12:
                        continue
                    for child in card.get("cards") or []:
                        if isinstance(child, dict) and "grid_options" in child:
                            errors.append(
                                "Room detail has nested grid columns:12 with child "
                                "grid_options — causes Configuration errors on iOS"
                            )
                            break
            if "position: fixed" in garage_blob:
                errors.append(
                    "Room detail FAB still uses position:fixed — breaks iOS Safari layout"
                )

    if '"template": "flux_light"' not in blob:
        errors.append("Missing flux_light toggle tiles")

    if not is_tablet and '"template": "flux_door"' not in blob:
        errors.append("Missing flux_door tiles for garage/shed quick actions")

    if "isDoorOpen(states[" in blob or 'isDoorOpen(states[' in blob:
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

    if "custom:mushroom-lock-card" in blob:
        errors.append(
            "Stale Mushroom card custom:mushroom-lock-card — pull latest branch and redeploy"
        )

    # mushroom-template-card is allowed inside the MetService weather panel popup only.
    if "custom:mushroom-template-card" in blob and WEATHER_PANEL_HASH not in overview_blob:
        errors.append(
            "Stale Mushroom card custom:mushroom-template-card — pull latest branch and redeploy"
        )

    # Gate buttons appear on phone overview and tablet Gates & Doors section.
    if "data:image/svg+xml;base64," not in blob:
        errors.append("Gate buttons missing inline SVG data-URI icons")
    if "binary_sensor.casa_luna_gate_status" not in blob:
        errors.append(
            "Gate Open missing status_entity binary_sensor.casa_luna_gate_status "
            "(lock pulse alone flips Closed while gate is still open)"
        )
    if "input_boolean.gate_hold_active" not in blob:
        errors.append("Gate buttons missing hold_entity input_boolean.gate_hold_active")
    if '"service": "lock.unlock"' not in blob and "lock.lock" not in blob:
        errors.append("Gate buttons missing lock service actions (unlock/lock)")
    if "return isOpen ? 'lock.lock' : 'lock.unlock';" not in blob:
        errors.append("Gate Latch should call lock.lock when already unlatched")
    gate_icons = ROOT / "www" / "flux-ui" / "icons"
    for name in ("vehicle-gate-closed.svg", "vehicle-gate-open.svg"):
        if not (gate_icons / name).exists():
            errors.append(f"Missing gate icon source file www/flux-ui/icons/{name}")

    if not is_tablet:
        if "/local/flux-ui/bitmoji/" not in blob:
            errors.append("Missing bitmoji hero avatar (/local/flux-ui/bitmoji/…)")
        if WEATHER_PANEL_HASH not in overview_blob:
            errors.append("Missing bottom weather panel (#weather-panel) on phone overview")
        if '"label": "Weather"' not in blob or "#weather-panel" not in blob:
            errors.append("Phone navbar missing Weather middle route (#weather-panel)")
        if "Good Morning!" not in overview_blob or "Pacific/Auckland" not in overview_blob:
            errors.append("Phone overview missing NZST greeting (Good Morning/Afternoon/Evening)")
        if "user.name" in overview_blob and "Good Morning" in overview_blob:
            errors.append("Phone greeting still includes HA user.name — use nameless NZ greeting")
        if "weather.homemetservice" not in blob:
            errors.append("Phone build missing MetService NZ weather.homemetservice")
        if '"refresh_interval": 360' not in blob:
            errors.append("Calendar missing refresh_interval 360 (mostly-static mode)")
        if '"show_countdown": true' in blob:
            errors.append("Calendar still has show_countdown — causes constant redraws")
        rooms_view = next((v for v in views if v.get("path") == "rooms"), None)
        rooms_blob = json.dumps(rooms_view) if rooms_view else ""
        if rooms_view and "custom:simple-tabs" not in rooms_blob:
            errors.append("Rooms view missing custom:simple-tabs (configuration errors expected otherwise)")
        if '"condition": "template"' in rooms_blob:
            errors.append(
                "Rooms view still uses condition:template — causes Configuration error cards"
            )

        # Music player checks only when media_players.yaml lists enabled players.
        # Offline builds use committed YAML — do not require live Sonos discovery.
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
                    1 for p in media_players if is_sonos_zone(p) and p.get("apple_tv")
                )
                if overview_blob.count('"entity_id":') < expected_panels:
                    errors.append(
                        "Music player popup missing per-zone mediocre entity_id cards "
                        f"(expected {expected_panels}, includes Apple TV TV-mode panels)"
                    )
                mp_start = overview_blob.find('"name": "Music Player"')
                mp_end = overview_blob.find('"popup_style"', mp_start)
                popup_blob = overview_blob[mp_start:mp_end] if mp_end > mp_start else ""
                if '"condition": "template"' in popup_blob:
                    errors.append(
                        "Music popup uses condition: template — conditional cards only support "
                        "state conditions; use binary_sensor.flux_ui_tv_* instead"
                    )
            if '"name": "Music Player"' in overview_blob:
                mp_start = overview_blob.find('"name": "Music Player"')
                mp_end = overview_blob.find('"popup_style"', mp_start)
                popup_blob = overview_blob[mp_start:mp_end] if mp_end > mp_start else ""
                if popup_blob and '"cards": [{"type": "custom:mushroom-chips-card"' not in popup_blob:
                    errors.append(
                        "Music popup must start with a single mushroom-chips-card zone picker"
                    )
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

    return errors


async def verify_live(ha_url: str, token: str) -> list[str]:
    from ha_common import ws_call

    errors: list[str] = []
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/dashboards/list"}]))[0]
    dash_paths = {d.get("url_path") for d in listed.get("result", [])}
    if "flux-ui" not in dash_paths:
        errors.append("Dashboard flux-ui not registered")

    cfg = (await ws_call(token, ha_url, [{"type": "lovelace/config", "url_path": "flux-ui", "force": True}]))[0]
    if not cfg.get("success"):
        errors.append(f"Could not load flux-ui config: {cfg.get('error')}")
        return errors

    views = cfg["result"].get("views", [])
    if not views:
        errors.append("flux-ui has no views")
    else:
        view_paths = {v.get("path") for v in views}
        for required in ("overview", "rooms", "scenes", "cameras"):
            if required not in view_paths:
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
        if "/local/flux-ui/bitmoji/" not in live_blob:
            errors.append("Live phone dashboard missing bitmoji hero — lovelace/config/save may have failed")
        if WEATHER_PANEL_HASH not in overview_blob:
            errors.append("Live phone dashboard missing #weather-panel")
        if '"label": "Weather"' not in live_blob:
            errors.append("Live phone navbar missing Weather route")
        if MUSIC_PLAYER_HASH not in overview_blob:
            errors.append("Live phone dashboard missing #music-player")
        rooms_live = next((v for v in views if v.get("path") == "rooms"), None)
        if rooms_live and '"condition": "template"' in json.dumps(rooms_live):
            errors.append("Live Rooms view still has condition:template Configuration errors")
        if rooms_live and "custom:simple-tabs" not in json.dumps(rooms_live):
            errors.append("Live Rooms view missing simple-tabs")
        if '"label": "Rooms"' not in live_blob:
            errors.append("Live navbar missing Rooms route (old Flux/Mobile/Solar nav)")
        if "kiosk_mode" not in live_blob or "hide_header" not in live_blob:
            errors.append(
                "Live config missing kiosk_mode — redeploy after kiosk-mode resource registered"
            )

    if "flux-ui-tablet" in dash_paths:
        tcfg = (
            await ws_call(
                token, ha_url, [{"type": "lovelace/config", "url_path": "flux-ui-tablet", "force": True}]
            )
        )[0]
        if tcfg.get("success"):
            tblob = json.dumps(tcfg["result"])
            if "Gates & Doors" not in tblob:
                errors.append("Live tablet dashboard missing Gates & Doors section")
            if '"days_to_show": 7' not in tblob:
                errors.append("Live tablet calendar not set to 7 days")
            if '"refresh_on_navigate": false' not in tblob:
                errors.append("Live tablet calendar should keep cache (refresh_on_navigate false)")
            if "custom:navbar-card" in tblob and '"label": "Home"' in tblob:
                errors.append("Live tablet still has bottom navbar covering Tesla cards")
            if "flux-tesla-charge-pulse" not in tblob:
                errors.append("Live tablet missing Tesla charging pulse glow")
            if '"type": "panel"' not in tblob:
                errors.append("Live tablet overview is not panel type")

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

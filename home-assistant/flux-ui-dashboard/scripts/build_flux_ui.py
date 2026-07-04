#!/usr/bin/env python3
"""Build Flux UI Lovelace config — MD3 / Flux visual language."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from md3_templates import (
    BUTTON_CARD_TEMPLATES,
    GLASS_CARD_MOD,
    TITLE_CARD_MOD,
    VIEW_CARD_MOD,
    wrap_glass,
    wrap_title,
)
from flux_navbar import navbar_section
from kiosk_config import KIOSK_MODE
from phase3_builders import (
    build_active_lights_section,
    build_home_status_section,
    build_open_garage_section,
    light_control_tile,
)

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
CONTEXT = ROOT / "context.yaml"
ROOMS = ROOT / "rooms.yaml"
GARAGE_DIR = ROOT.parent / "garage-doors"
sys.path.insert(0, str(GARAGE_DIR))

from garage_ui_helpers import (  # noqa: E402
    load_garage_doors,
    open_color_js,
    open_icon_js,
    open_label_js,
)


def load_entities() -> dict:
    cfg = yaml.safe_load(ENTITIES.read_text())
    cfg["quick_actions"]["garage"] = load_garage_doors()
    if ROOMS.exists():
        cfg["rooms"] = yaml.safe_load(ROOMS.read_text()).get("rooms", [])
    else:
        cfg["rooms"] = []
    if CONTEXT.exists():
        cfg["context"] = yaml.safe_load(CONTEXT.read_text())
    else:
        cfg["context"] = {}
    return cfg


def flux_view(
    *,
    title: str,
    path: str,
    icon: str,
    sections: list[dict],
    use_navbar_card: bool,
) -> dict:
    return {
        "title": title,
        "icon": icon,
        "path": path,
        "type": "sections",
        "max_columns": 2,
        "theme": "flux-ui-md3",
        "card_mod": VIEW_CARD_MOD,
        "sections": sections + [navbar_section(use_navbar_card=use_navbar_card)],
    }


def apply_md3_to_cards(obj: object) -> object:
    """Recursively add glass card-mod to cards imported from Mobile Home."""
    if isinstance(obj, list):
        return [apply_md3_to_cards(x) for x in obj]
    if not isinstance(obj, dict):
        return obj

    out = {k: apply_md3_to_cards(v) for k, v in obj.items()}

    if out.get("type") and out["type"] != "grid":
        existing = out.get("card_mod") or {}
        if isinstance(existing, dict):
            style = GLASS_CARD_MOD["style"]
            if "style" in existing:
                style = style + existing["style"]
            out["card_mod"] = {"style": style}
        elif "mushroom-title-card" in str(out.get("type", "")):
            out["card_mod"] = TITLE_CARD_MOD

    return out


def section_title(title: str, subtitle: str = "") -> dict:
    card: dict = {
        "type": "custom:mushroom-title-card",
        "title": title,
        "grid_options": {"columns": 12},
    }
    if subtitle:
        card["subtitle"] = subtitle
    return wrap_title(card)


def hero_card(weather_entity: str) -> dict:
    """Single Flux-style hero: weather icon + greeting + conditions (no duplicate chips)."""
    return {
        "type": "custom:button-card",
        "template": "flux_hero",
        "entity": weather_entity,
        "icon": "[[[ return entity.attributes?.condition ? `weather-${entity.attributes.condition}` : 'mdi:weather-partly-cloudy'; ]]]",
        "name": (
            "[[[\n"
            "  const h = new Date().getHours();\n"
            "  let g = 'Morning';\n"
            "  if (h >= 22 || h < 5) g = 'Night';\n"
            "  else if (h >= 18) g = 'Evening';\n"
            "  else if (h >= 12) g = 'Afternoon';\n"
            "  return `${g}, ${user.name}!`;\n"
            "]]]"
        ),
        "label": (
            "[[[\n"
            "  const cond = entity.attributes?.friendly_name || entity.attributes?.condition || '';\n"
            "  const temp = entity.attributes?.temperature;\n"
            "  const time = new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});\n"
            "  const wx = temp != null ? `${cond} · ${temp}°` : String(cond);\n"
            "  return `${wx} · ${time}`;\n"
            "]]]"
        ),
        "grid_options": {"columns": 12},
    }


def build_hero(weather_entity: str) -> dict:
    return {"type": "grid", "cards": [hero_card(weather_entity)]}


def lock_action(entity: str, name: str, *, columns: int = 6) -> dict:
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "entity": entity,
        "name": name,
        "icon": "mdi:gate",
        "label": "[[[ return entity.state === 'locked' ? 'Locked' : 'Unlocked'; ]]]",
        "tap_action": {"action": "toggle"},
        "grid_options": {"columns": columns},
    }


def garage_action(door: dict, *, columns: int = 6) -> dict:
    sensor = door["sensor"]
    invert = door.get("invert", False)
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "entity": sensor,
        "name": door["name"],
        "icon": open_icon_js(sensor, invert=invert),
        "label": open_label_js(sensor, invert=invert),
        "tap_action": {
            "action": "call-service",
            "service": "script.turn_on",
            "service_data": {"entity_id": door["script"]},
        },
        "styles": {
            "icon": [{"color": open_color_js(sensor, invert=invert)}]
        },
        "grid_options": {"columns": columns},
    }


def scene_action(
    name: str, subtitle: str, icon: str, service: str, target: str, *, columns: int = 6
) -> dict:
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "name": name,
        "label": subtitle,
        "icon": icon,
        "tap_action": {
            "action": "perform-action",
            "perform_action": service,
            "target": {"entity_id": target},
        },
        "grid_options": {"columns": columns},
    }


def light_tile(entity: str, name: str, *, columns: int = 6) -> dict:
    return {
        "type": "custom:button-card",
        "template": "flux_light",
        "entity": entity,
        "name": name,
        "icon": "mdi:lightbulb",
        "label": (
            "[[[\n"
            "  if (entity.state !== 'on') return 'Off';\n"
            "  const b = entity.attributes.brightness;\n"
            "  return b != null ? Math.round(b / 255 * 100) + '%' : 'On';\n"
            "]]]"
        ),
        "tap_action": {"action": "toggle"},
        "hold_action": {"action": "more-info"},
        "grid_options": {"columns": columns},
    }


def build_quick_actions(cfg: dict) -> dict:
    col = 6
    cards: list[dict] = [section_title("Quick Actions", "Tap to control")]
    for item in cfg["quick_actions"]["gate"]:
        cards.append(lock_action(item["entity"], item["name"], columns=col))
    for item in cfg["quick_actions"]["garage"]:
        cards.append(garage_action(item, columns=col))
    for item in cfg["quick_actions"]["actions"]:
        cards.append(
            scene_action(
                item["name"],
                item["subtitle"],
                item["icon"],
                item["service"],
                item["target"],
                columns=col,
            )
        )
    return {"type": "grid", "cards": cards}


def build_favourite_lights(cfg: dict) -> dict:
    cards: list[dict] = [section_title("Favourite lights", "Most used")]
    for item in cfg["favourite_lights"]:
        cards.append(light_control_tile(item["entity"], item["name"], columns=6))
    return {"type": "grid", "cards": cards}


def build_room_detail(room: dict) -> dict:
    cards: list[dict] = [
        section_title(room["name"], room.get("subtitle", "")),
        {
            "type": "custom:button-card",
            "template": "flux_action",
            "name": "Back to Rooms",
            "icon": "mdi:arrow-left",
            "label": "All areas",
            "tap_action": {"action": "navigate", "navigation_path": "/flux-ui/rooms"},
            "grid_options": {"columns": 12},
        },
    ]
    for light in room.get("lights", []):
        cards.append(light_control_tile(light["entity"], light["name"], columns=6))
    return {"type": "grid", "cards": cards}


def build_overview_sections(
    cfg: dict,
    weather: str,
    climate: dict,
    *,
    use_auto_entities: bool,
) -> list[dict]:
    sections: list[dict] = [
        build_hero(weather),
        build_home_status_section(cfg),
        build_quick_actions(cfg),
    ]
    if use_auto_entities:
        sections.append(build_active_lights_section(cfg))
    open_garage = build_open_garage_section(cfg)
    if open_garage:
        sections.append(open_garage)
    sections.extend(
        [
            climate,
            build_favourite_lights(cfg),
        ]
    )
    return sections


def room_tile(name: str, icon: str, subtitle: str, path: str, *, columns: int = 6) -> dict:
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "name": name,
        "label": subtitle,
        "icon": icon,
        "tap_action": {"action": "navigate", "navigation_path": f"/flux-ui/room/{path}"},
        "grid_options": {"columns": columns},
    }


def build_rooms_index(cfg: dict) -> dict:
    cards: list[dict] = [section_title("Rooms", "Choose an area")]
    for room in cfg.get("rooms", []):
        cards.append(
            room_tile(
                room["name"],
                room.get("icon", "mdi:home-outline"),
                room.get("subtitle", ""),
                room["path"],
                columns=6,
            )
        )
    return {"type": "grid", "cards": cards}



def build_scenes_view(cfg: dict) -> dict:
    cards: list[dict] = [section_title("Scenes", "Quick lighting")]
    for item in cfg["quick_actions"]["actions"]:
        cards.append(
            scene_action(
                item["name"],
                item["subtitle"],
                item["icon"],
                item["service"],
                item["target"],
                columns=6,
            )
        )
    cards.append(
        scene_action(
            "All lights",
            "Toggle whole home",
            "mdi:lightbulb-group",
            "homeassistant.toggle",
            "light.all_lights",
            columns=6,
        )
    )
    return {"type": "grid", "cards": cards}


def build_lights_view(cfg: dict, *, use_auto_entities: bool = False) -> dict:
    cards: list[dict] = [section_title("Lights", "All areas")]
    if use_auto_entities:
        active = build_active_lights_section(cfg)
        cards.extend(active["cards"][1:] if len(active["cards"]) > 1 else [])
    for item in cfg["favourite_lights"]:
        cards.append(light_control_tile(item["entity"], item["name"], columns=6))
    return {"type": "grid", "cards": cards}


def build_cameras_view(camera_section: dict | None) -> dict:
    if camera_section:
        return apply_md3_to_cards(camera_section)
    return {
        "type": "grid",
        "cards": [
            section_title("Cameras", "Live feeds"),
            wrap_glass(
                {
                    "type": "markdown",
                    "content": (
                        "No camera section imported yet.\n\n"
                        "Deploy with SMB mount so Mobile Home cameras are copied, "
                        "or add camera entities in a future update."
                    ),
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }


def extract_section_from_mobile_home(config: dict, *, path: str | None = None, title: str | None = None) -> dict | None:
    for view in config.get("views", []):
        if path and view.get("path") == path and view.get("sections"):
            return copy.deepcopy(view["sections"][0])
        if title and view.get("sections"):
            for section in view["sections"]:
                for card in section.get("cards", []):
                    if card.get("type") == "custom:mushroom-title-card" and card.get("title") == title:
                        return copy.deepcopy(section)
    return None


def climate_fallback_section(weather_entity: str) -> dict:
    return {
        "type": "grid",
        "cards": [
            section_title("Climate", "Live conditions"),
            wrap_glass(
                {
                    "type": "custom:mushroom-entity-card",
                    "entity": weather_entity,
                    "name": "Forecast",
                    "layout": "horizontal",
                    "fill_container": True,
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }


def extract_climate_from_mobile_home(config: dict) -> dict | None:
    return extract_section_from_mobile_home(config, path="home")


def build_config(
    *,
    climate_section: dict | None = None,
    camera_section: dict | None = None,
    use_navbar_card: bool = True,
    use_kiosk: bool = True,
    use_auto_entities: bool = True,
) -> dict:
    cfg = load_entities()
    weather = cfg.get("weather", "weather.forecast_home")
    climate = (
        apply_md3_to_cards(climate_section)
        if climate_section
        else climate_fallback_section(weather)
    )

    overview = build_overview_sections(
        cfg,
        weather,
        climate,
        use_auto_entities=use_auto_entities,
    )

    views: list[dict] = [
        flux_view(
            title="Overview",
            path="overview",
            icon="mdi:home",
            sections=overview,
            use_navbar_card=use_navbar_card,
        ),
        flux_view(
            title="Rooms",
            path="rooms",
            icon="mdi:sofa",
            sections=[build_rooms_index(cfg)],
            use_navbar_card=use_navbar_card,
        ),
        flux_view(
            title="Scenes",
            path="scenes",
            icon="mdi:layers",
            sections=[build_scenes_view(cfg)],
            use_navbar_card=use_navbar_card,
        ),
        flux_view(
            title="Lights",
            path="lights",
            icon="mdi:lightbulb-group",
            sections=[build_lights_view(cfg, use_auto_entities=use_auto_entities)],
            use_navbar_card=use_navbar_card,
        ),
        flux_view(
            title="Cameras",
            path="cameras",
            icon="mdi:cctv",
            sections=[build_cameras_view(camera_section)],
            use_navbar_card=use_navbar_card,
        ),
    ]

    for room in cfg.get("rooms", []):
        views.append(
            flux_view(
                title=room["name"],
                path=f"room/{room['path']}",
                icon=room.get("icon", "mdi:home-outline"),
                sections=[build_room_detail(room)],
                use_navbar_card=use_navbar_card,
            )
        )

    out: dict = {
        "title": "Flux UI",
        "button_card_templates": copy.deepcopy(BUTTON_CARD_TEMPLATES),
        "views": views,
    }
    if use_kiosk:
        out["kiosk_mode"] = copy.deepcopy(KIOSK_MODE)
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mobile-home-storage", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "generated" / "lovelace.flux_ui.json",
    )
    parser.add_argument(
        "--no-navbar-card",
        action="store_true",
        help="Use mushroom chip nav fallback (navbar-card HACS not installed)",
    )
    parser.add_argument(
        "--no-kiosk",
        action="store_true",
        help="Do not hide HA header (debug / before kiosk-mode HACS installed)",
    )
    parser.add_argument(
        "--no-auto-entities",
        action="store_true",
        help="Disable auto-entities active lights section",
    )
    args = parser.parse_args()

    climate_section = None
    camera_section = None
    if args.mobile_home_storage and args.mobile_home_storage.exists():
        raw = json.loads(args.mobile_home_storage.read_text())
        mobile_cfg = raw["data"]["config"]
        climate_section = extract_climate_from_mobile_home(mobile_cfg)
        if climate_section:
            print("Imported climate section from Mobile Home")
        camera_section = extract_section_from_mobile_home(mobile_cfg, path="cameras")
        if camera_section:
            print("Imported cameras section from Mobile Home")

    config = build_config(
        climate_section=climate_section,
        camera_section=camera_section,
        use_navbar_card=not args.no_navbar_card,
        use_kiosk=not args.no_kiosk,
        use_auto_entities=not args.no_auto_entities,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "minor_version": 1,
        "key": "lovelace.flux_ui",
        "data": {"config": config},
    }
    args.output.write_text(json.dumps(payload, indent=2))
    overview = next(v for v in config["views"] if v["path"] == "overview")
    print(
        f"Wrote {args.output} ({len(config['views'])} views, "
        f"{len(overview['sections'])} overview sections)"
    )


if __name__ == "__main__":
    main()

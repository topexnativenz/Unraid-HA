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

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
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
    return cfg


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
        cards.append(light_tile(item["entity"], item["name"], columns=6))
    return {"type": "grid", "cards": cards}


def build_navbar(*, use_navbar_card: bool = True) -> dict:
    if use_navbar_card:
        nav = {
            "type": "custom:navbar-card",
            "routes": [
                {"url": "/flux-ui/overview", "icon": "mdi:view-dashboard-variant", "label": "Flux"},
                {"url": "/mobile-home/home", "icon": "mdi:cellphone", "label": "Mobile"},
                {"url": "/solar-dashboard", "icon": "mdi:solar-power", "label": "Solar"},
            ],
            "mobile": {"show_labels": True},
            "styles": {
                "card": [
                    {"background": "color-mix(in srgb, var(--md-sys-color-surface-container) 88%, transparent)"},
                    {"backdrop-filter": "blur(20px)"},
                    {"border-radius": "999px"},
                    {"margin": "0 12px 12px"},
                    {"border": "1px solid color-mix(in srgb, var(--md-sys-color-outline-variant) 40%, transparent)"},
                ]
            },
        }
    else:
        # Fallback when navbar-card HACS plugin is not installed (avoids Configuration error).
        nav = {
            "type": "custom:mushroom-chips-card",
            "alignment": "center",
            "chips": [
                {
                    "type": "template",
                    "icon": "mdi:view-dashboard-variant",
                    "icon_color": "primary",
                    "content": "Flux",
                    "tap_action": {"action": "navigate", "navigation_path": "/flux-ui/overview"},
                },
                {
                    "type": "template",
                    "icon": "mdi:cellphone",
                    "content": "Mobile",
                    "tap_action": {"action": "navigate", "navigation_path": "/mobile-home/home"},
                },
                {
                    "type": "template",
                    "icon": "mdi:solar-power",
                    "content": "Solar",
                    "tap_action": {"action": "navigate", "navigation_path": "/solar-dashboard"},
                },
            ],
            "card_mod": GLASS_CARD_MOD,
        }
    nav["grid_options"] = {"columns": 12}
    return {"type": "grid", "cards": [nav]}


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


def build_config(
    *,
    climate_section: dict | None = None,
    use_navbar_card: bool = True,
) -> dict:
    cfg = load_entities()
    weather = cfg.get("weather", "weather.forecast_home")
    climate = (
        apply_md3_to_cards(climate_section)
        if climate_section
        else climate_fallback_section(weather)
    )

    return {
        "title": "Flux UI",
        "button_card_templates": copy.deepcopy(BUTTON_CARD_TEMPLATES),
        "views": [
            {
                "title": "Overview",
                "icon": "mdi:view-dashboard-variant",
                "path": "overview",
                "type": "sections",
                "max_columns": 2,
                "theme": "flux-ui-md3",
                "card_mod": VIEW_CARD_MOD,
                "sections": [
                    build_hero(weather),
                    climate,
                    build_quick_actions(cfg),
                    build_favourite_lights(cfg),
                    build_navbar(use_navbar_card=use_navbar_card),
                ],
            }
        ],
    }


def extract_climate_from_mobile_home(config: dict) -> dict | None:
    for view in config.get("views", []):
        if view.get("path") == "home" and view.get("sections"):
            return copy.deepcopy(view["sections"][0])
    return None


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
    args = parser.parse_args()

    climate_section = None
    if args.mobile_home_storage and args.mobile_home_storage.exists():
        raw = json.loads(args.mobile_home_storage.read_text())
        climate_section = extract_climate_from_mobile_home(raw["data"]["config"])
        if climate_section:
            print("Imported climate section from Mobile Home")

    config = build_config(
        climate_section=climate_section,
        use_navbar_card=not args.no_navbar_card,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "minor_version": 1,
        "key": "lovelace.flux_ui",
        "data": {"config": config},
    }
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.output} ({len(config['views'][0]['sections'])} overview sections)")


if __name__ == "__main__":
    main()

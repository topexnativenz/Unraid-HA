#!/usr/bin/env python3
"""Build Flux UI Lovelace config (overview = Mobile Home Home tab entities, MD3 styling)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"

MD3_CARD_MOD = {
    "style": (
        "ha-card {\n"
        "  border-radius: 28px;\n"
        "  background: color-mix(in srgb, var(--card-background-color) 88%, transparent);\n"
        "  backdrop-filter: blur(12px);\n"
        "  box-shadow: 0 1px 2px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.08);\n"
        "  border: 1px solid color-mix(in srgb, var(--divider-color) 40%, transparent);\n"
        "}\n"
    )
}


def load_entities() -> dict:
    return yaml.safe_load(ENTITIES.read_text())


def wrap_md3(card: dict) -> dict:
    out = copy.deepcopy(card)
    existing = out.get("card_mod") or {}
    if isinstance(existing, dict):
        merged = {**MD3_CARD_MOD, **existing}
        if "style" in existing and "style" in MD3_CARD_MOD:
            merged["style"] = MD3_CARD_MOD["style"] + existing["style"]
        out["card_mod"] = merged
    return out


def mushroom_light(entity: str, *, name: str | None = None, columns: int = 6, compact: bool = False) -> dict:
    card: dict = {
        "type": "custom:mushroom-light-card",
        "entity": entity,
        "fill_container": True,
        "show_brightness_control": not compact,
        "collapsible_controls": compact,
        "use_light_color": True,
        "grid_options": {"columns": columns},
    }
    if name:
        card["name"] = name
    if compact:
        card["layout"] = "horizontal"
    return wrap_md3(card)


def mushroom_lock(entity: str, name: str, *, columns: int = 6) -> dict:
    return wrap_md3(
        {
            "type": "custom:mushroom-lock-card",
            "entity": entity,
            "name": name,
            "fill_container": True,
            "grid_options": {"columns": columns},
        }
    )


def mushroom_garage_pulse(
    state_entity: str, label: str, script_id: str, *, columns: int = 6
) -> dict:
    return wrap_md3(
        {
            "type": "custom:mushroom-template-card",
            "entity": state_entity,
            "primary": label,
            "fill_container": True,
            "icon": "{{ 'mdi:garage-open' if is_state(entity, 'on') else 'mdi:garage' }}",
            "icon_color": "{{ 'red' if is_state(entity, 'on') else 'grey' }}",
            "tap_action": {
                "action": "call-service",
                "service": "script.turn_on",
                "target": {"entity_id": script_id},
            },
            "grid_options": {"columns": columns},
        }
    )


def mushroom_action(
    primary: str,
    secondary: str,
    icon: str,
    *,
    icon_color: str = "grey",
    columns: int = 6,
    tap_action: dict,
) -> dict:
    return wrap_md3(
        {
            "type": "custom:mushroom-template-card",
            "primary": primary,
            "secondary": secondary,
            "icon": icon,
            "icon_color": icon_color,
            "layout": "horizontal",
            "fill_container": True,
            "tap_action": tap_action,
            "grid_options": {"columns": columns},
        }
    )


def build_header(weather_entity: str) -> dict:
    return {
        "type": "grid",
        "cards": [
            wrap_md3(
                {
                    "type": "custom:mushroom-template-card",
                    "primary": "{{ now().strftime('%A') }}",
                    "secondary": "{{ now().strftime('%d %B · %H:%M') }}",
                    "icon": "mdi:home-assistant",
                    "icon_color": "primary",
                    "layout": "horizontal",
                    "fill_container": True,
                    "grid_options": {"columns": 12},
                }
            ),
            wrap_md3(
                {
                    "type": "custom:mushroom-entity-card",
                    "entity": weather_entity,
                    "name": "Weather",
                    "layout": "horizontal",
                    "fill_container": True,
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }


def build_quick_actions(cfg: dict) -> dict:
    col = 6
    cards: list[dict] = [
        wrap_md3(
            {
                "type": "custom:mushroom-title-card",
                "title": "Quick Actions",
                "subtitle": "Tap to control",
                "grid_options": {"columns": 12},
            }
        )
    ]
    for item in cfg["quick_actions"]["gate"]:
        cards.append(mushroom_lock(item["entity"], item["name"], columns=col))
    for item in cfg["quick_actions"]["garage"]:
        cards.append(
            mushroom_garage_pulse(
                item["state_entity"], item["name"], item["script"], columns=col
            )
        )
    for item in cfg["quick_actions"]["actions"]:
        cards.append(
            mushroom_action(
                item["name"],
                item["subtitle"],
                item["icon"],
                icon_color=item.get("icon_color", "grey"),
                columns=col,
                tap_action={
                    "action": "perform-action",
                    "perform_action": item["service"],
                    "target": {"entity_id": item["target"]},
                },
            )
        )
    return {"type": "grid", "cards": cards}


def build_favourite_lights(cfg: dict) -> dict:
    cards: list[dict] = [
        wrap_md3(
            {
                "type": "custom:mushroom-title-card",
                "title": "Favourite lights",
                "subtitle": "Most used",
                "grid_options": {"columns": 12},
            }
        )
    ]
    for item in cfg["favourite_lights"]:
        cards.append(
            mushroom_light(item["entity"], name=item["name"], columns=6, compact=True)
        )
    return {"type": "grid", "cards": cards}


def climate_fallback_section(weather_entity: str) -> dict:
    """Used when Mobile Home climate section cannot be read from HA storage."""
    return {
        "type": "grid",
        "cards": [
            wrap_md3(
                {
                    "type": "custom:mushroom-title-card",
                    "title": "Climate",
                    "subtitle": "Add climate chips from Mobile Home via deploy",
                    "grid_options": {"columns": 12},
                }
            ),
            wrap_md3(
                {
                    "type": "custom:mushroom-entity-card",
                    "entity": weather_entity,
                    "name": "Forecast",
                    "fill_container": True,
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }


def build_config(*, climate_section: dict | None = None) -> dict:
    cfg = load_entities()
    weather = cfg.get("weather", "weather.forecast_home")
    climate = climate_section if climate_section else climate_fallback_section(weather)

    return {
        "title": "Flux UI",
        "views": [
            {
                "title": "Overview",
                "icon": "mdi:view-dashboard-variant",
                "path": "overview",
                "type": "sections",
                "max_columns": 2,
                "theme": "flux-ui-md3",
                "sections": [
                    build_header(weather),
                    climate,
                    build_quick_actions(cfg),
                    build_favourite_lights(cfg),
                ],
            }
        ],
    }


def extract_climate_from_mobile_home(config: dict) -> dict | None:
    """Return first section from Mobile Home Home view (climate chips/graph)."""
    for view in config.get("views", []):
        if view.get("path") == "home" and view.get("sections"):
            return copy.deepcopy(view["sections"][0])
    return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mobile-home-storage",
        type=Path,
        help="Path to .storage/lovelace.mobile_home for climate section import",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "generated" / "lovelace.flux_ui.json",
    )
    args = parser.parse_args()

    climate_section = None
    if args.mobile_home_storage and args.mobile_home_storage.exists():
        raw = json.loads(args.mobile_home_storage.read_text())
        climate_section = extract_climate_from_mobile_home(raw["data"]["config"])
        if climate_section:
            print("Imported climate section from Mobile Home")

    config = build_config(climate_section=climate_section)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "minor_version": 1, "key": "lovelace.flux_ui", "data": {"config": config}}
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.output} ({len(config['views'][0]['sections'])} overview sections)")


if __name__ == "__main__":
    main()

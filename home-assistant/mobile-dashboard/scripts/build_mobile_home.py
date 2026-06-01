#!/usr/bin/env python3
"""Rebuild lovelace.mobile_home storage config."""

from __future__ import annotations

import copy
import json
from pathlib import Path

STORAGE_KEY = "lovelace.mobile_home"
STORAGE = Path("/tmp/ha-config-smb/.storage") / STORAGE_KEY
DASHBOARDS = Path("/tmp/ha-config-smb/.storage/lovelace_dashboards")


def mushroom_light(
    entity: str,
    *,
    columns: int = 6,
    name: str | None = None,
    compact: bool = False,
) -> dict:
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
    return card


def mushroom_lock(entity: str, name: str, *, columns: int = 6) -> dict:
    return {
        "type": "custom:mushroom-lock-card",
        "entity": entity,
        "name": name,
        "fill_container": True,
        "grid_options": {"columns": columns},
    }


def mushroom_lock_style(
    entity: str,
    name: str,
    *,
    columns: int = 6,
    tap_action: dict | None = None,
) -> dict:
    """Same layout as gate lock cards; entity-card for switch/cover actions."""
    card: dict = {
        "type": "custom:mushroom-entity-card",
        "entity": entity,
        "name": name,
        "fill_container": True,
        "grid_options": {"columns": columns},
    }
    card["tap_action"] = tap_action or {"action": "toggle"}
    return card


def mushroom_garage_pulse(
    state_entity: str,
    label: str,
    script_id: str,
    *,
    columns: int = 6,
) -> dict:
    """Pulse momentary relay via script; red/grey from tracked open boolean."""
    return {
        "type": "custom:mushroom-template-card",
        "entity": state_entity,
        "primary": label,
        "fill_container": True,
        "icon": "{{ 'mdi:garage-open' if is_state(entity, 'on') else 'mdi:garage' }}",
        "icon_color": "{{ 'red' if is_state(entity, 'on') else 'grey' }}",
        # call-service works reliably on Companion + mushroom-template-card
        "tap_action": {
            "action": "call-service",
            "service": "script.turn_on",
            "target": {"entity_id": script_id},
        },
        "grid_options": {"columns": columns},
    }


def mushroom_entity(
    entity: str,
    name: str,
    *,
    icon: str | None = None,
    icon_color: str | None = None,
    columns: int = 6,
) -> dict:
    card: dict = {
        "type": "custom:mushroom-entity-card",
        "entity": entity,
        "name": name,
        "fill_container": True,
        "tap_action": {"action": "toggle"},
        "grid_options": {"columns": columns},
    }
    if icon:
        card["icon"] = icon
    if icon_color:
        card["icon_color"] = icon_color
    return card


def mushroom_cover(entity: str, name: str, *, columns: int = 6) -> dict:
    return {
        "type": "custom:mushroom-cover-card",
        "entity": entity,
        "name": name,
        "fill_container": True,
        "show_buttons_control": True,
        "show_position_control": False,
        "icon": "mdi:garage",
        "grid_options": {"columns": columns},
    }


def mushroom_action(
    primary: str,
    secondary: str,
    icon: str,
    *,
    icon_color: str = "grey",
    columns: int = 6,
    tap_action: dict,
) -> dict:
    return {
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


def lights_grid(title: str, subtitle: str, entities: list[str], *, col: int = 6) -> dict:
    cards: list[dict] = [
        {"type": "custom:mushroom-title-card", "title": title, "subtitle": subtitle}
    ]
    for e in entities:
        cards.append(mushroom_light(e, columns=col))
    return {"type": "grid", "cards": cards}


TOP_FIVE: list[tuple[str, str]] = [
    ("light.kitchen", "Kitchen"),
    ("light.dining_room", "Kitchen dining"),
    ("light.main_atrium", "Main area"),
    ("light.garage", "Garage"),
    ("light.entry_centre", "Entry"),
    ("light.main_footlights", "Hall footlights"),
    ("light.all_lights", "All lights"),
    ("light.living_center", "Living"),
]

LIGHT_GROUPS: list[tuple[str, str, list[str]]] = [
    ("Whole home", "Master switches", ["light.all_lights", "light.ground_floor_lights"]),
    (
        "Entry & arrival",
        "Front door and night path",
        [
            "light.night_arrival",
            "light.entry",
            "light.entry_centre",
            "light.entry_high",
            "light.outside_entry",
            "light.covered_entry",
            "light.outside_entry_downlights",
        ],
    ),
    (
        "Kitchen & dining",
        "",
        [
            "light.kitchen",
            "light.dining_room",
            "light.dining_centre",
            "light.dining_pic_light",
            "light.cooking",
            "light.scullery",
            "light.sink",
            "light.walkway",
            "light.bar",
            "light.breakfast_high",
            "light.c_bus_light_036_c_bus_light_036",
        ],
    ),
    (
        "Living & media",
        "",
        [
            "light.living_center",
            "light.white_lounge",
            "light.black_lounge",
            "light.white_lounge_centre",
            "light.white_lounge_surround",
            "light.white_lounge_surround_2",
            "light.white_lounge_cabinet",
            "light.main_atrium",
            "light.media_room",
            "light.media_room_centre",
            "light.media_room_rear",
            "light.media_room_door",
            "light.media_room_right",
            "light.c_bus_light_002_c_bus_light_002",
            "light.c_bus_light_003_c_bus_light_003",
            "light.c_bus_light_004_c_bus_light_004",
        ],
    ),
    (
        "Hall & stairs",
        "Footlights and passages",
        [
            "light.main_footlights",
            "light.kids_hall_footlights",
            "light.stair_footlights",
            "light.lights_hall_table",
        ],
    ),
    (
        "Master bedroom",
        "",
        [
            "light.master_bedroom",
            "light.c_bus_light_067_c_bus_light_067",
            "light.c_bus_light_068_c_bus_light_068",
            "light.c_bus_light_069_c_bus_light_069",
            "light.c_bus_light_070_c_bus_light_070",
            "light.c_bus_light_071_c_bus_light_071",
        ],
    ),
    (
        "Upstairs",
        "Office, landing, ensuite",
        [
            "light.office",
            "light.c_bus_light_062_c_bus_light_062",
            "light.c_bus_light_063_c_bus_light_063",
            "light.c_bus_light_064_c_bus_light_064",
            "light.c_bus_light_065_c_bus_light_065",
            "light.c_bus_light_066_c_bus_light_066",
            "light.c_bus_light_072_c_bus_light_072",
            "light.c_bus_light_073_c_bus_light_073",
            "light.c_bus_light_074_c_bus_light_074",
            "light.c_bus_light_075_c_bus_light_075",
            "light.c_bus_light_076_c_bus_light_076",
            "light.c_bus_light_078_c_bus_light_078",
            "light.c_bus_light_021_c_bus_light_021",
        ],
    ),
    (
        "Outside",
        "Garden, pool, garage exterior",
        [
            "light.outside_area",
            "light.outside_area_downlights",
            "light.outside_black_lounge",
            "light.outside_garage",
            "light.outside_laundry",
            "light.outside_rainas",
            "light.pool_uplights",
            "light.garage",
            "light.c_bus_light_039_c_bus_light_039",
            "light.c_bus_light_040_c_bus_light_040",
            "light.c_bus_light_061_c_bus_light_061",
        ],
    ),
]


def section_by_title(sections: list[dict], title: str) -> dict:
    for sec in sections:
        for card in sec.get("cards", []):
            if card.get("type") == "custom:mushroom-title-card" and card.get("title") == title:
                return sec
    raise KeyError(title)


def build_quick_actions() -> dict:
    """Uniform 50% width (columns 6) cards matching gate button sizing."""
    col = 6
    cards: list[dict] = [
        {
            "type": "custom:mushroom-title-card",
            "title": "Quick Actions",
            "subtitle": "Tap to control",
            "grid_options": {"columns": 12},
        },
        mushroom_lock("lock.gate_intercom_gate_open", "Gate Open", columns=col),
        mushroom_lock("lock.gate_intercom_gate_latch", "Gate Latch", columns=col),
    ]
    cards.extend(
        [
            mushroom_garage_pulse(
                "input_boolean.house_garage_door_open",
                "House Garage",
                "script.pulse_house_garage_door",
                columns=col,
            ),
            mushroom_garage_pulse(
                "input_boolean.main_shed_door_open",
                "Main Shed",
                "script.pulse_main_shed_door",
                columns=col,
            ),
            mushroom_garage_pulse(
                "input_boolean.second_shed_door_open",
                "Second Shed",
                "script.pulse_second_shed_door",
                columns=col,
            ),
        ]
    )
    cards.extend(
        [
            mushroom_action(
                "All Off",
                "Turn off all lights",
                "mdi:lightbulb-off-outline",
                icon_color="grey",
                columns=col,
                tap_action={
                    "action": "perform-action",
                    "perform_action": "light.turn_off",
                    "target": {"entity_id": "light.all_lights"},
                },
            ),
            mushroom_action(
                "Goodnight",
                "Night arrival on",
                "mdi:weather-night",
                icon_color="indigo",
                columns=col,
                tap_action={
                    "action": "perform-action",
                    "perform_action": "light.turn_on",
                    "target": {"entity_id": "light.night_arrival"},
                },
            ),
        ]
    )
    return {"type": "grid", "cards": cards}


def build_top_lights() -> dict:
    cards: list[dict] = [
        {
            "type": "custom:mushroom-title-card",
            "title": "Favourite lights",
            "subtitle": "Most used",
            "grid_options": {"columns": 12},
        }
    ]
    for entity, name in TOP_FIVE:
        cards.append(mushroom_light(entity, name=name, columns=6, compact=True))
    return {"type": "grid", "cards": cards}


def build_lights_view(sections: list[dict]) -> dict:
    old = section_by_title(sections, "Lights")
    on_filter = old["cards"][-1]
    return {
        "title": "Lights",
        "path": "lights",
        "icon": "mdi:lightbulb-group",
        "type": "sections",
        "max_columns": 2,
        "sections": [lights_grid(t, s, e) for t, s, e in LIGHT_GROUPS]
        + [{"type": "grid", "cards": [copy.deepcopy(on_filter)]}],
    }


def load_raw() -> dict:
    for path in (STORAGE, STORAGE.parent / f"{STORAGE_KEY}.bak-20260525"):
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text())
            if raw.get("data", {}).get("config", {}).get("views"):
                return raw
        except json.JSONDecodeError:
            continue
    raise SystemExit(f"No valid {STORAGE_KEY} or backup on mount")


def load_legacy_sections() -> list[dict]:
    """Original home sections (12+) from backup."""
    bak = STORAGE.parent / f"{STORAGE_KEY}.bak-20260525"
    if not bak.exists():
        raise SystemExit(f"Missing {bak}")
    raw = json.loads(bak.read_text())
    return raw["data"]["config"]["views"][0]["sections"]


def load_tab_section(path: str, title: str) -> dict:
    """Reuse a tab section from already-split dashboard on disk."""
    raw = json.loads(STORAGE.read_text())
    for view in raw["data"]["config"]["views"]:
        if view.get("path") == path and view.get("sections"):
            return view["sections"][0]
    return section_by_title(load_legacy_sections(), title)


def main() -> None:
    raw = load_raw()
    legacy = load_legacy_sections()
    climate = legacy[0]

    raw["data"]["config"] = {
        "title": "Mobile Home",
        "views": [
            {
                "title": "Home",
                "icon": "mdi:home",
                "path": "home",
                "type": "sections",
                "max_columns": 2,
                "sections": [
                    climate,
                    build_quick_actions(),
                    build_top_lights(),
                ],
            },
            {
                "title": "Tesla",
                "path": "tesla",
                "icon": "mdi:car-electric",
                "type": "sections",
                "max_columns": 2,
                "sections": [section_by_title(legacy, "Tesla")],
            },
            {
                "title": "Cameras",
                "path": "cameras",
                "icon": "mdi:cctv",
                "type": "sections",
                "max_columns": 2,
                "sections": [section_by_title(legacy, "Cameras")],
            },
            build_lights_view(legacy),
        ],
    }
    STORAGE.write_text(json.dumps(raw, indent=2))

    dash = json.loads(DASHBOARDS.read_text())
    for item in dash["data"]["items"]:
        if item.get("id") == "dashboard_music":
            item["show_in_sidebar"] = False
    DASHBOARDS.write_text(json.dumps(dash, indent=2))
    print("Updated mobile_home (4 views) and hid Music sidebar dashboard")


if __name__ == "__main__":
    main()

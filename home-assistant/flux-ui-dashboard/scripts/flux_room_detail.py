"""Flux UI room detail page — ElementZoom Living reference layout."""

from __future__ import annotations

from flux_door_builders import build_doors_status_section
from flux_layouts import _lights_tile_grid, _title, build_room_status_chips
from flux_navbar import (
    URL_PREFIX,
    room_camera_navigation_path,
    room_grid_navigation_path,
    room_navigation_path,
)
from flux_room_sensors import ROOM_STATUS_ROW_HTML
from md3_templates import merge_card_mod, wrap_glass, wrap_title

DEFAULT_FEATURES: list[dict] = [
    {"name": "Presence Sensor", "icon": "mdi:motion-sensor", "stub": True},
    {"name": "Movie Mode", "icon": "mdi:movie-off-outline", "stub": True},
    {"name": "Adaptive Lighting", "icon": "mdi:lightbulb-auto-outline", "stub": True},
]

FAB_STACK_MOD = {
    "style": (
        "ha-card {\n"
        "  position: fixed !important;\n"
        "  bottom: 108px !important;\n"
        "  right: 12px !important;\n"
        "  width: min(188px, 44vw) !important;\n"
        "  z-index: 8 !important;\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "  pointer-events: none !important;\n"
        "  padding: 0 !important;\n"
        "}\n"
        "#root, .grid, hui-grid-card { pointer-events: auto !important; }\n"
    )
}

SUBNAV_MOD = {
    "style": (
        "ha-card {\n"
        "  border-radius: 999px !important;\n"
        "  padding: 4px 6px !important;\n"
        "}\n"
        "mushroom-chip {\n"
        "  flex: 1;\n"
        "  justify-content: center;\n"
        "}\n"
    )
}


def _full_width(card: dict) -> dict:
    card = dict(card)
    card["grid_options"] = {"columns": 12}
    return card


def build_room_status_chips_auto(room: dict) -> dict:
    """Status chips — Occupied, Cool (°C), Humid (%) with Tapo keyword discovery."""
    if room.get("status_chips"):
        chips_card = build_room_status_chips(room)
        if chips_card:
            return _full_width(chips_card)

    triggers: list[str] = ["sensor", "binary_sensor"]
    for key in ("occupancy_entity", "temperature_entity", "humidity_entity"):
        entity = room.get(key)
        if entity:
            triggers.append(entity)

    return _full_width(
        wrap_glass(
            {
                "type": "custom:button-card",
                "template": "flux_room_status",
                "variables": {
                    "keywords": room.get("keywords") or [],
                    "occupancy_entity": room.get("occupancy_entity"),
                    "temperature_entity": room.get("temperature_entity"),
                    "humidity_entity": room.get("humidity_entity"),
                },
                "custom_fields": {"row": ROOM_STATUS_ROW_HTML},
                "styles": {
                    "grid": [{"grid-template-areas": "'row'"}, {"grid-template-columns": "1fr"}],
                    "custom_fields": {
                        "row": [{"grid-area": "row"}, {"width": "100%"}, {"justify-self": "stretch"}],
                    },
                },
                "triggers_update": "all",
            }
        )
    )


def _feature_tile(feature: dict) -> dict:
    if feature.get("stub") or not feature.get("entity"):
        return {
            "type": "custom:button-card",
            "template": "flux_feature",
            "name": feature["name"],
            "icon": feature.get("icon", "mdi:gesture-tap"),
            "styles": {
                "card": [{"opacity": "0.55"}],
                "icon": [{"color": "var(--md-sys-color-on-surface-variant)"}],
            },
        }
    entity = feature["entity"]
    return {
        "type": "custom:button-card",
        "template": "flux_feature",
        "entity": entity,
        "name": feature["name"],
        "icon": feature.get("icon", "mdi:gesture-tap"),
        "tap_action": {"action": "toggle"},
        "hold_action": {"action": "more-info"},
    }


def build_room_features_row(room: dict) -> dict:
    """Quick action icons — Presence, Movie Mode, Adaptive Lighting (reference row)."""
    features = room.get("features") or DEFAULT_FEATURES
    return _full_width(
        wrap_glass(
            {
                "type": "grid",
                "columns": 3,
                "square": False,
                "cards": [_feature_tile(f) for f in features[:3]],
            }
        )
    )


def build_room_subnav(room: dict, *, active: str = "room") -> dict:
    """Room / Grid / Camera segmented sub-navigation."""
    path = room["path"]

    def chip(content: str, icon: str, nav_path: str, tab: str) -> dict:
        is_active = active == tab
        return {
            "type": "template",
            "icon": icon,
            "content": content,
            "icon_color": "pink" if is_active else "disabled",
            "tap_action": {"action": "navigate", "navigation_path": nav_path},
        }

    chips = [
        chip("Room", "mdi:home", room_navigation_path(path), "room"),
        chip("Grid", "mdi:view-grid", room_grid_navigation_path(path), "grid"),
        chip("Camera", "mdi:cctv", room_camera_navigation_path(path), "camera"),
    ]
    nav_card: dict = {
        "type": "custom:mushroom-chips-card",
        "alignment": "justify",
        "chips": chips,
    }
    return _full_width(merge_card_mod(wrap_glass(nav_card), SUBNAV_MOD["style"]))


def _lights_on_count_jinja(entities: list[str]) -> tuple[str, str]:
    if not entities:
        return "0", "disabled"
    parts = " + ".join(f"(1 if is_state('{e}', 'on') else 0)" for e in entities)
    content = f"{{% set n = {parts} %}}{{{{ n }}}}"
    icon_color = f"{{% set n = {parts} %}}{{% if n > 0 %}}amber{{% else %}}disabled{{% endif %}}"
    return content, icon_color


def build_room_light_groups_fab(room: dict) -> dict | None:
    """Floating vertical shortcut stack — reference FAB menu (Main Lights, Media, …)."""
    groups = room.get("light_groups") or []
    if not groups:
        return None
    cards: list[dict] = []
    for group in groups:
        cards.append(
            {
                "type": "custom:button-card",
                "template": "flux_fab_group",
                "entity": group["entity"],
                "name": group["name"],
                "icon": group.get("icon", "mdi:lightbulb-group"),
                "tap_action": {"action": "toggle"},
                "hold_action": {"action": "more-info"},
            }
        )
    return _full_width(
        {
            "type": "grid",
            "columns": 1,
            "square": False,
            "cards": cards,
            "card_mod": FAB_STACK_MOD,
        }
    )


def build_room_lights_section(room: dict) -> dict:
    """Lights block with live on-count badge + 2-col toggle grid."""
    lights = room.get("lights", [])
    entities = [light["entity"] for light in lights]
    count_content, count_color = _lights_on_count_jinja(entities)
    return {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "horizontal-stack",
                "cards": [
                    wrap_title(
                        {
                            "type": "custom:mushroom-title-card",
                            "title": "Lights",
                        }
                    ),
                    {
                        "type": "custom:mushroom-chips-card",
                        "alignment": "end",
                        "chips": [
                            {
                                "type": "template",
                                "icon": "mdi:lightbulb-on",
                                "icon_color": count_color,
                                "content": count_content,
                            }
                        ],
                    },
                ],
            },
            wrap_glass(_lights_tile_grid(lights)),
        ],
        "grid_options": {"columns": 12},
    }


def build_room_detail_page(room: dict, *, garage_doors: list[dict] | None = None) -> dict:
    """Full room detail matching ElementZoom reference (Living screenshot)."""
    cards: list[dict] = [
        _full_width(_title(room.get("card_name") or room["name"], room.get("subtitle", ""))),
        _full_width(
            {
                "type": "custom:button-card",
                "template": "flux_action",
                "name": "Back to Rooms",
                "icon": "mdi:arrow-left",
                "label": "All areas",
                "tap_action": {"action": "navigate", "navigation_path": f"{URL_PREFIX}/rooms"},
            }
        ),
        build_room_status_chips_auto(room),
        build_room_features_row(room),
        build_room_subnav(room, active="room"),
    ]
    if room.get("path") == "garage" and garage_doors:
        cards.append(build_doors_status_section(garage_doors, title="Garage & sheds", subtitle="Live Tapo contacts"))
    if room.get("lights"):
        cards.append(build_room_lights_section(room))
    fab = build_room_light_groups_fab(room)
    if fab:
        cards.append(fab)
    return {"type": "grid", "cards": cards}

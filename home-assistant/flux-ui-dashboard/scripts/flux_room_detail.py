"""Flux UI room detail page — ElementZoom Living reference layout."""

from __future__ import annotations

from flux_layouts import _lights_tile_grid, _title, build_room_status_chips
from flux_navbar import (
    room_camera_navigation_path,
    room_grid_navigation_path,
    room_navigation_path,
)
from md3_templates import wrap_glass, wrap_title

DEFAULT_FEATURES: list[dict] = [
    {"name": "Presence Sensor", "icon": "mdi:motion-sensor", "stub": True},
    {"name": "Movie Mode", "icon": "mdi:movie-off-outline", "stub": True},
    {"name": "Adaptive Lighting", "icon": "mdi:lightbulb-auto-outline", "stub": True},
]


def _chip(content: str, *, icon: str, icon_color: str = "primary", entity: str | None = None) -> dict:
    entry: dict = {
        "type": "template",
        "icon": icon,
        "icon_color": icon_color,
        "content": content,
    }
    if entity:
        entry["entity"] = entity
    return entry


def build_room_status_chips_auto(room: dict) -> dict:
    """Status chips row — Occupied, temperature, humidity (live or placeholder)."""
    if room.get("status_chips"):
        chips_card = build_room_status_chips(room)
        if chips_card:
            return chips_card

    chips: list[dict] = []
    occ = room.get("occupancy_entity")
    if occ:
        chips.append(
            _chip(
                f"{{% if is_state('{occ}', 'on') %}}Occupied{{% else %}}Empty{{% endif %}}",
                icon="mdi:account",
                icon_color=f"{{% if is_state('{occ}', 'on') %}}purple{{% else %}}disabled{{% endif %}}",
                entity=occ,
            )
        )
    else:
        chips.append(_chip("—", icon="mdi:account", icon_color="disabled"))

    temp = room.get("temperature_entity")
    if temp:
        chips.append(
            _chip(
                f"{{{{ states('{temp}') }}}}°C",
                icon="mdi:thermometer",
                icon_color="cyan",
                entity=temp,
            )
        )
    else:
        chips.append(_chip("—°C", icon="mdi:thermometer", icon_color="disabled"))

    humid = room.get("humidity_entity")
    if humid:
        chips.append(
            _chip(
                f"{{{{ states('{humid}') }}}}%",
                icon="mdi:water-percent",
                icon_color="teal",
                entity=humid,
            )
        )
    else:
        chips.append(_chip("—%", icon="mdi:water-percent", icon_color="disabled"))

    return wrap_glass(
        {
            "type": "custom:mushroom-chips-card",
            "alignment": "start",
            "chips": chips,
            "grid_options": {"columns": 12},
        }
    )


def _feature_tile(feature: dict, *, columns: int = 4) -> dict:
    if feature.get("stub") or not feature.get("entity"):
        return {
            "type": "custom:button-card",
            "template": "flux_feature",
            "name": feature["name"],
            "icon": feature.get("icon", "mdi:gesture-tap"),
            "label": "—",
            "styles": {
                "card": [{"opacity": "0.55"}],
                "icon": [{"color": "var(--md-sys-color-on-surface-variant)"}],
            },
            "grid_options": {"columns": columns},
        }
    entity = feature["entity"]
    return {
        "type": "custom:button-card",
        "template": "flux_feature",
        "entity": entity,
        "name": feature["name"],
        "icon": feature.get("icon", "mdi:gesture-tap"),
        "label": "[[[ return entity.state === 'on' ? 'On' : 'Off'; ]]]",
        "tap_action": {"action": "toggle"},
        "hold_action": {"action": "more-info"},
        "grid_options": {"columns": columns},
    }


def build_room_features_row(room: dict) -> dict:
    """Quick action icons — Presence, Movie Mode, Adaptive Lighting."""
    features = room.get("features") or DEFAULT_FEATURES
    return {
        "type": "grid",
        "columns": 12,
        "square": False,
        "cards": [_feature_tile(f, columns=4) for f in features[:3]],
        "grid_options": {"columns": 12},
    }


def build_room_subnav(room: dict, *, active: str = "room") -> dict:
    """Room / Grid / Camera sub-navigation chips."""
    path = room["path"]
    active_mod = {
        "style": (
            "ha-card {\n"
            "  background: rgba(208, 188, 255, 0.32) !important;\n"
            "  border: 1px solid rgba(208, 188, 255, 0.55) !important;\n"
            "}\n"
        )
    }

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
        "alignment": "start",
        "chips": chips,
        "grid_options": {"columns": 12},
    }
    if active == "room":
        nav_card["card_mod"] = active_mod
    return wrap_glass(nav_card)


def _lights_on_count_jinja(entities: list[str]) -> tuple[str, str]:
    if not entities:
        return "0", "disabled"
    parts = " + ".join(f"(1 if is_state('{e}', 'on') else 0)" for e in entities)
    content = f"{{% set n = {parts} %}}{{{{ n }}}}"
    icon_color = f"{{% set n = {parts} %}}{{% if n > 0 %}}amber{{% else %}}disabled{{% endif %}}"
    return content, icon_color


def build_room_light_groups(room: dict) -> dict | None:
    """Optional quick light-group shortcuts (reference FAB menu)."""
    groups = room.get("light_groups") or []
    if not groups:
        return None
    cards: list[dict] = []
    for group in groups:
        cards.append(
            {
                "type": "custom:button-card",
                "template": "flux_action",
                "entity": group["entity"],
                "name": group["name"],
                "icon": group.get("icon", "mdi:lightbulb-group"),
                "label": "[[[ return entity.state === 'on' ? 'On' : 'Off'; ]]]",
                "tap_action": {"action": "toggle"},
                "grid_options": {"columns": 6},
            }
        )
    return {"type": "grid", "cards": cards}


def build_room_lights_section(room: dict) -> dict:
    """Lights block with live on-count badge + 2-col toggle grid."""
    lights = room.get("lights", [])
    entities = [light["entity"] for light in lights]
    count_content, count_color = _lights_on_count_jinja(entities)
    return {
        "type": "grid",
        "cards": [
            {
                "type": "grid",
                "columns": 12,
                "square": False,
                "cards": [
                    wrap_title(
                        {
                            "type": "custom:mushroom-title-card",
                            "title": "Lights",
                            "grid_options": {"columns": 8},
                        }
                    ),
                    wrap_glass(
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
                            "grid_options": {"columns": 4},
                        }
                    ),
                ],
            },
            wrap_glass(_lights_tile_grid(lights)),
        ],
    }


def build_room_detail_page(room: dict) -> dict:
    """Full room detail matching ElementZoom reference (Living screenshot)."""
    cards: list[dict] = [
        _title(room.get("card_name") or room["name"], room.get("subtitle", "")),
        {
            "type": "custom:button-card",
            "template": "flux_action",
            "name": "Back to Rooms",
            "icon": "mdi:arrow-left",
            "label": "All areas",
            "tap_action": {"action": "navigate", "navigation_path": "/flux-ui/rooms"},
            "grid_options": {"columns": 12},
        },
        build_room_status_chips_auto(room),
        build_room_features_row(room),
        build_room_subnav(room, active="room"),
    ]
    groups = build_room_light_groups(room)
    if groups:
        cards.append(groups)
    if room.get("lights"):
        cards.append(build_room_lights_section(room))
    return {"type": "grid", "cards": cards}

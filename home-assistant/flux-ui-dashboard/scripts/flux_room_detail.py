"""Flux UI room detail page — ElementZoom Living reference layout."""

from __future__ import annotations

from flux_door_builders import build_doors_status_section
from flux_layouts import _lights_tile_grid, _title, build_room_status_chips
from flux_navbar import (
    overview_navigation_path,
    room_climate_navigation_path,
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

# Sticky (not fixed) — iOS Safari clips/breaks pages with position:fixed FABs
# inside sections views.
FAB_STACK_MOD = {
    "style": (
        "ha-card {\n"
        "  position: sticky !important;\n"
        "  bottom: 108px !important;\n"
        "  margin-left: auto !important;\n"
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
    """Span the full sections-view row (required for stacks / composite cards)."""
    card = dict(card)
    card["grid_options"] = {"columns": 12}
    return card


def build_room_top_bar(room: dict) -> dict:
    """Top bar — labeled Overview back control, centered room title, balance spacer."""
    title = room.get("card_name") or room["name"]
    overview_path = overview_navigation_path()
    return _full_width(
        {
            "type": "horizontal-stack",
            "cards": [
                wrap_glass(
                    {
                        "type": "custom:button-card",
                        "icon": "mdi:arrow-left-circle",
                        "name": "Overview",
                        "show_icon": True,
                        "show_name": True,
                        "show_state": False,
                        "tap_action": {
                            "action": "navigate",
                            "navigation_path": overview_path,
                        },
                        "styles": {
                            "grid": [
                                {"grid-template-areas": "'i n'"},
                                {"grid-template-columns": "min-content 1fr"},
                                {"grid-template-rows": "1fr"},
                                {"align-items": "center"},
                                {"column-gap": "6px"},
                            ],
                            "card": [
                                {"padding": "8px 14px 8px 10px"},
                                {"min-height": "48px"},
                                {"max-height": "48px"},
                                {"min-width": "132px"},
                                {"border-radius": "999px"},
                                {"display": "flex"},
                                {"align-items": "center"},
                                {"justify-content": "flex-start"},
                            ],
                            "icon": [
                                {"width": "26px"},
                                {"color": "var(--md-sys-color-primary)"},
                            ],
                            "name": [
                                {"font-size": "15px"},
                                {"font-weight": "700"},
                                {"justify-self": "start"},
                                {"color": "var(--md-sys-color-on-surface)"},
                            ],
                        },
                    }
                ),
                wrap_title(
                    {
                        "type": "custom:mushroom-title-card",
                        "title": title,
                        "alignment": "center",
                        "card_mod": {
                            "style": (
                                "ha-card { padding-top: 4px !important; }\n"
                                ".header { justify-content: center !important; "
                                "text-align: center; }\n"
                            )
                        },
                    }
                ),
                # Invisible spacer so the room title stays optically centered.
                {
                    "type": "custom:button-card",
                    "show_icon": False,
                    "show_name": False,
                    "tap_action": {"action": "none"},
                    "styles": {
                        "card": [
                            {"padding": "0"},
                            {"min-height": "48px"},
                            {"max-height": "48px"},
                            {"min-width": "132px"},
                            {"background": "transparent"},
                            {"box-shadow": "none"},
                            {"border": "none"},
                            {"pointer-events": "none"},
                        ],
                    },
                },
            ],
        }
    )


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
                        "row": [
                            {"grid-area": "row"},
                            {"width": "100%"},
                            {"justify-self": "stretch"},
                        ],
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
    """Room / Climate / Lights segmented pills — active pill shows its label."""
    path = room["path"]

    def chip(content: str, icon: str, nav_path: str, tab: str) -> dict:
        is_active = active == tab
        c: dict = {
            "type": "template",
            "icon": icon,
            "icon_color": "pink" if is_active else "disabled",
            "tap_action": {"action": "navigate", "navigation_path": nav_path},
        }
        if is_active:
            # Reference: selected pill expands with a label, others icon-only.
            c["content"] = content
        return c

    chips = [
        chip("Room", "mdi:home", room_navigation_path(path), "room"),
        chip("Climate", "mdi:thermostat", room_climate_navigation_path(path), "climate"),
        chip("Lights", "mdi:lightbulb-group", room_grid_navigation_path(path), "lights"),
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
    icon_color = (
        f"{{% set n = {parts} %}}"
        f"{{% if n > 0 %}}amber{{% else %}}disabled{{% endif %}}"
    )
    return content, icon_color


def build_room_light_groups_fab(room: dict) -> dict | None:
    """Shortcut stack for light groups — sticky on iOS (not position:fixed)."""
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
    return _full_width(
        {
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
        }
    )


def build_room_detail_page(room: dict, *, garage_doors: list[dict] | None = None) -> dict:
    """Full room detail matching ElementZoom reference (Living screenshot)."""
    cards: list[dict] = [
        build_room_top_bar(room),
        build_room_status_chips_auto(room),
        build_room_features_row(room),
        build_room_subnav(room, active="room"),
    ]
    if room.get("path") == "garage" and garage_doors:
        cards.append(
            build_doors_status_section(
                garage_doors, title="Garage & sheds", subtitle="Live Tapo contacts"
            )
        )
    if room.get("lights"):
        cards.append(build_room_lights_section(room))
    fab = build_room_light_groups_fab(room)
    if fab:
        cards.append(fab)
    return {"type": "grid", "cards": cards}


def build_room_climate_page(room: dict, *, active_tab: str = "climate") -> dict:
    """Climate subview — Control card + Climate History."""
    climate_entity = room.get("climate_entity")
    temp = room.get("temperature_entity")
    humidity = room.get("humidity_entity")

    cards: list[dict] = [
        build_room_top_bar(room),
        build_room_status_chips_auto(room),
        build_room_features_row(room),
        build_room_subnav(room, active=active_tab),
        _full_width(
            {
                "type": "horizontal-stack",
                "cards": [
                    wrap_title(
                        {
                            "type": "custom:mushroom-title-card",
                            "title": "Control",
                        }
                    ),
                    wrap_glass(
                        {
                            "type": "custom:mushroom-chips-card",
                            "alignment": "end",
                            "chips": [
                                {
                                    "type": "template",
                                    "icon": "mdi:water-percent",
                                    "icon_color": "red",
                                    "content": (
                                        "{{ states('" + humidity + "') | round(1) }}% - Humid"
                                        if humidity
                                        else "— % Humid"
                                    ),
                                }
                            ],
                        }
                    ),
                ],
            }
        ),
    ]

    if climate_entity:
        cards.append(
            _full_width(
                wrap_glass(
                    {
                        "type": "thermostat",
                        "entity": climate_entity,
                        "features": [{"type": "climate-hvac-modes"}],
                    }
                )
            )
        )
    else:
        # Stub — replaced once climate_entity is set in rooms.yaml.
        cards.append(
            _full_width(
                wrap_glass(
                    {
                        "type": "custom:button-card",
                        "template": "flux_glass",
                        "show_icon": True,
                        "show_name": True,
                        "show_label": True,
                        "icon": "mdi:thermostat",
                        "name": room.get("card_name") or room["name"],
                        "label": (
                            "[[[ return states["
                            + repr(temp)
                            + "] ? `Heat/Cool · ${states["
                            + repr(temp)
                            + "].state} °C` : 'Heat/Cool · no sensor'; ]]]"
                            if temp
                            else "Heat/Cool — set climate_entity in rooms.yaml"
                        ),
                        "styles": {
                            "card": [{"min-height": "140px"}, {"opacity": "0.75"}],
                            "name": [{"font-size": "28px"}, {"font-weight": "700"}],
                            "label": [{"font-size": "13px"}],
                        },
                    }
                )
            )
        )

    cards.append(_full_width(_title("Climate History", "")))
    cards.append(
        _full_width(
            wrap_glass(
                {
                    "type": "markdown",
                    "content": (
                        "Climate history will appear here once a `climate_entity` "
                        "is configured for this room in `rooms.yaml`."
                    ),
                }
            )
        )
    )
    return {"type": "grid", "cards": cards}

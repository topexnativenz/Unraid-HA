"""ElementZoom tablet room detail — landscape 3-column Living Area layout.

Reference screenshot: lights grid | climate control + history | room photo
"""

from __future__ import annotations

from flux_door_builders import build_doors_status_section
from flux_layouts import _lights_tile_grid
from flux_navbar import URL_PREFIX, build_navbar_card
from flux_room_detail import (
    build_room_features_row,
    build_room_status_chips_auto,
    build_room_subnav,
    build_room_top_bar,
)
from md3_templates import TABLET_VIEW_CARD_MOD, wrap_glass, wrap_title


def _area(name: str) -> dict:
    return {"grid-area": name}


def _climate_column(room: dict) -> dict:
    climate_entity = room.get("climate_entity")
    temp = room.get("temperature_entity")
    humidity = room.get("humidity_entity")
    cards: list[dict] = [
        wrap_title({"type": "custom:mushroom-title-card", "title": "Control"}),
    ]
    if climate_entity:
        cards.append(
            wrap_glass(
                {
                    "type": "thermostat",
                    "entity": climate_entity,
                    "features": [
                        {"type": "climate-hvac-modes"},
                        {"type": "target-temperature"},
                    ],
                }
            )
        )
    else:
        cards.append(
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
                        (
                            "[[[ const s = states["
                            + repr(temp)
                            + "]; return s ? `Indoor · ${s.state} °C` : 'Indoor · —'; ]]]"
                        )
                        if temp
                        else "Set climate_entity in rooms.yaml"
                    ),
                    "styles": {
                        "card": [{"min-height": "160px"}],
                        "name": [{"font-size": "28px"}, {"font-weight": "700"}],
                    },
                }
            )
        )
    if humidity:
        cards.append(
            wrap_glass(
                {
                    "type": "custom:mushroom-entity-card",
                    "entity": humidity,
                    "name": "Humidity",
                    "icon": "mdi:water-percent",
                    "layout": "horizontal",
                }
            )
        )
    hist_entities = [e for e in (temp, climate_entity) if e]
    if hist_entities:
        cards.append(wrap_title({"type": "custom:mushroom-title-card", "title": "Climate History"}))
        cards.append(
            wrap_glass(
                {
                    "type": "history-graph",
                    "hours_to_show": 24,
                    "entities": [{"entity": e} for e in hist_entities],
                }
            )
        )
    return {"type": "vertical-stack", "view_layout": _area("climate"), "cards": cards}


def _photo_column(room: dict) -> dict:
    photo = room.get("photo") or room.get("image")
    if photo:
        card = wrap_glass(
            {
                "type": "picture",
                "image": photo,
                "tap_action": {"action": "none"},
            }
        )
    else:
        card = wrap_glass(
            {
                "type": "custom:button-card",
                "template": "flux_glass",
                "show_icon": True,
                "show_name": True,
                "show_label": True,
                "icon": room.get("icon", "mdi:sofa"),
                "name": room.get("card_name") or room["name"],
                "label": "Add photo: in rooms.yaml",
                "styles": {
                    "card": [{"min-height": "280px"}],
                    "icon": [{"width": "72px"}],
                    "name": [{"font-size": "20px"}, {"font-weight": "700"}],
                },
            }
        )
    return {"type": "vertical-stack", "view_layout": _area("photo"), "cards": [card]}


def _lights_column(room: dict) -> dict:
    lights = room.get("lights") or []
    cards: list[dict] = [
        wrap_title({"type": "custom:mushroom-title-card", "title": "Lights"}),
    ]
    if lights:
        grid = _lights_tile_grid(lights)
        grid.pop("grid_options", None)
        cards.append(wrap_glass(grid))
    else:
        cards.append(wrap_glass({"type": "markdown", "content": "No lights configured."}))
    return {"type": "vertical-stack", "view_layout": _area("lights"), "cards": cards}


def build_tablet_room_detail_view(
    room: dict,
    *,
    garage_doors: list[dict] | None = None,
    use_navbar_card: bool = True,
) -> dict:
    """Landscape room detail view (custom:grid-layout)."""
    header_cards: list[dict] = [
        build_room_top_bar(room),
        build_room_status_chips_auto(room),
        build_room_features_row(room),
        build_room_subnav(room, active="room"),
    ]
    if room.get("path") == "garage" and garage_doors:
        header_cards.append(
            build_doors_status_section(garage_doors, title="Garage & sheds", subtitle="Live contacts")
        )

    # Strip section grid_options — not used in grid-layout view cards.
    for card in header_cards:
        if isinstance(card, dict):
            card.pop("grid_options", None)

    nav = build_navbar_card(use_navbar_card=use_navbar_card)
    nav["view_layout"] = _area("navbar")

    return {
        "title": room["name"],
        "icon": room.get("icon", "mdi:home-outline"),
        "path": f"room-{room['path']}",
        "type": "custom:grid-layout",
        "theme": "flux-ui-md3",
        "subview": True,
        "back_path": f"{URL_PREFIX}/rooms",
        "card_mod": TABLET_VIEW_CARD_MOD,
        "layout": {
            "margin": "4px 10px 0 10px",
            "grid-gap": "10px",
            "grid-template-columns": "34% 33% 33%",
            "grid-template-areas": (
                '"header header header"\n'
                '"lights climate photo"\n'
                '"navbar navbar navbar"'
            ),
        },
        "cards": [
            {"type": "vertical-stack", "view_layout": _area("header"), "cards": header_cards},
            _lights_column(room),
            _climate_column(room),
            _photo_column(room),
            nav,
        ],
    }

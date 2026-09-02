"""Rooms index — ElementZoom 02-rooms.yaml pattern (category tabs + 2-col room cards).

Reference: https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard
  dashboard/mobile/views/02-rooms.yaml
"""

from __future__ import annotations

from flux_layouts import flux_room_tile

ROOMS_TAB_ENTITY = "input_select.flux_ui_rooms_tab"

ROOM_CATEGORIES: list[dict[str, str]] = [
    {"option": "Default", "icon": "mdi:star", "slug": "default"},
    {"option": "Others", "icon": "mdi:home", "slug": "others"},
    {"option": "Outdoor", "icon": "mdi:tree", "slug": "outdoor"},
]


def _rooms_for_category(rooms: list[dict], slug: str) -> list[dict]:
    return [r for r in rooms if (r.get("category") or "default") == slug]


def _tab_active_if(option: str) -> str:
    """Jinja condition for {% if %} — no outer braces."""
    if option == "Default":
        return (
            "{% set tab = states('" + ROOMS_TAB_ENTITY + "') %}"
            "tab == 'Default' or tab in ['unknown', 'unavailable', none]"
        )
    return "is_state('" + ROOMS_TAB_ENTITY + "', '" + option + "')"


def _tab_active_template(option: str) -> str:
    """Full HA template for conditional card visibility."""
    if option == "Default":
        return (
            "{% set tab = states('" + ROOMS_TAB_ENTITY + "') %}"
            "{{ tab == 'Default' or tab in ['unknown', 'unavailable', none] }}"
        )
    return "{{ is_state('" + ROOMS_TAB_ENTITY + "', '" + option + "') }}"


def _chip_active_style(option: str) -> str:
    """card_mod style — active pill uses primary fill (ElementZoom room_toggles_chip_card)."""
    cond = _tab_active_if(option)
    return (
        "ha-card {\n"
        f"  --chip-background: {{% if {cond} %}}"
        "var(--md-sys-color-primary)"
        "{% else %}"
        "color-mix(in srgb, var(--md-sys-color-surface-container) 55%, transparent)"
        "{% endif %} !important;\n"
        f"  --color: {{% if {cond} %}}"
        "var(--md-sys-color-on-primary)"
        "{% else %}"
        "var(--md-sys-color-on-surface-variant)"
        "{% endif %} !important;\n"
        "  border-radius: 28px !important;\n"
        "  border: 1px solid color-mix(in srgb, var(--md-sys-color-outline-variant) 35%, transparent) !important;\n"
        "  min-height: 44px !important;\n"
        "  flex: 1 1 0 !important;\n"
        "  justify-content: center !important;\n"
        "}\n"
    )


def _chip_icon_color(option: str) -> str:
    cond = _tab_active_if(option)
    return (
        f"{{% if {cond} %}}"
        "var(--md-sys-color-on-primary)"
        "{% else %}"
        "var(--md-sys-color-on-surface-variant)"
        "{% endif %}"
    )


def _rooms_page_title() -> dict:
    return {
        "type": "custom:mushroom-title-card",
        "title": "Rooms",
        "grid_options": {"columns": 12},
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  padding: 0 4px 8px 4px !important;\n"
                "}\n"
                ".header {\n"
                "  font-weight: 700 !important;\n"
                "  font-size: 24px !important;\n"
                "  text-align: center !important;\n"
                "  width: 100% !important;\n"
                "  color: var(--md-sys-color-on-surface) !important;\n"
                "}\n"
            )
        },
    }


def _category_tab_chips() -> dict:
    """Default / Others / Outdoor — ElementZoom room_toggles_chip_card pattern."""
    chips: list[dict] = []
    for cat in ROOM_CATEGORIES:
        option = cat["option"]
        chips.append(
            {
                "type": "template",
                "icon": cat["icon"],
                "content": option,
                "icon_color": _chip_icon_color(option),
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "input_select.select_option",
                    "target": {"entity_id": ROOMS_TAB_ENTITY},
                    "data": {"option": option},
                },
                "card_mod": {"style": _chip_active_style(option)},
            }
        )

    return {
        "type": "custom:mushroom-chips-card",
        "alignment": "justify",
        "chips": chips,
        "grid_options": {"columns": 12},
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  margin: 0 !important;\n"
                "  padding: 0 !important;\n"
                "}\n"
                ".chip-container {\n"
                "  display: flex !important;\n"
                "  width: 100% !important;\n"
                "  gap: 8px !important;\n"
                "}\n"
                "mushroom-chip {\n"
                "  flex: 1 1 0 !important;\n"
                "  min-width: 0 !important;\n"
                "}\n"
            )
        },
    }


def _room_grid_for_category(rooms: list[dict]) -> dict:
    """Two-column grid of flux_room tiles — ElementZoom horizontal-stack pairs."""
    if not rooms:
        return {
            "type": "custom:mushroom-title-card",
            "title": "No rooms in this category",
            "subtitle": "Set category: default | others | outdoor in rooms.yaml",
            "grid_options": {"columns": 12},
        }
    return {
        "type": "grid",
        "columns": 2,
        "square": False,
        "cards": [flux_room_tile(room, columns=6) for room in rooms],
        "grid_options": {"columns": 12},
    }


def _category_panel(rooms: list[dict], *, option: str, slug: str) -> dict:
    category_rooms = _rooms_for_category(rooms, slug)
    return {
        "type": "conditional",
        "conditions": [
            {
                "condition": "template",
                "value_template": _tab_active_template(option),
            }
        ],
        "card": _room_grid_for_category(category_rooms),
    }


def build_rooms_index_section(rooms: list[dict]) -> dict:
    """ElementZoom Rooms view — centered title, category tabs, filtered 2-col cards."""
    return {
        "type": "grid",
        "cards": [
            _rooms_page_title(),
            _category_tab_chips(),
            *[_category_panel(rooms, option=c["option"], slug=c["slug"]) for c in ROOM_CATEGORIES],
        ],
    }

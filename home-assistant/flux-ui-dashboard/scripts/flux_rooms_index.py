"""Rooms index — ElementZoom simple-tabs (phone) + tablet category chips.

Phone uses custom:simple-tabs (no input_select / template conditionals) so HA
does not show Configuration error cards.

Tablet overview keeps mushroom chips + input_select.flux_ui_rooms_tab with
native state conditions (see flux_tablet_overview._rooms_band).
"""

from __future__ import annotations

from flux_layouts import flux_room_tile
from flux_tab_layout import simple_tabs_shell, strip_grid_options, tab_two_column_grid

ROOMS_TAB_ENTITY = "input_select.flux_ui_rooms_tab"

# title/option must match packages/flux_ui_rooms.yaml input_select options.
ROOM_CATEGORIES: list[dict[str, str]] = [
    {"title": "Default", "option": "Default", "icon": "mdi:star", "slug": "default"},
    {"title": "Others", "option": "Others", "icon": "mdi:home", "slug": "others"},
    {"title": "Outdoor", "option": "Outdoor", "icon": "mdi:tree", "slug": "outdoor"},
]


def _rooms_for_category(rooms: list[dict], slug: str) -> list[dict]:
    return [r for r in rooms if (r.get("category") or "default") == slug]


def _tab_active_if(option: str) -> str:
    """Jinja condition for chip card_mod {% if %} — no outer braces."""
    if option == "Default":
        return (
            "{% set tab = states('" + ROOMS_TAB_ENTITY + "') %}"
            "tab == 'Default' or tab in ['unknown', 'unavailable', none]"
        )
    return "is_state('" + ROOMS_TAB_ENTITY + "', '" + option + "')"


def _chip_active_style(option: str) -> str:
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
        "  --chip-height: 56px !important;\n"
        "  --chip-font-size: 15px !important;\n"
        "  --chip-icon-size: 22px !important;\n"
        "  --chip-padding: 0 14px !important;\n"
        "  border-radius: 28px !important;\n"
        "  border: 1px solid color-mix(in srgb, var(--md-sys-color-outline-variant) 35%, transparent) !important;\n"
        "  min-height: 56px !important;\n"
        "  height: 56px !important;\n"
        "  flex: 1 1 0 !important;\n"
        "  width: 100% !important;\n"
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
    """Tablet overview room selector — mushroom chips + input_select (state conditions)."""
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
                "  width: 100% !important;\n"
                "}\n"
                ".chip-container {\n"
                "  display: flex !important;\n"
                "  width: 100% !important;\n"
                "  gap: 8px !important;\n"
                "}\n"
                "mushroom-chip {\n"
                "  flex: 1 1 33.33% !important;\n"
                "  max-width: 33.33% !important;\n"
                "  min-width: 0 !important;\n"
                "}\n"
            )
        },
    }


def _room_tab_cards(rooms: list[dict], *, columns: int = 2) -> list[dict]:
    """Room tiles for a simple-tabs panel — no grid_options (invalid in tab panels)."""
    if not rooms:
        return [
            {
                "type": "custom:mushroom-title-card",
                "title": "No rooms in this category",
            }
        ]
    # Phone: 2-col (columns=6 each). Tablet rooms view: 3-col (columns=4 each).
    tile_cols = 12 // max(1, columns)
    return [strip_grid_options(flux_room_tile(room, columns=tile_cols)) for room in rooms]


def _room_tab_panel(rooms: list[dict], *, columns: int = 2) -> dict:
    cards = _room_tab_cards(rooms, columns=columns)
    if len(cards) == 1:
        return cards[0]
    if columns <= 2:
        return tab_two_column_grid(cards)
    return {
        "type": "grid",
        "columns": columns,
        "square": False,
        "cards": cards,
    }


def build_rooms_index_section(
    rooms: list[dict],
    *,
    use_simple_tabs: bool = True,
    columns: int = 2,
) -> dict:
    """Phone/tablet Rooms view — simple-tabs categories (no template conditionals)."""
    if use_simple_tabs:
        tabs = [
            {
                "title": cat["title"],
                "icon": cat["icon"],
                "cards": [
                    _room_tab_panel(
                        _rooms_for_category(rooms, cat["slug"]),
                        columns=columns,
                    )
                ],
            }
            for cat in ROOM_CATEGORIES
        ]
        return {
            "type": "grid",
            "cards": [
                _rooms_page_title(),
                {
                    **simple_tabs_shell(tabs, enable_swipe=True),
                    "grid_options": {"columns": 12},
                },
            ],
        }

    # Fallback when simple-tabs HACS is missing: default-category grid only.
    default_rooms = _rooms_for_category(rooms, "default")
    return {
        "type": "grid",
        "cards": [
            _rooms_page_title(),
            _room_tab_panel(default_rooms, columns=columns),
        ],
    }

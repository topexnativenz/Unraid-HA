"""Rooms index — ElementZoom 02-rooms.yaml pattern (simple-tabs + 2-col room cards).

Uses the same custom:simple-tabs bar as the Home overview tab (full-width pills).
No input_select helper required — avoids configuration errors from mushroom chip Jinja.
"""

from __future__ import annotations

from flux_layouts import flux_room_tile
from flux_tab_layout import simple_tabs_shell, strip_grid_options, tab_two_column_grid

ROOM_CATEGORIES: list[dict[str, str]] = [
    {"title": "Default", "icon": "mdi:star", "slug": "default"},
    {"title": "Others", "icon": "mdi:home", "slug": "others"},
    {"title": "Outdoor", "icon": "mdi:tree", "slug": "outdoor"},
]


def _rooms_for_category(rooms: list[dict], slug: str) -> list[dict]:
    return [r for r in rooms if (r.get("category") or "default") == slug]


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


def _room_tab_cards(rooms: list[dict]) -> list[dict]:
    """Two-column room grid for a simple-tabs panel — no grid_options (invalid in tab panels)."""
    if not rooms:
        return [
            {
                "type": "custom:mushroom-title-card",
                "title": "No rooms in this category",
            }
        ]
    return [strip_grid_options(flux_room_tile(room, columns=6)) for room in rooms]


def _room_tab_panel(rooms: list[dict]) -> dict:
    cards = _room_tab_cards(rooms)
    if len(cards) == 1:
        return cards[0]
    return tab_two_column_grid(cards)


def build_rooms_index_section(rooms: list[dict], *, use_simple_tabs: bool = True) -> dict:
    """ElementZoom Rooms view — centered title, simple-tabs categories, 2-col cards."""
    if use_simple_tabs:
        tabs = [
            {
                "title": cat["title"],
                "icon": cat["icon"],
                "cards": [_room_tab_panel(_rooms_for_category(rooms, cat["slug"]))],
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

    # Fallback: single grid of all default-category rooms (no tabs HACS).
    default_rooms = _rooms_for_category(rooms, "default")
    return {
        "type": "grid",
        "cards": [
            _rooms_page_title(),
            _room_tab_panel(default_rooms),
        ],
    }

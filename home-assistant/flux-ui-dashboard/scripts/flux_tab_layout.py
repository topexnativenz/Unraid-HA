"""Tab-panel layout helpers — full-width grids inside overview tabs.

ElementZoom reference: https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard
"""

from __future__ import annotations

import copy
from typing import Any


def strip_grid_options(card: dict) -> dict:
    """Remove sections-view grid_options so nested tab grids lay out correctly."""
    out = copy.deepcopy(card)
    out.pop("grid_options", None)
    return out


def grid_to_vertical_stack(section: dict) -> dict:
    """Convert a sections-style grid section into a vertical-stack for tab panels."""
    if section.get("type") != "grid":
        return section
    cards = section.get("cards") or []
    if not cards:
        return section
    return {"type": "vertical-stack", "cards": cards}


def tab_two_column_grid(cards: list[dict]) -> dict:
    """Full-width 2-column grid for action/light tiles inside a tab."""
    return {
        "type": "grid",
        "columns": 2,
        "square": False,
        "cards": [strip_grid_options(c) for c in cards],
    }


def tab_panel_stack(*sections: dict) -> dict:
    """Stack multiple section blocks vertically inside one tab."""
    cards: list[Any] = []
    for section in sections:
        adapted = grid_to_vertical_stack(section)
        if adapted.get("type") == "vertical-stack":
            cards.extend(adapted.get("cards") or [])
        else:
            cards.append(adapted)
    return {"type": "vertical-stack", "cards": cards}


def strip_grid_options_deep(obj: object) -> object:
    """Remove grid_options everywhere — invalid inside simple-tabs tab panels."""
    if isinstance(obj, dict):
        return {k: strip_grid_options_deep(v) for k, v in obj.items() if k != "grid_options"}
    if isinstance(obj, list):
        return [strip_grid_options_deep(x) for x in obj]
    return obj


def adapt_card_for_tab_panel(card: dict) -> dict:
    """Prepare a sections-view card tree for simple-tabs tab content."""
    cleaned = strip_grid_options_deep(card)
    if not isinstance(cleaned, dict):
        return cleaned  # type: ignore[return-value]

    card_type = cleaned.get("type")
    if card_type == "conditional":
        inner = cleaned.get("card")
        if isinstance(inner, dict):
            return {**cleaned, "card": adapt_card_for_tab_panel(inner)}
        return cleaned
    if card_type == "vertical-stack":
        return {
            "type": "vertical-stack",
            "cards": [
                adapt_card_for_tab_panel(c) if isinstance(c, dict) else c
                for c in cleaned.get("cards") or []
            ],
        }
    if card_type == "grid":
        return tab_section_from_grid(cleaned)
    return cleaned


def tab_section_from_grid(section: dict) -> dict:
    """Convert a sections-view grid (title + tiles) into a tab-friendly vertical stack."""
    if section.get("type") != "grid":
        return strip_grid_options(section)

    cards = section.get("cards") or []
    if not cards:
        return {"type": "vertical-stack", "cards": []}

    title = strip_grid_options(cards[0])
    body = cards[1:]
    tile_cards: list[dict] = []

    for card in body:
        stripped = strip_grid_options(card)
        if stripped.get("type") == "grid":
            tile_cards.extend(strip_grid_options(c) for c in stripped.get("cards") or [])
        else:
            tile_cards.append(stripped)

    if not tile_cards:
        return {"type": "vertical-stack", "cards": [title]}

    if len(tile_cards) == 1:
        return {"type": "vertical-stack", "cards": [title, tile_cards[0]]}

    return {"type": "vertical-stack", "cards": [title, tab_two_column_grid(tile_cards)]}

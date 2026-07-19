"""16:9 tablet layout helpers — full-bleed panel views.

HA sections views clamp content to ~500px columns even with column_span set.
Panel views render exactly one card at true full viewport width — required for
15.6\" / 1920×1080 wall tablets (ElementZoom landscape).
"""

from __future__ import annotations

from flux_navbar import build_navbar_card
from md3_templates import TABLET_VIEW_CARD_MOD

TABLET_MAX_COLUMNS = 4  # kept for CLI / legacy callers

# Force the single panel card to consume the full view width.
PANEL_ROOT_MOD = {
    "style": (
        "ha-card {\n"
        "  width: 100% !important;\n"
        "  max-width: none !important;\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "  padding: 0 !important;\n"
        "  margin: 0 !important;\n"
        "}\n"
        "#root {\n"
        "  width: 100% !important;\n"
        "  max-width: none !important;\n"
        "}\n"
    )
}

LAYOUT_CARD_MOD = {
    "style": (
        "ha-card {\n"
        "  width: 100% !important;\n"
        "  max-width: none !important;\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "}\n"
        "#root, .layout, layout-card {\n"
        "  width: 100% !important;\n"
        "  max-width: none !important;\n"
        "}\n"
    )
}


def tablet_layout_card(cards: list[dict], *, layout: dict) -> dict:
    """Full-width grid-layout card for panel views."""
    lay = {
        "width": "100%",
        "max_width": "100%",
        "height": "auto",
        "margin": "0",
        "padding": "8px 12px 96px 12px",
        "grid-gap": "12px",
        **layout,
    }
    return {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "layout": lay,
        "cards": cards,
        "card_mod": LAYOUT_CARD_MOD,
    }


def tablet_panel_stack(*cards: dict, use_navbar_card: bool = True) -> dict:
    """Single vertical-stack root for a panel view (full width + navbar)."""
    body = [c for c in cards if c]
    body.append(build_navbar_card(use_navbar_card=use_navbar_card))
    return {
        "type": "vertical-stack",
        "cards": body,
        "card_mod": PANEL_ROOT_MOD,
    }


def tablet_panel_view(
    *,
    title: str,
    path: str,
    icon: str,
    root_card: dict,
    subview: bool = False,
    back_path: str | None = None,
) -> dict:
    """Panel view — one card, full viewport width (true 16:9)."""
    view: dict = {
        "title": title,
        "icon": icon,
        "path": path,
        "type": "panel",
        "theme": "flux-ui-md3",
        "card_mod": TABLET_VIEW_CARD_MOD,
        "cards": [root_card],
    }
    if subview:
        view["subview"] = True
    if back_path:
        view["back_path"] = back_path
    return view


def flatten_section_cards(sections: list[dict]) -> list[dict]:
    """Pull cards out of sections-style grids for panel stacking."""
    cards: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        for card in section.get("cards") or []:
            if isinstance(card, dict):
                card = dict(card)
                card.pop("grid_options", None)
                cards.append(card)
    return cards

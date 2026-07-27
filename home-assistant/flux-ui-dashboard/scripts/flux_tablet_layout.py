"""16:9 tablet layout helpers — full-bleed panel views.

HA sections views clamp content to ~500px columns even with column_span set.
Panel views render exactly one card at true full viewport width — required for
15.6\" / 1920×1080 wall tablets (ElementZoom landscape).
"""

from __future__ import annotations

from md3_templates import TABLET_OVERVIEW_VIEW_CARD_MOD, TABLET_VIEW_CARD_MOD

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

# Overview root locks to the viewport (vh — % height is indefinite in HA panel
# views, so fr rows otherwise size to calendar content and push the page down).
# No bottom navbar on tablet — single child must fill 100dvh (do not use
# :last-child flex:0 or a lone child collapses to content height and page-scrolls).
OVERVIEW_PANEL_ROOT_MOD = {
    "style": (
        ":host {\n"
        "  display: block !important;\n"
        "  height: 100dvh !important;\n"
        "  max-height: 100dvh !important;\n"
        "  overflow: hidden !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
        "ha-card {\n"
        "  width: 100% !important;\n"
        "  height: 100dvh !important;\n"
        "  max-height: 100dvh !important;\n"
        "  max-width: none !important;\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "  padding: 0 !important;\n"
        "  margin: 0 !important;\n"
        "  overflow: hidden !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
        "#root {\n"
        "  width: 100% !important;\n"
        "  height: 100% !important;\n"
        "  max-height: 100% !important;\n"
        "  max-width: none !important;\n"
        "  overflow: hidden !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
        "  display: flex !important;\n"
        "  flex-direction: column !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
        "#root > * {\n"
        "  flex: 1 1 auto !important;\n"
        "  min-height: 0 !important;\n"
        "  max-height: 100% !important;\n"
        "  overflow: hidden !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
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

OVERVIEW_LAYOUT_CARD_MOD = {
    "style": (
        ":host {\n"
        "  display: block !important;\n"
        "  height: 100% !important;\n"
        "  max-height: 100% !important;\n"
        "  min-height: 0 !important;\n"
        "  overflow: hidden !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
        "ha-card {\n"
        "  width: 100% !important;\n"
        "  height: 100% !important;\n"
        "  max-height: 100% !important;\n"
        "  max-width: none !important;\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "  overflow: hidden !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
        "#root, .layout, layout-card {\n"
        "  width: 100% !important;\n"
        "  height: 100% !important;\n"
        "  max-height: 100% !important;\n"
        "  max-width: none !important;\n"
        "  min-height: 0 !important;\n"
        "  overflow: hidden !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
        "/* Grid children must shrink — music must not expand rooms rows. */\n"
        "#root > *, .layout > * {\n"
        "  min-height: 0 !important;\n"
        "  min-width: 0 !important;\n"
        "  max-height: 100% !important;\n"
        "}\n"
        "#root, .layout {\n"
        # Stretch tracks into the locked 100dvh — `start` left a void above Tesla.
        "  align-content: stretch !important;\n"
        "  overscroll-behavior: none !important;\n"
        "  touch-action: none !important;\n"
        "}\n"
    )
}


def tablet_layout_card(cards: list[dict], *, layout: dict, overview: bool = False) -> dict:
    """Full-width grid-layout card for panel views."""
    # Overview: fill the locked 100dvh panel root. No bottom navbar on tablet —
    # keep symmetric padding so Tesla / calendar reach the bottom edge cleanly.
    lay = {
        "width": "100%",
        "max_width": "100%",
        "height": "100%" if overview else "auto",
        "margin": "0",
        "padding": "8px 12px 8px 12px" if overview else "8px 12px 16px 12px",
        "grid-gap": "8px" if overview else "12px",
        **layout,
    }
    if overview:
        lay["card_margin"] = "0"
    return {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "layout": lay,
        "cards": cards,
        "card_mod": OVERVIEW_LAYOUT_CARD_MOD if overview else LAYOUT_CARD_MOD,
    }


def tablet_panel_stack(
    *cards: dict,
    use_navbar_card: bool = True,
    overview: bool = False,
) -> dict:
    """Single vertical-stack root for a tablet panel view (full width, no navbar).

    Bottom navbar covers Tesla tiles on 16:9; tablet uses HA's view tabs / kiosk
    chrome instead. ``use_navbar_card`` is accepted for call-site compatibility
    but ignored — navbar is never appended on tablet.
    """
    del use_navbar_card  # Tablet dashboard has no floating bottom nav.
    body = [c for c in cards if c]
    return {
        "type": "vertical-stack",
        "cards": body,
        "card_mod": OVERVIEW_PANEL_ROOT_MOD if overview else PANEL_ROOT_MOD,
    }


def tablet_panel_view(
    *,
    title: str,
    path: str,
    icon: str,
    root_card: dict,
    subview: bool = False,
    back_path: str | None = None,
    overview: bool = False,
) -> dict:
    """Panel view — one card, full viewport width (true 16:9)."""
    view: dict = {
        "title": title,
        "icon": icon,
        "path": path,
        "type": "panel",
        "theme": "flux-ui-md3",
        "card_mod": TABLET_OVERVIEW_VIEW_CARD_MOD if overview else TABLET_VIEW_CARD_MOD,
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

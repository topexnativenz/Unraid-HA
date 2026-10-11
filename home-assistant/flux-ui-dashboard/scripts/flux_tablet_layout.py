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
#
# The overview grid itself is rigid. layout-card copies grid-template-rows onto
# #root as an inline style and turns layout.height into --layout-height. A
# percentage height does not resolve in the HA panel chain, so minmax(0, Xfr)
# then grows to whatever card is tallest and Tesla leaves the screen. Fixed
# dvh maxima cannot grow, even when card-mod has not loaded yet.

# 8px top + 8px bottom padding, plus two 8px row gaps. --header-height falls
# back to 0px so Fully Kiosk (header hidden) does not leave an empty band.
OVERVIEW_GRID_HEIGHT = "calc(100dvh - var(--header-height, 0px))"
OVERVIEW_GRID_AUTO_ROWS = "0px"
_OVERVIEW_ROW_BUDGET = "(100dvh - var(--header-height, 0px) - 32px)"
OVERVIEW_RIGID_ROWS = (
    "minmax(0, calc(" + _OVERVIEW_ROW_BUDGET + " * 30 / 104)) "
    "minmax(0, calc(" + _OVERVIEW_ROW_BUDGET + " * 48 / 104)) "
    "minmax(0, calc(" + _OVERVIEW_ROW_BUDGET + " * 26 / 104))"
)
RIGID_GRID_COMMENT = "/* Rigid overview grid: no card may grow the 16:9 rows. */"
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

# card-mod on layout-card does not see grid-layout's #root. The "$" block is
# injected into the grid-layout shadow, where the cards are direct children.
_OVERVIEW_GRID_SHADOW_STYLE = (
    RIGID_GRID_COMMENT + "\n"
    "#root {\n"
    "  height: " + OVERVIEW_GRID_HEIGHT + " !important;\n"
    "  max-height: " + OVERVIEW_GRID_HEIGHT + " !important;\n"
    "  min-height: 0 !important;\n"
    "  overflow: hidden !important;\n"
    "  box-sizing: border-box !important;\n"
    "  align-content: stretch !important;\n"
    "  overscroll-behavior: none !important;\n"
    "  touch-action: none !important;\n"
    "}\n"
    "#root > * {\n"
    "  min-height: 0 !important;\n"
    "  min-width: 0 !important;\n"
    "  max-height: 100% !important;\n"
    "  overflow: hidden !important;\n"
    "  contain: size !important;\n"
    "  box-sizing: border-box !important;\n"
    "}\n"
)

OVERVIEW_LAYOUT_CARD_MOD = {
    "style": {
        ".": (
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
            "grid-layout {\n"
            "  display: block !important;\n"
            "  height: 100% !important;\n"
            "  min-height: 0 !important;\n"
            "  max-height: 100% !important;\n"
            "  overflow: hidden !important;\n"
            "}\n"
        ),
        "grid-layout": {"$": _OVERVIEW_GRID_SHADOW_STYLE},
    }
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
        # Applied after **layout so a caller cannot put growable fr rows back.
        lay["height"] = OVERVIEW_GRID_HEIGHT
        lay["max_height"] = OVERVIEW_GRID_HEIGHT
        lay["grid-template-rows"] = OVERVIEW_RIGID_ROWS
        lay["grid-auto-rows"] = OVERVIEW_GRID_AUTO_ROWS
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


def tablet_rigid_grid_errors(blob: str) -> list[str]:
    """Reject a tablet config whose overview grid can still grow with content."""
    errors: list[str] = []
    if OVERVIEW_RIGID_ROWS not in blob:
        errors.append(
            "overview grid-template-rows must be fixed 30/48/26 fractions of 100dvh"
        )
    auto_rows = '"grid-auto-rows": "' + OVERVIEW_GRID_AUTO_ROWS + '"'
    auto_rows_compact = '"grid-auto-rows":"' + OVERVIEW_GRID_AUTO_ROWS + '"'
    if auto_rows not in blob and auto_rows_compact not in blob:
        errors.append('overview grid-auto-rows must be "0px"')
    if OVERVIEW_GRID_HEIGHT not in blob:
        errors.append(
            "overview grid height must be calc(100dvh - var(--header-height, 0px))"
        )
    if "Rigid overview grid: no card may grow the 16:9 rows." not in blob:
        errors.append("overview card-mod missing the rigid-grid rule")
    if "contain: size !important" not in blob:
        errors.append("every overview grid item must use contain: size")
    if (
        "minmax(0, 30fr)" in blob
        or "minmax(0, 48fr)" in blob
        or "minmax(0, 26fr)" in blob
    ):
        errors.append(
            "growable fr overview rows are forbidden "
            "(they size to card content and push Tesla off the panel)"
        )
    if (
        '"grid-auto-rows": "minmax(0, auto)"' in blob
        or '"grid-auto-rows":"minmax(0, auto)"' in blob
    ):
        errors.append("grid-auto-rows minmax(0, auto) can grow an implicit row")
    return errors


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

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
# then grows to whatever card is tallest and Tesla leaves the screen.
# minmax(0, calc(...)) is only a maximum: the track may shrink, and contain:size
# on a height:auto card (Lights, Cameras) resolves that card to 0px.
# Exact lengths (minimum = maximum) cannot shrink or grow.

# 8px top + 8px bottom padding, plus two 8px row gaps. The kiosk header is
# hidden, so the grid is 100dvh — subtracting var(--header-height) left a
# wallpaper gap under Tesla when HA still published a header height.
OVERVIEW_GRID_HEIGHT = "100dvh"
OVERVIEW_GRID_AUTO_ROWS = "0px"
# Shares of (100dvh - 32px), summing to OVERVIEW_ROW_SCALE.
# 34 — clock and Gates & Doors (title + two button rows). The old 30 slice
#     clipped All Off / Goodnight.
# 50 — Lights (title + four button rows) and the square camera grid.
# 20 — both Tesla cards, stretched to the row that ends on the 8px padding.
OVERVIEW_ROW_PARTS = (34, 50, 20)
OVERVIEW_ROW_SCALE = 104
_OVERVIEW_ROW_BUDGET = "(100dvh - 32px)"
OVERVIEW_RIGID_ROWS = " ".join(
    "calc(" + _OVERVIEW_ROW_BUDGET + f" * {part} / {OVERVIEW_ROW_SCALE})"
    for part in OVERVIEW_ROW_PARTS
)
RIGID_GRID_COMMENT = "/* Rigid overview grid: no card may grow the 16:9 rows. */"
# Lights and Cameras size to their content (height: auto). Size containment
# on those items resolves to 0px and hides the section.
GRID_ITEMS_KEEP_HEIGHT_COMMENT = (
    "/* Grid items keep their own height; do not size-contain them. */"
)
# 1920×1080, header hidden. Section mins are the content that must be fully
# inside the row: Gates above the old 30/104 slice (~302px) that cut off
# All Off / Goodnight, Lights above a measured four-row stack (~380px),
# cameras above the square 2×2 in that column, Tesla above a readable pair.
OVERVIEW_FIT_VIEWPORT_H = 1080
OVERVIEW_FIT_CHROME_PX = 32
OVERVIEW_SECTION_MIN_PX = {
    "gates": 328,
    "lights": 400,
    "cameras": 460,
    "tesla": 180,
}
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
    + GRID_ITEMS_KEEP_HEIGHT_COMMENT + "\n"
    "#root {\n"
    "  --header-height: 0px;\n"
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
    "  margin: 0 !important;\n"
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


def overview_row_heights_px(viewport_h: int = OVERVIEW_FIT_VIEWPORT_H) -> tuple[float, float, float]:
    """Exact row heights (px) for a header-hidden viewport.

    Padding and the two row gaps are OVERVIEW_FIT_CHROME_PX, matching
    ``(100dvh - 32px)`` in the grid template.
    """
    budget = viewport_h - OVERVIEW_FIT_CHROME_PX
    return tuple(
        budget * part / OVERVIEW_ROW_SCALE for part in OVERVIEW_ROW_PARTS
    )  # type: ignore[return-value]


def tablet_overview_fit_errors(
    viewport_h: int = OVERVIEW_FIT_VIEWPORT_H,
) -> list[str]:
    """Fail when a section row is shorter than its buttons or Tesla sits high."""
    gates, lights, tesla = overview_row_heights_px(viewport_h)
    errors: list[str] = []
    checks = (
        (gates, "gates", "Gates & Doors (All Off / Goodnight would be clipped)"),
        (lights, "lights", "Lights (a button row would be clipped)"),
        (lights, "cameras", "Cameras (the 2×2 grid would be clipped)"),
        (tesla, "tesla", "Tesla cards"),
    )
    for height, key, label in checks:
        minimum = OVERVIEW_SECTION_MIN_PX[key]
        if height + 0.5 < minimum:
            errors.append(
                f"{label} need {minimum}px at {viewport_h}px but the row is {height:.0f}px"
            )
    filled = gates + lights + tesla + OVERVIEW_FIT_CHROME_PX
    if abs(filled - viewport_h) > 0.6:
        errors.append(
            f"overview rows plus the 8px padding and gaps must fill the "
            f"{viewport_h}px viewport (got {filled:.1f}px) so Tesla sits on "
            "the panel padding"
        )
    return errors


def tablet_rigid_grid_errors(blob: str) -> list[str]:
    """Reject a tablet config whose overview grid can still grow or hide a section."""
    errors: list[str] = []
    parts = "/".join(str(part) for part in OVERVIEW_ROW_PARTS)
    if OVERVIEW_RIGID_ROWS not in blob:
        errors.append(
            f"overview grid-template-rows must be fixed {parts} fractions of (100dvh - 32px)"
        )
    auto_rows = '"grid-auto-rows": "' + OVERVIEW_GRID_AUTO_ROWS + '"'
    auto_rows_compact = '"grid-auto-rows":"' + OVERVIEW_GRID_AUTO_ROWS + '"'
    if auto_rows not in blob and auto_rows_compact not in blob:
        errors.append('overview grid-auto-rows must be "0px"')
    if OVERVIEW_GRID_HEIGHT not in blob:
        errors.append("overview grid height must be 100dvh")
    if "Rigid overview grid: no card may grow the 16:9 rows." not in blob:
        errors.append("overview card-mod missing the rigid-grid rule")
    if GRID_ITEMS_KEEP_HEIGHT_COMMENT not in blob:
        errors.append(
            "overview grid items must keep their own height (Lights and Cameras "
            "collapse to 0px when size-contained)"
        )
    if "contain: size !important" not in blob:
        errors.append(
            "music grid item must use contain: size so the player cannot grow the rows"
        )
    # Music's contain:size is earlier in the config. The rigid-grid style is the
    # rule applied to every grid item; that rule must not size-contain them.
    rigid_at = blob.find("Rigid overview grid: no card may grow the 16:9 rows.")
    rigid_window = blob[rigid_at : rigid_at + 1400] if rigid_at >= 0 else ""
    if "contain: size" in rigid_window:
        errors.append(
            "overview grid items must not use contain: size "
            "(that gives Lights and Cameras a used height of 0)"
        )
    if "minmax(0, calc(" in blob:
        errors.append(
            "overview rows must be exact lengths, not minmax(0, calc(...)) maxima "
            "(a maximum can shrink and clip Gates & Doors)"
        )
    if "margin: 0 !important" not in rigid_window:
        errors.append(
            "overview grid items must set margin: 0 (layout-card's default card "
            "margin leaves a gap under Tesla and clips the bottom button row)"
        )
    if "--header-height: 0px" not in rigid_window:
        errors.append(
            "overview grid must force --header-height: 0px "
            "(a hidden kiosk header must not lift Tesla off the bottom padding)"
        )
    for label in ("Gates & Doors", '"name": "Lights"', '"name": "Cameras"', "Model X", "Model S"):
        if label not in blob:
            errors.append(f"tablet overview missing {label}")
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
    errors.extend(tablet_overview_fit_errors())
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

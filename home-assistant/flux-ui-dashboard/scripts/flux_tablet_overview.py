"""ElementZoom MD3 tablet overview — full-bleed 16:9 panel + layout-card.

Uses type: panel (one card, full viewport width). Sections views cannot
reliably fill a 1920×1080 landscape canvas.
"""

from __future__ import annotations

from flux_action_builders import garage_action, lock_action, scene_action
from flux_media_player import build_tablet_music_card
from flux_navbar import URL_PREFIX
from flux_overview_tabs import build_events_tab_cards
from flux_tablet_layout import tablet_layout_card, tablet_panel_stack, tablet_panel_view
from flux_tablet_tesla import build_tablet_tesla_band
from flux_time import nz_clock_date_js, nz_clock_time_js
from md3_templates import GLASS_CARD_MOD, wrap_glass

# Bubble modular window — Reolink Back Courtyard live stream (fullscreen on tablet).
REOLINK_CAMERA_HASH = "#back-courtyard"
REOLINK_CAMERA_ENTITY = "camera.back_courtyard_fluent"

REOLINK_POPUP_STYLES = """\
#root {
  height: unset !important;
  max-height: 100% !important;
  width: 100% !important;
  max-width: 100% !important;
  transition: transform var(--md-sys-motion-expressive-spatial-default) !important;
}
.bubble-header-container {
  --bubble-button-background-color: var(--md-sys-color-on-secondary);
  --bubble-button-icon-background-color: var(--md-sys-color-on-secondary);
}
/* Fully Kiosk / kiosk-mode: force true viewport fullscreen (ignore sidebar offset). */
.bubble-pop-up {
  --bubble-pop-up-margin: 0px !important;
  --mdc-drawer-width: 0px !important;
  --ha-sidebar-width: 0px !important;
  left: 0 !important;
  right: 0 !important;
  top: 0 !important;
  bottom: 0 !important;
  transform: none !important;
  margin: 0 !important;
  width: 100vw !important;
  max-width: 100vw !important;
  height: 100dvh !important;
  max-height: 100dvh !important;
  border-radius: 0 !important;
  box-sizing: border-box !important;
}
.bubble-pop-up-container {
  padding: 4px 8px 12px 8px !important;
  height: calc(100dvh - 56px) !important;
  max-height: calc(100dvh - 56px) !important;
  box-sizing: border-box !important;
  overflow: hidden !important;
}
"""


def _area(name: str) -> dict:
    """Grid area placement — stretch overview bands to their tracks."""
    if name == "lights":
        # Compact Gates-style toggles — top of mid only (do not stretch).
        return {"grid-area": name, "place-self": "start stretch"}
    if name == "cameras":
        # Square 2×2 sits on the mid-row floor — bottom flush with Music.
        return {"grid-area": name, "place-self": "end stretch"}
    if name in (
        "calendar_notification",
        "tesla",
        "music",
        "greeting",
        "simple_tab",
    ):
        return {"grid-area": name, "place-self": "stretch stretch"}
    return {"grid-area": name, "place-self": "start stretch"}


def _section_title(title: str, *, size: str = "24px", view_layout: dict | None = None) -> dict:
    """Section title — button-card static text renders on Fully Kiosk (markdown does not).

    Default 24px is 50% larger than the previous 16px overview headings.
    """
    card: dict = {
        "type": "custom:button-card",
        "show_icon": False,
        "show_name": True,
        "show_state": False,
        "name": title,
        "styles": {
            "card": [
                {"background": "transparent"},
                {"box-shadow": "none"},
                {"border": "none"},
                {"padding": "4px 8px 2px 8px"},
                {"margin": "0"},
                {"height": "auto"},
                {"min-height": "unset"},
                {"overflow": "visible"},
            ],
            "name": [
                {"font-size": size},
                {"font-weight": "600"},
                {"justify-self": "start"},
                {"text-align": "left"},
                {"color": "var(--primary-text-color)"},
                {"letter-spacing": "0.01em"},
                {"line-height": "1.25"},
            ],
            "grid": [
                {"grid-template-areas": "'n'"},
                {"grid-template-columns": "1fr"},
            ],
        },
    }
    if view_layout:
        card["view_layout"] = view_layout
    return card


def _calendar_body_mod() -> dict:
    """Glass shell — fixed height on .content-container so in-widget scroll works."""
    return {
        "style": (
            GLASS_CARD_MOD["style"]
            + ":host {\n"
            "  display: block !important;\n"
            "  height: 100% !important;\n"
            "  min-height: 0 !important;\n"
            "  overflow: hidden !important;\n"
            "  touch-action: pan-y !important;\n"
            "}\n"
            "ha-card {\n"
            "  height: 100% !important;\n"
            "  min-height: 0 !important;\n"
            "  overflow: hidden !important;\n"
            "  box-sizing: border-box !important;\n"
            "  touch-action: pan-y !important;\n"
            "}\n"
            # calendar-card-pro scrolls inside .content-container — re-enable pan-y
            # after the overview root sets touch-action: none on the page.
            ".content-container {\n"
            "  overflow-x: hidden !important;\n"
            "  overflow-y: auto !important;\n"
            "  -webkit-overflow-scrolling: touch !important;\n"
            "  overscroll-behavior: contain !important;\n"
            "  touch-action: pan-y !important;\n"
            "}\n"
        )
    }


def _greeting_stack(weather_entity: str, cfg: dict) -> dict:
    """Top-left corner — large NZ digital clock + weekday/date (no weather chips)."""
    del weather_entity, cfg  # weather lives in the calendar column
    return {
        "type": "custom:mod-card",
        "view_layout": _area("greeting"),
        "card": {
            "type": "custom:button-card",
            "template": "flux_glass",
            "show_icon": False,
            "show_name": True,
            "show_label": True,
            "show_state": False,
            "name": nz_clock_time_js(),
            "label": nz_clock_date_js(),
            "tap_action": {
                "action": "navigate",
                "navigation_path": f"{URL_PREFIX}/active",
            },
            "styles": {
                "card": [
                    {"padding": "12px 16px"},
                    {"min-height": "0"},
                    {"height": "100%"},
                    {"overflow": "hidden"},
                    {"display": "flex"},
                    {"align-items": "center"},
                    {"justify-content": "center"},
                ],
                "grid": [
                    {"grid-template-areas": "'n' 'l'"},
                    {"grid-template-columns": "1fr"},
                    {"grid-template-rows": "min-content min-content"},
                    {"row-gap": "8px"},
                    {"justify-items": "center"},
                    {"align-content": "center"},
                    {"height": "100%"},
                    {"width": "100%"},
                ],
                "name": [
                    {"font-size": "136px"},
                    {"font-weight": "700"},
                    {"letter-spacing": "0.04em"},
                    {"line-height": "0.9"},
                    {"justify-self": "center"},
                    {"text-align": "center"},
                    {"width": "100%"},
                    {"font-variant-numeric": "tabular-nums"},
                    {"color": "var(--md-sys-color-on-surface)"},
                ],
                "label": [
                    {"font-size": "30px"},
                    {"font-weight": "600"},
                    {"letter-spacing": "0.02em"},
                    {"justify-self": "center"},
                    {"text-align": "center"},
                    {"width": "100%"},
                    {"color": "var(--md-sys-color-on-surface-variant)"},
                    {"opacity": "0.92"},
                    {"padding-left": "0"},
                ],
            },
        },
        "card_mod": {
            "style": (
                ":host {\n"
                "  display: block !important;\n"
                "  height: 100% !important;\n"
                "  min-height: 0 !important;\n"
                "  overflow: hidden !important;\n"
                "}\n"
                "ha-card {\n"
                "  height: 100% !important;\n"
                "  min-height: 0 !important;\n"
                "}\n"
            )
        },
    }


def _climate_tab_cards(cfg: dict, weather_entity: str) -> list[dict]:
    tablet = cfg.get("tablet") or {}
    indoor = tablet.get("indoor_temperature")
    outdoor = tablet.get("outdoor_temperature") or weather_entity
    climate_entity = tablet.get("climate_entity")

    temp_cards: list[dict] = []
    if indoor:
        temp_cards.append(
            {
                "type": "custom:mushroom-entity-card",
                "entity": indoor,
                "name": "Indoor",
                "icon": "mdi:home-thermometer",
                "layout": "horizontal",
                "fill_container": True,
            }
        )
    temp_cards.append(
        {
            "type": "custom:mushroom-entity-card",
            "entity": outdoor,
            "name": "Outdoor",
            "icon": "mdi:thermometer",
            "layout": "horizontal",
            "fill_container": True,
        }
    )

    graph_entities = [e for e in (indoor, outdoor) if e]
    cards: list[dict] = [
        {
            "type": "grid",
            "columns": len(temp_cards),
            "square": False,
            "cards": [wrap_glass(c) for c in temp_cards],
        },
        wrap_glass(
            {
                "type": "history-graph",
                "hours_to_show": 24,
                "entities": [{"entity": e} for e in graph_entities],
            }
        ),
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
    return cards


def _toggles_tab_cards(cfg: dict) -> list[dict]:
    cards: list[dict] = []
    for item in cfg.get("quick_actions", {}).get("gate", []):
        card = lock_action(
            item["entity"],
            item["name"],
            columns=12,
            status_entity=item.get("status_entity"),
            hold_entity=item.get("hold_entity"),
            status_on_means_open=bool(item.get("status_on_means_open", True)),
        )
        card.pop("grid_options", None)
        cards.append(card)
    for item in cfg.get("quick_actions", {}).get("garage", []):
        card = garage_action(item, columns=12)
        card.pop("grid_options", None)
        cards.append(card)
    for item in cfg.get("quick_actions", {}).get("actions", []):
        card = scene_action(
            item["name"],
            item["subtitle"],
            item["icon"],
            item["service"],
            item["target"],
            columns=12,
        )
        card.pop("grid_options", None)
        cards.append(card)
    if not cards:
        cards.append(
            wrap_glass({"type": "markdown", "content": "No quick toggles configured."})
        )
    return [{"type": "grid", "columns": 2, "square": False, "cards": cards}]


def _scenes_tab_cards() -> list[dict]:
    prefix = URL_PREFIX
    return [
        {
            "type": "custom:mushroom-chips-card",
            "alignment": "center",
            "chips": [
                {
                    "type": "template",
                    "icon": "mdi:palette",
                    "content": "Open presets",
                    "tap_action": {
                        "action": "navigate",
                        "navigation_path": f"{prefix}/scenes",
                    },
                },
                {
                    "type": "template",
                    "icon": "mdi:lightbulb-group",
                    "content": "Lights",
                    "tap_action": {
                        "action": "navigate",
                        "navigation_path": f"{prefix}/lights",
                    },
                },
            ],
        }
    ]


def _simple_tab_panel(cfg: dict, weather_entity: str, *, use_simple_tabs: bool) -> dict:
    del weather_entity, use_simple_tabs
    toggles_cards = _toggles_tab_cards(cfg)
    return {
        "type": "custom:mod-card",
        "view_layout": _area("simple_tab"),
        "card": {
            "type": "vertical-stack",
            "cards": [_section_title("Gates & Doors"), *toggles_cards],
        },
        "card_mod": {
            "style": {
                ".": (
                    ":host {\n"
                    "  display: block !important;\n"
                    "  height: 100% !important;\n"
                    "  min-height: 0 !important;\n"
                    "  overflow: hidden !important;\n"
                    "}\n"
                    "hui-vertical-stack-card {\n"
                    "  height: 100% !important;\n"
                    "  display: block !important;\n"
                    "}\n"
                ),
                "hui-vertical-stack-card": {
                    "$": (
                        "#root {\n"
                        "  display: flex !important;\n"
                        "  flex-direction: column !important;\n"
                        "  height: 100% !important;\n"
                        "  min-height: 0 !important;\n"
                        "  gap: 8px !important;\n"
                        "}\n"
                        "#root > *:not(:first-child) {\n"
                        "  flex: 1 1 auto !important;\n"
                        "  min-height: 0 !important;\n"
                        "}\n"
                    )
                },
            }
        },
    }


def _weather_forecast_cards(weather_entity: str) -> list[dict]:
    """Compact daily forecast — sits above the calendar in the right column."""
    return [
        _section_title("Weather Forecast"),
        wrap_glass(
            {
                "type": "weather-forecast",
                "entity": weather_entity,
                "forecast_type": "daily",
                "show_current": False,
                "show_forecast": True,
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  max-height: 148px !important;\n"
                        "  overflow: hidden !important;\n"
                        "}\n"
                    )
                },
            }
        ),
    ]


def _music_panel(cfg: dict, *, use_mediocre_media: bool) -> dict:
    """Music column — source chips + artwork-first massive player (no footer bar)."""
    body = build_tablet_music_card(cfg, use_mediocre=use_mediocre_media)
    return {
        "type": "vertical-stack",
        "view_layout": _area("music"),
        "cards": [
            _section_title("Music"),
            wrap_glass(body),
        ],
        "card_mod": {
            "style": (
                ":host, ha-card {\n"
                "  height: 100% !important;\n"
                "  max-height: 100% !important;\n"
                "  min-height: 0 !important;\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  overflow: hidden !important;\n"
                "  box-sizing: border-box !important;\n"
                "  touch-action: pan-y !important;\n"
                "}\n"
                "#root {\n"
                "  display: flex !important;\n"
                "  flex-direction: column !important;\n"
                "  height: 100% !important;\n"
                "  min-height: 0 !important;\n"
                "  overflow: hidden !important;\n"
                "  gap: 2px !important;\n"
                "}\n"
                "#root > *:first-child {\n"
                "  flex: 0 0 auto !important;\n"
                "  overflow: visible !important;\n"
                "}\n"
                "#root > *:not(:first-child) {\n"
                "  flex: 1 1 auto !important;\n"
                "  min-height: 0 !important;\n"
                "  overflow: hidden !important;\n"
                "}\n"
            )
        },
    }


# Calendar column fills the locked overview grid (not raw 100dvh — that clips Tesla).
_CALENDAR_COLUMN_HEIGHT = "100%"
_CALENDAR_BODY_HEIGHT = "calc(100% - 200px)"


def _calendar_notification(
    cfg: dict, weather_entity: str, *, use_calendar_pro: bool
) -> dict:
    """Right column — weather forecast on top, scrollable week calendar below."""
    events = build_events_tab_cards(cfg, use_calendar_pro=use_calendar_pro)
    stack_cards: list[dict] = [
        *_weather_forecast_cards(weather_entity),
        _section_title("Calendar"),
    ]

    for card in events:
        if card.get("type") != "custom:calendar-card-pro":
            # Mushroom fallback — constrain with card-mod scroll box.
            if card.get("type") == "vertical-stack":
                fallback = {
                    "type": "vertical-stack",
                    "cards": card.get("cards") or [],
                    "card_mod": {
                        "style": (
                            ":host, ha-card, #root {\n"
                            "  height: 100% !important;\n"
                            "  max-height: 100% !important;\n"
                            "  min-height: 0 !important;\n"
                            "  overflow-y: auto !important;\n"
                            "  -webkit-overflow-scrolling: touch !important;\n"
                            "}\n"
                        )
                    },
                }
                stack_cards.append(wrap_glass(fallback))
            else:
                stack_cards.append(card)
            continue

        cal = dict(card)
        # Full week always visible on tablet — no compact/expand toggle.
        cal["days_to_show"] = 7
        cal["compact_days_to_show"] = 7
        cal["compact_events_complete_days"] = True
        cal["show_empty_days"] = True
        cal.pop("compact_events_to_show", None)
        cal.pop("tap_action", None)
        # Keep cache across view switches — refresh_on_navigate:true remounts the
        # card and leaves the top-right .loading-indicator spinning on tablets.
        cal["refresh_on_navigate"] = False
        # Keep the widget static — no ticking UI; rare poll + entity-driven updates.
        cal["show_countdown"] = False
        cal["show_progress_bar"] = False
        cal["today_indicator"] = "dot"
        cal["refresh_interval"] = int(
            ((cfg.get("overview_tabs") or {}).get("events") or {}).get("refresh_interval", 360)
        )
        # Fill remaining column — explicit dvh calc resolves on Fully Kiosk where
        # height:100% inside flex often stays at 0 and leaves "Loading calendar…".
        cal["height"] = _CALENDAR_BODY_HEIGHT
        cal["max_height"] = _CALENDAR_BODY_HEIGHT
        cal["min_height"] = "320px"
        # Narrow tablet column — slightly smaller date column
        cal["day_font_size"] = "20px"
        cal["weekday_font_size"] = "11px"
        cal["month_font_size"] = "10px"
        # Weather already sits above this card. Nested weather websocket subscriptions
        # hang on Fully Kiosk and leave .loading-indicator spinning forever.
        cal.pop("weather", None)
        body_mod = _calendar_body_mod()
        # Only hide the corner spinner — NOT [class*='loading'] (that matched event
        # nodes on calendar-card-pro and blanked the whole week on tablet).
        body_mod["style"] = (
            body_mod["style"]
            + ".loading-indicator,\n"
            + ".loading-indicator .spinner,\n"
            + "ha-card > .loading-indicator {\n"
            "  display: none !important;\n"
            "}\n"
        )
        cal["card_mod"] = body_mod
        stack_cards.append(cal)

    # Full-height column: weather (top) + calendar (fills remainder, scrolls inside).
    return {
        "type": "custom:mod-card",
        "view_layout": _area("calendar_notification"),
        "card_mod": {
            "style": (
                ":host {\n"
                "  display: block !important;\n"
                f"  height: {_CALENDAR_COLUMN_HEIGHT} !important;\n"
                f"  max-height: {_CALENDAR_COLUMN_HEIGHT} !important;\n"
                "  min-height: 0 !important;\n"
                "  overflow: hidden !important;\n"
                "  box-sizing: border-box !important;\n"
                "  padding-top: 2px !important;\n"
                "  touch-action: pan-y !important;\n"
                "}\n"
                "ha-card {\n"
                f"  height: {_CALENDAR_COLUMN_HEIGHT} !important;\n"
                f"  max-height: {_CALENDAR_COLUMN_HEIGHT} !important;\n"
                "  min-height: 0 !important;\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  overflow: hidden !important;\n"
                "  touch-action: pan-y !important;\n"
                "}\n"
            )
        },
        "card": {
            "type": "vertical-stack",
            "cards": stack_cards,
            "card_mod": {
                "style": (
                    ":host, ha-card {\n"
                    "  height: 100% !important;\n"
                    f"  max-height: {_CALENDAR_COLUMN_HEIGHT} !important;\n"
                    "  min-height: 0 !important;\n"
                    "  background: transparent !important;\n"
                    "  box-shadow: none !important;\n"
                    "  border: none !important;\n"
                    "  overflow: hidden !important;\n"
                    "  box-sizing: border-box !important;\n"
                    "  touch-action: pan-y !important;\n"
                    "}\n"
                    "#root {\n"
                    "  display: flex !important;\n"
                    "  flex-direction: column !important;\n"
                    "  height: 100% !important;\n"
                    "  min-height: 0 !important;\n"
                    "  overflow: hidden !important;\n"
                    "  box-sizing: border-box !important;\n"
                    "  gap: 4px !important;\n"
                    "  touch-action: pan-y !important;\n"
                    "}\n"
                    # Weather title + forecast + Calendar title stay compact.
                    "#root > *:nth-child(-n+3) {\n"
                    "  flex: 0 0 auto !important;\n"
                    "  overflow: visible !important;\n"
                    "}\n"
                    # Week calendar fills remaining height and scrolls inside.
                    "#root > *:last-child {\n"
                    "  flex: 1 1 auto !important;\n"
                    "  min-height: 0 !important;\n"
                    "  height: auto !important;\n"
                    "  max-height: none !important;\n"
                    "  overflow: hidden !important;\n"
                    "  display: flex !important;\n"
                    "  flex-direction: column !important;\n"
                    "  touch-action: pan-y !important;\n"
                    "}\n"
                )
            },
        },
    }


def _fill_track_style() -> str:
    """Children fill definite 1fr grid cells (Fully-safe — no per-tile aspect-ratio)."""
    return (
        "ha-card, #root, .layout, layout-card {\n"
        "  height: 100% !important;\n"
        "  max-height: 100% !important;\n"
        "  min-height: 0 !important;\n"
        "  width: 100% !important;\n"
        "  background: transparent !important;\n"
        "  box-shadow: none !important;\n"
        "  border: none !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
        "#root > *, .layout > * {\n"
        "  min-height: 0 !important;\n"
        "  min-width: 0 !important;\n"
        "  height: 100% !important;\n"
        "  max-height: 100% !important;\n"
        "  width: 100% !important;\n"
        "  overflow: hidden !important;\n"
        "}\n"
        "#root > * ha-card,\n"
        ".layout > * ha-card {\n"
        "  height: 100% !important;\n"
        "  min-height: 0 !important;\n"
        "  max-height: none !important;\n"
        "  width: 100% !important;\n"
        "  aspect-ratio: unset !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
    )


_DEFAULT_AREA_LIGHTS: list[dict] = [
    {"name": "Kitchen", "entity": "light.kitchen_all", "icon": "mdi:stove"},
    {"name": "Dining", "entity": "light.dining_all", "icon": "mdi:silverware-fork-knife"},
    {
        "name": "Black Lounge",
        "entity": "light.black_lounge_all",
        "icon": "mdi:sofa",
    },
    {
        "name": "White Lounge",
        "entity": "light.white_lounge_all",
        "icon": "mdi:sofa-outline",
    },
    {"name": "Walkway", "entity": "light.walkway_all", "icon": "mdi:walk"},
    {
        "name": "Kids Hallway",
        "entity": "light.kids_hallway_all",
        "icon": "mdi:human-male-child",
    },
]


def _area_light_button(area: dict) -> dict:
    """Area all-lights toggle — same compact flux_action chrome as Gates & Doors."""
    entity = area["entity"]
    name = area.get("name") or entity
    icon = area.get("icon") or "mdi:lightbulb-group"
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "entity": entity,
        "name": name,
        "icon": icon,
        "show_icon": True,
        "show_entity_picture": False,
        "show_label": True,
        "label": (
            "[[[ return entity?.state === 'on' ? 'On' "
            ": (entity?.state === 'off' ? 'Off' : (entity?.state || '—')); ]]]"
        ),
        "tap_action": {"action": "toggle"},
        "hold_action": {"action": "more-info"},
        "styles": {
            "grid": [
                {"grid-template-areas": "'i n' 'i l'"},
                {"grid-template-columns": "52px 1fr"},
                {"grid-template-rows": "min-content min-content"},
                {"column-gap": "12px"},
            ],
            "card": [
                {"height": "auto"},
                {"min-height": "unset"},
                {"max-height": "none"},
            ],
            "img_cell": [
                {"border-radius": "16px"},
                {"width": "52px"},
                {"height": "52px"},
                {"place-self": "center"},
                {"background-color": "var(--contrast1)"},
            ],
            "icon": [
                {"width": "26px"},
                {"height": "26px"},
                {"color": "var(--md-sys-color-primary)"},
            ],
            "name": [
                {"font-weight": "600"},
                {"font-size": "13px"},
                {"justify-self": "start"},
                {"text-align": "left"},
            ],
            "label": [
                {"justify-self": "start"},
                {"text-align": "left"},
            ],
        },
        "state": [
            {
                "value": "on",
                "styles": {
                    "icon": [{"color": "#FFD54F"}],
                    "img_cell": [
                        {
                            "background-color": (
                                "color-mix(in srgb, #FFD54F 28%, var(--contrast1))"
                            )
                        }
                    ],
                    "label": [{"color": "#FFD54F"}, {"font-weight": "700"}],
                },
            }
        ],
    }


def _lights_band(cfg: dict) -> dict:
    """Left mid — compact 2-col Gates-style toggles (top-aligned, not stretched)."""
    areas = list((cfg.get("area_lights") or {}).get("areas") or _DEFAULT_AREA_LIGHTS)
    buttons = [_area_light_button(a) for a in areas[:6]]
    while len(buttons) < 6:
        buttons.append(
            {
                "type": "custom:button-card",
                "template": "flux_action",
                "name": "Light",
                "label": "—",
                "icon": "mdi:lightbulb-outline",
                "show_icon": True,
            }
        )

    return {
        "type": "custom:mod-card",
        "view_layout": _area("lights"),
        "card": {
            "type": "vertical-stack",
            "cards": [
                _section_title("Lights"),
                {"type": "grid", "columns": 2, "square": False, "cards": buttons},
            ],
        },
        "card_mod": {
            "style": {
                ".": (
                    ":host {\n"
                    "  display: block !important;\n"
                    "  height: auto !important;\n"
                    "  max-height: 100% !important;\n"
                    "  min-height: 0 !important;\n"
                    "  align-self: start !important;\n"
                    "  overflow: hidden !important;\n"
                    "  box-sizing: border-box !important;\n"
                    "}\n"
                    "ha-card {\n"
                    "  height: auto !important;\n"
                    "  background: transparent !important;\n"
                    "  box-shadow: none !important;\n"
                    "  border: none !important;\n"
                    "}\n"
                    "hui-vertical-stack-card {\n"
                    "  height: auto !important;\n"
                    "  display: block !important;\n"
                    "}\n"
                ),
                "hui-vertical-stack-card": {
                    "$": (
                        "#root {\n"
                        "  display: flex !important;\n"
                        "  flex-direction: column !important;\n"
                        "  height: auto !important;\n"
                        "  min-height: 0 !important;\n"
                        "  gap: 8px !important;\n"
                        "}\n"
                        "#root > * {\n"
                        "  flex: 0 0 auto !important;\n"
                        "  height: auto !important;\n"
                        "  min-height: 0 !important;\n"
                        "}\n"
                    )
                },
            }
        },
    }


def _cameras_band(cfg: dict, *, use_auto_entities: bool = True) -> dict:
    """Right mid — square 2×2 cameras, bottom flush with Music.

    Music spans top+mid so its bottom is the mid-row floor. End-align a
    width-driven square tile grid on that floor (bring cards up vs stretch-fill).
    Mid track is 52fr (definite height) so Fully can resolve aspect-ratio.
    """
    del use_auto_entities
    cameras = _tablet_overview_cameras(cfg)
    cam_tiles = [_camera_feed_card(cam) for cam in cameras[:4]]
    if not cam_tiles:
        cam_tiles = [
            wrap_glass(
                {
                    "type": "markdown",
                    "content": (
                        "Configure tablet cameras in `cameras.yaml` "
                        "or `entities.yaml` → `tablet.overview_cameras`."
                    ),
                }
            )
        ]
    while len(cam_tiles) < 4:
        cam_tiles.append(wrap_glass({"type": "markdown", "content": "Camera"}))

    return {
        "type": "custom:mod-card",
        "view_layout": _area("cameras"),
        "card": {
            "type": "vertical-stack",
            "cards": [
                _section_title("Cameras"),
                {
                    "type": "custom:layout-card",
                    "layout_type": "custom:grid-layout",
                    "layout": {
                        "grid-template-columns": "1fr 1fr",
                        "grid-template-rows": "1fr 1fr",
                        "grid-gap": "8px",
                        "gap": "8px",
                        "height": "100%",
                        "width": "100%",
                        "margin": "0",
                        "padding": "0",
                        "card_margin": "0",
                        "align-items": "stretch",
                        "justify-items": "stretch",
                    },
                    "cards": cam_tiles,
                    "card_mod": {
                        "style": (
                            # Width is definite from the overview column; 1:1
                            # yields square cells. Cap so a short mid still fits.
                            ":host {\n"
                            "  display: block !important;\n"
                            "  width: 100% !important;\n"
                            "  height: auto !important;\n"
                            "  aspect-ratio: 1 / 1 !important;\n"
                            "  max-height: calc(100% - 36px) !important;\n"
                            "  min-height: 0 !important;\n"
                            "  overflow: hidden !important;\n"
                            "  box-sizing: border-box !important;\n"
                            "}\n"
                            + _fill_track_style()
                        )
                    },
                },
            ],
        },
        "card_mod": {
            "style": {
                ".": (
                    ":host {\n"
                    "  display: block !important;\n"
                    "  height: auto !important;\n"
                    "  max-height: 100% !important;\n"
                    "  min-height: 0 !important;\n"
                    "  width: 100% !important;\n"
                    "  align-self: end !important;\n"
                    "  overflow: hidden !important;\n"
                    "  box-sizing: border-box !important;\n"
                    "}\n"
                    "ha-card {\n"
                    "  height: auto !important;\n"
                    "  max-height: 100% !important;\n"
                    "  background: transparent !important;\n"
                    "  box-shadow: none !important;\n"
                    "  border: none !important;\n"
                    "}\n"
                    "hui-vertical-stack-card {\n"
                    "  height: auto !important;\n"
                    "  max-height: 100% !important;\n"
                    "  display: block !important;\n"
                    "}\n"
                ),
                "hui-vertical-stack-card": {
                    "$": (
                        "#root {\n"
                        "  display: flex !important;\n"
                        "  flex-direction: column !important;\n"
                        "  height: auto !important;\n"
                        "  max-height: 100% !important;\n"
                        "  min-height: 0 !important;\n"
                        "  gap: 8px !important;\n"
                        "  justify-content: flex-end !important;\n"
                        "}\n"
                        "#root > *:first-child {\n"
                        "  flex: 0 0 auto !important;\n"
                        "}\n"
                        "#root > *:last-child {\n"
                        "  flex: 0 0 auto !important;\n"
                        "  min-height: 0 !important;\n"
                        "  width: 100% !important;\n"
                        "  max-height: 100% !important;\n"
                        "}\n"
                    )
                },
            }
        },
    }


# Back-compat aliases for callers/tests that still import mid helpers.
def _rooms_band(cfg: dict) -> dict:
    return _lights_band(cfg)


def _mid_rooms_cameras_band(cfg: dict, *, use_auto_entities: bool) -> dict:
    del use_auto_entities
    return _lights_band(cfg)


def _camera_card_mod() -> dict:
    """Camera tile — fills its mid-grid cell (object-fit cover, no letterbox)."""
    return {
        "style": (
            "ha-card {\n"
            "  position: relative !important;\n"
            "  padding: 0 !important;\n"
            "  margin: 0 !important;\n"
            "  overflow: hidden !important;\n"
            "  width: 100% !important;\n"
            "  height: 100% !important;\n"
            "  min-height: 0 !important;\n"
            "  aspect-ratio: unset !important;\n"
            "  background: #111 !important;\n"
            "  box-sizing: border-box !important;\n"
            "}\n"
            ".card-content,\n"
            "hui-image,\n"
            "ha-camera-stream,\n"
            "img,\n"
            "video {\n"
            "  position: absolute !important;\n"
            "  inset: 0 !important;\n"
            "  top: 0 !important;\n"
            "  left: 0 !important;\n"
            "  right: 0 !important;\n"
            "  bottom: 0 !important;\n"
            "  width: 100% !important;\n"
            "  height: 100% !important;\n"
            "  max-width: 100% !important;\n"
            "  max-height: 100% !important;\n"
            "  min-width: 0 !important;\n"
            "  min-height: 0 !important;\n"
            "  object-fit: cover !important;\n"
            "  margin: 0 !important;\n"
            "  padding: 0 !important;\n"
            "  display: block !important;\n"
            "}\n"
            "#name,\n"
            ".name,\n"
            ".footer {\n"
            "  position: absolute !important;\n"
            "  inset: 0 !important;\n"
            "  left: 0 !important;\n"
            "  right: 0 !important;\n"
            "  top: 0 !important;\n"
            "  bottom: 0 !important;\n"
            "  display: flex !important;\n"
            "  align-items: center !important;\n"
            "  justify-content: center !important;\n"
            "  text-align: center !important;\n"
            "  z-index: 2 !important;\n"
            "  width: 100% !important;\n"
            "  height: 100% !important;\n"
            "  margin: 0 !important;\n"
            "  padding: 12px !important;\n"
            "  box-sizing: border-box !important;\n"
            "  font-size: 22px !important;\n"
            "  font-weight: 700 !important;\n"
            "  letter-spacing: 0.02em !important;\n"
            "  line-height: 1.15 !important;\n"
            "  color: #fff !important;\n"
            "  text-shadow: 0 2px 8px rgba(0,0,0,0.95),\n"
            "    0 0 18px rgba(0,0,0,0.7) !important;\n"
            "  pointer-events: none !important;\n"
            "}\n"
        )
    }


def build_reolink_fullscreen_popup(cfg: dict | None = None) -> dict:
    """Fullscreen bubble modular window for Reolink Back Courtyard live stream.

    Uses picture-entity live (stable HA MJPEG/HLS) — WebRTC often connects then
    drops black on Fully Kiosk. ``is_sidebar_hidden`` keeps the popup centered
    when kiosk-mode hides the HA sidebar.
    """
    del cfg  # reserved for future multi-camera popups
    return {
        "type": "custom:bubble-card",
        "card_type": "pop-up",
        "hash": REOLINK_CAMERA_HASH,
        "name": "Back Courtyard",
        "icon": "mdi:cctv",
        "entity": REOLINK_CAMERA_ENTITY,
        "styles": REOLINK_POPUP_STYLES,
        "bg_color": "#0a0a0a",
        "bg_opacity": "98",
        "bg_blur": "0",
        "button_type": "name",
        "sub_button": {"main": [], "bottom": []},
        "popup_style": "classic",
        # Tablet Fully Kiosk hides HA sidebar — without this, bubble offsets right.
        "is_sidebar_hidden": True,
        "width_desktop": "100%",
        "margin": "0px",
        "margin_top_mobile": "0px",
        "margin_top_desktop": "0px",
        "cards": [
            {
                "type": "picture-entity",
                "entity": REOLINK_CAMERA_ENTITY,
                "name": "Back Courtyard",
                "camera_image": REOLINK_CAMERA_ENTITY,
                "camera_view": "live",
                "show_name": False,
                "show_state": False,
                "tap_action": {"action": "none"},
                "hold_action": {
                    "action": "more-info",
                    "entity": REOLINK_CAMERA_ENTITY,
                },
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: #000 !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "  border-radius: 12px !important;\n"
                        "  padding: 0 !important;\n"
                        "  margin: 0 !important;\n"
                        "  width: 100% !important;\n"
                        "  height: calc(100dvh - 88px) !important;\n"
                        "  max-height: calc(100dvh - 88px) !important;\n"
                        "  overflow: hidden !important;\n"
                        "}\n"
                        "hui-image,\n"
                        "ha-camera-stream,\n"
                        "img,\n"
                        "video {\n"
                        "  width: 100% !important;\n"
                        "  height: 100% !important;\n"
                        # Cover fills the card — Duo 3 ultra-wide must not letterbox.
                        "  object-fit: cover !important;\n"
                        "  object-position: center !important;\n"
                        "  background: #000 !important;\n"
                        "}\n"
                    )
                },
            }
        ],
    }


def _with_camera_card_mod(tile: dict) -> dict:
    """Append square-tile cover card_mod for tablet mid-grid cameras."""
    tile = dict(tile)
    existing = tile.get("card_mod") or {}
    base = existing.get("style", "") if isinstance(existing, dict) else ""
    # Camera rules last so they override wrap_glass background / sizing.
    tile["card_mod"] = {"style": base + _camera_card_mod()["style"]}
    return tile


def _camera_feed_card(camera: dict) -> dict:
    """Camera tile that fills its mid-grid cell (same size as room tiles).

    All outdoor cams use ``/local/flux-ui/camera-stills/`` snapshots (not Eufy
    event images). Tap: Reolink → fullscreen bubble; Eufy → wake-then-live view.
    """
    from flux_tablet_eufy import build_eufy_overview_tile, build_overview_still_tile

    entity = camera["entity"]
    stream = (camera.get("stream") or "").strip()

    if stream:
        return _with_camera_card_mod(build_eufy_overview_tile(camera))
    if entity == REOLINK_CAMERA_ENTITY:
        return _with_camera_card_mod(
            build_overview_still_tile(camera, tap_path=REOLINK_CAMERA_HASH)
        )
    return _with_camera_card_mod(
        build_overview_still_tile(camera, tap_path=f"{URL_PREFIX}/overview")
    )


def _tablet_overview_cameras(cfg: dict) -> list[dict]:
    """Curated 4-camera set — never auto-discover the whole house."""
    tablet = cfg.get("tablet") or {}
    curated = list(tablet.get("overview_cameras") or [])
    if curated:
        return curated[:4]
    cameras_cfg = cfg.get("cameras_config") or {}
    manual = list(cameras_cfg.get("cameras") or [])
    return manual[:4]


def build_tablet_overview_view(
    cfg: dict,
    weather_entity: str,
    *,
    climate_section: dict | None = None,
    use_navbar_card: bool = True,
    use_calendar_pro: bool = True,
    use_auto_entities: bool = True,
    use_simple_tabs: bool = True,
    use_mediocre_media: bool = True,
) -> dict:
    """Full-bleed 16:9 overview — panel view + layout-card grid."""
    del climate_section
    content_cards = [
        _greeting_stack(weather_entity, cfg),
        _simple_tab_panel(cfg, weather_entity, use_simple_tabs=use_simple_tabs),
        _music_panel(cfg, use_mediocre_media=use_mediocre_media),
        _calendar_notification(
            cfg, weather_entity, use_calendar_pro=use_calendar_pro
        ),
        _lights_band(cfg),
        _cameras_band(cfg, use_auto_entities=use_auto_entities),
        build_tablet_tesla_band(cfg, view_layout=_area("tesla")),
    ]
    layout = tablet_layout_card(
        content_cards,
        overview=True,
        layout={
            # 15.6" / 1920×1080 — all bands visible inside 100dvh.
            # Top ~26%: clock | gates. Mid ~52%: compact Lights (top) + Cameras
            # filling to Music bottom. Bottom ~18%: Tesla snug under that edge.
            # Never use mid=1fr with huge top/tesla fr — mid collapses on Fully.
            "grid-template-columns": "1fr 1fr 1.05fr 1.15fr",
            "grid-template-rows": (
                "minmax(0, 26fr) minmax(0, 52fr) minmax(0, 18fr)"
            ),
            "grid-auto-rows": "minmax(0, auto)",
            "align-content": "stretch",
            "align-items": "stretch",
            "justify-items": "stretch",
            "grid-gap": "8px",
            "height": "100%",
            "max_height": "100%",
            "grid-template-areas": (
                '"greeting simple_tab music calendar_notification"\n'
                '"lights cameras music calendar_notification"\n'
                '"tesla tesla tesla calendar_notification"'
            ),
        },
    )
    # Bubble pop-up must live in the overview DOM; keep it zero-height when closed
    # so it does not steal flex space from the 16:9 layout.
    overview_body = {
        "type": "vertical-stack",
        "cards": [
            layout,
            build_reolink_fullscreen_popup(cfg),
        ],
        "card_mod": {
            "style": (
                ":host, ha-card {\n"
                "  height: 100% !important;\n"
                "  max-height: 100% !important;\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  padding: 0 !important;\n"
                "  margin: 0 !important;\n"
                "  overflow: hidden !important;\n"
                "}\n"
                "#root {\n"
                "  height: 100% !important;\n"
                "  display: flex !important;\n"
                "  flex-direction: column !important;\n"
                "  overflow: hidden !important;\n"
                "}\n"
                "#root > *:first-child {\n"
                "  flex: 1 1 auto !important;\n"
                "  min-height: 0 !important;\n"
                "  max-height: 100% !important;\n"
                "  overflow: hidden !important;\n"
                "}\n"
                "#root > *:last-child {\n"
                "  flex: 0 0 0 !important;\n"
                "  height: 0 !important;\n"
                "  min-height: 0 !important;\n"
                "  max-height: 0 !important;\n"
                "  overflow: visible !important;\n"
                "}\n"
            )
        },
    }
    root = tablet_panel_stack(
        overview_body, use_navbar_card=use_navbar_card, overview=True
    )
    return tablet_panel_view(
        title="Overview",
        path="overview",
        icon="mdi:home",
        root_card=root,
        overview=True,
    )

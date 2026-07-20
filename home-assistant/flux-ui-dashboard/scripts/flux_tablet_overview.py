"""ElementZoom MD3 tablet overview — full-bleed 16:9 panel + layout-card.

Uses type: panel (one card, full viewport width). Sections views cannot
reliably fill a 1920×1080 landscape canvas.
"""

from __future__ import annotations

from flux_action_builders import garage_action, lock_action, scene_action
from flux_layouts import flux_room_tile
from flux_navbar import URL_PREFIX
from flux_overview_tabs import _simple_tabs_shell, build_events_tab_cards
from flux_rooms_index import ROOM_CATEGORIES, ROOMS_TAB_ENTITY, _category_tab_chips
from flux_tablet_layout import tablet_layout_card, tablet_panel_stack, tablet_panel_view
from flux_tablet_tesla import build_tablet_tesla_band
from flux_time import nz_datetime_short_js, nz_greeting_js
from md3_templates import GLASS_CARD_MOD, wrap_glass


def _area(name: str) -> dict:
    """Grid area placement. Pack content rows to the top; calendar/tesla fill height."""
    if name in ("calendar_notification", "tesla"):
        return {"grid-area": name, "place-self": "stretch stretch"}
    # Greeting / toggles / weather / rooms — no vertical stretch (avoids huge gaps).
    return {"grid-area": name, "place-self": "start stretch"}


def _transparent_title(title: str, *, size: str = "16px") -> dict:
    return {
        "type": "custom:mushroom-title-card",
        "title": title,
        "alignment": "start",
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  padding: 0 0 4px 0 !important;\n"
                "}\n"
                f".header {{ font-size: {size} !important; font-weight: 600 !important; }}\n"
            )
        },
    }


def _bitmoji_url(cfg: dict) -> str:
    hero = (cfg.get("context") or {}).get("hero") or {}
    return str(hero.get("bitmoji_default") or "/local/flux-ui/bitmoji/dave.png")


def _greeting_stack(weather_entity: str, cfg: dict) -> dict:
    high_low = (
        "{% set f = state_attr('" + weather_entity + "', 'forecast') %}"
        "{% if f and f[0] is mapping %}"
        "{{ f[0].get('temperature', '—') }}° / {{ f[0].get('templow', '—') }}°"
        "{% else %}"
        "{% set t = state_attr('" + weather_entity + "', 'temperature') %}"
        "{{ t }}°"
        "{% endif %}"
    )
    return {
        "type": "vertical-stack",
        "view_layout": _area("greeting"),
        "cards": [
            {
                "type": "custom:mushroom-title-card",
                "alignment": "start",
                "title": "Home",
                "subtitle": "Live overview",
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: transparent !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "}\n"
                        ".header {\n"
                        "  font-weight: 700 !important;\n"
                        "  font-size: 22px !important;\n"
                        "  color: var(--md-sys-color-on-surface) !important;\n"
                        "}\n"
                    )
                },
            },
            {
                "type": "custom:button-card",
                "template": "flux_glass",
                "show_icon": False,
                "show_name": True,
                "show_label": True,
                "name": nz_datetime_short_js(),
                "label": (
                    "[[[\n"
                    f"  const w = states['{weather_entity}'];\n"
                    "  if (!w) return 'Weather unavailable';\n"
                    "  const t = w.attributes?.temperature;\n"
                    "  const c = (w.state || '').replace(/_/g,' ');\n"
                    "  const hi = w.attributes?.forecast?.[0]?.temperature;\n"
                    "  const lo = w.attributes?.forecast?.[0]?.templow;\n"
                    "  const range = (hi != null && lo != null) ? `${hi}° / ${lo}°` : '';\n"
                    "  return [t != null ? `${t}°C, ${c}` : c, range].filter(Boolean).join(' · ');\n"
                    "]]]"
                ),
                "styles": {
                    "card": [{"min-height": "52px"}, {"padding": "10px 14px"}],
                    "name": [{"font-size": "18px"}, {"font-weight": "700"}, {"justify-self": "start"}],
                    "label": [
                        {"justify-self": "start"},
                        {"color": "var(--md-sys-color-primary)"},
                        {"font-weight": "600"},
                    ],
                    "grid": [{"grid-template-areas": "'n' 'l'"}, {"grid-template-columns": "1fr"}],
                },
                "triggers_update": [weather_entity],
            },
            {
                "type": "custom:mushroom-chips-card",
                "alignment": "start",
                "chips": [
                    {
                        "type": "entity",
                        "entity": weather_entity,
                        "icon": "mdi:weather-partly-cloudy",
                        "content_info": "state",
                    },
                    {
                        "type": "template",
                        "icon": "mdi:thermometer-lines",
                        "content": high_low,
                        "tap_action": {"action": "more-info", "entity": weather_entity},
                        "card_mod": {
                            "style": (
                                "ha-card {\n"
                                "  --chip-background: color-mix(in srgb, "
                                "var(--md-sys-color-on-primary) 25%, transparent) !important;\n"
                                "  --color: var(--md-sys-color-primary) !important;\n"
                                "  border-radius: 24px !important;\n"
                                "  font-weight: 600 !important;\n"
                                "}\n"
                            )
                        },
                    },
                ],
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: transparent !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "}\n"
                        ".chip-container { gap: 8px !important; }\n"
                    )
                },
            },
            {
                "type": "custom:button-card",
                "template": "flux_hero",
                "entity": weather_entity,
                "show_icon": False,
                "show_entity_picture": True,
                "entity_picture": _bitmoji_url(cfg),
                "picture": _bitmoji_url(cfg),
                "name": nz_greeting_js(),
                "label": "Tap for active devices",
                "tap_action": {
                    "action": "navigate",
                    "navigation_path": f"{URL_PREFIX}/active",
                },
                "styles": {
                    "card": [
                        {"min-height": "60px"},
                        {"height": "auto"},
                        {"padding": "10px 14px"},
                    ],
                },
            },
        ],
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
    climate_cards = _climate_tab_cards(cfg, weather_entity)
    toggles_cards = _toggles_tab_cards(cfg)
    scenes_cards = _scenes_tab_cards()

    if use_simple_tabs:
        # Common (toggles) first — default_tab 1 opens it instead of Climate.
        shell = _simple_tabs_shell(
            [
                {
                    "title": "Common",
                    "icon": "mdi:toggle-switch",
                    "cards": [{"type": "vertical-stack", "cards": toggles_cards}],
                },
                {
                    "title": "Climate",
                    "icon": "mdi:thermostat",
                    "cards": [{"type": "vertical-stack", "cards": climate_cards}],
                },
                {
                    "title": "Scenes",
                    "icon": "mdi:palette",
                    "cards": [{"type": "vertical-stack", "cards": scenes_cards}],
                },
            ]
        )
        shell["default_tab"] = 1
        # Do not restore a previous Climate selection across refreshes.
        shell["remember_tab"] = False
        shell["hide_inactive_tab_titles"] = True
        shell["view_layout"] = _area("simple_tab")
        shell["card_mod"] = {
            "style": GLASS_CARD_MOD["style"]
            + "ha-card { padding: 6px !important; min-height: 0; }\n"
        }
        return shell

    return {
        "type": "vertical-stack",
        "view_layout": _area("simple_tab"),
        "cards": [_transparent_title("Common"), *toggles_cards],
    }


def _weather_forecast(weather_entity: str) -> dict:
    return {
        "type": "vertical-stack",
        "view_layout": _area("weather"),
        "cards": [
            _transparent_title("Weather Forecast", size="18px"),
            wrap_glass(
                {
                    "type": "weather-forecast",
                    "entity": weather_entity,
                    "forecast_type": "daily",
                    "show_current": False,
                    "show_forecast": True,
                }
            ),
        ],
    }


# Calendar column spans the full tablet viewport (navbar floats over the bottom).
_CALENDAR_COLUMN_HEIGHT = "calc(100dvh - 16px)"
# Title row ~32px + stack gap — body gets the rest and scrolls inside.
_CALENDAR_CARD_HEIGHT = "calc(100dvh - 48px)"


def _calendar_notification(cfg: dict, *, use_calendar_pro: bool) -> dict:
    """Right-column week calendar — full tablet height; scrolls inside the card."""
    events = build_events_tab_cards(cfg, use_calendar_pro=use_calendar_pro)
    weather = (
        cfg.get("weather")
        or ((cfg.get("weather_panel") or {}).get("weather_entity"))
        or ((cfg.get("overview_tabs") or {}).get("events") or {}).get("weather_entity")
    )
    stack_cards: list[dict] = [_transparent_title("Calendar", size="18px")]

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
                            f"  height: {_CALENDAR_CARD_HEIGHT} !important;\n"
                            "  max-height: 100% !important;\n"
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
        # Full week in both compact + expanded modes (older calendar-card-pro
        # versions blanked when compact_* was removed while expand was default).
        cal["days_to_show"] = 7
        cal["compact_days_to_show"] = 7
        cal["compact_events_to_show"] = 40
        cal["compact_events_complete_days"] = True
        cal["show_empty_days"] = True
        cal["tap_action"] = {"action": "expand"}
        # Keep the widget static — no ticking UI; rare poll + entity-driven updates.
        cal["show_countdown"] = False
        cal["show_progress_bar"] = False
        cal["today_indicator"] = "dot"
        cal["refresh_interval"] = int(
            ((cfg.get("overview_tabs") or {}).get("events") or {}).get("refresh_interval", 360)
        )
        cal["refresh_on_navigate"] = False
        # Native fixed height → full column; scrolls internally.
        cal["height"] = _CALENDAR_CARD_HEIGHT
        cal["max_height"] = _CALENDAR_CARD_HEIGHT
        # Narrow tablet column — slightly smaller date column
        cal["day_font_size"] = "20px"
        cal["weekday_font_size"] = "11px"
        cal["month_font_size"] = "10px"
        if weather and isinstance(cal.get("weather"), dict):
            # Date-only weather (not per-event) — fewer redraws; MetService NZ entity.
            cal["weather"] = {
                "position": "date",
                "date": {
                    "show_conditions": True,
                    "show_high_temp": True,
                    "show_low_temp": False,
                    "icon_size": "14px",
                    "font_size": "12px",
                    "color": "var(--primary-text-color)",
                },
                "entity": weather,
            }
        stack_cards.append(wrap_glass(cal))

    # Full-height column from top padding to bottom of the tablet viewport.
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
                "}\n"
                "ha-card {\n"
                f"  height: {_CALENDAR_COLUMN_HEIGHT} !important;\n"
                f"  max-height: {_CALENDAR_COLUMN_HEIGHT} !important;\n"
                "  min-height: 0 !important;\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  overflow: hidden !important;\n"
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
                    "}\n"
                    "#root {\n"
                    "  display: flex !important;\n"
                    "  flex-direction: column !important;\n"
                    "  height: 100% !important;\n"
                    "  min-height: 0 !important;\n"
                    "  overflow: hidden !important;\n"
                    "}\n"
                    "#root > *:first-child {\n"
                    "  flex: 0 0 auto !important;\n"
                    "}\n"
                    "#root > *:not(:first-child) {\n"
                    "  flex: 1 1 auto !important;\n"
                    "  min-height: 0 !important;\n"
                    "  overflow: hidden !important;\n"
                    "}\n"
                )
            },
        },
    }


def _room_selector() -> dict:
    chips = _category_tab_chips()
    chips.pop("grid_options", None)
    chips["view_layout"] = _area("room_selector")
    return chips


def _rooms_for_category(rooms: list[dict], slug: str) -> list[dict]:
    return [r for r in rooms if (r.get("category") or "default") == slug]


def _room_pair_row(rooms: list[dict]) -> dict:
    tiles = []
    for room in rooms:
        tile = flux_room_tile(room, columns=12)
        tile.pop("grid_options", None)
        tiles.append(tile)
    if not tiles:
        return wrap_glass({"type": "markdown", "content": "No rooms in this category."})
    # Reference tablet home: up to 6 room cards in one landscape row.
    return {
        "type": "grid",
        "columns": min(6, max(2, len(tiles))),
        "square": False,
        "cards": tiles,
    }


def _rooms_band(cfg: dict) -> dict:
    rooms = cfg.get("rooms") or []
    panels: list[dict] = []
    for cat in ROOM_CATEGORIES:
        option = cat["option"]
        slug = cat["slug"]
        category_rooms = _rooms_for_category(rooms, slug)
        if option == "Default":
            conditions = [
                {
                    "condition": "or",
                    "conditions": [
                        {"condition": "state", "entity": ROOMS_TAB_ENTITY, "state": "Default"},
                        {"condition": "state", "entity": ROOMS_TAB_ENTITY, "state": "unknown"},
                        {"condition": "state", "entity": ROOMS_TAB_ENTITY, "state": "unavailable"},
                    ],
                }
            ]
        else:
            conditions = [
                {"condition": "state", "entity": ROOMS_TAB_ENTITY, "state": option},
            ]
        panels.append(
            {
                "type": "conditional",
                "conditions": conditions,
                "card": _room_pair_row(category_rooms),
            }
        )
    return {
        "type": "vertical-stack",
        "view_layout": _area("rooms"),
        "cards": panels,
    }


def build_tablet_overview_view(
    cfg: dict,
    weather_entity: str,
    *,
    climate_section: dict | None = None,
    use_navbar_card: bool = True,
    use_calendar_pro: bool = True,
    use_auto_entities: bool = True,
    use_simple_tabs: bool = True,
) -> dict:
    """Full-bleed 16:9 overview — panel view + layout-card grid."""
    del climate_section, use_auto_entities
    content_cards = [
        _greeting_stack(weather_entity, cfg),
        _simple_tab_panel(cfg, weather_entity, use_simple_tabs=use_simple_tabs),
        _weather_forecast(weather_entity),
        _calendar_notification(cfg, use_calendar_pro=use_calendar_pro),
        _room_selector(),
        _rooms_band(cfg),
        build_tablet_tesla_band(cfg, view_layout=_area("tesla")),
    ]
    layout = tablet_layout_card(
        content_cards,
        overview=True,
        layout={
            # Content rows = max-content (no fr stretch gaps between bands).
            # Tesla tiles absorb leftover height; calendar spans full viewport height.
            "grid-template-columns": "1.05fr 1.25fr 1.05fr 1.15fr",
            "grid-template-rows": "max-content max-content max-content minmax(0, 1fr)",
            "grid-auto-rows": "max-content",
            "align-content": "start",
            "align-items": "start",
            "justify-items": "stretch",
            "grid-gap": "6px",
            "grid-template-areas": (
                '"greeting simple_tab weather calendar_notification"\n'
                '"room_selector simple_tab weather calendar_notification"\n'
                '"rooms rooms rooms calendar_notification"\n'
                '"tesla tesla tesla calendar_notification"'
            ),
        },
    )
    root = tablet_panel_stack(layout, use_navbar_card=use_navbar_card, overview=True)
    return tablet_panel_view(
        title="Overview",
        path="overview",
        icon="mdi:home",
        root_card=root,
        overview=True,
    )

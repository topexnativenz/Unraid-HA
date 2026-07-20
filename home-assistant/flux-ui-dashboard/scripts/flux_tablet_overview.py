"""ElementZoom MD3 tablet overview — full-bleed 16:9 panel + layout-card.

Uses type: panel (one card, full viewport width). Sections views cannot
reliably fill a 1920×1080 landscape canvas.
"""

from __future__ import annotations

from flux_action_builders import garage_action, lock_action, scene_action
from flux_layouts import flux_room_tile
from flux_media_player import build_tablet_music_card
from flux_navbar import URL_PREFIX
from flux_overview_tabs import build_events_tab_cards
from flux_rooms_index import ROOM_CATEGORIES, ROOMS_TAB_ENTITY, _category_tab_chips
from flux_tablet_layout import tablet_layout_card, tablet_panel_stack, tablet_panel_view
from flux_tablet_tesla import build_tablet_tesla_band
from flux_time import nz_datetime_short_js, nz_greeting_js
from md3_templates import GLASS_CARD_MOD, wrap_glass


def _area(name: str) -> dict:
    """Grid area placement. Pack content rows to the top; calendar/cameras/music fill height."""
    if name in ("calendar_notification", "cameras", "music"):
        return {"grid-area": name, "place-self": "stretch stretch"}
    # Greeting / toggles / rooms / tesla — no vertical stretch (avoids huge gaps).
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
                # Extra left/top padding — mushroom titles clip first glyphs at 18px.
                "  padding: 4px 4px 4px 6px !important;\n"
                "  overflow: visible !important;\n"
                "}\n"
                f".header {{ font-size: {size} !important; font-weight: 600 !important; "
                f"line-height: 1.35 !important; overflow: visible !important; "
                f"padding: 2px 0 0 0 !important; letter-spacing: 0 !important; }}\n"
                ".title, .subtitle, .header * {\n"
                "  overflow: visible !important;\n"
                "}\n"
            )
        },
    }


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


def _bitmoji_url(cfg: dict) -> str:
    hero = (cfg.get("context") or {}).get("hero") or {}
    return str(hero.get("bitmoji_default") or "/local/flux-ui/bitmoji/dave.png")


def _greeting_stack(weather_entity: str, cfg: dict) -> dict:
    """Top-left greeting + datetime — no Home / Live overview title."""
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
                        {"min-height": "64px"},
                        {"height": "auto"},
                        {"padding": "10px 14px"},
                    ],
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
                    "card": [{"min-height": "48px"}, {"padding": "10px 14px"}],
                    "name": [{"font-size": "16px"}, {"font-weight": "700"}, {"justify-self": "start"}],
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
    del weather_entity, use_simple_tabs
    toggles_cards = _toggles_tab_cards(cfg)
    return {
        "type": "vertical-stack",
        "view_layout": _area("simple_tab"),
        "cards": [_transparent_title("Gates & Doors", size="18px"), *toggles_cards],
    }


def _weather_forecast_cards(weather_entity: str) -> list[dict]:
    """Compact daily forecast — sits above the calendar in the right column."""
    return [
        _transparent_title("Weather Forecast", size="15px"),
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
    """Sonos multi-player — height locked to the rooms band so cameras stay visible."""
    body = build_tablet_music_card(cfg, use_mediocre=use_mediocre_media)
    return {
        "type": "custom:mod-card",
        "view_layout": {
            "grid-area": "music",
            # Stretch within the spanned rows; never grow those rows past rooms.
            "place-self": "stretch stretch",
        },
        "card_mod": {
            "style": (
                ":host {\n"
                "  display: block !important;\n"
                # Classic grid trick: intrinsic height 0 so music does not expand
                # greeting/room_selector/rooms rows; min-height fills the spanned area.
                "  height: 0 !important;\n"
                "  min-height: 100% !important;\n"
                "  max-height: 100% !important;\n"
                "  overflow: hidden !important;\n"
                "  contain: layout size !important;\n"
                "  touch-action: pan-x !important;\n"
                "  overscroll-behavior: contain !important;\n"
                "  box-sizing: border-box !important;\n"
                "}\n"
                "ha-card {\n"
                "  height: 100% !important;\n"
                "  max-height: 100% !important;\n"
                "  min-height: 0 !important;\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  overflow: hidden !important;\n"
                "  touch-action: pan-x !important;\n"
                "  overscroll-behavior: contain !important;\n"
                "}\n"
            )
        },
        "card": {
            "type": "vertical-stack",
            "cards": [
                _transparent_title("Music", size="15px"),
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
                    "  touch-action: pan-x !important;\n"
                    "}\n"
                    "#root {\n"
                    "  display: flex !important;\n"
                    "  flex-direction: column !important;\n"
                    "  height: 100% !important;\n"
                    "  max-height: 100% !important;\n"
                    "  min-height: 0 !important;\n"
                    "  overflow: hidden !important;\n"
                    "  gap: 4px !important;\n"
                    "  touch-action: pan-x !important;\n"
                    "}\n"
                    "#root > *:first-child {\n"
                    "  flex: 0 0 auto !important;\n"
                    "}\n"
                    "#root > *:not(:first-child) {\n"
                    "  flex: 1 1 auto !important;\n"
                    "  min-height: 0 !important;\n"
                    "  max-height: 100% !important;\n"
                    "  overflow: hidden !important;\n"
                    "  touch-action: pan-x !important;\n"
                    "}\n"
                )
            },
        },
    }


# Calendar column spans the full tablet viewport (weather stacked above calendar).
_CALENDAR_COLUMN_HEIGHT = "calc(100dvh - 16px)"
# Fixed length for calendar-card-pro .content-container (enables in-widget scroll).
# Leaves room for weather title + compact daily forecast + calendar title above.
_CALENDAR_BODY_HEIGHT = "calc(100dvh - 228px)"


def _calendar_notification(
    cfg: dict, weather_entity: str, *, use_calendar_pro: bool
) -> dict:
    """Right column — weather forecast on top, scrollable week calendar below."""
    events = build_events_tab_cards(cfg, use_calendar_pro=use_calendar_pro)
    cal_weather = (
        cfg.get("weather")
        or weather_entity
        or ((cfg.get("weather_panel") or {}).get("weather_entity"))
        or ((cfg.get("overview_tabs") or {}).get("events") or {}).get("weather_entity")
    )
    stack_cards: list[dict] = [
        *_weather_forecast_cards(weather_entity),
        _transparent_title("Calendar", size="18px"),
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
        # Fixed height (not %) — calendar-card-pro scrolls .content-container only
        # when height/max_height resolve to a real length.
        cal["height"] = _CALENDAR_BODY_HEIGHT
        cal["max_height"] = _CALENDAR_BODY_HEIGHT
        # Narrow tablet column — slightly smaller date column
        cal["day_font_size"] = "20px"
        cal["weekday_font_size"] = "11px"
        cal["month_font_size"] = "10px"
        if cal_weather and isinstance(cal.get("weather"), dict):
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
                "entity": cal_weather,
            }
        cal["card_mod"] = _calendar_body_mod()
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
                    f"  min-height: {_CALENDAR_BODY_HEIGHT} !important;\n"
                    f"  height: {_CALENDAR_BODY_HEIGHT} !important;\n"
                    f"  max-height: {_CALENDAR_BODY_HEIGHT} !important;\n"
                    "  overflow: hidden !important;\n"
                    "  display: flex !important;\n"
                    "  flex-direction: column !important;\n"
                    "  touch-action: pan-y !important;\n"
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


def _camera_feed_card(camera: dict) -> dict:
    """Compact single-feed tile for the tablet overview camera row."""
    entity = camera["entity"]
    name = camera.get("name") or entity.split(".", 1)[-1].replace("_", " ").title()
    return wrap_glass(
        {
            "type": "picture-entity",
            "entity": entity,
            "name": name,
            "camera_view": "live",
            "show_name": True,
            "show_state": False,
            "aspect_ratio": "16:9",
            "tap_action": {"action": "more-info", "entity": entity},
            "card_mod": {
                "style": (
                    "ha-card {\n"
                    "  overflow: hidden !important;\n"
                    "  max-height: 100% !important;\n"
                    "  height: 100% !important;\n"
                    "}\n"
                    "hui-image, img, video {\n"
                    "  max-height: 100% !important;\n"
                    "  object-fit: cover !important;\n"
                    "}\n"
                    ".header {\n"
                    "  font-size: 13px !important;\n"
                    "  font-weight: 600 !important;\n"
                    "  padding: 6px 10px !important;\n"
                    "}\n"
                )
            },
        }
    )


def _tablet_overview_cameras(cfg: dict) -> list[dict]:
    """Curated 4-camera row — never auto-discover the whole house."""
    tablet = cfg.get("tablet") or {}
    curated = list(tablet.get("overview_cameras") or [])
    if curated:
        return curated[:4]
    cameras_cfg = cfg.get("cameras_config") or {}
    manual = list(cameras_cfg.get("cameras") or [])
    return manual[:4]


def _cameras_band(cfg: dict, *, use_auto_entities: bool) -> dict:
    del use_auto_entities  # Tablet overview is always curated — never dump all cameras.
    cameras = _tablet_overview_cameras(cfg)
    fill_mod = {
        "style": (
            ":host, ha-card {\n"
            "  min-height: 0 !important;\n"
            "  max-height: 100% !important;\n"
            "  overflow: hidden !important;\n"
            "  box-sizing: border-box !important;\n"
            "  z-index: 2 !important;\n"
            "}\n"
            "#root {\n"
            "  min-height: 0 !important;\n"
            "  max-height: 100% !important;\n"
            "  gap: 8px !important;\n"
            "}\n"
            "#root > * {\n"
            "  min-height: 0 !important;\n"
            "  max-height: 100% !important;\n"
            "}\n"
        )
    }
    if cameras:
        feeds = [_camera_feed_card(cam) for cam in cameras[:4]]
        return {
            "type": "grid",
            "columns": 4,
            "square": False,
            "view_layout": {
                "grid-area": "cameras",
                "place-self": "stretch stretch",
            },
            "cards": feeds,
            "card_mod": fill_mod,
        }

    return {
        "type": "vertical-stack",
        "view_layout": _area("cameras"),
        "cards": [
            wrap_glass(
                {
                    "type": "markdown",
                    "content": (
                        "Configure the 4 tablet cameras in `cameras.yaml` "
                        "or `entities.yaml` → `tablet.overview_cameras`."
                    ),
                }
            )
        ],
        "card_mod": fill_mod,
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
        _room_selector(),
        _rooms_band(cfg),
        _cameras_band(cfg, use_auto_entities=use_auto_entities),
        build_tablet_tesla_band(cfg, view_layout=_area("tesla")),
    ]
    layout = tablet_layout_card(
        content_cards,
        overview=True,
        layout={
            # Music spans greeting→rooms but is height-capped (cannot grow those rows).
            # Cameras get a guaranteed band above Tesla so they are never covered.
            "grid-template-columns": "1.05fr 1.25fr 1.05fr 1.15fr",
            "grid-template-rows": (
                "max-content max-content max-content minmax(150px, 1fr) max-content"
            ),
            "grid-auto-rows": "max-content",
            "align-content": "stretch",
            "align-items": "stretch",
            "justify-items": "stretch",
            "grid-gap": "6px",
            "grid-template-areas": (
                '"greeting simple_tab music calendar_notification"\n'
                '"room_selector simple_tab music calendar_notification"\n'
                '"rooms rooms music calendar_notification"\n'
                '"cameras cameras cameras calendar_notification"\n'
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

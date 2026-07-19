"""ElementZoom MD3 tablet overview — author framework layout.

Reference:
  https://github.com/ElementZoom/Material-Design-3-Dynamic-Tablet-Dashboard

Uses sections + custom:layout-card (not view-type custom:grid-layout).
View-level grid-layout often renders blank with only a fixed navbar-card
visible on some HA / layout-card versions — layout-card-as-card is reliable.
"""

from __future__ import annotations

from flux_action_builders import garage_action, lock_action, scene_action
from flux_layouts import flux_room_tile
from flux_navbar import URL_PREFIX, navbar_section
from flux_overview_tabs import _simple_tabs_shell, build_events_tab_cards
from flux_rooms_index import ROOM_CATEGORIES, ROOMS_TAB_ENTITY, _category_tab_chips
from flux_tablet_layout import TABLET_MAX_COLUMNS, tablet_section
from md3_templates import GLASS_CARD_MOD, TABLET_VIEW_CARD_MOD, wrap_glass


def _area(name: str) -> dict:
    return {"grid-area": name}


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


def _greeting_stack(weather_entity: str) -> dict:
    """Author greeting column — date/time, weather pill, personalized hello."""
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
                # Plain text — mushroom-title does not evaluate Jinja.
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
                "name": (
                    "[[[ return new Date().toLocaleString([], {"
                    "weekday:'short', month:'short', day:'numeric',"
                    "hour:'numeric', minute:'2-digit'}); ]]]"
                ),
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
                    "card": [
                        {"min-height": "64px"},
                        {"padding": "12px 16px"},
                    ],
                    "name": [{"font-size": "18px"}, {"font-weight": "700"}, {"justify-self": "start"}],
                    "label": [
                        {"justify-self": "start"},
                        {"color": "var(--md-sys-color-primary)"},
                        {"font-weight": "600"},
                    ],
                    "grid": [{"grid-template-areas": "'n' 'l'"}, {"grid-template-columns": "1fr"}],
                },
                "triggers_update": "all",
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
                "name": (
                    "[[[\n"
                    "  const h = new Date().getHours();\n"
                    "  let g = 'Morning';\n"
                    "  if (h >= 22 || h < 5) g = 'Night';\n"
                    "  else if (h >= 18) g = 'Evening';\n"
                    "  else if (h >= 12) g = 'Afternoon';\n"
                    "  return `${g}, ${user.name}!`;\n"
                    "]]]"
                ),
                "label": "Tap for active devices",
                "tap_action": {
                    "action": "navigate",
                    "navigation_path": f"{URL_PREFIX}/active",
                },
                "styles": {
                    "card": [
                        {"min-height": "72px"},
                        {"height": "auto"},
                        {"padding": "12px 16px"},
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
        card = lock_action(item["entity"], item["name"], columns=12)
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
            wrap_glass(
                {
                    "type": "markdown",
                    "content": "No quick toggles configured in `entities.yaml`.",
                }
            )
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
        },
        wrap_glass(
            {
                "type": "markdown",
                "content": (
                    "**Hue / scene presets** live on the Scenes page — "
                    "same ElementZoom Preset grid as the tablet reference."
                ),
            }
        ),
    ]


def _simple_tab_panel(cfg: dict, weather_entity: str, *, use_simple_tabs: bool) -> dict:
    climate_cards = _climate_tab_cards(cfg, weather_entity)
    toggles_cards = _toggles_tab_cards(cfg)
    scenes_cards = _scenes_tab_cards()

    if use_simple_tabs:
        shell = _simple_tabs_shell(
            [
                {
                    "title": "Climate",
                    "icon": "mdi:thermostat",
                    "cards": [{"type": "vertical-stack", "cards": climate_cards}],
                },
                {
                    "title": "Toggles",
                    "icon": "mdi:toggle-switch",
                    "cards": [{"type": "vertical-stack", "cards": toggles_cards}],
                },
                {
                    "title": "Scenes",
                    "icon": "mdi:palette",
                    "cards": [{"type": "vertical-stack", "cards": scenes_cards}],
                },
            ]
        )
        shell["hide_inactive_tab_titles"] = True
        shell["view_layout"] = _area("simple_tab")
        shell["card_mod"] = {
            "style": GLASS_CARD_MOD["style"]
            + (
                "ha-card {\n"
                "  padding: 8px !important;\n"
                "  min-height: 260px;\n"
                "}\n"
            )
        }
        return shell

    return {
        "type": "vertical-stack",
        "view_layout": _area("simple_tab"),
        "cards": [_transparent_title("Climate"), *climate_cards],
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


def _calendar_notification(cfg: dict, *, use_calendar_pro: bool) -> dict:
    events = build_events_tab_cards(cfg, use_calendar_pro=use_calendar_pro)
    for card in events:
        if card.get("type") == "custom:calendar-card-pro":
            card["days_to_show"] = 5
            card["compact_events_to_show"] = 8
    return {
        "type": "vertical-stack",
        "view_layout": _area("calendar_notification"),
        "cards": [
            _transparent_title("Calendar", size="18px"),
            wrap_glass({"type": "vertical-stack", "cards": events}),
        ],
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
    return {
        "type": "grid",
        "columns": min(3, len(tiles)),
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
    entity = camera["entity"]
    name = camera.get("name") or entity.split(".", 1)[-1].replace("_", " ").title()
    lights = camera.get("lights") or camera.get("entities") or []
    light_ids: list[str] = []
    for item in lights:
        if isinstance(item, str):
            light_ids.append(item)
        elif isinstance(item, dict) and item.get("entity"):
            light_ids.append(item["entity"])

    chips: list[dict] = []
    for lid in light_ids[:3]:
        chips.append(
            {
                "type": "template",
                "entity": lid,
                "icon": "mdi:lightbulb",
                "content": (
                    "{{ state_attr('" + lid + "', 'friendly_name') or '"
                    + lid.split(".")[-1]
                    + "' }}"
                ),
                "tap_action": {"action": "toggle", "entity": lid},
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  --chip-background: {% if is_state('" + lid + "', 'on') %}"
                        "var(--md-sys-color-primary){% else %}"
                        "color-mix(in srgb, var(--md-sys-color-on-primary) 50%, transparent)"
                        "{% endif %} !important;\n"
                        "  --color: {% if is_state('" + lid + "', 'on') %}"
                        "var(--md-sys-color-on-primary){% else %}"
                        "var(--md-sys-color-primary){% endif %} !important;\n"
                        "}\n"
                    )
                },
            }
        )

    stack: list[dict] = [
        {
            "type": "custom:mushroom-title-card",
            "title": f"{name} ›",
            "card_mod": {
                "style": (
                    "ha-card {\n"
                    "  background: transparent !important;\n"
                    "  box-shadow: none !important;\n"
                    "  border: none !important;\n"
                    "  padding: 0 0 2px 0 !important;\n"
                    "}\n"
                    ".header { font-size: 15px !important; font-weight: 600 !important; }\n"
                )
            },
        },
        wrap_glass(
            {
                "type": "picture-glance",
                "title": "",
                "entities": [],
                "camera_image": entity,
                "camera_view": "live",
                "show_state": False,
                "tap_action": {"action": "more-info", "entity": entity},
            }
        ),
    ]
    if chips:
        stack.append(
            {
                "type": "custom:mushroom-chips-card",
                "alignment": "start",
                "chips": chips,
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: transparent !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "  margin-top: 4px !important;\n"
                        "}\n"
                    )
                },
            }
        )
    return {"type": "vertical-stack", "cards": stack}


def _cameras_band(cfg: dict, *, use_auto_entities: bool) -> dict:
    cameras_cfg = cfg.get("cameras_config") or {}
    manual = list(cameras_cfg.get("cameras") or [])
    if manual:
        feeds = [_camera_feed_card(cam) for cam in manual[:4]]
        return {
            "type": "grid",
            "columns": min(4, len(feeds)),
            "square": False,
            "view_layout": _area("cameras"),
            "cards": feeds,
        }

    if use_auto_entities and cameras_cfg.get("auto_discover", True):
        # picture-entity works with auto-entities' injected entity; picture-glance
        # needs camera_image and shows "Configuration error" otherwise.
        return {
            "type": "custom:auto-entities",
            "view_layout": _area("cameras"),
            "card": {"type": "grid", "columns": 4, "square": False},
            "card_param": "cards",
            "max_entities": 4,
            "filter": {
                "include": [
                    {
                        "domain": "camera",
                        "options": {
                            "type": "picture-entity",
                            "camera_view": "live",
                            "show_name": True,
                            "show_state": False,
                            "tap_action": {"action": "more-info"},
                        },
                    }
                ]
            },
            "sort": {"method": "friendly_name"},
            "card_mod": {"style": GLASS_CARD_MOD["style"]},
        }

    return {
        "type": "vertical-stack",
        "view_layout": _area("cameras"),
        "cards": [
            wrap_glass(
                {
                    "type": "markdown",
                    "content": (
                        "Add camera feeds to `cameras.yaml` "
                        "(optional `lights:` chips — ElementZoom camera_generic_with_chips)."
                    ),
                }
            )
        ],
    }


def _layout_card(cards: list[dict]) -> dict:
    """ElementZoom grid as a layout-card (reliable) rather than a view type."""
    return {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "layout": {
            "margin": "0",
            "padding": "4px 4px 0 4px",
            "grid-gap": "10px",
            # fr units avoid 0-width columns when parent width is unsettled.
            "grid-template-columns": "1fr 1.2fr 1fr 1fr",
            "grid-template-rows": "auto auto auto auto",
            "grid-template-areas": (
                '"greeting simple_tab weather calendar_notification"\n'
                '"room_selector simple_tab weather calendar_notification"\n'
                '"rooms rooms rooms calendar_notification"\n'
                '"cameras cameras cameras calendar_notification"'
            ),
        },
        "cards": cards,
        "grid_options": {"columns": 12},
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
    """Landscape overview — layout-card grid + separate bottom navbar section."""
    del climate_section
    content_cards = [
        _greeting_stack(weather_entity),
        _simple_tab_panel(cfg, weather_entity, use_simple_tabs=use_simple_tabs),
        _weather_forecast(weather_entity),
        _calendar_notification(cfg, use_calendar_pro=use_calendar_pro),
        _room_selector(),
        _rooms_band(cfg),
        _cameras_band(cfg, use_auto_entities=use_auto_entities),
    ]
    return {
        "title": "Overview",
        "icon": "mdi:home",
        "path": "overview",
        "type": "sections",
        "max_columns": TABLET_MAX_COLUMNS,
        "dense_section_placement": True,
        "theme": "flux-ui-md3",
        "card_mod": TABLET_VIEW_CARD_MOD,
        "sections": [
            tablet_section([_layout_card(content_cards)]),
            tablet_section(navbar_section(use_navbar_card=use_navbar_card)["cards"]),
        ],
    }

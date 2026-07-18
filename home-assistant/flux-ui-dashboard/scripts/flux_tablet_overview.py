"""ElementZoom-style 16:9 tablet overview — landscape grid, not stretched mobile.

Reference layout (Material Design 3 Dynamic Tablet Dashboard):
  greeting | climate | weather forecast | calendar
  rooms row (full width)
  cameras row (full width)
  bottom navbar (same Flux routes as mobile)
"""

from __future__ import annotations

from flux_layouts import flux_room_tile
from flux_navbar import URL_PREFIX, build_navbar_card
from flux_overview_tabs import build_events_tab_cards
from md3_templates import GLASS_CARD_MOD, TABLET_VIEW_CARD_MOD, wrap_glass


def _area(name: str) -> dict:
    return {"grid-area": name}


def _glass_mod() -> dict:
    return {"style": GLASS_CARD_MOD["style"]}


def _datetime_card(weather_entity: str) -> dict:
    """Top-left: weekday/date/time + current conditions."""
    return {
        "type": "vertical-stack",
        "view_layout": _area("greeting"),
        "cards": [
            {
                "type": "custom:mushroom-title-card",
                "alignment": "start",
                "title": "{{ now().strftime('%a %b %-d · %-I:%M %p') }}",
                "subtitle": (
                    "{% set t = state_attr('" + weather_entity + "', 'temperature') %}"
                    "{% set c = states('" + weather_entity + "') | title %}"
                    "{% set hi = state_attr('" + weather_entity + "', 'forecast') %}"
                    "{{ t }}° · {{ c }}"
                ),
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: transparent !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "  animation: fluxFadeInDown 0.8s ease-out;\n"
                        "}\n"
                        ".header {\n"
                        "  font-weight: 700 !important;\n"
                        "  font-size: 22px !important;\n"
                        "  color: var(--md-sys-color-on-surface) !important;\n"
                        "}\n"
                        ".subheader {\n"
                        "  color: var(--md-sys-color-primary) !important;\n"
                        "  font-weight: 600 !important;\n"
                        "  font-size: 14px !important;\n"
                        "}\n"
                        "@keyframes fluxFadeInDown {\n"
                        "  from { opacity: 0; transform: translateY(-8px); }\n"
                        "  to { opacity: 1; transform: translateY(0); }\n"
                        "}\n"
                    )
                },
            },
            {
                "type": "custom:button-card",
                "template": "flux_hero",
                "entity": weather_entity,
                "icon": (
                    "[[[ return entity.attributes?.condition "
                    "? `weather-${entity.attributes.condition}` "
                    ": 'mdi:weather-partly-cloudy'; ]]]"
                ),
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
                "label": (
                    "[[[\n"
                    "  const temp = entity.attributes?.temperature;\n"
                    "  const cond = entity.attributes?.friendly_name "
                    "|| entity.attributes?.condition || '';\n"
                    "  return temp != null ? `${cond} · ${temp}°` : String(cond);\n"
                    "]]]"
                ),
                "styles": {
                    "card": [
                        {"min-height": "88px"},
                        {"height": "auto"},
                    ],
                },
            },
        ],
    }


def _mode_pills() -> dict:
    """Center-top segmented control — Climate active (ElementZoom simple_tab header)."""
    prefix = URL_PREFIX
    chips = [
        ("Climate", "mdi:thermostat", f"{prefix}/overview", True),
        ("Rooms", "mdi:sofa-outline", f"{prefix}/rooms", False),
        ("Lights", "mdi:lightbulb-group-outline", f"{prefix}/lights", False),
        ("Camera", "mdi:cctv", f"{prefix}/cameras", False),
    ]
    chip_cards: list[dict] = []
    for label, icon, path, active in chips:
        bg = (
            "var(--md-sys-color-primary)"
            if active
            else "color-mix(in srgb, var(--md-sys-color-surface-container) 55%, transparent)"
        )
        fg = (
            "var(--md-sys-color-on-primary)"
            if active
            else "var(--md-sys-color-on-surface-variant)"
        )
        chip_cards.append(
            {
                "type": "template",
                "icon": icon,
                "content": label,
                "icon_color": fg,
                "tap_action": {"action": "navigate", "navigation_path": path},
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        f"  --chip-background: {bg} !important;\n"
                        f"  --color: {fg} !important;\n"
                        "  border-radius: 28px !important;\n"
                        "  border: 1px solid color-mix(in srgb, "
                        "var(--md-sys-color-outline-variant) 35%, transparent) !important;\n"
                        "  min-height: 40px !important;\n"
                        "  justify-content: center !important;\n"
                        "}\n"
                    )
                },
            }
        )
    return {
        "type": "custom:mushroom-chips-card",
        "alignment": "center",
        "chips": chip_cards,
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  margin: 0 0 8px 0 !important;\n"
                "}\n"
                ".chip-container { gap: 8px !important; justify-content: center !important; }\n"
            )
        },
    }


def _climate_panel(cfg: dict, weather_entity: str, climate_section: dict | None) -> dict:
    """Wide climate card: mode pills + temps + history graph + optional imported climate."""
    tablet = cfg.get("tablet") or {}
    indoor = tablet.get("indoor_temperature")
    outdoor = tablet.get("outdoor_temperature") or weather_entity
    climate_entity = tablet.get("climate_entity")

    inner: list[dict] = [_mode_pills()]

    temp_row: list[dict] = []
    if indoor:
        temp_row.append(
            wrap_glass(
                {
                    "type": "custom:mushroom-entity-card",
                    "entity": indoor,
                    "name": "Indoor",
                    "icon": "mdi:home-thermometer",
                    "layout": "horizontal",
                    "fill_container": True,
                }
            )
        )
    temp_row.append(
        wrap_glass(
            {
                "type": "custom:mushroom-entity-card",
                "entity": outdoor,
                "name": "Outdoor",
                "icon": "mdi:thermometer",
                "layout": "horizontal",
                "fill_container": True,
            }
        )
    )
    if climate_entity:
        temp_row.append(
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

    inner.append({"type": "grid", "columns": min(3, len(temp_row)), "square": False, "cards": temp_row})

    graph_entities = [e for e in (indoor, outdoor) if e]
    if not graph_entities:
        graph_entities = [weather_entity]
    inner.append(
        wrap_glass(
            {
                "type": "history-graph",
                "hours_to_show": 24,
                "entities": [{"entity": e} for e in graph_entities],
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: transparent !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "  min-height: 160px;\n"
                        "}\n"
                    )
                },
            }
        )
    )

    if climate_section and climate_section.get("cards"):
        # Drop titles from imported Mobile Home climate — panel already has header.
        for card in climate_section["cards"]:
            if card.get("type") == "custom:mushroom-title-card":
                continue
            if card.get("type") == "grid":
                continue
            inner.append(card)

    return {
        "type": "vertical-stack",
        "view_layout": _area("climate"),
        "cards": [
            wrap_glass(
                {
                    "type": "vertical-stack",
                    "cards": inner,
                }
            )
        ],
    }


def _weather_forecast_card(weather_entity: str) -> dict:
    return {
        "type": "vertical-stack",
        "view_layout": _area("forecast"),
        "cards": [
            {
                "type": "custom:mushroom-title-card",
                "title": "Weather Forecast",
                "alignment": "start",
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: transparent !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "  padding-bottom: 0 !important;\n"
                        "}\n"
                        ".header { font-size: 16px !important; font-weight: 600 !important; }\n"
                    )
                },
            },
            wrap_glass(
                {
                    "type": "weather-forecast",
                    "entity": weather_entity,
                    "forecast_type": "daily",
                    "show_current": True,
                    "show_forecast": True,
                }
            ),
        ],
    }


def _calendar_rail(cfg: dict, *, use_calendar_pro: bool) -> dict:
    events = build_events_tab_cards(cfg, use_calendar_pro=use_calendar_pro)
    # Compact for right rail on tablet.
    for card in events:
        if card.get("type") == "custom:calendar-card-pro":
            card["days_to_show"] = 5
            card["compact_events_to_show"] = 6
    return {
        "type": "vertical-stack",
        "view_layout": _area("calendar"),
        "cards": [
            {
                "type": "custom:mushroom-title-card",
                "title": "Calendar",
                "alignment": "start",
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: transparent !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "}\n"
                        ".header { font-size: 16px !important; font-weight: 600 !important; }\n"
                    )
                },
            },
            wrap_glass({"type": "vertical-stack", "cards": events}),
        ],
    }


def _rooms_row(cfg: dict) -> dict:
    rooms = cfg.get("rooms") or []
    # Prefer default-category rooms first (Garage, Living, Master…), then others.
    ordered = sorted(
        rooms,
        key=lambda r: (0 if (r.get("category") or "default") == "default" else 1, r.get("name", "")),
    )
    tiles = []
    for room in ordered[:6]:
        tile = flux_room_tile(room, columns=12)
        tile.pop("grid_options", None)
        tiles.append(tile)
    cols = max(2, min(6, len(tiles) or 1))
    return {
        "type": "grid",
        "columns": cols,
        "square": False,
        "view_layout": _area("rooms"),
        "cards": tiles
        or [
            wrap_glass(
                {
                    "type": "markdown",
                    "content": "No rooms configured in `rooms.yaml`.",
                }
            )
        ],
    }


def _camera_with_lights(camera: dict) -> dict:
    """picture-glance with optional light chips under the feed."""
    entity = camera["entity"]
    name = camera.get("name") or entity.split(".", 1)[-1].replace("_", " ").title()
    light_entities: list[dict] = []
    for item in camera.get("lights") or camera.get("entities") or []:
        if isinstance(item, str):
            light_entities.append({"entity": item})
        elif isinstance(item, dict) and item.get("entity"):
            light_entities.append({"entity": item["entity"]})

    return wrap_glass(
        {
            "type": "picture-glance",
            "title": name,
            "entities": light_entities,
            "camera_image": entity,
            "camera_view": "live",
            "show_state": False,
            "tap_action": {"action": "more-info"},
        }
    )


def _cameras_row(cfg: dict, *, use_auto_entities: bool) -> dict:
    cameras_cfg = cfg.get("cameras_config") or {}
    manual = list(cameras_cfg.get("cameras") or [])
    cards: list[dict] = []
    if manual:
        for cam in manual[:4]:
            cards.append(_camera_with_lights(cam))
    elif use_auto_entities and cameras_cfg.get("auto_discover", True):
        return {
            "type": "custom:auto-entities",
            "view_layout": _area("cameras"),
            "card": {"type": "grid", "columns": 4, "square": False},
            "card_param": "cards",
            "filter": {
                "include": [
                    {
                        "domain": "camera",
                        "options": {
                            "type": "picture-glance",
                            "entities": [],
                            "camera_view": "live",
                            "show_state": False,
                            "tap_action": {"action": "more-info"},
                        },
                    }
                ]
            },
            "sort": {"method": "friendly_name"},
            "max_entities": 4,
            "card_mod": _glass_mod(),
        }
    else:
        cards.append(
            wrap_glass(
                {
                    "type": "markdown",
                    "content": (
                        "No cameras configured.\n\n"
                        "Add feeds to `cameras.yaml` (optional `lights:` chips per camera)."
                    ),
                }
            )
        )

    cols = max(1, min(4, len(cards)))
    return {
        "type": "grid",
        "columns": cols,
        "square": False,
        "view_layout": _area("cameras"),
        "cards": cards,
    }


def _navbar_card(*, use_navbar_card: bool) -> dict:
    """Same floating bottom nav as mobile — Home / Rooms / Scenes / Camera / More."""
    nav = build_navbar_card(use_navbar_card=use_navbar_card)
    nav["view_layout"] = _area("navbar")
    return nav


def build_tablet_overview_view(
    cfg: dict,
    weather_entity: str,
    *,
    climate_section: dict | None = None,
    use_navbar_card: bool = True,
    use_calendar_pro: bool = True,
    use_auto_entities: bool = True,
) -> dict:
    """Full landscape overview view (custom:grid-layout)."""
    return {
        "title": "Overview",
        "icon": "mdi:home",
        "path": "overview",
        "type": "custom:grid-layout",
        "theme": "flux-ui-md3",
        "card_mod": TABLET_VIEW_CARD_MOD,
        "layout": {
            "margin": "4px 12px 0 12px",
            "grid-gap": "12px",
            "grid-template-columns": "22% 34% 22% 22%",
            "grid-template-rows": "auto auto auto auto",
            "grid-template-areas": (
                '"greeting climate forecast calendar"\n'
                '"greeting climate calendar calendar"\n'
                '"rooms rooms rooms rooms"\n'
                '"cameras cameras cameras cameras"\n'
                '"navbar navbar navbar navbar"'
            ),
        },
        "cards": [
            _datetime_card(weather_entity),
            _climate_panel(cfg, weather_entity, climate_section),
            _weather_forecast_card(weather_entity),
            _calendar_rail(cfg, use_calendar_pro=use_calendar_pro),
            _rooms_row(cfg),
            _cameras_row(cfg, use_auto_entities=use_auto_entities),
            _navbar_card(use_navbar_card=use_navbar_card),
        ],
    }

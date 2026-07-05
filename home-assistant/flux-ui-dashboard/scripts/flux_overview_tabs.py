"""Overview Home / Events / Active filter tabs (ElementZoom Flux UI pattern).

Reference implementation:
  https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard
  dashboard/mobile/views/01-overview.yaml — custom:simple-tabs (Home, Events, Active)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from md3_templates import wrap_glass

GARAGE_DIR = Path(__file__).resolve().parents[2] / "garage-doors"
sys.path.insert(0, str(GARAGE_DIR))

from garage_ui_helpers import jinja_door_open_expr  # noqa: E402
from phase3_builders import build_active_lights_section, build_open_garage_section

ELEMENTZOOM_REF = "https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard"


def _tabs_cfg(cfg: dict) -> dict:
    return cfg.get("overview_tabs") or cfg.get("context", {}).get("overview_tabs") or {}


def tabs_enabled(cfg: dict) -> bool:
    return bool(_tabs_cfg(cfg).get("enabled", True))


def _active_tab_visibility_jinja(cfg: dict) -> str:
    """ElementZoom Active tab — visible when anything is on/open."""
    parts = ["(states.light | selectattr('state', 'eq', 'on') | list | count) > 0"]
    for door in cfg.get("quick_actions", {}).get("garage", []):
        parts.append(jinja_door_open_expr(door["sensor"], invert=door.get("invert", False)))
    for group in _tabs_cfg(cfg).get("active", {}).get("groups", []):
        entity = group.get("entity")
        state = group.get("state", "on")
        if entity:
            parts.append(f"is_state('{entity}', '{state}')")
    return "{{ " + " or ".join(parts) + " }}"


def _simple_tabs_shell(tabs: list[dict]) -> dict:
    """MD3 pill tabs — matches ElementZoom simple-tabs styling."""
    return {
        "type": "custom:simple-tabs",
        "pre-load": False,
        "active-background": "var(--md-sys-color-primary)",
        "active-text-color": "var(--md-sys-color-on-primary)",
        "text-color": "var(--primary-text-color)",
        "haptic_feedback": True,
        "enable_swipe": True,
        "hide_inactive_tab_titles": False,
        "tabs": tabs,
    }


def build_events_tab_cards(cfg: dict, *, use_calendar_pro: bool) -> list[dict]:
    events = _tabs_cfg(cfg).get("events", {})
    calendars = events.get("calendars") or [{"entity": "calendar.home", "accent_color": "#B388FF"}]
    weather = events.get("weather_entity") or cfg.get("weather", "weather.forecast_home")

    if use_calendar_pro:
        return [
            {
                "type": "custom:calendar-card-pro",
                "entities": [
                    {"entity": c["entity"], "accent_color": c.get("accent_color", "#B388FF")}
                    for c in calendars
                ],
                "days_to_show": events.get("days_to_show", 10),
                "compact_events_to_show": events.get("compact_events_to_show", 10),
                "background_color": "transparent",
                "vertical_line_width": "5px",
                "event_spacing": 6,
                "first_day_of_week": events.get("first_day_of_week", "monday"),
                "show_week_numbers": "iso",
                "week_number_color": "var(--md-sys-color-on-primary)",
                "week_number_background_color": "var(--md-sys-color-primary)",
                "month_separator_width": "1px",
                "month_separator_color": "var(--md-sys-color-primary)",
                "today_indicator": "pulse",
                "today_indicator_position": "10% 50%",
                "today_indicator_color": "var(--md-sys-color-primary)",
                "weekday_font_size": 12,
                "month_font_size": 10,
                "show_countdown": events.get("show_countdown", True),
                "show_progress_bar": events.get("show_progress_bar", True),
                "progress_bar_color": "var(--md-sys-color-primary)",
                "weather": {
                    "position": "event",
                    "date": {
                        "show_conditions": True,
                        "show_high_temp": True,
                        "show_low_temp": False,
                        "icon_size": "14px",
                        "font_size": "12px",
                        "color": "var(--primary-text-color)",
                    },
                    "event": {
                        "show_conditions": True,
                        "show_temp": True,
                        "icon_size": "14px",
                        "font_size": "12px",
                        "color": "var(--primary-text-color)",
                    },
                    "entity": weather,
                },
                "tap_action": {"action": "expand"},
            }
        ]

    # Fallback when calendar-card-pro is not installed
    fallback: list[dict] = [
        {
            "type": "custom:mushroom-title-card",
            "title": "Events",
            "subtitle": "Install calendar-card-pro via HACS for ElementZoom timeline view",
        }
    ]
    for cal in calendars:
        fallback.append(
            {
                "type": "custom:mushroom-entity-card",
                "entity": cal["entity"],
                "name": cal.get("name") or cal["entity"].replace("calendar.", "").replace("_", " ").title(),
                "layout": "horizontal",
                "fill_container": True,
                "tap_action": {"action": "more-info"},
            }
        )
    return [{"type": "grid", "cards": fallback}]


def build_active_tab_cards(cfg: dict, *, use_auto_entities: bool) -> list[dict]:
    """Active tab content — lights on, doors open (ElementZoom Active tab)."""
    cards: list[dict] = []
    if use_auto_entities:
        cards.append(build_active_lights_section(cfg))
    open_garage = build_open_garage_section(cfg)
    if open_garage:
        cards.append(open_garage)

    active_cfg = _tabs_cfg(cfg).get("active", {})
    for group in active_cfg.get("groups", []):
        entity = group.get("entity")
        if not entity:
            continue
        cards.append(_active_group_section(group))

    return cards


def _active_group_section(group: dict) -> dict:
    """Optional active category (fans, switches, etc.) — ElementZoom count_active pattern."""
    from flux_layouts import flux_light_auto_entities_options

    entity = group["entity"]
    state = group.get("state", "on")
    title = group.get("title", entity.split(".")[-1].replace("_", " ").title())
    icon = group.get("icon", "mdi:flash")
    is_light = entity.startswith("light.")

    options: dict[str, Any]
    if is_light:
        options = flux_light_auto_entities_options(columns=6)
    else:
        options = {
            "type": "custom:button-card",
            "template": "flux_action",
            "tap_action": {"action": "toggle"},
            "grid_options": {"columns": 6},
        }

    auto_card: dict = {
        "type": "custom:auto-entities",
        "card": {"type": "grid", "square": False, "columns": 2},
        "card_param": "cards",
        "show_empty": False,
        "filter": {
            "include": [{"group": entity, "state": state, "options": options}],
        },
        "sort": {"method": "friendly_name"},
    }

    from phase3_builders import _title

    return {
        "type": "grid",
        "cards": [
            _title(title, "Currently active"),
            wrap_glass({**auto_card, "grid_options": {"columns": 12}}),
        ],
    }


def build_overview_tabs_section(
    cfg: dict,
    *,
    home_tab_cards: list[dict],
    use_auto_entities: bool,
    use_calendar_pro: bool,
) -> dict:
    """Wrap overview body in ElementZoom Home / Events / Active simple-tabs."""
    tabs: list[dict] = [
        {
            "title": "Home",
            "icon": "mdi:home",
            "cards": home_tab_cards,
        },
        {
            "title": "Events",
            "icon": "mdi:calendar",
            "cards": build_events_tab_cards(cfg, use_calendar_pro=use_calendar_pro),
        },
    ]

    active_cards = build_active_tab_cards(cfg, use_auto_entities=use_auto_entities)
    if active_cards:
        tabs.append(
            {
                "title": "Active",
                "icon": "mdi:play-circle",
                "conditions": [{"template": _active_tab_visibility_jinja(cfg)}],
                "cards": active_cards,
            }
        )

    return {
        "type": "grid",
        "cards": [
            wrap_glass(
                {
                    **_simple_tabs_shell(tabs),
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }

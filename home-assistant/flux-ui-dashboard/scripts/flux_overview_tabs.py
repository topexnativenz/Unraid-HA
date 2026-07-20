"""Overview Home / Events / Active filter tabs (ElementZoom Flux UI pattern).

Reference: https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard
  dashboard/mobile/views/01-overview.yaml

Uses a full-width 3-column tab bar (native engine) so pills span the screen edge-to-edge.
Optional engine: simple-tabs (HACS) for swipe — see overview_tabs.yaml.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from flux_action_builders import garage_action, lock_action, scene_action
from flux_tab_layout import (
    grid_to_vertical_stack,
    strip_grid_options,
    tab_panel_stack,
    tab_section_from_grid,
    tab_two_column_grid,
)
from md3_templates import wrap_title

GARAGE_DIR = Path(__file__).resolve().parents[2] / "garage-doors"
sys.path.insert(0, str(GARAGE_DIR))

from garage_ui_helpers import jinja_door_open_expr  # noqa: E402
from phase3_builders import build_active_lights_section, build_open_garage_section

ELEMENTZOOM_REF = "https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard"
OVERVIEW_TAB_ENTITY = "input_select.flux_ui_overview_tab"
FLUX_UI_TAB_LAYOUT = "native-v2"


def _tabs_cfg(cfg: dict) -> dict:
    return cfg.get("overview_tabs") or cfg.get("context", {}).get("overview_tabs") or {}


def tabs_enabled(cfg: dict) -> bool:
    return bool(_tabs_cfg(cfg).get("enabled", True))


def tab_engine(cfg: dict) -> str:
    return _tabs_cfg(cfg).get("engine", "native")


def _active_tab_visibility_jinja(cfg: dict) -> str:
    parts = ["(states.light | selectattr('state', 'eq', 'on') | list | count) > 0"]
    for door in cfg.get("quick_actions", {}).get("garage", []):
        parts.append(jinja_door_open_expr(door["sensor"], invert=door.get("invert", False)))
    for group in _tabs_cfg(cfg).get("active", {}).get("groups", []):
        entity = group.get("entity")
        state = group.get("state", "on")
        if entity:
            parts.append(f"is_state('{entity}', '{state}')")
    return "{{ " + " or ".join(parts) + " }}"


def _tab_is_active(label: str) -> dict:
    """Template condition — defaults to Home when tab helper entity is missing."""
    entity = OVERVIEW_TAB_ENTITY
    if label == "Home":
        template = (
            "{% set tab = states('" + entity + "') %}"
            "{{ tab == 'Home' or tab in ['unknown', 'unavailable', none] }}"
        )
    else:
        template = "{{ is_state('" + entity + "', '" + label + "') }}"
    return {"condition": "template", "value_template": template}


def _tab_button(label: str, icon: str) -> dict:
    """Full-width tab pill — one third of the tab bar grid."""
    return {
        "type": "custom:button-card",
        "template": "flux_overview_tab",
        "entity": OVERVIEW_TAB_ENTITY,
        "name": label,
        "icon": icon,
        "variables": {"tab_option": label},
        "tap_action": {
            "action": "perform-action",
            "perform_action": "input_select.select_option",
            "target": {"entity_id": OVERVIEW_TAB_ENTITY},
            "data": {"option": label},
        },
        "triggers_update": "all",
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  width: 100% !important;\n"
                "  margin: 0 !important;\n"
                "  box-sizing: border-box !important;\n"
                "}\n"
            )
        },
    }


def _native_tab_bar(cfg: dict) -> dict:
    """Edge-to-edge tab row — ElementZoom Home / Events / Active."""
    tabs = [
        _tab_button("Home", "mdi:home"),
        _tab_button("Events", "mdi:calendar"),
        _tab_button("Active", "mdi:play-circle"),
    ]
    return {
        "type": "grid",
        "columns": 3,
        "square": False,
        "grid_options": {"columns": 12},
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  width: 100% !important;\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  margin: 0 !important;\n"
                "  padding: 0 !important;\n"
                "}\n"
                "#root {\n"
                "  display: grid !important;\n"
                "  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;\n"
                "  gap: 8px !important;\n"
                "  width: 100% !important;\n"
                "}\n"
            )
        },
        "cards": tabs,
    }


def _tab_panel(label: str, cards: list[dict], *, visible_jinja: str | None = None) -> dict:
    panel = tab_panel_stack(*cards) if len(cards) > 1 else grid_to_vertical_stack(cards[0])
    # grid_options on conditional cards causes "Configuration error" in sections view —
    # wrap the panel in a full-width grid inside the conditional instead.
    panel_full: dict[str, Any] = {
        "type": "grid",
        "cards": [panel],
        "grid_options": {"columns": 12},
    }
    wrapped: dict[str, Any] = {
        "type": "conditional",
        "conditions": [_tab_is_active(label)],
        "card": panel_full,
    }
    if visible_jinja:
        wrapped = {
            "type": "conditional",
            "conditions": [{"condition": "template", "value_template": visible_jinja}],
            "card": wrapped,
        }
    return wrapped


def _simple_tabs_shell(tabs: list[dict], *, enable_swipe: bool = True) -> dict:
    """ElementZoom-style full-width tab bar — https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard"""
    return {
        "type": "custom:simple-tabs",
        "pre-load": False,
        "tabs_alignment": "center",
        "card_padding": "0",
        "bar_padding": "6px 8px",
        "bar_border_radius": "28px",
        "bar_border": "1px solid color-mix(in srgb, var(--md-sys-color-outline-variant) 35%, transparent)",
        "bar_background": "transparent",
        "tabs_gap": "8px",
        "button_padding": "14px 10px",
        "button_background": "color-mix(in srgb, var(--md-sys-color-surface-container) 55%, transparent)",
        "button_active_background": "var(--md-sys-color-primary)",
        "button_active_text_color": "var(--md-sys-color-on-primary)",
        "button_text_color": "var(--primary-text-color)",
        "button_border_color": "transparent",
        "button_hover_border_color": "transparent",
        "haptic_feedback": True,
        "enable_swipe": enable_swipe,
        "hide_inactive_tab_titles": False,
        "card_mod": {
            "style": {
                ".": (
                    "ha-card, :host {\n"
                    "  width: 100% !important;\n"
                    "  background: transparent !important;\n"
                    "  box-shadow: none !important;\n"
                    "  border: none !important;\n"
                    "  margin: 0 !important;\n"
                    "  padding: 0 !important;\n"
                    "}\n"
                    ".tabs-row {\n"
                    "  width: 100% !important;\n"
                    "}\n"
                    ".tabs-viewport {\n"
                    "  width: 100% !important;\n"
                    "  max-width: 100% !important;\n"
                    "}\n"
                    ".tabs-container {\n"
                    "  width: 100% !important;\n"
                    "  min-width: 100% !important;\n"
                    "}\n"
                    ".tabs {\n"
                    "  width: 100% !important;\n"
                    "  display: flex !important;\n"
                    "  box-sizing: border-box !important;\n"
                    "}\n"
                    ".tab-button {\n"
                    "  flex: 1 1 0 !important;\n"
                    "  min-width: 0 !important;\n"
                    "  justify-content: center !important;\n"
                    "}\n"
                ),
            },
        },
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
                "event_spacing": events.get("event_spacing", "6px"),
                "day_spacing": events.get("day_spacing", "4px"),
                "first_day_of_week": events.get("first_day_of_week", "monday"),
                "show_week_numbers": "iso",
                "week_number_color": "var(--md-sys-color-on-primary)",
                "week_number_background_color": "var(--md-sys-color-primary)",
                "month_separator_width": "1px",
                "month_separator_color": "var(--md-sys-color-primary)",
                "today_indicator": "pulse",
                "today_indicator_position": "10% 50%",
                "today_indicator_color": "var(--md-sys-color-primary)",
                "date_vertical_alignment": events.get("date_vertical_alignment", "top"),
                "weekday_font_size": events.get("weekday_font_size", "12px"),
                "day_font_size": events.get("day_font_size", "26px"),
                "month_font_size": events.get("month_font_size", "10px"),
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

    fallback: list[dict] = [
        wrap_title(
            {
                "type": "custom:mushroom-title-card",
                "title": "Events",
                "subtitle": "Install calendar-card-pro via HACS for ElementZoom timeline view",
            }
        )
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
    return [{"type": "vertical-stack", "cards": fallback}]


def build_active_tab_cards(cfg: dict, *, use_auto_entities: bool, for_tab_panel: bool = False) -> list[dict]:
    from flux_tab_layout import adapt_card_for_tab_panel, strip_grid_options_deep

    cards: list[dict] = []
    if use_auto_entities:
        cards.append(build_active_lights_section(cfg))
    open_garage = build_open_garage_section(cfg, for_tab_panel=for_tab_panel)
    if open_garage:
        cards.append(open_garage)
    active_cfg = _tabs_cfg(cfg).get("active", {})
    for group in active_cfg.get("groups", []):
        entity = group.get("entity")
        if entity:
            cards.append(_active_group_section(group))
    if for_tab_panel:
        prepared: list[dict] = []
        for card in cards:
            # Doors-open alert is already tab-panel shaped — only strip grid_options.
            if card.get("type") == "conditional":
                prepared.append(strip_grid_options_deep(card))  # type: ignore[arg-type]
            else:
                prepared.append(adapt_card_for_tab_panel(card))
        return prepared
    return cards


def _active_group_section(group: dict) -> dict:
    from flux_layouts import flux_light_auto_entities_options
    from phase3_builders import _title

    entity = group["entity"]
    state = group.get("state", "on")
    title = group.get("title", entity.split(".")[-1].replace("_", " ").title())
    is_light = entity.startswith("light.")
    options: dict[str, Any] = (
        flux_light_auto_entities_options(columns=6)
        if is_light
        else {
            "type": "custom:button-card",
            "template": "flux_action",
            "tap_action": {"action": "toggle"},
        }
    )
    auto_card: dict = {
        "type": "custom:auto-entities",
        "card": {"type": "grid", "columns": 2, "square": False},
        "card_param": "cards",
        "show_empty": False,
        "filter": {"include": [{"group": entity, "state": state, "options": options}]},
        "sort": {"method": "friendly_name"},
    }
    return {
        "type": "vertical-stack",
        "cards": [_title(title, "Currently active"), auto_card],
    }


def build_native_tabs_section(
    cfg: dict,
    *,
    home_tab_cards: list[dict],
    use_auto_entities: bool,
    use_calendar_pro: bool,
) -> dict:
    """Full-width tab bar + conditional panels (ElementZoom layout)."""
    active_jinja = _active_tab_visibility_jinja(cfg)
    active_cards = build_active_tab_cards(cfg, use_auto_entities=use_auto_entities)

    stack_cards: list[dict] = [
        _native_tab_bar(cfg),
        _tab_panel("Home", home_tab_cards),
        _tab_panel("Events", build_events_tab_cards(cfg, use_calendar_pro=use_calendar_pro)),
    ]
    if active_cards:
        stack_cards.append(
            _tab_panel("Active", active_cards, visible_jinja=active_jinja),
        )

    return {
        "type": "grid",
        "cards": stack_cards,
    }


def overview_tab_fingerprint(cfg: dict) -> dict[str, str]:
    """Deploy fingerprint — confirms native tab layout is in the built config."""
    engine = tab_engine(cfg)
    return {
        "layout": FLUX_UI_TAB_LAYOUT if engine == "native" else "simple-tabs",
        "engine": engine,
        "entity": OVERVIEW_TAB_ENTITY,
    }


def overview_tab_usage(config: dict) -> dict[str, bool]:
    """Detect tab engine from overview view cards only (not unused button_card templates)."""
    overview = next((v for v in config.get("views", []) if v.get("path") == "overview"), {})
    blob = json.dumps(overview)
    has_simple = "custom:simple-tabs" in blob
    has_native = not has_simple and (
        OVERVIEW_TAB_ENTITY in blob or '"template": "flux_overview_tab"' in blob
    )
    return {"has_simple_tabs": has_simple, "has_native_tabs": has_native}


def build_overview_tabs_section(
    cfg: dict,
    *,
    home_tab_cards: list[dict],
    use_auto_entities: bool,
    use_calendar_pro: bool,
    use_simple_tabs: bool = True,
    enable_tab_swipe: bool = True,
) -> dict:
    engine = tab_engine(cfg)
    use_hacs = use_simple_tabs and engine in ("simple-tabs", "auto")
    if use_hacs:
        tabs: list[dict] = [
            {"title": "Home", "icon": "mdi:home", "cards": home_tab_cards},
            {
                "title": "Events",
                "icon": "mdi:calendar",
                "cards": build_events_tab_cards(cfg, use_calendar_pro=use_calendar_pro),
            },
        ]
        active_cards = build_active_tab_cards(
            cfg, use_auto_entities=use_auto_entities, for_tab_panel=True
        )
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
                {
                    **_simple_tabs_shell(tabs, enable_swipe=enable_tab_swipe),
                    "grid_options": {"columns": 12},
                }
            ],
        }

    return build_native_tabs_section(
        cfg,
        home_tab_cards=home_tab_cards,
        use_auto_entities=use_auto_entities,
        use_calendar_pro=use_calendar_pro,
    )


def build_quick_actions_tab(cfg: dict, section_title_fn) -> dict:
    """Quick Actions for tab panels — full-width 2-column grid, readable labels."""
    buttons: list[dict] = []
    for item in cfg["quick_actions"]["gate"]:
        buttons.append(
            strip_grid_options(
                lock_action(
                    item["entity"],
                    item["name"],
                    columns=6,
                    status_entity=item.get("status_entity"),
                    hold_entity=item.get("hold_entity"),
                    status_on_means_open=bool(item.get("status_on_means_open", True)),
                )
            )
        )
    for item in cfg["quick_actions"]["garage"]:
        buttons.append(strip_grid_options(garage_action(item, columns=6)))
    for item in cfg["quick_actions"]["actions"]:
        buttons.append(
            strip_grid_options(
                scene_action(
                    item["name"],
                    item["subtitle"],
                    item["icon"],
                    item["service"],
                    item["target"],
                    columns=6,
                )
            )
        )
    title = section_title_fn("Quick Actions", "Tap to control")
    title.pop("grid_options", None)
    return {
        "type": "vertical-stack",
        "cards": [
            title,
            tab_two_column_grid(buttons),
        ],
    }

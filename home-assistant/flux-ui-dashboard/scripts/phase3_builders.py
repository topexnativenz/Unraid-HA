"""Phase 3 — context-aware overview sections (Flux home intelligence)."""

from __future__ import annotations

import sys
from pathlib import Path

from flux_door_builders import build_doors_open_alert_section
from flux_layouts import flux_light_auto_entities_options
from md3_templates import wrap_glass, wrap_title

GARAGE_DIR = Path(__file__).resolve().parents[2] / "garage-doors"
sys.path.insert(0, str(GARAGE_DIR))

from garage_ui_helpers import jinja_door_open_expr  # noqa: E402


def _title(title: str, subtitle: str = "") -> dict:
    card: dict = {
        "type": "custom:mushroom-title-card",
        "title": title,
        "grid_options": {"columns": 12},
    }
    if subtitle:
        card["subtitle"] = subtitle
    return wrap_title(card)


def _jinja_lights_chip(lights_entity: str) -> tuple[str, str]:
    content = (
        "{% set n = states.light | selectattr('state', 'eq', 'on') | list | count %}\n"
        "{% if n > 0 %}\n"
        "{{ n }} light{% if n != 1 %}s{% endif %} on\n"
        "{% else %}\n"
        "Lights off\n"
        "{% endif %}"
    )
    icon_color = (
        "{% set n = states.light | selectattr('state', 'eq', 'on') | list | count %}\n"
        "{% if n > 0 %}amber{% else %}disabled{% endif %}"
    )
    return content, icon_color


def _jinja_garage_chip(doors: list[dict]) -> tuple[str, str]:
    """Live garage/shed status — supports Tapo on/off and open/closed states."""
    if not doors:
        return "Garage closed", "disabled"
    count_parts = " + ".join(
        f"(1 if {jinja_door_open_expr(d['sensor'], invert=d.get('invert', False))} else 0)"
        for d in doors
    )
    content = (
        f"{{% set open = {count_parts} %}}\n"
        "{% if open > 0 %}\n"
        "{{ open }} door{% if open != 1 %}s{% endif %} open\n"
        "{% else %}\n"
        "All closed\n"
        "{% endif %}"
    )
    icon_color = (
        f"{{% set open = {count_parts} %}}\n"
        "{% if open > 0 %}red{% else %}green{% endif %}"
    )
    return content, icon_color


def build_home_status_section(cfg: dict) -> dict:
    """Status chips: lights on + open garage doors (always visible, counts update live)."""
    hs = cfg.get("context", {}).get("home_status", {})
    lights_entity = hs.get("lights_on", "light.all_lights")
    garage = cfg.get("quick_actions", {}).get("garage", [])

    lights_content, lights_color = _jinja_lights_chip(lights_entity)
    chips: list[dict] = [
        {
            "type": "template",
            "entity": lights_entity,
            "icon": "mdi:lightbulb-on",
            "icon_color": lights_color,
            "content": lights_content,
            "tap_action": {"action": "navigate", "navigation_path": "/flux-ui/lights"},
        },
    ]

    if garage:
        garage_content, garage_color = _jinja_garage_chip(garage)
        chips.append(
            {
                "type": "template",
                "entity": garage[0]["sensor"],
                "icon": "mdi:garage-alert",
                "icon_color": garage_color,
                "content": garage_content,
                "tap_action": {"action": "navigate", "navigation_path": "/flux-ui/room-garage"},
            }
        )

    return {
        "type": "grid",
        "cards": [
            _title("Home status", "Live"),
            wrap_glass(
                {
                    "type": "custom:mushroom-chips-card",
                    "alignment": "start",
                    "chips": chips,
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }


def build_active_lights_section(cfg: dict) -> dict:
    active = cfg.get("context", {}).get("active_lights", {})
    domain = active.get("domain", "light")
    state = active.get("state", "on")
    exclude = active.get("exclude", [])

    filter_include: dict = {
        "domain": domain,
        "state": state,
        "options": flux_light_auto_entities_options(columns=6),
    }

    card: dict = {
        "type": "custom:auto-entities",
        "card": {
            "type": "grid",
            "square": False,
            "columns": 2,
        },
        "card_param": "cards",
        "show_empty": False,
        "filter": {
            "include": [filter_include],
            "exclude": [{"entity_id": e} for e in exclude],
        },
        "sort": {"method": "friendly_name"},
    }

    return {
        "type": "grid",
        "cards": [
            _title("Active now", "Lights on"),
            wrap_glass({**card, "grid_options": {"columns": 12}}),
        ],
    }


def build_open_garage_section(cfg: dict, *, for_tab_panel: bool = False) -> dict | None:
    """Conditional alert when any Tapo garage/shed contact is open."""
    garage = cfg.get("quick_actions", {}).get("garage", [])
    return build_doors_open_alert_section(garage, for_tab_panel=for_tab_panel)


def bubble_popup_card(entity: str, name: str) -> dict:
    slug = entity.replace(".", "-")
    return {
        "type": "custom:bubble-card",
        "card_type": "pop-up",
        "hash": f"#light-{slug}",
        "name": name,
        "icon": "mdi:lightbulb",
        "entity": entity,
        "button_type": "name",
        "bg_blur": "14",
        "bg_opacity": "88",
        "styles": (
            "#root { max-height: 100% !important; }\n"
            ".bubble-pop-up-container { padding-bottom: 48px !important; }\n"
        ),
        "cards": [
            {
                "type": "custom:mushroom-light-card",
                "entity": entity,
                "name": name,
                "fill_container": True,
                "show_brightness_control": True,
                "show_color_control": True,
                "collapsible_controls": False,
                "use_light_color": True,
            }
        ],
    }


def light_tile_bubble(entity: str, name: str, *, columns: int = 6) -> dict:
    slug = entity.replace(".", "-")
    return {
        "type": "custom:button-card",
        "template": "flux_light",
        "entity": entity,
        "name": name,
        "icon": "mdi:lightbulb",
        "label": (
            "[[[\n"
            "  if (entity.state !== 'on') return 'Off';\n"
            "  const b = entity.attributes.brightness;\n"
            "  return b != null ? Math.round(b / 255 * 100) + '%' : 'On';\n"
            "]]]"
        ),
        "tap_action": {"action": "navigate", "navigation_path": f"#light-{slug}"},
        "hold_action": {"action": "toggle"},
        "grid_options": {"columns": columns},
    }


def build_bubble_popups_section(lights: list[dict]) -> dict:
    cards = [bubble_popup_card(item["entity"], item["name"]) for item in lights]
    return {"type": "grid", "cards": cards}


def collect_bubble_lights(cfg: dict) -> list[dict]:
    return list(cfg.get("favourite_lights", []))

"""Flux MD3 garage / shed door tiles — live Tapo contact sensor display."""

from __future__ import annotations

import sys
from pathlib import Path

GARAGE_DIR = Path(__file__).resolve().parents[2] / "garage-doors"
sys.path.insert(0, str(GARAGE_DIR))

from garage_ui_helpers import (  # noqa: E402
    door_open_state_js,
    open_color_js,
    open_icon_js,
    open_label_js,
)
from md3_templates import wrap_glass, wrap_title


def flux_door_tile(door: dict, *, columns: int = 4) -> dict:
    """Large MD3 door tile — green closed, pulsing red/pink when open."""
    sensor = door["sensor"]
    invert = door.get("invert", False)
    name = door["name"]
    return {
        "type": "custom:button-card",
        "template": "flux_door",
        "entity": sensor,
        "triggers_update": "all",
        "name": name,
        "icon": open_icon_js(sensor, invert=invert, name=name),
        "label": open_label_js(sensor, invert=invert),
        "variables": {"invert": invert, "door_name": name, "sensor_id": sensor},
        "tap_action": {
            "action": "call-service",
            "service": "script.turn_on",
            "service_data": {"entity_id": door["script"]},
        },
        "hold_action": {"action": "more-info"},
        "state": [
            {
                "operator": "template",
                "value": door_open_state_js(invert=invert, sensor=sensor),
                "styles": {
                    "card": [
                        {
                            "background": (
                                "color-mix(in srgb, #F2B8B5 42%, "
                                "var(--md-sys-color-surface-container) 58%)"
                            )
                        },
                        {"border": "1px solid rgba(242, 184, 181, 0.85)"},
                        {
                            "box-shadow": (
                                "0 0 22px rgba(242, 184, 181, 0.55), "
                                "0 0 40px rgba(242, 184, 181, 0.25)"
                            )
                        },
                        {"animation": "flux-door-pulse 2.4s ease-in-out infinite"},
                    ],
                    "icon": [{"color": "#3b1216"}],
                    "img_cell": [
                        {"background-color": "rgba(242, 184, 181, 0.55)"},
                        {"box-shadow": "0 0 16px rgba(242, 184, 181, 0.65)"},
                    ],
                    "name": [{"color": "#fff8f7"}, {"font-weight": "700"}],
                    "label": [{"color": "#F2B8B5"}, {"font-weight": "700"}],
                },
            },
        ],
        "styles": {
            "icon": [{"color": open_color_js(sensor, invert=invert)}],
        },
        "grid_options": {"columns": columns},
    }


def build_doors_status_section(doors: list[dict], *, title: str = "Doors", subtitle: str = "Tapo contact sensors") -> dict:
    """Always-visible door row — updates live when Tapo sensors change."""
    if not doors:
        return {"type": "grid", "cards": []}
    return {
        "type": "grid",
        "cards": [
            wrap_title(
                {
                    "type": "custom:mushroom-title-card",
                    "title": title,
                    "subtitle": subtitle,
                    "grid_options": {"columns": 12},
                }
            ),
            wrap_glass(
                {
                    "type": "grid",
                    "columns": 3,
                    "square": False,
                    "cards": [flux_door_tile(d, columns=4) for d in doors],
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }


def build_doors_open_alert_section(doors: list[dict]) -> dict | None:
    """Conditional alert strip listing only doors that are currently open."""
    from garage_ui_helpers import is_door_open_jinja

    if not doors:
        return None
    open_cards: list[dict] = []
    for door in doors:
        invert = door.get("invert", False)
        open_cards.append(
            {
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "template",
                        "value_template": is_door_open_jinja(door["sensor"], invert=invert),
                    }
                ],
                "card": flux_door_tile(door, columns=6),
            }
        )
    alert_cards = [
        wrap_title(
            {
                "type": "custom:mushroom-title-card",
                "title": "Doors open",
                "subtitle": "Check before leaving",
                "grid_options": {"columns": 12},
            }
        ),
        wrap_glass({"type": "grid", "columns": 2, "square": False, "cards": open_cards, "grid_options": {"columns": 12}}),
    ]
    from garage_ui_helpers import jinja_any_door_open

    return {
        "type": "grid",
        "cards": [
            {
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "template",
                        "value_template": jinja_any_door_open(doors),
                    }
                ],
                "card": {"type": "grid", "cards": alert_cards},
            }
        ],
    }

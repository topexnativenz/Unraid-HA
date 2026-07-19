"""Quick-action button-card builders shared by overview and tab panels."""

from __future__ import annotations

from flux_door_builders import flux_door_tile

# Vehicle gate colours — match garage door open/closed language.
_GATE_OPEN_BG = "color-mix(in srgb, #F2B8B5 42%, var(--md-sys-color-surface-container) 58%)"
_GATE_OPEN_BORDER = "1px solid rgba(242, 184, 181, 0.85)"
_GATE_OPEN_COLOR = "#F2B8B5"
_GATE_CLOSED_BG = "color-mix(in srgb, #81C784 28%, var(--md-sys-color-surface-container) 72%)"
_GATE_CLOSED_BORDER = "1px solid rgba(129, 199, 132, 0.55)"
_GATE_CLOSED_COLOR = "#81C784"
_GATE_UNLATCHED_BG = "color-mix(in srgb, #FFB74D 36%, var(--md-sys-color-surface-container) 64%)"
_GATE_UNLATCHED_BORDER = "1px solid rgba(255, 183, 77, 0.75)"
_GATE_UNLATCHED_COLOR = "#FFB74D"


def lock_action(entity: str, name: str, *, columns: int = 6) -> dict:
    """Gate Open / Gate Latch — vehicle-gate icons + open/closed/latched colours."""
    is_latch = "latch" in name.lower()
    closed_label = "Latched" if is_latch else "Closed"
    open_label = "Unlatched" if is_latch else "Open"
    open_bg = _GATE_UNLATCHED_BG if is_latch else _GATE_OPEN_BG
    open_border = _GATE_UNLATCHED_BORDER if is_latch else _GATE_OPEN_BORDER
    open_color = _GATE_UNLATCHED_COLOR if is_latch else _GATE_OPEN_COLOR

    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "entity": entity,
        "name": name,
        # locked = gate closed / latched; unlocked = gate open / unlatched
        "icon": (
            "[[[ return entity.state === 'locked' "
            "? 'mdi:gate' : 'mdi:gate-open'; ]]]"
        ),
        "label": (
            "[[[\n"
            f"  if (entity.state === 'locked') return '{closed_label}';\n"
            f"  if (entity.state === 'unlocked') return '{open_label}';\n"
            "  return entity.state;\n"
            "]]]"
        ),
        "tap_action": {"action": "toggle"},
        "triggers_update": "all",
        "state": [
            {
                "value": "unlocked",
                "styles": {
                    "card": [
                        {"background": open_bg},
                        {"border": open_border},
                    ],
                    "icon": [{"color": open_color}],
                    "img_cell": [{"background-color": f"color-mix(in srgb, {open_color} 22%, transparent)"}],
                    "label": [{"color": open_color}, {"font-weight": "600"}],
                    "name": [{"color": "var(--md-sys-color-on-surface)"}],
                },
            },
            {
                "value": "locked",
                "styles": {
                    "card": [
                        {"background": _GATE_CLOSED_BG},
                        {"border": _GATE_CLOSED_BORDER},
                    ],
                    "icon": [{"color": _GATE_CLOSED_COLOR}],
                    "img_cell": [
                        {"background-color": "rgba(129, 199, 132, 0.22)"}
                    ],
                    "label": [{"color": _GATE_CLOSED_COLOR}, {"font-weight": "600"}],
                    "name": [{"color": "var(--md-sys-color-on-surface)"}],
                },
            },
        ],
        "grid_options": {"columns": columns},
    }


def garage_action(door: dict, *, columns: int = 6) -> dict:
    """Quick action — flux_door tile bound to Tapo contact sensor."""
    return flux_door_tile(door, columns=columns)


def scene_action(
    name: str, subtitle: str, icon: str, service: str, target: str, *, columns: int = 6
) -> dict:
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "name": name,
        "label": subtitle,
        "icon": icon,
        "tap_action": {
            "action": "perform-action",
            "perform_action": service,
            "target": {"entity_id": target},
        },
        "grid_options": {"columns": columns},
    }

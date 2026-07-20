"""Quick-action button-card builders shared by overview and tab panels."""

from __future__ import annotations

import base64
from pathlib import Path

from flux_door_builders import flux_door_tile

# Soft tinted card fills (state colour on the button body).
_GATE_OPEN_BG = "color-mix(in srgb, #F2B8B5 42%, var(--md-sys-color-surface-container) 58%)"
_GATE_OPEN_BORDER = "1px solid rgba(242, 184, 181, 0.85)"
_GATE_CLOSED_BG = "color-mix(in srgb, #81C784 28%, var(--md-sys-color-surface-container) 72%)"
_GATE_CLOSED_BORDER = "1px solid rgba(129, 199, 132, 0.55)"
_GATE_UNLATCHED_BG = "color-mix(in srgb, #FFB74D 36%, var(--md-sys-color-surface-container) 64%)"
_GATE_UNLATCHED_BORDER = "1px solid rgba(255, 183, 77, 0.75)"

# High-contrast icon chips — dark saturated backgrounds + white double-swing SVGs.
_CHIP_CLOSED = "#0D3B1E"  # deep green on green card
_CHIP_OPEN = "#5C1010"  # deep rose on pink card
_CHIP_UNLATCHED = "#4A2800"  # deep amber on amber card

_ICONS_DIR = Path(__file__).resolve().parents[1] / "www" / "flux-ui" / "icons"


def _svg_data_uri(filename: str) -> str:
    """Inline SVG so gate icons work even when SMB cannot mkdir www/flux-ui/icons."""
    raw = (_ICONS_DIR / filename).read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")


_GATE_CLOSED_PIC = _svg_data_uri("vehicle-gate-closed.svg")
_GATE_OPEN_PIC = _svg_data_uri("vehicle-gate-open.svg")


def _gate_open_js_body(
    *,
    status_entity: str | None,
    hold_entity: str | None,
    status_on_means_open: bool,
) -> str:
    """JS body (no [[[ ]]]) — true while driveway gate should show Open/Unlatched.

    Akuvox lock.* entities are momentary pulses (~5 s). They return to locked
    while the physical gate is still open. Prefer contact/status + hold flag.
    """
    lines = [
        "if (entity.state === 'unlocked' || entity.state === 'opening') return true;",
    ]
    if status_entity:
        cmp = "===" if status_on_means_open else "!=="
        lines.append(f"const st = states['{status_entity}'];")
        lines.append(f"if (st && st.state {cmp} 'on') return true;")
    if hold_entity:
        lines.append(f"const hold = states['{hold_entity}'];")
        lines.append("if (hold && hold.state === 'on') return true;")
    lines.append("return false;")
    return "\n  ".join(lines)


def lock_action(
    entity: str,
    name: str,
    *,
    columns: int = 6,
    status_entity: str | None = None,
    hold_entity: str | None = None,
    status_on_means_open: bool = True,
) -> dict:
    """Gate Open / Gate Latch — double-swing icons + durable open/closed state."""
    is_latch = "latch" in name.lower()
    closed_label = "Latched" if is_latch else "Closed"
    open_label = "Unlatched" if is_latch else "Open"
    open_bg = _GATE_UNLATCHED_BG if is_latch else _GATE_OPEN_BG
    open_border = _GATE_UNLATCHED_BORDER if is_latch else _GATE_OPEN_BORDER
    open_chip = _CHIP_UNLATCHED if is_latch else _CHIP_OPEN
    open_label_color = "#FFB74D" if is_latch else "#F2B8B5"
    closed_label_color = "#81C784"

    open_body = _gate_open_js_body(
        status_entity=status_entity,
        hold_entity=hold_entity,
        status_on_means_open=status_on_means_open,
    )
    is_open_expr = f"[[[\n  {open_body}\n]]]"

    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "entity": entity,
        "name": name,
        "show_icon": False,
        "show_entity_picture": True,
        # Inline data-URI SVGs — independent of /local/flux-ui/icons on SMB.
        "entity_picture": (
            "[[[\n"
            f"  const isOpen = (() => {{ {open_body} }})();\n"
            f"  return isOpen ? '{_GATE_OPEN_PIC}' : '{_GATE_CLOSED_PIC}';\n"
            "]]]"
        ),
        "label": (
            "[[[\n"
            f"  const isOpen = (() => {{ {open_body} }})();\n"
            f"  return isOpen ? '{open_label}' : '{closed_label}';\n"
            "]]]"
        ),
        "tap_action": {
            # Always pulse unlock — toggle races the momentary relay state.
            "action": "call-service",
            "service": "lock.unlock",
            "service_data": {"entity_id": entity},
        },
        "triggers_update": "all",
        "styles": {
            "grid": [
                {"grid-template-areas": "'i n' 'i l'"},
                {"grid-template-columns": "52px 1fr"},
                {"grid-template-rows": "min-content min-content"},
                {"column-gap": "12px"},
            ],
            "img_cell": [
                {"border-radius": "16px"},
                {"width": "52px"},
                {"height": "52px"},
                {"place-self": "center"},
                {"background-color": _CHIP_CLOSED},
            ],
            "entity_picture": [
                {"width": "30px"},
                {"height": "30px"},
                {"object-fit": "contain"},
            ],
            "card": [
                {"background": _GATE_CLOSED_BG},
                {"border": _GATE_CLOSED_BORDER},
            ],
            "label": [{"color": closed_label_color}, {"font-weight": "700"}],
        },
        "state": [
            {
                "operator": "template",
                "value": is_open_expr,
                "styles": {
                    "card": [
                        {"background": open_bg},
                        {"border": open_border},
                    ],
                    "img_cell": [
                        {"background-color": open_chip},
                        {"box-shadow": f"0 0 0 1px {open_chip}"},
                    ],
                    "label": [{"color": open_label_color}, {"font-weight": "700"}],
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

"""Quick-action button-card builders shared by overview and tab panels."""

from __future__ import annotations

import base64
from pathlib import Path

from flux_door_builders import flux_door_tile

# Soft tinted card fill — only when gate is open (closed stays default theme).
_GATE_OPEN_BG = "color-mix(in srgb, #F2B8B5 42%, var(--md-sys-color-surface-container) 58%)"
_GATE_OPEN_BORDER = "1px solid rgba(242, 184, 181, 0.85)"

# High-contrast icon chips.
_CHIP_DEFAULT = "color-mix(in srgb, var(--md-sys-color-on-surface) 12%, transparent)"
_CHIP_OPEN = "#5C1010"  # deep rose on pink/red open card

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
    """Gate Open / Gate Latch — default chrome; red background only when open."""
    is_latch = "latch" in name.lower()
    closed_label = "Latched" if is_latch else "Closed"
    open_label = "Unlatched" if is_latch else "Open"
    open_label_color = "#F2B8B5"

    open_body = _gate_open_js_body(
        status_entity=status_entity,
        hold_entity=hold_entity,
        status_on_means_open=status_on_means_open,
    )
    is_open_expr = f"[[[\n  {open_body}\n]]]"

    triggers: list[str] = [entity]
    if status_entity:
        triggers.append(status_entity)
    if hold_entity:
        triggers.append(hold_entity)

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
        "triggers_update": triggers,
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
                {"background-color": _CHIP_DEFAULT},
            ],
            "entity_picture": [
                {"width": "30px"},
                {"height": "30px"},
                {"object-fit": "contain"},
            ],
        },
        "state": [
            {
                "operator": "template",
                "value": is_open_expr,
                "styles": {
                    "card": [
                        {"background": _GATE_OPEN_BG},
                        {"border": _GATE_OPEN_BORDER},
                    ],
                    "img_cell": [
                        {"background-color": _CHIP_OPEN},
                        {"box-shadow": f"0 0 0 1px {_CHIP_OPEN}"},
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

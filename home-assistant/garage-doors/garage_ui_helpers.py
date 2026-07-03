"""Shared garage door UI helpers — icons/state from Tapo contact sensors."""

from __future__ import annotations

from pathlib import Path

import yaml

GARAGE_ENTITIES = Path(__file__).resolve().parent / "entities.yaml"


def load_garage_doors() -> list[dict]:
    data = yaml.safe_load(GARAGE_ENTITIES.read_text())
    return data.get("doors", [])


def open_icon_jinja(sensor: str, *, invert: bool = False) -> str:
    if invert:
        return (
            f"{{{{ 'mdi:garage-open' if is_state('{sensor}', 'off') "
            f"else 'mdi:garage' }}}}"
        )
    return (
        f"{{{{ 'mdi:garage-open' if is_state('{sensor}', 'on') "
        f"else 'mdi:garage' }}}}"
    )


def open_color_jinja(sensor: str, *, invert: bool = False) -> str:
    if invert:
        return f"{{{{ 'red' if is_state('{sensor}', 'off') else 'grey' }}}}"
    return f"{{{{ 'red' if is_state('{sensor}', 'on') else 'grey' }}}}"


def open_label_jinja(sensor: str, *, invert: bool = False) -> str:
    if invert:
        return f"{{{{ 'Open' if is_state('{sensor}', 'off') else 'Closed' }}}}"
    return f"{{{{ 'Open' if is_state('{sensor}', 'on') else 'Closed' }}}}"


def open_icon_js(sensor: str, *, invert: bool = False) -> str:
    want = "off" if invert else "on"
    return (
        "[[[\n"
        f"  const s = states['{sensor}']?.state;\n"
        f"  return s === '{want}' ? 'mdi:garage-open' : 'mdi:garage';\n"
        "]]]"
    )


def open_label_js(sensor: str, *, invert: bool = False) -> str:
    want = "off" if invert else "on"
    return (
        "[[[\n"
        f"  const s = states['{sensor}']?.state;\n"
        f"  return s === '{want}' ? 'Open' : 'Closed';\n"
        "]]]"
    )


def open_color_js(sensor: str, *, invert: bool = False) -> str:
    want = "off" if invert else "on"
    return (
        "[[[\n"
        f"  const s = states['{sensor}']?.state;\n"
        f"  return s === '{want}' ? '#F2B8B5' : 'var(--md-sys-color-primary)';\n"
        "]]]"
    )

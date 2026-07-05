"""Shared garage door UI helpers — icons/state from Tapo contact sensors."""

from __future__ import annotations

from pathlib import Path

import yaml

GARAGE_ENTITIES = Path(__file__).resolve().parent / "entities.yaml"

# Tapo / HA door sensors may report on/off, open/closed, or detected/clear.
DOOR_OPEN_STATES = ("on", "open", "opened", "detected", "true")
DOOR_CLOSED_STATES = ("off", "closed", "close", "clear", "false", "undetected")


def load_garage_doors() -> list[dict]:
    data = yaml.safe_load(GARAGE_ENTITIES.read_text())
    return data.get("doors", [])


def door_icon(name: str, *, open_icon: bool) -> str:
    """Pick garage vs shed icon from door name."""
    lower = name.lower()
    if "shed" in lower:
        return "mdi:door-sliding-open" if open_icon else "mdi:warehouse"
    return "mdi:garage-open" if open_icon else "mdi:garage"


def _jinja_open_states() -> str:
    return ", ".join(f"'{s}'" for s in DOOR_OPEN_STATES)


def _jinja_closed_states() -> str:
    return ", ".join(f"'{s}'" for s in DOOR_CLOSED_STATES)


def is_door_open_jinja(sensor: str, *, invert: bool = False) -> str:
    open_list = _jinja_open_states()
    closed_list = _jinja_closed_states()
    if invert:
        return f"{{{{ states('{sensor}') | lower in [{closed_list}] }}}}"
    return f"{{{{ states('{sensor}') | lower in [{open_list}] }}}}"


def jinja_door_open_expr(sensor: str, *, invert: bool = False) -> str:
    """Jinja expression (no outer braces) — true when door is open."""
    open_list = _jinja_open_states()
    closed_list = _jinja_closed_states()
    if invert:
        return f"states('{sensor}') | lower in [{closed_list}]"
    return f"states('{sensor}') | lower in [{open_list}]"


def jinja_any_door_open(doors: list[dict]) -> str:
    parts = [jinja_door_open_expr(d["sensor"], invert=d.get("invert", False)) for d in doors]
    return f"{{{{ {' or '.join(parts)} }}}}"


def jinja_open_door_count(doors: list[dict]) -> str:
    parts = [
        f"(1 if {jinja_door_open_expr(d['sensor'], invert=d.get('invert', False))} else 0)"
        for d in doors
    ]
    return "{% set open = " + " + ".join(parts) + " %}{{ open }}"


def open_icon_jinja(sensor: str, *, invert: bool = False, name: str = "Garage") -> str:
    cond = is_door_open_jinja(sensor, invert=invert).replace("{{ ", "").replace(" }}", "")
    icon_open = door_icon(name, open_icon=True)
    icon_closed = door_icon(name, open_icon=False)
    return f"{{{{ '{icon_open}' if {cond} else '{icon_closed}' }}}}"


def open_color_jinja(sensor: str, *, invert: bool = False) -> str:
    cond = is_door_open_jinja(sensor, invert=invert).replace("{{ ", "").replace(" }}", "")
    return f"{{{{ '#F2B8B5' if {cond} else '#81C784' }}}}"


def open_label_jinja(sensor: str, *, invert: bool = False) -> str:
    cond = is_door_open_jinja(sensor, invert=invert).replace("{{ ", "").replace(" }}", "")
    return f"{{{{ 'Open' if {cond} else 'Closed' }}}}"


IS_DOOR_OPEN_JS = (
    "const isDoorOpen = (st, invert) => {\n"
    "  if (!st || ['unavailable','unknown'].includes(st.state)) return null;\n"
    f"  const openish = [{', '.join(repr(s) for s in DOOR_OPEN_STATES)}];\n"
    f"  const closedish = [{', '.join(repr(s) for s in DOOR_CLOSED_STATES)}];\n"
    "  const s = String(st.state).toLowerCase();\n"
    "  if (openish.includes(s)) return invert ? false : true;\n"
    "  if (closedish.includes(s)) return invert ? true : false;\n"
    "  return false;\n"
    "};\n"
)


def open_icon_js(sensor: str, *, invert: bool = False, name: str = "Garage") -> str:
    icon_open = door_icon(name, open_icon=True)
    icon_closed = door_icon(name, open_icon=False)
    return (
        "[[[\n"
        + IS_DOOR_OPEN_JS
        + f"  const st = states['{sensor}'];\n"
        f"  const open = isDoorOpen(st, {str(invert).lower()});\n"
        f"  if (open) return '{icon_open}';\n"
        f"  if (open === false) return '{icon_closed}';\n"
        "  return 'mdi:help-circle-outline';\n"
        "]]]"
    )


def open_label_js(sensor: str, *, invert: bool = False) -> str:
    return (
        "[[[\n"
        + IS_DOOR_OPEN_JS
        + f"  const st = states['{sensor}'];\n"
        f"  const open = isDoorOpen(st, {str(invert).lower()});\n"
        "  if (open === true) return 'Open';\n"
        "  if (open === false) return 'Closed';\n"
        "  return '—';\n"
        "]]]"
    )


def open_color_js(sensor: str, *, invert: bool = False) -> str:
    return (
        "[[[\n"
        + IS_DOOR_OPEN_JS
        + f"  const st = states['{sensor}'];\n"
        f"  const open = isDoorOpen(st, {str(invert).lower()});\n"
        "  if (open === true) return '#F2B8B5';\n"
        "  if (open === false) return '#81C784';\n"
        "  return '#938F99';\n"
        "]]]"
    )


def door_open_state_js(*, invert: bool = False) -> str:
    """Button-card state operator — card must set entity to the door sensor."""
    return (
        "[[[\n"
        + IS_DOOR_OPEN_JS
        + f"  return isDoorOpen(entity, {str(invert).lower()});\n"
        "]]]"
    )


def indicator_from_door(door: dict) -> dict:
    name = door["name"]
    is_shed = "shed" in name.lower()
    return {
        "entity": door["sensor"],
        "name": name,
        "invert": door.get("invert", False),
        "icon": "mdi:warehouse-open" if is_shed else "mdi:garage-open",
        "icon_closed": "mdi:warehouse" if is_shed else "mdi:garage",
        "color_on": "#F2B8B5",
        "color_off": "#81C784",
    }

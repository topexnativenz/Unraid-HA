"""Flux UI visual layout builders — ElementZoom reference patterns."""

from __future__ import annotations

import sys
from pathlib import Path

from flux_navbar import room_navigation_path
from md3_templates import wrap_glass, wrap_title

GARAGE_DIR = Path(__file__).resolve().parents[2] / "garage-doors"
sys.path.insert(0, str(GARAGE_DIR))

from garage_ui_helpers import IS_DOOR_OPEN_JS  # noqa: E402

_LIGHT_LABEL = (
    "[[[\n"
    "  if (entity.state !== 'on') return 'Off';\n"
    "  const b = entity.attributes.brightness;\n"
    "  return b != null ? Math.round(b / 255 * 100) + '%' : 'On';\n"
    "]]]"
)


def _title(title: str, subtitle: str = "") -> dict:
    card: dict = {
        "type": "custom:mushroom-title-card",
        "title": title,
        "grid_options": {"columns": 12},
    }
    if subtitle:
        card["subtitle"] = subtitle
    return wrap_title(card)


def _room_tile_grid(rooms: list[dict]) -> dict:
    """Inner 2-column grid for room index cards."""
    return {
        "type": "grid",
        "columns": 2,
        "square": False,
        "cards": [flux_room_tile(room, columns=6) for room in rooms],
        "grid_options": {"columns": 12},
    }


def build_rooms_index_section(rooms: list[dict]) -> dict:
    """Rooms index — reference: large 2-col room cards with status strip."""
    return {
        "type": "grid",
        "cards": [
            _title("Rooms", "Choose an area"),
            wrap_glass(_room_tile_grid(rooms)),
        ],
    }


_ROOM_BG_ICON = (
    "[[[\n"
    "  const icon = variables.room_icon || 'mdi:home-outline';\n"
    "  return `<ha-icon icon=\"${icon}\" style=\"width:68px;height:68px;opacity:0.22;color:var(--md-sys-color-on-surface);\"></ha-icon>`;\n"
    "]]]"
)


SENSOR_SLOT_COUNT = 4


def _sensor_slots(room: dict) -> list[dict]:
    """Build exactly 4 right-column sensor slots; pad with stubs when unconfigured."""
    slots: list[dict] = [dict(item) for item in (room.get("indicators") or [])[:SENSOR_SLOT_COUNT]]
    while len(slots) < SENSOR_SLOT_COUNT:
        slots.append({"stub": True})
    return slots


def _find_sensor_js(kind: str) -> str:
    var = "tempId" if kind == "temp" else "humidId"
    explicit = "variables.temperature_entity" if kind == "temp" else "variables.humidity_entity"
    dc = "temperature" if kind == "temp" else "humidity"
    suffix = "°C" if kind == "temp" else "%"
    return (
        f"  let {var} = {explicit};\n"
        f"  if (!{var} || !states[{var}] || ['unavailable','unknown'].includes(states[{var}].state)) {{\n"
        f"    const keywords = (variables.keywords || []).map(k => k.toLowerCase());\n"
        f"    for (const [eid, st] of Object.entries(states)) {{\n"
        f"      if (!eid.startsWith('sensor.')) continue;\n"
        f"      const cls = st.attributes?.device_class || '';\n"
        f"      const hay = (eid + ' ' + (st.attributes?.friendly_name || '')).toLowerCase();\n"
        f"      if (cls !== '{dc}' && !hay.includes('{dc}')) continue;\n"
        f"      if (keywords.some(k => hay.includes(k))) {{ {var} = eid; break; }}\n"
        f"    }}\n"
        f"  }}\n"
        f"  if ({var} && states[{var}] && !['unavailable','unknown'].includes(states[{var}].state)) {{\n"
        f"    const v = parseFloat(states[{var}].state);\n"
        f"    parts.push(Number.isFinite(v) ? v.toFixed(1) + '{suffix}' : states[{var}].state + '{suffix}');\n"
        f"  }}\n"
    )


_ROOM_SUBTITLE_JS = (
    "  const parts = [];\n"
    + _find_sensor_js("temp")
    + _find_sensor_js("humid")
    + "  const sub = parts.length ? parts.join(' / ') : (variables.subtitle || '');\n"
)

_ROOM_INFO_HTML = (
    "[[[\n"
    "  const title = variables.card_name || '';\n"
    + _ROOM_SUBTITLE_JS
    + "  return `\n"
    "    <div style=\"position:relative;z-index:2;text-align:left;line-height:1.2;max-width:100%;\">\n"
    "      <div style=\"font-weight:700;font-size:15px;color:var(--md-sys-color-on-surface);word-break:break-word;\">${title}</div>\n"
    "      <div style=\"font-size:11px;color:var(--md-sys-color-on-surface-variant);margin-top:2px;word-break:break-word;\">${sub}</div>\n"
    "    </div>`;\n"
    "]]]"
)


def flux_room_tile(room: dict, *, columns: int = 6) -> dict:
    """Reference room card: name top-left, large bg icon bottom-left, 4 sensor slots right."""
    lights = [light["entity"] for light in room.get("lights", [])]
    slots = _sensor_slots(room)

    triggers = list(lights)
    for key in ("temperature_entity", "humidity_entity"):
        entity = room.get(key)
        if entity and entity not in triggers:
            triggers.append(entity)
    for item in slots:
        entity = item.get("entity")
        if entity and entity not in triggers:
            triggers.append(entity)

    room_icon = room.get("icon", "mdi:home-outline")
    card_name = room.get("card_name") or room["name"]
    card: dict = {
        "type": "custom:button-card",
        "template": "flux_room",
        "show_icon": False,
        "variables": {
            "card_name": card_name,
            "subtitle": room.get("subtitle", ""),
            "keywords": room.get("keywords") or [],
            "lights": lights,
            "sensor_slots": slots,
            "room_icon": room_icon,
            "temperature_entity": room.get("temperature_entity"),
            "humidity_entity": room.get("humidity_entity"),
        },
        "custom_fields": {
            "bg": _ROOM_BG_ICON,
            "info": _ROOM_INFO_HTML,
            "sensors": _ROOM_SENSOR_COLUMN,
        },
        "tap_action": {"action": "navigate", "navigation_path": room_navigation_path(room["path"])},
        "grid_options": {"columns": columns},
    }
    if triggers:
        card["triggers_update"] = triggers
    else:
        card["triggers_update"] = "all"
    return card


_ROOM_LABEL = (
    "[[[\n"
    "  const parts = [];\n"
    + _find_sensor_js("temp")
    + _find_sensor_js("humid")
    + "  if (parts.length) return parts.join(' / ');\n"
    "  return variables.subtitle || '';\n"
    "]]]"
)

_ROOM_SENSOR_COLUMN = (
    "[[[\n"
    + IS_DOOR_OPEN_JS
    + "  const slots = variables.sensor_slots || [];\n"
    "  const pill = (inner) => `\n"
    "    <div style=\"width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;\">${inner}</div>`;\n"
    "  const stub = () => pill(`\n"
    "    <div style=\"width:26px;height:26px;border-radius:50%;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;\">\n"
    "      <div style=\"width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,0.14)\"></div>\n"
    "    </div>`);\n"
    "  const iconFor = (eid, st, item, open) => {\n"
    "    if (item.icon && open) return item.icon;\n"
    "    if (item.icon_closed && !open) return item.icon_closed;\n"
    "    if (!eid || !st) return 'mdi:circle-small';\n"
    "    const dc = st.attributes?.device_class || '';\n"
    "    if (eid.startsWith('binary_sensor.')) {\n"
    "      if (['motion','occupancy','presence'].includes(dc) || eid.includes('motion')) {\n"
    "        return open ? 'mdi:motion-sensor' : 'mdi:motion-sensor-off';\n"
    "      }\n"
    "      if (['door','garage_door','opening','window'].includes(dc) || eid.includes('door') || eid.includes('contact') || eid.includes('garage')) {\n"
    "        return open ? (item.icon || 'mdi:garage-open') : (item.icon_closed || 'mdi:garage');\n"
    "      }\n"
    "      return open ? 'mdi:checkbox-marked-circle' : 'mdi:checkbox-blank-circle-outline';\n"
    "    }\n"
    "    if (eid.startsWith('light.')) return open ? 'mdi:lightbulb-on' : 'mdi:lightbulb-outline';\n"
    "    if (eid.startsWith('sensor.')) {\n"
    "      if (dc === 'temperature' || eid.includes('temp')) return 'mdi:thermometer';\n"
    "      if (dc === 'humidity' || eid.includes('humid')) return 'mdi:water-percent';\n"
    "    }\n"
    "    return 'mdi:circle-small';\n"
    "  };\n"
    "  const isOpenState = (eid, st, item) => {\n"
    "    if (!eid || !st || ['unavailable','unknown'].includes(st.state)) return null;\n"
    "    const dc = st.attributes?.device_class || '';\n"
    "    const isDoor = eid.startsWith('binary_sensor.') && (\n"
    "      ['door','garage_door','opening','window'].includes(dc) || eid.includes('door') || eid.includes('contact') || eid.includes('garage') || eid.includes('shed')\n"
    "    );\n"
    "    if (isDoor) return isDoorOpen(st, !!item.invert);\n"
    "    if (item.invert) return !['on','open','home'].includes(st.state);\n"
    "    if (eid.startsWith('light.')) return st.state === 'on';\n"
    "    if (eid.startsWith('binary_sensor.')) return ['on','open','home','detected'].includes(String(st.state).toLowerCase());\n"
    "    if (eid.startsWith('sensor.')) return st.state !== '' && st.state !== '0';\n"
    "    return ['on','open','home'].includes(String(st.state).toLowerCase());\n"
    "  };\n"
    "  const styleFor = (item, eid, st) => {\n"
    "    if (item.stub || !eid || !st || ['unavailable','unknown'].includes(st.state)) {\n"
    "      return { bg: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', fg: 'rgba(255,255,255,0.2)', glow: '', open: false };\n"
    "    }\n"
    "    const dc = st.attributes?.device_class || '';\n"
    "    const open = isOpenState(eid, st, item);\n"
    "    const isDoor = eid.startsWith('binary_sensor.') && (\n"
    "      ['door','garage_door','opening','window'].includes(dc) || eid.includes('door') || eid.includes('contact') || eid.includes('garage')\n"
    "    );\n"
    "    const isMotion = eid.startsWith('binary_sensor.') && (\n"
    "      ['motion','occupancy','presence'].includes(dc) || eid.includes('motion')\n"
    "    );\n"
    "    const isLight = eid.startsWith('light.');\n"
    "    const isClimate = eid.startsWith('sensor.') && (dc === 'temperature' || dc === 'humidity' || eid.includes('temp') || eid.includes('humid'));\n"
    "    if (isDoor) {\n"
    "      if (open) {\n"
    "        return { bg: item.color_on || '#F2B8B5', border: 'none', fg: '#3b1216', glow: 'box-shadow:0 0 10px rgba(242,184,181,0.55);', open: true };\n"
    "      }\n"
    "      return { bg: item.color_off || '#81C784', border: 'none', fg: '#0d2818', glow: 'box-shadow:0 0 8px rgba(129,199,132,0.35);', open: false };\n"
    "    }\n"
    "    if (isMotion) {\n"
    "      if (open) {\n"
    "        return { bg: item.color_on || '#B388FF', border: 'none', fg: '#1c1028', glow: 'box-shadow:0 0 10px rgba(179,136,255,0.5);', open: true };\n"
    "      }\n"
    "      return { bg: item.color_off || 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.14)', fg: 'rgba(255,255,255,0.35)', glow: '', open: false };\n"
    "    }\n"
    "    if (isLight) {\n"
    "      if (open) {\n"
    "        return { bg: item.color_on || '#FFD54F', border: 'none', fg: '#1c1b1f', glow: 'box-shadow:0 0 10px rgba(255,213,79,0.45);', open: true };\n"
    "      }\n"
    "      return { bg: item.color_off || 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.14)', fg: 'rgba(255,255,255,0.35)', glow: '', open: false };\n"
    "    }\n"
    "    if (isClimate) {\n"
    "      const hue = dc === 'humidity' || eid.includes('humid') ? '#81C784' : '#80DEEA';\n"
    "      return { bg: item.color_on || hue, border: 'none', fg: '#1c1b1f', glow: 'box-shadow:0 0 8px rgba(128,222,234,0.35);', open: true };\n"
    "    }\n"
    "    if (open) {\n"
    "      return { bg: item.color_on || '#FFD54F', border: 'none', fg: '#1c1b1f', glow: '', open: true };\n"
    "    }\n"
    "    return { bg: item.color_off || 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.14)', fg: 'rgba(255,255,255,0.35)', glow: '', open: false };\n"
    "  };\n"
    "  const cells = slots.slice(0, 4).map(item => {\n"
    "    if (item.stub || !item.entity) return stub();\n"
    "    const st = states[item.entity];\n"
    "    const style = styleFor(item, item.entity, st);\n"
    "    const icon = iconFor(item.entity, st, item, style.open);\n"
    "    return `\n"
    "      <div style=\"width:26px;height:26px;border-radius:50%;background:${style.bg};border:${style.border};${style.glow}display:flex;align-items:center;justify-content:center;\">\n"
    "        <ha-icon icon=\"${icon}\" style=\"width:14px;height:14px;color:${style.fg};\"></ha-icon>\n"
    "      </div>`;\n"
    "  });\n"
    "  while (cells.length < 4) cells.push(stub());\n"
    "  return `<div style=\"display:flex;flex-direction:column;align-items:center;justify-content:space-between;height:100%;min-height:118px;width:100%;box-sizing:border-box;padding:2px 0;\">${cells.join('')}</div>`;\n"
    "]]]"
)


def flux_light_tile(entity: str, name: str, *, columns: int = 6) -> dict:
    """Reference room-detail light tile: icon, name, Off/On status — 2-col grid."""
    return {
        "type": "custom:button-card",
        "template": "flux_light",
        "entity": entity,
        "name": name,
        "icon": "mdi:lightbulb",
        "label": _LIGHT_LABEL,
        "tap_action": {"action": "toggle"},
        "hold_action": {"action": "more-info"},
        "grid_options": {"columns": columns},
    }


def flux_light_auto_entities_options(*, columns: int = 6) -> dict:
    """Active-now tiles in the same Flux reference style."""
    return {
        "type": "custom:button-card",
        "template": "flux_light",
        "icon": "mdi:lightbulb",
        "label": _LIGHT_LABEL,
        "tap_action": {"action": "toggle"},
        "hold_action": {"action": "more-info"},
        "grid_options": {"columns": columns},
    }


def _lights_tile_grid(lights: list[dict]) -> dict:
    """Inner 2-column grid — same structure as Active now auto-entities card."""
    return {
        "type": "grid",
        "columns": 2,
        "square": False,
        "cards": [flux_light_tile(item["entity"], item["name"], columns=6) for item in lights],
        "grid_options": {"columns": 12},
    }


def build_lights_grid_section(title: str, subtitle: str, lights: list[dict]) -> dict:
    """2-column light grid matching Flux room detail / Active now layout."""
    return {
        "type": "grid",
        "cards": [
            _title(title, subtitle),
            wrap_glass(_lights_tile_grid(lights)),
        ],
    }


def build_room_status_chips(room: dict) -> dict | None:
    """Optional status chip row (Occupied, climate, etc.) from rooms.yaml."""
    chips_cfg = room.get("status_chips") or []
    if not chips_cfg:
        return None
    chips: list[dict] = []
    for chip in chips_cfg:
        entry: dict = {
            "type": "template",
            "icon": chip.get("icon", "mdi:information-outline"),
            "content": chip["content"],
        }
        if chip.get("icon_color"):
            entry["icon_color"] = chip["icon_color"]
        if chip.get("entity"):
            entry["entity"] = chip["entity"]
        chips.append(entry)
    return wrap_glass(
        {
            "type": "custom:mushroom-chips-card",
            "alignment": "start",
            "chips": chips,
            "grid_options": {"columns": 12},
        }
    )


def build_room_lights_section(room: dict) -> dict:
    """Room detail lights block — reference: titled 2-col grid of toggle tiles."""
    lights = room.get("lights", [])
    return {
        "type": "grid",
        "cards": [
            _title("Lights", ""),
            wrap_glass(_lights_tile_grid(lights)),
        ],
    }

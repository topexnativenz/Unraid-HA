"""Flux UI visual layout builders — ElementZoom reference patterns."""

from __future__ import annotations

from md3_templates import wrap_glass, wrap_title

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


def flux_room_tile(room: dict, *, columns: int = 6) -> dict:
    """Reference room card: icon, name, temp/humidity label, status dots on right."""
    lights = [light["entity"] for light in room.get("lights", [])]
    indicators = room.get("indicators")
    if not indicators:
        indicators = [{"entity": entity} for entity in lights[:6]]

    triggers = list(lights)
    for key in ("temperature_entity", "humidity_entity"):
        entity = room.get(key)
        if entity and entity not in triggers:
            triggers.append(entity)
    for item in indicators:
        entity = item.get("entity")
        if entity and entity not in triggers:
            triggers.append(entity)

    card: dict = {
        "type": "custom:button-card",
        "template": "flux_room",
        "name": room["name"],
        "icon": room.get("icon", "mdi:home-outline"),
        "label": _ROOM_LABEL,
        "variables": {
            "subtitle": room.get("subtitle", ""),
            "lights": lights,
            "indicators": indicators,
            "temperature_entity": room.get("temperature_entity"),
            "humidity_entity": room.get("humidity_entity"),
        },
        "custom_fields": {"status": _ROOM_STATUS_HTML},
        "tap_action": {"action": "navigate", "navigation_path": f"/flux-ui/room/{room['path']}"},
        "grid_options": {"columns": columns},
    }
    if lights:
        card["entity"] = lights[0]
    if triggers:
        card["triggers_update"] = triggers
    return card


_ROOM_LABEL = (
    "[[[\n"
    "  const t = variables.temperature_entity;\n"
    "  const h = variables.humidity_entity;\n"
    "  const parts = [];\n"
    "  if (t && states[t] && !['unavailable', 'unknown'].includes(states[t].state)) {\n"
    "    const v = parseFloat(states[t].state);\n"
    "    parts.push(Number.isFinite(v) ? v.toFixed(1) + '°C' : states[t].state + '°C');\n"
    "  }\n"
    "  if (h && states[h] && !['unavailable', 'unknown'].includes(states[h].state)) {\n"
    "    const v = parseFloat(states[h].state);\n"
    "    parts.push(Number.isFinite(v) ? v.toFixed(1) + '%' : states[h].state + '%');\n"
    "  }\n"
    "  if (parts.length) return parts.join(' · ');\n"
    "  return variables.subtitle || '';\n"
    "]]]"
)

_ROOM_STATUS_HTML = (
    "[[[\n"
    "  const items = variables.indicators || [];\n"
    "  if (!items.length) return '';\n"
    "  const dots = items.slice(0, 6).map(item => {\n"
    "    const st = states[item.entity];\n"
    "    const on = st && ['on', 'home', 'open'].includes(st.state);\n"
    "    const color = on ? (item.color_on || '#FFD54F') : 'rgba(255,255,255,0.14)';\n"
    "    const glow = on ? 'box-shadow:0 0 8px rgba(255,213,79,0.45);' : '';\n"
    "    return `<div style=\"width:8px;height:8px;border-radius:50%;background:${color};margin:5px 0;${glow}\"></div>`;\n"
    "  }).join('');\n"
    "  return `<div style=\"display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%\">${dots}</div>`;\n"
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

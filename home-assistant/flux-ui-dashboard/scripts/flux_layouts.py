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


def build_lights_grid_section(title: str, subtitle: str, lights: list[dict]) -> dict:
    """2-column light grid matching Flux room detail / presets layout."""
    cards: list[dict] = [_title(title, subtitle)]
    cards.extend(flux_light_tile(item["entity"], item["name"], columns=6) for item in lights)
    return {"type": "grid", "cards": cards}


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
    cards: list[dict] = [_title("Lights", "")]
    cards.extend(
        flux_light_tile(light["entity"], light["name"], columns=6)
        for light in room.get("lights", [])
    )
    return {"type": "grid", "cards": cards}

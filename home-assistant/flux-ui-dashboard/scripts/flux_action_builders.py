"""Quick-action button-card builders shared by overview and tab panels."""

from __future__ import annotations

from flux_door_builders import flux_door_tile


def lock_action(entity: str, name: str, *, columns: int = 6) -> dict:
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "entity": entity,
        "name": name,
        "icon": "mdi:gate",
        "label": "[[[ return entity.state === 'locked' ? 'Locked' : 'Unlocked'; ]]]",
        "tap_action": {"action": "toggle"},
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

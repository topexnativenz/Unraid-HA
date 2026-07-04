"""Phase 3 — context-aware overview sections (Flux home intelligence)."""

from __future__ import annotations

from md3_templates import FLUX_LIGHTS_LIST_MOD, wrap_flux_light_card, wrap_glass, wrap_title


def _title(title: str, subtitle: str = "") -> dict:
    card: dict = {
        "type": "custom:mushroom-title-card",
        "title": title,
        "grid_options": {"columns": 12},
    }
    if subtitle:
        card["subtitle"] = subtitle
    return wrap_title(card)


def _jinja_lights_chip(lights_entity: str) -> tuple[str, str]:
    """Return (content, icon_color) Jinja templates for lights status chip."""
    content = (
        "{% set n = states.light | selectattr('state', 'eq', 'on') | list | count %}\n"
        "{% if n > 0 %}\n"
        "{{ n }} light{% if n != 1 %}s{% endif %} on\n"
        "{% else %}\n"
        "Lights off\n"
        "{% endif %}"
    )
    icon_color = (
        "{% set n = states.light | selectattr('state', 'eq', 'on') | list | count %}\n"
        "{% if n > 0 %}amber{% else %}disabled{% endif %}"
    )
    return content, icon_color


def _jinja_garage_chip(sensors: list[str]) -> tuple[str, str]:
    """Return (content, icon_color) Jinja templates for garage status chip."""
    if not sensors:
        return "Garage closed", "disabled"
    parts = " + ".join(f"(1 if is_state('{s}', 'on') else 0)" for s in sensors)
    content = (
        f"{{% set open = {parts} %}}\n"
        "{% if open > 0 %}\n"
        "{{ open }} door{% if open != 1 %}s{% endif %} open\n"
        "{% else %}\n"
        "Garage closed\n"
        "{% endif %}"
    )
    icon_color = (
        f"{{% set open = {parts} %}}\n"
        "{% if open > 0 %}red{% else %}green{% endif %}"
    )
    return content, icon_color


def build_home_status_section(cfg: dict) -> dict:
    """Status chips: lights on + open garage doors (always visible, counts update live)."""
    hs = cfg.get("context", {}).get("home_status", {})
    lights_entity = hs.get("lights_on", "light.all_lights")
    garage = cfg.get("quick_actions", {}).get("garage", [])

    lights_content, lights_color = _jinja_lights_chip(lights_entity)
    chips: list[dict] = [
        {
            "type": "template",
            "entity": lights_entity,
            "icon": "mdi:lightbulb-on",
            "icon_color": lights_color,
            "content": lights_content,
            "tap_action": {"action": "navigate", "navigation_path": "/flux-ui/lights"},
        },
    ]

    if garage:
        sensors = [d["sensor"] for d in garage]
        garage_content, garage_color = _jinja_garage_chip(sensors)
        chips.append(
            {
                "type": "template",
                "icon": "mdi:garage-alert",
                "icon_color": garage_color,
                "content": garage_content,
            }
        )

    return {
        "type": "grid",
        "cards": [
            _title("Home status", "Live"),
            wrap_glass(
                {
                    "type": "custom:mushroom-chips-card",
                    "alignment": "start",
                    "chips": chips,
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }


def _flux_slim_light_card(*, entity: str | None = None, name: str | None = None, columns: int = 12) -> dict:
    """Single-row dimmer: icon, name, and slider in one sleek MD3 pill."""
    card: dict = {
        "type": "custom:mushroom-light-card",
        "fill_container": True,
        "layout": "horizontal",
        "show_brightness_control": True,
        "show_color_control": False,
        "collapsible_controls": False,
        "use_light_color": True,
        "grid_options": {"columns": columns},
    }
    if entity:
        card["entity"] = entity
    if name:
        card["name"] = name
    return wrap_flux_light_card(card)


def light_control_tile(entity: str, name: str, *, columns: int = 12) -> dict:
    """Whole card is the dimmer — tap toggles, drag slider to dim."""
    return _flux_slim_light_card(entity=entity, name=name, columns=columns)


def build_lights_list_section(title: str, subtitle: str, lights: list[dict]) -> dict:
    """Single-column stack of fixed-height dimmer rows (no staggered 2-col grid)."""
    rows = [light_control_tile(item["entity"], item["name"]) for item in lights]
    return {
        "type": "grid",
        "cards": [
            _title(title, subtitle),
            {
                "type": "grid",
                "columns": 1,
                "square": False,
                "cards": rows,
                "grid_options": {"columns": 12},
                "card_mod": FLUX_LIGHTS_LIST_MOD,
            },
        ],
    }


def light_control_auto_entities_options() -> dict:
    """auto-entities: slim dimmer row per light (entity/name injected per match)."""
    return _flux_slim_light_card(columns=12)


def build_active_lights_section(cfg: dict) -> dict:
    """auto-entities: only lights that are on (section hidden when empty)."""
    active = cfg.get("context", {}).get("active_lights", {})
    domain = active.get("domain", "light")
    state = active.get("state", "on")
    exclude = active.get("exclude", [])

    filter_include: dict = {
        "domain": domain,
        "state": state,
        "options": light_control_auto_entities_options(),
    }

    card: dict = {
        "type": "custom:auto-entities",
        "card": {
            "type": "grid",
            "square": False,
            "columns": 1,
        },
        "card_param": "cards",
        "show_empty": False,
        "filter": {
            "include": [filter_include],
            "exclude": [{"entity_id": e} for e in exclude],
        },
        "sort": {"method": "friendly_name"},
    }

    return {
        "type": "grid",
        "cards": [
            _title("Active now", "Lights on"),
            wrap_glass({**card, "grid_options": {"columns": 12}}),
        ],
    }


def build_open_garage_section(cfg: dict) -> dict | None:
    """Conditional section when any garage door contact is open."""
    garage = cfg.get("quick_actions", {}).get("garage", [])
    if not garage:
        return None

    checks = " or ".join(f"is_state('{d['sensor']}', 'on')" for d in garage)
    cards = [_title("Doors open", "Check before leaving")]
    for door in garage:
        sensor = door["sensor"]
        cards.append(
            {
                "type": "custom:button-card",
                "template": "flux_action",
                "entity": sensor,
                "name": door["name"],
                "icon": "mdi:garage-open",
                "label": "Open",
                "styles": {"icon": [{"color": "#F2B8B5"}]},
                "tap_action": {
                    "action": "call-service",
                    "service": "script.turn_on",
                    "service_data": {"entity_id": door["script"]},
                },
                "grid_options": {"columns": 6},
            }
        )

    return {
        "type": "grid",
        "cards": [
            {
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "template",
                        "value_template": f"{{{{ {checks} }}}}",
                    }
                ],
                "card": {"type": "grid", "cards": cards},
            }
        ],
    }


def bubble_popup_card(entity: str, name: str) -> dict:
    """Bubble pop-up with mushroom light slider (Flux-style)."""
    slug = entity.replace(".", "-")
    return {
        "type": "custom:bubble-card",
        "card_type": "pop-up",
        "hash": f"#light-{slug}",
        "name": name,
        "icon": "mdi:lightbulb",
        "entity": entity,
        "button_type": "name",
        "bg_blur": "14",
        "bg_opacity": "88",
        "styles": (
            "#root { max-height: 100% !important; }\n"
            ".bubble-pop-up-container { padding-bottom: 48px !important; }\n"
        ),
        "cards": [
            {
                "type": "custom:mushroom-light-card",
                "entity": entity,
                "name": name,
                "fill_container": True,
                "show_brightness_control": True,
                "show_color_control": True,
                "collapsible_controls": False,
                "use_light_color": True,
            }
        ],
    }


def light_tile_bubble(entity: str, name: str, *, columns: int = 6) -> dict:
    slug = entity.replace(".", "-")
    return {
        "type": "custom:button-card",
        "template": "flux_light",
        "entity": entity,
        "name": name,
        "icon": "mdi:lightbulb",
        "label": (
            "[[[\n"
            "  if (entity.state !== 'on') return 'Off';\n"
            "  const b = entity.attributes.brightness;\n"
            "  return b != null ? Math.round(b / 255 * 100) + '%' : 'On';\n"
            "]]]"
        ),
        "tap_action": {"action": "navigate", "navigation_path": f"#light-{slug}"},
        "hold_action": {"action": "toggle"},
        "grid_options": {"columns": columns},
    }


def build_bubble_popups_section(lights: list[dict]) -> dict:
    """Hidden pop-up anchors (triggered by light tile hash navigation)."""
    cards = [bubble_popup_card(item["entity"], item["name"]) for item in lights]
    return {
        "type": "grid",
        "cards": cards,
    }


def collect_bubble_lights(cfg: dict) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in cfg.get("favourite_lights", []):
        if item["entity"] not in seen:
            seen.add(item["entity"])
            out.append(item)
    for room in cfg.get("rooms", []):
        for light in room.get("lights", []):
            if light["entity"] not in seen:
                seen.add(light["entity"])
                out.append(light)
    return out

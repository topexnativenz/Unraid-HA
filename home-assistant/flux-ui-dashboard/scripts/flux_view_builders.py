"""Flux UI full-page view builders — Scenes, Lights, Cameras, room subviews."""

from __future__ import annotations

from flux_layouts import (
    _title,
    build_lights_grid_section,
    flux_light_tile,
)
from flux_navbar import URL_PREFIX
from md3_templates import wrap_glass, wrap_title


def scene_action_card(
    name: str,
    subtitle: str,
    icon: str,
    service: str,
    target: str,
    *,
    columns: int = 6,
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


def ha_scene_card(scene: dict, *, columns: int = 6) -> dict:
    entity = scene["entity"]
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "entity": entity,
        "name": scene.get("name") or entity.split(".", 1)[-1].replace("_", " ").title(),
        "icon": scene.get("icon", "mdi:palette"),
        "label": "Tap to activate",
        "tap_action": {
            "action": "perform-action",
            "perform_action": "scene.turn_on",
            "target": {"entity_id": entity},
        },
        "grid_options": {"columns": columns},
    }


def section_title(title: str, subtitle: str = "", *, compact: bool = False) -> dict:
    card: dict = {
        "type": "custom:mushroom-title-card",
        "title": title,
        "grid_options": {"columns": 12},
    }
    if subtitle:
        card["subtitle"] = subtitle
    return wrap_title(card)


def build_scenes_view(cfg: dict, *, use_auto_entities: bool = True) -> dict:
    """Scenes tab — quick scripts + configured HA scenes + optional auto-discovery."""
    cards: list[dict] = [section_title("Scenes", "Ambience and quick lighting")]

    cards.append(section_title("Quick actions", "Scripts and master switches", compact=True))
    for item in cfg["quick_actions"]["actions"]:
        cards.append(
            scene_action_card(
                item["name"],
                item["subtitle"],
                item["icon"],
                item["service"],
                item["target"],
            )
        )
    cards.append(
        scene_action_card(
            "All lights",
            "Toggle whole home",
            "mdi:lightbulb-group",
            "homeassistant.toggle",
            "light.all_lights",
        )
    )

    scenes_cfg = cfg.get("scenes_config") or {}
    manual = scenes_cfg.get("scenes") or []
    manual_ids = {s["entity"] for s in manual if s.get("entity")}
    if manual:
        cards.append(section_title("Home Assistant scenes", "Saved scenes", compact=True))
        for scene in manual:
            cards.append(ha_scene_card(scene))

    if use_auto_entities and scenes_cfg.get("auto_discover", True):
        exclude = [{"entity_id": eid} for eid in sorted(manual_ids)]
        cards.append(section_title("Discovered scenes", "All scene entities", compact=True))
        cards.append(
            wrap_glass(
                {
                    "type": "custom:auto-entities",
                    "card": {
                        "type": "grid",
                        "columns": 2,
                        "square": False,
                    },
                    "card_param": "cards",
                    "filter": {
                        "include": [
                            {
                                "domain": "scene",
                                "options": {
                                    "type": "custom:button-card",
                                    "template": "flux_action",
                                    "icon": "mdi:palette",
                                    "label": "Tap to activate",
                                    "tap_action": {
                                        "action": "call-service",
                                        "service": "scene.turn_on",
                                    },
                                    "grid_options": {"columns": 6},
                                },
                            }
                        ],
                        "exclude": exclude,
                    },
                    "sort": {"method": "friendly_name"},
                    "grid_options": {"columns": 12},
                }
            )
        )

    return {"type": "grid", "cards": cards}


def build_lights_view(cfg: dict, *, use_auto_entities: bool = True) -> dict:
    """Lights tab — active now, favourites, per-room groups, extra light groups."""
    cards: list[dict] = []

    if use_auto_entities:
        from phase3_builders import build_active_lights_section

        cards.extend(build_active_lights_section(cfg)["cards"])

    cards.extend(
        build_lights_grid_section("Favourite lights", "Most used", cfg["favourite_lights"])["cards"]
    )

    seen: set[str] = set()
    for room in cfg.get("rooms", []):
        lights = room.get("lights") or []
        if not lights:
            continue
        title = room.get("card_name") or room["name"]
        subtitle = room.get("subtitle", "")
        cards.extend(build_lights_grid_section(title, subtitle, lights)["cards"])
        for light in lights:
            seen.add(light["entity"])

    for group in cfg.get("light_groups") or []:
        lights = [item for item in group.get("lights", []) if item.get("entity") not in seen]
        if not lights:
            continue
        cards.extend(
            build_lights_grid_section(
                group["name"],
                group.get("subtitle", ""),
                lights,
            )["cards"]
        )

    if not cards:
        cards.append(section_title("Lights", "No lights configured"))
    return {"type": "grid", "cards": cards}


def _full_width(card: dict) -> dict:
    card = dict(card)
    card["grid_options"] = {"columns": 12}
    return card


def _camera_card(camera: dict) -> dict:
    """Live picture-glance — used on room Camera subviews only."""
    entity = camera["entity"]
    name = camera.get("name") or entity.split(".", 1)[-1].replace("_", " ").title()
    return wrap_glass(
        {
            "type": "picture-glance",
            "title": name,
            "entities": [],
            "camera_image": entity,
            "camera_view": "live",
            "show_state": False,
            "tap_action": {"action": "more-info"},
        }
    )


# Same outdoor set as tablet 16:9 overview (`entities.yaml` → tablet.overview_cameras).
FLUX_OVERVIEW_CAMERA_ORDER = (
    "camera.back_courtyard_fluent",
    "camera.side_door",
    "camera.side_of_house",
    "camera.garage_door",
)


def curated_flux_cameras(cfg: dict) -> list[dict]:
    """Reolink Back Courtyard + Eufy Driveway / Side of House / Garage Door."""
    tablet = cfg.get("tablet") or {}
    curated = [c for c in (tablet.get("overview_cameras") or []) if c.get("entity")]
    if curated:
        return curated[:4]

    cameras_cfg = cfg.get("cameras_config") or {}
    by_id = {
        c["entity"]: c
        for c in (cameras_cfg.get("cameras") or [])
        if c.get("entity")
    }
    ordered = [by_id[eid] for eid in FLUX_OVERVIEW_CAMERA_ORDER if eid in by_id]
    if ordered:
        return ordered[:4]
    return list(cameras_cfg.get("cameras") or [])[:4]


def _cameras_tab_tile_mod(tile: dict) -> dict:
    """16:9 still tiles on the Cameras tab (overview mid-grid stays square)."""
    tile = dict(tile)
    styles = dict(tile.get("styles") or {})
    card_styles = list(styles.get("card") or [])
    card_styles.extend(
        [
            {"aspect-ratio": "16 / 9"},
            {"min-height": "160px"},
        ]
    )
    styles["card"] = card_styles
    tile["styles"] = styles
    name_styles = list((styles.get("name") or []))
    replaced = False
    for i, rule in enumerate(name_styles):
        if isinstance(rule, dict) and "font-size" in rule:
            name_styles[i] = {"font-size": "18px"}
            replaced = True
            break
    if not replaced:
        name_styles.append({"font-size": "18px"})
    styles["name"] = name_styles
    return tile


def _cameras_tab_tile(camera: dict) -> dict:
    """Branded still — Reolink opens bubble; Eufy opens wake-then-live subview."""
    from flux_tablet_eufy import build_eufy_overview_tile, build_overview_still_tile
    from flux_tablet_overview import REOLINK_CAMERA_ENTITY, REOLINK_CAMERA_HASH

    entity = camera["entity"]
    stream = (camera.get("stream") or "").strip()
    if stream:
        return build_eufy_overview_tile(camera)
    if entity == REOLINK_CAMERA_ENTITY:
        return build_overview_still_tile(camera, tap_path=REOLINK_CAMERA_HASH)
    return build_overview_still_tile(camera, tap_path=f"{URL_PREFIX}/cameras")


def build_cameras_view(
    cfg: dict,
    camera_section: dict | None = None,
    *,
    use_auto_entities: bool = True,
    apply_md3=None,
    tablet: bool = False,
) -> dict:
    """Cameras tab — same Eufy/Reolink feeds as the 16:9 overview (never Mobile Home)."""
    del camera_section, use_auto_entities, apply_md3, tablet

    from flux_tablet_overview import build_reolink_fullscreen_popup

    cameras = curated_flux_cameras(cfg)
    cards: list[dict] = [section_title("Cameras", "Eufy & Reolink")]
    if not cameras:
        cards.append(
            wrap_glass(
                {
                    "type": "markdown",
                    "content": (
                        "No cameras configured yet.\n\n"
                        "Set `tablet.overview_cameras` in `entities.yaml` "
                        "(or entries in `cameras.yaml`)."
                    ),
                    "grid_options": {"columns": 12},
                }
            )
        )
        return {"type": "grid", "cards": cards}

    for cam in cameras:
        cards.append(_full_width(_cameras_tab_tile_mod(_cameras_tab_tile(cam))))

    # Bubble lives on this view so Reolink still taps (#back-courtyard) work here too.
    cards.append(build_reolink_fullscreen_popup(cfg))
    return {"type": "grid", "cards": cards}


def cameras_for_room(cfg: dict, room_path: str) -> list[dict]:
    """Cameras assigned to a room via cameras.yaml or rooms.yaml cameras list."""
    room = next((r for r in cfg.get("rooms", []) if r.get("path") == room_path), None)
    if room and room.get("cameras"):
        return room["cameras"]

    out: list[dict] = []
    for cam in (cfg.get("cameras_config") or {}).get("cameras") or []:
        if cam.get("room") == room_path:
            out.append(cam)
    return out


def _room_header(room: dict, *, active_tab: str = "room") -> list[dict]:
    from flux_room_detail import (
        build_room_features_row,
        build_room_status_chips_auto,
        build_room_subnav,
        build_room_top_bar,
    )

    return [
        build_room_top_bar(room),
        build_room_status_chips_auto(room),
        build_room_features_row(room),
        build_room_subnav(room, active=active_tab),
    ]


def build_room_grid_page(room: dict, *, active_tab: str = "grid") -> dict:
    """Room Lights subview — dense 3-column control grid for all room lights."""
    cards: list[dict] = _room_header(room, active_tab=active_tab)

    lights = room.get("lights") or []
    if lights:
        grid_cards = [flux_light_tile(item["entity"], item["name"]) for item in lights]
        cards.append(
            _full_width(
                wrap_glass(
                    {
                        "type": "grid",
                        "columns": 3,
                        "square": False,
                        "cards": grid_cards,
                    }
                )
            )
        )
    else:
        cards.append(
            _full_width(
                wrap_glass(
                    {
                        "type": "markdown",
                        "content": "No lights configured for this room.",
                    }
                )
            )
        )

    groups = room.get("light_groups") or []
    if groups:
        cards.append(_full_width(section_title("Shortcuts", "Light groups", compact=True)))
        group_cards: list[dict] = []
        for group in groups:
            group_cards.append(
                {
                    "type": "custom:button-card",
                    "template": "flux_action",
                    "entity": group["entity"],
                    "name": group["name"],
                    "icon": group.get("icon", "mdi:lightbulb-group"),
                    "label": "[[[ return entity.state === 'on' ? 'On' : 'Off'; ]]]",
                    "tap_action": {"action": "toggle"},
                }
            )
        cards.append(
            _full_width({"type": "grid", "columns": 2, "square": False, "cards": group_cards})
        )

    return {"type": "grid", "cards": cards}


def build_room_camera_page(room: dict, cfg: dict, *, active_tab: str = "camera") -> dict:
    """Room Camera subview — picture-glance feeds for this area."""
    cards: list[dict] = _room_header(room, active_tab=active_tab)

    feeds = cameras_for_room(cfg, room["path"])
    if feeds:
        for cam in feeds:
            cards.append(_full_width(_camera_card(cam)))
    else:
        cards.append(
            _full_width(
                wrap_glass(
                    {
                        "type": "markdown",
                        "content": (
                            f"No cameras assigned to **{room.get('card_name') or room['name']}** yet.\n\n"
                            "Set `cameras:` on this room in `rooms.yaml`, or add `room: "
                            f"{room['path']}` in `cameras.yaml`."
                        ),
                    }
                )
            )
        )
        cards.append(
            _full_width(
                {
                    "type": "custom:button-card",
                    "template": "flux_action",
                    "name": "All cameras",
                    "icon": "mdi:cctv",
                    "label": "Open camera tab",
                    "tap_action": {
                        "action": "navigate",
                        "navigation_path": f"{URL_PREFIX}/cameras",
                    },
                }
            )
        )

    return {"type": "grid", "cards": cards}

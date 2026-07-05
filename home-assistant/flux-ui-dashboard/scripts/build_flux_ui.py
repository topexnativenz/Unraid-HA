#!/usr/bin/env python3
"""Build Flux UI Lovelace config — MD3 / Flux visual language."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flux_action_builders import garage_action, lock_action, scene_action
from flux_rooms_index import build_rooms_index_section
from flux_layouts import build_lights_grid_section
from flux_view_builders import (
    build_cameras_view,
    build_lights_view,
    build_room_camera_page,
    build_room_grid_page,
    build_scenes_view,
)
from flux_room_detail import build_room_detail_page
from md3_templates import (
    BUTTON_CARD_TEMPLATES,
    GLASS_CARD_MOD,
    TITLE_CARD_MOD,
    VIEW_CARD_MOD,
    wrap_glass,
    wrap_title,
)
from flux_media_player import (
    build_music_player_popup_section,
    build_navbar_media_player,
    extra_module_urls,
    media_player_active,
    write_carousel_sync_js,
)
from flux_weather_panel import build_weather_panel_section
from flux_navbar import (
    URL_PREFIX,
    navbar_section,
    room_camera_view_path,
    room_grid_view_path,
    room_view_path,
)
from kiosk_config import KIOSK_MODE
from swipe_nav_config import SWIPE_NAV
from phase3_builders import (
    build_active_lights_section,
    build_home_status_section,
    build_open_garage_section,
)
from flux_overview_tabs import (
    build_overview_tabs_section,
    build_quick_actions_tab,
    overview_tab_usage,
    tabs_enabled,
    tab_engine,
)
from flux_tab_layout import tab_section_from_grid

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
CONTEXT = ROOT / "context.yaml"
OVERVIEW_TABS = ROOT / "overview_tabs.yaml"
WEATHER_PANEL = ROOT / "weather_panel.yaml"
MEDIA_PLAYERS = ROOT / "media_players.yaml"
ROOMS = ROOT / "rooms.yaml"
ROOM_SENSORS = ROOT / "room_sensors.yaml"
SCENES = ROOT / "scenes.yaml"
CAMERAS = ROOT / "cameras.yaml"
LIGHT_GROUPS = ROOT / "light_groups.yaml"
GARAGE_DIR = ROOT.parent / "garage-doors"
sys.path.insert(0, str(GARAGE_DIR))

from garage_ui_helpers import indicator_from_door, load_garage_doors  # noqa: E402

def _sync_garage_room_indicators(rooms: list[dict], doors: list[dict]) -> None:
    """Keep garage room card indicators in sync with garage-doors/entities.yaml."""
    if not doors:
        return
    for room in rooms:
        if room.get("path") != "garage":
            continue
        door_inds = [indicator_from_door(d) for d in doors]
        light_ind = next(
            (i for i in (room.get("indicators") or []) if str(i.get("entity", "")).startswith("light.")),
            {"entity": "light.garage", "color_on": "#FFD54F", "icon": "mdi:lightbulb-on", "icon_closed": "mdi:lightbulb-outline"},
        )
        room["indicators"] = (door_inds + [light_ind])[:4]
        while len(room["indicators"]) < 4:
            room["indicators"].append({"stub": True})


def load_entities() -> dict:
    cfg = yaml.safe_load(ENTITIES.read_text())
    cfg["quick_actions"]["garage"] = load_garage_doors()
    if ROOMS.exists():
        rooms = yaml.safe_load(ROOMS.read_text()).get("rooms", [])
        _sync_garage_room_indicators(rooms, cfg["quick_actions"]["garage"])
        if ROOM_SENSORS.exists():
            overrides = yaml.safe_load(ROOM_SENSORS.read_text()).get("overrides") or {}
            merged: list[dict] = []
            for room in rooms:
                out = dict(room)
                extra = overrides.get(room["path"], {})
                for key, value in extra.items():
                    if key == "indicators" and room.get("indicators"):
                        continue
                    out[key] = value
                merged.append(out)
            cfg["rooms"] = merged
        else:
            cfg["rooms"] = rooms
    else:
        cfg["rooms"] = []
    if CONTEXT.exists():
        cfg["context"] = yaml.safe_load(CONTEXT.read_text())
    else:
        cfg["context"] = {}
    if OVERVIEW_TABS.exists():
        cfg["overview_tabs"] = yaml.safe_load(OVERVIEW_TABS.read_text())
    else:
        cfg["overview_tabs"] = {}
    if MEDIA_PLAYERS.exists():
        cfg["media_players"] = yaml.safe_load(MEDIA_PLAYERS.read_text()) or {}
    else:
        cfg["media_players"] = {}
    if WEATHER_PANEL.exists():
        cfg["weather_panel"] = yaml.safe_load(WEATHER_PANEL.read_text()) or {}
    else:
        cfg["weather_panel"] = {}
    cfg["scenes_config"] = yaml.safe_load(SCENES.read_text()) if SCENES.exists() else {}
    cfg["cameras_config"] = yaml.safe_load(CAMERAS.read_text()) if CAMERAS.exists() else {}
    cfg["light_groups"] = (
        yaml.safe_load(LIGHT_GROUPS.read_text()).get("groups", []) if LIGHT_GROUPS.exists() else []
    )
    return cfg


def flux_view(
    *,
    title: str,
    path: str,
    icon: str,
    sections: list[dict],
    use_navbar_card: bool,
    subview: bool = False,
    back_path: str | None = None,
    navbar_media_player: dict | None = None,
) -> dict:
    view: dict = {
        "title": title,
        "icon": icon,
        "path": path,
        "type": "sections",
        "max_columns": 2,
        "theme": "flux-ui-md3",
        "card_mod": VIEW_CARD_MOD,
        "sections": sections
        + [
            navbar_section(
                use_navbar_card=use_navbar_card,
                media_player=navbar_media_player,
            )
        ],
    }
    if subview:
        view["subview"] = True
    if back_path:
        view["back_path"] = back_path
    return view


def apply_md3_to_cards(obj: object) -> object:
    """Recursively add glass card-mod to cards imported from Mobile Home."""
    if isinstance(obj, list):
        return [apply_md3_to_cards(x) for x in obj]
    if not isinstance(obj, dict):
        return obj

    out = {k: apply_md3_to_cards(v) for k, v in obj.items()}

    if out.get("type") and out["type"] != "grid":
        existing = out.get("card_mod") or {}
        if isinstance(existing, dict):
            style = GLASS_CARD_MOD["style"]
            if "style" in existing:
                style = style + existing["style"]
            out["card_mod"] = {"style": style}
        elif "mushroom-title-card" in str(out.get("type", "")):
            out["card_mod"] = TITLE_CARD_MOD

    return out


def section_title(title: str, subtitle: str = "") -> dict:
    card: dict = {
        "type": "custom:mushroom-title-card",
        "title": title,
        "grid_options": {"columns": 12},
    }
    if subtitle:
        card["subtitle"] = subtitle
    return wrap_title(card)


def hero_bitmoji_picture_js(cfg: dict) -> str:
    """Logged-in user avatar: configured bitmoji map, then HA person picture, then default."""
    hero = (cfg.get("context") or {}).get("hero") or {}
    by_user = hero.get("bitmoji_by_user") or {"Dave": "/local/flux-ui/bitmoji/dave.png"}
    default = hero.get("bitmoji_default") or "/local/flux-ui/bitmoji/dave.png"
    map_json = json.dumps(by_user)
    default_json = json.dumps(default)
    return (
        "[[[\n"
        "  try {\n"
        "    const u = (typeof user !== 'undefined' && user) ? user : {};\n"
        "    const uname = u.name || 'Guest';\n"
        "    const uid = u.id;\n"
        f"    const map = {map_json};\n"
        f"    const fallback = {default_json};\n"
        "    if (map[uname]) return map[uname];\n"
        "    if (typeof states === 'object' && states && uid != null) {\n"
        "      for (const eid of Object.keys(states)) {\n"
        "        if (!eid.startsWith('person.')) continue;\n"
        "        const st = states[eid];\n"
        "        if (!st || !st.attributes) continue;\n"
        "        if (st.attributes.user_id === uid) {\n"
        "          const pic = st.attributes.entity_picture;\n"
        "          if (pic && !String(pic).includes('branding/logo')) return pic;\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "    return fallback;\n"
        "  } catch (e) {\n"
        f"    return {default_json};\n"
        "  }\n"
        "]]]"
    )


def hero_card(weather_entity: str, cfg: dict) -> dict:
    """Single Flux-style hero: user bitmoji + greeting + weather conditions."""
    avatar = hero_bitmoji_picture_js(cfg)
    return {
        "type": "custom:button-card",
        "template": "flux_hero",
        "entity": weather_entity,
        "show_icon": False,
        "show_entity_picture": True,
        "variables": {"avatar_url": avatar},
        "entity_picture": avatar,
        "triggers_update": "all",
        "name": (
            "[[[\n"
            "  const u = (typeof user !== 'undefined' && user) ? user : {};\n"
            "  const uname = u.name || 'Guest';\n"
            "  const h = new Date().getHours();\n"
            "  let g = 'Morning';\n"
            "  if (h >= 22 || h < 5) g = 'Night';\n"
            "  else if (h >= 18) g = 'Evening';\n"
            "  else if (h >= 12) g = 'Afternoon';\n"
            "  return `${g}, ${uname}!`;\n"
            "]]]"
        ),
        "label": (
            "[[[\n"
            "  if (!entity) return '';\n"
            "  const attrs = entity.attributes || {};\n"
            "  const cond = attrs.condition || attrs.weather || entity.state || '';\n"
            "  const temp = attrs.temperature;\n"
            "  const time = new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});\n"
            "  const wx = temp != null ? `${cond} · ${temp}°` : String(cond);\n"
            "  return `${wx} · ${time}`;\n"
            "]]]"
        ),
        "grid_options": {"columns": 12},
    }


def build_hero(weather_entity: str, cfg: dict) -> dict:
    return {"type": "grid", "cards": [hero_card(weather_entity, cfg)]}


def build_quick_actions(cfg: dict) -> dict:
    col = 6
    cards: list[dict] = [section_title("Quick Actions")]
    for item in cfg["quick_actions"]["gate"]:
        cards.append(lock_action(item["entity"], item["name"], columns=col))
    for item in cfg["quick_actions"]["garage"]:
        cards.append(garage_action(item, columns=col))
    for item in cfg["quick_actions"]["actions"]:
        cards.append(
            scene_action(
                item["name"],
                item["subtitle"],
                item["icon"],
                item["service"],
                item["target"],
                columns=col,
            )
        )
    return {"type": "grid", "cards": cards}


def build_favourite_lights(cfg: dict) -> dict:
    return build_lights_grid_section("Favourite lights", "", cfg["favourite_lights"])


def build_room_detail(room: dict, cfg: dict | None = None) -> dict:
    doors = (cfg or {}).get("quick_actions", {}).get("garage", []) if cfg else []
    return build_room_detail_page(room, garage_doors=doors if room.get("path") == "garage" else None)


def build_overview_sections(
    cfg: dict,
    weather: str,
    climate: dict,
    *,
    use_auto_entities: bool,
    use_simple_tabs: bool = True,
    use_calendar_pro: bool = True,
    use_mediocre_media: bool = True,
) -> list[dict]:
    """Overview layout — ElementZoom Home/Events/Active tabs below hero + status chips."""
    sections: list[dict] = [
        build_hero(weather, cfg),
        build_home_status_section(cfg),
    ]

    home_tab_cards: list[dict] = [
        build_quick_actions_tab(cfg, section_title),
        tab_section_from_grid(climate),
        tab_section_from_grid(build_favourite_lights(cfg)),
    ]

    if tabs_enabled(cfg):
        sections.append(
            build_overview_tabs_section(
                cfg,
                home_tab_cards=home_tab_cards,
                use_auto_entities=use_auto_entities,
                use_calendar_pro=use_calendar_pro,
                use_simple_tabs=use_simple_tabs and tab_engine(cfg) in ("simple-tabs", "auto"),
                enable_tab_swipe=not media_player_active(cfg),
            )
        )
        popup_section = build_music_player_popup_section(cfg, use_mediocre=use_mediocre_media)
        if popup_section:
            sections.append(popup_section)
        weather_section = build_weather_panel_section(cfg)
        if weather_section:
            sections.append(weather_section)
        return sections

    # Fallback: vertical stack (pre-tabs layout)
    sections.extend(home_tab_cards)
    if use_auto_entities:
        sections.append(build_active_lights_section(cfg))
    open_garage = build_open_garage_section(cfg)
    if open_garage:
        sections.append(open_garage)
    return sections


def build_rooms_index(cfg: dict, *, use_simple_tabs: bool = True) -> dict:
    return build_rooms_index_section(cfg.get("rooms", []), use_simple_tabs=use_simple_tabs)


def extract_section_from_mobile_home(config: dict, *, path: str | None = None, title: str | None = None) -> dict | None:
    for view in config.get("views", []):
        if path and view.get("path") == path and view.get("sections"):
            return copy.deepcopy(view["sections"][0])
        if title and view.get("sections"):
            for section in view["sections"]:
                for card in section.get("cards", []):
                    if card.get("type") == "custom:mushroom-title-card" and card.get("title") == title:
                        return copy.deepcopy(section)
    return None


def sanitize_climate_section(section: dict) -> dict | None:
    """Strip Mobile Home chip/header duplicates — hero already shows time and weather."""
    skip_types = {"custom:mushroom-chips-card", "custom:mushroom-title-card"}
    cards: list[dict] = []
    for card in section.get("cards", []):
        if card.get("type") in skip_types:
            continue
        cards.append(card)
    if not cards:
        return None
    return {"type": "grid", "cards": cards}


def extract_climate_from_mobile_home(config: dict) -> dict | None:
    """Climate entity cards only (no clock/temp chips — those duplicate the Flux hero)."""
    section = extract_section_from_mobile_home(config, path="home")
    if not section:
        section = extract_section_from_mobile_home(config, title="Climate")
    if not section:
        return None
    cleaned = sanitize_climate_section(section)
    if not cleaned:
        return None
    return {
        "type": "grid",
        "cards": [
            section_title("Climate"),
            *[
                wrap_glass({**card, "grid_options": card.get("grid_options") or {"columns": 12}})
                if card.get("type") != "grid"
                else apply_md3_to_cards(card)
                for card in cleaned["cards"]
            ],
        ],
    }


def climate_fallback_section(weather_entity: str) -> dict:
    return {
        "type": "grid",
        "cards": [
            section_title("Climate"),
            wrap_glass(
                {
                    "type": "custom:mushroom-entity-card",
                    "entity": weather_entity,
                    "name": "Forecast",
                    "layout": "horizontal",
                    "fill_container": True,
                    "grid_options": {"columns": 12},
                }
            ),
        ],
    }


def build_config(
    *,
    climate_section: dict | None = None,
    camera_section: dict | None = None,
    use_navbar_card: bool = True,
    use_kiosk: bool = True,
    use_auto_entities: bool = True,
    use_simple_tabs: bool = True,
    use_calendar_pro: bool = True,
    use_mediocre_media: bool = True,
) -> dict:
    cfg = load_entities()
    weather = cfg.get("weather", "weather.forecast_home")
    climate = (
        apply_md3_to_cards(climate_section)
        if climate_section
        else climate_fallback_section(weather)
    )

    overview = build_overview_sections(
        cfg,
        weather,
        climate,
        use_auto_entities=use_auto_entities,
        use_simple_tabs=use_simple_tabs,
        use_calendar_pro=use_calendar_pro,
        use_mediocre_media=use_mediocre_media,
    )

    navbar_media = build_navbar_media_player(cfg) if media_player_active(cfg) else None

    views: list[dict] = [
        flux_view(
            title="Overview",
            path="overview",
            icon="mdi:home",
            sections=overview,
            use_navbar_card=use_navbar_card,
            navbar_media_player=navbar_media,
        ),
        flux_view(
            title="Rooms",
            path="rooms",
            icon="mdi:sofa",
            sections=[build_rooms_index(cfg, use_simple_tabs=use_simple_tabs)],
            use_navbar_card=use_navbar_card,
        ),
        flux_view(
            title="Scenes",
            path="scenes",
            icon="mdi:layers",
            sections=[build_scenes_view(cfg, use_auto_entities=use_auto_entities)],
            use_navbar_card=use_navbar_card,
        ),
        flux_view(
            title="Lights",
            path="lights",
            icon="mdi:lightbulb-group",
            sections=[build_lights_view(cfg, use_auto_entities=use_auto_entities)],
            use_navbar_card=use_navbar_card,
        ),
        flux_view(
            title="Cameras",
            path="cameras",
            icon="mdi:cctv",
            sections=[
                build_cameras_view(
                    cfg,
                    camera_section,
                    use_auto_entities=use_auto_entities,
                    apply_md3=apply_md3_to_cards,
                )
            ],
            use_navbar_card=use_navbar_card,
        ),
    ]

    for room in cfg.get("rooms", []):
        slug = room["path"]
        back = f"{URL_PREFIX}/rooms"
        views.append(
            flux_view(
                title=room["name"],
                path=room_view_path(slug),
                icon=room.get("icon", "mdi:home-outline"),
                sections=[build_room_detail(room, cfg)],
                use_navbar_card=use_navbar_card,
                subview=True,
                back_path=back,
            )
        )
        views.append(
            flux_view(
                title=f"{room.get('card_name') or room['name']} — Grid",
                path=room_grid_view_path(slug),
                icon="mdi:view-grid",
                sections=[build_room_grid_page(room, active_tab="grid")],
                use_navbar_card=use_navbar_card,
                subview=True,
                back_path=back,
            )
        )
        views.append(
            flux_view(
                title=f"{room.get('card_name') or room['name']} — Camera",
                path=room_camera_view_path(slug),
                icon="mdi:cctv",
                sections=[build_room_camera_page(room, cfg, active_tab="camera")],
                use_navbar_card=use_navbar_card,
                subview=True,
                back_path=back,
            )
        )

    out: dict = {
        "title": "Flux UI",
        "button_card_templates": copy.deepcopy(BUTTON_CARD_TEMPLATES),
        "views": views,
    }
    # Unused native tab template confuses deploy fingerprinting when engine is simple-tabs.
    if tab_engine(cfg) == "simple-tabs":
        out["button_card_templates"].pop("flux_overview_tab", None)
    if use_kiosk:
        out["kiosk_mode"] = copy.deepcopy(KIOSK_MODE)
    # Bottom navbar handles view changes; keep horizontal swipes for media carousel.
    out["swipe_nav"] = copy.deepcopy(SWIPE_NAV)
    modules = extra_module_urls(cfg)
    if modules:
        out["extra_module_url"] = modules
        write_carousel_sync_js(cfg, ROOT / "www" / "flux-ui" / "carousel-sync.js")
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mobile-home-storage", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "generated" / "lovelace.flux_ui.json",
    )
    parser.add_argument(
        "--no-navbar-card",
        action="store_true",
        help="Use mushroom chip nav fallback (navbar-card HACS not installed)",
    )
    parser.add_argument(
        "--no-kiosk",
        action="store_true",
        help="Do not hide HA header (debug / before kiosk-mode HACS installed)",
    )
    parser.add_argument(
        "--no-auto-entities",
        action="store_true",
        help="Disable auto-entities active lights section",
    )
    parser.add_argument(
        "--no-simple-tabs",
        action="store_true",
        help="Use vertical overview layout instead of ElementZoom Home/Events/Active tabs",
    )
    parser.add_argument(
        "--no-calendar-pro",
        action="store_true",
        help="Use mushroom calendar fallback instead of calendar-card-pro Events tab",
    )
    parser.add_argument(
        "--no-mediocre-media",
        action="store_true",
        help="Use mushroom media player in popup instead of mediocre-massive card",
    )
    args = parser.parse_args()

    climate_section = None
    camera_section = None
    if args.mobile_home_storage and args.mobile_home_storage.exists():
        raw = json.loads(args.mobile_home_storage.read_text())
        mobile_cfg = raw["data"]["config"]
        climate_section = extract_climate_from_mobile_home(mobile_cfg)
        if climate_section:
            print("Imported climate section from Mobile Home")
        camera_section = extract_section_from_mobile_home(mobile_cfg, path="cameras")
        if camera_section:
            print("Imported cameras section from Mobile Home")

    cfg = load_entities()
    from generate_weather_package import write_weather_package

    write_weather_package()
    config = build_config(
        climate_section=climate_section,
        camera_section=camera_section,
        use_navbar_card=not args.no_navbar_card,
        use_kiosk=not args.no_kiosk,
        use_auto_entities=not args.no_auto_entities,
        use_simple_tabs=not args.no_simple_tabs,
        use_calendar_pro=not args.no_calendar_pro,
        use_mediocre_media=not args.no_mediocre_media,
    )
    usage = overview_tab_usage(config)
    print(
        f"Overview tabs: engine={tab_engine(cfg)} "
        f"simple-tabs={usage['has_simple_tabs']} native={usage['has_native_tabs']}"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "minor_version": 1,
        "key": "lovelace.flux_ui",
        "data": {"config": config},
    }
    args.output.write_text(json.dumps(payload, indent=2))
    overview = next(v for v in config["views"] if v["path"] == "overview")
    print(
        f"Wrote {args.output} ({len(config['views'])} views, "
        f"{len(overview['sections'])} overview sections)"
    )


if __name__ == "__main__":
    main()

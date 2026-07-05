"""Flux UI floating music player — ElementZoom navbar + bubble popup pattern.

Reference: ElementZoom Flux UI 01-overview.yaml
  - custom:navbar-card media_player.players[] → #music-player
  - custom:bubble-card pop-up with mediocre-massive-media-player-card
"""

from __future__ import annotations

from typing import Any

MUSIC_PLAYER_HASH = "#music-player"
MEDIA_SELECT_ENTITY = "input_select.flux_ui_media_player"
SELECT_ZONE_SCRIPT = "script.flux_ui_select_media_zone"
ZONE_PREV_SCRIPT = "script.flux_ui_media_zone_prev"
ZONE_NEXT_SCRIPT = "script.flux_ui_media_zone_next"

BUBBLE_POPUP_STYLES = """\
#root {
  height: unset !important;
  max-height: 100% !important;
  transition: transform var(--md-sys-motion-expressive-spatial-default) !important;
}
.bubble-header-container {
  --bubble-button-background-color: var(--md-sys-color-on-secondary);
  --bubble-button-icon-background-color: var(--md-sys-color-on-secondary);
}
.bubble-pop-up-container {
  padding-bottom: 64px !important;
}
"""

# Sonos / HA media_player attributes that may carry album art (checked by discover_sonos --audit-artwork).
ARTWORK_ATTRS = (
    "entity_picture",
    "entity_picture_local",
    "album_art",
    "album_art_url",
    "artwork_url",
)


def _media_cfg(cfg: dict) -> dict:
    return cfg.get("media_players") or {}


def enabled_players(cfg: dict) -> list[dict]:
    mp = _media_cfg(cfg)
    if not mp.get("enabled", True):
        return []
    return [p for p in mp.get("players", []) if p.get("enabled", True) and p.get("entity")]


def media_player_active(cfg: dict) -> bool:
    return len(enabled_players(cfg)) > 0


def _player_show_jinja(entity: str) -> str:
    return (
        "[[[ return ['playing', 'paused'].includes(states['"
        + entity
        + "']?.state); ]]]"
    )


def _select_zone_action(zone: str) -> dict:
    return {
        "action": "perform-action",
        "perform_action": SELECT_ZONE_SCRIPT,
        "data": {"zone": zone},
    }


def _mediocre_player_card(entity: str) -> dict:
    return {
        "type": "custom:mediocre-massive-media-player-card",
        "entity_id": entity,
        "mode": "panel",
        "use_art_colors": True,
        "options": {
            "show_volume_step_buttons": True,
            "show_source": True,
        },
    }


def build_navbar_media_player(cfg: dict) -> dict | None:
    """Navbar mini player — swipe carousel between active Sonos zones.

    Tap a zone to select it (syncs popup artwork/controls). Hold to open the full player.
    """
    players = enabled_players(cfg)
    if not players:
        return None

    entries: list[dict[str, Any]] = []
    for player in players:
        entity = player["entity"]
        name = player["name"]
        entry: dict[str, Any] = {
            "entity": entity,
            "show": _player_show_jinja(entity),
            "title": name,
            "tap_action": _select_zone_action(name),
            "hold_action": {
                "action": "navigate",
                "navigation_path": MUSIC_PLAYER_HASH,
            },
        }
        if player.get("icon"):
            entry["icon"] = player["icon"]
        entries.append(entry)

    return {
        # Per-slide artwork — widget-level blur shared one cover when swiping.
        "album_cover_background": False,
        "auto_padding": True,
        "players": entries,
    }


def _zone_nav_chip(icon: str, script: str) -> dict:
    return {
        "type": "template",
        "icon": icon,
        "icon_color": "primary",
        "content": "",
        "tap_action": {
            "action": "perform-action",
            "perform_action": script,
        },
    }


def _player_selector_chips(players: list[dict]) -> dict:
    chips: list[dict] = []
    if len(players) > 1:
        chips.append(_zone_nav_chip("mdi:chevron-left", ZONE_PREV_SCRIPT))
    for player in players:
        name = player["name"]
        chips.append(
            {
                "type": "template",
                "icon": player.get("icon", "mdi:speaker"),
                "content": name,
                "tap_action": _select_zone_action(name),
                "icon_color": (
                    "{{ 'primary' if is_state('" + MEDIA_SELECT_ENTITY + "', '" + name + "') else 'grey' }}"
                ),
            }
        )
    if len(players) > 1:
        chips.append(_zone_nav_chip("mdi:chevron-right", ZONE_NEXT_SCRIPT))
    return {
        "type": "custom:mushroom-chips-card",
        "alignment": "center",
        "chips": chips,
    }


def _mushroom_player_card(entity: str, name: str) -> dict:
    return {
        "type": "custom:mushroom-media-player-card",
        "entity": entity,
        "name": name,
        "use_media_info": True,
        "show_volume_level": True,
        "collapsible_controls": False,
        "layout": "horizontal",
        "fill_container": True,
    }


def _player_panel(player: dict, *, use_mediocre: bool) -> dict:
    entity = player["entity"]
    name = player["name"]
    card = _mediocre_player_card(entity) if use_mediocre else _mushroom_player_card(entity, name)
    return {
        "type": "conditional",
        "conditions": [
            {
                "condition": "state",
                "entity": MEDIA_SELECT_ENTITY,
                "state": name,
            }
        ],
        "card": card,
    }


def build_music_player_popup(cfg: dict, *, use_mediocre: bool = True) -> dict | None:
    """Full-screen bubble popup — player picker + volume / skip / queue controls."""
    players = enabled_players(cfg)
    if not players:
        return None

    popup_cards: list[dict] = [
        _player_selector_chips(players),
        *[_player_panel(p, use_mediocre=use_mediocre) for p in players],
    ]

    return {
        "type": "custom:bubble-card",
        "card_type": "pop-up",
        "hash": MUSIC_PLAYER_HASH,
        "name": "Music Player",
        "icon": "mdi:music",
        "styles": BUBBLE_POPUP_STYLES,
        "bg_color": "var(--md-sys-color-on-primary)",
        "bg_opacity": "85",
        "button_type": "name",
        "sub_button": {"main": [], "bottom": []},
        "cards": popup_cards,
        "popup_style": "classic",
    }


def build_music_player_popup_section(cfg: dict, *, use_mediocre: bool = True) -> dict | None:
    popup = build_music_player_popup(cfg, use_mediocre=use_mediocre)
    if not popup:
        return None
    return {
        "type": "grid",
        "cards": [popup],
    }


def media_zone_scripts(options: list[str]) -> dict:
    """HA scripts — zone select / prev / next for input_select.flux_ui_media_player."""
    if not options:
        return {}
    opt_yaml = yaml_list(options)
    return {
        "flux_ui_select_media_zone": {
            "alias": "Flux UI select media zone",
            "mode": "queued",
            "fields": {
                "zone": {
                    "description": "Sonos zone name (matches input_select option)",
                    "example": options[0],
                    "selector": {"text": {}},
                }
            },
            "sequence": [
                {
                    "service": "input_select.select_option",
                    "target": {"entity_id": MEDIA_SELECT_ENTITY},
                    "data": {"option": "{{ zone }}"},
                }
            ],
        },
        "flux_ui_media_zone_next": {
            "alias": "Flux UI next Sonos zone",
            "mode": "single",
            "sequence": [
                {
                    "service": "input_select.select_option",
                    "target": {"entity_id": MEDIA_SELECT_ENTITY},
                    "data": {
                        "option": (
                            "{% set opts = "
                            + opt_yaml
                            + " %}"
                            "{% set cur = states('"
                            + MEDIA_SELECT_ENTITY
                            + "') %}"
                            "{% set i = opts.index(cur) if cur in opts else 0 %}"
                            "{{ opts[(i + 1) % (opts | length)] }}"
                        ),
                    },
                }
            ],
        },
        "flux_ui_media_zone_prev": {
            "alias": "Flux UI previous Sonos zone",
            "mode": "single",
            "sequence": [
                {
                    "service": "input_select.select_option",
                    "target": {"entity_id": MEDIA_SELECT_ENTITY},
                    "data": {
                        "option": (
                            "{% set opts = "
                            + opt_yaml
                            + " %}"
                            "{% set cur = states('"
                            + MEDIA_SELECT_ENTITY
                            + "') %}"
                            "{% set i = opts.index(cur) if cur in opts else 0 %}"
                            "{{ opts[(i - 1) % (opts | length)] }}"
                        ),
                    },
                }
            ],
        },
    }


def yaml_list(items: list[str]) -> str:
    inner = ", ".join(repr(x) for x in items)
    return "[" + inner + "]"

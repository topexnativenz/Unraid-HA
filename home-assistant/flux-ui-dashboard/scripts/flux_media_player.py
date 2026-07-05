"""Flux UI floating music player — ElementZoom navbar + bubble popup pattern.

Reference: ElementZoom Flux UI 01-overview.yaml
  - custom:navbar-card media_player.players[] → #music-player
  - custom:bubble-card pop-up with mediocre-massive-media-player-card
"""

from __future__ import annotations

from typing import Any

MUSIC_PLAYER_HASH = "#music-player"
MEDIA_SELECT_ENTITY = "input_select.flux_ui_media_player"

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


def _album_art_picture(entity: str) -> dict:
    """Explicit album art — picture-entity reads entity_picture from Sonos when playing."""
    return {
        "type": "picture-entity",
        "entity": entity,
        "show_name": False,
        "show_state": False,
        "aspect_ratio": "1",
        "tap_action": {"action": "more-info"},
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  border-radius: 20px !important;\n"
                "  overflow: hidden !important;\n"
                "  aspect-ratio: 1 !important;\n"
                "  max-width: min(320px, 72vw) !important;\n"
                "  margin: 0 auto 8px auto !important;\n"
                "  background: color-mix(in srgb, var(--md-sys-color-surface-container) 60%, transparent) !important;\n"
                "}\n"
                "img {\n"
                "  object-fit: cover !important;\n"
                "  width: 100% !important;\n"
                "  height: 100% !important;\n"
                "}\n"
            )
        },
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
    """Navbar mini player — draggable carousel when multiple Sonos zones are active."""
    players = enabled_players(cfg)
    if not players:
        return None

    entries: list[dict[str, Any]] = []
    for player in players:
        entity = player["entity"]
        entry: dict[str, Any] = {
            "entity": entity,
            "show": _player_show_jinja(entity),
            "tap_action": {
                "action": "navigate",
                "navigation_path": MUSIC_PLAYER_HASH,
            },
        }
        if player.get("icon"):
            entry["icon"] = player["icon"]
        if player.get("name"):
            entry["title"] = player["name"]
        entries.append(entry)

    return {
        "album_cover_background": True,
        "auto_padding": True,
        "players": entries,
    }


def _player_selector_chips(players: list[dict]) -> dict:
    chips: list[dict] = []
    for player in players:
        name = player["name"]
        chips.append(
            {
                "type": "template",
                "icon": player.get("icon", "mdi:speaker"),
                "content": name,
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "input_select.select_option",
                    "target": {"entity_id": MEDIA_SELECT_ENTITY},
                    "data": {"option": name},
                },
                "icon_color": (
                    "{{ 'primary' if is_state('" + MEDIA_SELECT_ENTITY + "', '" + name + "') else 'grey' }}"
                ),
            }
        )
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

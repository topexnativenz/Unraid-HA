"""Flux UI floating music player — ElementZoom navbar + bubble popup pattern.

Reference: ElementZoom Flux UI 01-overview.yaml
  - custom:navbar-card media_player.players[] → #music-player
  - custom:bubble-card pop-up with mediocre-massive-media-player-card
  - /local/flux-ui/carousel-sync.js keeps input_select in sync when swiping zones
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MUSIC_PLAYER_HASH = "#music-player"
FLUX_UI_MUSIC_PLAYER_PATH = f"/flux-ui/overview{MUSIC_PLAYER_HASH}"
MEDIA_SELECT_ENTITY = "input_select.flux_ui_media_player"
SELECT_ZONE_SCRIPT = "script.flux_ui_select_media_zone"
ZONE_PREV_SCRIPT = "script.flux_ui_media_zone_prev"
ZONE_NEXT_SCRIPT = "script.flux_ui_media_zone_next"
CAROUSEL_SYNC_MODULE = "/local/flux-ui/carousel-sync.js"

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


def _player_show_jinja() -> str:
    """Show every configured zone in the carousel (idle zones use speaker icon)."""
    return "[[[ return true; ]]]"


def _navbar_player_title_js(entity: str, zone_name: str) -> str:
    """Track name when playing; Sonos zone name when idle."""
    return (
        "[[[ "
        f"const s = states[{entity!r}]; "
        f"const player = {zone_name!r}; "
        "if (!s) return player;"
        "const attrs = s.attributes || {};"
        "const track = attrs.media_title || attrs.media_series_title || '';"
        "return track || player; "
        "]]]"
    )


def _navbar_player_subtitle_js(entity: str, zone_name: str) -> str:
    """Artist + configured Sonos zone name (never Sonos 'Listening on' group text)."""
    return (
        "[[[ "
        f"const s = states[{entity!r}]; "
        f"const player = {zone_name!r}; "
        "if (!s) return '';"
        "const attrs = s.attributes || {};"
        "let artist = attrs.media_artist || attrs.media_album_artist || '';"
        "if (artist.indexOf('Listening on') >= 0 || artist.indexOf('SONOS') >= 0) artist = '';"
        "const track = attrs.media_title || attrs.media_series_title || '';"
        "if (artist) return artist + ' · ' + player;"
        "if (track) return player;"
        "return ''; "
        "]]]"
    )


def _navbar_player_actions(name: str) -> dict[str, dict]:
    """Open popup — disable default media_player toggle on double-tap."""
    open_action = _open_player_action(name)
    no_action = {"action": "none"}
    return {
        "tap_action": open_action,
        "hold_action": open_action,
        "double_tap_action": no_action,
    }


def _select_zone_action(zone: str) -> dict:
    """Select Sonos zone via input_select (no script dependency)."""
    return {
        "action": "call-service",
        "service": "input_select.select_option",
        "target": {"entity_id": MEDIA_SELECT_ENTITY},
        "data": {"option": zone},
    }


def _open_player_action(_zone: str) -> dict:
    """Open music popup — carousel-sync.js selects the visible zone before navigate."""
    return {
        "action": "navigate",
        "navigation_path": FLUX_UI_MUSIC_PLAYER_PATH,
    }


def _mediocre_player_card(entity: str, zone_name: str) -> dict:
    return {
        "type": "custom:mediocre-massive-media-player-card",
        "entity_id": entity,
        "mode": "panel",
        "use_art_colors": True,
        "options": {
            "show_volume_step_buttons": True,
            "show_source": False,
            "hide_selected_player_header": True,
        },
        "card_mod": {
            "style": (
                "ha-card h3 + div, ha-card .device, ha-card [class*='device-name'] "
                "{ display: none !important; }\n"
            )
        },
    }


def build_navbar_media_player(cfg: dict) -> dict | None:
    """Navbar mini player — swipe carousel between Sonos zones with per-zone artwork.

    Swiping updates input_select via carousel-sync.js so the popup player + art follow.
    Tap or hold opens the full player for the visible zone (selects zone first).
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
            "show": _player_show_jinja(),
            "title": _navbar_player_title_js(entity, name),
            "subtitle": _navbar_player_subtitle_js(entity, name),
            **_navbar_player_actions(name),
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


def _zone_nav_chip(icon: str, script_entity: str) -> dict:
    return {
        "type": "template",
        "icon": icon,
        "icon_color": "primary",
        "content": "",
        "tap_action": {
            "action": "call-service",
            "service": script_entity,
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
    card = _mediocre_player_card(entity, name) if use_mediocre else _mushroom_player_card(entity, name)
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


def write_carousel_sync_js(cfg: dict, dest: Path) -> bool:
    """Emit JS that syncs input_select when the navbar Sonos carousel is swiped."""
    players = enabled_players(cfg)
    if not players:
        return False

    zone_names = [p["name"] for p in players]
    zones_js = json.dumps(zone_names)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        f"""\
// Generated by build_flux_ui.py — syncs Sonos zone swipes to input_select + popup artwork.
(function () {{
  const ZONE_ORDER = {zones_js};
  let lastZone = null;
  let debounce = null;

  function hass() {{
    return document.querySelector('home-assistant')?.hass;
  }}

  function deepQueryAll(selector, root) {{
    const results = [];
    const seen = new Set();
    function walk(node) {{
      if (!node || seen.has(node)) return;
      if (node.nodeType === 1) seen.add(node);
      if (node.nodeType !== 1) return;
      if (node.matches?.(selector) && !results.includes(node)) results.push(node);
      node.querySelectorAll?.(selector)?.forEach((el) => {{
        if (!results.includes(el)) results.push(el);
      }});
      if (node.shadowRoot) walk(node.shadowRoot);
      node.children && [...node.children].forEach(walk);
    }}
    walk(root || document.body);
    return results;
  }}

  function activeCarouselIndex() {{
    const tracks = deepQueryAll('.media-player-track');
    for (const track of tracks) {{
      const t = track.style?.transform || '';
      const m = t.match(/translateX\\(calc\\((-?\\d+)%/);
      if (m) return Math.round(Math.abs(parseInt(m[1], 10)) / 100);
    }}
    const dots = deepQueryAll('.media-player-dot');
    if (!dots.length) return -1;
    const idx = dots.findIndex((d) => d.classList.contains('active'));
    return idx >= 0 ? idx : 0;
  }}

  function activeZoneTitle() {{
    const idx = activeCarouselIndex();
    if (idx >= 0 && idx < ZONE_ORDER.length) return ZONE_ORDER[idx];
    // Do not read .media-player-title — it shows track names, not zone names.
    return null;
  }}

  function selectVisibleZone() {{
    const zone = activeZoneTitle();
    if (!zone) return null;
    const h = hass();
    if (!h) return null;
    lastZone = zone;
    return h.callService('input_select', 'select_option', {{
      entity_id: 'input_select.flux_ui_media_player',
      option: zone,
    }});
  }}

  function syncZone() {{
    const zone = activeZoneTitle();
    if (!zone || zone === lastZone) return;
    selectVisibleZone();
  }}

  function installOpenHandler() {{
    // Select zone before navbar-card navigate opens the bubble popup.
    document.addEventListener(
      'pointerdown',
      (ev) => {{
        const hit = ev.target.closest(
          '.media-player-viewport, .media-player-carousel, .media-player-container, .media-player-track, .media-player-title, .media-player-subtitle',
        );
        if (!hit) return;
        selectVisibleZone();
      }},
      true,
    );
  }}

  function scheduleSync() {{
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(syncZone, 100);
  }}

  function observe() {{
    const root = document.querySelector('home-assistant');
    if (!root) return;
    new MutationObserver(scheduleSync).observe(root, {{
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style'],
      childList: true,
    }});
    setInterval(syncZone, 500);
    installOpenHandler();
    scheduleSync();
  }}

  window.addEventListener('load', observe);
  setTimeout(observe, 1500);
}})();
"""
    )
    return True


def extra_module_urls(cfg: dict) -> list[str]:
    if media_player_active(cfg):
        return [CAROUSEL_SYNC_MODULE]
    return []

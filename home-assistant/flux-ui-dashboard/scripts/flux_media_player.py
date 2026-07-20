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
MIN_PLAYER_SLOTS = 2

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
    overrides = mp.get("apple_tv_overrides") or {}
    out: list[dict] = []
    for p in mp.get("players", []):
        if not p.get("enabled", True) or not p.get("entity"):
            continue
        entry = dict(p)
        if is_sonos_zone(entry) and not entry.get("apple_tv"):
            linked = overrides.get(entry["entity"])
            if linked:
                entry["apple_tv"] = linked
        out.append(entry)
    return out


def player_source(player: dict) -> str:
    """sonos = Sonos zone (optional apple_tv link for TV sound). apple = ATV/HomePod direct."""
    return player.get("source", "sonos")


def is_sonos_zone(player: dict) -> bool:
    return player_source(player) == "sonos"


def media_player_active(cfg: dict) -> bool:
    return len(enabled_players(cfg)) > 0


def _any_music_playing_jinja(players: list[dict]) -> str:
    parts = [
        f"((is_state('{p['entity']}', 'playing') or is_state('{p['entity']}', 'paused')) "
        f"and ({_is_music_expr(p['entity'])}))"
        for p in players
    ]
    return "(" + " or ".join(parts) + ")" if parts else "false"


def _visible_entities_jinja_setup(players: list[dict]) -> str:
    """Build ns.visible: active sessions (music over TV), min 2 slots, extras only when 3+ active."""
    any_music = _any_music_playing_jinja(players)
    active_lines = []
    for p in players:
        e = p["entity"]
        is_music = _is_music_expr(e)
        active_lines.append(
            f"{{% if (is_state('{e}', 'playing') or is_state('{e}', 'paused')) "
            f"and (not ({any_music}) or ({is_music})) %}}"
            f"{{% set ns.visible = ns.visible + ['{e}'] %}}{{% endif %}}"
        )
    filler_lines = []
    for p in players:
        e = p["entity"]
        filler_lines.append(
            f"{{% if '{e}' not in ns.visible and ns.visible | length < {MIN_PLAYER_SLOTS} %}}"
            f"{{% set ns.visible = ns.visible + ['{e}'] %}}{{% endif %}}"
        )
    return (
        "{% set ns = namespace(visible=[]) %}\n"
        + "\n".join(active_lines)
        + f"\n{{% if ns.visible | length <= {MIN_PLAYER_SLOTS} %}}\n"
        + "\n".join(filler_lines)
        + "\n{% endif %}"
    )


def _player_visible_template(players: list[dict], entity: str) -> str:
    """Navbar/popup visibility: 2 slots minimum; 3+ only when extra zones are actively playing."""
    return _visible_entities_jinja_setup(players) + f"\n{{{{ '{entity}' in ns.visible }}}}"


def _is_music_js_fn() -> str:
    return (
        "const isMusic = (attrs) => {\n"
        "  if (!attrs) return false;\n"
        "  const t = String(attrs.media_content_type || '').toLowerCase();\n"
        "  const app = String(attrs.app_name || '').toLowerCase();\n"
        "  if (['music','artist','album','playlist','podcast','track','genre'].includes(t)) return true;\n"
        "  if (['video','tvshow','movie','channel','episode'].includes(t)) return false;\n"
        "  if (app.includes('tv') || app.includes('hdmi')) return false;\n"
        "  if (attrs.media_artist && !attrs.media_series_title) return true;\n"
        "  if (attrs.media_series_title && !attrs.media_artist) return false;\n"
        "  return !!attrs.media_artist || !attrs.media_series_title;\n"
        "};"
    )


def _is_sonos_tv_expr(entity: str) -> str:
    """Jinja expression (no braces): true when Sonos relays TV/HDMI."""
    content = f"state_attr('{entity}', 'media_content_type') | default('') | lower"
    app = f"state_attr('{entity}', 'app_name') | default('') | lower"
    title = f"state_attr('{entity}', 'media_title') | default('') | lower"
    return (
        f"({content} in ['video', 'tvshow', 'movie', 'channel', 'episode'] "
        f"or 'tv' in {app} or 'hdmi' in {app} or {title} == 'tv')"
    )


def _is_music_expr(entity: str) -> str:
    """Jinja expression (no braces): true when entity is playing music, not TV/video."""
    t = f"state_attr('{entity}', 'media_content_type') | default('') | lower"
    app = f"state_attr('{entity}', 'app_name') | default('') | lower"
    artist = f"state_attr('{entity}', 'media_artist') | default('')"
    series = f"state_attr('{entity}', 'media_series_title') | default('')"
    return (
        f"({t} in ['music', 'artist', 'album', 'playlist', 'podcast', 'track', 'genre'] "
        f"or ({artist} and {t} not in ['video', 'tvshow', 'movie', 'channel', 'episode']) "
        f"or ({artist} and not {series}) "
        f"or ({t} not in ['video', 'tvshow', 'movie', 'channel', 'episode'] "
        f"and 'tv' not in {app} and 'hdmi' not in {app} and not {series}))"
    )


def _is_atv_mode_expr(sonos_entity: str, atv_entity: str) -> str:
    """TV-mode: Sonos relays TV/HDMI AND the linked ATV/HomePod looks active.

    Active = playing/paused, or any awake state with Now Playing metadata.
    Apple TVs often report 'idle'/'on' (or lag behind) while content plays —
    metadata presence is the reliable signal. Excludes off/standby so an
    empty ATV card never covers TV-source sound (broadcast, console).
    """
    tv = _is_sonos_tv_expr(sonos_entity)
    st = f"states('{atv_entity}')"
    has_media = (
        f"(state_attr('{atv_entity}', 'media_title') "
        f"or state_attr('{atv_entity}', 'media_series_title') "
        f"or state_attr('{atv_entity}', 'entity_picture') "
        f"or state_attr('{atv_entity}', 'app_name'))"
    )
    atv_active = (
        f"({st} in ['playing', 'paused'] "
        f"or ({st} not in ['off', 'standby', 'unavailable', 'unknown'] and {has_media}))"
    )
    return f"({tv}) and {atv_active}"


def tv_mode_sensor_object_id(player: dict) -> str:
    """Template binary_sensor object id for a Sonos zone's TV mode."""
    slug = player["entity"].replace("media_player.", "")
    return f"flux_ui_tv_{slug}"


def tv_mode_sensor_entity(player: dict) -> str:
    return f"binary_sensor.{tv_mode_sensor_object_id(player)}"


def tv_mode_template_sensors(players: list[dict]) -> list[dict]:
    """Template binary_sensors for packages/flux_ui_media.yaml.

    Conditional cards only support state conditions (no Jinja), so TV-mode
    detection lives in backend template sensors the popup can test by state.
    """
    sensors: list[dict] = []
    for player in players:
        if not is_sonos_zone(player) or not player.get("apple_tv"):
            continue
        entity = player["entity"]
        sensors.append(
            {
                "name": tv_mode_sensor_object_id(player),
                "unique_id": tv_mode_sensor_object_id(player),
                "state": "{{ " + _is_atv_mode_expr(entity, player["apple_tv"]) + " }}",
            }
        )
    return sensors


def _is_sonos_tv_js_fn() -> str:
    return (
        "const isSonosTv = (attrs) => {\n"
        "  if (!attrs) return false;\n"
        "  const t = String(attrs.media_content_type || '').toLowerCase();\n"
        "  const app = String(attrs.app_name || '').toLowerCase();\n"
        "  const title = String(attrs.media_title || '').toLowerCase();\n"
        "  if (['video','tvshow','movie','channel','episode'].includes(t)) return true;\n"
        "  if (app.includes('tv') || app.includes('hdmi')) return true;\n"
        "  return title === 'tv';\n"
        "};"
    )


def _apple_tv_links(players: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """Sonos entity -> Apple TV entity, and Apple TV entity -> display name."""
    sonos_to_atv: dict[str, str] = {}
    atv_names: dict[str, str] = {}
    for player in players:
        atv = player.get("apple_tv")
        if not atv:
            continue
        sonos_to_atv[player["entity"]] = atv
        atv_names[atv] = player.get("apple_tv_name") or player.get("name", "Apple TV")
    return sonos_to_atv, atv_names


def _apple_tv_setup_js(players: list[dict]) -> str:
    sonos_to_atv, atv_names = _apple_tv_links(players)
    return (
        f"const ATV_BY_SONOS = {json.dumps(sonos_to_atv)};\n"
        f"const ATV_NAMES = {json.dumps(atv_names)};\n"
        + _is_sonos_tv_js_fn()
        + "\n"
        + _is_music_js_fn()
        + "\n"
        "function atvForSonos(sonosId) { return ATV_BY_SONOS[sonosId] || null; }\n"
        "function atvName(atvId) {\n"
        "  if (!atvId) return 'Apple TV';\n"
        "  if (ATV_NAMES[atvId]) return ATV_NAMES[atvId];\n"
        "  var st = states[atvId];\n"
        "  if (st && st.attributes && st.attributes.friendly_name) return st.attributes.friendly_name;\n"
        "  return 'Apple TV';\n"
        "}\n"
        "function activeAtv(sonosId) {\n"
        "  var atvId = atvForSonos(sonosId);\n"
        "  if (!atvId) return null;\n"
        "  var sonos = states[sonosId];\n"
        "  if (!sonos) return null;\n"
        "  var atv = states[atvId];\n"
        "  if (!atv) return null;\n"
        "  var sonosLive = sonos.state === 'playing' || sonos.state === 'paused';\n"
        "  if (!sonosLive || !isSonosTv(sonos.attributes)) return null;\n"
        "  var aa = atv.attributes || {};\n"
        "  var atvLive = atv.state === 'playing' || atv.state === 'paused';\n"
        "  var atvAwake = !['off', 'standby', 'unavailable', 'unknown'].includes(atv.state);\n"
        "  var hasMedia = !!(aa.media_title || aa.media_series_title || aa.entity_picture || aa.app_name);\n"
        "  if (atvLive || (atvAwake && hasMedia)) return atv;\n"
        "  return null;\n"
        "}\n"
        "function atvTitle(atv) {\n"
        "  var a = (atv && atv.attributes) ? atv.attributes : {};\n"
        "  return a.media_series_title || a.media_title || a.app_name || '';\n"
        "}\n"
        "function atvSubtitle(atv) {\n"
        "  var a = (atv && atv.attributes) ? atv.attributes : {};\n"
        "  var series = a.media_series_title || '';\n"
        "  var detail = '';\n"
        "  if (series && a.media_title && a.media_title !== series) detail = a.media_title;\n"
        "  else if (a.media_artist) detail = a.media_artist;\n"
        "  if (series && a.media_season != null && a.media_episode != null) {\n"
        "    var ep = 'S' + a.media_season + ' E' + a.media_episode;\n"
        "    detail = detail ? detail + ' · ' + ep : ep;\n"
        "  }\n"
        "  return detail;\n"
        "}\n"
    )


def _navbar_player_entity_js(entity: str, players: list[dict]) -> str:
    """Switch navbar artwork to linked Apple TV when Sonos relays TV sound."""
    setup = _apple_tv_setup_js(players)
    return (
        "[[[\n"
        + setup
        + f"var atv = activeAtv({entity!r});\n"
        f"return atv ? atv.entity_id : {entity!r};\n"
        "]]]"
    )


def _navbar_player_title_js(entity: str, zone_name: str, players: list[dict]) -> str:
    """Track/show title when playing; zone name when idle."""
    player = next((p for p in players if p.get("entity") == entity), None)
    use_atv = player and is_sonos_zone(player) and player.get("apple_tv")
    if not use_atv:
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
    setup = _apple_tv_setup_js(players)
    return (
        "[[[\n"
        + setup
        + f"var s = states[{entity!r}];\n"
        f"var player = {zone_name!r};\n"
        f"var atv = activeAtv({entity!r});\n"
        "if (atv) { var t = atvTitle(atv); if (t) return t; }\n"
        "if (!s) return player;\n"
        "var attrs = s.attributes || {};\n"
        "var track = attrs.media_title || attrs.media_series_title || '';\n"
        "if (track && String(track).toLowerCase() !== 'tv') return track;\n"
        "return player;\n"
        "]]]"
    )


def _navbar_player_subtitle_js(entity: str, zone_name: str, players: list[dict]) -> str:
    """Artist or episode detail; Apple TV/HomePod name when relaying TV sound."""
    player = next((p for p in players if p.get("entity") == entity), None)
    use_atv = player and is_sonos_zone(player) and player.get("apple_tv")
    if not use_atv:
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
    setup = _apple_tv_setup_js(players)
    return (
        "[[[\n"
        + setup
        + f"var s = states[{entity!r}];\n"
        f"var player = {zone_name!r};\n"
        f"var atv = activeAtv({entity!r});\n"
        "if (atv) {\n"
        "  var detail = atvSubtitle(atv);\n"
        "  var device = atvName(atv.entity_id);\n"
        "  return detail ? detail + ' · ' + device : device;\n"
        "}\n"
        "if (!s) return '';\n"
        "var attrs = s.attributes || {};\n"
        "var artist = attrs.media_artist || attrs.media_album_artist || '';\n"
        "if (artist.indexOf('Listening on') >= 0 || artist.indexOf('SONOS') >= 0) artist = '';\n"
        "var track = attrs.media_title || attrs.media_series_title || '';\n"
        "if (artist) return artist + ' · ' + player;\n"
        "if (track && String(track).toLowerCase() !== 'tv') return player;\n"
        "return '';\n"
        "]]]"
    )


def _visible_entities_js(players: list[dict]) -> str:
    """JS block that builds `visible` entity ids — min slots, music-over-TV, playing+paused."""
    entities = json.dumps([p["entity"] for p in players])
    return (
        f"const MIN_SLOTS = {MIN_PLAYER_SLOTS};\n"
        f"const ALL = {entities};\n"
        "const ACTIVE_STATES = ['playing', 'paused'];\n"
        + _is_music_js_fn()
        + "\n"
        "const live = ALL.filter((id) => ACTIVE_STATES.includes(states[id]?.state));\n"
        "const anyMusic = live.some((id) => isMusic(states[id]?.attributes));\n"
        "let visible = live.filter((id) => !anyMusic || isMusic(states[id]?.attributes));\n"
        "if (visible.length < MIN_SLOTS) {\n"
        "  for (const id of ALL) {\n"
        "    if (visible.length >= MIN_SLOTS) break;\n"
        "    if (!visible.includes(id)) visible.push(id);\n"
        "  }\n"
        "}\n"
    )


def _player_show_jinja(players: list[dict], entity: str) -> str:
    """Navbar carousel visibility — matches carousel-sync.js and popup jinja templates."""
    return f"[[[\n{_visible_entities_js(players)}return visible.includes({entity!r});\n]]]"


def _navbar_player_actions(name: str) -> dict[str, dict]:
    """Select this zone, then open the popup — static per slide, no DOM sniffing."""
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
        "action": "perform-action",
        "perform_action": "input_select.select_option",
        "target": {"entity_id": MEDIA_SELECT_ENTITY},
        "data": {"option": zone},
    }


def _script_action(script_entity: str) -> dict:
    return {"action": "perform-action", "perform_action": script_entity}


def _open_player_action(zone: str) -> dict:
    """custom-js-action: select this slide's zone in input_select, then open the popup.

    Each navbar slide knows its own zone, so tapping always opens the popup on the
    right player — no DOM carousel-index sniffing required.
    """
    code = (
        "[[[\n"
        "hass.callService('input_select', 'select_option', "
        f"{{ entity_id: {MEDIA_SELECT_ENTITY!r}, option: {zone!r} }});\n"
        f"history.pushState(null, '', {FLUX_UI_MUSIC_PLAYER_PATH!r});\n"
        "window.dispatchEvent(new Event('location-changed'));\n"
        "]]]"
    )
    return {
        "action": "custom-js-action",
        "code": code,
    }


def _mediocre_player_card(entity: str, zone_name: str) -> dict:
    del zone_name
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


def _mediocre_compact_player_card(entity: str, zone_name: str) -> dict:
    """Compact mediocre card — album art + transport/volume (fits music column)."""
    del zone_name
    return {
        "type": "custom:mediocre-media-player-card",
        "entity_id": entity,
        "use_art_colors": True,
        "tap_opens_popup": False,
        "options": {
            "show_volume_step_buttons": True,
            "always_show_power_button": True,
            "hide_when_off": False,
        },
        "card_mod": {
            "style": (
                ":host, ha-card {\n"
                "  height: auto !important;\n"
                "  max-height: 100% !important;\n"
                "  min-height: 96px !important;\n"
                "  overflow: visible !important;\n"
                "  box-sizing: border-box !important;\n"
                "}\n"
                # Explicit px art — Fully Kiosk paints these; % heights under
                # the grid height:0 containment often resolve to 0.
                "img {\n"
                "  width: 88px !important;\n"
                "  height: 88px !important;\n"
                "  min-width: 88px !important;\n"
                "  min-height: 88px !important;\n"
                "  max-height: 88px !important;\n"
                "  object-fit: cover !important;\n"
                "  border-radius: 10px !important;\n"
                "  flex-shrink: 0 !important;\n"
                "  display: block !important;\n"
                "}\n"
            )
        },
    }


def _default_media_entity(cfg: dict, players: list[dict]) -> str:
    """Prefer configured default_entity when it matches an enabled player."""
    preferred = (_media_cfg(cfg).get("default_entity") or "").strip()
    entities = {p["entity"] for p in players}
    if preferred and preferred in entities:
        return preferred
    return players[0]["entity"]


def _speaker_group_entities(players: list[dict]) -> list[str]:
    """Sonos entities available for grouping / output switching."""
    return [p["entity"] for p in players if is_sonos_zone(p)]


def build_tablet_music_card(cfg: dict, *, use_mediocre: bool = True) -> dict:
    """Contained tablet music: zone chips + compact art/controls (no push-down).

    Zone chips switch the active Sonos output. Selected zone shows a compact
    mediocre (or mushroom) player. Optional group chip for multi-room join.
    """
    players = enabled_players(cfg)
    if not players:
        return {
            "type": "markdown",
            "content": (
                "No Sonos players configured. Run "
                "`discover_sonos.py --apply` or edit `media_players.yaml`."
            ),
        }

    group_entities = _speaker_group_entities(players)
    header_cards: list[dict] = [_player_selector_chips(players)]

    # Optional group chip under the zone picker — easy multi-room output.
    if use_mediocre and len(group_entities) > 1:
        header_cards.append(
            {
                "type": "custom:mediocre-chip-media-player-group-card",
                "entity_id": _default_media_entity(cfg, players),
                "entities": group_entities,
                "card_mod": {
                    "style": (
                        "ha-card {\n"
                        "  background: transparent !important;\n"
                        "  box-shadow: none !important;\n"
                        "  border: none !important;\n"
                        "  padding: 0 !important;\n"
                        "}\n"
                    )
                },
            }
        )

    cards: list[dict] = [
        {
            "type": "vertical-stack",
            "cards": header_cards,
            "card_mod": {
                "style": (
                    ":host, ha-card, #root {\n"
                    "  background: transparent !important;\n"
                    "  box-shadow: none !important;\n"
                    "  border: none !important;\n"
                    "}\n"
                    "#root { gap: 4px !important; }\n"
                )
            },
        }
    ]

    for player in players:
        cards.append(
            _tablet_zone_panel(
                player,
                use_mediocre=use_mediocre,
                source="sonos",
                group_entities=group_entities,
            )
        )
        if is_sonos_zone(player) and player.get("apple_tv"):
            cards.append(
                _tablet_zone_panel(
                    player,
                    use_mediocre=use_mediocre,
                    source="apple_tv",
                    group_entities=group_entities,
                )
            )

    return {
        "type": "vertical-stack",
        "cards": cards,
        "card_mod": {
            "style": (
                ":host, ha-card {\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  height: 100% !important;\n"
                "  min-height: 0 !important;\n"
                "}\n"
                "#root {\n"
                "  display: flex !important;\n"
                "  flex-direction: column !important;\n"
                "  height: 100% !important;\n"
                "  min-height: 0 !important;\n"
                "  gap: 6px !important;\n"
                "}\n"
                "#root > *:first-child {\n"
                "  flex: 0 0 auto !important;\n"
                "}\n"
                "#root > *:not(:first-child) {\n"
                "  flex: 1 1 auto !important;\n"
                "  min-height: 0 !important;\n"
                "}\n"
            )
        },
    }


def _tablet_zone_panel(
    player: dict,
    *,
    use_mediocre: bool,
    source: str = "sonos",
    group_entities: list[str] | None = None,
) -> dict:
    """Conditional full-height player for one Sonos / Apple TV zone."""
    entity = player["entity"]
    name = player["name"]
    sonos = is_sonos_zone(player)
    atv = player.get("apple_tv") if sonos else None
    if source == "apple_tv" and atv:
        panel_entity = atv
        panel_name = player.get("apple_tv_name") or name
    else:
        panel_entity = entity
        panel_name = name
    if use_mediocre:
        card = _mediocre_compact_player_card(panel_entity, panel_name)
        if group_entities and source == "sonos":
            card["speaker_group"] = {
                "entity_id": panel_entity,
                "entities": [e for e in group_entities if e != panel_entity] or group_entities,
            }
    else:
        card = _mushroom_player_card(panel_entity, panel_name)
    conditions: list[dict] = [
        {"condition": "state", "entity": MEDIA_SELECT_ENTITY, "state": name},
    ]
    if sonos and atv:
        tv_sensor = tv_mode_sensor_entity(player)
        if source == "apple_tv":
            conditions.append({"condition": "state", "entity": tv_sensor, "state": "on"})
        else:
            conditions.append(
                {"condition": "state", "entity": tv_sensor, "state_not": "on"}
            )
    return {
        "type": "conditional",
        "conditions": conditions,
        "card": card,
        "card_mod": {
            "style": (
                ":host, ha-card {\n"
                "  height: 100% !important;\n"
                "  min-height: 96px !important;\n"
                "  display: block !important;\n"
                "}\n"
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
            "entity": (
                _navbar_player_entity_js(entity, players)
                if is_sonos_zone(player) and player.get("apple_tv")
                else entity
            ),
            "show": _player_show_jinja(players, entity),
            "title": _navbar_player_title_js(entity, name, players),
            "subtitle": _navbar_player_subtitle_js(entity, name, players),
            **_navbar_player_actions(name),
        }
        # No `icon` here — navbar-card replaces the album artwork with it.
        entries.append(entry)

    return {
        # Per-slide artwork — widget-level blur shared one cover when swiping.
        "album_cover_background": False,
        "auto_padding": True,
        "players": entries,
    }


def _visible_zone_cycle_jinja(players: list[dict], step: int) -> str:
    """input_select option for next/prev — cycles visible carousel slots only."""
    setup = _visible_entities_jinja_setup(players)
    name_lines = []
    for p in players:
        e, n = p["entity"], p["name"]
        name_lines.append(
            f"{{% if '{e}' in ns.visible %}}{{% set ns.zones = ns.zones + ['{n}'] %}}{{% endif %}}"
        )
    step_expr = f"(i + {step}) % (ns.zones | length)"
    return (
        setup.replace("namespace(visible=[])", "namespace(visible=[], zones=[])")
        + "\n"
        + "\n".join(name_lines)
        + "\n{% set cur = states('"
        + MEDIA_SELECT_ENTITY
        + "') %}"
        "{% set i = ns.zones.index(cur) if cur in ns.zones else 0 %}"
        "{% if ns.zones | length > 0 %}"
        "{{ ns.zones[" + step_expr + "] }}"
        "{% else %}{{ cur }}{% endif %}"
    )


def _player_selector_chips(players: list[dict]) -> dict:
    """Single chip row — zone picker + prev/next (no conditional wrappers; those cause config errors)."""
    chips: list[dict] = []
    if len(players) > 1:
        chips.append(
            {
                "type": "template",
                "icon": "mdi:chevron-left",
                "icon_color": "primary",
                "tap_action": _script_action(ZONE_PREV_SCRIPT),
            }
        )
    for player in players:
        name = player["name"]
        chips.append(
            {
                "type": "template",
                "icon": player.get("icon") or (
                    "mdi:speaker" if player_source(player) == "apple" else "mdi:speaker"
                ),
                "content": name,
                "tap_action": _select_zone_action(name),
                "icon_color": (
                    "{{ 'primary' if is_state('"
                    + MEDIA_SELECT_ENTITY
                    + "', '"
                    + name
                    + "') else 'grey' }}"
                ),
            }
        )
    if len(players) > 1:
        chips.append(
            {
                "type": "template",
                "icon": "mdi:chevron-right",
                "icon_color": "primary",
                "tap_action": _script_action(ZONE_NEXT_SCRIPT),
            }
        )
    return {
        "type": "custom:mushroom-chips-card",
        "alignment": "center",
        "chips": chips,
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  --chip-height: 36px !important;\n"
                "  --chip-padding: 0 10px !important;\n"
                "  --chip-font-size: 12px !important;\n"
                "  --chip-icon-size: 18px !important;\n"
                "  --chip-spacing: 6px !important;\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  padding: 0 !important;\n"
                "}\n"
                ".chip-container, mushroom-chips-card {\n"
                "  flex-wrap: wrap !important;\n"
                "  justify-content: center !important;\n"
                "  row-gap: 6px !important;\n"
                "}\n"
            )
        },
    }


def _mushroom_player_card(entity: str, name: str) -> dict:
    return {
        "type": "custom:mushroom-media-player-card",
        "entity": entity,
        "name": name,
        "use_media_info": True,
        "show_volume_level": True,
        "collapsible_controls": False,
        "media_controls": ["on_off", "previous", "play_pause_stop", "next"],
        "volume_controls": ["volume_buttons", "volume_set"],
        "layout": "horizontal",
        "fill_container": True,
        "card_mod": {
            "style": (
                "ha-card {\n"
                "  min-height: 96px !important;\n"
                "}\n"
                "mushroom-shape-avatar, img {\n"
                "  --icon-size: 72px !important;\n"
                "  width: 72px !important;\n"
                "  height: 72px !important;\n"
                "  min-width: 72px !important;\n"
                "  min-height: 72px !important;\n"
                "}\n"
            )
        },
    }


def _player_panel(player: dict, *, use_mediocre: bool, source: str = "sonos") -> dict:
    """Sonos zone: music on Sonos entity, TV sound on linked apple_tv. apple: single panel.

    Conditional cards support ONLY state/numeric_state/screen/user conditions —
    `condition: template` renders "Configuration error". TV mode is therefore a
    backend template binary_sensor tested by state here.
    """
    entity = player["entity"]
    name = player["name"]
    sonos = is_sonos_zone(player)
    atv = player.get("apple_tv") if sonos else None
    if source == "apple_tv" and atv:
        panel_entity = atv
        panel_name = player.get("apple_tv_name") or name
    else:
        panel_entity = entity
        panel_name = name
    card = (
        _mediocre_player_card(panel_entity, panel_name)
        if use_mediocre
        else _mushroom_player_card(panel_entity, panel_name)
    )
    conditions: list[dict] = [
        {
            "condition": "state",
            "entity": MEDIA_SELECT_ENTITY,
            "state": name,
        },
    ]
    if sonos and atv:
        tv_sensor = tv_mode_sensor_entity(player)
        if source == "apple_tv":
            conditions.append(
                {"condition": "state", "entity": tv_sensor, "state": "on"}
            )
        else:
            # state_not — music panel still shows if the sensor is unknown/unavailable.
            conditions.append(
                {"condition": "state", "entity": tv_sensor, "state_not": "on"}
            )
    return {
        "type": "conditional",
        "conditions": conditions,
        "card": card,
    }


def build_music_player_popup(cfg: dict, *, use_mediocre: bool = True) -> dict | None:
    """Full-screen bubble popup — player picker + volume / skip / queue controls."""
    players = enabled_players(cfg)
    if not players:
        return None

    popup_cards: list[dict] = [
        _player_selector_chips(players),
    ]
    for player in players:
        popup_cards.append(_player_panel(player, use_mediocre=use_mediocre, source="sonos"))
        if is_sonos_zone(player) and player.get("apple_tv"):
            popup_cards.append(_player_panel(player, use_mediocre=use_mediocre, source="apple_tv"))

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


def media_zone_scripts(players: list[dict]) -> dict:
    """HA scripts — zone select / prev / next for input_select.flux_ui_media_player."""
    options = [p["name"] for p in players if p.get("enabled", True) and p.get("name")]
    if not options:
        return {}
    enabled = [p for p in players if p.get("enabled", True) and p.get("entity")]
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
                    "data": {"option": _visible_zone_cycle_jinja(enabled, 1)},
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
                    "data": {"option": _visible_zone_cycle_jinja(enabled, -1)},
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
    players_js = json.dumps([{"entity": p["entity"], "name": p["name"]} for p in players])

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        f"""\
// Generated by build_flux_ui.py — syncs Sonos zone swipes to input_select + popup artwork.
(function () {{
  const ALL_PLAYERS = {players_js};

  function isMusic(attrs) {{
    if (!attrs) return false;
    const t = String(attrs.media_content_type || '').toLowerCase();
    const app = String(attrs.app_name || '').toLowerCase();
    if (['music','artist','album','playlist','podcast','track','genre'].includes(t)) return true;
    if (['video','tvshow','movie','channel','episode'].includes(t)) return false;
    if (app.includes('tv') || app.includes('hdmi')) return false;
    if (attrs.media_artist && !attrs.media_series_title) return true;
    if (attrs.media_series_title && !attrs.media_artist) return false;
    return !!attrs.media_artist || !attrs.media_series_title;
  }}

  function visiblePlayers() {{
    const h = hass();
    if (!h) return [];
    const ACTIVE = ['playing', 'paused'];
    const live = ALL_PLAYERS.filter((p) => ACTIVE.includes(h.states[p.entity]?.state));
    const anyMusic = live.some((p) => isMusic(h.states[p.entity]?.attributes));
    let visible = live.filter((p) => !anyMusic || isMusic(h.states[p.entity]?.attributes));
    const MIN_SLOTS = {MIN_PLAYER_SLOTS};
    if (visible.length < MIN_SLOTS) {{
      for (const p of ALL_PLAYERS) {{
        if (visible.length >= MIN_SLOTS) break;
        if (!visible.find((v) => v.entity === p.entity)) visible.push(p);
      }}
    }}
    return visible;
  }}

  function visibleZoneNames() {{
    return visiblePlayers().map((p) => p.name);
  }}

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
    const zones = visibleZoneNames();
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
    const zones = visibleZoneNames();
    const idx = activeCarouselIndex();
    if (idx >= 0 && idx < zones.length) return zones[idx];
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

#!/usr/bin/env python3
"""Discover Sonos media_player entities in HA and map them to media_players.yaml."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MEDIA_PLAYERS = ROOT / "media_players.yaml"
MEDIA_PACKAGE = ROOT / "packages" / "flux_ui_media.yaml"
ROOMS = ROOT / "rooms.yaml"

sys.path.insert(0, str(ROOT / "scripts"))
from flux_media_player import ARTWORK_ATTRS, media_zone_scripts  # noqa: E402
from ha_common import DEFAULT_HA, get_token, run_async, ws_call  # noqa: E402

SONOS_HINTS = re.compile(
    r"sonos|speaker|playbar|playbase|beam|arc|move|roam|one|five|era|symfonisk",
    re.I,
)
ATV_HINTS = re.compile(r"apple.?tv|appletv|\batv\b", re.I)
ATV_STOPWORDS = frozenset({"sonos", "media", "player", "apple", "tv", "the", "room"})


def fetch_states(token: str, ha_url: str) -> list[dict]:
    req = urllib.request.Request(
        f"{ha_url}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_entity_registry(token: str, ha_url: str) -> list[dict]:
    results = run_async(ws_call(token, ha_url, [{"type": "config/entity_registry/list"}]))
    if not results or not results[0].get("success"):
        return []
    return results[0].get("result") or []


def reload_sonos_integration(token: str, ha_url: str) -> list[str]:
    """Reload Sonos config entries so HA picks up renamed speakers from the Sonos app."""
    notes: list[str] = []
    list_res = run_async(ws_call(token, ha_url, [{"type": "config_entries/list"}]))
    if not list_res or not list_res[0].get("success"):
        notes.append("Could not list config entries — reload Sonos manually in HA Settings")
        return notes

    entries = list_res[0].get("result") or []
    sonos_entries = [e for e in entries if e.get("domain") == "sonos"]
    if not sonos_entries:
        notes.append("No Sonos config entry found in Home Assistant")
        return notes

    for entry in sonos_entries:
        entry_id = entry["entry_id"]
        title = entry.get("title") or entry_id
        reload_res = run_async(
            ws_call(token, ha_url, [{"type": "config_entries/reload", "entry_id": entry_id}])
        )
        if reload_res and reload_res[0].get("success"):
            notes.append(f"Reloaded Sonos integration: {title}")
        else:
            notes.append(f"Failed to reload Sonos integration: {title}")
    # Allow Sonos integration + entity registry to settle after reload.
    time.sleep(5)
    return notes


def registry_entry(registry: list[dict], entity_id: str) -> dict | None:
    return next((e for e in registry if e.get("entity_id") == entity_id), None)


def room_keywords() -> list[str]:
    if not ROOMS.exists():
        return []
    data = yaml.safe_load(ROOMS.read_text()) or {}
    words: set[str] = set()
    for room in data.get("rooms", []):
        for key in ("name", "card_name", "path"):
            val = room.get(key)
            if val:
                words.add(str(val).lower())
        for kw in room.get("keywords") or []:
            words.add(str(kw).lower())
    return sorted(words)


def registry_sonos_media_entities(registry: list[dict]) -> set[str]:
    """Entity IDs registered under the Sonos integration."""
    out: set[str] = set()
    for ent in registry:
        eid = ent.get("entity_id") or ""
        if not eid.startswith("media_player."):
            continue
        platform = (ent.get("platform") or "").lower()
        if platform == "sonos":
            out.add(eid)
    return out


def registry_apple_tv_media_entities(registry: list[dict]) -> set[str]:
    """Entity IDs registered under the Apple TV integration."""
    out: set[str] = set()
    for ent in registry:
        eid = ent.get("entity_id") or ""
        if not eid.startswith("media_player."):
            continue
        platform = (ent.get("platform") or "").lower()
        if platform == "apple_tv":
            out.add(eid)
    return out


def label_tokens(label: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", label.lower()) if t not in ATV_STOPWORDS and len(t) > 1}


def score_atv_match(sonos_label: str, atv_label: str, keywords: list[str]) -> int:
    """Score how well an Apple TV entity matches a Sonos zone (room name overlap)."""
    s = sonos_label.lower()
    a = atv_label.lower()
    score = 0
    for kw in keywords:
        if kw in s and kw in a:
            score += 8
    score += len(label_tokens(sonos_label) & label_tokens(atv_label)) * 3
    if ATV_HINTS.search(a):
        score += 1
    return score


def match_apple_tv(
    sonos_label: str,
    atv_entities: list[str],
    *,
    states: dict[str, dict],
    registry: list[dict],
    keywords: list[str],
) -> str | None:
    best: tuple[int, str] | None = None
    for eid in atv_entities:
        state = states.get(eid) or {"entity_id": eid, "attributes": {}}
        label = friendly_label(state, registry)
        score = score_atv_match(sonos_label, label, keywords)
        if score <= 0:
            continue
        if not best or score > best[0]:
            best = (score, eid)
    return best[1] if best else None


def is_sonos_candidate(state: dict, *, registry_ids: set[str] | None = None) -> bool:
    eid = state["entity_id"]
    if not eid.startswith("media_player."):
        return False
    if registry_ids and eid in registry_ids:
        return True

    attrs = state.get("attributes") or {}
    hay = " ".join(
        [
            eid,
            str(attrs.get("friendly_name", "")),
            str(attrs.get("device_class", "")),
            str(attrs.get("app_name", "")),
            str(attrs.get("manufacturer", "")),
            str(attrs.get("model", "")),
        ]
    ).lower()
    if "sonos" in hay:
        return True
    if attrs.get("source_list") and SONOS_HINTS.search(hay):
        return True
    # Sonos speakers expose group members and volume_level.
    if attrs.get("group_members") is not None and attrs.get("volume_level") is not None:
        return True
    return False


def friendly_label(state: dict, registry: list[dict] | None = None) -> str:
    """Display name from live HA / Sonos integration (matches Sonos app after reload)."""
    eid = state["entity_id"]
    attrs = state.get("attributes") or {}

    # Prefer live state friendly_name — updates when Sonos integration reloads.
    fn = (attrs.get("friendly_name") or "").strip()
    if fn:
        return fn

    reg = registry_entry(registry or [], eid)
    if reg:
        for key in ("name", "original_name"):
            val = reg.get(key)
            if val and str(val).strip():
                return str(val).strip()

    slug = eid.replace("media_player.", "")
    return slug.replace("_", " ").title()


def score_room_match(label: str, keywords: list[str]) -> int:
    hay = label.lower()
    score = 0
    for kw in keywords:
        if kw in hay or hay in kw:
            score += 5
    return score


def load_media_config() -> dict:
    if not MEDIA_PLAYERS.exists():
        return {"enabled": True, "players": []}
    return yaml.safe_load(MEDIA_PLAYERS.read_text()) or {}


def dedupe_sonos_players(candidates: list[dict]) -> list[dict]:
    """Prefer one entity per speaker — skip _2 / _sonos_2 duplicates and unavailable copies."""
    by_base: dict[str, dict] = {}
    for state in candidates:
        eid = state["entity_id"]
        base = re.sub(r"_2$", "", eid.replace("media_player.", ""))
        base = re.sub(r"_sonos_2$", "_sonos", base)
        score = 0
        if state["state"] not in ("unavailable", "unknown"):
            score += 10
        if not eid.endswith("_2"):
            score += 5
        if "sonos" in eid.lower():
            score += 2
        prev = by_base.get(base)
        if not prev or score > prev["_score"]:
            by_base[base] = {**state, "_score": score}
    return [v for k, v in sorted(by_base.items())]


def discover_from_states(
    states: list[dict],
    *,
    registry: list[dict] | None = None,
    refresh_names: bool = True,
) -> tuple[list[dict], str | None, list[str]]:
    registry = registry or []
    registry_ids = registry_sonos_media_entities(registry)
    state_by_id = {s["entity_id"]: s for s in states}

    candidates: list[dict] = []
    if registry_ids:
        # Authoritative list: every Sonos media_player in the HA entity registry.
        for eid in sorted(registry_ids):
            candidates.append(
                state_by_id.get(eid) or {"entity_id": eid, "state": "unknown", "attributes": {}}
            )
    else:
        seen: set[str] = set()
        for s in states:
            if is_sonos_candidate(s, registry_ids=registry_ids):
                candidates.append(s)
                seen.add(s["entity_id"])

    candidates = dedupe_sonos_players(candidates)
    keywords = room_keywords()
    existing = {p.get("entity"): p for p in load_media_config().get("players", [])}
    notes: list[str] = []
    updated: list[dict] = []

    atv_registry_ids = sorted(registry_apple_tv_media_entities(registry))
    atv_state_by_id = {s["entity_id"]: s for s in states if s["entity_id"] in atv_registry_ids}

    print("Sonos / media_player candidates in HA:\n")
    for s in sorted(candidates, key=lambda x: x["entity_id"]):
        label = friendly_label(s, registry)
        print(f"  {s['entity_id']:<48} state={s['state']:<10} {label}")

    if atv_registry_ids:
        print("\nApple TV / media_player candidates in HA:\n")
        for eid in atv_registry_ids:
            s = atv_state_by_id.get(eid) or {"entity_id": eid, "state": "unknown", "attributes": {}}
            label = friendly_label(s, registry)
            print(f"  {eid:<48} state={s['state']:<10} {label}")
    else:
        print("\nNo Apple TV media_player entities found in HA entity registry.\n")

    for state in sorted(candidates, key=lambda x: friendly_label(x, registry)):
        eid = state["entity_id"]
        label = friendly_label(state, registry)
        prior = existing.get(eid, {})

        if prior.get("pin_name") and prior.get("name"):
            name = prior["name"]
        else:
            name = label

        old_name = prior.get("name")
        if old_name and old_name != name:
            notes.append(f"{eid}: name {old_name!r} -> {name!r} (from HA/Sonos)")

        room_score = score_room_match(label, keywords)
        if room_score:
            notes.append(f"{eid}: room keyword match (score={room_score})")

        entry: dict = {
            "entity": eid,
            "name": name,
            "enabled": state["state"] not in ("unavailable",),
        }

        prior_atv = prior.get("apple_tv")
        if prior.get("pin_apple_tv") and prior_atv:
            apple_tv = prior_atv
        elif prior_atv and prior_atv in atv_registry_ids:
            apple_tv = prior_atv
        elif atv_registry_ids:
            apple_tv = match_apple_tv(
                label,
                atv_registry_ids,
                states=state_by_id,
                registry=registry,
                keywords=keywords,
            )
        else:
            apple_tv = None

        if apple_tv:
            entry["apple_tv"] = apple_tv
            atv_state = atv_state_by_id.get(apple_tv) or {"attributes": {}}
            atv_label = friendly_label(atv_state, registry)
            if prior.get("apple_tv_name"):
                entry["apple_tv_name"] = prior["apple_tv_name"]
            else:
                entry["apple_tv_name"] = atv_label
            if prior_atv != apple_tv:
                notes.append(f"{eid}: linked Apple TV {apple_tv!r} ({atv_label})")
            elif not prior_atv:
                notes.append(f"{eid}: auto-linked Apple TV {apple_tv!r} ({atv_label})")

        updated.append(entry)

    default_entity: str | None = load_media_config().get("default_entity")
    if default_entity and not any(p["entity"] == default_entity for p in updated):
        notes.append(f"default_entity {default_entity!r} not found — resetting")
        default_entity = None
    if not default_entity and updated:
        default_entity = updated[0]["entity"]
        notes.append(f"default_entity: {default_entity}")

    if not updated:
        notes.append("No Sonos media_player entities found — music bar hidden until speakers appear in HA.")

    return updated, default_entity, notes


def discover(token: str, ha_url: str, **kwargs) -> tuple[list[dict], str | None, list[str]]:
    states = fetch_states(token, ha_url)
    registry = fetch_entity_registry(token, ha_url)
    return discover_from_states(states, registry=registry, **kwargs)


def audit_artwork(states: list[dict], *, registry: list[dict] | None = None) -> None:
    """Report album-art-related attributes for every Sonos media_player."""
    registry_ids = registry_sonos_media_entities(registry or [])
    candidates = dedupe_sonos_players(
        [s for s in states if is_sonos_candidate(s, registry_ids=registry_ids)]
    )
    if not candidates:
        print("No Sonos media_player entities found.")
        return

    print("\nSonos artwork audit (entity_picture and related attributes):\n")
    for state in sorted(candidates, key=lambda x: x["entity_id"]):
        eid = state["entity_id"]
        attrs = state.get("attributes") or {}
        label = friendly_label(state, registry)
        title = attrs.get("media_title") or attrs.get("media_content_type") or "—"
        artist = attrs.get("media_artist") or attrs.get("media_series_title") or "—"
        print(f"  {eid}  ({label})")
        print(f"    state={state['state']!r}  title={title!r}  artist={artist!r}")
        found_art = False
        for key in ARTWORK_ATTRS:
            val = attrs.get(key)
            if val:
                found_art = True
                preview = str(val)
                if len(preview) > 100:
                    preview = preview[:97] + "..."
                print(f"    {key}: {preview}")
        if not found_art:
            print("    artwork: (none — entity_picture only appears while playing)")
        print()


def write_media_players(players: list[dict], default_entity: str | None) -> None:
    cfg = load_media_config()
    cfg["enabled"] = cfg.get("enabled", True)
    cfg["default_entity"] = default_entity
    cfg["players"] = players
    header = (
        "# Sonos media players for Flux UI floating music bar + popup.\n"
        "# Run: python3 home-assistant/flux-ui-dashboard/scripts/discover_sonos.py --apply\n"
        "# Names refresh from HA friendly_name on each --apply (set pin_name: true to keep a custom label).\n"
        "# Optional apple_tv links each Sonos zone to its Apple TV for TV/HDMI sound (title, art, popup).\n"
        "# Set pin_apple_tv: true to keep a manual apple_tv entity when re-running --apply.\n"
        "#\n"
        "# Apple Music and Spotify stream through Sonos in HA — each speaker is a media_player entity.\n"
        "# Tap mini player to select zone; swipe carousel to switch zones (artwork syncs via carousel-sync.js).\n"
        "# Hold to open full player popup.\n\n"
    )
    MEDIA_PLAYERS.write_text(header + yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False))


def write_package(players: list[dict], default_entity: str | None) -> None:
    options = [p["name"] for p in players if p.get("enabled", True)] or ["None"]
    initial = options[0]
    if default_entity:
        for p in players:
            if p.get("entity") == default_entity:
                initial = p["name"]
                break

    entities = [p["entity"] for p in players if p.get("enabled", True) and p.get("entity")]
    header = (
        "# Flux UI media player selection (Sonos zones)\n"
        "# Options are rewritten by discover_sonos.py --apply\n"
        "# Included from configuration.yaml: homeassistant: packages: !include_dir_named packages\n\n"
    )
    data: dict = {
        "input_select": {
            "flux_ui_media_player": {
                "name": "Flux UI Media Player",
                "options": options,
                "initial": initial,
                "icon": "mdi:speaker",
            }
        },
        "script": media_zone_scripts(players),
    }
    if entities:
        choose: list[dict] = []
        for player in players:
            if not player.get("enabled", True) or not player.get("entity"):
                continue
            choose.append(
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ trigger.entity_id == '" + player["entity"] + "' }}"
                            ),
                        }
                    ],
                    "sequence": [
                        {
                            "service": "input_select.select_option",
                            "target": {"entity_id": "input_select.flux_ui_media_player"},
                            "data": {"option": player["name"]},
                        }
                    ],
                }
            )
        data["automation"] = [
            {
                "id": "flux_ui_media_player_sync",
                "alias": "Flux UI sync media player to active Sonos zone",
                "description": "Keep input_select on the Sonos zone that is actively playing.",
                "mode": "queued",
                "max": 10,
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": entities,
                        "to": ["playing"],
                    }
                ],
                "action": [{"choose": choose}],
            }
        ]
    MEDIA_PACKAGE.write_text(header + yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def expected_zone_options(players: list[dict]) -> list[str]:
    return [p["name"] for p in players if p.get("enabled", True) and p.get("name")] or ["None"]


async def sync_input_select_options_async(token: str, ha_url: str, players: list[dict]) -> list[str]:
    """Push live input_select options to match discovered Sonos zone names."""
    import asyncio

    options = expected_zone_options(players)
    notes: list[str] = []

    states_res = await ws_call(token, ha_url, [{"type": "get_states"}])
    if not states_res[0].get("success"):
        notes.append("Could not read HA states for input_select sync")
        return notes

    entity = next(
        (s for s in states_res[0].get("result", []) if s.get("entity_id") == "input_select.flux_ui_media_player"),
        None,
    )
    if not entity:
        notes.append("input_select.flux_ui_media_player missing — reload packages")
        return notes

    live_opts = list(entity.get("attributes", {}).get("options") or [])
    current = entity.get("state") or ""

    if live_opts == options:
        notes.append(f"input_select options already match Sonos ({len(options)} zones)")
        return notes

    notes.append(f"Syncing input_select options: {live_opts} -> {options}")

    set_res = await ws_call(
        token,
        ha_url,
        [
            {
                "type": "call_service",
                "domain": "input_select",
                "service": "set_options",
                "target": {"entity_id": "input_select.flux_ui_media_player"},
                "service_data": {"options": options},
            }
        ],
    )
    if set_res[0].get("success") is False:
        notes.append(f"input_select.set_options failed: {set_res[0].get('error')}")
        return notes

    await asyncio.sleep(1)

    if current not in options:
        pick = options[0]
        for player in players:
            if player.get("entity") and player.get("name"):
                pick = player["name"]
                break
        await ws_call(
            token,
            ha_url,
            [
                {
                    "type": "call_service",
                    "domain": "input_select",
                    "service": "select_option",
                    "target": {"entity_id": "input_select.flux_ui_media_player"},
                    "service_data": {"option": pick},
                }
            ],
        )
        notes.append(f"Reset input_select selection to {pick!r}")

    return notes


def sync_input_select_options(token: str, ha_url: str, players: list[dict]) -> list[str]:
    return run_async(sync_input_select_options_async(token, ha_url, players))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--apply", action="store_true", help="Write media_players.yaml and package")
    parser.add_argument(
        "--audit-artwork",
        action="store_true",
        help="Print entity_picture / album art attributes for each Sonos entity",
    )
    parser.add_argument(
        "--reload-sonos",
        action="store_true",
        help="Reload Sonos integration before discover (picks up Sonos app renames)",
    )
    parser.add_argument(
        "--no-reload-sonos",
        action="store_true",
        help="Skip Sonos reload even when using --apply",
    )
    parser.add_argument(
        "--keep-names",
        action="store_true",
        help="Do not overwrite custom names from media_players.yaml (default: refresh from HA)",
    )
    args = parser.parse_args()

    token = get_token(args.token)
    ha_url = args.ha_url
    notes: list[str] = []

    if args.reload_sonos or (args.apply and not args.no_reload_sonos):
        print("Reloading Sonos integration (sync names from Sonos app)...")
        notes.extend(reload_sonos_integration(token, ha_url))

    registry = fetch_entity_registry(token, ha_url)
    states = fetch_states(token, ha_url)
    # Re-fetch after Sonos reload so friendly_name reflects Sonos app names.
    if args.reload_sonos or (args.apply and not args.no_reload_sonos):
        time.sleep(2)
        registry = fetch_entity_registry(token, ha_url)
        states = fetch_states(token, ha_url)

    if args.audit_artwork:
        audit_artwork(states, registry=registry)
        return 0

    players, default_entity, discover_notes = discover_from_states(
        states,
        registry=registry,
        refresh_names=not args.keep_names,
    )
    notes.extend(discover_notes)

    if notes:
        print("\nMapping:")
        for line in notes:
            print(f"  {line}")

    if args.apply:
        write_media_players(players, default_entity)
        write_package(players, default_entity)
        print(f"\nUpdated {MEDIA_PLAYERS}")
        print(f"Updated {MEDIA_PACKAGE}")
        sync_notes = sync_input_select_options(token, ha_url, players)
        for line in sync_notes:
            print(f"  {line}")
        if not players:
            print("WARNING: No Sonos players discovered — music bar will be hidden")
            return 1
    else:
        print("\nDry run — re-run with --apply to update media_players.yaml")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

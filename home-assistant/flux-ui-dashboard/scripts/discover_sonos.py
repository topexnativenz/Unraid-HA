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
    time.sleep(3)
    return notes


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
    attrs = state.get("attributes") or {}
    fn = (attrs.get("friendly_name") or "").strip()
    if fn:
        return fn
    if registry:
        reg = next((e for e in registry if e.get("entity_id") == state["entity_id"]), None)
        if reg and reg.get("name"):
            return str(reg["name"]).strip()
    slug = state["entity_id"].replace("media_player.", "")
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

    # Include registry Sonos entities even if state fetch missed them.
    candidates: list[dict] = []
    seen: set[str] = set()
    for eid in sorted(registry_ids):
        seen.add(eid)
        candidates.append(state_by_id.get(eid) or {"entity_id": eid, "state": "unknown", "attributes": {}})
    for s in states:
        if s["entity_id"] in seen:
            continue
        if is_sonos_candidate(s, registry_ids=registry_ids):
            candidates.append(s)

    candidates = dedupe_sonos_players(candidates)
    keywords = room_keywords()
    existing = {p.get("entity"): p for p in load_media_config().get("players", [])}
    notes: list[str] = []
    updated: list[dict] = []

    print("Sonos / media_player candidates in HA:\n")
    for s in sorted(candidates, key=lambda x: x["entity_id"]):
        label = friendly_label(s, registry)
        print(f"  {s['entity_id']:<48} state={s['state']:<10} {label}")

    for state in sorted(candidates, key=lambda x: friendly_label(x, registry)):
        eid = state["entity_id"]
        label = friendly_label(state, registry)
        prior = existing.get(eid, {})

        if refresh_names or not prior.get("name"):
            name = label
        elif prior.get("pin_name"):
            name = prior.get("name") or label
        else:
            name = label

        old_name = prior.get("name")
        if old_name and old_name != name:
            notes.append(f"{eid}: name {old_name!r} -> {name!r} (from HA/Sonos)")

        room_score = score_room_match(label, keywords)
        if room_score:
            notes.append(f"{eid}: room keyword match (score={room_score})")

        updated.append(
            {
                "entity": eid,
                "name": name,
                "enabled": state["state"] not in ("unavailable",),
            }
        )

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
        "#\n"
        "# Apple Music and Spotify stream through Sonos in HA — each speaker is a media_player entity.\n"
        "# Tap mini player to select zone; hold to open full player. Swipe then tap to sync artwork.\n\n"
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
        "script": media_zone_scripts(options),
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
                "description": "Keep input_select on the Sonos zone that is playing or paused.",
                "mode": "queued",
                "max": 10,
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": entities,
                        "to": ["playing", "paused"],
                    }
                ],
                "action": [{"choose": choose}],
            }
        ]
    MEDIA_PACKAGE.write_text(header + yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


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
    else:
        print("\nDry run — re-run with --apply to update media_players.yaml")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Discover Sonos media_player entities in HA and map them to media_players.yaml."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MEDIA_PLAYERS = ROOT / "media_players.yaml"
MEDIA_PACKAGE = ROOT / "packages" / "flux_ui_media.yaml"
ROOMS = ROOT / "rooms.yaml"

sys.path.insert(0, str(ROOT / "scripts"))
from ha_common import DEFAULT_HA, get_token  # noqa: E402

SONOS_HINTS = re.compile(r"sonos|speaker|playbar|playbase|beam|arc|move|roam|one|five|era", re.I)


def fetch_states(token: str, ha_url: str) -> list[dict]:
    req = urllib.request.Request(
        f"{ha_url}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


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


def is_sonos_candidate(state: dict) -> bool:
    eid = state["entity_id"]
    if not eid.startswith("media_player."):
        return False
    attrs = state.get("attributes") or {}
    hay = " ".join(
        [
            eid,
            str(attrs.get("friendly_name", "")),
            str(attrs.get("device_class", "")),
            str(attrs.get("app_name", "")),
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


def friendly_label(state: dict) -> str:
    attrs = state.get("attributes") or {}
    fn = (attrs.get("friendly_name") or "").strip()
    if fn:
        return fn
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


def load_package() -> dict:
    if not MEDIA_PACKAGE.exists():
        return {"input_select": {"flux_ui_media_player": {"options": ["None"]}}}
    return yaml.safe_load(MEDIA_PACKAGE.read_text()) or {}


def dedupe_sonos_players(candidates: list[dict]) -> list[dict]:
    """Prefer one entity per speaker — skip _sonos_2 duplicates and unavailable copies."""
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


def discover(token: str, ha_url: str) -> tuple[list[dict], str | None, list[str]]:
    states = fetch_states(token, ha_url)
    candidates = dedupe_sonos_players([s for s in states if is_sonos_candidate(s)])
    keywords = room_keywords()
    existing = {p.get("entity"): p for p in load_media_config().get("players", [])}
    notes: list[str] = []
    updated: list[dict] = []

    print("Sonos / media_player candidates in HA:\n")
    for s in sorted(candidates, key=lambda x: x["entity_id"]):
        fn = (s.get("attributes") or {}).get("friendly_name", "")
        print(f"  {s['entity_id']:<48} state={s['state']:<10} {fn}")

    for state in sorted(candidates, key=lambda x: friendly_label(x)):
        eid = state["entity_id"]
        label = friendly_label(state)
        prior = existing.get(eid, {})
        name = prior.get("name") or label
        room_score = score_room_match(label, keywords)
        if room_score and not prior.get("name"):
            notes.append(f"{eid}: matched room keywords (score={room_score})")

        updated.append(
            {
                "entity": eid,
                "name": name,
                "enabled": state["state"] not in ("unavailable",),
            }
        )

    default_entity: str | None = load_media_config().get("default_entity")
    if not default_entity and updated:
        default_entity = updated[0]["entity"]
        notes.append(f"default_entity: {default_entity}")

    if not updated:
        notes.append("No Sonos media_player entities found — music bar will be hidden until speakers appear in HA.")

    return updated, default_entity, notes


def write_media_players(players: list[dict], default_entity: str | None) -> None:
    cfg = load_media_config()
    cfg["enabled"] = cfg.get("enabled", True)
    cfg["default_entity"] = default_entity
    cfg["players"] = players
    header = (
        "# Sonos media players for Flux UI floating music bar + popup.\n"
        "# Run: python3 home-assistant/flux-ui-dashboard/scripts/discover_sonos.py --apply\n"
        "#\n"
        "# Apple Music and Spotify stream through Sonos in HA — each speaker is a media_player entity.\n"
        "# The navbar mini player shows all active players; tap opens #music-player for volume + queue.\n\n"
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

    header = (
        "# Flux UI media player selection (Sonos zones)\n"
        "# Options are rewritten by discover_sonos.py --apply\n"
        "# Included from configuration.yaml: homeassistant: packages: !include_dir_named packages\n\n"
    )
    data = {
        "input_select": {
            "flux_ui_media_player": {
                "name": "Flux UI Media Player",
                "options": options,
                "initial": initial,
                "icon": "mdi:speaker",
            }
        }
    }
    MEDIA_PACKAGE.write_text(header + yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--apply", action="store_true", help="Write media_players.yaml and package")
    args = parser.parse_args()

    token = get_token(args.token)
    players, default_entity, notes = discover(token, args.ha_url)

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

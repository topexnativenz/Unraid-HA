#!/usr/bin/env python3
"""Discover Tapo / climate / motion sensors and map them to Flux UI rooms."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import DEFAULT_HA, get_token  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROOMS = ROOT / "rooms.yaml"
OUTPUT = ROOT / "room_sensors.yaml"

ROOM_KEYWORDS: dict[str, list[str]] = {
    "kitchen": ["kitchen", "dining", "bar", "breakfast", "stove"],
    "living": ["living", "lounge", "media", "atrium", "sofa", "white lounge"],
    "entry": ["entry", "arrival", "front door", "outside entry", "covered entry"],
    "master-bedroom": ["master", "bedroom", "bed"],
    "hall": ["hall", "stair", "footlight", "passage", "stairs"],
    "garage": ["garage", "shed", "exterior", "outside garage", "carport"],
}

TEMP_CLASSES = {"temperature"}
HUMIDITY_CLASSES = {"humidity"}
MOTION_CLASSES = {"motion", "occupancy", "presence"}
CONTACT_CLASSES = {"door", "garage_door", "opening", "window"}


def fetch_states(token: str, ha_url: str) -> list[dict]:
    req = urllib.request.Request(
        f"{ha_url}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _haystack(state: dict) -> str:
    attrs = state.get("attributes") or {}
    parts = [
        state.get("entity_id", ""),
        str(attrs.get("friendly_name", "")),
        str(attrs.get("area_id", "")),
        str(attrs.get("device_class", "")),
    ]
    return " ".join(parts).lower()


def _score(state: dict, keywords: list[str]) -> int:
    hay = _haystack(state)
    score = 0
    for kw in keywords:
        if kw in hay:
            score += 3 if " " not in kw else 2
    if "tapo" in hay:
        score += 1
    return score


def _best_match(states: list[dict], keywords: list[str], *, domain: str, classes: set[str]) -> str | None:
    best_id: str | None = None
    best_score = 0
    for state in states:
        eid = state["entity_id"]
        if not eid.startswith(f"{domain}."):
            continue
        attrs = state.get("attributes") or {}
        dc = str(attrs.get("device_class", ""))
        hay = _haystack(state)
        class_ok = dc in classes or any(c in hay for c in classes)
        if not class_ok:
            continue
        score = _score(state, keywords)
        if score > best_score:
            best_score = score
            best_id = eid
    return best_id if best_score > 0 else None


def _indicator_candidates(states: list[dict], keywords: list[str], limit: int = 4) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()

    def add(
        entity_id: str,
        *,
        color_on: str = "#FFD54F",
        color_off: str | None = None,
        icon: str | None = None,
        icon_closed: str | None = None,
    ) -> None:
        if entity_id in seen or len(out) >= limit:
            return
        seen.add(entity_id)
        item: dict = {"entity": entity_id, "color_on": color_on}
        if color_off:
            item["color_off"] = color_off
        if icon:
            item["icon"] = icon
        if icon_closed:
            item["icon_closed"] = icon_closed
        out.append(item)

    temp = _best_match(states, keywords, domain="sensor", classes=TEMP_CLASSES | {"temperature"})
    humid = _best_match(states, keywords, domain="sensor", classes=HUMIDITY_CLASSES | {"humidity"})
    if temp:
        add(temp, color_on="#80DEEA", icon="mdi:thermometer")
    if humid:
        add(humid, color_on="#81C784", icon="mdi:water-percent")

    for state in sorted(states, key=lambda s: -_score(s, keywords)):
        eid = state["entity_id"]
        if _score(state, keywords) <= 0:
            continue
        if eid.startswith("binary_sensor."):
            dc = str((state.get("attributes") or {}).get("device_class", ""))
            if dc in MOTION_CLASSES or "motion" in eid or "occupancy" in eid:
                add(eid, color_on="#B388FF", icon="mdi:motion-sensor", icon_closed="mdi:motion-sensor-off")
            elif dc in CONTACT_CLASSES or "contact" in eid or "door" in eid:
                add(
                    eid,
                    color_on="#F2B8B5",
                    color_off="#81C784",
                    icon="mdi:garage-open",
                    icon_closed="mdi:garage",
                )
        elif eid.startswith("sensor."):
            dc = str((state.get("attributes") or {}).get("device_class", ""))
            if dc in TEMP_CLASSES:
                add(eid, color_on="#80DEEA", icon="mdi:thermometer")
            elif dc in HUMIDITY_CLASSES:
                add(eid, color_on="#81C784", icon="mdi:water-percent")

    return out[:limit]


def discover(states: list[dict], rooms: list[dict]) -> dict:
    overrides: dict[str, dict] = {}
    for room in rooms:
        path = room["path"]
        keywords = room.get("keywords") or ROOM_KEYWORDS.get(path, [])
        if not keywords:
            continue
        entry: dict = {}
        temp = _best_match(states, keywords, domain="sensor", classes=TEMP_CLASSES | {"temperature"})
        humid = _best_match(states, keywords, domain="sensor", classes=HUMIDITY_CLASSES | {"humidity"})
        if temp:
            entry["temperature_entity"] = temp
        if humid:
            entry["humidity_entity"] = humid
        indicators = _indicator_candidates(states, keywords)
        if indicators:
            entry["indicators"] = indicators
        if entry:
            overrides[path] = entry
    return overrides


def merge_rooms(rooms: list[dict], overrides: dict) -> list[dict]:
    merged: list[dict] = []
    for room in rooms:
        out = dict(room)
        extra = overrides.get(room["path"], {})
        for key, value in extra.items():
            if key == "indicators" and room.get("indicators"):
                continue
            out[key] = value
        merged.append(out)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rooms = yaml.safe_load(ROOMS.read_text()).get("rooms", [])
    try:
        token = get_token(args.token)
        states = fetch_states(token, args.ha_url)
    except Exception as exc:
        print(f"Discovery skipped: {exc}")
        return 1

    overrides = discover(states, rooms)
    payload = {
        "#": "Auto-generated by discover_room_sensors.py — re-run after adding Tapo devices",
        "overrides": overrides,
    }

    if args.dry_run:
        print(yaml.dump(payload, default_flow_style=False, sort_keys=False))
        return 0

    args.output.write_text(yaml.dump(payload, default_flow_style=False, sort_keys=False))
    print(f"Wrote {args.output} ({len(overrides)} rooms mapped)")
    for path, data in overrides.items():
        print(f"  {path}: {data}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

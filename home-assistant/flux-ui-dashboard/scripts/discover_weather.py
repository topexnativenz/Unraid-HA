#!/usr/bin/env python3
"""Pick NZ MetService weather entity in HA and update entities.yaml + overview_tabs.yaml."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
OVERVIEW_TABS = ROOT / "overview_tabs.yaml"

sys.path.insert(0, str(ROOT / "scripts"))
from ha_common import DEFAULT_HA, get_token  # noqa: E402

METSERVICE_HINT = re.compile(r"metservice|met service", re.I)


def fetch_states(token: str, ha_url: str) -> list[dict]:
    req = urllib.request.Request(
        f"{ha_url}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json

        return json.loads(resp.read())


def score_weather(state: dict) -> int:
    eid = state["entity_id"]
    if not eid.startswith("weather."):
        return -1
    fn = str((state.get("attributes") or {}).get("friendly_name") or "")
    score = 0
    if METSERVICE_HINT.search(eid) or METSERVICE_HINT.search(fn):
        score += 100
    if eid == "weather.metservice":
        score += 50
    if "forecast_home" in eid or "met_no" in eid or eid == "weather.home":
        score -= 40
    return score


def pick_metservice_entity(states: list[dict]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for state in states:
        score = score_weather(state)
        if score >= 0:
            candidates.append((score, state["entity_id"]))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][1]


def update_yaml_weather(path: Path, entity_id: str, *, key_path: tuple[str, ...]) -> bool:
    if not path.exists():
        return False
    data = yaml.safe_load(path.read_text()) or {}
    cur: dict = data
    for key in key_path[:-1]:
        cur = cur.setdefault(key, {})
    leaf = key_path[-1]
    if cur.get(leaf) == entity_id:
        return False
    cur[leaf] = entity_id
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    token = get_token(args.token)
    states = fetch_states(token, args.ha_url)
    picked = pick_metservice_entity(states)

    weather_entities = sorted(s["entity_id"] for s in states if s["entity_id"].startswith("weather."))
    print("Weather entities in HA:")
    for eid in weather_entities:
        st = next(s for s in states if s["entity_id"] == eid)
        fn = (st.get("attributes") or {}).get("friendly_name") or "—"
        mark = " ← selected" if eid == picked else ""
        print(f"  {eid:<40} {fn}{mark}")

    if not picked:
        print("\nWARNING: No MetService weather entity found — add HACS metservice-weather integration")
        return 1

    if not args.apply:
        print(f"\nDry run — re-run with --apply to set weather: {picked}")
        return 0

    changed = update_yaml_weather(ENTITIES, picked, key_path=("weather",))
    if OVERVIEW_TABS.exists():
        changed = (
            update_yaml_weather(OVERVIEW_TABS, picked, key_path=("events", "weather_entity"))
            or changed
        )
    wp = ROOT / "weather_panel.yaml"
    if wp.exists():
        changed = update_yaml_weather(wp, picked, key_path=("weather_entity",)) or changed
    print(f"\nUpdated weather entity to {picked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

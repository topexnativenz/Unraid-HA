#!/usr/bin/env python3
"""One-shot sync: set input_boolean tracked state from Tapo contact sensors."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
ENTITIES = REPO / "entities.yaml"


def get_token(explicit: str | None) -> str:
    if explicit:
        return explicit
    import os

    if os.environ.get("HA_TOKEN"):
        return os.environ["HA_TOKEN"]
    mcp = Path.home() / ".cursor/mcp.json"
    alt = Path("/Users/topexnative/.cursor/mcp.json")
    for path in (mcp, alt):
        if path.exists():
            data = json.loads(path.read_text())
            auth = data["mcpServers"]["homeassistant"]["headers"]["Authorization"]
            return auth.split(" ", 1)[1]
    raise SystemExit("No HA token")


def ha_state(token: str, ha_url: str, entity_id: str) -> str:
    req = urllib.request.Request(
        f"{ha_url}/api/states/{entity_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["state"]


def is_open(state: str, *, invert: bool) -> bool:
    if state in ("unknown", "unavailable"):
        return False
    return state == "off" if invert else state == "on"


def sync_bool(token: str, ha_url: str, tracked: str, sensor: str, invert: bool) -> None:
    state = ha_state(token, ha_url, sensor)
    want_on = is_open(state, invert=invert)
    svc = "input_boolean.turn_on" if want_on else "input_boolean.turn_off"
    req = urllib.request.Request(
        f"{ha_url}/api/services/{svc.replace('.', '/')}",
        data=json.dumps({"entity_id": tracked}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req):
        pass
    print(f"  {tracked} -> {'on' if want_on else 'off'} (from {sensor}={state})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default="http://192.168.1.239:8123")
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    token = get_token(args.token)
    doors = yaml.safe_load(ENTITIES.read_text()).get("doors", [])
    print("Syncing tracked state from Tapo sensors:")
    for door in doors:
        sync_bool(token, args.ha_url, door["tracked"], door["sensor"], door.get("invert", False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

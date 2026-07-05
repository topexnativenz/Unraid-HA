#!/usr/bin/env python3
"""One-shot sync: set input_boolean tracked state from Tapo contact sensors."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
ENTITIES = REPO / "entities.yaml"
sys.path.insert(0, str(REPO))

from garage_ui_helpers import is_open_state, load_garage_doors  # noqa: E402


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


def ha_state(token: str, ha_url: str, entity_id: str) -> str | None:
    req = urllib.request.Request(
        f"{ha_url}/api/states/{entity_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["state"]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def is_open(state: str, *, invert: bool) -> bool:
    return is_open_state(state, invert=invert)


def sync_bool(token: str, ha_url: str, name: str, tracked: str, sensor: str, invert: bool) -> bool:
    state = ha_state(token, ha_url, sensor)
    if state is None:
        print(
            f"  SKIP {name}: {sensor} not found in HA (404).\n"
            f"       Update home-assistant/garage-doors/entities.yaml with your Tapo sensor ID."
        )
        return False

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
    print(f"  OK   {name}: {tracked} -> {'on' if want_on else 'off'} (from {sensor}={state})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default="http://192.168.1.239:8123")
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    token = get_token(args.token)
    doors = load_garage_doors()
    print("Syncing tracked state from Tapo sensors:")
    ok = 0
    skipped = 0
    for door in doors:
        if sync_bool(
            token,
            args.ha_url,
            door["name"],
            door["tracked"],
            door["sensor"],
            door.get("invert", False),
        ):
            ok += 1
        else:
            skipped += 1

    if skipped:
        print(
            f"\nWarning: {skipped} sensor(s) missing — garage icons may be wrong until "
            "entities.local.yaml is updated (run discover_garage_doors.py --apply)."
        )
        print("Run: python3 home-assistant/garage-doors/scripts/list_garage_sensors.py")
    print(f"Synced {ok}/{len(doors)} doors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""List HA binary_sensor entities that may be Tapo garage/shed contacts."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

KEYWORDS = ("garage", "shed", "door", "contact", "tapo", "t110", "t100", "is_open")
DEFAULT_HA = "http://192.168.1.239:8123"


def get_token(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.environ.get("HA_TOKEN"):
        return os.environ["HA_TOKEN"]
    for path in (
        Path.home() / ".cursor/mcp.json",
        Path("/Users/topexnative/.cursor/mcp.json"),
    ):
        if path.exists():
            data = json.loads(path.read_text())
            auth = data["mcpServers"]["homeassistant"]["headers"]["Authorization"]
            return auth.split(" ", 1)[1]
    raise SystemExit("No HA token — set HA_TOKEN or pass --token")


def fetch_states(token: str, ha_url: str) -> list[dict]:
    req = urllib.request.Request(
        f"{ha_url}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    token = get_token(args.token)
    states = fetch_states(token, args.ha_url)
    matches = [
        s
        for s in states
        if s["entity_id"].startswith("binary_sensor.")
        and any(k in s["entity_id"].lower() or k in str(s.get("attributes", {})).lower() for k in KEYWORDS)
    ]

    if not matches:
        print("No matching binary_sensor entities found.")
        print("Open HA → Developer Tools → States and search: tapo, garage, contact")
        return 1

    print("Candidate Tapo / garage contact sensors:\n")
    for s in sorted(matches, key=lambda x: x["entity_id"]):
        name = s["attributes"].get("friendly_name", "")
        print(f"  {s['entity_id']:<55} state={s['state']:<12} {name}")

    print("\nCopy the correct IDs into home-assistant/garage-doors/entities.yaml")
    print("Or run: python3 home-assistant/garage-doors/scripts/discover_garage_doors.py --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

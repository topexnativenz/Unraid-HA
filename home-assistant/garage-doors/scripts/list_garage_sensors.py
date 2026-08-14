#!/usr/bin/env python3
"""List HA binary_sensor entities that may be Tapo garage/shed contacts."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "flux-ui-dashboard" / "scripts"))

from ha_common import DEFAULT_HA, get_token  # noqa: E402

KEYWORDS = ("garage", "shed", "door", "contact", "tapo", "t110", "t100", "is_open")


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

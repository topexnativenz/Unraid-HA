#!/usr/bin/env python3
"""Print Tessie/garage arrival entity states and recent automation traces from HA."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_HA = "http://192.168.1.239:8123"

WATCH_ENTITIES = (
    "input_boolean.gate_arrival_session",
    "input_boolean.gate_departure_in_progress",
    "input_boolean.model_s_was_away",
    "input_boolean.model_x_was_away",
    "binary_sensor.model_s_tessie_in_road_approach",
    "binary_sensor.model_s_tessie_in_gate_approach",
    "binary_sensor.model_x_tessie_in_road_approach",
    "binary_sensor.model_x_tessie_in_gate_approach",
    "sensor.model_s_tessie_distance_to_gate",
    "sensor.model_s_tessie_distance_to_home",
    "sensor.model_x_tessie_distance_to_gate",
    "sensor.model_x_tessie_distance_to_home",
    "sensor.model_x_tessie_latitude",
    "sensor.model_x_tessie_longitude",
    "binary_sensor.house_garage_door_is_open",
    "binary_sensor.house_garage_door_sensor_door",
    "switch.garage_door_3",
    "input_text.gate_status_message",
)

WATCH_AUTOMATIONS = (
    "automation.gate_open_on_tessie_arrival_model_x",
    "automation.gate_open_on_arrival",
    "automation.house_garage_open_on_gate_session",
    "automation.house_garage_open_on_tessie_arrival",
    "automation.house_garage_open_on_tessie_arrival_model_s_or_x",
)


def get_token(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.environ.get("HA_TOKEN"):
        return os.environ["HA_TOKEN"]
    for path in (Path.home() / ".cursor/mcp.json", Path("/Users/topexnative/.cursor/mcp.json")):
        if path.exists():
            data = json.loads(path.read_text())
            auth = data["mcpServers"]["homeassistant"]["headers"]["Authorization"]
            return auth.split(" ", 1)[1]
    raise SystemExit("No HA token")


def ha_get(token: str, ha_url: str, path: str) -> dict | list:
    req = urllib.request.Request(
        f"{ha_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", DEFAULT_HA))
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    token = get_token(args.token)
    print(f"HA: {args.ha_url}\n")

    print("=== Entity states ===")
    missing = 0
    for eid in WATCH_ENTITIES:
        try:
            st = ha_get(token, args.ha_url, f"/api/states/{eid}")
            fn = st.get("attributes", {}).get("friendly_name", "")
            print(f"  {eid:<52} {st['state']:<12} {fn}")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                print(f"  {eid:<52} {'MISSING':<12}")
                missing += 1
            else:
                raise

    if missing:
        print(f"\n⚠ {missing} entity/entities missing — automations cannot trigger on those.")

    print("\n=== Automation states ===")
    all_auto = ha_get(token, args.ha_url, "/api/states")
    auto_map = {s["entity_id"]: s for s in all_auto if s["entity_id"].startswith("automation.")}
    keywords = ("gate", "garage", "tessie", "house_garage")
    for eid, st in sorted(auto_map.items()):
        if any(k in eid for k in keywords):
            last = st.get("last_triggered") or "never"
            print(f"  {eid:<60} last={last}")

    print("\n=== Recent logbook (gate/garage, last 6h) ===")
    try:
        entries = ha_get(
            token,
            args.ha_url,
            "/api/logbook/"
            + datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
            + "?entity=automation.gate_open_on_tessie_arrival_model_x"
            + "&entity=automation.house_garage_open_on_gate_session"
            + "&entity=automation.house_garage_open_on_tessie_arrival"
            + "&entity=input_boolean.gate_arrival_session"
            + "&entity=script.house_garage_open_if_closed",
        )
        if isinstance(entries, list):
            for row in entries[-30:]:
                when = row.get("when", "")[:19]
                name = row.get("name", row.get("entity_id", ""))
                state = row.get("state", "")
                print(f"  {when}  {name}  {state}")
        else:
            print("  (logbook unavailable)")
    except urllib.error.HTTPError:
        print("  (logbook API failed — check traces in HA UI instead)")

    print("\nDone. In HA: Settings → Automations → Traces on gate/garage automations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create or update Gate Approach / Road Approach zones in the HA UI registry.

Zones defined in YAML cannot be moved on the map. This script uses the
Home Assistant WebSocket API (zone/create, zone/update) so you can drag
them under Settings → Areas & zones → Zones.

Optional defaults from /config/secrets.yaml:
  gate_latitude, gate_longitude, gate_approach_radius
  road_approach_latitude, road_approach_longitude, road_approach_radius

Usage:
  python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/gate/scripts/ensure_gate_zones.py
  python3 .../ensure_gate_zones.py --ha-url http://192.168.1.239:8123 --update-existing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

import websockets

DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/private/tmp/ha-config-smb"

ZONE_SPECS = [
    {
        "name": "Gate Approach",
        "icon": "mdi:gate-arrow-right",
        "secret_lat": "gate_latitude",
        "secret_lon": "gate_longitude",
        "secret_radius": "gate_approach_radius",
        "default_lat": -35.69110,
        "default_lon": 174.2669872,
        "default_radius": 120,
    },
    {
        "name": "Road Approach",
        "icon": "mdi:road-variant",
        "secret_lat": "road_approach_latitude",
        "secret_lon": "road_approach_longitude",
        "secret_radius": "road_approach_radius",
        # On Three Mile Bush Road upstream (~450 m radius for ~30 s Tessie GPS cadence)
        "default_lat": -35.68926,
        "default_lon": 174.26696,
        "default_radius": 450,
    },
]


def get_token() -> str:
    mcp = Path.home() / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    return data["mcpServers"]["homeassistant"]["headers"]["Authorization"].split(" ", 1)[1]


def parse_secrets(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^([a-z0-9_]+):\s*(.+)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip("'\"")
    return out


def zone_coords(secrets: dict[str, str], spec: dict) -> tuple[float, float, float]:
    lat = float(secrets.get(spec["secret_lat"], spec["default_lat"]))
    lon = float(secrets.get(spec["secret_lon"], spec["default_lon"]))
    radius = float(secrets.get(spec["secret_radius"], spec["default_radius"]))
    return lat, lon, radius


async def list_zones(call) -> list[dict]:
    msg = await call(type="zone/list")
    return msg.get("result", [])


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--secrets", default=f"{DEFAULT_MOUNT}/secrets.yaml")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update coordinates of existing UI zones from secrets/defaults",
    )
    parser.add_argument(
        "--delete-yaml-zones-first",
        action="store_true",
        help="Delete zones by name before create (use after removing zone: from YAML and reloading core config)",
    )
    args = parser.parse_args()

    secrets = parse_secrets(Path(args.secrets))
    token = get_token()
    ws_url = args.ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"HA auth failed: {auth}")
        mid = 0

        async def call(**kwargs):
            nonlocal mid
            mid += 1
            kwargs["id"] = mid
            await ws.send(json.dumps(kwargs))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == mid:
                    if not msg.get("success", True) and msg.get("error"):
                        raise RuntimeError(msg["error"])
                    return msg

        existing = await list_zones(call)
        by_name = {z.get("name"): z for z in existing}

        if args.delete_yaml_zones_first:
            for spec in ZONE_SPECS:
                z = by_name.get(spec["name"])
                if z and z.get("id"):
                    await call(type="zone/delete", zone_id=z["id"])
                    print(f"Deleted zone {spec['name']} ({z['id']})")
            existing = await list_zones(call)
            by_name = {z.get("name"): z for z in existing}

        for spec in ZONE_SPECS:
            lat, lon, radius = zone_coords(secrets, spec)
            z = by_name.get(spec["name"])

            if z is None:
                res = await call(
                    type="zone/create",
                    name=spec["name"],
                    latitude=lat,
                    longitude=lon,
                    radius=radius,
                    icon=spec["icon"],
                )
                print(
                    f"Created {spec['name']}: lat={lat}, lon={lon}, r={radius} m "
                    f"(id={res.get('result', {}).get('id', '?')})"
                )
                continue

            zone_id = z.get("id")
            if args.update_existing and zone_id:
                await call(
                    type="zone/update",
                    zone_id=zone_id,
                    latitude=lat,
                    longitude=lon,
                    radius=radius,
                    icon=spec["icon"],
                )
                print(f"Updated {spec['name']}: lat={lat}, lon={lon}, r={radius} m")
            else:
                print(
                    f"Exists {spec['name']}: lat={z.get('latitude')}, lon={z.get('longitude')}, "
                    f"r={z.get('radius')} m — drag on HA map or run with --update-existing"
                )

    print("\nNext: Settings → Areas & zones → Zones — drag circles on the map.")
    print("Companion app → Manage zones → re-sync Home Assistant zones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

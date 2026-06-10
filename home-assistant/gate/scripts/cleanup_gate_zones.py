#!/usr/bin/env python3
"""Remove duplicate/stale gate zones and leave one UI-editable pair.

Run after removing zone: blocks from YAML packages and reloading core config.
A full HA restart also helps clear stale zone entities.

Usage:
  python3 .../cleanup_gate_zones.py
  python3 .../cleanup_gate_zones.py --recreate
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import websockets

DEFAULT_HA = "http://192.168.1.239:8123"
NAMES = ("Gate Approach", "Road Approach")


def get_token() -> str:
    mcp = Path.home() / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    return data["mcpServers"]["homeassistant"]["headers"]["Authorization"].split(" ", 1)[1]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="After delete, run ensure_gate_zones.py logic inline",
    )
    args = parser.parse_args()
    token = get_token()
    ws_url = args.ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(auth)
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

        listed = (await call(type="zone/list")).get("result", [])
        for z in listed:
            if z.get("name") in NAMES and z.get("id"):
                await call(type="zone/delete", zone_id=z["id"])
                print(f"Deleted {z.get('name')} (id={z['id']})")

    if args.recreate:
        import subprocess

        ensure = Path(__file__).resolve().parent / "ensure_gate_zones.py"
        subprocess.check_call(["python3", str(ensure), "--ha-url", args.ha_url])

    print("\nRestart Home Assistant (Settings → System → Restart) if duplicate or YAML zones still appear.")
    print("Then drag zones on the map — only entries with a pencil icon are the ones automations should use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

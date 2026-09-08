#!/usr/bin/env python3
"""Set a system-wide default dashboard panel on Home Assistant (iOS Companion)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import websockets

DEFAULT_HA = os.environ.get("HA_URL", "http://192.168.1.239:8123")
DEFAULT_PANEL = "flux-ui"


def get_token() -> str:
    if os.environ.get("HA_TOKEN"):
        return os.environ["HA_TOKEN"]
    for path in (Path.home() / ".cursor" / "mcp.json", Path("/Users/topexnative/.cursor/mcp.json")):
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        auth = data["mcpServers"]["homeassistant"]["headers"]["Authorization"]
        return auth.split(" ", 1)[1]
    raise RuntimeError("No HA token — set HA_TOKEN or provide ~/.cursor/mcp.json")


def normalize_url(url: str) -> str:
    url = url.rstrip("/")
    for suffix in ("/mcp_server/sse", "/api/mcp/sse", "/sse"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url.rstrip("/")


async def run(ha_url: str, panel: str, user_panel: bool) -> None:
    token = get_token()
    ha_url = normalize_url(ha_url)
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"HA auth failed: {auth}")

        await ws.send(
            json.dumps(
                {
                    "type": "frontend/set_system_data",
                    "key": "core",
                    "value": {"default_panel": panel},
                    "id": 1,
                }
            )
        )
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == 1:
                if not r.get("success"):
                    raise RuntimeError(f"set_system_data failed: {r.get('error')}")
                break

        if user_panel:
            await ws.send(
                json.dumps(
                    {
                        "type": "frontend/set_user_data",
                        "key": "core",
                        "value": {"default_panel": panel, "showAdvanced": True},
                        "id": 2,
                    }
                )
            )
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == 2:
                    if not r.get("success"):
                        raise RuntimeError(f"set_user_data failed: {r.get('error')}")
                    break

        await ws.send(json.dumps({"type": "frontend/get_system_data", "key": "core", "id": 3}))
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == 3:
                print("System default_panel:", r["result"]["value"]["default_panel"])
                break

    print(f"Default dashboard set to '{panel}' for all users on this HA instance.")
    print("On iPhone: force-quit Companion, then App Configuration → Debugging → Reset Frontend Cache.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument(
        "--panel",
        default=DEFAULT_PANEL,
        help="Dashboard url_path: flux-ui (phone Flux) or mobile-home",
    )
    parser.add_argument(
        "--no-user",
        action="store_true",
        help="Only set system default, not current user profile",
    )
    args = parser.parse_args()
    asyncio.run(run(args.ha_url, args.panel, user_panel=not args.no_user))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

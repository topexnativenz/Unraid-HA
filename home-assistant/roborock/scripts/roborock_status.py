#!/usr/bin/env python3
"""Print Roborock integration and vacuum entity status from Home Assistant."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import websockets

DEFAULT_HA = "http://192.168.1.239:8123"
ENTRY_ID = "01KVZ2T1ZR0GVVGJETJQXCFMQ8"
VACUUM_ENTITY = "vacuum.saros_10"


def _token() -> str:
    mcp = Path("/Users/topexnative/.cursor/mcp.json")
    auth = json.loads(mcp.read_text())["mcpServers"]["homeassistant"]["headers"]["Authorization"]
    return auth.split(" ", 1)[1]


async def main() -> int:
    token = _token()
    ws_url = DEFAULT_HA.replace("http://", "ws://") + "/api/websocket"
    async with websockets.connect(ws_url) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        if json.loads(await ws.recv()).get("type") != "auth_ok":
            print("HA auth failed", file=sys.stderr)
            return 1

        await ws.send(json.dumps({"type": "config_entries/get", "id": 1}))
        await ws.send(json.dumps({"type": "get_states", "id": 2}))

        entry_state = None
        vacuum_state = None
        pending = {1, 2}
        while pending:
            msg = json.loads(await ws.recv())
            mid = msg.get("id")
            if mid == 1:
                pending.discard(1)
                for e in msg.get("result", []):
                    if e.get("entry_id") == ENTRY_ID:
                        entry_state = e
            elif mid == 2:
                pending.discard(2)
                for s in msg.get("result", []):
                    if s.get("entity_id") == VACUUM_ENTITY:
                        vacuum_state = s.get("state")

    if not entry_state:
        print("Roborock config entry not found")
        return 1

    print(f"Integration state: {entry_state.get('state')}")
    if entry_state.get("reason"):
        print(f"Reason: {entry_state.get('reason')}")
    if entry_state.get("error_reason_translation_key"):
        print(f"Error key: {entry_state.get('error_reason_translation_key')}")
    print(f"{VACUUM_ENTITY}: {vacuum_state or 'missing'}")

    ok = entry_state.get("state") == "loaded" and vacuum_state not in (None, "unavailable", "unknown")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

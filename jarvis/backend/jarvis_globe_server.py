#!/usr/bin/env python3
"""
JARVIS Globe WebSocket server — pipes voice/CLI commands to the 3D globe UI.

Usage:
  pip install -r requirements.txt
  python jarvis_globe_server.py

Then open jarvis/globe-interface/index.html via a local server (or file:// won't
connect to ws://localhost — use python -m http.server in globe-interface/).
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol

HOST = "localhost"
PORT = 8765

connected_clients: Set[WebSocketServerProtocol] = set()


async def register(websocket: WebSocketServerProtocol) -> None:
    connected_clients.add(websocket)
    print(f"[jarvis] Globe UI connected ({len(connected_clients)} client(s))")
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[jarvis] Globe UI disconnected ({len(connected_clients)} client(s))")


async def broadcast(payload: dict) -> None:
    if not connected_clients:
        print("[jarvis] No globe UI connected — command queued in log only:", payload)
        return
    message = json.dumps(payload)
    await asyncio.gather(
        *[client.send(message) for client in connected_clients.copy()],
        return_exceptions=True,
    )


async def broadcast_command(action: str, **fields) -> None:
    await broadcast({"action": action, **fields})


async def voice_command_loop() -> None:
    print("J.A.R.V.I.S. Core active.")
    print("Commands: scan | speak | idle | listen | quit")
    print("Example: scan  →  spins globe to London (51.50, -0.12)")
    loop = asyncio.get_running_loop()

    while True:
        try:
            command = await loop.run_in_executor(None, lambda: input("Jarvis Control Box >>> "))
        except (EOFError, KeyboardInterrupt):
            print("\n[jarvis] Shutting down.")
            break

        cmd = command.strip().lower()
        if not cmd:
            continue
        if cmd in ("quit", "exit", "q"):
            break
        if "scan" in cmd:
            print("Visualising target geographic coordinates on system UI...")
            await broadcast_command("scan_location", lat=51.50, lon=-0.12)
        elif cmd in ("speak", "speaking"):
            await broadcast_command("speaking", active=True)
            await asyncio.sleep(2.5)
            await broadcast_command("speaking", active=False)
        elif cmd == "listen":
            await broadcast_command("set_state", state="listening")
        elif cmd == "idle":
            await broadcast_command("set_state", state="idle")
        elif cmd.startswith("goto "):
            # goto 40.7 -74.0  (NYC)
            parts = cmd.replace("goto", "").strip().split()
            if len(parts) >= 2:
                lat, lon = float(parts[0]), float(parts[1])
                await broadcast_command("scan_location", lat=lat, lon=lon)
            else:
                print("Usage: goto <lat> <lon>")
        else:
            print(f"Unknown command: {command}")

        await asyncio.sleep(0.05)


async def main() -> None:
    async with websockets.serve(register, HOST, PORT):
        print(f"[jarvis] WebSocket server ws://{HOST}:{PORT}")
        await voice_command_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

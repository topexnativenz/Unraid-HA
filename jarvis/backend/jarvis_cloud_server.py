#!/usr/bin/env python3
"""JARVIS cloud demo — static globe UI + WebSocket on one port (for tunnels)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Set

from aiohttp import web

ROOT = Path(__file__).resolve().parent.parent
PORT = int(__import__("os").environ.get("JARVIS_PORT", "8080"))

connected: Set[web.WebSocketResponse] = set()


async def broadcast(payload: dict) -> None:
    if not connected:
        return
    msg = json.dumps(payload)
    for ws in connected.copy():
        try:
            await ws.send_str(msg)
        except ConnectionResetError:
            connected.discard(ws)


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    connected.add(ws)
    await ws.send_str(json.dumps({"action": "set_state", "state": "listening"}))
    await asyncio.sleep(0.4)
    await ws.send_str(json.dumps({"action": "scan_location", "lat": 51.50, "lon": -0.12}))
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("action") == "ping":
                        await ws.send_str(json.dumps({"action": "pong"}))
                except json.JSONDecodeError:
                    pass
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        connected.discard(ws)
    return ws


async def demo_loop() -> None:
    await asyncio.sleep(12)
    coords = [(51.50, -0.12), (40.71, -74.01), (35.68, 139.69), (-33.87, 151.21)]
    i = 0
    while True:
        if connected:
            lat, lon = coords[i % len(coords)]
            await broadcast({"action": "scan_location", "lat": lat, "lon": lon})
            await asyncio.sleep(4)
            await broadcast({"action": "speaking", "active": True})
            await asyncio.sleep(2.5)
            await broadcast({"action": "speaking", "active": False})
            i += 1
        await asyncio.sleep(8)


async def api_scan(request: web.Request) -> web.Response:
    lat = float(request.query.get("lat", 51.5))
    lon = float(request.query.get("lon", -0.12))
    await broadcast({"action": "scan_location", "lat": lat, "lon": lon})
    return web.json_response({"ok": True, "lat": lat, "lon": lon})


async def index_redirect(_request: web.Request) -> web.Response:
    raise web.HTTPFound("/globe-interface/")


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index_redirect)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/demo/scan", api_scan)
    app.router.add_static("/globe-interface/", ROOT / "globe-interface", show_index=True)
    app.router.add_static("/assistant/", ROOT / "assistant", show_index=True)
    app.router.add_static("/demo/", ROOT / "demo", show_index=True)
    app.router.add_static("/assets/", ROOT, show_index=False)
    return app


async def start_demo_task(app: web.Application) -> None:
    app["demo_task"] = asyncio.create_task(demo_loop())


async def cleanup_demo_task(app: web.Application) -> None:
    app["demo_task"].cancel()
    with asyncio.suppress(asyncio.CancelledError):
        await app["demo_task"]


def main() -> None:
    app = build_app()
    app.on_startup.append(start_demo_task)
    app.on_cleanup.append(cleanup_demo_task)
    print(f"[jarvis] Cloud demo http://0.0.0.0:{PORT}/globe-interface/")
    print(f"[jarvis] WebSocket ws://0.0.0.0:{PORT}/ws")
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

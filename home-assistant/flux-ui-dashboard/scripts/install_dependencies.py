#!/usr/bin/env python3
"""Register Flux UI frontend dependencies via Home Assistant Lovelace resources."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import websockets

DEFAULT_HA = "http://192.168.1.239:8123"

# HACS frontend modules required for Flux UI overview (phase 1).
# URLs use the standard /hacsfiles/ path after HACS install.
FRONTEND_RESOURCES: list[tuple[str, str]] = [
    ("mushroom", "/hacsfiles/lovelace-mushroom/mushroom.js"),
    ("card-mod", "/hacsfiles/lovelace-card-mod/card-mod.js"),
    ("button-card", "/hacsfiles/button-card/button-card.js"),
    ("layout-card", "/hacsfiles/lovelace-layout-card/layout-card.js"),
    ("stack-in-card", "/hacsfiles/stack-in-card/stack-in-card.js"),
    ("bubble-card", "/hacsfiles/bubble-card/bubble-card.js"),
    ("navbar-card", "/hacsfiles/lovelace-navbar-card/navbar-card.js"),
    ("material-you-utilities", "/hacsfiles/material-you-utilities/material-you-utilities.js"),
]

# HACS repos to install via supervisor/hassio when HACS API unavailable (manual fallback in README).
HACS_REPOS: list[tuple[str, str]] = [
    ("piitaya/lovelace-mushroom", "plugin"),
    ("thomasloven/lovelace-card-mod", "plugin"),
    ("custom-cards/button-card", "plugin"),
    ("thomasloven/lovelace-layout-card", "plugin"),
    ("custom-cards/stack-in-card", "plugin"),
    ("Clooos/bubble-card", "plugin"),
    ("joseluis9595/lovelace-navbar-card", "plugin"),
    ("Nerwyn/material-you-theme", "plugin"),
    ("Nerwyn/material-you-utilities", "plugin"),
]


def get_token() -> str:
    mcp = Path.home() / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    return data["mcpServers"]["homeassistant"]["headers"]["Authorization"].split(" ", 1)[1]


async def ws_call(token: str, ha_url: str, calls: list[dict]) -> list[dict]:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url, max_size=30_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"HA auth failed: {auth}")

        mid = 1
        results: list[dict] = []

        async def call(**kw: object) -> dict:
            nonlocal mid
            payload = dict(kw)
            payload["id"] = mid
            mid += 1
            await ws.send(json.dumps(payload))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == payload["id"]:
                    return r

        for c in calls:
            results.append(await call(**c))
        return results


async def ensure_resources(token: str, ha_url: str) -> None:
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]
    existing_urls = {r.get("url") for r in listed.get("result", [])}

    created = 0
    for label, url in FRONTEND_RESOURCES:
        if url in existing_urls:
            print(f"  ok  {label}")
            continue
        res = await ws_call(
            token,
            ha_url,
            [{"type": "lovelace/resources/create", "res_type": "module", "url": url}],
        )
        if res[0].get("success"):
            print(f"  add {label}")
            created += 1
        else:
            print(f"  MISSING {label} — install via HACS: {url}")

    print(f"Resources: {created} added, {len(FRONTEND_RESOURCES) - created} already present or failed")


async def ensure_dashboard(token: str, ha_url: str) -> None:
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/dashboards/list"}]))[0]
    paths = {d.get("url_path") for d in listed.get("result", [])}
    if "flux-ui" in paths:
        print("Dashboard flux-ui already registered")
        return
    res = await ws_call(
        token,
        ha_url,
        [
            {
                "type": "lovelace/dashboards/create",
                "title": "Flux UI",
                "icon": "mdi:view-dashboard-variant",
                "url_path": "flux-ui",
                "require_admin": False,
                "show_in_sidebar": True,
            }
        ],
    )
    if not res[0].get("success"):
        raise RuntimeError(f"dashboard create failed: {res[0]}")
    print("Created dashboard flux-ui (parallel to Mobile Home)")


async def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    args = parser.parse_args()

    token = get_token()
    await ensure_resources(token, args.ha_url)
    await ensure_dashboard(token, args.ha_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

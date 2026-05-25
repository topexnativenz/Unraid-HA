#!/usr/bin/env python3
"""Build and deploy Mobile Home Lovelace dashboard via HA WebSocket API.

SMB-only writes do not reload in a running HA instance; lovelace/config/save is required.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_mobile_home.py"
DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/tmp/ha-config-smb"
STORAGE_KEY = "lovelace.mobile_home"
URL_PATH = "mobile-home"


def get_token() -> str:
    mcp = Path.home() / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    return data["mcpServers"]["homeassistant"]["headers"]["Authorization"].split(" ", 1)[1]


async def get_samba_creds(token: str, ha_url: str) -> tuple[str, str]:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()
        await ws.send(
            json.dumps(
                {
                    "type": "supervisor/api",
                    "endpoint": "/addons/core_samba/info",
                    "method": "get",
                    "id": 1,
                }
            )
        )
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == 1:
                opts = r["result"]["options"]
                return opts["username"], opts["password"]


def mount_config(host: str, user: str, password: str, mount: str) -> None:
    Path(mount).mkdir(parents=True, exist_ok=True)
    subprocess.run(["diskutil", "umount", mount], capture_output=True)
    url = f"//{user}:{password}@{host}/config"
    res = subprocess.run(["mount_smbfs", url, mount], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"SMB mount failed: {res.stderr}")


def load_config_from_mount(mount: str) -> dict:
    storage = Path(mount) / ".storage" / STORAGE_KEY
    backup = Path(mount) / ".storage" / f"{STORAGE_KEY}.bak-20260525"
    for path in (storage, backup):
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text())
            cfg = raw["data"]["config"]
            if cfg.get("views"):
                return cfg
        except json.JSONDecodeError:
            continue
    raise RuntimeError(f"No valid config in {storage} or backup")


async def save_lovelace(token: str, ha_url: str, config: dict) -> None:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"HA auth failed: {auth}")

        await ws.send(
            json.dumps(
                {
                    "type": "lovelace/config/save",
                    "url_path": URL_PATH,
                    "config": config,
                    "id": 1,
                }
            )
        )
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == 1:
                if not r.get("success"):
                    raise RuntimeError(f"lovelace/config/save failed: {r.get('error')}")
                break

        await ws.send(
            json.dumps(
                {
                    "type": "lovelace/config",
                    "url_path": URL_PATH,
                    "force": True,
                    "id": 2,
                }
            )
        )
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == 2:
                if not r.get("success"):
                    raise RuntimeError(f"verify failed: {r.get('error')}")
                views = r["result"]["views"]
                print(
                    "Live dashboard:",
                    [(v["title"], v["path"]) for v in views],
                    f"Home sections={len(views[0]['sections'])}",
                )
                break


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default="192.168.1.239")
    parser.add_argument("--build-only", action="store_true", help="Only rebuild storage file via SMB")
    args = parser.parse_args()

    token = get_token()
    user, pw = await get_samba_creds(token, args.ha_url)
    mount_config(args.host, user, pw, args.mount)
    try:
        subprocess.run(["python3", str(BUILD)], check=True)
        config = load_config_from_mount(args.mount)
        raw = json.loads((Path(args.mount) / ".storage" / STORAGE_KEY).read_text())
        raw["data"]["config"] = config
        (Path(args.mount) / ".storage" / STORAGE_KEY).write_text(json.dumps(raw, indent=2))
    finally:
        subprocess.run(["diskutil", "umount", args.mount], capture_output=True)

    if not args.build_only:
        await save_lovelace(token, args.ha_url, config)

    print("Mobile Home deployed. Force-quit the HA app and reopen mobile-home.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

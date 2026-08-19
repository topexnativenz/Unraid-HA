#!/usr/bin/env python3
"""Build and deploy Mobile Home Lovelace dashboard via HA WebSocket API.

Modes:
  --api-only   Build config in-memory and push via WebSocket (no SMB mount needed).
               Works from CI / cloud agents via Nabu Casa Remote UI.
  (default)    Mount HA config via SMB, rebuild storage file, then push via WebSocket.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_mobile_home.py"
DEFAULT_HA = os.environ.get("HA_URL", "http://192.168.1.239:8123")
DEFAULT_MOUNT = "/tmp/ha-config-smb"
STORAGE_KEY = "lovelace.mobile_home"
URL_PATH = "mobile-home"


def get_token() -> str:
    if os.environ.get("HA_TOKEN"):
        return os.environ["HA_TOKEN"]
    mcp = Path.home() / ".cursor/mcp.json"
    alt = Path("/Users/topexnative/.cursor/mcp.json")
    for path in (mcp, alt):
        if path.exists():
            data = json.loads(path.read_text())
            auth = data["mcpServers"]["homeassistant"]["headers"]["Authorization"]
            return auth.split(" ", 1)[1]
    raise RuntimeError("No HA token — set HA_TOKEN env or provide ~/.cursor/mcp.json")


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


async def fetch_current_config(token: str, ha_url: str) -> dict:
    """Fetch the live lovelace config via WebSocket (no SMB needed)."""
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"HA auth failed: {auth}")
        await ws.send(
            json.dumps({"type": "lovelace/config", "url_path": URL_PATH, "force": True, "id": 1})
        )
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == 1:
                if not r.get("success"):
                    raise RuntimeError(f"lovelace/config fetch failed: {r.get('error')}")
                return r["result"]


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


def build_config_in_memory(existing_config: dict) -> dict:
    """Run build_mobile_home logic in-process against the existing live config.

    We write existing config to a temp .storage location, run the build script,
    and read back the result.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir) / ".storage"
        storage_dir.mkdir()
        storage_file = storage_dir / STORAGE_KEY
        backup_file = storage_dir / f"{STORAGE_KEY}.bak-20260525"

        raw = {"data": {"config": existing_config}, "key": STORAGE_KEY, "version": 1}
        storage_file.write_text(json.dumps(raw, indent=2))
        backup_file.write_text(json.dumps(raw, indent=2))

        env = os.environ.copy()
        env["HA_STORAGE_ROOT"] = str(storage_dir)
        result = subprocess.run(
            [sys.executable, str(BUILD)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.stdout:
            print(result.stdout, end="")

        updated_raw = json.loads(storage_file.read_text())
        return updated_raw["data"]["config"]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default="192.168.1.239")
    parser.add_argument("--build-only", action="store_true", help="Only rebuild storage file via SMB")
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Build in-memory and push via WebSocket (no SMB mount). Works from CI.",
    )
    args = parser.parse_args()

    token = get_token()

    if args.api_only:
        print("Fetching current Mobile Home config from HA...")
        existing = await fetch_current_config(token, args.ha_url)
        print(f"Current views: {[v.get('title') for v in existing.get('views', [])]}")

        print("Building updated config...")
        config = build_config_in_memory(existing)
        print(f"New views: {[v.get('title') for v in config.get('views', [])]}")

        print("Saving to HA...")
        await save_lovelace(token, args.ha_url, config)
        print("Mobile Home deployed via API. Force-quit the HA app and reopen mobile-home.")
        return 0

    user, pw = await get_samba_creds(token, args.ha_url)
    mount_config(args.host, user, pw, args.mount)
    try:
        subprocess.run([sys.executable, str(BUILD)], check=True)
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

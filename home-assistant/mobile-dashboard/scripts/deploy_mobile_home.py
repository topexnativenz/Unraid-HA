#!/usr/bin/env python3
"""Build and deploy Mobile Home Lovelace dashboard via HA WebSocket API.

SMB is used when the HA host is reachable (Mac on LAN). Cloud agents skip SMB
and only push when a prior build exists on the mount path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_mobile_home.py"
FLUX_SCRIPTS = ROOT.parent / "flux-ui-dashboard" / "scripts"
sys.path.insert(0, str(FLUX_SCRIPTS))

from ha_common import (  # noqa: E402
    DEFAULT_HA,
    DEFAULT_HOST,
    DEFAULT_MOUNT,
    ensure_ha_env,
    get_samba_creds,
    get_token,
    host_reachable,
    mount_config,
)

STORAGE_KEY = "lovelace.mobile_home"
URL_PATH = "mobile-home"


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


async def main_async(args: argparse.Namespace) -> int:
    ensure_ha_env()
    token = get_token(args.token)

    mounted = False
    config: dict | None = None

    if host_reachable(args.host, port=445):
        try:
            user, pw = await get_samba_creds(token, args.ha_url)
            mounted = mount_config(args.host, user, pw, args.mount)
        except Exception as exc:
            print(f"SMB skipped ({exc})")

    if mounted:
        try:
            subprocess.run(["python3", str(BUILD)], check=True)
            config = load_config_from_mount(args.mount)
            raw = json.loads((Path(args.mount) / ".storage" / STORAGE_KEY).read_text())
            raw["data"]["config"] = config
            (Path(args.mount) / ".storage" / STORAGE_KEY).write_text(json.dumps(raw, indent=2))
        finally:
            if sys.platform == "darwin":
                subprocess.run(["diskutil", "umount", args.mount], capture_output=True)
            else:
                subprocess.run(["umount", args.mount], capture_output=True)
    else:
        print(
            "Mobile Home: SMB unreachable from this session — skipping rebuild.\n"
            "  Flux UI deploy is unaffected. Rebuild Mobile Home from Mac/LAN when needed."
        )
        return 0

    if not args.build_only and config:
        await save_lovelace(token, args.ha_url, config)
        print("Mobile Home deployed. Force-quit the HA app and reopen mobile-home.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--build-only", action="store_true", help="Only rebuild storage file via SMB")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

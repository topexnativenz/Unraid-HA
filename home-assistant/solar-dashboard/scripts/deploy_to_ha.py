#!/usr/bin/env python3
"""Deploy solar dashboard package to Home Assistant (HA OS + Samba)."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import websockets
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/tmp/ha-config-smb"


def get_token() -> str:
    mcp = Path.home() / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    return data["mcpServers"]["homeassistant"]["headers"]["Authorization"].split(" ", 1)[1]


async def ws_call(token: str, ha_url: str, calls: list[dict]) -> list[dict]:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url, max_size=30_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()
        mid = 1
        results = []

        async def call(**kw):
            nonlocal mid
            kw["id"] = mid
            mid += 1
            await ws.send(json.dumps(kw))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == kw["id"]:
                    return r

        for c in calls:
            results.append(await call(**c))
        return results


async def get_samba_creds(token: str, ha_url: str) -> tuple[str, str]:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "supervisor/api", "endpoint": "/addons/core_samba/info", "method": "get"}],
    )
    opts = res[0]["result"]["options"]
    return opts["username"], opts["password"]


def mount_config(host: str, user: str, password: str, mount: str) -> None:
    Path(mount).mkdir(parents=True, exist_ok=True)
    subprocess.run(["diskutil", "umount", mount], capture_output=True)
    url = f"//{user}:{password}@{host}/config"
    res = subprocess.run(["mount_smbfs", url, mount], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"SMB mount failed: {res.stderr}")


def copy_files(mount: str) -> None:
    cfg = Path(mount)
    pkg_dst = cfg / "packages" / "solar_dashboard.yaml"
    pkg_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "packages" / "solar_dashboard.yaml", pkg_dst)
    shutil.copy2(ROOT / "packages" / "solar_dashboard_serpo.yaml", cfg / "packages" / "solar_dashboard_serpo.yaml")
    shutil.copy2(ROOT / "packages" / "solar_dashboard_ev.yaml", cfg / "packages" / "solar_dashboard_ev.yaml")
    shutil.copy2(ROOT / "packages" / "solar_dashboard_contact.yaml", cfg / "packages" / "solar_dashboard_contact.yaml")

    bg_dst = cfg / "www" / "solar-dashboard" / "backgrounds"
    bg_dst.mkdir(parents=True, exist_ok=True)
    for jpg in (ROOT / "www" / "solar-dashboard" / "backgrounds").glob("*.jpg"):
        shutil.copy2(jpg, bg_dst / jpg.name)
    for sub in ("v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"):
        src_sub = ROOT / "www" / "solar-dashboard" / "backgrounds" / sub
        dst_sub = bg_dst / sub
        dst_sub.mkdir(parents=True, exist_ok=True)
        if src_sub.is_dir():
            for jpg in src_sub.glob("*.jpg"):
                shutil.copy2(jpg, dst_sub / jpg.name)

    www = cfg / "www" / "solar-dashboard"
    www.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "www/solar-dashboard/transparent.png", www / "transparent.png")

    dash_dst = cfg / "dashboards"
    dash_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "lovelace/dashboards/solar_dashboard.yaml", dash_dst / "solar_dashboard.yaml")

    horizon_dir = cfg / "www" / "community" / "lovelace-horizon-card"
    horizon_js = horizon_dir / "lovelace-horizon-card.js"
    if not horizon_js.exists():
        horizon_dir.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(
            [
                "curl",
                "-sL",
                "https://github.com/rejuvenate/lovelace-horizon-card/releases/download/v1.4.0/lovelace-horizon-card.js",
                "-o",
                str(horizon_js),
            ]
        )

    conf = cfg / "configuration.yaml"
    text = conf.read_text()
    if "packages:" not in text and "include_dir_named packages" not in text:
        text = text.rstrip() + "\n\nhomeassistant:\n  packages: !include_dir_named packages\n"
        conf.write_text(text)
        text = conf.read_text()
    if "dashboards/solar_dashboard.yaml" not in text:
        conf.write_text(
            text.rstrip()
            + """

lovelace:
  mode: storage
  dashboards:
    solar-dashboard:
      mode: yaml
      filename: dashboards/solar_dashboard.yaml
      title: Solar
      icon: mdi:solar-power
      show_in_sidebar: true
"""
        )


async def deploy_lovelace(token: str, ha_url: str, french: bool) -> None:
    """YAML dashboard is deployed via SMB copy of lovelace/dashboards/solar_dashboard.yaml."""
    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]["result"]
    if not any("horizon" in (r.get("url") or "") for r in resources):
        await ws_call(
            token,
            ha_url,
            [
                {
                    "type": "lovelace/resources/create",
                    "res_type": "module",
                    "url": "/local/community/lovelace-horizon-card/lovelace-horizon-card.js",
                }
            ],
        )


def api_post(token: str, ha_url: str, path: str, data: dict | None = None) -> None:
    req = urllib.request.Request(
        f"{ha_url}{path}",
        data=json.dumps(data or {}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default="192.168.1.239")
    parser.add_argument("--english", action="store_true")
    parser.add_argument("--skip-restart", action="store_true")
    args = parser.parse_args()

    token = get_token()
    user, pw = await get_samba_creds(token, args.ha_url)
    mount_config(args.host, user, pw, args.mount)
    try:
        copy_files(args.mount)
        await deploy_lovelace(token, args.ha_url, french=not args.english)
        api_post(token, args.ha_url, "/api/config/core/check_config")
        api_post(token, args.ha_url, "/api/services/template/reload")
        if not args.skip_restart:
            await ws_call(token, args.ha_url, [{"type": "supervisor/api", "endpoint": "/core/restart", "method": "post", "data": {}}])
        api_post(token, args.ha_url, "/api/services/input_boolean/turn_on", {"entity_id": "input_boolean.solar_dashboard_demo"})
    finally:
        subprocess.run(["diskutil", "umount", args.mount], capture_output=True)

    print("Solar dashboard deployed. Open http://192.168.1.239:8123/solar-dashboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

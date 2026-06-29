#!/usr/bin/env python3
"""Deploy tablet dashboard package, theme, and Lovelace YAML to Home Assistant."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/tmp/ha-config-smb"

LOVELACE_RESOURCES = [
    ("/hacsfiles/button-card/button-card.js", "button-card"),
    ("/hacsfiles/lovelace-card-mod/card-mod.js", "card-mod"),
    ("/hacsfiles/lovelace-layout-card/layout-card.js", "layout-card"),
    ("/hacsfiles/lovelace-stack-in-card/stack-in-card.js", "stack-in-card"),
    ("/hacsfiles/lovelace-mushroom/mushroom.js", "mushroom"),
    ("/local/tablet-dashboard/tablet-glass.css", "tablet-glass"),
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

    for pkg_name in ("tablet_dashboard.yaml", "tablet_demo.yaml"):
        pkg_dst = cfg / "packages" / pkg_name
        pkg_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "packages" / pkg_name, pkg_dst)

    theme_dst = cfg / "themes" / "tablet_glass.yaml"
    theme_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "themes" / "tablet_glass.yaml", theme_dst)

    www_dst = cfg / "www" / "tablet-dashboard"
    www_dst.mkdir(parents=True, exist_ok=True)
    for asset in (ROOT / "www" / "tablet-dashboard").iterdir():
        shutil.copy2(asset, www_dst / asset.name)

    dash_dst = cfg / "dashboards"
    dash_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "lovelace/dashboards/tablet_dashboard.yaml", dash_dst / "tablet_dashboard.yaml")

    includes_dst = cfg / "dashboards" / "includes"
    includes_dst.mkdir(parents=True, exist_ok=True)
    for inc in (ROOT / "lovelace/includes").glob("*.yaml"):
        shutil.copy2(inc, includes_dst / inc.name)

    conf = cfg / "configuration.yaml"
    text = conf.read_text()
    if "packages:" not in text and "include_dir_named packages" not in text:
        text = text.rstrip() + "\n\nhomeassistant:\n  packages: !include_dir_named packages\n"
        conf.write_text(text)
        text = conf.read_text()

    if "themes:" not in text and "include_dir_merge_named themes" not in text:
        conf.write_text(
            text.rstrip()
            + """

frontend:
  themes: !include_dir_merge_named themes
"""
        )
        text = conf.read_text()

    conf.write_text(ensure_tablet_dashboard_registration(text))


TABLET_DASHBOARD_ENTRY = """    tablet-dashboard:
      mode: yaml
      filename: dashboards/tablet_dashboard.yaml
      title: Tablet
      icon: mdi:tablet-dashboard
      show_in_sidebar: true"""


def ensure_tablet_dashboard_registration(text: str) -> str:
    """Register tablet-dashboard without duplicating the top-level lovelace: block."""
    if "tablet-dashboard:" in text:
        return _collapse_duplicate_lovelace_blocks(text)

    if "lovelace:" in text and "  dashboards:" in text:
        return re.sub(
            r"(  dashboards:\n(?:    .+\n)+)",
            lambda match: match.group(1).rstrip() + "\n" + TABLET_DASHBOARD_ENTRY + "\n",
            text,
            count=1,
        )

    return (
        text.rstrip()
        + """

lovelace:
  mode: storage
  dashboards:
"""
        + TABLET_DASHBOARD_ENTRY
        + "\n"
    )


def _collapse_duplicate_lovelace_blocks(text: str) -> str:
    """Merge duplicate lovelace: sections left by older deploy runs."""
    parts = re.split(r"\nlovelace:\n", text, maxsplit=1)
    if len(parts) != 2:
        return text

    before, body = parts
    sections = re.split(r"\nlovelace:\n", body)
    merged = sections[0].rstrip()
    for extra in sections[1:]:
        for line in extra.splitlines():
            stripped = line.strip()
            if stripped.startswith("tablet-dashboard:") or stripped.startswith("solar-dashboard:"):
                key = stripped.rstrip(":")
                if f"{key}:" not in merged:
                    merged += "\n" + "\n".join(
                        ln for ln in extra.splitlines() if ln.startswith("    ")
                    )
                    break
    return before + "\nlovelace:\n" + merged + "\n"


async def ensure_resources(token: str, ha_url: str) -> None:
    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]["result"]
    existing = {r.get("url") or "" for r in resources}
    for url, _name in LOVELACE_RESOURCES:
        if url not in existing:
            await ws_call(
                token,
                ha_url,
                [{"type": "lovelace/resources/create", "res_type": "module", "url": url}],
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
    parser.add_argument("--skip-reload", action="store_true")
    parser.add_argument("--skip-restart", action="store_true")
    args = parser.parse_args()

    gen = ROOT / "scripts" / "generate_placeholders.py"
    if gen.exists():
        subprocess.run(["python3", str(gen)], check=True)

    token = get_token()
    user, pw = await get_samba_creds(token, args.ha_url)
    mount_config(args.host, user, pw, args.mount)
    try:
        copy_files(args.mount)
        await ensure_resources(token, args.ha_url)
        api_post(token, args.ha_url, "/api/config/core/check_config")
        if not args.skip_reload:
            api_post(token, args.ha_url, "/api/services/template/reload")
            api_post(token, args.ha_url, "/api/services/frontend/reload_themes")
            api_post(token, args.ha_url, "/api/services/automation/reload")
            api_post(token, args.ha_url, "/api/services/input_boolean/reload")
            api_post(token, args.ha_url, "/api/services/input_button/reload")
        if not args.skip_restart:
            try:
                await ws_call(
                    token,
                    args.ha_url,
                    [{"type": "supervisor/api", "endpoint": "/core/restart", "method": "post", "data": {}}],
                )
            except Exception:
                pass  # HA closes websocket during restart
            import time

            for _ in range(36):
                time.sleep(5)
                try:
                    api_post(token, args.ha_url, "/api/services/template/reload")
                    break
                except Exception:
                    continue
    finally:
        subprocess.run(["diskutil", "umount", args.mount], capture_output=True)

    print("Tablet dashboard deployed. Open http://192.168.1.239:8123/tablet-dashboard/home")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

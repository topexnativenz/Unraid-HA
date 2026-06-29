#!/usr/bin/env python3
"""Configure the Panel wall-tablet user: default dashboard G-UNIT, hide other sidebars."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import websockets

DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/private/tmp/ha-config-smb"
PANEL_USER_ID = "b682fecbfad44c71998a764ed5085db1"
DEFAULT_PANEL = "casa-luna"
PANEL_THEME = "panel-kiosk"

# Keep G-UNIT + Floorplan (lighting nav); hide admin/noisy dashboards from Panel sidebar.
HIDDEN_PANELS = [
    "map",
    "lovelace",
    "home-floorplan",
    "dashboard-iphone",
    "tesla-app",
    "dashboard-music",
    "mobile-home",
    "solar-dashboard",
    "tablet-dashboard",
    "a0d7b954_vscode",
    "hacs",
    "core_ssh",
    "8e14ce16_glamos_klet3d",
    "core_configurator",
    "media-browser",
    "history",
    "logbook",
    "energy",
    "calendar",
    "todo",
]

KIOSK_MODE_FLOORPLAN = {
    "user_settings": [
        {
            "users": ["Panel"],
            "kiosk": True,
            "hide_sidebar": True,
            "hide_header": True,
            "hide_overflow": True,
            "block_overflow": True,
            "hide_settings": True,
            "hide_account": True,
            "hide_search": True,
            "hide_assistant": True,
            "hide_notifications": True,
            "hide_edit_dashboard": True,
            "hide_add_to_home_assistant": True,
            "hide_refresh": True,
            "hide_unused_entities": True,
            "hide_reload_resources": True,
            "block_context_menu": True,
            "hide_dialog_header_settings": True,
            "hide_dialog_header_overflow": True,
            "hide_dialog_header_action_items": True,
            "hide_dialog_header_breadcrumb_navigation": True,
            "hide_dialog_header_history": True,
            "ignore_mobile_settings": True,
        }
    ],
    "non_admin_settings": {
        "kiosk": True,
        "hide_sidebar": True,
        "hide_header": True,
        "hide_overflow": True,
        "block_overflow": True,
        "hide_settings": True,
        "hide_account": True,
        "hide_search": True,
        "hide_assistant": True,
        "hide_notifications": True,
        "hide_edit_dashboard": True,
        "hide_add_to_home_assistant": True,
        "hide_refresh": True,
        "hide_unused_entities": True,
        "hide_reload_resources": True,
        "block_context_menu": True,
        "hide_dialog_header_settings": True,
        "hide_dialog_header_overflow": True,
        "hide_dialog_header_action_items": True,
        "hide_dialog_header_breadcrumb_navigation": True,
        "hide_dialog_header_history": True,
    },
}


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


def write_panel_user_data(mount: str, panel: str) -> dict:
    """Write Panel user frontend prefs. Merges existing data so device settings survive."""
    storage = Path(mount) / ".storage" / f"frontend.user_data_{PANEL_USER_ID}"
    existing: dict = {}
    if storage.exists():
        try:
            existing = json.loads(storage.read_text()).get("data", {})
        except json.JSONDecodeError:
            pass

    core = dict(existing.get("core") or {})
    core["default_panel"] = panel

    theme = dict(existing.get("theme") or {})
    theme.setdefault("theme", PANEL_THEME)
    theme.setdefault("dark", True)

    sidebar = dict(existing.get("sidebar") or {})
    sidebar["panelOrder"] = [panel, "floorplan-4-3"]
    sidebar["hiddenPanels"] = HIDDEN_PANELS

    data = dict(existing)
    data["core"] = core
    data["theme"] = theme
    data["sidebar"] = sidebar

    payload = {
        "version": 1,
        "minor_version": 1,
        "key": f"frontend.user_data_{PANEL_USER_ID}",
        "data": data,
    }
    storage.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {storage} default_panel={panel}")
    return data


async def patch_floorplan_kiosk(token: str, ha_url: str, url_path: str = "floorplan-4-3") -> None:
    res = await ws_call(token, ha_url, [{"type": "lovelace/config", "url_path": url_path}])
    cfg = res[0].get("result")
    if not cfg:
        print(f"{url_path}: no config — skip kiosk patch")
        return
    if cfg.get("kiosk_mode") == KIOSK_MODE_FLOORPLAN:
        print(f"{url_path}: kiosk_mode already present")
        return
    cfg["kiosk_mode"] = KIOSK_MODE_FLOORPLAN
    save = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": url_path, "config": cfg}],
    )
    if not save[0].get("success"):
        raise RuntimeError(f"{url_path} kiosk save failed: {save[0].get('error')}")
    print(f"{url_path}: kiosk_mode applied")


def panel_access_token(ha_url: str, password: str, username: str = "panel") -> str:
    """Exchange panel username/password for a short-lived access token."""
    payload = json.dumps(
        {
            "client_id": "set-panel-default.py",
            "grant_type": "password",
            "username": username,
            "password": password,
        }
    ).encode()
    req = urllib.request.Request(
        f"{ha_url.rstrip('/')}/auth/token",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"Panel auth failed: {body}")
    return token


async def set_panel_user_data_live(ha_url: str, panel: str, panel_password: str) -> bool:
    """Set default_panel in HA memory via Panel user's own session."""
    try:
        panel_token = panel_access_token(ha_url, panel_password)
    except (urllib.error.HTTPError, RuntimeError) as exc:
        print(f"Panel live update skipped (auth failed): {exc}")
        return False

    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": panel_token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            print(f"Panel live update skipped (WS auth failed): {auth}")
            return False

        await ws.send(
            json.dumps(
                {
                    "type": "frontend/set_user_data",
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
                    print(f"Panel live update failed: {r.get('error')}")
                    return False
                break

        await ws.send(json.dumps({"type": "frontend/get_user_data", "key": "core", "id": 2}))
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == 2:
                got = (r.get("result") or {}).get("value", {}).get("default_panel")
                ok = got == panel
                print(f"Panel live update {'OK' if ok else 'FAIL'}: default_panel={got!r}")
                return ok


async def restart_ha_core(token: str, ha_url: str) -> None:
    """Reload frontend.user_data from disk — in-memory prefs survive SMB writes until restart."""
    try:
        await ws_call(
            token,
            ha_url,
            [
                {
                    "type": "supervisor/api",
                    "endpoint": "/core/restart",
                    "method": "post",
                    "data": {},
                }
            ],
        )
    except Exception:
        # WebSocket closes when core restarts — expected.
        pass
    print("HA core restart requested (reloads Panel user prefs from disk).")
    for attempt in range(36):
        time.sleep(5)
        try:
            req = urllib.request.Request(
                f"{ha_url}/api/",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(f"HA back online after ~{(attempt + 1) * 5}s")
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    print("WARNING: HA did not respond within 3 minutes — verify manually.")


def verify_panel_storage(mount: str, panel: str) -> bool:
    storage = Path(mount) / ".storage" / f"frontend.user_data_{PANEL_USER_ID}"
    if not storage.exists():
        print(f"VERIFY FAIL: missing {storage}")
        return False
    data = json.loads(storage.read_text()).get("data", {})
    got = (data.get("core") or {}).get("default_panel")
    ok = got == panel
    print(f"VERIFY {'OK' if ok else 'FAIL'}: default_panel={got!r} (expected {panel!r})")
    return ok


async def run(
    ha_url: str,
    mount: str,
    host: str,
    panel: str,
    skip_floorplan: bool,
    skip_restart: bool,
    panel_password: str | None,
    write_only: bool,
) -> None:
    token = get_token()
    user, pw = await get_samba_creds(token, ha_url)
    mount_config(host, user, pw, mount)
    try:
        write_panel_user_data(mount, panel)
        verify_panel_storage(mount, panel)
    finally:
        subprocess.run(["diskutil", "umount", mount], capture_output=True)

    if write_only:
        print("Write-only mode — restart HA or run without --write-only to apply.")
        return

    if not skip_restart:
        await restart_ha_core(token, ha_url)

    if panel_password:
        await set_panel_user_data_live(ha_url, panel, panel_password)

    if not skip_floorplan:
        await patch_floorplan_kiosk(token, ha_url)

    print(f"Panel user default dashboard: {panel} ({ha_url}/{panel}/home)")
    print("Log in as username panel (local only), not admin — system default is mobile-home.")
    print("iPad/Companion: force-quit app → Settings → Companion → Reset frontend cache.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default="192.168.1.239")
    parser.add_argument("--panel", default=DEFAULT_PANEL)
    parser.add_argument("--skip-floorplan", action="store_true")
    parser.add_argument(
        "--skip-restart",
        action="store_true",
        help="Skip HA core restart (not recommended — in-memory prefs may override disk)",
    )
    parser.add_argument(
        "--write-only",
        action="store_true",
        help="Only write .storage file; defer restart to caller",
    )
    parser.add_argument(
        "--panel-password",
        default=os.environ.get("PANEL_HA_PASSWORD", ""),
        help="Panel user password for live in-memory update (or set PANEL_HA_PASSWORD)",
    )
    args = parser.parse_args()
    panel_password = args.panel_password.strip() or None
    asyncio.run(
        run(
            args.ha_url,
            args.mount,
            args.host,
            args.panel,
            skip_floorplan=args.skip_floorplan,
            skip_restart=args.skip_restart,
            panel_password=panel_password,
            write_only=args.write_only,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

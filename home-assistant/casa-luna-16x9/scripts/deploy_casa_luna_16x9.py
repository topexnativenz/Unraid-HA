#!/usr/bin/env python3
"""Deploy G-UNIT 16:9 dashboard (1920×1080) to Home Assistant."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/tmp/ha-config-smb-16x9"

CARD_JS_BUST = "gunit-16x9-7"
LOVELACE_RESOURCE_URL = f"/local/community/casa-luna-16x9/casa-luna.js?v={CARD_JS_BUST}"
PANEL_KIOSK_FIX_BUST = "2"
PANEL_KIOSK_FIX_URL = f"/local/community/casa-luna-16x9/panel-kiosk-fix.js?v={PANEL_KIOSK_FIX_BUST}"

DASHBOARD_KEY = "g-unit-16x9"
DASHBOARD_TITLE = "G-UNIT 16:9"
DASHBOARD_FILENAME = "casa_luna_16x9.yaml"
FLOORPLAN_URL_PATH = "floorplan-4-3"
GUNIT_HOME_PATH = "/g-unit-16x9/home"
LEGACY_GUNIT_HOME_PATH = "/casa-luna/home"
BACKLINK_PATCH = ROOT / "lovelace" / "patches" / "floorplan_4_3_gunit_backlink.yaml"

DASHBOARD_ENTRY = f"""    {DASHBOARD_KEY}:
      mode: yaml
      filename: dashboards/{DASHBOARD_FILENAME}
      title: {DASHBOARD_TITLE}
      icon: mdi:monitor-dashboard
      show_in_sidebar: true"""


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


def ensure_dashboard_registration(text: str) -> str:
    if f"{DASHBOARD_KEY}:" in text:
        return re.sub(
            rf"(    {re.escape(DASHBOARD_KEY)}:\n(?:      [^\n]+\n)*?      title: )[^\n]+",
            rf"\1{DASHBOARD_TITLE}",
            text,
            count=1,
        )

    if "lovelace:" in text and "  dashboards:" in text:
        return re.sub(
            r"(  dashboards:\n(?:    .+\n)+)",
            lambda match: match.group(1).rstrip() + "\n" + DASHBOARD_ENTRY + "\n",
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
        + DASHBOARD_ENTRY
        + "\n"
    )


def copy_files(mount: str) -> None:
    cfg = Path(mount)

    pkg_dst = cfg / "packages"
    pkg_dst.mkdir(parents=True, exist_ok=True)
    for name in ("casa_luna_demo.yaml", "casa_luna_entities.yaml"):
        src = ROOT / "packages" / name
        if src.exists():
            shutil.copy2(src, pkg_dst / name)

    www_dst = cfg / "www" / "community" / "casa-luna-16x9"
    sky_dst = www_dst / "sky"
    sky_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "www" / "community" / "casa-luna-16x9" / "casa-luna.js", www_dst / "casa-luna.js")
    fix_src = ROOT / "www" / "community" / "casa-luna-16x9" / "panel-kiosk-fix.js"
    if fix_src.exists():
        shutil.copy2(fix_src, www_dst / "panel-kiosk-fix.js")
    for png in (ROOT / "www" / "community" / "casa-luna-16x9" / "sky").glob("casa-luna-*.png"):
        shutil.copy2(png, sky_dst / png.name)

    dash_dst = cfg / "dashboards"
    dash_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / "lovelace" / "dashboards" / DASHBOARD_FILENAME,
        dash_dst / DASHBOARD_FILENAME,
    )

    conf = cfg / "configuration.yaml"
    text = conf.read_text()
    if "packages:" not in text and "include_dir_named packages" not in text:
        text = text.rstrip() + "\n\nhomeassistant:\n  packages: !include_dir_named packages\n"
        conf.write_text(text)
        text = conf.read_text()

    conf.write_text(ensure_dashboard_registration(text))


def load_gunit_backlink_element() -> dict:
    """Picture-elements overlay that navigates back to G-UNIT 16:9."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(BACKLINK_PATCH.read_text())
    except Exception:
        return {
            "type": "icon",
            "icon": "mdi:moon-waning-crescent",
            "tap_action": {"action": "navigate", "navigation_path": GUNIT_HOME_PATH},
            "style": {
                "left": "4%",
                "top": "4%",
                "z-index": 10,
                "--mdc-icon-size": "32px",
                "background": "rgba(0, 0, 0, 0.55)",
                "border-radius": "10px",
                "padding": "6px",
                "color": "#cce4ff",
            },
        }


def _is_floorplan_gunit_backlink(el: dict) -> bool:
    """True if element is the Floorplan moon icon backlink to G-UNIT."""
    tap = el.get("tap_action") or {}
    if tap.get("action") != "navigate":
        return False
    nav = tap.get("navigation_path")
    if nav in (GUNIT_HOME_PATH, LEGACY_GUNIT_HOME_PATH):
        return True
    return el.get("icon") == "mdi:moon-waning-crescent"


def _is_broken_gunit_backlink(el: dict) -> bool:
    """state-icon without entity is invalid and breaks picture-elements."""
    return _is_floorplan_gunit_backlink(el) and el.get("type") == "state-icon" and not el.get("entity")


async def patch_floorplan_gunit_backlink(token: str, ha_url: str) -> None:
    """Patch Floorplan (4:3) moon icon to navigate back to G-UNIT 16:9."""
    backlink = load_gunit_backlink_element()
    res = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config", "url_path": FLOORPLAN_URL_PATH}],
    )
    cfg = res[0].get("result")
    if not cfg or not cfg.get("views"):
        print("Floorplan (4:3): no views — skip backlink patch")
        return

    view = next((v for v in cfg["views"] if v.get("path") == "ground-floor"), cfg["views"][0])
    cards = view.get("cards") or []
    pe = next((c for c in cards if c.get("type") == "picture-elements"), None)
    if not pe:
        print("Floorplan (4:3): no picture-elements card — skip backlink patch")
        return

    elements = pe.setdefault("elements", [])
    broken = [i for i, el in enumerate(elements) if _is_broken_gunit_backlink(el)]
    for i in reversed(broken):
        elements.pop(i)

    backlink_changed = bool(broken)
    found = False
    for el in elements:
        if not _is_floorplan_gunit_backlink(el):
            continue
        found = True
        nav = (el.get("tap_action") or {}).get("navigation_path")
        if nav != GUNIT_HOME_PATH:
            el.setdefault("tap_action", {})["navigation_path"] = GUNIT_HOME_PATH
            backlink_changed = True
        if el.get("type") != "icon":
            el["type"] = "icon"
            el.pop("entity", None)
            backlink_changed = True

    if not found:
        elements.insert(0, backlink)
        backlink_changed = True

    if not backlink_changed:
        print(f"Floorplan (4:3): backlink already → {GUNIT_HOME_PATH}")
        return

    save = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": FLOORPLAN_URL_PATH, "config": cfg}],
    )
    if not save[0].get("success"):
        print(f"Floorplan (4:3): backlink save failed — {save[0].get('error')}")
        return
    print(f"Floorplan (4:3): backlink deployed → {GUNIT_HOME_PATH}")


async def ensure_resources(token: str, ha_url: str) -> None:
    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]["result"]
    stale = [
        r
        for r in resources
        if "casa-luna-16x9" in (r.get("url") or "")
        and r.get("url") not in (LOVELACE_RESOURCE_URL, PANEL_KIOSK_FIX_URL)
    ]
    for r in stale:
        await ws_call(
            token,
            ha_url,
            [{"type": "lovelace/resources/delete", "resource_id": r["id"]}],
        )

    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]["result"]
    if not any(r.get("url") == LOVELACE_RESOURCE_URL for r in resources):
        await ws_call(
            token,
            ha_url,
            [{"type": "lovelace/resources/create", "res_type": "module", "url": LOVELACE_RESOURCE_URL}],
        )
        print(f"Registered lovelace resource: {LOVELACE_RESOURCE_URL}")

    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]["result"]
    if not any(r.get("url") == PANEL_KIOSK_FIX_URL for r in resources):
        await ws_call(
            token,
            ha_url,
            [
                {
                    "type": "lovelace/resources/create",
                    "res_type": "module",
                    "url": PANEL_KIOSK_FIX_URL,
                }
            ],
        )
        print(f"Registered lovelace resource: {PANEL_KIOSK_FIX_URL}")


def api_post(token: str, ha_url: str, path: str, data: dict | None = None) -> None:
    req = urllib.request.Request(
        f"{ha_url}{path}",
        data=json.dumps(data or {}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


def api_get(token: str, ha_url: str, path: str) -> tuple[int, str]:
    req = urllib.request.Request(
        f"{ha_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read(512).decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(512).decode(errors="replace")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default="192.168.1.239")
    parser.add_argument("--skip-reload", action="store_true")
    parser.add_argument("--skip-restart", action="store_true")
    args = parser.parse_args()

    scale_script = ROOT / "scripts" / "scale_casa_luna_16x9.py"
    if scale_script.exists():
        subprocess.run(["python3", str(scale_script)], check=True)

    token = get_token()
    user, pw = await get_samba_creds(token, args.ha_url)
    mount_config(args.host, user, pw, args.mount)
    try:
        copy_files(args.mount)
        await ensure_resources(token, args.ha_url)
        await patch_floorplan_gunit_backlink(token, args.ha_url)
        api_post(token, args.ha_url, "/api/config/core/check_config")
        if not args.skip_reload:
            api_post(token, args.ha_url, "/api/services/template/reload")
            try:
                api_post(token, args.ha_url, "/api/services/frontend/reload_themes")
            except Exception:
                pass

        if not args.skip_restart:
            try:
                await ws_call(
                    token,
                    args.ha_url,
                    [{"type": "supervisor/api", "endpoint": "/core/restart", "method": "post", "data": {}}],
                )
            except Exception:
                pass
            for _ in range(36):
                time.sleep(5)
                try:
                    status_probe, _ = api_get(token, args.ha_url, f"/{DASHBOARD_KEY}/home")
                    if status_probe == 200:
                        break
                except Exception:
                    continue
    finally:
        subprocess.run(["diskutil", "umount", args.mount], capture_output=True)

    status, _ = api_get(token, args.ha_url, f"/{DASHBOARD_KEY}/home")
    legacy, _ = api_get(token, args.ha_url, "/casa-luna/home")
    fp_status, _ = api_get(token, args.ha_url, "/floorplan-4-3/ground-floor")
    print(f"G-UNIT 16:9 deployed. HTTP {status}: {args.ha_url}/{DASHBOARD_KEY}/home")
    print(f"Original G-UNIT (3:2) HTTP {legacy}: {args.ha_url}/casa-luna/home")
    print(f"Floorplan (4:3) HTTP {fp_status}: {args.ha_url}/floorplan-4-3/ground-floor")
    print(f"Floorplan backlink target: {GUNIT_HOME_PATH}")
    print(f"Card JS: {args.ha_url}{LOVELACE_RESOURCE_URL}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

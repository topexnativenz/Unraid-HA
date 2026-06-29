#!/usr/bin/env python3
"""Deploy Casa Luna side dashboard (card JS, sky PNGs, Lovelace YAML) to Home Assistant."""

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
DEFAULT_MOUNT = "/tmp/ha-config-smb"

# Cache-bust query forces browsers to reload after header-title fixes.
CARD_JS_BUST = "gunit-51"
LOVELACE_RESOURCE_URL = f"/local/community/casa-luna/casa-luna.js?v={CARD_JS_BUST}"
PANEL_KIOSK_FIX_BUST = "1"
PANEL_KIOSK_FIX_URL = f"/local/community/casa-luna/panel-kiosk-fix.js?v={PANEL_KIOSK_FIX_BUST}"

DASHBOARD_TITLE = "G-UNIT"
FLOORPLAN_URL_PATH = "floorplan-4-3"
BACKGROUND_PATCH = ROOT / "lovelace" / "patches" / "floorplan_4_3_background.yaml"
FLOORPLAN_BG_BUST = "floorplan-v3"
FLOORPLAN_BG_IMAGE = (
    f"/local/community/casa-luna/floorplan/base-view-alpha.png?v={FLOORPLAN_BG_BUST}"
)
FLOORPLAN_SKY_BG = (
    f"/local/community/casa-luna/floorplan/sky-bg.png?v={FLOORPLAN_BG_BUST}"
)

CASA_LUNA_DASHBOARD_ENTRY = f"""    casa-luna:
      mode: yaml
      filename: dashboards/casa_luna.yaml
      title: {DASHBOARD_TITLE}
      icon: mdi:moon-waning-crescent
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


def _sync_casa_luna_dashboard_title(text: str) -> str:
    """Keep sidebar title in sync when casa-luna is already registered."""
    if "casa-luna:" not in text:
        return text
    return re.sub(
        r"(    casa-luna:\n(?:      [^\n]+\n)*?      title: )[^\n]+",
        rf"\1{DASHBOARD_TITLE}",
        text,
        count=1,
    )


def ensure_casa_luna_dashboard_registration(text: str) -> str:
    """Register casa-luna without duplicating the top-level lovelace: block."""
    if "casa-luna:" in text:
        return _sync_casa_luna_dashboard_title(_collapse_duplicate_lovelace_blocks(text))

    if "lovelace:" in text and "  dashboards:" in text:
        return re.sub(
            r"(  dashboards:\n(?:    .+\n)+)",
            lambda match: match.group(1).rstrip() + "\n" + CASA_LUNA_DASHBOARD_ENTRY + "\n",
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
        + CASA_LUNA_DASHBOARD_ENTRY
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
    known = ("casa-luna:", "tablet-dashboard:", "solar-dashboard:")
    for extra in sections[1:]:
        for line in extra.splitlines():
            stripped = line.strip()
            if any(stripped.startswith(k) for k in known):
                key = stripped.rstrip(":")
                if f"{key}:" not in merged:
                    merged += "\n" + "\n".join(
                        ln for ln in extra.splitlines() if ln.startswith("    ")
                    )
                    break
    return before + "\nlovelace:\n" + merged + "\n"


def copy_files(mount: str) -> None:
    cfg = Path(mount)

    pkg_dst = cfg / "packages"
    pkg_dst.mkdir(parents=True, exist_ok=True)
    for name in ("casa_luna_demo.yaml", "casa_luna_entities.yaml"):
        src = ROOT / "packages" / name
        if src.exists():
            shutil.copy2(src, pkg_dst / name)

    www_dst = cfg / "www" / "community" / "casa-luna"
    sky_dst = www_dst / "sky"
    sky_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "www" / "community" / "casa-luna" / "casa-luna.js", www_dst / "casa-luna.js")
    fix_src = ROOT / "www" / "community" / "casa-luna" / "panel-kiosk-fix.js"
    if fix_src.exists():
        shutil.copy2(fix_src, www_dst / "panel-kiosk-fix.js")
    for png in (ROOT / "www" / "community" / "casa-luna" / "sky").glob("casa-luna-*.png"):
        shutil.copy2(png, sky_dst / png.name)

    floorplan_dst = www_dst / "floorplan"
    floorplan_dst.mkdir(parents=True, exist_ok=True)
    for name in ("base-view-alpha.png", "sky-bg.png"):
        floorplan_src = ROOT / "www" / "floorplan" / name
        if floorplan_src.exists():
            shutil.copy2(floorplan_src, floorplan_dst / name)

    dash_dst = cfg / "dashboards"
    dash_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "lovelace" / "dashboards" / "casa_luna.yaml", dash_dst / "casa_luna.yaml")

    theme_src = ROOT / "themes" / "panel_kiosk.yaml"
    if theme_src.exists():
        theme_dst = cfg / "themes" / "panel_kiosk.yaml"
        theme_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(theme_src, theme_dst)

    conf = cfg / "configuration.yaml"
    text = conf.read_text()
    if "packages:" not in text and "include_dir_named packages" not in text:
        text = text.rstrip() + "\n\nhomeassistant:\n  packages: !include_dir_named packages\n"
        conf.write_text(text)
        text = conf.read_text()

    conf.write_text(ensure_casa_luna_dashboard_registration(text))


def load_floorplan_background_patch() -> dict:
    """card_mod + image path for Floorplan (4:3) picture-elements."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(BACKGROUND_PATCH.read_text()) or {}
    except Exception:
        return {
            "image": FLOORPLAN_BG_IMAGE,
            "card_mod": {
                "style": (
                    "ha-card {\n"
                    f"  background: url('{FLOORPLAN_SKY_BG}') center / cover no-repeat #020c1e;\n"
                    "  border: none;\n"
                    "  box-shadow: none;\n"
                    "}\n"
                ),
            },
        }


def _apply_floorplan_background(pe: dict, bg_patch: dict) -> bool:
    """Apply night-sky background to picture-elements card. Returns True if changed."""
    changed = False
    target_image = bg_patch.get("image", FLOORPLAN_BG_IMAGE)
    if pe.get("image") != target_image:
        pe["image"] = target_image
        changed = True
    if bg_patch.get("card_mod") and pe.get("card_mod") != bg_patch["card_mod"]:
        pe["card_mod"] = bg_patch["card_mod"]
        changed = True
    return changed


async def patch_floorplan_storage(token: str, ha_url: str) -> None:
    """Patch Floorplan (4:3): night background only (backlink owned by deploy_casa_luna_16x9.py)."""
    bg_patch = load_floorplan_background_patch()
    res = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config", "url_path": FLOORPLAN_URL_PATH}],
    )
    cfg = res[0].get("result")
    if not cfg or not cfg.get("views"):
        print("Floorplan (4:3): no views — skip patch")
        return

    view = next((v for v in cfg["views"] if v.get("path") == "ground-floor"), cfg["views"][0])
    cards = view.get("cards") or []
    pe = next((c for c in cards if c.get("type") == "picture-elements"), None)
    if not pe:
        print("Floorplan (4:3): no picture-elements card — skip patch")
        return

    if not _apply_floorplan_background(pe, bg_patch):
        print("Floorplan (4:3): background already present")
        return

    save = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": FLOORPLAN_URL_PATH, "config": cfg}],
    )
    if not save[0].get("success"):
        print(f"Floorplan (4:3): save failed — {save[0].get('error')}")
        return
    print(f"Floorplan (4:3): background → {bg_patch.get('image', FLOORPLAN_BG_IMAGE)}")


async def ensure_resources(token: str, ha_url: str) -> None:
    """Register versioned /local JS; remove stale casa-luna entries (incl. unversioned / HACS)."""
    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]["result"]
    stale = [
        r
        for r in resources
        if "casa-luna" in (r.get("url") or "")
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

    resources = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]["result"]
    stale_fix = [
        r
        for r in resources
        if "panel-kiosk-fix" in (r.get("url") or "") and r.get("url") != PANEL_KIOSK_FIX_URL
    ]
    for r in stale_fix:
        await ws_call(
            token,
            ha_url,
            [{"type": "lovelace/resources/delete", "resource_id": r["id"]}],
        )

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

    token = get_token()
    user, pw = await get_samba_creds(token, args.ha_url)
    mount_config(args.host, user, pw, args.mount)
    try:
        copy_files(args.mount)
        await ensure_resources(token, args.ha_url)
        await patch_floorplan_storage(token, args.ha_url)
        api_post(token, args.ha_url, "/api/config/core/check_config")
        if not args.skip_reload:
            api_post(token, args.ha_url, "/api/services/template/reload")
            try:
                api_post(token, args.ha_url, "/api/services/frontend/reload_themes")
            except Exception:
                pass

        panel_script = ROOT / "scripts" / "set_panel_default.py"
        if panel_script.exists():
            subprocess.run(
                [
                    str(panel_script),
                    "--ha-url",
                    args.ha_url,
                    "--write-only",
                    "--skip-floorplan",
                ],
                check=False,
            )

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
                    api_post(token, args.ha_url, "/api/services/template/reload")
                    break
                except Exception:
                    continue

        if panel_script.exists():
            subprocess.run(
                [
                    str(panel_script),
                    "--ha-url",
                    args.ha_url,
                    "--skip-restart",
                ],
                check=False,
            )
    finally:
        subprocess.run(["diskutil", "umount", args.mount], capture_output=True)

    status, _ = api_get(token, args.ha_url, "/casa-luna/home")
    fp_status, _ = api_get(token, args.ha_url, "/floorplan-4-3/ground-floor")
    print(f"Casa Luna deployed. Dashboard HTTP {status}: {args.ha_url}/casa-luna/home")
    print(f"Floorplan (4:3) HTTP {fp_status}: {args.ha_url}/floorplan-4-3/ground-floor")
    print(f"Card JS: {args.ha_url}{LOVELACE_RESOURCE_URL}")
    print(f"Panel kiosk fix: {args.ha_url}{PANEL_KIOSK_FIX_URL}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

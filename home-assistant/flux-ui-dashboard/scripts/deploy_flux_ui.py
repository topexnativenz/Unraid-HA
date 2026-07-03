#!/usr/bin/env python3
"""Deploy Flux UI dashboard in parallel with Mobile Home (does not modify mobile-home)."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_flux_ui.py"
INSTALL = ROOT / "scripts" / "install_dependencies.py"
DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/tmp/ha-config-smb"
URL_PATH = "flux-ui"
MOBILE_STORAGE = "lovelace.mobile_home"


def get_token() -> str:
    mcp = Path.home() / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    return data["mcpServers"]["homeassistant"]["headers"]["Authorization"].split(" ", 1)[1]


async def ws_call(token: str, ha_url: str, calls: list[dict]) -> list[dict]:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
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


async def get_samba_creds(token: str, ha_url: str) -> tuple[str, str]:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "supervisor/api", "endpoint": "/addons/core_samba/info", "method": "get"}],
    )
    opts = res[0]["result"]["options"]
    return opts["username"], opts["password"]


def mount_config(host: str, user: str, password: str, mount: str) -> bool:
    Path(mount).mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        subprocess.run(["diskutil", "umount", mount], capture_output=True)
        url = f"//{user}:{password}@{host}/config"
        res = subprocess.run(["mount_smbfs", url, mount], capture_output=True, text=True)
        return res.returncode == 0
    subprocess.run(["umount", mount], capture_output=True)
    creds = Path("/tmp/.smb-flux-ui")
    creds.write_text(f"username={user}\npassword={password}\n")
    creds.chmod(0o600)
    res = subprocess.run(
        [
            "mount",
            "-t",
            "cifs",
            f"//{host}/config",
            mount,
            "-o",
            f"credentials={creds},vers=3.0",
        ],
        capture_output=True,
        text=True,
    )
    return res.returncode == 0


def unmount(mount: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["diskutil", "umount", mount], capture_output=True)
    else:
        subprocess.run(["umount", mount], capture_output=True)


def copy_theme(mount: str) -> None:
    dst = Path(mount) / "themes" / "flux-ui-md3.yaml"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "themes" / "flux-ui-md3.yaml", dst)
    conf = Path(mount) / "configuration.yaml"
    if conf.exists():
        text = conf.read_text()
        if "flux-ui-md3.yaml" not in text and "themes:" not in text:
            conf.write_text(
                text.rstrip()
                + "\n\nfrontend:\n  themes: !include_dir_merge_named themes\n"
            )


def build_config(mobile_storage: Path | None) -> dict:
    cmd = ["python3", str(BUILD), "--output", str(ROOT / "generated" / "lovelace.flux_ui.json")]
    if mobile_storage and mobile_storage.exists():
        cmd.extend(["--mobile-home-storage", str(mobile_storage)])
    subprocess.run(cmd, check=True)
    raw = json.loads((ROOT / "generated" / "lovelace.flux_ui.json").read_text())
    return raw["data"]["config"]


async def save_dashboard(token: str, ha_url: str, config: dict) -> None:
    await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": URL_PATH, "config": config}],
    )
    verify = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config", "url_path": URL_PATH, "force": True}],
    )
    views = verify[0]["result"]["views"]
    sections = views[0].get("sections", [])
    print(f"Live flux-ui: {[(v['title'], v['path']) for v in views]} sections={len(sections)}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default="192.168.1.239")
    parser.add_argument("--skip-mount", action="store_true", help="Build without Mobile Home climate import")
    args = parser.parse_args()

    token = get_token()
    mobile_storage: Path | None = None
    mounted = False

    if not args.skip_mount:
        try:
            user, pw = await get_samba_creds(token, args.ha_url)
            mounted = mount_config(args.host, user, pw, args.mount)
            if mounted:
                copy_theme(args.mount)
                mobile_storage = Path(args.mount) / ".storage" / MOBILE_STORAGE
                if not mobile_storage.exists():
                    mobile_storage = None
                    print("Mobile Home storage not found; using climate fallback")
            else:
                print("SMB mount failed; using climate fallback")
        except Exception as exc:
            print(f"SMB skipped ({exc}); using climate fallback")

    try:
        config = build_config(mobile_storage)
    finally:
        if mounted:
            unmount(args.mount)

    subprocess.run(["python3", str(INSTALL), "--ha-url", args.ha_url], check=True)
    await save_dashboard(token, args.ha_url, config)

    print(f"Flux UI deployed at {args.ha_url}/{URL_PATH}/overview")
    print("Mobile Home unchanged. Profile → theme: flux-ui-md3 (optional).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

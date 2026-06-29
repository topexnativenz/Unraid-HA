#!/usr/bin/env python3
"""Deploy gate packages + automations block to Home Assistant via SMB."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/private/tmp/ha-config-smb-gate"
PACKAGE_FILES = (
    "gate_akuvox.yaml",
    "gate_automations.yaml",
    "gate_phone.yaml",
    "gate_approach_layers.yaml",
    "gate_tessie_location.yaml",
    "gate_tessie.yaml",
    "gate_tessie_model_s_drive.yaml",
)


def get_token() -> str:
    mcp = Path.home() / ".cursor/mcp.json"
    data = json.loads(mcp.read_text())
    return data["mcpServers"]["homeassistant"]["headers"]["Authorization"].split(" ", 1)[1]


def get_samba_creds_from_env() -> tuple[str, str] | None:
    user = os.environ.get("HA_SAMBA_USER", "homeassistant")
    password = os.environ.get("HA_SAMBA_PASSWORD")
    if password:
        return user, password
    return None


async def get_samba_creds_from_ha(host: str, token: str) -> tuple[str, str]:
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError(
            "Missing Python package 'websockets'.\n"
            "Fix one of:\n"
            "  python3 -m pip install --user websockets\n"
            "  export HA_SAMBA_PASSWORD='…'  # HA → Settings → Add-ons → Samba share\n"
            "  deactivate  # leave .venv, then re-run deploy script"
        ) from exc

    ws_url = f"ws://{host}:8123/api/websocket"
    async with websockets.connect(ws_url) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"HA websocket auth failed: {auth}")
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
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                opts = msg["result"]["options"]
                return opts["username"], opts["password"]


def resolve_samba_creds(host: str, token: str) -> tuple[str, str]:
    env_creds = get_samba_creds_from_env()
    if env_creds:
        return env_creds
    return asyncio.run(get_samba_creds_from_ha(host, token))


def mount_config(host: str, user: str, password: str, mount: str) -> None:
    Path(mount).mkdir(parents=True, exist_ok=True)
    subprocess.run(["diskutil", "umount", mount], capture_output=True)
    url = f"//{user}:{password}@{host}/config"
    res = subprocess.run(["mount_smbfs", url, mount], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"SMB mount failed: {res.stderr.strip() or res.stdout.strip()}")


def merge_gate_automations(text: str, auto_src: str) -> str:
    marker_start = "# --- Gate automations (repo: home-assistant/gate) ---"
    marker_end = "# --- End gate automations ---"
    block = f"{marker_start}\n{auto_src.strip()}\n{marker_end}\n"

    if marker_start in text and marker_end in text:
        start = text.index(marker_start)
        end = text.index(marker_end) + len(marker_end)
        return text[:start] + block + text[end:].lstrip("\n")

    # HA UI / API edits may have removed comment markers — replace by gate automation ids.
    gate_id_markers = (
        "- id: gate_dave_mark_outside",
        "- id: gate_mark_exit_in_progress",
        "- id: gate_open_on_arrival",
    )
    start = -1
    for marker in gate_id_markers:
        pos = text.find(marker)
        if pos != -1:
            start = pos if start == -1 else min(start, pos)

    if start != -1:
        lines = text[start:].splitlines(keepends=True)
        cut = len(lines)
        for i, line in enumerate(lines):
            if i > 0 and line.startswith("- id: ") and not line.startswith("- id: gate_"):
                cut = i
                break
        old = "".join(lines[:cut])
        return text.replace(old, block, 1)

    return text.rstrip() + "\n\n" + block


def deploy_files(mount: str) -> None:
    cfg = Path(mount)
    for name in PACKAGE_FILES:
        src = ROOT / "packages" / name
        if src.exists():
            shutil.copy2(src, cfg / "packages" / name)
            print(f"copied {name}")

    auto_path = cfg / "automations.yaml"
    auto_src = (ROOT / "automations/gate.yaml").read_text()
    merged = merge_gate_automations(auto_path.read_text(), auto_src)
    auto_path.write_text(merged)
    print("merged automations.yaml")


def api_post_check(ha_url: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{ha_url}/api/config/core/check_config",
        data=b"{}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def api_post(ha_url: str, token: str, path: str, data: dict | None = None) -> int:
    req = urllib.request.Request(
        f"{ha_url}{path}",
        data=json.dumps(data or {}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status


def reload_ha(ha_url: str, token: str) -> None:
    api_post(ha_url, token, "/api/services/homeassistant/reload_core_config")
    time.sleep(8)
    for svc in ("input_boolean/reload", "template/reload", "rest_command/reload", "automation/reload", "script/reload"):
        domain, name = svc.split("/")
        status = api_post(ha_url, token, f"/api/services/{domain}/{name}")
        print(f"reloaded {name}: {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy gate packages to Home Assistant")
    parser.add_argument("--host", default=os.environ.get("HA_HOST", "192.168.1.239"))
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", DEFAULT_HA))
    parser.add_argument("--mount", default=os.environ.get("HA_CONFIG_MOUNT", DEFAULT_MOUNT))
    args = parser.parse_args()

    token = get_token()
    user, password = resolve_samba_creds(args.host, token)

    try:
        mount_config(args.host, user, password, args.mount)
        deploy_files(args.mount)
    finally:
        subprocess.run(["diskutil", "umount", args.mount], capture_output=True)

    check = api_post_check(args.ha_url, token)
    if check.get("result") != "valid":
        print(
            "error: Home Assistant config is invalid after deploy:\n"
            f"  {check.get('errors', check)}\n"
            "Fix the reported file, then re-run this script.",
            file=sys.stderr,
        )
        return 1

    try:
        reload_ha(args.ha_url, token)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(
            f"warning: HA reload failed ({exc.code} {body}); "
            "files are on disk — use Settings → System → Restart or reload from UI",
            file=sys.stderr,
        )
    except urllib.error.URLError as exc:
        print(f"warning: HA reload failed ({exc}); files are on disk — reload from HA UI", file=sys.stderr)

    print("Gate package deploy complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

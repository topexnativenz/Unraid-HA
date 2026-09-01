#!/usr/bin/env python3
"""Deploy garage packages + automations block to Home Assistant via SMB."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/private/tmp/ha-config-smb-garage"
PACKAGE_FILES = (
    "garage_doors_pulse.yaml",
    "main_garage_cover.yaml",
)

MARKER_START = "# --- Garage automations (repo: home-assistant/garage-doors) ---"
MARKER_END = "# --- End garage automations ---"


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
    raise RuntimeError("No HA token — set HA_TOKEN or provide ~/.cursor/mcp.json")


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


def merge_garage_automations(text: str, auto_src: str) -> str:
    block = f"{MARKER_START}\n{auto_src.strip()}\n{MARKER_END}\n"

    if MARKER_START in text and MARKER_END in text:
        start = text.index(MARKER_START)
        end = text.index(MARKER_END) + len(MARKER_END)
        return text[:start] + block + text[end:].lstrip("\n")

    garage_id_markers = (
        "- id: garage_outside_lights_on_tessie_arrival_after_dark",
        "- id: house_garage_open_on_tessie_arrival",
        "- id: garage_open_on_model_s_arrival",
        "- id: garage_close_at_9pm",
    )
    start = -1
    for marker in garage_id_markers:
        pos = text.find(marker)
        if pos != -1:
            start = pos if start == -1 else min(start, pos)

    if start != -1:
        lines = text[start:].splitlines(keepends=True)
        cut = len(lines)
        for i, line in enumerate(lines):
            if i > 0 and line.startswith("- id: ") and not line.startswith("- id: garage_"):
                cut = i
                break
        old = "".join(lines[:cut])
        return text.replace(old, block, 1)

    # Remove legacy UI automation (pre-repo) before inserting the managed block.
    legacy = re.compile(
        r"- alias: Auto Close Garage 9PM\n.*?(?=\n- id: |\n# --- Gate automations|\Z)",
        re.DOTALL,
    )
    text = legacy.sub("", text)

    gate_marker = "# --- Gate automations (repo: home-assistant/gate) ---"
    if gate_marker in text:
        return text.replace(gate_marker, block + "\n" + gate_marker, 1)

    return text.rstrip() + "\n\n" + block


def strip_configuration_cover_block(text: str) -> str:
    """Move inline template cover into packages/main_garage_cover.yaml."""
    pattern = re.compile(
        r"\ncover:\n  - platform: template\n    covers:\n      garage_door:.*?"
        r"(?=\nhomeassistant:|\nlovelace:|\Z)",
        re.DOTALL,
    )
    if not pattern.search(text):
        return text
    note = (
        "\n# Main Garage cover → packages/main_garage_cover.yaml (repo deploy)\n"
    )
    return pattern.sub(note, text, count=1)


def deploy_files(mount: str) -> None:
    cfg = Path(mount)
    for name in PACKAGE_FILES:
        src = ROOT / "packages" / name
        if src.exists():
            shutil.copy2(src, cfg / "packages" / name)
            print(f"copied {name}")

    config_path = cfg / "configuration.yaml"
    if config_path.exists():
        merged_cfg = strip_configuration_cover_block(config_path.read_text())
        if merged_cfg != config_path.read_text():
            config_path.write_text(merged_cfg)
            print("moved cover block from configuration.yaml → package")

    auto_path = cfg / "automations.yaml"
    auto_src = (ROOT / "automations/garage.yaml").read_text()
    merged = merge_garage_automations(auto_path.read_text(), auto_src)
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
    parser = argparse.ArgumentParser(description="Deploy garage packages to Home Assistant")
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

    print("Garage package deploy complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

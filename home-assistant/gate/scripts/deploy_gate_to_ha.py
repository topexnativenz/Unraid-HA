#!/usr/bin/env python3
"""Deploy Akuvox gate package and Local Akuvox integration to Home Assistant."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HA = "http://192.168.1.239:8123"
DEFAULT_MOUNT = "/tmp/ha-config-smb"
LOCAL_AKUVOX_REPO = "https://github.com/tykeal/homeassistant-local-akuvox.git"


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


def ensure_local_akuvox(clone_dir: Path) -> Path:
    component = clone_dir / "custom_components" / "local_akuvox"
    if not component.exists():
        subprocess.check_call(["git", "clone", "--depth", "1", LOCAL_AKUVOX_REPO, str(clone_dir)])
    return component


def clean_configuration_yaml(conf: Path) -> bool:
    text = conf.read_text()
    marker = "# Loads gate open command for E18 front gate"
    if marker not in text:
        return False
    start = text.index(marker)
    end = text.find("cover:", start)
    if end == -1:
        return False
    conf.write_text(text[:start] + text[end:])
    return True


def ensure_gate_secrets(secrets: Path, gate_password: str) -> None:
    text = secrets.read_text()
    lines = []
    if "gate_password:" not in text:
        lines.append(f'gate_password: "{gate_password}"')
    relay1 = (
        f'curl -skS --digest -u "admin:{gate_password}" '
        f'"https://192.168.1.73/fcgi/OpenDoor?action=OpenDoor&DoorNum=1"'
    )
    relay2 = (
        f'curl -skS --digest -u "admin:{gate_password}" '
        f'"https://192.168.1.73/fcgi/OpenDoor?action=OpenDoor&DoorNum=2"'
    )
    for key, value in [
        ("akuvox_gate_curl_relay_1", relay1),
        ("akuvox_gate_curl_relay_2", relay2),
    ]:
        if f"{key}:" not in text:
            lines.append(f'{key}: {json.dumps(value)}')
    if lines:
        secrets.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n")


def api_post(token: str, ha_url: str, path: str, data: dict | None = None) -> None:
    req = urllib.request.Request(
        f"{ha_url}{path}",
        data=json.dumps(data or {}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


async def wait_for_ha(token: str, ha_url: str, attempts: int = 36, delay: float = 10.0) -> bool:
    for _ in range(attempts):
        try:
            api_post(token, ha_url, "/api/config/core/check_config")
            return True
        except urllib.error.URLError:
            await asyncio.sleep(delay)
    return False


async def add_local_akuvox_entry(token: str, ha_url: str, password: str) -> None:
    entries = await ws_call(token, ha_url, [{"type": "config_entries/get", "domain": "local_akuvox"}])
    if entries[0].get("result"):
        print("Local Akuvox config entry already exists")
        return

    flow = await ws_call(
        token,
        ha_url,
        [{"type": "config_entries/flow/create", "handler": "local_akuvox", "context": {"source": "user"}}],
    )
    flow_id = flow[0]["result"]["flow_id"]

    steps = [
        {"host": "192.168.1.73", "use_ssl": True},
        {"verify_ssl": False},
        {"auth_method": "digest"},
        {"username": "admin", "password": password},
        {"webhook_enabled": True},
    ]

    for step_input in steps:
        res = await ws_call(
            token,
            ha_url,
            [{
                "type": "config_entries/flow/configure",
                "flow_id": flow_id,
                "user_input": step_input,
            }],
        )
        result = res[0].get("result", {})
        if result.get("type") == "create_entry":
            print("Created Local Akuvox config entry:", result.get("title"))
            return
        if result.get("type") == "abort":
            print("Local Akuvox flow aborted:", result.get("reason"))
            return
        if result.get("errors"):
            print("Local Akuvox flow error:", result["errors"])
            return

    print("Local Akuvox flow did not complete; finish in HA UI if needed")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default="192.168.1.239")
    parser.add_argument("--gate-password", required=True)
    parser.add_argument("--skip-restart", action="store_true")
    args = parser.parse_args()

    token = get_token()
    if not await wait_for_ha(token, args.ha_url, attempts=3, delay=2.0):
        print("Home Assistant API not reachable yet", file=sys.stderr)
        return 1

    user, pw = await get_samba_creds(token, args.ha_url)

    with tempfile.TemporaryDirectory() as tmp:
        component_src = ensure_local_akuvox(Path(tmp))
        mount_config(args.host, user, pw, args.mount)
        try:
            cfg = Path(args.mount)
            shutil.copy2(ROOT / "packages/gate_akuvox.yaml", cfg / "packages/gate_akuvox.yaml")

            dst = cfg / "custom_components/local_akuvox"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(component_src, dst)

            cleaned = clean_configuration_yaml(cfg / "configuration.yaml")
            print("Removed legacy gate block from configuration.yaml" if cleaned else "No legacy gate block found")

            ensure_gate_secrets(cfg / "secrets.yaml", args.gate_password)

            api_post(token, args.ha_url, "/api/config/core/check_config")
            if not args.skip_restart:
                await ws_call(
                    token,
                    args.ha_url,
                    [{"type": "supervisor/api", "endpoint": "/core/restart", "method": "post", "data": {}}],
                )
                print("Restarting Home Assistant core...")
        finally:
            subprocess.run(["diskutil", "umount", args.mount], capture_output=True)

    if not args.skip_restart:
        if not await wait_for_ha(token, args.ha_url):
            print("HA did not come back in time after restart", file=sys.stderr)
            return 1

    await add_local_akuvox_entry(token, args.ha_url, args.gate_password)
    print("Gate package deployed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

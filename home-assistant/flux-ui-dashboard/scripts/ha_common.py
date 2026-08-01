#!/usr/bin/env python3
"""Shared Home Assistant auth, WebSocket, and Samba helpers for Flux UI deploy."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import websockets

DEFAULT_HA = os.environ.get("HA_URL", "http://192.168.1.239:8123")
DEFAULT_HOST = os.environ.get("HA_HOST", "192.168.1.239")
DEFAULT_MOUNT = os.environ.get("HA_CONFIG_MOUNT", "/tmp/ha-config-smb")

MCP_PATHS = [
    Path.home() / ".cursor/mcp.json",
    Path("/Users/topexnative/.cursor/mcp.json"),
]


def get_token(explicit: str | None = None) -> str:
    if explicit:
        return explicit.strip()
    env = os.environ.get("HA_TOKEN") or os.environ.get("HOMEASSISTANT_TOKEN")
    if env:
        return env.strip()
    for path in MCP_PATHS:
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        auth = data.get("mcpServers", {}).get("homeassistant", {}).get("headers", {}).get(
            "Authorization", ""
        )
        if auth.startswith("Bearer "):
            return auth.split(" ", 1)[1]
    raise RuntimeError(
        "No HA token. Set HA_TOKEN, pass --token, or configure ~/.cursor/mcp.json homeassistant."
    )


async def ws_call(token: str, ha_url: str, calls: list[dict]) -> list[dict]:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url, max_size=50_000_000, open_timeout=30) as ws:
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


async def wait_for_ha(
    token: str,
    ha_url: str,
    *,
    timeout_s: float = 180,
    interval_s: float = 3,
    label: str = "HA",
) -> None:
    """Block until the HA websocket API accepts auth again (post-reload / restart)."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    attempt = 0
    last_err: Exception | None = None
    while loop.time() < deadline:
        attempt += 1
        try:
            if await ha_reachable(ha_url, token):
                if attempt > 1:
                    print(f"  {label} reachable again after {attempt} attempt(s)")
                return
        except Exception as exc:  # pragma: no cover - defensive
            last_err = exc
        await asyncio.sleep(interval_s)
    detail = f" ({last_err})" if last_err else ""
    raise RuntimeError(
        f"{label} at {ha_url} did not become reachable within {timeout_s:.0f}s{detail}"
    )


async def ws_call_retry(
    token: str,
    ha_url: str,
    calls: list[dict],
    *,
    attempts: int = 8,
    delay_s: float = 3,
    label: str = "HA websocket",
) -> list[dict]:
    """ws_call with retries — survives core reload / brief connection refused."""
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return await ws_call(token, ha_url, calls)
        except Exception as exc:
            last = exc
            if i >= attempts:
                break
            print(
                f"  WARNING: {label} failed ({type(exc).__name__}: {exc}) "
                f"— retry {i}/{attempts - 1} in {delay_s:.0f}s…"
            )
            await asyncio.sleep(delay_s)
            try:
                await wait_for_ha(token, ha_url, timeout_s=60, interval_s=2, label=label)
            except Exception:
                pass
    assert last is not None
    raise last


async def get_samba_creds(token: str, ha_url: str) -> tuple[str, str]:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "supervisor/api", "endpoint": "/addons/core_samba/info", "method": "get"}],
    )
    if not res[0].get("success"):
        raise RuntimeError(f"Samba addon info failed: {res[0]}")
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


async def ha_reachable(ha_url: str, token: str) -> bool:
    try:
        await ws_call(token, ha_url, [{"type": "ping"}])
        return True
    except Exception:
        return False


def run_async(coro):
    return asyncio.run(coro)

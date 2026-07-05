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

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_ENV = REPO_ROOT / ".secrets" / "ha.env"

DEFAULT_HA = os.environ.get("HA_URL", "http://192.168.1.239:8123")
DEFAULT_HOST = os.environ.get("HA_HOST", "192.168.1.239")
DEFAULT_MOUNT = os.environ.get("HA_CONFIG_MOUNT", "/tmp/ha-config-smb")

MCP_PATHS = [
    Path.home() / ".cursor/mcp.json",
    Path("/Users/topexnative/.cursor/mcp.json"),
]


def load_env_file(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .secrets/ha.env into os.environ (does not override)."""
    env_path = path or SECRETS_ENV
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def ensure_ha_env() -> None:
    """Load cloud secrets file so HA_URL / HA_TOKEN are available in agent sessions."""
    load_env_file()


def has_ha_credentials() -> bool:
    """True when a live deploy token is available (env, secrets file, or mcp.json)."""
    ensure_ha_env()
    if os.environ.get("HA_TOKEN") or os.environ.get("HOMEASSISTANT_TOKEN"):
        return True
    for path in MCP_PATHS:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            auth = data.get("mcpServers", {}).get("homeassistant", {}).get("headers", {}).get(
                "Authorization", ""
            )
            if auth.startswith("Bearer "):
                return True
        except (json.JSONDecodeError, OSError):
            continue
    return False


def ssh_configured() -> bool:
    ensure_ha_env()
    return bool(os.environ.get("HA_SSH_HOST") and os.environ.get("HA_SSH_USER"))


def get_token(explicit: str | None = None) -> str:
    ensure_ha_env()
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


async def fetch_lovelace_config(token: str, ha_url: str, url_path: str) -> dict:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config", "url_path": url_path, "force": True}],
    )
    if not res[0].get("success"):
        raise RuntimeError(f"lovelace/config failed for {url_path}: {res[0].get('error')}")
    return res[0]["result"]


def host_reachable(host: str, *, port: int = 445, timeout: float = 3.0) -> bool:
    """Quick TCP check — SMB/SSH push only when HA host is reachable from this machine."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_async(coro):
    return asyncio.run(coro)


# Load secrets as soon as this module is imported (cloud agent sessions).
ensure_ha_env()

#!/usr/bin/env python3
"""Shared Home Assistant auth, WebSocket, and Samba helpers for Flux UI deploy."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets

LAN_HA = "http://192.168.1.239:8123"
LAN_HOST = "192.168.1.239"
DEFAULT_HA = os.environ.get("HA_URL", LAN_HA)
DEFAULT_HOST = os.environ.get("HA_HOST", LAN_HOST)
DEFAULT_MOUNT = os.environ.get("HA_CONFIG_MOUNT", "/tmp/ha-config-smb")

MCP_PATHS = [
    Path.home() / ".cursor/mcp.json",
    Path("/Users/topexnative/.cursor/mcp.json"),
]
REMOTE_CACHE_PATHS = [
    Path.home() / ".cursor/ha-remote.json",
    Path("/Users/topexnative/.cursor/ha-remote.json"),
]


@dataclass
class HaEndpoint:
    url: str
    via: str  # env | lan | nabu_casa
    lan_host: str = LAN_HOST
    lan_url: str = LAN_HA
    nabu_casa_url: str | None = None
    smb_ok: bool = False

    def to_json(self, *, redact: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if redact and data.get("nabu_casa_url"):
            data["nabu_casa_url"] = _redact_url(data["nabu_casa_url"])
            if data["via"] != "lan":
                data["url"] = _redact_url(data["url"])
        return data


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


def _redact_url(url: str) -> str:
    if "nabu.casa" not in url:
        return url
    prefix, _, rest = url.partition("://")
    host, _, tail = rest.partition("/")
    label, _, domain = host.partition(".")
    hidden = (label[:2] + "…" + label[-2:]) if len(label) > 6 else "…"
    return f"{prefix}://{hidden}.{domain}/{tail}".rstrip("/")


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def _is_lan_url(url: str) -> bool:
    u = url.lower()
    return "192.168.1.239" in u or u.endswith("homeassistant.local:8123")


def _is_nabu_url(url: str) -> bool:
    return "ui.nabu.casa" in url.lower()


def _http_up(url: str, timeout: float = 1.5) -> bool:
    try:
        req = urllib.request.Request(_normalize_url(url) + "/api/", method="GET")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError as exc:
        return exc.code in {200, 401, 403, 405}
    except Exception:
        return False


def _cache_path() -> Path | None:
    for path in REMOTE_CACHE_PATHS:
        if path.exists():
            return path
    return REMOTE_CACHE_PATHS[0]


def load_remote_cache() -> dict[str, Any]:
    path = _cache_path()
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_remote_cache(*, nabu_casa_url: str) -> Path:
    path = _cache_path()
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "lan_url": LAN_HA,
        "lan_host": LAN_HOST,
        "nabu_casa_url": _normalize_url(nabu_casa_url),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    path.chmod(0o600)
    return path


def cached_nabu_casa_url() -> str | None:
    env = os.environ.get("HA_NABU_CASA_URL")
    if env:
        return _normalize_url(env)
    cached = load_remote_cache().get("nabu_casa_url")
    if isinstance(cached, str) and cached:
        return _normalize_url(cached)
    return None


def nabu_url_from_cloud_status(status: dict[str, Any]) -> str | None:
    domain = status.get("remote_domain")
    if isinstance(domain, str) and domain.strip():
        host = domain.strip()
        if host.startswith("http"):
            return _normalize_url(host)
        return f"https://{host.rstrip('/')}"
    return None


def refresh_nabu_cache(token: str, ha_url: str) -> str | None:
    """When LAN is up, persist the Nabu Casa Remote UI URL for travel."""
    try:
        results = run_async(ws_call(token, ha_url, [{"type": "cloud/status"}]))
    except Exception:
        return None
    if not results or not results[0].get("success"):
        return None
    url = nabu_url_from_cloud_status(results[0].get("result") or {})
    if not url:
        return None
    save_remote_cache(nabu_casa_url=url)
    return url


def resolve_ha(*, explicit: str | None = None, probe: bool = True) -> HaEndpoint:
    """LAN first, then Nabu Casa. HA_URL env wins (GitHub Actions / travel override)."""
    if explicit:
        url = _normalize_url(explicit)
        if _is_nabu_url(url):
            via = "nabu_casa"
        elif _is_lan_url(url):
            via = "lan"
        else:
            via = "env"
        return HaEndpoint(
            url=url,
            via=via,
            nabu_casa_url=url if via == "nabu_casa" else cached_nabu_casa_url(),
            smb_ok=via == "lan" and (not probe or _http_up(url)),
        )

    env_url = os.environ.get("HA_URL")
    if env_url:
        url = _normalize_url(env_url)
        via = "nabu_casa" if _is_nabu_url(url) else ("lan" if _is_lan_url(url) else "env")
        return HaEndpoint(
            url=url,
            via=via,
            nabu_casa_url=url if _is_nabu_url(url) else cached_nabu_casa_url(),
            smb_ok=via == "lan" and (not probe or _http_up(url)),
        )

    nabu = cached_nabu_casa_url()
    if not probe or _http_up(LAN_HA):
        return HaEndpoint(
            url=LAN_HA,
            via="lan",
            nabu_casa_url=nabu,
            smb_ok=True,
        )

    if nabu:
        return HaEndpoint(
            url=nabu,
            via="nabu_casa",
            nabu_casa_url=nabu,
            smb_ok=False,
        )

    raise RuntimeError(
        "Home Assistant LAN is unreachable and no Nabu Casa URL is cached. "
        "On LAN once: python3 home-assistant/scripts/ha_resolve.py --cache. "
        "Or set HA_URL to the Remote UI URL, or HA_NABU_CASA_URL."
    )


def resolved_ha_url(explicit: str | None = None) -> str:
    return resolve_ha(explicit=explicit).url


def apply_resolved_ha(args: Any) -> HaEndpoint:
    """Bind argparse namespace ha_url/host/skip_mount for LAN vs Nabu Casa."""
    endpoint = resolve_ha(explicit=getattr(args, "ha_url", None) or None)
    args.ha_url = endpoint.url
    host = getattr(args, "host", None)
    if not host or host == DEFAULT_HOST:
        args.host = endpoint.lan_host
    print(f"HA endpoint: {endpoint.url} (via {endpoint.via}, smb_ok={endpoint.smb_ok})")
    if not endpoint.smb_ok and not getattr(args, "force_mount", False):
        if hasattr(args, "skip_mount"):
            args.skip_mount = True
            print("  off-LAN or remote URL: SMB skipped — Lovelace API push only")
    return endpoint


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

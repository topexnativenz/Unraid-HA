"""Shared Home Assistant REST + WebSocket client for deploy and diagnostics scripts."""

from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_HA_URL = "http://192.168.1.239:8123"

MCP_PATHS = (
    Path.home() / ".cursor" / "mcp.json",
    Path("/Users/topexnative/.cursor/mcp.json"),
)

LAN_HOST_RE = re.compile(
    r"^https?://("
    r"localhost|127\.0\.0\.1|192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\."
    r")",
    re.I,
)


@dataclass
class HaConfig:
    url: str
    token: str
    source: str  # env | mcp | explicit


class HaAuthError(RuntimeError):
    pass


class HaConnectionError(RuntimeError):
    pass


def is_lan_url(url: str) -> bool:
    return bool(LAN_HOST_RE.match(url.rstrip("/")))


def resolve_ha_config(*, url: str | None = None, token: str | None = None) -> HaConfig:
    """Resolve HA URL and long-lived token from args, env, or ~/.cursor/mcp.json."""
    if token and url:
        return HaConfig(url=url.rstrip("/"), token=token, source="explicit")

    env_token = os.environ.get("HA_TOKEN")
    env_url = os.environ.get("HA_URL")
    if env_token:
        return HaConfig(
            url=(url or env_url or DEFAULT_HA_URL).rstrip("/"),
            token=env_token,
            source="env",
        )

    for mcp_path in MCP_PATHS:
        if not mcp_path.exists():
            continue
        data = json.loads(mcp_path.read_text())
        servers = data.get("mcpServers", {})
        ha = servers.get("homeassistant") or servers.get("home-assistant")
        if not ha:
            continue
        headers = ha.get("headers") or {}
        auth = headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            continue
        resolved_token = auth.split(" ", 1)[1]
        resolved_url = url or env_url or _url_from_mcp_server(ha) or DEFAULT_HA_URL
        return HaConfig(url=resolved_url.rstrip("/"), token=resolved_token, source="mcp")

    raise HaAuthError(
        "No Home Assistant credentials found.\n"
        "Cloud Agent: set environment secrets HA_URL (Nabu Casa https://….ui.nabu.casa) "
        "and HA_TOKEN (long-lived access token) in Cursor → Cloud Agents → Environment.\n"
        "Mac/local: ensure ~/.cursor/mcp.json has homeassistant MCP with Authorization header.\n"
        "Or export HA_URL and HA_TOKEN before running diagnostics."
    )


def _url_from_mcp_server(server: dict) -> str | None:
    for key in ("url", "serverUrl", "baseUrl"):
        val = server.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val.rstrip("/")
    return None


def ws_url(http_url: str) -> str:
    return http_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"


def _request(
    cfg: HaConfig,
    method: str,
    path: str,
    *,
    data: dict | None = None,
    timeout: float = 30,
    accept: str = "application/json",
) -> Any:
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        f"{cfg.url}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {cfg.token}",
            "Content-Type": "application/json",
            "Accept": accept,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return None
            if accept != "application/json":
                return raw.decode(errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise HaConnectionError(f"HTTP {exc.code} {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        hint = ""
        if is_lan_url(cfg.url):
            hint = " LAN URLs are unreachable from Cloud Agents — use your Nabu Casa URL in HA_URL."
        raise HaConnectionError(f"Cannot reach {cfg.url}{path}: {exc}.{hint}") from exc


def get_state(cfg: HaConfig, entity_id: str) -> dict | None:
    try:
        return _request(cfg, "GET", f"/api/states/{entity_id}")
    except HaConnectionError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def get_states(cfg: HaConfig) -> list[dict]:
    return _request(cfg, "GET", "/api/states")


def get_config(cfg: HaConfig) -> dict:
    return _request(cfg, "GET", "/api/config")


def get_error_log(cfg: HaConfig, *, lines: int = 80) -> str:
    """Fetch home-assistant.log error tail via REST."""
    text = _request(cfg, "GET", "/api/error_log", accept="text/plain")
    if not isinstance(text, str):
        return ""
    rows = text.strip().splitlines()
    return "\n".join(rows[-lines:])


def get_logbook(
    cfg: HaConfig,
    *,
    start: str,
    end: str | None = None,
    entities: list[str] | None = None,
) -> list[dict]:
    path = f"/api/logbook/{start}"
    params: list[str] = []
    if end:
        params.append(f"end_time={end}")
    for entity in entities or []:
        params.append(f"entity={entity}")
    if params:
        path += "?" + "&".join(params)
    result = _request(cfg, "GET", path, timeout=60)
    return result if isinstance(result, list) else []


def get_history(
    cfg: HaConfig,
    *,
    start: str,
    end: str | None = None,
    entities: list[str] | None = None,
    minimal: bool = True,
) -> list[list[dict]]:
    params = [f"filter_entity_id={','.join(entities or [])}", f"minimal={'true' if minimal else 'false'}"]
    if end:
        params.append(f"end_time={end}")
    path = f"/api/history/period/{start}?" + "&".join(params)
    result = _request(cfg, "GET", path, timeout=60)
    return result if isinstance(result, list) else []


async def ws_call(cfg: HaConfig, msg: dict, *, msg_id: int = 1) -> dict:
    import websockets

    payload = dict(msg)
    payload.setdefault("id", msg_id)
    async with websockets.connect(ws_url(cfg.url), max_size=20_000_000) as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": cfg.token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise HaAuthError(f"WebSocket auth failed: {auth}")

        await ws.send(json.dumps(payload))
        while True:
            reply = json.loads(await ws.recv())
            if reply.get("id") == payload["id"]:
                if reply.get("type") == "result" and not reply.get("success", True):
                    err = reply.get("error") or reply
                    raise HaConnectionError(f"WebSocket {payload['type']} failed: {err}")
                return reply


async def get_entity_registry_entry(cfg: HaConfig, entity_id: str) -> dict | None:
    try:
        reply = await ws_call(cfg, {"type": "config/entity_registry/get", "entity_id": entity_id})
        result = reply.get("result")
        return result if isinstance(result, dict) else None
    except HaConnectionError:
        return None


async def resolve_trace_target(cfg: HaConfig, entity_id: str) -> tuple[str, str]:
    """Return (domain, item_id) for trace/list and trace/get."""
    if entity_id.startswith("automation."):
        domain = "automation"
    elif entity_id.startswith("script."):
        domain = "script"
    else:
        raise HaConnectionError(f"Not an automation or script entity: {entity_id}")

    object_id = entity_id.split(".", 1)[1]
    entry = await get_entity_registry_entry(cfg, entity_id)
    if entry and entry.get("unique_id"):
        return domain, str(entry["unique_id"])

    st = get_state(cfg, entity_id)
    attrs = (st or {}).get("attributes") or {}
    if attrs.get("id"):
        return domain, str(attrs["id"])

    return domain, object_id


async def list_traces(cfg: HaConfig, domain: str, item_id: str) -> list[dict]:
    msg: dict[str, Any] = {"type": "trace/list", "domain": domain, "item_id": item_id}
    reply = await ws_call(cfg, msg)
    result = reply.get("result", reply)
    if isinstance(result, list):
        return [row for row in result if isinstance(row, dict)]
    return normalize_trace_index(result)


async def get_trace(cfg: HaConfig, domain: str, item_id: str, run_id: str) -> dict:
    msg = {"type": "trace/get", "domain": domain, "item_id": item_id, "run_id": run_id}
    reply = await ws_call(cfg, msg)
    result = reply.get("result", reply)
    return result if isinstance(result, dict) else {"trace": result}


async def list_system_log(cfg: HaConfig) -> list[dict]:
    reply = await ws_call(cfg, {"type": "system_log/list"})
    result = reply.get("result", reply)
    return result if isinstance(result, list) else []


def normalize_trace_index(traces: object) -> list[dict]:
    """Normalize trace/list payloads across HA versions."""
    if isinstance(traces, list):
        return [t for t in traces if isinstance(t, dict)]
    if not isinstance(traces, dict):
        return []
    entries: list[dict] = []
    for key, runs in traces.items():
        if isinstance(runs, dict):
            for run_id, summary in runs.items():
                row = {"automation_id": key, "run_id": run_id}
                if isinstance(summary, dict):
                    row.update(summary)
                entries.append(row)
        elif isinstance(runs, list):
            for row in runs:
                if isinstance(row, dict):
                    entries.append(row)
    return entries


async def list_automation_traces(cfg: HaConfig, automation_id: str | None = None) -> Any:
    """Legacy helper — prefer list_traces after resolve_trace_target."""
    if automation_id:
        entity_id = automation_id if "." in automation_id else f"automation.{automation_id}"
        domain, item_id = await resolve_trace_target(cfg, entity_id)
        return await list_traces(cfg, domain, item_id)

    msg: dict[str, Any] = {"type": "automation/trace/list"}
    try:
        reply = await ws_call(cfg, msg)
        return reply.get("result", reply)
    except HaConnectionError:
        reply = await ws_call(cfg, {"type": "trace/list", "domain": "automation"}, msg_id=2)
        return reply.get("result", reply)


async def get_automation_trace(cfg: HaConfig, automation_id: str, run_id: str) -> Any:
    entity_id = automation_id if "." in automation_id else f"automation.{automation_id}"
    domain, item_id = await resolve_trace_target(cfg, entity_id)
    return await get_trace(cfg, domain, item_id, run_id)


async def verify_connection(cfg: HaConfig) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "url": cfg.url,
        "auth_source": cfg.source,
        "lan_url": is_lan_url(cfg.url),
        "rest_ok": False,
        "websocket_ok": False,
        "traces_ok": False,
        "logbook_ok": False,
        "system_log_ok": False,
        "error_log_ok": False,
        "ha_version": None,
        "timezone": None,
        "errors": [],
        "warnings": [],
    }
    if summary["lan_url"] and summary["auth_source"] == "env":
        summary["warnings"].append(
            "HA_URL looks like a LAN address. Cloud Agents need your Nabu Casa URL "
            "(https://….ui.nabu.casa)."
        )

    try:
        config = get_config(cfg)
        summary["rest_ok"] = True
        summary["ha_version"] = config.get("version")
        summary["timezone"] = config.get("time_zone")
    except HaConnectionError as exc:
        summary["errors"].append(f"REST: {exc}")

    try:
        reply = await ws_call(cfg, {"type": "ping"})
        summary["websocket_ok"] = reply.get("success", False) or reply.get("type") == "pong"
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"WebSocket: {exc}")

    if summary["rest_ok"]:
        try:
            get_logbook(cfg, start="1970-01-01T00:00:00", entities=["sun.sun"])
            summary["logbook_ok"] = True
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"Logbook: {exc}")

        try:
            log = get_error_log(cfg, lines=5)
            summary["error_log_ok"] = bool(log.strip())
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"Error log: {exc}")

    if summary["websocket_ok"]:
        try:
            await list_system_log(cfg)
            summary["system_log_ok"] = True
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"System log: {exc}")

        try:
            await ws_call(cfg, {"type": "trace/list", "domain": "automation"}, msg_id=99)
            summary["traces_ok"] = True
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"Traces: {exc}")

    return summary


def run_async(coro):
    return asyncio.run(coro)

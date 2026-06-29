from __future__ import annotations

import time
from typing import Any

from xero_mcp.audit import audit_event
from xero_mcp.auth import AuthError, TokenSet, ensure_access_token, fetch_connections
from xero_mcp.config import load_credentials, load_token_store, save_token_store
from xero_mcp.health import (
    load_health,
    token_keeper_installed,
    token_keeper_loaded,
    write_health,
    xero_audit_hints,
)


def run_maintenance(*, live_connections: bool = True) -> dict[str, Any]:
    """Refresh token if needed, optionally sync org list, update health.json."""
    started = time.time()
    report: dict[str, Any] = {
        "checked_at": started,
        "healthy": False,
        "reauth_required": False,
        "token_expires_in_seconds": 0,
        "connections_count": 0,
        "connections": [],
        "token_keeper_installed": token_keeper_installed(),
        "token_keeper_loaded": token_keeper_loaded(),
        "last_error": None,
    }

    try:
        creds = load_credentials()
        report["app_name"] = creds.app_name
        report["client_id_prefix"] = creds.client_id[:8] + "…"
        report["xero_audit"] = xero_audit_hints(creds.app_name)

        access_token = ensure_access_token()
        store = load_token_store()
        token_data = store.get("token") or {}
        token_set = TokenSet.from_store(token_data)
        report["token_expires_in_seconds"] = max(0, int(token_set.expires_at - time.time()))

        connections = store.get("connections") or []
        if live_connections:
            connections = fetch_connections(access_token)
            store["connections"] = connections
            store["updated_at"] = time.time()
            save_token_store(store)

        report["connections_count"] = len(connections)
        report["connections"] = [
            {
                "tenant_id": c.get("tenantId"),
                "tenant_name": c.get("tenantName"),
                "updated_date_utc": c.get("updatedDateUtc"),
            }
            for c in connections
        ]
        report["healthy"] = True
        audit_event(
            "maintain_ok",
            connections=len(connections),
            token_expires_in=report["token_expires_in_seconds"],
            duration_ms=int((time.time() - started) * 1000),
        )
        try:
            from xero_mcp.tenants import ensure_default_active_org, get_active_organisation

            ensure_default_active_org()
            active = get_active_organisation()
            if active:
                report["active_organisation"] = active.to_dict()
        except Exception as exc:
            report["active_organisation_error"] = str(exc)
    except AuthError as exc:
        message = str(exc)
        report["last_error"] = message
        report["reauth_required"] = "login" in message.lower() or "refresh" in message.lower()
        audit_event("maintain_failed", error=message, reauth_required=report["reauth_required"])
    except FileNotFoundError as exc:
        report["last_error"] = str(exc)
        report["reauth_required"] = True
        audit_event("maintain_failed", error=str(exc), reauth_required=True)

    report["checked_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    write_health(report)
    return report


def doctor_report() -> dict[str, Any]:
    """Human-facing health summary; safe to print (no secrets)."""
    health = load_health()
    if not health:
        health = run_maintenance(live_connections=False)

    lines = [
        "Xero MCP health",
        "---------------",
        f"Healthy: {'yes' if health.get('healthy') else 'no'}",
        f"Re-auth required: {'yes' if health.get('reauth_required') else 'no'}",
        f"Token expires in: {health.get('token_expires_in_seconds', 0)}s",
        f"Connected orgs: {health.get('connections_count', 0)}",
        f"Token keeper installed: {'yes' if health.get('token_keeper_installed') else 'no'}",
        f"Token keeper loaded: {'yes' if health.get('token_keeper_loaded') else 'no'}",
    ]
    for conn in health.get("connections") or []:
        lines.append(f"  - {conn.get('tenant_name')} ({conn.get('tenant_id')})")

    audit = health.get("xero_audit") or {}
    if audit:
        lines.extend(
            [
                "",
                "Verify in Xero (any time):",
                f"  App name: {audit.get('app_name', '—')}",
                f"  Each org → {audit.get('connected_apps_in_xero', 'Connected apps')}",
                f"  Developer portal → {audit.get('developer_portal', '')}",
            ]
        )
    if health.get("last_error"):
        lines.extend(["", f"Last error: {health['last_error']}"])

    return {"summary_lines": lines, "health": health}

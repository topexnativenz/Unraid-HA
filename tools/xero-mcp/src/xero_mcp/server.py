from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from xero_mcp import tenants as tenant_store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("xero-orgs-mcp")

mcp = FastMCP(
    "xero-orgs",
    instructions=(
        "Multi-org tenant picker for Xero. ALWAYS call set_active_organisation with the "
        "target company slug or name before using xero MCP accounting tools (list-invoices, "
        "create-invoice, etc.). Switch takes effect immediately — no MCP restart needed. "
        "Slugs: matariki-property-group, matariki-traders, matariki-morningside-development."
    ),
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2)


@mcp.tool()
def list_organisations(refresh: bool = False) -> str:
    """List connected Xero organisations with slugs for set_active_organisation."""
    try:
        orgs = tenant_store.list_organisations(refresh=refresh)
        active = tenant_store.get_active_organisation()
        return _json(
            {
                "active_slug": active.slug if active else None,
                "organisations": [o.to_dict() for o in orgs],
            }
        )
    except tenant_store.TenantError as exc:
        return _json({"error": str(exc)})


@mcp.tool()
def get_active_organisation() -> str:
    """Return the organisation currently selected for xero MCP tool calls."""
    tenant_store.ensure_default_active_org()
    return _json(tenant_store.active_org_summary())


@mcp.tool()
def set_active_organisation(org: str) -> str:
    """Select which Xero organisation subsequent xero MCP tools should use.

    Args:
        org: Slug (e.g. matariki-traders), partial name, or tenant UUID.
    """
    try:
        selected = tenant_store.set_active_organisation(org)
        return _json(
            {
                "ok": True,
                "message": f"Active organisation set to {selected.tenant_name}",
                "active": selected.to_dict(),
            }
        )
    except tenant_store.TenantError as exc:
        return _json({"ok": False, "error": str(exc)})


@mcp.tool()
def sync_organisations() -> str:
    """Refresh org list from Xero /connections (after OAuth or org access changes)."""
    try:
        orgs = tenant_store.sync_org_registry()
        return _json({"synced": len(orgs), "organisations": [o.to_dict() for o in orgs]})
    except tenant_store.TenantError as exc:
        return _json({"error": str(exc)})


def main() -> None:
    try:
        tenant_store.ensure_default_active_org()
    except tenant_store.TenantError:
        log.warning("No active org yet — complete OAuth login first.")
    mcp.run()


if __name__ == "__main__":
    main()

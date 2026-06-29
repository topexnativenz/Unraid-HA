from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from xero_mcp.inbound.config import load_inbound_config
from xero_mcp.inbound.heal import health_summary, run_heal
from xero_mcp.inbound.processor import process_message, process_pending, queue_summary, retry_failed

logging.basicConfig(level=logging.INFO)

mcp = FastMCP(
    "xero-inbound",
    instructions=(
        "Inbound email → Xero draft bills. Intake at accounts@ / david@ / genna@ with "
        "portfolio AI routing to Matariki orgs. Use list_inbound_queue to monitor, "
        "process_inbound_message to process manually, retry_failed_inbound on errors, "
        "scan_inbound_health / auto_heal_inbound for stuck queue recovery. "
        "Call xero-orgs set_active_organisation is handled automatically during processing."
    ),
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2)


@mcp.tool()
def list_inbound_queue(limit: int = 20) -> str:
    """List recent inbound email queue entries and route addresses."""
    return _json(queue_summary(limit=limit))


@mcp.tool()
def get_inbound_routes() -> str:
    """Show configured per-org email aliases and org slugs."""
    config = load_inbound_config()
    return _json(
        {
            "domain": config.domain,
            "auto_process": config.auto_process,
            "webhook_port": config.webhook_port,
            "routes": [
                {
                    "address": route.address,
                    "org_slug": route.org_slug,
                    "document_type": route.document_type,
                    "default_account_code": route.default_account_code,
                    "label": route.label,
                }
                for route in config.routes
            ],
        }
    )


@mcp.tool()
def process_inbound_message(message_id: str) -> str:
    """Process a queued inbound message into a Xero draft bill with attachment."""
    return _json(process_message(message_id))


@mcp.tool()
def process_pending_inbound(limit: int = 10) -> str:
    """Process all pending inbound messages (up to limit)."""
    return _json(process_pending(limit=limit))


@mcp.tool()
def retry_failed_inbound(message_id: str) -> str:
    """Retry a failed inbound message."""
    return _json(retry_failed(message_id))


@mcp.tool()
def scan_inbound_health(limit: int = 30) -> str:
    """Summarize failed/stuck inbound queue items with heal diagnoses (no changes)."""
    return _json(health_summary(scan_limit=limit))


@mcp.tool()
def auto_heal_inbound(limit: int = 10, dry_run: bool = False) -> str:
    """Auto-retry stuck/failed inbound messages (429, pending timeout, done without bill)."""
    return _json(run_heal(dry_run=dry_run, limit=limit))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

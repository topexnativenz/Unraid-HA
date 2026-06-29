from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from xero_mcp.config import HEALTH_FILE, ensure_config_dir

LAUNCH_AGENT_LABEL = "com.unraid-array-design.xero-mcp-token-keeper"
LAUNCH_AGENT_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
)

XERO_CONNECTED_APPS_PATH = "Settings → General Settings → Connected apps"


def token_keeper_installed() -> bool:
    return LAUNCH_AGENT_PLIST.exists()


def token_keeper_loaded() -> bool:
    if not token_keeper_installed():
        return False
    import subprocess

    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def write_health(payload: dict[str, Any]) -> None:
    ensure_config_dir()
    HEALTH_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    HEALTH_FILE.chmod(0o600)


def load_health() -> dict[str, Any]:
    if not HEALTH_FILE.exists():
        return {}
    return json.loads(HEALTH_FILE.read_text())


def xero_audit_hints(app_name: str) -> dict[str, Any]:
    return {
        "app_name": app_name,
        "developer_portal": "https://developer.xero.com/app/manage/",
        "connected_apps_in_xero": XERO_CONNECTED_APPS_PATH,
        "revoke_instructions": (
            f"In each Xero org, open {XERO_CONNECTED_APPS_PATH}, find "
            f"\"{app_name}\", and click Disconnect. API access stops immediately."
        ),
        "transaction_audit": (
            "Invoice, bill, contact, and payment changes made via MCP appear in "
            "each org's usual Xero history (e.g. invoice History & Notes)."
        ),
    }

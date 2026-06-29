from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from xero_mcp.config import AUDIT_LOG_FILE, ensure_config_dir


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_event(event: str, **fields: Any) -> None:
    """Append a redacted audit record (never log tokens or secrets)."""
    ensure_config_dir()
    record = {"ts": _now_iso(), "event": event, **fields}
    with AUDIT_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    try:
        AUDIT_LOG_FILE.chmod(0o600)
    except OSError:
        pass


def read_recent_events(limit: int = 20) -> list[dict[str, Any]]:
    if not AUDIT_LOG_FILE.exists():
        return []
    lines = AUDIT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events

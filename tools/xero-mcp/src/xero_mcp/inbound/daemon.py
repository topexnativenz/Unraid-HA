from __future__ import annotations

import logging
import threading
import time

from xero_mcp.maintain import run_maintenance

log = logging.getLogger("xero-inbound-daemon")


def _maintain_loop(interval_seconds: int = 900) -> None:
    while True:
        try:
            report = run_maintenance(live_connections=True)
            if not report.get("healthy"):
                log.warning("Token maintenance unhealthy: %s", report.get("error"))
            else:
                log.info("Token maintenance OK")
        except Exception:
            log.exception("Token maintenance failed")
        time.sleep(interval_seconds)


def start_maintain_thread(interval_seconds: int = 900) -> threading.Thread:
    thread = threading.Thread(
        target=_maintain_loop,
        args=(interval_seconds,),
        name="xero-token-maintain",
        daemon=True,
    )
    thread.start()
    return thread

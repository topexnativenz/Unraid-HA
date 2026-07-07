#!/usr/bin/env python3
"""Exit 0 when HA credentials are configured for live cloud deploy."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import DEFAULT_HA, ensure_ha_env, get_token, has_ha_credentials, run_async, ha_reachable  # noqa: E402


def main() -> int:
    ensure_ha_env()
    if not has_ha_credentials():
        print("No HA token found (set HA_TOKEN or .secrets/ha.env)")
        return 1
    try:
        token = get_token()
    except RuntimeError as exc:
        print(exc)
        return 1

    print(f"  HA_URL={DEFAULT_HA}")
    print("  HA_TOKEN=***")

    if run_async(ha_reachable(DEFAULT_HA, token)):
        print(f"  HA reachable at {DEFAULT_HA}")
        return 0

    print(f"  WARNING: HA not reachable at {DEFAULT_HA} (check URL / Nabu Casa / VPN)")
    # Credentials exist — deploy scripts will retry; do not block build-only fallback.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

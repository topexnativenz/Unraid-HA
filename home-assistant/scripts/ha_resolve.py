#!/usr/bin/env python3
"""Resolve Home Assistant URL: LAN first, then cached Nabu Casa Remote UI.

Usage:
  python3 home-assistant/scripts/ha_resolve.py
  python3 home-assistant/scripts/ha_resolve.py --json
  python3 home-assistant/scripts/ha_resolve.py --cache   # refresh Nabu Casa URL while on LAN
  python3 home-assistant/scripts/ha_resolve.py --mcp     # print Cursor MCP SSE URL
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "flux-ui-dashboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ha_common import (  # noqa: E402
    cached_nabu_casa_url,
    get_token,
    refresh_nabu_cache,
    resolve_ha,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable endpoint")
    parser.add_argument(
        "--redact",
        action="store_true",
        help="Hide Nabu Casa hostname in JSON (for logs)",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="While on LAN, persist Remote UI URL to ~/.cursor/ha-remote.json",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Print MCP SSE URL only",
    )
    parser.add_argument("--ha-url", default=None)
    args = parser.parse_args()

    endpoint = resolve_ha(explicit=args.ha_url)

    if args.cache:
        if endpoint.via != "lan":
            print("ERROR: --cache requires LAN reachability (192.168.1.239).", file=sys.stderr)
            return 2
        url = refresh_nabu_cache(get_token(), endpoint.url)
        if not url:
            print("ERROR: cloud/status did not return a Remote UI domain.", file=sys.stderr)
            return 2
        endpoint = resolve_ha(explicit=args.ha_url)
        print(f"Cached Nabu Casa Remote UI → {Path.home() / '.cursor/ha-remote.json'}")

    if args.mcp:
        print(f"{endpoint.url}/mcp_server/sse")
        return 0

    if args.json:
        data = endpoint.to_json(redact=args.redact)
        data["mcp_url"] = f"{endpoint.url}/mcp_server/sse"
        data["cached_nabu"] = bool(cached_nabu_casa_url())
        print(json.dumps(data, indent=2))
        return 0

    print(endpoint.url)
    print(f"via={endpoint.via} smb_ok={endpoint.smb_ok}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash
# LAN-first Home Assistant URL (Nabu Casa fallback). See ha_resolve.py.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$ROOT/ha_resolve.py" "$@"

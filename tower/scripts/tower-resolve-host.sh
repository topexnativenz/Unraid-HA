#!/bin/bash
# Resolve tower SSH/MCP host: LAN first, then Tailscale.
# Usage:
#   tower-resolve-host.sh           → prints host (192.168.1.7 or 100.79.125.103)
#   tower-resolve-host.sh --via     → prints "lan" or "tailscale"
#   tower-resolve-host.sh --json    → {"host":"...","via":"..."}
set -euo pipefail

LAN_HOST="${TOWER_LAN_HOST:-192.168.1.7}"
TS_HOST="${TOWER_TS_HOST:-100.79.125.103}"
PORT="${TOWER_SSH_PORT:-22}"
NC_TIMEOUT="${TOWER_NC_TIMEOUT:-2}"

reachable() {
  python3 - "$1" "$PORT" "$NC_TIMEOUT" <<'PY' >/dev/null 2>&1
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
timeout = float(sys.argv[3])

s = socket.socket()
s.settimeout(timeout)
try:
    s.connect((host, port))
except Exception:
    sys.exit(1)
else:
    sys.exit(0)
finally:
    s.close()
PY
}

if reachable "$LAN_HOST"; then
  HOST="$LAN_HOST"
  VIA="lan"
elif reachable "$TS_HOST"; then
  HOST="$TS_HOST"
  VIA="tailscale"
else
  cat >&2 <<EOF
Tower unreachable from this Mac.

  • On home LAN: confirm tower is up (${LAN_HOST}:${PORT}).
  • Away from home: open Tailscale and connect, then retry.

  ssh tower-lan     # force LAN
  Tailscale app     # remote path → ${TS_HOST}
EOF
  exit 1
fi

case "${1:-}" in
  --via)   echo "$VIA" ;;
  --json)  printf '{"host":"%s","via":"%s"}\n' "$HOST" "$VIA" ;;
  --help|-h)
    echo "usage: $0 [--via|--json]" >&2
    exit 0
    ;;
  "")      echo "$HOST" ;;
  *)
    echo "unknown option: $1" >&2
    exit 2
    ;;
esac

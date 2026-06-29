#!/bin/bash
# Cursor tower-ssh MCP: resolve LAN vs Tailscale before starting ssh-mcp.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="$("${REPO_ROOT}/scripts/tower-resolve-host.sh")"
VIA="$("${REPO_ROOT}/scripts/tower-resolve-host.sh" --via)"

echo "tower-ssh MCP: via=${VIA} host=${HOST}" >&2

exec npx -y ssh-mcp -- \
  "--host=${HOST}" \
  --port=22 \
  --user=root \
  --key=/Users/topexnative/.ssh/id_ed25519_unraid \
  --timeout=120000 \
  --maxChars=none

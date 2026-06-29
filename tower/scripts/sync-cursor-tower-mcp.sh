#!/bin/bash
# Point Cursor tower MCP URLs at the current reachable host (LAN or Tailscale).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_JSON="${CURSOR_MCP_JSON:-/Users/topexnative/.cursor/mcp.json}"
MCP_WRAPPER="${REPO_ROOT}/scripts/tower-ssh-mcp.sh"
HOST="$("${REPO_ROOT}/scripts/tower-resolve-host.sh")"
VIA="$("${REPO_ROOT}/scripts/tower-resolve-host.sh" --via)"

python3 - "$MCP_JSON" "$HOST" "$MCP_WRAPPER" <<'PY'
import json
import sys
from pathlib import Path

path, host, wrapper = sys.argv[1:4]
data = json.loads(Path(path).read_text())
servers = data.setdefault("mcpServers", {})

servers["tower-ssh"] = {
    "command": wrapper,
    "args": [],
}

for name, port in (("unraid-filesystem", 8103), ("unraid-playwright", 8104)):
    srv = servers.setdefault(name, {})
    headers = srv.get("headers") or {}
    srv["url"] = f"http://{host}:{port}/sse"
    if headers:
        srv["headers"] = headers

Path(path).write_text(json.dumps(data, indent=2) + "\n")
print(f"Updated {path}: host={host}")
PY

echo "tower MCP synced: via=${VIA} host=${HOST}"
echo "Restart Cursor MCP servers (or reload window) for changes to take effect."

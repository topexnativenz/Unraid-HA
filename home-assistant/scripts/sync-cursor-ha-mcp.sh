#!/usr/bin/env bash
# Point Cursor Home Assistant MCP at the resolved URL (LAN or Nabu Casa).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MCP="${HA_MCP_JSON:-/Users/topexnative/.cursor/mcp.json}"

SSE="$(python3 "$ROOT/ha_resolve.py" --mcp)"
python3 - "$MCP" "$SSE" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
sse = sys.argv[2].rstrip("/")
data = json.loads(path.read_text())
server = data.setdefault("mcpServers", {}).setdefault("homeassistant", {})
server["url"] = sse
path.write_text(json.dumps(data, indent=2) + "\n")
print(f"Updated {path} homeassistant.url → {sse}")
PY

#!/bin/bash
# Register Xero MCP servers in Cursor mcp.json.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_JSON="${CURSOR_MCP_JSON:-/Users/topexnative/.cursor/mcp.json}"
WRAPPER="${REPO_ROOT}/scripts/xero-mcp-wrapper.sh"
VENV_PY="${REPO_ROOT}/.venv/bin/python"

chmod +x "$WRAPPER"

python3 - "$MCP_JSON" "$WRAPPER" "$VENV_PY" "$REPO_ROOT" <<'PY'
import json
import sys
from pathlib import Path

path, wrapper, venv_py, repo_root = sys.argv[1:5]
data = json.loads(Path(path).read_text())
servers = data.setdefault("mcpServers", {})

servers["xero"] = {
    "command": wrapper,
    "args": [],
}

servers["xero-orgs"] = {
    "command": venv_py,
    "args": ["-m", "xero_mcp.server"],
    "cwd": repo_root,
}

servers["xero-inbound"] = {
    "command": venv_py,
    "args": ["-m", "xero_mcp.inbound_server"],
    "cwd": repo_root,
}

Path(path).write_text(json.dumps(data, indent=2) + "\n")
print(f"Updated {path}: xero, xero-orgs, xero-inbound")
PY

echo "Reload Cursor MCP servers."

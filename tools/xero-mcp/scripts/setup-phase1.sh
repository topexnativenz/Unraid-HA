#!/bin/bash
# Phase 1: sync org registry, optional org labels config, Cursor MCP wiring.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
CONFIG_DIR="/Users/topexnative/.config/xero-mcp"

source .venv/bin/activate 2>/dev/null || {
  python3.12 -m venv .venv
  .venv/bin/pip install -e . -q
  source .venv/bin/activate
}

export PATH="/Users/topexnative/.nvm/versions/node/v24.15.0/bin:${PATH}"
npm install --silent
node scripts/apply-xero-tenant-patch.mjs

mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/orgs.config.json" ]]; then
  cp "$REPO_ROOT/xero.orgs.example.json" "$CONFIG_DIR/orgs.config.json"
  chmod 600 "$CONFIG_DIR/orgs.config.json"
  echo "Created $CONFIG_DIR/orgs.config.json"
fi

python -m xero_mcp sync-orgs
python -m xero_mcp list-orgs
bash "$REPO_ROOT/scripts/sync-cursor-xero-mcp.sh"

echo ""
echo "Phase 1 ready. Reload Cursor MCP servers."
echo "Use xero-orgs.set_active_organisation before xero accounting tools."

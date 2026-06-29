#!/bin/bash
# Start tenant-aware @xeroapi/xero-mcp-server with refreshed OAuth bearer token.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${REPO_ROOT}/.venv/bin/python"
XERO_SERVER="${REPO_ROOT}/node_modules/@xeroapi/xero-mcp-server/dist/index.js"

if [[ ! -x "$VENV_PY" ]]; then
  echo "xero-mcp: missing venv at ${REPO_ROOT}/.venv" >&2
  exit 1
fi

export PATH="/Users/topexnative/.nvm/versions/node/v24.15.0/bin:${PATH}"

if [[ ! -f "$XERO_SERVER" ]]; then
  (cd "$REPO_ROOT" && npm install --silent)
fi
node "$REPO_ROOT/scripts/apply-xero-tenant-patch.mjs"

if ! "$VENV_PY" -m xero_mcp maintain --quiet --skip-connections 2>/dev/null; then
  echo "xero-mcp: token maintenance failed — run: $VENV_PY -m xero_mcp doctor" >&2
  exit 1
fi

"$VENV_PY" -m xero_mcp sync-orgs >/dev/null 2>&1 || true
"$VENV_PY" -c "from xero_mcp.tenants import ensure_default_active_org; ensure_default_active_org()" >/dev/null 2>&1 || true

export XERO_CLIENT_BEARER_TOKEN="$("$VENV_PY" -m xero_mcp token)"
exec node "$XERO_SERVER"

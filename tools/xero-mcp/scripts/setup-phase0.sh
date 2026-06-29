#!/bin/bash
# Phase 0 setup: one-time OAuth, then fully hands-off token maintenance.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

APP_NAME="${XERO_APP_NAME:-Cursor MCP (Mac)}"

if [[ -z "${XERO_CLIENT_ID:-}" || -z "${XERO_CLIENT_SECRET:-}" ]]; then
  cat >&2 <<EOF
Missing XERO_CLIENT_ID and/or XERO_CLIENT_SECRET.

One-time Xero developer setup:
1. https://developer.xero.com/app/manage/ → New app → Web app
2. App name (use exactly): ${APP_NAME}
3. Redirect URI: http://localhost:8765/callback
4. Re-run:

   export XERO_CLIENT_ID="..."
   export XERO_CLIENT_SECRET="..."
   bash ${REPO_ROOT}/scripts/setup-phase0.sh
EOF
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  python3.12 -m venv .venv
  .venv/bin/pip install -e . -q
fi

.venv/bin/python -m xero_mcp init \
  --client-id "$XERO_CLIENT_ID" \
  --client-secret "$XERO_CLIENT_SECRET" \
  --app-name "$APP_NAME"

echo ""
echo "One-time OAuth — tick every organisation you want. Refresh tokens then run hands-off."
.venv/bin/python -m xero_mcp login

echo ""
.venv/bin/python -m xero_mcp maintain

bash "${REPO_ROOT}/scripts/install-token-keeper.sh"
bash "${REPO_ROOT}/scripts/sync-cursor-xero-mcp.sh"

echo ""
.venv/bin/python -m xero_mcp doctor

echo ""
echo "Setup complete. Day-to-day: no action needed."
echo "Check anytime: python -m xero_mcp doctor"
echo "Revoke in Xero: Settings → General Settings → Connected apps → ${APP_NAME}"

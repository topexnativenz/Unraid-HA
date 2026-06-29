#!/bin/bash
# Verify OAuth token and list connected Xero organisations.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
source .venv/bin/activate

python -m xero_mcp doctor
echo ""
TOKEN=$(python -m xero_mcp token)
echo "API /connections:"
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" \
  https://api.xero.com/connections | python -m json.tool

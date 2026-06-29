#!/bin/bash
# Phase 2: per-org email aliases → inbound webhook → Xero draft bills.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
CONFIG_DIR="/Users/topexnative/.config/xero-mcp"
DOMAIN="${XERO_INBOUND_DOMAIN:-}"

if [[ -z "$DOMAIN" ]]; then
  cat >&2 <<'EOF'
Set your email domain first:

  export XERO_INBOUND_DOMAIN="yourdomain.co.nz"
  bash /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp/scripts/setup-phase2.sh

This creates bills.property@, bills.traders@, bills.morningside@ on that domain.
EOF
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  python3.12 -m venv .venv
fi
source .venv/bin/activate
pip install -e . -q
export PATH="/Users/topexnative/.nvm/versions/node/v24.15.0/bin:${PATH}"
npm install --silent 2>/dev/null || true
node scripts/apply-xero-tenant-patch.mjs

.venv/bin/python -m xero_mcp inbound init --domain "$DOMAIN"

# Resolve first expense/overheads account code per org from Xero (fallback 400).
.venv/bin/python <<'PY'
import json
from pathlib import Path
import httpx
from xero_mcp.auth import ensure_access_token
from xero_mcp.tenants import list_organisations

config_path = Path("/Users/topexnative/.config/xero-mcp/inbound.json")
data = json.loads(config_path.read_text())
token = ensure_access_token()
headers_base = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

def pick_account_code(tenant_id: str) -> str:
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            "https://api.xero.com/api.xro/2.0/Accounts",
            headers={**headers_base, "xero-tenant-id": tenant_id},
        )
        resp.raise_for_status()
        accounts = resp.json().get("Accounts") or []
    for acct in accounts:
        if acct.get("Status") != "ACTIVE":
            continue
        if acct.get("Type") in ("EXPENSE", "OVERHEADS", "DIRECTCOSTS"):
            return str(acct.get("Code"))
    for acct in accounts:
        if acct.get("Status") == "ACTIVE" and acct.get("Code"):
            return str(acct.get("Code"))
    return "400"

orgs = {o.slug: o.tenant_id for o in list_organisations(refresh=True)}
for route in data.get("routes") or []:
    slug = route.get("org_slug")
    if slug in orgs:
        route["default_account_code"] = pick_account_code(orgs[slug])
config_path.write_text(json.dumps(data, indent=2) + "\n")
config_path.chmod(0o600)
print("Updated default_account_code per org from Xero chart of accounts.")
PY

bash "$REPO_ROOT/scripts/install-inbound-webhook.sh"
bash "$REPO_ROOT/scripts/sync-cursor-xero-mcp.sh"

SECRET=$(python -c "import json;print(json.load(open('$CONFIG_DIR/inbound.json'))['webhook_secret'])")
PORT=$(python -c "import json;print(json.load(open('$CONFIG_DIR/inbound.json'))['webhook_port'])")

cat <<EOF

Phase 2 installed locally.

Inbound aliases (configure in Cloudflare Email Routing → Send to Worker):
  bills.property@$DOMAIN      → matariki-property-group
  bills.traders@$DOMAIN       → matariki-traders
  bills.morningside@$DOMAIN   → matariki-morningside-development

Local webhook:  http://127.0.0.1:$PORT/health
Webhook secret: see $CONFIG_DIR/inbound.json (field webhook_secret)

Expose webhook to the internet (choose one):
  tailscale funnel --bg $PORT
  # then set WEBHOOK_URL in cloudflare/wrangler.toml to your funnel HTTPS URL

Deploy Cloudflare Email Worker:
  cd $REPO_ROOT/cloudflare
  # Edit wrangler.toml: WEBHOOK_URL + WEBHOOK_SECRET
  npx wrangler deploy

Test without email:
  python -m xero_mcp inbound test \\
    --to bills.morningside@$DOMAIN \\
    --pdf /path/to/test-invoice.pdf

Reload Cursor MCP servers (xero-inbound added).

EOF

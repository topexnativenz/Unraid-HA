#!/bin/bash
# Deploy xero-inbound Email Worker + secrets on tower only (no Mac wrangler).
set -euo pipefail

CF_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-6b75f8187544327aba3ac88047b7fb92}"
TOKEN_FILE="${CLOUDFLARE_TOKEN_FILE:-/mnt/user/appdata/claude-agent/data/.cloudflare_api_token}"
INBOUND_CONFIG="${XERO_INBOUND_CONFIG:-/mnt/user/appdata/xero-inbound/config/inbound.json}"
SRC_DIR="${XERO_CF_SRC:-/mnt/user/appdata/xero-inbound/cloudflare}"

normalize_token() {
  docker run --rm -v "$(dirname "$TOKEN_FILE"):/data" node:20-slim node -e "
const fs=require('fs');
const p='/data/$(basename "$TOKEN_FILE")';
const raw=fs.readFileSync(p,'utf8').trim();
const i=raw.indexOf('cfut_',5);
const fixed=(i>0?raw.slice(0,i):raw).trim();
if(fixed.length!==raw.length) fs.writeFileSync(p,fixed);
"
}

deploy_worker() {
  if [[ ! -f "$INBOUND_CONFIG" || ! -d "$SRC_DIR" ]]; then
    echo "Missing $INBOUND_CONFIG or $SRC_DIR" >&2
    exit 1
  fi
  local secret_file="/tmp/xero-webhook-secret.$$"
  grep -m1 webhook_secret "$INBOUND_CONFIG" | sed 's/.*: *"\([^"]*\)".*/\1/' > "$secret_file"
  chmod 600 "$secret_file"

  export CLOUDFLARE_API_TOKEN="$(tr -d '\n\r' < "$TOKEN_FILE")"
  export CLOUDFLARE_ACCOUNT_ID="$CF_ACCOUNT_ID"
  cd "$SRC_DIR"
  docker run --rm \
    -v "$(pwd):/app" -w /app \
    -v "${secret_file}:/run/secrets/webhook_secret:ro" \
    -e CLOUDFLARE_API_TOKEN \
    -e CLOUDFLARE_ACCOUNT_ID \
    node:20-slim bash -c '
      npm install -g wrangler@4 >/dev/null 2>&1
      npm install --omit=dev 2>/dev/null || npm install
      wrangler secret put WEBHOOK_SECRET < /run/secrets/webhook_secret
      wrangler deploy
    '
  rm -f "$secret_file"
}

normalize_token
echo "==> Deploy Worker from tower (account ${CF_ACCOUNT_ID})"
deploy_worker
echo "Done."

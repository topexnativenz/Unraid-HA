#!/bin/bash
# Wire Cloudflare from Mac: sync files to tower, then tower runs wrangler + Email Routing (no Mac wrangler).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CF_DIR="${REPO_ROOT}/cloudflare"
TOWER_SWAG_SRC="/Users/topexnative/Projects/unraid-array-design/tower/boot/config/swag/xero-inbound.subdomain.conf"
TOWER_SWAG_DEST="/mnt/user/appdata/swag/nginx/proxy-confs/xero-inbound.subdomain.conf"
TOWER_CF_DEST="/mnt/user/appdata/xero-inbound/cloudflare"
WEBHOOK_HOST="${XERO_WEBHOOK_HOST:-xero-inbound.gillespie.kiwi}"

SSH=(ssh -o ConnectTimeout=15 -o IdentitiesOnly=yes tower)
SCP=(scp -o ConnectTimeout=15 -o IdentitiesOnly=yes)

echo "==> SWAG proxy (${WEBHOOK_HOST} → tower :8766)"
"${SSH[@]}" "mkdir -p /mnt/user/appdata/swag/nginx/proxy-confs ${TOWER_CF_DEST}"
"${SCP[@]}" "${TOWER_SWAG_SRC}" "tower:${TOWER_SWAG_DEST}"
"${SCP[@]}" "${CF_DIR}/worker.js" "${CF_DIR}/wrangler.toml" "${CF_DIR}/package.json" \
  "${CF_DIR}/setup-email-routing.mjs" "${CF_DIR}/restore-native-google-inboxes.mjs" \
  "${CF_DIR}/restore-gillespie-inbox-routing.mjs" "${CF_DIR}/query-email-routing-rules.mjs" \
  "${CF_DIR}/fix-xero-inbound-public-dns.mjs" "${CF_DIR}/fix-matariki-forward-rules.mjs" \
  "tower:${TOWER_CF_DEST}/"
"${SCP[@]}" /Users/topexnative/Projects/unraid-array-design/tower/scripts/deploy-cloudflare-xero-inbound.sh \
  "tower:/mnt/user/appdata/xero-inbound/deploy-cloudflare-xero-inbound.sh"
"${SSH[@]}" "chmod +x /mnt/user/appdata/xero-inbound/deploy-cloudflare-xero-inbound.sh"

echo "==> Public DNS + tunnel route (${WEBHOOK_HOST} must not resolve to 192.168.1.7)"
"${SSH[@]}" bash -s <<'REMOTE'
set -euo pipefail
export CLOUDFLARE_API_TOKEN="$(tr -d '\n\r' < /mnt/user/appdata/claude-agent/data/.cloudflare_api_token)"
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/fix-xero-inbound-public-dns.mjs:/app/fix.mjs \
  -e CLOUDFLARE_API_TOKEN node:20-slim node /app/fix.mjs || true
REMOTE

echo "==> Deploy Worker + WEBHOOK_SECRET on tower (wrangler 4, no Mac)"
"${SSH[@]}" "bash /mnt/user/appdata/xero-inbound/deploy-cloudflare-xero-inbound.sh"

echo "==> Email Routing rules (tower API)"
"${SSH[@]}" bash -s <<'REMOTE'
set -euo pipefail
export CLOUDFLARE_API_TOKEN="$(tr -d '\n\r' < /mnt/user/appdata/claude-agent/data/.cloudflare_api_token)"
export CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN%cfut_}"
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/setup-email-routing.mjs:/app/setup.mjs \
  -e CLOUDFLARE_API_TOKEN node:20-slim node /app/setup.mjs
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/query-email-routing-rules.mjs:/app/q.mjs \
  -e CLOUDFLARE_API_TOKEN node:20-slim node /app/q.mjs || true
REMOTE

echo "==> Verify public webhook"
sleep 2
curl -sf "https://${WEBHOOK_HOST}/health" | grep -q '"ok"' && echo "Health OK: https://${WEBHOOK_HOST}/health"

cat <<EOF

Tower-only Cloudflare path is configured.

  Worker deploy:  ssh tower 'bash /mnt/user/appdata/xero-inbound/deploy-cloudflare-xero-inbound.sh'
  Full setup:     bash ${REPO_ROOT}/scripts/setup-cloudflare-xero-inbound.sh

Personal mail: matarikigroup forwards to verified @gillespie.kiwi (NEVER same-domain loop).
  gillespie.kiwi: routing OFF (native Google MX).

  ssh tower 'TOKEN=$(tr -d "\n\r" < /mnt/user/appdata/claude-agent/data/.cloudflare_api_token); TOKEN="${TOKEN%cfut_}"
  docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/setup-email-routing.mjs:/app/setup.mjs \
    -e CLOUDFLARE_API_TOKEN="$TOKEN" node:20-slim node /app/setup.mjs'

Revert to native Google everywhere (routing off both zones):

  ssh tower 'TOKEN=$(tr -d "\n\r" < /mnt/user/appdata/claude-agent/data/.cloudflare_api_token); TOKEN="${TOKEN%cfut_}"
  docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/restore-native-google-inboxes.mjs:/app/r.mjs \
    -e CLOUDFLARE_API_TOKEN="$TOKEN" node:20-slim node /app/r.mjs'

EOF

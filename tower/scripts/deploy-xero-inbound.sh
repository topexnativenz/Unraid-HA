#!/bin/bash
# Deploy Xero inbound webhook (portfolio routing) to Unraid tower — Mac-independent runtime.
set -euo pipefail

REPO_ROOT="/Users/topexnative/Projects/unraid-array-design"
XERO_SRC="${REPO_ROOT}/tools/xero-mcp"
MAC_CONFIG="/Users/topexnative/.config/xero-mcp"
TOWER_APPDATA="/mnt/user/appdata/xero-inbound"
TOWER_CONFIG="${TOWER_APPDATA}/config"
CONTAINER_NAME="xero-inbound"
IMAGE_TAG="xero-inbound:local"

SSH=(ssh -o ConnectTimeout=15 -o IdentitiesOnly=yes tower)

echo "Tower connectivity:"
"${REPO_ROOT}/tower/scripts/tower-resolve-host.sh" --json

"${SSH[@]}" "mkdir -p ${TOWER_CONFIG}/inbound/queue ${TOWER_CONFIG}/inbound/attachments"
chmod_cmd='chmod 700 '"${TOWER_CONFIG}"' '"${TOWER_CONFIG}"'/inbound; find '"${TOWER_CONFIG}"' -type f -exec chmod 600 {} + 2>/dev/null || true'
"${SSH[@]}" "${chmod_cmd}"

if [[ ! -f "${MAC_CONFIG}/credentials.json" || ! -f "${MAC_CONFIG}/connections.json" ]]; then
  echo "Missing Mac OAuth config. Run setup-phase0.sh first." >&2
  exit 1
fi

VENV_PY="${XERO_SRC}/.venv/bin/python"
if [[ ! -x "${VENV_PY}" ]]; then
  echo "Missing venv at ${XERO_SRC}/.venv" >&2
  exit 1
fi

SECRET="$("${VENV_PY}" -c "
from xero_mcp.keychain import load_client_secret
print(load_client_secret())
" 2>/dev/null || true)"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

python3 <<PY
import json
from pathlib import Path

mac = Path("${MAC_CONFIG}")
tmp = Path("${TMP_DIR}")
example = json.loads(Path("${XERO_SRC}/xero.inbound.example.json").read_text())
data = dict(example)

inbound_path = mac / "inbound.json"
if inbound_path.exists():
    data.update(json.loads(inbound_path.read_text()))

# Mac inbound.json may omit office formats — always allow bill attachment types
_bill_exts = [".pdf", ".jpg", ".jpeg", ".png", ".heic", ".doc", ".docx", ".xls", ".xlsx"]
data["allowed_extensions"] = list(
    dict.fromkeys((data.get("allowed_extensions") or []) + _bill_exts)
)

data["routing_mode"] = "portfolio"
if not data.get("intake_addresses"):
    data["intake_addresses"] = example["intake_addresses"]
if not data.get("allowed_from"):
    data["allowed_from"] = example["allowed_from"]
if not data.get("default_intake_address"):
    data["default_intake_address"] = example["default_intake_address"]
data["routes"] = data.get("routes") or []
(tmp / "inbound.json").write_text(json.dumps(data, indent=2) + "\n")

creds = json.loads((mac / "credentials.json").read_text())
creds["secret_storage"] = "file"
secret = """${SECRET}""".strip()
if secret:
    creds["client_secret"] = secret
(tmp / "credentials.json").write_text(json.dumps(creds, indent=2) + "\n")

for name in ("connections.json", "orgs.json", "orgs.config.json", "active-org.json"):
    src = mac / name
    if src.exists():
        (tmp / name).write_text(src.read_text())

portfolio = mac / "portfolio.entities.json"
if portfolio.exists():
    (tmp / "portfolio.entities.json").write_text(portfolio.read_text())
else:
    (tmp / "portfolio.entities.json").write_text(
        Path("${XERO_SRC}/portfolio.entities.example.json").read_text()
    )
PY

scp -o ConnectTimeout=15 -o IdentitiesOnly=yes \
  "${TMP_DIR}/"* \
  "tower:${TOWER_CONFIG}/"

echo "Syncing xero-mcp source to tower (for docker build)..."
tar -C "${XERO_SRC}" --exclude .venv --exclude node_modules --exclude __pycache__ -czf "${TMP_DIR}/xero-mcp.tgz" .
scp -o ConnectTimeout=15 -o IdentitiesOnly=yes "${TMP_DIR}/xero-mcp.tgz" "tower:/tmp/xero-mcp.tgz"

"${SSH[@]}" bash -s <<'REMOTE'
set -euo pipefail
APPDATA="/mnt/user/appdata/xero-inbound"
SRC="${APPDATA}/src"
rm -rf "${SRC}"
mkdir -p "${SRC}"
tar -xzf /tmp/xero-mcp.tgz -C "${SRC}"
cd "${SRC}"
docker build -f docker/Dockerfile -t xero-inbound:local .
docker rm -f xero-inbound 2>/dev/null || true
docker run -d \
  --name xero-inbound \
  --restart unless-stopped \
  -p 8766:8766 \
  -v "${APPDATA}/config:/config:rw" \
  -e XERO_MCP_CONFIG_DIR=/config \
  -e WEBHOOK_PORT=8766 \
  xero-inbound:local
sleep 2
curl -sf http://127.0.0.1:8766/health
docker exec xero-inbound python -m xero_mcp sync-orgs >/dev/null
# Drop stale active-org if it points at an excluded tenant (e.g. MPG Cancelled)
docker exec xero-inbound python - <<'PY'
import json
from pathlib import Path
from xero_mcp.tenants import get_active_organisation, list_organisations

active = get_active_organisation()
if not active:
    raise SystemExit(0)
known = {o.tenant_id for o in list_organisations()}
if active.tenant_id not in known:
    Path("/config/active-org.json").unlink(missing_ok=True)
PY
REMOTE

echo ""
echo "Deployed ${CONTAINER_NAME} on tower :8766"
echo "Config: ${TOWER_CONFIG}"
echo "Health: ssh tower 'curl -s http://127.0.0.1:8766/health'"
echo ""
echo "Cloudflare (tower wrangler): bash ${REPO_ROOT}/tools/xero-mcp/scripts/setup-cloudflare-xero-inbound.sh"
echo "Auto-heal cron (optional): */30 * * * * docker exec ${CONTAINER_NAME} python -m xero_mcp inbound heal --limit 10"
echo "Heal from Mac: bash ${REPO_ROOT}/tower/scripts/xero-inbound-heal.sh"
echo "See ${REPO_ROOT}/docs/xero-inbound-tower.md"

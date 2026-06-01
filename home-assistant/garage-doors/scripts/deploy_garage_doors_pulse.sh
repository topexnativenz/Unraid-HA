#!/bin/bash
# Copy garage_doors_pulse.yaml to HA and sync tracked open state from Shelly switches.
set -euo pipefail

REPO="/Users/topexnative/Projects/unraid-array-design"
PKG_SRC="${REPO}/home-assistant/garage-doors/packages/garage_doors_pulse.yaml"
HA_HOST="${HA_HOST:-192.168.1.239}"
MOUNT="${HA_CONFIG_MOUNT:-/tmp/ha-config-smb}"
PKG_DEST="${MOUNT}/packages/garage_doors_pulse.yaml"

TOKEN=$(python3 -c "import json;from pathlib import Path;d=json.loads(Path('/Users/topexnative/.cursor/mcp.json').read_text());print(d['mcpServers']['homeassistant']['headers']['Authorization'].split(' ',1)[1])")

get_samba() {
  python3 <<PY
import asyncio, json
from pathlib import Path
import websockets

token = "$TOKEN"
ha = "http://${HA_HOST}:8123"

async def main():
    ws_url = ha.replace("http://", "ws://") + "/api/websocket"
    async with websockets.connect(ws_url) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()
        await ws.send(json.dumps({
            "type": "supervisor/api",
            "endpoint": "/addons/core_samba/info",
            "method": "get",
            "id": 1,
        }))
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == 1:
                o = r["result"]["options"]
                print(o["username"], o["password"])
                break
asyncio.run(main())
PY
}

read -r SMB_USER SMB_PASS < <(get_samba)
mkdir -p "${MOUNT}"
diskutil umount "${MOUNT}" 2>/dev/null || true
mount_smbfs "//${SMB_USER}:${SMB_PASS}@${HA_HOST}/config" "${MOUNT}"

mkdir -p "$(dirname "${PKG_DEST}")"
cp "${PKG_SRC}" "${PKG_DEST}"
echo "Copied package to ${PKG_DEST}"

diskutil umount "${MOUNT}" 2>/dev/null || true

echo "Reloading scripts and input_boolean..."
curl -sS -X POST -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "http://${HA_HOST}:8123/api/services/script/reload" >/dev/null
curl -sS -X POST -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "http://${HA_HOST}:8123/api/services/input_boolean/reload" >/dev/null

sleep 2

sync_bool() {
  local bool_entity="$1"
  local switch_entity="$2"
  local want
  want=$(curl -sS -H "Authorization: Bearer ${TOKEN}" "http://${HA_HOST}:8123/api/states/${switch_entity}" \
    | python3 -c "import json,sys; print('on' if json.load(sys.stdin)['state']=='on' else 'off')")
  svc="input_boolean.turn_${want}"
  curl -sS -X POST -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    "http://${HA_HOST}:8123/api/services/${svc}" \
    -d "{\"entity_id\":\"${bool_entity}\"}" >/dev/null
  echo "  ${bool_entity} -> ${want} (from ${switch_entity})"
}

echo "Syncing tracked state from Shelly switches (one-time alignment):"
sync_bool input_boolean.house_garage_door_open switch.garage_door_3
sync_bool input_boolean.main_shed_door_open switch.garage_door_1
sync_bool input_boolean.second_shed_door_open switch.garage_door_2

echo "Done. If helpers are new, restart HA or reload all YAML once."

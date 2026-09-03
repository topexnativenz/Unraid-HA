# Home Assistant scripts — diagnostics and shared client

Cloud Agents and CI cannot reach `192.168.1.239` on your LAN. Configure **environment secrets** in Cursor (Settings → Cloud Agents → Environment):

| Secret | Value |
|--------|--------|
| `HA_URL` | Nabu Casa Remote UI URL, e.g. `https://xxxx.ui.nabu.casa` |
| `HA_TOKEN` | Long-lived access token from HA → Profile → Security |

On your Mac, scripts also read `~/.cursor/mcp.json` (homeassistant MCP Authorization header). The MCP `url` is often `…/mcp_server/sse` — the client automatically strips that to the HA origin (`http://192.168.1.239:8123` or your Nabu Casa host). For LAN-only URLs, use the Mac terminal; cloud agents need Nabu Casa.

## Verify connectivity

```bash
pip install -r home-assistant/scripts/requirements.txt
python3 home-assistant/scripts/fetch_ha_diagnostics.py --verify
```

Expected output includes `rest_ok`, `websocket_ok`, `traces_ok`, `logbook_ok`, `system_log_ok`, and `error_log_ok` all true.

## Fetch traces, logbook, history, and logs (arrival debugging)

```bash
python3 home-assistant/scripts/fetch_ha_diagnostics.py --hours 24 --topic arrival
python3 home-assistant/scripts/fetch_ha_diagnostics.py --automation gate_open_on_arrival_model_x
python3 home-assistant/scripts/fetch_ha_diagnostics.py --json --hours 6 --topic arrival
```

Pulls:

- Entity states (gate/garage/Tessie sensors)
- Automation `last_triggered`
- **Automation & script traces** via WebSocket (`trace/list` + `trace/get`, with entity-registry unique_id resolution)
- **Logbook** entries (REST)
- **History** state changes (REST)
- **System log** errors/warnings (`system_log/list` via WebSocket)
- **Error log** tail (`/api/error_log` via REST)

Garage-specific wrapper (same backend):

```bash
python3 home-assistant/garage-doors/scripts/diagnose_arrival.py
python3 home-assistant/garage-doors/scripts/diagnose_arrival.py --hours 24
```

## Why traces failed before

Cloud Agent VMs have no access to your LAN and no credentials unless you configure them. Without `HA_URL` + `HA_TOKEN` in the environment, scripts cannot authenticate or reach Home Assistant. Use your **Nabu Casa** URL, not `192.168.1.239`.

## Shared module

Other deploy scripts can import from `home-assistant/scripts` (add that directory to `sys.path`):

```python
from ha_client import resolve_ha_config, get_state, verify_connection, list_traces
```

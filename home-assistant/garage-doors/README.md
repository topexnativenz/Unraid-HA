# Garage doors (Shelly) — House Garage unavailable

## Mobile Home pulse scripts (momentary Shelly)

Shelly relays are **momentary** — do not use `switch.toggle` on the dashboard (first press only flips HA state). Use:

| Button | Tracked state | Script |
|--------|---------------|--------|
| House Garage | `input_boolean.house_garage_door_open` | `script.pulse_house_garage_door` |
| Main Shed | `input_boolean.main_shed_door_open` | `script.pulse_main_shed_door` |
| Second Shed | `input_boolean.second_shed_door_open` | `script.pulse_second_shed_door` |

Package: `packages/garage_doors_pulse.yaml` — deploy:

```bash
bash /Users/topexnative/Projects/unraid-array-design/home-assistant/garage-doors/scripts/deploy_garage_doors_pulse.sh
```

Red = open (boolean on), grey = closed. Each tap runs the pulse script: if the Shelly switch is already `on`, `turn_off` then `turn_on` so the relay always fires; then toggles the boolean.

## Entity map (Mobile Home → Garage & Doors)

| Dashboard label | Entity | Hardware |
|-----------------|--------|----------|
| Main Garage | `cover.garage_door` | Main door (cover integration) |
| House Garage | `switch.garage_door_3` | Shelly Plus 1 `shellyplus1-d4d4daf3cabc` (MAC `d4:d4:da:f3:ca:bc`) |
| Main Shed | `switch.garage_door_1` | Shelly 1G3 `192.168.1.94` |
| Second Shed | `switch.garage_door_2` | Shelly 1G3 `192.168.1.95` |

## Root cause (2026-05-24)

`switch.garage_door_3` shows **unavailable** because the **Shelly Plus 1 for the house garage is not on the LAN**:

- HA integration `shellyplus1-d4d4daf3cabc` → `setup_retry` / device communication error
- ARP scan: `.94` and `.95` respond; **no ARP entry for `d4:d4:da:f3:ca:bc`**
- Shed Shelly devices load and work (`switch.garage_door_1` / `_2` → `off`)

`input_button.house_garage_door` is a separate helper; pressing it does **not** drive the Shelly relay.

## Fix on site

**Step-by-step Wi‑Fi / Bluetooth / AP setup:** [shelly-plus-wifi-reset.md](shelly-plus-wifi-reset.md)

1. At the **house garage Shelly Plus 1**: check power, Wi‑Fi, and that it joins `192.168.1.x`.
2. When the device is back, in HA: **Settings → Devices & Services → Shelly** → `shellyplus1-d4d4daf3cabc` → **Reload** (or disable/enable integration).
3. Confirm entity: **Developer Tools → States** → `switch.garage_door_3` should be `on`/`off`, not `unavailable`.
4. Test from **Garage & Doors** on Mobile Home (card uses `switch.garage_door_3`).

## Verify from Mac (when on home LAN)

```bash
# Shelly Plus should answer RPC when online
curl -sS -X POST http://<SHELLY_IP>/rpc/Shelly.GetDeviceInfo -d '{}'

# HA entity state
TOKEN=$(python3 -c "import json;from pathlib import Path;d=json.loads(Path('/Users/topexnative/.cursor/mcp.json').read_text());print(d['mcpServers']['homeassistant']['headers']['Authorization'].split(' ',1)[1])")
curl -sS -H "Authorization: Bearer $TOKEN" http://192.168.1.239:8123/api/states/switch.garage_door_3
```

## HA actions already taken

- Reloaded all three Shelly config entries via API
- Shed integrations → `loaded`; House Garage Shelly Plus remains unreachable until hardware is back

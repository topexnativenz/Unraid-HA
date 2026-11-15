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

## 2026-11-16 — House Garage closing on a reversing Tesla (fixed)

**Cause:** the House Garage is a momentary Shelly relay (`switch.garage_door_3`) — every pulse TOGGLES the door.
`script.house_garage_open_if_closed` (package, on HA) was written to *fail open*: if every contact sensor was
unavailable it pulsed anyway. The Tapo H200 hub (192.168.1.58, MAC 18:69:45:66:32:67) dropped off the LAN at
14:37 NZDT 14 Nov, so `binary_sensor.house_garage_door_sensor_door` went `unavailable` and every Tesla shift out of
Park (and every Tessie "approach") pulsed the relay blind. If the door was already open, that pulse closed it —
e.g. 16 Nov 08:36 NZDT Model X shifted to R → pulse; 08:37 the approach automation fired as the X left → pulse again.

**Fix (live via HA config API, exported in `ui-config/`):**
- New `script.house_garage_open_safe` — pulses ONLY when the Tapo contact is `off` (closed) with signal > 0 and no
  pulse in the last 90 s; otherwise does nothing and notifies `mobile_app_halo`. Never closes / blind-toggles.
- `House Garage — open when Tesla departure starts` → uses the safe script (re-enabled).
- `Gate — open when Tesla leaves park at home` → garage step removed (duplicate) (re-enabled).
- Gate arrival (Model S, Model X) → garage step uses the safe script.
- Left OFF pending David: `House Garage — open on Tessie approach (S or X)` (fired during a departure),
  `House Garage — open when gate arrival session starts` (duplicate), `House Garage — close when last Tesla is away`.
- `script.house_garage_open_if_closed` is no longer called by anything; its package YAML still has the fail-open
  fallback and should be changed/removed when the HA config share is next edited.
- Until the Tapo hub is back online, the garage will NOT auto-open (by design). Dashboard tap still pulses.

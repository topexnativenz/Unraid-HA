# Garage doors — Main Garage (Tapo sensor + Shelly) + shed pulses

LAN Home Assistant: **http://192.168.1.239:8123** · timezone **Pacific/Auckland**

## Entity map

| Role | Entity | Hardware / integration |
|------|--------|------------------------|
| Main Garage cover | `cover.garage_door` | Template cover (package) |
| Main Garage contact sensor | `binary_sensor.garage_door_sensor_open` | Tapo T110 via **Tuya** (cloud); `off` = closed |
| Tapo H200 hub | `sensor.tapo_h200_signal_level` (+ `switch.tapo_h200_led`, etc.) | **TP-Link Smart Home** (local) |
| House Garage contact sensor | `binary_sensor.house_garage_door_sensor_door` | Tapo T110 via **H200** / TP-Link |
| Opener relay pulse | `switch.garage_door_1` | Shelly 1G3 `192.168.1.94` |
| Model S — gate approach | `binary_sensor.model_s_tessie_in_gate_approach` | Tessie (gate package) |
| Model S — distance home | `sensor.model_s_tessie_distance_to_home` | Tessie |
| Model S — shift state | `sensor.model_s_p100d_shift_state` | Tessie (`p`/`d`/`r`/`n`) |
| Model S — speed | `sensor.model_s_p100d_speed` | Tessie |
| Model S — was away flag | `input_boolean.model_s_was_away` | Gate package |
| Model X — gate approach | `binary_sensor.model_x_tessie_in_gate_approach` | Tessie (gate package) |
| Model X — distance home | `sensor.model_x_tessie_distance_to_home` | Tessie |
| Model X — shift state | `sensor.x_shift_state` | Tessie |
| Model X — speed | `sensor.x_speed` | Tessie |
| Model X — was away flag | `input_boolean.model_x_was_away` | Gate package |
| Garage camera — person | `binary_sensor.garage_door_person_detected` | Tapo camera (9 PM safety skip) |
| House Garage (separate) | `switch.garage_door_3` / `input_boolean.house_garage_door_open` | Shelly Plus 1 — see [shelly-plus-wifi-reset.md](shelly-plus-wifi-reset.md) |
| Outside garage lights | `light.outside_garage` | C-Bus exterior by House Garage |
| Arrival outside-lights session | `input_boolean.garage_outside_lights_arrival_active` | Set when outside lights turned on for night arrival |
| Main Shed | `switch.garage_door_1` | Shelly 1G3 `192.168.1.94` (same relay as Main Garage opener) |
| Second Shed | `switch.garage_door_2` | Shelly 1G3 `192.168.1.95` |

**Contact sensor polarity (confirmed on site):** `off` = door closed, `on` = door open. The template cover maps sensor `on` → cover **open** (HA template covers use `true` = open).

## Automations (repo-managed)

| ID | Alias | Behaviour |
|----|-------|-----------|
| `garage_outside_lights_on_tessie_arrival_after_dark` | Garage outside lights — on Tessie arrival after dark | After sunset; turns on `light.outside_garage` on Model S/X approach |
| `garage_outside_lights_off_house_garage_closed` | Garage outside lights — off when House Garage closes | When `binary_sensor.house_garage_door_sensor_door` closes after an arrival session |
| `house_garage_open_on_tessie_arrival` | House Garage — open and light on Tessie arrival (Model S or X) | Gate approach or \<90 m from home; opens House Garage if contact sensor closed; turns on `light.garage` if off |
| `garage_close_at_9pm` | Garage — close Main Garage at 9 PM | Daily **21:00**; only if door open **and** Tapo camera reports **no person** in garage |

Car-triggered **Main Garage** open (Tessie shift) was removed — use `cover.garage_door` manually. **House Garage** (separate door, Shelly) uses Tessie arrival above.

Gate automations are unchanged ([gate README](../gate/README.md)).

## Tapo integrations (H200 hub + T110 sensors)

Two integrations are active:

| Integration | Devices | Path |
|-------------|---------|------|
| **Tuya** (cloud) | Main Garage T110 | `binary_sensor.main_garage_door_sensor_door` — used by cover + automations |
| **TP-Link Smart Home** (local) | Tapo H200 hub, House Garage T110 | `binary_sensor.house_garage_door_sensor_door`, `sensor.tapo_h200_signal_level`, etc. |

Main Garage automations use the **Tuya** sensor only. House Garage is a separate door (Shelly opener + H200 sensor).

### First-time setup (T110 / door sensor)

1. **Tapo app:** add the contact sensor to your Tapo account; mount on the Main Garage door frame; confirm open/closed states in the app.
2. **Same LAN:** sensor must be on `192.168.1.x` Wi‑Fi (2.4 GHz).
3. **Home Assistant → Settings → Devices & services → Add integration:**
   - Try **Tuya** first (matches current entity `platform: tuya`), **or**
   - **TP-Link Tapo** if your HA version exposes the door sensor there.
4. Sign in with the **same account** used in the Tapo app; wait for discovery.
5. Rename the device to **Main Garage Door Sensor** (Area: **Garage**) so the entity stays `binary_sensor.main_garage_door_sensor_door`.
6. **Developer tools → States** — toggle the door manually and confirm:
   - Closed → `binary_sensor.main_garage_door_sensor_door` = `off`
   - Open → `on`
7. If polarity is reversed, flip the magnet mount or invert in a template (do **not** change the package without updating `main_garage_cover.yaml`).

### Re-pair / entity rename

If HA creates a different entity ID after re-pairing, update:

- `packages/main_garage_cover.yaml` → `value_template` entity
- `automations/garage.yaml` → contact sensor conditions

Then redeploy (below).

## Packages

| File | Role |
|------|------|
| `main_garage_cover.yaml` | Template `cover.garage_door` (sensor + Shelly pulse) |
| `garage_doors_pulse.yaml` | House Garage + shed momentary pulse scripts |
| `automations/garage.yaml` | Automations block merged into `/config/automations.yaml` |

## Deploy

```bash
bash /Users/topexnative/Projects/unraid-array-design/home-assistant/garage-doors/scripts/deploy_garage_doors.sh
```

The deploy script:

1. Copies packages to HA via Samba
2. Moves the inline `cover:` block out of `configuration.yaml` into `packages/main_garage_cover.yaml`
3. Merges garage automations (replaces legacy UI **Auto Close Garage 9PM**)
4. Runs `check_config` and reloads core / automations / scripts

Pulse-only deploy (no automations / cover):

```bash
bash /Users/topexnative/Projects/unraid-array-design/home-assistant/garage-doors/scripts/deploy_garage_doors_pulse.sh
```

If Samba credentials are needed:

```bash
export HA_SAMBA_PASSWORD='…'   # HA → Settings → Add-ons → Samba share
```

## Verify

```bash
TOKEN=$(python3 -c "import json;from pathlib import Path;d=json.loads(Path('/Users/topexnative/.cursor/mcp.json').read_text());print(d['mcpServers']['homeassistant']['headers']['Authorization'].split(' ',1)[1])")

curl -sS -H "Authorization: Bearer $TOKEN" http://192.168.1.239:8123/api/states/cover.garage_door
curl -sS -H "Authorization: Bearer $TOKEN" http://192.168.1.239:8123/api/states/binary_sensor.main_garage_door_sensor_door
curl -sS -H "Authorization: Bearer $TOKEN" http://192.168.1.239:8123/api/states/automation.garage_close_main_garage_at_9_pm
```

**Settings → Automations** — only the 9 PM close automation should remain for garage.

## House Garage Shelly unavailable

See [shelly-plus-wifi-reset.md](shelly-plus-wifi-reset.md). `switch.garage_door_3` offline does **not** affect Main Garage (`cover.garage_door` / `switch.garage_door_1`).

## HA actions already taken (live instance)

- Tapo/Tuya contact sensor paired → `binary_sensor.main_garage_door_sensor_door`
- Template cover in `configuration.yaml` (migrated to package on first repo deploy)
- Legacy UI automation **Auto Close Garage 9PM** (replaced by repo `garage_close_at_9pm` on deploy)

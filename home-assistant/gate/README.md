# Gate intercom (Akuvox / Akubela community)

Deploy to Home Assistant at `http://192.168.1.239:8123`.

## Root cause (fixed)

The old `configuration.yaml` gate block used **HTTP** and the legacy `/fcgi/do?...&UserName=...&Password=...` URL. The door phone at `192.168.1.73` requires **HTTPS + HTTP Digest auth** via `/fcgi/OpenDoor?action=OpenDoor&DoorNum=N`.

## Entities (after deploy)

| Entity | Purpose |
|--------|---------|
| `button.gate_open` | Pulse relay 1 (primary gate test) |
| `button.gate_open_relay_2` | Pulse relay 2 (secondary test) |
| `input_datetime.gate_last_open` | Last open attempt timestamp |
| `input_select.gate_last_relay` | Which relay was last triggered |

Services: `shell_command.akuvox_gate_open_relay_1` / `_relay_2`

Lovelace (**Mobile Home** Quick Actions): gate controls use `custom:mushroom-lock-card` with friendly **Locked** / **Unlocked** labels. Reference: `home-assistant/gate/lovelace/gate_cards.yaml`.

## Automations (`automations/gate.yaml` → `/config/automations.yaml`)

| Automation | Trigger | Notes |
|------------|---------|-------|
| **Gate — open on approach from outside** | `person.dave` goes `not_home` → `Gate Approach` | Zone centred on road end of driveway (200 m radius); hold until clear |
| **Gate — open when Model S leaves park at home** | Shift p→d/r, speed > 0.5 km/h, or driver door opens | Wakes Tessie; holds gate open until car clears (passengers/delays OK) |

**Gate hold:** the Akuvox relay auto-closes after ~5 s. `script.gate_open_with_hold` re-pulses every 4 s while `binary_sensor.gate_still_needs_hold` is on (only when `input_boolean.gate_hold_active` is on). Hold continues during active departure (Drive/Reverse, moving, doors open) or while in the approach zone — **not** while the car is simply parked at home in Park. Stops when clear or after 8 min max.

**Emergency close:** turn off `input_boolean.gate_hold_active`, stop `script.gate_open_with_hold`, then `lock.lock` on both gate lock entities.

Tune hold timing: `input_number.gate_hold_repulse_seconds`, `input_number.gate_hold_max_minutes`.

**Tessie:** API key and wake URL live in `/config/secrets.yaml` (`tessie_api_key_header`, `tessie_wake_model_s_url`). Do not commit secrets to git.
| **Gate — mark exit in progress** | `person.dave` leaves `zone.home` | Prevents false open when driving out |

Entity IDs: `automation.gate_open_on_approach_from_outside_100_m`, `automation.gate_open_when_model_s_leaves_park_at_home`, `automation.gate_mark_exit_in_progress_when_leaving_home`.

Tune gate position in `/config/secrets.yaml` (quotes required on negative latitude):

```yaml
gate_latitude: "-35.69110"      # road end of driveway — drag zone on HA map to refine
gate_longitude: "174.2669872"
gate_approach_radius: 200       # metres; increase if GPS triggers too late
```

The **Gate Approach** zone is centred on those coordinates with the configured radius (`packages/gate_automations.yaml`).

**Approach logic:** triggers only on `not_home` → `Gate Approach` (removed the `home` backup — it opened the gate too close to the intercom). Leaving (`home` → `Gate Approach`) does not match.

**Tesla logic:** Tessie often sleeps and does not report shift/speed changes. The script wakes the car via Tessie REST + HA button, waits up to 15 s for Drive/Reverse or movement, then runs `gate_open_with_hold`.

**Exit flag:** `input_boolean.gate_exit_in_progress` is set when leaving home (for visibility) and cleared when an arrival automation opens the gate.

## Deploy

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/gate/scripts/deploy_gate_to_ha.py --gate-password 'YOUR_PASSWORD'
```

Secrets on HA (`/config/secrets.yaml`) must define `akuvox_gate_curl_relay_1` and `_relay_2` as full curl commands (see deployed example). Use **single-quoted** YAML scalars for passwords containing `!!`.

## Local Akuvox (recommended next step)

Custom component is copied to `/config/custom_components/local_akuvox`. Add via HA UI:

**Settings → Devices & Services → Add Integration → Local Akuvox**

| Setting | Value |
|---------|-------|
| Host | `192.168.1.73` |
| SSL | On |
| Verify SSL | Off |
| Auth | Digest |
| Username | `admin` |
| Password | (from secrets) |
| Webhooks | On |

This creates `lock.*` entities and pushes relay events to HA (`local_akuvox_webhook_received`).

## Relay mapping (TBD on site)

Both **DoorNum=1** and **DoorNum=2** return `{"retcode":0,"message":"OK"}` from the API. Test each button and see which one actually moves the swing gate.

## Door phone

- IP: `192.168.1.73` (MAC `0c:11:05:32:20:7b`)
- RTSP: port `554`
- HyPanel IP: not found on LAN scan (may be Wi‑Fi / sleeping); HTTP API whitelist already includes HA (`192.168.1.239`) and tower (`192.168.1.7`).

## BelaHome

No native HA integration. BelaHome / SmartPlus cloud (`custom_components/akuvox`) is optional for remote control; local control is preferred.

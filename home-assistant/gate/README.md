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

Live Home Assistant uses **Tessie for Model X** and the same approach/departure shape for Model S, mapped onto sensors that actually update.

| Automation | Trigger | Notes |
|------------|---------|-------|
| **Gate — open on Tessie arrival (Model X)** | Tessie road/gate after `model_x_was_away` | Working template. GPS is live. |
| **Gate — open on Tessie arrival (Model S)** | Phone enters Road/Gate Approach from anywhere except home, or jumps straight to home while `model_s_was_away` and someone is in the S | Model S Tessie GPS stays ~50 m home. Also opens House Garage. Relay runs before the Tessie wake. |
| **Gate — open when Tesla leaves park at home** | Model X shift P→D/R; Model S phone leaving home while someone is in the S. Driver door only if `model_s_was_away` is off | Pulses gate + House Garage, then wakes the car |
| **Gate — begin departure** | Same as above | Sets `model_s_was_away` / `model_x_was_away`. Does not wait on `model_x_was_away` for the S |
| **Gate — wake Tessie while Model S is away** | Every 5 min while was_away and Gen/Dave still out | Model X equivalent; S GPS never shows >200 m |

**2026-09-29:** Occupant/odometer “arrival” opened the gate after Gen was already home (phone hit Road Approach 90 s earlier; they used the intercom). That fallback is removed. Do not treat stale GPS-home as parked while Gen/Dave are still `not_home`.

**Gate hold:** Akuvox auto-closes after ~5 s. Live uses `script.gate_pulse_hold_approach` / `script.gate_pulse_departure`. Repo `script.gate_open_with_hold` is the older equivalent.

**Emergency close:** turn off `input_boolean.gate_hold_active`, stop the pulse scripts, then `lock.lock` on both gate lock entities.

Tune hold timing: `input_number.gate_hold_repulse_seconds`, `input_number.gate_hold_max_minutes`.

**Tessie:** API key and wake URL live in `/config/secrets.yaml` (`tessie_api_key_header`, `tessie_wake_model_s_url`, `tessie_model_s_location_url`). Do not commit secrets to git.

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

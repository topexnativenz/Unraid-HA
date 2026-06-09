# Gate approach — reliability strategy

## Problem

The driveway mouth has **poor or no cellular coverage**. The Home Assistant Companion app only reports location when the phone can reach the internet. If the last update was at home, HA never sees **Gate Approach** until you are past the gate — too late.

The Companion app does **not** need to stay open, but it **does** need to deliver at least one location update **before** the dead zone (or another signal source must trigger the gate).

## Layered solution (implemented in HA)

| Layer | Source | When it fires | Dead-zone safe? |
|-------|--------|---------------|-----------------|
| **1 — Road Approach** | Tessie enters road approach circle (450 m radius) | ~30 s GPS updates while driving | **Yes** — primary Tessie trigger |
| **2 — Tessie distance** | `sensor.model_s_tessie_distance_to_home` &lt; 400 m | Backup if zone circle drifts | **Yes** |
| **3 — Gate Approach** | Tessie at driveway mouth (~100 m) | Second Tessie trigger | **Yes** |

All layers call `script.gate_pulse_hold_approach` (relay 1 only, repulse until passage clear or timeout).

### Zone placement (UI-editable)

Zones are managed in **Settings → Areas & zones → Zones** (not `configuration.yaml`). Drag the circles on the map:

- **Gate Approach** — driveway mouth on Three Mile Bush Road (~100 m radius).
- **Road Approach** — centred **upstream** on Three Mile Bush Road (~**450 m** radius). Sized for Tessie’s ~30 s position updates at 50–60 km/h (~400–500 m between pings). Drag on the HA map if the centre needs a tweak.

After changing zones, re-sync zones in the **Companion app**.

### Tunables (HA UI)

- `input_number.gate_early_hold_seconds` — default **300** (5 min hold through dead zone).
- `input_number.gate_tessie_trigger_distance_m` — default **400** m from gate centre.
- `input_number.gate_hold_repulse_seconds` — relay pulse interval (default 4 s).

## Companion app (still required for Layer 1)

Phones must report GPS to HA while still on LTE **before** the driveway dead zone. That requires reliable **remote** connectivity — use **Nabu Casa** (HA Cloud), not Tailscale on the phone. Full setup: [home-assistant/README.md](../home-assistant/README.md#companion-app--remote-access-nabu-casa).

1. **Use Home Assistant Cloud** on in Companion; internal URL `http://192.168.1.239:8123`; home Wi‑Fi SSID set
2. Location: **Always**
3. **Background location** / significant-change updates enabled
4. **Manage zones** → sync HA zones; confirm **Road Approach** and **Gate Approach** appear
5. **Location submission: Always** (not only “when connected to HA”) so updates queue and send when cell returns
6. Remove any Companion **external URL** pointing at Tailscale (`100.x.x.x`) — use cloud relay only

iOS may batch updates until signal returns; that is why **Road Approach** must be **before** the dead zone.

## Hardware / infrastructure options (most reliable)

| Option | Reliability | Effort |
|--------|-------------|--------|
| **Cell booster / small antenna** at house aimed toward driveway | High for phone layers | Medium cost |
| **Wi‑Fi mesh AP** toward gate (UniFi, etc.) | High if phone joins Wi‑Fi before gate | Medium |
| **mmWave / radar** (ESP32 + LD2410) at gate → ESPHome → HA | **Highest** — no phone | Low–medium DIY |
| **Vehicle loop or beam** wired to relay/ESPHome | Highest for cars | Electrician |
| **Akuvox call button** at gate (manual) | Manual only | Already installed |
| **Tesla BLE** (if supported in your HA setup) | Car-specific | Varies |

Recommended long-term: **ESPHome presence sensor at the gate post** firing `shell_command.akuvox_gate_open_relay_1` when a vehicle is detected, with phone/Tessie as secondary.

## Verification

After a drive home, check in HA:

- `input_text.gate_status_message` — which trigger fired (`halo_enter_road`, `tessie_distance`, etc.)
- `sensor.model_s_tessie_distance_to_gate` — did Tessie update during approach?
- `device_tracker.halo` — last update time vs time you reached the gate
- **Settings → Automations → Gate — open on arrival** — last triggered

If only Tessie should apply (walking home without phone), lower Tessie distance or add a separate “pedestrian” hardware trigger.

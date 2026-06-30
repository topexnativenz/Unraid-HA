# Gate intercom (Akuvox / Akubela community)

Deploy to Home Assistant at `http://192.168.1.239:8123`.

**Strategy doc (dead zone, layers, hardware):** [`docs/gate-approach-strategy.md`](../../docs/gate-approach-strategy.md)

## Arrival — Tessie only (Model S)

| Layer | Trigger | Notes |
|-------|---------|-------|
| **Road Approach** | `binary_sensor.model_s_tessie_in_road_approach` | Primary — Tessie GPS on Three Mile Bush Road |
| **Gate Approach** | `binary_sensor.model_s_tessie_in_gate_approach` | Driveway mouth / road end (~120 m) |
| **Distance** | `sensor.model_s_tessie_distance_to_gate` &lt; `gate_tessie_trigger_distance_m` | Backup at mouth (~180 m) |

Automation: **Gate — open on Tessie arrival** → relay 1 pulse, then `script.gate_pulse_hold_approach` until Tessie reports car parked at home.

**Departure** (unchanged): Tesla **P → R/D** → short departure hold.

Phones are not used for gate open. Companion zones remain useful for dashboards only.

**Zone entity IDs:** automations reference the live UI zones (`zone.gate_approach_2`, `zone.road_approach_2` on this HA). If you recreate zones, run `cleanup_gate_zones.py` and update `automations/gate.yaml` to match entity IDs shown under **Developer tools → States**.

## Zones (editable on the HA map)

**Gate Approach** and **Road Approach** are **not** in YAML anymore — create/update them in the UI:

**Settings → Areas & zones → Zones** — drag the circles on the map (pencil icon).

After deploy or a YAML→UI migration, run once:

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/gate/scripts/ensure_gate_zones.py
```

Use `--update-existing` only if you want to reset coordinates from `secrets.yaml` defaults (normally **drag the map** instead).

| Zone | Place on map |
|------|----------------|
| **Gate Approach** | Three Mile Bush Road at the **driveway mouth** (small radius ~100 m) |
| **Road Approach** | On **Three Mile Bush Road** upstream of the driveway — **~450 m** radius for Tessie’s ~30 s GPS cadence |

Optional starting values in `/config/secrets.yaml` (used only by `ensure_gate_zones.py`):

```yaml
gate_latitude: "-35.69110"
gate_longitude: "174.2669872"
gate_approach_radius: 100
road_approach_latitude: "-35.68926"
road_approach_longitude: "174.26696"
road_approach_radius: 450
```

## Other secrets (`/config/secrets.yaml`)

```yaml
tessie_api_key_header: "Bearer …"
tessie_wake_model_s_url: "https://api.tessie.com/…/wake"
tessie_model_s_location_url: "https://api.tessie.com/…/location"
```

## Notifications

Gate open/close alerts use `notify.halo`. Arrival is **Tessie-only** — phones are not in the open automation.

Tessie location polls every 10 s; `gate_tessie_wake_while_away` wakes the car every 5 min when `model_s_was_away` is on.

## Packages

| File | Role |
|------|------|
| `gate_automations.yaml` | Gate + home zones |
| `gate_approach_layers.yaml` | Road Approach zone + tunables |
| `gate_tessie_location.yaml` | Tessie REST poll + distance sensors |
| `gate_akuvox.yaml` | Relay scripts, `gate_arrival_passage_active` |
| `gate_phone.yaml` | Status sensor |
| `automations/gate.yaml` | Automations block for `automations.yaml` |

## Relays

Relay **1** = pulse (automations). Relay **2** = latch (manual test only).

## Deploy

```bash
/Users/topexnative/Projects/unraid-array-design/home-assistant/gate/scripts/deploy_gate_packages.sh
```

If you are inside a `.venv` without `websockets`, the script uses system Python automatically. Alternatively:

```bash
python3 -m pip install --user websockets
# or
export HA_SAMBA_PASSWORD='…'   # HA → Settings → Add-ons → Samba share
```

Manual fallback: copy all `packages/gate*.yaml` and the gate block in `automations/gate.yaml` into `/config`, then reload core config + template + automations + scripts.

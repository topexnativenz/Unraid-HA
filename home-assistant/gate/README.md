# Gate intercom (Akuvox / Akubela community)

Deploy to Home Assistant at `http://192.168.1.239:8123`.

**Strategy doc (dead zone, layers, hardware):** [`docs/gate-approach-strategy.md`](../../docs/gate-approach-strategy.md)

## Arrival — Tessie only (Model S + Model X)

Each car has its own Tessie location poll, approach sensors, and arrival automation. Shared session/hold scripts apply to whichever car triggers first.

| Layer | Model S | Model X |
|-------|---------|---------|
| **Road Approach** | `binary_sensor.model_s_tessie_in_road_approach` | `binary_sensor.model_x_tessie_in_road_approach` |
| **Gate Approach** | `binary_sensor.model_s_tessie_in_gate_approach` | `binary_sensor.model_x_tessie_in_gate_approach` |
| **Distance** | `sensor.model_s_tessie_distance_to_home` | `sensor.model_x_tessie_distance_to_home` |
| **Shift / speed** | `sensor.model_s_p100d_shift_state` / `_speed` | `sensor.x_shift_state` / `sensor.x_speed` |
| **Was away** | `input_boolean.model_s_was_away` | `input_boolean.model_x_was_away` |

Automations: **Gate — open on Tessie arrival** (Model S) and **Gate — open on Tessie arrival (Model X)** → relay 1 pulse, then `script.gate_pulse_hold_approach` until Tessie reports car parked at home.

**Departure**: Tesla **P → R/D** on either car → short departure hold.

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
tessie_wake_model_x_url: "https://api.tessie.com/…/wake"
tessie_model_x_location_url: "https://api.tessie.com/…/location"
```

If Tessie HA entity IDs differ from `sensor.tesla_model_x_shift_state` / `sensor.tesla_model_x_speed`, update `automations/gate.yaml` and `garage-doors/automations/garage.yaml` after checking **Developer tools → States**.

### Getting Tessie URLs for Model X

1. **API token** — [my.tessie.com → Settings → Developer](https://dash.tessie.com/settings/api) → copy any **Access Token**. One token works for **all** vehicles on the account; you do not need a separate token per car unless you want to rotate/revoke independently.
2. **Model X VIN** — on [my.tessie.com](https://my.tessie.com), use the **vehicle switcher** (top of the dashboard). Open **Settings** for Model X; the VIN is shown there (17 characters, e.g. `5YJ…`). Alternatively: Tesla app → Model X → **Controls** → scroll to **VIN**.
3. **URLs** — substitute the Model X VIN into the Tessie API paths ([developer.tessie.com](https://developer.tessie.com)):
   - Location (GET): `https://api.tessie.com/<MODEL_X_VIN>/location`
   - Wake (POST): `https://api.tessie.com/<MODEL_X_VIN>/wake`
4. **Virtual key** — on the phone logged into the Tesla account for Model X, open [tessie.com/key](https://tessie.com/key) and complete setup so wake/location work when the car is asleep.
5. **HA Tessie integration** — **Settings → Devices & services → Tessie** must include Model X (shift/speed entities). Re-add or reconfigure if `sensor.tesla_model_x_shift_state` is missing.

### Restoring Model S in HA Tessie

If Tessie shows Model S + Model X at [my.tessie.com](https://my.tessie.com) but HA only lists Model X, Energy Site, and Wall Connector:

1. **Tessie account** — **Settings → Connectivity**: Tesla email must match the Tesla app. Tap **Sync** (or **Sync vehicles**). Confirm Model S is not archived (**Fleet → Archived → Unarchive**).
2. **HA has no reconfigure** — [official docs](https://www.home-assistant.io/integrations/tessie/): remove Tessie (⋮ → Delete), then **Add integration → Tessie** with the same API token. **Do not** use **Add hub** for a second car on the same account — one hub/token discovers all active vehicles.
3. **After re-add** — **Developer tools → States**, filter `shift`. Entity slug follows the Tesla vehicle name (Model X named `X` → `sensor.x_shift_state`). Model S may be `sensor.s_shift_state`, `sensor.model_s_shift_state`, or the old `sensor.model_s_p100d_shift_state` — copy the real IDs into repo YAML (see table above + `garage-doors/automations/garage.yaml`, `solar-dashboard/packages/solar_dashboard_ev.yaml`).
4. **Pre-2021 Model S** — virtual key / command signing not required ([HA Tessie docs](https://www.home-assistant.io/integrations/tessie/#command-signing)); wake/location via REST still need correct VIN URLs in `secrets.yaml`.

## Notifications

Gate open/close alerts use `notify.halo`. Arrival is **Tessie-only** — phones are not in the open automation.

Tessie location polls every 10 s; `gate_tessie_wake_while_away` / `gate_tessie_wake_while_away_model_x` wake each car every 5 min when its `model_*_was_away` helper is on.

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

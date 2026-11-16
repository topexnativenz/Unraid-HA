# Home Assistant — lights

## Hall footlights auto-off

Package: `packages/footlights_auto_off.yaml`

| Setting | Default |
|---------|---------|
| `input_number.footlights_auto_off_seconds` | **120** seconds (2 min) |

| Automation | Behaviour |
|------------|-----------|
| **Hallway footlights after sunset** | On at sunset / motion → off after delay (`mode: restart`) |
| **Hall footlights — auto off after delay** | Any footlight `on` → off after delay (covers C-Bus / motion) |
| **Sensor Lights off during daylight** | Off at sunrise (07:30–19:30 window) |

Adjust delay in HA: **Settings → Devices & services → Helpers → Footlights auto-off delay**.

Deploy:

```bash
cp /Users/topexnative/Projects/unraid-array-design/home-assistant/lights/packages/footlights_auto_off.yaml \
   /tmp/ha-config-smb/packages/footlights_auto_off.yaml
# Then reload automations + core config in HA
```

## 2026-11-17 — Garage / shed lights staying on at night (fixed)

**What happened**
- Shed lights (`switch.shed_shed_lights_1`, `switch.shed_shelly_light_2`, `switch.shed_shelly_light_3`) were on from
  Sun 15 Nov 8:09pm to Mon 16 Nov 10:27pm NZDT (turned off by hand). `Shed lights — on at sunset if shed garage already open`
  fired every sunset because `input_boolean.second_shed_door_open` had been stuck `on` since 13 Nov 7:23pm (no sensor on the
  second shed — it only toggles on dashboard pulses) and `binary_sensor.contact_sensor_door` (Main Shed Tapo T110) was
  unavailable 14 Nov 2:35pm → 16 Nov 8:41pm (H200 hub offline) and came back reporting a stale **open**.
  The "off when door closes" automation needs an on→off transition, which never came.
- `light.garage` is turned on by `House Garage — open when Tesla departure starts` (and arrival paths) and nothing turned it off
  (16 Nov 4:49pm → 8:34pm; 17 Nov from 7:49am).
- `input_boolean.garage_outside_lights_arrival_active` stuck `on` since 16 Nov 8:30pm (garage-closed trigger never fired;
  automation also referenced non-existent `binary_sensor.house_garage_door_is_open`).

**Changes (live via HA config API, exported in `ui-config/automations_garage_shed_lights.yaml`)**
- Sunset shed-on: only if a shed door was seen opening in the last 6 h (main: live Tapo with signal > 0, ignoring an
  "open" restored by a hub reconnect; second: helper changed in last 6 h).
- Shed-off: also triggers on `input_boolean.main_shed_door_open` on→off.
- Outside-garage-off: removed dead entity; added 15-min fallback after the arrival turns the light on.
- New `Garage light — off 15 min after an automation turned it on` (manual switch-ons are left alone).
- New `Garage & shed lights — night sweep off` at 23:30 and sunrise+30 min (skipped during a gate session), notifies `mobile_app_halo`.
- Helpers reset: `second_shed_door_open` off, `garage_outside_lights_arrival_active` off. Door/gate safety logic untouched.

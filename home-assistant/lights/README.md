# Home Assistant — lights

## C-Bus bridge watchdog (Flux tablet Lights)

Package: `packages/cbus2mqtt_watchdog.yaml`

Flux tablet overview Lights buttons toggle C-Bus via **cbus2mqtt** (`a9f92ca1_cbus2mqtt`). If that add-on wedges, taps look dead (HA publishes MQTT, rooms never change).

| Helper | Role |
|--------|------|
| `script.restart_cbus2mqtt` | Manual / dashboard restart of the add-on |
| **Restart cbus2mqtt when C-Bus lights go unavailable** | Auto-restart after Cooking + Main Atrium stay `unavailable` for 2 minutes |

Quick fix without deploy: **Settings → Add-ons → cbus2mqtt → Restart**.

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

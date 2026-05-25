# Home Assistant — lights

Daylight footlight restrictions were **reverted** (2026-05-25). Sensor lights are allowed to stay on during the day; no `sensor_lights` package on HA.

Footlight automations live in `/config/automations.yaml` on the HA host:

- **Hallway footlights after sunset** — sunset + hall motion (20:00–07:00 window)
- **Sensor Lights off during daylight** — off at sunrise (07:30–19:30 window)

# Casa Luna side dashboard (Home Assistant)

Experimental **wall-tablet energy + home control dashboard** using [Casa Luna](https://github.com/thekhan1122/casa-luna) (`custom:casa-luna`). Separate from the locked **solar-dashboard** (332 Three Mile Bush Road) and the **tablet-dashboard** glass UI.

**Energy** still uses template sensors from the deployed `solar_dashboard.yaml` package (`input_boolean.solar_dashboard_demo` must be **on** until Sigenergy is live). **Home** entities (gate, lights, Tessie, cameras, automations) are wired to real HA entities.

## What you get

| File | Purpose |
|------|---------|
| `www/community/casa-luna/casa-luna.js` | Custom Lovelace card (v1.0.0 build 49) |
| `www/community/casa-luna/sky/*.png` | 13 weather × time sky backgrounds |
| `www/floorplan/base-view-night.png` | 4:3 floorplan night-sky composite (replaces grey `my-floorplan/base-view.png`) |
| `lovelace/patches/floorplan_4_3_background.yaml` | Storage dashboard image + card_mod patch |
| `lovelace/dashboards/casa_luna.yaml` | Panel dashboard + entity bindings |
| `packages/casa_luna_demo.yaml` | PV total, inverter state, battery current, today load |
| `packages/casa_luna_entities.yaml` | Scene/light scripts for card scene buttons |
| `scripts/deploy_casa_luna.py` | SMB + WebSocket deploy |

## Open

**http://192.168.1.239:8123/casa-luna/home** (sidebar: **G-UNIT**)

Floorplan (4:3) ground floor includes a moon icon (top-left) that navigates back to **G-UNIT 16:9** (`/g-unit-16x9/home`). That backlink is patched by `casa-luna-16x9/scripts/deploy_casa_luna_16x9.py` via WebSocket (`casa-luna-16x9/lovelace/patches/floorplan_4_3_gunit_backlink.yaml`). This 3:2 deploy only patches the floorplan night background (`floorplan_4_3_background.yaml`).

Regenerate the floorplan background: `python3 home-assistant/casa-luna/scripts/generate_floorplan_background.py`

Hard-refresh after deploy: `Cmd + Shift + R`.

## Wall panel (kiosk) user

HACS **[Kiosk Mode](https://github.com/NemesisRE/kiosk-mode)** is installed. G-UNIT and Floorplan (4:3) include `kiosk_mode` in Lovelace YAML — sidebar, header, overflow menu, edit dashboard, and entity **Settings** icons are hidden for the **Panel** user (`username`: `panel`, local-only).

| Item | Value |
|------|-------|
| Login | `panel` (password set in HA **Settings → People**) |
| Default dashboard | **G-UNIT** (`casa-luna`) |
| Open URL | http://192.168.1.239:8123/casa-luna/home |
| Temporarily disable kiosk | append `?disable_km` to the URL (admin only useful for testing) |

Apply panel defaults after deploy:

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/casa-luna/scripts/set_panel_default.py
```

Optional — set in-memory prefs immediately (no restart needed) if you pass the Panel password:

```bash
PANEL_HA_PASSWORD='your-panel-password' python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/casa-luna/scripts/set_panel_default.py
```

**Important:** log wall tablets in as **`panel`**, not your admin account. The system default for everyone else is **Mobile Home** (`mobile-home`).

### Panel user on iPhone / iPad (Companion)

The iOS app often opens **Mobile Home** even when the server pins Panel to G-UNIT — especially with **Dashboard → Auto** or a stale frontend cache.

Do **all** of these while logged in as **`panel`**:

1. **Profile → Dashboard** → choose **G-UNIT** (not **Auto**).
2. **Settings → Dashboards → G-UNIT** → **Set as default on this device**.
3. **Companion App → Debugging → Reset Frontend Cache**, then force-quit and reopen.
4. Re-apply server pin (writes disk + restarts HA so in-memory prefs do not overwrite):
   ```bash
   python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/casa-luna/scripts/set_panel_default.py
   ```

Direct link (LAN): http://192.168.1.239:8123/casa-luna/home  
Deep link: `homeassistant://navigate/casa-luna/home`

Other dashboards are hidden from the Panel sidebar; lighting nav still opens Floorplan (4:3) with the same kiosk lockdown.

### iPad blank sidebar fix

If the left column is empty but still reserves space (common on iPad / HA 2026 `wa-drawer`), deploy includes **`panel-kiosk-fix.js`** — a small Lovelace resource that forces `--ha-sidebar-width: 0` in the HA shell shadow DOM. The **panel-kiosk** theme is also assigned to the Panel user as backup.

After deploy on the iPad:

1. Log in as **panel** (not admin)
2. Force-quit Safari / HA Companion, reopen
3. Hard refresh: hold reload → **Request Desktop Website** off, then reload; or clear website data for `192.168.1.239`
4. Open http://192.168.1.239:8123/casa-luna/home — G-UNIT should span full width

Verify resource in **Settings → Dashboards → Resources**: `/local/community/casa-luna/panel-kiosk-fix.js?v=1` (loads after kiosk-mode).

## Install

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/casa-luna/scripts/deploy_casa_luna.py
```

The script copies card assets, both package YAMLs, dashboard YAML, registers the Lovelace resource, and reloads templates.

## Bottom tile order (left → right)

| # | Label | Entity | Tile status | Tap for detail |
|---|-------|--------|-------------|----------------|
| 1 | Gate | `lock.gate_intercom_gate_open` | LOCKED / UNLOCKED | Lock toggle + gate scripts |
| 2 | House garage | `binary_sensor.house_garage_door_sensor_door` | OPEN / CLOSED | Full state + last changed |
| 3 | Main shed | `binary_sensor.casa_luna_main_shed_garage_door` | OPEN / CLOSED | Full state + last changed (Tapo `binary_sensor.contact_sensor_door`) |
| 4 | Model S | `sensor.model_s_p100d_battery_level` | `72%` | SOC, charging W, current, state |
| 5 | Model X | `sensor.x_battery_level` | `48%` | SOC, charging W, state |
| 6 | UniFi AP | `sensor.casa_luna_unifi_summary_short` | Pending / Online / `2 upd` | AP status + firmware pending list |

Model S + Model X are adjacent (tiles 4–5). Garage doors adjacent (tiles 2–3). Downloads removed from bottom row; TV/movie detail stays in Recent Events.

## Entity mapping

### Energy & weather (demo until Sigenergy)

| Casa Luna key | Entity | Status |
|---------------|--------|--------|
| `pv1_power` / `en_pv1` | `sensor.solar_roof_power` | Demo (solar_dashboard) |
| `pv2_power` / `en_pv2` | `sensor.solar_ground_power` | Demo |
| `pv_total_power` | `sensor.casa_luna_pv_total` | Computed sum |
| `grid_*` / `consump` / `en_load` | `sensor.grid_import_power`, `sensor.grid_voltage`, `sensor.home_consumption_power` | Demo |
| `battery_*` / `bat_*` | `sensor.solar_battery_*`, `sensor.casa_luna_battery_current` | Demo |
| `inverter_state` / `en_work_mode` | `sensor.casa_luna_inverter_state` | Demo |
| `inv_temp` / `sys_inv_temp` | `sensor.inverter_temperature` | Demo |
| `today_pv` / `today_load` / `total_pv` | solar production sensors | Demo |
| `weather_entity` | `weather.forecast_home` | **Live** |
| `sun` | `sun.sun` | **Live** |

### EV / Tessie

| Key | Entity | Status |
|-----|--------|--------|
| `_show_ev` | `true` | Enabled |
| `charger_soc` | `sensor.model_s_p100d_battery_level` | **Live** |
| `charger_power` | `sensor.model_s_p100d_charger_power` | **Live** |
| `charger_current` | `sensor.model_s_p100d_charger_current` | **Live** |
| `charger_state` | `sensor.model_s_p100d_charging` | **Live** |
| `_extra_tile_4` | `sensor.model_s_p100d_battery_level` | **Live** (Model S SOC % on tile) |
| `_extra_tile_5` | `sensor.x_battery_level` | **Live** (Model X SOC %) |
| `events_entities` | `sensor.x_battery_level`, `sensor.x_charging` | **Live** (detail in feed) |

Model S on EV banner and bottom tile 4; Model X on bottom tile 5.

### Climate

| Key | Entity | Status |
|-----|--------|--------|
| `auto_discover_climate` | `true` | All `climate.*` + temp/humidity sensors |
| `clim_ambient` | `sensor.hypanel_pro_temperature_2` | **Live** (manual slot; also in auto) |
| `clim_humidity` | `sensor.hypanel_pro_humidity_2` | **Live** |
| Home thermostat | `climate.main_thermostat` | **Missing** — not in HA |

### Security & gate

| Key | Entity | Status |
|-----|--------|--------|
| `sec_cam1` | `camera.front_yard` | **Live** (stream needs `camera_stream_base` / go2rtc) |
| `sec_cam2` | `camera.garage_door` | **Live** |
| `sec_motion` | `binary_sensor.front_yard_motion_detected` | **Live** |
| `sec_door1` | `binary_sensor.house_garage_door_sensor_door` | **Live** (House Garage) |
| `sec_door2` | `binary_sensor.garage_door_sensor_open` | **Live** (Main Garage contact) |
| `sec_door3` | `binary_sensor.casa_luna_main_shed_garage_door` | **Live** (Main Shed — Tapo T110 via `binary_sensor.contact_sensor_door`) |
| `sec_window1` | `binary_sensor.front_door_doorbell_person_detected` | **Live** |
| `sec_scene_arm` | `script.gate_pulse_open_once` | **Live** (gate open) |
| `sec_scene_disarm` | `script.gate_pulse_departure` | **Live** |
| `sec_scene_night` | `script.gate_open_tesla_when_leaving` | **Live** |
| `_extra_tile_1` | `lock.gate_intercom_gate_open` | **Live** |
| `_extra_tile_2` | `binary_sensor.house_garage_door_sensor_door` | **Live** (Tapo — OPEN/CLOSED) |
| `_extra_tile_3` | `binary_sensor.casa_luna_main_shed_garage_door` | **Live** (Tapo — OPEN/CLOSED) |
| `events_entities` | gate status, gate/garage automations, motion, alarm | **Live** |
| Alarm arm/disarm scenes | — | **Not wired** — card scene buttons only call `scene.turn_on` / `script.turn_on`; use HA app or `alarm_control_panel.three_mile_bush` directly |
| `sec_flame` / gas sensors | — | **Missing** (no ESP sensors) |

Other cameras on HA (`camera.side_door`, `camera.front_door_doorbell`, etc.) are not in the two camera slots; enable `auto_discover_security` or add go2rtc streams to expose more.

### Lighting

| Key | Entity | Status |
|-----|--------|--------|
| `auto_discover_lighting` | `true` | All `light.*` (~40 C-Bus + groups) |
| `light_all_on` / `light_all_off` | `script.casa_luna_lights_all_on/off` | **Live** |

Ground-floor quick tile removed (`light.ground_floor_lights`); use Lighting nav or floorplan.

### Media & downloads

| Key | Entity | Status |
|-----|--------|--------|
| `events_entities` | `sensor.casa_luna_latest_tv_download`, `sensor.casa_luna_latest_movie_download` | **Placeholder** — per-source detail in feed only (no bottom tile) |
| `auto_alexa` | *(cleared)* | Kitchen Sonos removed from automation panel |

### Network (UniFi)

| Key | Entity | Status |
|-----|--------|--------|
| `_extra_tile_6` | `sensor.casa_luna_unifi_summary_short` | **Placeholder** — short tile label: Pending / Online / `N upd` |
| `sensor.casa_luna_unifi_summary` | (template) | Full summary for automations / other uses |
| `sys_wifi` | `sensor.casa_luna_unifi_ap_status` | **Placeholder** — header WiFi popup (build 49) |
| `sys_unifi_firmware` | `sensor.casa_luna_unifi_firmware_pending` | **Placeholder** — counts `update.unifi_*` when present |
| `events_entities` | `sensor.casa_luna_unifi_ap_status`, `sensor.casa_luna_unifi_firmware_pending` | **Placeholder** — detail in feed |

### Covers

| Key | Entity | Status |
|-----|--------|--------|
| `cover.garage_door` | Main garage cover | **Live** — in Security view + events feed (bottom tile removed) |
| Tessie windows/frunk | `cover.model_s_p100d_*`, `cover.x_*` | Not wired (too many; use Tessie app) |

### Automations & scenes

| Key | Entity | Status |
|-----|--------|--------|
| Scene buttons | `script.casa_luna_*` → tablet demo `input_button.*` | **Live** (demo toasts until real scenes exist) |
| `auto_motion_lights` | `automation.night_lights_on_arrival` | **Live** (toggle) |
| `auto_sunset_lights` | `automation.hallway_footlights_after_sunset` | **Live** |
| `auto_door_alerts` | `automation.garage_close_main_garage_at_9_pm` | **Live** |
| `auto_relay1–3` | gate + garage pulse scripts | **Live** |
| `auto_relay4` | `script.pulse_main_shed_door` | **Live** |
| Gate automations (~15) | various `automation.gate_*` | In **Recent Events** feed only |
| Real `scene.*` entities | — | **None in HA** |

### People

| Entity | Status |
|--------|--------|
| `person.dave`, `person.gen` | **Not supported** — Casa Luna card has no people/tracker slots |

### Demo / missing summary

| Item | Notes |
|------|-------|
| Energy/BMS | Demo until Sigenergy; JK cell temps, 3-phase, grid import kWh show `--` |
| `climate.main_thermostat` | Documented in tablet-dashboard but not present in HA |
| Camera live streams | Set `camera_stream_base` (e.g. go2rtc URL) for WebRTC embeds |
| `person.*` | No card support |
| `scene.*` | None defined; scripts wrap tablet demo buttons |

## Casa Luna limitations hit

1. **Two camera slots** — only `sec_cam1` / `sec_cam2`; more cameras need go2rtc or `auto_discover_security`.
2. **Scene buttons** — only `scene.*` and `script.*`; `input_button` and `alarm_control_panel` need wrapper scripts.
3. **No people row** — unlike tablet-dashboard; `person.dave` / `person.gen` not displayable.
4. **Lighting auto-discover** — lists every `light.*` (no area filter); can be slow on first open.
5. **Automation auto-discover off** — would include dozens of camera `switch.*` entities; key automations wired manually instead.
6. **EV banner** — Model S on main EV strip; Model S + Model X on adjacent bottom tiles 4–5.
7. **Bottom tiles (build 49)** — Gate · House garage · Main shed · Model S · Model X · UniFi. Text ellipsis on overflow; tap any tile for detail popup. Removed: Downloads bottom tile, RoboVac, ground lights, garage cover, Kitchen Sonos.
8. **`view_*_entities` arrays** — defined in card stub but unused in build 48; use per-view keys or auto-discover toggles.
9. **Sonarr/Radarr** — no HA sensors yet; template sensors show placeholders until HACS/REST wired.
10. **UniFi** — no UniFi Network integration in HA yet; template sensors auto-activate when `unifi_*` entities appear.
11. **Main Shed door** — `binary_sensor.casa_luna_main_shed_garage_door` mirrors Tapo `binary_sensor.contact_sensor_door` (Shed Main Door T110).

## When Sigenergy is live

1. Turn off `input_boolean.solar_dashboard_demo`
2. Rebind energy/battery keys in `casa_luna.yaml` to Sigenergy / GoodWe / JK entities
3. Re-run deploy script

**Do not edit** `home-assistant/solar-dashboard/`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Custom element doesn't exist | Confirm resource `/local/community/casa-luna/casa-luna.js` in **Settings → Dashboards → Resources**; hard-refresh |
| Blank / wrong sky | Check 13 PNGs in `/config/www/community/casa-luna/sky/`; `weather.forecast_home` must be available |
| Energy values `--` | Enable `input_boolean.solar_dashboard_demo`; reload templates |
| Camera tiles show placeholder | Set `camera_stream_base` to your go2rtc base URL |
| Scene button does nothing | Ensure `casa_luna_entities.yaml` is deployed; check **Developer tools → Scripts** |
| Downloads overflow / bottom tile | Removed from bottom row (build 49); detail in Recent Events feed |
| UniFi tile `pending UniFi integration` | Short label `Pending` on tile; tap for full AP + firmware detail |
| Main shed tile wrong OPEN/CLOSED | Confirm `binary_sensor.contact_sensor_door` in **Developer tools → States**; reload templates after deploy |
| Floorplan (4:3) "Configuration error" | Backlink must use picture-elements `type: icon` (not `state-icon` without `entity`). Re-run deploy script; it removes broken overlays and re-applies the patch |
| Floorplan still grey | Re-run `generate_floorplan_background.py` then deploy; hard-refresh (`Cmd+Shift+R`) |

## Branding

- **Sidebar title:** **G-UNIT** (set by deploy script in `configuration.yaml`)
- **In-card header:** `header_title` / `header_subtitle` on the card in `casa_luna.yaml`

## Notes

- Fixed **1500 × 1000** layout — landscape wall tablet
- Card source: [thekhan1122/casa-luna](https://github.com/thekhan1122/casa-luna) (Apache 2.0)

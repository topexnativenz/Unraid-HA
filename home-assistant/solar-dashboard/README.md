# Solar energy dashboard (Home Assistant)

Picture-elements dashboard inspired by the French community solar card: a house-on-a-lake scene with live production, battery, grid, and forecast data overlaid on a **weather- and time-aware background**.

Designed for a wall tablet. Works in **demo mode** today; swap entity IDs when your inverter and battery are live.

## What you get

| File | Purpose |
|------|---------|
| `packages/solar_dashboard.yaml` | Template sensors, background selector, demo helpers |
| `lovelace/views/solar-energy.yaml` | English dashboard view |
| `lovelace/views/solar-energy-fr.yaml` | French labels (matches reference screenshots) |
| `www/solar-dashboard/` | Background images and optional overlay assets |

## Prerequisites (HACS)

Install from [HACS](https://hacs.xyz/):

| Custom card | Why |
|-------------|-----|
| [button-card](https://github.com/custom-cards/button-card) | Styled data boxes, battery card, bottom stats |
| [card-mod](https://github.com/thomasloven/lovelace-card-mod) | Fine typography and transparency |
| [horizon-card](https://github.com/rejuvena604/lovelace-horizon-card) | Sun/moon arc with sunrise and sunset times |

Optional later: [Forecast.Solar](https://www.home-assistant.io/integrations/forecast_solar/) for real tomorrow kWh.

## Install

### 1. Copy files to Home Assistant

On your HA host (adjust paths if your config root differs):

```bash
# Package (sensors + helpers)
cp /Users/topexnative/Projects/unraid-array-design/home-assistant/solar-dashboard/packages/solar_dashboard.yaml \
   /config/packages/solar_dashboard.yaml

# Lovelace view — merge into your dashboard YAML or paste as a new view
cp /Users/topexnative/Projects/unraid-array-design/home-assistant/solar-dashboard/lovelace/views/solar-energy.yaml \
   /config/lovelace/views/solar-energy.yaml

# Web assets (backgrounds)
mkdir -p /config/www/solar-dashboard/backgrounds
cp -r /Users/topexnative/Projects/unraid-array-design/home-assistant/solar-dashboard/www/solar-dashboard/* \
   /config/www/solar-dashboard/
```

Ensure `configuration.yaml` loads packages:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

If you use YAML mode for Lovelace, add the view to your dashboard `views:` list:

```yaml
  - !include views/solar-energy.yaml
```

Or run the automated deploy script (uses your Cursor HA token + Samba):

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/solar-dashboard/scripts/deploy_to_ha.py
```

## Deployed on your HA (2026-05-24)

Live at **http://192.168.1.239:8123/solar-dashboard** (French labels, sidebar: **Solaire**).

Home Assistant requires dashboard URL paths to include a hyphen, so `/solaire` alone is not valid. Use `/solar-dashboard` for kiosk/tablet bookmarks.

| Item | Status |
|------|--------|
| button-card, card-mod | Already installed (HACS) |
| horizon-card | Installed to `/config/www/community/lovelace-horizon-card/` |
| Package `solar_dashboard.yaml` | Loaded via `/config/packages/` |
| Background images (5 scenes) | `/config/www/solar-dashboard/backgrounds/` |
| Demo mode | **ON** (`input_boolean.solar_dashboard_demo`) |
| Weather entity | `weather.forecast_home` |

Background images are stylized placeholders (house, panels, pylon, flow arrows). Swap for final artwork when ready — keep the same filenames and layout positions.


### 2. Background images

The original post uses a custom landscape (based on work by Zia Ul Hassan) with flow arrows baked in. You need **one image per scene** in `/config/www/solar-dashboard/backgrounds/`:

| Filename | When used |
|----------|-----------|
| `clear.jpg` | Daytime, fair weather |
| `cloudy.jpg` | Partly cloudy / cloudy |
| `covered.jpg` | Overcast, rain, fog |
| `very_covered.jpg` | Heavy rain / storm (optional; falls back to `covered.jpg`) |
| `night.jpg` | Sun below horizon |

Recommended size: **1920×1080** (16:9) for tablets. Keep dashed energy-flow arrows in the same position on every variant so overlays line up.

Until you have final art, use any 16:9 placeholders with the same filenames so the layout can be tuned.

### 3. Weather entity

Edit `packages/solar-dashboard.yaml` and set your weather entity (default `weather.home`):

```yaml
# In sensor.solar_dashboard_background template — replace weather.home
```

If you have no weather integration yet, add [Meteorologisk institutt (Met.no)](https://www.home-assistant.io/integrations/met/) or your preferred provider.

### 4. Demo mode

Turn on **Solar dashboard demo mode** in **Settings → Devices & services → Helpers**. All overlay values animate with plausible demo data so you can mount the tablet and refine layout before install day.

Turn demo off when real entities are wired (see entity map below).

## Entity map (when solar is live)

Replace placeholders in `packages/solar-dashboard.yaml` under `variables:` (or edit each template). Typical sources:

| Dashboard sensor | Example real entity | Notes |
|------------------|----------------------|--------|
| `sensor.solar_roof_power` | Inverter string / roof MPPT | W |
| `sensor.solar_ground_power` | Second MPPT or aggregate − roof | W |
| `sensor.solar_battery_power` | Battery charge/discharge | W (+ charge / − discharge) |
| `sensor.solar_battery_soc` | BMS SOC | % |
| `sensor.solar_battery_voltage` | BMS voltage | V |
| `sensor.grid_import_power` | Grid import (positive = drawing) | W |
| `sensor.grid_voltage` | Inverter grid voltage | V |
| `sensor.inverter_temperature` | Inverter temp | °C |
| `sensor.battery_cycle_count` | BMS cycles | count |
| `sensor.solar_pv_total_today` | Total PV today | kWh |
| `sensor.home_consumption_power` | House load | W |
| `sensor.solar_production_today` | Today solar | kWh |
| `sensor.solar_production_month` | Utility meter / integration | kWh |
| `sensor.solar_production_year` | Utility meter / integration | kWh |
| `sensor.solar_forecast_today` | `forecast_solar` or inverter API | kWh |
| `sensor.solar_forecast_tomorrow` | Forecast.Solar | kWh |

Popular integrations: **SolarEdge**, **Fronius**, **Huawei Solar**, **SMA**, **GivEnergy**, **Modbus** (via `homeassistant-modbus`), **Energy Dashboard** utility meters.

## French labels (optional)

The reference UI uses French. To match it, edit display names in `lovelace/views/solar-energy.yaml` button-card `name:` fields, for example:

- Grid consumption → `CONSO RÉSEAU`
- Roof solar → `SOLAIRE (TOIT)`
- Ground solar → `SOLAIRE (SOL)`
- Battery → `BATTERIE`

## Tablet tips

- Dashboard **Settings → Appearance**: dark theme, hide header (kiosk).
- **Fully Kiosk Browser** or **WallPanel** on Android for full-screen + wake on motion.
- Use **Browser Mod** or the HA Companion app in **kiosk mode** on iPad.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Blank background | Check `/local/solar-dashboard/backgrounds/*.jpg` exists and filenames match |
| `custom:button-card` error | Install via HACS; clear browser cache |
| Wrong weather scene | Confirm `weather.*` state strings; adjust template conditions |
| Entities show `unknown` | Enable demo mode or map real entity IDs in the package |

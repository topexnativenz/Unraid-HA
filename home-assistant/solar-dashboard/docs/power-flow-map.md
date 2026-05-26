# Power flow map — 332 Three Mile Bush Road dashboard

Visual layers on `backgrounds/v4/*.jpg` (built by `scripts/build_v4_backgrounds.py`).

**Style:** Bright daytime CGI master; smooth dashed Bézier curves (white grid, amber solar, green EV). Grid lines anchor to the **master lattice tower** on the right hill (no pasted sprite / ellipse mask).

## Layer 1 — Transmission (Northpower grid)

| Visual | Meaning |
|--------|---------|
| **Solid dark lines** from left/right horizon | 11 kV / grid transmission into the district |
| **Lattice tower on hill** (behind garage, distant) | Grid connection point |
| **White dashed** tower → garage inverter | Import / export at site |

| Card | Entity (live, TBD) | Demo entity |
|------|-------------------|-------------|
| Grid use | `TBD.sigenergy_grid_power` | `sensor.grid_import_power` |
| Grid details | voltage, temp, cycles | `sensor.grid_voltage`, etc. |

## Layer 2 — Solar (SunPower ground array)

| Visual | Meaning |
|--------|---------|
| **Amber dashed** along lawn → inverter | PV production |

| Card | Entity (live) | Demo |
|------|---------------|------|
| Solar array | `TBD.sigenergy_pv_power` | `sensor.solar_ground_power` |
| PV total / today / month / year | Sigenergy energy counters | `sensor.solar_*` |

## Layer 3 — Site hub (Sigenergy SigenStor)

| Visual | Meaning |
|--------|---------|
| **Inverter** on garage exterior wall | 30 kW controller |
| **Amber** inverter ↔ house | Home load / battery discharge |
| **Amber** inverter ↔ battery cabinet | SOC / charge |

| Card | Entity (live) | Demo |
|------|---------------|------|
| Home use | calculated load W | `sensor.home_consumption_power` |
| Battery | SOC, power, V | `sensor.solar_battery_*` |

## Layer 4 — EV (Sigenergy DC charger + Tessie)

| Visual | Meaning |
|--------|---------|
| **Green dashed** inverter → charger → garage | EV charging |

| Card | Entity (live) | Demo |
|------|---------------|------|
| Garage Model S | Tessie | `sensor.garage_model_s_*` |
| Garage Model X | Tessie when added | `sensor.garage_model_x_*` |

## Tuning line geometry

Edit waypoint lists in `scripts/build_v4_backgrounds.py` (`SITE`, `ROUTES`, `HV_LINES`, `CARD_STUBS`), then:

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/solar-dashboard/scripts/build_v4_backgrounds.py
```

Redeploy with `scripts/deploy_to_ha.py --skip-restart`.

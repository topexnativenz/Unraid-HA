# Power flow map — 332 Three Mile Bush Road dashboard

> **Baked art frozen:** `backgrounds/v4/master-clear.png` is the locked CGI master. **Do not regenerate** it. Weather JPGs live in `backgrounds/v14/` and are built by **synthetic sky replace only** (`scripts/build_v4_backgrounds.py --out …/v14`) — no TELEA/inpaint on the master, no flow-line overlays on backgrounds. Lovelace card positions are tunable on user request (see `docs/332-three-mile-bush-build-spec.md` § *Background master (LOCKED)*).

Visual layers: clean CGI property render + Lovelace `button-card` overlays (no dashed energy-flow lines baked into JPGs).

**Style:** Bright daytime CGI master; grid pylon on the right hill stays 100% master pixels. Sky band uses v14 synthetic gradient + clouds; palm foliage and house silhouettes preserved via keep mask.

## Layer 1 — Transmission (Northpower grid)

| Visual | Meaning |
|--------|---------|
| **Lattice tower on hill** (behind garage, distant) | Grid connection point (master CGI — never edited) |
| *(No baked flow lines)* | Import/export shown via **Grid use** card only |

| Card | Entity (live, TBD) | Demo entity |
|------|-------------------|-------------|
| Grid use | `TBD.sigenergy_grid_power` | `sensor.grid_import_power` |
| Grid details | voltage, temp, cycles | `sensor.grid_voltage`, etc. |

## Layer 2 — Solar (SunPower ground array)

| Card | Entity (live) | Demo |
|------|---------------|------|
| Solar array | `TBD.sigenergy_pv_power` | `sensor.solar_ground_power` |
| PV total / today / month / year | Sigenergy energy counters | `sensor.solar_*` |

## Layer 3 — Site hub (Sigenergy SigenStor)

| Card | Entity (live) | Demo |
|------|---------------|------|
| Home use | calculated load W | `sensor.home_consumption_power` |
| Battery | SOC, power, V | `sensor.solar_battery_*` |

## Layer 4 — EV (Sigenergy DC charger + Tessie)

| Card | Entity (live) | Demo |
|------|---------------|------|
| Garage Model S | Tessie | `sensor.garage_model_s_*` |
| Garage Model X | Tessie when added | `sensor.garage_model_x_*` |

## Rebuilding backgrounds (agent / maintainer)

**Locked by default** — see note at top. When the user asks to adjust sky or weather grades:

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/solar-dashboard/scripts/build_v4_backgrounds.py \
  --out /Users/topexnative/Projects/unraid-array-design/home-assistant/solar-dashboard/www/solar-dashboard/backgrounds/v14
```

Bump the Lovelace cache-bust query (`?v=…`) in `lovelace/dashboards/solar_dashboard.yaml`, then redeploy with `scripts/deploy_to_ha.py --skip-restart`.

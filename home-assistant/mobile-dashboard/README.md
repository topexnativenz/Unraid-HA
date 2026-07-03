# Mobile Home dashboard

Lovelace dashboard `mobile-home` (storage: `.storage/lovelace.mobile_home`).

**Flux UI (MD3):** A parallel dashboard with the same Home-tab entities lives in [`../flux-ui-dashboard/`](../flux-ui-dashboard/). Deploy does not change Mobile Home.

## Layout (2026-05-25)

| Tab | Contents |
|-----|----------|
| **Home** | Climate chips/graph, Quick Actions (gate + 3 garage pulse buttons + all off + goodnight), favourite lights |
| **Tesla** | Model S controls (moved off Home) |
| **Cameras** | Eufy picture-glance cameras |
| **Lights** | Grouped by room/area + “currently on” filter |

Removed from Home: Calendar, To-Do, Tesla, Cameras, full Lights list, Sonos, Vacuum, Shopping list, Latest on Plex. Removed **Music** view from this dashboard; standalone Music dashboard hidden from sidebar.

## Deploy (required: WebSocket API)

Editing `.storage/lovelace.mobile_home` over Samba **does not** update a running HA instance. Use:

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/mobile-dashboard/scripts/deploy_mobile_home.py
```

This rebuilds the config, writes storage on disk, then calls `lovelace/config/save` for `mobile-home`.

After deploy: **force-quit** the Home Assistant app and reopen (or open `http://192.168.1.239:8123/mobile-home/home` in a browser).

Garage buttons require `home-assistant/garage-doors/packages/garage_doors_pulse.yaml` on HA (pulse + tracked open state). Deploy with `garage-doors/scripts/deploy_garage_doors_pulse.sh` before first use.

## Default dashboard (iOS Companion → Mobile Home)

HA **2026.2+** added a built-in **Overview** (“Welcome Dave”, summaries, areas). The iOS Companion app often opens that screen even when you picked **Mobile Home** in profile — a known frontend/iOS issue (especially after the second app open or a network change).

### Server-side default (all users)

Already applied on your instance: system `default_panel` = `mobile-home`.

Re-apply anytime:

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/mobile-dashboard/scripts/set_mobile_home_default.py
```

In the HA web UI: **Settings → Dashboards → Mobile Home → ⋮ → Set as default** (system-wide).

### iPhone Companion (required)

Do **all** of these — profile alone is not enough on iOS:

1. **Profile → Dashboard** → choose **Mobile Home** (not **Auto**).
2. **Settings → Dashboards → Mobile Home** → **Set as default on this device**.
3. **App Configuration → Debugging → Reset Frontend Cache**, then force-quit and reopen the app.

Direct link (Safari or after cache reset): `http://192.168.1.239:8123/mobile-home/home`

Shortcut / automation deep link: `homeassistant://navigate/mobile-home/home`

### If it still opens Overview

- Confirm **Overview** stays hidden: profile **sidebar** settings (you already hide `lovelace`).
- Dwains Dashboard was removed 2026-05-27 (was interfering with default dashboard on iOS).
- Track [HA frontend #29523](https://github.com/home-assistant/frontend/issues/29523) — workaround is system default + device default + cache reset.

There is **no** supported way to delete the built-in Overview; only hide it and set another dashboard as default.

## Favourite lights (Home tab)

1. `light.kitchen` — Kitchen
2. `light.dining_room` — Kitchen dining
3. `light.main_atrium` — Main area
4. `light.garage` — Garage
5. `light.entry_centre` — Entry
6. `light.main_footlights` — Hall footlights
7. `light.all_lights` — All lights
8. `light.living_center` — Living

Change `TOP_FIVE` in `scripts/build_mobile_home.py` to reorder.

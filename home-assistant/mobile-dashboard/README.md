# Mobile Home dashboard

Lovelace dashboard `mobile-home` (storage: `.storage/lovelace.mobile_home`).

## Layout (2026-05-25)

| Tab | Contents |
|-----|----------|
| **Home** | Climate chips/graph, Quick Actions (gate + 4 garage doors + all off + goodnight), top 5 favourite lights |
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

## Favourite lights (Home tab)

1. `light.kitchen`
2. `light.entry_centre`
3. `light.main_footlights`
4. `light.all_lights`
5. `light.living_center`

Change `TOP_FIVE` in `scripts/build_mobile_home.py` to reorder.

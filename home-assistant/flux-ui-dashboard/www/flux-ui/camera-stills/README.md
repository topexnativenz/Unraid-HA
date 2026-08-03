# Camera tile backgrounds

Branded animated WebP stills (name-themed), used on Flux UI tablet overview
tiles instead of live `camera.snapshot` JPEGs.

| File | Camera |
|------|--------|
| `back_courtyard_fluent.webp` | Back Courtyard |
| `side_door.webp` | Driveway |
| `side_of_house.webp` | Side of House |
| `garage_door.webp` | Garage Door |
| `front_door_doorbell.webp` | Front door Doorbell |

Source illustrations: `sources/cam-*.png`

Regenerate:

```bash
python3 scripts/generate_camera_stills.py
```

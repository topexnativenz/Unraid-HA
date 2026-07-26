#!/usr/bin/env python3
"""Keep only the used Eufy cameras enabled; disable unused Eufy camera devices.

Driveway (camera.side_door) is the primary outdoor Eufy feed for Flux UI.
Front door Doorbell + Garage Door stay enabled for the tablet overview row.
Indoor / unused outdoor Eufy cameras are disabled (user) to cut clutter.

Usage:
  python3 fix_eufy_cameras.py
  python3 fix_eufy_cameras.py --ha-url URL --token TOKEN
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import DEFAULT_HA, get_token  # noqa: E402

try:
    import websockets
except ImportError as exc:  # pragma: no cover
    raise SystemExit("websockets package required") from exc

# Enabled Eufy camera device names (HA device registry name / name_by_user).
KEEP_ENABLED = {
    "Driveway",
    "Front door Doorbell",
    "Garage Door",
}

# Explicitly disable these Eufy camera device names when present.
DISABLE_EUFY_CAMERAS = {
    "Front Yard",
    "Side of House",
    "Clubrooms 1",
    "Showroom 1",
}

# Leftover generic RTSP driveway (replaced by Eufy Driveway + Reolink).
DISABLE_OTHER = {
    "Home_Driveway",
}


async def _ws_call(ws, mid: int, msg_type: str, **kwargs) -> tuple[int, dict]:
    msg = {"id": mid, "type": msg_type, **kwargs}
    await ws.send(json.dumps(msg))
    while True:
        raw = json.loads(await ws.recv())
        if raw.get("id") == mid:
            return mid + 1, raw


async def fix_eufy_cameras(token: str, ha_url: str) -> int:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            print(f"ERROR: HA auth failed: {auth}", file=sys.stderr)
            return 1

        mid = 1
        mid, dr = await _ws_call(ws, mid, "config/device_registry/list")
        if not dr.get("success"):
            print(f"ERROR: device registry list failed: {dr.get('error')}", file=sys.stderr)
            return 1

        changed = 0
        for device in dr.get("result") or []:
            name = device.get("name_by_user") or device.get("name") or ""
            mfg = (device.get("manufacturer") or "").lower()
            model = device.get("model") or ""
            ids = str(device.get("identifiers"))
            is_eufy = "eufy" in mfg or "eufy" in ids
            is_camera_model = model.startswith("T8")  # T8160 / T8161 / T8210…
            device_id = device["id"]
            disabled_by = device.get("disabled_by")

            if name in DISABLE_OTHER and not disabled_by:
                mid, res = await _ws_call(
                    ws, mid, "config/device_registry/update",
                    device_id=device_id, disabled_by="user",
                )
                print(f"  disabled leftover {name!r}: success={res.get('success')}")
                changed += int(bool(res.get("success")))
                continue

            if not is_eufy or not is_camera_model:
                continue

            if name in DISABLE_EUFY_CAMERAS and not disabled_by:
                mid, res = await _ws_call(
                    ws, mid, "config/device_registry/update",
                    device_id=device_id, disabled_by="user",
                )
                print(f"  disabled unused Eufy camera {name!r}: success={res.get('success')}")
                changed += int(bool(res.get("success")))
            elif name in KEEP_ENABLED and disabled_by == "user":
                mid, res = await _ws_call(
                    ws, mid, "config/device_registry/update",
                    device_id=device_id, disabled_by=None,
                )
                print(f"  re-enabled Eufy camera {name!r}: success={res.get('success')}")
                changed += int(bool(res.get("success")))
            elif name in KEEP_ENABLED:
                print(f"  keep enabled: {name!r}")
            elif is_camera_model and name not in KEEP_ENABLED and not disabled_by:
                # Any other Eufy camera model not on the keep list.
                mid, res = await _ws_call(
                    ws, mid, "config/device_registry/update",
                    device_id=device_id, disabled_by="user",
                )
                print(f"  disabled other Eufy camera {name!r}: success={res.get('success')}")
                changed += int(bool(res.get("success")))

        mid, er = await _ws_call(ws, mid, "config/entity_registry/list")
        print("\nCamera entities:")
        for ent in sorted(er.get("result") or [], key=lambda e: e["entity_id"]):
            if not ent["entity_id"].startswith("camera."):
                continue
            if ent.get("platform") not in ("eufy_security", "reolink", "generic"):
                continue
            flag = "DISABLED" if ent.get("disabled_by") else "active"
            print(f"  [{flag}] {ent['entity_id']} ({ent.get('platform')})")

        print(f"\nDone ({changed} device update(s)).")
        return 0


def _resolve_ha(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve HA URL + token (supports cloud-agent Nabu Casa env injection)."""
    import os

    if args.token:
        return args.ha_url, args.token.strip()
    for key, value in os.environ.items():
        if "nabu.casa" in key and isinstance(value, str) and value.startswith("eyJ"):
            return key, value
    return args.ha_url, get_token(None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()
    ha_url, token = _resolve_ha(args)
    return asyncio.run(fix_eufy_cameras(token, ha_url))


if __name__ == "__main__":
    raise SystemExit(main())

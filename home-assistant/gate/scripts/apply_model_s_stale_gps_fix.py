#!/usr/bin/env python3
"""Push Model S = Model X-aligned gate/garage automations to live Home Assistant."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATE_YAML = ROOT / "automations" / "gate.yaml"
WATCHDOG_YAML = ROOT / "automations" / "model_s_watchdog.yaml"
GARAGE_YAML = ROOT.parent / "garage-doors" / "automations" / "garage.yaml"

UPDATE_IDS = {
    "gate_begin_departure",
    "gate_end_departure",
    "gate_clear_exit_on_approach",
    "gate_open_tesla_departure",
    "model_s_refresh_approach_while_driving",
    "gate_tessie_wake_while_away",
    "gate_model_s_mark_away",
    "gate_model_s_clear_away",
    "gate_model_x_clear_away",
    "gate_end_arrival_session",
    "gate_open_on_arrival",
    "gate_open_on_arrival_model_x",
    "house_garage_open_on_tessie_arrival",
    "house_garage_open_on_gate_session",
    "garage_outside_lights_on_tessie_arrival_after_dark",
    "model_s_watchdog_gps_frozen",
    "model_s_watchdog_arrival_miss",
    "model_s_watchdog_departure_miss",
    "model_s_watchdog_entities_unavailable",
}


def load_docs(path: Path) -> list[dict]:
    docs = list(yaml.safe_load_all(path.read_text()))
    items: list[dict] = []
    for doc in docs:
        if isinstance(doc, list):
            items.extend(doc)
        elif isinstance(doc, dict):
            items.append(doc)
    return items


def get_json(ha: str, token: str, path: str) -> tuple[int, str]:
    req = urllib.request.Request(
        f"{ha}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def seed_home_odometer(ha: str, token: str) -> None:
    """Create input_number.model_s_home_odometer if needed and seed it once."""
    status, body = get_json(ha, token, "/api/states/input_number.model_s_home_odometer")
    if status == 200:
        state = json.loads(body).get("state")
        print(f"model_s_home_odometer already {state}")
        try:
            if float(state) > 0:
                return
        except ValueError:
            pass
    else:
        import asyncio
        import websockets

        async def create() -> None:
            ws_url = ha.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
            async with websockets.connect(ws_url, max_size=2_000_000) as ws:
                await ws.recv()
                await ws.send(json.dumps({"type": "auth", "access_token": token}))
                auth = json.loads(await ws.recv())
                if auth.get("type") != "auth_ok":
                    raise RuntimeError(auth)
                payload = {
                    "id": 1,
                    "type": "input_number/create",
                    "name": "Model S home odometer",
                    "min": 0,
                    "max": 1000000,
                    "step": 0.1,
                    "mode": "box",
                    "unit_of_measurement": "km",
                    "icon": "mdi:counter",
                }
                await ws.send(json.dumps(payload))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == 1:
                        print("input_number/create", json.dumps(msg)[:400])
                        if not msg.get("success"):
                            raise RuntimeError(msg)
                        return

        asyncio.run(create())

    odo_status, odo_body = get_json(ha, token, "/api/states/sensor.model_s_p100d_odometer")
    if odo_status != 200:
        print(f"odometer read failed HTTP {odo_status}")
        return
    odo = float(json.loads(odo_body)["state"])
    seeded = round(odo, 1)
    status, body = post(
        ha,
        token,
        "/api/services/input_number/set_value",
        {"entity_id": "input_number.model_s_home_odometer", "value": seeded},
    )
    print(f"seeded model_s_home_odometer={seeded} from live odometer HTTP {status} {body[:120]}")


def post(ha: str, token: str, path: str, payload: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        f"{ha}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def main() -> int:
    ha = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    if not ha or not token:
        print("HA_URL and HA_TOKEN are required", file=sys.stderr)
        return 2

    seed_home_odometer(ha, token)

    autos = load_docs(GATE_YAML) + load_docs(GARAGE_YAML) + load_docs(WATCHDOG_YAML)
    selected = [a for a in autos if a.get("id") in UPDATE_IDS]
    missing = UPDATE_IDS - {a.get("id") for a in selected}
    if missing:
        print(f"missing automation ids in YAML: {sorted(missing)}", file=sys.stderr)
        return 1

    failed = 0
    for auto in selected:
        aid = auto["id"]
        status, body = post(ha, token, f"/api/config/automation/config/{aid}", auto)
        print(f"{aid}: HTTP {status} {body[:200]}")
        if status not in (200, 201):
            failed += 1

    reload_status, reload_body = post(
        ha, token, "/api/services/automation/reload", {}
    )
    print(f"automation.reload: HTTP {reload_status} {reload_body[:200]}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

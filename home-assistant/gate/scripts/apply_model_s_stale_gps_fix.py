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
GARAGE_YAML = ROOT.parent / "garage-doors" / "automations" / "garage.yaml"

UPDATE_IDS = {
    "gate_begin_departure",
    "gate_end_departure",
    "gate_clear_exit_on_approach",
    "gate_open_tesla_departure",
    "gate_tessie_wake_while_away",
    "gate_model_s_mark_away",
    "gate_model_s_clear_away",
    "gate_end_arrival_session",
    "gate_open_on_arrival",
    "house_garage_open_on_tessie_arrival",
    "garage_outside_lights_on_tessie_arrival_after_dark",
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

    autos = load_docs(GATE_YAML) + load_docs(GARAGE_YAML)
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

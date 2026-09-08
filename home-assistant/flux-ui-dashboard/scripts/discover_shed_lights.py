#!/usr/bin/env python3
"""Discover shed / workshop light entities on Home Assistant.

Matches light.* entities whose entity_id or friendly_name contains shed/workshop
keywords, then optionally writes them to entities.yaml (shed_lights) and the
Shed All group package.

Examples:
  python3 home-assistant/flux-ui-dashboard/scripts/discover_shed_lights.py
  python3 home-assistant/flux-ui-dashboard/scripts/discover_shed_lights.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
PACKAGE = ROOT / "packages" / "flux_ui_area_lights.yaml"

KEYWORDS = ("shed", "workshop", "barn", "outbuilding")
EXCLUDE = ("all_lights", "ground_floor", "night_arrival")


def get_token() -> str:
    if os.environ.get("HA_TOKEN"):
        return os.environ["HA_TOKEN"]
    for path in (Path.home() / ".cursor" / "mcp.json", Path("/Users/topexnative/.cursor/mcp.json")):
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        ha = (data.get("mcpServers") or {}).get("homeassistant") or {}
        auth = (ha.get("headers") or {}).get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth.split(" ", 1)[1]
    raise SystemExit("No HA token — set HA_TOKEN or provide ~/.cursor/mcp.json")


def normalize_url(url: str) -> str:
    url = url.rstrip("/")
    for suffix in ("/mcp_server/sse", "/api/mcp/sse", "/sse"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url.rstrip("/")


def fetch_states(ha_url: str, token: str) -> list[dict]:
    req = urllib.request.Request(
        f"{ha_url}/api/states",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.load(resp)


def score_light(eid: str, name: str) -> int:
    hay = f"{eid} {name}".lower()
    if any(x in hay for x in EXCLUDE):
        return -1
    score = 0
    for kw in KEYWORDS:
        if kw in hay:
            score += 10
    if "main" in hay and "shed" in hay:
        score += 5
    if "second" in hay and "shed" in hay:
        score += 4
    return score


def discover(states: list[dict]) -> list[dict]:
    found: list[tuple[int, dict]] = []
    for st in states:
        eid = st.get("entity_id", "")
        if not eid.startswith("light."):
            continue
        fn = (st.get("attributes") or {}).get("friendly_name") or eid
        sc = score_light(eid, fn)
        if sc <= 0:
            continue
        found.append((sc, {"entity": eid, "name": _short_name(fn, eid)}))
    found.sort(key=lambda x: (-x[0], x[1]["name"].lower()))
    # Prefer at most 4 shed lights for favourite buttons.
    return [item for _, item in found[:4]]


def _short_name(fn: str, eid: str) -> str:
    name = fn.strip()
    for prefix in ("Light ", "Lights "):
        if name.lower().startswith(prefix.lower()):
            name = name[len(prefix) :]
    if len(name) > 28:
        name = eid.split(".", 1)[-1].replace("_", " ").title()
    return name


def apply_entities(lights: list[dict]) -> None:
    import yaml

    data = yaml.safe_load(ENTITIES.read_text()) or {}
    data["shed_lights"] = lights
    ENTITIES.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    print(f"Updated {ENTITIES} shed_lights ({len(lights)})")


def apply_package(lights: list[dict]) -> None:
    if not lights or not PACKAGE.exists():
        return
    text = PACKAGE.read_text()
    entities_block = "\n".join(f"      - {item['entity']}" for item in lights)
    pattern = re.compile(
        r"(name: Shed All\n(?:.*\n)*?entities:\n)(?:      - light\.[^\n]+\n)+",
        re.M,
    )
    replacement = r"\1" + entities_block + "\n"
    new_text, n = pattern.subn(replacement, text, count=1)
    if n:
        PACKAGE.write_text(new_text)
        print(f"Updated {PACKAGE} Shed All group members")
    else:
        print(f"WARNING: could not rewrite Shed All entities in {PACKAGE}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover shed light entities")
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", "http://192.168.1.239:8123"))
    parser.add_argument("--token", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    token = args.token or get_token()
    ha_url = normalize_url(args.ha_url)
    try:
        states = fetch_states(ha_url, token)
    except urllib.error.URLError as exc:
        print(f"Cannot reach HA at {ha_url}: {exc}", file=sys.stderr)
        return 1
    lights = discover(states)
    if not lights:
        print("No shed/workshop lights found. Keeping configured shed_lights defaults.")
        return 0
    print(f"Found {len(lights)} shed light(s):")
    for item in lights:
        print(f"  {item['entity']:<40} {item['name']}")
    if args.apply:
        apply_entities(lights)
        apply_package(lights)
    else:
        print("Dry run — pass --apply to write entities.yaml + package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

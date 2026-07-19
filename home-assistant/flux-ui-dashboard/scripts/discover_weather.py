#!/usr/bin/env python3
"""Discover NZ MetService weather + sensors in HA and wire the Flux UI weather panel.

No local weather station required — all data comes from the MetService HACS integration
(ciejer/metservice-weather) via weather.get_forecasts and integration sensors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
OVERVIEW_TABS = ROOT / "overview_tabs.yaml"
WEATHER_PANEL = ROOT / "weather_panel.yaml"
GENERATE_PKG = ROOT / "scripts" / "generate_weather_package.py"

sys.path.insert(0, str(ROOT / "scripts"))
from ha_common import DEFAULT_HA, get_token  # noqa: E402

METSERVICE_HINT = re.compile(r"metservice|met service", re.I)
ATTRIBUTION_HINT = re.compile(r"metservice|met service", re.I)
# Never treat these as MetService weather sensors (false suffix matches).
SENSOR_BLOCKLIST = re.compile(r"growatt|battery|inverter|solar|spf_", re.I)

# MetService integration sensor suffixes (entity_id ends with these after location slug)
SENSOR_SUFFIXES: dict[str, list[str]] = {
    "uv": ["uv_index", "uv_alert"],
    "warnings": ["metservice_weather_warnings", "weather_warnings"],
    "humidity": ["relative_humidity"],
    "wind_speed": ["wind_speed"],
    "wind_direction": ["wind_direction"],
    "temperature": ["temperature"],
}


def api_get(token: str, ha_url: str, path: str) -> Any:
    req = urllib.request.Request(
        f"{ha_url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_states(token: str, ha_url: str) -> list[dict]:
    return api_get(token, ha_url, "/api/states")


def fetch_ha_config(token: str, ha_url: str) -> dict:
    return api_get(token, ha_url, "/api/config")


def score_weather(state: dict) -> int:
    eid = state["entity_id"]
    if not eid.startswith("weather."):
        return -1
    attrs = state.get("attributes") or {}
    fn = str(attrs.get("friendly_name") or "")
    attribution = str(attrs.get("attribution") or "")
    score = 0
    if METSERVICE_HINT.search(eid) or METSERVICE_HINT.search(fn) or ATTRIBUTION_HINT.search(attribution):
        score += 100
    if eid == "weather.metservice":
        score += 50
    if "forecast_home" in eid or "met_no" in eid or eid == "weather.home":
        score -= 40
    return score


def pick_metservice_weather(states: list[dict]) -> dict | None:
    candidates: list[tuple[int, dict]] = []
    for state in states:
        score = score_weather(state)
        if score >= 0:
            candidates.append((score, state))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1]["entity_id"]))
    return candidates[0][1]


def weather_location_slug(weather_entity: str, weather_state: dict) -> str | None:
    """Best-effort location prefix for MetService sensor entity_ids."""
    fn = str((weather_state.get("attributes") or {}).get("friendly_name") or "")
    # "Hamilton Forecast" -> hamilton
    base = re.sub(r"\s+forecast\s*$", "", fn, flags=re.I).strip()
    if base:
        return re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
    eid = weather_entity.removeprefix("weather.")
    if eid != "metservice":
        return eid
    return None


def find_metservice_sensor(
    states: list[dict],
    *,
    slug: str | None,
    suffix_keys: list[str],
) -> str | None:
    """Find a MetService integration sensor by suffix, scoped to the weather location slug."""
    if not slug:
        return None

    prefix = f"sensor.{slug}_"
    ranked: list[tuple[int, str]] = []

    for state in states:
        eid = state["entity_id"]
        if not eid.startswith("sensor."):
            continue
        if SENSOR_BLOCKLIST.search(eid):
            continue
        attrs = state.get("attributes") or {}
        fn = str(attrs.get("friendly_name") or "")

        matched_suffix = next((s for s in suffix_keys if eid.endswith(f"_{s}")), None)
        if not matched_suffix:
            continue

        if eid.startswith(prefix):
            ranked.append((0, eid))
        elif "metservice" in eid.lower():
            ranked.append((1, eid))
        elif METSERVICE_HINT.search(fn):
            ranked.append((2, eid))

    if not ranked:
        return None
    ranked.sort(key=lambda x: (x[0], x[1]))
    return ranked[0][1]


def discover_metservice_sensors(states: list[dict], weather_entity: str, weather_state: dict) -> dict[str, str]:
    slug = weather_location_slug(weather_entity, weather_state)
    found: dict[str, str] = {}
    for key, suffixes in SENSOR_SUFFIXES.items():
        eid = find_metservice_sensor(states, slug=slug, suffix_keys=suffixes)
        if eid:
            found[key] = eid
    return found


def update_yaml_value(path: Path, updates: dict[str, Any], *, root_key: str | None = None) -> bool:
    if not path.exists():
        return False
    data = yaml.safe_load(path.read_text()) or {}
    target = data if root_key is None else data.setdefault(root_key, {})
    changed = False
    for key, value in updates.items():
        if target.get(key) != value:
            target[key] = value
            changed = True
    if changed:
        path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    return changed


def update_weather_panel(
    weather_entity: str,
    sensors: dict[str, str],
    location: dict[str, Any],
) -> bool:
    if not WEATHER_PANEL.exists():
        return False
    data = yaml.safe_load(WEATHER_PANEL.read_text()) or {}
    changed = False

    if data.get("weather_entity") != weather_entity:
        data["weather_entity"] = weather_entity
        changed = True

    ms = data.setdefault("metservice", {})
    if ms.get("weather_entity") != weather_entity:
        ms["weather_entity"] = weather_entity
        changed = True

    ms_sensors = ms.setdefault("sensors", {})
    for key, eid in sensors.items():
        if ms_sensors.get(key) != eid:
            ms_sensors[key] = eid
            changed = True

    warnings = sensors.get("warnings")
    if warnings and data.get("warnings_entity") != warnings:
        data["warnings_entity"] = warnings
        changed = True

    loc = data.setdefault("location", {})
    for k, v in location.items():
        if v is not None and loc.get(k) != v:
            loc[k] = v
            changed = True

    if changed:
        WEATHER_PANEL.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    token = get_token(args.token)
    states = fetch_states(token, args.ha_url)
    ha_cfg = fetch_ha_config(token, args.ha_url)
    picked_state = pick_metservice_weather(states)

    weather_entities = sorted(s["entity_id"] for s in states if s["entity_id"].startswith("weather."))
    print("Weather entities in HA:")
    for eid in weather_entities:
        st = next(s for s in states if s["entity_id"] == eid)
        fn = (st.get("attributes") or {}).get("friendly_name") or "—"
        mark = " ← selected" if picked_state and eid == picked_state["entity_id"] else ""
        print(f"  {eid:<40} {fn}{mark}")

    if not picked_state:
        print("\nWARNING: No MetService weather entity found.")
        print("Install HACS integration: https://github.com/ciejer/metservice-weather")
        print("Then add via Settings → Devices & services → MetService New Zealand Weather")
        return 1

    weather_entity = picked_state["entity_id"]
    sensors = discover_metservice_sensors(states, weather_entity, picked_state)
    location = {
        "latitude": ha_cfg.get("latitude"),
        "longitude": ha_cfg.get("longitude"),
        "country": "New Zealand",
    }

    print(f"\nMetService weather: {weather_entity}")
    print("MetService sensors:")
    if sensors:
        for key, eid in sorted(sensors.items()):
            print(f"  {key:<16} {eid}")
    else:
        print("  (none matched — integration may still be loading; forecasts use weather.get_forecasts)")

    print(f"\nHome coordinates: {location.get('latitude')}, {location.get('longitude')}")

    if not args.apply:
        print("\nDry run — re-run with --apply to update YAML + regenerate flux_ui_weather package")
        return 0

    changed = update_yaml_value(ENTITIES, {"weather": weather_entity})
    # Keep tablet outdoor chip on the same live weather entity.
    if ENTITIES.exists():
        ent = yaml.safe_load(ENTITIES.read_text()) or {}
        tablet = ent.setdefault("tablet", {})
        if tablet.get("outdoor_temperature") != weather_entity:
            tablet["outdoor_temperature"] = weather_entity
            ENTITIES.write_text(yaml.safe_dump(ent, sort_keys=False, default_flow_style=False))
            changed = True
    if OVERVIEW_TABS.exists():
        ot = yaml.safe_load(OVERVIEW_TABS.read_text()) or {}
        if ot.get("events", {}).get("weather_entity") != weather_entity:
            ot.setdefault("events", {})["weather_entity"] = weather_entity
            OVERVIEW_TABS.write_text(yaml.safe_dump(ot, sort_keys=False, default_flow_style=False))
            changed = True

    changed = update_weather_panel(weather_entity, sensors, location) or changed

    import subprocess

    subprocess.run(
        [sys.executable, str(GENERATE_PKG), "--weather-entity", weather_entity],
        check=True,
    )
    print("\nUpdated MetService wiring + regenerated packages/flux_ui_weather.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

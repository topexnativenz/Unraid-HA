#!/usr/bin/env python3
"""Generate packages/flux_ui_weather.yaml — MetService template sensors for Flux UI weather panel."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
WEATHER_PANEL = ROOT / "weather_panel.yaml"
TEMPLATE = ROOT / "templates" / "flux_ui_weather.package.yaml"
OUT = ROOT / "packages" / "flux_ui_weather.yaml"

PLACEHOLDERS = {
    "__WEATHER_ENTITY__": "weather.metservice",
    "__UV_SENSOR__": "sensor.unknown",
    "__HUMIDITY_SENSOR__": "sensor.unknown",
    "__WIND_SPEED_SENSOR__": "sensor.unknown",
    "__WIND_DIRECTION_SENSOR__": "sensor.unknown",
    "__TEMPERATURE_SENSOR__": "sensor.unknown",
    "__WARNINGS_SENSOR__": "sensor.unknown",
}


def load_panel_config() -> dict:
    if not WEATHER_PANEL.exists():
        return {}
    return yaml.safe_load(WEATHER_PANEL.read_text()) or {}


def load_weather_entity(panel: dict) -> str:
    ms = panel.get("metservice") or {}
    if ms.get("weather_entity"):
        return str(ms["weather_entity"])
    if panel.get("weather_entity"):
        return str(panel["weather_entity"])
    if ENTITIES.exists():
        cfg = yaml.safe_load(ENTITIES.read_text()) or {}
        if cfg.get("weather"):
            return str(cfg["weather"])
    return "weather.metservice"


def sensor_map(panel: dict, weather: str) -> dict[str, str]:
    ms = panel.get("metservice") or {}
    discovered = ms.get("sensors") or {}
    # Sensible fallbacks: use weather entity attributes when dedicated sensor not discovered
    return {
        "__WEATHER_ENTITY__": weather,
        "__UV_SENSOR__": discovered.get("uv") or weather,
        "__HUMIDITY_SENSOR__": discovered.get("humidity") or weather,
        "__WIND_SPEED_SENSOR__": discovered.get("wind_speed") or weather,
        "__WIND_DIRECTION_SENSOR__": discovered.get("wind_direction") or weather,
        "__TEMPERATURE_SENSOR__": discovered.get("temperature") or weather,
        "__WARNINGS_SENSOR__": discovered.get("warnings") or panel.get("warnings_entity") or "sensor.unknown",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weather-entity", default=None)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    panel = load_panel_config()
    weather = args.weather_entity or load_weather_entity(panel)
    mapping = sensor_map(panel, weather)

    template = TEMPLATE.read_text()
    for key, default in PLACEHOLDERS.items():
        template = template.replace(key, mapping.get(key, default))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template)
    print(f"Wrote {args.output}")
    print(f"  weather: {mapping['__WEATHER_ENTITY__']}")
    for k in ("__UV_SENSOR__", "__HUMIDITY_SENSOR__", "__WIND_SPEED_SENSOR__", "__WARNINGS_SENSOR__"):
        if mapping.get(k) and mapping[k] != "sensor.unknown":
            print(f"  {k.strip('_')}: {mapping[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

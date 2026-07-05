#!/usr/bin/env python3
"""Generate packages/flux_ui_weather.yaml — ElementZoom weather template sensors for MetService."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTITIES = ROOT / "entities.yaml"
WEATHER_PANEL = ROOT / "weather_panel.yaml"
TEMPLATE = ROOT / "templates" / "flux_ui_weather.package.yaml"
OUT = ROOT / "packages" / "flux_ui_weather.yaml"
PLACEHOLDER = "__WEATHER_ENTITY__"


def load_weather_entity() -> str:
    if WEATHER_PANEL.exists():
        wp = yaml.safe_load(WEATHER_PANEL.read_text()) or {}
        if wp.get("weather_entity"):
            return str(wp["weather_entity"])
    if ENTITIES.exists():
        cfg = yaml.safe_load(ENTITIES.read_text()) or {}
        if cfg.get("weather"):
            return str(cfg["weather"])
    return "weather.metservice"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weather-entity", default=None)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    weather = args.weather_entity or load_weather_entity()
    template = TEMPLATE.read_text().replace(PLACEHOLDER, weather)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template)
    print(f"Wrote {args.output} (weather entity: {weather})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

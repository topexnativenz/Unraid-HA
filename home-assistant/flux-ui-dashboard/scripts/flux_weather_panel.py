"""Flux UI weather panel — ElementZoom Material Design 3 mobile dashboard (MetService NZ).

Reference: ElementZoom/Material-Design-3-Dynamic-Mobile-Dashboard assets/weather panel
Requires HACS: bubble-card, simple-tabs, weather-forecast-extended-card, apexcharts-card,
  lunar-phase-card (+ lunar-phase integration), stack-in-card, card-mod (mod-card).
"""

from __future__ import annotations

from typing import Any

WEATHER_PANEL_HASH = "#weather-panel"
FLUX_UI_WEATHER_PANEL_PATH = f"/flux-ui/overview{WEATHER_PANEL_HASH}"

BUBBLE_POPUP_STYLES = """\
#root {
  height: unset !important;
  max-height: 100% !important;
  transition: transform var(--md-sys-motion-expressive-spatial-default) !important;
}
.bubble-header-container {
  --bubble-button-background-color: var(--md-sys-color-on-secondary);
  --bubble-button-icon-background-color: var(--md-sys-color-on-secondary);
}
.bubble-pop-up-container {
  padding-bottom: 64px !important;
}
"""

METSERVICE_CHIP_STYLE = {
    ".": (
        "ha-card {\n"
        "  --text-color: var(--primary-background-color);\n"
        "  --color: var(--primary-background-color);\n"
        "  --chip-background: var(--md-sys-color-primary);\n"
        "}\n"
    )
}

METSERVICE_CHIP_ABSOLUTE = {
    "style": (
        "ha-card {\n"
        "  position: absolute;\n"
        "  top: 20px;\n"
        "  right: 2px;\n"
        "}\n"
    )
}

FORECAST_HEADER_PAD = {
    "style": "ha-card {\n  padding-right: 120px;\n}\n"
}


def _panel_cfg(cfg: dict) -> dict:
    wp = cfg.get("weather_panel") or {}
    ms = wp.get("metservice") or {}
    entities = wp.get("entities") or {}
    ms_sensors = ms.get("sensors") or {}
    loc = wp.get("location") or {}
    weather = ms.get("weather_entity") or wp.get("weather_entity") or cfg.get("weather", "weather.metservice")
    warnings = wp.get("warnings_entity") or ms_sensors.get("warnings")

    def _live(key: str, fallback: str) -> str:
        return str(ms_sensors.get(key) or fallback)

    live = {
        "uv": _live("uv", weather),
        "humidity": _live("humidity", weather),
        "temperature": _live("temperature", weather),
        "wind_speed": _live("wind_speed", weather),
        "wind_direction": _live("wind_direction", weather),
    }

    return {
        "enabled": wp.get("enabled", True),
        "weather": weather,
        "source_label": wp.get("source_label", "MetService"),
        "source_url": wp.get("source_url", "https://www.metservice.com/warnings/home"),
        "location": loc,
        "aqi_entity": wp.get("aqi_entity"),
        "aqi_pollutant_entity": wp.get("aqi_pollutant_entity"),
        "warnings_entity": warnings,
        "metservice_sensors": ms_sensors,
        "live": live,
        "entities": {
            "hourly": entities.get("hourly_forecast", "sensor.flux_ui_hourly_forecast_full"),
            "daily": entities.get("daily_forecast", "sensor.flux_ui_daily_forecast_data"),
            "next_rain": entities.get("next_rain_summary", "sensor.flux_ui_next_rain_summary"),
            "rain_summary": entities.get("rainfall_summary", "sensor.flux_ui_24h_rainfall_summary"),
            "uv_cloud": entities.get("uv_cloud_summary", "sensor.flux_ui_uv_and_cloud_summary"),
            "wind_summary": entities.get("wind_summary", "sensor.flux_ui_wind_summary"),
            "moon_summary": entities.get("moon_summary", "sensor.flux_ui_moon_summary"),
            "rain": entities.get("forecast_rainfall", "sensor.flux_ui_forecast_rainfall"),
            "temp": entities.get("forecast_temperature", "sensor.flux_ui_forecast_temperature"),
            "uv": entities.get("forecast_uv_index", "sensor.flux_ui_forecast_uv_index"),
            "cloud": entities.get("forecast_cloud_coverage", "sensor.flux_ui_forecast_cloud_coverage"),
            "wind_speed": entities.get("forecast_wind_speed", "sensor.flux_ui_forecast_wind_speed"),
            "wind_dir": entities.get("forecast_wind_direction", "sensor.flux_ui_forecast_wind_direction"),
        },
    }


def weather_panel_enabled(cfg: dict) -> bool:
    return bool(_panel_cfg(cfg).get("enabled", True))


def _metservice_chip(label: str, url: str) -> dict:
    return {
        "type": "custom:mushroom-chips-card",
        "alignment": "center",
        "chips": [
            {
                "type": "template",
                "icon": "mdi:weather-lightning",
                "content": label,
                "tap_action": {"action": "url", "url_path": url},
                "card_mod": {"style": METSERVICE_CHIP_STYLE},
            }
        ],
    }


def _title_subtitle(title: str, subtitle: str) -> dict:
    """ElementZoom streamline title_subtitle_card equivalent."""
    return {
        "type": "custom:mushroom-title-card",
        "title": title,
        "subtitle": subtitle,
    }


def _temp_color_template(weather: str) -> str:
    return (
        "{% set current = state_attr('" + weather + "', 'temperature') | float(0) %}"
        "{% if current < 16 %}#CEB2F5"
        "{% elif current < 18 %}#5EBDEE"
        "{% elif current < 22 %}#9cc8b8"
        "{% elif current < 24 %}#e7b562"
        "{% elif current < 27 %}#FF564B"
        "{% else %}#99332d{% endif %}"
    )


def _apex_base() -> dict[str, Any]:
    return {
        "graph_span": "24h",
        "span": {"start": "hour"},
        "now": {"show": True},
        "apex_config": {
            "chart": {"height": 240},
            "legend": {"show": True},
            "grid": {"yaxis": {"lines": {"show": False}}},
            "xaxis": {"crosshairs": {"show": False}, "tooltip": {"enabled": False}},
        },
    }


def _forecasts_js() -> str:
    """Read MetService online forecast from weather entity (forecast_hourly attribute)."""
    return (
        "let forecasts = [];\n"
        "const raw = entity.attributes.forecast_hourly ?? entity.attributes.forecasts;\n"
        "if (typeof raw === 'string') { try { forecasts = JSON.parse(raw || '[]'); } catch (e) { forecasts = []; } }\n"
        "else if (Array.isArray(raw)) forecasts = raw;\n"
        "if (!forecasts.length) return [];\n"
        "forecasts = forecasts.map(f => ({\n"
        "  datetime: f.datetime || f.time,\n"
        "  temperature: Number(f.temperature ?? f.temp ?? 0),\n"
        "  precipitation: Number(f.precipitation ?? 0),\n"
        "  wind_speed: Number(f.wind_speed ?? 0),\n"
        "  wind_bearing: f.wind_bearing ?? 0,\n"
        "  condition: f.condition || '',\n"
        "  uv_index: f.uv_index,\n"
        "  cloud_coverage: f.cloud_coverage,\n"
        "}));\n"
    )


def _rain_summary_subtitle(w: str) -> str:
    return (
        "{% set fc = state_attr('" + w + "', 'forecast_hourly') %}"
        "{% if fc is string %}{% set fc = fc | from_json %}{% endif %}"
        "{% if fc is iterable and fc | count > 0 %}"
        "{% set values = fc | map(attribute='precipitation') | map('float', default=0) | list %}"
        "{% set total = values | sum %}"
        "{% if total == 0 %}🌤️ Rainfall: None expected in the next 24 hours"
        "{% elif total < 2.5 %}🌦️ Rainfall: {{ total | round(1) }} mm (Light) next 24h"
        "{% elif total < 7.6 %}🌧️ Rainfall: {{ total | round(1) }} mm (Moderate) next 24h"
        "{% elif total < 35 %}⛈️ Rainfall: {{ total | round(1) }} mm (Heavy) next 24h"
        "{% else %}🌊 Rainfall: {{ total | round(1) }} mm (Very heavy) next 24h{% endif %}"
        "{% else %}🌤️ MetService forecast loading…{% endif %}"
    )


def _next_rain_subtitle(w: str) -> str:
    return (
        "{% set fc = state_attr('" + w + "', 'forecast_hourly') %}"
        "{% if fc is string %}{% set fc = fc | from_json %}{% endif %}"
        "{% if fc is iterable and fc | count > 0 %}"
        "{% set rain = fc | selectattr('precipitation','defined') | selectattr('precipitation','gt',0) | list %}"
        "{% if rain | count > 0 %}"
        "{% set n = rain | first %}{% set val = n.precipitation | float %}"
        "{% if val < 2.5 %}🌦️ Light · {{ val | round(1) }} mm · {{ as_datetime(n.datetime).strftime('%a, %b %d at %I:%M %p') }}"
        "{% elif val < 7.6 %}🌧️ Moderate · {{ val | round(1) }} mm · {{ as_datetime(n.datetime).strftime('%a, %b %d at %I:%M %p') }}"
        "{% else %}⛈️ Heavy · {{ val | round(1) }} mm · {{ as_datetime(n.datetime).strftime('%a, %b %d at %I:%M %p') }}{% endif %}"
        "{% else %}🌤️ No rain today{% endif %}"
        "{% else %}🌤️ MetService forecast loading…{% endif %}"
    )


def _uv_summary_subtitle(w: str, uv: str) -> str:
    return (
        "🌤️ UV now: {{ states('" + uv + "') }} · "
        "💧 Humidity from MetService · forecast from {{ state_attr('" + w + "', 'friendly_name') }}"
    )


def _wind_summary_subtitle(w: str) -> str:
    return (
        "{% set fc = state_attr('" + w + "', 'forecast_hourly') %}"
        "{% if fc is string %}{% set fc = fc | from_json %}{% endif %}"
        "{% if fc is iterable and fc | count > 0 %}"
        "{% set speeds = fc | map(attribute='wind_speed') | map('float', default=0) | list %}"
        "💨 Peak wind: {{ speeds | max | round(1) }} {{ state_attr('" + w + "', 'wind_speed_unit') | default('km/h') }} next 24h"
        "{% else %}💨 MetService forecast loading…{% endif %}"
    )


def _cloud_from_condition_js() -> str:
    return (
        "let cloud = 60;\n"
        "const cond = String(f.condition || '').toLowerCase();\n"
        "if (f.cloud_coverage != null) cloud = Number(f.cloud_coverage);\n"
        "else if (['sunny','clear','clear-night'].includes(cond)) cloud = 15;\n"
        "else if (cond.includes('partly')) cloud = 45;\n"
        "else if (['cloudy','fog','foggy'].includes(cond)) cloud = 75;\n"
        "else if (['rainy','pouring','drizzle','snowy'].includes(cond)) cloud = 90;\n"
    )


def _wind_bearing_js() -> str:
    return (
        "const dirs = {N:0,NNE:22.5,NE:45,ENE:67.5,E:90,ESE:112.5,SE:135,SSE:157.5,"
        "S:180,SSW:202.5,SW:225,WSW:247.5,W:270,WNW:292.5,NW:315,NNW:337.5};\n"
        "const b = f.wind_bearing;\n"
        "const bearing = typeof b === 'number' ? b : (dirs[String(b || '').toUpperCase()] ?? 0);\n"
    )


def _rainfall_chart(weather: str) -> dict:
    chart = _apex_base()
    chart["header"] = {"show": True}
    chart["apex_config"]["yaxis"] = [
        {"id": "rain", "title": {"text": "Rain (mm)"}, "opposite": False},
        {"id": "temp", "title": {"text": "Temp (°C)"}, "opposite": True, "decimalsInFloat": 0},
    ]
    chart["series"] = [
        {
            "entity": weather,
            "name": "Rain",
            "type": "column",
            "yaxis_id": "rain",
            "data_generator": (
                _forecasts_js()
                + "return forecasts.map(f => {\n"
                "  let val = Number(f.precipitation) || 0;\n"
                "  let color = '#9e9e9e';\n"
                "  if (val > 0 && val < 2.5) color = '#4FC3F7';\n"
                "  else if (val < 7.6) color = '#0288D1';\n"
                "  else if (val < 35) color = '#01579B';\n"
                "  else color = '#311B92';\n"
                "  return { x: new Date(f.datetime).getTime(), y: val, fillColor: color };\n"
                "});"
            ),
        },
        {
            "entity": weather,
            "name": "Temp",
            "type": "line",
            "curve": "smooth",
            "yaxis_id": "temp",
            "stroke_width": 2,
            "color": "#E53935",
            "data_generator": (
                _forecasts_js()
                + "return forecasts.map(f => ({\n"
                "  x: new Date(f.datetime).getTime(), y: Number(f.temperature) || 0\n"
                "}));"
            ),
        },
    ]
    return {"type": "custom:apexcharts-card", **chart}


def _uv_chart(weather: str) -> dict:
    chart = _apex_base()
    chart["apex_config"]["yaxis"] = [
        {"id": "uv", "title": {"text": "UV Index"}, "opposite": False, "min": 0, "max": 11},
        {"id": "cloud", "title": {"text": "Cloud Coverage (%)"}, "opposite": True, "min": 0, "max": 100},
    ]
    chart["series"] = [
        {
            "entity": weather,
            "name": "UV Index",
            "type": "line",
            "curve": "smooth",
            "yaxis_id": "uv",
            "color": "#F9A825",
            "stroke_width": 2,
            "data_generator": (
                _forecasts_js()
                + "const hourUv = (dt) => { const h = new Date(dt).getHours(); return (h >= 7 && h < 19) ? 3 : 0; };\n"
                "return forecasts.map(f => {\n"
                "  const uv = f.uv_index != null ? Number(f.uv_index) : hourUv(f.datetime);\n"
                "  return { x: new Date(f.datetime).getTime(), y: uv };\n"
                "});"
            ),
        },
        {
            "entity": weather,
            "name": "Cloud Coverage",
            "type": "area",
            "yaxis_id": "cloud",
            "color": "#90CAF9",
            "stroke_width": 1,
            "opacity": 0.3,
            "data_generator": (
                _forecasts_js()
                + "return forecasts.map(f => {\n"
                + _cloud_from_condition_js()
                + "  return { x: new Date(f.datetime).getTime(), y: cloud };\n"
                "});"
            ),
        },
    ]
    return {"type": "custom:apexcharts-card", **chart}


def _wind_chart(weather: str) -> dict:
    chart = _apex_base()
    chart["apex_config"]["yaxis"] = [
        {"id": "speed", "title": {"text": "Wind Speed (km/h)"}, "opposite": False},
        {"id": "direction", "title": {"text": "Direction (°)"}, "opposite": True, "min": 0, "max": 360},
    ]
    chart["series"] = [
        {
            "entity": weather,
            "name": "Speed",
            "type": "line",
            "curve": "smooth",
            "yaxis_id": "speed",
            "color": "#0288D1",
            "stroke_width": 2,
            "data_generator": (
                _forecasts_js()
                + "return forecasts.map(f => ({\n"
                "  x: new Date(f.datetime).getTime(),\n"
                "  y: Math.round((Number(f.wind_speed) || 0) * 10) / 10\n"
                "}));"
            ),
        },
        {
            "entity": weather,
            "name": "Direction",
            "type": "line",
            "curve": "smooth",
            "yaxis_id": "direction",
            "color": "#8E24AA",
            "stroke_width": 1,
            "data_generator": (
                _forecasts_js()
                + "return forecasts.map(f => {\n"
                + _wind_bearing_js()
                + "  return { x: new Date(f.datetime).getTime(), y: Math.round(bearing) };\n"
                "});"
            ),
        },
    ]
    return {"type": "custom:apexcharts-card", **chart}


def _mushroom_info(entity: str, icon: str, primary: str, secondary: str, color: str) -> dict:
    return {
        "type": "custom:mushroom-template-card",
        "entity": entity,
        "icon": icon,
        "primary": primary,
        "secondary": secondary,
        "color": color,
        "features_position": "bottom",
        "multiline_secondary": True,
    }


def _forecast_tab(p: dict) -> dict:
    w = p["weather"]
    e = p["entities"]
    cards: list[dict] = [
        {
            "type": "horizontal-stack",
            "cards": [
                {
                    "type": "custom:stack-in-card",
                    "mode": "vertical",
                    "cards": [
                        {
                            **_title_subtitle("Forecast", _next_rain_subtitle(w)),
                            "card_mod": FORECAST_HEADER_PAD,
                        },
                        {
                            **_metservice_chip(p["source_label"], p["source_url"]),
                            "card_mod": METSERVICE_CHIP_ABSOLUTE,
                        },
                    ],
                }
            ],
        },
        {
            "type": "vertical-stack",
            "cards": [
                {
                    "type": "custom:weather-forecast-extended-card",
                    "entity": w,
                    "show_header": True,
                    "hourly_forecast": True,
                    "daily_forecast": True,
                    "daily_min_gap": 30,
                    "hourly_min_gap": 16,
                    "show_sun_times": True,
                    "sun_use_home_coordinates": True,
                    "use_night_header_backgrounds": True,
                }
            ],
        },
    ]

    live = p["live"]
    bottom_row: list[dict] = [
        _mushroom_info(
            live["temperature"],
            "mdi:thermometer",
            (
                "Temp: {{ states('" + live["temperature"] + "') }} "
                "{{ state_attr('" + w + "', 'temperature_unit') }}"
            ),
            (
                "{% set fd = state_attr('" + w + "', 'forecast_daily') %}"
                "{% if fd is string %}{% set fd = fd | from_json %}{% endif %}"
                "{% set forecast = fd[0] if fd is iterable and fd | count > 0 else {} %}"
                "{% set unit = state_attr('" + w + "', 'temperature_unit') %}"
                "{% if forecast.temperature is defined and forecast.templow is defined %}"
                "High: {{ forecast.temperature }}{{ unit }} - Low: {{ forecast.templow }}{{ unit }}"
                "{% else %}High: N/A - Low: N/A{% endif %}"
            ),
            _temp_color_template(w),
        )
    ]

    if p.get("aqi_entity"):
        aqi = p["aqi_entity"]
        pol = p.get("aqi_pollutant_entity") or aqi
        bottom_row.append(
            _mushroom_info(
                aqi,
                "mdi:leaf",
                "Air Quality",
                (
                    "{% set aqi = states('" + aqi + "') %}"
                    "{% set pollutant = states('" + pol + "') %}"
                    "{% if aqi not in ['unknown','unavailable','none',''] %}"
                    "{% set aqi = aqi | int %}"
                    "{% set level = ('Good' if aqi <= 50 else 'Moderate' if aqi <= 100 else "
                    "'Unhealthy' if aqi <= 150 else 'Very Unhealthy' if aqi <= 200 else 'Hazardous') %}"
                    "{{ level }} - AQI {{ aqi }} - {{ pollutant }}"
                    "{% else %}Data unavailable{% endif %}"
                ),
                (
                    "{% set aqi = states('" + aqi + "') %}"
                    "{% if aqi not in ['unknown','unavailable','none',''] %}"
                    "{% set aqi = aqi | int %}"
                    "{% if aqi <= 50 %}green{% elif aqi <= 100 %}yellow{% elif aqi <= 150 %}orange"
                    "{% elif aqi <= 200 %}red{% elif aqi <= 300 %}purple{% else %}brown{% endif %}"
                    "{% else %}grey{% endif %}"
                ),
            )
        )

    cards.append({"type": "horizontal-stack", "cards": bottom_row})
    return {"title": "Forecast", "icon": "mdi:weather-partly-cloudy", "card": {"type": "vertical-stack", "cards": cards}}


def _rainfall_tab(p: dict) -> dict:
    w = p["weather"]
    live = p["live"]
    cards = [
        _title_subtitle("Rainfall & Temperature Forecast", _rain_summary_subtitle(w)),
        {"type": "vertical-stack", "cards": [_rainfall_chart(w)]},
        _title_subtitle("Current Rainfall", ""),
        {
            "type": "horizontal-stack",
            "cards": [
                _mushroom_info(
                    w,
                    "mdi:weather-rainy",
                    (
                        "{% set fc = state_attr('" + w + "', 'forecast_hourly') %}"
                        "{% if fc is string %}{% set fc = fc | from_json %}{% endif %}"
                        "{% set r = (fc[0].precipitation if fc is iterable and fc | count > 0 else 0) | float(0) %}"
                        "{% if r == 0 %}Rainfall: None{% else %}Rainfall: {{ r }} mm{% endif %}"
                    ),
                    (
                        "{% set fc = state_attr('" + w + "', 'forecast_hourly') %}"
                        "{% if fc is string %}{% set fc = fc | from_json %}{% endif %}"
                        "{% set r = (fc[0].precipitation if fc is iterable and fc | count > 0 else 0) | float(0) %}"
                        "{% if r == 0 %}None - Dry conditions{% elif r < 1 %}Light - Possible drizzle"
                        "{% elif r < 5 %}Moderate - Bring umbrella{% elif r < 20 %}Heavy - Wet outdoors"
                        "{% else %}Intense - Flood risk{% endif %}"
                    ),
                    (
                        "{% set fc = state_attr('" + w + "', 'forecast_hourly') %}"
                        "{% if fc is string %}{% set fc = fc | from_json %}{% endif %}"
                        "{% set r = (fc[0].precipitation if fc is iterable and fc | count > 0 else 0) | float(0) %}"
                        "{% if r == 0 %}blue{% elif r < 1 %}lightblue{% elif r < 5 %}cyan"
                        "{% elif r < 20 %}orange{% else %}red{% endif %}"
                    ),
                ),
                _mushroom_info(
                    live["temperature"],
                    "mdi:thermometer",
                    (
                        "Temp: {{ states('" + live["temperature"] + "') }} "
                        "{{ state_attr('" + w + "', 'temperature_unit') }}"
                    ),
                    (
                        "{% set t = states('" + live["temperature"] + "') | float(0) %}"
                        "{% if t < 5 %}Cold - Bundle up{% elif t < 15 %}Cool - Light jacket"
                        "{% elif t < 25 %}Mild - Comfortable{% elif t < 32 %}Warm - Stay hydrated"
                        "{% else %}Hot - Avoid heat{% endif %}"
                    ),
                    _temp_color_template(w),
                ),
            ],
        },
    ]
    return {"title": "Rainfall", "icon": "m3of:rainy", "card": {"type": "vertical-stack", "cards": cards}}


def _uv_tab(p: dict) -> dict:
    w = p["weather"]
    live = p["live"]
    uv = live["uv"]
    humidity = live["humidity"]
    cards = [
        _title_subtitle("UV Index & Cloud Coverage Forecast", _uv_summary_subtitle(w, uv)),
        {"type": "vertical-stack", "cards": [_uv_chart(w)]},
        _title_subtitle("Current Sky Conditions", ""),
        {
            "type": "horizontal-stack",
            "cards": [
                _mushroom_info(
                    uv,
                    "mdi:weather-sunny-alert",
                    "UV Index: {{ states('" + uv + "') }}",
                    (
                        "{% set raw = states('" + uv + "') | lower %}"
                        "{% set uv = raw | float(0) if raw not in ['low','moderate','high','very high','extreme'] else "
                        "{'low':2,'moderate':5,'high':8,'very high':10,'extreme':11}.get(raw, 0) %}"
                        "{% if uv < 3 %}Low - Safe outdoors{% elif uv < 6 %}Moderate - Use hat & sunglasses"
                        "{% elif uv < 8 %}High - Apply sunscreen{% elif uv < 11 %}Very High - Seek shade"
                        "{% else %}Extreme - Stay indoors{% endif %}"
                    ),
                    (
                        "{% set raw = states('" + uv + "') | lower %}"
                        "{% set uv = raw | float(0) if raw not in ['low','moderate','high','very high','extreme'] else "
                        "{'low':2,'moderate':5,'high':8,'very high':10,'extreme':11}.get(raw, 0) %}"
                        "{% if uv < 3 %}green{% elif uv < 6 %}yellow{% elif uv < 8 %}orange"
                        "{% elif uv < 11 %}red{% else %}purple{% endif %}"
                    ),
                ),
                _mushroom_info(
                    humidity,
                    "mdi:water-percent",
                    (
                        "Humidity: {{ states('" + humidity + "') }}"
                        "{% if state_attr('" + humidity + "', 'unit_of_measurement') %}%"
                        "{% elif states('" + humidity + "') not in ['unknown','unavailable'] %}%"
                        "{% endif %}"
                    ),
                    (
                        "{% set h = states('" + humidity + "') | float(0) %}"
                        "{% if h < 30 %}Dry air{% elif h < 60 %}Comfortable{% elif h < 75 %}Humid"
                        "{% else %}Very humid{% endif %} · MetService online"
                    ),
                    (
                        "{% set h = states('" + humidity + "') | float(0) %}"
                        "{% if h < 30 %}orange{% elif h < 60 %}green{% elif h < 75 %}blue"
                        "{% else %}indigo{% endif %}"
                    ),
                ),
            ],
        },
    ]
    return {"title": "UV", "icon": "m3of:sunny", "card": {"type": "vertical-stack", "cards": cards}}


def _wind_tab(p: dict) -> dict:
    w = p["weather"]
    live = p["live"]
    cards = [
        _title_subtitle("Wind Speed & Direction Forecast", _wind_summary_subtitle(w)),
        {"type": "vertical-stack", "cards": [_wind_chart(w)]},
        _title_subtitle("Current Wind", ""),
        _mushroom_info(
            live["wind_speed"],
            "mdi:weather-windy",
            (
                "Wind: {{ states('" + live["wind_speed"] + "') }} "
                "{{ state_attr('" + w + "', 'wind_speed_unit') }}"
            ),
            (
                "{% set s = states('" + live["wind_speed"] + "') | float(0) %}"
                "{% set d = states('" + live["wind_direction"] + "') %}"
                "{% if s < 5 %}Calm - Smooth air{% elif s < 20 %}Breezy - Light gusts"
                "{% elif s < 40 %}Windy - Secure items{% elif s < 60 %}Strong - Use caution"
                "{% else %}Gale - Stay indoors{% endif %} ({{ d }})"
            ),
            (
                "{% set s = states('" + live["wind_speed"] + "') | float(0) %}"
                "{% if s < 5 %}green{% elif s < 20 %}yellow{% elif s < 40 %}orange"
                "{% elif s < 60 %}red{% else %}purple{% endif %}"
            ),
        ),
    ]
    return {"title": "Wind", "icon": "m3of:storm", "card": {"type": "vertical-stack", "cards": cards}}


def _radar_tab(p: dict) -> dict:
    w = p["weather"]
    loc = p["location"]
    ms = p.get("metservice_sensors") or {}
    humidity = ms.get("humidity")
    lat = loc.get("latitude", -37.787)
    lon = loc.get("longitude", 175.2793)
    windy_url = (
        f"https://embed.windy.com/embed2.html?lat={lat}&lon={lon}"
        f"&detailLat={lat}&detailLon={lon}&width=800&height=600&zoom=8"
        "&level=surface&overlay=rain&product=ecmwf&menu=&message=true"
        "&marker=&calendar=now&pressure=&type=map&location=coordinates"
        "&detail=&metricWind=km%2Fh&metricTemp=%C2%B0C&radarRange=-1"
    )
    if humidity:
        subtitle = (
            "{% set wx = state_attr('" + w + "') %}"
            "🌡️ {{ wx.temperature }}{{ wx.temperature_unit }} "
            "💧 Humidity: {{ states('" + humidity + "') }}% "
            "💨 Wind: {{ wx.wind_speed }} {{ wx.wind_speed_unit }} "
            "🌤️ UV: {{ states('" + (p.get('live') or {}).get('uv', 'sensor.flux_ui_forecast_uv_index') + "') }}"
        )
    else:
        subtitle = (
            "{% set wx = state_attr('" + w + "') %}"
            "🌡️ {{ wx.temperature }}{{ wx.temperature_unit }} "
            "💧 Humidity: {{ wx.humidity }}% "
            "💨 Wind: {{ wx.wind_speed }} {{ wx.wind_speed_unit }} "
            "🌤️ UV: {{ states('" + (p.get('live') or {}).get('uv', w) + "') }}"
        )
    cards = [
        _title_subtitle("Radar", subtitle),
        {
            "type": "custom:mod-card",
            "card": {"type": "iframe", "url": windy_url},
            "style": (
                "ha-card {\n  padding: 0;\n  height: 350px !important;\n"
                "  width: 100% !important;\n  overflow: hidden;\n}\n"
                "iframe {\n  width: 100% !important;\n  height: 100% !important;\n}\n"
            ),
        },
    ]
    return {"title": "Radar", "icon": "m3of:radar", "card": {"type": "vertical-stack", "cards": cards}}


def _lunar_tab(p: dict) -> dict:
    loc = p["location"]
    lat = loc.get("latitude", -37.787)
    lon = loc.get("longitude", 175.2793)
    e = p["entities"]
    cards = [
        _title_subtitle("Lunar Cycle & Visibility", f"{{{{ states('{e['moon_summary']}') }}}}"),
        {
            "type": "custom:lunar-phase-card",
            "entity": "",
            "12hr_format": True,
            "calendar_modal": False,
            "compact_view": True,
            "default_card": "base",
            "hide_buttons": False,
            "mile_unit": False,
            "moon_position": "left",
            "number_decimals": 2,
            "selected_language": "en",
            "show_background": False,
            "southern_hemisphere": True,
            "use_custom": False,
            "use_default": True,
            "use_entity": False,
            "graph_config": {
                "graph_type": "default",
                "y_ticks": False,
                "x_ticks": False,
                "show_time": True,
                "show_Temp": True,
                "show_highest": True,
                "y_ticks_position": "left",
                "y_ticks_step_size": 30,
                "time_step_size": 30,
            },
            "font_customize": {
                "header_font_size": "medium",
                "header_font_style": "capitalize",
                "label_font_size": "small",
                "label_font_style": "none",
                "label_font_color": "",
                "hide_label": False,
            },
            "latitude": lat,
            "longitude": lon,
            "location": {"city": loc.get("city", ""), "country": loc.get("country", "New Zealand")},
            "custom_background": (
                "https://cdn.jsdelivr.net/gh/ngocjohn/lunar-phase-card@1.7.3/background/moon_bg_2.png"
            ),
        },
    ]
    return {"title": "Lunar", "icon": "m3of:moon-stars", "card": {"type": "vertical-stack", "cards": cards}}


def _warning_tab(p: dict) -> dict | None:
    warnings = p.get("warnings_entity")
    if not warnings:
        return None
    return {
        "title": "Warning",
        "icon": "m3of:warning",
        "conditions": [
            {
                "condition": "template",
                "template": "{{ states('" + warnings + "') not in ['unavailable', 'unknown'] }}",
            }
        ],
        "card": {
            "type": "vertical-stack",
            "cards": [
                _title_subtitle("Weather Warning", ""),
                {
                    "type": "markdown",
                    "content": (
                        "{{ state_attr('" + warnings + "', 'warnings') | default('No warnings') }}\n\n"
                        "_Issued: {{ states." + warnings + ".last_changed.strftime('%I:%M%p %A, %d %b') }}_"
                    ),
                    "text_only": True,
                },
                {
                    **_metservice_chip("Open MetService", p["source_url"]),
                    "alignment": "center",
                },
            ],
        },
    }


def weather_tabs_shell(tabs: list[dict]) -> dict:
    """ElementZoom simple-tabs styling for weather panel."""
    return {
        "type": "custom:simple-tabs",
        "pre-load": True,
        "active-background": "var(--md-sys-color-primary)",
        "active-text-color": "var(--md-sys-color-on-primary)",
        "text-color": "var(--primary-text-color)",
        "tabs_alignment": "center",
        "card_padding": "0",
        "bar_padding": "6px 8px",
        "enable_swipe": True,
        "haptic_feedback": True,
        "card_mod": {
            "style": {
                ".": (
                    "ha-card, :host {\n  width: 100% !important;\n  background: transparent !important;\n"
                    "  box-shadow: none !important; border: none !important;\n}\n"
                    ".tabs-row, .tabs-viewport, .tabs-container, .tabs {\n  width: 100% !important;\n}\n"
                    ".tab-button { flex: 0 0 auto !important; min-width: 0 !important; }\n"
                ),
            },
        },
        "tabs": tabs,
    }


def build_weather_panel_popup(cfg: dict) -> dict | None:
    if not weather_panel_enabled(cfg):
        return None

    p = _panel_cfg(cfg)
    tabs: list[dict] = [
        _forecast_tab(p),
        _rainfall_tab(p),
        _uv_tab(p),
        _wind_tab(p),
        _radar_tab(p),
        _lunar_tab(p),
    ]
    warning = _warning_tab(p)
    if warning:
        tabs.insert(0, warning)

    return {
        "type": "custom:bubble-card",
        "card_type": "pop-up",
        "hash": WEATHER_PANEL_HASH,
        "name": "Weather Panel",
        "icon": "mdi:weather-cloudy-arrow-right",
        "styles": BUBBLE_POPUP_STYLES,
        "bg_color": "var(--md-sys-color-on-primary)",
        "bg_opacity": "85",
        "button_type": "name",
        "sub_button": {"main": [], "bottom": []},
        "cards": [weather_tabs_shell(tabs)],
        "popup_style": "classic",
    }


def build_weather_panel_section(cfg: dict) -> dict | None:
    popup = build_weather_panel_popup(cfg)
    if not popup:
        return None
    return {"type": "grid", "cards": [popup]}

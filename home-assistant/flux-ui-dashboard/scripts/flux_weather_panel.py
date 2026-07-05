"""Flux UI weather panel — ElementZoom bubble popup with Forecast / Rainfall / UV / Wind / Moon tabs.

Reference: ElementZoom Material-Design-3-Dynamic-Mobile-Dashboard assets/weather panel
Uses stub layouts when optional forecast sensors are not yet configured in HA.
"""

from __future__ import annotations

from md3_templates import wrap_glass, wrap_title
from flux_tab_layout import simple_tabs_shell

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

CHART_PLACEHOLDER_MOD = {
    "style": (
        "ha-card {\n"
        "  border-radius: 24px;\n"
        "  min-height: 220px;\n"
        "  background: color-mix(in srgb, var(--md-sys-color-surface-container) 72%, transparent) !important;\n"
        "  border: 1px dashed color-mix(in srgb, var(--md-sys-color-outline-variant) 55%, transparent);\n"
        "  display: flex;\n"
        "  align-items: center;\n"
        "  justify-content: center;\n"
        "  padding: 24px;\n"
        "}\n"
    )
}

METSERVICE_CHIP_MOD = {
    "style": (
        "ha-card {\n"
        "  --text-color: var(--md-sys-color-on-primary);\n"
        "  --color: var(--md-sys-color-on-primary);\n"
        "  --chip-background: var(--md-sys-color-primary);\n"
        "  --chip-border-color: transparent;\n"
        "}\n"
    )
}


def _panel_cfg(cfg: dict) -> dict:
    wp = cfg.get("weather_panel") or {}
    weather = wp.get("weather_entity") or cfg.get("weather", "weather.metservice")
    return {
        "enabled": wp.get("enabled", True),
        "weather_entity": weather,
        "source_label": wp.get("source_label", "MetService"),
        "source_url": wp.get("source_url", "https://www.metservice.com"),
        "sensors": wp.get("sensors") or {},
    }


def weather_panel_enabled(cfg: dict) -> bool:
    return bool(_panel_cfg(cfg).get("enabled", True))


def _title_block(title: str, subtitle: str = "") -> dict:
    card: dict = {
        "type": "custom:mushroom-title-card",
        "title": title,
    }
    if subtitle:
        card["subtitle"] = subtitle
    return wrap_title(card)


def _source_chip(label: str, url: str) -> dict:
    return {
        "type": "custom:mushroom-chips-card",
        "alignment": "end",
        "chips": [
            {
                "type": "template",
                "icon": "mdi:weather-lightning",
                "content": label,
                "tap_action": {"action": "url", "url_path": url},
                "card_mod": {"style": METSERVICE_CHIP_MOD},
            }
        ],
    }


def _stub_chart_caption(primary: str, secondary: str = "") -> dict:
    content = f"**{primary}**"
    if secondary:
        content += f"\n\n_{secondary}_"
    content += "\n\n_Chart placeholder — connect hourly forecast sensors to enable live graphs._"
    return wrap_glass(
        {
            "type": "markdown",
            "content": content,
            "text_only": True,
            "card_mod": CHART_PLACEHOLDER_MOD,
        }
    )


def _template_info_card(
    *,
    entity: str | None,
    icon: str,
    primary: str,
    secondary: str,
    color: str = "primary",
) -> dict:
    card: dict = {
        "type": "custom:mushroom-template-card",
        "icon": icon,
        "primary": primary,
        "secondary": secondary,
        "color": color,
        "features_position": "bottom",
        "multiline_secondary": True,
    }
    if entity:
        card["entity"] = entity
    return wrap_glass(card)


def _weather_hero_card(weather_entity: str) -> dict:
    """Large forecast hero — temp + condition from MetService weather entity."""
    return wrap_glass(
        {
            "type": "custom:button-card",
            "entity": weather_entity,
            "template": "flux_glass",
            "show_icon": True,
            "show_name": True,
            "show_label": True,
            "show_state": True,
            "state_display": (
                "[[[\n"
                "  const t = entity.attributes.temperature;\n"
                "  const u = entity.attributes.temperature_unit || '°C';\n"
                "  return t != null ? `${t} ${u}` : entity.state;\n"
                "]]]"
            ),
            "name": (
                "[[[\n"
                "  const a = entity.attributes || {};\n"
                "  return a.condition || a.weather || entity.state || 'Forecast';\n"
                "]]]"
            ),
            "label": (
                "[[[\n"
                "  const a = entity.attributes || {};\n"
                "  const parts = [];\n"
                "  if (a.humidity != null) parts.push(`Humidity ${a.humidity}%`);\n"
                "  if (a.wind_speed != null) parts.push(`Wind ${a.wind_speed}`);\n"
                "  return parts.join(' · ') || 'NZ MetService';\n"
                "]]]"
            ),
            "styles": {
                "card": [
                    {"min-height": "160px"},
                    {"padding": "22px 20px"},
                ],
                "icon": [{"width": "42px"}],
                "name": [{"font-size": "22px"}, {"font-weight": "700"}],
                "state": [{"font-size": "36px"}, {"font-weight": "700"}],
            },
        }
    )


def _daily_forecast_markdown(weather_entity: str) -> dict:
    return wrap_glass(
        {
            "type": "markdown",
            "content": (
                "{% set fc = state_attr('" + weather_entity + "', 'forecast') %}\n"
                "**Daily forecast**\n\n"
                "{% if fc %}\n"
                "{% for day in fc[:4] %}\n"
                "- **{{ day.datetime | as_timestamp | timestamp_custom('%a %d') }}** — "
                "{{ day.condition }} · {{ day.temperature }}° / {{ day.templow }}°\n"
                "{% endfor %}\n"
                "{% else %}\n"
                "_Daily rows will populate when `"
                + weather_entity
                + "` exposes forecast attributes._\n"
                "{% endif %}"
            ),
        }
    )


def _hourly_forecast_markdown(weather_entity: str) -> dict:
    return wrap_glass(
        {
            "type": "markdown",
            "content": (
                "{% set hourly = state_attr('" + weather_entity + "', 'hourly') %}\n"
                "**Hourly forecast**\n\n"
                "{% if hourly %}\n"
                "{% for hour in hourly[:8] %}\n"
                "- {{ hour.datetime | as_timestamp | timestamp_custom('%a %I %p') }} — "
                "{{ hour.condition }} · {{ hour.temperature }}°\n"
                "{% endfor %}\n"
                "{% else %}\n"
                "_Hourly strip placeholder — wire MetService hourly attributes or forecast sensors._\n"
                "{% endif %}"
            ),
        }
    )


def _forecast_tab(cfg: dict) -> dict:
    panel = _panel_cfg(cfg)
    weather = panel["weather_entity"]
    source = panel["source_label"]
    url = panel["source_url"]
    sensors = panel["sensors"]
    summary_entity = sensors.get("next_rain_summary")
    summary = (
        "{{ states('" + summary_entity + "') }}"
        if summary_entity
        else "_Light · 0.3 mm · next rain when sensors are connected_"
    )

    header = {
        "type": "vertical-stack",
        "cards": [
            _title_block("Forecast", summary),
            _source_chip(source, url),
        ],
    }

    cards = [
        header,
        _weather_hero_card(weather),
        _daily_forecast_markdown(weather),
        _hourly_forecast_markdown(weather),
    ]
    return {"title": "Forecast", "icon": "mdi:weather-partly-cloudy", "card": {"type": "vertical-stack", "cards": cards}}


def _rainfall_tab(cfg: dict) -> dict:
    panel = _panel_cfg(cfg)
    weather = panel["weather_entity"]
    sensors = panel["sensors"]
    summary_entity = sensors.get("rainfall_summary")
    summary = (
        "{{ states('" + summary_entity + "') }}"
        if summary_entity
        else "_Rainfall: 11.3 mm (Heavy), peaking when sensors are connected_"
    )

    rain_entity = sensors.get("rainfall")
    temp_entity = sensors.get("temperature")

    rain_primary = (
        "{% set r = states('" + rain_entity + "') %}"
        "{% if r in ['unknown', 'unavailable', None, ''] %}Rainfall: — mm{% else %}Rainfall: {{ r }} mm{% endif %}"
        if rain_entity
        else "Rainfall: 0.3 mm (stub)"
    )
    rain_secondary = (
        "{% set r = states('" + rain_entity + "') | float(0) %}"
        "{% if r == 0 %}None — Dry conditions{% elif r < 1 %}Light — Possible drizzle{% elif r < 5 %}Moderate — Bring umbrella{% elif r < 20 %}Heavy — Wet outdoors{% else %}Intense — Flood risk{% endif %}"
        if rain_entity
        else "Light — Possible drizzle"
    )

    temp_primary = (
        "Temp: {{ states('" + temp_entity + "') }} {{ state_attr('" + weather + "', 'temperature_unit') }}"
        if temp_entity
        else "Temp: {{ state_attr('" + weather + "', 'temperature') }} {{ state_attr('" + weather + "', 'temperature_unit') }}"
    )
    temp_secondary = (
        "{% set t = states('" + temp_entity + "') | float(0) %}"
        "{% if t < 5 %}Cold — Bundle up{% elif t < 15 %}Cool — Light jacket{% elif t < 25 %}Mild — Comfortable{% elif t < 32 %}Warm — Stay hydrated{% else %}Hot — Avoid heat{% endif %}"
        if temp_entity
        else "Cool — Light jacket"
    )

    cards = [
        _title_block("Rainfall & Temperature Forecast", summary),
        _stub_chart_caption("Rain + temperature", "Blue bars = rain · red line = temp"),
        {
            "type": "horizontal-stack",
            "cards": [
                _template_info_card(
                    entity=rain_entity,
                    icon="mdi:weather-rainy",
                    primary=rain_primary,
                    secondary=rain_secondary,
                    color="cyan",
                ),
                _template_info_card(
                    entity=temp_entity or weather,
                    icon="mdi:thermometer",
                    primary=temp_primary,
                    secondary=temp_secondary,
                    color="#5EBDEE",
                ),
            ],
        },
    ]
    return {"title": "Rainfall", "icon": "mdi:weather-rainy", "card": {"type": "vertical-stack", "cards": cards}}


def _uv_tab(cfg: dict) -> dict:
    panel = _panel_cfg(cfg)
    sensors = panel["sensors"]
    summary_entity = sensors.get("uv_cloud_summary")
    summary = (
        "{{ states('" + summary_entity + "') }}"
        if summary_entity
        else "_Peak UV: 1.0 (Low), Avg Cloud: 60% — summary stub until sensors exist_"
    )

    uv_entity = sensors.get("uv_index")
    cloud_entity = sensors.get("cloud_coverage")

    uv_primary = (
        "UV Index: {{ states('" + uv_entity + "') }}"
        if uv_entity
        else "UV Index: 0 (stub)"
    )
    uv_secondary = (
        "{% set uv = states('" + uv_entity + "') | float(0) %}"
        "{% if uv < 3 %}Low — Safe outdoors{% elif uv < 6 %}Moderate — Use hat & sunglasses{% elif uv < 8 %}High — Apply sunscreen{% elif uv < 11 %}Very High — Seek shade{% else %}Extreme — Stay indoors{% endif %}"
        if uv_entity
        else "Low — Safe outdoors"
    )

    cloud_primary = (
        "Cloud: {{ states('" + cloud_entity + "') }}%"
        if cloud_entity
        else "Cloud: 97% (stub)"
    )
    cloud_secondary = (
        "{% set c = states('" + cloud_entity + "') | float(0) %}"
        "{% if c <= 25 %}Clear skies — ideal visibility{% elif c <= 50 %}Partly cloudy — some sun breaks{% elif c <= 75 %}Mostly cloudy — limited sunshine{% else %}Overcast — likely dull conditions{% endif %}"
        if cloud_entity
        else "Overcast — likely dull conditions"
    )

    cards = [
        _title_block("UV Index & Cloud Coverage Forecast", summary),
        _stub_chart_caption("UV index + cloud coverage", "Yellow = UV · blue area = cloud %"),
        {
            "type": "horizontal-stack",
            "cards": [
                _template_info_card(
                    entity=uv_entity,
                    icon="mdi:weather-sunny-alert",
                    primary=uv_primary,
                    secondary=uv_secondary,
                    color="amber",
                ),
                _template_info_card(
                    entity=cloud_entity,
                    icon="mdi:weather-cloudy",
                    primary=cloud_primary,
                    secondary=cloud_secondary,
                    color="blue-grey",
                ),
            ],
        },
    ]
    return {"title": "UV", "icon": "mdi:weather-sunny", "card": {"type": "vertical-stack", "cards": cards}}


def _wind_tab(cfg: dict) -> dict:
    panel = _panel_cfg(cfg)
    weather = panel["weather_entity"]
    sensors = panel["sensors"]
    summary_entity = sensors.get("wind_summary")
    summary = (
        "{{ states('" + summary_entity + "') }}"
        if summary_entity
        else "_Strongest wind expected when forecast sensors are connected_"
    )

    speed_entity = sensors.get("wind_speed")
    direction_entity = sensors.get("wind_direction")

    wind_primary = (
        "Wind: {{ states('" + speed_entity + "') }} {{ state_attr('" + weather + "', 'wind_speed_unit') }}"
        if speed_entity
        else "Wind: {{ state_attr('" + weather + "', 'wind_speed') }} {{ state_attr('" + weather + "', 'wind_speed_unit') }}"
    )
    if speed_entity:
        wind_secondary = (
            "{% set s = states('" + speed_entity + "') | float(0) %}"
            "{% if s < 5 %}Calm — Smooth air{% elif s < 20 %}Breezy — Light gusts{% elif s < 40 %}Windy — Secure items{% elif s < 60 %}Strong — Use caution{% else %}Gale — Stay indoors{% endif %}"
        )
        if direction_entity:
            wind_secondary += (
                " ({% set d = states('" + direction_entity + "') | float(0) %}{{ d | round(0) }}°)"
            )
    else:
        wind_secondary = "Breezy — Light gusts (stub)"

    cards = [
        _title_block("Wind Speed & Direction Forecast", summary),
        _stub_chart_caption("Wind speed + direction", "Blue = speed · purple = bearing"),
        _template_info_card(
            entity=speed_entity or weather,
            icon="mdi:weather-windy",
            primary=wind_primary,
            secondary=wind_secondary,
            color="light-blue",
        ),
    ]
    return {"title": "Wind", "icon": "mdi:weather-windy", "card": {"type": "vertical-stack", "cards": cards}}


def _moon_tab(cfg: dict) -> dict:
    sensors = _panel_cfg(cfg)["sensors"]
    summary_entity = sensors.get("moon_summary")
    summary = (
        "{{ states('" + summary_entity + "') }}"
        if summary_entity
        else "_Lunar phase — connect lunar-phase integration for live moon data_"
    )

    cards = [
        _title_block("Lunar Cycle & Visibility", summary),
        wrap_glass(
            {
                "type": "markdown",
                "content": (
                    "**Moon phase (stub)**\n\n"
                    "🌙 Waxing crescent · 24% illumination\n\n"
                    "_Install [lunar-phase](https://github.com/ngocjohn/lunar-phase) "
                    "and lunar-phase-card to replace this placeholder._"
                ),
            }
        ),
    ]
    return {"title": "Moon", "icon": "mdi:moon-waning-crescent", "card": {"type": "vertical-stack", "cards": cards}}


def build_weather_panel_popup(cfg: dict) -> dict | None:
    if not weather_panel_enabled(cfg):
        return None

    tabs = [
        _forecast_tab(cfg),
        _rainfall_tab(cfg),
        _uv_tab(cfg),
        _wind_tab(cfg),
        _moon_tab(cfg),
    ]

    return {
        "type": "custom:bubble-card",
        "card_type": "pop-up",
        "hash": WEATHER_PANEL_HASH,
        "name": "Weather Panel",
        "icon": "mdi:weather-partly-cloudy",
        "styles": BUBBLE_POPUP_STYLES,
        "bg_color": "var(--md-sys-color-on-primary)",
        "bg_opacity": "85",
        "button_type": "name",
        "sub_button": {"main": [], "bottom": []},
        "cards": [
            simple_tabs_shell(tabs, enable_swipe=True),
        ],
        "popup_style": "classic",
    }


def build_weather_panel_section(cfg: dict) -> dict | None:
    popup = build_weather_panel_popup(cfg)
    if not popup:
        return None
    return {"type": "grid", "cards": [popup]}

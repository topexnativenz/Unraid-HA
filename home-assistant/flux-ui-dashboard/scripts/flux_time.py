"""New Zealand time helpers for Flux UI (Pacific/Auckland / NZST·NZDT)."""

from __future__ import annotations

# IANA zone — handles NZST/NZDT automatically.
NZ_TIMEZONE = "Pacific/Auckland"
NZ_LOCALE = "en-NZ"

# HA sensors from packages/flux_ui_time.yaml (follow HA time_zone = Pacific/Auckland).
NZ_CLOCK_ENTITY = "sensor.flux_ui_nz_clock"
NZ_DATE_ENTITY = "sensor.flux_ui_nz_date"

# Default MetService NZ weather entity (ciejer/metservice-weather).
METSERVICE_WEATHER = "weather.homemetservice"


def _fully_timezone_js() -> str:
    """Best-effort: pin Fully Kiosk device TZ so calendar-card-pro times match NZST."""
    return (
        "  if (typeof fully !== 'undefined' && !window.__fluxNzTzPinned) {\n"
        "    try {\n"
        f"      if (typeof fully.setTimezone === 'function') fully.setTimezone('{NZ_TIMEZONE}');\n"
        f"      else if (typeof fully.setStringSetting === 'function') fully.setStringSetting('timezoneId', '{NZ_TIMEZONE}');\n"
        "      window.__fluxNzTzPinned = true;\n"
        "    } catch (e) {}\n"
        "  }\n"
    )


def nz_hour_js() -> str:
    """JS expression: current hour 0–23 in Pacific/Auckland."""
    return (
        "Number(new Intl.DateTimeFormat('en-NZ', {"
        f"timeZone: '{NZ_TIMEZONE}', hour: 'numeric', hourCycle: 'h23'"
        "}).format(new Date()))"
    )


def nz_greeting_js() -> str:
    """JS button-card template: 'Good Morning/Afternoon/Evening!' (no username)."""
    return (
        "[[[\n"
        f"  const h = {nz_hour_js()};\n"
        "  if (h >= 17) return 'Good Evening!';\n"
        "  if (h >= 12) return 'Good Afternoon!';\n"
        "  return 'Good Morning!';\n"
        "]]]"
    )


def nz_greeting_name_js(*, user_expr: str | None = None) -> str:
    """Deprecated alias — dashboards use nz_greeting_js() (no HA user name)."""
    del user_expr
    return nz_greeting_js()


def nz_datetime_short_js() -> str:
    """JS: short weekday/date/time in NZ locale + Pacific/Auckland."""
    return (
        "[[[ return new Date().toLocaleString('en-NZ', {"
        f"timeZone: '{NZ_TIMEZONE}', "
        "weekday:'short', month:'short', day:'numeric', "
        "hour:'numeric', minute:'2-digit'}); ]]]"
    )


def nz_time_short_js() -> str:
    """JS: time only in NZ."""
    return (
        "[[[ return new Date().toLocaleTimeString('en-NZ', {"
        f"timeZone: '{NZ_TIMEZONE}', "
        "hour: 'numeric', minute: '2-digit'}); ]]]"
    )


def nz_clock_time_js() -> str:
    """Large digital 12h h:mm in NZST/NZDT (no AM/PM).

    Prefers HA sensor.flux_ui_nz_clock (server NZ local time) so Fully Kiosk
    tablets with a wrong device timezone stay in sync. Falls back to Intl
    Pacific/Auckland. Also asks Fully to pin device TZ for calendar-card-pro.
    """
    return (
        "[[[\n"
        + _fully_timezone_js()
        + "  if (this && !this.__fluxNzClock) {\n"
        "    this.__fluxNzClock = setInterval(() => {\n"
        "      try { this.update(); } catch (e) {}\n"
        "    }, 15000);\n"
        "  }\n"
        f"  const haClock = hass?.states?.['{NZ_CLOCK_ENTITY}']?.state;\n"
        "  if (haClock && /^\\d{1,2}:\\d{2}$/.test(haClock)) return haClock;\n"
        "  const haTime = hass?.states?.['sensor.time']?.state;\n"
        "  if (haTime && /^\\d{1,2}:\\d{2}/.test(haTime)) {\n"
        "    let h = parseInt(haTime.split(':')[0], 10);\n"
        "    const m = haTime.split(':')[1].slice(0, 2);\n"
        "    if (h === 0) h = 12; else if (h > 12) h -= 12;\n"
        "    return `${h}:${m}`;\n"
        "  }\n"
        "  const parts = new Intl.DateTimeFormat('en-NZ', {\n"
        f"    timeZone: '{NZ_TIMEZONE}',\n"
        "    hour: 'numeric',\n"
        "    minute: '2-digit',\n"
        "    hour12: true,\n"
        "    hourCycle: 'h12'\n"
        "  }).formatToParts(new Date());\n"
        "  const hour = (parts.find((p) => p.type === 'hour') || {}).value || '';\n"
        "  const minute = (parts.find((p) => p.type === 'minute') || {}).value || '';\n"
        "  return `${hour}:${minute}`;\n"
        "]]]"
    )


def nz_clock_date_js() -> str:
    """Weekday + date in NZST/NZDT (no zone suffix). Prefers HA sensor."""
    return (
        "[[[\n"
        + _fully_timezone_js()
        + f"  const haDate = hass?.states?.['{NZ_DATE_ENTITY}']?.state;\n"
        "  if (haDate && haDate !== 'unknown' && haDate !== 'unavailable') return haDate;\n"
        "  return new Date().toLocaleDateString('en-NZ', {\n"
        f"    timeZone: '{NZ_TIMEZONE}',\n"
        "    weekday: 'long',\n"
        "    day: 'numeric',\n"
        "    month: 'long'\n"
        "  });\n"
        "]]]"
    )

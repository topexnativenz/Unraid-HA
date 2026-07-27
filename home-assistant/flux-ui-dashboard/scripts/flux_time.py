"""New Zealand time helpers for Flux UI (Pacific/Auckland / NZST·NZDT)."""

from __future__ import annotations

# IANA zone — handles NZST/NZDT automatically.
NZ_TIMEZONE = "Pacific/Auckland"
NZ_LOCALE = "en-NZ"

# Default MetService NZ weather entity (ciejer/metservice-weather).
METSERVICE_WEATHER = "weather.homemetservice"


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
    """Large digital 24h HH:MM in Pacific/Auckland; refreshes every 15s."""
    return (
        "[[[\n"
        "  if (this && !this.__fluxNzClock) {\n"
        "    this.__fluxNzClock = setInterval(() => {\n"
        "      try { this.update(); } catch (e) {}\n"
        "    }, 15000);\n"
        "  }\n"
        "  const parts = new Intl.DateTimeFormat('en-NZ', {\n"
        f"    timeZone: '{NZ_TIMEZONE}',\n"
        "    hour: '2-digit',\n"
        "    minute: '2-digit',\n"
        "    hour12: false,\n"
        "    hourCycle: 'h23'\n"
        "  }).formatToParts(new Date());\n"
        "  const hour = (parts.find((p) => p.type === 'hour') || {}).value || '';\n"
        "  const minute = (parts.find((p) => p.type === 'minute') || {}).value || '';\n"
        "  return `${hour}:${minute}`;\n"
        "]]]"
    )


def nz_clock_date_js() -> str:
    """Weekday + date in Pacific/Auckland (no NZST/NZDT suffix)."""
    return (
        "[[[\n"
        "  return new Date().toLocaleDateString('en-NZ', {\n"
        f"    timeZone: '{NZ_TIMEZONE}',\n"
        "    weekday: 'long',\n"
        "    day: 'numeric',\n"
        "    month: 'long'\n"
        "  });\n"
        "]]]"
    )

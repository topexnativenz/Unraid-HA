"""Dashboard swipe navigation — disabled on Flux UI.

Flux UI uses navbar-card for Home / Rooms / Scenes / Camera. The HACS
hass-swipe-navigation module otherwise steals horizontal swipes from the
navbar media player carousel (Sonos zone switching).
"""

from __future__ import annotations

# Root-level Lovelace key: swipe_nav (requires hass-swipe-navigation resource).
SWIPE_NAV: dict = {
    "enable": False,
}

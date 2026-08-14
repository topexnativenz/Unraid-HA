"""Kiosk mode config — hide HA header on mobile (ElementZoom Flux pattern)."""

from __future__ import annotations

# Matches ElementZoom dashboard/mobile/dashboard.yaml
# Requires HACS: maykar/kiosk-mode (+ lovelace resource registered on deploy).
KIOSK_MODE: dict = {
    "mobile_settings": {
        "hide_header": True,
        # Keep sidebar — swipe from left edge opens drawer (Profile, other dashboards).
        # Do NOT set hide_sidebar here; that blocks swipe and traps users.
    },
}

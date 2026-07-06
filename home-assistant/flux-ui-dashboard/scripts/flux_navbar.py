"""Flux UI bottom navbar — matches ElementZoom mobile dashboard pattern."""

from __future__ import annotations

from md3_templates import GLASS_CARD_MOD

URL_PREFIX = "/flux-ui"

try:
    from flux_weather_panel import FLUX_UI_WEATHER_PANEL_PATH
except ImportError:
    FLUX_UI_WEATHER_PANEL_PATH = "/flux-ui/overview#weather-panel"


def room_view_path(room_slug: str) -> str:
    """Lovelace view path for a room detail page (no slashes — HA requirement)."""
    return f"room-{room_slug}"


def room_navigation_path(room_slug: str) -> str:
    """Full browser path to a room detail view on the Flux UI dashboard."""
    return f"{URL_PREFIX}/{room_view_path(room_slug)}"


def room_grid_view_path(room_slug: str) -> str:
    return f"{room_view_path(room_slug)}-grid"


def room_camera_view_path(room_slug: str) -> str:
    return f"{room_view_path(room_slug)}-camera"


def room_grid_navigation_path(room_slug: str) -> str:
    return f"{URL_PREFIX}/{room_grid_view_path(room_slug)}"


def room_camera_navigation_path(room_slug: str) -> str:
    return f"{URL_PREFIX}/{room_camera_view_path(room_slug)}"


# ElementZoom-style navbar CSS (blur pill, slide-up).
NAVBAR_STYLES = """
.navbar-card {
  background: color-mix(in srgb, var(--md-sys-color-on-primary) 25%, transparent);
  backdrop-filter: blur(50px);
  -webkit-backdrop-filter: blur(20px) !important;
  background-blend-mode: overlay;
  border-radius: 20px;
  box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
  margin-bottom: 15px;
  overflow: hidden;
}
.button {
  --icon-primary-color: color-mix(in srgb, var(--md-sys-color-primary) 40%, transparent);
}
.button.active {
  background: transparent;
}
ha-ripple {
  display: none !important;
}
/* Capture horizontal swipes for the Sonos zone carousel (navbar-card sets pan-y). */
.media-player-viewport {
  touch-action: none !important;
  overflow: hidden !important;
}
.media-player-carousel {
  touch-action: none !important;
  overflow: hidden !important;
}
.media-player-container {
  overflow: hidden !important;
  background: color-mix(in srgb, var(--card-background-color, var(--ha-card-background)) 90%, transparent) !important;
  border-radius: 14px;
}
.media-player-track {
  overflow: hidden !important;
}
"""


def flux_routes() -> list[dict]:
    """Primary nav routes — same structure as ElementZoom Flux mobile."""
    return [
        {
            "url": f"{URL_PREFIX}/overview",
            "label": "Home",
            "icon": "mdi:home-outline",
            "icon_selected": "mdi:home",
        },
        {
            "url": f"{URL_PREFIX}/rooms",
            "label": "Rooms",
            "icon": "mdi:sofa-outline",
            "icon_selected": "mdi:sofa",
            "selected": (
                "[[[ return window.location.pathname === '/flux-ui/rooms' "
                "|| window.location.pathname.startsWith('/flux-ui/room-'); ]]]"
            ),
        },
        {
            "url": FLUX_UI_WEATHER_PANEL_PATH,
            "label": "Weather",
            "icon": "mdi:weather-partly-cloudy",
            "icon_selected": "mdi:weather-partly-cloudy",
        },
        {
            "url": f"{URL_PREFIX}/cameras",
            "label": "Camera",
            "icon": "mdi:cctv",
            "icon_selected": "mdi:cctv",
        },
        {
            "icon": "mdi:dots-horizontal",
            "label": "More",
            "tap_action": {"action": "open-popup"},
            "popup": [
                {
                    "icon": "mdi:layers-outline",
                    "label": "Scenes",
                    "url": f"{URL_PREFIX}/scenes",
                },
                {
                    "icon": "mdi:palette-outline",
                    "label": "Lights",
                    "url": f"{URL_PREFIX}/lights",
                },
                {
                    "icon": "mdi:cellphone",
                    "label": "Mobile Home",
                    "url": "/mobile-home/home",
                },
                {
                    "icon": "mdi:solar-power",
                    "label": "Solar",
                    "url": "/solar-dashboard",
                },
                {
                    "icon": "mdi:car-electric",
                    "label": "Tesla",
                    "url": "/mobile-home/tesla",
                },
                {
                    "icon": "mdi:account-circle-outline",
                    "label": "Profile",
                    "url": "/profile",
                },
                {
                    "icon": "mdi:cog-outline",
                    "label": "HA Settings",
                    "url": "/config/dashboard",
                },
            ],
        },
    ]


def build_navbar_card(
    *,
    use_navbar_card: bool = True,
    media_player: dict | None = None,
) -> dict:
    if use_navbar_card:
        nav: dict = {
            "type": "custom:navbar-card",
            "mobile": {"show_labels": True},
            "haptic": True,
            "desktop": {
                "show_labels": True,
                "position": "bottom",
                "min_width": 768,
                "show_popup_label_backgrounds": False,
            },
            "routes": flux_routes(),
            "styles": NAVBAR_STYLES,
        }
        if media_player:
            nav["media_player"] = media_player
        return nav

    # Mushroom fallback — same destinations, no popup support.
    chips = [
        {
            "type": "template",
            "icon": "mdi:home",
            "icon_color": "primary",
            "content": "Home",
            "tap_action": {"action": "navigate", "navigation_path": f"{URL_PREFIX}/overview"},
        },
        {
            "type": "template",
            "icon": "mdi:sofa",
            "content": "Rooms",
            "tap_action": {"action": "navigate", "navigation_path": f"{URL_PREFIX}/rooms"},
        },
        {
            "type": "template",
            "icon": "mdi:weather-partly-cloudy",
            "content": "Weather",
            "tap_action": {"action": "navigate", "navigation_path": FLUX_UI_WEATHER_PANEL_PATH},
        },
        {
            "type": "template",
            "icon": "mdi:cctv",
            "content": "Camera",
            "tap_action": {"action": "navigate", "navigation_path": f"{URL_PREFIX}/cameras"},
        },
    ]
    return {
        "type": "custom:mushroom-chips-card",
        "alignment": "center",
        "chips": chips,
        "card_mod": GLASS_CARD_MOD,
    }


def navbar_section(
    *,
    use_navbar_card: bool = True,
    media_player: dict | None = None,
) -> dict:
    nav = build_navbar_card(use_navbar_card=use_navbar_card, media_player=media_player)
    nav["grid_options"] = {"columns": 12}
    return {"type": "grid", "cards": [nav]}

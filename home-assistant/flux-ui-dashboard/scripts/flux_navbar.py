"""Flux UI bottom navbar — matches ElementZoom mobile dashboard pattern."""

from __future__ import annotations

from md3_templates import GLASS_CARD_MOD

URL_PREFIX = "/flux-ui"
TABLET_URL_PREFIX = "/flux-ui-tablet"

try:
    from flux_weather_panel import FLUX_UI_WEATHER_PANEL_PATH
except ImportError:
    FLUX_UI_WEATHER_PANEL_PATH = "/flux-ui/overview#weather-panel"


def set_url_prefix(prefix: str) -> None:
    """Point navbar + room navigation at mobile (/flux-ui) or tablet (/flux-ui-tablet)."""
    global URL_PREFIX
    URL_PREFIX = prefix.rstrip("/") or "/flux-ui"


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


def room_climate_view_path(room_slug: str) -> str:
    return f"{room_view_path(room_slug)}-climate"


def room_climate_navigation_path(room_slug: str) -> str:
    return f"{URL_PREFIX}/{room_climate_view_path(room_slug)}"


# ElementZoom-style navbar CSS (blur pill, slide-up).
# touch-action:none on media carousel — navbar-card defaults to pan-y and steals swipes.
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
.media-player-viewport,
.media-player-carousel,
.media-player-viewport *,
.media-player-carousel *,
.navbar-media-player,
.navbar-media-player * {
  touch-action: none !important;
  -webkit-user-select: none !important;
  user-select: none !important;
}
"""


def _is_tablet() -> bool:
    return URL_PREFIX == TABLET_URL_PREFIX


def flux_routes() -> list[dict]:
    """Primary nav — phone: Weather middle slot; tablet: Scenes/Lights popup."""
    prefix = URL_PREFIX

    middle: dict
    if _is_tablet():
        middle = {
            "url": f"{prefix}/scenes",
            "label": "Scenes",
            "icon": "mdi:layers-outline",
            "icon_selected": "mdi:layers",
            "tap_action": {"action": "open-popup"},
            "popup": [
                {
                    "icon": "mdi:lightbulb-group-outline",
                    "label": "Scenes",
                    "url": f"{prefix}/scenes",
                },
                {
                    "icon": "mdi:palette-outline",
                    "label": "Lights",
                    "url": f"{prefix}/lights",
                },
            ],
        }
    else:
        middle = {
            "url": FLUX_UI_WEATHER_PANEL_PATH,
            "label": "Weather",
            "icon": "mdi:weather-partly-cloudy",
            "icon_selected": "mdi:weather-partly-cloudy",
        }

    more_popup = [
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
    ]
    if not _is_tablet():
        more_popup = [
            {
                "icon": "mdi:layers-outline",
                "label": "Scenes",
                "url": f"{prefix}/scenes",
            },
            {
                "icon": "mdi:palette-outline",
                "label": "Lights",
                "url": f"{prefix}/lights",
            },
            *more_popup,
        ]

    return [
        {
            "url": f"{prefix}/overview",
            "label": "Home",
            "icon": "mdi:home-outline",
            "icon_selected": "mdi:home",
        },
        {
            "url": f"{prefix}/rooms",
            "label": "Rooms",
            "icon": "mdi:sofa-outline",
            "icon_selected": "mdi:sofa",
            "selected": (
                f"[[[ return window.location.pathname === '{prefix}/rooms' "
                f"|| window.location.pathname.startsWith('{prefix}/room-'); ]]]"
            ),
        },
        middle,
        {
            "url": f"{prefix}/cameras",
            "label": "Camera",
            "icon": "mdi:cctv",
            "icon_selected": "mdi:cctv",
        },
        {
            "icon": "mdi:dots-horizontal",
            "label": "More",
            "tap_action": {"action": "open-popup"},
            "popup": more_popup,
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
    prefix = URL_PREFIX
    if _is_tablet():
        mid_chip = {
            "type": "template",
            "icon": "mdi:layers",
            "content": "Scenes",
            "tap_action": {"action": "navigate", "navigation_path": f"{prefix}/scenes"},
        }
    else:
        mid_chip = {
            "type": "template",
            "icon": "mdi:weather-partly-cloudy",
            "content": "Weather",
            "tap_action": {
                "action": "navigate",
                "navigation_path": FLUX_UI_WEATHER_PANEL_PATH,
            },
        }
    chips = [
        {
            "type": "template",
            "icon": "mdi:home",
            "icon_color": "primary",
            "content": "Home",
            "tap_action": {"action": "navigate", "navigation_path": f"{prefix}/overview"},
        },
        {
            "type": "template",
            "icon": "mdi:sofa",
            "content": "Rooms",
            "tap_action": {"action": "navigate", "navigation_path": f"{prefix}/rooms"},
        },
        mid_chip,
        {
            "type": "template",
            "icon": "mdi:cctv",
            "content": "Camera",
            "tap_action": {"action": "navigate", "navigation_path": f"{prefix}/cameras"},
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

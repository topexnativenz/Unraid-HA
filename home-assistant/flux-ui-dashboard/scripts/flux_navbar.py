"""Flux UI bottom navbar — matches ElementZoom mobile dashboard pattern."""

from __future__ import annotations

from md3_templates import GLASS_CARD_MOD

URL_PREFIX = "/flux-ui"

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
        },
        {
            "url": f"{URL_PREFIX}/scenes",
            "label": "Scenes",
            "icon": "mdi:layers-outline",
            "icon_selected": "mdi:layers",
            "tap_action": {"action": "open-popup"},
            "popup": [
                {
                    "icon": "mdi:lightbulb-group-outline",
                    "label": "Scenes",
                    "url": f"{URL_PREFIX}/scenes",
                },
                {
                    "icon": "mdi:palette-outline",
                    "label": "Lights",
                    "url": f"{URL_PREFIX}/lights",
                },
            ],
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


def build_navbar_card(*, use_navbar_card: bool = True) -> dict:
    if use_navbar_card:
        return {
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
            "icon": "mdi:layers",
            "content": "Scenes",
            "tap_action": {"action": "navigate", "navigation_path": f"{URL_PREFIX}/scenes"},
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


def navbar_section(*, use_navbar_card: bool = True) -> dict:
    nav = build_navbar_card(use_navbar_card=use_navbar_card)
    nav["grid_options"] = {"columns": 12}
    return {"type": "grid", "cards": [nav]}

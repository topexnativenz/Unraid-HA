"""Tablet outdoor cameras — branded animated stills on overview, live on tap.

Overview tiles use name-themed animated WebPs from
``/local/flux-ui/camera-stills/<suffix>.webp`` (committed assets).
Tap opens live (Reolink Bubble / Eufy wake-then-live). Live snapshots are
no longer written over these branded backgrounds.
"""

from __future__ import annotations

from flux_navbar import overview_navigation_path
from flux_tablet_layout import tablet_panel_stack, tablet_panel_view
from md3_templates import wrap_glass

# Bump when replacing still assets so Fully/Companion caches refresh.
STILL_ASSET_VERSION = "branded2"
STILL_LOCAL_DIR = "/local/flux-ui/camera-stills"
STILL_EXT = "webp"


def camera_still_filename(entity: str) -> str:
    return entity.split(".", 1)[-1] + f".{STILL_EXT}"


def camera_still_url(entity: str) -> str:
    """Static URL for the branded animated still (cache-busted by asset version)."""
    return f"{STILL_LOCAL_DIR}/{camera_still_filename(entity)}?v={STILL_ASSET_VERSION}"


def camera_still_url_template(entity: str) -> str:
    """button-card CSS background value for the branded animated still."""
    return f'center / cover no-repeat url("{camera_still_url(entity)}")'


def eufy_live_view_path(camera: dict) -> str:
    name = camera.get("name") or camera.get("entity", "camera").split(".", 1)[-1]
    slug = name.lower().replace(" ", "-").replace("_", "-")
    return f"eufy-{slug}"


def eufy_live_navigation_path(camera: dict) -> str:
    # Read live module value (set_url_prefix) — avoid stale imported binding.
    import flux_navbar

    return f"{flux_navbar.URL_PREFIX}/{eufy_live_view_path(camera)}"


def _rtsp_url_template(stream_sensor: str) -> str:
    """HomeBase RTSP URL with credentials; ffmpeg: wrapper helps flaky DESCRIBE."""
    return (
        "{% set u = states('"
        + stream_sensor
        + "') %}"
        "{% set auth = states('sensor.side_door_rtsp_stream_url') %}"
        "{% if u[:7] == 'rtsp://' and '@' not in u and '@' in auth %}"
        "{% set cred = auth[7:].split('@')[0] %}"
        "{% set u = 'rtsp://' ~ cred ~ '@' ~ u[7:] %}"
        "{% endif %}"
        "{{ 'ffmpeg:' ~ u ~ '#video=h264' }}"
    )


def _stream_status_entity(camera_entity: str) -> str:
    return "sensor." + camera_entity.split(".", 1)[-1] + "_stream_status"


def _rtsp_switch_entity(camera_entity: str) -> str:
    return "switch." + camera_entity.split(".", 1)[-1] + "_rtsp_stream"


def _still_img_html(entity: str) -> str:
    """Absolute cover image — fills the camera tile (no letterbox bars)."""
    url = camera_still_url(entity)
    return (
        f'<img src="{url}" alt="" '
        'style="position:absolute;inset:0;width:100%;height:100%;'
        "object-fit:cover;object-position:center;display:block;"
        'margin:0;padding:0;border:0;" />'
    )


def build_overview_still_tile(
    camera: dict,
    *,
    tap_path: str,
) -> dict:
    """Branded animated still tile — tap opens live (bubble hash or eufy subview).

    Image uses object-fit:cover so ultra-wide cams fill the card with no bars.
    """
    entity = camera["entity"]
    name = camera.get("name") or entity.split(".", 1)[-1].replace("_", " ").title()
    return wrap_glass(
        {
            "type": "custom:button-card",
            "entity": entity,
            "name": name,
            "show_name": True,
            "show_icon": False,
            "show_state": False,
            "show_entity_picture": False,
            "triggers_update": [entity],
            "tap_action": {
                "action": "navigate",
                "navigation_path": tap_path,
            },
            "hold_action": {
                "action": "navigate",
                "navigation_path": tap_path,
            },
            "custom_fields": {
                "still": _still_img_html(entity),
            },
            "card_mod": {
                "style": (
                    "ha-card {\n"
                    "  aspect-ratio: unset !important;\n"
                    "  height: 100% !important;\n"
                    "  min-height: 0 !important;\n"
                    "  padding: 0 !important;\n"
                    "  overflow: hidden !important;\n"
                    "  background: #111 !important;\n"
                    "}\n"
                    "img {\n"
                    "  position: absolute !important;\n"
                    "  inset: 0 !important;\n"
                    "  width: 100% !important;\n"
                    "  height: 100% !important;\n"
                    "  object-fit: cover !important;\n"
                    "  object-position: center !important;\n"
                    "}\n"
                ),
            },
            "styles": {
                "card": [
                    {"height": "100%"},
                    {"min-height": "0"},
                    {"aspect-ratio": "unset"},
                    {"padding": "0"},
                    {"overflow": "hidden"},
                    {"background-color": "#111"},
                    {"background": camera_still_url_template(entity)},
                    {"background-size": "cover"},
                    {"background-position": "center"},
                    {"background-repeat": "no-repeat"},
                ],
                "grid": [
                    {"grid-template-areas": "'still'"},
                    {"grid-template-columns": "1fr"},
                    {"grid-template-rows": "1fr"},
                    {"position": "relative"},
                ],
                "custom_fields": {
                    "still": [
                        {"position": "absolute"},
                        {"inset": "0"},
                        {"width": "100%"},
                        {"height": "100%"},
                        {"z-index": 0},
                        {"pointer-events": "none"},
                        {"overflow": "hidden"},
                    ],
                },
                "name": [
                    {"position": "absolute"},
                    {"inset": "0"},
                    {"left": "0"},
                    {"right": "0"},
                    {"top": "0"},
                    {"bottom": "0"},
                    {"display": "flex"},
                    {"align-items": "center"},
                    {"justify-content": "center"},
                    {"text-align": "center"},
                    {"width": "100%"},
                    {"height": "100%"},
                    {"box-sizing": "border-box"},
                    {"padding": "12px"},
                    {"margin": "0"},
                    {"color": "#fff"},
                    {"font-size": "22px"},
                    {"font-weight": "700"},
                    {"letter-spacing": "0.02em"},
                    {"line-height": "1.15"},
                    {
                        "text-shadow": (
                            "0 2px 8px rgba(0,0,0,0.95), "
                            "0 0 18px rgba(0,0,0,0.7)"
                        )
                    },
                    {"pointer-events": "none"},
                    {"z-index": 2},
                ],
            },
        }
    )


def build_eufy_overview_tile(camera: dict) -> dict:
    """Eufy overview tile — branded still; tap opens wake-then-live subview."""
    return build_overview_still_tile(
        camera, tap_path=eufy_live_navigation_path(camera)
    )


def build_tablet_eufy_live_view(camera: dict, *, use_navbar_card: bool = False) -> dict:
    """Full-bleed live view — wake cam, WebRTC when STREAMING; branded still while waiting."""
    entity = camera["entity"]
    name = camera.get("name") or entity.split(".", 1)[-1].replace("_", " ").title()
    stream = (camera.get("stream") or "").strip()
    status = _stream_status_entity(entity)
    rtsp_switch = _rtsp_switch_entity(entity)
    overview = overview_navigation_path()
    still_bg = camera_still_url_template(entity)

    back = {
        "type": "custom:button-card",
        "icon": "mdi:arrow-left-circle",
        "name": "Overview",
        "show_icon": True,
        "show_name": True,
        "tap_action": {
            "action": "navigate",
            "navigation_path": overview,
        },
        "styles": {
            "grid": [
                {"grid-template-areas": "'i n'"},
                {"grid-template-columns": "min-content 1fr"},
                {"column-gap": "6px"},
                {"align-items": "center"},
            ],
            "card": [
                {"padding": "8px 14px 8px 10px"},
                {"min-height": "48px"},
                {"border-radius": "999px"},
                {"width": "fit-content"},
            ],
            "icon": [{"width": "26px"}, {"color": "var(--md-sys-color-primary)"}],
            "name": [{"font-size": "15px"}, {"font-weight": "700"}],
        },
    }

    title_js = (
        "[[[ const cam = "
        + repr(entity)
        + "; const sw = "
        + repr(rtsp_switch)
        + "; const key = '__fluxEufyStart_' + cam; "
        "if (!window[key]) { window[key] = true; "
        "try { hass.callService('switch','turn_on',{entity_id:sw}); "
        "hass.callService('camera','turn_on',{entity_id:cam}); } catch(e) {} "
        "setTimeout(() => { window[key] = false; }, 90000); } "
        "return "
        + repr(f"Live — {name}")
        + "; ]]]"
    )
    starter = {
        "type": "custom:button-card",
        "name": title_js,
        "show_icon": False,
        "show_name": True,
        "styles": {
            "card": [
                {"background": "transparent"},
                {"box-shadow": "none"},
                {"border": "none"},
                {"padding": "8px 4px"},
            ],
            "name": [{"font-size": "22px"}, {"font-weight": "700"}, {"justify-self": "start"}],
        },
    }

    waiting = wrap_glass(
        {
            "type": "custom:button-card",
            "entity": entity,
            "name": "Starting live stream… tap to retry",
            "show_name": True,
            "show_icon": False,
            "show_entity_picture": False,
            "triggers_update": [entity, status],
            "tap_action": {
                "action": "perform-action",
                "perform_action": "camera.turn_on",
                "target": {"entity_id": entity},
            },
            "styles": {
                "card": [
                    {"height": "min(70vh, 720px)"},
                    {"padding": "0"},
                    {"overflow": "hidden"},
                    {"background": still_bg},
                    {"background-color": "#111"},
                ],
                "name": [
                    {"position": "absolute"},
                    {"left": "12px"},
                    {"bottom": "12px"},
                    {"color": "#fff"},
                    {"font-size": "16px"},
                    {"font-weight": "600"},
                    {"text-shadow": "0 1px 4px rgba(0,0,0,0.85)"},
                ],
            },
        }
    )

    live: dict = {
        "type": "custom:webrtc-camera",
        "title": name,
        "entity": entity,
        "muted": True,
        "media": "video",
        "mode": "mse,mjpeg",
        "url": _rtsp_url_template(stream) if stream else entity,
        "style": (
            "video{object-fit:contain;width:100%;max-height:70vh;background:#111}"
            ".mode{right:8px;top:8px}"
        ),
    }

    stack = {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "horizontal-stack",
                "cards": [wrap_glass(back), starter],
            },
            {
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": status,
                        "state": "StreamStatus.STREAMING",
                    }
                ],
                "card": wrap_glass(live),
            },
            {
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": status,
                        "state_not": "StreamStatus.STREAMING",
                    }
                ],
                "card": waiting,
            },
        ],
    }

    root = tablet_panel_stack(stack, use_navbar_card=use_navbar_card)
    return tablet_panel_view(
        title=f"{name} live",
        path=eufy_live_view_path(camera),
        icon="mdi:cctv",
        root_card=root,
        subview=True,
        back_path=overview,
    )


def tablet_eufy_cameras(cfg: dict) -> list[dict]:
    """Eufy entries from tablet.overview_cameras that have an RTSP stream sensor."""
    tablet = cfg.get("tablet") or {}
    out: list[dict] = []
    for cam in tablet.get("overview_cameras") or []:
        if cam.get("stream") and str(cam.get("entity", "")).startswith("camera."):
            out.append(cam)
    return out


def build_tablet_eufy_live_views(cfg: dict, *, use_navbar_card: bool = False) -> list[dict]:
    return [
        build_tablet_eufy_live_view(cam, use_navbar_card=use_navbar_card)
        for cam in tablet_eufy_cameras(cfg)
    ]

"""Tablet Eufy outdoor cameras — stills on overview, live WebRTC subviews.

Eufy ``/api/camera_proxy`` returns HTTP 500. HomeBase RTSP also rejects go2rtc
DESCRIBE until ``camera.turn_on`` has woken the cam. Overview therefore shows
``image.*_event_image`` stills; tap opens a live subview that starts the stream
then plays via WebRTC (MSE).
"""

from __future__ import annotations

from flux_navbar import overview_navigation_path
from flux_tablet_layout import tablet_panel_stack, tablet_panel_view
from md3_templates import wrap_glass, wrap_title


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
    # camera.side_door → sensor.side_door_stream_status
    return "sensor." + camera_entity.split(".", 1)[-1] + "_stream_status"


def _rtsp_switch_entity(camera_entity: str) -> str:
    return "switch." + camera_entity.split(".", 1)[-1] + "_rtsp_stream"


def build_eufy_overview_tile(camera: dict) -> dict:
    """Event-image still tile — tap opens the live subview (starts stream there)."""
    entity = camera["entity"]
    name = camera.get("name") or entity.split(".", 1)[-1].replace("_", " ").title()
    still = (camera.get("still") or "").strip() or entity
    live_path = eufy_live_navigation_path(camera)
    return wrap_glass(
        {
            "type": "custom:button-card",
            "entity": still,
            "name": name,
            "show_name": True,
            "show_icon": False,
            "show_state": False,
            "show_entity_picture": True,
            "tap_action": {
                "action": "navigate",
                "navigation_path": live_path,
            },
            "hold_action": {
                "action": "perform-action",
                "perform_action": "camera.turn_on",
                "target": {"entity_id": entity},
            },
            "styles": {
                "card": [
                    {"height": "160px"},
                    {"min-height": "160px"},
                    {"max-height": "160px"},
                    {"padding": "0"},
                    {"overflow": "hidden"},
                    {"background": "#111"},
                ],
                "img_cell": [
                    {"width": "100%"},
                    {"height": "160px"},
                    {"position": "absolute"},
                    {"top": "0"},
                    {"left": "0"},
                    {"margin": "0"},
                    {"padding": "0"},
                ],
                "entity_picture": [
                    {"width": "100%"},
                    {"height": "160px"},
                    {"object-fit": "cover"},
                    {"border-radius": "0"},
                ],
                "name": [
                    {"position": "absolute"},
                    {"left": "8px"},
                    {"bottom": "6px"},
                    {"color": "#fff"},
                    {"font-size": "12px"},
                    {"font-weight": "600"},
                    {"text-shadow": "0 1px 4px rgba(0,0,0,0.85)"},
                    {"pointer-events": "none"},
                    {"z-index": 2},
                ],
            },
        }
    )


def build_tablet_eufy_live_view(camera: dict, *, use_navbar_card: bool = False) -> dict:
    """Full-bleed live view — wake cam, then WebRTC MSE once STREAMING."""
    entity = camera["entity"]
    name = camera.get("name") or entity.split(".", 1)[-1].replace("_", " ").title()
    still = (camera.get("still") or "").strip()
    stream = (camera.get("stream") or "").strip()
    status = _stream_status_entity(entity)
    rtsp_switch = _rtsp_switch_entity(entity)
    overview = overview_navigation_path()

    back = {
        "type": "custom:button-card",
        "icon": "mdi:arrow-left-circle",
        "name": "Overview",
        "show_icon": True,
        "show_name": True,
        "tap_action": {"action": "navigate", "navigation_path": overview},
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

    # Auto-start once when the title card renders on this view.
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
            "entity": still or entity,
            "name": "Starting live stream… tap to retry",
            "show_name": True,
            "show_icon": False,
            "show_entity_picture": bool(still),
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
                    {"background": "#111"},
                ],
                "entity_picture": [
                    {"width": "100%"},
                    {"height": "min(70vh, 720px)"},
                    {"object-fit": "cover"},
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
    if still:
        live["poster"] = "{{ state_attr('%s', 'entity_picture') }}" % still

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
    """Eufy entries from tablet.overview_cameras that have still + stream."""
    tablet = cfg.get("tablet") or {}
    out: list[dict] = []
    for cam in tablet.get("overview_cameras") or []:
        if cam.get("still") and cam.get("stream") and cam.get("entity", "").startswith("camera."):
            out.append(cam)
    return out


def build_tablet_eufy_live_views(cfg: dict, *, use_navbar_card: bool = False) -> list[dict]:
    return [
        build_tablet_eufy_live_view(cam, use_navbar_card=use_navbar_card)
        for cam in tablet_eufy_cameras(cfg)
    ]

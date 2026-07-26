"""Tablet outdoor cameras — last-stream stills on overview, live on tap.

Overview tiles use JPEGs written by ``camera.snapshot`` to
``/local/flux-ui/camera-stills/<suffix>.jpg`` (see packages/flux_ui_eufy_cameras.yaml).
Eufy ``/api/camera_proxy`` returns HTTP 500 and event images go stale, so we never
use ``image.*_event_image`` on the tablet row.

Eufy live: HomeBase RTSP needs ``camera.turn_on`` first (DESCRIBE fails until awake).
Reolink live: Bubble Card ``#back-courtyard`` fullscreen window.
"""

from __future__ import annotations

from flux_navbar import overview_navigation_path
from flux_tablet_layout import tablet_panel_stack, tablet_panel_view
from md3_templates import wrap_glass

STILL_TOKEN_ENTITY = "input_text.flux_ui_camera_still_token"
STILL_LOCAL_DIR = "/local/flux-ui/camera-stills"


def camera_still_filename(entity: str) -> str:
    return entity.split(".", 1)[-1] + ".jpg"


def camera_still_url_template(entity: str) -> str:
    """button-card JS — local still + cache-bust token from last snapshot."""
    fname = camera_still_filename(entity)
    return (
        "[[[ const t = states['"
        + STILL_TOKEN_ENTITY
        + "'] ? states['"
        + STILL_TOKEN_ENTITY
        + "'].state : '0'; "
        "return `center / cover no-repeat url(\""
        + STILL_LOCAL_DIR
        + "/"
        + fname
        + "?v=${t}\")`; ]]]"
    )


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


def build_overview_still_tile(
    camera: dict,
    *,
    tap_path: str,
) -> dict:
    """Last-stream JPEG tile — tap opens live (bubble hash or eufy subview)."""
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
            "triggers_update": [STILL_TOKEN_ENTITY, entity],
            "tap_action": {
                "action": "navigate",
                "navigation_path": tap_path,
            },
            "hold_action": {
                "action": "perform-action",
                "perform_action": "script.flux_ui_camera_snapshot",
                "data": {"camera_entity": entity},
            },
            "styles": {
                "card": [
                    {"height": "160px"},
                    {"min-height": "160px"},
                    {"max-height": "160px"},
                    {"padding": "0"},
                    {"overflow": "hidden"},
                    {"background": camera_still_url_template(entity)},
                    {"background-color": "#111"},
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
                "grid": [
                    {"grid-template-areas": "'n'"},
                    {"grid-template-columns": "1fr"},
                ],
            },
        }
    )


def build_eufy_overview_tile(camera: dict) -> dict:
    """Eufy overview tile — last-stream still; tap opens wake-then-live subview."""
    return build_overview_still_tile(
        camera, tap_path=eufy_live_navigation_path(camera)
    )


def build_tablet_eufy_live_view(camera: dict, *, use_navbar_card: bool = False) -> dict:
    """Full-bleed live view — wake cam, snapshot while live, WebRTC when STREAMING."""
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

    # Auto-start once when the title card renders; snapshot after wake via package automation.
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
            "triggers_update": [STILL_TOKEN_ENTITY, entity, status],
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

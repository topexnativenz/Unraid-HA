#!/usr/bin/env python3
"""Build + deploy Flux UI Wall Display (flux-ui-wall).

Fixes unresponsive garage / gate taps on Fully Kiosk:
  - perform-action instead of call-service
  - ES5-safe door JS (no ?. / ??)
  - correct Tapo sensor entity IDs
  - Gate Open + Gate Latch + House Garage + Main Shed + All Off
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
GARAGE_DIR = ROOT.parent / "garage-doors"
OUT = ROOT / "lovelace" / "dashboards" / "flux_ui_wall.json"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(GARAGE_DIR))

from flux_action_builders import lock_action  # noqa: E402
from flux_door_builders import flux_door_tile  # noqa: E402
from garage_ui_helpers import load_garage_doors  # noqa: E402
from ha_common import get_token, ws_call  # noqa: E402

WALL_URL_PATH = "flux-ui-wall"
WALL_TITLE = "Wall Display"
ALL_OFF_SCRIPT = "script.house_lights_all_off"

GATE_OPEN = {
    "entity": "lock.gate_intercom_gate_open",
    "name": "Gate Open",
    "status_entity": "binary_sensor.casa_luna_gate_status",
    "hold_entity": "input_boolean.gate_hold_active",
}
GATE_LATCH = {
    "entity": "lock.gate_intercom_gate_latch",
    "name": "Gate Latch",
    "hold_entity": "input_boolean.gate_hold_active",
}

TILE_CARD = [
    {"padding": "14px 10px 12px"},
    {"height": "100%"},
    {"min-height": "0"},
    {"display": "flex"},
    {"align-items": "center"},
    {"justify-content": "center"},
    {"border-radius": "22px"},
]

VIEW_MOD = {
    "style": (
        "ha-view {\n"
        "  background: center / cover no-repeat fixed "
        "url('/local/flux-ui/wallpapers/dark-purple.webp') !important;\n"
        "  height: 100dvh !important; max-height: 100dvh !important;\n"
        "  overflow: hidden !important;\n"
        "}\n"
        "#view {\n"
        "  background: transparent !important; max-width: none !important;\n"
        "  width: 100% !important; height: 100dvh !important;\n"
        "  max-height: 100dvh !important; margin: 0 !important;\n"
        "  padding: 0 !important; overflow: hidden !important;\n"
        "}\n"
        "hui-panel-view, hui-view-panel {\n"
        "  width: 100% !important; height: 100dvh !important;\n"
        "  max-height: 100dvh !important; overflow: hidden !important;\n"
        "}\n"
        "hui-panel-view > *, hui-view-panel > * {\n"
        "  width: 100% !important; height: 100dvh !important;\n"
        "  max-height: 100dvh !important; overflow: hidden !important;\n"
        "}\n"
        "@keyframes flux-door-pulse {\n"
        "  0%, 100% { box-shadow: 0 0 18px rgba(242, 184, 181, 0.45); }\n"
        "  50% { box-shadow: 0 0 28px rgba(242, 184, 181, 0.75); }\n"
        "}\n"
    )
}

STACK_MOD = {
    "style": (
        ":host {\n"
        "  display: block !important; height: 100dvh !important;\n"
        "  max-height: 100dvh !important; box-sizing: border-box !important;\n"
        "  padding: 10px 12px 14px !important;\n"
        "}\n"
        "#root {\n"
        "  height: 100% !important; display: flex !important;\n"
        "  flex-direction: column !important; gap: 10px !important;\n"
        "}\n"
        "#root > *:first-child { flex: 0 0 auto !important; }\n"
        "#root > *:nth-child(2) { flex: 1 1 auto !important; min-height: 0 !important; }\n"
        "#root > *:last-child { flex: 0 0 auto !important; }\n"
    )
}

GRID_MOD = {
    "style": (
        ":host { display: block !important; height: 100% !important; min-height: 0 !important; }\n"
        "#root {\n"
        "  height: 100% !important; min-height: 0 !important;\n"
        "  display: grid !important; grid-template-columns: 1fr 1fr !important;\n"
        "  grid-template-rows: 1fr 1fr !important; gap: 10px !important;\n"
        "}\n"
        "#root > * { min-height: 0 !important; height: 100% !important; }\n"
    )
}


def _templates_from_live(live: dict | None) -> dict:
    base = {
        "flux_glass": {
            "styles": {
                "card": [
                    {"border-radius": "28px"},
                    {
                        "background": (
                            "color-mix(in srgb, var(--md-sys-color-surface-container) "
                            "78%, transparent)"
                        )
                    },
                    {"backdrop-filter": "blur(18px) saturate(140%)"},
                    {
                        "border": (
                            "1px solid color-mix(in srgb, "
                            "var(--md-sys-color-outline-variant) 45%, transparent)"
                        )
                    },
                    {"box-shadow": "0 4px 24px rgba(0, 0, 0, 0.28)"},
                    {"padding": "14px 16px"},
                ]
            }
        },
        "flux_action": {"template": "flux_glass", "show_label": True},
        "flux_door": {"template": "flux_glass", "show_icon": True, "show_label": True},
    }
    if not live:
        return base
    live_tmpl = live.get("button_card_templates") or {}
    merged = copy.deepcopy(live_tmpl)
    for key, value in base.items():
        merged.setdefault(key, value)
    return merged


def _clock() -> dict:
    return {
        "type": "custom:button-card",
        "entity": "sensor.time",
        "triggers_update": "all",
        "show_icon": False,
        "show_name": True,
        "show_label": True,
        "show_state": False,
        "name": (
            "[[[ return new Date().toLocaleTimeString('en-NZ', "
            "{timeZone: 'Pacific/Auckland', hour: 'numeric', "
            "minute: '2-digit', hour12: true}); ]]]"
        ),
        "label": (
            "[[[ return new Date().toLocaleDateString('en-NZ', "
            "{timeZone: 'Pacific/Auckland', weekday: 'short', "
            "day: 'numeric', month: 'short'}); ]]]"
        ),
        "tap_action": {"action": "none"},
        "hold_action": {"action": "none"},
        "styles": {
            "card": [
                {"background": "transparent"},
                {"box-shadow": "none"},
                {"border": "none"},
                {"padding": "8px 8px 4px"},
                {"height": "auto"},
                {"min-height": "unset"},
            ],
            "grid": [
                {"grid-template-areas": "'n' 'l'"},
                {"grid-template-columns": "1fr"},
                {"grid-template-rows": "min-content min-content"},
                {"row-gap": "2px"},
                {"justify-items": "center"},
            ],
            "name": [
                {"font-size": "64px"},
                {"font-weight": "800"},
                {"letter-spacing": "-0.02em"},
                {"line-height": "1"},
                {"color": "var(--md-sys-color-on-surface)"},
                {"justify-self": "center"},
                {"font-variant-numeric": "tabular-nums"},
            ],
            "label": [
                {"font-size": "18px"},
                {"font-weight": "600"},
                {"color": "var(--md-sys-color-on-surface-variant)"},
                {"justify-self": "center"},
                {"letter-spacing": "0.04em"},
                {"text-transform": "uppercase"},
            ],
        },
    }


def _tile(card: dict) -> dict:
    out = copy.deepcopy(card)
    out.pop("grid_options", None)
    styles = dict(out.get("styles") or {})
    card_styles = list(styles.get("card") or [])
    card_styles.extend(TILE_CARD)
    styles["card"] = card_styles
    out["styles"] = styles
    return out


def _all_off() -> dict:
    return {
        "type": "custom:button-card",
        "template": "flux_action",
        "name": "All Off",
        "label": "House lights",
        "icon": "mdi:lightbulb-off-outline",
        "show_icon": True,
        "show_label": True,
        "tap_action": {
            "action": "perform-action",
            "perform_action": "script.turn_on",
            "target": {"entity_id": ALL_OFF_SCRIPT},
        },
        "styles": {
            "card": [
                {"padding": "12px 14px"},
                {"min-height": "64px"},
                {"border-radius": "22px"},
            ]
        },
    }


def _grid() -> dict:
    doors = load_garage_doors()
    by_name = {d["name"]: d for d in doors}
    house = by_name.get("House Garage") or (doors[0] if doors else None)
    shed = by_name.get("Main Shed") or (doors[1] if len(doors) > 1 else None)

    tiles = [
        _tile(
            lock_action(
                GATE_OPEN["entity"],
                GATE_OPEN["name"],
                columns=6,
                status_entity=GATE_OPEN.get("status_entity"),
                hold_entity=GATE_OPEN.get("hold_entity"),
            )
        ),
        _tile(
            lock_action(
                GATE_LATCH["entity"],
                GATE_LATCH["name"],
                columns=6,
                hold_entity=GATE_LATCH.get("hold_entity"),
            )
        ),
    ]
    if house:
        tiles.append(_tile(flux_door_tile(house)))
    if shed:
        tiles.append(_tile(flux_door_tile(shed)))
    while len(tiles) < 4:
        tiles.append({"type": "markdown", "content": " "})

    return {
        "type": "grid",
        "columns": 2,
        "square": False,
        "cards": tiles[:4],
        "card_mod": GRID_MOD,
    }


def build_wall_config(*, live: dict | None = None) -> dict:
    return {
        "title": WALL_TITLE,
        "button_card_templates": _templates_from_live(live),
        "views": [
            {
                "title": WALL_TITLE,
                "path": "home",
                "type": "panel",
                "panel": True,
                "icon": "mdi:wall",
                "card_mod": VIEW_MOD,
                "cards": [
                    {
                        "type": "vertical-stack",
                        "cards": [_clock(), _grid(), _all_off()],
                        "card_mod": STACK_MOD,
                    }
                ],
            }
        ],
    }


def _validate(config: dict) -> None:
    blob = json.dumps(config)
    for needle in (
        "script.pulse_house_garage_door",
        "script.pulse_main_shed_door",
        "perform-action",
        "lock.gate_intercom_gate_open",
        "lock.gate_intercom_gate_latch",
        "binary_sensor.house_garage_door_sensor_door",
        "binary_sensor.contact_sensor_door",
        "Gate Open",
        "House Garage",
        "Main Shed",
    ):
        if needle not in blob:
            raise SystemExit(f"wall config missing {needle!r}")
    if "call-service" in blob:
        raise SystemExit("wall config still has call-service taps")
    if "variables?." in blob or "states?." in blob:
        raise SystemExit("wall config still has optional-chaining in button JS")


async def _load_live(token: str, ha_url: str) -> dict | None:
    res = await ws_call(
        token, ha_url, [{"type": "lovelace/config", "url_path": WALL_URL_PATH, "force": True}]
    )
    if res[0].get("success"):
        return res[0]["result"]
    return None


async def _save(token: str, ha_url: str, config: dict) -> None:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": WALL_URL_PATH, "config": config}],
    )
    if not res[0].get("success"):
        raise RuntimeError(f"lovelace/config/save failed: {res[0].get('error')}")
    verify = await ws_call(
        token, ha_url, [{"type": "lovelace/config", "url_path": WALL_URL_PATH, "force": True}]
    )
    if not verify[0].get("success"):
        raise RuntimeError(f"verify failed: {verify[0].get('error')}")
    live = verify[0]["result"]
    _validate(live)
    print(f"Saved + verified {WALL_URL_PATH}")


async def async_main(args: argparse.Namespace) -> int:
    config = build_wall_config()
    token = None
    ha_url = args.ha_url
    if not args.offline:
        token = get_token(args.token)
        live = await _load_live(token, ha_url)
        config = build_wall_config(live=live)

    _validate(config)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")

    if args.offline:
        return 0

    assert token is not None
    await _save(token, ha_url, config)

    # Also repair wall-2 taps that still use call-service if any appear later.
    # Wall-2 already uses perform-action for its four buttons — leave as-is.
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--offline", action="store_true", help="Write JSON only; do not push")
    args = parser.parse_args()
    if args.ha_url is None:
        import os

        args.ha_url = os.environ.get("HA_URL") or os.environ.get("HOMEASSISTANT_URL")
        if not args.ha_url and not args.offline:
            raise SystemExit("Pass --ha-url or set HA_URL")
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())

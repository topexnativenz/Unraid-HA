#!/usr/bin/env python3
"""Build + deploy Flux UI Wall Display (flux-ui-wall).

Garage wall Fully Kiosk home view:
  - Full-screen 2×2 grid (equal cells, edge-to-edge)
  - Top row: House Garage | Main Shed (flux_door)
  - Bottom row: Gate Open | Gate Latch (flux_action)
  - Flux UI MD3 theme + button-card templates only (no mushroom)
  - perform-action taps + ES5-safe door JS
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
from md3_templates import BUTTON_CARD_TEMPLATES  # noqa: E402

WALL_URL_PATH = "flux-ui-wall"
WALL_TITLE = "Wall Display"
WALL_THEME = "flux-ui-md3"

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

# Wall-scale touch targets — fill each equal grid cell.
TILE_CARD = [
    {"padding": "28px 24px"},
    {"height": "100%"},
    {"min-height": "0"},
    {"width": "100%"},
    {"display": "flex"},
    {"align-items": "center"},
    {"justify-content": "center"},
    {"border-radius": "28px"},
    {"box-sizing": "border-box"},
]

TILE_GRID = [
    {"grid-template-areas": "'i n' 'i l'"},
    {"grid-template-columns": "88px 1fr"},
    {"grid-template-rows": "min-content min-content"},
    {"column-gap": "20px"},
    {"align-items": "center"},
    {"justify-content": "center"},
]

TILE_IMG = [
    {"border-radius": "24px"},
    {"width": "88px"},
    {"height": "88px"},
    {"place-self": "center"},
]

TILE_ICON = [
    {"width": "48px"},
    {"height": "48px"},
]

TILE_NAME = [
    {"font-size": "28px"},
    {"font-weight": "700"},
    {"line-height": "1.2"},
    {"white-space": "normal"},
    {"overflow": "visible"},
    {"text-overflow": "clip"},
    {"justify-self": "start"},
    {"text-align": "left"},
    {"color": "var(--md-sys-color-on-surface)"},
]

TILE_LABEL = [
    {"font-size": "18px"},
    {"font-weight": "600"},
    {"justify-self": "start"},
    {"color": "var(--md-sys-color-on-surface-variant)"},
]

TILE_ENTITY_PIC = [
    {"width": "48px"},
    {"height": "48px"},
    {"object-fit": "contain"},
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

GRID_MOD = {
    "style": (
        ":host {\n"
        "  display: block !important; height: 100dvh !important;\n"
        "  max-height: 100dvh !important; width: 100% !important;\n"
        "  box-sizing: border-box !important;\n"
        "  padding: 12px !important;\n"
        "}\n"
        "#root {\n"
        "  height: 100% !important; min-height: 0 !important;\n"
        "  width: 100% !important;\n"
        "  display: grid !important;\n"
        "  grid-template-columns: 1fr 1fr !important;\n"
        "  grid-template-rows: 1fr 1fr !important;\n"
        "  gap: 12px !important;\n"
        "  box-sizing: border-box !important;\n"
        "}\n"
        "#root > * {\n"
        "  min-height: 0 !important; min-width: 0 !important;\n"
        "  height: 100% !important; width: 100% !important;\n"
        "}\n"
        "#root > * > * {\n"
        "  height: 100% !important; width: 100% !important;\n"
        "}\n"
    )
}


def _templates_from_live(live: dict | None = None) -> dict:
    """Flux MD3 button-card templates only — no mushroom cards on the wall."""
    del live  # Wall home view only needs Flux chrome; don't inherit stale templates.
    flux_keys = ("flux_glass", "flux_action", "flux_door")
    return {k: copy.deepcopy(BUTTON_CARD_TEMPLATES[k]) for k in flux_keys}


def _merge_styles(styles: dict, key: str, extras: list[dict]) -> None:
    styles[key] = list(styles.get(key) or []) + list(extras)


def _tile(card: dict) -> dict:
    """Scale a Flux MD3 tile to fill one equal full-screen grid cell."""
    out = copy.deepcopy(card)
    out.pop("grid_options", None)
    styles = dict(out.get("styles") or {})
    _merge_styles(styles, "card", TILE_CARD)
    _merge_styles(styles, "grid", TILE_GRID)
    _merge_styles(styles, "img_cell", TILE_IMG)
    _merge_styles(styles, "icon", TILE_ICON)
    _merge_styles(styles, "entity_picture", TILE_ENTITY_PIC)
    _merge_styles(styles, "name", TILE_NAME)
    _merge_styles(styles, "label", TILE_LABEL)
    out["styles"] = styles
    return out


def _grid() -> dict:
    """2×2 Flux button-card grid — garage doors on top, gates underneath."""
    doors = load_garage_doors()
    by_name = {d["name"]: d for d in doors}
    house = by_name.get("House Garage") or (doors[0] if doors else None)
    shed = by_name.get("Main Shed") or (doors[1] if len(doors) > 1 else None)

    tiles: list[dict] = []
    # Top row: House Garage | Main Shed
    if house:
        tiles.append(_tile(flux_door_tile(house)))
    if shed:
        tiles.append(_tile(flux_door_tile(shed)))
    # Bottom row: Gate Open | Gate Latch
    tiles.append(
        _tile(
            lock_action(
                GATE_OPEN["entity"],
                GATE_OPEN["name"],
                columns=6,
                status_entity=GATE_OPEN.get("status_entity"),
                hold_entity=GATE_OPEN.get("hold_entity"),
            )
        )
    )
    tiles.append(
        _tile(
            lock_action(
                GATE_LATCH["entity"],
                GATE_LATCH["name"],
                columns=6,
                hold_entity=GATE_LATCH.get("hold_entity"),
            )
        )
    )
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
                "theme": WALL_THEME,
                "icon": "mdi:garage-variant",
                "card_mod": VIEW_MOD,
                # Single full-screen card: four equal buttons, no clock / footer.
                "cards": [_grid()],
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
        '"template": "flux_door"',
        '"template": "flux_action"',
        f'"theme": "{WALL_THEME}"',
    ):
        if needle not in blob:
            raise SystemExit(f"wall config missing {needle!r}")
    if "call-service" in blob:
        raise SystemExit("wall config still has call-service taps")
    if "mushroom" in blob.lower():
        raise SystemExit("wall config still references mushroom cards")
    if "variables?." in blob or "states?." in blob:
        raise SystemExit("wall config still has optional-chaining in button JS")
    if "All Off" in blob or "sensor.time" in blob:
        raise SystemExit("wall config must be 4 buttons only (no clock / All Off)")

    view_cards = config["views"][0]["cards"]
    if len(view_cards) != 1 or view_cards[0].get("type") != "grid":
        raise SystemExit("wall view must be a single full-screen grid")
    cards = view_cards[0]["cards"]
    if len(cards) != 4:
        raise SystemExit(f"wall grid must have exactly 4 buttons, got {len(cards)}")
    names = [c.get("name") for c in cards]
    if names[:2] != ["House Garage", "Main Shed"]:
        raise SystemExit(f"garage doors must be top row, got {names!r}")
    if names[2:4] != ["Gate Open", "Gate Latch"]:
        raise SystemExit(f"gates must be bottom row, got {names!r}")


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

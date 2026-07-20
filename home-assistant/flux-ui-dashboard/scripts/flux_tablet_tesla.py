"""Tesla tiles for the 16:9 tablet overview (full-width row under cameras)."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

_TESLA_DIR = Path(__file__).resolve().parents[1] / "www" / "flux-ui" / "tesla"

_DEFAULT_TESLA: dict[str, Any] = {
    "model_s": {
        "name": "Model S",
        "battery": "sensor.model_s_p100d_battery_level",
        "charging": "sensor.model_s_p100d_charging",
        "charger_power": "sensor.model_s_p100d_charger_power",
        "image": "model-s-white.webp",
        "accent": "#E8EEF4",
    },
    "model_x": {
        "name": "Model X",
        "battery": "sensor.x_battery_level",
        "charging": "sensor.x_charging",
        "charger_power": "sensor.x_charger_power",
        "image": "model-x-blue.webp",
        "accent": "#4FC3F7",
    },
}


def _image_data_uri(filename: str) -> str:
    """Inline image so Tesla art renders even when /local SMB paths fail."""
    path = _TESLA_DIR / filename
    if not path.exists():
        # Fall back to png / svg siblings.
        stem = path.stem
        for ext, mime in ((".webp", "image/webp"), (".png", "image/png"), (".svg", "image/svg+xml")):
            alt = _TESLA_DIR / f"{stem}{ext}" if ext != path.suffix else path
            if alt.exists():
                path = alt
                break
        else:
            return f"/local/flux-ui/tesla/{filename}"
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    mime = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix, "image/png")
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _charging_js(charging_entity: str) -> str:
    return (
        "const st = String(states['"
        + charging_entity
        + "']?.state || '').toLowerCase();\n"
        "return ['charging','connected','on'].includes(st);"
    )


def _vehicle_triggers(vehicle: dict) -> list[str]:
    return [vehicle[k] for k in ("battery", "charging", "charger_power") if vehicle.get(k)]


def _tesla_vehicle_card(vehicle: dict) -> dict:
    """Tesla-app style tile — big car photo, SOC, charging line; no glass chrome."""
    name = vehicle.get("name") or "Tesla"
    battery = vehicle["battery"]
    charging = vehicle["charging"]
    power = vehicle.get("charger_power") or battery
    image_uri = _image_data_uri(vehicle.get("image") or "model-s-white.webp")
    accent = vehicle.get("accent") or "#E8EEF4"

    return {
        "type": "custom:button-card",
        "entity": battery,
        "show_icon": False,
        "show_name": True,
        "show_label": True,
        "show_state": False,
        "show_entity_picture": True,
        "entity_picture": image_uri,
        "name": (
            "[[[\n"
            f"  const soc = states['{battery}']?.state;\n"
            f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
            "  const color = charging ? '#66BB6A' : 'var(--primary-text-color)';\n"
            f"  const pct = (soc == null || ['unavailable','unknown'].includes(String(soc))) "
            f"? '—' : soc;\n"
            "  return `<span style=\"color:${color}\">${pct}"
            "<span style=\"font-size:0.45em;opacity:0.85;margin-left:2px;\">%</span></span>`;\n"
            "]]]"
        ),
        "label": (
            "[[[\n"
            f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
            f"  const st = String(states['{charging}']?.state || '').toLowerCase();\n"
            f"  const pwr = states['{power}']?.state;\n"
            f"  const title = '{name}';\n"
            "  let status = charging ? 'Charging' : 'Not charging';\n"
            "  if (!charging && st && !['unavailable','unknown','off','disconnected',"
            "'idle','complete','stopped',''].includes(st)) status = st;\n"
            "  const kw = charging && pwr != null && Number(pwr) > 0 ? ` · ${pwr} kW` : '';\n"
            "  return `${title} · ${status}${kw}`;\n"
            "]]]"
        ),
        "triggers_update": _vehicle_triggers(vehicle),
        "tap_action": {"action": "more-info", "entity": battery},
        "styles": {
            "grid": [
                {"grid-template-areas": "'n i' 'l i' 'bar i'"},
                {"grid-template-columns": "minmax(88px, 0.55fr) 1.45fr"},
                {"grid-template-rows": "min-content min-content min-content"},
                {"align-items": "center"},
            ],
            "card": [
                {"background": "transparent"},
                {"box-shadow": "none"},
                {"border": "none"},
                {"border-radius": "0"},
                {"backdrop-filter": "none"},
                {"-webkit-backdrop-filter": "none"},
                {"padding": "8px 4px 8px 8px"},
                {"min-height": "120px"},
                {"height": "auto"},
                {"overflow": "visible"},
            ],
            "name": [
                {"justify-self": "start"},
                {"align-self": "end"},
                {"font-size": "42px"},
                {"font-weight": "700"},
                {"letter-spacing": "-0.02em"},
                {"line-height": "1"},
                {"padding": "0"},
                {"margin": "0"},
            ],
            "label": [
                {"justify-self": "start"},
                {"align-self": "start"},
                {"font-size": "13px"},
                {"font-weight": "600"},
                {"opacity": "0.78"},
                {"padding-top": "4px"},
            ],
            "img_cell": [
                {"justify-self": "end"},
                {"align-self": "center"},
                {"width": "100%"},
                {"max-width": "100%"},
                {"overflow": "visible"},
                {"background": "transparent"},
                {"border-radius": "0"},
                {"padding": "0"},
                {"margin": "0"},
            ],
            "entity_picture": [
                {"width": "100%"},
                {"max-height": "110px"},
                {"object-fit": "contain"},
                {"object-position": "right center"},
                {"background": "transparent"},
                {"border-radius": "0"},
            ],
            "custom_fields": {
                "bar": [
                    {"grid-area": "bar"},
                    {"justify-self": "stretch"},
                    {"width": "100%"},
                    {"padding-top": "8px"},
                ]
            },
        },
        "custom_fields": {
            "bar": (
                "[[[\n"
                f"  const raw = Number(states['{battery}']?.state);\n"
                "  const pct = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 0;\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                f"  const fill = charging ? '#66BB6A' : '{accent}';\n"
                "  return `<div style=\"width:100%;height:5px;border-radius:999px;"
                "background:rgba(255,255,255,0.14);\">"
                "<div style=\"width:${pct}%;height:100%;border-radius:999px;background:${fill};"
                "transition:width 0.35s ease;\"></div></div>`;\n"
                "]]]"
            )
        },
    }


def tablet_tesla_config(cfg: dict) -> dict[str, Any]:
    """Merge entities.yaml tablet_tesla block with Tessie defaults."""
    raw = {k: dict(v) if isinstance(v, dict) else v for k, v in _DEFAULT_TESLA.items()}
    user = cfg.get("tablet_tesla") or {}
    for key in ("model_s", "model_x"):
        if isinstance(user.get(key), dict):
            raw[key].update(user[key])
    return raw


def build_tablet_tesla_tiles(cfg: dict) -> list[dict]:
    """Model X + Model S — each fills half of the camera row width."""
    tesla = tablet_tesla_config(cfg)
    return [
        _tesla_vehicle_card(tesla["model_x"]),
        _tesla_vehicle_card(tesla["model_s"]),
    ]


def build_tablet_tesla_band(cfg: dict, *, view_layout: dict) -> dict:
    """Two equal columns spanning the full camera-band width."""
    return {
        "type": "grid",
        "columns": 2,
        "square": False,
        "view_layout": view_layout,
        "cards": build_tablet_tesla_tiles(cfg),
        "card_mod": {
            "style": (
                ":host, ha-card {\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  padding-bottom: 72px !important;\n"
                "  box-sizing: border-box !important;\n"
                "}\n"
                "#root {\n"
                "  background: transparent !important;\n"
                "  gap: 12px !important;\n"
                "}\n"
            )
        },
    }

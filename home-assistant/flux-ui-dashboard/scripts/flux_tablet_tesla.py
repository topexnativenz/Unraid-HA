"""Tesla tiles for the 16:9 tablet overview (full-width row under cameras).

Visual language matches Tesla companion cards: black stage, floating side-profile
car photo on top, status + SOC underneath — no glass chrome.
"""

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
        stem = Path(filename).stem
        for ext in (".webp", ".png", ".svg"):
            alt = _TESLA_DIR / f"{stem}{ext}"
            if alt.exists():
                path = alt
                break
        else:
            return f"/local/flux-ui/tesla/{filename}"
    raw = path.read_bytes()
    mime = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(path.suffix.lower(), "image/png")
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
    """Tesla-app / companion-card style — car hero on black, status below."""
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
        "show_name": False,
        "show_label": False,
        "show_state": False,
        "show_entity_picture": False,
        "triggers_update": _vehicle_triggers(vehicle),
        "tap_action": {"action": "more-info", "entity": battery},
        "styles": {
            "grid": [
                {"grid-template-areas": "'hdr' 'car' 'soc' 'bar'"},
                {"grid-template-columns": "1fr"},
                {"grid-template-rows": "min-content min-content min-content min-content"},
            ],
            "card": [
                # Black stage so the cutout car floats like the Tesla companion card.
                {"background": "#000000"},
                {"box-shadow": "none"},
                {"border": "1px solid rgba(255,255,255,0.08)"},
                {"border-radius": "18px"},
                {"backdrop-filter": "none"},
                {"-webkit-backdrop-filter": "none"},
                {"padding": "10px 14px 14px 14px"},
                {"min-height": "168px"},
                {"height": "auto"},
                {"overflow": "hidden"},
            ],
            "custom_fields": {
                "hdr": [{"grid-area": "hdr"}, {"width": "100%"}],
                "car": [
                    {"grid-area": "car"},
                    {"width": "100%"},
                    {"justify-self": "center"},
                    {"padding": "4px 0 2px 0"},
                ],
                "soc": [{"grid-area": "soc"}, {"width": "100%"}, {"padding-top": "2px"}],
                "bar": [{"grid-area": "bar"}, {"width": "100%"}, {"padding-top": "8px"}],
            },
        },
        "custom_fields": {
            # Top meta row — mirrors companion-card "15 hours … PARKED" strip.
            "hdr": (
                "[[[\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                f"  const pwr = states['{power}']?.state;\n"
                f"  const title = '{name}';\n"
                "  const left = charging\n"
                "    ? (pwr != null && Number(pwr) > 0 ? `${pwr} kW` : 'Charging')\n"
                "    : title;\n"
                "  const right = charging ? 'CHARGING' : 'NOT CHARGING';\n"
                "  const rightColor = charging ? '#66BB6A' : 'rgba(255,255,255,0.72)';\n"
                "  return `<div style=\"display:flex;justify-content:space-between;align-items:center;"
                "gap:10px;font-size:11px;letter-spacing:0.04em;text-transform:uppercase;"
                "font-weight:600;color:rgba(255,255,255,0.78);\">"
                "<span>• ${left}</span>"
                "<span style=\"color:${rightColor};\">${right}</span></div>`;\n"
                "]]]"
            ),
            # Hero car — full-width floating side profile (same treatment as companion card).
            "car": (
                "[[[\n"
                f"  return `<div style=\"width:100%;display:flex;justify-content:center;"
                f"align-items:center;min-height:96px;\">"
                f"<img src=\"{image_uri}\" alt=\"{name}\" "
                f"style=\"width:100%;max-height:118px;object-fit:contain;"
                f"object-position:center center;background:transparent;"
                f"filter:drop-shadow(0 14px 18px rgba(0,0,0,0.55));\" /></div>`;\n"
                "]]]"
            ),
            "soc": (
                "[[[\n"
                f"  const soc = states['{battery}']?.state;\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                "  const color = charging ? '#66BB6A' : '#ffffff';\n"
                "  const pct = (soc == null || ['unavailable','unknown'].includes(String(soc))) "
                "? '—' : soc;\n"
                f"  const title = '{name}';\n"
                "  return `<div style=\"display:flex;justify-content:space-between;"
                "align-items:baseline;gap:12px;\">"
                "<div style=\"font-size:34px;font-weight:700;line-height:1;color:${color};"
                "letter-spacing:-0.02em;\">${pct}"
                "<span style=\"font-size:15px;opacity:0.8;margin-left:2px;\">%</span></div>"
                "<div style=\"font-size:12px;font-weight:600;color:rgba(255,255,255,0.7);"
                "text-align:right;\">${title}</div></div>`;\n"
                "]]]"
            ),
            "bar": (
                "[[[\n"
                f"  const raw = Number(states['{battery}']?.state);\n"
                "  const pct = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 0;\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                f"  const fill = charging ? '#66BB6A' : '{accent}';\n"
                "  return `<div style=\"width:100%;height:4px;border-radius:999px;"
                "background:rgba(255,255,255,0.14);\">"
                "<div style=\"width:${pct}%;height:100%;border-radius:999px;background:${fill};"
                "transition:width 0.35s ease;\"></div></div>`;\n"
                "]]]"
            ),
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

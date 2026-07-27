"""Tesla tiles for the 16:9 tablet overview (full-width row under cameras).

Visual language matches Tesla companion cards: black stage, floating side-profile
car photo on top, status + SOC underneath — no glass chrome.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

_TESLA_DIR = Path(__file__).resolve().parents[1] / "www" / "flux-ui" / "tesla"

# Tesla band fills its grid track (see overview % row). No fixed px max —
# fixed 220–240px mins previously pushed Tesla below the Fully Kiosk viewport.
TESLA_BAND_MAX = "100%"

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

_CHARGE_PULSE_CSS = (
    "@keyframes flux-tesla-charge-pulse {\n"
    "  0%, 100% {\n"
    "    box-shadow: 0 0 10px 2px rgba(102, 187, 106, 0.35),\n"
    "      0 0 28px 8px rgba(76, 175, 80, 0.22);\n"
    "  }\n"
    "  50% {\n"
    "    box-shadow: 0 0 22px 6px rgba(129, 199, 132, 0.9),\n"
    "      0 0 52px 16px rgba(76, 175, 80, 0.55);\n"
    "  }\n"
    "}\n"
)


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
    max_h = TESLA_BAND_MAX

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
        "extra_styles": _CHARGE_PULSE_CSS,
        "styles": {
            "grid": [
                {"grid-template-areas": "'hdr' 'car' 'soc' 'bar'"},
                {"grid-template-columns": "1fr"},
                {"grid-template-rows": "min-content 1fr min-content min-content"},
            ],
            "card": [
                {"background": "#000000"},
                {"box-shadow": "none"},
                {"border": "1px solid rgba(255,255,255,0.08)"},
                {"border-radius": "18px"},
                {"backdrop-filter": "none"},
                {"-webkit-backdrop-filter": "none"},
                {"padding": "8px 12px 10px 12px"},
                {"min-height": "0"},
                {"height": "100%"},
                {"max-height": max_h},
                {"overflow": "hidden"},
                {"transition": "box-shadow 0.35s ease, border-color 0.35s ease"},
            ],
            "custom_fields": {
                "hdr": [{"grid-area": "hdr"}, {"width": "100%"}],
                "car": [
                    {"grid-area": "car"},
                    {"width": "100%"},
                    {"justify-self": "center"},
                    {"align-self": "center"},
                    {"min-height": "0"},
                    {"padding": "4px 0 2px 0"},
                ],
                "soc": [{"grid-area": "soc"}, {"width": "100%"}, {"padding-top": "2px"}],
                "bar": [{"grid-area": "bar"}, {"width": "100%"}, {"padding-top": "6px"}],
            },
        },
        "state": [
            {
                "operator": "template",
                "value": f"[[[ {_charging_js(charging)} ]]]",
                "styles": {
                    "card": [
                        {"border": "1px solid rgba(129, 199, 132, 0.65)"},
                        {"animation": "flux-tesla-charge-pulse 1.6s ease-in-out infinite"},
                    ]
                },
            }
        ],
        "custom_fields": {
            "hdr": (
                "[[[\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                f"  const pwr = states['{power}']?.state;\n"
                f"  const title = '{name}';\n"
                "  const left = charging\n"
                "    ? (pwr != null && Number(pwr) > 0 ? `${pwr} kW` : 'Charging')\n"
                "    : title;\n"
                "  const right = charging ? 'CHARGING' : 'NOT CHARGING';\n"
                "  const rightColor = charging ? '#81C784' : 'rgba(255,255,255,0.72)';\n"
                "  const rightGlow = charging\n"
                "    ? 'text-shadow:0 0 10px rgba(129,199,132,0.95),0 0 22px rgba(76,175,80,0.7);'\n"
                "    : '';\n"
                "  return `<div style=\"display:flex;justify-content:space-between;align-items:center;"
                "gap:10px;font-size:11px;letter-spacing:0.04em;text-transform:uppercase;"
                "font-weight:600;color:rgba(255,255,255,0.78);\">"
                "<span>• ${left}</span>"
                "<span style=\"color:${rightColor};font-weight:700;${rightGlow}\">${right}</span>"
                "</div>`;\n"
                "]]]"
            ),
            "car": (
                "[[[\n"
                f"  return `<div style=\"width:100%;height:100%;display:flex;justify-content:center;"
                f"align-items:center;min-height:0;max-height:100%;flex:1;\">"
                f"<img src=\"{image_uri}\" alt=\"{name}\" "
                f"style=\"width:100%;max-height:100%;object-fit:contain;"
                f"object-position:center center;background:transparent;"
                f"filter:drop-shadow(0 14px 18px rgba(0,0,0,0.55));\" /></div>`;\n"
                "]]]"
            ),
            "soc": (
                "[[[\n"
                f"  const soc = states['{battery}']?.state;\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                "  const color = charging ? '#81C784' : '#ffffff';\n"
                "  const glow = charging\n"
                "    ? 'text-shadow:0 0 14px rgba(129,199,132,0.85);'\n"
                "    : '';\n"
                "  const pct = (soc == null || ['unavailable','unknown'].includes(String(soc))) "
                "? '—' : soc;\n"
                f"  const title = '{name}';\n"
                "  return `<div style=\"display:flex;justify-content:space-between;"
                "align-items:baseline;gap:12px;\">"
                "<div style=\"font-size:28px;font-weight:700;line-height:1;color:${color};"
                "letter-spacing:-0.02em;${glow}\">${pct}"
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
                "  const barGlow = charging\n"
                "    ? 'box-shadow:0 0 10px rgba(102,187,106,0.85);'\n"
                "    : '';\n"
                "  return `<div style=\"width:100%;height:4px;border-radius:999px;"
                "background:rgba(255,255,255,0.14);\">"
                "<div style=\"width:${pct}%;height:100%;border-radius:999px;background:${fill};"
                "transition:width 0.35s ease;${barGlow}\"></div></div>`;\n"
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
    """Model X + Model S — each fills half of the Tesla band."""
    tesla = tablet_tesla_config(cfg)
    return [
        _tesla_vehicle_card(tesla["model_x"]),
        _tesla_vehicle_card(tesla["model_s"]),
    ]


def build_tablet_tesla_band(cfg: dict, *, view_layout: dict) -> dict:
    """Two equal Tesla cards — layout-card so gap matches rooms/cameras (8px)."""
    max_h = TESLA_BAND_MAX
    return {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "view_layout": view_layout,
        "layout": {
            "grid-template-columns": "1fr 1fr",
            "grid-template-rows": "minmax(0, 1fr)",
            "grid-gap": "8px",
            "gap": "8px",
            "height": "100%",
            "width": "100%",
            "max_width": "100%",
            "margin": "0",
            "padding": "0",
            "card_margin": "0",
            "align-items": "stretch",
            "justify-items": "stretch",
        },
        "cards": build_tablet_tesla_tiles(cfg),
        "card_mod": {
            "style": (
                ":host {\n"
                "  display: block !important;\n"
                "  height: 100% !important;\n"
                f"  max-height: {max_h} !important;\n"
                "  min-height: 0 !important;\n"
                "  width: 100% !important;\n"
                "  overflow: hidden !important;\n"
                "  box-sizing: border-box !important;\n"
                "}\n"
                "ha-card, #root, .layout, layout-card {\n"
                "  height: 100% !important;\n"
                f"  max-height: {max_h} !important;\n"
                "  min-height: 0 !important;\n"
                "  width: 100% !important;\n"
                "  background: transparent !important;\n"
                "  box-shadow: none !important;\n"
                "  border: none !important;\n"
                "  box-sizing: border-box !important;\n"
                "}\n"
                "#root > *, .layout > * {\n"
                "  min-height: 0 !important;\n"
                "  min-width: 0 !important;\n"
                "  height: 100% !important;\n"
                f"  max-height: {max_h} !important;\n"
                "  overflow: hidden !important;\n"
                "}\n"
            )
        },
    }

"""Tesla tiles for the 16:9 tablet overview (compact strip under cameras)."""

from __future__ import annotations

from typing import Any

_DEFAULT_TESLA: dict[str, Any] = {
    "model_s": {
        "name": "Model S",
        "battery": "sensor.garage_model_s_battery",
        "charging": "sensor.garage_model_s_charging",
        "charger_power": "sensor.garage_model_s_charger_power",
        "image": "model-s-white.png",
        "accent": "#E8EEF4",
    },
    "model_x": {
        "name": "Model X",
        "battery": "sensor.garage_model_x_battery",
        "charging": "sensor.garage_model_x_charging",
        "charger_power": "sensor.garage_model_x_charger_power",
        "image": "model-x-blue.png",
        "accent": "#1565C0",
    },
}


def _image_uri(filename: str) -> str:
    """Serve from /local — deploy copies www/flux-ui/tesla/*.png over SMB."""
    return f"/local/flux-ui/tesla/{filename}"


def _charging_js(charging_entity: str) -> str:
    return (
        "const st = String(states['"
        + charging_entity
        + "']?.state || '').toLowerCase();\n"
        "return st === 'charging' || st === 'connected' || st === 'on';"
    )


def _vehicle_triggers(vehicle: dict) -> list[str]:
    keys = ("battery", "charging", "charger_power")
    return [vehicle[k] for k in keys if vehicle.get(k)]


def _tesla_vehicle_card(vehicle: dict) -> dict:
    """Tesla-app style tile — transparent chrome, photo cutout, SOC + charge state."""
    name = vehicle.get("name") or "Tesla"
    battery = vehicle["battery"]
    charging = vehicle["charging"]
    power = vehicle.get("charger_power") or battery
    image_file = vehicle.get("image") or "model-s-white.png"
    image_uri = _image_uri(image_file)
    accent = vehicle.get("accent") or "#E8EEF4"

    return {
        "type": "custom:button-card",
        "show_icon": False,
        "show_name": False,
        "show_label": False,
        "entity": battery,
        "triggers_update": _vehicle_triggers(vehicle),
        "tap_action": {"action": "more-info", "entity": battery},
        "styles": {
            "grid": [
                {"grid-template-areas": "'soc car' 'bar bar' 'meta meta'"},
                {"grid-template-columns": "minmax(72px, 0.7fr) 1.3fr"},
                {"grid-template-rows": "minmax(0, 1fr) 4px min-content"},
            ],
            "card": [
                {"background": "transparent"},
                {"box-shadow": "none"},
                {"border": "none"},
                {"border-radius": "0"},
                {"backdrop-filter": "none"},
                {"padding": "4px 6px 2px 2px"},
                {"min-height": "96px"},
                {"height": "100%"},
                {"overflow": "visible"},
            ],
            "custom_fields": {
                "soc": [{"grid-area": "soc"}, {"align-self": "center"}, {"justify-self": "start"}],
                "car": [
                    {"grid-area": "car"},
                    {"align-self": "center"},
                    {"justify-self": "end"},
                    {"width": "100%"},
                    {"max-height": "78px"},
                    {"overflow": "visible"},
                ],
                "bar": [{"grid-area": "bar"}, {"width": "100%"}],
                "meta": [{"grid-area": "meta"}, {"width": "100%"}],
            },
        },
        "custom_fields": {
            "soc": (
                "[[[\n"
                f"  const soc = states['{battery}']?.state ?? '—';\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                "  const color = charging ? '#66BB6A' : 'var(--primary-text-color)';\n"
                f"  return `<div style=\"line-height:1;\">"
                f"<div style=\"font-size:11px;font-weight:600;opacity:0.7;margin-bottom:4px;\">{name}</div>"
                f"<div style=\"font-size:30px;font-weight:700;color:${{color}};\">${{soc}}"
                f"<span style=\"font-size:14px;opacity:0.85;\">%</span></div>"
                f"</div>`;\n"
                "]]]"
            ),
            "car": (
                "[[[\n"
                f"  return `<img src=\"{image_uri}\" alt=\"{name}\" "
                f"style=\"width:100%;max-height:78px;object-fit:contain;"
                f"object-position:right center;background:transparent;\" />`;\n"
                "]]]"
            ),
            "bar": (
                "[[[\n"
                f"  const raw = Number(states['{battery}']?.state);\n"
                f"  const pct = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 0;\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                f"  const fill = charging ? '#66BB6A' : '{accent}';\n"
                "  return `<div style=\"width:100%;height:4px;border-radius:999px;"
                "background:color-mix(in srgb, var(--primary-text-color) 14%, transparent);\">"
                "<div style=\"width:${pct}%;height:100%;border-radius:999px;background:${fill};"
                "transition:width 0.35s ease;\"></div></div>`;\n"
                "]]]"
            ),
            "meta": (
                "[[[\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                f"  const st = states['{charging}']?.state ?? '—';\n"
                f"  const pwr = states['{power}']?.state ?? '0';\n"
                "  const status = charging ? 'Charging' : "
                "(['disconnected','off','idle','complete','stopped'].includes(String(st).toLowerCase()) "
                "? 'Not charging' : (st || 'Not charging'));\n"
                "  const pColor = charging ? '#66BB6A' : 'var(--secondary-text-color)';\n"
                "  const pLabel = charging && Number(pwr) > 0 ? `${pwr} kW` : '';\n"
                "  return `<div style=\"display:flex;justify-content:space-between;align-items:center;"
                "font-size:11px;margin-top:4px;gap:8px;\">"
                "<span style=\"font-weight:600;color:${pColor};text-transform:capitalize;\">${status}</span>"
                "<span style=\"font-weight:600;color:${pColor};\">${pLabel}</span></div>`;\n"
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
    """Model X + Model S only (Tesla-app style)."""
    tesla = tablet_tesla_config(cfg)
    return [
        _tesla_vehicle_card(tesla["model_x"]),
        _tesla_vehicle_card(tesla["model_s"]),
    ]


def build_tablet_tesla_band(cfg: dict, *, view_layout: dict) -> dict:
    """Two vehicle tiles in the left half of a 4-col row (half the old 4-tile footprint)."""
    tiles = build_tablet_tesla_tiles(cfg)
    # Invisible spacers keep the two cars in the left half of the previous 4-slot band.
    spacers = [
        {
            "type": "custom:button-card",
            "show_icon": False,
            "show_name": False,
            "styles": {
                "card": [
                    {"background": "transparent"},
                    {"box-shadow": "none"},
                    {"border": "none"},
                    {"padding": "0"},
                    {"height": "1px"},
                ]
            },
        }
        for _ in range(2)
    ]
    return {
        "type": "grid",
        "columns": 4,
        "square": False,
        "view_layout": view_layout,
        "cards": [*tiles, *spacers],
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
                "}\n"
            )
        },
    }

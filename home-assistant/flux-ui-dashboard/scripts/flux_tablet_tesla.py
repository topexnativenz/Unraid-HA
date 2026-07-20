"""Tesla / Tessie tiles for the 16:9 tablet overview (replaces camera band)."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from md3_templates import GLASS_CARD_MOD, wrap_glass

_TESLA_DIR = Path(__file__).resolve().parents[1] / "www" / "flux-ui" / "tesla"

_DEFAULT_TESLA: dict[str, Any] = {
    "model_s": {
        "name": "Model S",
        "battery": "sensor.garage_model_s_battery",
        "charging": "sensor.garage_model_s_charging",
        "charger_power": "sensor.garage_model_s_charger_power",
        "charge_energy": "sensor.model_s_p100d_charge_energy_added",
        "software_update": "update.model_s_p100d",
        "image": "model-s-white.svg",
        "accent": "#E8EEF4",
    },
    "model_x": {
        "name": "Model X",
        "battery": "sensor.garage_model_x_battery",
        "charging": "sensor.garage_model_x_charging",
        "charger_power": "sensor.garage_model_x_charger_power",
        "charge_energy": "sensor.tesla_model_x_charge_energy_added",
        "software_update": "update.tesla_model_x",
        "image": "model-x-blue.svg",
        "accent": "#1565C0",
    },
    "charge_history_days": 7,
}


def _svg_data_uri(filename: str) -> str:
    """Inline SVG so vehicle art works when SMB cannot mkdir www/flux-ui/tesla."""
    raw = (_TESLA_DIR / filename).read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")


def _charging_js(charging_entity: str) -> str:
    return (
        "const st = String(states['"
        + charging_entity
        + "']?.state || '').toLowerCase();\n"
        "return st === 'charging' || st === 'connected';"
    )


def _vehicle_triggers(vehicle: dict) -> list[str]:
    keys = ("battery", "charging", "charger_power", "software_update")
    return [vehicle[k] for k in keys if vehicle.get(k)]


def _tesla_vehicle_card(vehicle: dict) -> dict:
    """Tesla-app style tile — SOC, charging state, car silhouette."""
    name = vehicle.get("name") or "Tesla"
    battery = vehicle["battery"]
    charging = vehicle["charging"]
    power = vehicle.get("charger_power") or battery
    image_file = vehicle.get("image") or "model-s-white.svg"
    image_uri = _svg_data_uri(image_file)
    accent = vehicle.get("accent") or "#E8EEF4"
    is_charging = _charging_js(charging)

    return {
        "type": "custom:button-card",
        "template": "flux_glass",
        "show_icon": False,
        "show_name": False,
        "show_label": False,
        "entity": battery,
        "triggers_update": _vehicle_triggers(vehicle),
        "tap_action": {"action": "more-info", "entity": battery},
        "styles": {
            "grid": [
                {"grid-template-areas": "'soc car' 'bar bar' 'meta meta'"},
                {"grid-template-columns": "1fr 1.15fr"},
                {"grid-template-rows": "minmax(0, 1fr) 6px min-content"},
            ],
            "card": [
                {"min-height": "132px"},
                {"height": "100%"},
                {"padding": "12px 14px 10px 14px"},
                {"overflow": "hidden"},
            ],
            "custom_fields": {
                "soc": [{"grid-area": "soc"}, {"align-self": "start"}, {"justify-self": "start"}],
                "car": [
                    {"grid-area": "car"},
                    {"align-self": "end"},
                    {"justify-self": "end"},
                    {"width": "100%"},
                    {"max-height": "88px"},
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
                f"<div style=\"font-size:11px;font-weight:600;opacity:0.72;margin-bottom:4px;\">{name}</div>"
                f"<div style=\"font-size:34px;font-weight:700;color:${{color}};\">${{soc}}<span style=\"font-size:16px;opacity:0.85;\">%</span></div>"
                f"</div>`;\n"
                "]]]"
            ),
            "car": (
                "[[[\n"
                f"  return `<img src=\"{image_uri}\" alt=\"{name}\" "
                f"style=\"width:100%;max-height:88px;object-fit:contain;object-position:right bottom;"
                f"filter:drop-shadow(0 10px 14px rgba(0,0,0,0.28));\" />`;\n"
                "]]]"
            ),
            "bar": (
                "[[[\n"
                f"  const raw = Number(states['{battery}']?.state);\n"
                f"  const pct = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 0;\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                f"  const fill = charging ? '#66BB6A' : '{accent}';\n"
                "  return `<div style=\"width:100%;height:6px;border-radius:999px;"
                "background:color-mix(in srgb, var(--primary-text-color) 12%, transparent);\">"
                "<div style=\"width:${pct}%;height:100%;border-radius:999px;background:${fill};"
                "transition:width 0.35s ease;\"></div></div>`;\n"
                "]]]"
            ),
            "meta": (
                "[[[\n"
                f"  const charging = (() => {{ {_charging_js(charging)} }})();\n"
                f"  const st = states['{charging}']?.state ?? '—';\n"
                f"  const pwr = states['{power}']?.state ?? '0';\n"
                "  const status = charging ? 'Charging' : (String(st).toLowerCase() === 'disconnected' ? 'Not charging' : st);\n"
                "  const pColor = charging ? '#66BB6A' : 'var(--secondary-text-color)';\n"
                "  const pLabel = charging && Number(pwr) > 0 ? `${pwr} kW` : '';\n"
                "  return `<div style=\"display:flex;justify-content:space-between;align-items:center;"
                "font-size:12px;margin-top:8px;gap:8px;\">"
                "<span style=\"font-weight:600;color:${pColor};text-transform:capitalize;\">${status}</span>"
                "<span style=\"font-weight:600;color:${pColor};\">${pLabel}</span></div>`;\n"
                "]]]"
            ),
        },
    }


def _software_tracker_card(model_s: dict, model_x: dict) -> dict:
    """Both vehicles — Tessie software versions and pending updates."""

    def _row_js(label: str, update_entity: str) -> str:
        return (
            f"{{ const u = states['{update_entity}'];\n"
            f"const label = '{label}';\n"
            "if (!u) {\n"
            "  rows.push(`<div style=\"margin-top:8px;padding-top:8px;"
            "border-top:1px solid color-mix(in srgb, var(--primary-text-color) 10%, transparent);\">"
            "<div style=\"font-weight:700;font-size:12px;margin-bottom:4px;\">${label}</div>"
            "<div style=\"font-size:11px;opacity:0.65;\">Unavailable</div></div>`);\n"
            "} else {\n"
            "const cur = u.attributes?.installed_version || u.attributes?.auto_update || u.state;\n"
            "const latest = u.attributes?.latest_version;\n"
            "const pending = latest && cur && String(latest).split(' ')[0] !== String(cur).split(' ')[0];\n"
            "const inProg = u.attributes?.in_progress;\n"
            "const pct = u.attributes?.update_percentage;\n"
            "let status = pending ? `Update ${latest}` : 'Up to date';\n"
            "let color = pending ? '#FFB74D' : '#81C784';\n"
            "if (inProg) { status = pct != null ? `Installing ${pct}%` : 'Installing…'; color = '#64B5F6'; }\n"
            "else if (u.state === 'on' && pending) { status = 'Ready to install'; color = '#FFB74D'; }\n"
            "rows.push(`<div style=\"margin-top:8px;padding-top:8px;"
            "border-top:1px solid color-mix(in srgb, var(--primary-text-color) 10%, transparent);\">"
            "<div style=\"font-weight:700;font-size:12px;margin-bottom:4px;\">${label}</div>"
            "<div style=\"display:flex;justify-content:space-between;gap:8px;font-size:11px;\">"
            "<span style=\"opacity:0.85;\">${cur || '—'}</span>"
            "<span style=\"font-weight:600;color:${color};\">${status}</span></div></div>`);\n"
            "} }\n"
        )

    update_s = model_s.get("software_update") or ""
    update_x = model_x.get("software_update") or ""
    triggers = [e for e in (update_s, update_x) if e]

    body = "const rows = [];\n" + _row_js("Model S", update_s) + _row_js("Model X", update_x)

    return {
        "type": "custom:button-card",
        "template": "flux_glass",
        "show_icon": False,
        "show_name": False,
        "show_label": False,
        "entity": update_s or update_x or battery_entity_fallback(model_s),
        "triggers_update": triggers,
        "tap_action": (
            {"action": "more-info", "entity": update_s}
            if update_s
            else {"action": "none"}
        ),
        "styles": {
            "grid": [{"grid-template-areas": "'h' 'b'"}, {"grid-template-columns": "1fr"}],
            "card": [{"min-height": "132px"}, {"height": "100%"}, {"padding": "12px 14px"}],
            "custom_fields": {
                "h": [{"grid-area": "h"}],
                "b": [{"grid-area": "b"}, {"width": "100%"}],
            },
        },
        "custom_fields": {
            "h": (
                "[[[\n"
                "  return `<div style=\"font-size:13px;font-weight:700;\">"
                "Software tracker</div>"
                "<div style=\"font-size:11px;opacity:0.65;margin-top:2px;\">Tessie</div>`;\n"
                "]]]"
            ),
            "b": f"[[[\n  {body}\n  return rows.join('');\n]]]",
        },
    }


def battery_entity_fallback(vehicle: dict) -> str:
    return str(vehicle.get("battery") or "sensor.garage_model_s_battery")


def _charge_history_card(model_s: dict, model_x: dict, *, days: int = 7) -> dict:
    """Both vehicles — energy added over the last N days (charge sessions)."""
    span = f"{days}d"
    series: list[dict] = []
    for vehicle, default_name in ((model_s, "Model S"), (model_x, "Model X")):
        entity = vehicle.get("charge_energy")
        if not entity:
            continue
        series.append(
            {
                "entity": entity,
                "name": vehicle.get("name") or default_name,
                "type": "column",
                "color": vehicle.get("accent") or "#90CAF9",
                "group_by": {"func": "diff", "duration": "6h"},
                "show": {"legend_value": True},
            }
        )

    if not series:
        return wrap_glass(
            {
                "type": "markdown",
                "content": "Configure `charge_energy` entities in `entities.yaml` → `tablet_tesla`.",
            }
        )

    chart: dict[str, Any] = {
        "graph_span": span,
        "span": {"start": "day"},
        "header": {
            "show": True,
            "title": f"Last charges ({days} days)",
            "show_states": False,
            "colorize_states": False,
        },
        "now": {"show": False},
        "apex_config": {
            "chart": {"height": 118, "toolbar": {"show": False}, "fontFamily": "inherit"},
            "legend": {"show": True, "fontSize": "11px", "position": "top", "horizontalAlign": "left"},
            "grid": {"padding": {"left": 4, "right": 4, "top": 0, "bottom": 0}},
            "dataLabels": {"enabled": False},
            "xaxis": {"labels": {"show": True, "style": {"fontSize": "10px"}}},
            "yaxis": {
                "labels": {"style": {"fontSize": "10px"}},
                "title": {"text": "kWh", "style": {"fontSize": "10px"}},
            },
            "tooltip": {"theme": "dark"},
        },
        "series": series,
    }
    card = {"type": "custom:apexcharts-card", **chart}
    return wrap_glass(card)


def tablet_tesla_config(cfg: dict) -> dict[str, Any]:
    """Merge entities.yaml tablet_tesla block with Tessie defaults."""
    raw = dict(_DEFAULT_TESLA)
    user = cfg.get("tablet_tesla") or {}
    for key in ("model_s", "model_x"):
        merged = dict(raw[key])
        if isinstance(user.get(key), dict):
            merged.update(user[key])
        raw[key] = merged
    if user.get("charge_history_days"):
        raw["charge_history_days"] = int(user["charge_history_days"])
    return raw


def build_tablet_tesla_tiles(cfg: dict) -> list[dict]:
    """Four tiles: Model X, Model S, software tracker, charge history."""
    tesla = tablet_tesla_config(cfg)
    model_s = tesla["model_s"]
    model_x = tesla["model_x"]
    days = int(tesla.get("charge_history_days") or 7)
    # User asked for Model X first, then Model S (matches garage layout).
    return [
        _tesla_vehicle_card(model_x),
        _tesla_vehicle_card(model_s),
        _software_tracker_card(model_s, model_x),
        _charge_history_card(model_s, model_x, days=days),
    ]


def build_tablet_tesla_band(cfg: dict, *, view_layout: dict) -> dict:
    """2×2-capable row replacing the old camera band on tablet overview."""
    tiles = build_tablet_tesla_tiles(cfg)
    fill_mod = {
        "style": (
            ":host, ha-card {\n"
            "  height: 100% !important;\n"
            "  min-height: 0 !important;\n"
            "  overflow: hidden !important;\n"
            "  padding-bottom: 72px !important;\n"
            "  box-sizing: border-box !important;\n"
            "}\n"
            "#root {\n"
            "  height: 100% !important;\n"
            "  min-height: 0 !important;\n"
            "}\n"
        )
    }
    return {
        "type": "grid",
        "columns": 4,
        "square": False,
        "view_layout": view_layout,
        "cards": tiles,
        "card_mod": {"style": GLASS_CARD_MOD["style"] + fill_mod["style"]},
    }

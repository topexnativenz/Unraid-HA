"""Shared JS helpers — room detail status chips with keyword sensor discovery."""

from __future__ import annotations


def _find_sensor_js(kind: str) -> str:
    var = "tempId" if kind == "temp" else "humidId"
    explicit = "variables.temperature_entity" if kind == "temp" else "variables.humidity_entity"
    dc = "temperature" if kind == "temp" else "humidity"
    return (
        f"  let {var} = {explicit};\n"
        f"  if (!{var} || !states[{var}] || ['unavailable','unknown'].includes(states[{var}].state)) {{\n"
        f"    const keywords = (variables.keywords || []).map(k => k.toLowerCase());\n"
        f"    for (const [eid, st] of Object.entries(states)) {{\n"
        f"      if (!eid.startsWith('sensor.')) continue;\n"
        f"      const cls = st.attributes?.device_class || '';\n"
        f"      const hay = (eid + ' ' + (st.attributes?.friendly_name || '')).toLowerCase();\n"
        f"      if (cls !== '{dc}' && !hay.includes('{dc}')) continue;\n"
        f"      if (keywords.some(k => hay.includes(k))) {{ {var} = eid; break; }}\n"
        f"    }}\n"
        f"  }}\n"
    )


_FIND_OCCUPANCY_JS = (
    "  let occId = variables.occupancy_entity;\n"
    "  if (!occId || !states[occId] || ['unavailable','unknown'].includes(states[occId].state)) {\n"
    "    const keywords = (variables.keywords || []).map(k => k.toLowerCase());\n"
    "    for (const [eid, st] of Object.entries(states)) {\n"
    "      if (!eid.startsWith('binary_sensor.')) continue;\n"
    "      const dc = st.attributes?.device_class || '';\n"
    "      const hay = (eid + ' ' + (st.attributes?.friendly_name || '')).toLowerCase();\n"
    "      const isOcc = ['motion','occupancy','presence'].includes(dc) || hay.includes('motion') || hay.includes('occupancy');\n"
    "      if (!isOcc) continue;\n"
    "      if (keywords.some(k => hay.includes(k))) { occId = eid; break; }\n"
    "    }\n"
    "  }\n"
)

ROOM_STATUS_ROW_HTML = (
    "[[[\n"
    + _FIND_OCCUPANCY_JS
    + _find_sensor_js("temp")
    + _find_sensor_js("humid")
    + "  const pill = (label, icon, active) => {\n"
    "    const bg = active\n"
    "      ? 'background:rgba(208,188,255,0.38);border:1px solid rgba(208,188,255,0.65);'\n"
    "      : 'background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.14);';\n"
    "    const color = active ? '#fff' : 'var(--md-sys-color-on-surface-variant)';\n"
    "    return `\n"
    "      <div style=\"display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:999px;"
    "${bg}font-size:12px;font-weight:600;color:${color};white-space:nowrap;\">\n"
    "        <ha-icon icon=\"${icon}\" style=\"width:16px;height:16px;color:inherit;\"></ha-icon>\n"
    "        <span>${label}</span>\n"
    "      </div>`;\n"
    "  };\n"
    "  const chips = [];\n"
    "  if (occId && states[occId] && !['unavailable','unknown'].includes(states[occId].state)) {\n"
    "    const on = ['on','open','home'].includes(states[occId].state);\n"
    "    chips.push(pill(on ? 'Occupied' : 'Empty', 'mdi:account', on));\n"
    "  } else {\n"
    "    chips.push(pill('—', 'mdi:account', false));\n"
    "  }\n"
    "  if (tempId && states[tempId] && !['unavailable','unknown'].includes(states[tempId].state)) {\n"
    "    const v = parseFloat(states[tempId].state);\n"
    "    const t = Number.isFinite(v) ? v.toFixed(1) : states[tempId].state;\n"
    "    chips.push(pill(`Cool (${t}°C)`, 'mdi:thermometer', true));\n"
    "  } else {\n"
    "    chips.push(pill('—°C', 'mdi:thermometer', false));\n"
    "  }\n"
    "  if (humidId && states[humidId] && !['unavailable','unknown'].includes(states[humidId].state)) {\n"
    "    const v = parseFloat(states[humidId].state);\n"
    "    const h = Number.isFinite(v) ? v.toFixed(1) : states[humidId].state;\n"
    "    chips.push(pill(`Humid (${h}%)`, 'mdi:water-percent', true));\n"
    "  } else {\n"
    "    chips.push(pill('—%', 'mdi:water-percent', false));\n"
    "  }\n"
    "  return `<div style=\"display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:2px 0;\">${chips.join('')}</div>`;\n"
    "]]]"
)

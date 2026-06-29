#!/usr/bin/env python3
"""Generate casa-luna-16x9.js from casa-luna/casa-luna.js with 1920×1080 geometry."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "casa-luna" / "www" / "community" / "casa-luna" / "casa-luna.js"
DST = ROOT / "www" / "community" / "casa-luna-16x9" / "casa-luna.js"

VB_W, VB_H = 1920, 1080
SX = VB_W / 1500
SY = VB_H / 1000

# Flow dash geometry (pixel units — not canvas-scaled)
H_CYC = 19.5
V_CYC = 10
CR = 15


def sx(v: float) -> int:
    return round(v * SX)


def sy(v: float) -> int:
    return round(v * SY)


def flow_anchors_32() -> dict[str, int]:
    """Compute 1500×1000 flow anchors (source of truth)."""
    r_stats_1, r_cyl_0 = 136, 1113
    a_y = r_stats_1 + 38 + 3 * 46 + 9 + 20
    batt_y = a_y + 10
    pole_y = a_y + 45
    batt_a_x = r_cyl_0
    batt_h_len = round(12 * H_CYC)
    batt_b_x = batt_a_x - batt_h_len
    batt_v_len = round(5 * V_CYC)
    batt_c_y = batt_y + CR + batt_v_len
    batt_d_len = round(2 * H_CYC)
    batt_d_x = batt_b_x - CR - batt_d_len
    pole_p_x = 300 + round(5 * H_CYC) - 40
    pole_h_len = round((11 - 3) * H_CYC)
    pole_q_x = pole_p_x + pole_h_len
    pole_v_len = round(5 * V_CYC)
    pole_c_y = pole_y + CR + pole_v_len
    pole_d_len = round(2 * H_CYC)
    pole_d_x = pole_q_x + CR + pole_d_len
    return {
        "A_Y": a_y,
        "BATT_Y": batt_y,
        "POLE_Y": pole_y,
        "BATT_A_X": batt_a_x,
        "BATT_B_X": batt_b_x,
        "BATT_C_Y": batt_c_y,
        "BATT_D_X": batt_d_x,
        "BATT_D_LEN": batt_d_len,
        "POLE_P_X": pole_p_x,
        "POLE_Q_X": pole_q_x,
        "POLE_C_Y": pole_c_y,
        "POLE_D_X": pole_d_x,
        "POLE_D_LEN": pole_d_len,
    }


def flow_anchors_16(f32: dict[str, int]) -> dict[str, int]:
    """Scale 3:2 flow anchors to 1920×1080; dash counts stay in px."""
    r_stats_1 = sy(136)
    r_cyl_0 = sx(1113)
    a_y = r_stats_1 + sy(38) + 3 * sy(46) + sy(9) + sy(20)
    batt_y = a_y + sy(10)
    pole_y = a_y + sy(45)
    batt_a_x = r_cyl_0
    batt_h_len = round(12 * H_CYC)
    batt_b_x = batt_a_x - batt_h_len
    batt_v_len = round(5 * V_CYC)
    batt_c_y = batt_y + CR + batt_v_len
    pole_p_x = sx(300) + round(5 * H_CYC) - sx(40)
    pole_h_len = round((11 - 3) * H_CYC)
    pole_q_x = pole_p_x + pole_h_len
    pole_v_len = round(5 * V_CYC)
    pole_c_y = pole_y + CR + pole_v_len
    # House junctions: scale 3:2 endpoint X (dash geometry alone drifts on wider canvas)
    batt_d_x = sx(f32["BATT_D_X"])
    pole_d_x = sx(f32["POLE_D_X"])
    batt_d_len = (batt_b_x - CR) - batt_d_x
    pole_d_len = pole_d_x - (pole_q_x + CR)
    return {
        "A_Y": a_y,
        "BATT_Y": batt_y,
        "POLE_Y": pole_y,
        "BATT_A_X": batt_a_x,
        "BATT_B_X": batt_b_x,
        "BATT_C_Y": batt_c_y,
        "BATT_D_X": batt_d_x,
        "BATT_D_LEN": batt_d_len,
        "POLE_P_X": pole_p_x,
        "POLE_Q_X": pole_q_x,
        "POLE_C_Y": pole_c_y,
        "POLE_D_X": pole_d_x,
        "POLE_D_LEN": pole_d_len,
    }


SL = {
    "nav": {"x": sx(20), "w": sx(211), "h": sy(77), "tops": [sy(t) for t in [146, 229, 311, 396, 485, 568, 652, 735]]},
    "r_cyl": [sx(1113), sy(92), sx(152), sy(288)],
    "r_stats": [sx(1275), sy(136), sx(208), sy(237)],
    "r_mode": [sx(1275), sy(25), sx(208), sy(104)],
    "r_pvtile": [sx(1113), sy(384), sx(369), sy(50)],
    "r_ev": [sx(1113), sy(436), sx(369), sy(50)],
    "r_cons": [sx(1113), sy(488), sx(369), sy(123)],
    "r_prod": [sx(1113), sy(613), sx(369), sy(123)],
    "r_events": [sx(1113), sy(738), sx(369), sy(141)],
    "pv": [sx(323), sy(575), sx(360), sy(33)],
    "pwr": [sx(720), sy(575), sx(355), sy(33)],
    "stat_cont": [sx(297), sy(619), sx(799), sy(131)],
    "stat": {"y": sy(630), "h": sy(107), "w": sx(180), "xs": [sx(x) for x in [309, 508, 707, 906]]},
    "inv_box": [sx(299), sy(762), sx(209), sy(136)],
    "inv_right": [sx(509), sy(762), sx(585), sy(136)],
    "donut_c": [sx(556), sy(786), sx(87), sy(106)],
    "invt": {"y": sy(781), "h": sy(107), "w": sx(122), "xs": [sx(x) for x in [687, 823, 959]]},
    "bot": {"y": sy(917), "h": sy(75), "w": sx(182), "xs": [sx(x) for x in [156, 357, 558, 759, 960, 1161]]},
    "icons": {"x": sx(1110), "y": sy(20)},
    "arc": {"lx": sx(413), "ly": sy(205), "px": sx(735), "py": sy(150), "rx": sx(1057), "ry": sy(205)},
}


def sl_block() -> str:
    tops = ", ".join(str(t) for t in SL["nav"]["tops"])
    stat_xs = ", ".join(str(x) for x in SL["stat"]["xs"])
    invt_xs = ", ".join(str(x) for x in SL["invt"]["xs"])
    bot_xs = ", ".join(str(x) for x in SL["bot"]["xs"])
    return f"""const SL = {{
  nav:  {{ x:{SL['nav']['x']}, w:{SL['nav']['w']}, h:{SL['nav']['h']}, tops:[{tops}] }},
  r_cyl:[{', '.join(map(str, SL['r_cyl']))}], r_stats:[{', '.join(map(str, SL['r_stats']))}], r_mode:[{', '.join(map(str, SL['r_mode']))}],
  r_pvtile:[{', '.join(map(str, SL['r_pvtile']))}], r_ev:[{', '.join(map(str, SL['r_ev']))}], r_cons:[{', '.join(map(str, SL['r_cons']))}], r_prod:[{', '.join(map(str, SL['r_prod']))}], r_events:[{', '.join(map(str, SL['r_events']))}],
  pv:[{', '.join(map(str, SL['pv']))}], pwr:[{', '.join(map(str, SL['pwr']))}],
  stat_cont:[{', '.join(map(str, SL['stat_cont']))}],
  stat:{{ y:{SL['stat']['y']},h:{SL['stat']['h']},w:{SL['stat']['w']},xs:[{stat_xs}] }},
  inv_box:[{', '.join(map(str, SL['inv_box']))}],
  inv_right:[{', '.join(map(str, SL['inv_right']))}],
  donut_c:[{', '.join(map(str, SL['donut_c']))}],
  invt:{{ y:{SL['invt']['y']},h:{SL['invt']['h']},w:{SL['invt']['w']},xs:[{invt_xs}] }},
  bot:{{ y:{SL['bot']['y']},h:{SL['bot']['h']},w:{SL['bot']['w']},xs:[{bot_xs}] }},
  icons:{{ x:{SL['icons']['x']}, y:{SL['icons']['y']} }},
  arc:{{ lx:{SL['arc']['lx']},ly:{SL['arc']['ly']}, px:{SL['arc']['px']},py:{SL['arc']['py']}, rx:{SL['arc']['rx']},ry:{SL['arc']['ry']} }},
}};"""


def main() -> None:
    text = SRC.read_text()

    text = re.sub(r"// v1\.0\.0 · build no\.\d+.*", "// v1.0.0 · build no.16x9-7 (1920×1080 fork)", text, count=1)
    text = text.replace("template 60883 (1500×1000)", "1920×1080 wall tablet (forked from 1500×1000)")
    text = text.replace("/local/community/casa-luna/sky/casa-luna-", "/local/community/casa-luna-16x9/sky/casa-luna-")
    text = text.replace("const BUILD = 51;", "const BUILD = 7;")
    text = text.replace("const VB_W = 1500, VB_H = 1000;", f"const VB_W = {VB_W}, VB_H = {VB_H};")
    text = text.replace("const SCALE_X = 1920/1500, SCALE_Y = 1080/1000;", "")  # idempotent

    text = re.sub(
        r"/\* ── canonical geometry \(measured from template, scaled 1536→1500\) ── \*/\nconst SL = \{[\s\S]*?\};",
        "/* ── canonical geometry (1500×1000 → 1920×1080: x×1.28, y×1.08) ── */\n" + sl_block(),
        text,
        count=1,
    )

    # Detail panel (nav slide-over)
    text = text.replace(
        ".detail { position:absolute; left:231px; top:130px;\n        width:869px; height:445px;",
        f".detail {{ position:absolute; left:{sx(231)}px; top:{sy(130)}px;\n        width:{sx(869)}px; height:{sy(445)}px;",
    )

    # Header band
    text = text.replace(
        f"width:${{VB_W}}px;height:140px;pointer-events:none",
        f"width:${{VB_W}}px;height:{sy(140)}px;pointer-events:none",
    )
    text = text.replace('left:44px;top:30px;font-size:44px', f"left:{sx(44)}px;top:{sy(30)}px;font-size:44px")
    text = text.replace('left:46px;top:84px;font-size:16px', f"left:{sx(46)}px;top:{sy(84)}px;font-size:16px")
    text = text.replace('left:46px;top:104px;font-size:15px', f"left:{sx(46)}px;top:{sy(104)}px;font-size:15px")
    text = text.replace(
        'left:40px;top:24px;width:150px;height:104px',
        f"left:{sx(40)}px;top:{sy(24)}px;width:{sx(150)}px;height:{sy(104)}px",
    )
    text = text.replace(
        'left:185px;top:44px;width:180px;height:80px',
        f"left:{sx(185)}px;top:{sy(44)}px;width:{sx(180)}px;height:{sy(80)}px",
    )
    text = text.replace(
        'left:190px;top:56px;width:50px;height:60px',
        f"left:{sx(190)}px;top:{sy(56)}px;width:{sx(50)}px;height:{sy(60)}px",
    )
    text = text.replace('left:252px;top:46px;font-size:32px', f"left:{sx(252)}px;top:{sy(46)}px;font-size:32px")
    text = text.replace('left:252px;top:82px;font-size:14px', f"left:{sx(252)}px;top:{sy(82)}px;font-size:14px")
    text = text.replace('left:252px;top:104px;font-size:14px', f"left:{sx(252)}px;top:{sy(104)}px;font-size:14px")

    # Sun/moon arc layer (card coords)
    text = text.replace(
        'style="position:absolute;left:252px;top:44px;width:1063px;height:260px;overflow:visible;background:none"',
        f'style="position:absolute;left:{sx(252)}px;top:{sy(44)}px;width:{sx(1063)}px;height:{sy(260)}px;overflow:visible;background:none"',
    )

    # Flow overlay — full canvas + paint above right-column tiles
    text = text.replace(
        '<svg id="flowOverlay" style="position:absolute;left:0;top:0;width:${VB_W}px;height:1000px;overflow:visible;pointer-events:none;z-index:2">',
        '<svg id="flowOverlay" viewBox="0 0 ${VB_W} ${VB_H}" style="position:absolute;left:0;top:0;width:${VB_W}px;height:${VB_H}px;overflow:visible;pointer-events:none;z-index:8">',
    )

    # Flow path anchor Y (battery + grid lines)
    text = text.replace(
        "const A_Y    = SL.r_stats[1] + 38 + 3 * 46 + 9 + 20;  // 341 (base)",
        f"const A_Y    = SL.r_stats[1] + {sy(38)} + 3 * {sy(46)} + {sy(9)} + {sy(20)};  // scaled base",
    )
    text = text.replace(
        "const BATT_Y = A_Y + 10;    // battery flow line pulled down 10px",
        f"const BATT_Y = A_Y + {sy(10)};    // battery flow line pulled down",
    )
    text = text.replace(
        "const POLE_Y = A_Y + 45;    // grid flow line (pulled down 45px)",
        f"const POLE_Y = A_Y + {sy(45)};    // grid flow line (pulled down)",
    )
    text = text.replace(
        "const POLE_P_X   = 300 + Math.round(5 * H_CYC) - 40; // A start, moved 40px left total",
        f"const POLE_P_X   = {sx(300)} + Math.round(5 * H_CYC) - {sx(40)}; // scaled grid flow start",
    )

    f32 = flow_anchors_32()
    f16 = flow_anchors_16(f32)

    # House junction X: scale 3:2 computed endpoints; derive C→D run from bend corners
    text = text.replace(
        "const BATT_D_LEN = Math.round(2 * H_CYC);            // C→D horizontal: 2 dashes (toward house = left)\n"
        "    const BATT_D_X   = BATT_B_X - CR - BATT_D_LEN;       // D end x",
        f"const BATT_D_X   = {f16['BATT_D_X']};                    // sx({f32['BATT_D_X']}) battery→house junction\n"
        f"    const BATT_D_LEN = (BATT_B_X - CR) - BATT_D_X;       // {f16['BATT_D_LEN']}px toward house",
    )
    text = text.replace(
        "const POLE_D_LEN = Math.round(2 * H_CYC);            // C→D horizontal: 2 dashes (right)\n"
        "    const POLE_D_X   = POLE_Q_X + CR + POLE_D_LEN;       // D end x (moved left with B)",
        f"const POLE_D_X   = {f16['POLE_D_X']};                    // sx({f32['POLE_D_X']}) grid→house junction\n"
        f"    const POLE_D_LEN = POLE_D_X - (POLE_Q_X + CR);       // {f16['POLE_D_LEN']}px toward house",
    )

    # Stage fills panel viewport (no aspect-ratio letterboxing)
    text = text.replace(
        ":host { display:block; }\n"
        "      .stage { position:relative; width:100%; aspect-ratio:${VB_W}/${VB_H};\n"
        "        border-radius:18px; overflow:hidden; background:#020c1e;",
        ":host { display:block; width:100%; height:100%; min-height:100%; }\n"
        "      .stage { position:relative; width:100%; height:100%; min-height:100%;\n"
        "        border-radius:0; overflow:hidden; background:#020c1e;",
    )

    # Responsive scaling — width-fit on ~16:9, letterbox-safe fallback otherwise
    text = text.replace(
        "      const s = stage.clientWidth / VB_W;\n      scaler.style.transform = `scale(${s})`;",
        "      const w = stage.clientWidth, h = stage.clientHeight;\n"
        "      if (!w || !h) return;\n"
        "      const ar = w / h, target = VB_W / VB_H;\n"
        "      const s = Math.abs(ar - target) < 0.03 ? w / VB_W : Math.min(w / VB_W, h / VB_H);\n"
        "      scaler.style.transform = `scale(${s})`;",
    )

    # Card type + default sky path
    text = text.replace(
        "background_path: '/local/community/casa-luna/sky',",
        "background_path: '/local/community/casa-luna-16x9/sky',",
    )

    # Battery cylinder — 16:9 container is height-limited; pad viewBox + inset + scale so cap/base clear border-radius
    text = text.replace(
        '<div class="box" style="left:${cx0}px;top:${cy0}px;width:${cw0}px;height:${ch0}px;overflow:hidden">\n'
        '      <svg viewBox="34 118 100 168" width="${cw0}" height="${ch0}" preserveAspectRatio="xMidYMid meet" style="display:block;position:absolute;inset:0">',
        '<div class="box cyl-widget" style="left:${cx0}px;top:${cy0}px;width:${cw0}px;height:${ch0}px;overflow:hidden">\n'
        '      <svg viewBox="32 114 104 178" width="${cw0}" height="${ch0}" preserveAspectRatio="xMidYMid meet" style="display:block;position:absolute;inset:5px 8px 14px 8px">',
    )
    text = text.replace(
        "      .box::before { content:\"\"; position:absolute; inset:3px; border:1px solid rgba(120,175,235,.15);\n"
        "        border-radius:10px; pointer-events:none; }",
        "      .box::before { content:\"\"; position:absolute; inset:3px; border:1px solid rgba(120,175,235,.15);\n"
        "        border-radius:10px; pointer-events:none; }\n"
        "      .cyl-widget { overflow:hidden; }\n"
        "      .cyl-widget > svg { overflow:visible; transform:scale(0.88); transform-origin:50% 45%; }",
    )

    # Custom element registration (collision-safe with 3:2 G-UNIT)
    text = text.replace("if (!customElements.get('casa-luna')) customElements.define('casa-luna', CasaLuna);", "")
    text = text.replace(
        "if (!customElements.get('casa-luna-editor')) customElements.define('casa-luna-editor', CasaLunaEditor);",
        "if (!customElements.get('casa-luna-16x9')) customElements.define('casa-luna-16x9', CasaLuna);\n"
        "if (!customElements.get('casa-luna-16x9-editor')) customElements.define('casa-luna-16x9-editor', CasaLunaEditor);",
    )
    text = text.replace(
        "  type: 'casa-luna',\n  name: 'Casa Luna',",
        "  type: 'casa-luna-16x9',\n  name: 'Casa Luna 16:9 (G-UNIT)',",
    )
    text = text.replace(
        "console.info(`%c CASA-LUNA %c v${VERSION} b${BUILD} `",
        "console.info(`%c CASA-LUNA-16X9 %c v${VERSION} b${BUILD} `",
    )

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(text)
    print(f"Wrote {DST} ({len(text)} bytes)")


if __name__ == "__main__":
    main()

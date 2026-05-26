#!/usr/bin/env python3
"""Build v4: daytime CGI master + small right-hill pylon + smooth dashed energy curves."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4" / "master-clear.png"
PYLON_REF = ROOT / "www" / "solar-dashboard" / "assets" / "pylon-reference.png"
OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4"
V5_OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v5"
SIZE = (1920, 1080)

# Right hill — ~1/3 smaller than prior 70×150 paste (target ~46×100)
PYLON_CX = 1250
PYLON_ATTACH_Y = 200
PYLON_BASE_Y = 290
PYLON_WIDTH_PX = 46
PYLON_MAX_HEIGHT_PX = 100

SITE = {
    "pylon": (PYLON_CX, PYLON_ATTACH_Y),
    "pylon_base": (PYLON_CX, PYLON_BASE_Y),
    "inverter": (1410, 498),
    "battery_wall": (1385, 468),
    "ev_charger": (1465, 538),
    "array_field": (1570, 790),
    "house_tie": (806, 454),
}

# Cubic Bézier control chains (start, cp1, cp2, end) — gentle arcs, no card stubs
FLOW_CURVES: dict[str, tuple[tuple[int, int], ...]] = {
    "grid_pylon_to_inverter": (
        SITE["pylon_base"],
        (1280, 340),
        (1180, 430),
        SITE["inverter"],
    ),
    "solar_to_inverter": (
        SITE["array_field"],
        (1520, 720),
        (1460, 580),
        SITE["inverter"],
    ),
    "house_to_inverter": (
        SITE["house_tie"],
        (980, 500),
        (1220, 492),
        SITE["inverter"],
    ),
    "pylon_to_house": (
        SITE["pylon_base"],
        (1080, 380),
        (900, 420),
        SITE["house_tie"],
    ),
    "inverter_to_charger": (
        SITE["inverter"],
        (1445, 520),
        (1458, 532),
        SITE["ev_charger"],
    ),
}

LINE_STYLES = {
    "grid_pylon_to_inverter": ("#ffffff", 3),
    "solar_to_inverter": ("#f5c842", 3),
    "house_to_inverter": ("#f5c842", 3),
    "pylon_to_house": ("#ffffff", 3),
    "inverter_to_charger": ("#69f0ae", 3),
}

DASH_LEN = 16
DASH_GAP = 10


def crop_16_9(img: Image.Image) -> Image.Image:
    w, h = img.size
    target = 16 / 9
    if w / h > target:
        nw = int(h * target)
        left = (w - nw) // 2
        box = (left, 0, left + nw, h)
    else:
        nh = int(w / target)
        top = (h - nh) // 2
        box = (0, top, w, top + nh)
    return img.crop(box).resize(SIZE, Image.Resampling.LANCZOS)


def prepare_daytime_master(img: Image.Image) -> Image.Image:
    """Keep master bright; mild contrast only (no dusk crush)."""
    img = ImageEnhance.Contrast(img).enhance(1.05)
    img = ImageEnhance.Brightness(img).enhance(1.02)
    img = ImageEnhance.Color(img).enhance(1.04)
    return img


def _key_sprite_background(img: Image.Image) -> Image.Image:
    """Make sky/water/grass transparent; keep lattice steel."""
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    px_in = img.load()
    px_out = out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px_in[x, y]
            lum = (r + g + b) / 3
            if lum > 175 and abs(r - g) < 35 and b >= g - 10:
                continue
            if b > max(r, g) + 12 and b > 95:
                continue
            if g > 165 and r > 65 and b < 145:
                continue
            nr = int(r * 0.82)
            ng = int(g * 0.84)
            nb = int(b * 0.88)
            px_out[x, y] = (nr, ng, nb, a)
    return out


def prepare_pylon_sprite(ref_path: Path) -> Image.Image:
    """Extract lattice tower; scale to ~46×100 for right hill."""
    ref = Image.open(ref_path).convert("RGBA")
    tower = ref.crop((40, 12, 200, 355))
    tower = _key_sprite_background(tower)
    tw, th = tower.size
    scale = min(PYLON_WIDTH_PX / tw, PYLON_MAX_HEIGHT_PX / th)
    nw, nh = max(1, int(tw * scale)), max(1, int(th * scale))
    sprite = tower.resize((nw, nh), Image.Resampling.LANCZOS)
    rgb = ImageEnhance.Contrast(sprite.convert("RGB")).enhance(1.15)
    rgb = ImageEnhance.Brightness(rgb).enhance(0.92)
    sprite = Image.merge("RGBA", (*rgb.split(), sprite.split()[3]))
    return sprite


def _darken_tower_footprint(img: Image.Image) -> None:
    """Soft ellipse over master full-size tower so smaller sprite reads cleanly."""
    patch = Image.new("RGBA", (120, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch)
    draw.ellipse((8, 20, 112, 198), fill=(0, 0, 0, 110))
    patch = patch.filter(ImageFilter.GaussianBlur(3))
    x = PYLON_CX - patch.width // 2
    y = PYLON_ATTACH_Y - 24
    img.alpha_composite(patch, (x, y))


def composite_pylon_on_right_hill(base: Image.Image, sprite: Image.Image) -> Image.Image:
    """Small pylon on right hill at (1250, 200) attach / base_y=290."""
    img = base.convert("RGBA")
    _darken_tower_footprint(img)
    cx, base_y = PYLON_CX, PYLON_BASE_Y
    x = cx - sprite.width // 2
    y = base_y - sprite.height + 12

    shadow = Image.new("RGBA", (sprite.width + 32, 22), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse((4, 5, shadow.width - 4, shadow.height - 2), fill=(0, 0, 0, 85))
    img.alpha_composite(shadow, (x - 16, base_y - 5))
    img.alpha_composite(sprite, (x, y))
    return img.convert("RGB")


def _bezier_point(t: float, controls: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    pts = [tuple(float(c) for c in p) for p in controls]
    while len(pts) > 1:
        nxt: list[tuple[float, float]] = []
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            nxt.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        pts = nxt
    return pts[0]


def sample_bezier(controls: tuple[tuple[int, int], ...], steps: int = 140) -> list[tuple[float, float]]:
    if len(controls) < 2:
        return [tuple(float(c) for c in controls[0])] if controls else []
    return [_bezier_point(i / steps, controls) for i in range(steps + 1)]


def _polyline_length(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def _point_at_distance(points: list[tuple[float, float]], dist: float) -> tuple[float, float]:
    if dist <= 0:
        return points[0]
    walked = 0.0
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        seg = math.hypot(x1 - x0, y1 - y0)
        if walked + seg >= dist:
            t = (dist - walked) / seg if seg else 0.0
            return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
        walked += seg
    return points[-1]


def smooth_dashed_bezier(
    layer: Image.Image,
    control_points: tuple[tuple[int, int], ...],
    color: str,
    width: int,
    *,
    dash_len: int = DASH_LEN,
    dash_gap: int = DASH_GAP,
) -> None:
    """Anti-aliased dashed cubic/quadratic curve with soft glow (3× supersample)."""
    samples = sample_bezier(control_points)
    if len(samples) < 2:
        return

    scale = 3
    w, h = layer.size
    hi = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(hi)

    hi_pts = [(x * scale, y * scale) for x, y in samples]
    glow_w = max(1, width * scale + 6)
    core_w = max(1, width * scale)

    glow_rgb: tuple[int, int, int, int] = (0, 0, 0, 70)
    if color.startswith("#") and len(color) >= 7:
        cr = int(color[1:3], 16)
        cg = int(color[3:5], 16)
        cb = int(color[5:7], 16)
        glow_rgb = (cr, cg, cb, 55)

    total = _polyline_length(hi_pts)
    period = dash_len * scale + dash_gap * scale
    dist = 0.0
    while dist < total:
        d0 = dist
        d1 = min(total, dist + dash_len * scale)
        p0 = _point_at_distance(hi_pts, d0)
        p1 = _point_at_distance(hi_pts, d1)
        draw.line([p0, p1], fill=glow_rgb, width=glow_w)
        draw.line([p0, p1], fill=color, width=core_w)
        dist += period

    smooth = hi.resize((w, h), Image.Resampling.LANCZOS)
    layer.alpha_composite(smooth)


def arrow_head(
    layer: Image.Image,
    tip: tuple[int, int],
    origin: tuple[int, int],
    colour: str,
    size: int = 14,
) -> None:
    tx, ty = tip
    ox, oy = origin
    ang = math.atan2(ty - oy, tx - ox)
    pts = [
        (tx - size * math.cos(ang - 2.4), ty - size * math.sin(ang - 2.4)),
        (tx - size * math.cos(ang + 2.4), ty - size * math.sin(ang + 2.4)),
    ]
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.polygon([(tx, ty), *pts], fill="#000000cc")
    draw.polygon([(tx, ty), *pts], fill=colour)


def draw_flow_lines(base: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    for route_id, controls in FLOW_CURVES.items():
        colour, width = LINE_STYLES[route_id]
        smooth_dashed_bezier(layer, controls, colour, width)

    arrow_head(layer, SITE["inverter"], FLOW_CURVES["solar_to_inverter"][-2], "#f5c842")
    arrow_head(layer, SITE["inverter"], FLOW_CURVES["grid_pylon_to_inverter"][-2], "#ffffff")
    arrow_head(layer, SITE["inverter"], FLOW_CURVES["house_to_inverter"][-2], "#f5c842")
    arrow_head(layer, SITE["house_tie"], FLOW_CURVES["pylon_to_house"][-2], "#ffffff")
    arrow_head(layer, SITE["ev_charger"], SITE["inverter"], "#69f0ae")

    out = base.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def draw_overlays(base: Image.Image, pylon_sprite: Image.Image | None, paste_pylon: bool) -> Image.Image:
    img = base
    if paste_pylon and pylon_sprite:
        img = composite_pylon_on_right_hill(base, pylon_sprite)
    return draw_flow_lines(img)


def variant(img: Image.Image, mode: str) -> Image.Image:
    if mode == "clear":
        return img
    if mode == "cloudy":
        return ImageEnhance.Brightness(img).enhance(0.92)
    if mode == "covered":
        g = img.convert("L").filter(ImageFilter.GaussianBlur(1))
        out = Image.merge("RGB", (g, g, g)).point(lambda p: min(255, int(p * 0.88)))
        return ImageEnhance.Brightness(out).enhance(0.94)
    if mode == "very_covered":
        g = img.convert("L").filter(ImageFilter.GaussianBlur(2))
        dark = Image.merge("RGB", (g, g, g)).point(lambda p: min(255, int(p * 0.75)))
        return ImageEnhance.Brightness(dark).enhance(0.88)
    if mode == "night":
        return ImageEnhance.Brightness(img).enhance(0.58)
    raise ValueError(mode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=MASTER)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--pylon-ref", type=Path, default=PYLON_REF)
    parser.add_argument(
        "--no-paste-pylon",
        action="store_true",
        help="Skip small sprite (master tower only)",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    paste_pylon = not args.no_paste_pylon

    pylon_sprite = prepare_pylon_sprite(args.pylon_ref) if args.pylon_ref.is_file() else None
    if paste_pylon and pylon_sprite:
        print(
            f"pylon sprite {pylon_sprite.size[0]}×{pylon_sprite.size[1]} @ "
            f"({PYLON_CX}, {PYLON_ATTACH_Y}); smooth bezier flow lines"
        )
    elif pylon_sprite:
        print(f"pylon ref available ({pylon_sprite.size}); flow lines only")
    else:
        print(f"warning: no pylon reference at {args.pylon_ref}")

    master = prepare_daytime_master(crop_16_9(Image.open(args.master).convert("RGB")))
    overlaid = draw_overlays(master, pylon_sprite, paste_pylon=paste_pylon)
    for name in ("clear", "cloudy", "covered", "very_covered", "night"):
        out = variant(overlaid, name)
        out.save(args.out / f"{name}.jpg", quality=92)
        print(f"wrote {args.out / f'{name}.jpg'}")

    v5 = V5_OUT if args.out == OUT else args.out.parent / "v5"
    if args.out == OUT:
        v5.mkdir(parents=True, exist_ok=True)
        for name in ("clear", "cloudy", "covered", "very_covered", "night"):
            src = args.out / f"{name}.jpg"
            dst = v5 / f"{name}.jpg"
            dst.write_bytes(src.read_bytes())
            print(f"copied {dst}")


if __name__ == "__main__":
    main()

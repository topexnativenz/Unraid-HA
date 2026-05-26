#!/usr/bin/env python3
"""Build v4/v5: daytime CGI master + smooth dashed energy curves (master pylon only)."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4" / "master-clear.png"
OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4"
V5_OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v5"
SIZE = (1920, 1080)

# Master lattice tower on right hill (1920×1080) — cross-arms / wire junction + foot on slope
PYLON_CX = 1320
PYLON_ATTACH_Y = 168
PYLON_BASE_Y = 298

SITE = {
    "pylon": (PYLON_CX, PYLON_ATTACH_Y),
    "pylon_base": (PYLON_CX - 8, PYLON_BASE_Y),
    "inverter": (1410, 498),
    "battery_wall": (1385, 468),
    "ev_charger": (1465, 538),
    "array_field": (1570, 790),
    "house_tie": (806, 454),
    "grid_left": (140, 360),
    "grid_right": (1880, 95),
}

# Cubic Bézier (start, cp1, cp2, end) — converge on right pylon, hub at garage inverter
FLOW_CURVES: dict[str, tuple[tuple[int, int], ...]] = {
    "grid_left_to_pylon": (
        SITE["grid_left"],
        (360, 260),
        (1080, 188),
        SITE["pylon"],
    ),
    "grid_right_to_pylon": (
        SITE["grid_right"],
        (1720, 108),
        (1420, 152),
        SITE["pylon"],
    ),
    "grid_pylon_to_inverter": (
        SITE["pylon_base"],
        (1360, 360),
        (1395, 440),
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
    "inverter_to_charger": (
        SITE["inverter"],
        (1445, 520),
        (1458, 532),
        SITE["ev_charger"],
    ),
}

LINE_STYLES = {
    "grid_left_to_pylon": ("#ffffff", 3),
    "grid_right_to_pylon": ("#ffffff", 3),
    "grid_pylon_to_inverter": ("#ffffff", 3),
    "solar_to_inverter": ("#f5c842", 3),
    "house_to_inverter": ("#f5c842", 3),
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

    arrow_head(layer, SITE["pylon"], FLOW_CURVES["grid_left_to_pylon"][-2], "#ffffff")
    arrow_head(layer, SITE["pylon"], FLOW_CURVES["grid_right_to_pylon"][-2], "#ffffff")
    arrow_head(layer, SITE["inverter"], FLOW_CURVES["grid_pylon_to_inverter"][-2], "#ffffff")
    arrow_head(layer, SITE["inverter"], FLOW_CURVES["solar_to_inverter"][-2], "#f5c842")
    arrow_head(layer, SITE["inverter"], FLOW_CURVES["house_to_inverter"][-2], "#f5c842")
    arrow_head(layer, SITE["ev_charger"], SITE["inverter"], "#69f0ae")

    out = base.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def draw_overlays(base: Image.Image) -> Image.Image:
    return draw_flow_lines(base)


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
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print(
        f"master pylon anchor ({PYLON_CX}, {PYLON_ATTACH_Y}) "
        f"base ({SITE['pylon_base'][0]}, {SITE['pylon_base'][1]}); "
        "no sprite paste / ellipse"
    )

    master = prepare_daytime_master(crop_16_9(Image.open(args.master).convert("RGB")))
    overlaid = draw_overlays(master)
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

#!/usr/bin/env python3
"""Build v4: dark-contrast CGI + drawn lattice pylon + high-visibility flow lines."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4" / "master-clear.png"
OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4"
SIZE = (1920, 1080)

SITE = {
    "pylon": (1085, 200),
    "pylon_base": (1085, 295),
    "inverter": (1410, 498),
    "battery_wall": (1385, 468),
    "ev_charger": (1465, 538),
    "array_field": (1570, 790),
    "house_tie": (800, 508),
}

CARD_STUBS = {
    "grid": ((1040, 125), "pylon"),
    "grid_details": ((1040, 195), "pylon"),
    "home": ((730, 432), "house_tie"),
    "battery": ((1267, 346), "battery_wall"),
    "garage": ((1421, 389), "ev_charger"),
    "solar_array": ((200, 1010), "array_field"),
}

ROUTES = {
    "solar_to_inverter": [
        (1520, 860),
        (1485, 800),
        (1455, 720),
        (1435, 640),
        (1420, 560),
        SITE["inverter"],
    ],
    "array_card_to_field": [
        (200, 1010),
        (380, 980),
        (620, 920),
        (920, 860),
        (1180, 820),
        (1380, 760),
        SITE["array_field"],
    ],
    "grid_pylon_to_inverter": [
        SITE["pylon_base"],
        (1110, 340),
        (1200, 400),
        (1300, 450),
        (1370, 480),
        SITE["inverter"],
    ],
    "house_to_inverter": [
        SITE["house_tie"],
        (920, 518),
        (1080, 512),
        (1220, 505),
        (1340, 500),
        SITE["inverter"],
    ],
    "inverter_to_battery": [SITE["inverter"], (1400, 485), SITE["battery_wall"]],
    "inverter_to_charger": [SITE["inverter"], (1440, 515), SITE["ev_charger"]],
    "charger_to_garage": [SITE["ev_charger"], (1475, 555), (1485, 575)],
}

HV_LINES = {
    "from_left": [(0, 120), (200, 115), (450, 125), (700, 150), (900, 175), SITE["pylon"]],
    "from_right": [(1919, 115), (1720, 118), (1480, 135), (1280, 160), (1160, 185), SITE["pylon"]],
}


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


def darken_master(img: Image.Image) -> Image.Image:
    """Dark high-contrast base for overlay legibility."""
    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Brightness(img).enhance(0.72)
    img = ImageEnhance.Color(img).enhance(0.85)
    return img


def draw_lattice_pylon(draw: ImageDraw.ImageDraw, cx: int, base_y: int) -> None:
    """Draw visible lattice transmission tower (reference-style) on the hill."""
    top = base_y - 175
    steel = (195, 205, 220, 255)
    steel_dark = (120, 130, 150, 255)
    insulator = (240, 240, 245, 255)

    # Main legs (A-frame)
    for dx in (-22, 0, 22):
        draw.line([(cx + dx, base_y), (cx, top + 25)], fill=steel_dark, width=4)
    draw.line([(cx - 22, base_y), (cx + 22, base_y)], fill=steel, width=5)

    # Cross-bracing
    for y in range(base_y - 30, top + 40, -35):
        w = int(18 + (base_y - y) * 0.08)
        draw.line([(cx - w, y), (cx + w, y)], fill=steel, width=3)
        draw.line([(cx - w, y), (cx, y - 28)], fill=steel_dark, width=2)
        draw.line([(cx + w, y), (cx, y - 28)], fill=steel_dark, width=2)

    # Three cross-arms with insulators
    for arm_y, arm_w in ((top + 55, 55), (top + 95, 70), (top + 130, 48)):
        draw.line([(cx - arm_w, arm_y), (cx + arm_w, arm_y)], fill=steel, width=5)
        for ax in (cx - arm_w, cx, cx + arm_w):
            for iy in range(arm_y, arm_y + 22, 6):
                draw.line([(ax, arm_y), (ax, iy)], fill=insulator, width=2)

    # Peak
    draw.line([(cx, top + 25), (cx, top)], fill=steel, width=4)


def glow_polyline(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    colour: str,
    width: int,
    dashed: bool = False,
) -> None:
    """Draw with dark outline for contrast on dark backgrounds."""
    outline = "#000000"
    if dashed:
        for i in range(len(points) - 1):
            dashed_segment(draw, points[i], points[i + 1], outline, width + 4)
        for i in range(len(points) - 1):
            dashed_segment(draw, points[i], points[i + 1], colour, width)
    else:
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=outline, width=width + 4)
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=colour, width=width)


def dashed_segment(draw: ImageDraw.ImageDraw, a: tuple[int, int], b: tuple[int, int], colour: str, width: int) -> None:
    x0, y0 = a
    x1, y1 = b
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 1:
        return
    dash, gap = 14, 7
    n = int(length / (dash + gap)) + 1
    for i in range(n):
        t0 = i * (dash + gap) / length
        t1 = min(1.0, (i * (dash + gap) + dash) / length)
        draw.line(
            (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0, x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1),
            fill=colour,
            width=width,
        )


def dashed_polyline(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], colour: str, width: int = 4) -> None:
    for i in range(len(points) - 1):
        dashed_segment(draw, points[i], points[i + 1], colour, width)


def arrow_head(draw: ImageDraw.ImageDraw, tip: tuple[int, int], origin: tuple[int, int], colour: str, size: int = 16) -> None:
    tx, ty = tip
    ox, oy = origin
    ang = math.atan2(ty - oy, tx - ox)
    pts = [
        (tx - size * math.cos(ang - 2.4), ty - size * math.sin(ang - 2.4)),
        (tx - size * math.cos(ang + 2.4), ty - size * math.sin(ang + 2.4)),
    ]
    draw.polygon([(tx, ty), *pts], fill="#000000")
    draw.polygon([(tx, ty), *pts], fill=colour)


def stub_to_target(draw: ImageDraw.ImageDraw, card: tuple[int, int], target: tuple[int, int], colour: str, width: int = 5) -> None:
    cx, cy = card
    tx, ty = target
    mid = (cx + (tx - cx) // 2, cy)
    glow_polyline(draw, [card, mid, target], colour, width, dashed=True)


def draw_overlays(base: Image.Image) -> Image.Image:
    img = base.copy()
    draw = ImageDraw.Draw(img, "RGBA")

    cx, base_y = SITE["pylon"][0], SITE["pylon_base"][1]
    draw_lattice_pylon(draw, cx, base_y)

    amber = "#ffeb3b"
    white = "#ffffff"
    green = "#69f0ae"
    hv_line = "#d0d8e8"

    # HV transmission (solid, visible from distance)
    glow_polyline(draw, HV_LINES["from_left"], hv_line, 4, dashed=False)
    glow_polyline(draw, HV_LINES["from_right"], hv_line, 4, dashed=False)

    # Site energy flow (dashed, thick)
    glow_polyline(draw, ROUTES["grid_pylon_to_inverter"], white, 6, dashed=True)
    glow_polyline(draw, ROUTES["solar_to_inverter"], amber, 7, dashed=True)
    glow_polyline(draw, ROUTES["array_card_to_field"], amber, 6, dashed=True)
    glow_polyline(draw, ROUTES["house_to_inverter"], amber, 7, dashed=True)
    glow_polyline(draw, ROUTES["inverter_to_battery"], amber, 6, dashed=True)
    glow_polyline(draw, ROUTES["inverter_to_charger"], green, 6, dashed=True)
    glow_polyline(draw, ROUTES["charger_to_garage"], green, 5, dashed=True)

    arrow_head(draw, SITE["inverter"], ROUTES["solar_to_inverter"][-2], amber)
    arrow_head(draw, SITE["inverter"], ROUTES["grid_pylon_to_inverter"][-2], white)
    arrow_head(draw, SITE["inverter"], ROUTES["house_to_inverter"][-2], amber)
    arrow_head(draw, SITE["battery_wall"], SITE["inverter"], amber)
    arrow_head(draw, SITE["ev_charger"], SITE["inverter"], green)
    arrow_head(draw, ROUTES["charger_to_garage"][-1], ROUTES["charger_to_garage"][-2], green)
    arrow_head(draw, SITE["array_field"], ROUTES["array_card_to_field"][-2], amber)

    for _key, (card_pos, join) in CARD_STUBS.items():
        if join == "pylon":
            stub_to_target(draw, card_pos, SITE["pylon"], white)
        elif join == "house_tie":
            stub_to_target(draw, card_pos, SITE["house_tie"], amber)
        elif join == "battery_wall":
            stub_to_target(draw, card_pos, SITE["battery_wall"], amber)
        elif join == "ev_charger":
            stub_to_target(draw, card_pos, SITE["ev_charger"], green)
        elif join == "array_field":
            stub_to_target(draw, card_pos, ROUTES["array_card_to_field"][3], amber)

    return img


def variant(img: Image.Image, mode: str) -> Image.Image:
    if mode == "clear":
        return img
    if mode == "cloudy":
        return ImageEnhance.Brightness(img).enhance(0.88)
    if mode == "covered":
        g = img.convert("L").filter(ImageFilter.GaussianBlur(1))
        out = Image.merge("RGB", (g, g, g)).point(lambda p: min(255, int(p * 0.82)))
        return ImageEnhance.Brightness(out).enhance(0.9)
    if mode == "very_covered":
        g = img.convert("L").filter(ImageFilter.GaussianBlur(2))
        dark = Image.merge("RGB", (g, g, g)).point(lambda p: min(255, int(p * 0.68)))
        return ImageEnhance.Brightness(dark).enhance(0.82)
    if mode == "night":
        return ImageEnhance.Brightness(img).enhance(0.65)
    raise ValueError(mode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=MASTER)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    master = darken_master(crop_16_9(Image.open(args.master).convert("RGB")))
    overlaid = draw_overlays(master)
    for name in ("clear", "cloudy", "covered", "very_covered", "night"):
        out = variant(overlaid, name)
        out.save(args.out / f"{name}.jpg", quality=92)
        print(f"wrote {args.out / f'{name}.jpg'}")


if __name__ == "__main__":
    main()

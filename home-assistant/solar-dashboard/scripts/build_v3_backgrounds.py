#!/usr/bin/env python3
"""Build v3 photoreal backgrounds from drone aerial (332 Three Mile Bush Road-3.jpg)."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "www" / "solar-dashboard" / "source-photos" / "332 Three Mile Bush Road-3.jpg"
OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v3"
SIZE = (1920, 1080)

# Pixel anchors on 1920×1080 master (aerial: house centre, garage right, array far right)
ANCHORS = {
    "array": (1680, 520),
    "garage": (1280, 480),
    "house": (820, 520),
    "grid": (420, 620),
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


def dashed_line(draw: ImageDraw.ImageDraw, a: tuple[int, int], b: tuple[int, int], colour: str, width: int = 4) -> None:
    import math

    x0, y0 = a
    x1, y1 = b
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 1:
        return
    dash, gap = 18, 12
    n = int(length / (dash + gap)) + 1
    for i in range(n):
        t0 = i * (dash + gap) / length
        t1 = min(1.0, (i * (dash + gap) + dash) / length)
        draw.line(
            (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0, x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1),
            fill=colour,
            width=width,
        )


def arrow_head(draw: ImageDraw.ImageDraw, tip: tuple[int, int], origin: tuple[int, int], colour: str) -> None:
    import math

    tx, ty = tip
    ox, oy = origin
    ang = math.atan2(ty - oy, tx - ox)
    size = 14
    for da in (2.6, -2.6):
        ax = tx - size * math.cos(ang - da)
        ay = ty - size * math.sin(ang - da)
        draw.polygon([(tx, ty), (ax, ay), (ox, oy)], fill=colour)


def draw_overlays(base: Image.Image) -> Image.Image:
    img = base.copy()
    draw = ImageDraw.Draw(img, "RGBA")
    amber = (245, 200, 66, 220)
    white = (255, 255, 255, 200)
    array, garage, house, grid = ANCHORS["array"], ANCHORS["garage"], ANCHORS["house"], ANCHORS["grid"]

    draw.rectangle((1580, 380, 1860, 660), outline=(245, 200, 66, 90), width=2)
    dashed_line(draw, array, garage, "#f5c842", 4)
    dashed_line(draw, garage, house, "#f5c842", 4)
    dashed_line(draw, grid, garage, "#ffffff", 3)
    arrow_head(draw, garage, array, amber)
    arrow_head(draw, house, garage, amber)
    arrow_head(draw, garage, grid, white)
    return img


def variant(img: Image.Image, mode: str) -> Image.Image:
    if mode == "clear":
        return img
    if mode == "cloudy":
        return ImageEnhance.Brightness(img).enhance(0.92)
    if mode == "covered":
        g = img.convert("L").filter(ImageFilter.GaussianBlur(1))
        return Image.merge("RGB", (g, g, g)).point(lambda p: min(255, int(p * 0.88)))
    if mode == "very_covered":
        g = img.convert("L").filter(ImageFilter.GaussianBlur(2))
        dark = Image.merge("RGB", (g, g, g)).point(lambda p: min(255, int(p * 0.72)))
        return ImageEnhance.Color(dark).enhance(0.35)
    if mode == "night":
        n = ImageEnhance.Brightness(img).enhance(0.28)
        return ImageEnhance.Color(n).enhance(0.45)
    raise ValueError(mode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SRC)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    master = crop_16_9(Image.open(args.source).convert("RGB"))
    overlaid = draw_overlays(master)
    for name in ("clear", "cloudy", "covered", "very_covered", "night"):
        variant(overlaid, name).save(args.out / f"{name}.jpg", quality=92)
        print(f"wrote {args.out / f'{name}.jpg'}")


if __name__ == "__main__":
    main()

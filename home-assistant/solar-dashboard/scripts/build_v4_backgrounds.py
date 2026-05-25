#!/usr/bin/env python3
"""Build v4: dark-contrast CGI + composited lattice pylon + high-visibility flow lines."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4" / "master-clear.png"
PYLON_REF = ROOT / "www" / "solar-dashboard" / "assets" / "pylon-reference.png"
OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4"
SIZE = (1920, 1080)

# Hill crest (user red arrow) — lattice tower on distant hill
PYLON_CX = 960
PYLON_BASE_Y = 308
PYLON_WIDTH_PX = 168
PYLON_MAX_HEIGHT_PX = 300

SITE = {
    "pylon": (PYLON_CX, 198),
    "pylon_base": (PYLON_CX, PYLON_BASE_Y),
    "inverter": (1410, 498),
    "battery_wall": (1385, 468),
    "ev_charger": (1465, 538),
    "array_field": (1570, 790),
    "house_tie": (806, 454),
}

# Pixel stubs aligned to Serpo-style card positions in solar_dashboard.yaml
CARD_STUBS = {
    "grid": ((422, 130), "pylon"),
    "grid_details": ((422, 216), "pylon"),
    "home": (SITE["house_tie"], "house_tie"),
    "battery": ((1766, 194), "battery_wall"),
    "garage": ((1402, 562), "ev_charger"),
    "solar_array": ((96, 1026), "array_field"),
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
        (96, 1026),
        (288, 1010),
        (480, 990),
        (672, 960),
        (864, 920),
        (1180, 860),
        (1380, 800),
        SITE["array_field"],
    ],
    "grid_pylon_to_inverter": [
        SITE["pylon_base"],
        (1000, 340),
        (1060, 375),
        (1140, 410),
        (1225, 440),
        (1315, 470),
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
    "from_left": [
        (0, 72),
        (200, 76),
        (420, 88),
        (640, 108),
        (800, 138),
        (880, 168),
        (920, 188),
        SITE["pylon"],
    ],
    "from_right": [
        (1919, 72),
        (1720, 76),
        (1480, 86),
        (1240, 108),
        (1080, 148),
        (1000, 178),
        SITE["pylon"],
    ],
}

HV_COLOUR = "#2a2a30"
HV_HIGHLIGHT = "#e0e8f0"


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
            # Soften fringe toward dusk steel tones
            nr = int(r * 0.82)
            ng = int(g * 0.84)
            nb = int(b * 0.88)
            px_out[x, y] = (nr, ng, nb, a)
    return out


def prepare_pylon_sprite(ref_path: Path) -> Image.Image:
    """Extract lattice tower from reference PNG; scale for hill composite."""
    ref = Image.open(ref_path).convert("RGBA")
    # Crop tower only (exclude right-hand icon and most foreground island)
    tower = ref.crop((40, 12, 200, 355))
    tower = _key_sprite_background(tower)
    tw, th = tower.size
    scale = min(PYLON_WIDTH_PX / tw, PYLON_MAX_HEIGHT_PX / th)
    nw, nh = max(1, int(tw * scale)), max(1, int(th * scale))
    sprite = tower.resize((nw, nh), Image.Resampling.LANCZOS)
    rgb = ImageEnhance.Contrast(sprite.convert("RGB")).enhance(1.2)
    rgb = ImageEnhance.Brightness(rgb).enhance(0.78)
    sprite = Image.merge("RGBA", (*rgb.split(), sprite.split()[3]))
    return sprite


def composite_pylon_on_hill(base: Image.Image, sprite: Image.Image) -> Image.Image:
    """Paste visible CGI pylon on hill crest with soft ground shadow."""
    img = base.convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    cx, base_y = PYLON_CX, PYLON_BASE_Y
    x = cx - sprite.width // 2
    y = base_y - sprite.height + 12

    shadow = Image.new("RGBA", (sprite.width + 40, 28), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse((4, 6, shadow.width - 4, shadow.height - 2), fill=(0, 0, 0, 90))
    img.alpha_composite(shadow, (x - 20, base_y - 6))
    img.alpha_composite(sprite, (x, y))
    return img.convert("RGB")


def draw_hv_line(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]]) -> None:
    """Thick transmission lines: dark core + light highlight."""
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=HV_COLOUR, width=4)
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=HV_HIGHLIGHT, width=2)


def draw_lattice_pylon(draw: ImageDraw.ImageDraw, cx: int, base_y: int) -> None:
    """Subtle vector reinforcement on cross-arms (wires attach here)."""
    s = 1.35
    top = base_y - int(165 * s)
    steel = (210, 220, 235, 255)
    steel_dark = (155, 165, 180, 255)
    leg = int(20 * s)
    peak_off = int(22 * s)

    for dx in (-leg, 0, leg):
        draw.line([(cx + dx, base_y), (cx, top + peak_off)], fill=steel_dark, width=int(3 * s))
    draw.line([(cx - leg, base_y), (cx + leg, base_y)], fill=steel, width=int(4 * s))

    for arm_y, arm_w in (
        (top + int(50 * s), int(50 * s)),
        (top + int(88 * s), int(64 * s)),
        (top + int(120 * s), int(44 * s)),
    ):
        draw.line([(cx - arm_w, arm_y), (cx + arm_w, arm_y)], fill=steel, width=int(4 * s))


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


def draw_overlays(base: Image.Image, pylon_sprite: Image.Image | None) -> Image.Image:
    img = composite_pylon_on_hill(base, pylon_sprite) if pylon_sprite else base
    draw = ImageDraw.Draw(img, "RGBA")

    draw_lattice_pylon(draw, PYLON_CX, PYLON_BASE_Y)
    draw_hv_line(draw, HV_LINES["from_left"])
    draw_hv_line(draw, HV_LINES["from_right"])

    amber = "#ffeb3b"
    white = "#ffffff"
    green = "#69f0ae"

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
            stub_to_target(draw, card_pos, ROUTES["array_card_to_field"][5], amber)

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
    parser.add_argument("--pylon-ref", type=Path, default=PYLON_REF)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    pylon_sprite = prepare_pylon_sprite(args.pylon_ref) if args.pylon_ref.is_file() else None
    if pylon_sprite:
        print(f"pylon sprite {pylon_sprite.size} → hill ({PYLON_CX}, {PYLON_BASE_Y})")
    else:
        print(f"warning: no pylon reference at {args.pylon_ref}; vector tower only")

    master = darken_master(crop_16_9(Image.open(args.master).convert("RGB")))
    overlaid = draw_overlays(master, pylon_sprite)
    for name in ("clear", "cloudy", "covered", "very_covered", "night"):
        out = variant(overlaid, name)
        out.save(args.out / f"{name}.jpg", quality=92)
        print(f"wrote {args.out / f'{name}.jpg'}")


if __name__ == "__main__":
    main()

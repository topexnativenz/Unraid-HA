#!/usr/bin/env python3
"""Build v4: dark-contrast CGI master + optional half-scale pylon on right hill (no flow lines)."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4" / "master-clear.png"
PYLON_REF = ROOT / "www" / "solar-dashboard" / "assets" / "pylon-reference.png"
OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4"
SIZE = (1920, 1080)

# Right hill — half-scale lattice (~50% of 139×300 reference crop)
PYLON_CX = 1250
PYLON_ATTACH_Y = 200
PYLON_BASE_Y = 290
PYLON_WIDTH_PX = 70
PYLON_MAX_HEIGHT_PX = 150


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
            nr = int(r * 0.82)
            ng = int(g * 0.84)
            nb = int(b * 0.88)
            px_out[x, y] = (nr, ng, nb, a)
    return out


def prepare_pylon_sprite(ref_path: Path) -> Image.Image:
    """Extract lattice tower from reference PNG; scale to ~70×150 for right hill."""
    ref = Image.open(ref_path).convert("RGBA")
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


def _darken_tower_footprint(img: Image.Image) -> None:
    """Soft ellipse over master full-size tower so half-scale sprite reads cleanly."""
    patch = Image.new("RGBA", (120, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch)
    draw.ellipse((8, 20, 112, 198), fill=(0, 0, 0, 110))
    patch = patch.filter(ImageFilter.GaussianBlur(3))
    x = PYLON_CX - patch.width // 2
    y = PYLON_ATTACH_Y - 24
    img.alpha_composite(patch, (x, y))


def composite_pylon_on_right_hill(base: Image.Image, sprite: Image.Image) -> Image.Image:
    """Half-scale pylon on right hill, centered on attach point."""
    img = base.convert("RGBA")
    _darken_tower_footprint(img)
    cx, base_y = PYLON_CX, PYLON_BASE_Y
    x = cx - sprite.width // 2
    y = base_y - sprite.height + 12

    shadow = Image.new("RGBA", (sprite.width + 40, 28), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse((4, 6, shadow.width - 4, shadow.height - 2), fill=(0, 0, 0, 90))
    img.alpha_composite(shadow, (x - 20, base_y - 6))
    img.alpha_composite(sprite, (x, y))
    return img.convert("RGB")


def draw_overlays(base: Image.Image, pylon_sprite: Image.Image | None, paste_pylon: bool) -> Image.Image:
    """Optional half-scale pylon only — no HV or site flow lines."""
    if paste_pylon and pylon_sprite:
        return composite_pylon_on_right_hill(base, pylon_sprite)
    return base


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
    parser.add_argument(
        "--no-paste-pylon",
        action="store_true",
        help="Skip half-scale sprite (master tower only)",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    paste_pylon = not args.no_paste_pylon

    pylon_sprite = prepare_pylon_sprite(args.pylon_ref) if args.pylon_ref.is_file() else None
    if paste_pylon and pylon_sprite:
        print(
            f"pylon sprite {pylon_sprite.size[0]}×{pylon_sprite.size[1]} @ "
            f"({PYLON_CX}, {PYLON_ATTACH_Y}) base_y={PYLON_BASE_Y}; no flow lines"
        )
    elif pylon_sprite:
        print(f"pylon ref available ({pylon_sprite.size}); master tower only (no paste)")
    else:
        print(f"warning: no pylon reference at {args.pylon_ref}; darken only")

    master = darken_master(crop_16_9(Image.open(args.master).convert("RGB")))
    overlaid = draw_overlays(master, pylon_sprite, paste_pylon=paste_pylon)
    for name in ("clear", "cloudy", "covered", "very_covered", "night"):
        out = variant(overlaid, name)
        out.save(args.out / f"{name}.jpg", quality=92)
        print(f"wrote {args.out / f'{name}.jpg'}")


if __name__ == "__main__":
    main()

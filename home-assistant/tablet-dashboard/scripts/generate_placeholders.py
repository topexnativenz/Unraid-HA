#!/usr/bin/env python3
"""Generate tablet dashboard placeholder images (camera feeds, avatars, radar)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WWW = Path(__file__).resolve().parents[1] / "www" / "tablet-dashboard"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    return img


def camera_placeholder(name: str, top: tuple[int, int, int], bottom: tuple[int, int, int], accent: tuple[int, int, int]) -> None:
    w, h = 960, 540
    img = gradient((w, h), top, bottom)
    draw = ImageDraw.Draw(img)
    # subtle horizon line
    horizon = int(h * 0.62)
    draw.rectangle([0, horizon, w, h], fill=tuple(int(c * 0.55) for c in bottom))
    # abstract shapes suggesting outdoor scene
    draw.ellipse([w * 0.08, h * 0.12, w * 0.28, h * 0.38], fill=accent)
    draw.rounded_rectangle([w * 0.55, h * 0.35, w * 0.92, h * 0.78], radius=18, fill=(40, 44, 52))
    draw.rounded_rectangle([w * 0.62, h * 0.42, w * 0.85, h * 0.68], radius=8, fill=(72, 78, 90))
    # label pill
    label_font = _font(28)
    bbox = draw.textbbox((0, 0), name, font=label_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 18, 10
    lx, ly = 24, h - th - pad_y - 24
    draw.rounded_rectangle(
        [lx - pad_x, ly - pad_y, lx + tw + pad_x, ly + th + pad_y],
        radius=14,
        fill=(0, 0, 0, 180),
    )
    draw.text((lx, ly), name, fill=(255, 255, 255), font=label_font)
    slug = name.lower().replace(" ", "-")
    img.save(WWW / f"camera-{slug}.jpg", quality=88)


def avatar(name: str, initials: str, colors: tuple[tuple[int, int, int], tuple[int, int, int]]) -> None:
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        c = tuple(int(colors[0][i] + (colors[1][i] - colors[0][i]) * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=c + (255,))
    draw.ellipse([8, 8, size - 8, size - 8], fill=None, outline=(255, 255, 255, 90), width=4)
    font = _font(96)
    bbox = draw.textbbox((0, 0), initials, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2 - 8), initials, fill=(255, 255, 255), font=font)
    img.save(WWW / f"avatar-{name.lower()}.png")


def radar_placeholder() -> None:
    w, h = 800, 320
    img = gradient((w, h), (12, 18, 32), (8, 12, 22))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2 + 20
    for r, alpha in [(140, 40), (100, 55), (60, 70), (25, 90)]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(34, 211, 238, alpha), width=2)
    draw.line([cx, cy - 150, cx, cy + 150], fill=(34, 211, 238, 50), width=1)
    draw.line([cx - 150, cy, cx + 150, cy], fill=(34, 211, 238, 50), width=1)
    draw.pieslice([cx - 120, cy - 120, cx + 120, cy + 120], start=200, end=250, fill=(74, 222, 128, 120))
    font = _font(22)
    draw.text((24, 20), "Weather Radar (demo placeholder)", fill=(200, 210, 230), font=font)
    img.save(WWW / "radar-placeholder.png")


def main() -> None:
    WWW.mkdir(parents=True, exist_ok=True)
    camera_placeholder("Backyard", (34, 72, 48), (18, 38, 28), (74, 180, 110))
    camera_placeholder("Front Yard", (48, 58, 78), (28, 32, 42), (120, 140, 160))
    camera_placeholder("Driveway", (52, 62, 72), (36, 40, 48), (160, 170, 180))
    camera_placeholder("Porch", (44, 50, 62), (30, 34, 44), (180, 150, 120))
    avatar("david", "D", ((99, 102, 241), (168, 85, 247)))
    avatar("genna", "G", ((236, 72, 153), (251, 113, 133)))
    radar_placeholder()
    print(f"Generated placeholders in {WWW}")


if __name__ == "__main__":
    main()

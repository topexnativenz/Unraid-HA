#!/usr/bin/env python3
"""Prepare floorplan night background assets without touching house pixels.

Creates two files from base-view.png (RGB, opaque grey exterior void):
  - base-view-alpha.png — identical RGB; exterior void alpha=0 (house untouched)
  - sky-bg.png — standalone starry gradient for card_mod behind the floorplan

Only border-connected pixels matching the exterior void grey are made transparent.
Interior floors, wall tops, and model surfaces stay fully opaque with original RGB.

Input: www/floorplan/base-view.png (or --base / HA fetch).
"""

from __future__ import annotations

import argparse
import urllib.request
from collections import Counter, deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "www" / "floorplan" / "base-view.png"
DEFAULT_ALPHA_OUT = ROOT / "www" / "floorplan" / "base-view-alpha.png"
DEFAULT_SKY_OUT = ROOT / "www" / "floorplan" / "sky-bg.png"
DEFAULT_HA_BASE = "http://192.168.1.239:8123/local/my-floorplan/base-view.png"


def fetch_base(path: Path | None, ha_url: str) -> Image.Image:
    if path and path.is_file():
        return Image.open(path).convert("RGB")
    if DEFAULT_BASE.is_file():
        return Image.open(DEFAULT_BASE).convert("RGB")
    cache = Path("/tmp/base-view.png")
    if not cache.is_file():
        urllib.request.urlretrieve(ha_url, cache)
    return Image.open(cache).convert("RGB")


def _void_rgb_from_border(arr: np.ndarray) -> tuple[int, int, int]:
    h, w = arr.shape[:2]
    border: list[tuple[int, ...]] = []
    for x in range(w):
        border.append(tuple(arr[0, x]))
        border.append(tuple(arr[h - 1, x]))
    for y in range(h):
        border.append(tuple(arr[y, 0]))
        border.append(tuple(arr[y, w - 1]))
    void_rgb = Counter(border).most_common(1)[0][0]
    return int(void_rgb[0]), int(void_rgb[1]), int(void_rgb[2])


def _exterior_void_mask(arr: np.ndarray, tol: int = 3) -> np.ndarray:
    """Border flood-fill on pixels matching exterior void grey only."""
    void_r, void_g, void_b = _void_rgb_from_border(arr)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    void_match = (
        (np.abs(r.astype(np.int16) - void_r) <= tol)
        & (np.abs(g.astype(np.int16) - void_g) <= tol)
        & (np.abs(b.astype(np.int16) - void_b) <= tol)
    )
    h, w = void_match.shape
    exterior = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        if void_match[0, x]:
            q.append((0, x))
        if void_match[h - 1, x]:
            q.append((h - 1, x))
    for y in range(h):
        if void_match[y, 0]:
            q.append((y, 0))
        if void_match[y, w - 1]:
            q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        if exterior[y, x] or not void_match[y, x]:
            continue
        exterior[y, x] = True
        if y > 0:
            q.append((y - 1, x))
        if y < h - 1:
            q.append((y + 1, x))
        if x > 0:
            q.append((y, x - 1))
        if x < w - 1:
            q.append((y, x + 1))
    return exterior


def build_sky(bw: int, bh: int) -> np.ndarray:
    sky = np.zeros((bh, bw, 3), dtype=np.float32)
    top = np.array([2, 12, 30], dtype=np.float32)
    mid = np.array([10, 26, 58], dtype=np.float32)
    horizon = np.array([20, 45, 75], dtype=np.float32)
    for row in range(bh):
        t = row / max(bh - 1, 1)
        col = top * (1 - t) + mid * t
        if t > 0.55:
            hw = min(1.0, (t - 0.55) / 0.35)
            col = col * (1 - hw * 0.35) + horizon * (hw * 0.35)
        sky[row, :, :] = col

    rng = np.random.default_rng(42)
    stars = rng.random((bh, bw)) > 0.9985
    star_glow = np.zeros((bh, bw), dtype=np.float32)
    star_glow[stars] = 1.0
    star_glow = (
        np.array(Image.fromarray((star_glow * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1)))
        / 255.0
    )
    sky += star_glow[:, :, None] * np.array([180, 200, 255], dtype=np.float32)

    yy, xx = np.mgrid[0:bh, 0:bw].astype(np.float32)
    cx, cy = bw * 0.5, bh * 0.48
    dist = np.sqrt(((xx - cx) / bw) ** 2 + ((yy - cy) / bh) ** 2)
    glow = np.clip(1 - dist / 0.55, 0, 1) ** 2 * 0.12
    sky += glow[:, :, None] * np.array([30, 80, 140], dtype=np.float32)
    return np.clip(sky, 0, 255).astype(np.uint8)


def make_alpha(base: Image.Image) -> Image.Image:
    arr = np.array(base, dtype=np.uint8)
    exterior = _exterior_void_mask(arr)
    rgba = np.zeros((*arr.shape[:2], 4), dtype=np.uint8)
    rgba[:, :, :3] = arr
    rgba[:, :, 3] = 255
    rgba[exterior, 3] = 0
    transparent = int(exterior.sum())
    opaque = int((~exterior).sum())
    print(f"alpha: transparent={transparent} opaque={opaque} void_rgb={_void_rgb_from_border(arr)}")
    return Image.fromarray(rgba)


def make_sky_bg(base: Image.Image) -> Image.Image:
    bw, bh = base.size
    sky = build_sky(bw, bh)
    return Image.fromarray(sky)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, help="Local base-view.png (default: repo or HA fetch)")
    parser.add_argument("--ha-url", default=DEFAULT_HA_BASE, help="HA URL for base-view.png")
    parser.add_argument("--alpha-out", type=Path, default=DEFAULT_ALPHA_OUT)
    parser.add_argument("--sky-out", type=Path, default=DEFAULT_SKY_OUT)
    args = parser.parse_args()

    base = fetch_base(args.base, args.ha_url)
    alpha = make_alpha(base)
    sky = make_sky_bg(base)

    args.alpha_out.parent.mkdir(parents=True, exist_ok=True)
    alpha.save(args.alpha_out, optimize=True)
    sky.save(args.sky_out, optimize=True)
    print(f"Wrote {args.alpha_out} ({args.alpha_out.stat().st_size} bytes)")
    print(f"Wrote {args.sky_out} ({args.sky_out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

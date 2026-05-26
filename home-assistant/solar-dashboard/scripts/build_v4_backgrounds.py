#!/usr/bin/env python3
"""Build clean CGI backgrounds (no flow overlays).

Notes:
- The CGI master render is locked. This script only derives variants (incl. night).
- v8: optional left-sky wire inpaint (use --keep-wires to skip).
- v9: master-only weather grades (--keep-wires); no inpaint/smudge.
- v10: median wire-corridor clean (smears — superseded).
- v11: remove_left_orphan_wires — Fal fill or OpenCV TELEA (2-pass), pylon hard-restore.
- v12: remove_all_sky_wires — full sky band (no wires anywhere), pylon 100% master.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4" / "master-clear.png"
OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v4"
V5_OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v5"
V7_OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v7"
V8_OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v8"
V10_OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v10"
V11_OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v11"
V12_OUT = ROOT / "www" / "solar-dashboard" / "backgrounds" / "v12"
QA_OUT = ROOT / "assets" / "wire-removal-qa.jpg"
SKY_CLEAN_QA = ROOT / "assets" / "sky-clean-qa.jpg"
SIZE = (1920, 1080)

# Left-side sky wire corridors (1920×1080). Right-side pylon wires stay untouched.
# Far-left sky only (x < 1020) — keeps pylon-attached conductors to the right.
_UPPER_WIRE_CORRIDOR = [(0, 4), (1020, 12), (1020, 168), (0, 228)]
_MIDDLE_WIRE_CORRIDOR = [(0, 148), (1010, 162), (1010, 298), (0, 282)]
_LOWER_WIRE_CORRIDOR = [(0, 238), (1080, 288), (1080, 388), (0, 368)]

# Clean sky donor — no wires (master crop).
_SKY_PATCH_SOURCE = (1500, 40, 1900, 200)

# Master lattice tower on right hill (1920×1080) — never edit; always restore from master
PYLON_CX = 1315
PYLON_CY = 220
PYLON_RX = 90
PYLON_RY = 200
PYLON_BASE_Y = 298
# Bitmap restore bounds (lattice only — wires outside this are removed)
PYLON_BITMAP = (1180, 80, 1420, 380)

# v12 sky-edit band (1920×1080): above roofline; excludes house, trees, pylon, lower ground
_SKY_BAND_Y = 420
_SKY_EDIT_OUTER = [
    (0, 0),
    (1920, 0),
    (1920, 320),
    (1880, 312),
    (1680, 368),
    (1420, 398),
    (1180, 412),
    (880, 418),
    (520, 412),
    (280, 388),
    (0, 352),
    (0, 0),
]
_HOUSE_ROOF_EXCLUDE = [
    (88, 268),
    (720, 248),
    (920, 318),
    (880, 418),
    (520, 412),
    (280, 388),
    (88, 340),
]
_LEFT_TREES_EXCLUDE = [(0, 300), (268, 278), (312, 418), (0, 418)]
_GROUND_EXCLUDE_Y = 540  # bottom ~50% — no sky edits below this line

# Wire-bearing sky corridors (master 1920×1080) — merged into detection mask
_WIRE_SKY_CORRIDORS = [
    _UPPER_WIRE_CORRIDOR,
    _MIDDLE_WIRE_CORRIDOR,
    _LOWER_WIRE_CORRIDOR,
    [(1080, 8), (1920, 0), (1920, 195), (1120, 175)],
    [(1100, 88), (1920, 108), (1920, 298), (1140, 268)],
]

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

def _cool_grade(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Brightness(img).enhance(0.46)
    img = ImageEnhance.Contrast(img).enhance(1.14)
    img = ImageEnhance.Color(img).enhance(0.72)
    r, g, b = img.split()
    r = r.point(lambda p: int(p * 0.78))
    g = g.point(lambda p: int(p * 0.88))
    b = b.point(lambda p: min(255, int(p * 1.12)))
    return Image.merge("RGB", (r, g, b))


def _add_star_field(img: Image.Image, *, sky_y: int = 320, seed: int = 7) -> Image.Image:
    w, h = img.size
    rng = random.Random(seed)
    stars = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(stars)

    n = 720
    for i in range(n):
        x = rng.randrange(0, w)
        t = rng.random()
        y = int((t * t) * sky_y)
        if y < 0 or y >= sky_y:
            continue

        if i % 90 == 0:
            rad = rng.choice([2, 3])
            a = rng.randint(120, 190)
        else:
            rad = 1
            a = rng.randint(60, 120)

        tint = rng.random()
        if tint < 0.12:
            col = (190, 210, 255, a)
        else:
            c = rng.randint(235, 255)
            col = (c, c, c, a)

        draw.ellipse((x - rad, y - rad, x + rad, y + rad), fill=col)

    stars = stars.filter(ImageFilter.GaussianBlur(0.6))
    out = img.convert("RGBA")
    out.alpha_composite(stars)
    return out.convert("RGB")


def _add_house_glow(img: Image.Image) -> Image.Image:
    w, h = img.size
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)

    # Hand-tuned glows over house/garage openings (approx, 1920×1080 master)
    d.ellipse((220, 420, 560, 690), fill=(255, 180, 90, 110))  # main house windows
    d.ellipse((120, 470, 350, 700), fill=(255, 170, 80, 85))  # left wing glass
    d.ellipse((1260, 470, 1605, 760), fill=(255, 190, 110, 120))  # garage interior
    d.ellipse((1455, 500, 1695, 700), fill=(255, 195, 120, 90))  # inverter wall vicinity

    glow = glow.filter(ImageFilter.GaussianBlur(26))
    out = img.convert("RGBA")
    out.alpha_composite(glow)
    return out.convert("RGB")


def _pylon_protect_mask(w: int, h: int, *, soft: bool = False) -> Image.Image:
    """L mask: 255 = lattice + hill foot only (not conductor airspace)."""
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    # Narrow lattice core inside bitmap bounds (wires pass outside this)
    d.rectangle(
        (PYLON_CX - 38, PYLON_CY - 20, PYLON_CX + 42, PYLON_BASE_Y + 8),
        fill=255,
    )
    d.ellipse(
        (PYLON_CX - PYLON_RX, PYLON_CY - PYLON_RY, PYLON_CX + PYLON_RX, PYLON_CY + PYLON_RY),
        fill=255,
    )
    d.polygon(
        [
            (PYLON_CX - 72, PYLON_BASE_Y - 6),
            (PYLON_CX + 78, PYLON_BASE_Y - 6),
            (PYLON_CX + 78, h),
            (PYLON_CX - 72, h),
        ],
        fill=255,
    )
    return mask.filter(ImageFilter.GaussianBlur(2)) if soft else mask


def _sky_edit_region_mask(w: int, h: int) -> Image.Image:
    """L mask: 255 = sky pixels allowed for wire removal (excludes house, trees, pylon, ground)."""
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.polygon(_SKY_EDIT_OUTER, fill=255)
    for poly in (_HOUSE_ROOF_EXCLUDE, _LEFT_TREES_EXCLUDE):
        d.polygon(poly, fill=0)
    d.rectangle((0, _GROUND_EXCLUDE_Y, w, h), fill=0)
    d.rectangle((0, _SKY_BAND_Y, w, h), fill=0)
    protect = _pylon_protect_mask(w, h, soft=False)
    m_px = mask.load()
    p_px = protect.load()
    for y in range(h):
        for x in range(w):
            if p_px[x, y] > 0:
                m_px[x, y] = 0
    return mask


def _wire_corridor_mask(w: int, h: int) -> Image.Image:
    """L mask: sky zones known to contain conductors in master."""
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    for poly in _WIRE_SKY_CORRIDORS:
        d.polygon(poly, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(3))


def _hough_wire_strokes(img: Image.Image, region: np.ndarray) -> np.ndarray:
    """Binary mask of Hough line segments in region."""
    gray = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 45, 130)
    edges[~region] = 0
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=55,
        minLineLength=70,
        maxLineGap=25,
    )
    mask = np.zeros(gray.shape, dtype=np.uint8)
    if lines is None:
        return mask
    for seg in lines:
        x1, y1, x2, y2 = seg[0]
        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness=6)
    return mask


def _detect_sky_wire_mask(
    img: Image.Image,
    sky_edit: Image.Image,
    protect: Image.Image,
    *,
    dilate_px: int = 5,
) -> Image.Image:
    """Find wire / smear pixels inside sky_edit only (excludes pylon lattice)."""
    rgb = np.array(img.convert("RGB"), dtype=np.uint8)
    edit = np.array(sky_edit) > 64
    prot = np.array(protect) > 32
    region = edit & ~prot

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    sat = hsv[:, :, 1].astype(np.float32)

    lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F))
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(gx, gy)

    k_line = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9))
    tophat = cv2.morphologyEx(gray.astype(np.uint8), cv2.MORPH_BLACKHAT, k_line).astype(np.float32)

    dark_line = region & (gray < 175) & ((grad > 10) | (tophat > 8)) & (lap > 4)
    faint_smear = region & (gray < 200) & (sat < 48) & ((lap > 3) | (tophat > 6))
    wire = (dark_line | faint_smear).astype(np.uint8) * 255

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    opened = cv2.morphologyEx(wire, cv2.MORPH_OPEN, k3)
    thin = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, k3)

    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1, dilate_px * 2 + 1))
    dilated = cv2.dilate(thin, k5, iterations=1)

    w, h = img.size
    corridors = np.array(_wire_corridor_mask(w, h)) > 64
    corridor_dark = corridors & region & (gray < 178) & ((grad > 8) | (tophat > 5))
    hough = _hough_wire_strokes(img, region)
    merged = np.maximum(dilated, np.maximum(corridor_dark.astype(np.uint8) * 255, hough))
    return Image.fromarray(merged).filter(ImageFilter.GaussianBlur(1))


def _remaining_sky_wire_mask(
    img: Image.Image,
    sky_edit: Image.Image,
    protect: Image.Image,
) -> Image.Image:
    """Second-pass mask for residual dark pixels in sky band."""
    rgb = np.array(img.convert("RGB"), dtype=np.float32)
    edit = np.array(sky_edit) > 64
    prot = np.array(protect) > 32
    region = edit & ~prot
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    hsv = cv2.cvtColor(np.array(img.convert("RGB"), dtype=np.uint8), cv2.COLOR_RGB2HSV)
    sat = hsv[:, :, 1].astype(np.float32)
    faint = region & (lum < 178) & (sat < 48)
    return Image.fromarray((faint.astype(np.uint8) * 255))


def _sky_gradient_donor_fill(img: Image.Image, sky_edit: Image.Image, wire_mask: Image.Image) -> Image.Image:
    """Feather clean top-right sky donor only inside wire_mask bbox (no full-frame stretch)."""
    bbox = wire_mask.getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    donor = img.crop(_SKY_PATCH_SOURCE).resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    filled = img.copy()
    filled.paste(donor, (x0, y0))
    feather = wire_mask.crop(bbox).filter(ImageFilter.GaussianBlur(8))
    full_alpha = Image.new("L", img.size, 0)
    full_alpha.paste(feather, (x0, y0))
    return Image.composite(filled, img, full_alpha)


def _hard_sky_composite(
    master: Image.Image,
    cleaned: Image.Image,
    sky_edit: Image.Image,
    protect: Image.Image,
) -> Image.Image:
    """Outside sky_edit: master. Inside sky_edit: cleaned. Pylon protect: always master."""
    m = np.array(master.convert("RGB"), dtype=np.uint8)
    c = np.array(cleaned.convert("RGB"), dtype=np.uint8)
    edit = np.array(sky_edit) > 64
    prot = np.array(protect) > 64
    out = m.copy()
    out[edit & ~prot] = c[edit & ~prot]
    out[prot] = m[prot]
    return Image.fromarray(out)


def _left_wire_corridor_mask(w: int, h: int) -> Image.Image:
    """L mask: 255 = inpaint target (left orphan wire corridors only)."""
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    for poly in (_UPPER_WIRE_CORRIDOR, _MIDDLE_WIRE_CORRIDOR, _LOWER_WIRE_CORRIDOR):
        d.polygon(poly, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(4))


def _corridor_mask_excluding_pylon(w: int, h: int) -> Image.Image:
    corridor = _left_wire_corridor_mask(w, h)
    protect = _pylon_protect_mask(w, h, soft=True)
    c_px = corridor.load()
    p_px = protect.load()
    for y in range(h):
        for x in range(w):
            if p_px[x, y] > 0:
                c_px[x, y] = 0
    return corridor


def _load_fal_key() -> str | None:
    key = os.environ.get("FAL_KEY", "").strip()
    if key:
        return key
    mcp = Path.home() / ".cursor" / "mcp.json"
    if not mcp.exists():
        return None
    try:
        data = json.loads(mcp.read_text())
        return (data.get("mcpServers", {}).get("user-media-render", {}).get("env", {}).get("FAL_KEY") or "").strip() or None
    except (json.JSONDecodeError, OSError):
        return None


def _save_wire_mask_png(path: Path, mask: Image.Image) -> None:
    """RGB mask for Fal: white = edit, black = keep."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = Image.merge("RGB", (mask, mask, mask))
    rgb.save(path)


def _wire_stroke_mask(img: Image.Image, corridor: Image.Image, protect: Image.Image) -> Image.Image:
    """L mask: 255 = thin wire pixels inside corridor, excluding pylon protect."""
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    cmask = np.array(corridor) > 64
    pmask = np.array(protect) > 32
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    dark = cmask & ~pmask & (lum < 168)
    mask = Image.fromarray((dark.astype(np.uint8) * 255))
    return mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(2))


def _remaining_wire_mask(img: Image.Image, corridor: Image.Image, protect: Image.Image) -> Image.Image:
    """Second-pass mask for faint wire halos left in corridor."""
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    cmask = np.array(corridor) > 64
    pmask = np.array(protect) > 32
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    faint = cmask & ~pmask & (lum < 172)
    return Image.fromarray((faint.astype(np.uint8) * 255))


def _sky_patch_fill(img: Image.Image, blend_mask: Image.Image) -> Image.Image:
    """Paste resized clean-sky donor (1500,40)-(1900,200) through feathered wire mask."""
    bbox = blend_mask.getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    donor = img.crop(_SKY_PATCH_SOURCE).resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    filled = img.copy()
    filled.paste(donor, (x0, y0))
    feather = blend_mask.filter(ImageFilter.GaussianBlur(8))
    return Image.composite(filled, img, feather)


def _inpaint_telea(img: Image.Image, wire_mask: Image.Image, *, radius: int = 5) -> Image.Image:
    bgr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    m = np.array(wire_mask)
    if m.max() == 0:
        return img
    repaired = cv2.inpaint(bgr, m, radius, cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.cvtColor(repaired, cv2.COLOR_BGR2RGB))


def _fal_inpaint_sky(img: Image.Image, wire_mask: Image.Image, *, mask_path: Path) -> Image.Image:
    """Fal flux-pro fill: remove masked orphan wires; restore pylon from master."""
    key = _load_fal_key()
    if not key:
        raise RuntimeError("FAL_KEY not set")

    os.environ["FAL_KEY"] = key
    import fal_client

    w, h = img.size
    tmp = mask_path.parent
    tmp.mkdir(parents=True, exist_ok=True)
    src_jpg = tmp / "_fal_source.jpg"
    msk_png = mask_path

    img.convert("RGB").save(src_jpg, quality=95)
    _save_wire_mask_png(msk_png, wire_mask)

    image_url = fal_client.upload_file(str(src_jpg))
    mask_url = fal_client.upload_file(str(msk_png))

    prompt = (
        "Seamless photorealistic daytime blue sky with soft white wispy clouds, "
        "matching the surrounding sky exactly. No power lines, no wires, no cables, "
        "no smudges, no blur artifacts. Natural clear sky only."
    )
    result = fal_client.subscribe(
        "fal-ai/flux-pro/v1/fill",
        arguments={
            "prompt": prompt,
            "image_url": image_url,
            "mask_url": mask_url,
        },
    )
    images = result.get("images") or []
    if not images:
        raise RuntimeError(f"Fal fill returned no images: {result}")

    image_entry = images[0]
    out_url = image_entry.get("url") if isinstance(image_entry, dict) else image_entry
    if not out_url:
        raise RuntimeError(f"No image URL in Fal response: {result}")

    import httpx

    with httpx.Client(timeout=180.0) as client:
        resp = client.get(out_url)
        resp.raise_for_status()
        filled = Image.open(__import__("io").BytesIO(resp.content)).convert("RGB")

    if filled.size != (w, h):
        filled = filled.resize((w, h), Image.Resampling.LANCZOS)

    protect = _pylon_protect_mask(w, h, soft=False)
    feather = wire_mask.filter(ImageFilter.GaussianBlur(6))
    wired = Image.composite(filled, img, feather)
    return Image.composite(img, wired, protect)


def save_wire_removal_qa(before: Image.Image, after: Image.Image, path: Path) -> None:
    """Side-by-side crop of left sky band (before | after)."""
    band = (0, 0, 1280, 400)
    qa = Image.new("RGB", (band[2] * 2, band[3]))
    qa.paste(before.crop(band), (0, 0))
    qa.paste(after.crop(band), (band[2], 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    qa.save(path, quality=90)
    print(f"wrote QA {path}")


def save_sky_clean_qa(before: Image.Image, after: Image.Image, path: Path) -> None:
    """Full-width sky strip y=0..450 (before | after)."""
    band = (0, 0, before.width, 450)
    qa = Image.new("RGB", (band[2] * 2, band[3]))
    qa.paste(before.crop(band), (0, 0))
    qa.paste(after.crop(band), (band[2], 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    qa.save(path, quality=90)
    print(f"wrote QA {path}")


def remove_left_orphan_wires(
    img: Image.Image,
    *,
    method: str = "auto",
    mask_dir: Path | None = None,
) -> tuple[Image.Image, str]:
    """Remove left orphan sky wires; keep pylon-attached conductors. Returns (image, method)."""
    w, h = img.size
    base = img.convert("RGB")
    protect_hard = _pylon_protect_mask(w, h, soft=False)
    corridor = _corridor_mask_excluding_pylon(w, h)
    if not corridor.getbbox():
        return base, "none"

    wire_mask = _wire_stroke_mask(base, corridor, protect_hard)
    if not wire_mask.getbbox():
        return base, "none"

    mask_dir = mask_dir or V11_OUT
    mask_path = mask_dir / "wire-inpaint-mask.png"
    _save_wire_mask_png(mask_path, wire_mask)

    if method == "fal":
        if not _load_fal_key():
            raise RuntimeError("FAL_KEY not set (required for --wire-method fal)")
        return _fal_inpaint_sky(base, wire_mask, mask_path=mask_path), "fal-flux-pro-fill"

    inpainted = _inpaint_telea(base, wire_mask, radius=7)
    pass2 = _remaining_wire_mask(inpainted, corridor, protect_hard)
    if pass2.getbbox():
        inpainted = _inpaint_telea(inpainted, pass2, radius=5)
    patched = _sky_patch_fill(inpainted, wire_mask)
    out = np.array(patched, dtype=np.uint8)
    base_arr = np.array(base, dtype=np.uint8)
    prot = np.array(protect_hard) > 64
    out[prot] = base_arr[prot]
    return Image.fromarray(out), "opencv-telea+sky-donor"


def remove_all_sky_wires(
    img: Image.Image,
    *,
    method: str = "opencv",
    mask_dir: Path | None = None,
) -> tuple[Image.Image, str]:
    """Remove every wire/smear in sky band; pylon + non-sky pixels stay 100% master."""
    w, h = img.size
    base = img.convert("RGB")
    protect = _pylon_protect_mask(w, h, soft=False)
    sky_edit = _sky_edit_region_mask(w, h)
    if not sky_edit.getbbox():
        return base, "none"

    wire_mask = _detect_sky_wire_mask(base, sky_edit, protect, dilate_px=4)
    if not wire_mask.getbbox():
        return base, "none"

    mask_dir = mask_dir or V12_OUT
    mask_path = mask_dir / "sky-wire-mask.png"
    _save_wire_mask_png(mask_path, wire_mask)

    if method == "fal":
        if not _load_fal_key():
            raise RuntimeError("FAL_KEY not set (required for --wire-method fal)")
        filled = _fal_inpaint_sky(base, wire_mask, mask_path=mask_path)
        return _hard_sky_composite(base, filled, sky_edit, protect), "fal-flux-pro-fill"

    inpainted = _inpaint_telea(base, wire_mask, radius=8)
    for radius in (8, 7, 6, 5, 5):
        pass_n = _remaining_sky_wire_mask(inpainted, sky_edit, protect)
        if not pass_n.getbbox():
            break
        inpainted = _inpaint_telea(inpainted, pass_n, radius=radius)
    # Target any still-dark pixels along original wire mask
    wm_arr = np.array(wire_mask) > 32
    lum = cv2.cvtColor(np.array(inpainted), cv2.COLOR_RGB2GRAY).astype(np.float32)
    stubborn = wm_arr & (lum < 168)
    if stubborn.any():
        stub_mask = Image.fromarray((stubborn.astype(np.uint8) * 255))
        inpainted = _inpaint_telea(inpainted, stub_mask, radius=7)
    patched = _sky_gradient_donor_fill(inpainted, sky_edit, wire_mask)
    out = _hard_sky_composite(base, patched, sky_edit, protect)
    # Final lattice restore from master (bitmap bounds, narrow mask above)
    bx0, by0, bx1, by1 = PYLON_BITMAP
    lattice = _pylon_protect_mask(w, h, soft=False)
    out_arr = np.array(out, dtype=np.uint8)
    base_arr = np.array(base, dtype=np.uint8)
    lat = np.array(lattice) > 64
    out_arr[lat] = base_arr[lat]
    return Image.fromarray(out_arr), "opencv-telea+sky-gradient"


def pylon_pixel_diff(master: Image.Image, edited: Image.Image) -> tuple[int, float]:
    """Return (changed_pixels, max_channel_delta) inside pylon protect mask."""
    w, h = master.size
    protect = _pylon_protect_mask(w, h, soft=False)
    m_px = master.convert("RGB").load()
    e_px = edited.convert("RGB").load()
    p_px = protect.load()
    changed = 0
    max_delta = 0
    for y in range(h):
        for x in range(w):
            if p_px[x, y] < 128:
                continue
            dr = abs(m_px[x, y][0] - e_px[x, y][0])
            dg = abs(m_px[x, y][1] - e_px[x, y][1])
            db = abs(m_px[x, y][2] - e_px[x, y][2])
            d = max(dr, dg, db)
            if d:
                changed += 1
                max_delta = max(max_delta, d)
    return changed, max_delta


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
        n = _cool_grade(img)
        n = _add_star_field(n)
        n = _add_house_glow(n)
        return n
    raise ValueError(mode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=MASTER)
    parser.add_argument("--out", type=Path, default=V12_OUT)
    parser.add_argument("--keep-wires", action="store_true", help="Skip sky wire removal")
    parser.add_argument(
        "--wire-method",
        choices=("opencv", "fal"),
        default="opencv",
        help="Wire removal: OpenCV TELEA + sky donor (default), or Fal fill",
    )
    parser.add_argument(
        "--legacy-left-wires",
        action="store_true",
        help="v11 left-corridor removal only (default is v12 full sky)",
    )
    parser.add_argument("--qa", type=Path, default=None, help="Before/after sky QA crop")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    v12 = not args.legacy_left_wires and args.out.resolve() == V12_OUT.resolve()
    if args.qa is None:
        args.qa = SKY_CLEAN_QA if v12 else QA_OUT

    print(f"building backgrounds from {args.master} -> {args.out}")

    master = prepare_daytime_master(crop_16_9(Image.open(args.master).convert("RGB")))
    wire_method = "skipped"
    if args.keep_wires:
        base = master
    elif v12 or not args.legacy_left_wires:
        base, wire_method = remove_all_sky_wires(
            master, method=args.wire_method, mask_dir=args.out
        )
        print(f"wire removal method: {wire_method}")
        save_sky_clean_qa(master, base, args.qa)
    else:
        base, wire_method = remove_left_orphan_wires(
            master, method=args.wire_method, mask_dir=args.out
        )
        print(f"wire removal method: {wire_method}")
        save_wire_removal_qa(master, base, args.qa)
    if not args.keep_wires:
        changed, max_d = pylon_pixel_diff(master, base)
        print(f"pylon protect: {changed} changed px, max delta {max_d}")
        if changed > 0:
            raise SystemExit(f"pylon region altered ({changed} px) — aborting")
    for name in ("clear", "cloudy", "covered", "very_covered", "night"):
        out = variant(base, name)
        out.save(args.out / f"{name}.jpg", quality=92)
        print(f"wrote {args.out / f'{name}.jpg'}")

    # Back-compat copy: if someone explicitly rebuilds v4, also mirror to v5.
    if args.out == OUT:
        V5_OUT.mkdir(parents=True, exist_ok=True)
        for name in ("clear", "cloudy", "covered", "very_covered", "night"):
            src = args.out / f"{name}.jpg"
            dst = V5_OUT / f"{name}.jpg"
            dst.write_bytes(src.read_bytes())
            print(f"copied {dst}")


if __name__ == "__main__":
    main()

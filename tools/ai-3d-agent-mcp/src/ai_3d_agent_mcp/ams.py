from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image


# Practical PLA-ish AMS palette suggestions (name → approx RGB)
PALETTE = [
    ("Black", (20, 20, 20)),
    ("White", (245, 245, 245)),
    ("Red", (200, 40, 40)),
    ("Orange", (230, 120, 40)),
    ("Yellow", (240, 210, 50)),
    ("Green", (40, 160, 70)),
    ("Blue", (40, 90, 200)),
    ("Purple", (120, 60, 160)),
    ("Gray", (140, 140, 140)),
    ("Brown", (110, 70, 40)),
    ("Pink", (230, 140, 170)),
    ("Cyan", (60, 190, 210)),
]


def _nearest(rgb: tuple[int, int, int]) -> str:
    best_name = PALETTE[0][0]
    best_dist = 1e18
    for name, pref in PALETTE:
        dist = sum((a - b) ** 2 for a, b in zip(rgb, pref))
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def suggest_ams_from_images(image_paths: list[str], max_slots: int = 4) -> dict[str, Any]:
    """
    Extract dominant colours and map to AMS filament slot suggestions.
    Bambu colour painting still happens in Studio; this primes the filament list.
    """
    if not image_paths:
        return {
            "slots": [{"slot": 1, "color": "White", "material_hint": "PLA", "role": "body"}],
            "note": "No images — default single white PLA slot.",
        }

    samples: list[tuple[int, int, int]] = []
    for raw in image_paths[:4]:
        path = Path(raw).expanduser()
        if not path.is_file():
            continue
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((64, 64))
            pixels = list(im.getdata())
            # Drop near-white / near-black background-ish extremes lightly
            for r, g, b in pixels:
                if r > 245 and g > 245 and b > 245:
                    continue
                if r < 12 and g < 12 and b < 12:
                    continue
                samples.append((r, g, b))

    if not samples:
        return {
            "slots": [{"slot": 1, "color": "White", "material_hint": "PLA", "role": "body"}],
            "note": "Could not sample colours; default white.",
        }

    # Quantize by rounding to 32-step buckets then map to palette names
    buckets: Counter[str] = Counter()
    for r, g, b in samples:
        qr = (r // 32) * 32 + 16
        qg = (g // 32) * 32 + 16
        qb = (b // 32) * 32 + 16
        buckets[_nearest((qr, qg, qb))] += 1

    top = [name for name, _ in buckets.most_common(max_slots)]
    if not top:
        top = ["White"]

    roles = ["body", "accent", "detail", "support_interface"]
    slots = []
    for i, name in enumerate(top, start=1):
        slots.append(
            {
                "slot": i,
                "color": name,
                "material_hint": "PLA",
                "role": roles[min(i - 1, len(roles) - 1)],
                "sample_weight": buckets[name],
            }
        )

    return {
        "slots": slots,
        "note": (
            "Suggested AMS mapping from image colours. Open the 3MF in Bambu Studio, "
            "assign filaments to slots, then paint/segment as needed. No auto-print."
        ),
    }

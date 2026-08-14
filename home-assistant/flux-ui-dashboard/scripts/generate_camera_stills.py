#!/usr/bin/env python3
"""Generate branded animated WebP camera stills for Flux UI tiles.

Reads source PNGs from --source-dir (or regenerates via ffmpeg only when
sources already exist). Outputs to www/flux-ui/camera-stills/<entity>.webp.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STILLS = ROOT / "www" / "flux-ui" / "camera-stills"

# Source stem → HA camera entity suffix (tile filename without .webp).
CAMERA_SOURCES: dict[str, str] = {
    "cam-back-courtyard": "back_courtyard_fluent",
    "cam-driveway": "side_door",
    "cam-side-of-house": "side_of_house",
    "cam-garage-door": "garage_door",
    "cam-front-door": "front_door_doorbell",
}


def animate(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        "scale=960:540:force_original_aspect_ratio=increase,"
        "crop=960:540,"
        "zoompan="
        "z='1.015+0.03*sin(2*PI*on/48)':"
        "x='iw/2-(iw/zoom/2)+12*sin(2*PI*on/60)':"
        "y='ih/2-(ih/zoom/2)+8*cos(2*PI*on/52)':"
        "d=1:s=720x405:fps=10,"
        "eq=brightness=0.015:saturation=1.04,"
        "vignette=PI/5"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-i",
        str(src),
        "-vf",
        vf,
        "-t",
        "4.8",
        "-an",
        "-c:v",
        "libwebp",
        "-lossless",
        "0",
        "-compression_level",
        "6",
        "-q:v",
        "55",
        "-loop",
        "0",
        str(dest),
    ]
    subprocess.check_call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=ROOT / "www" / "flux-ui" / "camera-stills" / "sources",
        help="Directory containing cam-*.png sources",
    )
    args = parser.parse_args()
    missing = []
    for stem, suffix in CAMERA_SOURCES.items():
        src = args.source_dir / f"{stem}.png"
        if not src.exists():
            missing.append(str(src))
            continue
        dest = STILLS / f"{suffix}.webp"
        print(f"  {src.name} → {dest.relative_to(ROOT)}")
        animate(src, dest)
        print(f"    {dest.stat().st_size // 1024} KiB")
    if missing:
        print("Missing sources:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1
    print(f"Wrote animated stills under {STILLS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

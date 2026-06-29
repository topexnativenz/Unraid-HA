#!/usr/bin/env python3
"""One-off smoke test for img2img_with_reference (Moore Ave archviz)."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from media_render_mcp.config import load_config
from media_render_mcp.render import img2img_with_reference_live

REFERENCE = Path(
    "/Users/topexnative/.cursor/projects/Volumes-appdata-claude-agent-data-projects/"
    "assets/moore-ave-main-house-render-v2.png"
)
OUTPUT = REFERENCE.parent / "moore-ave-main-house-render-fal-v1.png"
PROMPT = (
    "clean pseudo-realistic CAD isometric cutaway, professional entourage, no labels"
)

ICLOUD_CANDIDATES = [
    Path.home()
    / "Library/Mobile Documents/com~apple~CloudDocs/1. PROPERTY/1 Moore Avenue, Tawhero, Whanganui/Corrected Renders",
    Path.home()
    / "Library/Mobile Documents/com~apple~CloudDocs/Moore Ave/Corrected Renders",
    Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Corrected Renders",
]


def find_icloud_dest() -> Path | None:
    for candidate in ICLOUD_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


def main() -> int:
    if not os.environ.get("FAL_KEY"):
        print(json.dumps({"error": "FAL_KEY not set", "mode": "aborted"}, indent=2))
        return 1
    if not REFERENCE.is_file():
        print(json.dumps({"error": f"Reference missing: {REFERENCE}"}, indent=2))
        return 1

    os.environ.setdefault("RENDER_LIVE", "1")
    cfg = load_config()
    result = img2img_with_reference_live(
        cfg,
        reference_path=str(REFERENCE),
        prompt=PROMPT,
        strength=0.65,
        output_path=str(OUTPUT),
    )
    print(json.dumps(result, indent=2))

    if result.get("mode") != "live" or not result.get("written"):
        return 1

    icloud = find_icloud_dest()
    if icloud:
        dest = icloud / OUTPUT.name
        shutil.copy2(OUTPUT, dest)
        print(json.dumps({"icloud_copy": str(dest)}, indent=2))
    else:
        print(json.dumps({"icloud_copy": None, "note": "Corrected Renders folder not found"}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

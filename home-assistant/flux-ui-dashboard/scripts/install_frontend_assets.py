#!/usr/bin/env python3
"""Download bundled frontend JS for Flux UI overview (Mushroom + card-mod)."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / "www" / "community"

# (folder, download_url) — mushroom from GitHub release; card-mod from repo master (no release asset).
ASSETS: list[tuple[str, str]] = [
    (
        "lovelace-mushroom",
        "release:piitaya/lovelace-mushroom:mushroom.js",
    ),
    (
        "lovelace-card-mod",
        "https://raw.githubusercontent.com/thomasloven/lovelace-card-mod/master/card-mod.js",
    ),
]


def github_release_asset(repo: str, filename: str) -> str:
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(api, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    for asset in data.get("assets", []):
        if asset["name"] == filename:
            return asset["browser_download_url"]
    raise RuntimeError(f"{filename} not found in latest release of {repo}")


def resolve_url(spec: str) -> str:
    if spec.startswith("release:"):
        repo, filename = spec.removeprefix("release:").split(":", 1)
        return github_release_asset(repo, filename)
    return spec


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(["curl", "-fsSL", url, "-o", str(dest)])
    print(f"  {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)")


def main() -> int:
    for folder, url_spec in ASSETS:
        dest = WWW / folder / ("mushroom.js" if "mushroom" in folder else "card-mod.js")
        if dest.exists() and dest.stat().st_size > 10_000:
            print(f"  skip {dest.relative_to(ROOT)} (exists)")
            continue
        url = resolve_url(url_spec)
        download(url, dest)

    print(f"Frontend assets ready under {WWW.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import re
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = _PKG_ROOT.parent.parent
MCP_ROOT = _PKG_ROOT

_VERSION_DIR_RE = re.compile(r"^v\d+$", re.IGNORECASE)


def resolve_repo_path(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def list_version_folders(backgrounds_root: Path) -> list[str]:
    if not backgrounds_root.is_dir():
        return []
    versions: list[str] = []
    for entry in sorted(backgrounds_root.iterdir()):
        if entry.is_dir() and _VERSION_DIR_RE.match(entry.name):
            versions.append(entry.name)
    return versions


def next_version_folder(backgrounds_root: Path) -> str:
    versions = list_version_folders(backgrounds_root)
    if not versions:
        return "v1"
    nums = []
    for v in versions:
        try:
            nums.append(int(v[1:]))
        except ValueError:
            continue
    return f"v{max(nums, default=0) + 1}"


def variant_output_path(backgrounds_root: Path, version_folder: str, variant: str = "clear") -> Path:
    return backgrounds_root / version_folder / f"{variant}.jpg"

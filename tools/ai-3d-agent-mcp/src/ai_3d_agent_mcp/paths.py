from __future__ import annotations

from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = _PKG_ROOT.parent.parent
MCP_ROOT = _PKG_ROOT


def resolve_repo_path(relative: str) -> Path:
    path = Path(relative).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()

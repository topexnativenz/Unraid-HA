from __future__ import annotations

from pathlib import Path

from media_render_mcp.config import MediaRenderConfig
from media_render_mcp.paths import list_version_folders, next_version_folder, variant_output_path


class GuardrailError(ValueError):
    """Blocked action per media-render policy."""


def assert_not_locked_master(
    reference_path: Path,
    cfg: MediaRenderConfig,
    *,
    allow_master_override: bool = False,
) -> None:
    locked = cfg.locked_master_path.resolve()
    ref = reference_path.resolve()
    if ref == locked and not allow_master_override:
        raise GuardrailError(
            f"Refusing edit on LOCKED master ({cfg.locked_master}). "
            "Set allow_master_override=true only with explicit user art direction."
        )


def assert_version_folder_new_or_empty(
    backgrounds_root: Path,
    version_folder: str,
    variant: str = "clear",
) -> None:
    out = variant_output_path(backgrounds_root, version_folder, variant)
    if out.exists():
        suggested = next_version_folder(backgrounds_root)
        raise GuardrailError(
            f"Refusing to overwrite existing asset: {out.name} in {version_folder}/. "
            f"Use a new version folder (e.g. {suggested}) instead of overwriting baked JPGs."
        )


def assert_version_folder_exists_for_publish(backgrounds_root: Path, version_folder: str) -> None:
    folder = backgrounds_root / version_folder
    if not folder.is_dir():
        known = ", ".join(list_version_folders(backgrounds_root)) or "(none)"
        raise GuardrailError(f"Version folder {version_folder}/ does not exist. Known: {known}")

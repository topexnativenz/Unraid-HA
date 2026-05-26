from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from media_render_mcp.config import MediaRenderConfig

_CACHE_BUST_RE = re.compile(r"(\?v=)([0-9a-zA-Z]+)")


def new_cache_bust_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d") + "a"


def update_lovelace_cache_bust(
    cfg: MediaRenderConfig,
    *,
    version_folder: str,
    dry_run: bool = True,
) -> dict:
    """Update ?v= tokens and /backgrounds/vN/ paths in configured Lovelace YAML files."""
    token = new_cache_bust_token()
    changes: list[dict] = []

    from media_render_mcp.paths import resolve_repo_path

    for rel in cfg.lovelace_yaml_paths:
        yaml_path = resolve_repo_path(rel)
        if not yaml_path.is_file():
            changes.append({"file": str(yaml_path), "status": "missing", "skipped": True})
            continue

        text = yaml_path.read_text()
        updated = text
        updated = re.sub(
            r"/local/solar-dashboard/backgrounds/v\d+/",
            f"/local/solar-dashboard/backgrounds/{version_folder}/",
            updated,
        )
        updated = _CACHE_BUST_RE.sub(rf"\g<1>{token}", updated)

        if updated == text:
            changes.append({"file": str(yaml_path), "status": "unchanged"})
            continue

        if dry_run:
            changes.append(
                {
                    "file": str(yaml_path),
                    "status": "would_update",
                    "cache_bust": token,
                    "version_folder": version_folder,
                }
            )
        else:
            yaml_path.write_text(updated)
            changes.append(
                {
                    "file": str(yaml_path),
                    "status": "updated",
                    "cache_bust": token,
                    "version_folder": version_folder,
                }
            )

    return {"cache_bust": token, "version_folder": version_folder, "dry_run": dry_run, "files": changes}


def deploy_documentation(cfg: MediaRenderConfig) -> str:
    script = cfg.deploy_script_path
    return (
        f"After assets are in repo, run deploy (same pattern as solar dashboard):\n"
        f"  cd {script.parent} && python3 {script.name}\n"
        f"Requires HA token in ~/.cursor/mcp.json (homeassistant server) and SMB mount on macOS."
    )

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from media_render_mcp.config import load_config
from media_render_mcp.guardrails import (
    GuardrailError,
    assert_not_locked_master,
    assert_version_folder_exists_for_publish,
)
from media_render_mcp.paths import list_version_folders, resolve_repo_path
from media_render_mcp.publish import deploy_documentation, update_lovelace_cache_bust
from media_render_mcp.render import plan_render_image, render_image_live, render_live_enabled

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("media-render-mcp")

mcp = FastMCP(
    "user-media-render",
    instructions=(
        "Generate and publish solar dashboard background assets via Fal.ai with guardrails: "
        "LOCKED master (v5/master-clear.png), version folders (vN), and Lovelace cache-bust."
    ),
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2)


@mcp.tool()
def list_versions() -> str:
    """Scan solar-dashboard backgrounds for v* version folders and their JPG assets."""
    cfg = load_config()
    root = cfg.backgrounds_path
    versions = list_version_folders(root)
    detail: dict[str, Any] = {"backgrounds_root": str(root), "versions": versions, "folders": {}}
    for v in versions:
        folder = root / v
        jpgs = sorted(p.name for p in folder.glob("*.jpg"))
        masters = sorted(p.name for p in folder.glob("master-*.png"))
        detail["folders"][v] = {"jpg": jpgs, "masters": masters}
    return _json(detail)


@mcp.tool()
def render_image(
    prompt: str,
    width: int = 1920,
    height: int = 1080,
    version_folder: str = "v8",
    variant: str = "clear",
    dry_run: bool = True,
) -> str:
    """Generate a background JPG (Fal when RENDER_LIVE=1 and FAL_KEY set). Default dry_run plans paths only."""
    cfg = load_config()
    try:
        if dry_run:
            plan = plan_render_image(
                cfg,
                prompt=prompt,
                width=width,
                height=height,
                version_folder=version_folder,
                variant=variant,
            )
            return _json(
                {
                    **plan,
                    "hint": "Set dry_run=false and RENDER_LIVE=1 (plus FAL_KEY) to call Fal.",
                }
            )

        if render_live_enabled():
            result = render_image_live(
                cfg,
                prompt=prompt,
                width=width,
                height=height,
                version_folder=version_folder,
                variant=variant,
            )
            return _json(result)

        plan = plan_render_image(
            cfg,
            prompt=prompt,
            width=width,
            height=height,
            version_folder=version_folder,
            variant=variant,
        )
        return _json(
            {
                **plan,
                "error": "RENDER_LIVE not set; refusing to write without RENDER_LIVE=1.",
                "blocked": True,
            }
        )
    except GuardrailError as exc:
        return _json({"error": str(exc), "blocked": True})


@mcp.tool()
def edit_image(
    reference_path: str,
    prompt: str,
    mask_path: str | None = None,
    version_folder: str | None = None,
    allow_master_override: bool = False,
    dry_run: bool = True,
) -> str:
    """Edit an existing reference image (inpaint/outpaint). Blocks LOCKED master unless override."""
    cfg = load_config()
    ref = resolve_repo_path(reference_path)
    try:
        assert_not_locked_master(ref, cfg, allow_master_override=allow_master_override)
    except GuardrailError as exc:
        return _json({"error": str(exc), "blocked": True})

    out_version = version_folder or "v8"
    payload = {
        "mode": "stub",
        "reference_path": str(ref),
        "prompt": prompt,
        "mask_path": str(resolve_repo_path(mask_path)) if mask_path else None,
        "version_folder": out_version,
        "dry_run": dry_run,
        "note": "Phase 0: Fal edit/inpaint wiring in Phase 1+.",
    }
    if dry_run:
        payload["planned_output"] = str(cfg.backgrounds_path / out_version / "clear.jpg")
    return _json(payload)


@mcp.tool()
def img2img_with_reference(
    reference_path: str,
    prompt: str,
    version_folder: str = "v8",
    strength: float = 0.65,
    dry_run: bool = True,
) -> str:
    """Image-to-image using a reference frame (stub in Phase 0)."""
    cfg = load_config()
    ref = resolve_repo_path(reference_path)
    try:
        assert_not_locked_master(ref, cfg, allow_master_override=False)
    except GuardrailError as exc:
        return _json({"error": str(exc), "blocked": True})

    return _json(
        {
            "mode": "stub",
            "reference_path": str(ref),
            "prompt": prompt,
            "version_folder": version_folder,
            "strength": strength,
            "dry_run": dry_run,
            "note": "Phase 0 stub — implement Fal img2img in Phase 1.",
        }
    )


@mcp.tool()
def render_video(
    prompt: str,
    version_folder: str = "v8",
    duration_seconds: int = 5,
    dry_run: bool = True,
) -> str:
    """Generate a short background video clip (stub in Phase 0)."""
    return _json(
        {
            "mode": "stub",
            "prompt": prompt,
            "version_folder": version_folder,
            "duration_seconds": duration_seconds,
            "dry_run": dry_run,
            "planned_output": f"{load_config().backgrounds_path / version_folder / 'hero.mp4'}",
            "note": "Phase 0 stub — Fal video model TBD.",
        }
    )


@mcp.tool()
def publish_ha_assets(
    version_folder: str,
    dry_run: bool = True,
    run_deploy: bool = False,
) -> str:
    """Update Lovelace cache-bust and document deploy_to_ha.py integration."""
    cfg = load_config()
    try:
        assert_version_folder_exists_for_publish(cfg.backgrounds_path, version_folder)
    except GuardrailError as exc:
        return _json({"error": str(exc), "blocked": True})

    cache_result = update_lovelace_cache_bust(cfg, version_folder=version_folder, dry_run=dry_run)

    if dry_run:
        log.info("publish_ha_assets dry_run: would update cache-bust to %s", cache_result["cache_bust"])
    else:
        log.info("publish_ha_assets updated Lovelace YAML cache-bust=%s", cache_result["cache_bust"])

    payload: dict[str, Any] = {
        "version_folder": version_folder,
        "dry_run": dry_run,
        "cache_bust_update": cache_result,
        "deploy": deploy_documentation(cfg),
        "ha_host": cfg.ha_host,
        "ha_url": cfg.ha_url,
    }
    if run_deploy and not dry_run:
        payload["deploy_note"] = (
            "run_deploy not executed automatically in Phase 0 — invoke deploy script manually."
        )
    elif dry_run:
        payload["deploy_note"] = "Set dry_run=false to write cache-bust tokens into Lovelace YAML."

    return _json(payload)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from pathlib import Path

from media_render_mcp.config import MediaRenderConfig
from media_render_mcp.guardrails import assert_version_folder_new_or_empty
from media_render_mcp.paths import REPO_ROOT


def render_live_enabled() -> bool:
    return os.environ.get("RENDER_LIVE", "").strip() in ("1", "true", "yes")


def plan_render_image(
    cfg: MediaRenderConfig,
    *,
    prompt: str,
    width: int,
    height: int,
    version_folder: str,
    variant: str = "clear",
) -> dict:
    backgrounds = cfg.backgrounds_path
    assert_version_folder_new_or_empty(backgrounds, version_folder, variant)
    out = backgrounds / version_folder / f"{variant}.jpg"
    return {
        "mode": "dry_run",
        "prompt": prompt,
        "width": width,
        "height": height,
        "version_folder": version_folder,
        "variant": variant,
        "output_path": str(out),
        "repo_relative": str(out.relative_to(REPO_ROOT)),
        "backend": cfg.render_backend,
        "model": cfg.fal_image_model,
    }


def render_image_live(
    cfg: MediaRenderConfig,
    *,
    prompt: str,
    width: int,
    height: int,
    version_folder: str,
    variant: str = "clear",
) -> dict:
    plan = plan_render_image(
        cfg,
        prompt=prompt,
        width=width,
        height=height,
        version_folder=version_folder,
        variant=variant,
    )
    if not os.environ.get("FAL_KEY"):
        return {**plan, "error": "FAL_KEY not set", "mode": "aborted"}

    try:
        import fal_client
    except ImportError as exc:
        return {**plan, "error": f"fal_client not installed: {exc}", "mode": "aborted"}

    result = fal_client.subscribe(
        cfg.fal_image_model,
        arguments={
            "prompt": prompt,
            "image_size": {"width": width, "height": height},
        },
    )
    images = result.get("images") or []
    if not images:
        return {**plan, "error": "Fal returned no images", "mode": "failed", "raw": result}

    image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
    if not image_url:
        return {**plan, "error": "No image URL in Fal response", "mode": "failed", "raw": result}

    import httpx

    out = Path(plan["output_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(image_url)
        resp.raise_for_status()
        out.write_bytes(resp.content)

    return {
        **plan,
        "mode": "live",
        "written": True,
        "bytes": out.stat().st_size,
        "fal_image_url": image_url,
    }

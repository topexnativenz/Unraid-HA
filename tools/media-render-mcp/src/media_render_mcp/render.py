from __future__ import annotations

import os
from pathlib import Path

from media_render_mcp.config import MediaRenderConfig
from media_render_mcp.guardrails import assert_version_folder_new_or_empty
from media_render_mcp.paths import REPO_ROOT, resolve_repo_path

# fal-ai/flux-pro/v1/depth is deprecated; kontext fits reference-based archviz refinement.
DEFAULT_IMG2IMG_MODEL = "fal-ai/flux-pro/kontext"


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


def _is_remote_reference(reference: str) -> bool:
    ref = reference.strip()
    return ref.startswith(("http://", "https://", "data:"))


def resolve_reference_location(reference: str) -> Path | None:
    """Resolve a local reference path; return None for remote URLs."""
    ref = reference.strip()
    if _is_remote_reference(ref):
        return None
    path = Path(ref).expanduser()
    if path.is_absolute():
        return path.resolve()
    return resolve_repo_path(ref)


def resolve_output_path(
    cfg: MediaRenderConfig,
    *,
    output_path: str | None,
    version_folder: str,
) -> Path:
    if output_path:
        path = Path(output_path).expanduser()
        if path.is_absolute():
            return path.resolve()
        return resolve_repo_path(output_path)
    return cfg.backgrounds_path / version_folder / "img2img-reference.png"


def strength_to_guidance_scale(strength: float) -> float:
    """Map img2img strength (0–1) to Kontext guidance_scale (~2–7)."""
    clamped = max(0.0, min(1.0, strength))
    return round(2.0 + clamped * 5.0, 2)


def plan_img2img_with_reference(
    cfg: MediaRenderConfig,
    *,
    reference_path: str,
    prompt: str,
    version_folder: str = "v8",
    strength: float = 0.65,
    output_path: str | None = None,
) -> dict:
    ref_loc = resolve_reference_location(reference_path)
    out = resolve_output_path(cfg, output_path=output_path, version_folder=version_folder)
    model = cfg.fal_img2img_model or DEFAULT_IMG2IMG_MODEL
    return {
        "mode": "dry_run",
        "reference_path": str(ref_loc) if ref_loc else reference_path.strip(),
        "reference_kind": "url" if ref_loc is None else "file",
        "prompt": prompt,
        "version_folder": version_folder,
        "strength": strength,
        "guidance_scale": strength_to_guidance_scale(strength),
        "output_path": str(out),
        "backend": cfg.render_backend,
        "model": model,
    }


def _reference_image_url(reference_path: str) -> tuple[str, str]:
    ref = reference_path.strip()
    if _is_remote_reference(ref):
        return ref, ref
    ref_loc = resolve_reference_location(ref)
    if ref_loc is None or not ref_loc.is_file():
        raise FileNotFoundError(f"Reference image not found: {reference_path}")

    try:
        import fal_client
    except ImportError as exc:
        raise RuntimeError(f"fal_client not installed: {exc}") from exc

    try:
        image_url = fal_client.upload_file(ref_loc)
    except Exception:
        # Fal CDN upload can 403 on some keys; data URIs are accepted by Kontext.
        image_url = fal_client.encode_file(ref_loc)

    return str(ref_loc), image_url


def _download_fal_image(image_url: str, out: Path) -> int:
    import httpx

    out.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(image_url)
        resp.raise_for_status()
        out.write_bytes(resp.content)
    return out.stat().st_size


def img2img_with_reference_live(
    cfg: MediaRenderConfig,
    *,
    reference_path: str,
    prompt: str,
    version_folder: str = "v8",
    strength: float = 0.65,
    output_path: str | None = None,
) -> dict:
    plan = plan_img2img_with_reference(
        cfg,
        reference_path=reference_path,
        prompt=prompt,
        version_folder=version_folder,
        strength=strength,
        output_path=output_path,
    )
    if not os.environ.get("FAL_KEY"):
        return {**plan, "error": "FAL_KEY not set", "mode": "aborted"}

    try:
        import fal_client
    except ImportError as exc:
        return {**plan, "error": f"fal_client not installed: {exc}", "mode": "aborted"}

    try:
        ref_label, image_url = _reference_image_url(reference_path)
    except (FileNotFoundError, RuntimeError) as exc:
        return {**plan, "error": str(exc), "mode": "aborted"}

    model = plan["model"]
    out = Path(plan["output_path"])
    suffix = out.suffix.lower()
    output_format = "png" if suffix == ".png" else "jpeg"

    arguments: dict = {
        "prompt": prompt,
        "image_url": image_url,
        "guidance_scale": plan["guidance_scale"],
        "num_images": 1,
        "output_format": output_format,
    }

    try:
        result = fal_client.subscribe(model, arguments=arguments)
    except Exception as exc:
        return {**plan, "error": str(exc), "mode": "failed"}

    images = result.get("images") or []
    if not images:
        return {**plan, "error": "Fal returned no images", "mode": "failed", "raw": result}

    fal_image = images[0]
    fal_image_url = fal_image.get("url") if isinstance(fal_image, dict) else fal_image
    if not fal_image_url:
        return {**plan, "error": "No image URL in Fal response", "mode": "failed", "raw": result}

    try:
        nbytes = _download_fal_image(fal_image_url, out)
    except Exception as exc:
        return {
            **plan,
            "error": f"Failed to download Fal image: {exc}",
            "mode": "failed",
            "fal_image_url": fal_image_url,
        }

    repo_relative: str | None = None
    try:
        repo_relative = str(out.relative_to(REPO_ROOT))
    except ValueError:
        pass

    return {
        **plan,
        "mode": "live",
        "written": True,
        "bytes": nbytes,
        "reference_resolved": ref_label,
        "fal_image_url": fal_image_url,
        "repo_relative": repo_relative,
    }

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import trimesh

from ai_3d_agent_mcp.config import AgentConfig
from ai_3d_agent_mcp.dimensions import TargetDimensions
from ai_3d_agent_mcp.parametric import build_parametric, classify_route


def _placeholder_organic(target: TargetDimensions) -> trimesh.Trimesh:
    """Deterministic organic-ish blob for stub backend / offline demos."""
    # Icosahedron scaled to target — stands in for self-hosted AI mesh
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    extents = np.asarray(mesh.extents, dtype=float)
    desired = np.array([target.width_mm, target.depth_mm, target.height_mm], dtype=float)
    mesh.apply_scale(desired / extents)
    return mesh


def generate_stub(
    *,
    target: TargetDimensions,
    prompt: str,
    category: str,
    image_paths: list[Path],
    out_stl: Path,
) -> dict[str, Any]:
    route = classify_route(category, prompt, has_images=bool(image_paths))
    # Keep parametric hooks/signs even with reference photos (dims win); else AI mesh
    if image_paths and route not in {"parametric_hook", "parametric_sign"}:
        route = "ai_mesh"

    if route.startswith("parametric"):
        mesh, info = build_parametric(route, target, prompt=prompt)
    else:
        mesh = _placeholder_organic(target)
        info = {
            "route": "ai_mesh",
            "engine": "stub",
            "dimensional": False,
            "note": (
                "Stub organic mesh. Point generation_backend at Unraid HTTP (TRELLIS/Hunyuan) "
                "or switch to meshy/tripo when self-hosted accuracy is insufficient."
            ),
        }

    out_stl.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out_stl, file_type="stl")
    return {
        **info,
        "stl_path": str(out_stl),
        "image_count": len(image_paths),
        "prompt": prompt,
    }


def generate_http(
    cfg: AgentConfig,
    *,
    target: TargetDimensions,
    prompt: str,
    category: str,
    image_paths: list[Path],
    out_stl: Path,
) -> dict[str, Any]:
    """
    Call a self-hosted generator on Unraid.

    Expected JSON API:
      POST {generation_http_url}
      body: {
        prompt, category, width_mm, depth_mm, height_mm,
        images: [{name, b64}], output_format: "stl"
      }
      response: { stl_b64: "..." } OR { download_url: "..." } OR raw STL bytes (application/sla)
    """
    route = classify_route(category, prompt, has_images=bool(image_paths))
    if not image_paths and route.startswith("parametric"):
        mesh, info = build_parametric(route, target, prompt=prompt)
        out_stl.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(out_stl, file_type="stl")
        return {**info, "stl_path": str(out_stl), "via": "parametric_local"}

    images_payload = []
    for path in image_paths:
        images_payload.append(
            {"name": path.name, "b64": base64.b64encode(path.read_bytes()).decode("ascii")}
        )

    payload = {
        "prompt": prompt,
        "category": category,
        "width_mm": target.width_mm,
        "depth_mm": target.depth_mm,
        "height_mm": target.height_mm,
        "images": images_payload,
        "output_format": "stl",
    }
    with httpx.Client(timeout=600.0) as client:
        resp = client.post(cfg.generation_http_url, json=payload)
        content_type = resp.headers.get("content-type", "")
        if resp.status_code >= 400:
            raise RuntimeError(f"Generation HTTP {resp.status_code}: {resp.text[:500]}")
        out_stl.parent.mkdir(parents=True, exist_ok=True)
        if "application/json" in content_type or resp.text.lstrip().startswith("{"):
            data = resp.json()
            if data.get("stl_b64"):
                out_stl.write_bytes(base64.b64decode(data["stl_b64"]))
            elif data.get("download_url"):
                file_resp = client.get(data["download_url"])
                file_resp.raise_for_status()
                out_stl.write_bytes(file_resp.content)
            else:
                raise RuntimeError(f"HTTP generator JSON missing stl_b64/download_url: {data!r}")
        else:
            out_stl.write_bytes(resp.content)

    return {
        "route": "ai_mesh",
        "engine": "http",
        "dimensional": False,
        "url": cfg.generation_http_url,
        "stl_path": str(out_stl),
        "image_count": len(image_paths),
        "note": "Self-hosted HTTP generator. Mesh will be scaled to requested dimensions next.",
    }


def generate_meshy_placeholder(cfg: AgentConfig) -> dict[str, Any]:
    return {
        "error": "meshy backend not enabled in v1 (self-hosted first)",
        "hint": (
            f"Set generation_backend=http for Unraid, or later wire {cfg.meshy_api_key_env}. "
            "Use stub for offline pipeline tests."
        ),
        "blocked": True,
    }


def copy_images_into_job(image_paths: list[str], job_dir: Path) -> list[Path]:
    dest_dir = job_dir / "inputs"
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for i, raw in enumerate(image_paths):
        src = Path(raw).expanduser().resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Image not found: {raw}")
        dest = dest_dir / f"{i:02d}_{src.name}"
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied


def run_generation(
    cfg: AgentConfig,
    *,
    target: TargetDimensions,
    prompt: str,
    category: str,
    image_paths: list[str],
    job_dir: Path,
) -> dict[str, Any]:
    images = copy_images_into_job(image_paths, job_dir) if image_paths else []
    out_stl = job_dir / "raw" / "model.stl"
    backend = (cfg.generation_backend or "stub").lower()

    # Functional parametric short-circuit even on http/meshy when no photos and route parametric
    route = classify_route(category, prompt, has_images=bool(images))
    if not images and route.startswith("parametric"):
        mesh, info = build_parametric(route, target, prompt=prompt)
        out_stl.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(out_stl, file_type="stl")
        return {**info, "stl_path": str(out_stl), "backend": backend}

    if backend == "stub":
        result = generate_stub(
            target=target,
            prompt=prompt,
            category=category,
            image_paths=images,
            out_stl=out_stl,
        )
    elif backend == "http":
        result = generate_http(
            cfg,
            target=target,
            prompt=prompt,
            category=category,
            image_paths=images,
            out_stl=out_stl,
        )
    elif backend in {"meshy", "tripo"}:
        return generate_meshy_placeholder(cfg)
    else:
        raise ValueError(f"Unknown generation_backend: {backend}")

    result["backend"] = backend
    # Persist generation meta
    (job_dir / "raw").mkdir(parents=True, exist_ok=True)
    (job_dir / "raw" / "generation.json").write_text(json.dumps(result, indent=2))
    return result

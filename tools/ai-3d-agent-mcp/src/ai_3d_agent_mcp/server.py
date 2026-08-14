from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ai_3d_agent_mcp.ams import suggest_ams_from_images
from ai_3d_agent_mcp.config import load_config
from ai_3d_agent_mcp.dimensions import missing_dimensions_prompt, parse_dimensions
from ai_3d_agent_mcp.generate import run_generation
from ai_3d_agent_mcp.guardrails import CATEGORIES, MATERIALS, GuardrailError
from ai_3d_agent_mcp.handoff import handoff
from ai_3d_agent_mcp.history import JobHistory
from ai_3d_agent_mcp.package_3mf import package_job
from ai_3d_agent_mcp.simple_flow import (
    dims_complete,
    infer_category,
    looks_like_print_request,
    user_facing_dimension_question,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ai-3d-agent-mcp")

mcp = FastMCP(
    "ai-3d-bambu-agent",
    instructions=(
        "SIMPLE 3D PRINT FLOW for Bambu X1 Carbon. End users only do one of two things: "
        "(1) describe what they want in plain text, or (2) upload a photo with optional caption. "
        "When you detect a print request, call simple_print_request. "
        "If it returns needs_dimensions, ask the user ONLY the ask_user question — nothing else. "
        "When they give sizes, call simple_print_request again with width_mm/depth_mm/height_mm. "
        "Then tell them the model is ready in Bambu Studio / iOS and they must confirm before printing. "
        "NEVER auto-start a print. Defaults: PLA, 0.20mm Standard. Do not quiz them about AMS/supports."
    ),
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2)


def _history() -> JobHistory:
    cfg = load_config()
    return JobHistory(cfg.history_db_path, cfg.workspace_path)


@mcp.tool()
def agent_info() -> str:
    """Show config, printers, materials, backends, and policy (no auto-print)."""
    cfg = load_config()
    return _json(
        {
            "version": "0.2.0",
            "simple_entry_tool": "simple_print_request",
            "end_user_paths": [
                "Plain text description → ask size only → build → open Bambu Studio",
                "Upload photo (+ optional caption) → ask size only → build → open Bambu / iOS",
            ],
            "generation_backend": cfg.generation_backend,
            "generation_http_url": cfg.generation_http_url,
            "gpu_note": (
                "No GPU assumed. Text hooks/signs/brackets use parametric CAD (accurate, no GPU). "
                "Photo/figurine mesh uses stub until you add a GPU host or paid Meshy/Tripo."
            ),
            "workspace": str(cfg.workspace_path),
            "default_printer": cfg.default_printer,
            "printers": cfg.printers,
            "materials": cfg.materials,
            "default_material": cfg.default_material,
            "process_default": "0.20mm Standard",
            "macos_display_name": cfg.macos_display_name,
            "macos_hostname": cfg.macos_hostname,
            "macos_jobs_mount": cfg.macos_jobs_mount,
            "allow_auto_print": cfg.allow_auto_print,
            "warn_only_mesh_checks": cfg.warn_only_mesh_checks,
            "categories": list(CATEGORIES),
            "handoff_targets": ["macos_studio", "ios_bambu", "file_only"],
            "policy": [
                "Ask ONLY for approximate dimensions",
                "Warn and continue on mesh issues",
                "Auto flat base for figurines",
                "No auto-print — user confirms in Bambu UI",
            ],
        }
    )


@mcp.tool()
def detect_print_intent(text: str = "", has_images: bool = False) -> str:
    """
    Check whether a user message looks like a 3D-print request.
    If is_print_request=true, immediately call simple_print_request.
    """
    matched = looks_like_print_request(text, has_images=has_images)
    return _json(
        {
            "is_print_request": matched,
            "next": "simple_print_request" if matched else None,
            "agent_instruction": (
                "Call simple_print_request now with the user description and any image paths."
                if matched
                else "Not a print request — continue the normal conversation."
            ),
        }
    )


@mcp.tool()
def simple_print_request(
    description: str = "",
    image_paths: list[str] | None = None,
    width_mm: float | None = None,
    depth_mm: float | None = None,
    height_mm: float | None = None,
    material: str = "",
    printer: str = "",
    handoff_target: str = "",
    open_now: bool = True,
) -> str:
    """
    PRIMARY end-user tool. Two inputs only:
      1) description (plain text), and/or
      2) image_paths (photo upload) with optional description.

    If sizes are missing → returns ask_user (dimension question ONLY).
    If sizes are present → builds model, packages 3MF, hands off to Bambu Studio/iOS.
    Never starts the printer.
    """
    cfg = load_config()
    images = list(image_paths or [])
    desc = (description or "").strip()
    if not desc and not images:
        return _json(
            {
                "status": "needs_input",
                "ask_user": "What would you like to 3D print? Describe it, or drop a photo.",
                "ask_user_only": True,
            }
        )

    category = infer_category(desc, has_images=bool(images))
    if not dims_complete(width_mm, depth_mm, height_mm):
        return _json(user_facing_dimension_question(category, desc, bool(images)))

    material = (material or cfg.default_material).upper()
    if material not in MATERIALS:
        material = cfg.default_material
    printer = printer or cfg.default_printer
    if printer not in cfg.printers:
        printer = cfg.default_printer
    target = (handoff_target or cfg.default_handoff_target or "macos_studio").lower()
    if target not in {"macos_studio", "ios_bambu", "file_only"}:
        target = "macos_studio"

    # create → generate → package → handoff
    created = json.loads(
        create_job(
            prompt=desc or "photo reference",
            width_mm=float(width_mm),  # type: ignore[arg-type]
            depth_mm=float(depth_mm),  # type: ignore[arg-type]
            height_mm=float(height_mm),  # type: ignore[arg-type]
            category=category,
            material=material,
            printer=printer,
            image_paths=images,
        )
    )
    if created.get("blocked"):
        return _json(created)

    job_id = created["job_id"]
    built = json.loads(generate_and_package(job_id))
    if built.get("blocked") or built.get("error"):
        return _json({"job_id": job_id, **built})

    # open_now → dry_run=false when SSH/local open is configured; else still stage files
    dry_run = not open_now
    hand = json.loads(
        handoff_to_bambu(
            job_id,
            target=target,
            dry_run=dry_run,
            confirm_send_to_printer=False,
        )
    )

    pkg = built.get("package") or {}
    warnings = list(pkg.get("mesh_report", {}).get("warnings") or [])
    three_mf = pkg.get("three_mf") or hand.get("three_mf")
    user_summary = (
        f"Ready for Bambu. Opened/staged: {three_mf}. "
        f"Confirm slice & print yourself in Bambu Studio on {cfg.macos_display_name} "
        f"(or iOS Bambu app). Nothing was sent to the printer automatically."
    )
    if target == "ios_bambu":
        user_summary = (
            f"Ready on iOS share. File: {hand.get('ios_path') or three_mf}. "
            f"URL: {hand.get('ios_url') or '(set ios_share_base_url)'}. "
            "Open in Bambu app and confirm before printing."
        )

    return _json(
        {
            "status": "ready_for_bambu",
            "job_id": job_id,
            "category": category,
            "material": material,
            "printer": printer,
            "dimensions": {
                "width_mm": width_mm,
                "depth_mm": depth_mm,
                "height_mm": height_mm,
            },
            "three_mf": three_mf,
            "handoff": hand,
            "warnings": warnings,
            "tell_user": user_summary,
            "agent_instruction": (
                "Tell the user the model is ready using tell_user. "
                "Mention they must confirm in Bambu before printing. "
                "Only mention warnings if they affect fit/strength. Keep it short."
            ),
        }
    )


@mcp.tool()
def dimension_prompt(category: str = "other") -> str:
    """Low-level dimension questionnaire (prefer simple_print_request for normal chat)."""
    if category not in CATEGORIES:
        category = "other"
    return _json(missing_dimensions_prompt(category))


@mcp.tool()
def create_job(
    prompt: str,
    width_mm: float,
    depth_mm: float,
    height_mm: float,
    category: str = "other",
    material: str = "PLA",
    printer: str = "",
    scale_mode: str = "fit_bbox",
    image_paths: list[str] | None = None,
) -> str:
    """
    Create a tracked job. Dimensions are REQUIRED (mm).
    category: figurine | hook | sign | functional | other
    Optional image_paths for single or multi-angle photos.
    """
    cfg = load_config()
    if category not in CATEGORIES:
        return _json({"error": f"category must be one of {CATEGORIES}", "blocked": True})
    material = (material or cfg.default_material).upper()
    if material not in MATERIALS:
        return _json({"error": f"material must be one of {MATERIALS}", "blocked": True})
    printer = printer or cfg.default_printer
    if printer not in cfg.printers:
        return _json({"error": f"printer must be one of {list(cfg.printers)}", "blocked": True})

    try:
        dims = parse_dimensions(width_mm, depth_mm, height_mm, scale_mode=scale_mode)
    except ValueError as exc:
        return _json({"error": str(exc), "blocked": True, **missing_dimensions_prompt(category)})

    bed_ok, bed_msg = dims.fits_bed(cfg.printer_profile(printer).bed_mm)
    hist = _history()
    record = hist.create_job(
        category=category,
        prompt=prompt,
        material=material,
        printer=printer,
        width_mm=dims.width_mm,
        depth_mm=dims.depth_mm,
        height_mm=dims.height_mm,
        scale_mode=dims.scale_mode,
        image_paths=list(image_paths or []),
        meta={"bed_fit_ok": bed_ok, "bed_fit_msg": bed_msg},
    )
    warnings = [] if bed_ok else [f"BED FIT WARNING: {bed_msg}"]
    if warnings:
        hist.update(record.job_id, append_warnings=warnings)

    return _json(
        {
            **record.as_dict(),
            "bed_fit_ok": bed_ok,
            "bed_fit_msg": bed_msg,
            "next": "Call generate_and_package(job_id) or generate_model + package_for_bambu.",
        }
    )


@mcp.tool()
def generate_model(job_id: str) -> str:
    """Run generation for an existing job (parametric or AI stub/HTTP). Writes raw STL."""
    cfg = load_config()
    hist = _history()
    try:
        job = hist.require(job_id)
    except KeyError as exc:
        return _json({"error": str(exc), "blocked": True})

    dims = parse_dimensions(job.width_mm, job.depth_mm, job.height_mm, job.scale_mode)
    job_dir = hist.job_dir(job_id)
    try:
        result = run_generation(
            cfg,
            target=dims,
            prompt=job.prompt,
            category=job.category,
            image_paths=job.image_paths,
            job_dir=job_dir,
        )
    except Exception as exc:
        hist.update(job_id, status="generate_failed", append_warnings=[str(exc)])
        return _json({"error": str(exc), "job_id": job_id, "blocked": True})

    if result.get("blocked"):
        return _json(result)

    hist.update(
        job_id,
        status="generated",
        artifacts={"raw_stl": result.get("stl_path", "")},
        meta={"generation": result},
    )
    return _json({"job_id": job_id, **result})


@mcp.tool()
def package_for_bambu(job_id: str, add_flat_base: bool | None = None) -> str:
    """
    Repair/scale mesh, optional figurine flat base, AMS colour suggestions, export STL+3MF.
    Warns on mesh issues but continues (warn_only policy).
    """
    cfg = load_config()
    hist = _history()
    try:
        job = hist.require(job_id)
    except KeyError as exc:
        return _json({"error": str(exc), "blocked": True})

    raw = Path(job.artifacts.get("raw_stl") or hist.job_dir(job_id) / "raw" / "model.stl")
    if not raw.is_file():
        return _json({"error": "raw STL missing — run generate_model first", "blocked": True})

    dims = parse_dimensions(job.width_mm, job.depth_mm, job.height_mm, job.scale_mode)
    try:
        packaged = package_job(
            cfg,
            job_dir=hist.job_dir(job_id),
            raw_stl=raw,
            target=dims,
            category=job.category,
            material=job.material,
            printer_name=job.printer,
            image_paths=job.image_paths,
            add_flat_base=add_flat_base,
        )
    except Exception as exc:
        hist.update(job_id, status="package_failed", append_warnings=[str(exc)])
        return _json({"error": str(exc), "blocked": True})

    warnings = list(packaged.get("mesh_report", {}).get("warnings") or [])
    hist.update(
        job_id,
        status="packaged",
        append_warnings=warnings,
        artifacts={
            "stl": packaged["stl"],
            "three_mf": packaged["three_mf"],
            "manifest": packaged["manifest"],
            "checklist": packaged["checklist"],
        },
        meta={"ams": packaged.get("ams"), "mesh_report": packaged.get("mesh_report")},
    )
    return _json({"job_id": job_id, **packaged})


@mcp.tool()
def generate_and_package(job_id: str, add_flat_base: bool | None = None) -> str:
    """Convenience: generate_model then package_for_bambu."""
    gen = json.loads(generate_model(job_id))
    if gen.get("blocked") or gen.get("error"):
        return _json(gen)
    pkg = json.loads(package_for_bambu(job_id, add_flat_base=add_flat_base))
    return _json({"job_id": job_id, "generation": gen, "package": pkg})


@mcp.tool()
def handoff_to_bambu(
    job_id: str,
    target: str = "macos_studio",
    dry_run: bool = True,
    confirm_send_to_printer: bool = False,
) -> str:
    """
    Hand off packaged 3MF to macOS Bambu Studio or stage for iOS Bambu app.
    confirm_send_to_printer must stay false — auto-print is blocked by policy.
    """
    cfg = load_config()
    hist = _history()
    try:
        job = hist.require(job_id)
    except KeyError as exc:
        return _json({"error": str(exc), "blocked": True})

    three_mf = Path(job.artifacts.get("three_mf") or "")
    if not three_mf.is_file():
        return _json({"error": "3MF missing — run package_for_bambu first", "blocked": True})

    try:
        result = handoff(
            cfg,
            job_id=job_id,
            three_mf=three_mf,
            target=target,
            confirm_send_to_printer=confirm_send_to_printer,
            dry_run=dry_run,
        )
    except GuardrailError as exc:
        return _json({"error": str(exc), "blocked": True, "auto_print": False})
    except Exception as exc:
        return _json({"error": str(exc), "blocked": True})

    hist.update(job_id, status=f"handoff_{result.get('status', 'done')}", meta={"handoff": result})
    return _json(result)


@mcp.tool()
def suggest_ams_colors(image_paths: list[str], max_slots: int = 4) -> str:
    """Suggest AMS filament colour slots from one or more reference images."""
    return _json(suggest_ams_from_images(image_paths, max_slots=max_slots))


@mcp.tool()
def list_jobs(limit: int = 20) -> str:
    """List recent jobs (newest first)."""
    hist = _history()
    jobs = [j.as_dict() for j in hist.list_jobs(limit=limit)]
    return _json({"count": len(jobs), "jobs": jobs})


@mcp.tool()
def get_job(job_id: str) -> str:
    """Fetch full job history record + on-disk job.json path."""
    hist = _history()
    try:
        job = hist.require(job_id)
    except KeyError as exc:
        return _json({"error": str(exc), "blocked": True})
    return _json(
        {
            **job.as_dict(),
            "job_dir": str(hist.job_dir(job_id)),
            "sidecar": str(hist.job_dir(job_id) / "job.json"),
        }
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

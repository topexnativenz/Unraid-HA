from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import trimesh

from ai_3d_agent_mcp.config import AgentConfig, PrinterProfile
from ai_3d_agent_mcp.mesh_ops import export_3mf, export_stl, load_mesh, process_pipeline
from ai_3d_agent_mcp.dimensions import TargetDimensions
from ai_3d_agent_mcp.ams import suggest_ams_from_images


def package_job(
    cfg: AgentConfig,
    *,
    job_dir: Path,
    raw_stl: Path,
    target: TargetDimensions,
    category: str,
    material: str,
    printer_name: str,
    image_paths: list[str],
    add_flat_base: bool | None = None,
) -> dict[str, Any]:
    printer = cfg.printer_profile(printer_name)
    if add_flat_base is None:
        add_flat_base = category in cfg.auto_flat_base_categories

    mesh = load_mesh(raw_stl)
    mesh, report = process_pipeline(
        mesh,
        target,
        add_base=bool(add_flat_base),
        base_height_mm=cfg.flat_base_height_mm,
    )

    out_dir = job_dir / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    stl_path = export_stl(mesh, out_dir / "model.stl")
    three_mf_path = export_3mf(mesh, out_dir / "model.3mf")

    ams = suggest_ams_from_images(image_paths)
    bed_ok, bed_msg = target.fits_bed(printer.bed_mm)
    if not bed_ok:
        report.warnings.append(f"BED FIT WARNING: {bed_msg}")
    else:
        report.warnings.append(f"Bed fit OK: {bed_msg}")

    manifest = {
        "printer": printer_name,
        "printer_model": printer.model,
        "process": printer.process,
        "nozzle_mm": printer.nozzle_mm,
        "material": material,
        "category": category,
        "add_flat_base": bool(add_flat_base),
        "dimensions_requested": target.as_dict(),
        "mesh_report": report.as_dict(),
        "ams": ams,
        "files": {
            "stl": str(stl_path),
            "three_mf": str(three_mf_path),
        },
        "bambu_notes": [
            "Open model.3mf in Bambu Studio (macOS) or share to iOS Bambu app via Files.",
            "Confirm process profile: 0.20mm Standard unless overridden.",
            "Assign AMS slots from ams suggestions, then slice.",
            "Do not start print until you explicitly confirm in Bambu Studio / Bambu Handy.",
        ],
        "allow_auto_print": cfg.allow_auto_print,
    }
    manifest_path = out_dir / "bambu_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Human-readable slice checklist
    checklist = out_dir / "SLICE_CHECKLIST.md"
    checklist.write_text(
        "\n".join(
            [
                "# Bambu slice checklist",
                "",
                f"- Printer: **{printer_name}** ({printer.model})",
                f"- Process: **{printer.process}**",
                f"- Material: **{material}**",
                f"- Requested size: {target.width_mm}×{target.depth_mm}×{target.height_mm} mm",
                f"- Flat base: {'yes' if add_flat_base else 'no'}",
                "",
                "## AMS suggestions",
                *[
                    f"- Slot {s['slot']}: {s['color']} ({s.get('role', '')})"
                    for s in ams.get("slots", [])
                ],
                "",
                "## Warnings",
                *([f"- {w}" for w in report.warnings] or ["- none"]),
                "",
                "## Open",
                f"- macOS Studio: `{three_mf_path}`",
                "- iOS: use handoff_to_bambu with target=ios_bambu",
                "- **Never auto-print** — confirm in the Bambu UI.",
                "",
            ]
        )
    )

    return {
        "stl": str(stl_path),
        "three_mf": str(three_mf_path),
        "manifest": str(manifest_path),
        "checklist": str(checklist),
        "mesh_report": report.as_dict(),
        "ams": ams,
        "printer": _printer_dict(printer_name, printer),
        "warn_only": cfg.warn_only_mesh_checks,
        "blocked": False,
    }


def _printer_dict(name: str, printer: PrinterProfile) -> dict[str, Any]:
    return {
        "name": name,
        "model": printer.model,
        "bed_mm": printer.bed_mm,
        "process": printer.process,
        "ams": printer.ams,
    }


def stage_ios_share(cfg: AgentConfig, job_id: str, three_mf: Path) -> dict[str, Any]:
    share_dir = cfg.ios_share_path / job_id
    share_dir.mkdir(parents=True, exist_ok=True)
    dest = share_dir / three_mf.name
    shutil.copy2(three_mf, dest)
    url = ""
    if cfg.ios_share_base_url:
        url = cfg.ios_share_base_url.rstrip("/") + f"/{job_id}/{three_mf.name}"
    return {
        "ios_path": str(dest),
        "ios_url": url,
        "instructions": [
            "On iPhone: open the share URL (or NAS Files bookmark) and download the .3mf.",
            "Share → Open in Bambu / Bambu Handy.",
            "Select printer via Bambu cloud, slice or send project, confirm before printing.",
        ],
    }

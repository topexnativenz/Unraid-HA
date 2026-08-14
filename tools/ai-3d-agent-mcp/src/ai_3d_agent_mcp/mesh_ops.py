from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from ai_3d_agent_mcp.dimensions import TargetDimensions


@dataclass
class MeshReport:
    watertight: bool
    volume: float | None
    bounds_mm: list[list[float]]
    extents_mm: list[float]
    face_count: int
    vertex_count: int
    warnings: list[str] = field(default_factory=list)
    scale_factor: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "watertight": self.watertight,
            "volume": self.volume,
            "bounds_mm": self.bounds_mm,
            "extents_mm": self.extents_mm,
            "face_count": self.face_count,
            "vertex_count": self.vertex_count,
            "warnings": self.warnings,
            "scale_factor": self.scale_factor,
        }


def load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        geoms = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not geoms:
            raise ValueError(f"No mesh geometry in {path}")
        loaded = trimesh.util.concatenate(geoms)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"Unsupported mesh type from {path}: {type(loaded)}")
    return loaded


def inspect_mesh(mesh: trimesh.Trimesh) -> MeshReport:
    warnings: list[str] = []
    try:
        watertight = bool(mesh.is_watertight)
    except Exception:
        watertight = False
        warnings.append("watertight check failed")
    if not watertight:
        warnings.append("mesh is not watertight — slicer may still accept after repair")

    volume: float | None
    try:
        volume = float(mesh.volume) if watertight else None
    except Exception:
        volume = None

    if mesh.faces is None or len(mesh.faces) == 0:
        warnings.append("mesh has no faces")
    if len(mesh.faces) > 1_500_000:
        warnings.append(f"very high face count ({len(mesh.faces)}); remesh recommended")

    # Thin feature heuristic: smallest extent under 0.8 mm
    extents = [float(x) for x in mesh.extents]
    if min(extents) < 0.8:
        warnings.append(f"thin dimension {min(extents):.2f} mm may be below reliable wall thickness")

    bounds = mesh.bounds.tolist()
    return MeshReport(
        watertight=watertight,
        volume=volume,
        bounds_mm=bounds,
        extents_mm=extents,
        face_count=int(len(mesh.faces)),
        vertex_count=int(len(mesh.vertices)),
        warnings=warnings,
    )


def repair_mesh(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, list[str]]:
    warnings: list[str] = []
    mesh = mesh.copy()
    try:
        mesh.remove_duplicate_faces()
    except Exception:
        warnings.append("remove_duplicate_faces skipped")
    try:
        mesh.remove_unreferenced_vertices()
    except Exception:
        warnings.append("remove_unreferenced_vertices skipped")
    try:
        mesh.fill_holes()
    except Exception:
        warnings.append("fill_holes failed or incomplete")
    try:
        trimesh.repair.fix_normals(mesh)
    except Exception:
        warnings.append("fix_normals failed")
    try:
        trimesh.repair.fix_winding(mesh)
    except Exception:
        warnings.append("fix_winding failed")
    return mesh, warnings


def center_on_bed(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mesh = mesh.copy()
    bounds = mesh.bounds
    center_xy = (bounds[0, :2] + bounds[1, :2]) / 2.0
    mesh.apply_translation([-center_xy[0], -center_xy[1], -bounds[0, 2]])
    return mesh


def scale_to_dimensions(mesh: trimesh.Trimesh, target: TargetDimensions) -> tuple[trimesh.Trimesh, float]:
    mesh = mesh.copy()
    extents = np.asarray(mesh.extents, dtype=float)
    if np.any(extents <= 0):
        raise ValueError("Cannot scale mesh with zero extent")

    desired = np.array([target.width_mm, target.depth_mm, target.height_mm], dtype=float)

    if target.scale_mode == "match_height":
        factor = desired[2] / extents[2]
    elif target.scale_mode == "match_longest":
        factor = float(desired.max() / extents.max())
    else:  # fit_bbox — uniform scale that fits inside target box
        factor = float(np.min(desired / extents))

    mesh.apply_scale(factor)
    return mesh, factor


def add_flat_base(mesh: trimesh.Trimesh, height_mm: float = 2.0, margin_mm: float = 2.0) -> trimesh.Trimesh:
    mesh = center_on_bed(mesh)
    extents = mesh.extents
    base = trimesh.creation.box(
        extents=(extents[0] + margin_mm * 2, extents[1] + margin_mm * 2, height_mm)
    )
    # Place base under Z=0, centered on XY
    base.apply_translation([0, 0, height_mm / 2.0])
    # Lift original mesh onto base
    mesh.apply_translation([0, 0, height_mm])
    combined = trimesh.util.concatenate([base, mesh])
    return center_on_bed(combined)


def export_stl(mesh: trimesh.Trimesh, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path, file_type="stl")
    return path


def export_3mf(mesh: trimesh.Trimesh, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mesh.export(path, file_type="3mf")
        return path
    except Exception:
        # Fallback: minimal OPC 3MF (mesh only) so Studio can still open it
        return _export_minimal_3mf(mesh, path)


def _export_minimal_3mf(mesh: trimesh.Trimesh, path: Path) -> Path:
    import zipfile
    from xml.sax.saxutils import escape

    vertices = mesh.vertices
    faces = mesh.faces
    v_lines = "\n".join(
        f'<vertex x="{float(x):.6f}" y="{float(y):.6f}" z="{float(z):.6f}" />'
        for x, y, z in vertices
    )
    t_lines = "\n".join(
        f'<triangle v1="{int(a)}" v2="{int(b)}" v3="{int(c)}" />' for a, b, c in faces
    )
    model_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
 xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <resources>
  <object id="1" type="model">
   <mesh>
    <vertices>
{v_lines}
    </vertices>
    <triangles>
{t_lines}
    </triangles>
   </mesh>
  </object>
 </resources>
 <build>
  <item objectid="1" />
 </build>
</model>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model"
  Id="rel0"
  Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""
    # escape unused but keep import honest for future metadata
    _ = escape
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
    return path


def process_pipeline(
    mesh: trimesh.Trimesh,
    target: TargetDimensions,
    *,
    add_base: bool = False,
    base_height_mm: float = 2.0,
) -> tuple[trimesh.Trimesh, MeshReport]:
    mesh, repair_warnings = repair_mesh(mesh)
    mesh, factor = scale_to_dimensions(mesh, target)
    if add_base:
        mesh = add_flat_base(mesh, height_mm=base_height_mm)
    mesh = center_on_bed(mesh)
    report = inspect_mesh(mesh)
    report.scale_factor = factor
    report.warnings = repair_warnings + report.warnings
    # Check final fit vs requested box (informational)
    ex = report.extents_mm
    report.warnings.append(
        f"final extents {ex[0]:.2f}×{ex[1]:.2f}×{ex[2]:.2f} mm "
        f"(requested {target.width_mm:.1f}×{target.depth_mm:.1f}×{target.height_mm:.1f}, "
        f"mode={target.scale_mode}, scale={factor:.4f})"
    )
    return mesh, report

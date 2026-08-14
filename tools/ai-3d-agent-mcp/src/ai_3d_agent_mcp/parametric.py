from __future__ import annotations

import re
from typing import Any

import numpy as np
import trimesh

from ai_3d_agent_mcp.dimensions import TargetDimensions


def classify_route(category: str, prompt: str, has_images: bool = False) -> str:
    """Return generation route: parametric_hook | parametric_sign | ai_mesh."""
    text = f"{category} {prompt}".lower()
    if category == "hook" or re.search(r"\b(hook|hanger|peg)\b", text):
        return "parametric_hook"
    if category == "sign" or re.search(r"\b(sign|plaque|nameplate|label)\b", text):
        return "parametric_sign"
    if category == "figurine":
        return "ai_mesh"
    if re.search(r"\b(bracket|spacer|washer|clip|mount)\b", text):
        return "parametric_bracket"
    # Photos of unknown functional shapes → AI mesh; text-only functional → simple bracket blank
    if has_images:
        return "ai_mesh"
    if category == "functional":
        return "parametric_bracket"
    return "ai_mesh"


def build_hook(target: TargetDimensions, prompt: str = "") -> trimesh.Trimesh:
    """
    Simple wall hook sized to the target bounding box.
    W = plate width, D = protrusion depth, H = plate height.
    """
    w, d, h = target.width_mm, target.depth_mm, target.height_mm
    plate_t = max(2.0, min(4.0, w * 0.12))
    arm_t = max(2.0, min(plate_t, d * 0.25))
    plate = trimesh.creation.box(extents=(w, plate_t, h))
    plate.apply_translation([0, plate_t / 2.0, h / 2.0])

    # Hook arm: horizontal protrusion + small lip
    arm_len = max(d - plate_t, 8.0)
    arm = trimesh.creation.box(extents=(arm_t * 2.2, arm_len, arm_t))
    arm_z = h * 0.62
    arm.apply_translation([0, plate_t + arm_len / 2.0, arm_z])

    lip = trimesh.creation.box(extents=(arm_t * 2.2, arm_t, arm_t * 2.5))
    lip.apply_translation([0, plate_t + arm_len - arm_t / 2.0, arm_z + arm_t])

    # Screw holes (boolean difference if available)
    hole_r = 2.2
    mesh = trimesh.util.concatenate([plate, arm, lip])
    try:
        for hz in (h * 0.2, h * 0.8):
            cyl = trimesh.creation.cylinder(radius=hole_r, height=plate_t + 2.0, sections=24)
            cyl.apply_transform(
                trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
            )
            cyl.apply_translation([0, plate_t / 2.0, hz])
            mesh = mesh.difference(cyl, engine="auto")
    except Exception:
        # If boolean engine missing, keep solid plate — slicer can still print
        pass

    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    return mesh


def build_sign(target: TargetDimensions, prompt: str = "") -> trimesh.Trimesh:
    """Flat sign plate with slight raised border."""
    w, d, h = target.width_mm, target.depth_mm, target.height_mm
    thickness = max(1.5, d)
    plate = trimesh.creation.box(extents=(w, thickness, h))
    plate.apply_translation([0, thickness / 2.0, h / 2.0])

    border_t = max(0.6, thickness * 0.35)
    inset = 3.0
    if w > inset * 4 and h > inset * 4:
        frame_outer = trimesh.creation.box(extents=(w, border_t, h))
        frame_inner = trimesh.creation.box(extents=(w - inset * 2, border_t + 1.0, h - inset * 2))
        frame_outer.apply_translation([0, thickness + border_t / 2.0, h / 2.0])
        frame_inner.apply_translation([0, thickness + border_t / 2.0, h / 2.0])
        try:
            frame = frame_outer.difference(frame_inner, engine="auto")
            mesh = trimesh.util.concatenate([plate, frame])
        except Exception:
            mesh = plate
    else:
        mesh = plate

    # Mounting holes near top corners
    try:
        for hx in (-w * 0.4, w * 0.4):
            cyl = trimesh.creation.cylinder(radius=1.8, height=thickness + border_t + 2.0, sections=20)
            cyl.apply_transform(
                trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
            )
            cyl.apply_translation([hx, thickness / 2.0, h * 0.85])
            mesh = mesh.difference(cyl, engine="auto")
    except Exception:
        pass

    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    # Encode prompt lightly in metadata only; geometry stays dimensional
    mesh.metadata = {"prompt": prompt, "kind": "sign"}
    return mesh


def build_bracket(target: TargetDimensions, prompt: str = "") -> trimesh.Trimesh:
    """L-bracket / general functional blank sized to the target box."""
    w, d, h = target.width_mm, target.depth_mm, target.height_mm
    t = max(2.0, min(w, d, h) * 0.15)
    vertical = trimesh.creation.box(extents=(w, t, h))
    vertical.apply_translation([0, t / 2.0, h / 2.0])
    horizontal = trimesh.creation.box(extents=(w, d, t))
    horizontal.apply_translation([0, d / 2.0, t / 2.0])
    mesh = trimesh.util.concatenate([vertical, horizontal])
    mesh.metadata = {"prompt": prompt, "kind": "bracket"}
    return mesh


def build_parametric(route: str, target: TargetDimensions, prompt: str = "") -> tuple[trimesh.Trimesh, dict[str, Any]]:
    builders = {
        "parametric_hook": build_hook,
        "parametric_sign": build_sign,
        "parametric_bracket": build_bracket,
    }
    if route not in builders:
        raise ValueError(f"Not a parametric route: {route}")
    mesh = builders[route](target, prompt=prompt)
    info = {
        "route": route,
        "engine": "parametric",
        "dimensional": True,
        "note": "Parametric CAD path used for dimensional accuracy on functional geometry.",
    }
    return mesh, info

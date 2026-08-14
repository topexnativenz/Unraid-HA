from __future__ import annotations

import trimesh

from ai_3d_agent_mcp.dimensions import TargetDimensions
from ai_3d_agent_mcp.mesh_ops import add_flat_base, process_pipeline, scale_to_dimensions


def test_scale_fit_bbox():
    mesh = trimesh.creation.box(extents=(10, 20, 40))
    scaled, factor = scale_to_dimensions(mesh, TargetDimensions(20, 40, 80, scale_mode="fit_bbox"))
    assert abs(factor - 2.0) < 1e-6
    assert abs(scaled.extents[2] - 80) < 1e-4


def test_flat_base_increases_height():
    mesh = trimesh.creation.icosphere(radius=10)
    before = mesh.extents[2]
    based = add_flat_base(mesh, height_mm=2.0)
    assert based.extents[2] >= before


def test_process_pipeline_warns():
    mesh = trimesh.creation.box(extents=(5, 5, 5))
    out, report = process_pipeline(mesh, TargetDimensions(10, 10, 10), add_base=True)
    assert out.extents[0] > 0
    assert report.scale_factor is not None
    assert report.warnings

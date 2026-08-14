from __future__ import annotations

from ai_3d_agent_mcp.dimensions import TargetDimensions
from ai_3d_agent_mcp.parametric import build_hook, build_sign, classify_route


def test_classify_hook():
    assert classify_route("functional", "wall hook for coats") == "parametric_hook"
    assert classify_route("hook", "something") == "parametric_hook"


def test_classify_figurine():
    assert classify_route("figurine", "cute fox") == "ai_mesh"


def test_classify_functional_photo_uses_ai():
    assert classify_route("functional", "odd replacement part from photo", has_images=True) == "ai_mesh"
    assert classify_route("functional", "simple mount blank", has_images=False) == "parametric_bracket"


def test_hook_extents_reasonable():
    target = TargetDimensions(40, 25, 60)
    mesh = build_hook(target)
    assert mesh.extents[0] > 0
    assert mesh.extents[2] > 0
    # Should roughly respect target scale (not tiny)
    assert mesh.extents[0] >= 30
    assert mesh.extents[2] >= 40


def test_sign_builds():
    mesh = build_sign(TargetDimensions(120, 3, 60), prompt="Workshop")
    assert len(mesh.faces) > 0

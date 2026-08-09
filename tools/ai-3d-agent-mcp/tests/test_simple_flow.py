from __future__ import annotations

from pathlib import Path

from ai_3d_agent_mcp.config import AgentConfig
from ai_3d_agent_mcp.simple_flow import (
    dims_complete,
    infer_category,
    looks_like_print_request,
    user_facing_dimension_question,
)


def test_detect_text_print():
    assert looks_like_print_request("Can you 3D print a wall hook for coats?")
    assert looks_like_print_request("design and print a small sign")
    assert not looks_like_print_request("what's the weather tomorrow?")


def test_detect_photo():
    assert looks_like_print_request("", has_images=True)
    assert looks_like_print_request("make this", has_images=True)


def test_infer_category():
    assert infer_category("coat hook", False) == "hook"
    assert infer_category("desk figurine fox", False) == "figurine"
    assert infer_category("", True) == "figurine"


def test_dimension_question_is_user_facing():
    q = user_facing_dimension_question("hook", "coat hook", False)
    assert q["status"] == "needs_dimensions"
    assert q["ask_user_only"] is True
    assert "millimetres" in q["ask_user"].lower() or "millimetre" in q["ask_user"].lower()


def test_dims_complete():
    assert dims_complete(40, 25, 60)
    assert not dims_complete(None, 25, 60)
    assert not dims_complete(0, 25, 60)


def test_macos_path_mapping(tmp_path: Path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    cfg = AgentConfig(
        workspace_root=str(jobs),
        history_db=str(jobs / "h.sqlite3"),
        macos_jobs_mount="/Volumes/ai-3d-agent/jobs",
    )
    server_file = jobs / "abc" / "export" / "model.3mf"
    server_file.parent.mkdir(parents=True)
    server_file.write_text("x")
    assert cfg.path_for_macos(server_file) == "/Volumes/ai-3d-agent/jobs/abc/export/model.3mf"

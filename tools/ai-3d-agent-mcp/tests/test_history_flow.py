from __future__ import annotations

import json
from pathlib import Path

from ai_3d_agent_mcp.config import AgentConfig
from ai_3d_agent_mcp.dimensions import parse_dimensions
from ai_3d_agent_mcp.generate import run_generation
from ai_3d_agent_mcp.guardrails import GuardrailError, assert_no_auto_print
from ai_3d_agent_mcp.handoff import handoff
from ai_3d_agent_mcp.history import JobHistory
from ai_3d_agent_mcp.package_3mf import package_job
import pytest


def test_job_flow(tmp_path: Path):
    cfg = AgentConfig(
        workspace_root=str(tmp_path / "jobs"),
        history_db=str(tmp_path / "jobs" / "history.sqlite3"),
        generation_backend="stub",
        ios_share_dir=str(tmp_path / "ios"),
    )
    # Override resolve by using absolute paths already in AgentConfig properties
    # AgentConfig uses resolve_repo_path — absolute paths work.
    hist = JobHistory(Path(cfg.history_db), Path(cfg.workspace_root))
    job = hist.create_job(
        category="hook",
        prompt="coat hook",
        material="PLA",
        printer="X1C-A",
        width_mm=40,
        depth_mm=25,
        height_mm=60,
        scale_mode="fit_bbox",
    )
    dims = parse_dimensions(40, 25, 60)
    gen = run_generation(
        cfg,
        target=dims,
        prompt=job.prompt,
        category=job.category,
        image_paths=[],
        job_dir=hist.job_dir(job.job_id),
    )
    assert Path(gen["stl_path"]).is_file()
    hist.update(job.job_id, status="generated", artifacts={"raw_stl": gen["stl_path"]})

    packaged = package_job(
        cfg,
        job_dir=hist.job_dir(job.job_id),
        raw_stl=Path(gen["stl_path"]),
        target=dims,
        category="hook",
        material="PLA",
        printer_name="X1C-A",
        image_paths=[],
        add_flat_base=False,
    )
    assert Path(packaged["three_mf"]).is_file()
    assert Path(packaged["manifest"]).is_file()

    result = handoff(
        cfg,
        job_id=job.job_id,
        three_mf=Path(packaged["three_mf"]),
        target="ios_bambu",
        dry_run=True,
    )
    assert result["status"] == "staged_ios"
    assert Path(result["ios_path"]).is_file()

    with pytest.raises(GuardrailError):
        assert_no_auto_print(False, True)

    listed = hist.list_jobs()
    assert listed[0].job_id == job.job_id
    sidecar = json.loads((hist.job_dir(job.job_id) / "job.json").read_text())
    assert sidecar["prompt"] == "coat hook"

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from ai_3d_agent_mcp.config import AgentConfig
from ai_3d_agent_mcp.guardrails import GuardrailError, assert_no_auto_print
from ai_3d_agent_mcp.package_3mf import stage_ios_share


def handoff(
    cfg: AgentConfig,
    *,
    job_id: str,
    three_mf: Path,
    target: str = "macos_studio",
    confirm_send_to_printer: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Prepare / open in Bambu Studio or stage for iOS. Never starts a print.
    """
    assert_no_auto_print(cfg.allow_auto_print, confirm_send_to_printer)

    if not three_mf.is_file():
        raise FileNotFoundError(f"3MF not found: {three_mf}")

    target = target.lower().strip()
    if target not in {"macos_studio", "ios_bambu", "file_only"}:
        raise ValueError("target must be macos_studio, ios_bambu, or file_only")

    result: dict[str, Any] = {
        "job_id": job_id,
        "target": target,
        "three_mf": str(three_mf),
        "auto_print": False,
        "dry_run": dry_run,
        "actions": [],
    }

    if target == "file_only":
        result["actions"].append("file ready — open manually in Bambu Studio")
        result["status"] = "ready"
        return result

    if target == "ios_bambu":
        ios = stage_ios_share(cfg, job_id, three_mf)
        result.update(ios)
        result["actions"].append("staged for iOS Files → Bambu app")
        result["status"] = "staged_ios"
        return result

    # macos_studio
    app = cfg.macos_bambu_app or "BambuStudio"
    open_cmd = cfg.open_studio_command.strip()
    if open_cmd:
        # Supports remote open via SSH to the Mac, e.g.:
        # ssh user@mac 'open -a BambuStudio "{path}"'
        # Placeholders: {path} {app}
        formatted = open_cmd.format(path=str(three_mf), app=app)
        cmd = shlex.split(formatted)
    else:
        # Local macOS only — on Unraid this remains a planned command
        cmd = ["open", "-a", app, str(three_mf)]

    result["open_command"] = cmd
    result["actions"].append("open 3MF in Bambu Studio (no slice/print started)")

    if dry_run:
        result["status"] = "planned"
        result["hint"] = (
            "dry_run=true: command not executed. Set dry_run=false on the Mac host, "
            "or configure open_studio_command to SSH into the Mac that has Bambu Studio. "
            "Unraid-only runs should use target=ios_bambu or mount the jobs share on the Mac."
        )
        return result

    # Safety: only execute open on Darwin unless a custom open_studio_command is set
    if not open_cmd and os.uname().sysname != "Darwin":
        result["status"] = "skipped_non_macos"
        result["warning"] = (
            "Not running on macOS and open_studio_command is empty. "
            "File is ready; open it from the Mac share or set open_studio_command."
        )
        return result

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        result["returncode"] = proc.returncode
        result["stdout"] = (proc.stdout or "")[:1000]
        result["stderr"] = (proc.stderr or "")[:1000]
        result["status"] = "opened" if proc.returncode == 0 else "open_failed"
    except FileNotFoundError as exc:
        raise GuardrailError(f"Failed to execute open command: {exc}") from exc

    return result

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_3d_agent_mcp.paths import MCP_ROOT, REPO_ROOT, resolve_repo_path


@dataclass
class PrinterProfile:
    model: str = "Bambu Lab X1 Carbon"
    bed_mm: list[float] = field(default_factory=lambda: [256.0, 256.0, 256.0])
    nozzle_mm: float = 0.4
    process: str = "0.20mm Standard"
    ams: bool = True


@dataclass
class AgentConfig:
    workspace_root: str = "tools/ai-3d-agent-mcp/jobs"
    history_db: str = "tools/ai-3d-agent-mcp/jobs/history.sqlite3"
    generation_backend: str = "stub"
    generation_http_url: str = "http://192.168.1.239:7860/generate"
    default_printer: str = "X1C-A"
    printers: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "X1C-A": {
                "model": "Bambu Lab X1 Carbon",
                "bed_mm": [256, 256, 256],
                "nozzle_mm": 0.4,
                "process": "0.20mm Standard",
                "ams": True,
            },
            "X1C-B": {
                "model": "Bambu Lab X1 Carbon",
                "bed_mm": [256, 256, 256],
                "nozzle_mm": 0.4,
                "process": "0.20mm Standard",
                "ams": True,
            },
        }
    )
    default_material: str = "PLA"
    materials: list[str] = field(default_factory=lambda: ["PLA", "PETG", "TPU"])
    auto_flat_base_categories: list[str] = field(default_factory=lambda: ["figurine"])
    flat_base_height_mm: float = 2.0
    warn_only_mesh_checks: bool = True
    allow_auto_print: bool = False
    macos_bambu_app: str = "BambuStudio"
    ios_share_base_url: str = ""
    ios_share_dir: str = "tools/ai-3d-agent-mcp/jobs/ios-share"
    open_studio_command: str = ""
    meshy_api_key_env: str = "MESHY_API_KEY"
    tripo_api_key_env: str = "TRIPO_API_KEY"

    @property
    def workspace_path(self) -> Path:
        return resolve_repo_path(self.workspace_root)

    @property
    def history_db_path(self) -> Path:
        return resolve_repo_path(self.history_db)

    @property
    def ios_share_path(self) -> Path:
        return resolve_repo_path(self.ios_share_dir)

    def printer_profile(self, name: str | None = None) -> PrinterProfile:
        key = name or self.default_printer
        raw = self.printers.get(key) or self.printers[self.default_printer]
        return PrinterProfile(
            model=str(raw.get("model", "Bambu Lab X1 Carbon")),
            bed_mm=[float(x) for x in raw.get("bed_mm", [256, 256, 256])],
            nozzle_mm=float(raw.get("nozzle_mm", 0.4)),
            process=str(raw.get("process", "0.20mm Standard")),
            ams=bool(raw.get("ams", True)),
        )


def config_file_candidates() -> list[Path]:
    candidates: list[Path] = []
    if custom := os.environ.get("AI_3D_AGENT_CONFIG"):
        candidates.append(Path(custom).expanduser())
    candidates.extend(
        [
            MCP_ROOT / "ai-3d-agent.config.json",
            REPO_ROOT / "ai-3d-agent.config.json",
        ]
    )
    return candidates


def load_config() -> AgentConfig:
    for path in config_file_candidates():
        if path.is_file():
            data = json.loads(path.read_text())
            allowed = AgentConfig.__dataclass_fields__
            return AgentConfig(**{k: v for k, v in data.items() if k in allowed})
    return AgentConfig()

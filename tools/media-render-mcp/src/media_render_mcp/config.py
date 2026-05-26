from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from media_render_mcp.paths import MCP_ROOT, REPO_ROOT, resolve_repo_path


@dataclass
class MediaRenderConfig:
    ha_host: str = "192.168.1.239"
    ha_url: str = "http://192.168.1.239:8123"
    backgrounds_root: str = "home-assistant/solar-dashboard/www/solar-dashboard/backgrounds"
    locked_master: str = (
        "home-assistant/solar-dashboard/www/solar-dashboard/backgrounds/v5/master-clear.png"
    )
    render_backend: str = "fal"
    fal_image_model: str = "fal-ai/flux/dev"
    deploy_script: str = "home-assistant/solar-dashboard/scripts/deploy_to_ha.py"
    lovelace_yaml_paths: list[str] = field(
        default_factory=lambda: [
            "home-assistant/solar-dashboard/lovelace/views/solar-energy.yaml",
            "home-assistant/solar-dashboard/lovelace/views/solar-energy-fr.yaml",
            "home-assistant/solar-dashboard/lovelace/dashboards/solar_dashboard.yaml",
        ]
    )
    weather_variants: list[str] = field(
        default_factory=lambda: ["clear", "cloudy", "covered", "very_covered", "night"]
    )

    @property
    def backgrounds_path(self) -> Path:
        return resolve_repo_path(self.backgrounds_root)

    @property
    def locked_master_path(self) -> Path:
        return resolve_repo_path(self.locked_master)

    @property
    def deploy_script_path(self) -> Path:
        return resolve_repo_path(self.deploy_script)


def config_file_candidates() -> list[Path]:
    import os

    candidates: list[Path] = []
    if custom := os.environ.get("MEDIA_RENDER_CONFIG"):
        candidates.append(Path(custom).expanduser())
    candidates.extend(
        [
            MCP_ROOT / "media-render.config.json",
            REPO_ROOT / "media-render.config.json",
        ]
    )
    return candidates


def load_config() -> MediaRenderConfig:
    for path in config_file_candidates():
        if path.is_file():
            data = json.loads(path.read_text())
            return MediaRenderConfig(**{k: v for k, v in data.items() if k in MediaRenderConfig.__dataclass_fields__})
    return MediaRenderConfig()

#!/usr/bin/env python3
"""Push a Lovelace YAML/JSON config to HA via lovelace/config/save (no SMB).

Examples:
  python3 home-assistant/scripts/push_lovelace.py \\
    --url-path flux-ui-tablet \\
    --config home-assistant/flux-ui-dashboard/lovelace/dashboards/flux_ui_tablet.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parents[1] / "flux-ui-dashboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ha_common import (  # noqa: E402
    apply_resolved_ha,
    get_token,
    run_async,
    wait_for_ha,
    ws_call_retry,
)


def load_config(path: Path) -> dict:
    text = path.read_text()
    if path.suffix.lower() == ".json":
        raw = json.loads(text)
        if isinstance(raw, dict) and "data" in raw and "config" in raw["data"]:
            return raw["data"]["config"]
        if isinstance(raw, dict) and "views" in raw:
            return raw
        raise SystemExit(f"{path} is not a Lovelace config JSON")
    lines = text.splitlines(keepends=True)
    while lines and lines[0].lstrip().startswith("#"):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)
    cfg = yaml.safe_load("".join(lines))
    if not isinstance(cfg, dict) or "views" not in cfg:
        raise SystemExit(f"{path} is not a Lovelace YAML config (missing views)")
    return cfg


async def push(token: str, ha_url: str, url_path: str, config: dict, *, title: str) -> None:
    listed = (await ws_call_retry(token, ha_url, [{"type": "lovelace/dashboards/list"}]))[0]
    items = listed.get("result") or []
    if not any(d.get("url_path") == url_path for d in items):
        created = await ws_call_retry(
            token,
            ha_url,
            [
                {
                    "type": "lovelace/dashboards/create",
                    "url_path": url_path,
                    "title": title,
                    "icon": "mdi:view-dashboard",
                    "show_in_sidebar": True,
                    "require_admin": False,
                    "mode": "storage",
                }
            ],
        )
        if not created[0].get("success"):
            raise SystemExit(f"Could not create dashboard {url_path}: {created[0].get('error')}")
        print(f"Created storage dashboard {url_path}")

    await wait_for_ha(token, ha_url, timeout_s=60, label="HA before lovelace/config/save")
    saved = await ws_call_retry(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": url_path, "config": config}],
        label=f"lovelace/config/save ({url_path})",
    )
    if not saved[0].get("success"):
        raise SystemExit(f"lovelace/config/save failed: {saved[0].get('error')}")

    verify = await ws_call_retry(
        token,
        ha_url,
        [{"type": "lovelace/config", "url_path": url_path, "force": True}],
        label=f"lovelace/config verify ({url_path})",
    )
    if not verify[0].get("success"):
        raise SystemExit(f"verify failed: {verify[0].get('error')}")
    views = verify[0]["result"].get("views") or []
    print(f"Pushed {url_path}: {len(views)} view(s) → {ha_url}/{url_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--url-path", required=True, help="Dashboard url_path (e.g. flux-ui-tablet)")
    parser.add_argument("--config", required=True, type=Path, help="YAML or JSON Lovelace config")
    parser.add_argument("--title", default=None, help="Title when creating a missing dashboard")
    args = parser.parse_args()
    apply_resolved_ha(args)

    if not args.config.exists():
        raise SystemExit(f"Missing config: {args.config}")
    config = load_config(args.config)
    token = get_token(args.token)
    title = args.title or args.url_path.replace("-", " ").title()
    return run_async(push(token, args.ha_url, args.url_path, config, title=title)) or 0


if __name__ == "__main__":
    raise SystemExit(main())

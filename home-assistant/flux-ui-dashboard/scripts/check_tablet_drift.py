#!/usr/bin/env python3
"""Compare live flux-ui-tablet Lovelace config to the locked repo YAML.

Exit 0 when the live dashboard matches this checkout.
Exit 1 when it drifted (fingerprint or rigid-grid rules).
Exit 2 when Home Assistant cannot be reached.

Does not print the access token or the Home Assistant URL.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy_flux_ui import (  # noqa: E402
    TABLET_URL_PATH,
    load_tablet_yaml,
    tablet_config_fingerprint,
)
from flux_tablet_layout import tablet_rigid_grid_errors  # noqa: E402
from ha_common import get_token, ws_call  # noqa: E402

_URL_RE = re.compile(r"wss?://\S+|https?://\S+")


def _safe(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return _URL_RE.sub("HA", text)


async def _live_config(token: str, ha_url: str) -> dict:
    res = (
        await ws_call(
            token,
            ha_url,
            [{"type": "lovelace/config", "url_path": TABLET_URL_PATH, "force": True}],
        )
    )[0]
    if not res.get("success"):
        raise RuntimeError(f"lovelace/config failed: {res.get('error')}")
    config = res.get("result")
    if not isinstance(config, dict):
        raise RuntimeError("lovelace/config returned no dashboard")
    return config


def main() -> int:
    ha_url = (os.environ.get("HA_URL") or "").strip().rstrip("/")
    if not ha_url:
        print("live tablet check skipped: HA_URL is not set")
        return 2
    try:
        token = get_token(None)
    except Exception as exc:
        print(f"live tablet check skipped: {_safe(exc)}")
        return 2

    try:
        repo = load_tablet_yaml()
    except SystemExit as exc:
        print(f"repo tablet YAML unreadable: {_safe(exc)}")
        return 1

    repo_blob = json.dumps(repo)
    repo_fp = tablet_config_fingerprint(repo)
    repo_errors = tablet_rigid_grid_errors(repo_blob)
    print(f"repo_sha256={repo_fp}")
    print(f"repo_rigid_grid={'no' if repo_errors else 'yes'}")
    if repo_errors:
        for msg in repo_errors:
            print(f"repo_rigid_error={msg}")

    try:
        live = asyncio.run(_live_config(token, ha_url))
    except Exception as exc:
        print(f"live tablet unreachable: {_safe(exc)}")
        return 2

    live_blob = json.dumps(live)
    live_fp = tablet_config_fingerprint(live)
    live_errors = tablet_rigid_grid_errors(live_blob)
    print(f"live_sha256={live_fp}")
    print(f"live_rigid_grid={'no' if live_errors else 'yes'}")
    print(f"match={'yes' if live_fp == repo_fp else 'no'}")

    if live_fp != repo_fp or live_errors or repo_errors:
        print(
            "DRIFT: live flux-ui-tablet does not match the locked repo YAML "
            "or is missing the rigid overview grid."
        )
        return 1
    print("OK: live flux-ui-tablet matches the locked repo YAML.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

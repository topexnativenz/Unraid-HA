#!/usr/bin/env python3
"""Register Flux UI frontend dependencies via Home Assistant Lovelace resources."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import DEFAULT_HA, get_token, run_async, ws_call

URL_PATH = "flux-ui"

# Prefer bundled /local/ assets (E2E), then HACS /hacsfiles/ paths.
FRONTEND_RESOURCES: list[tuple[str, str]] = [
    ("mushroom-local", "/local/community/lovelace-mushroom/mushroom.js"),
    ("card-mod-local", "/local/community/lovelace-card-mod/card-mod.js"),
    ("mushroom-hacs", "/hacsfiles/lovelace-mushroom/mushroom.js"),
    ("card-mod-hacs", "/hacsfiles/lovelace-card-mod/card-mod.js"),
    ("button-card", "/hacsfiles/button-card/button-card.js"),
    ("layout-card", "/hacsfiles/lovelace-layout-card/layout-card.js"),
    ("stack-in-card", "/hacsfiles/stack-in-card/stack-in-card.js"),
    ("bubble-card", "/hacsfiles/bubble-card/bubble-card.js"),
    ("navbar-card", "/hacsfiles/lovelace-navbar-card/navbar-card.js"),
    ("kiosk-mode", "/hacsfiles/kiosk-mode/kiosk-mode.js"),
]


async def ensure_resources(token: str, ha_url: str) -> None:
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]
    existing_urls = {r.get("url") for r in listed.get("result", [])}

    # One mushroom + one card-mod is enough for overview.
    have_mushroom = any("mushroom" in u for u in existing_urls)
    have_card_mod = any("card-mod" in u for u in existing_urls)

    created = 0
    for label, url in FRONTEND_RESOURCES:
        if url in existing_urls:
            print(f"  ok  {label}")
            continue
        if "mushroom" in label and have_mushroom:
            continue
        if "card-mod" in label and have_card_mod:
            continue

        res = await ws_call(
            token,
            ha_url,
            [{"type": "lovelace/resources/create", "res_type": "module", "url": url}],
        )
        if res[0].get("success"):
            print(f"  add {label}")
            created += 1
            if "mushroom" in url:
                have_mushroom = True
            if "card-mod" in url:
                have_card_mod = True
        elif label.endswith("-local"):
            print(f"  skip {label} (not on HA yet — deploy copies www/ via SMB)")
        else:
            print(f"  MISSING {label} — install via HACS or run install_frontend_assets.py + deploy")

    if not have_mushroom or not have_card_mod:
        print("WARNING: mushroom and/or card-mod still missing after resource registration")
    else:
        print("Core overview resources: mushroom + card-mod OK")


async def ensure_dashboard(token: str, ha_url: str) -> None:
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/dashboards/list"}]))[0]
    paths = {d.get("url_path") for d in listed.get("result", [])}
    if URL_PATH in paths:
        print(f"Dashboard {URL_PATH} already registered")
        return
    res = await ws_call(
        token,
        ha_url,
        [
            {
                "type": "lovelace/dashboards/create",
                "title": "Flux UI",
                "icon": "mdi:view-dashboard-variant",
                "url_path": URL_PATH,
                "require_admin": False,
                "show_in_sidebar": True,
            }
        ],
    )
    if not res[0].get("success"):
        raise RuntimeError(f"dashboard create failed: {res[0]}")
    print(f"Created dashboard {URL_PATH} (parallel to Mobile Home)")


async def main_async(ha_url: str, token: str | None) -> int:
    token = get_token(token)
    await ensure_resources(token, ha_url)
    await ensure_dashboard(token, ha_url)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()
    return run_async(main_async(args.ha_url, args.token))


if __name__ == "__main__":
    raise SystemExit(main())

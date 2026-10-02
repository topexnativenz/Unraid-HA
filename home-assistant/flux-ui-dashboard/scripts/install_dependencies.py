#!/usr/bin/env python3
"""Register Flux UI frontend dependencies via Home Assistant Lovelace resources.

HA 2026.7 patches CustomElementRegistry so a second `customElements.define()`
for the same tag throws. `ensure_resources` used to add `/hacsfiles/foo.js`
even when HACS already registered `/hacsfiles/foo.js?hacstag=…`, which made
every custom card on the phone dashboards (Flux UI Home, tablet, wall,
mobile-home) render as "Configuration error" on cold cache / Companion.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import DEFAULT_HA, get_token, run_async, ws_call

URL_PATH = "flux-ui"
CAROUSEL_SYNC = "/local/flux-ui/carousel-sync.js"

# Prefer HACS hacstag URLs already on the instance. Only add a path when no
# equivalent resource exists (query strings ignored). Wrong / 404 paths must
# never be created — they stall the module loader on Companion.
FRONTEND_RESOURCES: list[tuple[str, str]] = [
    ("nz-timezone", "/local/flux-ui/nz-timezone.js"),
    ("carousel-sync", CAROUSEL_SYNC),
    ("mushroom-local", "/local/community/lovelace-mushroom/mushroom.js"),
    ("card-mod-local", "/local/community/lovelace-card-mod/card-mod.js"),
    ("mushroom-hacs", "/hacsfiles/lovelace-mushroom/mushroom.js"),
    ("card-mod-hacs", "/hacsfiles/lovelace-card-mod/card-mod.js"),
    ("button-card", "/hacsfiles/button-card/button-card.js"),
    ("layout-card", "/hacsfiles/lovelace-layout-card/layout-card.js"),
    ("stack-in-card", "/hacsfiles/stack-in-card/stack-in-card.js"),
    ("bubble-card", "/hacsfiles/Bubble-Card/bubble-card.js"),
    ("auto-entities", "/hacsfiles/lovelace-auto-entities/auto-entities.js"),
    ("navbar-card", "/hacsfiles/lovelace-navbar-card/navbar-card.js"),
    ("kiosk-mode", "/hacsfiles/kiosk-mode/kiosk-mode.js"),
    ("simple-tabs", "/hacsfiles/home-assistant-simple-tabs/simple-tabs.js"),
    ("calendar-card-pro", "/hacsfiles/calendar-card-pro/calendar-card-pro.js"),
    ("mediocre-media", "/hacsfiles/mediocre-hass-media-player-cards/mediocre-hass-media-player-cards.js"),
    ("apexcharts-card", "/hacsfiles/apexcharts-card/apexcharts-card.js"),
    (
        "weather-forecast-extended",
        "/hacsfiles/weather-forecast-extended/weatherforecastextended.js",
    ),
    ("lunar-phase-card", "/hacsfiles/lunar-phase-card/lunar-phase-card.js"),
]

# Known-bad URLs from older deploys (404 or CSS loaded as JS module).
DELETE_EXACT_URLS = {
    "/hacsfiles/bubble-card/bubble-card.js",
    "/hacsfiles/lovelace-kiosk-mode/kiosk-mode.js",
    "/hacsfiles/weather-forecast-extended-card/weather-forecast-extended-card.js",
}

CSS_AS_MODULE_SUFFIXES = (".css",)


def canonical_path(url: str) -> str:
    """Strip query/fragment so hacstag and bare HACS URLs compare equal."""
    parsed = urlparse(url or "")
    path = parsed.path or url.split("?", 1)[0]
    return path.rstrip("/") or path


def _resource_id(item: dict) -> str | None:
    return item.get("id") or item.get("resource_id")


async def _list_resources(token: str, ha_url: str) -> list[dict]:
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]
    return list(listed.get("result") or [])


async def _delete_resource(token: str, ha_url: str, item: dict) -> bool:
    rid = _resource_id(item)
    if not rid:
        print(f"  skip delete (no id) {item.get('url')}")
        return False
    res = (
        await ws_call(
            token,
            ha_url,
            [{"type": "lovelace/resources/delete", "resource_id": rid}],
        )
    )[0]
    if res.get("success"):
        print(f"  del {item.get('url')}")
        return True
    print(f"  FAIL delete {item.get('url')}: {res.get('error')}")
    return False


async def _update_resource(token: str, ha_url: str, item: dict, *, res_type: str, url: str) -> bool:
    rid = _resource_id(item)
    if not rid:
        return False
    res = (
        await ws_call(
            token,
            ha_url,
            [
                {
                    "type": "lovelace/resources/update",
                    "resource_id": rid,
                    "res_type": res_type,
                    "url": url,
                }
            ],
        )
    )[0]
    if res.get("success"):
        print(f"  fix {url} type={res_type}")
        return True
    print(f"  FAIL update {url}: {res.get('error')}")
    return False


def _sort_keep_first(items: list[dict]) -> list[dict]:
    """Prefer hacstag / versioned URLs over the bare duplicate."""

    def score(item: dict) -> tuple[int, str]:
        url = item.get("url") or ""
        prefer = 0
        if "hacstag=" in url or "?v=" in url:
            prefer = 0
        else:
            prefer = 1
        # Prefer the canonical Bubble-Card capital-B path.
        if "/bubble-card/" in url:
            prefer += 5
        return (prefer, url)

    return sorted(items, key=score)


async def dedupe_resources(token: str, ha_url: str) -> None:
    """Drop duplicate module URLs and known-bad resources (HA 2026.7 safe)."""
    resources = await _list_resources(token, ha_url)
    by_path: dict[str, list[dict]] = {}
    for item in resources:
        by_path.setdefault(canonical_path(item.get("url") or ""), []).append(item)

    deleted = 0
    for item in resources:
        url = item.get("url") or ""
        res_type = (item.get("type") or item.get("res_type") or "module").lower()
        if url in DELETE_EXACT_URLS:
            if await _delete_resource(token, ha_url, item):
                deleted += 1
            continue
        if url.lower().endswith(CSS_AS_MODULE_SUFFIXES) and res_type == "module":
            if await _update_resource(token, ha_url, item, res_type="css", url=url):
                continue
            if await _delete_resource(token, ha_url, item):
                deleted += 1

    resources = await _list_resources(token, ha_url)
    by_path = {}
    for item in resources:
        by_path.setdefault(canonical_path(item.get("url") or ""), []).append(item)

    for path, items in by_path.items():
        if len(items) < 2:
            continue
        keep, *dupes = _sort_keep_first(items)
        print(f"  keep {keep.get('url')}")
        for item in dupes:
            if await _delete_resource(token, ha_url, item):
                deleted += 1

    print(f"Resource cleanup: deleted {deleted} duplicate/bad module(s)")


async def ensure_resources(token: str, ha_url: str) -> None:
    await dedupe_resources(token, ha_url)

    resources = await _list_resources(token, ha_url)
    existing_paths = {canonical_path(r.get("url") or "") for r in resources}
    existing_urls = {r.get("url") for r in resources}

    have_mushroom = any("mushroom" in (u or "") for u in existing_urls)
    have_card_mod = any("card-mod" in (u or "") for u in existing_urls)

    created = 0
    for label, url in FRONTEND_RESOURCES:
        path = canonical_path(url)
        if path in existing_paths or url in existing_urls:
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
            existing_paths.add(path)
            existing_urls.add(url)
            if "mushroom" in url:
                have_mushroom = True
            if "card-mod" in url:
                have_card_mod = True
        elif label.endswith("-local") or label == "carousel-sync":
            print(f"  skip {label} (not on HA yet — deploy copies www/ via SMB)")
        else:
            print(f"  MISSING {label} — install via HACS or run install_frontend_assets.py + deploy")

    if not have_mushroom or not have_card_mod:
        print("WARNING: mushroom and/or card-mod still missing after resource registration")
    else:
        print("Core overview resources: mushroom + card-mod OK")

    if any("kiosk-mode" in (u or "") for u in existing_urls) or created:
        print("Kiosk mode resource: OK (header hide will work on Flux UI dashboard)")


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


async def strip_invalid_lovelace_root_keys(token: str, ha_url: str) -> None:
    """extra_module_url belongs in frontend:, not the Lovelace dashboard JSON.

    The same class of invalid root key (_flux_ui) previously made every card
    on Flux UI show Configuration error.
    """
    for url_path in ("flux-ui", "flux-ui-tablet", "flux-ui-wall", "flux-ui-wall-2"):
        cfg_res = (
            await ws_call(
                token,
                ha_url,
                [{"type": "lovelace/config", "url_path": url_path}],
            )
        )[0]
        if not cfg_res.get("success"):
            continue
        cfg = cfg_res["result"]
        dropped = [k for k in ("extra_module_url", "_flux_ui") if k in cfg]
        if not dropped:
            print(f"  ok  {url_path} root keys")
            continue
        for key in dropped:
            cfg.pop(key, None)
        save = (
            await ws_call(
                token,
                ha_url,
                [
                    {
                        "type": "lovelace/config/save",
                        "url_path": url_path,
                        "config": cfg,
                    }
                ],
            )
        )[0]
        if save.get("success"):
            print(f"  stripped {dropped} from {url_path}")
        else:
            print(f"  FAIL strip {url_path}: {save.get('error')}")


async def main_async(ha_url: str, token: str | None) -> int:
    token = get_token(token)
    await ensure_resources(token, ha_url)
    await ensure_dashboard(token, ha_url)
    await strip_invalid_lovelace_root_keys(token, ha_url)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()
    return run_async(main_async(args.ha_url, args.token))


if __name__ == "__main__":
    raise SystemExit(main())

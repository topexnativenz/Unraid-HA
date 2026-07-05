#!/usr/bin/env python3
"""Reload HA packages and verify Flux UI input_select helpers are loaded."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import DEFAULT_HA, get_token, run_async, ws_call

FLUX_ENTITIES = (
    "input_select.flux_ui_rooms_tab",
    "input_select.flux_ui_media_player",
    "input_select.flux_ui_overview_tab",
)

REQUIRED = (
    "input_select.flux_ui_rooms_tab",
    "input_select.flux_ui_media_player",
)

MEDIA_SCRIPTS = (
    "script.flux_ui_select_media_zone",
    "script.flux_ui_media_zone_next",
    "script.flux_ui_media_zone_prev",
)


async def entity_exists(token: str, ha_url: str, entity_id: str) -> bool:
    res = await ws_call(token, ha_url, [{"type": "get_states"}])
    if not res[0].get("success"):
        return False
    return any(s.get("entity_id") == entity_id for s in res[0].get("result", []))


async def reload_core_config(token: str, ha_url: str) -> bool:
    res = await ws_call(
        token,
        ha_url,
        [
            {
                "type": "call_service",
                "domain": "homeassistant",
                "service": "reload_core_config",
            }
        ],
    )
    return res[0].get("success") is not False


async def reload_service_domain(token: str, ha_url: str, domain: str, service: str) -> bool:
    res = await ws_call(
        token,
        ha_url,
        [
            {
                "type": "call_service",
                "domain": domain,
                "service": service,
            }
        ],
    )
    return res[0].get("success") is not False


async def restart_ha(token: str, ha_url: str) -> bool:
    res = await ws_call(
        token,
        ha_url,
        [
            {
                "type": "call_service",
                "domain": "homeassistant",
                "service": "restart",
            }
        ],
    )
    return res[0].get("success") is not False


async def wait_for_entities(
    token: str,
    ha_url: str,
    entity_ids: tuple[str, ...],
    *,
    attempts: int = 20,
    delay: float = 3.0,
) -> dict[str, bool]:
    found = {e: False for e in entity_ids}
    for _ in range(attempts):
        for eid in entity_ids:
            if not found[eid] and await entity_exists(token, ha_url, eid):
                found[eid] = True
        if all(found.values()):
            break
        await asyncio.sleep(delay)
    return found


async def main_async(ha_url: str, token: str | None, *, restart: bool) -> int:
    token = get_token(token)
    print("Ensuring Flux UI package helpers (input_select + scripts) are loaded…")

    for attempt in range(1, 3):
        print(f"  reload_core_config (pass {attempt}/2)")
        await reload_core_config(token, ha_url)
        await asyncio.sleep(3)
        print("  reload scripts + automations")
        await reload_service_domain(token, ha_url, "script", "reload")
        await reload_service_domain(token, ha_url, "automation", "reload")
        await asyncio.sleep(3)
        found = await wait_for_entities(token, ha_url, FLUX_ENTITIES, attempts=10, delay=2.0)
        for eid in FLUX_ENTITIES:
            status = "ok" if found[eid] else "missing"
            optional = "" if eid in REQUIRED else " (optional)"
            print(f"    {status:7} {eid}{optional}")

        scripts_ok = True
        for sid in MEDIA_SCRIPTS:
            exists = await entity_exists(token, ha_url, sid)
            status = "ok" if exists else "missing"
            print(f"    {status:7} {sid}")
            if not exists:
                scripts_ok = False

        if all(found[e] for e in REQUIRED) and scripts_ok:
            print("Flux UI package helpers and media scripts loaded.")
            return 0

    missing = [e for e in REQUIRED if not found[e]]
    print(f"\nWARNING: Required helpers still missing: {', '.join(missing)}")
    print("Packages were copied to /config/packages/ but HA has not loaded them yet.")

    if restart:
        print("Restarting Home Assistant (this takes ~60–120s)…")
        await restart_ha(token, ha_url)
        for i in range(40):
            await asyncio.sleep(3)
            try:
                found = await wait_for_entities(token, ha_url, REQUIRED, attempts=1, delay=0)
            except Exception:
                found = {e: False for e in REQUIRED}
            if all(found[e] for e in REQUIRED):
                print("Flux UI package helpers loaded after restart.")
                return 0
            if i % 5 == 4:
                print(f"  waiting for HA… ({(i + 1) * 3}s)")
        print("ERROR: Helpers still missing after restart.")
        return 1

    print("\nFix: run deploy again with package reload, or restart HA once manually:")
    print("  Settings → System → Restart Home Assistant")
    print("  Then hard-refresh Flux UI (Cmd+Shift+R)")
    print("\nOr re-run:")
    print("  bash home-assistant/scripts/deploy_mac.sh --restart-ha")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument(
        "--restart-ha",
        action="store_true",
        help="Restart Home Assistant if helpers still missing after reload",
    )
    args = parser.parse_args()
    return run_async(main_async(args.ha_url, args.token, restart=args.restart_ha))


if __name__ == "__main__":
    raise SystemExit(main())

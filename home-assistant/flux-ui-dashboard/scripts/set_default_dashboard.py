#!/usr/bin/env python3
"""Set a Home Assistant user's default dashboard (server-side, HA >= 2025.12).

HA stores each user's default dashboard in .storage/frontend.user_data_<user_id>
under data.defaultPanel. There is no admin websocket API to set it for another
user, so this patches the storage file over the SMB config share.

Usage:
  python3 set_default_dashboard.py --user smarthome --dashboard flux-ui-tablet
  python3 set_default_dashboard.py --user smarthome --dashboard flux-ui-tablet --restart-ha

A restart is recommended when the user has opened HA since boot: the frontend
user-data store is cached in memory and may not re-read the file until restart.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import (
    DEFAULT_HA,
    DEFAULT_HOST,
    DEFAULT_MOUNT,
    get_samba_creds,
    get_token,
    mount_config,
    run_async,
    unmount,
    ws_call,
)


async def find_user_id(token: str, ha_url: str, name: str) -> str | None:
    res = await ws_call(token, ha_url, [{"type": "config/auth/list"}])
    if not res[0].get("success"):
        raise RuntimeError(f"config/auth/list failed: {res[0].get('error')}")
    users = res[0].get("result") or []
    wanted = name.strip().lower()

    def _match(user: dict) -> bool:
        display = (user.get("name") or "").strip().lower()
        if display == wanted:
            return True
        for cred in user.get("credentials") or []:
            if (cred.get("username") or "").strip().lower() == wanted:
                return True
        return False

    for user in users:
        if _match(user):
            return user["id"]

    # Aliases: deploy shorthand "smarthome" → wall-tablet display accounts.
    aliases = {
        "smarthome": ("smarthome display 1", "smarthome display", "panel"),
        "smarthome display": ("smarthome display 1",),
        "tablet": ("smarthome display 1", "panel"),
    }
    for alias in aliases.get(wanted, ()):
        for user in users:
            display = (user.get("name") or "").strip().lower()
            if display == alias or alias in display:
                print(f"Matched user {user.get('name')!r} via alias {wanted!r}")
                return user["id"]

    # Substring fallback (e.g. smarthome ⊂ SmartHome Display 1).
    if len(wanted) >= 4:
        for user in users:
            display = (user.get("name") or "").strip().lower()
            if wanted in display or display in wanted:
                print(f"Matched user {user.get('name')!r} via fuzzy name {wanted!r}")
                return user["id"]

    print("Users in HA:")
    for user in users:
        print(f"  {user.get('name')!r} (id={user.get('id')}, active={user.get('is_active')})")
    return None


async def dashboard_exists(token: str, ha_url: str, url_path: str) -> bool:
    res = await ws_call(token, ha_url, [{"type": "lovelace/dashboards/list"}])
    if not res[0].get("success"):
        return False
    return any(d.get("url_path") == url_path for d in res[0].get("result") or [])


def patch_user_data(mount: str, user_id: str, dashboard: str) -> tuple[Path, bool]:
    """Returns (path, changed)."""
    storage = Path(mount) / ".storage"
    path = storage / f"frontend.user_data_{user_id}"
    if path.exists():
        raw = json.loads(path.read_text())
        if (raw.get("data") or {}).get("defaultPanel") == dashboard:
            return path, False
        raw.setdefault("data", {})["defaultPanel"] = dashboard
    else:
        raw = {
            "version": 1,
            "minor_version": 1,
            "key": f"frontend.user_data_{user_id}",
            "data": {"defaultPanel": dashboard},
        }
    path.write_text(json.dumps(raw, indent=2))
    return path, True


async def restart_ha(token: str, ha_url: str) -> None:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "call_service", "domain": "homeassistant", "service": "restart"}],
    )
    if res[0].get("success") is False:
        raise RuntimeError(f"HA restart failed: {res[0].get('error')}")


async def main_async(args: argparse.Namespace) -> int:
    token = get_token(args.token)

    user_id = await find_user_id(token, args.ha_url, args.user)
    if not user_id:
        print(f"ERROR: no HA user named {args.user!r} found (see list above).")
        return 1
    print(f"User {args.user!r} -> id {user_id}")

    if not await dashboard_exists(token, args.ha_url, args.dashboard):
        print(
            f"ERROR: dashboard {args.dashboard!r} is not registered in HA — "
            "deploy it first (bash home-assistant/scripts/deploy_mac.sh)."
        )
        return 1

    user, pw = await get_samba_creds(token, args.ha_url)
    if not mount_config(args.host, user, pw, args.mount):
        print("ERROR: could not mount HA config share (Samba add-on running?).")
        return 1
    try:
        path, changed = patch_user_data(args.mount, user_id, args.dashboard)
        if changed:
            print(f"Wrote defaultPanel={args.dashboard!r} to {path.name}")
        else:
            print(f"defaultPanel already {args.dashboard!r} in {path.name} — nothing to do")
            return 0
    finally:
        unmount(args.mount)

    if args.restart_ha:
        print("Restarting Home Assistant so the cached user settings reload…")
        await restart_ha(token, args.ha_url)
        print("Restart requested — HA back in ~60–120s.")
    else:
        print(
            "NOTE: if this user has already used HA since last restart, restart HA "
            "(or re-run with --restart-ha) so the new default takes effect."
        )
    print(
        f"Done. When {args.user!r} opens Home Assistant it will land on "
        f"/{args.dashboard}/ by default."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", required=True, help="HA user display name or login (e.g. smarthome)")
    parser.add_argument(
        "--dashboard",
        default="flux-ui-tablet",
        help="Dashboard url_path to set as the user's default (default: flux-ui-tablet)",
    )
    parser.add_argument(
        "--restart-ha",
        action="store_true",
        help="Restart HA after writing so cached user settings reload",
    )
    args = parser.parse_args()
    return run_async(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deploy garage_doors_pulse package to HA and sync Tapo sensor state."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "flux-ui-dashboard" / "scripts"))

from ha_common import (  # noqa: E402
    DEFAULT_HA,
    DEFAULT_HOST,
    DEFAULT_MOUNT,
    get_token,
    ha_reachable,
    mount_config,
    run_async,
    unmount,
)
from ha_common import get_samba_creds  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = ROOT / "packages" / "garage_doors_pulse.yaml"
SYNC = ROOT / "scripts" / "sync_garage_state_from_sensors.py"


def ha_post(token: str, ha_url: str, service: str) -> None:
    req = urllib.request.Request(
        f"{ha_url}/api/services/{service.replace('.', '/')}",
        data=b"{}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req):
        pass


async def deploy_async(args: argparse.Namespace) -> int:
    if not PKG_SRC.exists():
        print(f"Missing package: {PKG_SRC}", file=sys.stderr)
        return 1

    token: str | None = None
    if not args.offline:
        try:
            token = get_token(args.token)
        except RuntimeError as exc:
            if args.offline_ok:
                print(f"{exc} — skipping live garage deploy.")
                return 0
            raise

    if args.offline or not token:
        print("Offline: garage package not copied (needs HA token + LAN).")
        return 0

    ha_up = await ha_reachable(args.ha_url, token)
    if not ha_up:
        msg = f"HA unreachable at {args.ha_url}"
        if args.offline_ok:
            print(f"{msg} — skipping garage deploy.")
            return 0
        print(msg, file=sys.stderr)
        return 2

    mounted = False
    try:
        user, pw = await get_samba_creds(token, args.ha_url)
        mounted = mount_config(args.host, user, pw, args.mount)
        if not mounted:
            print("SMB mount failed", file=sys.stderr)
            return 3

        dest = Path(args.mount) / "packages" / "garage_doors_pulse.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PKG_SRC, dest)
        print(f"Copied package to {dest}")
    finally:
        if mounted:
            unmount(args.mount)

    print("Reloading scripts, automations, input_boolean...")
    for svc in ("script.reload", "automation.reload", "input_boolean.reload"):
        ha_post(token, args.ha_url, svc)

    sync = subprocess.run(
        ["python3", str(SYNC), "--ha-url", args.ha_url, "--token", token],
        check=False,
    )
    if sync.returncode != 0:
        print("Warning: sensor sync had errors (dashboard deploy can continue).")
    print("Garage doors pulse package deployed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--offline-ok", action="store_true")
    args = parser.parse_args()
    return run_async(deploy_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

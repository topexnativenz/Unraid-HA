#!/usr/bin/env python3
"""Push HA config files (packages, www, themes) when SMB mount is unavailable from cloud."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import (  # noqa: E402
    DEFAULT_HA,
    DEFAULT_HOST,
    DEFAULT_MOUNT,
    ensure_ha_env,
    get_samba_creds,
    get_token,
    host_reachable,
    mount_config,
    run_async,
    ssh_configured,
    unmount,
)

ROOT = Path(__file__).resolve().parents[1]
GARAGE_PKG = ROOT.parent / "garage-doors" / "packages" / "garage_doors_pulse.yaml"


def _package_sources() -> list[Path]:
    src = ROOT / "packages"
    files = sorted(src.glob("*.yaml")) if src.exists() else []
    if GARAGE_PKG.exists():
        files.append(GARAGE_PKG)
    return files


def _ssh_base_args() -> list[str]:
    ensure_ha_env()
    host = os.environ["HA_SSH_HOST"]
    user = os.environ["HA_SSH_USER"]
    port = os.environ.get("HA_SSH_PORT", "22")
    args = ["ssh", "-p", port, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
    key = os.environ.get("HA_SSH_KEY_PATH")
    if key:
        args.extend(["-i", key])
    args.append(f"{user}@{host}")
    return args


def push_via_ssh(files: list[tuple[Path, str]]) -> bool:
    """Copy files to /config/... via scp + ssh (Tailscale / SSH add-on)."""
    if not ssh_configured():
        return False
    ensure_ha_env()
    host = os.environ["HA_SSH_HOST"]
    user = os.environ["HA_SSH_USER"]
    port = os.environ.get("HA_SSH_PORT", "22")
    if not host_reachable(host, port=int(port)):
        print(f"  SSH host {host}:{port} unreachable — skipping SSH push")
        return False

    scp_base = ["scp", "-P", port, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
    key = os.environ.get("HA_SSH_KEY_PATH")
    if key:
        scp_base.extend(["-i", key])

    remote_dirs: set[str] = set()
    for _, rel in files:
        remote_dirs.add(str(Path("/config") / rel).rsplit("/", 1)[0])

    for remote_dir in sorted(remote_dirs):
        res = subprocess.run(
            _ssh_base_args() + [f"mkdir -p {remote_dir}"],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            print(f"  SSH mkdir failed for {remote_dir}: {res.stderr.strip()}")
            return False

    for src, rel in files:
        remote = f"{user}@{host}:/config/{rel}"
        res = subprocess.run([*scp_base, str(src), remote], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  scp failed for {rel}: {res.stderr.strip()}")
            return False
        print(f"  pushed /config/{rel} via SSH")

    return True


def push_via_smb(
    token: str,
    ha_url: str,
    host: str,
    mount: str,
    files: list[tuple[Path, str]],
) -> bool:
    if not host_reachable(host, port=445):
        print(f"  SMB host {host}:445 unreachable — skipping SMB push")
        return False

    mounted = False
    try:
        user, pw = run_async(get_samba_creds(token, ha_url))
        mounted = mount_config(host, user, pw, mount)
        if not mounted:
            print("  SMB mount failed")
            return False

        for src, rel in files:
            dest = Path(mount) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"  copied /config/{rel} via SMB")
        copy_www_and_theme(mount)
        return True
    except Exception as exc:
        print(f"  SMB push failed: {exc}")
        return False
    finally:
        if mounted:
            unmount(mount)


def copy_www_and_theme(mount: str) -> None:
    """Copy bundled frontend assets and theme when SMB mount is active."""
    src_community = ROOT / "www" / "community"
    if src_community.exists():
        for item in src_community.iterdir():
            if not item.is_dir():
                continue
            dst = Path(mount) / "www" / "community" / item.name
            dst.mkdir(parents=True, exist_ok=True)
            for js in item.glob("*.js"):
                shutil.copy2(js, dst / js.name)
                print(f"  copied www/community/{item.name}/{js.name}")

    src_flux = ROOT / "www" / "flux-ui"
    if src_flux.exists():
        for f in src_flux.rglob("*"):
            if f.is_file():
                rel = f.relative_to(src_flux)
                target = Path(mount) / "www" / "flux-ui" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
                print(f"  copied www/flux-ui/{rel}")

    theme_src = ROOT / "themes" / "flux-ui-md3.yaml"
    if theme_src.exists():
        theme_dst = Path(mount) / "themes" / "flux-ui-md3.yaml"
        theme_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(theme_src, theme_dst)
        print("  copied themes/flux-ui-md3.yaml")


def build_www_file_list() -> list[tuple[Path, str]]:
    """Frontend static assets under /config/www (served as /local/...)."""
    files: list[tuple[Path, str]] = []
    src_flux = ROOT / "www" / "flux-ui"
    if src_flux.exists():
        for f in src_flux.rglob("*"):
            if f.is_file():
                rel = f.relative_to(src_flux)
                files.append((f, f"www/flux-ui/{rel.as_posix()}"))
    theme_src = ROOT / "themes" / "flux-ui-md3.yaml"
    if theme_src.exists():
        files.append((theme_src, "themes/flux-ui-md3.yaml"))
    return files


def build_file_list(*, include_garage: bool) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    pkg_dir = ROOT / "packages"
    if pkg_dir.exists():
        for pkg in sorted(pkg_dir.glob("*.yaml")):
            files.append((pkg, f"packages/{pkg.name}"))
    if include_garage and GARAGE_PKG.exists():
        files.append((GARAGE_PKG, "packages/garage_doors_pulse.yaml"))
    return files


async def push_async(args: argparse.Namespace) -> int:
    ensure_ha_env()
    token = get_token(args.token)
    files = build_file_list(include_garage=args.include_garage)
    www_files = build_www_file_list()
    if not files and not www_files:
        print("No package or www files to push.")
        return 0

    print(f"Pushing {len(files)} package file(s) + {len(www_files)} www asset(s) to Home Assistant…")

    if push_via_smb(token, args.ha_url, args.host, args.mount, files):
        print("Package push complete (SMB).")
        return 0

    if push_via_ssh(files + www_files):
        print("Package + www push complete (SSH).")
        return 0

    print(
        "WARNING: Could not push packages (SMB/SSH unreachable from this machine).\n"
        "  Lovelace dashboard can still deploy via HA API.\n"
        "  For full E2E from cloud, set HA_SSH_HOST + HA_SSH_USER (Tailscale SSH)\n"
        "  or HA_HOST to a LAN/Tailscale IP reachable from this session."
    )
    return 1 if args.require_push else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Push HA packages/www/themes to /config")
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--include-garage", action="store_true", default=True)
    parser.add_argument(
        "--require-push",
        action="store_true",
        help="Exit 1 if neither SMB nor SSH push succeeded",
    )
    args = parser.parse_args()
    return run_async(push_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

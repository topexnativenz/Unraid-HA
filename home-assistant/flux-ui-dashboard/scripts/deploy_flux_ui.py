#!/usr/bin/env python3
"""Deploy Flux UI dashboard in parallel with Mobile Home (does not modify mobile-home)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import (
    DEFAULT_HA,
    DEFAULT_HOST,
    DEFAULT_MOUNT,
    get_samba_creds,
    get_token,
    ha_reachable,
    mount_config,
    run_async,
    unmount,
    ws_call,
)

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_flux_ui.py"
INSTALL = ROOT / "scripts" / "install_dependencies.py"
ASSETS = ROOT / "scripts" / "install_frontend_assets.py"
VERIFY = ROOT / "scripts" / "verify_flux_ui.py"
URL_PATH = "flux-ui"
STORAGE_KEY = "lovelace.flux_ui"
MOBILE_STORAGE = "lovelace.mobile_home"


def copy_theme(mount: str) -> None:
    dst = Path(mount) / "themes" / "flux-ui-md3.yaml"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "themes" / "flux-ui-md3.yaml", dst)
    conf = Path(mount) / "configuration.yaml"
    if conf.exists():
        text = conf.read_text()
        if "flux-ui-md3.yaml" not in text and "themes:" not in text:
            conf.write_text(
                text.rstrip() + "\n\nfrontend:\n  themes: !include_dir_merge_named themes\n"
            )


def copy_frontend_assets(mount: str) -> None:
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
        dst_flux = Path(mount) / "www" / "flux-ui"
        for f in src_flux.rglob("*"):
            if f.is_file():
                rel = f.relative_to(src_flux)
                target = dst_flux / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
                print(f"  copied www/flux-ui/{rel}")


def write_storage(mount: str, config: dict) -> None:
    storage_dir = Path(mount) / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"config": config},
    }
    (storage_dir / STORAGE_KEY).write_text(json.dumps(payload, indent=2))
    print(f"  wrote .storage/{STORAGE_KEY}")

    dashboards_file = storage_dir / "lovelace_dashboards"
    if dashboards_file.exists():
        raw = json.loads(dashboards_file.read_text())
        items = raw.get("data", {}).get("items", [])
        if not any(i.get("url_path") == URL_PATH for i in items):
            items.append(
                {
                    "id": "flux_ui",
                    "show_in_sidebar": True,
                    "icon": "mdi:view-dashboard-variant",
                    "title": "Flux UI",
                    "require_admin": False,
                    "mode": "storage",
                    "url_path": URL_PATH,
                }
            )
            raw["data"]["items"] = items
            dashboards_file.write_text(json.dumps(raw, indent=2))
            print("  registered flux-ui in lovelace_dashboards")


async def has_navbar_resource(token: str, ha_url: str) -> bool:
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]
    urls = " ".join(r.get("url", "") for r in listed.get("result", []))
    return "navbar-card" in urls or "lovelace-navbar-card" in urls


async def has_kiosk_resource(token: str, ha_url: str) -> bool:
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]
    urls = " ".join(r.get("url", "") for r in listed.get("result", []))
    return "kiosk-mode" in urls


def build_config(
    mobile_storage: Path | None,
    *,
    use_navbar_card: bool = True,
    use_kiosk: bool = True,
) -> dict:
    out = ROOT / "generated" / "lovelace.flux_ui.json"
    cmd = ["python3", str(BUILD), "--output", str(out)]
    if mobile_storage and mobile_storage.exists():
        cmd.extend(["--mobile-home-storage", str(mobile_storage)])
    if not use_navbar_card:
        cmd.append("--no-navbar-card")
    if not use_kiosk:
        cmd.append("--no-kiosk")
    subprocess.run(cmd, check=True)
    raw = json.loads(out.read_text())
    config = raw["data"]["config"]
    sections = len(config["views"][0].get("sections", []))
    if sections != 5:
        print(
            f"\nERROR: Built {sections} sections — MD3 requires 5.\n"
            "Your repo is stale (git pull likely failed). Run:\n"
            "  bash home-assistant/flux-ui-dashboard/scripts/update_and_deploy.sh\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if "flux_greeting" not in json.dumps(config) and "flux_hero" not in json.dumps(config):
        print(
            "\nERROR: Build missing MD3 button-card templates.\n"
            "Pull latest: git stash && git pull origin cursor/flux-ui-md3-dashboard-bf3a\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return config


async def save_dashboard(token: str, ha_url: str, config: dict) -> None:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": URL_PATH, "config": config}],
    )
    if not res[0].get("success"):
        raise RuntimeError(f"lovelace/config/save failed: {res[0].get('error')}")

    verify = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config", "url_path": URL_PATH, "force": True}],
    )
    views = verify[0]["result"]["views"]
    sections = views[0].get("sections", [])
    print(f"Live flux-ui: {[(v['title'], v['path']) for v in views]} sections={len(sections)}")


async def deploy_async(args: argparse.Namespace) -> int:
    token: str | None = None
    if not args.offline:
        try:
            token = get_token(args.token)
        except RuntimeError as exc:
            if args.offline_ok:
                print(f"{exc} — continuing build-only.")
            else:
                raise

    ha_up = False
    if token and not args.offline:
        ha_up = await ha_reachable(args.ha_url, token)
        if ha_up:
            print(f"HA reachable at {args.ha_url}")
        else:
            print(f"HA unreachable at {args.ha_url}")
            if not args.offline_ok:
                print("Use --offline-ok to build only, or set HA_URL / HA_TOKEN.")
                return 2

    if not args.skip_assets:
        subprocess.run(["python3", str(ASSETS)], check=True)

    mobile_storage: Path | None = None
    mounted = False

    if not args.skip_mount and ha_up:
        try:
            user, pw = await get_samba_creds(token, args.ha_url)
            mounted = mount_config(args.host, user, pw, args.mount)
            if mounted:
                copy_theme(args.mount)
                copy_frontend_assets(args.mount)
                mobile_storage = Path(args.mount) / ".storage" / MOBILE_STORAGE
                if not mobile_storage.exists():
                    mobile_storage = None
                    print("Mobile Home storage not found; using climate fallback")
            else:
                print("SMB mount failed; using climate fallback")
        except Exception as exc:
            print(f"SMB skipped ({exc}); using climate fallback")
    elif not args.skip_mount and not ha_up:
        print("SMB skipped (HA offline — cannot fetch Samba credentials)")

    use_navbar = False
    use_kiosk = False
    if token and ha_up:
        try:
            use_navbar = await has_navbar_resource(token, args.ha_url)
            use_kiosk = await has_kiosk_resource(token, args.ha_url)
            if not use_navbar:
                print(
                    "navbar-card not installed — using mushroom chip nav fallback.\n"
                    "  HACS → joseluis9595/lovelace-navbar-card for Flux pill nav."
                )
            if not use_kiosk:
                print(
                    "kiosk-mode not installed — HA header will stay visible on mobile.\n"
                    "  HACS → maykar/kiosk-mode then redeploy."
                )
        except Exception:
            use_navbar = False
            use_kiosk = False

    config = build_config(
        mobile_storage,
        use_navbar_card=use_navbar,
        use_kiosk=use_kiosk,
    )

    if mounted:
        write_storage(args.mount, config)

    subprocess.run(["python3", str(VERIFY)], check=True)

    if args.offline or not ha_up:
        if mounted:
            print("Offline deploy: storage + theme + www copied to HA config share.")
            print("Restart HA or reload frontend, then open /flux-ui/overview")
        else:
            print("Offline deploy: build verified. Re-run setup_e2e.sh when on your LAN with HA_TOKEN.")
        if mounted:
            unmount(args.mount)
        return 0

    assert token is not None

    subprocess.run(
        ["python3", str(INSTALL), "--ha-url", args.ha_url, "--token", token],
        check=True,
    )
    await save_dashboard(token, args.ha_url, config)

    subprocess.run(
        ["python3", str(VERIFY), "--live", "--ha-url", args.ha_url, "--token", token],
        check=True,
    )

    if mounted:
        unmount(args.mount)

    print(f"Flux UI deployed at {args.ha_url}/{URL_PATH}/overview")
    print("Mobile Home unchanged. Profile → theme: flux-ui-md3 (optional).")
    print("Hard-refresh browser (Cmd+Shift+R) if cards still look like Mushroom.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--mount", default=DEFAULT_MOUNT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--skip-mount", action="store_true")
    parser.add_argument("--skip-assets", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Never push to HA API")
    parser.add_argument(
        "--offline-ok",
        action="store_true",
        help="If HA unreachable, still copy to SMB and exit 0",
    )
    args = parser.parse_args()
    return run_async(deploy_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

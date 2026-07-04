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


async def has_resource(token: str, ha_url: str, needle: str) -> bool:
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/resources"}]))[0]
    urls = " ".join(r.get("url", "") for r in listed.get("result", []))
    return needle in urls


async def has_navbar_resource(token: str, ha_url: str) -> bool:
    return await has_resource(token, ha_url, "navbar-card") or await has_resource(
        token, ha_url, "lovelace-navbar-card"
    )


async def has_kiosk_resource(token: str, ha_url: str) -> bool:
    return await has_resource(token, ha_url, "kiosk-mode") or await has_resource(
        token, ha_url, "kiosk_mode"
    )


async def ensure_frontend_resources(token: str, ha_url: str) -> None:
    """Register Lovelace JS modules before building (HACS download ≠ resource registered)."""
    print("Registering Lovelace frontend resources (navbar, kiosk-mode, …)")
    subprocess.run(
        ["python3", str(INSTALL), "--ha-url", ha_url, "--token", token],
        check=True,
    )


def build_config(
    mobile_storage: Path | None,
    *,
    use_navbar_card: bool = True,
    use_kiosk: bool = True,
    use_auto_entities: bool = True,
) -> dict:
    out = ROOT / "generated" / "lovelace.flux_ui.json"
    cmd = ["python3", str(BUILD), "--output", str(out)]
    if mobile_storage and mobile_storage.exists():
        cmd.extend(["--mobile-home-storage", str(mobile_storage)])
    if not use_navbar_card:
        cmd.append("--no-navbar-card")
    if not use_kiosk:
        cmd.append("--no-kiosk")
    if not use_auto_entities:
        cmd.append("--no-auto-entities")
    subprocess.run(cmd, check=True)
    raw = json.loads(out.read_text())
    config = raw["data"]["config"]
    blob = json.dumps(config)
    overview = next((v for v in config["views"] if v.get("path") == "overview"), config["views"][0])
    sections = len(overview.get("sections", []))
    if sections < 6:
        print(
            f"\nERROR: Built {sections} overview sections — Phase 3 expects at least 6.\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if "flux_hero" not in blob:
        print("\nERROR: Build missing flux_hero.", file=sys.stderr)
        raise SystemExit(1)
    if "Home status" not in blob:
        print("\nERROR: Build missing Phase 3 home status section.", file=sys.stderr)
        raise SystemExit(1)
    if use_kiosk and "kiosk_mode" not in config:
        print("\nERROR: Build missing kiosk_mode block.", file=sys.stderr)
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
    overview = next((v for v in views if v.get("path") == "overview"), views[0])
    sections = overview.get("sections", [])
    has_kiosk = "kiosk_mode" in verify[0]["result"]
    phase3 = "auto-entities" in json.dumps(verify[0]["result"]) and '"template": "flux_light"' in json.dumps(
        verify[0]["result"]
    )
    print(
        f"Live flux-ui: {[(v['title'], v['path']) for v in views]} "
        f"overview_sections={len(sections)} kiosk={has_kiosk} phase3={phase3}"
    )


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

    # Register HACS frontend modules BEFORE build (kiosk-mode must be a Lovelace resource).
    if token and ha_up and not args.offline:
        await ensure_frontend_resources(token, args.ha_url)

    use_navbar = False
    use_kiosk = True
    use_auto_entities = True
    if token and ha_up:
        try:
            use_navbar = await has_navbar_resource(token, args.ha_url)
            use_kiosk = await has_kiosk_resource(token, args.ha_url) or True
            use_auto_entities = await has_resource(token, args.ha_url, "auto-entities")
            if not use_navbar:
                print("navbar-card not in resources — mushroom chip nav fallback.")
            if not use_auto_entities:
                print("auto-entities not in resources — skipping Active now section.")
                print("  HACS → thomasloven/lovelace-auto-entities")
            if not await has_kiosk_resource(token, args.ha_url):
                print("WARNING: kiosk-mode resource missing (config still embedded).")
        except Exception:
            use_navbar = False
            use_auto_entities = True
            use_kiosk = True

    config = build_config(
        mobile_storage,
        use_navbar_card=use_navbar,
        use_kiosk=use_kiosk,
        use_auto_entities=use_auto_entities,
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

    await save_dashboard(token, args.ha_url, config)

    subprocess.run(
        ["python3", str(VERIFY), "--live", "--ha-url", args.ha_url, "--token", token],
        check=True,
    )

    if mounted:
        unmount(args.mount)

    print(f"Flux UI deployed at {args.ha_url}/{URL_PATH}/overview")
    print("Kiosk mode: mobile header hidden on Flux UI (swipe left for sidebar, More → Profile).")
    print("Hard-refresh or reset Companion frontend cache if header still visible.")
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

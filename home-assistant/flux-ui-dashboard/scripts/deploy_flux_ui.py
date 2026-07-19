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
GARAGE_DIR = ROOT.parent / "garage-doors"
BUILD = ROOT / "scripts" / "build_flux_ui.py"
DISCOVER_ROOMS = ROOT / "scripts" / "discover_room_sensors.py"
DISCOVER_CALENDARS = ROOT / "scripts" / "discover_calendars.py"
INSTALL = ROOT / "scripts" / "install_dependencies.py"
ASSETS = ROOT / "scripts" / "install_frontend_assets.py"
VERIFY = ROOT / "scripts" / "verify_flux_ui.py"
URL_PATH = "flux-ui"
STORAGE_KEY = "lovelace.flux_ui"
MOBILE_STORAGE = "lovelace.mobile_home"

# 16:9 landscape (wall tablet) variant — same functions, 3-column sections.
TABLET_URL_PATH = "flux-ui-tablet"
TABLET_STORAGE_KEY = "lovelace.flux_ui_tablet"
TABLET_TITLE = "Flux UI 16:9"
TABLET_DASHBOARD_ID = "flux_ui_tablet"


def copy_packages(mount: str) -> None:
    src = ROOT / "packages"
    if not src.exists():
        return
    dst_root = Path(mount) / "packages"
    dst_root.mkdir(parents=True, exist_ok=True)
    for pkg in src.glob("*.yaml"):
        shutil.copy2(pkg, dst_root / pkg.name)
        print(f"  copied packages/{pkg.name}")
    ensure_packages_in_configuration(mount)


def ensure_packages_in_configuration(mount: str) -> None:
    """Ensure HA loads /config/packages/*.yaml (input_select tab helper)."""
    conf = Path(mount) / "configuration.yaml"
    if not conf.exists():
        return
    text = conf.read_text()
    if "include_dir_named packages" in text or "include_dir_merge_named packages" in text:
        return
    block = "\nhomeassistant:\n  packages: !include_dir_named packages\n"
    if "homeassistant:" in text:
        text = text.replace("homeassistant:", "homeassistant:\n  packages: !include_dir_named packages", 1)
    else:
        text = text.rstrip() + block
    conf.write_text(text)
    print("  added homeassistant.packages to configuration.yaml")


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

    _register_dashboard(
        storage_dir,
        dashboard_id="flux_ui",
        url_path=URL_PATH,
        title="Flux UI",
        icon="mdi:view-dashboard-variant",
    )


def write_tablet_storage(mount: str, config: dict) -> None:
    storage_dir = Path(mount) / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": 1,
        "minor_version": 1,
        "key": TABLET_STORAGE_KEY,
        "data": {"config": config},
    }
    (storage_dir / TABLET_STORAGE_KEY).write_text(json.dumps(payload, indent=2))
    print(f"  wrote .storage/{TABLET_STORAGE_KEY}")

    _register_dashboard(
        storage_dir,
        dashboard_id=TABLET_DASHBOARD_ID,
        url_path=TABLET_URL_PATH,
        title=TABLET_TITLE,
        icon="mdi:tablet-dashboard",
    )


def _register_dashboard(
    storage_dir: Path, *, dashboard_id: str, url_path: str, title: str, icon: str
) -> None:
    dashboards_file = storage_dir / "lovelace_dashboards"
    if dashboards_file.exists():
        raw = json.loads(dashboards_file.read_text())
        items = raw.get("data", {}).get("items", [])
        if not any(i.get("url_path") == url_path for i in items):
            items.append(
                {
                    "id": dashboard_id,
                    "show_in_sidebar": True,
                    "icon": icon,
                    "title": title,
                    "require_admin": False,
                    "mode": "storage",
                    "url_path": url_path,
                }
            )
            raw["data"]["items"] = items
            dashboards_file.write_text(json.dumps(raw, indent=2))
            print(f"  registered {url_path} in lovelace_dashboards")


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


def overview_tab_usage(config: dict) -> dict[str, bool]:
    from flux_overview_tabs import overview_tab_usage as _usage

    return _usage(config)


def config_fingerprint(config: dict) -> dict[str, object]:
    usage = overview_tab_usage(config)
    overview = next((v for v in config.get("views", []) if v.get("path") == "overview"), {})
    engine = "simple-tabs" if usage["has_simple_tabs"] else ("native-v2" if usage["has_native_tabs"] else "none")
    return {
        "tab_layout": engine,
        "has_native_tabs": usage["has_native_tabs"],
        "has_simple_tabs": usage["has_simple_tabs"],
        "has_input_select": OVERVIEW_TAB_ENTITY in json.dumps(config),
        "overview_sections": len(overview.get("sections") or []),
        "quick_actions_grid": "Quick Actions" in json.dumps(overview)
        and '"columns": 2' in json.dumps(overview),
    }


OVERVIEW_TAB_ENTITY = "input_select.flux_ui_overview_tab"
ROOMS_TAB_ENTITY = "input_select.flux_ui_rooms_tab"


def print_fingerprint(config: dict, *, label: str) -> None:
    fp = config_fingerprint(config)
    print(f"  {label}: tab_layout={fp['tab_layout']} "
          f"native={fp['has_native_tabs']} simple-tabs={fp['has_simple_tabs']} "
          f"sections={fp['overview_sections']}")


async def reload_core_config(token: str, ha_url: str) -> None:
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
    if res[0].get("success") is False:
        print(f"  WARNING: reload_core_config failed: {res[0].get('error')}")
    else:
        print("  reloaded HA core config (packages/input_select)")


async def wait_for_entity(token: str, ha_url: str, entity_id: str, *, attempts: int = 5) -> bool:
    import asyncio

    for i in range(attempts):
        if await entity_exists(token, ha_url, entity_id):
            return True
        if i < attempts - 1:
            await asyncio.sleep(2)
    return False


async def entity_exists(token: str, ha_url: str, entity_id: str) -> bool:
    res = await ws_call(token, ha_url, [{"type": "get_states"}])
    if not res[0].get("success"):
        return False
    return any(s.get("entity_id") == entity_id for s in res[0].get("result", []))


def build_config(
    mobile_storage: Path | None,
    *,
    use_navbar_card: bool = True,
    use_kiosk: bool = True,
    use_auto_entities: bool = True,
    use_simple_tabs: bool = True,
    use_calendar_pro: bool = True,
    tablet: bool = False,
) -> dict:
    out = ROOT / "generated" / ("lovelace.flux_ui_tablet.json" if tablet else "lovelace.flux_ui.json")
    cmd = ["python3", str(BUILD), "--output", str(out)]
    if tablet:
        cmd.append("--tablet")
    if mobile_storage and mobile_storage.exists():
        cmd.extend(["--mobile-home-storage", str(mobile_storage)])
    if not use_navbar_card:
        cmd.append("--no-navbar-card")
    if not use_kiosk:
        cmd.append("--no-kiosk")
    if not use_auto_entities:
        cmd.append("--no-auto-entities")
    if not use_calendar_pro:
        cmd.append("--no-calendar-pro")
    subprocess.run(cmd, check=True)
    raw = json.loads(out.read_text())
    config = raw["data"]["config"]
    blob = json.dumps(config)
    overview = next((v for v in config["views"] if v.get("path") == "overview"), config["views"][0])

    if tablet:
        if overview.get("type") != "sections":
            print(
                "\nERROR: Tablet overview must be sections + layout-card "
                "(view-type grid-layout renders blank with navbar-only).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        sections = overview.get("sections") or []
        if len(sections) < 2:
            print(
                f"\nERROR: Tablet overview has {len(sections)} sections — "
                "expected layout-card section + navbar.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        for needle in (
            "custom:layout-card",
            "custom:grid-layout",
            "custom:navbar-card",
            "custom:simple-tabs",
            "weather-forecast",
            "history-graph",
            "/flux-ui-tablet/overview",
            '"template": "flux_room"',
            "room_selector",
            "calendar_notification",
            "simple_tab",
            '"column_span": 4',
        ):
            if needle not in blob:
                print(f"\nERROR: Tablet build missing {needle}.", file=sys.stderr)
                raise SystemExit(1)
        if "flux_hero" not in blob:
            print("\nERROR: Tablet build missing flux_hero greeting.", file=sys.stderr)
            raise SystemExit(1)
        if use_kiosk and "kiosk_mode" not in config:
            print("\nERROR: Build missing kiosk_mode block.", file=sys.stderr)
            raise SystemExit(1)
        print(
            f"Built tablet config: sections+layout-card overview, "
            f"{len(sections)} sections, {len(config['views'])} views"
        )
        return config

    sections = len(overview.get("sections", []))
    usage = overview_tab_usage(config)
    min_sections = 3 if usage["has_simple_tabs"] or usage["has_native_tabs"] else 6
    if sections < min_sections:
        print(
            f"\nERROR: Built {sections} overview sections — expected at least {min_sections}.\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if "flux_hero" not in blob:
        print("\nERROR: Build missing flux_hero.", file=sys.stderr)
        raise SystemExit(1)
    if "Home status" not in blob:
        print("\nERROR: Build missing Phase 3 home status section.", file=sys.stderr)
        raise SystemExit(1)
    has_tabs = usage["has_simple_tabs"] or usage["has_native_tabs"]
    if not has_tabs:
        print("\nERROR: Build missing ElementZoom overview tabs.", file=sys.stderr)
        raise SystemExit(1)
    if use_kiosk and "kiosk_mode" not in config:
        print("\nERROR: Build missing kiosk_mode block.", file=sys.stderr)
        raise SystemExit(1)
    fp = config_fingerprint(config)
    if not fp["has_native_tabs"] and not fp["has_simple_tabs"]:
        print("\nERROR: Built config missing overview tabs.", file=sys.stderr)
        raise SystemExit(1)
    label = "Built config (simple-tabs)" if fp["has_simple_tabs"] else "Built config (native)"
    print_fingerprint(config, label=label)
    return config


async def ensure_tablet_dashboard(token: str, ha_url: str) -> None:
    """Create the 16:9 dashboard entry live (sidebar shows without restart)."""
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/dashboards/list"}]))[0]
    items = listed.get("result") or []
    if any(d.get("url_path") == TABLET_URL_PATH for d in items):
        return
    res = await ws_call(
        token,
        ha_url,
        [
            {
                "type": "lovelace/dashboards/create",
                "url_path": TABLET_URL_PATH,
                "title": TABLET_TITLE,
                "icon": "mdi:tablet-dashboard",
                "show_in_sidebar": True,
                "require_admin": False,
                "mode": "storage",
            }
        ],
    )
    if not res[0].get("success"):
        raise RuntimeError(f"Could not create {TABLET_URL_PATH} dashboard: {res[0].get('error')}")
    print(f"  created dashboard {TABLET_URL_PATH} ({TABLET_TITLE})")


async def save_dashboard(token: str, ha_url: str, config: dict, *, url_path: str = URL_PATH) -> None:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": url_path, "config": config}],
    )
    if not res[0].get("success"):
        raise RuntimeError(f"lovelace/config/save failed: {res[0].get('error')}")

    verify = await ws_call(
        token,
        ha_url,
        [{"type": "lovelace/config", "url_path": url_path, "force": True}],
    )
    if not verify[0].get("success"):
        raise RuntimeError(f"Could not verify saved {url_path} config: {verify[0].get('error')}")

    if url_path != URL_PATH:
        views = verify[0]["result"].get("views", [])
        cols = {v.get("max_columns") for v in views}
        print(f"Live {url_path}: {len(views)} views, max_columns={sorted(c for c in cols if c)}")
        return

    live_config = verify[0]["result"]
    usage = overview_tab_usage(live_config)
    views = live_config.get("views", [])
    overview = next((v for v in views if v.get("path") == "overview"), views[0])
    sections = overview.get("sections", [])
    has_kiosk = "kiosk_mode" in live_config
    live_blob = json.dumps(live_config)
    phase3 = "auto-entities" in live_blob and '"template": "flux_light"' in live_blob
    print(
        f"Live flux-ui: {[(v['title'], v['path']) for v in views]} "
        f"overview_sections={len(sections)} kiosk={has_kiosk} phase3={phase3}"
    )
    print_fingerprint(live_config, label="Live config")

    if not usage["has_simple_tabs"] and not usage["has_native_tabs"]:
        raise RuntimeError(
            "Live flux-ui missing overview tabs (expected custom:simple-tabs or native tab bar)."
        )
    if usage["has_simple_tabs"]:
        print("  Live tabs engine: simple-tabs (ElementZoom)")
    elif usage["has_native_tabs"]:
        print("  Live tabs engine: native")
    if "_flux_ui" in live_blob:
        raise RuntimeError("Live config contains invalid _flux_ui key — rebuild and redeploy.")


async def deploy_async(args: argparse.Namespace) -> int:
    try:
        git_head = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT.parent.parent)
            .decode()
            .strip()
        )
        git_branch = (
            subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT.parent.parent)
            .decode()
            .strip()
        )
        print(f"Deploy source: {git_branch} @ {git_head}")
    except Exception:
        pass

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
                copy_packages(args.mount)
                copy_frontend_assets(args.mount)
                if token and ha_up and not args.offline:
                    await reload_core_config(token, args.ha_url)
                    if await wait_for_entity(token, args.ha_url, OVERVIEW_TAB_ENTITY):
                        print(f"  loaded {OVERVIEW_TAB_ENTITY}")
                    else:
                        print(
                            f"  NOTE: {OVERVIEW_TAB_ENTITY} not loaded (OK when using simple-tabs engine). "
                            "Native tab fallback needs packages in configuration.yaml."
                        )
                    if await wait_for_entity(token, args.ha_url, ROOMS_TAB_ENTITY):
                        print(f"  loaded {ROOMS_TAB_ENTITY}")
                    else:
                        print(
                            f"  NOTE: {ROOMS_TAB_ENTITY} not loaded — Rooms category tabs need "
                            "packages/flux_ui_rooms.yaml in configuration.yaml."
                        )
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
    use_simple_tabs = True
    use_calendar_pro = True
    if token and ha_up:
        try:
            use_navbar = await has_navbar_resource(token, args.ha_url)
            use_kiosk = await has_kiosk_resource(token, args.ha_url) or True
            use_auto_entities = await has_resource(token, args.ha_url, "auto-entities")
            use_simple_tabs = await has_resource(token, args.ha_url, "simple-tabs")
            use_calendar_pro = await has_resource(token, args.ha_url, "calendar-card-pro")
            if not use_navbar:
                print("navbar-card not in resources — mushroom chip nav fallback.")
            if not use_auto_entities:
                print("auto-entities not in resources — Active tab will omit live lights.")
                print("  HACS → thomasloven/lovelace-auto-entities")
            if not use_simple_tabs:
                print("simple-tabs not in resources — using native full-width tab bar (default).")
                print("  Optional HACS → agoberg85/home-assistant-simple-tabs for swipe tabs")
            if not use_calendar_pro:
                print("calendar-card-pro not in resources — Events tab uses mushroom fallback.")
                print("  HACS → alexpfau/calendar-card-pro (ElementZoom reference)")
            if not await has_kiosk_resource(token, args.ha_url):
                print("WARNING: kiosk-mode resource missing (config still embedded).")
        except Exception:
            use_navbar = False
            use_auto_entities = True
            use_kiosk = True
            use_simple_tabs = True
            use_calendar_pro = True

    if ha_up and token and not args.offline:
        print("Discovering Tapo garage/shed door sensors…")
        subprocess.run(
            [
                "python3",
                str(GARAGE_DIR / "scripts" / "discover_garage_doors.py"),
                "--ha-url",
                args.ha_url,
                "--token",
                token,
                "--apply",
            ],
            check=False,
        )
        print("Discovering Tapo / climate sensors for room cards…")
        subprocess.run(
            ["python3", str(DISCOVER_ROOMS), "--ha-url", args.ha_url, "--token", token],
            check=False,
        )
        print("Discovering Whanau calendar for Events tab…")
        subprocess.run(
            [
                "python3",
                str(DISCOVER_CALENDARS),
                "--ha-url",
                args.ha_url,
                "--token",
                token,
                "--apply",
            ],
            check=False,
        )

    config = build_config(
        mobile_storage,
        use_navbar_card=use_navbar,
        use_kiosk=use_kiosk,
        use_auto_entities=use_auto_entities,
        use_simple_tabs=use_simple_tabs,
        use_calendar_pro=use_calendar_pro,
    )

    tablet_config: dict | None = None
    if not args.skip_tablet:
        print("Building Flux UI 16:9 tablet variant…")
        tablet_config = build_config(
            mobile_storage,
            use_navbar_card=use_navbar,
            use_kiosk=use_kiosk,
            use_auto_entities=use_auto_entities,
            use_simple_tabs=use_simple_tabs,
            use_calendar_pro=use_calendar_pro,
            tablet=True,
        )

    if mounted:
        write_storage(args.mount, config)
        if tablet_config:
            write_tablet_storage(args.mount, tablet_config)

    subprocess.run(["python3", str(VERIFY)], check=True)
    if tablet_config:
        subprocess.run(
            [
                "python3",
                str(VERIFY),
                "--json",
                str(ROOT / "generated" / "lovelace.flux_ui_tablet.json"),
            ],
            check=True,
        )

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

    if tablet_config:
        await ensure_tablet_dashboard(token, args.ha_url)
        await save_dashboard(token, args.ha_url, tablet_config, url_path=TABLET_URL_PATH)

    subprocess.run(
        ["python3", str(VERIFY), "--live", "--ha-url", args.ha_url, "--token", token],
        check=True,
    )

    if mounted:
        unmount(args.mount)

    print(f"Flux UI deployed at {args.ha_url}/{URL_PATH}/overview")
    if tablet_config:
        print(f"Flux UI 16:9 deployed at {args.ha_url}/{TABLET_URL_PATH}/overview")
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
        "--skip-tablet",
        action="store_true",
        help="Skip the 16:9 tablet dashboard (flux-ui-tablet)",
    )
    parser.add_argument(
        "--offline-ok",
        action="store_true",
        help="If HA unreachable, still copy to SMB and exit 0",
    )
    args = parser.parse_args()
    return run_async(deploy_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

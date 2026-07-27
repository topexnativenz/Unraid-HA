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
FIX_EUFY_CAMERAS = ROOT / "scripts" / "fix_eufy_cameras.py"
DISCOVER_WEATHER = ROOT / "scripts" / "discover_weather.py"
DISCOVER_SONOS = ROOT / "scripts" / "discover_sonos.py"
INSTALL = ROOT / "scripts" / "install_dependencies.py"
ASSETS = ROOT / "scripts" / "install_frontend_assets.py"
VERIFY = ROOT / "scripts" / "verify_flux_ui.py"
WEATHER_PANEL = ROOT / "weather_panel.yaml"
WEATHER_HOURLY_ENTITY = "sensor.flux_ui_hourly_forecast_full"
URL_PATH = "flux-ui"
STORAGE_KEY = "lovelace.flux_ui"
MOBILE_STORAGE = "lovelace.mobile_home"

# 16:9 landscape (wall tablet) variant — same functions, 3-column sections.
TABLET_URL_PATH = "flux-ui-tablet"
TABLET_STORAGE_KEY = "lovelace.flux_ui_tablet"
TABLET_TITLE = "Flux UI 16:9"
TABLET_DASHBOARD_ID = "flux_ui_tablet"


# Packages that must land on HA for tablet RGB / media / tabs to work.
REQUIRED_PACKAGES = (
    "flux_ui_media.yaml",
    "flux_ui_overview.yaml",
    "flux_ui_rooms.yaml",
    "flux_ui_weather.yaml",
    "flux_ui_tablet_led.yaml",
    "flux_ui_eufy_cameras.yaml",
)

TABLET_LED_ENTITY = "input_text.flux_ui_tablet_rgb_led"
TABLET_EV_CHARGING_ENTITY = "binary_sensor.flux_ui_ev_charging"
TABLET_LED_SCRIPT = "script.flux_ui_tablet_led_charge_pulse"


def copy_packages(mount: str) -> None:
    src = ROOT / "packages"
    if not src.exists():
        raise SystemExit("ERROR: packages/ directory missing — aborting deploy")
    missing = [name for name in REQUIRED_PACKAGES if not (src / name).exists()]
    if missing:
        raise SystemExit(
            "ERROR: required package(s) missing from repo: "
            + ", ".join(missing)
            + "\n  You are likely on an old git SHA. Run:\n"
            "  git fetch origin cursor/flux-ui-md3-dashboard-bf3a\n"
            "  git reset --hard origin/cursor/flux-ui-md3-dashboard-bf3a\n"
            "  git rev-parse --short HEAD"
        )
    dst_root = Path(mount) / "packages"
    dst_root.mkdir(parents=True, exist_ok=True)
    for pkg in sorted(src.glob("*.yaml")):
        shutil.copy2(pkg, dst_root / pkg.name)
        print(f"  copied packages/{pkg.name}")
    for name in REQUIRED_PACKAGES:
        if not (dst_root / name).exists():
            raise SystemExit(f"ERROR: failed to copy packages/{name} to HA config share")
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


def _mkdir_smb(path: Path) -> bool:
    """Create a directory on the HA SMB share; return False if the share rejects it.

    Some Samba mounts fail pathlib.mkdir even when the parent exists (ENOENT).
    Try level-by-level mkdir, then `mkdir -p`, then a .keep touch fallback.
    """
    import os
    import subprocess

    if path.exists():
        return True
    parts: list[Path] = []
    cur = path
    while cur != cur.parent and not cur.exists():
        parts.append(cur)
        cur = cur.parent
    for part in reversed(parts):
        if part.exists():
            continue
        try:
            part.mkdir(exist_ok=True)
        except OSError:
            try:
                os.makedirs(part, exist_ok=True)
            except OSError:
                try:
                    subprocess.run(
                        ["mkdir", "-p", str(part)],
                        check=False,
                        capture_output=True,
                    )
                except OSError:
                    pass
        if not part.exists():
            # Last resort: open() sometimes creates parent dirs on flaky SMB.
            keep = part / ".keep"
            try:
                part.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            try:
                keep.parent.mkdir(parents=True, exist_ok=True)
                keep.write_text("")
                keep.unlink(missing_ok=True)
            except OSError as exc:
                print(f"  WARNING: cannot create {part} on SMB ({exc})")
                return False
        if not part.exists():
            print(f"  WARNING: cannot create {part} on SMB")
            return False
    return path.exists()


def copy_frontend_assets(mount: str) -> None:
    """Copy www assets to the HA config share. Never aborts the whole deploy."""
    src_community = ROOT / "www" / "community"
    if src_community.exists():
        for item in src_community.iterdir():
            if not item.is_dir():
                continue
            dst = Path(mount) / "www" / "community" / item.name
            if not _mkdir_smb(dst):
                continue
            for js in item.glob("*.js"):
                try:
                    shutil.copy2(js, dst / js.name)
                    print(f"  copied www/community/{item.name}/{js.name}")
                except OSError as exc:
                    print(f"  WARNING: skip www/community/{item.name}/{js.name} ({exc})")

    src_flux = ROOT / "www" / "flux-ui"
    if src_flux.exists():
        dst_flux = Path(mount) / "www" / "flux-ui"
        if not _mkdir_smb(dst_flux):
            print("  WARNING: cannot create www/flux-ui on SMB — skipping flux-ui assets")
            return
        for f in src_flux.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(src_flux)
            target = dst_flux / rel
            if not _mkdir_smb(target.parent):
                # Samba often cannot mkdir www/flux-ui/icons — fall back to flat copy
                # under www/flux-ui/ for any icons/* assets.
                if rel.parts and rel.parts[0] == "icons":
                    flat = dst_flux / rel.name
                    try:
                        shutil.copy2(f, flat)
                        print(f"  copied www/flux-ui/{rel.name} (flat fallback for icons/)")
                    except OSError as exc:
                        print(f"  WARNING: skip www/flux-ui/{rel} ({exc})")
                else:
                    print(f"  WARNING: skip www/flux-ui/{rel} (parent mkdir failed)")
                continue
            try:
                shutil.copy2(f, target)
                print(f"  copied www/flux-ui/{rel}")
            except OSError as exc:
                print(f"  WARNING: skip www/flux-ui/{rel} ({exc})")


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
MEDIA_SELECT_ENTITY = "input_select.flux_ui_media_player"


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


async def reload_template(token: str, ha_url: str) -> None:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "call_service", "domain": "template", "service": "reload"}],
    )
    if res[0].get("success") is False:
        print(f"  WARNING: template.reload failed: {res[0].get('error')}")
    else:
        print("  reloaded template sensors (weather forecasts)")


def _weather_entity_from_config() -> str:
    if not WEATHER_PANEL.exists():
        return "weather.metservice"
    import yaml

    data = yaml.safe_load(WEATHER_PANEL.read_text()) or {}
    ms = data.get("metservice") or {}
    return str(ms.get("weather_entity") or data.get("weather_entity") or "weather.metservice")


async def ensure_weather_package_helpers(token: str, ha_url: str) -> None:
    """Reload packages/templates and wait for MetService forecast sensors."""
    import asyncio

    await asyncio.sleep(1)
    await reload_core_config(token, ha_url)
    await asyncio.sleep(2)
    await reload_template(token, ha_url)
    await asyncio.sleep(3)
    weather_entity = _weather_entity_from_config()
    if not await wait_for_entity(token, ha_url, weather_entity, attempts=8):
        print(f"  WARNING: {weather_entity} not found — run discover_weather.py --apply")
    if not await wait_for_entity(token, ha_url, WEATHER_HOURLY_ENTITY, attempts=8):
        print(
            f"  WARNING: {WEATHER_HOURLY_ENTITY} not loaded — "
            "Forecast charts need packages/flux_ui_weather.yaml."
        )


async def ensure_media_package_helpers(token: str, ha_url: str) -> bool:
    """Wait for music player zone picker input_select after packages reload."""
    if await wait_for_entity(token, ha_url, MEDIA_SELECT_ENTITY, attempts=8):
        print(f"  loaded {MEDIA_SELECT_ENTITY}")
        return True
    print(
        f"  WARNING: {MEDIA_SELECT_ENTITY} not loaded — music player zone picker disabled.\n"
        "  Re-run: bash home-assistant/scripts/deploy_mac.sh --restart-ha"
    )
    return False


async def _reload_domain(token: str, ha_url: str, domain: str, service: str = "reload") -> None:
    res = await ws_call(
        token,
        ha_url,
        [{"type": "call_service", "domain": domain, "service": service}],
    )
    if res[0].get("success") is False:
        print(f"  WARNING: {domain}.{service} failed: {res[0].get('error')}")
    else:
        print(f"  reloaded {domain}.{service}")


async def ensure_tablet_led_helpers(token: str, ha_url: str) -> None:
    """Reload tablet LED package helpers and confirm EV-charge pulse entities exist."""
    import asyncio
    import yaml

    await asyncio.sleep(1)
    await reload_core_config(token, ha_url)
    await asyncio.sleep(1)
    # Package YAML defines automations + scripts — force-reload both so a soft
    # core reload cannot leave the previous (missing) LED pulse dormant.
    await _reload_domain(token, ha_url, "automation")
    await _reload_domain(token, ha_url, "script")
    await _reload_domain(token, ha_url, "template")
    await asyncio.sleep(2)

    for entity_id in (TABLET_LED_ENTITY, TABLET_EV_CHARGING_ENTITY, TABLET_LED_SCRIPT):
        if await wait_for_entity(token, ha_url, entity_id, attempts=8):
            print(f"  loaded {entity_id}")
        else:
            print(
                f"  WARNING: {entity_id} not loaded — "
                "rk3576_u green pulse needs packages/flux_ui_tablet_led.yaml "
                "(hard-reset to latest branch SHA, then re-deploy)."
            )

    led_entity = "light.rk3576_u_rk3576_u_rgb"
    entities_path = ROOT / "entities.yaml"
    if entities_path.exists():
        try:
            data = yaml.safe_load(entities_path.read_text()) or {}
            tablet = data.get("tablet") or {}
            if isinstance(tablet.get("rgb_led"), str) and tablet["rgb_led"].strip():
                led_entity = tablet["rgb_led"].strip()
        except Exception:
            pass
    # Prefer the template-resolved entity when the package is loaded.
    resolved = "sensor.flux_ui_tablet_rgb_led_resolved"
    if await wait_for_entity(token, ha_url, resolved, attempts=4):
        print(f"  loaded {resolved}")
    if await entity_exists(token, ha_url, led_entity):
        print(f"  MQTT RGB light OK: {led_entity}")
    else:
        # Scan common discovery names from the rk3576_u AndroidTablet device page.
        found = None
        for candidate in (
            "light.rk3576_u_rk3576_u_rgb",
            "light.rk3576_u_rgb",
            "light.rk3576_u_led",
            "light.rk3576_u_rgb_led",
            "light.androidtablet_rgb",
        ):
            if await entity_exists(token, ha_url, candidate):
                found = candidate
                break
        if found:
            print(f"  MQTT RGB light found as {found} (entities.yaml had {led_entity})")
            led_entity = found
        else:
            print(
                f"  WARNING: {led_entity} not in HA — tablet LED pulse cannot run. "
                "Open the rk3576_u device → Controls → RGB and set "
                "input_text.flux_ui_tablet_rgb_led to that light entity_id."
            )
            return

    # If a Tesla is already charging, kick the pulse script now (covers the case
    # where the resolved LED entity_id changed during this deploy).
    try:
        res = await ws_call(token, ha_url, [{"type": "get_states"}])
        states = res[0].get("result", []) if res[0].get("success") else []
        charging_on = any(
            s.get("entity_id") == TABLET_EV_CHARGING_ENTITY and s.get("state") == "on"
            for s in states
        )
        if charging_on:
            await ws_call(
                token,
                ha_url,
                [
                    {
                        "type": "call_service",
                        "domain": "script",
                        "service": "turn_on",
                        "target": {"entity_id": TABLET_LED_SCRIPT},
                    }
                ],
            )
            print(f"  started {TABLET_LED_SCRIPT} (EV charging + LED {led_entity})")
    except Exception as exc:
        print(f"  WARNING: could not start LED pulse script: {exc}")


def assert_required_packages_present() -> None:
    """Fail fast when deploying from an old SHA that lacks tablet LED / media packages."""
    src = ROOT / "packages"
    missing = [name for name in REQUIRED_PACKAGES if not (src / name).exists()]
    if missing:
        raise SystemExit(
            "ERROR: required package(s) missing from repo: "
            + ", ".join(missing)
            + "\n  Deploy aborted — git reset likely failed (old SHA).\n"
            "  Do NOT pass a SHA as a second argument to `git reset --hard` "
            "(that means pathspec → 'Cannot do hard reset with paths').\n"
            "  Use:\n"
            "    git fetch origin cursor/flux-ui-md3-dashboard-bf3a\n"
            "    git reset --hard origin/cursor/flux-ui-md3-dashboard-bf3a\n"
            "    git rev-parse --short HEAD"
        )


async def _sync_sonos_input_select(token: str, ha_url: str) -> None:
    """Push live input_select options to match media_players.yaml after package reload."""
    from discover_sonos import load_media_config, sync_input_select_options_async

    players = load_media_config().get("players", [])
    if not players:
        return
    notes = await sync_input_select_options_async(token, ha_url, players)
    for line in notes:
        print(f"  {line}")


def build_config(
    mobile_storage: Path | None,
    *,
    use_navbar_card: bool = True,
    use_kiosk: bool = True,
    use_auto_entities: bool = True,
    use_simple_tabs: bool = True,
    use_calendar_pro: bool = True,
    use_mediocre_media: bool = True,
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
    if not use_mediocre_media:
        cmd.append("--no-mediocre-media")
    subprocess.run(cmd, check=True)
    raw = json.loads(out.read_text())
    config = raw["data"]["config"]
    blob = json.dumps(config)
    overview = next((v for v in config["views"] if v.get("path") == "overview"), config["views"][0])

    if tablet:
        if overview.get("type") != "panel":
            print(
                "\nERROR: Tablet overview must be type panel + layout-card "
                "(sections views stay phone-column width).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        cards = overview.get("cards") or []
        if len(cards) != 1:
            print(
                f"\nERROR: Panel overview must have exactly 1 root card, got {len(cards)}.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        for needle in (
            '"type": "panel"',
            "custom:layout-card",
            "custom:grid-layout",
            "weather-forecast",
            "Gates & Doors",
            '"template": "flux_room"',
            "calendar_notification",
            "simple_tab",
            '"grid-area": "mid"',
            '"grid-area": "tesla"',
            '"grid-area": "music"',
            '"grid-area": "greeting"',
            "Model X",
            "Model S",
            "camera.back_courtyard_fluent",
            "#back-courtyard",
            "custom:bubble-card",
            "is_sidebar_hidden",
            '"width_desktop": "100%"',
            "/local/flux-ui/camera-stills/",
            "input_text.flux_ui_camera_still_token",
            "script.flux_ui_camera_snapshot",
            "eufy-driveway",
            "eufy-side-of-house",
            "eufy-garage-door",
            "custom:webrtc-camera",
            "ffmpeg:",
            '"camera_view": "live"',
            "data:image/webp;base64,",
            "__fluxNzClock",
            "hour12: false",
            "Pacific/Auckland",
            "gap: 8px !important",
            '"width": "100%"',
            '"days_to_show": 7',
            '"refresh_on_navigate": false',
            "flux-tesla-charge-pulse",
            ".content-container",
            "touch-action: pan-y",
            "picture-entity",
            "mediocre-massive-media-player-card",
            "media_player.kitchen_sonos",
            "Weather Forecast",
            "mid mid music calendar_notification",
            "tesla tesla tesla calendar_notification",
            "minmax(0, 30%)",
            "minmax(0, 24%)",
            "aspect-ratio: 1 / 1",
            '"place-self": "start stretch"',
            '"grid-template-rows": "auto auto"',
            "height: 100% !important",
            "position: absolute !important",
            "max-height: 100% !important",
            ".loading-indicator",
            "1fr 1fr 1fr 1fr",
            '"font-size": "22px"',
            "justify-content: center !important",
        ):
            if needle not in blob:
                print(f"\nERROR: Tablet build missing {needle}.", file=sys.stderr)
                raise SystemExit(1)
        if "room_selector" in blob:
            print(
                "\nERROR: Tablet overview still has room_selector "
                "(Default/Others/Outdoor filter chips).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "cameras cameras cameras calendar_notification" in blob:
            print(
                "\nERROR: Tablet cameras must sit beside rooms as 2x2 "
                "(not a full-width one-row cameras band).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "[class*='loading']" in blob:
            print(
                "\nERROR: Calendar card-mod must not use [class*='loading'] (hides events).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "mediocre-chip-media-player-group-card" in blob:
            print(
                "\nERROR: Tablet music must not include zone/group chip header "
                "(artwork should sit under Music title).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "mediocre-massive-media-player-card" not in blob:
            print(
                "\nERROR: Tablet music missing mediocre-massive-media-player-card "
                "(full player, same as popup).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if '"type": "custom:mediocre-media-player-card"' in blob:
            print(
                "\nERROR: Tablet music must not use compact mediocre-media-player-card.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "media_player.kitchen_sonos" not in blob:
            print(
                "\nERROR: Tablet music must be fixed to media_player.kitchen_sonos.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        # Kitchen-only — no multi-zone speaker_group chips above artwork.
        if '"speaker_group"' in blob:
            print(
                "\nERROR: Tablet music must not include speaker_group "
                "(Kitchen-only; no zone list above artwork).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "media_player.select_source" not in blob:
            print(
                "\nERROR: Tablet music missing in-card source selector "
                "(media_player.select_source chips).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "custom:mod-card" not in blob:
            print(
                "\nERROR: Tablet music must wrap mediocre player in "
                "custom:mod-card so footer hide styles apply.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "mediocre-massive-media-player-card > div > div:last-child" not in blob:
            print(
                "\nERROR: Tablet music must hide mediocre Home/Sonos footer "
                "(mod-card → mediocre-massive-media-player-card > div > div:last-child).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        # Music player must not reshuffle overview grid areas / other cards.
        locked_area_rows = (
            "greeting simple_tab music calendar_notification",
            "mid mid music calendar_notification",
            "tesla tesla tesla calendar_notification",
        )
        if any(row not in blob for row in locked_area_rows):
            print(
                "\nERROR: Tablet overview grid-template-areas changed unexpectedly.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if '"rooms cameras music calendar_notification"' in blob:
            print(
                "\nERROR: Tablet must use unified mid band "
                "(mid mid), not separate rooms|cameras areas.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "1fr 1fr 1.05fr 1.15fr" not in blob:
            print(
                "\nERROR: Tablet overview columns must be 1fr 1fr 1.05fr 1.15fr.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "1.05fr 1.25fr" in blob:
            print(
                "\nERROR: Tablet still uses unequal rooms/cameras columns "
                "(1.05fr 1.25fr).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "minmax(220px, 240px)" in blob or "minmax(150px, 180px)" in blob:
            print(
                "\nERROR: Tablet Tesla row must use flexible % tracks "
                "(minmax(0, 24%)), not fixed px mins that push off-screen.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if '"grid-area": "cameras"' in blob or '"grid-area": "rooms"' in blob:
            print(
                "\nERROR: Tablet must use unified mid band, not separate "
                "rooms/cameras grid-areas.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if '"grid-area": "weather"' in blob:
            print(
                "\nERROR: Tablet still has standalone weather grid area.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "custom:navbar-card" in blob and '"label": "Home"' in blob:
            print(
                "\nERROR: Tablet build still includes bottom navbar (covers Tesla cards).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "Live overview" in blob:
            print("\nERROR: Tablet still has Home / Live overview title.", file=sys.stderr)
            raise SystemExit(1)
        if "Software tracker" in blob or "Last charges (7 days)" in blob:
            print(
                "\nERROR: Tablet overview still has broken Tesla widgets "
                "(software tracker / last charges).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if '"domain": "camera"' in blob and '"grid-area": "mid"' in blob:
            # Overview must not auto-discover every camera (causes 2+ rows).
            mid_idx = blob.find('"grid-area": "mid"')
            mid_slice = blob[max(0, mid_idx - 200) : mid_idx + 2500]
            if '"domain": "camera"' in mid_slice and "camera.side_door" not in mid_slice:
                print(
                    "\nERROR: Tablet mid band still auto-discovers camera domain.\n",
                    file=sys.stderr,
                )
                raise SystemExit(1)
        if "__fluxNzClock" not in blob or "hour12: false" not in blob:
            print(
                "\nERROR: Tablet build missing NZ digital clock (24h HH:MM greeting corner).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "Good Morning!" in blob and '"grid-area": "greeting"' in blob:
            # Greeting corner must be clock-only on tablet (phone keeps flux_hero).
            greeting_idx = blob.find('"grid-area": "greeting"')
            greeting_slice = blob[max(0, greeting_idx - 800) : greeting_idx + 200]
            if "Good Morning!" in greeting_slice:
                print(
                    "\nERROR: Tablet greeting corner still uses Good Morning greeting.\n",
                    file=sys.stderr,
                )
                raise SystemExit(1)
        if use_kiosk and "kiosk_mode" not in config:
            print("\nERROR: Build missing kiosk_mode block.", file=sys.stderr)
            raise SystemExit(1)
        non_panel = [v.get("path") for v in config["views"] if v.get("type") != "panel"]
        if non_panel:
            print(
                f"\nERROR: All tablet views must be panel for 16:9; non-panel: {non_panel[:8]}\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        print(
            f"Built tablet config: panel+layout-card overview, "
            f"{len(config['views'])} full-bleed panel views"
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
    if "/local/flux-ui/bitmoji/" not in blob and "bitmoji" not in blob:
        print("\nERROR: Build missing bitmoji hero avatar.", file=sys.stderr)
        raise SystemExit(1)
    if "#weather-panel" not in blob and "Weather Panel" not in blob:
        print("\nERROR: Build missing bottom weather panel.", file=sys.stderr)
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
    assert_required_packages_present()
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
        print(
            "  Tip: if this SHA is older than origin, git reset failed earlier — "
            "re-run reset WITHOUT an extra SHA argument, then deploy again."
        )
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
    use_mediocre_media = True
    if token and ha_up:
        try:
            use_navbar = await has_navbar_resource(token, args.ha_url)
            use_kiosk = await has_kiosk_resource(token, args.ha_url) or True
            use_auto_entities = await has_resource(token, args.ha_url, "auto-entities")
            use_simple_tabs = await has_resource(token, args.ha_url, "simple-tabs")
            use_calendar_pro = await has_resource(token, args.ha_url, "calendar-card-pro")
            use_mediocre_media = await has_resource(token, args.ha_url, "mediocre")
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
            if not use_mediocre_media:
                print("mediocre media player cards not in resources — popup uses mushroom fallback.")
                print("  HACS → antontanderup/mediocre-hass-media-player-cards")
            if not await has_resource(token, args.ha_url, "weather-forecast-extended"):
                print("weather-forecast-extended not in resources — Forecast tab will not render.")
                print("  HACS → Thyraz/weather-forecast-extended")
            if not await has_kiosk_resource(token, args.ha_url):
                print("WARNING: kiosk-mode resource missing (config still embedded).")
        except Exception:
            use_navbar = False
            use_auto_entities = True
            use_kiosk = True
            use_simple_tabs = True
            use_calendar_pro = True
            use_mediocre_media = True

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
        print("Discovering NZ MetService weather for phone weather panel…")
        subprocess.run(
            [
                "python3",
                str(DISCOVER_WEATHER),
                "--ha-url",
                args.ha_url,
                "--token",
                token,
                "--apply",
            ],
            check=False,
        )
        print("Discovering Sonos media players for music bar…")
        discover = subprocess.run(
            [
                "python3",
                str(DISCOVER_SONOS),
                "--ha-url",
                args.ha_url,
                "--token",
                token,
                "--apply",
            ],
            check=False,
        )
        if discover.returncode != 0:
            print(
                "WARNING: Sonos discovery failed or no speakers — "
                "music bar may be hidden until speakers appear in HA"
            )
        print("Pruning unused Eufy cameras (keep Driveway + tablet outdoor feeds)…")
        subprocess.run(
            [
                "python3",
                str(FIX_EUFY_CAMERAS),
                "--ha-url",
                args.ha_url,
                "--token",
                token,
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
        use_mediocre_media=use_mediocre_media,
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
            use_mediocre_media=use_mediocre_media,
            tablet=True,
        )

    # Verify built JSON BEFORE writing HA storage / live API save.
    # Previous bug: SMB storage was written, then verify failed on weather entity
    # rename (forecast_home → homemetservice), so lovelace/config/save never ran
    # and Companion apps kept serving the old dashboards.
    print("Verifying built phone config…")
    subprocess.run(["python3", str(VERIFY)], check=True)
    if tablet_config:
        print("Verifying built tablet config…")
        subprocess.run(
            [
                "python3",
                str(VERIFY),
                "--json",
                str(ROOT / "generated" / "lovelace.flux_ui_tablet.json"),
            ],
            check=True,
        )

    if mounted:
        # Re-copy packages after weather/Sonos discover regenerates package YAMLs.
        # SMB hiccups must never block lovelace/config/save below — that is what
        # Companion apps actually load.
        try:
            copy_packages(args.mount)
            copy_frontend_assets(args.mount)
            if token and ha_up and not args.offline:
                await ensure_weather_package_helpers(token, args.ha_url)
                await ensure_media_package_helpers(token, args.ha_url)
                await ensure_tablet_led_helpers(token, args.ha_url)
                await _sync_sonos_input_select(token, args.ha_url)
            write_storage(args.mount, config)
            if tablet_config:
                write_tablet_storage(args.mount, tablet_config)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"WARNING: SMB storage write failed ({exc}) — continuing with live API save")

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

    print("Pushing phone dashboard via lovelace/config/save…")
    await save_dashboard(token, args.ha_url, config)

    if tablet_config:
        await ensure_tablet_dashboard(token, args.ha_url)
        print("Pushing tablet dashboard via lovelace/config/save…")
        await save_dashboard(token, args.ha_url, tablet_config, url_path=TABLET_URL_PATH)

    if token and ha_up and not args.offline:
        await _sync_sonos_input_select(token, args.ha_url)

    print("Verifying live dashboards…")
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

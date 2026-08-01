#!/usr/bin/env python3
"""Deploy Flux UI dashboard in parallel with Mobile Home (does not modify mobile-home)."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
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
    wait_for_ha,
    ws_call,
    ws_call_retry,
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
TABLET_YAML = ROOT / "lovelace" / "dashboards" / "flux_ui_tablet.yaml"
TABLET_YAML_FILENAME = "dashboards/flux_ui_tablet.yaml"
TABLET_VERSIONS_DIR = ROOT / "lovelace" / "dashboards" / "versions"
TABLET_VERSIONS_MANIFEST = TABLET_VERSIONS_DIR / "MANIFEST.json"
TABLET_GENERATED_JSON = ROOT / "generated" / "lovelace.flux_ui_tablet.json"
URL_PATH = "flux-ui"
STORAGE_KEY = "lovelace.flux_ui"
MOBILE_STORAGE = "lovelace.mobile_home"

# 16:9 landscape (wall tablet) variant — same functions, 3-column sections.
TABLET_URL_PATH = "flux-ui-tablet"
TABLET_STORAGE_KEY = "lovelace.flux_ui_tablet"
TABLET_TITLE = "Flux UI 16:9"
TABLET_DASHBOARD_ID = "flux_ui_tablet"

TABLET_YAML_HEADER = """# Flux UI 16:9 tablet dashboard — LOCKED BASELINE (source of truth)
#
# LAYOUT LOCK: gaps, spacings, grid fr tracks, card sizes, and overview
# composition are frozen. Normal deploy / page refresh / Companion cache
# reload MUST push this exact config — they must NOT regenerate layout.
#
# The only approved way to change this dashboard is an explicit Cursor agent
# (or human) edit of this file, followed by updating the layout lock hash.
#
# Version history: lovelace/dashboards/versions/
# Snapshot before any intentional replace:
#   python3 scripts/deploy_flux_ui.py --snapshot-tablet-yaml [--label <name>]
# Rebuild / pull require an unlock flag (refuses otherwise):
#   python3 scripts/deploy_flux_ui.py --rebuild-tablet-yaml --replace-locked-tablet-baseline
#   python3 scripts/deploy_flux_ui.py --pull-tablet-yaml --replace-locked-tablet-baseline
#
"""

# Overview layout constants that must stay byte-stable across refresh/redeploy.
# Markers are matched against json.dumps(config) (quoted JSON keys/values).
TABLET_LOCKED_LAYOUT_MARKERS = (
    '"grid-gap": "8px"',
    '"padding": "8px 12px 8px 12px"',
    "minmax(0, 30fr) minmax(0, 48fr) minmax(0, 26fr)",
    '"days_to_show": 7',
    '"compact_days_to_show": 7',
    '"show_empty_days": true',
    '"refresh_on_navigate": false',
    '"time_24h": false',
    "calc(100% - 200px)",
)


# Packages that must land on HA for tablet RGB / media / tabs to work.
REQUIRED_PACKAGES = (
    "flux_ui_media.yaml",
    "flux_ui_overview.yaml",
    "flux_ui_rooms.yaml",
    "flux_ui_weather.yaml",
    "flux_ui_tablet_led.yaml",
    "flux_ui_eufy_cameras.yaml",
    "flux_ui_area_lights.yaml",
    "flux_ui_time.yaml",
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


def snapshot_tablet_yaml(*, label: str = "snapshot") -> Path | None:
    """Copy current baseline YAML into versions/ before it is replaced."""
    import re

    if not TABLET_YAML.exists() or TABLET_YAML.stat().st_size < 32:
        print("  no tablet baseline YAML to snapshot yet")
        return None
    TABLET_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", label).strip("-") or "snapshot"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = TABLET_VERSIONS_DIR / f"{ts}_{safe}.yaml"
    shutil.copy2(TABLET_YAML, dest)
    print(f"  snapshotted tablet baseline → {dest.relative_to(ROOT)}")
    _update_tablet_versions_manifest(last_snapshot=dest.name)
    return dest


def _update_tablet_versions_manifest(**extra: object) -> None:
    TABLET_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if TABLET_VERSIONS_MANIFEST.exists():
        try:
            data = json.loads(TABLET_VERSIONS_MANIFEST.read_text()) or {}
        except json.JSONDecodeError:
            data = {}
    data.setdefault("current", "flux_ui_tablet.yaml")
    data.setdefault("baseline", "2026-08-01_baseline.yaml")
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data.update({k: v for k, v in extra.items() if v is not None})
    snaps = sorted(
        p.name
        for p in TABLET_VERSIONS_DIR.glob("*.yaml")
        if p.name != "README.md"
    )
    data["snapshots"] = snaps
    TABLET_VERSIONS_MANIFEST.write_text(json.dumps(data, indent=2) + "\n")


def tablet_config_fingerprint(config: dict) -> str:
    """Stable SHA-256 of the tablet Lovelace config (layout lock)."""
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_tablet_manifest() -> dict:
    if not TABLET_VERSIONS_MANIFEST.exists():
        return {}
    try:
        return json.loads(TABLET_VERSIONS_MANIFEST.read_text()) or {}
    except json.JSONDecodeError:
        return {}


def update_tablet_layout_lock(config: dict, *, reason: str) -> str:
    """Record the locked fingerprint after an intentional baseline replace."""
    digest = tablet_config_fingerprint(config)
    _update_tablet_versions_manifest(
        current="flux_ui_tablet.yaml",
        layout_locked=True,
        layout_lock_sha256=digest,
        layout_lock_updated_at=datetime.now(timezone.utc).isoformat(),
        layout_lock_reason=reason,
    )
    print(f"  layout lock updated ({reason}): {digest[:16]}…")
    return digest


def assert_tablet_layout_lock(config: dict, *, update_if_missing: bool = False) -> str:
    """Fail deploy if the loaded baseline does not match the committed lock hash."""
    digest = tablet_config_fingerprint(config)
    manifest = _read_tablet_manifest()
    expected = manifest.get("layout_lock_sha256")
    if not expected:
        if update_if_missing:
            return update_tablet_layout_lock(config, reason="initial-lock")
        raise SystemExit(
            "ERROR: tablet layout lock missing in versions/MANIFEST.json.\n"
            "  Refusing to deploy an unlocked baseline.\n"
            "  Intentional replace:\n"
            "    python3 scripts/deploy_flux_ui.py --rebuild-tablet-yaml "
            "--replace-locked-tablet-baseline\n"
            "  Or re-lock the current YAML via an agent edit that updates the lock."
        )
    if digest != expected:
        raise SystemExit(
            "ERROR: LOCKED tablet baseline fingerprint mismatch.\n"
            f"  expected: {expected}\n"
            f"  actual:   {digest}\n"
            "  Layout/gaps/sizing drifted from the locked design.\n"
            "  Do not silently rebuild. Ask the Cursor agent for a direct change,\n"
            "  or unlock deliberately:\n"
            "    python3 scripts/deploy_flux_ui.py --pull-tablet-yaml "
            "--replace-locked-tablet-baseline"
        )
    blob = json.dumps(config)
    missing = [m for m in TABLET_LOCKED_LAYOUT_MARKERS if m not in blob]
    if missing:
        raise SystemExit(
            "ERROR: LOCKED tablet overview layout markers missing:\n  - "
            + "\n  - ".join(missing)
            + "\n  Baseline YAML must keep exact gaps/spacings/sizings."
        )
    print(f"  layout lock OK ({digest[:16]}…)")
    return digest


def require_tablet_baseline_unlock(args: argparse.Namespace, *, action: str) -> None:
    if getattr(args, "replace_locked_tablet_baseline", False):
        print(f"  UNLOCK: replacing locked tablet baseline via {action}")
        return
    raise SystemExit(
        f"ERROR: refusing {action} — tablet baseline is LAYOUT LOCKED.\n"
        "  Gaps/spacings/sizings stay frozen across refresh and normal deploy.\n"
        "  Only an explicit Cursor agent change (or unlock) may replace it:\n"
        f"    python3 scripts/deploy_flux_ui.py {action} --replace-locked-tablet-baseline"
    )


def write_tablet_yaml_from_config(
    config: dict,
    *,
    snapshot_label: str | None = None,
    lock_reason: str = "baseline-write",
) -> Path:
    """Write the tablet Lovelace YAML baseline (snapshots previous file first)."""
    import yaml

    if snapshot_label:
        snapshot_tablet_yaml(label=snapshot_label)
    TABLET_YAML.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.dump(config, sort_keys=False, allow_unicode=True, width=120)
    TABLET_YAML.write_text(TABLET_YAML_HEADER + body)
    print(f"  wrote {TABLET_YAML.relative_to(ROOT)} ({TABLET_YAML.stat().st_size} bytes)")
    update_tablet_layout_lock(config, reason=lock_reason)
    _update_tablet_versions_manifest(current="flux_ui_tablet.yaml")
    return TABLET_YAML


def load_tablet_yaml() -> dict:
    """Load the committed tablet baseline YAML (strips comment header)."""
    import yaml

    if not TABLET_YAML.exists():
        raise SystemExit(
            f"ERROR: missing tablet baseline {TABLET_YAML}.\n"
            "  Intentional pull (unlock required):\n"
            "    python3 scripts/deploy_flux_ui.py --pull-tablet-yaml "
            "--replace-locked-tablet-baseline\n"
            "  Intentional rebuild (unlock required):\n"
            "    python3 scripts/deploy_flux_ui.py --rebuild-tablet-yaml "
            "--replace-locked-tablet-baseline"
        )
    raw = TABLET_YAML.read_text()
    # Drop leading comment header so yaml can parse title/views.
    lines = raw.splitlines(keepends=True)
    while lines and lines[0].lstrip().startswith("#"):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)
    config = yaml.safe_load("".join(lines))
    if not isinstance(config, dict) or "views" not in config:
        raise SystemExit(f"ERROR: {TABLET_YAML} is not a valid Lovelace config")
    return config


def write_generated_tablet_json(config: dict) -> Path:
    """Write HA storage-shaped JSON for verify_flux_ui.py --json."""
    TABLET_GENERATED_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "minor_version": 1,
        "key": TABLET_STORAGE_KEY,
        "data": {"config": config},
    }
    TABLET_GENERATED_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    return TABLET_GENERATED_JSON


async def pull_tablet_yaml_from_ha(token: str, ha_url: str, *, label: str = "pre-pull") -> dict:
    """Fetch live flux-ui-tablet into the baseline YAML (versions previous first)."""
    res = (
        await ws_call(
            token, ha_url, [{"type": "lovelace/config", "url_path": TABLET_URL_PATH}]
        )
    )[0]
    if not res.get("success"):
        raise SystemExit(f"ERROR: could not pull live tablet config: {res.get('error')}")
    config = res["result"]
    write_tablet_yaml_from_config(
        config, snapshot_label=label, lock_reason="pull-tablet-yaml"
    )
    write_generated_tablet_json(config)
    print(f"  pulled live {TABLET_URL_PATH} → {TABLET_YAML.relative_to(ROOT)}")
    return config


def ensure_tablet_yaml_in_configuration(mount: str) -> None:
    """Register flux-ui-tablet as a YAML-mode Lovelace dashboard (like solar)."""
    conf = Path(mount) / "configuration.yaml"
    if not conf.exists():
        raise SystemExit(f"ERROR: missing {conf}")
    text = conf.read_text()
    if TABLET_YAML_FILENAME in text:
        print(f"  configuration.yaml already registers {TABLET_YAML_FILENAME}")
        return

    entry = (
        f"    {TABLET_URL_PATH}:\n"
        f"      mode: yaml\n"
        f"      title: {TABLET_TITLE}\n"
        f"      icon: mdi:tablet-dashboard\n"
        f"      show_in_sidebar: true\n"
        f"      filename: {TABLET_YAML_FILENAME}\n"
    )

    if "lovelace:" in text and "dashboards:" in text:
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        inserted = False
        for i, line in enumerate(lines):
            out.append(line)
            if inserted:
                continue
            if line.rstrip() == "  dashboards:" or line.rstrip() == "dashboards:":
                out.append(entry)
                inserted = True
        if not inserted:
            # dashboards: with different indent — append under lovelace block end
            text = text.rstrip() + "\n" + entry
            conf.write_text(text if text.endswith("\n") else text + "\n")
            print(f"  registered {TABLET_YAML_FILENAME} in configuration.yaml (appended)")
            return
        conf.write_text("".join(out))
        print(f"  registered {TABLET_YAML_FILENAME} under existing lovelace.dashboards")
        return

    if "lovelace:" in text:
        conf.write_text(
            text.rstrip()
            + "\n  dashboards:\n"
            + entry
            + ("\n" if not entry.endswith("\n") else "")
        )
        print(f"  added dashboards + {TABLET_YAML_FILENAME} under existing lovelace:")
        return

    conf.write_text(
        text.rstrip()
        + "\n\nlovelace:\n  mode: storage\n  dashboards:\n"
        + entry
        + "\n"
    )
    print(f"  added lovelace.dashboards → {TABLET_YAML_FILENAME}")


def clear_tablet_yaml_from_configuration(mount: str) -> None:
    """Remove flux-ui-tablet YAML-mode registration so storage mode can take over."""
    conf = Path(mount) / "configuration.yaml"
    if not conf.exists():
        return
    text = conf.read_text()
    if TABLET_YAML_FILENAME not in text and f"{TABLET_URL_PATH}:" not in text:
        return
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    removed = False
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        # Match "    flux-ui-tablet:" (or similar indent) under dashboards
        if stripped.startswith(f"{TABLET_URL_PATH}:"):
            indent = len(line) - len(line.lstrip(" "))
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    i += 1
                    break
                nxt_indent = len(nxt) - len(nxt.lstrip(" "))
                if nxt_indent <= indent and nxt.strip():
                    break
                i += 1
            removed = True
            continue
        out.append(line)
        i += 1
    if not removed:
        return
    conf.write_text("".join(out))
    print(
        f"  removed {TABLET_URL_PATH} YAML dashboard from configuration.yaml "
        "(restoring storage mode)"
    )


def copy_tablet_yaml_dashboard(mount: str) -> None:
    """Copy editable tablet YAML to HA; does not regenerate from Python."""
    if not TABLET_YAML.exists():
        raise SystemExit(
            f"ERROR: missing {TABLET_YAML}.\n"
            "  Pull live: python3 scripts/deploy_flux_ui.py --pull-tablet-yaml\n"
            "  Or rebuild: python3 scripts/deploy_flux_ui.py --rebuild-tablet-yaml"
        )
    dst_dir = Path(mount) / "dashboards"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "flux_ui_tablet.yaml"
    shutil.copy2(TABLET_YAML, dst)
    print(f"  copied {TABLET_YAML_FILENAME} ({dst.stat().st_size} bytes)")
    ensure_tablet_yaml_in_configuration(mount)

    # Drop stale storage-mode tablet config so YAML mode is the only source.
    storage_file = Path(mount) / ".storage" / TABLET_STORAGE_KEY
    if storage_file.exists():
        storage_file.unlink()
        print(f"  removed stale .storage/{TABLET_STORAGE_KEY} (YAML mode owns tablet)")


async def remove_storage_tablet_dashboard(token: str, ha_url: str) -> None:
    """Delete storage-mode flux-ui-tablet if present (avoids duplicate url_path)."""
    listed = (await ws_call(token, ha_url, [{"type": "lovelace/dashboards/list"}]))[0]
    if not listed.get("success"):
        return
    for dash in listed.get("result") or []:
        if dash.get("url_path") != TABLET_URL_PATH:
            continue
        if dash.get("mode") != "storage":
            continue
        dash_id = dash.get("id")
        if not dash_id:
            continue
        res = await ws_call(
            token,
            ha_url,
            [{"type": "lovelace/dashboards/delete", "dashboard_id": dash_id}],
        )
        if res[0].get("success"):
            print(f"  deleted storage dashboard {TABLET_URL_PATH} ({dash_id})")
        else:
            print(
                f"  WARNING: could not delete storage {TABLET_URL_PATH}: "
                f"{res[0].get('error')} — restart HA after YAML registration"
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
    try:
        res = await ws_call_retry(
            token,
            ha_url,
            [
                {
                    "type": "call_service",
                    "domain": "homeassistant",
                    "service": "reload_core_config",
                }
            ],
            attempts=3,
            delay_s=2,
            label="reload_core_config",
        )
    except Exception as exc:
        print(f"  WARNING: reload_core_config call failed ({exc}) — waiting for HA…")
        await wait_for_ha(token, ha_url, timeout_s=180, label="HA after core reload")
        return
    if res[0].get("success") is False:
        print(f"  WARNING: reload_core_config failed: {res[0].get('error')}")
    else:
        print("  reloaded HA core config (packages/input_select)")
    # Core reload often drops the API briefly — never continue until it's back.
    await wait_for_ha(token, ha_url, timeout_s=180, label="HA after core reload")


async def wait_for_entity(token: str, ha_url: str, entity_id: str, *, attempts: int = 5) -> bool:
    import asyncio

    for i in range(attempts):
        if await entity_exists(token, ha_url, entity_id):
            return True
        if i < attempts - 1:
            await asyncio.sleep(2)
    return False


async def entity_exists(token: str, ha_url: str, entity_id: str) -> bool:
    try:
        res = await ws_call_retry(
            token,
            ha_url,
            [{"type": "get_states"}],
            attempts=3,
            delay_s=2,
            label="get_states",
        )
    except Exception:
        return False
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

    weather_entity = _weather_entity_from_config()
    # Avoid a second full core reload when weather helpers are already live —
    # reload_core_config mid-deploy is what dropped HA during the last run.
    if await entity_exists(token, ha_url, weather_entity) and await entity_exists(
        token, ha_url, WEATHER_HOURLY_ENTITY
    ):
        print(
            f"  weather helpers already loaded ({weather_entity}, "
            f"{WEATHER_HOURLY_ENTITY}) — skip core reload"
        )
        return

    await asyncio.sleep(1)
    await reload_core_config(token, ha_url)
    try:
        await reload_template(token, ha_url)
    except Exception as exc:
        print(f"  WARNING: template.reload skipped ({exc})")
    await wait_for_ha(token, ha_url, timeout_s=120, label="HA after weather helpers")
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
            "calendar_notification",
            "simple_tab",
            '"grid-area": "lights"',
            '"grid-area": "cameras"',
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
            "hour12: true",
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
            "lights cameras music calendar_notification",
            "tesla tesla tesla calendar_notification",
            "minmax(0, 30fr)",
            "minmax(0, 48fr)",
            "minmax(0, 26fr)",
            "minmax(0, 30fr) minmax(0, 48fr) minmax(0, 26fr)",
            "aspect-ratio: unset",
            '"font-size": "24px"',
            '"name": "Lights"',
            '"name": "Cameras"',
            "light.kitchen",
            "light.main_atrium",
            "light.dining_all",
            "light.black_lounge_all",
            "light.white_lounge_all",
            "light.walkway_all",
            "light.kids_hallway_all",
            '"name": "Main Area"',
            "flux_action",
            '"columns": 2',
            '"place-self": "start stretch"',
            "aspect-ratio: 1 / 1",
            "height: 100% !important",
            "position: absolute !important",
            "max-height: 100% !important",
            ".loading-indicator",
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
                "\nERROR: Tablet cameras must sit beside lights as 2x2 "
                "(not a full-width one-row cameras band).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if '"grid-area": "cameras"' in blob:
            cam_place_idx = blob.find('"grid-area": "cameras"')
            cam_place_slice = blob[cam_place_idx : cam_place_idx + 220]
            if "start stretch" not in cam_place_slice or "end stretch" in cam_place_slice:
                print(
                    "\nERROR: Tablet cameras must use place-self: start stretch "
                    "(Cameras heading aligned with Lights).\n",
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
            "lights cameras music calendar_notification",
            "tesla tesla tesla calendar_notification",
        )
        if any(row not in blob for row in locked_area_rows):
            print(
                "\nERROR: Tablet overview grid-template-areas changed unexpectedly.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "mid mid music calendar_notification" in blob:
            print(
                "\nERROR: Tablet must use lights|cameras mid row "
                "(not unified mid mid rooms band).\n",
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
                "\nERROR: Tablet still uses unequal lights/cameras columns "
                "(1.05fr 1.25fr).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "minmax(220px, 240px)" in blob or "minmax(150px, 180px)" in blob:
            print(
                "\nERROR: Tablet Tesla row must use flexible fr tracks "
                "(minmax(0, 28fr)), not fixed px mins that push off-screen.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "aspect-ratio: 2 / 1" in blob:
            print(
                "\nERROR: Tablet mid must not use a 2:1 rooms+cameras frame.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "minmax(0, 28fr) minmax(0, 1fr) minmax(0, 16fr)" in blob:
            print(
                "\nERROR: Tablet mid must not be 1fr "
                "(collapses lights/cameras) — expect 48fr mid.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if '"name": "Lights"' not in blob or '"name": "Cameras"' not in blob:
            print(
                "\nERROR: Tablet mid band missing Lights/Cameras section headings.\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if '"grid-area": "mid"' in blob or '"grid-area": "rooms"' in blob:
            print(
                "\nERROR: Tablet overview must use lights|cameras areas, "
                "not mid/rooms room cards.\n",
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
        if '"domain": "camera"' in blob and '"grid-area": "cameras"' in blob:
            # Overview must not auto-discover every camera (causes 2+ rows).
            cam_idx = blob.find('"grid-area": "cameras"')
            cam_slice = blob[max(0, cam_idx - 200) : cam_idx + 2500]
            if '"domain": "camera"' in cam_slice and "camera.side_door" not in cam_slice:
                print(
                    "\nERROR: Tablet cameras band still auto-discovers camera domain.\n",
                    file=sys.stderr,
                )
                raise SystemExit(1)
        if "__fluxNzClock" not in blob or "hour12: true" not in blob:
            print(
                "\nERROR: Tablet build missing NZ digital clock (12h h:mm, no AM/PM).\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if "hourCycle: 'h12'" not in blob:
            print(
                "\nERROR: Tablet clock must use hourCycle h12 (12-hour, no AM/PM label).\n",
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
    await wait_for_ha(token, ha_url, timeout_s=120, label=f"HA before saving {url_path}")
    res = await ws_call_retry(
        token,
        ha_url,
        [{"type": "lovelace/config/save", "url_path": url_path, "config": config}],
        attempts=8,
        delay_s=4,
        label=f"lovelace/config/save ({url_path})",
    )
    if not res[0].get("success"):
        raise RuntimeError(f"lovelace/config/save failed: {res[0].get('error')}")

    verify = await ws_call_retry(
        token,
        ha_url,
        [{"type": "lovelace/config", "url_path": url_path, "force": True}],
        attempts=5,
        delay_s=3,
        label=f"lovelace/config verify ({url_path})",
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
        if getattr(args, "rebuild_tablet_yaml", False):
            require_tablet_baseline_unlock(args, action="--rebuild-tablet-yaml")
            print("Rebuilding Flux UI 16:9 tablet from Python builders…")
            print("  (snapshots current baseline YAML into versions/ first)")
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
            write_tablet_yaml_from_config(
                tablet_config,
                snapshot_label="pre-rebuild",
                lock_reason="rebuild-tablet-yaml",
            )
            write_generated_tablet_json(tablet_config)
        else:
            print("Loading LOCKED Flux UI 16:9 tablet baseline YAML (not regenerating)…")
            tablet_config = load_tablet_yaml()
            assert_tablet_layout_lock(tablet_config)
            write_generated_tablet_json(tablet_config)
            print(
                f"  loaded {TABLET_YAML.relative_to(ROOT)} "
                f"({TABLET_YAML.stat().st_size} bytes, "
                f"{len(tablet_config.get('views') or [])} views) — layout frozen"
            )
        # Legacy alias: --export-tablet-yaml after a rebuild already wrote YAML.
        if getattr(args, "export_tablet_yaml", False) and not getattr(
            args, "rebuild_tablet_yaml", False
        ):
            print("  --export-tablet-yaml ignored: baseline YAML already is the source")

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
            # If a prior YAML-mode experiment registered flux-ui-tablet in
            # configuration.yaml, strip it so storage mode is authoritative.
            clear_tablet_yaml_from_configuration(args.mount)
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

    # Core/package reloads above often leave HA briefly refusing connections.
    print("Waiting for Home Assistant API before lovelace/config/save…")
    await wait_for_ha(token, args.ha_url, timeout_s=180, label="HA before dashboard push")

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
        "--export-tablet-yaml",
        action="store_true",
        help="Deprecated alias — baseline YAML is already the deploy source",
    )
    parser.add_argument(
        "--rebuild-tablet-yaml",
        action="store_true",
        help=(
            "Regenerate tablet dashboard from Python builders, snapshotting the "
            "current baseline YAML into lovelace/dashboards/versions/ first. "
            "Requires --replace-locked-tablet-baseline."
        ),
    )
    parser.add_argument(
        "--pull-tablet-yaml",
        action="store_true",
        help=(
            "Pull live flux-ui-tablet from HA into the baseline YAML "
            "(snapshots the previous baseline into versions/ first). "
            "Requires --replace-locked-tablet-baseline."
        ),
    )
    parser.add_argument(
        "--replace-locked-tablet-baseline",
        action="store_true",
        help=(
            "Required unlock for --rebuild-tablet-yaml / --pull-tablet-yaml. "
            "Updates the layout lock hash after replacing the frozen baseline."
        ),
    )
    parser.add_argument(
        "--snapshot-tablet-yaml",
        action="store_true",
        help="Copy current baseline YAML into lovelace/dashboards/versions/ and exit",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Label suffix for --snapshot-tablet-yaml / --pull-tablet-yaml",
    )
    parser.add_argument(
        "--offline-ok",
        action="store_true",
        help="If HA unreachable, still copy to SMB and exit 0",
    )
    args = parser.parse_args()

    if args.snapshot_tablet_yaml:
        snap = snapshot_tablet_yaml(label=args.label or "manual")
        return 0 if snap else 1

    if args.relock_tablet_baseline:
        config = load_tablet_yaml()
        # Validate locked geometry markers still present after the edit.
        blob = json.dumps(config)
        missing = [m for m in TABLET_LOCKED_LAYOUT_MARKERS if m not in blob]
        if missing:
            raise SystemExit(
                "ERROR: cannot relock — overview layout markers missing:\n  - "
                + "\n  - ".join(missing)
            )
        digest = update_tablet_layout_lock(
            config, reason=args.label or "intentional-edit"
        )
        write_generated_tablet_json(config)
        print(f"Relocked tablet baseline ({digest})")
        return 0

    if args.pull_tablet_yaml:
        require_tablet_baseline_unlock(args, action="--pull-tablet-yaml")

        async def _pull() -> int:
            token = get_token(args.token)
            if not await ha_reachable(args.ha_url, token):
                raise SystemExit(f"ERROR: HA unreachable at {args.ha_url}")
            await pull_tablet_yaml_from_ha(
                token, args.ha_url, label=args.label or "pre-pull"
            )
            # pull_tablet_yaml_from_ha → write_tablet_yaml_from_config updates lock.
            print(
                "Tablet baseline updated from live HA "
                "(previous version kept in versions/; layout lock refreshed)."
            )
            return 0

        return run_async(_pull())

    return run_async(deploy_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

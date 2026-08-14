#!/usr/bin/env python3
"""Discover Home Assistant calendar entities and map them to overview_tabs.yaml."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ha_common import DEFAULT_HA, get_token  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_TABS = ROOT / "overview_tabs.yaml"

# Whanau calendar — the.gillespie.tribe@gmail.com Google account
WHANAU_MATCHERS = [
    re.compile(r"whanau", re.I),
    re.compile(r"gillespie\.tribe@gmail\.com", re.I),
]


def fetch_states(token: str, ha_url: str) -> list[dict]:
    req = urllib.request.Request(
        f"{ha_url}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _haystack(state: dict) -> str:
    attrs = state.get("attributes") or {}
    parts = [
        state.get("entity_id", ""),
        str(attrs.get("friendly_name", "")),
        str(attrs.get("message", "")),
    ]
    return " ".join(parts).lower()


def score_calendar(state: dict, patterns: list[re.Pattern[str]]) -> int:
    if not state["entity_id"].startswith("calendar."):
        return 0
    hay = _haystack(state)
    score = 0
    for pat in patterns:
        if pat.search(hay):
            score += 10
    if "whanau" in hay:
        score += 5
    return score


def find_whanau_calendar(states: list[dict]) -> dict | None:
    best: dict | None = None
    best_score = 0
    for state in states:
        score = score_calendar(state, WHANAU_MATCHERS)
        if score > best_score:
            best_score = score
            best = state
    return best if best_score > 0 else None


def load_overview_tabs() -> dict:
    if not OVERVIEW_TABS.exists():
        return {"enabled": True, "engine": "native", "events": {"calendars": []}}
    return yaml.safe_load(OVERVIEW_TABS.read_text()) or {}


def write_overview_tabs(data: dict) -> None:
    header = (
        "# Overview Home / Events / Active tabs\n"
        "# Reference: https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard\n"
        "# Run: python3 home-assistant/flux-ui-dashboard/scripts/discover_calendars.py --apply\n\n"
    )
    OVERVIEW_TABS.write_text(header + yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def upsert_whanau_calendar(data: dict, entity_id: str, *, display_name: str) -> bool:
    events = data.setdefault("events", {})
    calendars: list[dict] = list(events.get("calendars") or [])
    entry = {
        "entity": entity_id,
        "name": display_name,
        "accent_color": "#81C784",
        "account": "the.gillespie.tribe@gmail.com",
    }

    for i, cal in enumerate(calendars):
        if cal.get("name") == display_name or "whanau" in str(cal.get("entity", "")).lower():
            if cal == entry:
                return False
            calendars[i] = entry
            events["calendars"] = calendars
            return True
        if cal.get("entity") == entity_id:
            if cal.get("name") == display_name:
                return False
            calendars[i] = {**cal, **entry}
            events["calendars"] = calendars
            return True

    # Insert Whanau first so it leads the Events timeline
    calendars.insert(0, entry)
    events["calendars"] = calendars
    return True


def discover(token: str, ha_url: str) -> tuple[str | None, list[str]]:
    states = fetch_states(token, ha_url)
    calendars = [s for s in states if s["entity_id"].startswith("calendar.")]
    notes: list[str] = []

    if not calendars:
        notes.append("No calendar.* entities found in HA — add Google Calendar integration first.")
        return None, notes

    notes.append("Available calendars:")
    for state in sorted(calendars, key=lambda s: s["entity_id"]):
        fn = (state.get("attributes") or {}).get("friendly_name", "")
        notes.append(f"  {state['entity_id']:<40} {fn}")

    match = find_whanau_calendar(states)
    if not match:
        notes.append(
            "Whanau calendar not found — look for entity containing 'whanau' "
            "or link the.gillespie.tribe@gmail.com in HA → Settings → Calendar."
        )
        return None, notes

    entity_id = match["entity_id"]
    fn = (match.get("attributes") or {}).get("friendly_name") or "Whanau calendar"
    notes.append(f"Matched Whanau calendar: {entity_id} ({fn})")
    return entity_id, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", default=DEFAULT_HA)
    parser.add_argument("--token", default=None)
    parser.add_argument("--apply", action="store_true", help="Write matched calendar to overview_tabs.yaml")
    args = parser.parse_args()

    token = get_token(args.token)
    entity_id, notes = discover(token, args.ha_url)

    print("\n".join(notes))

    if not entity_id:
        return 1

    data = load_overview_tabs()
    changed = upsert_whanau_calendar(data, entity_id, display_name="Whanau calendar")

    if args.apply and changed:
        write_overview_tabs(data)
        print(f"\nUpdated {OVERVIEW_TABS} → events.calendars[0].entity = {entity_id}")
    elif args.apply:
        print(f"\nNo change needed — {OVERVIEW_TABS} already has {entity_id}")
    else:
        print(f"\nDry run — re-run with --apply to write {entity_id} to overview_tabs.yaml")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

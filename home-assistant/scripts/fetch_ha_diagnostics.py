#!/usr/bin/env python3
"""Fetch HA traces, logbook, history, and entity states for gate/garage arrival debugging.

Works from Mac (~/.cursor/mcp.json) or Cloud Agent (HA_URL + HA_TOKEN secrets).

Examples:
  python3 home-assistant/scripts/fetch_ha_diagnostics.py --verify
  python3 home-assistant/scripts/fetch_ha_diagnostics.py --hours 12 --topic arrival
  python3 home-assistant/scripts/fetch_ha_diagnostics.py --automation gate_open_on_arrival_model_x
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from ha_client import (  # noqa: E402
    HaAuthError,
    HaConfig,
    get_error_log,
    get_history,
    get_logbook,
    get_state,
    get_states,
    get_trace,
    list_system_log,
    list_traces,
    normalize_trace_index,
    resolve_ha_config,
    resolve_trace_target,
    run_async,
    verify_connection,
)

TOPIC_ENTITIES: dict[str, tuple[str, ...]] = {
    "arrival": (
        "input_boolean.gate_arrival_session",
        "input_boolean.gate_departure_in_progress",
        "input_boolean.model_s_was_away",
        "input_boolean.model_x_was_away",
        "binary_sensor.model_s_tessie_in_road_approach",
        "binary_sensor.model_s_tessie_in_gate_approach",
        "binary_sensor.model_x_tessie_in_road_approach",
        "binary_sensor.model_x_tessie_in_gate_approach",
        "sensor.model_s_tessie_distance_to_gate",
        "sensor.model_s_tessie_distance_to_home",
        "sensor.model_x_tessie_distance_to_gate",
        "sensor.model_x_tessie_distance_to_home",
        "sensor.model_x_tessie_latitude",
        "sensor.model_x_tessie_longitude",
        "binary_sensor.house_garage_door_is_open",
        "binary_sensor.house_garage_door_sensor_door",
        "switch.garage_door_3",
        "input_text.gate_status_message",
        "script.house_garage_open_if_closed",
    ),
}

TOPIC_AUTOMATIONS: dict[str, tuple[str, ...]] = {
    "arrival": (
        "gate_open_on_arrival_model_x",
        "gate_open_on_arrival",
        "house_garage_open_on_gate_session",
        "house_garage_open_on_tessie_arrival",
        "garage_outside_lights_on_tessie_arrival_after_dark",
    ),
}

TOPIC_SCRIPTS: dict[str, tuple[str, ...]] = {
    "arrival": ("script.house_garage_open_if_closed",),
}


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def print_section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def entity_id_for_automation(states: list[dict], item_id: str) -> str | None:
    for st in states:
        eid = st["entity_id"]
        if not eid.startswith("automation."):
            continue
        attrs = st.get("attributes") or {}
        if attrs.get("id") == item_id:
            return eid
    for st in states:
        eid = st["entity_id"]
        if eid.startswith("automation.") and item_id.replace("_", "") in eid.replace("_", ""):
            return eid
    return None


def summarize_trace_steps(detail: dict) -> list[str]:
    lines: list[str] = []
    raw = detail.get("trace", detail)
    if not isinstance(raw, dict):
        return lines

    for path, steps in sorted(raw.items()):
        if not isinstance(steps, list):
            continue
        for step in steps[:3]:
            if not isinstance(step, dict):
                continue
            result = step.get("result", step.get("error"))
            ts = str(step.get("timestamp", ""))[:19]
            lines.append(f"    {path} @ {ts}: {result}")
    return lines[:12]


async def fetch_traces_for_entity(cfg: HaConfig, entity_id: str, *, limit: int = 3) -> dict[str, Any]:
    out: dict[str, Any] = {"entity_id": entity_id, "runs": [], "error": None}
    st = get_state(cfg, entity_id)
    out["last_triggered"] = (st or {}).get("last_triggered")
    out["state"] = (st or {}).get("state")

    try:
        domain, item_id = await resolve_trace_target(cfg, entity_id)
        out["trace_item_id"] = item_id
        traces = await list_traces(cfg, domain, item_id)
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
        return out

    for row in traces[:limit]:
        run_id = row.get("run_id") or row.get("id")
        run: dict[str, Any] = {
            "run_id": run_id,
            "timestamp": row.get("timestamp") or row.get("last_step") or row.get("started"),
            "trigger": row.get("trigger"),
            "state": row.get("state") or row.get("status"),
            "error": row.get("error"),
        }
        if run_id:
            try:
                detail = await get_trace(cfg, domain, item_id, str(run_id))
                run["steps"] = summarize_trace_steps(detail)
                trigger = detail.get("trigger")
                if trigger and not run["trigger"]:
                    run["trigger"] = trigger
            except Exception as exc:  # noqa: BLE001
                run["detail_error"] = str(exc)
        out["runs"].append(run)
    return out


async def fetch_traces(
    cfg: HaConfig,
    automation_ids: list[str],
    script_ids: list[str],
    states: list[dict],
    *,
    json_mode: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not json_mode:
        print_section("Automation & script traces (latest runs)")

    targets: list[tuple[str, str]] = []
    for item_id in automation_ids:
        eid = entity_id_for_automation(states, item_id) or f"automation.{item_id}"
        targets.append((item_id, eid))
    for eid in script_ids:
        targets.append((eid.split(".", 1)[-1], eid))

    for config_id, entity_id in targets:
        if not json_mode:
            print(f"\n--- {entity_id} (lookup: {config_id}) ---")
        row = await fetch_traces_for_entity(cfg, entity_id)
        row["config_id"] = config_id
        results.append(row)
        if json_mode:
            continue
        print(f"  state={row.get('state')}  last_triggered={row.get('last_triggered') or 'never'}")
        print(f"  trace item_id={row.get('trace_item_id')}")
        if row.get("error"):
            print(f"  trace/list failed: {row['error']}")
            continue
        if not row["runs"]:
            print("  (no stored traces)")
            continue
        for run in row["runs"]:
            print(
                f"  run={run.get('run_id')}  at={run.get('timestamp')}  "
                f"trigger={run.get('trigger')}  state={run.get('state')}"
            )
            if run.get("error"):
                print(f"    error: {run['error']}")
            for step in run.get("steps") or []:
                print(step)
            if run.get("detail_error"):
                print(f"    trace/get failed: {run['detail_error']}")
    return results


def fetch_logbook_and_history(
    cfg: HaConfig,
    *,
    hours: int,
    entities: list[str],
    json_mode: bool = False,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    start = iso(now - timedelta(hours=hours))
    end = iso(now)
    payload: dict[str, Any] = {"logbook": [], "history": []}

    if not json_mode:
        print_section(f"Logbook (last {hours}h)")
    try:
        rows = get_logbook(cfg, start=start, end=end, entities=list(entities))
        payload["logbook"] = rows[-40:]
        if json_mode:
            pass
        elif not rows:
            print("  (empty)")
        else:
            for row in payload["logbook"]:
                when = str(row.get("when", ""))[:19]
                name = row.get("name") or row.get("entity_id", "")
                state = row.get("state", "")
                msg = row.get("message", "")
                print(f"  {when}  {name}  {state}  {msg}")
    except Exception as exc:  # noqa: BLE001
        payload["logbook_error"] = str(exc)
        if not json_mode:
            print(f"  logbook failed: {exc}")

    key = [e for e in entities if e.startswith(("binary_sensor.", "input_boolean.", "sensor."))][:12]
    if not json_mode:
        print_section(f"History state changes (last {hours}h, key entities)")
    try:
        hist = get_history(cfg, start=start, end=end, entities=key, minimal=True)
        for series in hist:
            if not series:
                continue
            eid = series[0].get("entity_id", "?")
            changes = [f"{s.get('last_changed', '')[:19]}→{s.get('state')}" for s in series[-6:]]
            row = {"entity_id": eid, "changes": changes}
            payload["history"].append(row)
            if not json_mode:
                print(f"  {eid}: {' | '.join(changes)}")
    except Exception as exc:  # noqa: BLE001
        payload["history_error"] = str(exc)
        if not json_mode:
            print(f"  history failed: {exc}")
    return payload


def fetch_logs(cfg: HaConfig, *, json_mode: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if not json_mode:
        print_section("System log (errors/warnings)")
    try:
        rows = run_async(list_system_log(cfg))
        payload["system_log"] = rows[-30:]
        if json_mode:
            pass
        elif not rows:
            print("  (empty)")
        else:
            for row in payload["system_log"]:
                when = str(row.get("timestamp", row.get("when", "")))[:19]
                level = row.get("level", row.get("levelname", ""))
                src = row.get("source", row.get("name", ""))
                msg = row.get("message", row.get("msg", ""))
                print(f"  {when}  {level:<8}  {src}  {msg}")
    except Exception as exc:  # noqa: BLE001
        payload["system_log_error"] = str(exc)
        if not json_mode:
            print(f"  system_log/list failed: {exc}")

    if not json_mode:
        print_section("Error log tail (home-assistant.log)")
    try:
        text = get_error_log(cfg, lines=40)
        payload["error_log"] = text
        if not json_mode:
            print(text or "  (empty)")
    except Exception as exc:  # noqa: BLE001
        payload["error_log_error"] = str(exc)
        if not json_mode:
            print(f"  error_log failed: {exc}")
    return payload


async def main_async(args: argparse.Namespace) -> int:
    try:
        cfg = resolve_ha_config(url=args.ha_url, token=args.token)
    except HaAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.verify:
        summary = await verify_connection(cfg)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print_section("Connection verify")
            print(json.dumps(summary, indent=2))
        ok = (
            summary["rest_ok"]
            and summary["websocket_ok"]
            and summary["traces_ok"]
            and summary["logbook_ok"]
            and not summary["errors"]
        )
        return 0 if ok else 1

    summary = await verify_connection(cfg)
    report: dict[str, Any] = {"connection": summary}

    if not summary["rest_ok"]:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_section("Connection")
            print(json.dumps(summary, indent=2))
            print("\nCannot continue without REST access.", file=sys.stderr)
        return 1

    entities = list(TOPIC_ENTITIES.get(args.topic, TOPIC_ENTITIES["arrival"]))
    automation_ids = list(TOPIC_AUTOMATIONS.get(args.topic, TOPIC_AUTOMATIONS["arrival"]))
    script_ids = list(TOPIC_SCRIPTS.get(args.topic, TOPIC_SCRIPTS["arrival"]))
    if args.automation:
        automation_ids = [args.automation]
        script_ids = []

    if not args.json:
        print_section("Connection")
        print(json.dumps(summary, indent=2))

    entity_states: list[dict[str, Any]] = []
    missing = 0
    if not args.json:
        print_section("Entity states")
    for eid in entities:
        st = get_state(cfg, eid)
        if st is None:
            missing += 1
            entity_states.append({"entity_id": eid, "missing": True})
            if not args.json:
                print(f"  {eid:<52} MISSING")
        else:
            fn = (st.get("attributes") or {}).get("friendly_name", "")
            entity_states.append(
                {"entity_id": eid, "state": st["state"], "friendly_name": fn, "last_changed": st.get("last_changed")}
            )
            if not args.json:
                print(f"  {eid:<52} {st['state']:<12} {fn}")
    if missing and not args.json:
        print(f"\n⚠ {missing} entities missing — related automations may not trigger.")
    report["entities"] = entity_states

    states = get_states(cfg)
    automations: list[dict[str, Any]] = []
    if not args.json:
        print_section("Matching automations (enabled + last_triggered)")
    for item_id in automation_ids:
        eid = entity_id_for_automation(states, item_id)
        row: dict[str, Any] = {"config_id": item_id, "entity_id": eid}
        if not eid:
            row["missing"] = True
            automations.append(row)
            if not args.json:
                print(f"  {item_id:<45} NOT FOUND in entity registry")
            continue
        st = next((s for s in states if s["entity_id"] == eid), None)
        if st:
            attrs = st.get("attributes") or {}
            row.update(
                {
                    "state": st["state"],
                    "last_triggered": st.get("last_triggered"),
                    "config_id_attr": attrs.get("id"),
                }
            )
            if not args.json:
                print(
                    f"  {eid:<55} state={st['state']:<8} "
                    f"last={st.get('last_triggered') or 'never'}"
                )
                if attrs.get("id"):
                    print(f"    config id: {attrs['id']}")
        automations.append(row)
    report["automations"] = automations

    report["traces"] = await fetch_traces(
        cfg, automation_ids, script_ids, states, json_mode=args.json
    )
    report["events"] = fetch_logbook_and_history(
        cfg, hours=args.hours, entities=entities, json_mode=args.json
    )
    report["logs"] = fetch_logs(cfg, json_mode=args.json)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch HA diagnostics for gate/garage arrival")
    parser.add_argument("--ha-url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--verify", action="store_true", help="Only test HA connectivity")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON report")
    parser.add_argument("--hours", type=int, default=12)
    parser.add_argument("--topic", default="arrival", choices=sorted(TOPIC_ENTITIES))
    parser.add_argument("--automation", default=None)
    args = parser.parse_args()
    return run_async(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

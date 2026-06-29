from __future__ import annotations

import argparse
import json
import sys

from xero_mcp.audit import read_recent_events
from xero_mcp.auth import AuthError, ensure_access_token, fetch_connections, login_interactive, status
from xero_mcp.config import DEFAULT_APP_NAME, ensure_config_dir, load_credentials, load_token_store, save_credentials
from xero_mcp.maintain import doctor_report, run_maintenance


def _default_scopes() -> list[str]:
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / "xero.credentials.example.json"
    return json.loads(example.read_text())["scopes"]


def cmd_init(args: argparse.Namespace) -> int:
    scopes = args.scopes.split() if args.scopes else _default_scopes()

    from xero_mcp.config import Credentials

    creds = Credentials(
        client_id=args.client_id,
        client_secret=args.client_secret,
        redirect_uri=args.redirect_uri,
        scopes=scopes,
        app_name=args.app_name or DEFAULT_APP_NAME,
    )
    save_credentials(creds)
    ensure_config_dir()
    print(f"Saved credentials (secret in Keychain) under {ensure_config_dir()}")
    print(f"Use this exact app name in Xero developer portal: {creds.app_name}")
    print("Next: python -m xero_mcp login")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    try:
        store = login_interactive(open_browser=not args.no_browser)
        run_maintenance(live_connections=False)
    except AuthError as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1
    connections = store.get("connections") or []
    print(f"Authenticated. {len(connections)} organisation(s) connected:")
    for conn in connections:
        print(f"  - {conn.get('tenantName')} ({conn.get('tenantId')})")
    print("")
    print("Verify in Xero: Settings → General Settings → Connected apps")
    return 0


def cmd_token(_args: argparse.Namespace) -> int:
    try:
        print(ensure_access_token())
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    try:
        load_credentials()
        info = status()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(info, indent=2))
    return 0


def cmd_refresh_connections(_args: argparse.Namespace) -> int:
    try:
        report = run_maintenance(live_connections=True)
        print(json.dumps(report.get("connections") or [], indent=2))
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0 if report.get("healthy") else 1


def cmd_list_orgs(args: argparse.Namespace) -> int:
    from xero_mcp.tenants import TenantError, active_org_summary, ensure_default_active_org

    try:
        ensure_default_active_org()
        if args.json:
            print(json.dumps(active_org_summary(), indent=2))
        else:
            summary = active_org_summary()
            active = summary.get("active")
            print(f"Active: {active['tenant_name'] if active else 'none'} ({active['slug'] if active else '-'})")
            for org in summary.get("organisations") or []:
                mark = "*" if active and org["slug"] == active["slug"] else " "
                print(f"{mark} {org['slug']:40} {org['tenant_name']}")
    except TenantError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_use_org(args: argparse.Namespace) -> int:
    from xero_mcp.tenants import TenantError, set_active_organisation

    try:
        org = set_active_organisation(args.org)
        print(f"Active organisation: {org.tenant_name} ({org.slug})")
    except TenantError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_sync_orgs(_args: argparse.Namespace) -> int:
    from xero_mcp.tenants import TenantError, sync_org_registry

    try:
        orgs = sync_org_registry()
        for org in orgs:
            print(f"  {org.slug:40} {org.tenant_name}")
        print(f"Synced {len(orgs)} organisation(s).")
    except TenantError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_maintain(args: argparse.Namespace) -> int:
    report = run_maintenance(live_connections=not args.skip_connections)
    if args.quiet:
        return 0 if report.get("healthy") else 1
    print(json.dumps(report, indent=2))
    return 0 if report.get("healthy") else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor_report()
    if not args.json:
        for line in report["summary_lines"]:
            print(line)
        recent = read_recent_events(5)
        if recent:
            print("")
            print("Recent audit events:")
            for event in recent:
                print(f"  {event.get('ts')}  {event.get('event')}")
    else:
        report["recent_audit"] = read_recent_events(10)
        print(json.dumps(report, indent=2))
    health = report.get("health") or {}
    return 0 if health.get("healthy") else 1


def cmd_inbound_init(args: argparse.Namespace) -> int:
    from xero_mcp.inbound.config import init_inbound_config

    path = init_inbound_config(args.domain)
    print(f"Created {path}")
    print("Next: configure Cloudflare Email Routing, then bash scripts/setup-phase2.sh")
    return 0


def cmd_inbound_serve(args: argparse.Namespace) -> int:
    from xero_mcp.inbound.daemon import start_maintain_thread
    from xero_mcp.inbound.webhook import serve_webhook

    if getattr(args, "daemon", False):
        start_maintain_thread(interval_seconds=args.maintain_interval)
    port = args.port or None
    serve_webhook(host=args.host, port=port)
    return 0


def cmd_inbound_sync_portfolio(args: argparse.Namespace) -> int:
    from xero_mcp.inbound.portfolio_sync import init_portfolio_entities, sync_portfolio_from_notified

    if args.init_only:
        path = init_portfolio_entities()
        print(f"Portfolio entities: {path}")
        return 0
    path = sync_portfolio_from_notified(jwt=args.jwt or None)
    print(f"Synced portfolio entities → {path}")
    return 0


def cmd_inbound_queue(args: argparse.Namespace) -> int:
    from xero_mcp.inbound.processor import queue_summary

    summary = queue_summary()
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("Routes:")
        for route in summary["routes"]:
            print(f"  {route['address']} → {route['org_slug']}")
        print("")
        for msg in summary["messages"]:
            print(f"{msg['status']:10} {msg['id'][:8]}… {msg.get('subject','')[:50]}")
    return 0


def cmd_inbound_process(args: argparse.Namespace) -> int:
    from xero_mcp.inbound.processor import process_message, process_pending

    if args.pending:
        results = process_pending()
        print(json.dumps(results, indent=2))
        return 0 if all(r.get("ok") for r in results) else 1
    if not args.message_id:
        print("Provide message_id or --pending", file=sys.stderr)
        return 1
    result = process_message(args.message_id, force=bool(getattr(args, "force", False)))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_inbound_heal(args: argparse.Namespace) -> int:
    from xero_mcp.inbound.heal import health_summary, run_heal

    if getattr(args, "scan_only", False):
        payload = health_summary(scan_limit=args.limit or 50)
        print(json.dumps(payload, indent=2))
        return 0

    summary = run_heal(dry_run=bool(args.dry_run), limit=args.limit)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"Heal: candidates={summary['candidates']} attempted={summary['attempted']} "
            f"ok={summary['healed_ok']} skipped={summary['skipped']} dry_run={summary['dry_run']}"
        )
        for item in summary.get("results") or []:
            mid = (item.get("message_id") or "")[:8]
            print(
                f"  {mid}… ok={item.get('ok')} skipped={item.get('skipped')} "
                f"reason={item.get('reason')}"
            )
    if summary.get("dry_run"):
        return 0
    return 0 if summary.get("healed_ok", 0) >= 0 else 1


def cmd_inbound_test(args: argparse.Namespace) -> int:
    from email.message import EmailMessage

    from xero_mcp.inbound.config import load_inbound_config
    from xero_mcp.inbound.parser import enqueue_email, parse_eml_bytes
    from xero_mcp.inbound.processor import process_queued_records

    pdf_path = __import__("pathlib").Path(args.pdf)
    if not pdf_path.exists():
        print(f"Missing PDF: {pdf_path}", file=sys.stderr)
        return 1

    message = EmailMessage()
    message["To"] = args.to
    message["From"] = args.from_addr
    message["Subject"] = args.subject
    message.set_content("Automated inbound test message.")
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    records = enqueue_email(parse_eml_bytes(message.as_bytes()), source="test")
    print(json.dumps(records, indent=2))
    config = load_inbound_config()
    if config.auto_process:
        results = process_queued_records(records)
        if results:
            print(json.dumps(results, indent=2))
            return 0 if all(r.get("ok") for r in results) else 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xero-mcp",
        description="Xero OAuth helper for @xeroapi/xero-mcp-server in Cursor",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Save Xero app client id; secret → macOS Keychain")
    init.add_argument("--client-id", required=True)
    init.add_argument("--client-secret", required=True)
    init.add_argument("--redirect-uri", default="http://localhost:8765/callback")
    init.add_argument("--app-name", default=DEFAULT_APP_NAME, help="Shown in Xero Connected apps")
    init.add_argument("--scopes", default="", help="Space-separated scopes (optional)")
    init.set_defaults(func=cmd_init)

    login = sub.add_parser("login", help="One-time OAuth PKCE flow in browser")
    login.add_argument("--no-browser", action="store_true")
    login.set_defaults(func=cmd_login)

    sub.add_parser("token", help="Print a valid access token (refresh if needed)").set_defaults(
        func=cmd_token
    )
    sub.add_parser("status", help="Show auth and connected orgs").set_defaults(func=cmd_status)
    sub.add_parser("refresh-connections", help="Re-fetch /connections from Xero").set_defaults(
        func=cmd_refresh_connections
    )

    list_orgs = sub.add_parser("list-orgs", help="Show org slugs and active tenant")
    list_orgs.add_argument("--json", action="store_true")
    list_orgs.set_defaults(func=cmd_list_orgs)

    use_org = sub.add_parser("use-org", help="Set active organisation for xero MCP tools")
    use_org.add_argument("org", help="Slug, name fragment, or tenant id")
    use_org.set_defaults(func=cmd_use_org)

    sub.add_parser("sync-orgs", help="Refresh org slug registry from connections").set_defaults(
        func=cmd_sync_orgs
    )

    maintain = sub.add_parser("maintain", help="Background token refresh + health.json update")
    maintain.add_argument("--quiet", action="store_true")
    maintain.add_argument(
        "--skip-connections",
        action="store_true",
        help="Skip live /connections call (token refresh only)",
    )
    maintain.set_defaults(func=cmd_maintain)

    doctor = sub.add_parser("doctor", help="Health check + where to verify in Xero app")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    inbound = sub.add_parser("inbound", help="Inbound email → Xero bill commands")
    inbound_sub = inbound.add_subparsers(dest="inbound_command", required=True)

    inbound_init = inbound_sub.add_parser("init", help="Create inbound.json with domain + webhook secret")
    inbound_init.add_argument("--domain", required=True, help="e.g. matarikigroup.co.nz")
    inbound_init.set_defaults(func=cmd_inbound_init)

    inbound_serve = inbound_sub.add_parser("serve", help="Run inbound webhook HTTP server")
    inbound_serve.add_argument("--host", default="127.0.0.1")
    inbound_serve.add_argument("--port", type=int, default=0)
    inbound_serve.add_argument(
        "--daemon",
        action="store_true",
        help="Background token refresh loop (for tower Docker)",
    )
    inbound_serve.add_argument("--maintain-interval", type=int, default=900)
    inbound_serve.set_defaults(func=cmd_inbound_serve)

    inbound_sync = inbound_sub.add_parser(
        "sync-portfolio",
        help="Sync Notified portfolio properties → portfolio.entities.json",
    )
    inbound_sync.add_argument("--jwt", default="", help="Notified service JWT (or NOTIFIED_SERVICE_JWT)")
    inbound_sync.add_argument("--init-only", action="store_true", help="Copy example entities file only")
    inbound_sync.set_defaults(func=cmd_inbound_sync_portfolio)

    inbound_queue = inbound_sub.add_parser("queue", help="List inbound queue")
    inbound_queue.add_argument("--json", action="store_true")
    inbound_queue.set_defaults(func=cmd_inbound_queue)

    inbound_process = inbound_sub.add_parser("process", help="Process queued message(s)")
    inbound_process.add_argument("message_id", nargs="?", help="Optional message UUID")
    inbound_process.add_argument("--pending", action="store_true")
    inbound_process.add_argument(
        "--force",
        action="store_true",
        help="Reprocess done/duplicate/failed records (clears prior Xero ids)",
    )
    inbound_process.set_defaults(func=cmd_inbound_process)

    inbound_heal = inbound_sub.add_parser(
        "heal",
        help="Auto-diagnose and retry stuck/failed inbound queue items",
    )
    inbound_heal.add_argument("--dry-run", action="store_true", help="Report actions without processing")
    inbound_heal.add_argument("--limit", type=int, default=10, help="Max records to heal per run")
    inbound_heal.add_argument("--json", action="store_true")
    inbound_heal.add_argument(
        "--scan-only",
        action="store_true",
        help="List candidates and diagnoses only (no heal)",
    )
    inbound_heal.set_defaults(func=cmd_inbound_heal)

    inbound_test = inbound_sub.add_parser("test", help="Simulate inbound email for E2E test")
    inbound_test.add_argument("--to", required=True, help="Route address e.g. bills.morningside@domain")
    inbound_test.add_argument("--pdf", required=True, help="Path to PDF attachment")
    inbound_test.add_argument("--from", dest="from_addr", default="supplier@example.com")
    inbound_test.add_argument("--subject", default="Test supplier invoice")
    inbound_test.set_defaults(func=cmd_inbound_test)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()

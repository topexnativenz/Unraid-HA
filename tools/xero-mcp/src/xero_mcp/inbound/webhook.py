from __future__ import annotations

import cgi
import json
import logging
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from xero_mcp.inbound.config import InboundError, load_inbound_config
from xero_mcp.inbound.parser import enqueue_email, parse_cloudflare_json, parse_eml_bytes, parse_mailgun_form
from xero_mcp.inbound.processor import process_queued_records

log = logging.getLogger("xero-inbound-webhook")


def _verify_secret(provided: str | None) -> None:
    config = load_inbound_config()
    if not config.webhook_secret:
        return
    if not provided or not secrets.compare_digest(provided, config.webhook_secret):
        raise InboundError("Invalid webhook secret")


def _schedule_auto_process(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Run auto-process in a background thread so HTTP returns before Xero API work.

    Cloudflare Email Workers / SWAG time out (~30–100s). Synchronous process_queued_records
    (429 backoff + process_delay_sec stagger) can exceed that and cause HTTP 524 — email rejected
    before the queue record is durable.
    """
    config = load_inbound_config()
    if not config.auto_process:
        return None
    pending = [r for r in records if r.get("status") == "pending"]
    if not pending:
        return None

    def _run() -> None:
        try:
            process_queued_records(pending)
        except Exception:
            log.exception(
                "background auto-process failed ids=%s",
                [r.get("id") for r in pending],
            )

    threading.Thread(
        target=_run,
        name=f"xero-inbound-process-{pending[0].get('id', 'batch')[:8]}",
        daemon=True,
    ).start()
    return {"async": True, "pending_count": len(pending)}


class InboundWebhookHandler(BaseHTTPRequestHandler):
    server_version = "XeroInboundWebhook/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        log.info("%s - %s", self.address_string(), format % args)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_health(self) -> None:
        self._json_response(200, {"ok": True, "service": "xero-inbound-webhook"})

    def _handle_ingest(self) -> None:
        try:
            _verify_secret(self.headers.get("X-Xero-Inbound-Secret"))
            raw = self._read_body()
            if not raw:
                raise InboundError("Empty body")
            parsed = parse_eml_bytes(raw)
            records = enqueue_email(parsed, source="eml-upload")
            scheduled = _schedule_auto_process(records)
            self._json_response(
                200,
                {"ok": True, "queued": records, "processed": scheduled},
            )
        except InboundError as exc:
            self._json_response(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            log.exception("ingest failed")
            self._json_response(500, {"ok": False, "error": str(exc)})

    def _handle_mailgun(self) -> None:
        try:
            _verify_secret(self.headers.get("X-Xero-Inbound-Secret"))
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                raise InboundError("Expected multipart/form-data from Mailgun")
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            }
            form = cgi.FieldStorage(fp=self.rfile, environ=environ, keep_blank_values=True)
            fields = {key: form.getvalue(key) for key in form.keys()}
            files: dict[str, Any] = {}
            if hasattr(form, "list") and form.list:
                for item in form.list:
                    if item.filename:
                        files[item.name] = item.file.read()
            parsed = parse_mailgun_form(fields, files)
            records = enqueue_email(parsed, source="mailgun")
            scheduled = _schedule_auto_process(records)
            self._json_response(200, {"ok": True, "queued": records, "processed": scheduled})
        except InboundError as exc:
            self._json_response(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            log.exception("mailgun failed")
            self._json_response(500, {"ok": False, "error": str(exc)})

    def _handle_cloudflare(self) -> None:
        """Accept-always for Cloudflare Email Worker — never 5xx on authenticated POST."""
        try:
            _verify_secret(self.headers.get("X-Xero-Inbound-Secret"))
        except InboundError as exc:
            self._json_response(401, {"ok": False, "error": str(exc)})
            return
        try:
            payload = json.loads(self._read_body().decode() or "{}")
            parsed = parse_cloudflare_json(payload)
            records = enqueue_email(parsed, source="cloudflare")
            scheduled = _schedule_auto_process(records)
            self._json_response(200, {"ok": True, "queued": records, "processed": scheduled})
        except InboundError as exc:
            log.warning("cloudflare ingest soft-fail: %s", exc)
            self._json_response(200, {"ok": False, "error": str(exc), "queued": []})
        except Exception as exc:
            log.exception("cloudflare ingest error (soft-fail)")
            self._json_response(200, {"ok": False, "error": str(exc), "queued": []})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._handle_health()
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/inbound/eml":
            self._handle_ingest()
        elif path == "/inbound/mailgun":
            self._handle_mailgun()
        elif path == "/inbound/cloudflare":
            self._handle_cloudflare()
        else:
            self.send_error(404)


def serve_webhook(host: str = "127.0.0.1", port: int | None = None) -> None:
    config = load_inbound_config()
    bind_port = port or config.webhook_port
    server = ThreadingHTTPServer((host, bind_port), InboundWebhookHandler)
    log.info("Xero inbound webhook listening on http://%s:%s", host, bind_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def serve_webhook_background(host: str = "127.0.0.1", port: int | None = None) -> ThreadingHTTPServer:
    config = load_inbound_config()
    bind_port = port or config.webhook_port
    server = ThreadingHTTPServer((host, bind_port), InboundWebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("Xero inbound webhook background on http://%s:%s", host, bind_port)
    return server

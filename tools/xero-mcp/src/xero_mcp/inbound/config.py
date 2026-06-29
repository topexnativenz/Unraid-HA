from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xero_mcp.config import DEFAULT_CONFIG_DIR, ensure_config_dir

INBOUND_CONFIG_FILE = DEFAULT_CONFIG_DIR / "inbound.json"
INBOUND_DIR = DEFAULT_CONFIG_DIR / "inbound"
QUEUE_DIR = INBOUND_DIR / "queue"
ATTACHMENTS_DIR = INBOUND_DIR / "attachments"
INBOUND_AUDIT_FILE = INBOUND_DIR / "audit.log"
INBOUND_EXAMPLE = Path(__file__).resolve().parents[3] / "xero.inbound.example.json"


class InboundError(RuntimeError):
    pass


@dataclass(frozen=True)
class InboundRoute:
    address: str
    org_slug: str
    document_type: str = "ACCPAY"
    default_account_code: str = "400"
    label: str | None = None


@dataclass(frozen=True)
class InboundConfig:
    domain: str
    webhook_secret: str
    webhook_port: int
    auto_process: bool
    process_delay_sec: float
    default_document_type: str
    default_status: str
    allowed_extensions: tuple[str, ...]
    routes: tuple[InboundRoute, ...]
    intake_addresses: tuple[str, ...]
    allowed_from: tuple[str, ...]
    default_intake_address: str
    routing_mode: str
    default_org_slug: str
    require_attachment: bool
    require_bill_classification: bool
    min_bill_confidence: float
    bill_classifier_mode: str
    allow_xero_links: bool
    allow_xero_link_without_attachment: bool
    allow_email_body_without_attachment: bool
    blocked_sender_domains: tuple[str, ...]

    def route_for_address(self, address: str) -> InboundRoute | None:
        normalized = address.strip().lower()
        for route in self.routes:
            if route.address.lower() == normalized:
                return route
        return None

    def accepts_recipient(self, address: str) -> bool:
        normalized = address.strip().lower()
        if self.route_for_address(normalized):
            return True
        if not self.intake_addresses:
            return False
        return normalized in self.intake_addresses

    def accepts_sender(self, address: str) -> bool:
        normalized = address.strip().lower()
        if not self.allowed_from:
            return False
        return normalized in self.allowed_from


def ensure_inbound_dirs() -> None:
    ensure_config_dir()
    for path in (INBOUND_DIR, QUEUE_DIR, ATTACHMENTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
    try:
        INBOUND_DIR.chmod(0o700)
    except OSError:
        pass


def load_inbound_config() -> InboundConfig:
    if not INBOUND_CONFIG_FILE.exists():
        raise InboundError(
            f"Missing {INBOUND_CONFIG_FILE}. Run: "
            "bash /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp/scripts/setup-phase2.sh"
        )
    data = json.loads(INBOUND_CONFIG_FILE.read_text())
    routes = tuple(
        InboundRoute(
            address=r["address"],
            org_slug=r["org_slug"],
            document_type=r.get("document_type", data.get("default_document_type", "ACCPAY")),
            default_account_code=str(r.get("default_account_code", "400")),
            label=r.get("label"),
        )
        for r in data.get("routes") or []
    )
    intake = tuple(a.strip().lower() for a in (data.get("intake_addresses") or []) if a)
    allowed_from = tuple(a.strip().lower() for a in (data.get("allowed_from") or []) if a)
    default_intake = (data.get("default_intake_address") or "accounts@matarikigroup.co.nz").strip().lower()
    return InboundConfig(
        domain=data.get("domain", ""),
        webhook_secret=data.get("webhook_secret", ""),
        webhook_port=int(data.get("webhook_port", 8766)),
        auto_process=bool(data.get("auto_process", True)),
        process_delay_sec=float(data.get("process_delay_sec", 1.5)),
        default_document_type=data.get("default_document_type", "ACCPAY"),
        default_status=data.get("default_status", "DRAFT"),
        allowed_extensions=tuple(ext.lower() for ext in (data.get("allowed_extensions") or [".pdf"])),
        routes=routes,
        intake_addresses=intake,
        allowed_from=allowed_from,
        default_intake_address=default_intake,
        routing_mode=data.get("routing_mode", "portfolio"),
        default_org_slug=data.get("default_org_slug", "matariki-property-group"),
        require_attachment=bool(data.get("require_attachment", True)),
        require_bill_classification=bool(data.get("require_bill_classification", True)),
        min_bill_confidence=float(data.get("min_bill_confidence", 0.55)),
        bill_classifier_mode=str(data.get("bill_classifier_mode", "heuristic")),
        allow_xero_links=bool(data.get("allow_xero_links", True)),
        allow_xero_link_without_attachment=bool(
            data.get("allow_xero_link_without_attachment", True)
        ),
        allow_email_body_without_attachment=bool(
            data.get("allow_email_body_without_attachment", True)
        ),
        blocked_sender_domains=tuple(
            d.strip().lower()
            for d in (data.get("blocked_sender_domains") or [])
            if d and str(d).strip()
        ),
    )


def effective_process_delay_sec(config: InboundConfig) -> float:
    """Delay between queue items; env XERO_INBOUND_PROCESS_DELAY_SEC overrides inbound.json."""
    env = os.environ.get("XERO_INBOUND_PROCESS_DELAY_SEC")
    if env is not None and str(env).strip() != "":
        try:
            return max(0.0, float(env))
        except ValueError:
            pass
    return max(0.0, config.process_delay_sec)


def init_inbound_config(domain: str) -> Path:
    ensure_inbound_dirs()
    if INBOUND_CONFIG_FILE.exists():
        data = json.loads(INBOUND_CONFIG_FILE.read_text())
        if domain and "REPLACE" in data.get("domain", "REPLACE"):
            data["domain"] = domain
            for route in data.get("routes") or []:
                addr = route.get("address", "")
                if "REPLACE" in addr:
                    local = addr.split("@")[0]
                    route["address"] = f"{local}@{domain}"
        data["webhook_secret"] = data.get("webhook_secret") or secrets.token_urlsafe(32)
        if data["webhook_secret"] == "GENERATE_ON_SETUP":
            data["webhook_secret"] = secrets.token_urlsafe(32)
        INBOUND_CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n")
        INBOUND_CONFIG_FILE.chmod(0o600)
        return INBOUND_CONFIG_FILE

    template = json.loads(INBOUND_EXAMPLE.read_text())
    template["domain"] = domain or template["domain"]
    template["webhook_secret"] = secrets.token_urlsafe(32)
    for route in template.get("routes") or []:
        local = route["address"].split("@")[0]
        route["address"] = f"{local}@{template['domain']}"
    INBOUND_CONFIG_FILE.write_text(json.dumps(template, indent=2) + "\n")
    INBOUND_CONFIG_FILE.chmod(0o600)
    return INBOUND_CONFIG_FILE

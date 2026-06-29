from __future__ import annotations

import email
import email.policy
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from xero_mcp.inbound.attachments import is_bill_attachment, is_signature_image, rank_bill_attachments
from xero_mcp.inbound.bill_splits import (
    build_split_dedupe_key,
    collect_non_bill_attachments,
    split_inbound_into_bills,
)
from xero_mcp.inbound.classifier import ClassificationResult, classify_inbound_email
from xero_mcp.inbound.config import (
    ATTACHMENTS_DIR,
    INBOUND_AUDIT_FILE,
    QUEUE_DIR,
    InboundConfig,
    InboundError,
    InboundRoute,
    ensure_inbound_dirs,
    load_inbound_config,
)
from xero_mcp.inbound.extract import email_from_header, has_actionable_email_bill
from xero_mcp.inbound.xero_links import fetch_invoice_in_org
from xero_mcp.inbound.xero_links import detect_xero_links

_BODY_ATTACHMENT_MENTION_RE = re.compile(
    r"\b(?:attached|please find|enclosed|see attached|file attached)\b",
    re.IGNORECASE,
)

_OFFICE_MIME_PREFIXES = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel",
)


def _infer_attachment_name(filename: str | None, content_type: str) -> str:
    if filename and filename.strip() and filename.strip() != "attachment":
        return Path(filename).name
    lower = (content_type or "").lower()
    if "wordprocessingml" in lower:
        return "attachment.docx"
    if "spreadsheetml" in lower:
        return "attachment.xlsx"
    if lower == "application/msword":
        return "attachment.doc"
    if lower == "application/pdf":
        return "attachment.pdf"
    return filename or "attachment"


def _is_office_mime(content_type: str) -> bool:
    lower = (content_type or "").lower()
    return any(lower.startswith(prefix) for prefix in _OFFICE_MIME_PREFIXES)


def _merge_attachment_lists(
    primary: list[InboundAttachment],
    secondary: list[InboundAttachment],
) -> list[InboundAttachment]:
    seen = {item.sha256 for item in primary}
    merged = list(primary)
    for item in secondary:
        if item.sha256 in seen:
            continue
        seen.add(item.sha256)
        merged.append(item)
    return merged


from xero_mcp.inbound.email_models import InboundAttachment, ParsedInboundEmail

# Re-export for callers that import from parser
__all__ = ["InboundAttachment", "ParsedInboundEmail", "enqueue_email", "parse_eml_bytes"]


def _audit(event: str, **fields: Any) -> None:
    ensure_inbound_dirs()
    record = {"ts": time.time(), "event": event, **fields}
    with INBOUND_AUDIT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def _extract_addresses(header_value: str) -> list[str]:
    if not header_value:
        return []
    return [match.lower() for match in re.findall(r"[\w.+-]+@[\w.-]+\.\w+", header_value)]


def _recipient_candidates(parsed: ParsedInboundEmail) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for address in parsed.to_addresses:
        normalized = address.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _sender_address(from_address: str) -> str:
    return (email_from_header(from_address) or from_address).strip().lower()


def parse_eml_bytes(raw: bytes) -> ParsedInboundEmail:
    message = email.message_from_bytes(raw, policy=email.policy.default)
    attachments: list[InboundAttachment] = []
    body_text = ""

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type in ("multipart/mixed", "multipart/alternative", "multipart/related"):
                continue
            disposition = part.get_content_disposition()
            filename = _infer_attachment_name(part.get_filename(), content_type)
            payload = part.get_payload(decode=True)
            is_image = content_type.startswith("image/")
            is_office = _is_office_mime(content_type)
            is_attachment = disposition == "attachment" or (
                disposition != "inline"
                and content_type not in ("text/plain", "text/html", "message/rfc822")
            )
            is_inline_bill = disposition == "inline" and is_office

            if payload and filename and (is_attachment or is_inline_bill):
                if disposition == "inline" and is_image:
                    if is_signature_image(filename, len(payload), content_type):
                        continue
                attachments.append(
                    InboundAttachment(
                        name=filename,
                        content_type=content_type,
                        data=payload,
                    )
                )
            elif content_type == "text/plain" and not body_text:
                payload = part.get_payload(decode=True) or b""
                body_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            elif content_type == "text/html" and not body_text:
                payload = part.get_payload(decode=True) or b""
                html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                body_text = re.sub(r"<[^>]+>", " ", html)
                body_text = re.sub(r"\s+", " ", body_text).strip()
    else:
        payload = message.get_payload(decode=True) or b""
        body_text = payload.decode(message.get_content_charset() or "utf-8", errors="replace")

    return ParsedInboundEmail(
        to_addresses=_extract_addresses(message.get("To", ""))
        + _extract_addresses(message.get("Cc", ""))
        + _extract_addresses(message.get("Delivered-To", ""))
        + _extract_addresses(message.get("Envelope-To", ""))
        + _extract_addresses(message.get("X-Original-To", "")),
        from_address=(message.get("From") or "").strip(),
        subject=(message.get("Subject") or "").strip(),
        attachments=attachments,
        body_text=body_text,
    )


def parse_mailgun_form(form: dict[str, Any], files: dict[str, Any]) -> ParsedInboundEmail:
    count = int(form.get("attachment-count") or 0)
    attachments: list[InboundAttachment] = []
    for index in range(1, count + 1):
        uploaded = files.get(f"attachment-{index}")
        if not uploaded:
            continue
        data = uploaded if isinstance(uploaded, bytes) else uploaded.read()
        name = form.get(f"attachment-{index}-name") or f"attachment-{index}"
        attachments.append(
            InboundAttachment(
                name=str(name),
                content_type=form.get(f"attachment-{index}-type") or "application/octet-stream",
                data=data,
            )
        )
    return ParsedInboundEmail(
        to_addresses=_extract_addresses(str(form.get("recipient", ""))),
        from_address=str(form.get("sender") or form.get("from") or ""),
        subject=str(form.get("subject") or ""),
        attachments=attachments,
        body_text=str(form.get("body-plain") or form.get("stripped-text") or ""),
    )


def parse_cloudflare_json(payload: dict[str, Any]) -> ParsedInboundEmail:
    import base64

    attachments: list[InboundAttachment] = []
    for item in payload.get("attachments") or []:
        raw = base64.b64decode(item["data_base64"])
        name = _infer_attachment_name(item.get("filename"), item.get("content_type") or "")
        attachments.append(
            InboundAttachment(
                name=name,
                content_type=item.get("content_type") or "application/octet-stream",
                data=raw,
            )
        )

    body_text = str(payload.get("text") or "")
    raw_b64 = payload.get("raw_base64")
    if raw_b64:
        eml = parse_eml_bytes(base64.b64decode(raw_b64))
        attachments = _merge_attachment_lists(attachments, eml.attachments)
        if not body_text.strip():
            body_text = eml.body_text

    to_parts = [str(payload.get("to") or ""), str(payload.get("cc") or "")]
    return ParsedInboundEmail(
        to_addresses=_extract_addresses(" ".join(to_parts)),
        from_address=str(payload.get("from") or ""),
        subject=str(payload.get("subject") or ""),
        attachments=attachments,
        body_text=body_text,
    )


def _intake_sort_key(address: str, config: InboundConfig) -> tuple[int, str]:
    if config.route_for_address(address):
        return (0, address)
    if address == config.default_intake_address:
        return (1, address)
    return (2, address)


def _resolve_recipient(parsed: ParsedInboundEmail, config: InboundConfig) -> tuple[str, InboundRoute | None]:
    candidates = _recipient_candidates(parsed)
    matched = [address for address in candidates if config.accepts_recipient(address)]
    if matched:
        best = min(matched, key=lambda address: _intake_sort_key(address, config))
        if best == config.default_intake_address or config.route_for_address(best):
            return best, config.route_for_address(best)
        sender = _sender_address(parsed.from_address)
        if config.accepts_sender(sender) and config.accepts_recipient(config.default_intake_address):
            return config.default_intake_address, config.route_for_address(config.default_intake_address)
        return best, config.route_for_address(best)

    sender = _sender_address(parsed.from_address)
    if config.accepts_sender(sender):
        fallback = config.default_intake_address
        if config.accepts_recipient(fallback):
            return fallback, config.route_for_address(fallback)

    raise InboundError(
        f"No intake address for recipient(s): {parsed.to_addresses}. "
        f"Configured intake: {list(config.intake_addresses)} "
        f"allowed_from: {list(config.allowed_from)} "
        f"legacy routes: {[r.address for r in config.routes]}"
    )


def _resolve_org(
    parsed: ParsedInboundEmail,
    config: InboundConfig,
    route: InboundRoute | None,
    matched_to: str,
) -> tuple[str, str, ClassificationResult | None, str]:
    if route:
        return route.org_slug, route.default_account_code, None, "legacy_alias"

    classification = classify_inbound_email(
        subject=parsed.subject,
        body_text=parsed.body_text,
        from_address=parsed.from_address,
        to_address=matched_to,
    )
    account_code = "400"
    if config.routes:
        for r in config.routes:
            if r.org_slug == classification.org_slug:
                account_code = r.default_account_code
                break
    return classification.org_slug, account_code, classification, classification.method


def _allowed_attachment(name: str, config: InboundConfig) -> bool:
    suffix = Path(name).suffix.lower()
    return suffix in config.allowed_extensions


def _store_attachments(
    attachment_dir: Path,
    attachments: list[InboundAttachment],
) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    for attachment in attachments:
        path = attachment_dir / Path(attachment.name).name
        path.write_bytes(attachment.data)
        stored.append(
            {
                "name": path.name,
                "path": str(path),
                "sha256": attachment.sha256,
                "content_type": attachment.content_type,
                "size": len(attachment.data),
                "is_primary": True,
            }
        )
    return stored


def enqueue_email(parsed: ParsedInboundEmail, *, source: str = "email") -> list[dict[str, Any]]:
    """Enqueue one queue record per bill (attachment, link group, or body-only)."""
    config = load_inbound_config()
    matched_to, route = _resolve_recipient(parsed, config)
    org_slug, account_code, classification, routing_method = _resolve_org(
        parsed, config, route, matched_to
    )
    usable = [a for a in parsed.attachments if _allowed_attachment(a.name, config)]
    bill_attachments = [
        a for a in usable if is_bill_attachment(a.name, len(a.data), a.content_type)
    ]
    xero_links = detect_xero_links(parsed.body_text)
    has_xero_link = bool(xero_links)
    has_bill_file = bool(bill_attachments)
    has_actionable_body = has_actionable_email_bill(
        subject=parsed.subject,
        body_text=parsed.body_text,
        from_address=parsed.from_address,
    )
    missing_attachment = config.require_attachment and not has_bill_file and not (
        config.allow_xero_links
        and config.allow_xero_link_without_attachment
        and has_xero_link
    ) and not (config.allow_email_body_without_attachment and has_actionable_body)

    source_message_id = str(uuid.uuid4())
    attachment_dir = ATTACHMENTS_DIR / source_message_id
    attachment_dir.mkdir(parents=True, exist_ok=True)

    splits = split_inbound_into_bills(
        parsed,
        bill_attachments=bill_attachments,
        xero_links=xero_links,
        config=config,
        has_actionable_body=has_actionable_body,
    )
    extra_images = collect_non_bill_attachments(parsed, config, splits)

    document_type = route.document_type if route else config.default_document_type
    routing_detail: dict[str, Any] | None = None
    if classification:
        routing_detail = {
            "method": classification.method,
            "confidence": classification.confidence,
            "matched_property": classification.matched_property,
            "matched_keyword": classification.matched_keyword,
            "notes": classification.notes,
        }

    attach_error = None
    if missing_attachment:
        attach_error = (
            f"No bill attachments ({', '.join(config.allowed_extensions)}) "
            f"in message to {matched_to} — only signature/logo images found"
        )
        if not has_xero_link and not has_actionable_body:
            attach_error += " and no Xero bill link or bill data in body"

    attachment_warning = None
    if (
        not bill_attachments
        and _BODY_ATTACHMENT_MENTION_RE.search(parsed.body_text or "")
        and not has_xero_link
    ):
        attachment_warning = (
            "Email mentions an attachment but no pdf/docx/doc/xlsx was received "
            "(forward may have dropped the file; only inline images may have arrived)"
        )

    records: list[dict[str, Any]] = []
    for split in splits:
        message_id = str(uuid.uuid4())
        to_store = list(split.attachments)
        if split.split_index == 0 and extra_images:
            to_store = to_store + extra_images
        stored = _store_attachments(attachment_dir, to_store)

        dedupe_key = build_split_dedupe_key(
            org_slug=org_slug,
            from_address=parsed.from_address,
            split=split,
        )

        status = "failed" if missing_attachment else "pending"
        error = attach_error
        attach_sha = split.attachments[0].sha256 if split.attachments else None
        if _is_duplicate(dedupe_key, message_id) or (
            attach_sha
            and _is_duplicate_attachment(
                org_slug=org_slug,
                attachment_sha256=attach_sha,
                invoice_hint=split.invoice_hint,
                current_id=message_id,
            )
        ):
            status = "duplicate"
            error = "Duplicate of a previously processed bill from this sender"

        record = {
            "id": message_id,
            "status": status,
            "source": source,
            "received_at": time.time(),
            "source_message_id": source_message_id,
            "split_index": split.split_index,
            "split_total": split.split_total,
            "split_kind": split.kind,
            "invoice_hint": split.invoice_hint,
            "to": matched_to,
            "from": parsed.from_address,
            "subject": parsed.subject,
            "org_slug": org_slug,
            "routing_method": routing_method,
            "routing": routing_detail,
            "document_type": document_type,
            "default_account_code": account_code,
            "attachments": stored,
            "xero_links": [
                {"url": link.url, "invoice_id": link.invoice_id, "kind": link.kind}
                for link in split.xero_links
            ],
            "dedupe_key": dedupe_key,
            "body_text": parsed.body_text[:8000],
            "xero_invoice_id": None,
            "xero_invoice_ids": [],
            "error": error,
        }
        if attachment_warning:
            record["attachment_warning"] = attachment_warning

        _write_queue_record(record)
        records.append(record)

        if status == "duplicate":
            _audit(
                "inbound_duplicate",
                id=message_id,
                source_message_id=source_message_id,
                org_slug=org_slug,
                to=matched_to,
                split_index=split.split_index,
            )
        elif missing_attachment:
            _audit(
                "inbound_rejected",
                id=message_id,
                source_message_id=source_message_id,
                org_slug=org_slug,
                to=matched_to,
                error=attach_error,
            )
        else:
            _audit(
                "inbound_received",
                id=message_id,
                source_message_id=source_message_id,
                org_slug=org_slug,
                to=matched_to,
                routing=routing_method,
                split_kind=split.kind,
                split_index=split.split_index,
                split_total=split.split_total,
            )

    return records


def _prior_done_bill_still_active(record: dict[str, Any]) -> bool:
    invoice_id = record.get("xero_invoice_id")
    if not invoice_id:
        return False
    org_slug = record.get("org_slug") or ""
    try:
        invoice = fetch_invoice_in_org(org_slug=org_slug, invoice_id=str(invoice_id))
    except InboundError:
        return False
    if not invoice:
        return False
    return str(invoice.get("Status") or "").upper() != "DELETED"


def _is_duplicate_attachment(
    *,
    org_slug: str,
    attachment_sha256: str,
    invoice_hint: str | None,
    current_id: str,
) -> bool:
    from xero_mcp.inbound.bill_splits import format_invoice_hint

    hint_number = format_invoice_hint(invoice_hint)
    for path in QUEUE_DIR.glob("*.json"):
        if path.stem == current_id:
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if data.get("status") != "done" or data.get("org_slug") != org_slug:
            continue
        if not _prior_done_bill_still_active(data):
            continue
        for item in data.get("attachments") or []:
            if item.get("sha256") != attachment_sha256:
                continue
            prior_hint = format_invoice_hint(data.get("invoice_hint"))
            prior_inv = (data.get("extracted") or {}).get("invoice_number")
            if hint_number and (prior_hint == hint_number or prior_inv == hint_number):
                return True
            if not hint_number:
                return True
    return False


def _is_duplicate(dedupe_key: str, current_id: str) -> bool:
    for path in QUEUE_DIR.glob("*.json"):
        if path.stem == current_id:
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if data.get("dedupe_key") != dedupe_key or data.get("status") != "done":
            continue
        if _prior_done_bill_still_active(data):
            return True
    return False


def _write_queue_record(record: dict[str, Any]) -> None:
    ensure_inbound_dirs()
    path = QUEUE_DIR / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    path.chmod(0o600)


def load_queue_record(message_id: str) -> dict[str, Any]:
    path = QUEUE_DIR / f"{message_id}.json"
    if not path.exists():
        raise InboundError(f"Unknown inbound message id: {message_id}")
    return json.loads(path.read_text())


def save_queue_record(record: dict[str, Any]) -> None:
    _write_queue_record(record)


def list_queue_records(*, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    ensure_inbound_dirs()
    records: list[dict[str, Any]] = []
    for path in sorted(QUEUE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if status and data.get("status") != status:
            continue
        records.append(data)
        if len(records) >= limit:
            break
    return records

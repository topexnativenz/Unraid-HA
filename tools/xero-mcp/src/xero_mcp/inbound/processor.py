from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from xero_mcp.audit import audit_event
from xero_mcp.inbound.attachments import (
    attachment_priority,
    collect_bill_attachment_files,
    is_bill_attachment,
    is_signature_image,
)
from xero_mcp.inbound.bill_gate import is_actionable_bill
from xero_mcp.inbound.bill_splits import format_invoice_hint
from xero_mcp.inbound.config import InboundError, effective_process_delay_sec, load_inbound_config
from xero_mcp.inbound.document_text import extract_text_from_attachment
from xero_mcp.inbound.extract import (
    build_bill_reference,
    build_line_description,
    extract_from_email,
    extraction_summary,
    has_actionable_email_bill,
    is_xero_reminder_email,
    merge_extraction,
    coalesce_pdf_invoice_sections,
    split_extracted_text_by_invoices,
)
from xero_mcp.inbound.parser import (
    load_queue_record,
    list_queue_records,
    save_queue_record,
)
from xero_mcp.inbound.xero_bills import create_draft_bill, update_draft_bill
from xero_mcp.inbound.xero_links import (
    XeroLink,
    detect_xero_links,
    primary_xero_link,
    resolve_xero_links,
    try_fetch_external_pdf,
)
from xero_mcp.tenants import set_active_organisation

_process_lock = threading.Lock()


def process_queued_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process pending queue items sequentially (global lock + stagger for Xero rate limits)."""
    config = load_inbound_config()
    delay = effective_process_delay_sec(config)
    pending_ids = [r["id"] for r in records if r.get("status") == "pending"]
    if not pending_ids:
        return []
    results: list[dict[str, Any]] = []
    with _process_lock:
        for index, message_id in enumerate(pending_ids):
            if index > 0 and delay > 0:
                time.sleep(delay)
            results.append(_process_message_impl(message_id))
    return results


def _reject_record(record: dict[str, Any], *, reason: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    record["status"] = "rejected"
    record["error"] = reason
    record["processed_at"] = time.time()
    if detail:
        record["rejection"] = detail
    save_queue_record(record)
    audit_event("inbound_rejected", id=record["id"], reason=reason)
    return {"ok": False, "rejected": True, "reason": reason, "record": record}


def _ordered_attachments(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        attachments,
        key=lambda item: attachment_priority(
            item.get("name") or "",
            int(item.get("size") or 0),
            item.get("content_type") or "",
        ),
        reverse=True,
    )


def _read_attachment_bytes(item: dict[str, Any]) -> bytes:
    with open(item["path"], "rb") as handle:
        return handle.read()


def _select_primary_attachment(
    attachments: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, bytes]:
    bill_files = collect_bill_attachment_files(attachments, read_bytes=_read_attachment_bytes)
    if bill_files:
        primary_name, primary_bytes = bill_files[0]
        primary = next(
            (item for item in attachments if Path(item.get("name") or "").name == primary_name),
            {"name": primary_name},
        )
        return primary, primary_bytes

    ordered = _ordered_attachments(attachments)
    for item in ordered:
        name = item.get("name") or ""
        size = int(item.get("size") or 0)
        if is_signature_image(name, size, item.get("content_type") or ""):
            continue
        return item, _read_attachment_bytes(item)
    return None, b""


def _reset_record_for_reprocess(record: dict[str, Any]) -> None:
    prior_invoice = record.get("xero_invoice_id")
    record["status"] = "pending"
    record["error"] = None
    record.pop("rejection", None)
    if prior_invoice:
        record["_update_invoice_id"] = prior_invoice
    record["xero_invoice_id"] = None
    record["xero_invoice_ids"] = []
    record.pop("xero_result", None)
    record.pop("processed_at", None)
    record.pop("extracted", None)


def process_message(message_id: str, *, force: bool = False) -> dict[str, Any]:
    with _process_lock:
        return _process_message_impl(message_id, force=force)


def _process_message_impl(message_id: str, *, force: bool = False) -> dict[str, Any]:
    record = load_queue_record(message_id)
    if force and record.get("status") in (
        "done",
        "duplicate",
        "failed",
        "rejected",
        "processing",
    ):
        _reset_record_for_reprocess(record)
        save_queue_record(record)
    elif record.get("status") == "done":
        return {"ok": True, "already_processed": True, "record": record}

    elif record.get("status") == "duplicate":
        return {"ok": False, "duplicate": True, "record": record}

    elif record.get("status") == "rejected":
        return {"ok": False, "rejected": True, "record": record}

    elif record.get("status") == "failed":
        return {"ok": False, "failed": True, "record": record}

    config = load_inbound_config()
    record["status"] = "processing"
    save_queue_record(record)

    try:
        attachments = _ordered_attachments(record.get("attachments") or [])
        primary, primary_bytes = _select_primary_attachment(attachments)

        body_text = record.get("body_text") or ""
        xero_links = record.get("xero_links") or []
        if not xero_links:
            link_objects = detect_xero_links(body_text)
            xero_links = [
                {"url": link.url, "invoice_id": link.invoice_id, "kind": link.kind}
                for link in link_objects
            ]
        link_urls = [
            link["url"] if isinstance(link, dict) else link.url for link in xero_links
        ]

        has_bill_file = primary is not None and is_bill_attachment(
            primary.get("name") or "",
            int(primary.get("size") or 0),
            primary.get("content_type") or "",
        )
        has_actionable_body = has_actionable_email_bill(
            subject=record.get("subject") or "",
            body_text=body_text,
            from_address=record.get("from") or "",
        )
        if config.require_attachment and not has_bill_file and not (
            config.allow_xero_links
            and config.allow_xero_link_without_attachment
            and link_urls
        ) and not (config.allow_email_body_without_attachment and has_actionable_body):
            raise InboundError("No attachment on queued message")

        extracted_text = (
            extract_text_from_attachment(primary_bytes, primary.get("name") or "")
            if primary_bytes and primary
            else ""
        )
        email_preview = extract_from_email(
            subject=record.get("subject") or "",
            body_text=body_text,
            from_address=record.get("from") or "",
        )
        gate_text = "\n".join(
            part for part in (extracted_text, email_preview.raw_text, body_text[:3000]) if part
        )
        gate = is_actionable_bill(
            subject=record.get("subject") or "",
            body_text=body_text,
            from_address=record.get("from") or "",
            attachment_names=[a["name"] for a in attachments],
            extracted_text=gate_text,
            classifier_mode=config.bill_classifier_mode,
            min_confidence=config.min_bill_confidence,
            blocked_domains=config.blocked_sender_domains,
            trusted_forwarders=config.allowed_from,
        )
        record["bill_gate"] = {
            "is_bill": gate.is_bill,
            "confidence": gate.confidence,
            "reason": gate.reason,
            "method": gate.method,
        }
        if config.require_bill_classification and not gate.is_bill:
            return _reject_record(record, reason=gate.reason, detail=record["bill_gate"])

        set_active_organisation(record["org_slug"])

        is_reminder = is_xero_reminder_email(
            from_address=record.get("from") or "",
            body_text=body_text,
            subject=record.get("subject") or "",
        )

        bill_files = collect_bill_attachment_files(
            record.get("attachments") or [],
            read_bytes=_read_attachment_bytes,
        )

        invoice_number_for_lookup = email_preview.invoice_number
        if not invoice_number_for_lookup and record.get("invoice_hint"):
            invoice_number_for_lookup = format_invoice_hint(str(record["invoice_hint"]))

        resolution: dict[str, Any] = {}
        pending_update_id = record.get("_update_invoice_id")
        if (
            config.allow_xero_links
            and (link_urls or invoice_number_for_lookup)
            and not pending_update_id
        ):
            link_objects = detect_xero_links(body_text)
            if record.get("split_kind") == "link" and xero_links:
                link_objects = [
                    XeroLink(
                        url=item["url"],
                        invoice_id=item.get("invoice_id"),
                        kind=item.get("kind") or "xero",
                    )
                    for item in xero_links
                    if isinstance(item, dict)
                ]
            resolution = resolve_xero_links(
                org_slug=record["org_slug"],
                links=link_objects,
                invoice_number=invoice_number_for_lookup,
            )
            record["xero_link_resolution"] = resolution
            if resolution.get("resolved"):
                resolved_org = resolution.get("org_slug")
                if resolved_org:
                    record["org_slug"] = resolved_org
                    set_active_organisation(resolved_org)
                if bill_files:
                    record["_update_invoice_id"] = resolution.get("invoice_id")
                else:
                    record["status"] = "done"
                    record["processed_at"] = time.time()
                    record["xero_invoice_id"] = resolution.get("invoice_id")
                    record["xero_result"] = resolution
                    record["error"] = None
                    save_queue_record(record)
                    audit_event(
                        "inbound_linked_existing",
                        id=message_id,
                        org_slug=resolution.get("org_slug"),
                        invoice_id=resolution.get("invoice_id"),
                    )
                    return {"ok": True, "linked_existing": True, "record": record, "xero": resolution}

        if not bill_files and resolution.get("download_pdf_link"):
            pdf_bytes = try_fetch_external_pdf(resolution["download_pdf_link"])
            if pdf_bytes:
                pdf_name = f"{email_preview.invoice_number or 'bill'}.pdf"
                bill_files = [(pdf_name, pdf_bytes)]
                record["external_pdf_fetched"] = True

        link_objects = detect_xero_links(body_text)
        if record.get("split_kind") == "link" and xero_links:
            link_objects = [
                XeroLink(
                    url=item["url"],
                    invoice_id=item.get("invoice_id"),
                    kind=item.get("kind") or "xero",
                )
                for item in xero_links
                if isinstance(item, dict)
            ]
        primary_link = primary_xero_link(link_objects) if link_objects else None

        text_sections: list[str | None] = [None]
        if (
            len(bill_files) == 1
            and primary_bytes
            and primary
            and Path(primary.get("name") or "").suffix.lower() in (".pdf", ".docx", ".doc")
        ):
            full_text = extract_text_from_attachment(
                primary_bytes,
                primary.get("name") or "",
            )
            chunks = coalesce_pdf_invoice_sections(
                full_text,
                split_extracted_text_by_invoices(full_text),
            )
            if len(chunks) > 1:
                text_sections = chunks
                record["pdf_split_sections"] = len(chunks)

        xero_results: list[dict[str, Any]] = []
        invoice_ids: list[str] = []
        last_fields = None
        split_kind = record.get("split_kind") or ""
        record_invoice_hint = record.get("invoice_hint")
        attachment_only_invoice = split_kind == "attachment" and bool(record_invoice_hint or has_bill_file)
        attachment_only_supplier = split_kind == "attachment" and has_bill_file

        merge_body_text = "" if attachment_only_supplier else body_text

        for section_index, section_text in enumerate(text_sections):
            fields = merge_extraction(
                from_address=record.get("from") or "",
                subject=record.get("subject") or "",
                body_text=merge_body_text,
                attachment_bytes=primary_bytes if has_bill_file else b"",
                attachment_name=primary.get("name") if primary else None,
                attachment_text=section_text,
                invoice_hint=record_invoice_hint,
                attachment_only_invoice=attachment_only_invoice,
                attachment_only_supplier=attachment_only_supplier,
            )
            if (
                not bill_files
                and not (fields.total and fields.total > 0)
                and not link_urls
                and not has_bill_file
            ):
                raise InboundError(
                    "No bill PDF and no amounts or Xero link in email — "
                    "re-forward with the invoice PDF attached (do not rely on subject only)"
                )

            if is_reminder and email_preview.supplier_name:
                fields.supplier_name = email_preview.supplier_name
            if is_reminder and email_preview.due_date:
                fields.due_date = email_preview.due_date
            if is_reminder and email_preview.invoice_date:
                fields.invoice_date = email_preview.invoice_date
            elif is_reminder:
                fields.invoice_date = None
            if is_reminder:
                fields.is_overdue = email_preview.is_overdue or fields.is_overdue
                fields.supplier_email = None
                fields.contact_email = None
                fields.contact_person = None
                fields.address_line1 = None
                fields.city = None

            reference = build_bill_reference(fields, xero_link=primary_link)
            line_description = build_line_description(fields)
            section_bill_files = bill_files
            if len(text_sections) > 1 and bill_files:
                name, data = bill_files[0]
                suffix = Path(name).suffix or ".pdf"
                inv = fields.invoice_number or f"section-{section_index + 1}"
                section_bill_files = [(f"{inv}{suffix}", data)]

            update_id = record.get("_update_invoice_id") if section_index == 0 else None
            if update_id:
                result = update_draft_bill(
                    invoice_id=str(update_id),
                    org_slug=record["org_slug"],
                    fields=fields,
                    account_code=record.get("default_account_code") or "400",
                    reference=reference,
                    line_description=line_description,
                    bill_attachments=section_bill_files,
                    status=config.default_status,
                    prefer_due_as_issue=is_reminder and bool(fields.due_date) and not fields.invoice_date,
                )
                record.pop("_update_invoice_id", None)
            else:
                result = create_draft_bill(
                    org_slug=record["org_slug"],
                    fields=fields,
                    account_code=record.get("default_account_code") or "400",
                    reference=reference,
                    line_description=line_description,
                    bill_attachments=section_bill_files,
                    status=config.default_status,
                    prefer_due_as_issue=is_reminder and bool(fields.due_date) and not fields.invoice_date,
                )
            if primary_link:
                result["xero_link"] = primary_link
                if resolution.get("method") == "manual_review":
                    result["manual_review"] = True
            xero_results.append(result)
            invoice_ids.append(result["invoice_id"])
            last_fields = fields

        if not has_bill_file and not bill_files and has_actionable_body and not is_reminder:
            record["attachment_warning"] = (
                "Bill created from email body only — no pdf/docx/doc/xlsx reached tower "
                "(forward may have dropped attachments; re-send with file attached)"
            )
        elif is_reminder and not bill_files:
            record["attachment_warning"] = (
                "Xero reminder email — no PDF attached. "
                "Open the supplier link in Reference to view/import the bill."
            )
        if len(text_sections) > 1:
            record["attachment_warning"] = (
                (record.get("attachment_warning") or "")
                + " Single PDF split into multiple draft bills by invoice headers (best effort)."
            ).strip()

        record["status"] = "done"
        record["processed_at"] = time.time()
        record["xero_invoice_id"] = invoice_ids[0] if invoice_ids else None
        record["xero_invoice_ids"] = invoice_ids
        record["extracted"] = extraction_summary(last_fields) if last_fields else {}
        record["xero_result"] = xero_results[0] if len(xero_results) == 1 else {"bills": xero_results}
        record["error"] = None
        save_queue_record(record)
        audit_event(
            "inbound_processed",
            id=message_id,
            org_slug=record["org_slug"],
            invoice_id=record["xero_invoice_id"],
            invoice_count=len(invoice_ids),
        )
        return {
            "ok": True,
            "record": record,
            "xero": record["xero_result"],
            "invoice_ids": invoice_ids,
        }
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)
        record["processed_at"] = time.time()
        save_queue_record(record)
        audit_event("inbound_failed", id=message_id, error=str(exc))
        return {"ok": False, "error": str(exc), "record": record}


def process_pending(limit: int = 10) -> list[dict[str, Any]]:
    pending = list_queue_records(status="pending", limit=limit)
    return process_queued_records(pending)


def retry_failed(message_id: str) -> dict[str, Any]:
    record = load_queue_record(message_id)
    if record.get("status") not in ("failed", "rejected"):
        raise InboundError(
            f"Message {message_id} is not failed/rejected (status={record.get('status')})"
        )
    record["status"] = "pending"
    record["error"] = None
    record.pop("rejection", None)
    save_queue_record(record)
    return process_message(message_id)


def queue_summary(limit: int = 20) -> dict[str, Any]:
    records = list_queue_records(limit=limit)
    config = load_inbound_config()
    return {
        "routing_mode": config.routing_mode,
        "intake_addresses": list(config.intake_addresses),
        "routes": [
            {"address": r.address, "org_slug": r.org_slug, "label": r.label}
            for r in config.routes
        ],
        "bill_classification": {
            "require_bill_classification": config.require_bill_classification,
            "min_bill_confidence": config.min_bill_confidence,
            "bill_classifier_mode": config.bill_classifier_mode,
            "allow_xero_links": config.allow_xero_links,
            "allow_email_body_without_attachment": config.allow_email_body_without_attachment,
        },
        "messages": records,
        "counts": {
            status: len(list_queue_records(status=status, limit=1000))
            for status in ("pending", "processing", "done", "failed", "duplicate", "rejected")
        },
    }

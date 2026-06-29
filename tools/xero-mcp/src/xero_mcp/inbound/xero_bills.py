from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from xero_mcp.auth import ensure_access_token
from xero_mcp.inbound.config import InboundError
from xero_mcp.inbound.extract import ExtractedFields, LineItem
from xero_mcp.inbound.xero_contacts import ensure_contact
from xero_mcp.inbound.xero_http import xero_request
from xero_mcp.tenants import list_organisations

XERO_API = "https://api.xero.com/api.xro/2.0"

_GST_ALIASES = frozenset({"gst", "15%", "15.00%", "nz gst", "input", "input2"})


def _tenant_id_for_slug(org_slug: str) -> str:
    for org in list_organisations():
        if org.slug == org_slug:
            return org.tenant_id
    raise InboundError(f"Unknown org slug: {org_slug}")


@lru_cache(maxsize=8)
def _fetch_tax_rates(org_slug: str) -> list[dict[str, Any]]:
    access_token = ensure_access_token()
    tenant_id = _tenant_id_for_slug(org_slug)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = xero_request(client, "GET", f"{XERO_API}/TaxRates", headers=headers)
        if resp.status_code >= 400:
            raise InboundError(f"Xero tax rates failed ({resp.status_code}): {resp.text}")
        return list(resp.json().get("TaxRates") or [])


def map_tax_type(org_slug: str, label: str | None) -> str | None:
    if not label:
        return None
    try:
        rates = _fetch_tax_rates(org_slug)
    except InboundError as exc:
        if "429" not in str(exc):
            raise
        rates = []
    needle = label.lower().strip()
    for rate in rates:
        name = str(rate.get("Name") or "").lower()
        tax_type = rate.get("TaxType")
        if not tax_type:
            continue
        if needle in name or name in needle:
            return str(tax_type)
    if needle in _GST_ALIASES or "gst" in needle:
        for rate in rates:
            name = str(rate.get("Name") or "").lower()
            tax_type = rate.get("TaxType")
            if tax_type and ("gst" in name or "15" in name):
                return str(tax_type)
        for rate in rates:
            tax_type = rate.get("TaxType")
            if tax_type and str(tax_type).upper().startswith("INPUT"):
                return str(tax_type)
        if not rates:
            return "INPUT2"
    return None


def _line_items_payload(
    *,
    fields: ExtractedFields,
    account_code: str,
    description: str,
    org_slug: str,
) -> tuple[list[dict[str, Any]], str]:
    line_amount_types = fields.line_amount_types or "Exclusive"
    if line_amount_types == "NoTax":
        default_tax = None
    elif fields.tax_rate_label:
        default_tax = map_tax_type(org_slug, fields.tax_rate_label)
    elif fields.tax_amount:
        default_tax = map_tax_type(org_slug, "GST")
    else:
        default_tax = None

    if fields.line_items:
        payload: list[dict[str, Any]] = []
        for item in fields.line_items:
            line: dict[str, Any] = {
                "Description": item.description[:4000],
                "Quantity": item.quantity,
                "AccountCode": item.account_code or account_code,
            }
            if (
                item.line_amount is not None
                and item.line_amount > 0
                and item.unit_amount <= 0
                and item.quantity > 0
            ):
                # Qty-only PDF rows: UnitAmount + Quantity (Xero rejects LineAmount + Quantity drift).
                line["UnitAmount"] = round(item.line_amount / item.quantity, 2)
            elif item.line_amount is not None and item.line_amount > 0:
                line["LineAmount"] = item.line_amount
            elif item.unit_amount > 0:
                line["UnitAmount"] = item.unit_amount
            else:
                line["UnitAmount"] = 0
            tax_type = item.tax_type or default_tax
            if tax_type:
                line["TaxType"] = tax_type
            payload.append(line)
        return payload, line_amount_types

    if fields.subtotal and fields.subtotal > 0 and fields.tax_amount:
        line_amount = fields.subtotal
    else:
        line_amount = fields.total if fields.total and fields.total > 0 else 0.0
    line_description = description or "Imported bill — review amounts"
    if fields.total == 0.0:
        line_description += " (total not detected — set line amount in Xero)"
    line: dict[str, Any] = {
        "Description": line_description[:4000],
        "Quantity": 1,
        "UnitAmount": line_amount,
        "AccountCode": account_code,
    }
    if default_tax:
        line["TaxType"] = default_tax
    return [line], line_amount_types


def _build_bill_payload(
    *,
    org_slug: str,
    fields: ExtractedFields,
    account_code: str,
    reference: str,
    line_description: str | None,
    status: str,
    prefer_due_as_issue: bool,
    invoice_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    contact_ref: dict[str, str] | None
    if invoice_id:
        # Updating an existing draft: keep its contact — no Contacts API lookup.
        contact_result = {
            "contact_id": None,
            "name": fields.supplier_name,
            "created": False,
            "match": "existing_invoice",
        }
        contact_ref = None
    else:
        contact_result = ensure_contact(org_slug=org_slug, fields=fields)
        contact_ref = {"ContactID": str(contact_result["contact_id"])}
    line_items, line_amount_types = _line_items_payload(
        fields=fields,
        account_code=account_code,
        description=line_description or reference,
        org_slug=org_slug,
    )

    invoice_date = fields.invoice_date
    if not invoice_date and fields.due_date and prefer_due_as_issue:
        invoice_date = fields.due_date
    if not invoice_date:
        invoice_date = date.today().isoformat()

    payload: dict[str, Any] = {
        "Type": "ACCPAY",
        "Status": status,
        "Date": invoice_date,
        "InvoiceNumber": (fields.invoice_number or reference or "")[:255] or None,
        "Reference": reference[:255] if reference else None,
        "LineAmountTypes": line_amount_types,
        "LineItems": line_items,
    }
    if contact_ref:
        payload["Contact"] = contact_ref
    if invoice_id:
        payload["InvoiceID"] = invoice_id
    if fields.due_date:
        payload["DueDate"] = fields.due_date
    payload = {k: v for k, v in payload.items() if v is not None}
    return payload, line_items, contact_result


def _attach_files_to_invoice(
    *,
    client: httpx.Client,
    access_token: str,
    tenant_id: str,
    invoice_id: str,
    files: list[tuple[str, bytes]],
) -> list[str]:
    attached_names: list[str] = []
    for name, data in files:
        safe_name = Path(name).name
        attach_headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Content-Type": _content_type_for_name(safe_name),
            "Accept": "application/json",
        }
        attach_resp = xero_request(
            client,
            "PUT",
            f"{XERO_API}/Invoices/{invoice_id}/Attachments/{safe_name}",
            headers=attach_headers,
            content=data,
        )
        if attach_resp.status_code >= 400:
            raise InboundError(
                f"Bill attachment {safe_name} failed ({attach_resp.status_code}): {attach_resp.text}"
            )
        attached_names.append(safe_name)
    return attached_names


def create_draft_bill(
    *,
    org_slug: str,
    fields: ExtractedFields,
    account_code: str,
    reference: str,
    line_description: str | None = None,
    bill_attachments: list[tuple[str, bytes]] | None = None,
    attachment_name: str | None = None,
    attachment_bytes: bytes | None = None,
    status: str = "DRAFT",
    xero_link: str | None = None,
    prefer_due_as_issue: bool = False,
) -> dict[str, Any]:
    access_token = ensure_access_token()
    tenant_id = _tenant_id_for_slug(org_slug)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "xero-tenant-id": tenant_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    contact_name = fields.supplier_name or "Imported Supplier"
    payload, line_items, contact_result = _build_bill_payload(
        org_slug=org_slug,
        fields=fields,
        account_code=account_code,
        reference=reference,
        line_description=line_description,
        status=status,
        prefer_due_as_issue=prefer_due_as_issue,
    )

    files: list[tuple[str, bytes]] = list(bill_attachments or [])
    if attachment_name and attachment_bytes and not files:
        files = [(attachment_name, attachment_bytes)]

    with httpx.Client(timeout=60.0) as client:
        resp = xero_request(
            client, "POST", f"{XERO_API}/Invoices", headers=headers, json={"Invoices": [payload]}
        )
        if resp.status_code >= 400:
            raise InboundError(f"Xero create bill failed ({resp.status_code}): {resp.text}")
        body = resp.json()
        invoice = (body.get("Invoices") or [{}])[0]
        invoice_id = invoice.get("InvoiceID")
        if not invoice_id:
            raise InboundError(f"Xero did not return InvoiceID: {body}")

        attached_names = _attach_files_to_invoice(
            client=client,
            access_token=access_token,
            tenant_id=tenant_id,
            invoice_id=str(invoice_id),
            files=files,
        )

    return {
        "invoice_id": invoice_id,
        "invoice_number": invoice.get("InvoiceNumber"),
        "contact": contact_result.get("name") or contact_name,
        "contact_id": contact_result.get("contact_id"),
        "contact_created": contact_result.get("created"),
        "contact_match": contact_result.get("match"),
        "total": invoice.get("Total"),
        "status": invoice.get("Status"),
        "org_slug": org_slug,
        "tenant_id": tenant_id,
        "line_items": len(line_items),
        "attachment_count": len(attached_names),
        "attachments": attached_names,
        "updated": False,
    }


def update_draft_bill(
    *,
    invoice_id: str,
    org_slug: str,
    fields: ExtractedFields,
    account_code: str,
    reference: str,
    line_description: str | None = None,
    bill_attachments: list[tuple[str, bytes]] | None = None,
    status: str = "DRAFT",
    prefer_due_as_issue: bool = False,
) -> dict[str, Any]:
    """Update an existing draft ACCPAY (force reprocess) instead of creating a duplicate."""
    access_token = ensure_access_token()
    tenant_id = _tenant_id_for_slug(org_slug)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "xero-tenant-id": tenant_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    contact_name = fields.supplier_name or "Imported Supplier"
    payload, line_items, contact_result = _build_bill_payload(
        org_slug=org_slug,
        fields=fields,
        account_code=account_code,
        reference=reference,
        line_description=line_description,
        status=status,
        prefer_due_as_issue=prefer_due_as_issue,
        invoice_id=invoice_id,
    )

    files: list[tuple[str, bytes]] = list(bill_attachments or [])

    with httpx.Client(timeout=60.0) as client:
        resp = xero_request(
            client, "POST", f"{XERO_API}/Invoices", headers=headers, json={"Invoices": [payload]}
        )
        if resp.status_code >= 400:
            raise InboundError(f"Xero update bill failed ({resp.status_code}): {resp.text}")
        body = resp.json()
        invoice = (body.get("Invoices") or [{}])[0]
        updated_id = invoice.get("InvoiceID") or invoice_id

        attached_names = _attach_files_to_invoice(
            client=client,
            access_token=access_token,
            tenant_id=tenant_id,
            invoice_id=str(updated_id),
            files=files,
        )

    return {
        "invoice_id": updated_id,
        "invoice_number": invoice.get("InvoiceNumber"),
        "contact": contact_result.get("name") or contact_name,
        "contact_id": contact_result.get("contact_id"),
        "contact_created": contact_result.get("created"),
        "contact_match": contact_result.get("match"),
        "total": invoice.get("Total"),
        "status": invoice.get("Status"),
        "org_slug": org_slug,
        "tenant_id": tenant_id,
        "line_items": len(line_items),
        "attachment_count": len(attached_names),
        "attachments": attached_names,
        "updated": True,
    }


def _content_type_for_name(name: str) -> str:
    lower = name.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".doc"):
        return "application/msword"
    if lower.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower.endswith(".xls"):
        return "application/vnd.ms-excel"
    return "application/pdf"


def attach_files_to_bill(
    *,
    org_slug: str,
    invoice_id: str,
    files: list[tuple[str, bytes]],
) -> list[dict[str, Any]]:
    if not files:
        return []
    access_token = ensure_access_token()
    tenant_id = _tenant_id_for_slug(org_slug)
    attached: list[dict[str, Any]] = []
    with httpx.Client(timeout=120.0) as client:
        for name, data in files:
            safe_name = Path(name).name
            headers = {
                "Authorization": f"Bearer {access_token}",
                "xero-tenant-id": tenant_id,
                "Content-Type": _content_type_for_name(safe_name),
                "Accept": "application/json",
            }
            resp = xero_request(
                client,
                "PUT",
                f"{XERO_API}/Invoices/{invoice_id}/Attachments/{safe_name}",
                headers=headers,
                content=data,
            )
            if resp.status_code >= 400:
                raise InboundError(
                    f"Attachment {safe_name} failed ({resp.status_code}): {resp.text}"
                )
            attached.append({"name": safe_name, "bytes": len(data)})
    return attached

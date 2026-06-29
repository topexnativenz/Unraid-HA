from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from xero_mcp.auth import ensure_access_token
from xero_mcp.inbound.config import InboundError
from xero_mcp.inbound.xero_http import xero_request
from xero_mcp.tenants import list_organisations

XERO_API = "https://api.xero.com/api.xro/2.0"

_XERO_URL = re.compile(
    r"https?://(?:[\w.-]+\.)?xero\.com[^\s\"'<>]*",
    re.IGNORECASE,
)

_INVOICE_ID_PARAM = re.compile(
    r"(?:InvoiceID|invoiceId|invoice_id)=([0-9a-f-]{36})",
    re.IGNORECASE,
)

_INVOICE_UUID = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.IGNORECASE,
)

_DOWNLOAD_PDF_PATH = re.compile(
    r"/Invoice/DownloadPdf/([0-9a-f-]{36})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class XeroLink:
    url: str
    invoice_id: str | None
    kind: str


def _link_kind(url: str) -> str:
    lower = url.lower()
    if "in.xero.com" in lower:
        return "in_xero"
    if "accountspayable" in lower or "/bills/" in lower or "payable" in lower:
        return "bill"
    if "accountsreceivable" in lower or "/invoices/" in lower:
        return "invoice"
    if "invoicelink" in lower or "pay.xero" in lower:
        return "pay_link"
    if "go.xero.com" in lower:
        return "go"
    return "xero"


def detect_xero_links(text: str) -> list[XeroLink]:
    links: list[XeroLink] = []
    seen: set[str] = set()
    for match in _XERO_URL.finditer(text or ""):
        url = match.group(0).rstrip(".,;)\"'")
        if url in seen:
            continue
        seen.add(url)
        invoice_id = _extract_invoice_id(url)
        links.append(XeroLink(url=url, invoice_id=invoice_id, kind=_link_kind(url)))
    return links


def _extract_invoice_id(url: str) -> str | None:
    pdf_match = _DOWNLOAD_PDF_PATH.search(url)
    if pdf_match:
        return pdf_match.group(1).lower()
    param_match = _INVOICE_ID_PARAM.search(url)
    if param_match:
        return param_match.group(1).lower()
    parsed = urlparse(url)
    for key in ("InvoiceID", "invoiceId", "invoice_id", "id"):
        values = parse_qs(parsed.query).get(key)
        if values and _INVOICE_UUID.fullmatch(values[0]):
            return values[0].lower()
    path_uuid = _INVOICE_UUID.search(parsed.path)
    if path_uuid:
        return path_uuid.group(1).lower()
    return None


def group_xero_links_for_bills(links: list[XeroLink]) -> list[list[XeroLink]]:
    """Group URLs that refer to the same bill (UUID or same in.xero.com path)."""
    if not links:
        return []
    groups: dict[str, list[XeroLink]] = {}
    order: list[str] = []
    for link in links:
        if link.invoice_id:
            key = f"uuid:{link.invoice_id.lower()}"
        else:
            parsed = urlparse(link.url)
            path = parsed.path.rstrip("/")
            if "in.xero.com" in link.url.lower() and path:
                key = f"in:{path}"
            else:
                key = f"url:{link.url.split('?')[0].rstrip('/')}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(link)
    return [groups[key] for key in order]


def primary_xero_link(links: list[XeroLink]) -> str | None:
    if not links:
        return None
    for preferred in ("in_xero", "go", "bill", "invoice", "pay_link", "xero"):
        for link in links:
            if link.kind == preferred and "downloadpdf" not in link.url.lower():
                return link.url
    return links[0].url


def download_pdf_link(links: list[XeroLink]) -> str | None:
    for link in links:
        if "downloadpdf" in link.url.lower():
            return link.url
    return None


def _tenant_id_for_slug(org_slug: str) -> str:
    for org in list_organisations():
        if org.slug == org_slug:
            return org.tenant_id
    raise InboundError(f"Unknown org slug: {org_slug}")


def _api_headers(org_slug: str) -> tuple[str, dict[str, str]]:
    access_token = ensure_access_token()
    tenant_id = _tenant_id_for_slug(org_slug)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }
    return tenant_id, headers


def _escape_odata(value: str) -> str:
    return value.replace("'", "''")


def fetch_invoice_in_org(*, org_slug: str, invoice_id: str) -> dict[str, Any] | None:
    _, headers = _api_headers(org_slug)
    with httpx.Client(timeout=30.0) as client:
        resp = xero_request(client, "GET", f"{XERO_API}/Invoices/{invoice_id}", headers=headers)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise InboundError(f"Xero invoice lookup failed ({resp.status_code}): {resp.text}")
        invoice = (resp.json().get("Invoices") or [{}])[0]
        if not invoice.get("InvoiceID"):
            return None
        return invoice


def search_invoice_by_number(
    *,
    org_slug: str,
    invoice_number: str,
    invoice_type: str = "ACCPAY",
) -> dict[str, Any] | None:
    safe_number = _escape_odata(invoice_number.strip())
    where = f'Type=="{invoice_type}"&&InvoiceNumber=="{safe_number}"'
    _, headers = _api_headers(org_slug)
    with httpx.Client(timeout=30.0) as client:
        resp = xero_request(
            client,
            "GET",
            f"{XERO_API}/Invoices",
            headers=headers,
            params={"where": where},
        )
        if resp.status_code >= 400:
            raise InboundError(f"Xero invoice search failed ({resp.status_code}): {resp.text}")
        invoices = resp.json().get("Invoices") or []
        return invoices[0] if invoices else None


def fetch_invoice_attachment_files(
    *,
    org_slug: str,
    invoice_id: str,
) -> list[tuple[str, bytes]]:
    _, headers = _api_headers(org_slug)
    files: list[tuple[str, bytes]] = []
    with httpx.Client(timeout=60.0) as client:
        resp = xero_request(
            client,
            "GET",
            f"{XERO_API}/Invoices/{invoice_id}/Attachments",
            headers=headers,
        )
        if resp.status_code == 404:
            return []
        if resp.status_code >= 400:
            raise InboundError(
                f"Xero list attachments failed ({resp.status_code}): {resp.text}"
            )
        attachments = resp.json().get("Attachments") or []
        for item in attachments:
            name = str(item.get("FileName") or "attachment.pdf")
            attach_resp = xero_request(
                client,
                "GET",
                f"{XERO_API}/Invoices/{invoice_id}/Attachments/{name}",
                headers=headers,
            )
            if attach_resp.status_code >= 400:
                continue
            if attach_resp.content:
                files.append((name, attach_resp.content))
    return files


def try_fetch_external_pdf(url: str) -> bytes | None:
    """Best-effort PDF from supplier in.xero.com link (usually auth-walled)."""
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code >= 400:
                return None
            content = resp.content
            if content[:4] == b"%PDF":
                return content
    except Exception:
        return None
    return None


def _invoice_resolution(invoice: dict[str, Any], *, org_slug: str, link: str | None, method: str) -> dict[str, Any]:
    contact = invoice.get("Contact") or {}
    return {
        "resolved": True,
        "method": method,
        "org_slug": org_slug,
        "invoice_id": invoice.get("InvoiceID"),
        "invoice_number": invoice.get("InvoiceNumber"),
        "status": invoice.get("Status"),
        "type": invoice.get("Type"),
        "total": invoice.get("Total"),
        "date": invoice.get("Date"),
        "due_date": invoice.get("DueDate"),
        "contact_id": contact.get("ContactID"),
        "contact_name": contact.get("Name"),
        "link": link,
    }


def resolve_xero_links(
    *,
    org_slug: str,
    links: list[XeroLink],
    invoice_number: str | None = None,
    try_all_orgs: bool = True,
) -> dict[str, Any]:
    """Best-effort resolution for Xero URLs in email.

    1. UUID from go.xero.com / DownloadPdf path — lookup in connected orgs
    2. InvoiceNumber search (ACCPAY) across connected orgs
    3. Otherwise manual_review with primary link stored for reference field
    """
    if not links and not invoice_number:
        return {"resolved": False, "reason": "no_links"}

    org_slugs = [org_slug]
    if try_all_orgs:
        org_slugs = list(dict.fromkeys([org_slug] + [o.slug for o in list_organisations()]))

    invoice_ids: list[str] = []
    seen_ids: set[str] = set()
    for link in links:
        if link.invoice_id and link.invoice_id not in seen_ids:
            seen_ids.add(link.invoice_id)
            invoice_ids.append(link.invoice_id)

    primary = primary_xero_link(links) if links else None

    for invoice_id in invoice_ids:
        for slug in org_slugs:
            invoice = fetch_invoice_in_org(org_slug=slug, invoice_id=invoice_id)
            if not invoice:
                continue
            result = _invoice_resolution(invoice, org_slug=slug, link=primary, method="existing_invoice_uuid")
            attachments = fetch_invoice_attachment_files(org_slug=slug, invoice_id=invoice_id)
            if attachments:
                result["attachments"] = [{"name": n, "bytes": len(b)} for n, b in attachments]
            return result

    if invoice_number:
        for slug in org_slugs:
            invoice = search_invoice_by_number(org_slug=slug, invoice_number=invoice_number)
            if not invoice:
                continue
            invoice_id = str(invoice.get("InvoiceID") or "")
            result = _invoice_resolution(
                invoice,
                org_slug=slug,
                link=primary,
                method="existing_invoice_number",
            )
            if invoice_id:
                attachments = fetch_invoice_attachment_files(org_slug=slug, invoice_id=invoice_id)
                if attachments:
                    result["attachments"] = [{"name": n, "bytes": len(b)} for n, b in attachments]
            return result

    return {
        "resolved": False,
        "method": "manual_review",
        "reason": (
            "Xero link found but bill is not in a connected org — "
            "open the link in Xero to accept/import manually"
        ),
        "links": [{"url": link.url, "invoice_id": link.invoice_id, "kind": link.kind} for link in links],
        "primary_link": primary,
        "download_pdf_link": download_pdf_link(links),
    }

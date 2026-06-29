from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class LineItem:
    description: str
    quantity: float = 1.0
    unit_amount: float = 0.0
    line_amount: float | None = None
    account_code: str | None = None
    tax_type: str | None = None


@dataclass
class ExtractedFields:
    supplier_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    total: float | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    tax_rate_label: str | None = None
    currency: str | None = None
    is_overdue: bool = False
    line_items: list[LineItem] = field(default_factory=list)
    sender_email: str | None = None
    supplier_email: str | None = None
    contact_email: str | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    postal_code: str | None = None
    region: str | None = None
    contact_person: str | None = None
    raw_text: str = ""
    line_amount_types: str | None = None  # Xero: Exclusive, Inclusive, NoTax


_AMOUNT_RE = re.compile(
    r"(?P<label>(?:grand\s+total|total\s+due|invoice\s+total|amount\s+due|balance\s+due))"
    r"[:\s]*\$?\s*(?P<amount>[\d, ]+\.\d{2})",
    re.IGNORECASE,
)
_TOTAL_NZD_RE = re.compile(r"\bTOTAL\s+NZD\s+([\d, ]+\.\d{2})\b", re.IGNORECASE)
_TABLE_HEADER_RE = re.compile(
    r"Description\s+Quantity\s+Unit\s+Price",
    re.IGNORECASE,
)
_TO_SUPPLIER_RE = re.compile(r"^To:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_SUPPLIER_AFTER_REFERENCE_RE = re.compile(
    r"Reference\s*\n[^\n]+\n(.*?)(?:\n(?:PO Box|Description\s+Quantity|Bank Account|Email:|\Z))",
    re.IGNORECASE | re.DOTALL,
)
_SUPPLIER_AFTER_GST_NUMBER_RE = re.compile(
    r"GST\s*Number\s*\n[\d-]+\s*\n(.*?)(?:\n(?:PO Box|Description\s+Quantity|Bank Account|Ph:|Email:|\Z))",
    re.IGNORECASE | re.DOTALL,
)
_SUBTOTAL_RE = re.compile(
    r"(?:sub\s*total|subtotal)[:\s]*\$?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
_GST_RE = re.compile(
    r"(?:gst|vat|tax)(?:\s*\(?\s*15\s*%?\s*\)?)?[:\s]*\$?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
_INVOICE_NO_RE = re.compile(
    r"(?:invoice\s*number|invoice\s*(?:no|#)|inv\s*#|tax\s*invoice\s*(?:no|#))"
    r"[:\s#-]+([A-Z0-9][A-Z0-9-/]{2,})",
    re.IGNORECASE,
)
_TAX_INVOICE_NUM_RE = re.compile(
    r"Tax\s+Invoice\s*#?\s*(\d{3,8})\b",
    re.IGNORECASE,
)
_DATE_VALUE = (
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"(?:\w+day,\s*)?\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
    r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{4}(?:\s+at\s+\d{1,2}:\d{2})?|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})"
)
_DATE_LABEL_RE = re.compile(
    rf"(invoice\s*date|issue\s*date|date\s*of\s*issue|bill\s*date|tax\s*date)[:\s]*{_DATE_VALUE}",
    re.IGNORECASE,
)
_DUE_LABEL_RE = re.compile(
    rf"(due\s*date|payment\s*due|pay\s*by|payable\s*by)[:\s]*{_DATE_VALUE}",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"(?:\w+day,\s*)?\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
    r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{4})\b",
    re.IGNORECASE,
)
_FORWARD_DATE_RE = re.compile(
    r"^Date:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_XERO_REMINDER_DOMAINS = frozenset({"post.xero.com", "mail.xero.com", "notify.mail.xero.com"})
_XERO_BILL_SUBJECT_RE = re.compile(
    r"Bill\s+([A-Z0-9][\w-]+)\s+from\s+(.+?)\s+is\s+due",
    re.IGNORECASE,
)
_XERO_INVOICE_SUBJECT_RE = re.compile(
    r"(?:Fwd:\s*)?(?:Invoice|Bill)\s+([A-Z0-9][\w-]+)\s+from\s+(.+?)\s+(?:for|to)\s+",
    re.IGNORECASE,
)
_XERO_OVERDUE_LINE_RE = re.compile(r"Overdue\s*-\s*(.+)", re.IGNORECASE)
_XERO_WAS_DUE_RE = re.compile(r"was due on\s+(.+?)(?:\.|\s|$)", re.IGNORECASE)
_NZD_AMOUNT_RE = re.compile(r"\$([\d, ]+\.\d{2})\s*NZD", re.IGNORECASE)
_LINE_ITEM_RE = re.compile(
    r"^(.{3,80}?)\s+(?:\d+\s+x\s+)?\$?\s*([\d,]+\.\d{2})\s*$",
)
_QTY_LINE_RE = re.compile(
    r"^(.{3,60}?)\s+(\d+(?:\.\d+)?)\s+\$?\s*([\d,]+\.\d{2})\s+\$?\s*([\d,]+\.\d{2})\s*$",
)
_QTY_MULTI_AMOUNT_RE = re.compile(
    r"^(.{3,120}?)\s+(\d+(?:\.\d+)?)((?:\s+\$?\s*[\d,]+\.\d{2})+)\s*$",
)
_TRAILING_AMOUNTS_RE = re.compile(r"[\d,]+\.\d{2}")
_QTY_ONLY_LINE_RE = re.compile(
    r"^(?=.*[A-Za-z])(.{3,80}?)\s+(?:Qty\.?\s+)?(\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
_ORPHAN_VALUES_LINE_RE = re.compile(
    r"^(\d+(?:\.\d+)?)((?:\s+[\d,]+\.\d{2})+)\s*$",
)
_NZ_GST_FACTOR = 1.15
_LINE_PRICE_RE = re.compile(
    r"^(.{3,80}?)\s+(?:\d+\s+x\s+)?\$([\d, ]+\.\d{2})\s*$",
)
_FOOTER_SUMMARY_LINE_RE = re.compile(
    r"^(?:Amount(?:\s+including\s+GST)?|Subtotal|Total(?:\s+NZD)?|GST(?:\s+\d+\s*%)?)\b",
    re.IGNORECASE,
)
_OVERDUE_RE = re.compile(r"\b(overdue|past due|payment overdue)\b", re.IGNORECASE)
_SUPPLIER_SKIP = frozenset({
    "tax invoice", "invoice", "bill to", "ship to", "statement", "remittance advice",
    "page", "abn", "gst number", "nzbn", "phone", "email", "tel", "mobile",
})
_SUPPLIER_BLOCKLIST = frozenset({
    "payment advice", "amount enclosed", "amount due", "enter the amount",
    "customer", "invoice date", "invoice number", "reference", "due date",
    "description", "quantity", "unit price", "amount nzd", "subtotal", "total nzd",
    "bank account", "tax invoice", "new zealand", "nzd", "total", "gst", "tax",
    "amount", "page", "remittance advice",
})
_LINE_LABEL_SKIP = frozenset({
    "subtotal", "total", "total nzd", "gst", "tax", "amount due", "amount enclosed",
    "description", "quantity", "unit price", "amount nzd", "payment advice",
    "amount", "amount including gst",
})
_INVOICE_METADATA_LINE_RE = re.compile(
    r"^(?:invoice\s*(?:no|number|#)|invoice\s+date|payment\s+due|customer\s+order|"
    r"job\s+(?:site|description)|gst\s*(?:no|number)|attention|to:|bank\s+account)\b",
    re.IGNORECASE,
)
_INVOICE_FIELD_VALUE_LINE_RE = re.compile(
    r"^.{3,120}:\s*\S",
    re.IGNORECASE,
)
_EMAIL_LABEL_RE = re.compile(
    r"(?:email|e-mail)[:\s]*([\w.+-]+@[\w.-]+\.\w+)",
    re.IGNORECASE,
)
_EMAIL_ANY_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_PHONE_LABEL_RE = re.compile(
    r"(?:phone|tel|telephone|mobile|ph|mob)[:\s]*([+\d][\d\s\-().]{7,})",
    re.IGNORECASE,
)
_STREET_HINT_RE = re.compile(
    r"\b(?:street|st|road|rd|drive|dr|avenue|ave|lane|ln|place|pl|way|parade|pde|crescent|cres)\b",
    re.IGNORECASE,
)
_CITY_POSTAL_RE = re.compile(
    r"^(.+?)\s+(\d{4})$",
)

_INTERNAL_EMAIL_DOMAINS = frozenset({
    "matarikigroup.co.nz",
    "gillespie.kiwi",
})

_BILL_DOC_EXTENSIONS = frozenset({".pdf", ".doc", ".docx", ".xls", ".xlsx"})

_BLOCKED_CONTACT_NAMES = frozenset({
    "matarikigroup",
    "matariki group",
    "matariki property group",
    "matariki traders",
    "matariki morningside",
    "matariki morningside development",
    "gillespie",
    "design nz",
    "design nz limited",
})

_COLLECTION_AGENT_MARKERS = (
    "design nz",
    "debt collection",
    "credit control",
    "collection agency",
    "accounts receivable",
    "invoice management",
    "payment reminder",
    "overdue account",
)

_SUBJECT_PREFIX_RE = re.compile(r"^(?:(?:fw|fwd|re):\s*)+", re.IGNORECASE)
_REFERENCE_LABEL_RE = re.compile(
    r"\b(?:reference|ref(?:erence)?|invoice(?:\s*(?:no|#|number))?|"
    r"account(?:\s*(?:no|#|number))?|contribution(?:\s*(?:no|#|number))?)"
    r"[:\s#]+([A-Z0-9][A-Z0-9-]{3,})\b",
    re.IGNORECASE,
)
_REF_TOKEN_RE = re.compile(r"\b([A-Z]{2,6}\d{5,})\b")
_COUNCIL_LINE_RE = re.compile(
    r"^([A-Z][A-Za-z'’-]*(?:\s+[A-Z][A-Za-z'’-]*)*\s+(?:District\s+)?Council)"
    r"(?:\s*[|].*)?\s*$",
)
_ORG_NAME_RE = re.compile(
    r"\b([A-Z][A-Za-z'’-]*(?:\s+[A-Z][A-Za-z'’-]*)+\s+"
    r"(?:Ltd|Limited|Inc|Trust|Holdings|Group|Services|Authority|Corporation))\b",
)
_FORWARD_FROM_RE = re.compile(
    r"^From:\s*(?:\"([^\"\n]+)\"|'([^'\n]+)'|([^<\n]+?))?\s*(?:<([^>\n]+)>)?",
    re.IGNORECASE | re.MULTILINE,
)
_DOLLAR_AMOUNT_RE = re.compile(
    r"(?:NZD|\$\s*|total(?:\s+(?:amount|due))?[:\s]*\$?\s*|amount due[:\s]*\$?\s*)"
    r"([\d, ]+\.\d{2})",
    re.IGNORECASE,
)
_NZD_TRAILING_RE = re.compile(r"([\d, ]+\.\d{2})\s*(?:NZD|inc\.?\s*GST)", re.IGNORECASE)
_CONFIRM_AMOUNT_RE = re.compile(
    r"\b(?:for|confirm(?:\s+it\s+is\s+for)?)\s+\$?\s*([\d, ]+\.\d{2})\b",
    re.IGNORECASE,
)


def _parse_date(value: str) -> str | None:
    value = re.sub(r"\s+at\s+\d{1,2}:\d{2}(?:\s*[AP]M)?", "", value.strip(), flags=re.IGNORECASE)
    value = re.sub(r"^\w+day,\s*", "", value, flags=re.IGNORECASE).strip()
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%m/%d/%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%B %d %Y",
        "%b %d, %Y",
        "%b %d %Y",
    ):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _extract_forward_issue_date(body_text: str) -> str | None:
    """Issue-date proxy from Outlook/Gmail forward headers (supplier's sent date)."""
    for match in _FORWARD_DATE_RE.finditer(body_text[:4000]):
        parsed = _parse_date(match.group(1).strip())
        if parsed:
            return parsed
    return None


def _parse_xero_invoice_subject(subject: str) -> tuple[str, str] | None:
    cleaned = _clean_subject(subject)
    for pattern in (_XERO_BILL_SUBJECT_RE, _XERO_INVOICE_SUBJECT_RE):
        match = pattern.search(cleaned)
        if match:
            inv = match.group(1).strip()
            supplier = match.group(2).strip().rstrip(".")
            if inv and supplier and not _is_blocked_contact_name(supplier):
                return inv, supplier
    return None


def is_xero_reminder_email(*, from_address: str = "", body_text: str = "", subject: str = "") -> bool:
    sender = email_from_header(from_address or "")
    if sender and any(sender.endswith(domain) for domain in _XERO_REMINDER_DOMAINS):
        return True
    hay = f"{body_text or ''}\n{subject or ''}"
    if "Payment Reminder" in hay and "in.xero.com" in hay:
        return True
    if "post.xero.com" in hay.lower() and (
        "payment reminder" in hay.lower() or _XERO_BILL_SUBJECT_RE.search(hay)
    ):
        return True
    # Do not treat supplier invoice forwards ("Fwd: Invoice INV-… from … for Matariki")
    # as Xero reminders — those need a PDF or reminder body with amounts/links.
    if _XERO_BILL_SUBJECT_RE.search(body_text or ""):
        return True
    return False


def extract_xero_reminder_fields(*, subject: str, body_text: str) -> ExtractedFields:
    """Parse Xero payment reminder emails (in.xero.com links, no PDF attachment)."""
    fields = ExtractedFields()
    hay = f"{_clean_subject(subject)}\n{body_text[:8000]}"

    parsed_subject = _parse_xero_invoice_subject(subject)
    if parsed_subject:
        fields.invoice_number, fields.supplier_name = parsed_subject

    for text in (hay, body_text or ""):
        if fields.invoice_number and fields.supplier_name:
            break
        match = _XERO_BILL_SUBJECT_RE.search(text)
        if match:
            fields.invoice_number = match.group(1).strip()
            fields.supplier_name = match.group(2).strip().rstrip(".")
            break

    for pattern in (_XERO_WAS_DUE_RE, _XERO_OVERDUE_LINE_RE, _DUE_LABEL_RE):
        match = pattern.search(body_text or "")
        if match:
            due = _parse_date(match.group(1).strip())
            if due:
                fields.due_date = due
                break

    inv_match = _DATE_LABEL_RE.search(body_text or "")
    if inv_match:
        fields.invoice_date = _parse_date(inv_match.group(2))

    nzd_match = _NZD_AMOUNT_RE.search(body_text or "")
    if nzd_match:
        fields.total = _parse_amount(nzd_match.group(1))
    else:
        total, _, _ = _extract_amounts_from_text(body_text or "")
        if total is not None:
            fields.total = total

    fields.is_overdue = bool(re.search(r"\boverdue\b", body_text or "", re.IGNORECASE))
    fields.raw_text = hay[:8000]
    return fields


def build_line_description(fields: ExtractedFields) -> str:
    supplier = fields.supplier_name or "Supplier"
    ref = fields.invoice_number or "bill"
    description = f"{supplier} — {ref}"
    if fields.is_overdue and fields.due_date:
        description += f" (overdue, due {fields.due_date})"
    elif fields.is_overdue:
        description += " (overdue)"
    return description[:4000]


def build_bill_reference(fields: ExtractedFields, *, xero_link: str | None = None) -> str:
    parts: list[str] = []
    if fields.invoice_number:
        parts.append(fields.invoice_number)
    elif fields.supplier_name:
        parts.append(fields.supplier_name[:80])
    if xero_link:
        parts.append(xero_link)
    return " | ".join(parts)[:255] if parts else "Imported bill"


def _parse_amount(value: str) -> float:
    return float(value.replace(",", "").replace(" ", ""))


def _is_internal_email(email: str | None) -> bool:
    if not email:
        return False
    domain = email.split("@")[-1].lower()
    return domain in _INTERNAL_EMAIL_DOMAINS


def _is_collection_agent_name(name: str | None) -> bool:
    if not name:
        return False
    normalized = re.sub(r"[^\w\s]", " ", name.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return any(marker in normalized for marker in _COLLECTION_AGENT_MARKERS)


def _is_blocked_contact_name(name: str | None) -> bool:
    if not name:
        return True
    stripped = name.strip()
    if re.match(r"^GST\s*(?:No\.?|Number)\b", stripped, re.IGNORECASE):
        return True
    if re.match(r"^Attention\s*:", stripped, re.IGNORECASE):
        return True
    if re.match(r"^(?:Payee|Remit\s+to|Payment\s+to)\s*:", stripped, re.IGNORECASE):
        return True
    normalized = re.sub(r"[^\w\s]", " ", name.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if normalized.startswith("gst no") or normalized.startswith("gst number"):
        return True
    if normalized.startswith("attention"):
        return True
    if normalized in _BLOCKED_CONTACT_NAMES:
        return True
    if normalized.endswith(" group") and "matariki" in normalized:
        return True
    if "matariki" in normalized and "property" in normalized:
        return True
    if _is_collection_agent_name(normalized):
        return True
    return False


def _is_plausible_supplier_name(name: str | None) -> bool:
    return bool(name and not _is_blocked_contact_name(name) and len(name.strip()) >= 3)


def _clean_subject(subject: str) -> str:
    cleaned = _SUBJECT_PREFIX_RE.sub("", subject or "").strip()
    return cleaned or (subject or "")


def _first_match(patterns: list[re.Pattern[str]], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


_REJECT_REF_TOKENS = frozenset({
    "invoice",
    "reference",
    "payment",
    "contribution",
    "number",
    "date",
})


def _extract_reference_number(text: str) -> str | None:
    token = _REF_TOKEN_RE.search(text)
    if token:
        return token.group(1).strip()
    labeled = _REFERENCE_LABEL_RE.search(text)
    if labeled:
        value = labeled.group(1).strip()
        if value.lower() not in _REJECT_REF_TOKENS and len(value) >= 4:
            return value
    return None


def _extract_amounts_from_text(text: str) -> tuple[float | None, float | None, float | None]:
    total = None
    subtotal = None
    tax = None
    amounts = list(_AMOUNT_RE.finditer(text))
    if amounts:
        total = _parse_amount(amounts[-1].group("amount"))
    subtotal_match = _SUBTOTAL_RE.search(text)
    if subtotal_match:
        subtotal = _parse_amount(subtotal_match.group(1))
    gst_match = _GST_RE.search(text)
    if gst_match:
        tax = _parse_amount(gst_match.group(1))
    if total is None:
        for pattern in (_DOLLAR_AMOUNT_RE, _NZD_TRAILING_RE, _CONFIRM_AMOUNT_RE):
            match = pattern.search(text)
            if match:
                total = _parse_amount(match.group(1))
                break
    return total, subtotal, tax


def _extract_supplier_from_email(*, subject: str, body_text: str, from_address: str) -> str | None:
    hay = f"{_clean_subject(subject)}\n{body_text[:6000]}"
    for line in hay.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        council_match = _COUNCIL_LINE_RE.match(cleaned)
        if council_match and not _is_blocked_contact_name(council_match.group(1)):
            return council_match.group(1).strip()

    for match in _FORWARD_FROM_RE.finditer(body_text[:8000]):
        display = (match.group(1) or match.group(2) or match.group(3) or "").strip()
        forward_email = (match.group(4) or "").strip().lower()
        if forward_email and not _is_internal_email(forward_email):
            if display and not _is_blocked_contact_name(display):
                return display[:255]
            domain = forward_email.split("@")[-1]
            if domain.endswith(".govt.nz") or "council" in domain:
                for line in hay.splitlines():
                    council_match = _COUNCIL_LINE_RE.match(line.strip())
                    if council_match:
                        return council_match.group(1).strip()
        if display and not _is_blocked_contact_name(display) and not _is_internal_email(forward_email):
            if not re.search(r"\b(gmail|outlook|hotmail|yahoo)\b", display, re.I):
                return display[:255]

    org = _ORG_NAME_RE.search(hay)
    if org and not _is_blocked_contact_name(org.group(1)):
        return org.group(1).strip()

    subject_org = None
    for line in _clean_subject(subject).splitlines():
        council_match = _COUNCIL_LINE_RE.match(line.strip())
        if council_match:
            subject_org = council_match.group(1).strip()
            break
    if subject_org:
        return subject_org

    display_match = re.search(r"^([^<]+)<", from_address or "")
    if display_match:
        display = display_match.group(1).strip().strip('"')
        sender = email_from_header(from_address)
        if display and not _is_blocked_contact_name(display) and not _is_internal_email(sender):
            return display[:255]
    return None


def _apply_signature_contact(fields: ExtractedFields, body_text: str) -> None:
    from xero_mcp.inbound.email_signatures import best_signature_contact

    signature = best_signature_contact(body_text)
    if not signature:
        return
    if signature.organization and not _is_blocked_contact_name(signature.organization):
        fields.supplier_name = signature.organization
    if signature.person_name:
        fields.contact_person = signature.person_name
    if signature.email and not _is_internal_email(signature.email):
        fields.supplier_email = signature.email
    if signature.phone and not fields.phone:
        fields.phone = signature.phone
    if signature.address_line1 and not fields.address_line1:
        fields.address_line1 = signature.address_line1
    if signature.address_line2 and not fields.address_line2:
        fields.address_line2 = signature.address_line2
    if signature.city and not fields.city:
        fields.city = signature.city
    if signature.postal_code and not fields.postal_code:
        fields.postal_code = signature.postal_code


def extract_from_email(*, subject: str, body_text: str, from_address: str = "") -> ExtractedFields:
    text = f"{_clean_subject(subject)}\n{body_text[:8000]}"
    is_reminder = is_xero_reminder_email(
        from_address=from_address, body_text=body_text, subject=subject
    )

    if is_reminder:
        fields = extract_xero_reminder_fields(subject=subject, body_text=body_text)
        if not fields.invoice_number:
            fields.invoice_number = _extract_reference_number(text)
    else:
        email_supplier = _extract_supplier_from_email(
            subject=subject,
            body_text=body_text,
            from_address=from_address,
        )
        fields = parse_extracted_text(text)
        if email_supplier:
            fields.supplier_name = email_supplier
        _apply_signature_contact(fields, body_text)
        if not fields.invoice_number:
            fields.invoice_number = _extract_reference_number(text)
        total, subtotal, tax = _extract_amounts_from_text(text)
        if fields.total is None and total is not None:
            fields.total = total
        if fields.subtotal is None and subtotal is not None:
            fields.subtotal = subtotal
        if fields.tax_amount is None and tax is not None:
            fields.tax_amount = tax
            fields.tax_rate_label = fields.tax_rate_label or "GST"
        if not fields.invoice_date or not fields.due_date:
            inv_date, due_date = _extract_labeled_dates(text)
            fields.invoice_date = fields.invoice_date or inv_date
            fields.due_date = fields.due_date or due_date
        if not fields.invoice_date:
            fields.invoice_date = _extract_forward_issue_date(body_text)
        fields.raw_text = text[:8000]
        return fields

    if not fields.invoice_number:
        fields.invoice_number = _extract_reference_number(text)
    if fields.supplier_email and fields.supplier_email.endswith("post.xero.com"):
        fields.supplier_email = None
    fields.raw_text = text[:8000]
    return fields


def has_actionable_email_bill(*, subject: str, body_text: str, from_address: str = "") -> bool:
    """True when forwarded email body has enough bill data to create a draft without PDF."""
    if is_xero_reminder_email(from_address=from_address, body_text=body_text, subject=subject):
        parsed = _parse_xero_invoice_subject(subject)
        if parsed:
            return True
        fields = extract_xero_reminder_fields(subject=subject, body_text=body_text)
        return (
            bool(fields.supplier_name)
            and bool(fields.invoice_number)
            and not _is_blocked_contact_name(fields.supplier_name or "")
        )
    fields = extract_from_email(subject=subject, body_text=body_text, from_address=from_address)
    return (
        fields.total is not None
        and fields.total > 0
        and bool(fields.supplier_name)
        and not _is_blocked_contact_name(fields.supplier_name)
    )


def _merge_optional_str(pdf_val: str | None, email_val: str | None) -> str | None:
    return pdf_val or email_val


def _merge_optional_float(pdf_val: float | None, email_val: float | None) -> float | None:
    if pdf_val is not None and pdf_val > 0:
        return pdf_val
    return email_val if email_val is not None and email_val > 0 else pdf_val


_PORTFOLIO_INVOICE_NOISE = frozenset({
    "matariki",
    "matariki property group",
    "matariki group",
    "matariki traders",
    "matariki morningside",
    "logyard",
    "logyard road",
})


def _is_weak_invoice_number(value: str | None) -> bool:
    """Reject portfolio/property tokens mistaken for invoice numbers (no digits)."""
    if not value or not value.strip():
        return True
    cleaned = value.strip()
    lower = cleaned.lower()
    if lower in _PORTFOLIO_INVOICE_NOISE:
        return True
    if "matariki" in lower and not re.search(r"\d", cleaned):
        return True
    if not re.search(r"\d", cleaned):
        return True
    return False


def _resolve_supplier_name(
    *,
    doc_name: str | None,
    email_name: str | None,
    attachment_only_supplier: bool,
    from_address: str,
) -> str | None:
    if _is_plausible_supplier_name(doc_name):
        return doc_name.strip()[:255]
    if attachment_only_supplier:
        return None
    if _is_plausible_supplier_name(email_name):
        return email_name.strip()[:255]
    sender = supplier_from_email(from_address)
    if _is_plausible_supplier_name(sender):
        return sender[:255]
    return None


def _resolve_invoice_number(
    *,
    doc_number: str | None,
    email_number: str | None,
    invoice_hint: str | None,
    attachment_only_invoice: bool,
    subject: str,
    body_text: str,
) -> str | None:
    from xero_mcp.inbound.bill_splits import format_invoice_hint

    hint_number = format_invoice_hint(invoice_hint)
    doc = doc_number.strip() if doc_number and not _is_weak_invoice_number(doc_number) else None
    email = (
        None
        if attachment_only_invoice
        else (email_number.strip() if email_number and not _is_weak_invoice_number(email_number) else None)
    )
    for candidate in (doc, hint_number, email):
        if candidate:
            return candidate
    if not attachment_only_invoice:
        fallback = _extract_reference_number(f"{subject}\n{body_text[:4000]}")
        if fallback and not _is_weak_invoice_number(fallback):
            return fallback
    return hint_number


def merge_field_sources(pdf_fields: ExtractedFields, email_fields: ExtractedFields) -> ExtractedFields:
    merged = ExtractedFields(raw_text=(pdf_fields.raw_text or email_fields.raw_text)[:8000])
    merged.supplier_name = _merge_optional_str(pdf_fields.supplier_name, email_fields.supplier_name)
    merged.invoice_number = _merge_optional_str(pdf_fields.invoice_number, email_fields.invoice_number)
    merged.invoice_date = _merge_optional_str(pdf_fields.invoice_date, email_fields.invoice_date)
    merged.due_date = _merge_optional_str(pdf_fields.due_date, email_fields.due_date)
    merged.total = _merge_optional_float(pdf_fields.total, email_fields.total)
    merged.subtotal = _merge_optional_float(pdf_fields.subtotal, email_fields.subtotal)
    merged.tax_amount = _merge_optional_float(pdf_fields.tax_amount, email_fields.tax_amount)
    merged.tax_rate_label = pdf_fields.tax_rate_label or email_fields.tax_rate_label
    merged.is_overdue = pdf_fields.is_overdue or email_fields.is_overdue
    merged.line_items = pdf_fields.line_items or email_fields.line_items
    merged.supplier_email = _merge_optional_str(pdf_fields.supplier_email, email_fields.supplier_email)
    merged.contact_person = _merge_optional_str(pdf_fields.contact_person, email_fields.contact_person)
    merged.phone = _merge_optional_str(pdf_fields.phone, email_fields.phone)
    merged.address_line1 = _merge_optional_str(pdf_fields.address_line1, email_fields.address_line1)
    merged.address_line2 = _merge_optional_str(pdf_fields.address_line2, email_fields.address_line2)
    merged.city = _merge_optional_str(pdf_fields.city, email_fields.city)
    merged.postal_code = _merge_optional_str(pdf_fields.postal_code, email_fields.postal_code)
    merged.region = _merge_optional_str(pdf_fields.region, email_fields.region)
    return merged


def _extract_labeled_dates(text: str) -> tuple[str | None, str | None]:
    invoice_date = None
    due_date = None
    issue_match = _DATE_LABEL_RE.search(text)
    if issue_match:
        invoice_date = _parse_date(issue_match.group(2))
    due_match = _DUE_LABEL_RE.search(text)
    if due_match:
        due_date = _parse_date(due_match.group(2))
    if not invoice_date:
        dates = [_parse_date(match) for match in _DATE_RE.findall(text)]
        dates = [d for d in dates if d]
        if dates:
            invoice_date = dates[0]
    return invoice_date, due_date


def _is_blocked_supplier_line(line: str) -> bool:
    lower = line.lower().strip()
    if lower in _SUPPLIER_BLOCKLIST:
        return True
    if lower.startswith("to:") and "payment advice" in lower:
        return True
    return False


def _is_invoice_metadata_line(line: str) -> bool:
    """Header/footer fields (Invoice No:, Job Site / Address:, etc.) — not bill line items."""
    stripped = line.strip()
    if not stripped:
        return False
    if _INVOICE_METADATA_LINE_RE.match(stripped):
        return True
    if _INVOICE_FIELD_VALUE_LINE_RE.match(stripped):
        lower = stripped.lower()
        if any(
            token in lower
            for token in (
                "invoice no",
                "invoice date",
                "payment due",
                "job site",
                "job description",
                "customer order",
                "gst no",
                "logyard",
                "whangarei",
                " road",
                "address:",
            )
        ):
            return True
    return False


def _is_plausible_line_quantity(quantity: float, label: str) -> bool:
    """Reject invoice numbers, postcodes, and address fragments parsed as qty."""
    if quantity <= 0:
        return False
    lower = label.lower()
    if _is_invoice_metadata_line(label):
        return False
    if any(token in lower for token in ("invoice no", "job site", "address:")):
        return False
    if re.match(r"^\d+[\s\w]*(?:road|rd|street|st|lane)\s*$", lower) and not re.search(
        r"\b(?:labour|labor|hours|hrs|service|supply|install)\b",
        lower,
    ):
        return False
    labour_hours = bool(re.search(r"\b(?:labour|labor|hours|hrs)\b", lower))
    if quantity >= 100 and not re.search(r"\.\d", label) and not labour_hours:
        return False
    if quantity >= 24 and "." not in f"{quantity:g}" and not labour_hours:
        return False
    return True


def _is_footer_summary_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _FOOTER_SUMMARY_LINE_RE.match(stripped):
        return True
    lower = stripped.lower()
    if lower.startswith(("amount ", "gst ", "subtotal", "total ")):
        return True
    if re.match(r"^gst\s*(?:no|number)\b", lower):
        return True
    return False


def _line_items_section(text: str) -> str:
    match = _TABLE_HEADER_RE.search(text)
    if not match:
        return ""
    section = text[match.end() :]
    section = re.sub(r"^\s*Amount(?:\s+NZD)?\s*\n", "", section, count=1, flags=re.IGNORECASE)
    stop = re.search(
        r"\n(?:Subtotal|TOTAL\b|Amount\s+(?:\$|including)|GST\s+(?:\d+\s*%|No))",
        section,
        re.IGNORECASE,
    )
    return section[: stop.start()] if stop else section


def _resolve_line_amounts(quantity: float, amounts: list[float]) -> tuple[float, float | None]:
    """Pick GST-exclusive unit and line total from trailing PDF amount columns."""
    if not amounts:
        return 0.0, None
    if len(amounts) == 1:
        amount = amounts[0]
        line = round(quantity * amount, 2) if quantity > 0 else amount
        return amount, line

    tol = lambda base: max(0.02, abs(base) * 0.02)
    pairs: list[tuple[float, float, int]] = []
    for unit_idx, unit_cand in enumerate(amounts):
        for line_idx, line_cand in enumerate(amounts):
            if unit_idx == line_idx:
                continue
            if abs(unit_cand - line_cand) <= 0.01:
                continue
            if abs(quantity * unit_cand - line_cand) <= tol(line_cand):
                pairs.append((unit_cand, line_cand, unit_idx))

    if pairs:
        pairs.sort(key=lambda item: (item[0], item[2]))
        return pairs[0][0], pairs[0][1]

    if len(amounts) >= 3:
        unit_cand, gst_cand, line_cand = amounts[0], amounts[1], amounts[2]
        if (
            abs(gst_cand - unit_cand * quantity * 0.15) <= tol(gst_cand)
            and abs(unit_cand * quantity - line_cand) <= tol(line_cand)
        ):
            return unit_cand, line_cand

    if len(amounts) >= 2 and max(amounts) - min(amounts) < 0.01:
        amt = amounts[0]
        if abs(quantity * amt - amt) <= tol(amt):
            return amt, amt

    unit_cand, line_incl = amounts[0], amounts[-1]
    line_ex = round(line_incl / _NZ_GST_FACTOR, 2)
    if abs(quantity * unit_cand - line_ex) <= tol(line_ex):
        return unit_cand, line_ex
    if abs(quantity * unit_cand - line_incl) <= tol(line_incl):
        return round(unit_cand / _NZ_GST_FACTOR, 2), line_ex

    return amounts[0], amounts[-1]


def _normalize_line_item_rows(section: str) -> list[str]:
    """Join PDF description lines with following qty/unit/amount-only rows."""
    rows: list[str] = []
    pending: list[str] = []
    for line in section.splitlines():
        cleaned = line.strip()
        if len(cleaned) < 2:
            continue
        if _is_footer_summary_line(cleaned) or _is_invoice_metadata_line(cleaned):
            if pending:
                rows.append(" ".join(pending))
                pending = []
            continue
        lower = cleaned.lower()
        if lower in _LINE_LABEL_SKIP or lower.startswith("amount nzd"):
            continue
        if _ORPHAN_VALUES_LINE_RE.match(cleaned) or _QTY_MULTI_AMOUNT_RE.match(cleaned):
            if pending:
                rows.append(f"{' '.join(pending)} {cleaned}")
                pending = []
            else:
                rows.append(cleaned)
            continue
        if (
            _QTY_LINE_RE.match(cleaned)
            or _QTY_ONLY_LINE_RE.match(cleaned)
            or _LINE_PRICE_RE.match(cleaned)
            or (_LINE_ITEM_RE.match(cleaned) and "$" in cleaned)
        ):
            if pending:
                rows.append(" ".join(pending))
                pending = []
            rows.append(cleaned)
            continue
        pending.append(cleaned)
    if pending:
        rows.append(" ".join(pending))
    return rows


def _extract_footer_totals(text: str) -> tuple[float | None, float | None, float | None]:
    """Parse Amount / GST / Amount including GST footer lines (excl, tax, incl)."""
    subtotal = None
    tax = None
    total_incl = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^Amount\s+including\s+GST\b", stripped, re.IGNORECASE):
            match = re.search(r"([\d, ]+\.\d{2})", stripped)
            if match:
                total_incl = _parse_amount(match.group(1))
        elif re.match(r"^GST\s+(?:\d+\s*%)?", stripped, re.IGNORECASE) and "gst no" not in stripped.lower():
            match = re.search(r"([\d, ]+\.\d{2})\s*$", stripped)
            if match:
                tax = _parse_amount(match.group(1))
        elif re.match(r"^Amount\s*(?!including)", stripped, re.IGNORECASE) and re.search(
            r"[\d,]+\.\d{2}", stripped
        ):
            if re.match(r"^Amount\s*:", stripped, re.IGNORECASE) or re.match(
                r"^Amount\s+\$", stripped, re.IGNORECASE
            ):
                match = re.search(r"([\d, ]+\.\d{2})", stripped)
                if match:
                    subtotal = _parse_amount(match.group(1))
    return subtotal, tax, total_incl


def _extract_totals(text: str) -> tuple[float | None, float | None]:
    subtotal, tax, total_incl = _extract_footer_totals(text)
    total = total_incl
    if subtotal is None:
        subtotal_match = _SUBTOTAL_RE.search(text)
        if subtotal_match:
            subtotal = _parse_amount(subtotal_match.group(1))
    if total is None:
        total_nzd = _TOTAL_NZD_RE.search(text)
        if total_nzd:
            total = _parse_amount(total_nzd.group(1))
    if total is None:
        amounts = list(_AMOUNT_RE.finditer(text))
        if amounts:
            total = _parse_amount(amounts[-1].group("amount"))
    if total is None:
        for line in text.splitlines():
            if re.match(r"^\s*Subtotal\b", line, re.IGNORECASE):
                continue
            plain = re.match(r"^\s*Total\s+\$?\s*([\d, ]+\.\d{2})\s*$", line, re.IGNORECASE)
            if plain:
                total = _parse_amount(plain.group(1))
    if subtotal is None and total is not None and tax is not None:
        subtotal = round(total - tax, 2)
    return total, subtotal


def _infer_tax_treatment(fields: ExtractedFields) -> None:
    if fields.tax_amount and fields.tax_amount > 0:
        fields.tax_rate_label = fields.tax_rate_label or "GST"
        fields.line_amount_types = fields.line_amount_types or "Exclusive"
        return
    if fields.subtotal is not None and fields.total is not None:
        if abs(fields.subtotal - fields.total) < 0.02:
            fields.tax_amount = None
            fields.tax_rate_label = None
            fields.line_amount_types = "NoTax"
            return
    if fields.total and fields.subtotal and fields.tax_amount is None:
        diff = round(fields.total - fields.subtotal, 2)
        if 0 < diff <= max(1.0, fields.subtotal * 0.2):
            fields.tax_amount = diff
            fields.tax_rate_label = "GST"
            fields.line_amount_types = "Exclusive"
            return
    if not fields.tax_rate_label:
        fields.line_amount_types = fields.line_amount_types or "NoTax"


def _score_supplier_candidate_lines(lines: list[str]) -> list[tuple[int, str]]:
    scored: list[tuple[int, str]] = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned or len(cleaned) > 80:
            continue
        if not _is_supplier_candidate_line(cleaned):
            continue
        if _is_blocked_contact_name(cleaned):
            continue
        score = 0
        if re.search(r"\b(?:Limited|Ltd|Services|Holdings|Group|Corporation|Masonry)\b", cleaned, re.IGNORECASE):
            score += 3
        if re.search(r"\b(?:Hainesco|Haines)\b", cleaned, re.IGNORECASE):
            score += 4
        if re.search(r"\b(?:Building|Fire|Plumbing|Electrical)\b", cleaned, re.IGNORECASE):
            score += 4
        if re.search(r"Three\s*60", cleaned, re.IGNORECASE):
            score += 5
        if re.search(r"Electrical\s*&\s*Security", cleaned, re.IGNORECASE):
            score += 5
        if re.search(r"&\s*Fire", cleaned, re.IGNORECASE):
            score += 2
        scored.append((score, cleaned))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _extract_supplier_from_letterhead(header_lines: list[str]) -> str | None:
    scored = _score_supplier_candidate_lines(header_lines[:15])
    if not scored:
        return None
    return scored[0][1][:255]


def _merge_split_supplier_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    buffer = ""
    for line in lines:
        if buffer and (
            buffer.endswith(" of")
            or buffer.endswith(" &")
            or buffer.endswith(" and")
            or (len(line.split()) <= 2 and not re.search(r"\b(?:Limited|Ltd)\b", line, re.I))
        ):
            buffer = f"{buffer} {line}"
            continue
        if buffer:
            merged.append(buffer)
        buffer = line
    if buffer:
        merged.append(buffer)
    return merged


def _supplier_from_post_reference_block(block: str) -> str | None:
    ref_lines: list[str] = []
    for line in block.splitlines():
        cleaned = line.strip()
        if not cleaned or _is_blocked_supplier_line(cleaned):
            continue
        if re.fullmatch(r"[\d\s$.,/-]+", cleaned) or "@" in cleaned:
            break
        if cleaned.lower().startswith("po box"):
            break
        if re.match(r"^GST\s*Number", cleaned, re.IGNORECASE):
            continue
        if re.fullmatch(r"[\d-]+", cleaned):
            continue
        if not _is_supplier_candidate_line(cleaned):
            continue
        ref_lines.append(cleaned)
    ref_candidates = _merge_split_supplier_lines(ref_lines)
    if ref_candidates:
        scored = _score_supplier_candidate_lines(ref_candidates)
        if scored:
            return scored[0][1][:255]
    return None


def _normalize_payment_advice_supplier(name: str) -> str:
    """Prefer trading name after slash (e.g. HAINESCO/Haines Masonry ltd)."""
    cleaned = re.sub(r"\s+", " ", name.strip())
    if "/" in cleaned:
        left, right = cleaned.split("/", 1)
        right = right.strip()
        if right and (
            re.search(r"\b(?:Ltd|Limited|Masonry|Services|Group)\b", right, re.IGNORECASE)
            or len(right) > len(left)
        ):
            return right[:255]
    return cleaned[:255]


def _extract_supplier(text: str) -> str | None:
    to_match = _TO_SUPPLIER_RE.search(text)
    if to_match:
        candidate = _normalize_payment_advice_supplier(to_match.group(1).strip())
        if (
            candidate
            and not _is_blocked_supplier_line(candidate)
            and not _is_blocked_contact_name(candidate)
        ):
            return candidate[:255]

    tax_idx = text.upper().find("TAX INVOICE")
    header_lines = text[:tax_idx].splitlines() if tax_idx >= 0 else text.splitlines()
    if any("payment advice" in line.lower() for line in header_lines[:5]):
        header_lines = []

    letterhead = _extract_supplier_from_letterhead(header_lines)
    if letterhead:
        return letterhead

    gst_match = _SUPPLIER_AFTER_GST_NUMBER_RE.search(text)
    if gst_match:
        name = _supplier_from_post_reference_block(gst_match.group(1))
        if name:
            return name

    ref_match = _SUPPLIER_AFTER_REFERENCE_RE.search(text)
    if ref_match:
        name = _supplier_from_post_reference_block(ref_match.group(1))
        if name:
            return name

    search_lines = text[tax_idx:].splitlines() if tax_idx >= 0 else []
    for line in search_lines[:30]:
        cleaned = line.strip()
        if not cleaned or len(cleaned) > 80:
            continue
        if _is_supplier_candidate_line(cleaned) and not _is_blocked_contact_name(cleaned):
            return cleaned[:255]

    return None


def _is_supplier_candidate_line(cleaned: str) -> bool:
    lower = cleaned.lower()
    if re.match(r"^gst\s*(?:no\.?|number)\b", lower):
        return False
    if re.match(r"^attention\s*:", lower):
        return False
    if re.match(r"^(?:payee|remit\s+to|payment\s+to)\s*:", lower):
        return False
    if any(lower.startswith(prefix) for prefix in _SUPPLIER_SKIP):
        return False
    if _is_blocked_supplier_line(cleaned):
        return False
    if re.search(r"@|https?://|www\.", lower):
        return False
    if re.fullmatch(r"[\d\s$.,/-]+", cleaned):
        return False
    if _STREET_HINT_RE.search(cleaned) and len(cleaned.split()) <= 4:
        return False
    if re.match(r"^(invoice date|invoice number|reference|due date)(:|\s)*", lower):
        return False
    if _DATE_LABEL_RE.search(cleaned) or _DUE_LABEL_RE.search(cleaned):
        return False
    if re.match(r"^\d{1,2}\s+\w+\s+\d{4}$", cleaned):
        return False
    if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", cleaned):
        return False
    return True


def _parse_line_items_from_section(section: str) -> list[LineItem]:
    items: list[LineItem] = []
    for line in _normalize_line_item_rows(section):
        cleaned = line.strip()
        if len(cleaned) < 5 or _is_footer_summary_line(cleaned) or _is_invoice_metadata_line(cleaned):
            continue
        multi_match = _QTY_MULTI_AMOUNT_RE.match(cleaned)
        if multi_match:
            label = multi_match.group(1).strip()
            quantity = float(multi_match.group(2))
            amounts = [_parse_amount(value) for value in _TRAILING_AMOUNTS_RE.findall(multi_match.group(3))]
            if label.lower() in _LINE_LABEL_SKIP or not _is_plausible_line_quantity(quantity, label):
                continue
            unit_amount, line_amount = _resolve_line_amounts(quantity, amounts)
            item = LineItem(
                description=label[:4000],
                quantity=quantity,
                unit_amount=unit_amount,
            )
            if line_amount is not None and abs(quantity * unit_amount - line_amount) > 0.01:
                item.line_amount = line_amount
            items.append(item)
            continue
        qty_match = _QTY_LINE_RE.match(cleaned)
        if qty_match:
            label = qty_match.group(1).strip()
            quantity = float(qty_match.group(2))
            if label.lower() in _LINE_LABEL_SKIP or not _is_plausible_line_quantity(quantity, label):
                continue
            amounts = [_parse_amount(qty_match.group(3)), _parse_amount(qty_match.group(4))]
            unit_amount, line_amount = _resolve_line_amounts(quantity, amounts)
            item = LineItem(
                description=label[:4000],
                quantity=quantity,
                unit_amount=unit_amount,
            )
            if line_amount is not None:
                item.line_amount = line_amount
            items.append(item)
            continue
        qty_only = _QTY_ONLY_LINE_RE.match(cleaned)
        if qty_only:
            label = qty_only.group(1).strip()
            quantity = float(qty_only.group(2))
            if label.lower() in _LINE_LABEL_SKIP or not _is_plausible_line_quantity(quantity, label):
                continue
            items.append(
                LineItem(
                    description=label[:4000],
                    quantity=quantity,
                    unit_amount=0.0,
                )
            )
            continue
        price_match = _LINE_PRICE_RE.match(cleaned)
        if price_match:
            label = price_match.group(1).strip()
            if label.lower() in _LINE_LABEL_SKIP:
                continue
            items.append(
                LineItem(
                    description=label[:4000],
                    quantity=1.0,
                    unit_amount=_parse_amount(price_match.group(2)),
                )
            )
            continue
        line_match = _LINE_ITEM_RE.match(cleaned)
        if line_match and "$" in cleaned:
            label = line_match.group(1).strip()
            if label.lower() in _LINE_LABEL_SKIP:
                continue
            items.append(
                LineItem(
                    description=label[:4000],
                    quantity=1.0,
                    unit_amount=_parse_amount(line_match.group(2)),
                )
            )
    return items[:20]


def _reconcile_exclusive_line_prices(fields: ExtractedFields) -> None:
    """When unit*qty exceeds footer subtotal, treat unit as GST-inclusive."""
    if not fields.subtotal or fields.subtotal <= 0:
        return
    for item in fields.line_items:
        if item.quantity <= 0 or item.unit_amount <= 0:
            continue
        gross = round(item.quantity * item.unit_amount, 2)
        if gross > fields.subtotal * 1.02:
            item.unit_amount = round(fields.subtotal / item.quantity, 2)
            item.line_amount = None


def _finalize_qty_only_line_items(fields: ExtractedFields) -> None:
    """Allocate footer subtotal across qty-only rows via LineAmount (UnitAmount stays 0)."""
    if not fields.line_items:
        return
    if any(item.unit_amount > 0 for item in fields.line_items):
        return
    base = fields.subtotal
    if base is None and fields.total and fields.tax_amount:
        base = round(fields.total - fields.tax_amount, 2)
    if base is None or base <= 0:
        return
    total_qty = sum(item.quantity for item in fields.line_items if item.quantity > 0)
    if total_qty <= 0:
        return
    cents = int(round(base * 100))
    allocated_cents = 0
    for index, item in enumerate(fields.line_items):
        if index == len(fields.line_items) - 1:
            item.line_amount = round((cents - allocated_cents) / 100, 2)
        else:
            share_cents = int(round(cents * (item.quantity / total_qty)))
            item.line_amount = round(share_cents / 100, 2)
            allocated_cents += share_cents


def _extract_line_items(text: str) -> list[LineItem]:
    section = _line_items_section(text)
    items = _parse_line_items_from_section(section) if section.strip() else []
    if not items:
        items = _parse_line_items_from_section(text)
    return items[:20]


def _extract_contact_details(text: str, supplier_name: str | None) -> dict[str, str | None]:
    header = text[:2500]
    details: dict[str, str | None] = {
        "supplier_email": None,
        "phone": None,
        "address_line1": None,
        "address_line2": None,
        "city": None,
        "postal_code": None,
        "region": None,
    }

    email_match = _EMAIL_LABEL_RE.search(text)
    if email_match:
        details["supplier_email"] = email_match.group(1).lower()
    else:
        for line in text.splitlines()[:25]:
            if supplier_name and supplier_name in line:
                continue
            found = _EMAIL_ANY_RE.search(line)
            if found and "bill to" not in line.lower():
                details["supplier_email"] = found.group(0).lower()
                break

    phone_match = _PHONE_LABEL_RE.search(header)
    if phone_match:
        details["phone"] = re.sub(r"\s+", " ", phone_match.group(1)).strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    address_lines: list[str] = []
    started = False
    supplier_norm = (supplier_name or "").lower()
    for line in lines:
        lower = line.lower()
        if supplier_norm and supplier_norm in lower and "to:" not in lower:
            started = True
            continue
        if supplier_norm and line == supplier_name:
            started = True
            continue
        if not started and line.lower().startswith("po box"):
            started = True
            address_lines.append(line)
            continue
        if not started:
            continue
        if any(lower.startswith(prefix) for prefix in _SUPPLIER_SKIP):
            break
        if _INVOICE_NO_RE.search(line) or _DATE_LABEL_RE.search(line) or lower.startswith("tax invoice"):
            break
        if _EMAIL_ANY_RE.search(line) or _PHONE_LABEL_RE.search(line):
            continue
        if re.fullmatch(r"[\d\s$.,/-]+", line):
            continue
        if len(line) <= 80:
            address_lines.append(line)
        if len(address_lines) >= 3:
            break

    if address_lines:
        details["address_line1"] = address_lines[0]
        if len(address_lines) > 2:
            details["address_line2"] = address_lines[1]
            city_line = address_lines[2]
        elif len(address_lines) > 1:
            city_line = address_lines[1]
        else:
            city_line = None
        if city_line:
            city_match = _CITY_POSTAL_RE.match(city_line)
            if city_match:
                details["city"] = city_match.group(1).strip()
                details["postal_code"] = city_match.group(2)
            elif _STREET_HINT_RE.search(city_line):
                details["address_line2"] = city_line
            else:
                details["city"] = city_line

    return details


def extract_text_from_pdf(data: bytes) -> str:
    from xero_mcp.inbound.document_text import extract_pdf_text

    return extract_pdf_text(data)


def extract_from_attachment(data: bytes, filename: str) -> ExtractedFields:
    from xero_mcp.inbound.document_text import extract_text_from_attachment

    text = extract_text_from_attachment(data, filename)
    if not text.strip():
        return ExtractedFields()
    return parse_extracted_text(text)


def parse_extracted_text(text: str) -> ExtractedFields:
    fields = ExtractedFields(raw_text=text[:8000])

    footer_sub, footer_tax, footer_total = _extract_footer_totals(text)
    fields.total, fields.subtotal = _extract_totals(text)
    if footer_sub is not None:
        fields.subtotal = footer_sub
    if footer_total is not None:
        fields.total = footer_total
    if footer_tax is not None:
        fields.tax_amount = footer_tax
        fields.tax_rate_label = "GST"
    elif (gst_match := _GST_RE.search(text)):
        fields.tax_amount = _parse_amount(gst_match.group(1))
        fields.tax_rate_label = "GST"

    inv_match = _INVOICE_NO_RE.search(text)
    tax_inv_match = _TAX_INVOICE_NUM_RE.search(text)
    fields.invoice_number = _extract_reference_number(text)
    if tax_inv_match:
        fields.invoice_number = tax_inv_match.group(1).strip()
    elif not fields.invoice_number and inv_match:
        fields.invoice_number = inv_match.group(1).strip()

    fields.invoice_date, fields.due_date = _extract_labeled_dates(text)
    fields.is_overdue = bool(_OVERDUE_RE.search(text))
    fields.supplier_name = _extract_supplier(text)
    contact = _extract_contact_details(text, fields.supplier_name)
    fields.supplier_email = contact["supplier_email"]
    fields.phone = contact["phone"]
    fields.address_line1 = contact["address_line1"]
    fields.address_line2 = contact["address_line2"]
    fields.city = contact["city"]
    fields.postal_code = contact["postal_code"]
    fields.region = contact["region"]
    fields.line_items = _extract_line_items(text)
    _finalize_qty_only_line_items(fields)
    _reconcile_exclusive_line_prices(fields)

    _infer_tax_treatment(fields)

    if fields.line_items and fields.total:
        line_sum = round(
            sum(
                item.line_amount
                if item.line_amount is not None
                else item.quantity * item.unit_amount
                for item in fields.line_items
            ),
            2,
        )
        compare_to = fields.subtotal or fields.total
        if line_sum <= 0 or abs(line_sum - compare_to) > max(5.0, compare_to * 0.08):
            if not any(item.line_amount for item in fields.line_items):
                fields.line_items = []

    return fields


def extract_from_pdf(data: bytes) -> ExtractedFields:
    text = extract_text_from_pdf(data)
    if not text.strip():
        return ExtractedFields()
    return parse_extracted_text(text)


def email_from_header(from_header: str) -> str | None:
    match = _EMAIL_ANY_RE.search(from_header or "")
    return match.group(0).lower() if match else None


def supplier_from_email(from_header: str) -> str | None:
    sender = email_from_header(from_header)
    if _is_internal_email(sender):
        display_match = re.search(r"^([^<]+)<", from_header or "")
        if display_match:
            display = display_match.group(1).strip().strip('"')
            if display and not _is_blocked_contact_name(display):
                return display[:255]
        return None
    match = re.search(r"^([^<]+)<", from_header)
    if match:
        display = match.group(1).strip().strip('"')
        if display and not _is_blocked_contact_name(display):
            return display
    match = re.search(r"([\w.+-]+)@([\w.-]+)", from_header)
    if match:
        domain = match.group(2).split(".")[0]
        name = domain.replace("-", " ").title()
        if not _is_blocked_contact_name(name):
            return name
    return None


def _invoice_numbers_in_text(text: str) -> set[str]:
    numbers: set[str] = set()
    for pattern in (_INVOICE_NO_RE, _TAX_INVOICE_NUM_RE):
        for match in pattern.finditer(text or ""):
            value = match.group(1).strip()
            if value and not _is_weak_invoice_number(value):
                numbers.add(value)
    ref = _extract_reference_number(text or "")
    if ref and not _is_weak_invoice_number(ref):
        numbers.add(ref)
    return numbers


def coalesce_pdf_invoice_sections(full_text: str, chunks: list[str]) -> list[str]:
    """One PDF → one draft unless multiple distinct invoice numbers are detected."""
    if len(chunks) <= 1:
        return chunks
    if len(_invoice_numbers_in_text(full_text)) <= 1:
        return [full_text]
    return chunks


def split_extracted_text_by_invoices(text: str) -> list[str]:
    """Best-effort split when one PDF contains multiple invoices (multiple headers)."""
    if not text or len(text) < 120:
        return [text] if text else [""]

    markers: list[int] = []
    for pattern in (
        r"(?:^|\n)\s*(?:TAX\s+INVOICE|Tax\s+Invoice)\b",
        r"(?:^|\n)\s*Invoice\s*(?:No\.?|Number|#)\s*[:=]",
    ):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if not markers or match.start() > markers[-1] + 40:
                markers.append(match.start())

    markers = sorted(set(markers))
    if len(markers) <= 1:
        return [text]

    chunks: list[str] = []
    for index, start in enumerate(markers):
        end = markers[index + 1] if index + 1 < len(markers) else len(text)
        chunk = text[start:end].strip()
        if len(chunk) >= 50:
            chunks.append(chunk)
    return chunks if len(chunks) > 1 else [text]


def merge_extraction(
    *,
    from_address: str,
    subject: str,
    body_text: str,
    attachment_bytes: bytes,
    attachment_name: str | None = None,
    extra_attachments: list[tuple[str, bytes]] | None = None,
    attachment_text: str | None = None,
    invoice_hint: str | None = None,
    attachment_only_invoice: bool = False,
    attachment_only_supplier: bool = False,
) -> ExtractedFields:
    from pathlib import Path

    doc_fields = ExtractedFields()
    candidates: list[tuple[str, bytes]] = []
    if attachment_bytes and attachment_name:
        candidates.append((attachment_name, attachment_bytes))
    candidates.extend(extra_attachments or [])

    for name, data in candidates:
        if not data:
            continue
        if Path(name).suffix.lower() not in _BILL_DOC_EXTENSIONS:
            continue
        if attachment_text and name == attachment_name:
            attempt = parse_extracted_text(attachment_text)
        else:
            attempt = extract_from_attachment(data, name)
        if attempt.raw_text.strip() or attempt.total or attempt.invoice_number or attempt.supplier_name:
            doc_fields = attempt
            break
        if not doc_fields.raw_text and (attempt.supplier_name or attempt.total):
            doc_fields = attempt

    email_fields = extract_from_email(
        subject=subject,
        body_text=body_text,
        from_address=from_address,
    )
    extracted = merge_field_sources(doc_fields, email_fields)
    extracted.invoice_number = _resolve_invoice_number(
        doc_number=doc_fields.invoice_number,
        email_number=email_fields.invoice_number,
        invoice_hint=invoice_hint,
        attachment_only_invoice=attachment_only_invoice,
        subject=subject,
        body_text=body_text,
    )
    extracted.supplier_name = _resolve_supplier_name(
        doc_name=doc_fields.supplier_name,
        email_name=email_fields.supplier_name,
        attachment_only_supplier=attachment_only_supplier,
        from_address=from_address,
    )
    skip_signature = attachment_only_supplier and _is_plausible_supplier_name(doc_fields.supplier_name)
    if not skip_signature:
        _apply_signature_contact(extracted, body_text)
        if attachment_only_supplier and _is_blocked_contact_name(extracted.supplier_name):
            extracted.supplier_name = doc_fields.supplier_name

    extracted.sender_email = email_from_header(from_address)
    if extracted.supplier_email and "post.xero.com" in extracted.supplier_email:
        extracted.supplier_email = None
    if extracted.contact_email and "post.xero.com" in extracted.contact_email:
        extracted.contact_email = None
    if extracted.supplier_email:
        extracted.contact_email = extracted.supplier_email
    elif extracted.sender_email and not _is_internal_email(extracted.sender_email):
        extracted.contact_email = extracted.sender_email

    if not _is_plausible_supplier_name(extracted.supplier_name):
        fallback_candidates: list[str | None] = []
        if not attachment_only_supplier:
            fallback_candidates.append(email_fields.supplier_name)
        fallback_candidates.extend([supplier_from_email(from_address), "Imported Supplier"])
        for candidate in fallback_candidates:
            if _is_plausible_supplier_name(candidate):
                extracted.supplier_name = candidate
                break
        else:
            extracted.supplier_name = "Imported Supplier"

    if extracted.total is None:
        extracted.total = 0.0

    if body_text:
        merged_raw = "\n".join(part for part in (extracted.raw_text, body_text[:2000]) if part)
        extracted.raw_text = merged_raw[:8000]
    return extracted


def extraction_summary(fields: ExtractedFields) -> dict[str, Any]:
    return {
        "supplier_name": fields.supplier_name,
        "invoice_number": fields.invoice_number,
        "invoice_date": fields.invoice_date,
        "due_date": fields.due_date,
        "total": fields.total,
        "subtotal": fields.subtotal,
        "tax_amount": fields.tax_amount,
        "tax_rate_label": fields.tax_rate_label,
        "is_overdue": fields.is_overdue,
        "line_item_count": len(fields.line_items),
        "sender_email": fields.sender_email,
        "supplier_email": fields.supplier_email,
        "contact_email": fields.contact_email,
        "contact_person": fields.contact_person,
        "phone": fields.phone,
        "address_line1": fields.address_line1,
        "city": fields.city,
        "postal_code": fields.postal_code,
    }

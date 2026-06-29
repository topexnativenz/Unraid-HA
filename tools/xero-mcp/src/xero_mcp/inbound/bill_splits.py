from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from xero_mcp.inbound.attachments import is_bill_attachment, rank_bill_attachments
from xero_mcp.inbound.config import InboundConfig
from xero_mcp.inbound.extract import has_actionable_email_bill
from xero_mcp.inbound.email_models import InboundAttachment, ParsedInboundEmail
from xero_mcp.inbound.xero_links import XeroLink, detect_xero_links, group_xero_links_for_bills

_FILENAME_INV_RE = re.compile(
    r"(?:^|[_\-.])(?:INV|INVOICE)[-_ ]?([A-Z0-9][-A-Z0-9]{2,})(?:[_\-.]|$)",
    re.IGNORECASE,
)
_FILENAME_REF_RE = re.compile(
    r"(?:^|[_\-.])(DCPM\d+|INV[-_]?\d+)(?:[_\-.]|$)",
    re.IGNORECASE,
)
_FILENAME_NUMERIC_RE = re.compile(
    r"(?:^|[_\-.])(\d{4,10})(?:[_\-.]|$)",
)


@dataclass
class InboundBillSplit:
    kind: str
    attachments: list[InboundAttachment]
    xero_links: list[XeroLink]
    invoice_hint: str | None
    split_index: int
    split_total: int


def invoice_number_from_filename(name: str) -> str | None:
    base = Path(name).stem
    for pattern in (_FILENAME_INV_RE, _FILENAME_REF_RE, _FILENAME_NUMERIC_RE):
        match = pattern.search(base)
        if match:
            return match.group(1).upper().replace("_", "-")
    return None


def format_invoice_hint(hint: str | None) -> str | None:
    """Turn queue invoice_hint (68451) into Xero InvoiceNumber (INV-68451)."""
    if not hint or not str(hint).strip():
        return None
    cleaned = str(hint).strip().upper().replace("_", "-")
    if cleaned.startswith("INV-"):
        return cleaned
    if cleaned.startswith("INV") and cleaned[3:].replace("-", "").isdigit():
        return f"INV-{cleaned[3:].lstrip('-')}"
    digits = cleaned.replace("-", "")
    if digits.isdigit():
        if len(digits) <= 4:
            return digits.lstrip("0") or digits
        return f"INV-{digits.lstrip('0') or digits}"
    return cleaned


def split_inbound_into_bills(
    parsed: ParsedInboundEmail,
    *,
    bill_attachments: list[InboundAttachment],
    xero_links: list[XeroLink],
    config: InboundConfig,
    has_actionable_body: bool,
) -> list[InboundBillSplit]:
    """One queue record (and Xero draft) per bill attachment, link group, or body-only bill."""
    if bill_attachments:
        ranked = rank_bill_attachments(bill_attachments)
        total = len(ranked)
        return [
            InboundBillSplit(
                kind="attachment",
                attachments=[attachment],
                xero_links=[],
                invoice_hint=invoice_number_from_filename(attachment.name),
                split_index=index,
                split_total=total,
            )
            for index, attachment in enumerate(ranked)
        ]

    if xero_links and config.allow_xero_links and config.allow_xero_link_without_attachment:
        groups = group_xero_links_for_bills(xero_links)
        total = len(groups)
        return [
            InboundBillSplit(
                kind="link",
                attachments=[],
                xero_links=group,
                invoice_hint=None,
                split_index=index,
                split_total=total,
            )
            for index, group in enumerate(groups)
        ]

    if config.allow_email_body_without_attachment and has_actionable_body:
        return [
            InboundBillSplit(
                kind="body",
                attachments=[],
                xero_links=[],
                invoice_hint=None,
                split_index=0,
                split_total=1,
            )
        ]

    return [
        InboundBillSplit(
            kind="none",
            attachments=[],
            xero_links=[],
            invoice_hint=None,
            split_index=0,
            split_total=1,
        )
    ]


def build_split_dedupe_key(
    *,
    org_slug: str,
    from_address: str,
    split: InboundBillSplit,
) -> str:
    import hashlib

    parts = [org_slug, from_address]
    if split.attachments:
        parts.append(split.attachments[0].sha256)
    elif split.xero_links:
        primary = split.xero_links[0].invoice_id or split.xero_links[0].url.split("?")[0]
        parts.append(primary)
    else:
        parts.append("body-only")
    if split.invoice_hint:
        parts.append(split.invoice_hint)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def collect_non_bill_attachments(
    parsed: ParsedInboundEmail,
    config: InboundConfig,
    splits: list[InboundBillSplit],
) -> list[InboundAttachment]:
    """Signature/logo images stored on the first split for audit only."""
    bill_hashes = {
        att.sha256
        for split in splits
        for att in split.attachments
    }
    extras: list[InboundAttachment] = []
    for attachment in parsed.attachments:
        suffix = Path(attachment.name).suffix.lower()
        if suffix not in config.allowed_extensions:
            continue
        if attachment.sha256 in bill_hashes:
            continue
        if is_bill_attachment(attachment.name, len(attachment.data), attachment.content_type):
            continue
        extras.append(attachment)
    return extras

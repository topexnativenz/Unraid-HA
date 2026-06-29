from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

from xero_mcp.inbound.attachments import is_bill_attachment
from xero_mcp.inbound.bill_splits import format_invoice_hint, invoice_number_from_filename
from xero_mcp.inbound.config import ATTACHMENTS_DIR

_SUBJECT_INV_RE = re.compile(r"\bINV[-\s]?(\d[\d\-]*)\b", re.IGNORECASE)


def _invoice_hint_from_record(record: dict[str, Any]) -> str | None:
    hint = record.get("invoice_hint")
    if hint:
        return format_invoice_hint(str(hint))
    subject = record.get("subject") or ""
    match = _SUBJECT_INV_RE.search(subject)
    if match:
        return format_invoice_hint(match.group(1))
    return None


def _record_has_bill_attachment(record: dict[str, Any]) -> bool:
    for item in record.get("attachments") or []:
        name = item.get("name") or ""
        size = int(item.get("size") or 0)
        if is_bill_attachment(name, size, item.get("content_type") or ""):
            return True
    return False


def _hint_matches_filename(hint: str, filename: str) -> bool:
    formatted = format_invoice_hint(hint) or hint
    upper_name = filename.upper()
    if formatted and formatted.upper() in upper_name:
        return True
    digits = formatted.replace("INV-", "").replace("-", "") if formatted else ""
    if digits and digits in upper_name.replace("-", "").replace("_", ""):
        return True
    from_name = invoice_number_from_filename(filename)
    if from_name and formatted and format_invoice_hint(from_name) == formatted:
        return True
    return False


def recover_missing_bill_attachment(record: dict[str, Any]) -> bool:
    """Copy a matching bill PDF from another enqueue folder when intake dropped it."""
    if _record_has_bill_attachment(record):
        return False

    hint = _invoice_hint_from_record(record)
    if not hint:
        return False

    source_message_id = record.get("source_message_id")
    if not source_message_id:
        return False
    dest_dir = ATTACHMENTS_DIR / str(source_message_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    best: Path | None = None
    for folder in ATTACHMENTS_DIR.iterdir():
        if not folder.is_dir() or folder.name == str(source_message_id):
            continue
        for path in folder.iterdir():
            if path.suffix.lower() != ".pdf":
                continue
            if not _hint_matches_filename(hint, path.name):
                continue
            if best is None or path.stat().st_size > best.stat().st_size:
                best = path

    if best is None:
        return False

    target = dest_dir / best.name
    if not target.exists() or target.stat().st_size != best.stat().st_size:
        shutil.copy2(best, target)

    data = target.read_bytes()
    record.setdefault("attachments", []).append(
        {
            "name": target.name,
            "path": str(target),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_type": "application/pdf",
            "size": len(data),
            "is_primary": True,
        }
    )
    record["invoice_hint"] = record.get("invoice_hint") or hint.replace("INV-", "")
    record["error"] = None
    record.pop("attachment_warning", None)
    return True

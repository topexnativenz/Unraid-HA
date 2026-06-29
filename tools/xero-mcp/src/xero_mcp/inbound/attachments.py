from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_SIGNATURE_NAME = re.compile(
    r"^(?:image\d*|logo|signature|sig|banner|icon|spacer|pixel|footer|header|"
    r"linkedin|facebook|twitter|instagram|youtube|cid|att\d+|sm\d+|"
    r"outlook-\d+|~?[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"
    r"(?:[._-].*)?$",
    re.IGNORECASE,
)

_EXT_SCORE = {
    ".pdf": 100,
    ".doc": 100,
    ".docx": 100,
    ".xls": 100,
    ".xlsx": 100,
    ".heic": 55,
    ".jpg": 50,
    ".jpeg": 50,
    ".png": 45,
}

_MIN_BILL_IMAGE_BYTES = 100_000
_MAX_SIGNATURE_BYTES = 80_000


def is_signature_image(name: str, size: int, content_type: str = "") -> bool:
    base = Path(name).name
    if _SIGNATURE_NAME.match(base):
        return True
    lower = base.lower()
    if any(token in lower for token in ("signature", "logo", "sig.", "sig_", "-sig", "footer", "header")):
        return True
    if content_type.startswith("image/") and size < _MAX_SIGNATURE_BYTES:
        if re.match(r"^image\d+\.(png|jpe?g|gif)$", lower):
            return True
    return False


def is_bill_attachment(name: str, size: int, content_type: str = "") -> bool:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        return True
    if suffix in (".doc", ".docx", ".xls", ".xlsx"):
        return True
    if suffix in (".jpg", ".jpeg", ".png", ".heic"):
        if is_signature_image(name, size, content_type):
            return False
        return size >= _MIN_BILL_IMAGE_BYTES
    return False


def attachment_priority(name: str, size: int, content_type: str = "") -> tuple[int, int]:
    suffix = Path(name).suffix.lower()
    type_score = _EXT_SCORE.get(suffix, 20)
    if is_signature_image(name, size, content_type):
        type_score = min(type_score, 5)
    size_score = min(size // 500, 400)
    return (type_score, size_score)


def rank_bill_attachments(attachments: list[Any]) -> list[Any]:
    if not attachments:
        return []
    ranked = sorted(
        attachments,
        key=lambda att: attachment_priority(att.name, len(att.data), att.content_type),
        reverse=True,
    )
    bill_like = [att for att in ranked if is_bill_attachment(att.name, len(att.data), att.content_type)]
    if bill_like:
        return bill_like + [att for att in ranked if att not in bill_like]
    return ranked


def collect_bill_attachment_files(
    attachments: list[dict[str, Any]],
    *,
    read_bytes: Any,
) -> list[tuple[str, bytes]]:
    """All bill-source files (pdf/docx/doc/xlsx/large scans), signatures excluded."""
    ordered = sorted(
        attachments,
        key=lambda item: attachment_priority(
            item.get("name") or "",
            int(item.get("size") or 0),
            item.get("content_type") or "",
        ),
        reverse=True,
    )
    files: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for item in ordered:
        name = item.get("name") or "attachment"
        size = int(item.get("size") or 0)
        content_type = item.get("content_type") or ""
        if is_signature_image(name, size, content_type):
            continue
        if not is_bill_attachment(name, size, content_type):
            continue
        safe = Path(name).name
        if safe in seen:
            continue
        seen.add(safe)
        files.append((safe, read_bytes(item)))
    return files

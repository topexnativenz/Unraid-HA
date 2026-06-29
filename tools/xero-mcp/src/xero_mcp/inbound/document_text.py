from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

_W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_XL_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _xml_text_chunks(xml_bytes: bytes, tag: str, ns: dict[str, str]) -> list[str]:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return []
    chunks: list[str] = []
    for node in root.findall(f".//{tag}", ns):
        if node.text:
            chunks.append(node.text)
        if node.tail:
            chunks.append(node.tail)
    return chunks


def extract_docx_text(data: bytes) -> str:
    if not data:
        return ""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                return ""
            xml_bytes = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        return ""
    parts = _xml_text_chunks(xml_bytes, "w:t", _W_NS)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def extract_xlsx_text(data: bytes) -> str:
    if not data:
        return ""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
            chunks: list[str] = []
            if "xl/sharedStrings.xml" in names:
                chunks.extend(_xml_text_chunks(archive.read("xl/sharedStrings.xml"), "main:t", _XL_NS))
            for sheet in sorted(name for name in names if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")):
                chunks.extend(_xml_text_chunks(archive.read(sheet), "main:t", _XL_NS))
                if len(chunks) > 500:
                    break
    except (zipfile.BadZipFile, KeyError):
        return ""
    return "\n".join(part.strip() for part in chunks if part and part.strip())


def extract_doc_text(data: bytes) -> str:
    """Best-effort legacy .doc text (binary OLE — no structured parser)."""
    if not data:
        return ""
    utf16 = data.decode("utf-16-le", errors="ignore")
    utf16_clean = re.sub(r"[^\S\n\r\t\u0080-\uFFFF]", " ", utf16)
    utf16_lines = [line.strip() for line in utf16_clean.splitlines() if len(line.strip()) >= 4]
    if utf16_lines:
        return "\n".join(utf16_lines[:200])
    ascii_text = re.sub(rb"[^\x09\x0a\x0d\x20-\x7e]", b" ", data)
    lines = [
        line.decode("ascii", errors="ignore").strip()
        for line in re.split(rb"[\r\n]+", ascii_text)
        if len(line.strip()) >= 4
    ]
    return "\n".join(lines[:200])


def extract_pdf_text(data: bytes) -> str:
    if not data:
        return ""
    try:
        reader = PdfReader(BytesIO(data))
        chunks: list[str] = []
        for page in reader.pages[:8]:
            chunks.append(page.extract_text() or "")
        return "\n".join(chunks)
    except Exception:
        return ""


def extract_text_from_attachment(data: bytes, filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(data)
    if suffix == ".docx":
        return extract_docx_text(data)
    if suffix == ".doc":
        return extract_doc_text(data)
    if suffix in (".xlsx", ".xls"):
        if suffix == ".xlsx":
            return extract_xlsx_text(data)
        return extract_doc_text(data)
    return ""


def is_document_attachment(filename: str) -> bool:
    return Path(filename or "").suffix.lower() in {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
    }

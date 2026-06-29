from __future__ import annotations

import re
from dataclasses import dataclass, field

from xero_mcp.inbound.extract import (
    _COUNCIL_LINE_RE,
    _CITY_POSTAL_RE,
    _EMAIL_ANY_RE,
    _EMAIL_LABEL_RE,
    _ORG_NAME_RE,
    _PHONE_LABEL_RE,
    _STREET_HINT_RE,
    _is_blocked_contact_name,
    _is_internal_email,
)

_SIGNATURE_DELIM = re.compile(
    r"(?:^|\n)(?:--+\s*$|_{3,}|Kind regards,?,?|Best regards,?,?|Ngā mihi,?,?|"
    r"Nga mihi,?,?|Thanks,?,?|Thank you,?,?|Sent from (?:my )?(?:iPhone|Outlook|Mail))",
    re.IGNORECASE | re.MULTILINE,
)
_TITLE_LINE_RE = re.compile(
    r"\b(officer|manager|coordinator|administrator|assistant|specialist|accountant|"
    r"contributions|accounts|billing|finance)\b",
    re.IGNORECASE,
)
_PERSON_LINE_RE = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z'’-]+){1,2}$")


@dataclass
class SignatureContact:
    organization: str | None = None
    person_name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    postal_code: str | None = None


def _parse_signature_block(block: str) -> SignatureContact | None:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    contact = SignatureContact()
    emails = _EMAIL_ANY_RE.findall(block)
    for email in emails:
        lower = email.lower()
        if not _is_internal_email(lower):
            contact.email = lower
            break

    phone_match = _PHONE_LABEL_RE.search(block)
    if phone_match:
        contact.phone = re.sub(r"\s+", " ", phone_match.group(1)).strip()
    else:
        for line in lines:
            if re.search(r"^(\+64|0)\d", line.replace(" ", "")):
                contact.phone = line.strip()
                break

    for line in lines:
        council_match = _COUNCIL_LINE_RE.match(line)
        if council_match:
            contact.organization = council_match.group(1).strip()
            break

    if not contact.organization:
        org_match = _ORG_NAME_RE.search(block)
        if org_match and not _is_blocked_contact_name(org_match.group(1)):
            contact.organization = org_match.group(1).strip()

    for index, line in enumerate(lines):
        if contact.organization and line == contact.organization:
            if index >= 2:
                prev = lines[index - 1]
                prev2 = lines[index - 2]
                if _TITLE_LINE_RE.search(prev) and _PERSON_LINE_RE.match(prev2):
                    contact.person_name = prev2
                    contact.title = prev
                    break
            if index >= 1:
                prev = lines[index - 1]
                if _PERSON_LINE_RE.match(prev) and not _TITLE_LINE_RE.search(prev):
                    contact.person_name = prev
                    break
            break

    if not contact.person_name:
        for line in lines[:6]:
            if _PERSON_LINE_RE.match(line) and not _TITLE_LINE_RE.search(line):
                if not _COUNCIL_LINE_RE.match(line) and not _ORG_NAME_RE.match(line):
                    contact.person_name = line
                    break

    address_lines: list[str] = []
    for line in lines:
        lower = line.lower()
        if contact.organization and line == contact.organization:
            continue
        if _EMAIL_ANY_RE.search(line) or _PHONE_LABEL_RE.search(line):
            continue
        if lower.startswith(("phone", "email", "mobile", "tel")):
            continue
        if _STREET_HINT_RE.search(line) or lower.startswith("private bag") or lower.startswith("po box"):
            address_lines.append(line)
        elif _CITY_POSTAL_RE.match(line):
            address_lines.append(line)

    if address_lines:
        contact.address_line1 = address_lines[0]
        if len(address_lines) > 1:
            city_match = _CITY_POSTAL_RE.match(address_lines[-1])
            if city_match:
                contact.city = city_match.group(1).strip()
                contact.postal_code = city_match.group(2)
                if len(address_lines) > 2:
                    contact.address_line2 = address_lines[1]
            else:
                contact.address_line2 = address_lines[1]

    if not any((contact.organization, contact.email, contact.phone, contact.person_name)):
        return None
    if contact.organization and _is_blocked_contact_name(contact.organization):
        contact.organization = None
    if not any((contact.organization, contact.email, contact.phone, contact.person_name)):
        return None
    return contact


def extract_signature_contacts(body_text: str) -> list[SignatureContact]:
    if not body_text:
        return []
    contacts: list[SignatureContact] = []
    seen: set[tuple[str | None, str | None]] = set()

    blocks = _SIGNATURE_DELIM.split(body_text)
    for block in blocks:
        parsed = _parse_signature_block(block)
        if not parsed:
            continue
        key = (parsed.organization, parsed.email)
        if key in seen:
            continue
        seen.add(key)
        contacts.append(parsed)

    for forward_match in re.finditer(
        r"^From:\s*(?:\"([^\"\n]+)\"|'([^'\n]+)'|([^<\n]+?))?\s*(?:<([^>\n]+)>)?",
        body_text,
        re.IGNORECASE | re.MULTILINE,
    ):
        display = (forward_match.group(1) or forward_match.group(2) or forward_match.group(3) or "").strip()
        email = (forward_match.group(4) or "").strip().lower()
        if not email or _is_internal_email(email):
            continue
        contact = SignatureContact(email=email)
        if display and _PERSON_LINE_RE.match(display):
            contact.person_name = display
        elif display and not _TITLE_LINE_RE.search(display) and "@" not in display:
            contact.person_name = display
        start = forward_match.end()
        snippet = body_text[start : start + 800]
        org_match = _COUNCIL_LINE_RE.search(snippet)
        if org_match:
            contact.organization = org_match.group(1).strip()
        phone_match = _PHONE_LABEL_RE.search(snippet)
        if phone_match:
            contact.phone = re.sub(r"\s+", " ", phone_match.group(1)).strip()
        key = (contact.organization, contact.email)
        if key not in seen and any((contact.organization, contact.email, contact.person_name)):
            seen.add(key)
            contacts.append(contact)

    return contacts


def best_signature_contact(body_text: str) -> SignatureContact | None:
    candidates = extract_signature_contacts(body_text)
    if not candidates:
        return None

    def score(contact: SignatureContact) -> tuple[int, int]:
        points = 0
        if contact.organization:
            points += 4
        if contact.email and not _is_internal_email(contact.email):
            points += 3
        if contact.phone:
            points += 1
        if contact.person_name:
            points += 1
        if contact.organization and "council" in contact.organization.lower():
            points += 2
        return (points, len(contact.organization or ""))

    return max(candidates, key=score)

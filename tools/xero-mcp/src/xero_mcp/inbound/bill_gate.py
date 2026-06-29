from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from xero_mcp.inbound.xero_links import detect_xero_links


@dataclass(frozen=True)
class BillGateResult:
    is_bill: bool
    confidence: float
    reason: str
    method: str = "heuristic"


_BILL_KEYWORDS = frozenset({
    "invoice", "tax invoice", "bill", "statement", "amount due", "balance due",
    "payment due", "remittance", "purchase order", "credit note", "debit note",
    "gst", "subtotal", "invoice number", "invoice no", "inv-", "inv ",
})

_REJECT_SUBJECT = re.compile(
    r"\b(newsletter|unsubscribe|marketing|promotion|password reset|verify your email|"
    r"security alert|login attempt|social media|webinar|survey|special offer|"
    r"black friday|cyber monday|your order has shipped|tracking number|"
    r"receipt for your payment|payment received|thank you for your payment|"
    r"payment confirmation|auto.?reply|out of office)\b",
    re.IGNORECASE,
)

_REJECT_BODY = re.compile(
    r"\b(unsubscribe|view in browser|email preferences|manage subscriptions|"
    r"you(?:'re| are) receiving this (?:email|message) because|"
    r"payment (?:was|has been) (?:received|processed|successful)|"
    r"thank you for your payment|no action (?:is )?required)\b",
    re.IGNORECASE,
)

_BILL_SUBJECT = re.compile(
    r"\b(invoice|tax invoice|bill|statement|remittance|credit note|amount due|"
    r"payment due|overdue|outstanding)\b",
    re.IGNORECASE,
)

_INVOICE_NUMBER = re.compile(
    r"\b(?:invoice|inv(?:oice)?)\s*(?:no|#|number)?[:\s#-]*([A-Z0-9][A-Z0-9-]{2,})\b",
    re.IGNORECASE,
)

_AMOUNT = re.compile(
    r"(?:total|amount due|balance due|invoice total|grand total)[:\s]*\$?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)


def _haystack(*parts: str) -> str:
    return " ".join(p for p in parts if p).lower()


def _has_pdf_attachment(attachment_names: list[str]) -> bool:
    return any(name.lower().endswith(".pdf") for name in attachment_names)


def _sender_email(from_address: str) -> str:
    match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", from_address or "")
    return match.group(0).lower() if match else (from_address or "").strip().lower()


def _score_heuristic(
    *,
    subject: str,
    body_text: str,
    from_address: str,
    attachment_names: list[str],
    extracted_text: str = "",
    blocked_domains: tuple[str, ...] = (),
    trusted_forwarders: tuple[str, ...] = (),
) -> BillGateResult:
    hay = _haystack(subject, body_text, extracted_text)
    reasons: list[str] = []
    score = 0.0

    domain_match = re.search(r"@([\w.-]+)", from_address.lower())
    domain = domain_match.group(1) if domain_match else ""
    for blocked in blocked_domains:
        if blocked and blocked.lower() in domain:
            return BillGateResult(
                is_bill=False,
                confidence=0.95,
                reason=f"Sender domain blocked: {domain}",
                method="heuristic",
            )

    xero_links = detect_xero_links(hay)
    has_pdf = _has_pdf_attachment(attachment_names)
    has_bill_attachment = has_pdf or any(
        name.lower().endswith((".jpg", ".jpeg", ".png", ".heic")) for name in attachment_names
    )

    if _REJECT_SUBJECT.search(subject):
        score -= 0.55
        reasons.append("subject looks like marketing/notification")
    if _REJECT_BODY.search(body_text):
        score -= 0.45
        reasons.append("body looks like marketing or payment confirmation")

    if xero_links:
        score += 0.65
        reasons.append(f"Xero bill link ({xero_links[0].kind})")
    if _BILL_SUBJECT.search(subject):
        score += 0.35
        reasons.append("bill keywords in subject")
    if has_pdf:
        score += 0.25
        reasons.append("PDF attachment")
    elif has_bill_attachment:
        score += 0.15
        reasons.append("image attachment")

    sender = _sender_email(from_address)
    if trusted_forwarders and sender in trusted_forwarders:
        if has_pdf or has_bill_attachment:
            score += 0.35
            reasons.append("trusted forwarder with bill attachment")
        elif re.match(r"^\s*(?:fw|fwd)\s*:", subject, re.IGNORECASE):
            score += 0.2
            reasons.append("trusted forwarder forward")

    keyword_hits = sum(1 for kw in _BILL_KEYWORDS if kw in hay)
    if keyword_hits:
        score += min(0.35, keyword_hits * 0.08)
        reasons.append(f"{keyword_hits} bill keyword(s) in content")

    if _INVOICE_NUMBER.search(hay):
        score += 0.12
        reasons.append("invoice number pattern")
    if _AMOUNT.search(hay):
        score += 0.12
        reasons.append("amount due pattern")

    if not has_bill_attachment and not xero_links:
        score -= 0.35
        reasons.append("no bill attachment or Xero link")

    if "invoice" in hay or "tax invoice" in hay:
        score += 0.08

    confidence = max(0.0, min(1.0, 0.45 + score))
    is_bill = confidence >= 0.55 and score > 0.0

    if not reasons:
        reasons.append("insufficient bill signals")

    return BillGateResult(
        is_bill=is_bill,
        confidence=round(confidence, 3),
        reason="; ".join(reasons),
        method="heuristic",
    )


def _classify_with_openai(
    *,
    subject: str,
    body_text: str,
    from_address: str,
    attachment_names: list[str],
    extracted_text: str,
) -> BillGateResult | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        import httpx
    except ImportError:
        return None

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    prompt = {
        "subject": subject,
        "from": from_address,
        "attachments": attachment_names,
        "body_excerpt": body_text[:2000],
        "pdf_excerpt": extracted_text[:2000],
    }
    system = (
        "Decide if an inbound email is a supplier bill/invoice that should become a Xero ACCPAY draft. "
        "Reject newsletters, marketing, personal mail, payment confirmations (money already paid), "
        "shipping notices, and auto-replies. Accept tax invoices, bills, statements with amount due, "
        "and emails with Xero bill/invoice links. "
        'Reply JSON only: {"is_bill": bool, "confidence": number, "reason": string}.'
    )
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                json={
                    "model": model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(prompt)},
                    ],
                },
            )
            resp.raise_for_status()
            parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
    except Exception:
        return None

    return BillGateResult(
        is_bill=bool(parsed.get("is_bill")),
        confidence=float(parsed.get("confidence") or 0.5),
        reason=str(parsed.get("reason") or "LLM classification")[:500],
        method="llm",
    )


def is_actionable_bill(
    *,
    subject: str,
    body_text: str,
    from_address: str = "",
    attachment_names: list[str] | None = None,
    extracted_text: str = "",
    classifier_mode: str = "heuristic",
    min_confidence: float = 0.55,
    blocked_domains: tuple[str, ...] = (),
    trusted_forwarders: tuple[str, ...] = (),
) -> BillGateResult:
    names = attachment_names or []
    heuristic = _score_heuristic(
        subject=subject,
        body_text=body_text,
        from_address=from_address,
        attachment_names=names,
        extracted_text=extracted_text,
        blocked_domains=blocked_domains,
        trusted_forwarders=trusted_forwarders,
    )

    mode = (classifier_mode or "heuristic").lower()
    llm: BillGateResult | None = None
    if mode in ("llm", "hybrid"):
        llm = _classify_with_openai(
            subject=subject,
            body_text=body_text,
            from_address=from_address,
            attachment_names=names,
            extracted_text=extracted_text,
        )

    if mode == "llm" and llm:
        result = llm
    elif mode == "hybrid" and llm:
        combined_conf = (heuristic.confidence + llm.confidence) / 2
        is_bill = heuristic.is_bill or llm.is_bill
        if heuristic.is_bill != llm.is_bill:
            combined_conf *= 0.85
        result = BillGateResult(
            is_bill=is_bill,
            confidence=round(combined_conf, 3),
            reason=f"heuristic: {heuristic.reason}; llm: {llm.reason}",
            method="hybrid",
        )
    else:
        result = heuristic

    if result.confidence < min_confidence:
        return BillGateResult(
            is_bill=False,
            confidence=result.confidence,
            reason=f"Below min confidence ({min_confidence}): {result.reason}",
            method=result.method,
        )
    return result

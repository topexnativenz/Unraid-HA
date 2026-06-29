from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xero_mcp.config import DEFAULT_CONFIG_DIR

PORTFOLIO_ENTITIES_FILE = DEFAULT_CONFIG_DIR / "portfolio.entities.json"
PORTFOLIO_EXAMPLE = Path(__file__).resolve().parents[3] / "portfolio.entities.example.json"

_STREET_SUFFIXES = frozenset({
    "place", "pl", "road", "rd", "drive", "dr", "avenue", "ave",
    "street", "st", "lane", "ln", "way", "court", "ct",
    "crescent", "cres", "highway", "hwy", "terrace", "tce",
    "parade", "pde", "close", "mews", "square", "sq", "rise",
    "grove", "park", "view",
})


@dataclass(frozen=True)
class ClassificationResult:
    org_slug: str
    method: str
    confidence: float
    matched_property: str | None = None
    matched_keyword: str | None = None
    notes: str | None = None


def _distinctive_token(query: str) -> str | None:
    q = query.lower().strip()
    tokens = [t for t in q.split() if len(t) >= 3 and t not in _STREET_SUFFIXES]
    if tokens and tokens[0] != q:
        return tokens[0]
    return None


def _text_haystack(*parts: str) -> str:
    return " ".join(p.lower() for p in parts if p).strip()


def _keyword_in_hay(keyword: str, hay: str) -> bool:
    k = keyword.lower().strip()
    if not k or len(k) < 3:
        return False
    if k in hay:
        return True
    token = _distinctive_token(k)
    return bool(token and token in hay)


def load_portfolio_entities() -> dict[str, Any]:
    path = Path(os.environ.get("XERO_PORTFOLIO_ENTITIES_FILE", PORTFOLIO_ENTITIES_FILE))
    if not path.exists():
        if PORTFOLIO_EXAMPLE.exists():
            return json.loads(PORTFOLIO_EXAMPLE.read_text())
        return {"default_org_slug": "matariki-property-group", "properties": [], "org_hints": []}
    return json.loads(path.read_text())


def classify_inbound_email(
    *,
    subject: str,
    body_text: str,
    from_address: str = "",
    to_address: str = "",
) -> ClassificationResult:
    data = load_portfolio_entities()
    default_slug = data.get("default_org_slug") or "matariki-property-group"
    hay = _text_haystack(subject, body_text, from_address)

    best_prop: dict[str, Any] | None = None
    best_kw: str | None = None
    best_len = 0

    for prop in data.get("properties") or []:
        org_slug = prop.get("org_slug") or default_slug
        keywords: list[str] = list(prop.get("keywords") or [])
        for field in ("nickname", "address", "suburb", "city"):
            val = prop.get(field)
            if val:
                keywords.append(str(val))
        for keyword in keywords:
            if _keyword_in_hay(keyword, hay) and len(keyword) > best_len:
                best_len = len(keyword)
                best_kw = keyword
                best_prop = {**prop, "_org_slug": org_slug}

    if best_prop and best_kw:
        label = best_prop.get("nickname") or best_prop.get("address") or best_kw
        return ClassificationResult(
            org_slug=best_prop["_org_slug"],
            method="portfolio_property",
            confidence=0.92 if best_len >= 8 else 0.78,
            matched_property=str(label),
            matched_keyword=best_kw,
        )

    best_hint: dict[str, Any] | None = None
    best_hint_len = 0
    for hint in data.get("org_hints") or []:
        slug = hint.get("org_slug")
        if not slug:
            continue
        for keyword in hint.get("keywords") or []:
            if _keyword_in_hay(str(keyword), hay) and len(str(keyword)) > best_hint_len:
                best_hint_len = len(str(keyword))
                best_hint = hint

    if best_hint:
        return ClassificationResult(
            org_slug=str(best_hint["org_slug"]),
            method="org_hint",
            confidence=0.7,
            matched_keyword=str(best_hint.get("keywords", [""])[0]),
            notes=best_hint.get("label"),
        )

    mode = (data.get("classifier_mode") or "keyword").lower()
    if mode in ("llm", "hybrid") and os.environ.get("OPENAI_API_KEY"):
        llm = _classify_with_openai(hay=hay, subject=subject, data=data, default_slug=default_slug)
        if llm:
            return llm

    return ClassificationResult(
        org_slug=default_slug,
        method="default",
        confidence=0.35,
        notes="No property or org keyword match — review org in Xero",
    )


def _classify_with_openai(
    *,
    hay: str,
    subject: str,
    data: dict[str, Any],
    default_slug: str,
) -> ClassificationResult | None:
    try:
        import httpx
    except ImportError:
        return None

    orgs = data.get("org_hints") or []
    props = data.get("properties") or []
    prompt = {
        "subject": subject,
        "text_excerpt": hay[:4000],
        "organisations": [
            {"slug": h.get("org_slug"), "label": h.get("label"), "keywords": h.get("keywords")}
            for h in orgs
        ],
        "properties_sample": [
            {
                "nickname": p.get("nickname"),
                "address": p.get("address"),
                "org_slug": p.get("org_slug", default_slug),
            }
            for p in props[:40]
        ],
        "default_org_slug": default_slug,
        "valid_slugs": list(
            {
                h.get("org_slug")
                for h in orgs
                if h.get("org_slug")
            }
            | {p.get("org_slug", default_slug) for p in props}
            | {default_slug}
        ),
    }

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.environ["OPENAI_API_KEY"]
    system = (
        "You route supplier bills to the correct Xero organisation for a NZ property group. "
        "Reply with JSON only: {\"org_slug\": string, \"reason\": string, \"confidence\": number}. "
        "Pick exactly one slug from valid_slugs."
    )
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
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
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
    except Exception:
        return None

    slug = str(parsed.get("org_slug") or default_slug)
    valid = set(prompt["valid_slugs"])
    if slug not in valid:
        slug = default_slug
    return ClassificationResult(
        org_slug=slug,
        method="llm",
        confidence=float(parsed.get("confidence") or 0.6),
        notes=str(parsed.get("reason") or "")[:500],
    )

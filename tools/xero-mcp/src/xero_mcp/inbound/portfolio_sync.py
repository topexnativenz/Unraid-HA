from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from xero_mcp.config import DEFAULT_CONFIG_DIR, ensure_config_dir
from xero_mcp.inbound.classifier import PORTFOLIO_ENTITIES_FILE, PORTFOLIO_EXAMPLE

NOTIFIED_API_BASE = os.environ.get("NOTIFIED_API_BASE", "https://api.notified.co.nz").rstrip("/")

_DEFAULT_ORG_HINTS = [
    {
        "org_slug": "matariki-property-group",
        "label": "Matariki Property Group",
        "keywords": ["property group", "matariki property", "mpg", "rental", "tenancy"],
    },
    {
        "org_slug": "matariki-traders",
        "label": "Matariki Traders",
        "keywords": ["traders", "matariki traders", "retail", "shop", "store"],
    },
    {
        "org_slug": "matariki-morningside-development",
        "label": "Matariki Morningside Development",
        "keywords": ["morningside", "development", "msn", "construction", "build"],
    },
]


def _keywords_for_property(prop: dict[str, Any]) -> list[str]:
    keywords: list[str] = []
    for field in ("nickname", "address", "suburb", "city"):
        val = prop.get(field)
        if not val:
            continue
        text = str(val).strip()
        keywords.append(text)
        token = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        for part in token.split():
            if len(part) >= 4 and part not in keywords:
                keywords.append(part)
    return keywords


def _fetch_portfolio_properties(jwt: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {jwt}", "Accept": "application/json"}
    with httpx.Client(timeout=60.0, base_url=NOTIFIED_API_BASE) as client:
        resp = client.get("/portfolio/properties", headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("properties") or data.get("results") or []
    return []


def build_portfolio_entities(
    properties: list[dict[str, Any]],
    *,
    default_org_slug: str = "matariki-property-group",
) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    for prop in properties:
        prop_id = prop.get("id") or prop.get("property_id")
        org_slug = prop.get("xero_org_slug") or default_org_slug
        entities.append(
            {
                "id": prop_id,
                "nickname": prop.get("nickname"),
                "address": prop.get("address"),
                "suburb": prop.get("suburb"),
                "city": prop.get("city"),
                "org_slug": org_slug,
                "keywords": _keywords_for_property(prop),
            }
        )
    return {
        "version": 1,
        "synced_from": "notified",
        "default_org_slug": default_org_slug,
        "classifier_mode": "hybrid",
        "org_hints": _DEFAULT_ORG_HINTS,
        "properties": entities,
    }


def sync_portfolio_from_notified(
    *,
    jwt: str | None = None,
    output: Path | None = None,
    default_org_slug: str = "matariki-property-group",
) -> Path:
    token = jwt or os.environ.get("NOTIFIED_SERVICE_JWT") or os.environ.get("NOTIFIED_JWT")
    if not token:
        raise RuntimeError(
            "Set NOTIFIED_SERVICE_JWT (or pass --jwt) to sync portfolio from Notified API"
        )
    properties = _fetch_portfolio_properties(token)
    payload = build_portfolio_entities(properties, default_org_slug=default_org_slug)
    ensure_config_dir()
    dest = output or PORTFOLIO_ENTITIES_FILE
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    dest.chmod(0o600)
    return dest


def init_portfolio_entities() -> Path:
    ensure_config_dir()
    if PORTFOLIO_ENTITIES_FILE.exists():
        return PORTFOLIO_ENTITIES_FILE
    template = json.loads(PORTFOLIO_EXAMPLE.read_text())
    PORTFOLIO_ENTITIES_FILE.write_text(json.dumps(template, indent=2) + "\n")
    PORTFOLIO_ENTITIES_FILE.chmod(0o600)
    return PORTFOLIO_ENTITIES_FILE

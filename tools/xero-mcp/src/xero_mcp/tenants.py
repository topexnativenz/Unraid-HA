from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xero_mcp.audit import audit_event
from xero_mcp.config import DEFAULT_CONFIG_DIR, ensure_config_dir, load_token_store

ACTIVE_ORG_FILE = DEFAULT_CONFIG_DIR / "active-org.json"
ORGS_REGISTRY_FILE = DEFAULT_CONFIG_DIR / "orgs.json"
ORGS_CONFIG_FILE = DEFAULT_CONFIG_DIR / "orgs.config.json"
ORGS_CONFIG_EXAMPLE = Path(__file__).resolve().parents[2] / "xero.orgs.example.json"


class TenantError(RuntimeError):
    pass


@dataclass(frozen=True)
class Organisation:
    slug: str
    tenant_id: str
    tenant_name: str
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant_name,
            "label": self.label,
        }


def slugify_org_name(name: str) -> str:
    text = name.lower()
    text = re.sub(r"\blimited\b", "", text)
    text = re.sub(r"\bcompany\b", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-+", "-", text)
    return text or "org"


def _load_org_config() -> dict[str, Any]:
    if ORGS_CONFIG_FILE.exists():
        return json.loads(ORGS_CONFIG_FILE.read_text())
    if ORGS_CONFIG_EXAMPLE.exists():
        return json.loads(ORGS_CONFIG_EXAMPLE.read_text())
    return {}


def _org_config_entry(
    tenant_id: str, base_slug: str, labels: dict[str, Any]
) -> dict[str, Any]:
    for key in (tenant_id, base_slug):
        cfg = labels.get(key)
        if isinstance(cfg, dict):
            return cfg
    return {}


def _allocate_slug(base_slug: str, used_slugs: dict[str, int]) -> str:
    count = used_slugs.get(base_slug, 0)
    used_slugs[base_slug] = count + 1
    return base_slug if count == 0 else f"{base_slug}-{count + 1}"


def sync_org_registry() -> list[Organisation]:
    """Build slug registry from OAuth connections + optional labels config."""
    ensure_config_dir()
    store = load_token_store()
    connections = store.get("connections") or []
    if not connections:
        raise TenantError("No Xero organisations connected — run: python -m xero_mcp login")

    config = _load_org_config()
    labels: dict[str, Any] = config.get("organisations") or {}
    used_slugs: dict[str, int] = {}
    orgs: list[Organisation] = []

    for conn in connections:
        tenant_id = conn.get("tenantId") or ""
        tenant_name = conn.get("tenantName") or tenant_id
        base_slug = slugify_org_name(tenant_name)
        cfg = _org_config_entry(tenant_id, base_slug, labels)
        if cfg.get("exclude"):
            continue

        slug = cfg.get("slug") or _allocate_slug(base_slug, used_slugs)
        if slug != base_slug:
            used_slugs[base_slug] = used_slugs.get(base_slug, 0) + 1
        label = cfg.get("label")
        orgs.append(
            Organisation(
                slug=slug,
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                label=label,
            )
        )

    payload = {
        "synced_at": time.time(),
        "organisations": [o.to_dict() for o in orgs],
    }
    ORGS_REGISTRY_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    ORGS_REGISTRY_FILE.chmod(0o600)
    return orgs


def list_organisations(*, refresh: bool = False) -> list[Organisation]:
    if refresh or not ORGS_REGISTRY_FILE.exists():
        return sync_org_registry()
    data = json.loads(ORGS_REGISTRY_FILE.read_text())
    return [Organisation(**item) for item in data.get("organisations") or []]


def _resolve_org(query: str, orgs: list[Organisation]) -> Organisation:
    q = query.strip().lower()
    if not q:
        raise TenantError("Organisation query is empty.")

    for org in orgs:
        if q in {org.slug, org.tenant_id.lower(), org.tenant_name.lower()}:
            return org

    matches = [
        org
        for org in orgs
        if q in org.slug
        or q in org.tenant_name.lower()
        or (org.label and q in org.label.lower())
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(o.slug for o in matches)
        raise TenantError(f"Ambiguous organisation '{query}'. Matches: {names}")

    raise TenantError(
        f"Unknown organisation '{query}'. "
        f"Available: {', '.join(o.slug for o in orgs)}"
    )


def get_active_organisation() -> Organisation | None:
    if not ACTIVE_ORG_FILE.exists():
        return None
    data = json.loads(ACTIVE_ORG_FILE.read_text())
    if not data.get("tenant_id"):
        return None
    return Organisation(
        slug=data.get("slug") or "",
        tenant_id=data["tenant_id"],
        tenant_name=data.get("tenant_name") or data["tenant_id"],
        label=data.get("label"),
    )


def set_active_organisation(query: str) -> Organisation:
    orgs = list_organisations(refresh=True)
    org = _resolve_org(query, orgs)
    payload = {
        **org.to_dict(),
        "set_at": time.time(),
    }
    ensure_config_dir()
    ACTIVE_ORG_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    ACTIVE_ORG_FILE.chmod(0o600)
    audit_event("org_switched", slug=org.slug, tenant_name=org.tenant_name)
    return org


def ensure_default_active_org() -> Organisation | None:
    active = get_active_organisation()
    if active:
        orgs = list_organisations()
        if any(o.tenant_id == active.tenant_id for o in orgs):
            return active

    orgs = list_organisations(refresh=True)
    if not orgs:
        return None

    config = _load_org_config()
    default_slug = config.get("default_slug")
    if default_slug:
        try:
            return set_active_organisation(default_slug)
        except TenantError:
            return None

    return set_active_organisation(orgs[0].slug)


def active_org_summary() -> dict[str, Any]:
    orgs = list_organisations()
    active = get_active_organisation()
    return {
        "active": active.to_dict() if active else None,
        "organisations": [o.to_dict() for o in orgs],
        "hint": "Call set_active_organisation before Xero accounting tools when working with a specific company.",
    }

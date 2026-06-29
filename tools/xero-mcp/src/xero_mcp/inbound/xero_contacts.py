from __future__ import annotations

import re
from typing import Any

import httpx

from xero_mcp.auth import ensure_access_token
from xero_mcp.inbound.config import InboundError
from xero_mcp.inbound.extract import (
    ExtractedFields,
    _is_blocked_contact_name,
    _is_collection_agent_name,
    _is_internal_email,
    _is_plausible_supplier_name,
)
from xero_mcp.inbound.xero_http import xero_request
from xero_mcp.tenants import list_organisations

XERO_API = "https://api.xero.com/api.xro/2.0"

_NAME_SUFFIXES = (
    " limited",
    " ltd.",
    " ltd",
    " inc.",
    " inc",
    " co.",
    " co",
    " nz",
    " plc",
)


def _contact_name_matches_supplier(matched_name: str, search_name: str | None) -> bool:
    if not search_name or not _is_plausible_supplier_name(search_name):
        return True
    matched_norm = normalize_contact_name(matched_name)
    search_norm = normalize_contact_name(search_name)
    if matched_norm == search_norm:
        return True
    if search_norm in matched_norm or matched_norm in search_norm:
        return True
    matched_lower = matched_name.lower()
    search_lower = search_name.lower()
    if "gst number" in matched_lower and search_lower != matched_lower:
        return False
    search_tokens = set(search_norm.split())
    matched_tokens = set(matched_norm.split())
    if len(search_tokens & matched_tokens) >= 2:
        return True
    if "building" in search_norm and "fire" in search_norm:
        return "building" in matched_norm or "fire" in matched_norm
    return False


def normalize_contact_name(name: str) -> str:
    normalized = name.lower().strip()
    for suffix in _NAME_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _tenant_id_for_slug(org_slug: str) -> str:
    for org in list_organisations():
        if org.slug == org_slug:
            return org.tenant_id
    raise InboundError(f"Unknown org slug: {org_slug}")


def _api_headers(org_slug: str) -> tuple[str, dict[str, str]]:
    access_token = ensure_access_token()
    tenant_id = _tenant_id_for_slug(org_slug)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }
    return tenant_id, headers


def _escape_odata(value: str) -> str:
    return value.replace("'", "''")


def _list_contacts(
    org_slug: str,
    *,
    where: str | None = None,
    search_term: str | None = None,
) -> list[dict[str, Any]]:
    _, headers = _api_headers(org_slug)
    params: dict[str, str] = {}
    if where:
        params["where"] = where
    if search_term:
        params["searchTerm"] = search_term
    with httpx.Client(timeout=30.0) as client:
        resp = xero_request(client, "GET", f"{XERO_API}/Contacts", headers=headers, params=params)
        if resp.status_code >= 400:
            raise InboundError(f"Xero contacts list failed ({resp.status_code}): {resp.text}")
        return list(resp.json().get("Contacts") or [])


def find_contact(
    *,
    org_slug: str,
    email: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    if email:
        safe_email = _escape_odata(email.strip().lower())
        matches = _list_contacts(org_slug, where=f'EmailAddress=="{safe_email}"')
        if matches:
            return matches[0]

    if name:
        matches = _list_contacts(org_slug, search_term=name.strip())
        target = normalize_contact_name(name)
        target_lower = name.strip().lower()
        for contact in matches:
            contact_name = str(contact.get("Name") or "")
            contact_lower = contact_name.lower()
            if normalize_contact_name(contact_name) == target:
                return contact
            if contact_lower == target_lower:
                return contact
            if (
                target_lower.startswith(contact_lower)
                and len(target_lower) - len(contact_lower) <= 4
                and contact_lower != target_lower
            ):
                continue
        if len(matches) == 1:
            only = matches[0]
            only_name = str(only.get("Name") or "")
            if only_name.lower() == target_lower or normalize_contact_name(only_name) == target:
                return only
    return None


def _contact_payload(fields: ExtractedFields) -> dict[str, Any]:
    name = (fields.supplier_name or "Imported Supplier")[:255]
    payload: dict[str, Any] = {"Name": name}
    if fields.contact_email:
        payload["EmailAddress"] = fields.contact_email[:255]
    if fields.phone:
        payload["Phones"] = [{"PhoneType": "DEFAULT", "PhoneNumber": fields.phone[:50]}]
    address_lines = [fields.address_line1, fields.address_line2]
    address_lines = [line for line in address_lines if line]
    if address_lines or fields.city or fields.postal_code or fields.region:
        payload["Addresses"] = [
            {
                "AddressType": "POBOX",
                "AddressLine1": (fields.address_line1 or "")[:500] or None,
                "AddressLine2": (fields.address_line2 or "")[:500] or None,
                "City": (fields.city or "")[:255] or None,
                "Region": (fields.region or "")[:255] or None,
                "PostalCode": (fields.postal_code or "")[:50] or None,
            }
        ]
        payload["Addresses"][0] = {
            k: v for k, v in payload["Addresses"][0].items() if v is not None
        }
    return payload


def create_contact(*, org_slug: str, fields: ExtractedFields) -> dict[str, Any]:
    _, headers = _api_headers(org_slug)
    headers["Content-Type"] = "application/json"
    body = {"Contacts": [_contact_payload(fields)]}
    with httpx.Client(timeout=30.0) as client:
        resp = xero_request(client, "POST", f"{XERO_API}/Contacts", headers=headers, json=body)
        if resp.status_code >= 400:
            raise InboundError(f"Xero create contact failed ({resp.status_code}): {resp.text}")
        contact = (resp.json().get("Contacts") or [{}])[0]
        if not contact.get("ContactID"):
            raise InboundError(f"Xero did not return ContactID: {resp.text}")
        return contact


def ensure_contact(*, org_slug: str, fields: ExtractedFields) -> dict[str, Any]:
    """Find existing supplier contact by email or normalized name, else create."""
    search_email = fields.contact_email
    if _is_internal_email(search_email):
        search_email = fields.supplier_email if not _is_internal_email(fields.supplier_email) else None
    search_name = fields.supplier_name
    if not _is_plausible_supplier_name(search_name):
        search_name = None

    existing = find_contact(
        org_slug=org_slug,
        email=search_email,
        name=search_name,
    )
    if existing:
        matched_name = str(existing.get("Name") or "")
        if _is_collection_agent_name(matched_name) and _is_plausible_supplier_name(search_name):
            existing = None
        elif not _contact_name_matches_supplier(matched_name, search_name):
            existing = None
    if not existing and search_name:
        existing = find_contact(org_slug=org_slug, email=None, name=search_name)
    if existing:
        return {
            "contact_id": existing.get("ContactID"),
            "name": existing.get("Name"),
            "email": existing.get("EmailAddress") or fields.contact_email,
            "created": False,
            "match": "email" if fields.contact_email and existing.get("EmailAddress") else "name",
        }

    created = create_contact(org_slug=org_slug, fields=fields)
    return {
        "contact_id": created.get("ContactID"),
        "name": created.get("Name"),
        "email": created.get("EmailAddress") or fields.contact_email,
        "created": True,
        "match": "created",
    }


def contact_summary(fields: ExtractedFields) -> dict[str, Any]:
    return {
        "supplier_name": fields.supplier_name,
        "sender_email": fields.sender_email,
        "supplier_email": fields.supplier_email,
        "contact_email": fields.contact_email,
        "phone": fields.phone,
        "address_line1": fields.address_line1,
        "address_line2": fields.address_line2,
        "city": fields.city,
        "postal_code": fields.postal_code,
        "region": fields.region,
    }

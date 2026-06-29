from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import httpx

from xero_mcp.config import (
    AUTHORIZE_URL,
    CONNECTIONS_URL,
    TOKEN_URL,
    Credentials,
    load_credentials,
    load_token_store,
    save_token_store,
)
from xero_mcp.audit import audit_event


class AuthError(RuntimeError):
    pass


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float
    token_type: str = "Bearer"
    scope: str | None = None

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> TokenSet:
        expires_in = float(payload.get("expires_in", 1800))
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=time.time() + expires_in - 60,
            token_type=payload.get("token_type", "Bearer"),
            scope=payload.get("scope"),
        )

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    def to_store(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "scope": self.scope,
        }

    @classmethod
    def from_store(cls, data: dict[str, Any]) -> TokenSet:
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=float(data["expires_at"]),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


def _parse_callback_query(path: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(path)
    return {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}


def _exchange_code(creds: Credentials, code: str, code_verifier: str) -> TokenSet:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": creds.redirect_uri,
        "client_id": creds.client_id,
        "code_verifier": code_verifier,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=(creds.client_id, creds.client_secret),
        )
    if resp.status_code >= 400:
        audit_event("token_exchange_failed", status=resp.status_code)
        raise AuthError(f"Token exchange failed ({resp.status_code}): {resp.text}")
    audit_event("login_success")
    return TokenSet.from_response(resp.json())


def _refresh_access_token(creds: Credentials, refresh_token: str) -> TokenSet:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": creds.client_id,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=(creds.client_id, creds.client_secret),
        )
    if resp.status_code >= 400:
        audit_event("token_refresh_failed", status=resp.status_code)
        raise AuthError(f"Token refresh failed ({resp.status_code}): {resp.text}")
    refreshed = TokenSet.from_response(resp.json())
    if not refreshed.refresh_token:
        refreshed = TokenSet(
            access_token=refreshed.access_token,
            refresh_token=refresh_token,
            expires_at=refreshed.expires_at,
            token_type=refreshed.token_type,
            scope=refreshed.scope,
        )
    return refreshed


def fetch_connections(access_token: str) -> list[dict[str, Any]]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            CONNECTIONS_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
    if resp.status_code >= 400:
        raise AuthError(f"Connections fetch failed ({resp.status_code}): {resp.text}")
    return resp.json()


def login_interactive(open_browser: bool = True) -> dict[str, Any]:
    creds = load_credentials()
    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = _pkce_pair()

    params = {
        "response_type": "code",
        "client_id": creds.client_id,
        "redirect_uri": creds.redirect_uri,
        "scope": creds.scope_string,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    parsed = urllib.parse.urlparse(creds.redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8765
    callback_path = parsed.path or "/callback"

    result: dict[str, str | None] = {"code": None, "error": None, "state": None}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            query = _parse_callback_query(self.path)
            if not self.path.startswith(callback_path):
                self.send_response(404)
                self.end_headers()
                return
            result["code"] = query.get("code")
            result["error"] = query.get("error")
            result["state"] = query.get("state")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if result["error"]:
                body = f"<h1>Xero auth failed</h1><p>{result['error']}</p>"
            else:
                body = "<h1>Xero connected</h1><p>You can close this tab and return to Cursor.</p>"
            self.wfile.write(body.encode())

    bind_host = "127.0.0.1"
    try:
        server = HTTPServer((bind_host, port), CallbackHandler)
    except OSError as exc:
        raise AuthError(
            f"Could not bind {bind_host}:{port} for OAuth callback ({exc}). "
            "Stop any process using that port and retry."
        ) from exc

    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print(f"Open this URL if the browser does not launch:\n{auth_url}\n")
    if open_browser:
        webbrowser.open(auth_url)

    thread.join(timeout=300)
    server.server_close()

    if result["error"]:
        raise AuthError(f"OAuth error: {result['error']}")
    if result["state"] != state:
        raise AuthError("OAuth state mismatch — possible CSRF; try again.")
    if not result["code"]:
        raise AuthError("Timed out waiting for OAuth callback (5 minutes).")

    token_set = _exchange_code(creds, str(result["code"]), code_verifier)
    connections = fetch_connections(token_set.access_token)

    store = {
        "token": token_set.to_store(),
        "connections": connections,
        "updated_at": time.time(),
    }
    save_token_store(store)
    audit_event(
        "oauth_complete",
        organisations=len(connections),
        org_names=[c.get("tenantName") for c in connections],
    )
    try:
        from xero_mcp.tenants import ensure_default_active_org, sync_org_registry

        sync_org_registry()
        ensure_default_active_org()
    except Exception:
        pass
    return store


def ensure_access_token() -> str:
    creds = load_credentials()
    store = load_token_store()
    token_data = store.get("token")
    if not token_data:
        raise AuthError(
            "No Xero tokens stored. Run: "
            f"cd /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp && "
            "source .venv/bin/activate && python -m xero_mcp login"
        )

    token_set = TokenSet.from_store(token_data)
    if not token_set.is_expired():
        return token_set.access_token

    if not token_set.refresh_token:
        raise AuthError("Access token expired and no refresh token — run login again.")

    refreshed = _refresh_access_token(creds, token_set.refresh_token)
    store["token"] = refreshed.to_store()
    store["updated_at"] = time.time()
    save_token_store(store)
    audit_event("token_refresh_ok")
    return refreshed.access_token


def status() -> dict[str, Any]:
    creds = load_credentials()
    store = load_token_store()
    token_data = store.get("token")
    connections = store.get("connections") or []

    info: dict[str, Any] = {
        "app_name": creds.app_name,
        "client_id_prefix": creds.client_id[:8] + "…",
        "secret_storage": "keychain",
        "redirect_uri": creds.redirect_uri,
        "scopes": creds.scopes,
        "authenticated": bool(token_data),
        "connections_count": len(connections),
        "connections": [
            {
                "tenant_id": c.get("tenantId"),
                "tenant_name": c.get("tenantName"),
                "tenant_type": c.get("tenantType"),
            }
            for c in connections
        ],
    }
    if token_data:
        token_set = TokenSet.from_store(token_data)
        info["token_expires_in_seconds"] = max(0, int(token_set.expires_at - time.time()))
        info["token_expired"] = token_set.is_expired()
    return info

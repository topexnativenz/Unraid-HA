from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_APP_NAME = "Cursor MCP (Mac)"

DEFAULT_CONFIG_DIR = Path(
    os.environ.get("XERO_MCP_CONFIG_DIR", Path.home() / ".config" / "xero-mcp")
)
CREDENTIALS_FILE = DEFAULT_CONFIG_DIR / "credentials.json"
TOKENS_FILE = DEFAULT_CONFIG_DIR / "connections.json"
HEALTH_FILE = DEFAULT_CONFIG_DIR / "health.json"
AUDIT_LOG_FILE = DEFAULT_CONFIG_DIR / "audit.log"

AUTHORIZE_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"


@dataclass(frozen=True)
class Credentials:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]
    app_name: str = DEFAULT_APP_NAME

    @property
    def scope_string(self) -> str:
        return " ".join(self.scopes)


def ensure_config_dir() -> Path:
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        DEFAULT_CONFIG_DIR.chmod(0o700)
    except OSError:
        pass
    return DEFAULT_CONFIG_DIR


def _load_client_secret_from_store(data: dict[str, Any]) -> str:
    from xero_mcp.keychain import KeychainError, load_client_secret

    storage = data.get("secret_storage", "keychain")
    if storage == "keychain":
        return load_client_secret()
    if "client_secret" in data:
        return str(data["client_secret"])
    raise KeychainError(
        "No client secret in Keychain and credentials.json has no fallback secret."
    )


def load_credentials() -> Credentials:
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Missing {CREDENTIALS_FILE}. Run: python -m xero_mcp init --client-id ... --client-secret ..."
        )
    data = json.loads(CREDENTIALS_FILE.read_text())
    if "client_secret" in data and data.get("secret_storage") != "file":
        _migrate_plaintext_secret_to_keychain(data)
        data = json.loads(CREDENTIALS_FILE.read_text())
    scopes = data.get("scopes") or []
    if isinstance(scopes, str):
        scopes = scopes.split()
    secret = _load_client_secret_from_store(data)
    return Credentials(
        client_id=data["client_id"],
        client_secret=secret,
        redirect_uri=data.get("redirect_uri", "http://localhost:8765/callback"),
        scopes=scopes,
        app_name=data.get("app_name", DEFAULT_APP_NAME),
    )


def save_credentials(creds: Credentials, *, use_keychain: bool = True) -> None:
    from xero_mcp.keychain import KeychainError, store_client_secret

    ensure_config_dir()
    secret_storage = "keychain"
    if use_keychain:
        try:
            store_client_secret(creds.client_secret)
        except KeychainError:
            secret_storage = "file"
    payload: dict[str, Any] = {
        "app_name": creds.app_name,
        "client_id": creds.client_id,
        "redirect_uri": creds.redirect_uri,
        "scopes": creds.scopes,
        "secret_storage": secret_storage,
        "created_at": time.time(),
    }
    if secret_storage == "file":
        payload["client_secret"] = creds.client_secret
    CREDENTIALS_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    CREDENTIALS_FILE.chmod(0o600)


def _migrate_plaintext_secret_to_keychain(data: dict[str, Any]) -> None:
    """One-time upgrade: move legacy plaintext secret into Keychain."""
    if data.get("secret_storage") == "keychain" or "client_secret" not in data:
        return
    from xero_mcp.keychain import KeychainError, store_client_secret

    try:
        store_client_secret(str(data["client_secret"]))
    except KeychainError:
        return
    payload = dict(data)
    payload.pop("client_secret", None)
    payload["secret_storage"] = "keychain"
    CREDENTIALS_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    CREDENTIALS_FILE.chmod(0o600)


def load_token_store() -> dict[str, Any]:
    if not TOKENS_FILE.exists():
        return {}
    return json.loads(TOKENS_FILE.read_text())


def save_token_store(data: dict[str, Any]) -> None:
    ensure_config_dir()
    TOKENS_FILE.write_text(json.dumps(data, indent=2) + "\n")
    TOKENS_FILE.chmod(0o600)

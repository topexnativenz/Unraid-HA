from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SERVICE = "xero-mcp-client-secret"
ACCOUNT = "default"


class KeychainError(RuntimeError):
    pass


def is_macos() -> bool:
    return sys.platform == "darwin"


def store_client_secret(secret: str) -> None:
    if not is_macos():
        raise KeychainError("Keychain storage requires macOS.")
    result = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-a",
            ACCOUNT,
            "-s",
            SERVICE,
            "-w",
            secret,
            "-U",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise KeychainError(f"Could not store client secret in Keychain: {result.stderr.strip()}")


def load_client_secret() -> str:
    if not is_macos():
        raise KeychainError("Keychain storage requires macOS.")
    result = subprocess.run(
        ["security", "find-generic-password", "-a", ACCOUNT, "-s", SERVICE, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise KeychainError(
            "Client secret not found in Keychain. Re-run: python -m xero_mcp init ..."
        )
    secret = result.stdout.strip()
    if not secret:
        raise KeychainError("Keychain returned an empty client secret.")
    return secret


def delete_client_secret() -> None:
    if not is_macos():
        return
    subprocess.run(
        ["security", "delete-generic-password", "-a", ACCOUNT, "-s", SERVICE],
        capture_output=True,
        text=True,
    )

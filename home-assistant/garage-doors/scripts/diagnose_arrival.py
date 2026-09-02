#!/usr/bin/env python3
"""Thin wrapper — use fetch_ha_diagnostics.py for full traces/logbook/history."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fetch_ha_diagnostics.py"


def main() -> int:
    cmd = [sys.executable, str(SCRIPT), "--topic", "arrival", "--hours", "12", *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())

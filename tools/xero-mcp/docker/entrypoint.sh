#!/bin/sh
set -eu
exec python -m xero_mcp inbound serve --host 0.0.0.0 --port "${WEBHOOK_PORT:-8766}" --daemon

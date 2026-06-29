#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/topexnative/Projects/unraid-array-design/tools/todoist-mcp"
ENV_FILE="${TODOIST_MCP_ENV:-$ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${TODOIST_API_KEY:-}" ]]; then
  cat >&2 <<EOF
TODOIST_API_KEY is not set.

1. Get a token: Todoist → Settings → Integrations → Developer → API token
2. Either:
   - export TODOIST_API_KEY=... in /Users/topexnative/.zshrc, or
   - copy /Users/topexnative/Projects/unraid-array-design/tools/todoist-mcp/.env.example
     to /Users/topexnative/Projects/unraid-array-design/tools/todoist-mcp/.env

See /Users/topexnative/Projects/unraid-array-design/tools/todoist-mcp/README.md
EOF
  exit 1
fi

exec npx -y @doist/todoist-mcp

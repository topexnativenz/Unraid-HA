# user-todoist MCP

Cursor MCP integration for **Todoist** tasks and projects. Wraps the official [`@doist/todoist-mcp`](https://github.com/Doist/todoist-mcp) package (stdio transport).

**Location:** `tools/todoist-mcp/`

## Setup

### 1. API token

In Todoist: **Settings → Integrations → Developer → API token**.

Set it in **one** of these places (never commit the token):

```bash
# Option A — shell env (recommended)
echo 'export TODOIST_API_KEY="your-token-here"' >> /Users/topexnative/.zshrc
source /Users/topexnative/.zshrc
```

```bash
# Option B — local .env (gitignored)
cp /Users/topexnative/Projects/unraid-array-design/tools/todoist-mcp/.env.example \
   /Users/topexnative/Projects/unraid-array-design/tools/todoist-mcp/.env
# edit .env and paste token
```

### 2. Cursor MCP config

Already wired in `/Users/topexnative/.cursor/mcp.json` as `todoist`:

```json
"todoist": {
  "command": "/Users/topexnative/Projects/unraid-array-design/tools/todoist-mcp/scripts/todoist-mcp-wrapper.sh",
  "args": []
}
```

Restart Cursor (or reload MCP servers) after setting the token.

### 3. Smoke test

```bash
/Users/topexnative/Projects/unraid-array-design/tools/todoist-mcp/scripts/todoist-mcp-wrapper.sh
```

Should print `Server started` and wait on stdio. Ctrl+C to exit.

## Agent tools (official server)

The Doist server exposes workflow-oriented tools, including:

| Tool | Use |
|------|-----|
| `user-info` | Confirm which Todoist account is connected |
| `find-projects` | List projects (Inbox, Life, Work, …) |
| `find-tasks` / `find-tasks-by-date` | Query tasks with filters |
| `add-tasks` | Create tasks (content, due, project, labels, priority) |
| `update-tasks` | Edit existing tasks |
| `complete-tasks` / `uncomplete-tasks` | Mark done or reopen |
| `reschedule-tasks` | Bulk date changes |
| `find-labels` / `add-labels` | Label management |
| `get-overview` | Daily/weekly snapshot |

Full list: [Doist/todoist-mcp `src/tools`](https://github.com/Doist/todoist-mcp/tree/main/src/tools).

## OAuth alternative (no API key)

Todoist also hosts an OAuth MCP at `https://ai.todoist.net/mcp`. Useful for interactive chat; for unattended agents, prefer the API token + stdio setup above.

```json
"todoist-oauth": {
  "command": "npx",
  "args": ["-y", "mcp-remote", "https://ai.todoist.net/mcp"]
}
```

## Personal ops context

Per `cursor-life` workflow: Todoist holds **Inbox**, **Life**, and **Work** projects. Ask before creating tasks from an agent unless the user explicitly requested capture.

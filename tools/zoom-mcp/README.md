# Zoom MCP setup (Cursor)

Two-server setup for transcripts/notes + scheduling.

| Server | MCP name | Auth | Purpose |
|--------|----------|------|---------|
| Official Zoom MCP | `zoom` | User OAuth | Meeting transcripts, AI Companion notes, recordings |
| kindflow | `zoom-api` | S2S OAuth | Create/list/update meetings |

## Local config (done)

- `/Users/topexnative/.cursor/mcp.json` — `zoom` + `zoom-api` entries
- `/Users/topexnative/.zshrc` — `ZOOM_*` placeholder exports

## Checklist

### 1. User-managed OAuth app (official MCP)

1. [marketplace.zoom.us](https://marketplace.zoom.us/) → **Develop** → **Build App** → **General app** → **User-managed**
2. Scopes: `meeting:read:search`, `meeting:read:assets`, `cloud_recording:read:list_user_recordings`, `cloud_recording:read:content`, `ai_companion:read:search`, `docs:read:export`
3. Redirect URL: `cursor://anysphere.cursor-mcp/oauth/callback`
4. Copy Client ID + Secret → `/Users/topexnative/.zshrc`:
   - `ZOOM_MCP_CLIENT_ID`
   - `ZOOM_MCP_CLIENT_SECRET`

### 2. Server-to-Server OAuth app (kindflow)

1. marketplace.zoom.us → **Server-to-Server OAuth**
2. Scopes: `meeting:read:admin`, `meeting:write:admin`, `user:read:admin` (optional: `cloud_recording:read:admin`)
3. Copy Account ID, Client ID, Secret → `/Users/topexnative/.zshrc`:
   - `ZOOM_ACCOUNT_ID`
   - `ZOOM_S2S_CLIENT_ID`
   - `ZOOM_S2S_CLIENT_SECRET`

### 3. Zoom admin settings

- Enable **AI Companion**
- Enable **cloud recording** + **audio transcript**
- Set transcript retention policy

### 4. Connect in Cursor

1. `source /Users/topexnative/.zshrc` (or restart terminal + Cursor)
2. **Cursor Settings → Tools & MCP**
3. **zoom** → **Connect** (browser OAuth)
4. **zoom-api** should show green once S2S creds are set

## Test prompts

- "List my recent Zoom meetings" (`zoom-api`)
- "Schedule a 30-min meeting tomorrow at 2pm NZT titled Team sync" (`zoom-api`)
- "Get the transcript from my last Zoom meeting" (`zoom`)
- "Search AI Companion notes for action items from last week's standup" (`zoom`)

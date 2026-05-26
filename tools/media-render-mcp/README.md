# user-media-render MCP

In-repo MCP server for **Fal.ai** image/video generation and **Home Assistant** solar-dashboard background publishing.

**Location:** `tools/media-render-mcp/` (repo root relative paths in config point at `home-assistant/solar-dashboard/`).

## Guardrails

| Rule | Behavior |
|------|----------|
| **LOCKED master** | `backgrounds/v5/master-clear.png` — `edit_image` / `img2img_with_reference` refuse unless `allow_master_override=true` |
| **No JPG overwrite** | `render_image` refuses if `{version_folder}/{variant}.jpg` already exists; use a new `vN` folder |
| **Cache-bust** | `publish_ha_assets` updates `?v=` tokens in Lovelace YAML only when `dry_run=false` |
| **Deploy** | Full HA copy uses existing [`deploy_to_ha.py`](../../home-assistant/solar-dashboard/scripts/deploy_to_ha.py) (SMB + token from `~/.cursor/mcp.json`) |

## Setup

**Requires Python 3.10+** (the `mcp` SDK does not install on 3.9). Use `python3.12` or `brew install python@3.12` if system `python3` is older.

```bash
cd /Users/topexnative/Projects/unraid-array-design/tools/media-render-mcp
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy config if needed (committed defaults are safe — no secrets):

```bash
cp /Users/topexnative/Projects/unraid-array-design/tools/media-render-mcp/media-render.config.example.json \
   /Users/topexnative/Projects/unraid-array-design/tools/media-render-mcp/media-render.config.json
```

Set **FAL_KEY** in your environment (do not commit). Recommended: add to Cursor MCP server `env` (see below).

Optional live renders:

```bash
export RENDER_LIVE=1   # required for Fal writes when dry_run=false
```

## Tools (Phase 0 + minimal Phase 1)

| Tool | Phase |
|------|-------|
| `list_versions` | Lists `v*` folders under backgrounds root |
| `render_image` | `dry_run=true` → planned paths; live with `dry_run=false` + `RENDER_LIVE=1` + `FAL_KEY` |
| `edit_image` | Stub; LOCKED master check |
| `img2img_with_reference` | Stub |
| `render_video` | Stub |
| `publish_ha_assets` | Cache-bust YAML update (dry_run default) + deploy docs |

## Cursor `mcp.json` snippet

Add under `mcpServers` in `/Users/topexnative/.cursor/mcp.json` (paste **your** FAL key via env — never commit it):

```json
"user-media-render": {
  "command": "/Users/topexnative/Projects/unraid-array-design/tools/media-render-mcp/.venv/bin/python",
  "args": ["-m", "media_render_mcp"],
  "cwd": "/Users/topexnative/Projects/unraid-array-design/tools/media-render-mcp",
  "env": {
    "FAL_KEY": "<paste-from-fal-dashboard>",
    "MEDIA_RENDER_CONFIG": "/Users/topexnative/Projects/unraid-array-design/tools/media-render-mcp/media-render.config.json"
  }
}
```

Restart Cursor after editing MCP config.

## Config

`media-render.config.json` keys:

- `ha_host` / `ha_url` — HA instance (default `192.168.1.239`)
- `backgrounds_root` — repo-relative path to `www/solar-dashboard/backgrounds`
- `locked_master` — frozen CGI master PNG
- `render_backend` — `fal` (uses `FAL_KEY`)
- `lovelace_yaml_paths` — files receiving cache-bust updates
- `deploy_script` — path to `deploy_to_ha.py`

Override path: `MEDIA_RENDER_CONFIG` env var.

## Manual smoke test

```bash
cd /Users/topexnative/Projects/unraid-array-design/tools/media-render-mcp
source .venv/bin/activate
python -c "from media_render_mcp.config import load_config; from media_render_mcp.paths import list_version_folders; c=load_config(); print(list_version_folders(c.backgrounds_path))"
```

## Phase 1+ next steps

1. Wire `edit_image` / `img2img_with_reference` to Fal inpaint + reference models.
2. Batch weather variants (`clear`, `cloudy`, …) from one master workflow.
3. Optional: invoke `deploy_to_ha.py` from `publish_ha_assets` when `run_deploy=true`.
4. `render_video` — pick Fal video endpoint and MP4 placement under `www/solar-dashboard/`.

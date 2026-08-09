# AI 3D → Bambu Agent (MCP)

Cursor/Claude MCP agent that turns **photos or freeform prompts** into **print-oriented 3MF** for your two **Bambu Lab X1 Carbon** printers, then hands off to **Bambu Studio (macOS)** or **Bambu on iOS**. Prints are **never started automatically**.

**Location:** `tools/ai-3d-agent-mcp/`

## Design (locked to your answers)

| Requirement | Implementation |
|-------------|----------------|
| Done = open in Studio / iOS slicer | `handoff_to_bambu` → macOS `open -a BambuStudio` or iOS share folder/URL |
| Functional + hooks + signs + figurines | **Parametric CAD** for hooks/signs/brackets; **AI mesh** for figurines/photos |
| Dimensional accuracy | Tools **require** `width_mm/depth_mm/height_mm`; mesh is scaled to target |
| Single + multi-angle photos | `image_paths[]` on `create_job` |
| AMS multi-colour | Dominant-colour → AMS slot suggestions in manifest (paint in Studio) |
| Unraid host | MCP + job store on tower; optional HTTP generator container |
| Self-hosted first | `generation_backend`: `stub` → `http` (TRELLIS/Hunyuan wrapper); paid later |
| Job history | SQLite + per-job `job.json` + artifacts |
| No auto-print | Hard guardrail; confirm in Bambu UI |

```text
Prompt / photo(s) + dimensions
        │
        ▼
┌───────────────────┐
│  Route selector   │  hook/sign/bracket → parametric
│                   │  figurine / photo  → AI mesh (HTTP/stub)
└─────────┬─────────┘
          ▼
   Repair · scale · flat base (figurines)
          ▼
   Export STL + 3MF + AMS suggestions + checklist
          ▼
   macOS Bambu Studio  OR  iOS Files → Bambu app
          ▼
   YOU confirm slice/print (cloud OK)
```

## Why dual-path (accuracy)

AI image-to-3D is great for likeness, weak for exact mm. For **hooks / signs / brackets** this agent builds **parametric geometry** sized to your numbers. For **figurines / organic** shapes it generates a mesh (self-hosted HTTP or stub), then **uniformly scales** into your bounding box and can add a **flat base**.

## Setup (Unraid / tower or Mac)

Python **3.10+** required.

```bash
cd /path/to/Unraid-HA/tools/ai-3d-agent-mcp
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ai-3d-agent.config.example.json ai-3d-agent.config.json
```

Edit `ai-3d-agent.config.json`:

- `workspace_root` — durable job store (prefer `/mnt/user/ai-3d-agent/jobs` on Unraid)
- `printers.X1C-A` / `X1C-B` — rename to match how you think about the two machines
- `ios_share_base_url` — HTTPS/SMB web path iPhone can open (e.g. Nextcloud/Unraid share)
- `open_studio_command` — optional SSH-to-Mac opener, e.g.  
  `ssh macuser@mac-studio 'open -a BambuStudio "{path}"'`  
  (Mac must mount the same jobs path, or copy the 3MF first)
- `generation_backend` — `stub` (offline), then `http` when the GPU container is up

### Cursor `mcp.json`

```json
"ai-3d-bambu-agent": {
  "command": "/mnt/user/appdata/ai-3d-agent/.venv/bin/python",
  "args": ["-m", "ai_3d_agent_mcp"],
  "cwd": "/mnt/user/appdata/ai-3d-agent",
  "env": {
    "AI_3D_AGENT_CONFIG": "/mnt/user/appdata/ai-3d-agent/ai-3d-agent.config.json"
  }
}
```

Adjust paths if the MCP runs from the git checkout instead of appdata.

## Agent workflow (what Cursor should do)

1. Ask category + **approx W×D×H mm** (`dimension_prompt`).
2. `create_job(...)` with dimensions (and `image_paths` if any).
3. `generate_and_package(job_id)`.
4. Surface **warnings** (non-blocking) + AMS suggestions + final extents.
5. `handoff_to_bambu(job_id, target="macos_studio"|"ios_bambu", dry_run=false)` — **never** set `confirm_send_to_printer=true`.
6. You slice / send in Bambu Studio or Bambu iOS via **Bambu cloud**.

## MCP tools

| Tool | Purpose |
|------|---------|
| `agent_info` | Config, printers, policy |
| `dimension_prompt` | Forced dimension questionnaire |
| `create_job` | Start tracked job (dims required) |
| `generate_model` | Parametric or AI raw STL |
| `package_for_bambu` | Repair, scale, base, 3MF, AMS, checklist |
| `generate_and_package` | Both steps |
| `handoff_to_bambu` | Open Studio / stage iOS (no print) |
| `suggest_ams_colors` | Colour slots from images |
| `list_jobs` / `get_job` | History |

## Self-hosted generator HTTP contract

`POST generation_http_url` JSON:

```json
{
  "prompt": "fox figurine",
  "category": "figurine",
  "width_mm": 50,
  "depth_mm": 40,
  "height_mm": 70,
  "images": [{"name": "a.jpg", "b64": "..."}],
  "output_format": "stl"
}
```

Response JSON: `{ "stl_b64": "..." }` or `{ "download_url": "..." }`, or raw STL bytes.

CPU test server:

```bash
source .venv/bin/activate
python docker/http_generator_stub.py
# then set generation_backend=http and generation_http_url=http://127.0.0.1:7860/
```

GPU: see `docker/docker-compose.yml` (profile `gpu`) — swap in TRELLIS/Hunyuan image that speaks this API.

## Paid upgrade path (later)

If self-hosted likeness/topology is weak: set `generation_backend` to a future `meshy` / `tripo` adapter (keys via env). Keep parametric path for functional parts.

## Tests

```bash
cd tools/ai-3d-agent-mcp
source .venv/bin/activate
pytest -q
```

## Safety

- `allow_auto_print` defaults **false** and is enforced in `handoff_to_bambu`.
- Mesh failures are **warnings** (continue) unless you change policy later.
- Every job writes history for audit / re-handoff.

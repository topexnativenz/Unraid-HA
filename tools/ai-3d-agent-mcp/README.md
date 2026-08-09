# AI 3D → Bambu (simple)

**End-user experience is only two paths:**

1. **Describe** what you want in plain English in Cursor → answer **one size question** → model opens in Bambu Studio.
2. **Drop a photo** (optional short caption) → answer **one size question** → model opens in Bambu Studio / iOS.

Claude/Cursor auto-detects print intent (see `.cursor/rules/ai-3d-bambu-print.mdc`) and calls **`simple_print_request`**. Nothing starts on the printer until **you** confirm in Bambu.

**Location:** `tools/ai-3d-agent-mcp/`

---

## What you do

| You | Agent |
|-----|--------|
| “Make me a wall hook for coats” | Asks: roughly how big (mm)? |
| “40 × 25 × 60 mm” | Builds → opens/stages 3MF on **David’s MacBook Air (2139)** |
| Drop photo of a figurine | Asks size only → builds → Bambu |
| In Bambu Studio / iOS | You slice & confirm print (cloud OK) |

No filament / AMS / support quiz unless you ask.

---

## What Claude does (automatic)

```text
detect print intent
    → simple_print_request(description and/or photos)
        → if no size: ask ONLY dimensions
        → if size given: build → 3MF → handoff to Studio/iOS
    → you confirm print in Bambu
```

Under the hood (you can ignore this day-to-day):

- Hooks / signs / brackets → **parametric CAD** (accurate mm, **no GPU**)
- Figurines / photos → mesh backend (`stub` today; GPU HTTP or paid Meshy later)
- Job history saved every time

---

## GPU reality (your setup)

You are **unsure** either X1C host has a GPU for TRELLIS/Hunyuan. That is fine for v1:

| Request type | Works without GPU? |
|--------------|--------------------|
| Text hooks, signs, mounts | **Yes** (parametric) |
| Photo / figurine likeness | Placeholder mesh until you add GPU **or** paid Meshy/Tripo |

When photo quality matters, either stand up a GPU container on Unraid (`generation_backend=http`) or enable a paid adapter later.

---

## One-time setup

Python **3.10+**.

```bash
cd tools/ai-3d-agent-mcp
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ai-3d-agent.config.example.json ai-3d-agent.config.json
```

Edit `ai-3d-agent.config.json`:

| Key | Purpose |
|-----|---------|
| `workspace_root` | Prefer `/mnt/user/ai-3d-agent/jobs` on Unraid |
| `macos_hostname` | Default `Davids-MacBook-Air-2139.local` (verify in Sharing) |
| `macos_ssh_user` | Your Mac login short name (enables SSH open) |
| `macos_jobs_mount` | Mac path to that share, e.g. `/Volumes/ai-3d-agent/jobs` |
| `ios_share_base_url` | Optional HTTPS link for iPhone |
| `generation_backend` | `stub` now; `http` when a generator exists |

### Cursor MCP snippet

```json
"ai-3d-bambu-agent": {
  "command": "/path/to/tools/ai-3d-agent-mcp/.venv/bin/python",
  "args": ["-m", "ai_3d_agent_mcp"],
  "cwd": "/path/to/tools/ai-3d-agent-mcp",
  "env": {
    "AI_3D_AGENT_CONFIG": "/path/to/tools/ai-3d-agent-mcp/ai-3d-agent.config.json"
  }
}
```

Restart Cursor after saving. The rule `.cursor/rules/ai-3d-bambu-print.mdc` is always-on.

### Mac share (required for Studio open from Unraid)

1. Export Unraid share `ai-3d-agent` (jobs folder).
2. On **David’s MacBook Air (2139)**, mount it so files appear at `macos_jobs_mount`.
3. Enable Remote Login (SSH) if you want the agent to launch Bambu Studio for you.
4. Confirm hostname: System Settings → General → Sharing (Bonjour name).

If SSH is not set, the 3MF is still created — open it manually from the share in Bambu Studio.

---

## MCP tools (daily vs power-user)

| Daily | Tool |
|-------|------|
| **Primary** | `simple_print_request` |
| Optional | `detect_print_intent` |
| History | `list_jobs`, `get_job` |

Power-user steps (`create_job`, `generate_model`, …) remain available but are not needed in normal chat.

---

## Tests

```bash
cd tools/ai-3d-agent-mcp && source .venv/bin/activate && pytest -q
```

## Safety

- Auto-print is **off** and blocked in handoff.
- Mesh problems **warn and continue**.
- Every job is logged under `workspace_root`.

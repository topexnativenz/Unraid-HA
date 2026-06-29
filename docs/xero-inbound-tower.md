# Xero inbound bills (tower + portfolio routing)

Supplier invoices arrive by email, are classified against the **Notified portfolio** (property address / nickname in subject or body), and land as **draft bills** in the correct Xero org with **all attachments**.

Production runs on **Unraid tower** only — not on your Mac.

**Parsing / splitting / blocklists (canonical):** [xero-inbound-extraction-rules.md](./xero-inbound-extraction-rules.md) — use that doc when changing `tools/xero-mcp/src/xero_mcp/inbound/` or debugging supplier/line-item behaviour on future invoices.

## Target workflow

| Intake (short-term + permanent) | Routing |
|-----------------------------------|---------|
| `accounts@matarikigroup.co.nz` | Cloudflare Worker → tower → Xero draft bills |
| `david@` / `genna@` @ `matarikigroup.co.nz` | CF forward → `@gillespie.kiwi` Google Workspace (personal inbox, **not** Worker) |
| `david@` / `genna@` @ `gillespie.kiwi` | Native Google MX (direct to Workspace) |

**Forwarding bills to Xero:** Genna and David send or forward supplier invoices **to** `accounts@matarikigroup.co.nz` (To or Cc). Cloudflare delivers that address to the Worker. Tower accepts senders in `allowed_from` (`genna@`, `david@`, `accounts@` on both domains); if a forward keeps the supplier in `To` only, tower still queues to `accounts@` via `default_intake_address`. Mail sent only to `genna@matarikigroup.co.nz` / `david@matarikigroup.co.nz` never hits the Worker — it goes to personal Gmail.

| Xero organisation | Slug | Notes |
|-------------------|------|-------|
| **Matariki Property Group Limited** | `matariki-property-group` | Production MPG — all property bills + portfolio default |
| Matariki Traders | `matariki-traders` | |
| Matariki Morningside Development | `matariki-morningside-development` | |
| ~~MPG Cancelled~~ | `mpg-cancelled` | **Do not use** — duplicate org; excluded in `orgs.config.json` |

**OAuth:** Only connected orgs appear in the registry. After renaming the duplicate to **MPG Cancelled**, run `python -m xero_mcp login` and authorise **Matariki Property Group Limited** (the real org). Slug `matariki-property-group` is assigned automatically from the Xero name. Until then, `set_active_organisation matariki-property-group` and inbound property routing will fail.

| Tenant | Org | Status |
|--------|-----|--------|
| `5b20078f-bd79-4f72-b236-25683e58dc3a` | MPG Cancelled | Excluded — duplicate |
| *(connect via OAuth)* | Matariki Property Group Limited | Required for `matariki-property-group` slug |
| `6d997fc9-0776-4c42-87cf-1e9be8cba204` | Matariki Traders Limited | Active |
| `f51aa912-30bb-4826-95cc-1797e3505ca9` | Matariki Morningside Development Limited | Active |

Example: subject contains **Logyard Road** → portfolio match → **Matariki Property Group Limited** (`matariki-property-group`).

## Bill intelligence (PDF + gate + Xero links)

Inbound processing now has three layers before a Xero draft is created:

| Layer | What it does |
|-------|----------------|
| **PDF extraction** | pypdf text → supplier (header/`To:`/TAX INVOICE block, skips PAYMENT ADVICE footer), invoice #, dates, `TOTAL NZD` totals, qty/unit/line table rows, NoTax when subtotal equals total with no GST line; **contact** email/address from PDF |
| **Office docs** | `.docx` / `.xlsx` via zip+XML (no extra deps); legacy `.doc` best-effort binary text; ranked equal to PDF for primary attachment |
| **Email extraction** | When PDF/doc is missing or weak (e.g. forwarded `FW:` mail), parse subject/body for council/supplier name, reference tokens (`DCPM2500002`), amounts, and dates |
| **Email signatures** | Parse blocks after `--`, `Kind regards`, and forwarded `From:` lines — org (e.g. Whangarei District Council), person (Caroline Ngata), email, phone, address; merged with attachment extraction; internal forwarder domains never used as supplier |
| **Attachment ranking** | PDF = docx = doc = xlsx preferred over `image001.png` signature/logo inline images; small PNGs skipped as primary bill source |
| **Multi-invoice email** | One queue record + one Xero draft **per** bill attachment (pdf/docx/doc/xlsx) or per distinct Xero link group; shared `source_message_id` ties splits from the same email; dedupe per attachment hash + `invoice_hint` from filename |
| **Invoice numbers (splits)** | `invoice_hint` on each queue record → `INV-{hint}` for Xero `InvoiceNumber`; beats shared email body text (e.g. portfolio name "Matariki"); PDF extraction still wins when it has a numeric invoice # |
| **Supplier (splits)** | Per-attachment letterhead wins; shared forward body ignored for `split_kind=attachment` (blocks **Design NZ**, **Matariki Property Group**, collection agents); Xero contact match rejects collection-agent hits when PDF supplier is set |
| **Qty-only lines** | Description + quantity rows (no unit price) → Xero **Quantity** set, **UnitAmount** 0, **LineAmount** split from footer **Amount** (excl GST); footer lines (Amount/GST/Amount including GST) are not line items |
| **One PDF → one bill** | False PDF section splits coalesced when only one invoice number; body-only queue suppressed when a bill PDF is attached; dedupe by attachment SHA256 + invoice # |
| **Single PDF, multiple invoices** | Best-effort split on repeated `TAX INVOICE` / `Invoice Number:` headers → multiple drafts from one queue record (`xero_invoice_ids`); if headers not detected, one draft per attachment only |
| **Dates** | Issue/due from attachment labels (`Invoice date`, `Due date`, NZ `dd/mm/yyyy`, `19 May 2026`); due date omitted when not found (no longer copied from issue date); forwarded `Date:` header used as issue-date fallback when doc missing |
| **Bill gate** | `is_actionable_bill()` — rejects newsletters, marketing, payment confirmations, personal mail; accepts PDF bills, image attachments, and Xero link emails |
| **Xero links** | Detects `go.xero.com`, `invoicing.xero.com`, etc.; if the bill UUID already exists in a connected org → queue marks **done** (linked); otherwise creates a draft with the link in the description for manual import |
| **Contact match** | Find-or-create Xero Contact by PDF supplier email (preferred) or sender email, then normalized company name — avoids duplicate suppliers on repeat invoices |

Queue statuses include **`rejected`** (failed bill gate — no Xero draft) and **`failed`** (processing error). Rejected messages store `bill_gate.reason`.

**Queue fields for splits:** `source_message_id` (email batch), `split_index` / `split_total`, `split_kind` (`attachment` | `link` | `body`), optional `invoice_hint` from filename (`INV-5859.pdf`). After processing, `xero_invoice_id` is the first draft; `xero_invoice_ids` lists all when a single PDF was section-split.

### Config (`inbound.json`)

| Key | Default | Purpose |
|-----|---------|---------|
| `require_bill_classification` | `true` | Run bill gate before creating drafts |
| `min_bill_confidence` | `0.55` | Minimum gate confidence |
| `bill_classifier_mode` | `heuristic` | `heuristic`, `llm`, or `hybrid` (needs `OPENAI_API_KEY`) |
| `allow_xero_links` | `true` | Detect and handle Xero URLs in email body |
| `allow_xero_link_without_attachment` | `true` | Accept link-only emails (no PDF) |
| `allow_email_body_without_attachment` | `true` | Create draft from forwarded email body when supplier + total extracted (PDF lost in forward) |
| `blocked_sender_domains` | `[]` | Always reject (e.g. `mailchimp.com`) |
| `allowed_from` | genna/david/accounts @ matarikigroup + gillespie | Trusted forwarders; maps to `default_intake_address` when `To` is not an intake address |
| `default_intake_address` | `accounts@matarikigroup.co.nz` | Fallback recipient for trusted forwarders |
| `process_delay_sec` | `1.5` | Seconds between auto-processed queue items in one webhook batch (reduces Xero 429 on burst forwards). Override: env `XERO_INBOUND_PROCESS_DELAY_SEC` |

**Burst forwards:** Multiple PDFs in one email become multiple queue records; auto-process runs **in a background thread** after the webhook returns **200** (enqueue only). Processing is **sequential** under a global lock with `process_delay_sec` between items. Each Xero API call retries on HTTP **429** with exponential backoff (respects `Retry-After`, up to ~120s total).

### Cloudflare HTTP 524 (origin timeout)

If the tower webhook waited for full `process_queued_records` before responding, Cloudflare Email Routing could hit **HTTP 524** (origin timeout, typically ~30–100s) and **reject the email** — nothing queued, CF dashboard shows "Handled" only on the Worker side with a failed forward.

| Symptom | Cause | Fix |
|---------|-------|-----|
| CF 524 on `xero-inbound.gillespie.kiwi` | Sync auto-process + 429 backoff + stagger delays | Webhook returns **200 immediately** after `enqueue_email()`; Xero work runs async on `ThreadingHTTPServer` |
| Email never in tower queue | 524 = rejected before enqueue | Deploy tower + Worker **accept-always** policy (see below) |
| `failed` with `429` in queue | Burst Xero rate limits | Heal cron (`inbound heal`) + `process_delay_sec`; not a 524 issue once queued |

Post-deploy check: `curl -o /dev/null -w '%{time_total}\n' -X POST …/inbound/cloudflare` with a minimal JSON body should complete in **&lt;5s** (secret header required).

### Zero-bounce policy (`accounts@matarikigroup.co.nz`)

**Priority:** suppliers must never receive an NDR from `accounts@`. Losing automation and landing mail in a human inbox is acceptable; bouncing is not.

Every inbound message to `accounts@` has **three acceptable outcomes** (supplier always gets SMTP 250 — no bounce):

| Outcome | When | What David sees |
|---------|------|-----------------|
| **1. Xero draft** | Tower POST succeeds; queue processes normally | `[accounts@ copy] {original subject}` in `david@gillespie.kiwi` **plus** draft bill in Xero |
| **2. Inbox copy (normal path)** | Same as #1 — copy is sent on every successful tower enqueue | Full original message + attachments; subject prefix **`[accounts@ copy]`** (distinct from fallback) |
| **3. Fallback on outage** | Tower POST fails after retries (524/502/503/network) | `[XERO-INBOUND-FALLBACK] {original subject}` in fallback inbox — full message + attachments for manual handling |

**If you received `[accounts@ copy]` but no Xero draft:** tower accepted the webhook (200) but queue processing may still be pending, failed, or rejected by bill gate. Check tower queue — not a delivery/bounce issue.

```bash
# Queue status (tower)
ssh tower 'docker exec xero-inbound python -m xero_mcp inbound queue --json'

# Reprocess a failed id
ssh tower 'docker exec xero-inbound python -m xero_mcp inbound process <message-uuid>'

# Auto-heal stuck/failed items
bash /Users/topexnative/Projects/unraid-array-design/tower/scripts/xero-inbound-heal.sh
```

| Layer | Policy |
|-------|--------|
| **Email Worker** (`worker.js`) | **Never** `setReject()`. On **successful** tower POST → `message.forward()` to **`INBOX_COPY_TO`** (default **`david@gillespie.kiwi`**, comma-separated for multiple) with subject **`[accounts@ copy]`** — original attachments preserved. Tower POST retries **4 attempts** (initial + 3) on HTTP **524/502/503** and network errors (backoff 1.5s → 3s → 6s). On persistent failure → `message.forward()` to **`FALLBACK_TO`** (default **`david@gillespie.kiwi`**) with subject prefix **`[XERO-INBOUND-FALLBACK]`**. Attachment parse errors → minimal JSON POST, then fallback forward if tower still fails. |
| **Tower webhook** (`/inbound/cloudflare`) | Authenticated POST **never returns 5xx**. Bad secret → **401** only. Enqueue/parse errors → **200** `{ok:false, error, queued:[]}`. Xero processing failures stay in queue (`failed`/`rejected`) — never affect HTTP response. |
| **CF routing** | `accounts@` → Worker only (no duplicate forward rule). Catch-all drop **disabled**. |

**Worker vars** (`wrangler.toml` `[vars]` or Cloudflare dashboard):

| Var | Default | Purpose |
|-----|---------|---------|
| `INBOX_COPY_TO` | `david@gillespie.kiwi` | Inbox copy after successful tower enqueue (comma-separated; blank disables) |
| `FALLBACK_TO` | `david@gillespie.kiwi` | Fallback when tower POST fails (first address if comma-separated) |

Example in `xero.inbound.example.json` → `cloudflare_worker` block mirrors these defaults for documentation.

**Operational checks after deploy:**

```bash
# Worker deployed (note version id in wrangler output)
ssh tower 'bash /mnt/user/appdata/xero-inbound/deploy-cloudflare-xero-inbound.sh'

# Tower webhook (if webhook.py changed)
bash /Users/topexnative/Projects/unraid-array-design/tower/scripts/deploy-xero-inbound.sh

# Routing: accounts@ → worker, no drop/forward conflict
ssh tower 'TOKEN=$(tr -d "\n\r" < /mnt/user/appdata/claude-agent/data/.cloudflare_api_token); TOKEN="${TOKEN%cfut_}"
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/query-email-routing-rules.mjs:/app/q.mjs \
  -e CLOUDFLARE_API_TOKEN="$TOKEN" node:20-slim node /app/q.mjs matarikigroup.co.nz'
```

**Supplier notice (one paragraph):** *We fixed an issue where invoices sent to accounts@matarikigroup.co.nz could bounce before [DEPLOY DATE]. Please send all bills directly to accounts@matarikigroup.co.nz (PDF or Word attachment preferred). If you received an undeliverable notice before that date, please resend — delivery is now confirmed. Thank you.*

| `allowed_extensions` | `.pdf`, `.jpg`, `.jpeg`, `.png`, `.heic`, `.doc`, `.docx`, `.xls`, `.xlsx` | Tower deploy merges office formats even if Mac `inbound.json` omits them |

**Contact fields:** PDF trading name wins over the email `From` display name. Internal domains (`matarikigroup.co.nz`, `gillespie.kiwi`) are never used as supplier contact names — extraction uses forwarded body text (e.g. **Whangarei District Council**). Primary email is PDF `Email:` line when present, else non-internal sender address.

### Xero payment reminder emails (`in.xero.com`)

Supplier bills sent via **Xero payment reminders** (`invoicereminders@post.xero.com`, `in.xero.com` links, no PDF attachment) are parsed specially:

| Field | Source |
|-------|--------|
| Supplier | Subject pattern `Bill INV-xxx from {Supplier} is due` |
| Invoice # | Subject / `Invoice #:` line |
| Due date | `was due on 20 May 2026`, `Overdue - 20 May 2026` |
| Amount | `$2,074.72 NZD` |
| Issue date | Only when explicitly labeled — **not** the forwarder's `Date:` header |
| Line description | `{Supplier} — {INV}` (short, no FW subject boilerplate) |
| Reference | `{INV} \| {in.xero.com link}` — link stored here, not in line description |

**Link resolution order:**

1. UUID from `DownloadPdf/{uuid}` or `go.xero.com?InvoiceID=` → lookup in connected orgs
2. Search all orgs by `InvoiceNumber` (e.g. `INV-00001769`) — if found, queue links existing bill (no duplicate)
3. External supplier link (bill not in your org) → draft ACCPAY with metadata from email; open link to import manually

**PDF attachment:** If bill already exists in your org, attachments are listed on link. External `DownloadPdf` URLs are auth-walled — tower attempts fetch but usually cannot download without supplier session. No file preview expected for external links until you import via the link.

**Contact matching:** Truncated name matches (e.g. `Limit` vs `Limited`) are rejected; full supplier name from subject is used.

### Xero link limitations

The Xero API **cannot import a bill from an arbitrary shared link** in another organisation. Supported paths:

1. **Bill already in org** — UUID lookup or `InvoiceNumber` search succeeds → queue marks **done** (linked to existing bill).
2. **External supplier link** — draft ACCPAY with clean description + link in **Reference**; open link in Xero to accept/import manually. PDF not auto-attached.
3. **Link + PDF attachment in email** — normal extraction; link in Reference for reference.

Optional LLM bill gate: set `bill_classifier_mode` to `hybrid` and `OPENAI_API_KEY` in container env (same pattern as portfolio routing).

## Architecture

**Production (hybrid):** Email Routing **ON** on `matarikigroup.co.nz` only; **OFF** on `gillespie.kiwi`.

| Address | Delivery |
|---------|----------|
| `accounts@matarikigroup.co.nz` | Cloudflare Worker → tower webhook → Xero draft bills |
| `david@matarikigroup.co.nz` | CF forward → verified `david@gillespie.kiwi` → Google Workspace |
| `genna@matarikigroup.co.nz` | CF forward → verified `genna@gillespie.kiwi` → Google Workspace |
| `david@gillespie.kiwi` | Native Google MX (gillespie org) |
| `genna@gillespie.kiwi` | Native Google MX (gillespie org) |

**Never** same-domain forward (`david@matarikigroup` → `david@matarikigroup`) while Cloudflare holds MX — mail re-enters CF and loops (521 / 550 too many forwards). Cross-domain forward to `@gillespie.kiwi` breaks the loop. Catch-all **drop** stays **disabled** on matarikigroup so personal addresses are not silently discarded.

Re-apply hybrid rules on tower:

```bash
ssh tower 'TOKEN=$(tr -d "\n\r" < /mnt/user/appdata/claude-agent/data/.cloudflare_api_token); TOKEN="${TOKEN%cfut_}"
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/setup-email-routing.mjs:/app/setup.mjs \
  -e CLOUDFLARE_API_TOKEN="$TOKEN" node:20-slim node /app/setup.mjs'
```

```mermaid
flowchart LR
  subgraph Gillespie["gillespie.kiwi — routing OFF"]
    MXG[Google MX]
    GWG[Workspace inboxes]
    MXG --> GWG
  end
  subgraph Matariki["matarikigroup.co.nz — routing ON"]
    CFMX[CF MX]
    CFMX -->|accounts@| EW[Email Worker]
    CFMX -->|david@ genna@| FWD[Forward to @gillespie.kiwi]
    FWD --> GWG
    EW --> WH[xero-inbound :8766]
  end
  Supplier --> CFMX
  Supplier --> MXG
```

**Fallback (routing off both zones):** native Google MX everywhere; use Gmail filters to forward PDF bills to `accounts@`. Run `restore-native-google-inboxes.mjs`.

Restore native inboxes on tower:

```bash
ssh tower 'export CLOUDFLARE_API_TOKEN=$(cat /mnt/user/appdata/claude-agent/data/.cloudflare_api_token)
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/restore-native-google-inboxes.mjs:/app/r.mjs \
  -e CLOUDFLARE_API_TOKEN node:20-slim node /app/r.mjs'
```

If the disable API fails (token lacks Zone DNS Edit), complete **Disable Email Routing** in the Cloudflare dashboard for **both** `gillespie.kiwi` and `matarikigroup.co.nz`.

## Tower paths

| Path | Purpose |
|------|---------|
| `/mnt/user/appdata/xero-inbound/config/` | OAuth tokens, `inbound.json`, `portfolio.entities.json` |
| Container `xero-inbound` | Webhook + 15‑min token refresh |
| Port **8766** | LAN webhook (`/health`, `/inbound/cloudflare`) |

Deploy Xero container on tower:

```bash
bash /Users/topexnative/Projects/unraid-array-design/tower/scripts/deploy-xero-inbound.sh
```

Cloudflare Worker (tower only, no Mac wrangler):

```bash
bash /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp/scripts/setup-cloudflare-xero-inbound.sh
# or on tower only:
ssh tower 'bash /mnt/user/appdata/xero-inbound/deploy-cloudflare-xero-inbound.sh'
```

## Cloudflare setup

**One command (SWAG + Worker deploy + routing API attempt):**

```bash
bash /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp/scripts/setup-cloudflare-xero-inbound.sh
```

### 1. Public webhook URL — done

| Component | Status |
|-----------|--------|
| SWAG `xero-inbound.gillespie.kiwi` → `192.168.1.7:8766` | On tower |
| Health (LAN) | `curl -s https://xero-inbound.gillespie.kiwi/health` → `{"ok":true}` |
| **Public DNS** | Must be **proxied CNAME** → `f7333fc4-04bc-447c-9040-ce0a6a1ba711.cfargotunnel.com` + tunnel hostname → `https://192.168.1.7:443` (No TLS Verify). Wildcard `*.gillespie.kiwi` A → `192.168.1.7` is **LAN-only** — Email Worker `fetch` cannot reach it. |

### 2. Email Worker — done (tower only)

- Worker: **`xero-inbound-email`** — `wrangler 4` in Docker on tower (`deploy-cloudflare-xero-inbound.sh`)
- `WEBHOOK_SECRET` from `/mnt/user/appdata/xero-inbound/config/inbound.json`
- Posts to `https://xero-inbound.gillespie.kiwi/inbound/cloudflare`

### 3. Email delivery — hybrid (current)

| Zone | Email Routing | MX | Rules |
|------|---------------|-----|-------|
| `gillespie.kiwi` | **OFF** | `ASPMX.L.GOOGLE.COM` (+ ALT*) | none (native Google) |
| `matarikigroup.co.nz` | **ON** | `route*.mx.cloudflare.net` | see below |

Xero webhook uses HTTP only (`xero-inbound.gillespie.kiwi`) — **never** enable Email Routing on gillespie.kiwi.

| Address | Cloudflare rule |
|---------|-----------------|
| `accounts@matarikigroup.co.nz` | **Send to Worker** → `xero-inbound-email` |
| `david@matarikigroup.co.nz` | **Forward** → verified `david@gillespie.kiwi` (Google Workspace) |
| `genna@matarikigroup.co.nz` | **Forward** → verified `genna@gillespie.kiwi` (Google Workspace) |
| Catch-all | **Disabled** (do not drop unmatched mail silently) |

**Never** same-domain forward on matarikigroup (`@matarikigroup` → `@matarikigroup`) — infinite loop while CF MX is active.

Apply / refresh: `setup-email-routing.mjs` on tower (requires routing already enabled via dashboard or `enable-email-routing-dns.mjs`).

Revert to native Google everywhere: `restore-native-google-inboxes.mjs` — removes forward rules, attempts API disable, prints dashboard steps if blocked.

#### Same-domain forward loops and 521 errors

Cloudflare MX on matarikigroup means **all** inbound `@matarikigroup.co.nz` mail hits CF first. A forward rule like `david@matarikigroup` → `david@matarikigroup` sends mail back into Cloudflare’s MX → forward again → **550 5.4.6 Email was forwarded too many times** (often preceded by **521 5.3.0 Upstream error**).

| Broken pattern | Why it fails |
|----------------|--------------|
| `david@matarikigroup` → `david@matarikigroup` | Re-enters CF MX every hop — infinite loop |
| Any `@matarikigroup` → same `@matarikigroup` address | Same loop |

| Working pattern | Why it works |
|-----------------|--------------|
| `david@matarikigroup` → `david@gillespie.kiwi` | CF delivers to Google MX on gillespie (routing OFF) — loop broken |
| `accounts@matarikigroup` → Worker | HTTP webhook — no SMTP forward |

Fix live rules: `fix-matariki-forward-rules.mjs` or `setup-email-routing.mjs` on tower.

If Activity Log shows **521** on a **cross-domain** forward, expand the row for Google’s detail (550 policy/auth). Ensure `genna@gillespie.kiwi` / `david@gillespie.kiwi` are **verified** in Email → Destination addresses.

Fallback if hybrid is untenable: disable routing on matarikigroup + Gmail filters for `accounts@` bills (`restore-native-google-inboxes.mjs`).

#### Cross-domain ping-pong (Gmail → matarikigroup loop)

Cloudflare on matarikigroup can be **correct** (forward to `@gillespie.kiwi`) while mail still loops. The second hop is **not** Cloudflare — it is **Google Workspace / Gmail** on `gillespie.kiwi` forwarding mail **back** to `@matarikigroup.co.nz`.

| Hop | What happens |
|-----|----------------|
| 1 | External mail → `david@matarikigroup.co.nz` → CF MX → **Forward** → `david@gillespie.kiwi` (Google) |
| 2 | Gmail **Forwarding and POP/IMAP** or Admin **routing rule** → `david@matarikigroup.co.nz` again |
| 3 | CF MX receives same message → rejects (too many forwards / policy) → **bounce** |

**Symptoms:** Undeliverable from `mailer-daemon@googlemail.com`; rejecting server `route*.mx.cloudflare.net`; failed recipient `david@matarikigroup.co.nz`; subject may be a simple test. Bounce often lands in the **matarikigroup** inbox because that address is the **failed recipient** on the return path (RFC 5321), not because delivery succeeded there.

**Verify Cloudflare (tower — read-only):**

```bash
ssh tower 'TOKEN=$(tr -d "\n\r" < /mnt/user/appdata/claude-agent/data/.cloudflare_api_token); TOKEN="${TOKEN%cfut_}"
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/query-email-routing-rules.mjs:/app/q.mjs \
  -e CLOUDFLARE_API_TOKEN="$TOKEN" node:20-slim node /app/q.mjs gillespie.kiwi
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/query-email-routing-rules.mjs:/app/q.mjs \
  -e CLOUDFLARE_API_TOKEN="$TOKEN" node:20-slim node /app/q.mjs matarikigroup.co.nz'
```

| Zone | Expected |
|------|----------|
| `gillespie.kiwi` | `enabled=false`; no active forward rules to `@matarikigroup.co.nz` |
| `matarikigroup.co.nz` | `david@` / `genna@` → forward to verified `@gillespie.kiwi`; `accounts@` → Worker |

**Fix (Google — not Cloudflare):** Remove reverse forwarding on each affected `*@gillespie.kiwi` mailbox:

1. **Gmail (user):** Settings → **Forwarding and POP/IMAP** → disable or delete forwarding to any `@matarikigroup.co.nz` address.
2. **Google Admin:** Apps → Google Workspace → Gmail → **Routing** (and **Default routing** / **Address maps**) — delete rules that send `david@gillespie.kiwi` or `genna@gillespie.kiwi` mail to `@matarikigroup.co.nz`.
3. Optional: **Send mail as** / **Alternate email** — ensure nothing re-injects matarikigroup as a forward target for inbound copy.

**Correct end-to-end test** (after removing reverse forward):

- Send **from an external Gmail** (not the same Workspace org) **to** `david@matarikigroup.co.nz`.
- Expect delivery in **`david@gillespie.kiwi`** inbox (Gmail app or web).
- Do **not** expect the test message in matarikigroup unless you sent there directly; bounces and mis-tests often appear on matarikigroup only.

Do **not** test by sending from `david@gillespie.kiwi` to `david@matarikigroup.co.nz` while reverse forward still exists — that can recreate the loop from the gillespie side.

#### Google rejects CF forward (no Gmail reverse forward)

When user Gmail **Forwarding and POP/IMAP** and **Filters** are confirmed empty on both mailboxes, the same symptoms usually mean **Google rejected Cloudflare’s SMTP forward** to `@gillespie.kiwi` — not a CF↔Gmail ping-pong loop.

| Symptom | Meaning |
|---------|---------|
| CF Activity **Forwarded** (or **521** on cross-domain forward) | CF matched the rule and attempted delivery to Google |
| No mail in `david@gillespie.kiwi` inbox | Google rejected, quarantined, or (for self-send tests) blocked as loop |
| Undeliverable; rejecting server `route*.mx.cloudflare.net`; **failed recipient** `david@matarikigroup.co.nz` | DSN names the original RCPT TO — **not** proof the bounce landed in a matarikigroup Google inbox (apex MX is Cloudflare, not Google) |

**Invalid test:** `david@gillespie.kiwi` → `david@matarikigroup.co.nz` → CF forwards back to `david@gillespie.kiwi`. Google often returns **550** (loop / auth) even with zero Gmail forwarders. Always test with an **external** sender (personal Gmail outside both Workspace orgs).

**Still check (Admin console, not user Gmail):** Google Admin → Apps → Google Workspace → Gmail → **Routing**, **Default routing**, **Address maps** on **both** orgs. Also check **Quarantine** / **Security** for silently dropped forwards.

**Notified.co.nz:** Disabled forward on gillespie to `*@in.notified.co.nz` does not affect matarikigroup intake; portfolio sync is HTTP API only.

#### Recommended fix when native `david@matarikigroup` is required

Hybrid apex routing **cannot** deliver native matarikigroup inboxes and `accounts@` Worker on the same apex domain: Cloudflare must hold apex MX for the Worker, so `@matarikigroup.co.nz` never reaches Google natively.

**Preferred — subdomain split (Option A):**

1. Restore **Google MX on apex** `matarikigroup.co.nz` (`restore-native-google-inboxes.mjs` + dashboard disable if API blocked).
2. Add subdomain e.g. `xero.matarikigroup.co.nz` with MX → `route1/2/3.mx.cloudflare.net`; enable Email Routing rules on that subdomain only (`accounts@xero.matarikigroup.co.nz` → Worker).
3. Google Admin on matarikigroup: route `accounts@matarikigroup.co.nz` → `accounts@xero.matarikigroup.co.nz` (or notify suppliers of the subdomain address).
4. `david@` / `genna@` stay native on Google matarikigroup; **remove** CF personal forward rules. Keep gillespie routing **OFF**.

**Fallback — Gmail path (Option B):** Disable CF routing on matarikigroup; all mail native Google; use Gmail filters to copy PDF bills to a monitored label (Worker HTTP intake from Gmail not implemented in repo yet).

**Do not rely on Option D long-term:** Cross-domain CF forward matarikigroup → gillespie remains fragile under Google 2024+ inbound auth (SPF/DMARC break on forward, self-send failures, quarantine).

### Troubleshooting: nothing in Xero after sending email

Check status on tower:

```bash
ssh tower 'export CLOUDFLARE_API_TOKEN=$(cat /mnt/user/appdata/claude-agent/data/.cloudflare_api_token)
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/enable-email-routing-dns.mjs:/app/e.mjs \
  -e CLOUDFLARE_API_TOKEN node:20-slim node /app/e.mjs'
```

| Symptom | Cause | Fix |
|---------|--------|-----|
| Personal mail missing on matarikigroup | Same-domain forward loop removed; gillespie dest unverified | Run `fix-matariki-forward-rules.mjs`; verify `@gillespie.kiwi` destinations |
| Personal mail missing on gillespie | Email Routing enabled on gillespie | Keep routing **OFF** on gillespie; native Google MX |
| Catch-all dropping mail | Catch-all drop enabled | `setup-email-routing.mjs` disables catch-all; check dashboard |
| `route*.mx.cloudflare.net` in `dig MX matarikigroup` | Expected while hybrid routing ON | gillespie should still show Google MX |
| Activity: **550 too many forwards** | Same-domain `@matarikigroup` forward | Delete rule; use `@gillespie.kiwi` destination — `fix-matariki-forward-rules.mjs` |
| Activity: **521** on personal forward | Same-domain loop or unverified gillespie dest | Cross-domain to verified gillespie; see § Same-domain forward loops |
| Activity: **521** on cross-domain forward | Google rejected delivery or dest unverified | Verify `david@gillespie.kiwi` / `genna@gillespie.kiwi` in CF dashboard |
| CF shows **Forwarded** but no mail in gillespie inbox; **Undeliverable** bounce to `david@matarikigroup` from `route3.mx.cloudflare.net` | **If** Gmail reverse forward exists: CF↔Gmail loop. **If forwarders confirmed off:** Google rejected CF forward (auth/quarantine/self-send test) | Remove reverse forward if any; retest from **external** sender; check Admin **Quarantine**; prefer subdomain split (§ Recommended fix) for native matarikigroup |
| `accounts@` not reaching Xero | Worker rule missing or routing OFF | Run `setup-email-routing.mjs`; send test PDF |
| No new files in `.../inbound/queue/` | Routing off or worker/webhook issue | If routing intentionally off, use Gmail path; else check worker + `fix-xero-inbound-public-dns.mjs` |
| CF Activity **Handled**, empty queue | Worker/webhook failure | Redeploy worker; check tunnel DNS |
| Queue shows `failed` — only logo PNG, no PDF/docx | Gmail/Outlook forward dropped bill file; only inline signature PNG arrived | Send **direct to `accounts@`** (or forward-as-attachment); check Worker logs for `files=[...]`; queue `attachment_warning` when body-only |
| `.docx` in Worker logs but missing from queue | `allowed_extensions` on tower omitted `.docx` (Mac config overwrote example) | Redeploy — script now merges office extensions; verify `grep allowed_extensions /mnt/user/appdata/xero-inbound/config/inbound.json` |
| Queue shows `duplicate` but no bill in Xero | Earlier attempt failed; resend after fix or `inbound process <id>` on failed record | Check **failed** entries first, not duplicate retries |
| Activity log: **worker script threw an exception** | Worker crash or missing PDF | Redeploy worker; resend with PDF attached |

Simulated tests already created drafts (subjects like `Logyard Road - public webhook E2E`) — search Draft bills if checking those.

**Query live rules:**

```bash
ssh tower 'TOKEN=$(tr -d "\n\r" < /mnt/user/appdata/claude-agent/data/.cloudflare_api_token); TOKEN="${TOKEN%cfut_}"
docker run --rm -v /mnt/user/appdata/xero-inbound/cloudflare/query-email-routing-rules.mjs:/app/q.mjs \
  -e CLOUDFLARE_API_TOKEN="$TOKEN" node:20-slim node /app/q.mjs matarikigroup.co.nz'
```

### API token permissions (tower + wrangler)

Create or edit a **Custom Token** at [API Tokens](https://dash.cloudflare.com/profile/api-tokens). Store on tower only:

`/mnt/user/appdata/claude-agent/data/.cloudflare_api_token`

| Permission | Access | Why |
|------------|--------|-----|
| **User → Memberships** | Read | Wrangler `whoami` / account lookup *(optional if `account_id` is in `wrangler.toml`)* |
| **User → User Details** | Read | Wrangler “whoami” email line *(optional)* |
| **Account → Workers Scripts** | Edit | Deploy `xero-inbound-email` |
| **Account → Workers KV** | Edit | Wrangler deploy helper |
| **Zone → Email Routing Rules** | Edit | Hybrid rules: worker + personal forwards |
| **Account → Email Routing Addresses** | Edit | Verify david@/genna@ gillespie.kiwi forward destinations |
| **Zone → DNS** | Edit | Disable routing / restore Google MX via API *(often dashboard-only)* |
| **Zone → Zone Settings** | Read | `email/routing/disable` API |
| **Zone → Zone** | Read | List zones |
| **Zone → Analytics** | Read | `query-email-activity.mjs` GraphQL (optional) |

**Zone resources:** `matarikigroup.co.nz` and **`gillespie.kiwi`** (DNS Edit required for `fix-xero-inbound-public-dns.mjs`).

**Account → Cloudflare Tunnel** Edit (optional): auto-add `xero-inbound.gillespie.kiwi` tunnel public hostname.

**Wrangler on tower:** `account_id` is in `wrangler.toml`. Token file: `/mnt/user/appdata/claude-agent/data/.cloudflare_api_token` (single token only — use `printf '%s'`, never paste twice).

```bash
# Worker + secret + routing (syncs repo files to tower, runs wrangler 4 in Docker on tower)
bash /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp/scripts/setup-cloudflare-xero-inbound.sh

# Worker only (on tower)
ssh tower 'bash /mnt/user/appdata/xero-inbound/deploy-cloudflare-xero-inbound.sh'
```

No Mac `npx wrangler` required.

**Migration tip:** Gmail filter on david/genna — forward PDF bills to `accounts@matarikigroup.co.nz` (lands in Google when routing is off).

## Portfolio data

Sync property keywords from Notified (requires service JWT on tower):

```bash
ssh tower 'docker exec -e NOTIFIED_SERVICE_JWT=*** xero-inbound python -m xero_mcp inbound sync-portfolio'
```

Or edit `/mnt/user/appdata/xero-inbound/config/portfolio.entities.json` directly.

Optional LLM: set `OPENAI_API_KEY` in container env and `"classifier_mode": "hybrid"` in portfolio file.

## Suggestions (beyond core spec)

1. **Gmail label + leave-in-inbox** for david/genna during migration — only `accounts@` fully automated.
2. **Slack/HA notification** on `failed` queue status (tower can curl HA webhook).
3. **Weekly `sync-portfolio` cron** on tower after Notified property changes.
4. **Supplier allowlist** — ignore marketing domains before creating bills (`blocked_sender_domains` in `inbound.json`).
5. **Xero duplicate bill check** — same invoice number + contact within 30 days → queue `duplicate` not second draft.
6. **Default account code per org** — keep org-specific codes in `inbound.json` `routes` keyed by `org_slug` (deploy script preserves Mac values).
7. **Audit spreadsheet** — export `config/inbound/audit.log` monthly.

## Operations

```bash
# Health
ssh tower 'curl -s http://127.0.0.1:8766/health'

# Queue (inside container)
ssh tower 'docker exec xero-inbound python -m xero_mcp inbound queue --json'

# Reprocess failed / rejected
ssh tower 'docker exec xero-inbound python -m xero_mcp inbound process <message-uuid>'

# Unit tests (Mac, from repo)
cd /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp && PYTHONPATH=src .venv/bin/python -m unittest tests.test_inbound -v

# Logs
ssh tower 'docker logs --tail 100 xero-inbound'
```

OAuth re-auth (rare): run `python -m xero_mcp login` on Mac, then redeploy `deploy-xero-inbound.sh` to copy fresh `connections.json`.

---

## Testing schedule

Run in order after deploy. Use a **test PDF** (no real supplier PII) and note Xero draft IDs.

### Phase A — Infrastructure (day 1)

| # | Test | Pass criteria |
|---|------|----------------|
| A1 | `curl http://192.168.1.7:8766/health` on LAN | `{"ok":true}` |
| A2 | `curl https://xero-inbound.gillespie.kiwi/health` (if configured) | `{"ok":true}` |
| A3 | Wrong `X-Xero-Inbound-Secret` POST to `/inbound/cloudflare` | **401** invalid secret (Worker forwards fallback if secret drift; fix secret sync) |
| A4 | `docker exec … python -m xero_mcp doctor` | healthy + 3 orgs |

### Phase B — Classification (no email, day 1)

| # | Test | Pass criteria |
|---|------|----------------|
| B1 | Queue test: subject `Logyard Road invoice` → `accounts@matarikigroup.co.nz` | `routing.method=portfolio_property`, `org_slug=matariki-property-group` |
| B2 | Subject `Morningside development invoice` | `org_slug=matariki-morningside-development` |
| B3 | Subject `Traders stock order` | `org_slug=matariki-traders` |
| B4 | Ambiguous subject only | `routing.method=default` or `llm` — draft still created, **review org in Xero** |
| B5 | Subject `March newsletter` (no PDF) | Queue `rejected`, `bill_gate.is_bill=false` |
| B6 | Body with `go.xero.com/...InvoiceID=...` only | Gate passes; draft or linked existing bill |

CLI (on tower):

```bash
ssh tower 'docker exec xero-inbound python -m xero_mcp inbound test \
  --to accounts@matarikigroup.co.nz \
  --subject "Logyard Road - test invoice" \
  --pdf /app/tests/fixtures/test-invoice.pdf'
```

Test PDF is baked into the Docker image at `/app/tests/fixtures/test-invoice.pdf` (see `tools/xero-mcp/docker/Dockerfile`).

### Phase C — Xero drafts (day 2)

| # | Test | Pass criteria |
|---|------|----------------|
| C1 | Single PDF → Property Group | Draft ACCPAY in MPG, one attachment |
| C2 | Email with 2+ PDFs | **Two queue records / two drafts** (one per attachment); see extraction-rules doc |
| C3 | Resend same email | Queue status `duplicate`, no second bill |
| C4 | JPEG attachment | Accepted if extension allowed |

### Phase D — Live email (day 3–7, staggered)

| # | Test | Pass criteria |
|---|------|----------------|
| D1 | Send test mail to `accounts@matarikigroup.co.nz` with PDF | Worker → tower → Xero draft &lt; 5 min |
| D2 | Forward real bill from `david@matarikigroup.co.nz` (if routed) | Correct org from property hint |
| D3 | `david@gillespie.kiwi` test (if routed) | Same |
| D4 | Google inbox still receives human mail for david/genna | No MX breakage |

### Phase E — Production cutover (week 2+)

| # | Action |
|---|--------|
| E1 | Notify top 10 suppliers: new `accounts@matarikigroup.co.nz` |
| E2 | Monitor `inbound/audit.log` daily for `inbound_failed`; optional auto-heal (below) |
| E3 | Run `sync-portfolio` after any Notified property add/rename |
| E4 | Disable legacy `bills.*@` routes when traffic is zero |

## Auto-heal (stuck / failed queue)

Cloudflare Email Routing marks messages **Handled** after the Worker POST succeeds; tower can still leave queue items **failed**, **pending** too long, **processing** (crashed mid-run), or **done** without `xero_invoice_id`. Heal fixes the **tower side only** — CF delivery status does not change.

| Symptom | Typical cause | Heal action |
|---------|---------------|-------------|
| `failed` + 429 / timeout | Xero rate limit | `RETRY_NOW` with `--force` after cooldown |
| `pending` &gt; 15 min | Webhook never auto-processed | Reprocess |
| `processing` &gt; 10 min | Container restart mid-bill | Reset → pending → process |
| `done` but no invoice id | Partial write / race | Force reprocess (dedupe still applies) |
| `duplicate` but prior bill deleted in Xero | Old dedupe | `DUPLICATE_OK` force |
| Missing PDF / signature only | Forward dropped file | `NEEDS_PDF` — **no** auto-heal (re-send mail) |
| `rejected` / bill gate | Not a bill | `PERMANENT` — manual only |

**Config** (`inbound.json` → `heal` object; defaults in `xero.inbound.example.json`):

| Key | Default | Purpose |
|-----|---------|---------|
| `enabled` | `true` | Master switch |
| `pending_max_age_sec` | `900` | Stuck pending threshold |
| `processing_max_age_sec` | `600` | Stuck processing threshold |
| `done_missing_bill_grace_sec` | `120` | Wait before re-healing empty `done` |
| `max_attempts` | `5` | Per-record heal cap (`heal_attempts` on queue JSON) |
| `min_interval_sec` | `300` | Min gap between heals on same id |
| `retryable_error_patterns` | 429, 503, timeout, … | Regex list for `classify_failure` |

**CLI (tower container or Mac venv):**

```bash
docker exec xero-inbound python -m xero_mcp inbound heal --scan-only --json
docker exec xero-inbound python -m xero_mcp inbound heal --limit 10 --json
docker exec xero-inbound python -m xero_mcp inbound heal --dry-run --limit 10
```

**Mac → tower (LAN):**

```bash
bash /Users/topexnative/Projects/unraid-array-design/tower/scripts/xero-inbound-heal.sh
```

**Schedule (light I/O — OK every 15–30 min daytime):** Unraid **User Scripts** or cron on tower:

```bash
*/30 * * * * docker exec xero-inbound python -m xero_mcp inbound heal --limit 10 >>/mnt/user/appdata/xero-inbound/config/inbound/heal-cron.log 2>&1
```

Last run summary: `~/.config/xero-mcp/inbound/heal-last.json` on Mac, `/config/inbound/heal-last.json` in container.

**MCP (`xero-inbound`):** `scan_inbound_health`, `auto_heal_inbound` (optional `dry_run=true`). Cursor Automations can call these on a schedule if `xero-inbound` MCP is dashboard-connected.

**Genna’s next failed PDF forward:** After CF shows Handled, if tower queue is `failed` (429) or stuck `pending`, the next heal cron (or `auto_heal_inbound`) re-runs `process --force` with dedupe checks — no SSH unless `NEEDS_PDF` (re-forward with attachment to `accounts@matarikigroup.co.nz`).

## Lessons learned

Short pointers; detail and code map in [xero-inbound-extraction-rules.md](./xero-inbound-extraction-rules.md).

| Lesson | Takeaway |
|--------|----------|
| Multi-PDF emails | One Xero draft **per** bill attachment (`split_kind=attachment`), not one draft with all PDFs — avoids merged wrong supplier/totals. |
| Forwarded MPG mail | PDF letterhead wins; body ignored for supplier on attachment splits — blocks **Design NZ** / **Matariki** collection text. |
| Single PDF noise | False `TAX INVOICE` section splits **coalesced** when only one invoice number in file (Three60 case). |
| Line tables | Qty-only rows + footer **Amount/GST** totals; metadata lines (job site, invoice no) are not line items. |
| Filename hints | `INV-5859.pdf` → per-attachment `invoice_hint` beats shared email body for `InvoiceNumber`. |
| Dedupe | SHA256 + `invoice_hint`; auto-heal or `inbound process <uuid> --force` / MCP `auto_heal_inbound`. |
| Intake address | Only **`accounts@matarikigroup`** hits the Worker; david/genna matarikigroup → gillespie personal. |
| Apex MX hybrid | Same-domain `@matarikigroup` forwards loop; cross-domain to `@gillespie.kiwi` or subdomain split for native matarikigroup mailboxes. |

### Rollback

1. Pause Cloudflare Email Routing rules to Worker.
2. `docker stop xero-inbound` on tower.
3. Bills continue via manual Xero / Gmail as today.

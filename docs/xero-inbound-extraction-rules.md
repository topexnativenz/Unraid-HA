# Xero inbound — extraction & splitting rules

Canonical reference for **why** inbound bills are parsed, split, and deduped the way they are. Operational deploy, Cloudflare, and tower paths live in [xero-inbound-tower.md](./xero-inbound-tower.md).

**Production path (every new email):** Cloudflare Worker → `webhook.py` → `parser.enqueue_email()` → `processor.process_message()` → `extract.py` / `xero_links.py` / `xero_bills.py`. No one-off scripts on this path.

| Module | Role |
|--------|------|
| `parser.py` | EML/Mailgun parse, nested MIME walk, enqueue splits, dedupe at intake |
| `bill_splits.py` | One queue record per bill attachment / link group / body-only |
| `attachments.py` | Bill vs signature images, extension ranking |
| `document_text.py` | PDF, docx/xlsx zip+XML, legacy `.doc` |
| `extract.py` | Supplier, lines, totals, coalesce/split PDF sections |
| `processor.py` | Gate, merge, multi-section PDF drafts, Xero create |
| `xero_links.py` | Link detect, org lookup, reminder-specific flow |
| `xero_contacts.py` | Contact match; rejects collection-agent when PDF supplier set |

---

## Email routing (intake only)

| Address | Behaviour |
|---------|-----------|
| `accounts@matarikigroup.co.nz` | Cloudflare Email Worker → tower webhook → queue + Xero |
| `david@` / `genna@` @ `matarikigroup.co.nz` | CF **forward** → `@gillespie.kiwi` (personal; **not** Worker) |
| `david@` / `genna@` @ `gillespie.kiwi` | Native Google MX |

Supplier PDFs for automation must hit **`accounts@matarikigroup.co.nz`** (To or Cc). Tower `allowed_from` accepts Genna/David/accounts on matarikigroup and gillespie.kiwi; if a forward leaves only the supplier in `To`, intake falls back to `default_intake_address`. Personal `@matarikigroup` inboxes still CF-forward to Gmail and do not hit the Worker unless the user forwards to `accounts@`.

---

## Split behaviour (one email → N queue records → N drafts)

Implemented in `split_inbound_into_bills()` (`bill_splits.py`), called from `enqueue_email()` (`parser.py`).

| Case | `split_kind` | Queue records |
|------|--------------|---------------|
| N bill attachments (pdf/docx/doc/xlsx) | `attachment` | **One per attachment**, ranked order |
| Xero links only (config allows) | `link` | One per link group |
| Forwarded body with supplier + total, no file | `body` | One (`allow_email_body_without_attachment`) |
| Bill files present | — | **No** separate body-only record (body split never runs) |

**Per-attachment fields:** `invoice_hint` from filename (`INV-5859.pdf`, `68451.pdf`, `DCPM2500002`, etc.) → Xero `InvoiceNumber` via `format_invoice_hint()` (`INV-{digits}`).

**Shared batch:** `source_message_id`, `split_index` / `split_total`.

**Single PDF, multiple real invoices:** `processor` runs `split_extracted_text_by_invoices()` then `coalesce_pdf_invoice_sections()` — multiple drafts only when **distinct** invoice numbers appear in full text; otherwise one coalesced bill (fixes false section splits on one invoice).

**Multi-PDF regression tests:** `test_two_pdfs_split_into_two_bills`, `test_six_hints_produce_distinct_invoice_numbers`.

---

## Supplier extraction (PDF letterhead)

Priority in `_extract_supplier()` (`extract.py`):

1. **`To:` on PAYMENT ADVICE** — e.g. `HAINESCO/Haines Masonry ltd` → trading name after `/`
2. Lines before `TAX INVOICE` (skipped if top is PAYMENT ADVICE remittance block)
3. Letterhead scoring (`_extract_supplier_from_letterhead`) — e.g. **Three60 Electrical & Security**
4. Block after GST number / Reference (customer site lines excluded)

**Blocked as supplier / contact** (`_is_blocked_contact_name`, `_BLOCKED_CONTACT_NAMES`, `_COLLECTION_AGENT_MARKERS`):

- Lines starting with **Attention:**, **GST No/Number**, Payee/Remit/Payment to
- **Matariki***, **gillespie**, **Design NZ** (collection agent on forwarded MPG mail)
- `_SUPPLIER_BLOCKLIST` tokens (payment advice, invoice date, quantity, total nzd, …)
- Internal domains: `matarikigroup.co.nz`, `gillespie.kiwi` (use PDF or forwarded council body)

**Attachment splits:** `attachment_only_supplier=True` in `processor` → email body **not** merged for supplier (stops forward boilerplate overwriting PDF letterhead). `xero_contacts` skips collection-agent Xero contact when PDF supplier is plausible.

---

## Line items

| Rule | Implementation |
|------|----------------|
| **Qty-only rows** | `Description … Qty 2` → quantity set, unit 0, amounts from footer split (`_finalize_qty_only_line_items`) |
| **Multi-line PDF rows** | Description on one or more lines, then orphan `qty unit amount` row — `_normalize_line_item_rows` joins before parse (e.g. Vital Signs INV-15841) |
| **Labour hours qty** | Integer qty ≥ 24 allowed when description contains labour/hours (e.g. Hainesco INV-1517, 157 hrs); site names in description (Logyard road) are not rejected |
| **Genna Xero forward (no PDF)** | Subject `Fwd: Invoice INV-… from … for Matariki…` → `is_xero_reminder_email` + body-only draft; heal **RETRY_NOW** (not NEEDS_PDF) |
| **Exclusive unit price** | Multiple trailing amounts: pick pair where `qty × unit ≈ line`; skip duplicate columns; reconcile down if `unit × qty` exceeds footer **subtotal** (GST-inclusive mistake). Fallback single line uses **subtotal** not total when GST present (`xero_bills._line_items_payload`) |
| **Footer not lines** | `Amount`, `GST`, `Amount including GST`, subtotal/total — `_is_footer_summary_line` |
| **Metadata not lines** | `Invoice No:`, `Job Site`, `GST No`, `Attention`, `To:` — `_is_invoice_metadata_line` |
| **Three60 layout** | Job site / invoice header rows must not become line items; qty-only + footer totals tested in `test_three60_*` |

Full price rows still use qty × unit when present (`_QTY_LINE_RE`).

---

## Invoice numbers

Resolution order in `merge_extraction()` / `_resolve_invoice_number()`:

1. PDF/doc extracted number
2. **`invoice_hint`** when `attachment_only_invoice` (attachment split)
3. Email subject/body (suppressed for attachment-only invoice when hint or bill file present)

Weak numbers (portfolio names, etc.) filtered via `_is_weak_invoice_number`.

---

## Dedupe & reprocess

**At enqueue** (`parser.py`):

- `dedupe_key` = SHA256(`org_slug|from|attachment_sha256|invoice_hint` or link id or `body-only`)
- Duplicate attachment: same org + SHA256 + matching formatted `invoice_hint` on a **done** record with bill still active in Xero

**Reprocess existing queue row** (not for new mail):

```bash
ssh tower 'docker exec xero-inbound python -m xero_mcp inbound process <message-uuid> --force'
```

`--force` clears prior Xero ids and resets status (`processor.process_message(force=True)`). **MCP** `process_inbound_message` does not expose `--force` yet — use tower CLI.

---

## Attachments & MIME

| Rule | Module |
|------|--------|
| PDF/docx/doc/xlsx score 100; tiny PNGs = signature | `attachments.py` |
| `rank_bill_attachments` before split | `bill_splits.py` |
| Inline **office** parts treated as attachments | `parser.parse_eml_bytes` (`message.walk`, skip multipart containers) |
| Nested docx in raw MIME | `test_cloudflare_raw_fallback_finds_nested_docx` |
| Non-bill images on first split for audit | `collect_non_bill_attachments` |

---

## Xero link & reminder emails

| Type | Behaviour |
|------|-----------|
| `in.xero.com` / `go.xero.com` | `detect_xero_links`; UUID lookup or invoice number search across orgs |
| Payment reminders (`invoicereminders@post.xero.com`) | `is_xero_reminder_email` — supplier/due/amount from subject; no forwarder `Date:` as issue date |
| External supplier link | Draft + link in **Reference**; manual import (API cannot pull arbitrary org bill) |
| Link-only | `allow_xero_link_without_attachment` |

---

## Config keys (`inbound.json`)

| Key | Default | Notes |
|-----|---------|-------|
| `allow_email_body_without_attachment` | `true` | Forwarded council/etc. when PDF dropped |
| `allow_xero_links` / `allow_xero_link_without_attachment` | `true` | |
| `require_bill_classification` | `true` | `bill_gate.py` |
| `allowed_extensions` | includes office formats | Tower deploy should merge docx/xlsx |

See [xero-inbound-tower.md](./xero-inbound-tower.md) for full config table and bill-gate modes.

---

## Known limitations

- **Cannot** auto-import a bill from another org’s shared Xero URL; draft + manual step only.
- **External `DownloadPdf`** URLs are auth-walled; tower usually cannot attach PDF.
- **True multi-invoice single PDF** without repeated headers → one draft (header-based split is best-effort).
- **Gmail/CF forwards** may strip PDFs; body-only draft + `attachment_warning`.
- **Hybrid matarikigroup MX** — personal `@matarikigroup` native inboxes conflict with Worker on same apex; see tower doc subdomain split.
- **Phase C2 in tower test schedule** (“one draft, all PDFs”) is **outdated** — production is **one draft per bill PDF**.

---

## Tests (Mac, from repo)

```bash
cd /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp && PYTHONPATH=src .venv/bin/python -m unittest tests.test_inbound -v
```

Focused examples:

```bash
cd /Users/topexnative/Projects/unraid-array-design/tools/xero-mcp && PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_inbound.TestBillSplits.test_two_pdfs_split_into_two_bills \
  tests.test_inbound.TestExtractThree60.test_three60_qty_only_lines_and_totals \
  tests.test_inbound.TestExtractThree60.test_coalesce_single_invoice_pdf_sections \
  -v
```

Tower E2E inject:

```bash
ssh tower 'docker exec xero-inbound python -m xero_mcp inbound test \
  --to accounts@matarikigroup.co.nz \
  --subject "Logyard Road - test invoice" \
  --pdf /app/tests/fixtures/test-invoice.pdf'
```

---

## Tower paths (quick)

| Path | Purpose |
|------|---------|
| `/mnt/user/appdata/xero-inbound/config/` | `inbound.json`, tokens, portfolio |
| Container `xero-inbound` :8766 | Webhook + processor |
| `config/inbound/queue/` | Per-message JSON |
| `config/inbound/audit.log` | Events |

Deploy: `/Users/topexnative/Projects/unraid-array-design/tower/scripts/deploy-xero-inbound.sh`

---

## Changelog (extraction behaviour)

| Date | Change |
|------|--------|
| 2026-06 | Multi-PDF → per-attachment splits + `invoice_hint`; attachment-only supplier/invoice; qty-only + footer totals; Three60 metadata skip; coalesce false PDF sections; Design NZ / Matariki blocklist; docx/MIME; Xero reminders; dedupe by SHA256 + hint; `--force` reprocess |

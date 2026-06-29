/**
 * Restore native Google Workspace inboxes on matarikigroup.co.nz and gillespie.kiwi.
 *
 * Use this to REVERT the hybrid setup (routing off, Google MX everywhere).
 * For hybrid (accounts@ worker + personal forwards on matarikigroup), use
 * setup-email-routing.mjs instead.
 *
 * Same-domain forward (david@matarikigroup → david@matarikigroup) loops while CF MX is active.
 * Hybrid setup uses cross-domain forwards to gillespie.kiwi — see setup-email-routing.mjs.
 *
 * Correct fallback architecture: Email Routing OFF on both domains → Google MX (ASPMX.L.GOOGLE.COM).
 * Xero inbound webhook uses HTTP (xero-inbound.gillespie.kiwi) — no email routing on gillespie.
 *
 * API token needs: Zone → Email Routing Rules Edit (delete forwards).
 * Disable routing + MX restore needs: Zone DNS Edit + Zone Settings Edit (often dashboard-only).
 *
 * Run on tower:
 *   CLOUDFLARE_API_TOKEN=… node restore-native-google-inboxes.mjs
 */
const token = process.env.CLOUDFLARE_API_TOKEN;
if (!token) {
  console.error("Set CLOUDFLARE_API_TOKEN");
  process.exit(1);
}

const ZONES = ["gillespie.kiwi", "matarikigroup.co.nz"];
const ACCOUNT_ID = process.env.CF_ACCOUNT_ID || "6b75f8187544327aba3ac88047b7fb92";

async function api(method, path, body) {
  const res = await fetch(`https://api.cloudflare.com/client/v4${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { success: false, errors: [{ message: `${res.status} ${text.slice(0, 120)}` }] };
  }
}

async function zoneId(name) {
  const z = await api("GET", `/zones?name=${name}`);
  return z.result?.[0]?.id;
}

async function deleteForwardRules(zid, zoneName) {
  const rules = await api("GET", `/zones/${zid}/email/routing/rules`);
  let removed = 0;
  for (const rule of rules.result || []) {
    const hasForward = rule.actions?.some((a) => a.type === "forward");
    if (!hasForward) continue;
    const to = rule.matchers?.find((m) => m.field === "to")?.value;
    const dest = rule.actions?.find((a) => a.type === "forward")?.value?.[0];
    const r = await api("DELETE", `/zones/${zid}/email/routing/rules/${rule.id}`);
    if (r.success) {
      console.log(`  removed forward: ${to || rule.name} → ${dest}`);
      removed++;
    } else {
      console.log(`  failed remove ${to || rule.name}:`, r.errors);
    }
  }
  return removed;
}

async function tryDisableRouting(zid, zoneName) {
  const dis = await api("POST", `/zones/${zid}/email/routing/disable`, {});
  if (dis.success) {
    console.log(`  disable routing: OK (${zoneName})`);
    return true;
  }
  console.log(`  disable routing: API blocked —`, dis.errors?.[0]?.message || "failed");
  return false;
}

async function showState(zid, zoneName) {
  const routing = await api("GET", `/zones/${zid}/email/routing`);
  console.log(`  routing: enabled=${routing.result?.enabled} status=${routing.result?.status}`);

  const rules = await api("GET", `/zones/${zid}/email/routing/rules`);
  for (const r of rules.result || []) {
    const to = r.matchers?.find((m) => m.field === "to")?.value;
    const action = (r.actions || [])
      .map((a) => `${a.type}:${Array.isArray(a.value) ? a.value.join(",") : a.value}`)
      .join("; ");
    if (to || r.enabled) console.log(`  rule: ${r.name} to=${to || "(catch-all)"} => ${action}`);
  }

  const mx = await api("GET", `/zones/${zid}/dns_records?type=MX`);
  if (!mx.success) {
    console.log(`  MX: (DNS API unavailable — ${mx.errors?.[0]?.message || "no permission"})`);
    return;
  }
  for (const x of mx.result || []) {
    console.log(`  MX: ${x.content} pri=${x.priority}`);
  }
}

console.log("=== Remove cross-domain / same-domain forward rules ===\n");
let anyDisableFailed = false;

for (const zoneName of ZONES) {
  const zid = await zoneId(zoneName);
  if (!zid) {
    console.error(`Zone not found: ${zoneName}`);
    continue;
  }
  console.log(`${zoneName} (${zid})`);
  await deleteForwardRules(zid, zoneName);
  if (!(await tryDisableRouting(zid, zoneName))) anyDisableFailed = true;
  await showState(zid, zoneName);
  console.log("");
}

const dests = await api("GET", `/accounts/${ACCOUNT_ID}/email/routing/addresses?per_page=50`);
console.log("Destination addresses (informational):");
for (const d of dests.result || []) {
  console.log(`  ${d.email} verified=${d.verified ? "yes" : "no"}`);
}

if (anyDisableFailed) {
  console.log(`
MANUAL STEPS REQUIRED (token lacks Zone DNS / disable routing permission):

For EACH zone — gillespie.kiwi AND matarikigroup.co.nz:

1. https://dash.cloudflare.com/ → select zone → Email → Email Routing
2. Click "Disable Email Routing" / "Delete and disable"
   (Cloudflare restores Google MX: ASPMX.L.GOOGLE.COM, ALT*.ASPMX.L.GOOGLE.COM)
3. Email → Settings → confirm SPF is Google-friendly:
   v=spf1 include:_spf.google.com ~all

Verify after ~5 min:
  dig +short MX gillespie.kiwi
  dig +short MX matarikigroup.co.nz
  (expect ASPMX.L.GOOGLE.COM, not route*.mx.cloudflare.net)

accounts@matarikigroup.co.nz Xero worker:
  With routing disabled, accounts@ delivers to Google Workspace (not Cloudflare Worker).
  Use Gmail filter: forward PDF supplier mail to accounts@, or re-enable routing later
  ONLY if you accept personal mail must stay on Google (see docs/xero-inbound-tower.md).
`);
  process.exit(2);
}

console.log("\nDone — both zones should use Google MX. Verify with dig +short MX.");
process.exit(0);

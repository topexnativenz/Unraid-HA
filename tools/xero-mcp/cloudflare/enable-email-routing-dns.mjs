/**
 * Enable Email Routing MX/SPF on matarikigroup.co.nz (run on tower).
 * Requires API token: Zone DNS Edit + Email Routing (or use dashboard).
 *
 * After enabling, run setup-email-routing.mjs for hybrid rules:
 *   accounts@ → Worker; david@/genna@ → cross-domain forward to @gillespie.kiwi (never same-domain).
 * gillespie.kiwi must stay OFF.
 */
const token = process.env.CLOUDFLARE_API_TOKEN;
const zoneName = process.env.CF_ZONE || "matarikigroup.co.nz";

if (!token) {
  console.error("Set CLOUDFLARE_API_TOKEN");
  process.exit(1);
}

async function api(method, path, body) {
  const res = await fetch(`https://api.cloudflare.com/client/v4${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

const zones = await api("GET", `/zones?name=${zoneName}`);
const zone = zones.result?.[0];
if (!zone) {
  console.error(`Zone not found: ${zoneName}`);
  process.exit(1);
}
const zid = zone.id;

const before = await api("GET", `/zones/${zid}/email/routing`);
console.log(`\n${zoneName} Email Routing:`);
console.log(`  enabled: ${before.result?.enabled}`);
console.log(`  status:  ${before.result?.status}`);
if (before.result?.errors?.length) {
  for (const e of before.result.errors) {
    console.log(`  - ${e.code}: ${e.existing?.content || e.missing?.content || ""}`);
  }
}

if (before.result?.status === "ready" && before.result?.enabled) {
  console.log("\nAlready ready — live mail should reach the Worker.");
  process.exit(0);
}

console.log("\nApplying DNS (POST /email/routing/dns)...");
const en = await api("POST", `/zones/${zid}/email/routing/dns`, {});
if (en.success) {
  console.log(`  OK — status: ${en.result?.status}, enabled: ${en.result?.enabled}`);
  process.exit(0);
}

console.log("\nAPI could not apply DNS:", en.errors);
console.log(`
Manual fix required (one-time, ~2 min):

1. https://dash.cloudflare.com/ → ${zoneName}
2. Email → Email Routing
3. Click "Enable" / "Add records and finish"
   (replaces Google MX with route1/2/3.mx.cloudflare.net)
4. Confirm status shows "Ready" / Active

Personal inboxes (david@, genna@): run setup-email-routing.mjs after enabling —
forward to verified david@gillespie.kiwi / genna@gillespie.kiwi (NEVER same @matarikigroup).

Until MX changes, mail to accounts@ stays on Google Workspace and never hits Xero.

After enabling, send a new test PDF to accounts@matarikigroup.co.nz
`);

process.exit(1);

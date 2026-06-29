/**
 * Hybrid Email Routing on matarikigroup.co.nz ONLY (gillespie.kiwi stays OFF).
 *
 * | Address                         | Action                                      |
 * |---------------------------------|---------------------------------------------|
 * | accounts@matarikigroup.co.nz    | Worker xero-inbound-email (Xero bills)      |
 * | david@matarikigroup.co.nz       | Forward → verified david@gillespie.kiwi     |
 * | genna@matarikigroup.co.nz       | Forward → verified genna@gillespie.kiwi     |
 *
 * NEVER forward matarikigroup → same @matarikigroup.co.nz address. Cloudflare holds
 * MX for matarikigroup.co.nz, so same-domain forwards re-enter CF MX → infinite loop
 * → Activity 521 then 550 "Email was forwarded too many times".
 *
 * Personal mail reaches Google Workspace on gillespie.kiwi (native Google MX there).
 * Cross-domain forward breaks the loop: CF delivers to ASPMX.L.GOOGLE.COM directly.
 *
 * Catch-all drop stays DISABLED so unmatched addresses are not silently dropped.
 *
 * Run on tower: CLOUDFLARE_API_TOKEN=… node setup-email-routing.mjs
 */
const token = process.env.CLOUDFLARE_API_TOKEN;
if (!token) {
  console.error("Set CLOUDFLARE_API_TOKEN");
  process.exit(1);
}

const WORKER = "xero-inbound-email";
const ZONE_NAME = "matarikigroup.co.nz";
const GILLESPIE_ZONE = "gillespie.kiwi";
const ACCOUNT_ID = process.env.CF_ACCOUNT_ID || "6b75f8187544327aba3ac88047b7fb92";

/** @type {{ addr: string, dest: string, name: string }[]} */
const PERSONAL_FORWARDS = [
  { name: "david-inbox", addr: "david@matarikigroup.co.nz", dest: "david@gillespie.kiwi" },
  { name: "genna-inbox", addr: "genna@matarikigroup.co.nz", dest: "genna@gillespie.kiwi" },
];

const MATARIKI_DOMAIN = "@matarikigroup.co.nz";

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

const zones = await api("GET", `/zones?name=${ZONE_NAME}`);
const zone = zones.result?.[0];
if (!zone) {
  console.error("Zone not found");
  process.exit(1);
}
const zid = zone.id;
console.log(`Zone ${zone.name} (${zone.status})`);

const gZones = await api("GET", `/zones?name=${GILLESPIE_ZONE}`);
const gZone = gZones.result?.[0];
if (gZone) {
  const gRouting = await api("GET", `/zones/${gZone.id}/email/routing`);
  if (gRouting.result?.enabled) {
    console.error(
      `${GILLESPIE_ZONE} Email Routing must stay OFF (native Google MX). Disable in dashboard first.`,
    );
    process.exit(1);
  }
  console.log(`${GILLESPIE_ZONE}: routing OFF (OK)`);
}

const routing = await api("GET", `/zones/${zid}/email/routing`);
console.log(`Email Routing: enabled=${routing.result?.enabled} status=${routing.result?.status}`);

if (!routing.result?.enabled) {
  console.log(`
Email Routing is OFF on ${ZONE_NAME}.

Run enable-email-routing-dns.mjs or enable in dashboard first, then re-run this script.
${GILLESPIE_ZONE} must stay OFF (native Google MX).
`);
  process.exit(1);
}

const dests = await api("GET", `/accounts/${ACCOUNT_ID}/email/routing/addresses?per_page=50`);
const destByEmail = new Map((dests.result || []).map((d) => [d.email.toLowerCase(), d]));

for (const { dest } of PERSONAL_FORWARDS) {
  const d = destByEmail.get(dest.toLowerCase());
  if (!d?.verified) {
    console.warn(`Destination not verified (rule skipped until verified): ${dest}`);
  }
}

async function upsertRule(name, fromAddr, actions) {
  const existing = await api("GET", `/zones/${zid}/email/routing/rules`);
  const rule = (existing.result || []).find((r) => {
    const to = r.matchers?.find((m) => m.field === "to")?.value;
    return to === fromAddr;
  });

  const body = {
    name,
    enabled: true,
    matchers: [{ type: "literal", field: "to", value: fromAddr }],
    actions,
  };

  if (rule) {
    const cur = JSON.stringify(rule.actions);
    const next = JSON.stringify(actions);
    if (cur === next && rule.enabled) {
      console.log(`  skip ok: ${fromAddr}`);
      return true;
    }
    const r = await api("PUT", `/zones/${zid}/email/routing/rules/${rule.id}`, body);
    console.log(`  update ${fromAddr}:`, r.success ? "OK" : r.errors);
    return r.success;
  }

  const r = await api("POST", `/zones/${zid}/email/routing/rules`, body);
  console.log(`  create ${fromAddr}:`, r.success ? "OK" : r.errors);
  return r.success;
}

async function removeSameDomainForwards() {
  const rules = await api("GET", `/zones/${zid}/email/routing/rules`);
  let removed = 0;
  for (const rule of rules.result || []) {
    const fwd = rule.actions?.find((a) => a.type === "forward");
    if (!fwd) continue;
    const dest = fwd.value?.[0];
    const to = rule.matchers?.find((m) => m.field === "to")?.value;
    if (!dest || !to) continue;
    const destLower = dest.toLowerCase();
    const toLower = to.toLowerCase();
    const sameDomain =
      destLower.endsWith(MATARIKI_DOMAIN) && toLower.endsWith(MATARIKI_DOMAIN) && destLower === toLower;
    if (!sameDomain) continue;
    const r = await api("DELETE", `/zones/${zid}/email/routing/rules/${rule.id}`);
    if (r.success) {
      console.log(`  removed same-domain loop: ${to} → ${dest}`);
      removed++;
    } else {
      console.log(`  failed remove ${to}:`, r.errors);
    }
  }
  return removed;
}

async function ensureCatchAllDisabled() {
  const rules = await api("GET", `/zones/${zid}/email/routing/rules`);
  for (const rule of rules.result || []) {
    const isCatchAll = !rule.matchers?.some((m) => m.field === "to");
    if (!isCatchAll) continue;
    if (!rule.enabled) {
      console.log("  catch-all: already disabled (OK)");
      return;
    }
    const r = await api("PUT", `/zones/${zid}/email/routing/rules/${rule.id}`, {
      ...rule,
      enabled: false,
    });
    console.log(`  catch-all drop disabled:`, r.success ? "OK" : r.errors);
  }
}

console.log("\nRemove same-domain forward loops (matarikigroup → matarikigroup):");
await removeSameDomainForwards();

console.log("\nWorker rule (accounts@):");
await upsertRule("xero-accounts", "accounts@matarikigroup.co.nz", [
  { type: "worker", value: [WORKER] },
]);

console.log("\nPersonal inbox forwards (cross-domain → gillespie.kiwi Google Workspace):");
for (const { name, addr, dest } of PERSONAL_FORWARDS) {
  const d = destByEmail.get(dest.toLowerCase());
  if (!d?.verified) {
    console.log(`  skip ${addr}: verify ${dest} in Cloudflare Email → Destination addresses`);
    continue;
  }
  await upsertRule(name, addr, [{ type: "forward", value: [dest] }]);
}

console.log("\nCatch-all:");
await ensureCatchAllDisabled();

console.log("\nFinal rules:");
const rules = await api("GET", `/zones/${zid}/email/routing/rules`);
for (const r of rules.result || []) {
  const to = r.matchers?.find((m) => m.field === "to")?.value;
  const action = (r.actions || [])
    .map((a) => `${a.type}:${Array.isArray(a.value) ? a.value.join(",") : a.value}`)
    .join("; ");
  console.log(`  enabled=${r.enabled} to=${to || "(catch-all)"} => ${action}`);
}

console.log(`
Done. ${GILLESPIE_ZONE} Email Routing must remain OFF (Google MX).

Same-domain forward warning: NEVER configure david@matarikigroup → david@matarikigroup
while Cloudflare MX is active — it always loops (521 / 550 too many forwards).

Unverified gillespie destinations: click the verification link Cloudflare emailed, then re-run.
`);

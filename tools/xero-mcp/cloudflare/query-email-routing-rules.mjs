/**
 * List Email Routing rules + destination addresses for a zone.
 * Run on tower: CLOUDFLARE_API_TOKEN=… node query-email-routing-rules.mjs [zone]
 */
const token = process.env.CLOUDFLARE_API_TOKEN;
const ZONE_NAME = process.argv[2] || "matarikigroup.co.nz";

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

const zones = await api("GET", `/zones?name=${ZONE_NAME}`);
const zone = zones.result?.[0];
if (!zone) {
  console.error(`Zone not found: ${ZONE_NAME}`);
  process.exit(1);
}
const zid = zone.id;
console.log(`Zone: ${zone.name} (${zid})`);

const routing = await api("GET", `/zones/${zid}/email/routing`);
console.log(`Routing: enabled=${routing.result?.enabled} status=${routing.result?.status}`);

const rules = await api("GET", `/zones/${zid}/email/routing/rules`);
console.log(`Rules (${(rules.result || []).length}):`);
for (const r of rules.result || []) {
  const to = r.matchers?.find((m) => m.field === "to")?.value;
  const action = (r.actions || [])
    .map((a) => `${a.type}:${Array.isArray(a.value) ? a.value.join(",") : a.value}`)
    .join("; ");
  console.log(`  [${r.id}] enabled=${r.enabled} name=${r.name} to=${to} => ${action}`);
}

const ACCOUNT_ID = process.env.CF_ACCOUNT_ID || "6b75f8187544327aba3ac88047b7fb92";
const dests = await api("GET", `/accounts/${ACCOUNT_ID}/email/routing/addresses?per_page=50`);
console.log(`Destination addresses (${(dests.result || []).length}):`);
for (const d of dests.result || []) {
  console.log(`  ${d.email} verified=${d.verified ? "yes" : "no"}`);
}

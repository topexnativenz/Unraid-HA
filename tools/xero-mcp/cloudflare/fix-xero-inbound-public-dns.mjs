/**
 * Ensure xero-inbound.gillespie.kiwi is reachable from Cloudflare edge (Email Worker fetch).
 * Wildcard *.gillespie.kiwi → 192.168.1.7 is LAN-only; Workers cannot reach RFC1918.
 *
 * Run on tower: CLOUDFLARE_API_TOKEN=… node fix-xero-inbound-public-dns.mjs
 */
const token = process.env.CLOUDFLARE_API_TOKEN;
const ZONE_NAME = process.env.XERO_DNS_ZONE || "gillespie.kiwi";
const HOSTNAME = process.env.XERO_WEBHOOK_HOST || "xero-inbound.gillespie.kiwi";
const TUNNEL_ID = process.env.CLOUDFLARE_TUNNEL_ID || "f7333fc4-04bc-447c-9040-ce0a6a1ba711";
const TUNNEL_CNAME = `${TUNNEL_ID}.cfargotunnel.com`;
const ACCOUNT_ID = process.env.CLOUDFLARE_ACCOUNT_ID || "6b75f8187544327aba3ac88047b7fb92";

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
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { success: false, errors: [{ message: `${res.status} ${text.slice(0, 200)}` }] };
  }
}

function fail(msg) {
  console.error(msg);
  process.exit(1);
}

const zones = await api("GET", `/zones?name=${ZONE_NAME}`);
const zone = zones.result?.[0];
if (!zone) {
  fail(`Zone ${ZONE_NAME} not found or token lacks Zone:Read`);
}
const zid = zone.id;
console.log(`Zone ${zone.name} (${zid})`);

const existing = await api("GET", `/zones/${zid}/dns_records?name=${HOSTNAME}`);
if (!existing.success) {
  console.error("DNS list failed:", existing.errors);
  console.log(`
Manual fix (API token needs Zone DNS Edit on ${ZONE_NAME}):

1. Cloudflare → ${ZONE_NAME} → DNS → Add record
   Type: CNAME  Name: xero-inbound  Target: ${TUNNEL_CNAME}  Proxy: ON

2. Zero Trust → Networks → Tunnels → marshal-home → Public Hostname
   Hostname: ${HOSTNAME}  Path: (empty)  Service: https://192.168.1.7:443
   Additional: No TLS Verify ON

3. Verify: curl -s https://${HOSTNAME}/health
   DoH must NOT return 192.168.1.7:
   curl -s 'https://cloudflare-dns.com/dns-query?name=${HOSTNAME}&type=A' -H 'accept: application/dns-json'
`);
  process.exit(1);
}

const records = existing.result || [];
const bad = records.filter((r) => r.type === "A" && r.content === "192.168.1.7");
const cname = records.find((r) => r.type === "CNAME" && r.content === TUNNEL_CNAME && r.proxied);

if (cname) {
  console.log(`OK: proxied CNAME ${HOSTNAME} → ${TUNNEL_CNAME} (id ${cname.id})`);
} else {
  for (const r of bad) {
    console.log(`Deleting LAN-only A record ${r.id} (${r.content})`);
    const del = await api("DELETE", `/zones/${zid}/dns_records/${r.id}`);
    console.log("  delete:", del.success ? "OK" : del.errors);
  }
  const body = {
    type: "CNAME",
    name: HOSTNAME,
    content: TUNNEL_CNAME,
    proxied: true,
    ttl: 1,
  };
  const create = await api("POST", `/zones/${zid}/dns_records`, body);
  if (!create.success) {
    console.error("CNAME create failed:", create.errors);
    process.exit(1);
  }
  console.log(`Created CNAME ${HOSTNAME} → ${TUNNEL_CNAME} (proxied)`);
}

// Tunnel public hostname (requires Account → Cloudflare Tunnel Edit)
const cfg = await api(
  "GET",
  `/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/configurations`
);
if (!cfg.success) {
  console.warn("Tunnel config API:", cfg.errors?.[0]?.message || "failed");
  console.log(`
Add tunnel public hostname manually:
  ${HOSTNAME} → https://192.168.1.7:443 (No TLS Verify ON)
`);
  process.exit(0);
}

const ingress = cfg.result?.config?.ingress || [];
const hasHost = ingress.some((r) => r.hostname === HOSTNAME);
if (hasHost) {
  console.log(`OK: tunnel ingress includes ${HOSTNAME}`);
} else {
  const base = ingress.filter((r) => !r.service?.includes("http_status"));
  const catchAll = ingress.find((r) => r.service?.includes("http_status"));
  const updated = [
    ...base,
    {
      hostname: HOSTNAME,
      service: "https://192.168.1.7:443",
      originRequest: { noTLSVerify: true },
    },
    catchAll || { service: "http_status:404" },
  ];
  const put = await api(
    "PUT",
    `/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/configurations`,
    { config: { ingress: updated } }
  );
  if (!put.success) {
    console.warn("Tunnel ingress update failed:", put.errors);
    console.log(`Add public hostname manually: ${HOSTNAME} → https://192.168.1.7:443`);
  } else {
    console.log(`Added tunnel ingress for ${HOSTNAME}`);
  }
}

const routing = await api("GET", `/zones/${zid}/email/routing`);
if (routing.result?.enabled) {
  const rules = await api("GET", `/zones/${zid}/email/routing/rules`);
  const forwards = (rules.result || []).filter((r) =>
    r.actions?.some((a) => a.type === "forward" || a.type === "worker")
  );
  if (forwards.length === 0) {
    console.warn(`
WARNING: Email Routing is enabled on ${ZONE_NAME} but no forward/worker rules exist.
Personal mail (david@/genna@) will be dropped. Run restore-native-google-inboxes.mjs
or disable Email Routing in the dashboard (Xero webhook does not need it).
`);
  }
}

console.log(`\nVerify: curl -sf https://${HOSTNAME}/health`);

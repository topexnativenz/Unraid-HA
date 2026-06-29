/**
 * Recent Email Routing activity (GraphQL). Run on tower with CLOUDFLARE_API_TOKEN.
 */
const token = process.env.CLOUDFLARE_API_TOKEN;
const zoneName = process.argv[2] || process.env.CF_ZONE || "matarikigroup.co.nz";
const since = process.env.SINCE || "2026-06-03T00:00:00Z";

async function zoneTagFor(name) {
  if (process.env.CF_ZONE_TAG) return process.env.CF_ZONE_TAG;
  const res = await fetch(`https://api.cloudflare.com/client/v4/zones?name=${encodeURIComponent(name)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  const z = data.result?.[0];
  if (!z) throw new Error(`Zone not found: ${name}`);
  return z.id;
}

const zoneTag = await zoneTagFor(zoneName);

if (!token) {
  console.error("Set CLOUDFLARE_API_TOKEN");
  process.exit(1);
}

const query = `
query EmailActivity($zoneTag: string, $filter: EmailRoutingAdaptiveFilter_InputObject) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      emailRoutingAdaptive(filter: $filter, limit: 20, orderBy: [datetime_DESC]) {
        datetime
        from
        to
        subject
        status
        action
        errorDetail
      }
    }
  }
}`;

const res = await fetch("https://api.cloudflare.com/client/v4/graphql", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    query,
    variables: {
      zoneTag,
      filter: { datetime_geq: since },
    },
  }),
});

const data = await res.json();
if (data.errors?.length) {
  console.error("GraphQL errors:", JSON.stringify(data.errors, null, 2));
  process.exit(1);
}

const rows =
  data?.data?.viewer?.zones?.[0]?.emailRoutingAdaptive ?? [];
console.log(`Zone: ${zoneName} (${zoneTag})`);
console.log(`Email routing events since ${since}: ${rows.length}\n`);
for (const r of rows) {
  const subj = (r.subject || "").slice(0, 70);
  const err = r.errorDetail ? ` | ${r.errorDetail}` : "";
  console.log(`${r.datetime} | ${r.to} | ${r.status} | ${r.action} | ${subj}${err}`);
}

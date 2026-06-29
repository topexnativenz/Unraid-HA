/**
 * Restore gillespie.kiwi personal inboxes — disable Cloudflare Email Routing.
 *
 * Same-domain forward rules (david@matarikigroup → david@matarikigroup) cause 521 loops
 * while Cloudflare MX is active. Hybrid uses cross-domain forward to gillespie.kiwi instead.
 *
 * Xero inbound uses HTTP (xero-inbound.gillespie.kiwi) — no email routing needed.
 *
 * Run on tower: CLOUDFLARE_API_TOKEN=… node restore-gillespie-inbox-routing.mjs
 */
console.log("Restoring native Google inboxes on gillespie.kiwi (+ matarikigroup.co.nz)…\n");
await import("./restore-native-google-inboxes.mjs");

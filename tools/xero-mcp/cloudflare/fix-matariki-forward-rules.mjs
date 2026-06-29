/**
 * Emergency fix: remove matarikigroup same-domain forward loops and apply cross-domain
 * forwards to verified @gillespie.kiwi destinations.
 *
 * Same as setup-email-routing.mjs (idempotent). Use when Activity shows:
 *   521 5.3.0 Upstream error
 *   550 5.4.6 Email was forwarded too many times
 *
 * Run on tower: CLOUDFLARE_API_TOKEN=… node fix-matariki-forward-rules.mjs
 */
console.log("Fixing matarikigroup forward loops (same-domain → cross-domain gillespie)…\n");
await import("./setup-email-routing.mjs");

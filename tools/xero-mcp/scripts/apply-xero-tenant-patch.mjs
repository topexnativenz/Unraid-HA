#!/usr/bin/env node
/**
 * Copy tenant-aware xero-client.js into the local @xeroapi/xero-mcp-server install.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const source = path.join(repoRoot, "patches", "xero-client.js");
const target = path.join(
  repoRoot,
  "node_modules",
  "@xeroapi",
  "xero-mcp-server",
  "dist",
  "clients",
  "xero-client.js",
);

if (!fs.existsSync(source)) {
  console.error(`Missing patch source: ${source}`);
  process.exit(1);
}
if (!fs.existsSync(target)) {
  console.error(`Missing xero-mcp-server install at ${target} — run: npm install`);
  process.exit(1);
}

fs.copyFileSync(source, target);
console.log("Applied Xero tenant patch ->", target);

import assert from "node:assert/strict";
import { describe, it, beforeEach, afterEach } from "node:test";
import worker, {
  acceptWithFallback,
  forwardInboxCopy,
  inboxCopyAddresses,
  INBOX_COPY_SUBJECT_PREFIX,
} from "./worker.js";

function mockMessage(subject = "Supplier invoice INV-1001") {
  const headers = new Headers({ subject });
  const forwards = [];
  return {
    to: "accounts@matarikigroup.co.nz",
    from: "billing@supplier.co.nz",
    headers,
    raw: new TextEncoder().encode(
      [
        "From: billing@supplier.co.nz",
        "To: accounts@matarikigroup.co.nz",
        `Subject: ${subject}`,
        "Content-Type: text/plain; charset=utf-8",
        "",
        "Please find attached invoice.",
      ].join("\r\n")
    ),
    forward(target, fwdHeaders) {
      forwards.push({ target, subject: fwdHeaders.get("subject") });
    },
    forwards,
  };
}

describe("inboxCopyAddresses", () => {
  it("defaults to david@gillespie.kiwi", () => {
    assert.deepEqual(inboxCopyAddresses({}), ["david@gillespie.kiwi"]);
  });

  it("parses comma-separated INBOX_COPY_TO", () => {
    assert.deepEqual(
      inboxCopyAddresses({ INBOX_COPY_TO: "david@gillespie.kiwi, genna@gillespie.kiwi" }),
      ["david@gillespie.kiwi", "genna@gillespie.kiwi"]
    );
  });

  it("returns empty when INBOX_COPY_TO is blank", () => {
    assert.deepEqual(inboxCopyAddresses({ INBOX_COPY_TO: "  " }), []);
  });
});

describe("forwardInboxCopy", () => {
  it("forwards with [accounts@ copy] subject prefix", () => {
    const message = mockMessage("Council rates Q2");
    forwardInboxCopy(message, {});
    assert.equal(message.forwards.length, 1);
    assert.equal(message.forwards[0].target, "david@gillespie.kiwi");
    assert.equal(
      message.forwards[0].subject,
      `${INBOX_COPY_SUBJECT_PREFIX} Council rates Q2`
    );
  });

  it("forwards to every configured inbox", () => {
    const message = mockMessage();
    forwardInboxCopy(message, {
      INBOX_COPY_TO: "david@gillespie.kiwi,genna@gillespie.kiwi",
    });
    assert.equal(message.forwards.length, 2);
    assert.deepEqual(
      message.forwards.map((item) => item.target),
      ["david@gillespie.kiwi", "genna@gillespie.kiwi"]
    );
  });
});

describe("acceptWithFallback", () => {
  it("forwards with [XERO-INBOUND-FALLBACK] prefix on tower failure", () => {
    const message = mockMessage("Overdue bill");
    acceptWithFallback(message, {}, "tower webhook HTTP 524");
    assert.equal(message.forwards.length, 1);
    assert.equal(message.forwards[0].target, "david@gillespie.kiwi");
    assert.equal(message.forwards[0].subject, "[XERO-INBOUND-FALLBACK] Overdue bill");
  });
});

describe("email handler", () => {
  /** @type {typeof globalThis.fetch} */
  let originalFetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("forwards inbox copy after successful tower POST", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ ok: true, queued: [{ status: "pending" }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });

    const message = mockMessage("Live supplier bill");
    await worker.email(message, {
      WEBHOOK_URL: "https://xero-inbound.example.test",
      WEBHOOK_SECRET: "test-secret",
    });

    assert.equal(message.forwards.length, 1);
    assert.equal(message.forwards[0].target, "david@gillespie.kiwi");
    assert.match(message.forwards[0].subject, /^\[accounts@ copy\]/);
  });

  it("uses fallback forward (not inbox copy) when tower POST fails", async () => {
    globalThis.fetch = async () =>
      new Response("upstream error", { status: 500 });

    const message = mockMessage("Tower down test");
    await worker.email(message, {
      WEBHOOK_URL: "https://xero-inbound.example.test",
      WEBHOOK_SECRET: "test-secret",
    });

    assert.equal(message.forwards.length, 1);
    assert.match(message.forwards[0].subject, /^\[XERO-INBOUND-FALLBACK\]/);
    assert.doesNotMatch(message.forwards[0].subject, /^\[accounts@ copy\]/);
  });
});

describe("zero-bounce policy", () => {
  it("worker.js never calls setReject", async () => {
    const fs = await import("node:fs/promises");
    const source = await fs.readFile(new URL("./worker.js", import.meta.url), "utf8");
    const withoutComments = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    assert.doesNotMatch(withoutComments, /\bsetReject\s*\(/);
  });
});

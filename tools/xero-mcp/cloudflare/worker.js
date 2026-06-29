/**
 * Cloudflare Email Worker — forwards inbound mail to the tower webhook (xero-inbound).
 * Zero-bounce policy: never call setReject(); forward to fallback inbox on tower failure.
 * Deploy on tower: deploy-cloudflare-xero-inbound.sh
 */
import PostalMime from "postal-mime";

const MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024;
const MAX_JSON_BYTES = 9 * 1024 * 1024;
const MAX_RAW_BASE64_BYTES = 6 * 1024 * 1024;
const MAX_NEST_DEPTH = 8;
const DEFAULT_FALLBACK_TO = "david@gillespie.kiwi";
const DEFAULT_INBOX_COPY_TO = "david@gillespie.kiwi";
const INBOX_COPY_SUBJECT_PREFIX = "[accounts@ copy]";
const RETRYABLE_HTTP_STATUSES = new Set([524, 502, 503]);
const MAX_TOWER_RETRIES = 3; // retries after first attempt (4 POSTs total)

const PARSE_OPTIONS = {
  attachmentEncoding: "base64",
  rfc822Attachments: true,
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function fallbackAddress(env) {
  const raw = (env?.FALLBACK_TO || DEFAULT_FALLBACK_TO).trim();
  const first = raw.split(",")[0]?.trim();
  return first || DEFAULT_FALLBACK_TO;
}

function inboxCopyAddresses(env) {
  const raw = (env?.INBOX_COPY_TO ?? DEFAULT_INBOX_COPY_TO).trim();
  if (!raw) return [];
  return raw
    .split(",")
    .map((addr) => addr.trim())
    .filter(Boolean);
}

function forwardWithSubjectPrefix(message, target, prefix, subject) {
  const headers = new Headers(message.headers);
  const prefixed = `${prefix} ${subject}`.slice(0, 998);
  headers.set("subject", prefixed);
  message.forward(target, headers);
}

function bytesToBase64(bytes) {
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < u8.length; i += chunk) {
    binary += String.fromCharCode.apply(null, u8.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function contentToArrayBuffer(content) {
  if (content instanceof ArrayBuffer) return content;
  if (content instanceof Uint8Array) return content.buffer.slice(content.byteOffset, content.byteOffset + content.byteLength);
  if (typeof content === "string") {
    const binary = atob(content);
    const out = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
    return out.buffer;
  }
  return null;
}

function attachmentByteSize(att) {
  if (typeof att.content === "string") {
    return Math.floor((att.content.length * 3) / 4);
  }
  if (att.content instanceof ArrayBuffer) return att.content.byteLength;
  if (att.content instanceof Uint8Array) return att.content.length;
  return 0;
}

function inferFilename(att) {
  const filename = att.filename || "";
  if (filename && filename !== "attachment") return filename;
  const mime = (att.mimeType || "").toLowerCase();
  if (mime.includes("wordprocessingml")) return "attachment.docx";
  if (mime.includes("spreadsheetml")) return "attachment.xlsx";
  if (mime === "application/msword") return "attachment.doc";
  if (mime === "application/pdf") return "attachment.pdf";
  if (mime === "message/rfc822") return "forwarded.eml";
  return "attachment";
}

function isLikelySignatureAttachment(att) {
  const filename = inferFilename(att).toLowerCase();
  if (/^image\d+\.(png|jpe?g|gif)$/.test(filename)) return true;
  if (/(logo|signature|sig\.|sig_|footer|header|banner|icon|linkedin|facebook)/.test(filename)) {
    return true;
  }
  const size = attachmentByteSize(att);
  if (/\.(png|jpe?g|gif)$/.test(filename) && size < 80000) return true;
  return false;
}

function isBillFilename(filename) {
  return /\.(pdf|docx?|xlsx?)$/i.test(filename || "");
}

function isBillAttachment(att) {
  return isBillFilename(inferFilename(att));
}

function attachmentSummary(attachments) {
  return attachments
    .map((att) => {
      const name = inferFilename(att);
      const type = att.mimeType || "application/octet-stream";
      const size = attachmentByteSize(att);
      return `${name} (${type}, ${size}b)`;
    })
    .join("; ");
}

function attachmentToPayload(att) {
  const filename = inferFilename(att);
  const content_type = att.mimeType || "application/octet-stream";
  let data_base64;
  if (typeof att.content === "string") {
    data_base64 = att.content;
  } else if (att.content instanceof ArrayBuffer) {
    data_base64 = bytesToBase64(new Uint8Array(att.content));
  } else if (att.content instanceof Uint8Array) {
    data_base64 = bytesToBase64(att.content);
  } else {
    return null;
  }
  const size = Math.floor((data_base64.length * 3) / 4);
  if (size > MAX_ATTACHMENT_BYTES) {
    console.warn(`skip oversized attachment ${filename} (${size} bytes)`);
    return null;
  }
  return { filename, content_type, data_base64 };
}

async function collectAttachmentsRecursive(rawBytes, depth = 0) {
  if (depth > MAX_NEST_DEPTH) return [];

  const parsed = await PostalMime.parse(rawBytes, PARSE_OPTIONS);
  const collected = [];

  for (const att of parsed.attachments || []) {
    const mime = (att.mimeType || "").toLowerCase();
    const filename = inferFilename(att).toLowerCase();

    if (mime === "message/rfc822" || filename.endsWith(".eml")) {
      const nestedRaw = contentToArrayBuffer(att.content);
      if (nestedRaw) {
        const nested = await collectAttachmentsRecursive(nestedRaw, depth + 1);
        collected.push(...nested);
      }
      continue;
    }

    collected.push(att);
  }

  return collected;
}

function dedupePayloadAttachments(items) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    const payload = attachmentToPayload(item);
    if (!payload) continue;
    const key = `${payload.filename}:${payload.data_base64.length}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(payload);
  }
  return out;
}

function payloadHasBillFile(attachments) {
  return attachments.some((item) => isBillFilename(item.filename));
}

function trimAttachmentsForPayload(payload) {
  const current = payload.attachments || [];
  if (current.length === 0) return payload;

  const billLike = current.filter((item) => isBillAttachment({ filename: item.filename }));
  const signatures = current.filter((item) => isLikelySignatureAttachment({ filename: item.filename }));

  if (billLike.length > 0 && signatures.length > 0) {
    payload.attachments = billLike;
    console.warn(
      `trimmed signature attachments, kept bills: ${billLike.map((a) => a.filename).join(", ")}`
    );
    return payload;
  }

  if (signatures.length > 0 && current.length > signatures.length) {
    payload.attachments = current.filter((item) => !signatures.includes(item));
    console.warn(`dropped ${signatures.length} signature/logo attachment(s) for payload size`);
    return payload;
  }

  if (current.length > 1) {
    const sorted = [...current].sort(
      (a, b) => (b.data_base64?.length || 0) - (a.data_base64?.length || 0)
    );
    const largest = sorted[0];
    if (!isBillFilename(largest?.filename)) {
      payload.attachments = sorted.slice(1);
      console.warn(`dropped largest non-bill attachment ${largest?.filename} for payload size`);
      return payload;
    }
    if (billLike.length > 0 && billLike.length < current.length) {
      payload.attachments = billLike;
      console.warn(
        `kept bill attachments only: ${billLike.map((a) => a.filename).join(", ")}`
      );
      return payload;
    }
  }

  return payload;
}

function resolveFrom(parsed, message) {
  const from = parsed?.from;
  if (typeof from === "string") return from;
  if (from?.address) return from.address;
  if (Array.isArray(from) && from[0]?.address) return from[0].address;
  return message.from;
}

async function buildPayload(message) {
  const raw = await new Response(message.raw).arrayBuffer();
  const rawBytes = new Uint8Array(raw);
  const parsed = await PostalMime.parse(raw, PARSE_OPTIONS);

  const allAttachments = await collectAttachmentsRecursive(raw);
  const attachments = dedupePayloadAttachments(allAttachments);

  console.log(
    `parsed attachments (${allAttachments.length} raw, ${attachments.length} payload): ${attachmentSummary(allAttachments)}`
  );

  const payload = {
    to: message.to,
    cc: message.headers.get("cc") || "",
    from: resolveFrom(parsed, message),
    subject: parsed.subject || message.headers.get("subject") || "",
    text: (parsed.text || "").slice(0, 16000),
    attachments,
  };

  const needsRawFallback =
    !payloadHasBillFile(attachments) &&
    (/\b(?:attached|please find|enclosed|see attached|file attached)\b/i.test(payload.text || "") ||
      /\binvoice\s+inv[-\s]?/i.test(payload.subject || "") ||
      /\binv[-\s]?\d{4,}/i.test(payload.subject || "") ||
      /\b(?:invoice|bill)\s+inv[-\s]?[\w-]+\s+from\s+/i.test(payload.subject || "") ||
      /payment\s+reminder/i.test(payload.text || "") ||
      /post\.xero\.com/i.test(payload.text || ""));

  if (needsRawFallback && rawBytes.length <= MAX_RAW_BASE64_BYTES) {
    payload.raw_base64 = bytesToBase64(rawBytes);
    console.warn(
      `including raw_base64 (${rawBytes.length}b) for tower MIME re-parse — no bill file in postal-mime output`
    );
  }

  return payload;
}

function minimalPayload(message, partial = null) {
  return {
    to: message.to,
    cc: message.headers.get("cc") || "",
    from: partial?.from || message.from || "",
    subject: partial?.subject || message.headers.get("subject") || "",
    text: (partial?.text || message.headers.get("subject") || "").slice(0, 16000),
    attachments: [],
    worker_fallback: "minimal-payload",
  };
}

async function postToTower(payload, env, trimAttempt = 0, retryAttempt = 0) {
  const url = `${env.WEBHOOK_URL.replace(/\/$/, "")}/inbound/cloudflare`;
  const body = JSON.stringify(payload);
  if (body.length > MAX_JSON_BYTES) {
    if (payload.attachments.length === 0 && !payload.raw_base64) {
      return {
        ok: false,
        reason: `payload too large (${body.length} bytes) even without attachments`,
        retryable: false,
      };
    }
    if (trimAttempt >= 5) {
      return {
        ok: false,
        reason: `payload too large (${body.length} bytes) after attachment trimming`,
        retryable: false,
      };
    }
    console.warn(
      `payload too large (${body.length} bytes), trimming attachments subject=${(payload.subject || "").slice(0, 80)}`
    );
    if (payload.raw_base64 && trimAttempt >= 2) {
      delete payload.raw_base64;
      console.warn("dropped raw_base64 to fit payload size limit");
    } else {
      trimAttachmentsForPayload(payload);
    }
    return postToTower(payload, env, trimAttempt + 1, retryAttempt);
  }

  let resp;
  let text;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Xero-Inbound-Secret": env.WEBHOOK_SECRET,
      },
      body,
    });
    text = await resp.text();
  } catch (err) {
    if (retryAttempt < MAX_TOWER_RETRIES) {
      const delayMs = 1500 * 2 ** retryAttempt;
      console.warn(
        `tower network error (retry ${retryAttempt + 1}/${MAX_TOWER_RETRIES}): ${err?.message || err} subject=${(payload.subject || "").slice(0, 80)}`
      );
      await sleep(delayMs);
      return postToTower(payload, env, trimAttempt, retryAttempt + 1);
    }
    return {
      ok: false,
      reason: `tower network error: ${err?.message || err}`,
      retryable: false,
    };
  }

  if (RETRYABLE_HTTP_STATUSES.has(resp.status) && retryAttempt < MAX_TOWER_RETRIES) {
    const delayMs = 1500 * 2 ** retryAttempt;
    console.warn(
      `tower HTTP ${resp.status} (retry ${retryAttempt + 1}/${MAX_TOWER_RETRIES}) subject=${(payload.subject || "").slice(0, 80)}`
    );
    await sleep(delayMs);
    return postToTower(payload, env, trimAttempt, retryAttempt + 1);
  }

  if (!resp.ok) {
    const detail =
      resp.status === 524
        ? "tower webhook timed out (HTTP 524)"
        : text.slice(0, 200);
    return {
      ok: false,
      status: resp.status,
      text,
      reason: `tower webhook HTTP ${resp.status}: ${detail}`,
      retryable: false,
    };
  }

  let result = {};
  try {
    result = JSON.parse(text);
  } catch {
    /* ok */
  }

  return { ok: true, result, text, payload };
}

function forwardInboxCopy(message, env) {
  const subject = message.headers.get("subject") || "";
  const targets = inboxCopyAddresses(env);
  for (const target of targets) {
    try {
      forwardWithSubjectPrefix(message, target, INBOX_COPY_SUBJECT_PREFIX, subject);
      console.log(`forwarded inbox copy to ${target} subject=${subject.slice(0, 80)}`);
    } catch (forwardErr) {
      console.error(
        `inbox copy forward to ${target} failed: ${forwardErr?.message || forwardErr} — tower ingest already accepted`
      );
    }
  }
}

function acceptWithFallback(message, env, reason) {
  const subject = message.headers.get("subject") || "";
  const msg = String(reason || "xero-inbound failure").slice(0, 500);
  console.error(`accept-with-fallback: ${msg}`);
  const target = fallbackAddress(env);
  try {
    forwardWithSubjectPrefix(message, target, "[XERO-INBOUND-FALLBACK]", subject);
    console.log(`forwarded fallback to ${target} subject=${subject.slice(0, 80)}`);
  } catch (forwardErr) {
    console.error(
      `fallback forward to ${target} failed: ${forwardErr?.message || forwardErr} — accepting without NDR`
    );
  }
}

async function ingestViaTower(message, env, payload) {
  const first = await postToTower(payload, env);
  if (first.ok) {
    return first;
  }

  if (first.reason?.includes("payload too large")) {
    console.warn(`retrying tower with minimal payload subject=${(payload.subject || "").slice(0, 80)}`);
    const minimal = minimalPayload(message, payload);
    const second = await postToTower(minimal, env);
    if (second.ok) {
      return second;
    }
    return second;
  }

  return first;
}

export {
  acceptWithFallback,
  fallbackAddress,
  forwardInboxCopy,
  inboxCopyAddresses,
  INBOX_COPY_SUBJECT_PREFIX,
};

export default {
  async email(message, env) {
    const subject = message.headers.get("subject") || "";
    let payload = null;

    try {
      if (!env?.WEBHOOK_URL || !env?.WEBHOOK_SECRET) {
        acceptWithFallback(
          message,
          env,
          "xero-inbound misconfigured: missing WEBHOOK_URL or WEBHOOK_SECRET"
        );
        return;
      }

      try {
        payload = await buildPayload(message);
      } catch (parseErr) {
        console.error(
          `attachment parse error (continuing minimal): ${parseErr?.message || parseErr} subject=${subject.slice(0, 80)}`
        );
        payload = minimalPayload(message);
      }

      const names = payload.attachments.map((a) => a.filename).join(", ") || "(none)";
      const types = payload.attachments.map((a) => a.content_type).join(", ") || "(none)";
      const ingest = await ingestViaTower(message, env, payload);

      if (!ingest.ok) {
        acceptWithFallback(
          message,
          env,
          `${ingest.reason} subject=${subject.slice(0, 80)}`
        );
        return;
      }

      forwardInboxCopy(message, env);

      const result = ingest.result || {};
      const queued = result?.queued;
      if (result?.ok === false) {
        console.warn(
          `xero-inbound tower soft-fail: ${result.error || "unknown"} subject=${subject.slice(0, 80)}`
        );
      }
      if (Array.isArray(queued)) {
        const failed = queued.find((item) => item?.status === "failed");
        if (failed) {
          console.warn(`xero-inbound queued failed: ${failed.error} subject=${subject.slice(0, 80)}`);
        } else {
          console.log(
            `xero-inbound ok: count=${payload.attachments.length} raw_fallback=${Boolean(payload.raw_base64)} files=[${names}] types=[${types}] subject=${subject.slice(0, 80)}`
          );
        }
      } else if (result?.ok !== false) {
        console.log(
          `xero-inbound ok: count=${payload.attachments.length} raw_fallback=${Boolean(payload.raw_base64)} files=[${names}] types=[${types}] subject=${subject.slice(0, 80)}`
        );
      }
    } catch (err) {
      acceptWithFallback(
        message,
        env,
        `xero-inbound error: ${err?.message || err} subject=${subject.slice(0, 80)}`
      );
    }
  },
};

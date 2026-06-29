from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from xero_mcp.audit import audit_event
from xero_mcp.inbound.config import INBOUND_DIR, QUEUE_DIR, ensure_inbound_dirs, load_inbound_config
from xero_mcp.inbound.attachment_recovery import (
    _record_has_bill_attachment,
    recover_missing_bill_attachment,
)
from xero_mcp.inbound.extract import _parse_xero_invoice_subject
from xero_mcp.inbound.parser import _prior_done_bill_still_active, load_queue_record, save_queue_record
from xero_mcp.inbound.processor import process_message

HEAL_LAST_REPORT = INBOUND_DIR / "heal-last.json"

DEFAULT_RETRYABLE_PATTERNS: tuple[str, ...] = (
    r"429",
    r"rate.?limit",
    r"too many requests",
    r"timeout",
    r"timed out",
    r"connection (?:reset|refused|error)",
    r"503",
    r"502",
    r"504",
    r"temporarily unavailable",
    r"Xero .* failed \(5\d{2}\)",
)

DEFAULT_CONFIG_PATTERNS: tuple[str, ...] = (
    r"re-?auth",
    r"token refresh failed",
    r"Missing .*credentials",
    r"Unknown inbound message",
    r"not in connected organisations",
    r"Active tenant",
)

DEFAULT_PERMANENT_PATTERNS: tuple[str, ...] = (
    r"Duplicate of a previously processed",
    r"newsletter",
    r"marketing/notification",
    r"blocked.?sender",
    r"not actionable",
    r"bill gate",
    r"rejected",
)

_VALIDATION_RETRY_HINTS: tuple[str, ...] = (
    r"ValidationException",
    r"validation exception",
    r"InvoiceNumber",
    r"not of valid status",
    r"Account code",
    r"TaxType",
    r"UnitAmount",
    r"LineAmount",
)


class HealAction(str, Enum):
    SKIP = "skip"
    RETRY_NOW = "retry_now"
    RETRY_LATER = "retry_later"
    NEEDS_PDF = "needs_pdf"
    DUPLICATE_OK = "duplicate_ok"
    CONFIG = "config"
    PERMANENT = "permanent"


@dataclass(frozen=True)
class HealConfig:
    enabled: bool
    pending_max_age_sec: float
    processing_max_age_sec: float
    done_missing_bill_grace_sec: float
    max_attempts: int
    min_interval_sec: float
    retryable_patterns: tuple[re.Pattern[str], ...]
    config_patterns: tuple[re.Pattern[str], ...]
    permanent_patterns: tuple[re.Pattern[str], ...]


@dataclass
class HealDiagnosis:
    message_id: str
    status: str
    action: HealAction
    reason: str
    error: str | None = None
    subject: str | None = None
    org_slug: str | None = None
    heal_attempts: int = 0
    last_heal_at: float | None = None


def _compile_patterns(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


def load_heal_config() -> HealConfig:
    from xero_mcp.inbound.config import INBOUND_CONFIG_FILE

    data: dict[str, Any] = {}
    if INBOUND_CONFIG_FILE.exists():
        data = json.loads(INBOUND_CONFIG_FILE.read_text())
    heal = data.get("heal") if isinstance(data.get("heal"), dict) else {}

    def patterns(key: str, default: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
        raw = heal.get(key)
        if isinstance(raw, list) and raw:
            return _compile_patterns(tuple(str(p) for p in raw))
        return _compile_patterns(default)

    return HealConfig(
        enabled=bool(heal.get("enabled", True)),
        pending_max_age_sec=float(heal.get("pending_max_age_sec", 900)),
        processing_max_age_sec=float(heal.get("processing_max_age_sec", 600)),
        done_missing_bill_grace_sec=float(heal.get("done_missing_bill_grace_sec", 120)),
        max_attempts=int(heal.get("max_attempts", 5)),
        min_interval_sec=float(heal.get("min_interval_sec", 300)),
        retryable_patterns=patterns("retryable_error_patterns", DEFAULT_RETRYABLE_PATTERNS),
        config_patterns=patterns("config_error_patterns", DEFAULT_CONFIG_PATTERNS),
        permanent_patterns=patterns("permanent_error_patterns", DEFAULT_PERMANENT_PATTERNS),
    )


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(text) for p in patterns)


def _record_age_sec(record: dict[str, Any], *, field: str = "received_at") -> float:
    ts = record.get(field) or record.get("received_at") or 0
    try:
        return max(0.0, time.time() - float(ts))
    except (TypeError, ValueError):
        return 0.0


def _has_xero_bill(record: dict[str, Any]) -> bool:
    if record.get("xero_invoice_id"):
        return True
    ids = record.get("xero_invoice_ids") or []
    return bool(ids)


def _has_complete_xero_bill(record: dict[str, Any]) -> bool:
    """True when a linked Xero draft has amounts or a bill PDF (not a $0 shell)."""
    if not _has_xero_bill(record):
        return False
    if _record_has_bill_attachment(record):
        return True
    extracted = record.get("extracted") or {}
    total = extracted.get("total")
    if total is not None and float(total) > 0:
        return True
    xero_result = record.get("xero_result") or {}
    if isinstance(xero_result, dict):
        result_total = xero_result.get("total")
        if result_total is not None and float(result_total) > 0:
            return True
        bills = xero_result.get("bills")
        if isinstance(bills, list):
            for bill in bills:
                if isinstance(bill, dict) and float(bill.get("total") or 0) > 0:
                    return True
    return False


def _error_text(record: dict[str, Any]) -> str:
    parts = [record.get("error") or ""]
    gate = record.get("bill_gate") or {}
    if gate.get("reason"):
        parts.append(str(gate["reason"]))
    rejection = record.get("rejection") or {}
    if rejection.get("reason"):
        parts.append(str(rejection["reason"]))
    return " ".join(p for p in parts if p).strip()


def _validation_error_retryable(error: str) -> bool:
    """400 ValidationException after a code fix may succeed on force reprocess."""
    if not error:
        return False
    lower = error.lower()
    if "validationexception" not in lower and "validation exception" not in lower:
        return False
    if "duplicate" in lower or "already exists" in lower:
        return False
    return True


def classify_failure(error: str | None, record: dict[str, Any]) -> HealAction:
    """Map queue state + error text to a heal action."""
    cfg = load_heal_config()
    status = str(record.get("status") or "")
    err = (error or _error_text(record)).strip()

    if status == "rejected":
        return HealAction.PERMANENT

    if status == "duplicate":
        for path in QUEUE_DIR.glob("*.json"):
            if path.stem == record.get("id"):
                continue
            try:
                other = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            if other.get("dedupe_key") != record.get("dedupe_key"):
                continue
            if other.get("status") == "done" and not _prior_done_bill_still_active(other):
                return HealAction.DUPLICATE_OK
        return HealAction.SKIP

    if err and _matches_any(err, cfg.permanent_patterns):
        return HealAction.PERMANENT

    if err and _validation_error_retryable(err):
        return HealAction.RETRY_NOW

    if err and _matches_any(err, cfg.config_patterns):
        return HealAction.CONFIG

    missing_pdf_markers = (
        "no bill attachments",
        "no allowed attachments",
        "no attachment on queued",
        "only signature/logo",
    )
    if err and any(m in err.lower() for m in missing_pdf_markers):
        subject = str(record.get("subject") or "")
        if _parse_xero_invoice_subject(subject):
            return HealAction.RETRY_NOW
        return HealAction.NEEDS_PDF
    if record.get("attachment_warning") and status in ("failed", "pending"):
        return HealAction.NEEDS_PDF

    if status == "done":
        if _has_complete_xero_bill(record):
            return HealAction.SKIP
        if record.get("xero_link_resolution", {}).get("resolved"):
            return HealAction.SKIP
        age = _record_age_sec(record, field="processed_at")
        if age < cfg.done_missing_bill_grace_sec:
            return HealAction.RETRY_LATER
        return HealAction.RETRY_NOW

    if status == "processing":
        age = _record_age_sec(record, field="received_at")
        if age >= cfg.processing_max_age_sec:
            return HealAction.RETRY_NOW
        return HealAction.RETRY_LATER

    if status == "pending":
        age = _record_age_sec(record, field="received_at")
        if age >= cfg.pending_max_age_sec:
            return HealAction.RETRY_NOW
        return HealAction.RETRY_LATER

    if status == "failed":
        if err and _matches_any(err, cfg.retryable_patterns):
            return HealAction.RETRY_NOW
        if err and _validation_error_retryable(err):
            return HealAction.RETRY_NOW
        if err and _matches_any(err, cfg.config_patterns):
            return HealAction.CONFIG
        if err and _matches_any(err, cfg.permanent_patterns):
            return HealAction.PERMANENT
        return HealAction.RETRY_NOW

    return HealAction.SKIP


def _diagnose_record(record: dict[str, Any]) -> HealDiagnosis:
    action = classify_failure(_error_text(record) or None, record)
    reason = action.value
    err = _error_text(record) or None

    if action == HealAction.SKIP and record.get("status") == "done" and _has_complete_xero_bill(record):
        reason = "done_with_bill"
    elif action == HealAction.RETRY_LATER:
        reason = f"cooldown_or_young_{record.get('status')}"
    elif action == HealAction.NEEDS_PDF:
        reason = "missing_bill_attachment"
    elif action == HealAction.DUPLICATE_OK:
        reason = "prior_duplicate_bill_deleted"
    elif err:
        reason = err[:200]

    return HealDiagnosis(
        message_id=str(record.get("id") or ""),
        status=str(record.get("status") or ""),
        action=action,
        reason=reason,
        error=err,
        subject=(record.get("subject") or "")[:120] or None,
        org_slug=record.get("org_slug"),
        heal_attempts=int(record.get("heal_attempts") or 0),
        last_heal_at=record.get("last_heal_at"),
    )


def iter_queue_records() -> list[dict[str, Any]]:
    ensure_inbound_dirs()
    records: list[dict[str, Any]] = []
    for path in QUEUE_DIR.glob("*.json"):
        try:
            records.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return records


def scan_queue(*, limit: int | None = None) -> list[HealDiagnosis]:
    """Return diagnoses for queue items that may need attention (non-healthy)."""
    cfg = load_heal_config()
    if not cfg.enabled:
        return []

    candidates: list[HealDiagnosis] = []
    for record in iter_queue_records():
        diagnosis = _diagnose_record(record)
        if diagnosis.action == HealAction.SKIP:
            continue
        candidates.append(diagnosis)

    candidates.sort(
        key=lambda d: (
            0 if d.action == HealAction.RETRY_NOW else 1,
            0 if d.action == HealAction.DUPLICATE_OK else 1,
            -(d.heal_attempts),
        ),
    )
    if limit is not None and limit > 0:
        candidates = candidates[:limit]
    return candidates


def _heal_cooldown_ok(record: dict[str, Any], cfg: HealConfig) -> bool:
    last = record.get("last_heal_at")
    if last is None:
        return True
    try:
        return (time.time() - float(last)) >= cfg.min_interval_sec
    except (TypeError, ValueError):
        return True


def _bump_heal_meta(record: dict[str, Any]) -> None:
    record["heal_attempts"] = int(record.get("heal_attempts") or 0) + 1
    record["last_heal_at"] = time.time()


def _reset_processing_stuck(record: dict[str, Any]) -> None:
    if record.get("status") == "processing":
        record["status"] = "pending"
        record.pop("processed_at", None)


def heal_record(message_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Attempt to heal one queue record; uses force reprocess when safe."""
    cfg = load_heal_config()
    record = load_queue_record(message_id)
    diagnosis = _diagnose_record(record)

    base = {
        "message_id": message_id,
        "dry_run": dry_run,
        "diagnosis": diagnosis.action.value,
        "reason": diagnosis.reason,
        "status_before": record.get("status"),
        "heal_attempts": int(record.get("heal_attempts") or 0),
    }

    if diagnosis.action == HealAction.NEEDS_PDF:
        if recover_missing_bill_attachment(record):
            save_queue_record(record)
            diagnosis = _diagnose_record(record)
            base["recovered_attachment"] = True
            if diagnosis.action == HealAction.NEEDS_PDF:
                base["skipped"] = True
                base["reason"] = "missing_bill_attachment"
                return base
        else:
            base["skipped"] = True
            base["reason"] = "missing_bill_attachment"
            return base

    if diagnosis.action in (HealAction.SKIP, HealAction.PERMANENT, HealAction.CONFIG):
        base["skipped"] = True
        return base

    if diagnosis.action == HealAction.RETRY_LATER:
        base["skipped"] = True
        base["reason"] = "retry_later_cooldown"
        return base

    if int(record.get("heal_attempts") or 0) >= cfg.max_attempts:
        base["skipped"] = True
        base["reason"] = "max_heal_attempts"
        return base

    if not _heal_cooldown_ok(record, cfg):
        base["skipped"] = True
        base["reason"] = "heal_min_interval"
        return base

    if diagnosis.action == HealAction.SKIP:
        base["skipped"] = True
        return base

    use_force = diagnosis.action in (
        HealAction.RETRY_NOW,
        HealAction.DUPLICATE_OK,
    ) or (
        record.get("status") == "done" and not _has_xero_bill(record)
    )

    if dry_run:
        base["would_heal"] = True
        base["force"] = use_force
        return base

    _bump_heal_meta(record)
    _reset_processing_stuck(record)
    save_queue_record(record)

    try:
        result = process_message(message_id, force=use_force)
    except Exception as exc:
        audit_event("inbound_heal_failed", id=message_id, error=str(exc))
        return {**base, "ok": False, "error": str(exc)}

    ok = bool(result.get("ok"))
    audit_event(
        "inbound_heal",
        id=message_id,
        ok=ok,
        force=use_force,
        status_after=(result.get("record") or {}).get("status"),
        error=result.get("error"),
    )
    return {
        **base,
        "ok": ok,
        "force": use_force,
        "result": {
            "ok": result.get("ok"),
            "error": result.get("error"),
            "status": (result.get("record") or {}).get("status"),
            "xero_invoice_id": (result.get("record") or {}).get("xero_invoice_id"),
        },
    }


def run_heal(*, dry_run: bool = False, limit: int = 10) -> dict[str, Any]:
    """Scan and heal up to `limit` candidates; writes heal-last.json summary."""
    cfg = load_heal_config()
    scanned = scan_queue(limit=None)
    actionable = [d for d in scanned if d.action in (HealAction.RETRY_NOW, HealAction.DUPLICATE_OK)]
    if limit > 0:
        actionable = actionable[:limit]

    results: list[dict[str, Any]] = []
    for diagnosis in actionable:
        results.append(heal_record(diagnosis.message_id, dry_run=dry_run))
        if not dry_run:
            load_inbound_config()
            delay = __import__(
                "xero_mcp.inbound.config", fromlist=["effective_process_delay_sec"]
            ).effective_process_delay_sec(load_inbound_config())
            if delay > 0:
                time.sleep(delay)

    summary = {
        "ts": time.time(),
        "dry_run": dry_run,
        "enabled": cfg.enabled,
        "candidates": len(scanned),
        "attempted": len(actionable),
        "healed_ok": sum(1 for r in results if r.get("ok")),
        "skipped": sum(1 for r in results if r.get("skipped")),
        "results": results,
        "by_action": _count_by_action(scanned),
    }
    if not dry_run:
        _write_heal_report(summary)
    return summary


def _count_by_action(diagnoses: list[HealDiagnosis]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for d in diagnoses:
        counts[d.action.value] = counts.get(d.action.value, 0) + 1
    return counts


def health_summary(*, scan_limit: int = 50) -> dict[str, Any]:
    """Failed/stuck summary for MCP and CLI."""
    cfg = load_heal_config()
    all_diagnoses = scan_queue(limit=None)
    shown = all_diagnoses[:scan_limit] if scan_limit else all_diagnoses
    return {
        "heal_enabled": cfg.enabled,
        "config": {
            "pending_max_age_sec": cfg.pending_max_age_sec,
            "processing_max_age_sec": cfg.processing_max_age_sec,
            "max_attempts": cfg.max_attempts,
            "min_interval_sec": cfg.min_interval_sec,
        },
        "candidate_count": len(all_diagnoses),
        "by_action": _count_by_action(all_diagnoses),
        "candidates": [
            {
                "message_id": d.message_id,
                "status": d.status,
                "action": d.action.value,
                "reason": d.reason,
                "subject": d.subject,
                "org_slug": d.org_slug,
                "heal_attempts": d.heal_attempts,
                "error": (d.error or "")[:300] or None,
            }
            for d in shown
        ],
        "last_report": _read_heal_report(),
    }


def _write_heal_report(summary: dict[str, Any]) -> None:
    ensure_inbound_dirs()
    HEAL_LAST_REPORT.write_text(json.dumps(summary, indent=2) + "\n")
    try:
        HEAL_LAST_REPORT.chmod(0o600)
    except OSError:
        pass


def _read_heal_report() -> dict[str, Any] | None:
    if not HEAL_LAST_REPORT.exists():
        return None
    try:
        return json.loads(HEAL_LAST_REPORT.read_text())
    except json.JSONDecodeError:
        return None

"""Tests for Xero API rate-limit retry and inbound process staggering."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from xero_mcp.inbound.config import InboundConfig, effective_process_delay_sec
from xero_mcp.inbound.xero_http import xero_request


def _minimal_inbound_config(**overrides: object) -> InboundConfig:
    base = dict(
        domain="matarikigroup.co.nz",
        webhook_secret="",
        webhook_port=8766,
        auto_process=True,
        process_delay_sec=2.0,
        default_document_type="ACCPAY",
        default_status="DRAFT",
        allowed_extensions=(".pdf",),
        routes=(),
        intake_addresses=(),
        allowed_from=(),
        default_intake_address="accounts@matarikigroup.co.nz",
        routing_mode="portfolio",
        default_org_slug="matariki-property-group",
        require_attachment=True,
        require_bill_classification=True,
        min_bill_confidence=0.55,
        bill_classifier_mode="heuristic",
        allow_xero_links=True,
        allow_xero_link_without_attachment=True,
        allow_email_body_without_attachment=True,
        blocked_sender_domains=(),
    )
    base.update(overrides)
    return InboundConfig(**base)


class XeroRequestRetryTests(unittest.TestCase):
    def test_retries_429_then_succeeds(self) -> None:
        client = MagicMock()
        ok = httpx.Response(200, json={"Contacts": []})
        rate_limited = httpx.Response(429, headers={"Retry-After": "0"})
        client.request.side_effect = [rate_limited, ok]

        with patch("xero_mcp.inbound.xero_http.time.sleep") as sleep:
            resp = xero_request(
                client,
                "GET",
                "https://api.xero.com/api.xro/2.0/Contacts",
                max_retries=3,
                max_total_wait_sec=60.0,
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(client.request.call_count, 2)
        sleep.assert_called_once()

    def test_returns_429_after_max_retries(self) -> None:
        client = MagicMock()
        rate_limited = httpx.Response(429, headers={})
        client.request.return_value = rate_limited

        with patch("xero_mcp.inbound.xero_http.time.sleep"):
            resp = xero_request(
                client,
                "GET",
                "https://api.xero.com/api.xro/2.0/Contacts",
                max_retries=2,
                max_total_wait_sec=120.0,
            )

        self.assertEqual(resp.status_code, 429)
        self.assertEqual(client.request.call_count, 3)


class ProcessDelayConfigTests(unittest.TestCase):
    def test_env_overrides_inbound_json(self) -> None:
        config = _minimal_inbound_config(process_delay_sec=1.5)
        with patch.dict("os.environ", {"XERO_INBOUND_PROCESS_DELAY_SEC": "3"}):
            self.assertEqual(effective_process_delay_sec(config), 3.0)

    def test_uses_config_when_env_unset(self) -> None:
        config = _minimal_inbound_config(process_delay_sec=1.25)
        with patch.dict("os.environ", {}, clear=True):
            import os

            os.environ.pop("XERO_INBOUND_PROCESS_DELAY_SEC", None)
            self.assertEqual(effective_process_delay_sec(config), 1.25)


class ProcessQueuedRecordsTests(unittest.TestCase):
    @patch("xero_mcp.inbound.processor._process_message_impl")
    @patch("xero_mcp.inbound.processor.effective_process_delay_sec", return_value=0.5)
    @patch("xero_mcp.inbound.processor.load_inbound_config")
    @patch("xero_mcp.inbound.processor.time.sleep")
    def test_staggers_pending_records(
        self,
        mock_sleep: MagicMock,
        mock_load: MagicMock,
        _mock_delay: MagicMock,
        mock_process: MagicMock,
    ) -> None:
        from xero_mcp.inbound.processor import process_queued_records

        mock_load.return_value = _minimal_inbound_config()
        mock_process.side_effect = [{"ok": True}, {"ok": True}, {"ok": True}]
        records = [
            {"id": "a", "status": "pending"},
            {"id": "b", "status": "pending"},
            {"id": "c", "status": "pending"},
            {"id": "d", "status": "done"},
        ]

        results = process_queued_records(records)

        self.assertEqual(len(results), 3)
        self.assertEqual(mock_process.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(0.5)

"""Tests for document text extraction, signatures, and attachment ranking."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import Any
import zipfile

from xero_mcp.inbound.attachments import (
    collect_bill_attachment_files,
    is_signature_image,
    rank_bill_attachments,
)
from xero_mcp.inbound.bill_gate import is_actionable_bill
from xero_mcp.inbound.document_text import extract_docx_text, extract_text_from_attachment
from xero_mcp.inbound.email_signatures import best_signature_contact, extract_signature_contacts
from xero_mcp.inbound.extract import (
    _parse_xero_invoice_subject,
    build_bill_reference,
    build_line_description,
    email_from_header,
    extract_from_email,
    extract_xero_reminder_fields,
    has_actionable_email_bill,
    is_xero_reminder_email,
    merge_extraction,
    parse_extracted_text,
)
from unittest.mock import patch

from xero_mcp.inbound.bill_splits import (
    build_split_dedupe_key,
    format_invoice_hint,
    invoice_number_from_filename,
    split_inbound_into_bills,
)
from xero_mcp.inbound.config import InboundConfig
from xero_mcp.inbound.extract import (
    coalesce_pdf_invoice_sections,
    merge_extraction,
    parse_extracted_text,
    split_extracted_text_by_invoices,
)
from xero_mcp.inbound.parser import (
    InboundAttachment,
    ParsedInboundEmail,
    _resolve_recipient,
    parse_cloudflare_json,
    parse_eml_bytes,
)
from xero_mcp.inbound.xero_contacts import normalize_contact_name, _contact_payload
from xero_mcp.inbound.xero_links import (
    XeroLink,
    _extract_invoice_id,
    detect_xero_links,
    group_xero_links_for_bills,
    primary_xero_link,
)


def make_docx(*lines: str) -> bytes:
    text = "\n".join(lines)
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buf.getvalue()


SAMPLE_INVOICE = """
ACME Plumbing Ltd
123 Main Street
Auckland 1010
Phone: 09 555 1234
Email: billing@acmeplumbing.co.nz

TAX INVOICE
Invoice Number: INV-2024-991
Invoice Date: 15/03/2024
Due Date: 29/03/2024

Callout fee          1    120.00    120.00
Parts replacement    2     45.50     91.00

Subtotal                        211.00
GST (15%)                        31.65
Total                           242.65

Payment overdue after due date.
"""

WDC_DOCX_TEXT = """
Whangarei District Council
Development Contribution Invoice
Reference: DCPM2500002
Invoice date: 01/04/2024
Due date: 15/04/2024
Total amount due: $12,345.67
"""

CAROLINE_FORWARD_BODY = """
Hi team,

Please process the attached development contribution invoice for Logyard Road.

Kind regards,
David

From: Caroline Ngata <caroline.ngata@wdc.govt.nz>
Sent: Monday, 1 April 2024
Subject: Development Contribution Invoice

Caroline Ngata
Development Contributions Officer
Whangarei District Council
Private Bag 9023
Whangarei 0148
Phone: 09 430 4200
caroline.ngata@wdc.govt.nz
"""

COUNCIL_FORWARD_BODY = """
Whangarei District Council
Development Contribution for Logyard Road subdivision
Reference: DCPM2500002
Invoice date: 01/04/2024
Due date: 15/04/2024
Total amount due: $12,345.67
"""

BIGGEST_LITTLE_BODY = """
From: Biggest Little Digger <invoicereminders@post.xero.com>
Date: Wednesday, 3 June 2026 at 7:37 AM
Subject: Bill INV-00001769 from Biggest Little Digger Limited is due

Payment Reminder
Biggest Little Digger Limited
$2,074.72 NZD
Overdue - 20 May 2026
Invoice #: INV-00001769
View invoice<https://in.xero.com/U8b6mek8Laro784fVY3CQEB3RJaRAdmq5xsPN8?utm_source=reminderEmailViewInvoiceButton>

Thanks for working with us. Your bill for $2,074.72 was due on 20 May 2026.
To view your bill visit https://in.xero.com/U8b6mek8Laro784fVY3CQEB3RJaRAdmq5xsPN8
Download PDF<https://in.xero.com/U8b6mek8Laro784fVY3CQEB3RJaRAdmq5xsPN8/Invoice/DownloadPdf/9d4ca9ea-aac6-45f4-94dc-8785050ef8a8?utm_source=remindersEmailUrl>
"""


class DocumentTextTests(unittest.TestCase):
    def test_extract_docx_text(self) -> None:
        data = make_docx("Whangarei District Council", "Reference: DCPM2500002", "Total: $500.00")
        text = extract_docx_text(data)
        self.assertIn("Whangarei District Council", text)
        self.assertIn("DCPM2500002", text)

    def test_merge_extraction_from_docx_attachment(self) -> None:
        docx = make_docx(*WDC_DOCX_TEXT.strip().splitlines())
        fields = merge_extraction(
            from_address="David <david@matarikigroup.co.nz>",
            subject="FW: Development Contribution - Logyard Road",
            body_text=CAROLINE_FORWARD_BODY,
            attachment_bytes=docx,
            attachment_name="contribution.docx",
        )
        self.assertEqual(fields.supplier_name, "Whangarei District Council")
        self.assertEqual(fields.invoice_number, "DCPM2500002")
        self.assertAlmostEqual(fields.total or 0, 12345.67)
        self.assertEqual(fields.contact_person, "Caroline Ngata")
        self.assertEqual(fields.supplier_email, "caroline.ngata@wdc.govt.nz")
        self.assertEqual(fields.phone, "09 430 4200")


class SignatureTests(unittest.TestCase):
    def test_caroline_wdc_signature(self) -> None:
        contact = best_signature_contact(CAROLINE_FORWARD_BODY)
        self.assertIsNotNone(contact)
        assert contact is not None
        self.assertEqual(contact.organization, "Whangarei District Council")
        self.assertEqual(contact.person_name, "Caroline Ngata")
        self.assertEqual(contact.email, "caroline.ngata@wdc.govt.nz")
        self.assertEqual(contact.phone, "09 430 4200")
        self.assertEqual(contact.city, "Whangarei")
        self.assertEqual(contact.postal_code, "0148")

    def test_forward_from_header_parsed(self) -> None:
        contacts = extract_signature_contacts(CAROLINE_FORWARD_BODY)
        emails = {c.email for c in contacts if c.email}
        self.assertIn("caroline.ngata@wdc.govt.nz", emails)


class ExtractTests(unittest.TestCase):
    def test_parse_invoice_fields(self) -> None:
        fields = parse_extracted_text(SAMPLE_INVOICE)
        self.assertEqual(fields.supplier_name, "ACME Plumbing Ltd")
        self.assertEqual(fields.invoice_number, "INV-2024-991")
        self.assertEqual(fields.invoice_date, "2024-03-15")
        self.assertEqual(fields.due_date, "2024-03-29")
        self.assertAlmostEqual(fields.total or 0, 242.65)
        self.assertAlmostEqual(fields.subtotal or 0, 211.0)
        self.assertAlmostEqual(fields.tax_amount or 0, 31.65)
        self.assertTrue(fields.is_overdue)
        self.assertGreaterEqual(len(fields.line_items), 2)
        self.assertEqual(fields.supplier_email, "billing@acmeplumbing.co.nz")
        self.assertEqual(fields.phone, "09 555 1234")
        self.assertEqual(fields.address_line1, "123 Main Street")
        self.assertEqual(fields.city, "Auckland")
        self.assertEqual(fields.postal_code, "1010")

    def test_swimming_academy_payment_advice_invoice(self) -> None:
        text = """
PAYMENT ADVICE
To: Whangarei Academy of Swimming
PO Box 283
Whangarei 0140
NEW ZEALAND
Customer Gillespie (Imogen)
Invoice Number INV-5859
Amount Due 60.00
Due Date 20 May 2026
TAX INVOICE
Gillespie (Imogen)
Invoice Date
20 May 2026
Invoice Number
INV-5859
Reference
Beanies
Whangarei Academy of
Swimming
PO Box 283
Whangarei 0140
NEW ZEALAND
Description Quantity Unit Price Amount NZD
New Club Beanie 2.00 30.00 60.00
Subtotal 60.00
TOTAL NZD 60.00
Due Date: 20 May 2026
Email: treasurerwasc@gmail.com
"""
        fields = parse_extracted_text(text)
        self.assertEqual(fields.supplier_name, "Whangarei Academy of Swimming")
        self.assertEqual(fields.invoice_number, "INV-5859")
        self.assertAlmostEqual(fields.total or 0, 60.0)
        self.assertAlmostEqual(fields.subtotal or 0, 60.0)
        self.assertEqual(fields.line_amount_types, "NoTax")
        self.assertIsNone(fields.tax_rate_label)
        self.assertEqual(len(fields.line_items), 1)
        item = fields.line_items[0]
        self.assertEqual(item.description, "New Club Beanie")
        self.assertAlmostEqual(item.quantity, 2.0)
        self.assertAlmostEqual(item.unit_amount, 30.0)
        self.assertEqual(fields.supplier_email, "treasurerwasc@gmail.com")

    def test_hainesco_payment_advice_labour_hours_qty(self) -> None:
        text = """
PAYMENT ADVICE
To: HAINESCO/Haines Masonry ltd
54 Mangakino Lane
Kauri
Whangarei 0185
mark@hainesco.co.nz
TAX INVOICE
Matariki Property Group
Invoice Date 30 Apr 2026
Invoice Number INV-1517
GST Number 121979187
HAINESCO/Haines Masonry
ltd
Description Quantity Unit Price Amount NZD
Labour for March and April at Logyard road 157.00 65.00 10,205.00
Subtotal 10,205.00
TOTAL GST 15% 1,530.75
TOTAL NZD 11,735.75
Due Date: 20 May 2026
"""
        fields = parse_extracted_text(text)
        self.assertEqual(fields.supplier_name, "Haines Masonry ltd")
        self.assertAlmostEqual(fields.total or 0, 11735.75)
        self.assertEqual(len(fields.line_items), 1)
        item = fields.line_items[0]
        self.assertIn("Labour", item.description)
        self.assertAlmostEqual(item.quantity, 157.0)
        self.assertAlmostEqual(item.unit_amount, 65.0)

        pdf = Path(__file__).resolve().parent / "fixtures" / "hainesco" / "INV-1517.pdf"
        if pdf.exists():
            pdf_fields = parse_extracted_text(
                extract_text_from_attachment(pdf.read_bytes(), pdf.name)
            )
            self.assertEqual(pdf_fields.invoice_number, "INV-1517")
            self.assertEqual(len(pdf_fields.line_items), 1)

    def test_vital_signs_multiline_qty_unit_ex_gst(self) -> None:
        """PDF splits description and qty/price rows (INV-15841-style)."""
        text = """
Vital Signs Northland Ltd
TAX INVOICE
Invoice Number INV-15841
Description Quantity Unit Price Amount NZD
1x small acm sign
MAX STORAGE
1.00 90.00 90.00
Subtotal 90.00
TOTAL GST 15% 13.50
TOTAL NZD 103.50
"""
        fields = parse_extracted_text(text)
        self.assertEqual(len(fields.line_items), 1)
        item = fields.line_items[0]
        self.assertIn("acm sign", item.description)
        self.assertIn("MAX STORAGE", item.description)
        self.assertAlmostEqual(item.quantity, 1.0)
        self.assertAlmostEqual(item.unit_amount, 90.0)
        self.assertAlmostEqual(fields.subtotal or 0, 90.0)
        self.assertAlmostEqual(fields.total or 0, 103.5)

    def test_dual_column_prefers_exclusive_unit_price(self) -> None:
        text = """
Supplier Ltd
TAX INVOICE
Description Qty Unit Excl GST Incl
Widget 2 50.00 15.00 115.00
Subtotal 100.00
GST 15.00
Amount including GST 115.00
"""
        fields = parse_extracted_text(text)
        self.assertEqual(len(fields.line_items), 1)
        item = fields.line_items[0]
        self.assertAlmostEqual(item.quantity, 2.0)
        self.assertAlmostEqual(item.unit_amount, 50.0)

    def test_inclusive_only_unit_derived_to_exclusive(self) -> None:
        text = """
Supplier Ltd
Description Quantity Unit Price Amount
Service call 1 103.50 103.50
Subtotal 90.00
GST 13.50
TOTAL NZD 103.50
"""
        fields = parse_extracted_text(text)
        self.assertEqual(len(fields.line_items), 1)
        self.assertAlmostEqual(fields.line_items[0].unit_amount, 90.0, places=2)

    def test_wdc_forward_body_actionable_without_pdf(self) -> None:
        body = """
From: Caroline Blakeley <Caroline.Blakeley@wdc.govt.nz>
Date: Tuesday, 19 May 2026 at 11:47 AM
Morena David
Attached is the DC invoice for BC2401256. I can confirm it is for $39 036.34.
Caroline Blakeley
Development Contributions Officer | Infrastructure Planning
Whangarei District Council | Te Iwitahi, 9 Rust Avenue
"""
        subject = (
            "FW: Development Contributions — DCPM2500002 / PM2401256 — "
            "26 Logyard Road — Reconsideration Request and Payment Proposal"
        )
        fields = extract_from_email(
            subject=subject,
            body_text=body,
            from_address="accounts@matarikigroup.co.nz",
        )
        self.assertEqual(fields.supplier_name, "Whangarei District Council")
        self.assertAlmostEqual(fields.total or 0, 39036.34)
        self.assertEqual(fields.invoice_date, "2026-05-19")
        self.assertIsNone(fields.due_date)
        self.assertTrue(
            has_actionable_email_bill(subject=subject, body_text=body, from_address="accounts@matarikigroup.co.nz")
        )

    def test_wdc_docx_labeled_dates(self) -> None:
        fields = parse_extracted_text(WDC_DOCX_TEXT)
        self.assertEqual(fields.invoice_date, "2024-04-01")
        self.assertEqual(fields.due_date, "2024-04-15")

    def test_due_date_not_guessed_from_email_thread(self) -> None:
        body = """
Invoice date: 01/04/2024
Sent: Monday, May 18, 2026 2:33:15 PM
From: someone@example.com
Date: Friday, 15 May 2026 at 5:38 PM
"""
        inv, due = extract_from_email(subject="Invoice", body_text=body).invoice_date, extract_from_email(
            subject="Invoice", body_text=body
        ).due_date
        self.assertEqual(inv, "2024-04-01")
        self.assertIsNone(due)


class ContactMergeTests(unittest.TestCase):
    def test_prefers_pdf_supplier_email_over_sender(self) -> None:
        fields = parse_extracted_text(SAMPLE_INVOICE)
        fields.sender_email = email_from_header("Accounts Payable <notify@mail.xero.com>")
        fields.contact_email = fields.supplier_email or fields.sender_email
        self.assertEqual(fields.supplier_name, "ACME Plumbing Ltd")
        self.assertEqual(fields.supplier_email, "billing@acmeplumbing.co.nz")
        self.assertEqual(fields.sender_email, "notify@mail.xero.com")
        self.assertEqual(fields.contact_email, "billing@acmeplumbing.co.nz")

    def test_falls_back_to_sender_email(self) -> None:
        minimal_pdf = b""
        fields = merge_extraction(
            from_address="Billing Team <billing@supplier.co.nz>",
            subject="Invoice",
            body_text="",
            attachment_bytes=minimal_pdf,
        )
        self.assertEqual(fields.contact_email, "billing@supplier.co.nz")
        self.assertEqual(fields.sender_email, "billing@supplier.co.nz")

    def test_email_from_header(self) -> None:
        self.assertEqual(
            email_from_header('"ACME Ltd" <billing@acme.co.nz>'),
            "billing@acme.co.nz",
        )


class ContactNormalizeTests(unittest.TestCase):
    def test_normalize_strips_ltd(self) -> None:
        self.assertEqual(
            normalize_contact_name("ACME Plumbing Ltd"),
            normalize_contact_name("ACME Plumbing Limited"),
        )

    def test_contact_payload_includes_address_and_phone(self) -> None:
        fields = parse_extracted_text(SAMPLE_INVOICE)
        fields.contact_email = fields.supplier_email
        payload = _contact_payload(fields)
        self.assertEqual(payload["Name"], "ACME Plumbing Ltd")
        self.assertEqual(payload["EmailAddress"], "billing@acmeplumbing.co.nz")
        self.assertEqual(payload["Phones"][0]["PhoneNumber"], "09 555 1234")
        self.assertEqual(payload["Addresses"][0]["AddressLine1"], "123 Main Street")
        self.assertEqual(payload["Addresses"][0]["City"], "Auckland")
        self.assertEqual(payload["Addresses"][0]["PostalCode"], "1010")


class BillGateTests(unittest.TestCase):
    def test_accepts_pdf_invoice(self) -> None:
        result = is_actionable_bill(
            subject="Tax invoice INV-991 - Logyard Road",
            body_text="Please find attached invoice.",
            from_address="billing@acmeplumbing.co.nz",
            attachment_names=["invoice.pdf"],
            extracted_text=SAMPLE_INVOICE,
        )
        self.assertTrue(result.is_bill)
        self.assertGreaterEqual(result.confidence, 0.55)

    def test_accepts_docx_attachment(self) -> None:
        result = is_actionable_bill(
            subject="FW: Development Contribution",
            body_text=CAROLINE_FORWARD_BODY,
            from_address="david@matarikigroup.co.nz",
            attachment_names=["invoice.docx", "image001.png"],
            extracted_text=WDC_DOCX_TEXT,
        )
        self.assertTrue(result.is_bill)

    def test_rejects_newsletter(self) -> None:
        result = is_actionable_bill(
            subject="March newsletter — unsubscribe anytime",
            body_text="View in browser. You are receiving this email because you subscribed.",
            from_address="news@supplier.co.nz",
            attachment_names=[],
        )
        self.assertFalse(result.is_bill)

    def test_rejects_payment_confirmation(self) -> None:
        result = is_actionable_bill(
            subject="Payment received — thank you",
            body_text="Thank you for your payment. No action is required.",
            from_address="noreply@bank.co.nz",
            attachment_names=[],
        )
        self.assertFalse(result.is_bill)

    def test_accepts_xero_link_without_pdf(self) -> None:
        body = "View bill: https://go.xero.com/AccountsPayable/View.aspx?InvoiceID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        result = is_actionable_bill(
            subject="New bill from Supplier Ltd",
            body_text=body,
            from_address="notify@mail.xero.com",
            attachment_names=[],
        )
        self.assertTrue(result.is_bill)


class CouncilForwardTests(unittest.TestCase):
    def test_extracts_council_supplier_from_forwarded_body(self) -> None:
        fields = extract_from_email(
            subject="FW: Development Contribution Payment Invoice - Logyard Road",
            body_text=COUNCIL_FORWARD_BODY,
            from_address="David Gillespie <david@matarikigroup.co.nz>",
        )
        self.assertEqual(fields.supplier_name, "Whangarei District Council")
        self.assertEqual(fields.invoice_number, "DCPM2500002")
        self.assertAlmostEqual(fields.total or 0, 12345.67)
        self.assertEqual(fields.invoice_date, "2024-04-01")
        self.assertEqual(fields.due_date, "2024-04-15")

    def test_internal_sender_not_used_as_contact(self) -> None:
        fields = merge_extraction(
            from_address="Accounts <accounts@matarikigroup.co.nz>",
            subject="FW: Invoice",
            body_text=COUNCIL_FORWARD_BODY,
            attachment_bytes=b"",
        )
        self.assertEqual(fields.supplier_name, "Whangarei District Council")
        self.assertNotIn("Matarikigroup", fields.supplier_name or "")


class AttachmentRankTests(unittest.TestCase):
    def test_pdf_preferred_over_signature_png(self) -> None:
        attachments = [
            InboundAttachment(name="image001.png", content_type="image/png", data=b"x" * 5000),
            InboundAttachment(name="invoice.pdf", content_type="application/pdf", data=b"%PDF" + b"y" * 50000),
        ]
        ranked = rank_bill_attachments(attachments)
        self.assertEqual(ranked[0].name, "invoice.pdf")

    def test_docx_preferred_over_signature_png(self) -> None:
        docx = make_docx("Invoice total $100.00")
        attachments = [
            InboundAttachment(name="image001.png", content_type="image/png", data=b"x" * 5000),
            InboundAttachment(name="contribution.docx", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", data=docx),
        ]
        ranked = rank_bill_attachments(attachments)
        self.assertEqual(ranked[0].name, "contribution.docx")

    def test_signature_image_detected(self) -> None:
        self.assertTrue(is_signature_image("image001.png", 5000, "image/png"))
        self.assertFalse(is_signature_image("scan-invoice.png", 150000, "image/png"))

    def test_extract_text_from_attachment_docx(self) -> None:
        docx = make_docx("Tax Invoice", "Total amount due: $99.00")
        text = extract_text_from_attachment(docx, "bill.docx")
        self.assertIn("Tax Invoice", text)
        self.assertIn("99.00", text)

    def test_collect_bill_files_skips_signature_keeps_docx_and_pdf(self) -> None:
        docx = make_docx("Invoice", "Total: $100")
        attachments = [
            {"name": "image001.png", "size": 13988, "content_type": "image/png"},
            {"name": "invoice.docx", "size": len(docx), "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            {"name": "backup.pdf", "size": 50000, "content_type": "application/pdf"},
        ]
        blobs = {
            "image001.png": b"png",
            "invoice.docx": docx,
            "backup.pdf": b"%PDF",
        }

        def read(item: dict) -> bytes:
            return blobs[item["name"]]

        files = collect_bill_attachment_files(attachments, read_bytes=read)
        names = [name for name, _ in files]
        self.assertEqual(names, ["backup.pdf", "invoice.docx"])
        self.assertNotIn("image001.png", names)


class GennaForwardIntakeTests(unittest.TestCase):
    def _config(self) -> InboundConfig:
        return _test_inbound_config()

    def test_genna_gillespie_to_accounts_direct(self) -> None:
        parsed = ParsedInboundEmail(
            to_addresses=["accounts@matarikigroup.co.nz"],
            from_address="Genna Gillespie <genna@gillespie.kiwi>",
            subject="FW: Tax invoice INV-1001",
            attachments=[InboundAttachment("invoice.pdf", "application/pdf", b"%PDF-1.4")],
        )
        matched_to, route = _resolve_recipient(parsed, self._config())
        self.assertEqual(matched_to, "accounts@matarikigroup.co.nz")
        self.assertIsNone(route)

    def test_genna_matariki_to_accounts_direct(self) -> None:
        parsed = ParsedInboundEmail(
            to_addresses=["accounts@matarikigroup.co.nz"],
            from_address="genna@matarikigroup.co.nz",
            subject="FW: Supplier bill",
            attachments=[InboundAttachment("bill.pdf", "application/pdf", b"%PDF-1.4")],
        )
        matched_to, _ = _resolve_recipient(parsed, self._config())
        self.assertEqual(matched_to, "accounts@matarikigroup.co.nz")

    def test_genna_forward_keeps_supplier_to_uses_allowed_from_fallback(self) -> None:
        parsed = ParsedInboundEmail(
            to_addresses=["billing@supplier.co.nz"],
            from_address="Genna <genna@gillespie.kiwi>",
            subject="FW: Invoice attached",
            attachments=[InboundAttachment("inv.pdf", "application/pdf", b"%PDF-1.4")],
        )
        matched_to, _ = _resolve_recipient(parsed, self._config())
        self.assertEqual(matched_to, "accounts@matarikigroup.co.nz")

    def test_accounts_sender_forward_fallback(self) -> None:
        parsed = ParsedInboundEmail(
            to_addresses=["genna@gillespie.kiwi"],
            from_address="Accounts <accounts@matarikigroup.co.nz>",
            subject="FW: Council invoice",
            attachments=[InboundAttachment("dc.pdf", "application/pdf", b"%PDF-1.4")],
        )
        matched_to, _ = _resolve_recipient(parsed, self._config())
        self.assertEqual(matched_to, "accounts@matarikigroup.co.nz")

    def test_david_paths_still_resolve_accounts(self) -> None:
        for from_addr in ("david@gillespie.kiwi", "david@matarikigroup.co.nz"):
            parsed = ParsedInboundEmail(
                to_addresses=["billing@vendor.example"],
                from_address=from_addr,
                subject="FW: Tax invoice",
                attachments=[InboundAttachment("x.pdf", "application/pdf", b"%PDF")],
            )
            matched_to, _ = _resolve_recipient(parsed, self._config())
            self.assertEqual(matched_to, "accounts@matarikigroup.co.nz", from_addr)

    def test_cloudflare_cc_includes_accounts(self) -> None:
        import base64

        payload = {
            "to": "genna@gillespie.kiwi",
            "cc": "accounts@matarikigroup.co.nz",
            "from": "Genna <genna@gillespie.kiwi>",
            "subject": "FW: Invoice",
            "text": "See attached",
            "attachments": [
                {
                    "filename": "invoice.pdf",
                    "content_type": "application/pdf",
                    "data_base64": base64.b64encode(b"%PDF-1.4").decode(),
                },
            ],
        }
        parsed = parse_cloudflare_json(payload)
        matched_to, _ = _resolve_recipient(parsed, self._config())
        self.assertEqual(matched_to, "accounts@matarikigroup.co.nz")

    def test_trusted_forwarder_bill_gate_with_pdf(self) -> None:
        result = is_actionable_bill(
            subject="FW:",
            body_text="Please see attached.",
            from_address="genna@gillespie.kiwi",
            attachment_names=["scan.pdf"],
            trusted_forwarders=("genna@gillespie.kiwi",),
        )
        self.assertTrue(result.is_bill)


class CloudflareParserTests(unittest.TestCase):
    def test_cloudflare_json_docx_and_png(self) -> None:
        docx = make_docx("Whangarei District Council", "DCPM2500002", "Total: $39036.34")
        import base64

        payload = {
            "to": "accounts@matarikigroup.co.nz",
            "from": "accounts@matarikigroup.co.nz",
            "subject": "FW: Development Contributions",
            "text": "Attached is the DC invoice.",
            "attachments": [
                {
                    "filename": "image001.png",
                    "content_type": "image/png",
                    "data_base64": base64.b64encode(b"x" * 5000).decode(),
                },
                {
                    "filename": "contribution.docx",
                    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "data_base64": base64.b64encode(docx).decode(),
                },
            ],
        }
        parsed = parse_cloudflare_json(payload)
        names = [a.name for a in parsed.attachments]
        self.assertIn("contribution.docx", names)
        self.assertIn("image001.png", names)

    def test_cloudflare_raw_fallback_finds_nested_docx(self) -> None:
        import base64
        from email.mime.application import MIMEApplication
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        docx = make_docx("Invoice date: 01/04/2024", "Due date: 15/04/2024", "DCPM2500002")
        inner = MIMEMultipart()
        inner.attach(MIMEText("Attached is the DC invoice.", "plain"))
        inner.attach(
            MIMEApplication(
                docx,
                _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                Name="invoice.docx",
            )
        )
        outer = MIMEMultipart()
        outer.attach(MIMEText("FW: please process\nAttached is the DC invoice.", "plain"))
        outer.attach(inner)
        raw = outer.as_bytes()

        payload = {
            "to": "accounts@matarikigroup.co.nz",
            "from": "accounts@matarikigroup.co.nz",
            "subject": "FW: Development Contributions",
            "text": "Attached is the DC invoice.",
            "attachments": [
                {
                    "filename": "image001.png",
                    "content_type": "image/png",
                    "data_base64": base64.b64encode(b"x" * 5000).decode(),
                },
            ],
            "raw_base64": base64.b64encode(raw).decode(),
        }
        parsed = parse_cloudflare_json(payload)
        names = [a.name for a in parsed.attachments]
        self.assertTrue(any(name.endswith(".docx") for name in names), names)

    def test_parse_eml_bytes_inline_docx(self) -> None:
        import base64
        from email.mime.application import MIMEApplication
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        docx = make_docx("Tax Invoice", "Total: $100.00")
        msg = MIMEMultipart()
        msg.attach(MIMEText("Invoice attached inline.", "plain"))
        part = MIMEApplication(
            docx,
            _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        part.add_header("Content-Disposition", "inline", filename="inline-invoice.docx")
        msg.attach(part)
        parsed = parse_eml_bytes(msg.as_bytes())
        self.assertTrue(any(a.name.endswith(".docx") for a in parsed.attachments))


class XeroReminderTests(unittest.TestCase):
    def test_detects_xero_reminder(self) -> None:
        subject = "FW: Bill INV-00001769 from Biggest Little Digger Limited is due"
        self.assertTrue(
            is_xero_reminder_email(
                from_address="David <david@gillespie.kiwi>",
                body_text=BIGGEST_LITTLE_BODY,
                subject=subject,
            )
        )

    def test_extracts_supplier_due_amount(self) -> None:
        subject = "FW: Bill INV-00001769 from Biggest Little Digger Limited is due"
        fields = extract_from_email(
            subject=subject,
            body_text=BIGGEST_LITTLE_BODY,
            from_address="David <david@gillespie.kiwi>",
        )
        self.assertEqual(fields.supplier_name, "Biggest Little Digger Limited")
        self.assertEqual(fields.invoice_number, "INV-00001769")
        self.assertEqual(fields.due_date, "2026-05-20")
        self.assertAlmostEqual(fields.total or 0, 2074.72)
        self.assertTrue(fields.is_overdue)
        self.assertIsNone(fields.invoice_date)

    def test_genna_forward_subject_not_reminder_without_body(self) -> None:
        subject = (
            "Fwd: Invoice INV-00001769 from Biggest Little Digger Limited "
            "for Matariki Property Group"
        )
        self.assertFalse(
            is_xero_reminder_email(
                subject=subject,
                body_text="",
                from_address="genna@gillespie.kiwi",
            )
        )
        self.assertFalse(
            has_actionable_email_bill(
                subject=subject,
                body_text="",
                from_address="genna@gillespie.kiwi",
            )
        )
        parsed = _parse_xero_invoice_subject(subject)
        self.assertEqual(parsed, ("INV-00001769", "Biggest Little Digger Limited"))

    def test_clean_description_and_reference(self) -> None:
        fields = extract_xero_reminder_fields(
            subject="Bill INV-00001769 from Biggest Little Digger Limited is due",
            body_text=BIGGEST_LITTLE_BODY,
        )
        link = "https://in.xero.com/U8b6mek8Laro784fVY3CQEB3RJaRAdmq5xsPN8"
        self.assertEqual(
            build_line_description(fields),
            "Biggest Little Digger Limited — INV-00001769 (overdue, due 2026-05-20)",
        )
        self.assertIn("INV-00001769", build_bill_reference(fields, xero_link=link))
        self.assertIn("in.xero.com", build_bill_reference(fields, xero_link=link))

    def test_in_xero_download_pdf_uuid(self) -> None:
        url = (
            "https://in.xero.com/U8b6mek8Laro784fVY3CQEB3RJaRAdmq5xsPN8/"
            "Invoice/DownloadPdf/9d4ca9ea-aac6-45f4-94dc-8785050ef8a8"
        )
        self.assertEqual(
            _extract_invoice_id(url),
            "9d4ca9ea-aac6-45f4-94dc-8785050ef8a8",
        )

    def test_primary_link_prefers_view_over_download(self) -> None:
        links = detect_xero_links(BIGGEST_LITTLE_BODY)
        primary = primary_xero_link(links)
        self.assertIsNotNone(primary)
        assert primary is not None
        self.assertNotIn("DownloadPdf", primary)


def _test_inbound_config() -> InboundConfig:
    return InboundConfig(
        domain="matarikigroup.co.nz",
        webhook_secret="",
        webhook_port=8766,
        auto_process=False,
        process_delay_sec=0.0,
        default_document_type="ACCPAY",
        default_status="DRAFT",
        allowed_extensions=(".pdf", ".docx", ".png"),
        routes=(),
        intake_addresses=(
            "accounts@matarikigroup.co.nz",
            "david@matarikigroup.co.nz",
            "genna@matarikigroup.co.nz",
            "david@gillespie.kiwi",
            "genna@gillespie.kiwi",
        ),
        allowed_from=(
            "accounts@matarikigroup.co.nz",
            "david@matarikigroup.co.nz",
            "genna@matarikigroup.co.nz",
            "david@gillespie.kiwi",
            "genna@gillespie.kiwi",
        ),
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


class MultiBillSplitTests(unittest.TestCase):
    def test_two_pdfs_split_into_two_bills(self) -> None:
        pdf_a = b"%PDF-1.4 minimal"
        pdf_b = b"%PDF-1.4 other"
        parsed = ParsedInboundEmail(
            to_addresses=["accounts@matarikigroup.co.nz"],
            from_address="billing@supplier.co.nz",
            subject="Two invoices",
            attachments=[
                InboundAttachment("INV-1001.pdf", "application/pdf", pdf_a),
                InboundAttachment("INV-1002.pdf", "application/pdf", pdf_b),
            ],
        )
        config = _test_inbound_config()
        bill_atts = [
            a
            for a in parsed.attachments
            if a.name.endswith(".pdf")
        ]
        splits = split_inbound_into_bills(
            parsed,
            bill_attachments=bill_atts,
            xero_links=[],
            config=config,
            has_actionable_body=False,
        )
        self.assertEqual(len(splits), 2)
        self.assertEqual(splits[0].kind, "attachment")
        self.assertEqual(splits[0].attachments[0].name, "INV-1001.pdf")
        self.assertEqual(splits[1].attachments[0].name, "INV-1002.pdf")

    def test_pdf_and_docx_split(self) -> None:
        parsed = ParsedInboundEmail(
            to_addresses=["accounts@matarikigroup.co.nz"],
            from_address="billing@supplier.co.nz",
            subject="Mixed",
            attachments=[
                InboundAttachment("bill.pdf", "application/pdf", b"%PDF"),
                InboundAttachment("bill.docx", "application/vnd.openxmlformats", make_docx("INV 9")),
            ],
        )
        config = _test_inbound_config()
        from xero_mcp.inbound.attachments import is_bill_attachment

        bill_atts = [
            a
            for a in parsed.attachments
            if is_bill_attachment(a.name, len(a.data), a.content_type)
        ]
        splits = split_inbound_into_bills(
            parsed,
            bill_attachments=bill_atts,
            xero_links=[],
            config=config,
            has_actionable_body=False,
        )
        self.assertEqual(len(splits), 2)

    def test_single_pdf_one_split(self) -> None:
        parsed = ParsedInboundEmail(
            to_addresses=["accounts@matarikigroup.co.nz"],
            from_address="billing@supplier.co.nz",
            subject="One",
            attachments=[InboundAttachment("invoice.pdf", "application/pdf", b"%PDF")],
        )
        config = _test_inbound_config()
        splits = split_inbound_into_bills(
            parsed,
            bill_attachments=parsed.attachments,
            xero_links=[],
            config=config,
            has_actionable_body=False,
        )
        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0].split_total, 1)

    def test_dedupe_key_per_attachment(self) -> None:
        att = InboundAttachment("INV-5859.pdf", "application/pdf", b"%PDF-5859")
        from xero_mcp.inbound.bill_splits import InboundBillSplit

        split_a = InboundBillSplit("attachment", [att], [], "5859", 0, 1)
        split_b = InboundBillSplit(
            "attachment",
            [InboundAttachment("other.pdf", "application/pdf", b"%PDF-other")],
            [],
            None,
            0,
            1,
        )
        key_a = build_split_dedupe_key(
            org_slug="matariki-property-group",
            from_address="a@b.co.nz",
            split=split_a,
        )
        key_b = build_split_dedupe_key(
            org_slug="matariki-property-group",
            from_address="a@b.co.nz",
            split=split_b,
        )
        self.assertNotEqual(key_a, key_b)

    def test_invoice_hint_from_filename(self) -> None:
        self.assertEqual(invoice_number_from_filename("Biggest-Little_INV-00001769.pdf"), "00001769")

    def test_multiple_xero_links_grouped_separately(self) -> None:
        links = [
            XeroLink("https://in.xero.com/abc123", None, "in_xero"),
            XeroLink("https://in.xero.com/xyz789", None, "in_xero"),
        ]
        groups = group_xero_links_for_bills(links)
        self.assertEqual(len(groups), 2)

    def test_format_invoice_hint_numeric(self) -> None:
        self.assertEqual(format_invoice_hint("68451"), "INV-68451")
        self.assertEqual(format_invoice_hint("1482"), "1482")
        self.assertEqual(format_invoice_hint("INV-68451"), "INV-68451")

    def test_three60_qty_only_lines_and_totals(self) -> None:
        text = """
Three60 Electrical & Security
12 Sample Road
Auckland

Attention: David Gillespie
Matariki Property Group

GST No: 120-790-455

Tax Invoice 1482

Description Quantity
Michael Humphris 6.50
Marcus Williams 8.50
Materials supply 3.00
Cable tray 1.00
Labour materials 4.00

Amount $1,730.48
GST 15% $259.57
Amount including GST $1,990.05
"""
        fields = parse_extracted_text(text)
        self.assertEqual(fields.invoice_number, "1482")
        self.assertIn("Three60", fields.supplier_name or "")
        self.assertIn("Electrical", fields.supplier_name or "")
        self.assertNotIn("Attention", fields.supplier_name or "")
        self.assertNotIn("GST No", fields.supplier_name or "")
        self.assertAlmostEqual(fields.subtotal or 0, 1730.48, places=2)
        self.assertAlmostEqual(fields.tax_amount or 0, 259.57, places=2)
        self.assertAlmostEqual(fields.total or 0, 1990.05, places=2)
        self.assertGreaterEqual(len(fields.line_items), 4)
        michael = next(i for i in fields.line_items if "Michael" in i.description)
        self.assertAlmostEqual(michael.quantity, 6.5, places=2)
        self.assertEqual(michael.unit_amount, 0.0)
        self.assertIsNotNone(michael.line_amount)
        descs = " ".join(i.description.lower() for i in fields.line_items)
        self.assertNotIn("amount including", descs)

    def test_three60_live_pdf_layout_skips_metadata_lines(self) -> None:
        """Regression: Invoice No: / Job Site lines must not become line items."""
        text = """
Three60 Electrical & Security Ltd
Tax Invoice
To: Matariki Property Group
Attention: David Gillespie
Invoice No: 1482.1
GST No: 120-790-455
Invoice Date: 04/06/2026
Payment Due: 11/06/2026
Job Site / Address: 26 Logyard Road, Port Whangarei, Whangarei 0110
Labour
Description Qty
Michael Humphries 6.50
Manaia Williams 6.50
Materials
Description Qty
Collar self-adhesive 150-165mm 3.00
Amount: $1,730.48
GST (15%): $259.56
Amount (including GST): $1,990.04
"""
        fields = parse_extracted_text(text)
        self.assertEqual(fields.invoice_number, "1482")
        self.assertAlmostEqual(fields.subtotal or 0, 1730.48, places=2)
        descs = [i.description.lower() for i in fields.line_items]
        self.assertNotIn("invoice no:", descs)
        self.assertFalse(any("job site" in d for d in descs))
        self.assertGreaterEqual(len(fields.line_items), 3)

    def test_coalesce_single_invoice_pdf_sections(self) -> None:
        text = """
Three60 Electrical & Security
Attention: David Gillespie
Tax Invoice 1482
Description Quantity
Item one 1.00
Amount $100.00
Amount including GST $115.00
"""
        chunks = split_extracted_text_by_invoices(text)
        merged = coalesce_pdf_invoice_sections(text, chunks)
        self.assertEqual(len(merged), 1)

    def test_one_pdf_one_split_unit(self) -> None:
        parsed = ParsedInboundEmail(
            to_addresses=["accounts@matarikigroup.co.nz"],
            from_address="billing@three60.co.nz",
            subject="Invoice 1482",
            attachments=[
                InboundAttachment("invoice-1482.pdf", "application/pdf", b"%PDF"),
            ],
            body_text="Attention: David Gillespie\nPlease pay invoice 1482.",
        )
        config = _test_inbound_config()
        bill_atts = parsed.attachments
        splits = split_inbound_into_bills(
            parsed,
            bill_attachments=bill_atts,
            xero_links=[],
            config=config,
            has_actionable_body=True,
        )
        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0].kind, "attachment")

    def test_supplier_after_reference_skips_customer_gst_block(self) -> None:
        pdf_text = """
TAX INVOICE
Matariki Property Group
2 Memorial Drive
Whangarei
Invoice Date
12 Jan 2026
Invoice Number
INV-68451
Reference
Monthly IQP Inspections -
Wolfe Street Collective
GST Number
99-672-811
Building & Fire Services
(2008) Limited
PO Box 7024
Tikipunga
Description Quantity Unit Price Amount NZD
TOTAL NZD 186.30
"""
        from xero_mcp.inbound.extract import _extract_supplier

        name = _extract_supplier(pdf_text)
        self.assertIn("Building", name or "")
        self.assertIn("Fire", name or "")
        self.assertNotIn("Wolfe Street", name or "")
        self.assertNotIn("GST Number", name or "")

    def test_attachment_supplier_beats_design_nz_body(self) -> None:
        pdf_text = """
Building and Fire Services Limited
12 Industrial Road
Auckland 1010

TAX INVOICE
Invoice Number: INV-68451
Invoice Date: 01/03/2024
Due Date: 15/03/2024
TOTAL NZD 1,234.56
"""
        body = (
            "FW: Overdue account — Matariki Property Group\n\n"
            "Design NZ Limited\n"
            "Credit control on behalf of multiple suppliers.\n"
            "Please remit payment for Logyard Road.\n"
        )
        fields = merge_extraction(
            from_address="collections@designnz.co.nz",
            subject="Overdue account statement",
            body_text=body,
            attachment_bytes=b"%PDF",
            attachment_name="INV-68451.pdf",
            attachment_text=pdf_text,
            invoice_hint="68451",
            attachment_only_invoice=True,
            attachment_only_supplier=True,
        )
        self.assertEqual(fields.invoice_number, "INV-68451")
        self.assertIn("Building and Fire", fields.supplier_name or "")
        self.assertNotIn("Design NZ", fields.supplier_name or "")
        self.assertNotIn("Matariki", fields.supplier_name or "")

    def test_merge_hint_beats_matariki_body(self) -> None:
        body = (
            "Please process for Matariki Property Group at Logyard Road.\n"
            "Reference: Matariki\n"
        )
        fields = merge_extraction(
            from_address="david@gillespie.kiwi",
            subject="Matariki — supplier invoices",
            body_text=body,
            attachment_bytes=b"%PDF-1.4",
            attachment_name="INV-68451.pdf",
            invoice_hint="68451",
            attachment_only_invoice=True,
        )
        self.assertEqual(fields.invoice_number, "INV-68451")

    def test_six_hints_produce_distinct_invoice_numbers(self) -> None:
        hints = ["68451", "68796", "69585", "70376", "70318", "68450"]
        body = "Forwarded for Matariki Property Group — Logyard Road\nReference: Matariki"
        numbers: list[str] = []
        for hint in hints:
            fields = merge_extraction(
                from_address="accounts@matarikigroup.co.nz",
                subject="Matariki invoices",
                body_text=body,
                attachment_bytes=b"%PDF",
                attachment_name=f"invoice-{hint}.pdf",
                invoice_hint=hint,
                attachment_only_invoice=True,
                attachment_only_supplier=True,
            )
            numbers.append(fields.invoice_number or "")
        self.assertEqual(len(set(numbers)), 6)
        self.assertEqual(numbers[0], "INV-68451")
        self.assertEqual(numbers[1], "INV-68796")

    @patch("xero_mcp.inbound.processor.create_draft_bill")
    def test_processor_single_bill_for_three60_pdf(self, mock_create: Any) -> None:
        from xero_mcp.inbound.processor import process_message

        three60_text = """
Three60 Electrical & Security
GST No: 120-790-455
Tax Invoice 1482
Description Quantity
Michael Humphris 6.50
Amount $1,730.48
GST 15% $259.57
Amount including GST $1,990.05
"""
        record = {
            "id": "test-1482",
            "status": "pending",
            "from": "billing@three60.co.nz",
            "subject": "Invoice 1482",
            "body_text": "Attention: David Gillespie",
            "org_slug": "matariki-property-group",
            "default_account_code": "400",
            "split_kind": "attachment",
            "invoice_hint": "1482",
            "attachments": [
                {
                    "name": "invoice-1482.pdf",
                    "path": "/tmp/invoice-1482.pdf",
                    "size": 100,
                    "content_type": "application/pdf",
                }
            ],
            "xero_links": [],
        }
        with patch(
            "xero_mcp.inbound.processor.load_queue_record",
            return_value=record,
        ), patch(
            "xero_mcp.inbound.processor.save_queue_record",
        ), patch(
            "xero_mcp.inbound.processor._read_attachment_bytes",
            return_value=b"%PDF",
        ), patch(
            "xero_mcp.inbound.processor.is_actionable_bill",
        ) as mock_gate, patch(
            "xero_mcp.inbound.processor.set_active_organisation",
        ), patch(
            "xero_mcp.inbound.processor.extract_text_from_attachment",
            return_value=three60_text,
        ), patch(
            "xero_mcp.inbound.processor.load_inbound_config",
        ) as mock_config:
            mock_gate.return_value = type(
                "Gate",
                (),
                {"is_bill": True, "confidence": 0.9, "reason": "ok", "method": "test"},
            )()
            mock_config.return_value = replace(
                _test_inbound_config(),
                require_bill_classification=False,
            )
            process_message(record["id"])
        self.assertEqual(mock_create.call_count, 1)
        fields = mock_create.call_args.kwargs["fields"]
        self.assertEqual(fields.invoice_number, "1482")
        self.assertIn("Three60", fields.supplier_name or "")

    @patch("xero_mcp.inbound.processor.create_draft_bill")
    def test_processor_passes_distinct_invoice_numbers(self, mock_create: Any) -> None:
        from xero_mcp.inbound.processor import process_message

        created_numbers: list[str] = []

        def _fake_create(*, fields: Any, **kwargs: Any) -> dict[str, str]:
            created_numbers.append(fields.invoice_number)
            return {"invoice_id": f"id-{len(created_numbers)}", "invoice_number": fields.invoice_number}

        mock_create.side_effect = _fake_create

        hints = ["68451", "68796", "69585", "70376", "70318", "68450"]
        for hint in hints:
            record = {
                "id": f"test-{hint}",
                "status": "pending",
                "from": "billing@supplier.co.nz",
                "subject": "Matariki batch",
                "body_text": "Matariki Property Group Logyard Road",
                "org_slug": "matariki-property-group",
                "default_account_code": "400",
                "split_kind": "attachment",
                "invoice_hint": hint,
                "attachments": [
                    {
                        "name": f"INV-{hint}.pdf",
                        "path": "/tmp/unused.pdf",
                        "size": 100,
                        "content_type": "application/pdf",
                    }
                ],
                "xero_links": [],
            }
            with patch(
                "xero_mcp.inbound.processor.load_queue_record",
                return_value=record,
            ), patch(
                "xero_mcp.inbound.processor.save_queue_record",
            ), patch(
                "xero_mcp.inbound.processor._read_attachment_bytes",
                return_value=b"%PDF-1.4 test",
            ), patch(
                "xero_mcp.inbound.processor.is_actionable_bill",
            ) as mock_gate, patch(
                "xero_mcp.inbound.processor.set_active_organisation",
            ), patch(
                "xero_mcp.inbound.processor.extract_text_from_attachment",
                return_value="TAX INVOICE\nTotal 100.00",
            ), patch(
                "xero_mcp.inbound.processor.load_inbound_config",
            ) as mock_config:
                mock_gate.return_value = type(
                    "Gate",
                    (),
                    {"is_bill": True, "confidence": 0.9, "reason": "ok", "method": "test"},
                )()
                mock_config.return_value = replace(
                    _test_inbound_config(),
                    require_bill_classification=False,
                )
                process_message(record["id"])

        self.assertEqual(len(created_numbers), 6)
        self.assertEqual(len(set(created_numbers)), 6)
        self.assertTrue(all(n.startswith("INV-") for n in created_numbers))

    @patch("xero_mcp.inbound.processor.update_draft_bill")
    @patch("xero_mcp.inbound.processor.create_draft_bill")
    @patch("xero_mcp.inbound.processor.resolve_xero_links")
    def test_processor_updates_existing_bill_from_subject_invoice_number(
        self,
        mock_resolve: Any,
        mock_create: Any,
        mock_update: Any,
    ) -> None:
        from xero_mcp.inbound.processor import process_message

        mock_resolve.return_value = {
            "resolved": True,
            "invoice_id": "9028d095-d1cf-48ee-8ae4-8cf330fe4bb6",
            "org_slug": "matariki-property-group",
            "method": "existing_invoice_number",
        }
        mock_update.return_value = {
            "invoice_id": "9028d095-d1cf-48ee-8ae4-8cf330fe4bb6",
            "total": 2074.72,
            "updated": True,
        }

        digger_pdf = """
Biggest Little Digger Limited
TAX INVOICE
Invoice Number INV-00001769
Total NZD 2,074.72
"""
        record = {
            "id": "f74ee092-7565-4ec3-a02d-ba4f573c6624",
            "status": "pending",
            "from": "genna@gillespie.kiwi",
            "subject": (
                "Fwd: Invoice INV-00001769 from Biggest Little Digger Limited "
                "for Matariki Property Group"
            ),
            "body_text": "",
            "org_slug": "matariki-property-group",
            "default_account_code": "310",
            "invoice_hint": "1769",
            "attachments": [
                {
                    "name": "Invoice INV-00001769.pdf",
                    "path": "/tmp/Invoice INV-00001769.pdf",
                    "size": 74629,
                    "content_type": "application/pdf",
                }
            ],
            "xero_links": [],
        }
        with patch(
            "xero_mcp.inbound.processor.load_queue_record",
            return_value=record,
        ), patch(
            "xero_mcp.inbound.processor.save_queue_record",
        ), patch(
            "xero_mcp.inbound.processor._read_attachment_bytes",
            return_value=b"%PDF",
        ), patch(
            "xero_mcp.inbound.processor.is_actionable_bill",
        ) as mock_gate, patch(
            "xero_mcp.inbound.processor.set_active_organisation",
        ), patch(
            "xero_mcp.inbound.processor.extract_text_from_attachment",
            return_value=digger_pdf,
        ), patch(
            "xero_mcp.inbound.processor.load_inbound_config",
        ) as mock_config:
            mock_gate.return_value = type(
                "Gate",
                (),
                {"is_bill": True, "confidence": 1.0, "reason": "ok", "method": "test"},
            )()
            mock_config.return_value = replace(
                _test_inbound_config(),
                require_bill_classification=False,
            )
            result = process_message(record["id"])

        mock_resolve.assert_called_once()
        self.assertEqual(
            mock_resolve.call_args.kwargs["invoice_number"],
            "INV-00001769",
        )
        mock_create.assert_not_called()
        mock_update.assert_called_once()
        self.assertEqual(
            mock_update.call_args.kwargs["invoice_id"],
            "9028d095-d1cf-48ee-8ae4-8cf330fe4bb6",
        )
        self.assertTrue(result.get("ok"))

    def test_split_pdf_text_by_invoice_headers(self) -> None:
        text = (
            "ACME Plumbing Ltd\n123 Main St\nTAX INVOICE\n"
            "Invoice Number: INV-1\nLine item 120.00\nTotal 138.00\n\n"
            "BETA Services Ltd\n456 Queen St\nTAX INVOICE\n"
            "Invoice Number: INV-2\nLine item 200.00\nTotal 230.00"
        )
        chunks = split_extracted_text_by_invoices(text)
        self.assertGreaterEqual(len(chunks), 2)


class XeroLinkTests(unittest.TestCase):
    def test_detect_go_xero_link(self) -> None:
        text = (
            "Open https://go.xero.com/AccountsPayable/View.aspx?"
            "InvoiceID=12345678-1234-1234-1234-123456789abc to pay"
        )
        links = detect_xero_links(text)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].invoice_id, "12345678-1234-1234-1234-123456789abc")
        self.assertEqual(links[0].kind, "bill")

    def test_extract_invoice_id_from_query(self) -> None:
        url = "https://invoicing.xero.com/view/abc?invoiceId=abcdef12-3456-7890-abcd-ef1234567890"
        self.assertEqual(
            _extract_invoice_id(url),
            "abcdef12-3456-7890-abcd-ef1234567890",
        )


class AttachmentRecoveryTests(unittest.TestCase):
    def test_recovers_matching_pdf_from_sibling_folder(self) -> None:
        import tempfile

        from xero_mcp.inbound.attachment_recovery import recover_missing_bill_attachment
        from xero_mcp.inbound.config import ATTACHMENTS_DIR

        with tempfile.TemporaryDirectory() as tmp:
            attach_root = Path(tmp) / "attachments"
            attach_root.mkdir()
            donor = attach_root / "donor-msg"
            donor.mkdir()
            pdf = donor / "Invoice INV-00001769.pdf"
            pdf.write_bytes(b"%PDF-1.4 test")

            record = {
                "id": "fail-1",
                "source_message_id": "new-msg",
                "subject": "Fwd: Invoice INV-00001769 from Biggest Little Digger Limited",
                "attachments": [],
                "error": "No bill attachments — only signature/logo images found",
            }
            dest = attach_root / "new-msg"
            with patch("xero_mcp.inbound.attachment_recovery.ATTACHMENTS_DIR", attach_root):
                self.assertTrue(recover_missing_bill_attachment(record))
            self.assertTrue((dest / pdf.name).exists())
            self.assertEqual(record["attachments"][0]["name"], pdf.name)
            self.assertIsNone(record.get("error"))


class HealTests(unittest.TestCase):
    def test_classify_429_retry_now(self) -> None:
        from xero_mcp.inbound.heal import HealAction, classify_failure

        record = {"status": "failed", "id": "a"}
        self.assertEqual(
            classify_failure("Xero create bill failed (429): Rate limit", record),
            HealAction.RETRY_NOW,
        )

    def test_classify_missing_pdf_needs_pdf(self) -> None:
        from xero_mcp.inbound.heal import HealAction, classify_failure

        for err in (
            "No bill attachments (.pdf) in message — only signature/logo images found",
            "No allowed attachments (.pdf, .jpg) in message to accounts@matarikigroup.co.nz",
        ):
            record = {"status": "failed", "error": err}
            self.assertEqual(classify_failure(err, record), HealAction.NEEDS_PDF)

    def test_classify_validation_retries_after_fix(self) -> None:
        from xero_mcp.inbound.heal import HealAction, classify_failure

        record = {"status": "failed"}
        err = 'Xero create bill failed (400): {"Type": "ValidationException"}'
        self.assertEqual(classify_failure(err, record), HealAction.RETRY_NOW)

    def test_classify_missing_pdf_forward_invoice_retries(self) -> None:
        from xero_mcp.inbound.heal import HealAction, classify_failure

        record = {
            "status": "failed",
            "subject": "Fwd: Invoice INV-00001769 from Biggest Little Digger Limited for Matariki Property Group",
        }
        err = "No bill attachments (.pdf) — only signature/logo images found and no Xero bill link"
        self.assertEqual(classify_failure(err, record), HealAction.RETRY_NOW)

    def test_classify_done_with_bill_skips(self) -> None:
        from xero_mcp.inbound.heal import HealAction, classify_failure

        record = {
            "status": "done",
            "xero_invoice_id": "inv-123",
            "extracted": {"total": 100.0},
        }
        self.assertEqual(classify_failure(None, record), HealAction.SKIP)

    def test_classify_done_zero_total_retries(self) -> None:
        from xero_mcp.inbound.heal import HealAction, classify_failure

        record = {
            "status": "done",
            "xero_invoice_id": "inv-123",
            "extracted": {"total": 0.0},
            "processed_at": 0,
        }
        self.assertEqual(classify_failure(None, record), HealAction.RETRY_NOW)

    def test_heal_skips_duplicate_when_prior_active(self) -> None:
        from xero_mcp.inbound.heal import heal_record

        record = {
            "id": "dup-1",
            "status": "duplicate",
            "dedupe_key": "key-1",
            "error": "Duplicate of a previously processed bill",
        }
        with patch(
            "xero_mcp.inbound.heal.load_queue_record",
            return_value=record,
        ), patch(
            "xero_mcp.inbound.heal.classify_failure",
            return_value=__import__(
                "xero_mcp.inbound.heal", fromlist=["HealAction"]
            ).HealAction.SKIP,
        ):
            result = heal_record("dup-1", dry_run=False)
        self.assertTrue(result.get("skipped"))

    @patch("xero_mcp.inbound.heal.process_message")
    def test_heal_retries_failed_with_force(self, mock_process: Any) -> None:
        from xero_mcp.inbound.heal import HealAction, heal_record

        record = {
            "id": "fail-429",
            "status": "failed",
            "error": "429 Too Many Requests",
            "heal_attempts": 0,
        }
        mock_process.return_value = {
            "ok": True,
            "record": {"status": "done", "xero_invoice_id": "new-id"},
        }
        with patch("xero_mcp.inbound.heal.load_queue_record", return_value=record), patch(
            "xero_mcp.inbound.heal.save_queue_record",
        ), patch(
            "xero_mcp.inbound.heal.classify_failure",
            return_value=HealAction.RETRY_NOW,
        ), patch(
            "xero_mcp.inbound.heal.load_heal_config",
        ) as mock_cfg:
            mock_cfg.return_value = __import__(
                "xero_mcp.inbound.heal", fromlist=["HealConfig"]
            ).HealConfig(
                enabled=True,
                pending_max_age_sec=900,
                processing_max_age_sec=600,
                done_missing_bill_grace_sec=120,
                max_attempts=5,
                min_interval_sec=0,
                retryable_patterns=(),
                config_patterns=(),
                permanent_patterns=(),
            )
            result = heal_record("fail-429", dry_run=False)
        self.assertTrue(result.get("ok"))
        mock_process.assert_called_once_with("fail-429", force=True)

    def test_heal_respects_max_attempts(self) -> None:
        from xero_mcp.inbound.heal import HealAction, heal_record

        record = {
            "id": "maxed",
            "status": "failed",
            "error": "429",
            "heal_attempts": 5,
        }
        with patch("xero_mcp.inbound.heal.load_queue_record", return_value=record), patch(
            "xero_mcp.inbound.heal.classify_failure",
            return_value=HealAction.RETRY_NOW,
        ), patch("xero_mcp.inbound.heal.load_heal_config") as mock_cfg:
            mock_cfg.return_value = __import__(
                "xero_mcp.inbound.heal", fromlist=["HealConfig"]
            ).HealConfig(
                enabled=True,
                pending_max_age_sec=900,
                processing_max_age_sec=600,
                done_missing_bill_grace_sec=120,
                max_attempts=5,
                min_interval_sec=0,
                retryable_patterns=(),
                config_patterns=(),
                permanent_patterns=(),
            )
            result = heal_record("maxed", dry_run=False)
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result.get("reason"), "max_heal_attempts")


class WebhookAsyncAutoProcessTests(unittest.TestCase):
    def test_schedule_auto_process_returns_before_process_finishes(self) -> None:
        import threading
        import time
        from unittest.mock import patch

        from xero_mcp.inbound.webhook import _schedule_auto_process

        started = threading.Event()
        release = threading.Event()
        records = [{"id": "msg-1", "status": "pending"}]

        def slow_process(_records: list) -> list:
            started.set()
            release.wait(timeout=5)
            return [{"ok": True}]

        with patch("xero_mcp.inbound.webhook.load_inbound_config", return_value=_test_inbound_config()), patch(
            "xero_mcp.inbound.webhook.process_queued_records",
            side_effect=slow_process,
        ):
            cfg = _test_inbound_config()
            with patch(
                "xero_mcp.inbound.webhook.load_inbound_config",
                return_value=replace(cfg, auto_process=True),
            ):
                scheduled = _schedule_auto_process(records)

        self.assertEqual(scheduled, {"async": True, "pending_count": 1})
        self.assertTrue(started.wait(timeout=2), "background thread should start process")
        release.set()
        time.sleep(0.05)

    def test_schedule_auto_process_skips_when_disabled(self) -> None:
        from xero_mcp.inbound.webhook import _schedule_auto_process

        records = [{"id": "msg-1", "status": "pending"}]
        with patch("xero_mcp.inbound.webhook.load_inbound_config", return_value=_test_inbound_config()):
            self.assertIsNone(_schedule_auto_process(records))


class CloudflareWebhookAcceptPolicyTests(unittest.TestCase):
    def _run_cloudflare(self, body: dict[str, Any], *, secret: str = "good-secret", patches: dict | None = None) -> tuple[int, dict[str, Any]]:
        from io import BytesIO
        from unittest.mock import patch

        from xero_mcp.inbound.webhook import InboundWebhookHandler

        captured: dict[str, Any] = {}

        def capture_json_response(_self, status: int, payload: dict[str, Any]) -> None:
            captured["status"] = status
            captured["payload"] = payload

        handler = object.__new__(InboundWebhookHandler)
        raw = json.dumps(body).encode()
        handler.headers = {
            "Content-Length": str(len(raw)),
            "X-Xero-Inbound-Secret": secret,
        }
        handler.rfile = BytesIO(raw)

        cfg = replace(_test_inbound_config(), webhook_secret="good-secret")
        patchers = [
            patch("xero_mcp.inbound.webhook.load_inbound_config", return_value=cfg),
            patch.object(InboundWebhookHandler, "_json_response", capture_json_response),
        ]
        if patches:
            for target, value in patches.items():
                if isinstance(value, BaseException):
                    patchers.append(patch(target, side_effect=value))
                elif callable(value):
                    patchers.append(patch(target, side_effect=value))
                else:
                    patchers.append(patch(target, return_value=value))

        for patcher in patchers:
            patcher.start()
        try:
            handler._handle_cloudflare()
        finally:
            for patcher in reversed(patchers):
                patcher.stop()

        return captured["status"], captured["payload"]

    def test_bad_secret_returns_401(self) -> None:
        status, payload = self._run_cloudflare({"to": "accounts@matarikigroup.co.nz"}, secret="wrong")
        self.assertEqual(status, 401)
        self.assertFalse(payload["ok"])

    def test_enqueue_error_returns_200_not_400(self) -> None:
        from xero_mcp.inbound.config import InboundError

        status, payload = self._run_cloudflare(
            {
                "to": "unknown@example.com",
                "from": "supplier@example.com",
                "subject": "Invoice",
                "text": "No intake route",
                "attachments": [],
            },
            patches={
                "xero_mcp.inbound.webhook.enqueue_email": InboundError("No intake address"),
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(payload["ok"])
        self.assertIn("error", payload)
        self.assertEqual(payload.get("queued"), [])

    def test_valid_supplier_to_accounts_returns_200_ok(self) -> None:
        status, payload = self._run_cloudflare(
            {
                "to": "accounts@matarikigroup.co.nz",
                "from": "supplier@example.com",
                "subject": "Invoice INV-123",
                "text": "Please find attached",
                "attachments": [],
            },
            patches={
                "xero_mcp.inbound.webhook.enqueue_email": [{"id": "q-1", "status": "pending"}],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["queued"][0]["id"], "q-1")

    def test_unexpected_exception_returns_200_not_500(self) -> None:
        status, payload = self._run_cloudflare(
            {"to": "accounts@matarikigroup.co.nz", "attachments": []},
            patches={"xero_mcp.inbound.webhook.parse_cloudflare_json": RuntimeError("boom")},
        )
        self.assertEqual(status, 200)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload.get("queued"), [])


if __name__ == "__main__":
    unittest.main()

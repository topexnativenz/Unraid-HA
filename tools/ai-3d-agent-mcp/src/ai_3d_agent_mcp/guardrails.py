from __future__ import annotations


class GuardrailError(ValueError):
    """Hard policy violation (e.g. auto-print requested)."""


def assert_no_auto_print(allow_auto_print: bool, confirm_send_to_printer: bool) -> None:
    if confirm_send_to_printer and not allow_auto_print:
        raise GuardrailError(
            "Auto-print is disabled. Package for Bambu Studio / iOS and confirm the print "
            "manually in the Bambu app. Set allow_auto_print=true only if you intentionally "
            "want remote start later (not recommended for v1)."
        )


CATEGORIES = ("figurine", "hook", "sign", "functional", "other")
MATERIALS = ("PLA", "PETG", "TPU")
HANDOFF_TARGETS = ("macos_studio", "ios_bambu", "file_only")

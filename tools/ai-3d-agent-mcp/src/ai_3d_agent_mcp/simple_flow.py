from __future__ import annotations

import re
from typing import Any

from ai_3d_agent_mcp.dimensions import missing_dimensions_prompt


PRINT_INTENT_PATTERNS = [
    r"\b3d\s*print",
    r"\bprint\s+(this|me|a|an|the)\b",
    r"\bbambu\b",
    r"\bslicer\b",
    r"\bstl\b",
    r"\b3mf\b",
    r"\bfigurine\b",
    r"\bwall\s*hook\b",
    r"\bmake\s+(me\s+)?(a|an)\b.+\b(hook|sign|bracket|mount|clip|spacer)\b",
    r"\bdesign\s+(and\s+)?print\b",
    r"\bmodel\s+for\s+print",
]


def looks_like_print_request(text: str, has_images: bool = False) -> bool:
    """Heuristic for Cursor/Claude auto-detection (also documented in .cursor/rules)."""
    t = (text or "").lower().strip()
    if has_images and (
        not t
        or re.search(r"\b(print|3d|model|figurine|hook|sign|bambu|replica|copy)\b", t)
        or len(t) < 80
    ):
        # Photo alone or short caption → treat as print intent when user is in a print chat,
        # or caption mentions print-ish words. Short captions with a photo default to yes.
        if not t:
            return True
        if re.search(r"\b(print|3d|model|figurine|hook|sign|bambu|replica|copy|make)\b", t):
            return True
    if not t:
        return False
    return any(re.search(p, t) for p in PRINT_INTENT_PATTERNS)


def infer_category(description: str, has_images: bool) -> str:
    text = (description or "").lower()
    if re.search(r"\b(hook|hanger|peg)\b", text):
        return "hook"
    if re.search(r"\b(sign|plaque|nameplate|label)\b", text):
        return "sign"
    if re.search(r"\b(figurine|statue|character|miniature|sculpture|toy)\b", text):
        return "figurine"
    if has_images and not re.search(r"\b(bracket|spacer|washer|clip|mount|hook|sign)\b", text):
        return "figurine"
    if re.search(r"\b(bracket|spacer|washer|clip|mount)\b", text):
        return "functional"
    if has_images:
        return "figurine"
    return "functional"


def user_facing_dimension_question(category: str, description: str, has_images: bool) -> dict[str, Any]:
    """
    The ONLY thing Claude should ask the user before building.
    Keep this short — no extra technical questions.
    """
    base = missing_dimensions_prompt(category)
    examples = {
        "hook": "e.g. about 40 mm wide, sticks out 25 mm, 60 mm tall",
        "sign": "e.g. 120 mm wide, 3 mm thick, 60 mm tall",
        "figurine": "e.g. about 50 mm tall (and roughly how wide/deep)",
        "functional": "e.g. the box it must fit in: 80 × 40 × 20 mm",
        "other": "width × depth × height in millimetres",
    }
    ask = (
        "Roughly how big should this be when printed?\n"
        "Please give **width × depth × height in millimetres** "
        f"({examples.get(category, examples['other'])})."
    )
    return {
        "status": "needs_dimensions",
        "ask_user": ask,
        "ask_user_only": True,
        "fields_needed": ["width_mm", "depth_mm", "height_mm"],
        "inferred_category": category,
        "description": description,
        "has_images": has_images,
        "agent_instruction": (
            "Stop and ask the user ONLY the ask_user question. "
            "Do not ask about filament, printer, AMS, supports, or process unless they bring it up. "
            "Defaults: PLA, 0.20mm Standard, X1C-A. "
            "When they reply with sizes, call simple_print_request again with those dimensions."
        ),
        "hint": base.get("message"),
    }


def dims_complete(width_mm: float | None, depth_mm: float | None, height_mm: float | None) -> bool:
    try:
        return (
            width_mm is not None
            and depth_mm is not None
            and height_mm is not None
            and float(width_mm) > 0
            and float(depth_mm) > 0
            and float(height_mm) > 0
        )
    except (TypeError, ValueError):
        return False

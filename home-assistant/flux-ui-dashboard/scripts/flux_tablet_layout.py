"""Shared 16:9 tablet section helpers.

HA sections views default to ~500px column max-width and column_span=1,
which squashes landscape content into a phone-sized strip. Tablet pages
must set column_span to max_columns and widen the sections column tokens.
"""

from __future__ import annotations

TABLET_MAX_COLUMNS = 4


def tablet_section(cards: list[dict], *, column_span: int = TABLET_MAX_COLUMNS) -> dict:
    """Full-bleed section for 15.6\" / 1920×1080 landscape."""
    return {
        "type": "grid",
        "column_span": column_span,
        "cards": cards,
    }


def ensure_tablet_section_spans(sections: list[dict], *, column_span: int = TABLET_MAX_COLUMNS) -> list[dict]:
    """Force every section to span the full tablet row width."""
    out: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            out.append(section)
            continue
        sec = dict(section)
        sec["column_span"] = column_span
        out.append(sec)
    return out

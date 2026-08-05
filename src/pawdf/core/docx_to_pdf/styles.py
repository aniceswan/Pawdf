"""Map a docx paragraph style name (e.g. "Heading 1", "Title", "Normal") to
a reportlab ParagraphStyle. Deliberately simple: docx style inheritance/
theming isn't modeled, just the handful of built-in style *names* Word
itself uses. See conversion_fidelity.md for what's out of scope.
"""

from __future__ import annotations

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle

_ALIGNMENT_MAP = {
    "left": TA_LEFT,
    "center": TA_CENTER,
    "right": TA_RIGHT,
    "justify": TA_JUSTIFY,
}

BASE_FONT = "Helvetica"
BASE_FONT_BOLD = "Helvetica-Bold"
BASE_FONT_ITALIC = "Helvetica-Oblique"

_HEADING_SIZES = {1: 24, 2: 20, 3: 17, 4: 15, 5: 13, 6: 12, 7: 11, 8: 11, 9: 11}


def style_for(style_name: str, alignment: str = "left") -> ParagraphStyle:
    align = _ALIGNMENT_MAP.get(alignment, TA_LEFT)
    name_lower = (style_name or "").lower()

    if name_lower == "title":
        return ParagraphStyle(
            "Title",
            fontName=BASE_FONT_BOLD,
            fontSize=28,
            leading=34,
            alignment=TA_CENTER,
            spaceAfter=18,
        )

    if name_lower.startswith("heading"):
        digits = "".join(ch for ch in name_lower if ch.isdigit())
        level = int(digits) if digits else 1
        size = _HEADING_SIZES.get(level, 11)
        return ParagraphStyle(
            f"Heading{level}",
            fontName=BASE_FONT_BOLD,
            fontSize=size,
            leading=size * 1.2,
            alignment=align,
            spaceBefore=size * 0.6,
            spaceAfter=size * 0.3,
        )

    if "quote" in name_lower:
        return ParagraphStyle(
            "Quote",
            fontName=BASE_FONT_ITALIC,
            fontSize=11,
            leading=14,
            alignment=align,
            leftIndent=24,
            spaceAfter=6,
        )

    return ParagraphStyle(
        "Normal",
        fontName=BASE_FONT,
        fontSize=11,
        leading=14,
        alignment=align,
        spaceAfter=6,
    )

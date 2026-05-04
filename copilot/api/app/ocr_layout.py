from __future__ import annotations

import re
from dataclasses import dataclass

from app.document_models import DocumentBoundingBox


class LayoutExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class LayoutLine:
    page: int
    line_index: int
    text: str
    bbox: DocumentBoundingBox


@dataclass(frozen=True)
class DocumentLayout:
    text: str
    lines: list[LayoutLine]


def extract_layout(content: bytes, content_type: str) -> DocumentLayout:
    """Extract reviewable text lines with deterministic synthetic bounding boxes.

    The Week 2 implementation deliberately keeps bounding boxes owned by the layout
    layer, not the LLM. For generated demo PDFs/forms this can decode embedded text
    directly. Real OCR can replace this function without changing downstream schemas.
    """

    text = _decode_document_text(content, content_type)
    raw_lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in raw_lines if line]
    if not lines:
        raise LayoutExtractionError("No readable text lines were found in the document")

    count = max(len(lines), 1)
    layout_lines = [
        LayoutLine(
            page=1,
            line_index=index,
            text=line,
            bbox=_line_bbox(index=index, line_count=count),
        )
        for index, line in enumerate(lines)
    ]
    return DocumentLayout(text="\n".join(lines), lines=layout_lines)


def _decode_document_text(content: bytes, content_type: str) -> str:
    decoded = content.decode("utf-8", errors="ignore")
    if content_type == "application/pdf" or decoded.lstrip().startswith("%PDF"):
        decoded = _extract_pdfish_strings(decoded)
    decoded = decoded.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(_clean_line(line) for line in decoded.splitlines())


def _extract_pdfish_strings(text: str) -> str:
    literal_strings = re.findall(r"\(([^()]*)\)", text)
    if literal_strings:
        return "\n".join(literal_strings)
    return text


def _clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    return "".join(character for character in line if character.isprintable())


def _line_bbox(*, index: int, line_count: int) -> DocumentBoundingBox:
    row_height = 1 / (line_count + 2)
    y0 = min(0.95, row_height * (index + 1))
    y1 = min(0.98, y0 + row_height * 0.7)
    return DocumentBoundingBox(page=1, x0=0.08, y0=y0, x1=0.92, y1=y1)


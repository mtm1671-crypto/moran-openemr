from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Literal

from app.document_models import (
    DocumentSourceCitation,
    IntakeFact,
    LabResultFact,
    W2CitationSourceType,
    W2DocType,
    W2FactType,
)
from app.ocr_layout import DocumentLayout, LayoutLine


class ExtractionError(RuntimeError):
    pass


_KNOWN_LABS: dict[str, tuple[str, str | None]] = {
    "hemoglobin a1c": ("Hemoglobin A1c", "4548-4"),
    "a1c": ("Hemoglobin A1c", "4548-4"),
    "cholesterol, total": ("Total Cholesterol", "2093-3"),
    "total cholesterol": ("Total Cholesterol", "2093-3"),
    "hdl cholesterol": ("HDL Cholesterol", "2085-9"),
    "ldl cholesterol": ("LDL Cholesterol", "13457-7"),
    "triglycerides": ("Triglycerides", "2571-8"),
    "wbc": ("WBC", "6690-2"),
    "rbc": ("RBC", "789-8"),
    "hemoglobin": ("Hemoglobin", "718-7"),
    "hematocrit": ("Hematocrit", "4544-3"),
    "mcv": ("MCV", "787-2"),
    "platelets": ("Platelets", "777-3"),
    "creatinine": ("Creatinine", "2160-0"),
    "egfr": ("eGFR", "33914-3"),
    "bun": ("BUN", "3094-0"),
    "glucose": ("Glucose", "2345-7"),
    "fasting glucose": ("Glucose", "2345-7"),
    "sodium": ("Sodium", "2951-2"),
    "potassium": ("Potassium", "2823-3"),
    "chloride": ("Chloride", "2075-0"),
    "calcium": ("Calcium", "17861-6"),
    "alt": ("ALT", "1742-6"),
    "ast": ("AST", "1920-8"),
    "alkaline phosphatase": ("Alkaline Phosphatase", "6768-6"),
}

AbnormalFlag = Literal["low", "normal", "high", "abnormal", "unknown"]
IntakeFactType = Literal[
    W2FactType.intake_chief_concern,
    W2FactType.intake_medication,
    W2FactType.intake_allergy,
    W2FactType.intake_history,
]


def extract_typed_facts(
    *,
    doc_type: W2DocType,
    layout: DocumentLayout,
    source_id: str,
) -> list[LabResultFact | IntakeFact]:
    if doc_type == W2DocType.lab_pdf:
        return list(extract_lab_facts(layout=layout, source_id=source_id))
    if doc_type == W2DocType.intake_form:
        return list(extract_intake_facts(layout=layout, source_id=source_id))
    raise ExtractionError(f"Unsupported document type: {doc_type}")


def extract_lab_facts(*, layout: DocumentLayout, source_id: str) -> list[LabResultFact]:
    collection_date = _find_document_date(layout.lines)
    facts: list[LabResultFact] = []
    has_lab_table = any(_looks_like_lab_table_header(line.text) for line in layout.lines)
    inside_lab_table = not has_lab_table

    for index, line in enumerate(layout.lines):
        if _looks_like_lab_table_header(line.text):
            inside_lab_table = True
            continue
        if inside_lab_table and _looks_like_lab_table_stop(line.text):
            inside_lab_table = False
        if not inside_lab_table:
            continue
        if not _looks_like_lab_data_row(line.text):
            continue
        parsed = _parse_lab_line(_line_window(layout.lines, index, size=8), lab_line=line.text)
        if parsed is None:
            continue
        test_name, loinc_code, value, unit, reference_range, abnormal_flag = parsed
        citation = _citation(
            source_id=source_id,
            line=line,
            field_id=_stable_field_id("lab", test_name, value, line.text),
            quote_or_value=f"{test_name}: {value}{f' {unit}' if unit else ''}",
            confidence=0.93,
        )
        facts.append(
            LabResultFact(
                test_name=test_name,
                loinc_code=loinc_code,
                value=value,
                unit=unit,
                reference_range=reference_range,
                collection_date=collection_date,
                abnormal_flag=abnormal_flag,
                source_citation=citation,
                extraction_confidence=0.93,
            )
        )

    if not facts:
        raise ExtractionError("No supported laboratory facts were extracted")
    return facts


def extract_intake_facts(*, layout: DocumentLayout, source_id: str) -> list[IntakeFact]:
    facts: list[IntakeFact] = []
    sections = _section_lines(layout.lines)

    chief_concern = (
        sections.get("chief concern")
        or sections.get("reason for visit")
        or _heading_value(layout.lines, "chief concern")
    )
    if chief_concern is not None:
        facts.append(
            _intake_fact(
                fact_type=W2FactType.intake_chief_concern,
                label="Chief concern",
                value=chief_concern.text,
                source_id=source_id,
                line=chief_concern,
                confidence=0.91,
            )
        )

    medication_lines = _split_list_section(sections.get("medications"))
    if not medication_lines:
        medication_lines = _table_section_lines(layout.lines, "current medications")
    for line in medication_lines:
        facts.append(
            _intake_fact(
                fact_type=W2FactType.intake_medication,
                label="Patient-reported medication",
                value=line.text,
                source_id=source_id,
                line=line,
                confidence=0.87,
            )
        )

    allergy_lines = _split_list_section(sections.get("allergies"))
    if not allergy_lines:
        allergy_lines = _table_section_lines(layout.lines, "allergies")
    for line in allergy_lines:
        facts.append(
            _intake_fact(
                fact_type=W2FactType.intake_allergy,
                label="Patient-reported allergy",
                value=line.text,
                source_id=source_id,
                line=line,
                confidence=0.87,
            )
        )

    for key, label in [("family history", "Family history"), ("social history", "Social history")]:
        section_line = sections.get(key) or _heading_value(layout.lines, key)
        if section_line is not None:
            facts.append(
                _intake_fact(
                    fact_type=W2FactType.intake_history,
                    label=label,
                    value=section_line.text,
                    source_id=source_id,
                    line=section_line,
                    confidence=0.84,
                )
            )

    if not facts:
        raise ExtractionError("No supported intake facts were extracted")
    return facts


def _parse_lab_line(
    line: str,
    *,
    lab_line: str | None = None,
) -> tuple[str, str | None, str, str | None, str | None, AbnormalFlag] | None:
    match_line = lab_line or line
    matched: tuple[str, str | None, int] | None = None
    for key, lab_tuple in _KNOWN_LABS.items():
        match = _known_lab_match(match_line, key)
        if match is not None:
            matched = (lab_tuple[0], lab_tuple[1], match.end())
            break
    if matched is None:
        return None

    test_name, loinc_code, search_start = matched
    result_text = line[search_start:]
    numeric = re.search(r"(?<!\d)(?:<|>)?\d+(?:\.\d+)?(?!\d)", result_text)
    if numeric is None:
        return None

    value = numeric.group(0)
    suffix = _trim_at_next_lab(result_text[numeric.end() :]).strip()
    unit = _unit_from_suffix(suffix)
    reference_range = _reference_range_from_suffix(suffix)
    abnormal_flag = _abnormal_flag(suffix)
    return test_name, loinc_code, value, unit, reference_range, abnormal_flag


def _known_lab_match(line: str, key: str) -> re.Match[str] | None:
    return re.search(rf"(?<![A-Za-z0-9-]){re.escape(key)}(?![A-Za-z0-9])", line, re.IGNORECASE)


def _trim_at_next_lab(text: str) -> str:
    offsets: list[int] = []
    for key in _KNOWN_LABS:
        match = _known_lab_match(text, key)
        if match is not None:
            offsets.append(match.start())
    if not offsets:
        return text
    return text[: min(offsets)]


def _looks_like_lab_data_row(line: str) -> bool:
    lowered = line.lower()
    if any(
        marker in lowered
        for marker in [
            "interpretation:",
            "interpretive comments",
            "recommend ",
            "reference ranges",
            "reviewed ",
            "loinc ",
        ]
    ):
        return False
    for key in _KNOWN_LABS:
        match = _known_lab_match(line, key)
        if match is None:
            continue
        suffix = line[match.end() :]
        if re.search(r"(?<!\d)(?:<|>)?\d+(?:\.\d+)?(?!\d)", suffix):
            return True
        if line.strip().endswith(","):
            return True
    return False


def _looks_like_lab_table_header(line: str) -> bool:
    lowered = line.lower()
    return "test" in lowered and "result" in lowered and (
        "reference" in lowered or "flag" in lowered or "units" in lowered
    )


def _looks_like_lab_table_stop(line: str) -> bool:
    lowered = line.lower()
    return any(
        lowered.startswith(marker)
        for marker in [
            "interpretive comments",
            "interpretation:",
            "comments",
            "reviewed ",
            "released ",
            "reference ranges",
        ]
    )


def _unit_from_suffix(suffix: str) -> str | None:
    unit_match = re.search(
        r"(%|mg/dL|mmol/L|mL/min/1\.73m(?:2|²)|mEq/L|U/L|g/dL|10\^3/uL|10\^6/uL|fL)",
        suffix,
        re.IGNORECASE,
    )
    return unit_match.group(1) if unit_match else None


def _reference_range_from_suffix(suffix: str) -> str | None:
    range_match = re.search(
        r"(?:ref(?:erence)?(?: range)?[: ]*)?([<>]?\d+(?:\.\d+)?\s*-\s*[<>]?\d+(?:\.\d+)?)",
        suffix,
        re.IGNORECASE,
    )
    return range_match.group(1) if range_match else None


def _abnormal_flag(line: str) -> AbnormalFlag:
    tokens = re.findall(r"[A-Za-z]+", line.lower())
    candidates = [*tokens[:4], *tokens[-2:]]
    for flag_token in candidates:
        if flag_token in {"h", "high"}:
            return "high"
        if flag_token in {"l", "low"}:
            return "low"
        if flag_token in {"abnormal", "critical"}:
            return "abnormal"
        if flag_token in {"n", "normal"}:
            return "normal"
    return "unknown"


def _find_document_date(lines: list[LayoutLine]) -> date | None:
    for line in lines:
        match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", line.text)
        if match:
            return date.fromisoformat(match.group(1))
    return None


def _section_lines(lines: list[LayoutLine]) -> dict[str, LayoutLine]:
    sections: dict[str, LayoutLine] = {}
    for line in lines:
        if ":" not in line.text:
            continue
        label, value = line.text.split(":", 1)
        normalized_label = label.strip().lower()
        cleaned_value = value.strip()
        if not cleaned_value:
            continue
        sections[normalized_label] = LayoutLine(
            page=line.page,
            line_index=line.line_index,
            text=cleaned_value,
            bbox=line.bbox,
        )
    return sections


def _line_window(lines: list[LayoutLine], index: int, *, size: int) -> str:
    return " ".join(line.text for line in lines[index : index + size])


def _heading_value(lines: list[LayoutLine], heading: str) -> LayoutLine | None:
    start = _heading_index(lines, heading)
    if start is None:
        return None
    values: list[str] = []
    first_line = lines[start]
    inline_value = _value_after_heading(first_line.text, heading)
    if inline_value:
        values.append(inline_value)
    for line in lines[start + 1 :]:
        if _looks_like_table_header(line.text):
            continue
        if _looks_like_heading(line.text):
            break
        values.append(line.text)
        if len(values) >= 3:
            break
    if not values:
        return None
    return LayoutLine(
        page=first_line.page,
        line_index=first_line.line_index,
        text=" ".join(values),
        bbox=first_line.bbox,
    )


def _table_section_lines(lines: list[LayoutLine], heading: str) -> list[LayoutLine]:
    start = _heading_index(lines, heading)
    if start is None:
        return []
    values: list[LayoutLine] = []
    for line in lines[start + 1 :]:
        if _looks_like_table_header(line.text):
            continue
        if _looks_like_heading(line.text):
            break
        if _looks_like_section_data_row(line.text, heading):
            values.append(line)
        elif values and _looks_like_table_continuation(line.text):
            previous = values[-1]
            values[-1] = LayoutLine(
                page=previous.page,
                line_index=previous.line_index,
                text=f"{previous.text} {line.text}",
                bbox=previous.bbox,
            )
            continue
        if len(values) >= 8:
            break
    return values


def _heading_index(lines: list[LayoutLine], heading: str) -> int | None:
    normalized_heading = heading.lower()
    for index, line in enumerate(lines):
        normalized_line = line.text.lower().strip(" :")
        if normalized_line == normalized_heading or normalized_line.startswith(f"{normalized_heading} "):
            return index
    return None


def _value_after_heading(text: str, heading: str) -> str | None:
    normalized_text = text.lower().strip()
    normalized_heading = heading.lower()
    if not normalized_text.startswith(f"{normalized_heading} "):
        return None
    value = text[len(heading) :].strip(" :-")
    return value or None


def _looks_like_heading(text: str) -> bool:
    cleaned = re.sub(r"[^A-Za-z /&-]", "", text).strip()
    if len(cleaned) < 4:
        return False
    letters = [character for character in cleaned if character.isalpha()]
    return bool(letters) and "".join(letters).isupper()


def _looks_like_table_header(text: str) -> bool:
    lowered = text.lower()
    header_terms = [
        "medication dose",
        "allergen reaction",
        "substance reaction",
        "condition icd",
        "relation condition",
        "test result flag",
    ]
    return any(term in lowered for term in header_terms)


def _looks_like_data_row(text: str) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in ["signature", "date ", "page ", "hipaa confidential"]):
        return False
    return bool(re.search(r"\d|nkda|penicillin|ibuprofen|lisinopril|metformin|atorvastatin|apixaban|tamsulosin", lowered))


def _looks_like_section_data_row(text: str, heading: str) -> bool:
    lowered = text.lower()
    normalized_heading = heading.lower()
    if "allerg" in normalized_heading:
        return lowered.startswith(
            (
                "nkda",
                "penicillin",
                "sulfa",
                "shellfish",
                "iodine",
            )
        )
    return _looks_like_data_row(text)


def _looks_like_table_continuation(text: str) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in ["signature", "date ", "page ", "hipaa confidential"]):
        return False
    if _looks_like_table_header(text) or _looks_like_heading(text):
        return False
    return bool(re.search(r"[A-Za-z0-9]", text))


def _split_list_section(line: LayoutLine | None) -> list[LayoutLine]:
    if line is None:
        return []
    values = [value.strip() for value in re.split(r",|;", line.text) if value.strip()]
    if not values or values == [line.text]:
        return [line]
    return [
        LayoutLine(page=line.page, line_index=line.line_index, text=value, bbox=line.bbox)
        for value in values
    ]


def _intake_fact(
    *,
    fact_type: IntakeFactType,
    label: str,
    value: str,
    source_id: str,
    line: LayoutLine,
    confidence: float,
) -> IntakeFact:
    return IntakeFact(
        fact_type=fact_type,
        label=label,
        value=value,
        source_citation=_citation(
            source_id=source_id,
            line=line,
            field_id=_stable_field_id("intake", label, value),
            quote_or_value=value,
            confidence=confidence,
        ),
        extraction_confidence=confidence,
    )


def _citation(
    *,
    source_id: str,
    line: LayoutLine,
    field_id: str,
    quote_or_value: str,
    confidence: float,
) -> DocumentSourceCitation:
    return DocumentSourceCitation(
        source_type=W2CitationSourceType.local_document,
        source_id=source_id,
        page_or_section=f"page-{line.page}",
        field_or_chunk_id=field_id,
        quote_or_value=quote_or_value,
        bbox=line.bbox,
        confidence=confidence,
    )


def _stable_field_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).lower().encode("utf-8")).hexdigest()
    return digest[:24]

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
    "ldl cholesterol": ("LDL Cholesterol", "13457-7"),
    "creatinine": ("Creatinine", "2160-0"),
    "egfr": ("eGFR", "33914-3"),
    "glucose": ("Glucose", "2345-7"),
    "sodium": ("Sodium", "2951-2"),
    "potassium": ("Potassium", "2823-3"),
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

    for line in layout.lines:
        parsed = _parse_lab_line(line.text)
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

    chief_concern = sections.get("chief concern") or sections.get("reason for visit")
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

    for line in _split_list_section(sections.get("medications")):
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

    for line in _split_list_section(sections.get("allergies")):
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
        section_line = sections.get(key)
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
) -> tuple[str, str | None, str, str | None, str | None, AbnormalFlag] | None:
    lowered = line.lower()
    matched: tuple[str, str | None, int] | None = None
    for key, lab_tuple in _KNOWN_LABS.items():
        label_index = lowered.find(key)
        if label_index >= 0:
            matched = (lab_tuple[0], lab_tuple[1], label_index + len(key))
            break
    if matched is None:
        return None

    test_name, loinc_code, search_start = matched
    numeric = re.search(r"(?<!\d)(?:<|>)?\d+(?:\.\d+)?(?!\d)", line[search_start:])
    if numeric is None:
        return None

    value = numeric.group(0)
    suffix = line[search_start + numeric.end() :].strip()
    unit = _unit_from_suffix(suffix)
    reference_range = _reference_range_from_suffix(suffix)
    abnormal_flag = _abnormal_flag(line)
    return test_name, loinc_code, value, unit, reference_range, abnormal_flag


def _unit_from_suffix(suffix: str) -> str | None:
    unit_match = re.search(r"(%|mg/dL|mmol/L|mL/min/1\.73m2|mEq/L|U/L|g/dL)", suffix, re.IGNORECASE)
    return unit_match.group(1) if unit_match else None


def _reference_range_from_suffix(suffix: str) -> str | None:
    range_match = re.search(
        r"(?:ref(?:erence)?(?: range)?[: ]*)?([<>]?\d+(?:\.\d+)?\s*-\s*[<>]?\d+(?:\.\d+)?)",
        suffix,
        re.IGNORECASE,
    )
    return range_match.group(1) if range_match else None


def _abnormal_flag(line: str) -> AbnormalFlag:
    lowered = line.lower()
    if re.search(r"\b(h|high)\b", lowered):
        return "high"
    if re.search(r"\b(l|low)\b", lowered):
        return "low"
    if re.search(r"\b(abnormal|critical)\b", lowered):
        return "abnormal"
    if re.search(r"\b(n|normal)\b", lowered):
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

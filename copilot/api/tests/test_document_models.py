import base64

import pytest
from pydantic import ValidationError

from app.document_models import (
    DocumentAttachExtractRequest,
    DocumentBoundingBox,
    DocumentSourceCitation,
    LabResultFact,
    W2CitationSourceType,
)


def test_document_bounding_box_rejects_inverted_coordinates() -> None:
    with pytest.raises(ValidationError):
        DocumentBoundingBox(page=1, x0=0.5, y0=0.1, x1=0.4, y1=0.2)


def test_document_citation_requires_bbox_for_document_sources() -> None:
    with pytest.raises(ValidationError):
        DocumentSourceCitation(
            source_type=W2CitationSourceType.local_document,
            source_id="local-doc",
            page_or_section="page-1",
            field_or_chunk_id="lab-a1c",
            quote_or_value="A1c 8.6 %",
            confidence=0.9,
        )


def test_lab_result_fact_accepts_source_backed_value() -> None:
    citation = DocumentSourceCitation(
        source_type=W2CitationSourceType.local_document,
        source_id="local-doc",
        page_or_section="page-1",
        field_or_chunk_id="lab-a1c",
        quote_or_value="A1c 8.6 %",
        bbox=DocumentBoundingBox(page=1, x0=0.1, y0=0.1, x1=0.9, y1=0.2),
        confidence=0.93,
    )

    fact = LabResultFact(
        test_name="Hemoglobin A1c",
        loinc_code="4548-4",
        value="8.6",
        unit="%",
        reference_range="4.0-5.6",
        collection_date="2026-03-12",
        abnormal_flag="high",
        source_citation=citation,
        extraction_confidence=0.93,
    )

    assert fact.test_name == "Hemoglobin A1c"
    assert fact.source_citation.bbox is not None


def test_attach_request_decodes_bounded_base64_content() -> None:
    request = DocumentAttachExtractRequest(
        patient_id="p1",
        doc_type="lab_pdf",
        filename="lab.txt",
        content_type="text/plain",
        content_base64=base64.b64encode(b"Hemoglobin A1c 8.6 % H").decode("ascii"),
    )

    assert request.decoded_content() == b"Hemoglobin A1c 8.6 % H"


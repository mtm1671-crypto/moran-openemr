from app.document_models import W2DocType
from app.extraction_pipeline import extract_document_facts


def test_extract_lab_document_returns_review_required_source_backed_facts() -> None:
    content = b"""
    Patient: Synthetic Demo
    Collection Date: 2026-03-12
    Hemoglobin A1c 8.6 % reference range 4.0-5.6 H
    LDL Cholesterol 142 mg/dL reference range 0-99 H
    Creatinine 1.1 mg/dL reference range 0.7-1.3 N
    """

    facts = extract_document_facts(
        job_id="job-1",
        patient_id="p1",
        doc_type=W2DocType.lab_pdf,
        source_id="source-1",
        content=content,
        content_type="text/plain",
    )

    assert [fact.display_label for fact in facts] == [
        "Hemoglobin A1c",
        "LDL Cholesterol",
        "Creatinine",
    ]
    assert facts[0].normalized_value == "8.6 % on 2026-03-12 (high)"
    assert facts[0].citation.bbox is not None
    assert facts[0].blocking_reasons == []


def test_extract_intake_document_keeps_facts_as_derived_evidence() -> None:
    content = b"""
    Chief Concern: Follow up for diabetes and fatigue
    Medications: Metformin 1000 mg twice daily, Atorvastatin 40 mg nightly
    Allergies: Penicillin - rash
    Family History: Father with myocardial infarction at 58
    Social History: Misses doses when work shifts change
    """

    facts = extract_document_facts(
        job_id="job-2",
        patient_id="p1",
        doc_type=W2DocType.intake_form,
        source_id="source-2",
        content=content,
        content_type="text/plain",
    )

    assert len(facts) == 6
    assert {fact.proposed_destination.value for fact in facts} == {"derived_evidence"}
    assert any(fact.normalized_value == "Penicillin - rash" for fact in facts)
    assert all(fact.citation.bbox is not None for fact in facts)


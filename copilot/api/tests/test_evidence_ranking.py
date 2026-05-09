from datetime import UTC, datetime

from app.evidence_ranking import rank_evidence_for_query, sparse_search_evidence
from app.guideline_rag import guideline_hits_to_evidence, retrieve_guideline_chunks
from app.models import EvidenceObject


def test_sparse_search_finds_lab_name_without_dense_vectors() -> None:
    evidence = [
        _evidence("ldl", "lab_result", "LDL Cholesterol was 158 mg/dL on 2026-04-23."),
        _evidence("creatinine", "lab_result", "Creatinine was 1.6 mg/dL on 2026-05-02."),
    ]

    hits = sparse_search_evidence(
        message="What creatinine abnormality is in the new lab?",
        evidence=evidence,
        limit=1,
    )

    assert [item.source_id for item in hits] == ["creatinine"]


def test_reranker_prioritizes_demographics_over_unrelated_labs() -> None:
    evidence = [
        _evidence("ldl", "lab_result", "LDL Cholesterol was 158 mg/dL on 2026-04-23."),
        _evidence("name", "patient_demographics", "Patient name is Margaret Chen.", field="name"),
        _evidence("dob", "patient_demographics", "Patient birth date is 1967-08-14.", field="birthDate"),
    ]

    ranked = rank_evidence_for_query(
        message="What is the patient name and DOB?",
        evidence=evidence,
        limit=2,
    )

    assert {item.source_id for item in ranked.evidence} == {"dob", "name"}
    assert ranked.sparse_hit_count == 2


def test_guideline_evidence_keeps_source_chunk_metadata() -> None:
    hits = retrieve_guideline_chunks(
        question="What diabetes A1c guideline context matters?",
        patient_facts=[],
        extracted_facts=["Hemoglobin A1c was 8.6 %."],
        limit=1,
    )

    evidence = guideline_hits_to_evidence(patient_id="p1", hits=hits)

    assert evidence
    assert evidence[0].source_type == "guideline"
    assert evidence[0].metadata["retrieval_mode"] == "hybrid_sparse_dense_guideline_rag"
    assert evidence[0].metadata["corpus_id"] == "af-w2-primary-care-guidelines-v1"
    assert evidence[0].metadata["source_id"] == evidence[0].source_id
    assert evidence[0].metadata["section"]
    assert evidence[0].metadata["section_heading"]
    assert evidence[0].metadata["snippet"]
    assert evidence[0].metadata["sparse_score"] >= 0
    assert evidence[0].metadata["dense_score"] >= 0


def _evidence(
    source_id: str,
    source_type: str,
    fact: str,
    *,
    field: str | None = None,
) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=f"ev_{source_id}",
        patient_id="p1",
        source_type=source_type,
        source_id=source_id,
        display_name=source_id,
        fact=fact,
        retrieved_at=datetime.now(tz=UTC),
        metadata={"field": field} if field else {},
    )

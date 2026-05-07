from datetime import UTC, datetime

import pytest

from app.models import Citation, EvidenceObject, VerifiedAnswer
from app.verifier import VerificationError, verify_answer


def test_verifier_rejects_cross_patient_citation() -> None:
    evidence = [
        EvidenceObject(
            evidence_id="ev1",
            patient_id="patient-a",
            source_type="lab",
            source_id="lab1",
            display_name="A1c",
            fact="A1c was 8.6%",
            retrieved_at=datetime.now(tz=UTC),
        )
    ]
    answer = VerifiedAnswer(
        answer="A1c was 8.6% [A1c]",
        citations=[Citation(evidence_id="ev1", label="A1c")],
        audit={},
    )

    with pytest.raises(VerificationError):
        verify_answer(answer, evidence, "patient-b")


def test_verifier_rejects_citation_url_that_does_not_match_evidence() -> None:
    evidence = [
        EvidenceObject(
            evidence_id="ev1",
            patient_id="patient-a",
            source_type="lab",
            source_id="lab1",
            display_name="A1c",
            fact="A1c was 8.6%",
            source_url="/api/source/openemr/Observation/o1?patient_id=patient-a",
            retrieved_at=datetime.now(tz=UTC),
        )
    ]
    answer = VerifiedAnswer(
        answer="A1c was 8.6% [A1c]",
        citations=[Citation(evidence_id="ev1", label="A1c", source_url="https://evil.example")],
        audit={},
    )

    with pytest.raises(VerificationError, match="source URL"):
        verify_answer(answer, evidence, "patient-a")


def test_verifier_rejects_wrong_numeric_value_even_with_valid_citation() -> None:
    evidence = [
        EvidenceObject(
            evidence_id="ev1",
            patient_id="patient-a",
            source_type="lab",
            source_id="lab1",
            display_name="A1c",
            fact="A1c was 8.6% on 2026-03-12.",
            retrieved_at=datetime.now(tz=UTC),
        )
    ]
    answer = VerifiedAnswer(
        answer="A1c was 6.8% on 2026-03-12 [A1c]",
        citations=[Citation(evidence_id="ev1", label="A1c")],
        audit={},
    )

    with pytest.raises(VerificationError, match="not present in cited evidence"):
        verify_answer(answer, evidence, "patient-a")

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

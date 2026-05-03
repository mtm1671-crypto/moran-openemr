from app.models import EvidenceObject, VerifiedAnswer


class VerificationError(ValueError):
    pass


def verify_answer(answer: VerifiedAnswer, evidence: list[EvidenceObject], patient_id: str) -> None:
    evidence_by_id = {item.evidence_id: item for item in evidence}

    for citation in answer.citations:
        item = evidence_by_id.get(citation.evidence_id)
        if item is None:
            raise VerificationError(f"Unknown evidence id: {citation.evidence_id}")
        if item.patient_id != patient_id:
            raise VerificationError("Citation does not belong to the selected patient")
        if citation.source_url != item.source_url:
            raise VerificationError("Citation source URL does not match verified evidence")

    if "recommend" in answer.answer.lower() or "should prescribe" in answer.answer.lower():
        raise VerificationError("Treatment recommendation detected in MVP answer")

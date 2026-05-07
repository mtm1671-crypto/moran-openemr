import re

from app.models import EvidenceObject, VerifiedAnswer


class VerificationError(ValueError):
    pass


def verify_answer(answer: VerifiedAnswer, evidence: list[EvidenceObject], patient_id: str) -> None:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    cited_evidence: list[EvidenceObject] = []

    for citation in answer.citations:
        item = evidence_by_id.get(citation.evidence_id)
        if item is None:
            raise VerificationError(f"Unknown evidence id: {citation.evidence_id}")
        if item.patient_id != patient_id:
            raise VerificationError("Citation does not belong to the selected patient")
        if citation.source_url != item.source_url:
            raise VerificationError("Citation source URL does not match verified evidence")
        cited_evidence.append(item)

    if cited_evidence:
        unsupported_values = _unsupported_value_tokens(answer.answer, cited_evidence)
        if unsupported_values:
            raise VerificationError(
                "Answer contains values or dates not present in cited evidence: "
                + ", ".join(unsupported_values[:5])
            )

    if "recommend" in answer.answer.lower() or "should prescribe" in answer.answer.lower():
        raise VerificationError("Treatment recommendation detected in MVP answer")


def _unsupported_value_tokens(answer_text: str, cited_evidence: list[EvidenceObject]) -> list[str]:
    evidence_parts: list[str] = []
    for item in cited_evidence:
        evidence_parts.extend(
            [
                item.display_name,
                item.fact,
                str(item.effective_at.date()) if item.effective_at else "",
                str(item.metadata.get("value") or ""),
            ]
        )
    evidence_text = " ".join(evidence_parts)
    normalized_evidence = _normalize_for_value_check(evidence_text)
    unsupported: list[str] = []
    for token in _answer_value_tokens(answer_text):
        if token not in normalized_evidence:
            unsupported.append(token)
    return unsupported


def _answer_value_tokens(answer_text: str) -> list[str]:
    cleaned = re.sub(r"(?m)^\s*\d+\.\s*", "", answer_text)
    cleaned = re.sub(r"\[[^\]]+\]", "", cleaned)
    tokens = [
        *re.findall(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b", cleaned),
        *re.findall(r"(?<![A-Za-z0-9])(?:<|>)?\d+(?:\.\d+)?%?(?![A-Za-z0-9])", cleaned),
    ]
    return [token.rstrip("%") for token in tokens if token not in {"0", "1"}]


def _normalize_for_value_check(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("%", "")).strip()

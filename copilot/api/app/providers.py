from typing import Protocol

from app.models import Citation, EvidenceObject, VerifiedAnswer


class ProviderAdapter(Protocol):
    async def answer(
        self,
        *,
        patient_id: str,
        user_message: str,
        evidence: list[EvidenceObject],
    ) -> VerifiedAnswer:
        ...


class MockProviderAdapter:
    _max_facts = 5

    async def answer(
        self,
        *,
        patient_id: str,
        user_message: str,
        evidence: list[EvidenceObject],
    ) -> VerifiedAnswer:
        if not evidence:
            return VerifiedAnswer(
                answer=(
                    "I could not find source-backed chart facts for that question in the retrieved "
                    "OpenEMR records."
                ),
                citations=[],
                audit={
                    "patient_id": patient_id,
                    "provider": "mock",
                    "verification": "no_evidence_available",
                    "requested": user_message,
                },
            )

        selected = self._select_evidence(user_message, evidence)
        return VerifiedAnswer(
            answer="Source-backed chart facts:\n"
            + "\n".join(f"{index}. {item.fact} [{item.display_name}]" for index, item in enumerate(selected, 1)),
            citations=[
                Citation(
                    evidence_id=item.evidence_id,
                    label=item.display_name,
                    source_url=item.source_url,
                )
                for item in selected
            ],
            audit={
                "patient_id": patient_id,
                "provider": "mock",
                "verification": "pending",
                "evidence_count": len(evidence),
                "evidence_used_count": len(selected),
                "reasoning_summary": (
                    "Retrieved selected-patient chart evidence, limited the response to cited facts, "
                    "and skipped treatment recommendations."
                ),
            },
        )

    def _select_evidence(self, user_message: str, evidence: list[EvidenceObject]) -> list[EvidenceObject]:
        text = user_message.lower()
        wants_broad_brief = any(
            term in text for term in ["before seeing", "know", "brief", "summary", "overview"]
        )
        wants_labs = any(term in text for term in ["lab", "a1c", "result", "abnormal", "creatinine", "egfr"])
        wants_problems = any(term in text for term in ["problem", "history", "condition", "diagnosis"])
        wants_medications = any(
            term in text for term in ["medication", "medicine", "meds", "prescription", "drug"]
        )
        wants_allergies = any(term in text for term in ["allergy", "allergies", "intolerance"])
        wants_notes = any(
            term in text
            for term in ["note", "notes", "visit", "hpi", "assessment", "subjective", "narrative"]
        )

        if wants_broad_brief:
            notes = self._by_type(evidence, "clinical_note", limit=1)
            ordered = [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_type(evidence, "active_problem", limit=2),
                *self._by_type(evidence, "lab_result", limit=1 if notes else 2),
                *notes,
            ]
            return self._fill_selection(ordered, evidence)

        if wants_labs:
            ordered = [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_type(evidence, "lab_result", limit=4),
            ]
            return self._fill_selection(ordered, evidence)

        if wants_problems:
            ordered = [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_type(evidence, "active_problem", limit=4),
            ]
            return self._fill_selection(ordered, evidence)

        if wants_medications:
            ordered = [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_type(evidence, "medication", limit=4),
            ]
            return self._fill_selection(ordered, evidence)

        if wants_allergies:
            ordered = [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_type(evidence, "allergy", limit=4),
            ]
            return self._fill_selection(ordered, evidence)

        if wants_notes:
            ordered = [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_type(evidence, "clinical_note", limit=4),
            ]
            return self._fill_selection(ordered, evidence)

        return evidence[: self._max_facts]

    def _by_type(
        self,
        evidence: list[EvidenceObject],
        source_type: str,
        *,
        limit: int,
    ) -> list[EvidenceObject]:
        return [item for item in evidence if item.source_type == source_type][:limit]

    def _fill_selection(
        self,
        selected: list[EvidenceObject],
        evidence: list[EvidenceObject],
    ) -> list[EvidenceObject]:
        seen = {item.evidence_id for item in selected}
        for item in evidence:
            if len(selected) >= self._max_facts:
                break
            if item.evidence_id in seen:
                continue
            selected.append(item)
            seen.add(item.evidence_id)
        return selected[: self._max_facts]

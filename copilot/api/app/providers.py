import re
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
            return self._no_matching_evidence(patient_id, user_message)

        selected = self._select_evidence(user_message, evidence)
        if not selected:
            return self._no_matching_evidence(patient_id, user_message)
        answer_lines = self._answer_lines(selected)
        return VerifiedAnswer(
            answer="Source-backed chart facts:\n" + "\n".join(answer_lines),
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
        tokens = set(re.findall(r"[a-z0-9]+", text))
        wants_demographics = any(
            term in tokens
            for term in ["demographic", "demographics", "name", "birth", "dob", "gender", "age"]
        ) or "date of birth" in text
        wants_broad_brief = (
            "before seeing" in text
            or "pre-room" in text
            or any(term in tokens for term in ["know", "brief", "summary", "overview"])
        )
        wants_guidelines = any(term in tokens for term in ["guideline", "guidelines", "context"])
        wants_labs = any(
            term in tokens
            for term in [
                "lab",
                "labs",
                "a1c",
                "result",
                "results",
                "abnormal",
                "abnormalities",
                "creatinine",
                "egfr",
                "cholesterol",
                "lipid",
                "ldl",
                "hdl",
                "triglyceride",
                "glucose",
                "potassium",
                "alt",
                "ast",
                "cbc",
                "platelet",
                "platelets",
                "kidney",
            ]
        )
        wants_problems = any(term in tokens for term in ["problem", "problems", "history", "condition", "diagnosis"])
        wants_medications = any(
            term in tokens for term in ["medication", "medications", "medicine", "meds", "prescription", "drug"]
        )
        wants_allergies = any(term in tokens for term in ["allergy", "allergies", "intolerance"])
        wants_notes = any(
            term in tokens
            for term in ["note", "notes", "visit", "hpi", "assessment", "subjective", "narrative"]
        )
        wants_document_context = wants_notes or any(
            term in tokens
            for term in [
                "social",
                "barrier",
                "barriers",
                "intake",
                "family",
                "tobacco",
                "alcohol",
                "recreational",
                "substance",
                "substances",
                "drug",
                "drugs",
                "transportation",
                "work",
                "shift",
            ]
        ) or "work shift" in text

        if wants_broad_brief:
            notes = self._by_document_context(evidence, limit=1)
            ordered = [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_type(evidence, "active_problem", limit=2),
                *self._by_type(evidence, "lab_result", limit=1 if notes else 2),
                *notes,
                *(self._by_type(evidence, "guideline", limit=1) if wants_guidelines else []),
            ]
            return self._fill_selection(ordered, evidence)

        if wants_demographics:
            return self._by_type(evidence, "patient_demographics", limit=3)

        if wants_labs:
            return [
                *self._by_type(evidence, "lab_result", limit=4),
                *self._by_type(evidence, "patient_demographics", limit=1),
                *(self._by_type(evidence, "guideline", limit=2) if wants_guidelines else []),
            ][: self._max_facts]

        if wants_medications and wants_allergies:
            return [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_any_type(evidence, {"medication", "intake_medication"}, limit=2),
                *self._by_any_type(evidence, {"allergy", "intake_allergy"}, limit=2),
            ]

        if wants_document_context:
            return [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_document_context(evidence, limit=4),
            ]

        if wants_problems:
            return [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_type(evidence, "active_problem", limit=4),
            ]

        if wants_medications:
            return [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_any_type(evidence, {"medication", "intake_medication"}, limit=4),
            ]

        if wants_allergies:
            return [
                *self._by_type(evidence, "patient_demographics", limit=1),
                *self._by_any_type(evidence, {"allergy", "intake_allergy"}, limit=4),
            ]

        return evidence[: self._max_facts]

    def _answer_lines(self, selected: list[EvidenceObject]) -> list[str]:
        patient_facts = [item for item in selected if item.source_type != "guideline"]
        guideline_facts = [item for item in selected if item.source_type == "guideline"]
        if not guideline_facts:
            return [
                f"{index}. {item.fact} [{item.display_name}]"
                for index, item in enumerate(selected, 1)
            ]

        lines: list[str] = []
        if patient_facts:
            lines.append("Patient-record facts:")
            lines.extend(
                f"{index}. {item.fact} [{item.display_name}]"
                for index, item in enumerate(patient_facts, 1)
            )
        lines.append("Guideline evidence:")
        offset = len(patient_facts)
        lines.extend(
            f"{offset + index}. {item.fact} [{item.display_name}]"
            for index, item in enumerate(guideline_facts, 1)
        )
        return lines

    def _by_type(
        self,
        evidence: list[EvidenceObject],
        source_type: str,
        *,
        limit: int,
    ) -> list[EvidenceObject]:
        return [item for item in evidence if item.source_type == source_type][:limit]

    def _by_any_type(
        self,
        evidence: list[EvidenceObject],
        source_types: set[str],
        *,
        limit: int,
    ) -> list[EvidenceObject]:
        return [item for item in evidence if item.source_type in source_types][:limit]

    def _by_document_context(
        self,
        evidence: list[EvidenceObject],
        *,
        limit: int,
    ) -> list[EvidenceObject]:
        return [
            item
            for item in evidence
            if item.source_type == "clinical_note"
            or item.source_type.startswith("intake_")
            or item.metadata.get("schema") == "w2_document_fact_v1"
        ][:limit]

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

    def _no_matching_evidence(self, patient_id: str, user_message: str) -> VerifiedAnswer:
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

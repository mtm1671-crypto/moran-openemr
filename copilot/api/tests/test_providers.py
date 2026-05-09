from datetime import UTC, datetime

import pytest

from app.models import EvidenceObject
from app.providers import MockProviderAdapter


@pytest.mark.asyncio
async def test_mock_provider_balances_broad_brief_across_identity_problems_and_labs() -> None:
    evidence = [
        _evidence("name", "patient_demographics", "Patient name is Elena Morrison."),
        _evidence("dob", "patient_demographics", "Patient birth date is 1972-09-18."),
        _evidence("gender", "patient_demographics", "Patient gender is female."),
        _evidence("dm", "active_problem", "Active problem: Type 2 diabetes mellitus."),
        _evidence("htn", "active_problem", "Active problem: Essential hypertension."),
        _evidence("ckd", "active_problem", "Active problem: Stage 3a chronic kidney disease."),
        _evidence("a1c", "lab_result", "Hemoglobin A1c was 8.6 %."),
        _evidence("cr", "lab_result", "Creatinine was 1.28 mg/dL."),
    ]

    answer = await MockProviderAdapter().answer(
        patient_id="p1",
        user_message="What should I know before seeing this patient?",
        evidence=evidence,
    )

    assert "Patient name is Elena Morrison." in answer.answer
    assert "Type 2 diabetes mellitus" in answer.answer
    assert "Essential hypertension" in answer.answer
    assert "Hemoglobin A1c was 8.6 %." in answer.answer
    assert "Creatinine was 1.28 mg/dL." in answer.answer
    assert "Patient birth date is 1972-09-18." not in answer.answer
    assert len(answer.citations) == 5


@pytest.mark.asyncio
async def test_mock_provider_does_not_answer_demographic_question_with_lab_facts() -> None:
    answer = await MockProviderAdapter().answer(
        patient_id="p1",
        user_message="What is the patient name and date of birth?",
        evidence=[_evidence("ldl", "lab_result", "LDL Cholesterol was 158 mg/dL.")],
    )

    assert "could not find source-backed chart facts" in answer.answer
    assert answer.citations == []
    assert answer.audit["verification"] == "no_evidence_available"


@pytest.mark.asyncio
async def test_mock_provider_separates_patient_facts_from_guideline_evidence() -> None:
    answer = await MockProviderAdapter().answer(
        patient_id="p1",
        user_message="What changed in this A1c and what guideline context matters?",
        evidence=[
            _evidence("a1c", "lab_result", "Hemoglobin A1c was 8.6 %."),
            _evidence(
                "a1c-guideline",
                "guideline",
                "Guideline context (diabetes): A1c monitoring. Use recent A1c values.",
            ),
        ],
    )

    assert "Patient-record facts:" in answer.answer
    assert "Guideline evidence:" in answer.answer
    assert "Hemoglobin A1c was 8.6 %." in answer.answer
    assert "Guideline context (diabetes)" in answer.answer
    assert len(answer.citations) == 2


def _evidence(source_id: str, source_type: str, fact: str) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=f"ev_{source_id}",
        patient_id="p1",
        source_type=source_type,
        source_id=source_id,
        display_name=source_id,
        fact=fact,
        retrieved_at=datetime.now(tz=UTC),
    )

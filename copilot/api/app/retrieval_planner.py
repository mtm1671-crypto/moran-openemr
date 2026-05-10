"""Deterministic retrieval planning for low-latency evidence budgets.

The planner is intentionally local and rule based. It decides which source
families are worth touching before any model/provider work happens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalPlan:
    intent: str
    evidence_limit: int
    fhir_tools: tuple[str, ...] = ()
    use_demo_evidence: bool = True
    use_approved_documents: bool = True
    approved_document_source_types: tuple[str, ...] = ()
    use_guidelines: bool = False
    use_vector_search: bool = False

    def cache_key(self) -> str:
        return "|".join(
            [
                self.intent,
                str(self.evidence_limit),
                ",".join(self.fhir_tools),
                "demo" if self.use_demo_evidence else "no-demo",
                "docs" if self.use_approved_documents else "no-docs",
                ",".join(self.approved_document_source_types),
                "guidelines" if self.use_guidelines else "no-guidelines",
                "vector" if self.use_vector_search else "no-vector",
            ]
        )

    def audit_payload(self) -> dict[str, object]:
        return {
            "intent": self.intent,
            "evidence_limit": self.evidence_limit,
            "fhir_tools": list(self.fhir_tools),
            "use_demo_evidence": self.use_demo_evidence,
            "use_approved_documents": self.use_approved_documents,
            "approved_document_source_types": list(self.approved_document_source_types),
            "use_guidelines": self.use_guidelines,
            "use_vector_search": self.use_vector_search,
        }


def plan_retrieval(message: str, quick_question_id: str | None = None) -> RetrievalPlan:
    text = _normalize(f"{message} {quick_question_id or ''}")
    tokens = set(re.findall(r"[a-z0-9]+", text))
    restrictive = _is_restrictive(text)

    if "chief concern" in text or "reason for visit" in text:
        return RetrievalPlan(
            intent="chief_concern_lookup",
            evidence_limit=1,
            use_demo_evidence=False,
            use_approved_documents=True,
            approved_document_source_types=("intake_chief_concern",),
        )

    if _mentions_demographics(text, tokens):
        return RetrievalPlan(
            intent="demographics_lookup",
            evidence_limit=2 if restrictive else 3,
            fhir_tools=("get_patient_demographics",),
            use_approved_documents=False,
        )

    if _mentions_explicit_medications(tokens) and _mentions_social_or_documents(text, tokens):
        return RetrievalPlan(
            intent="document_medication_history_lookup",
            evidence_limit=5 if restrictive else 6,
            fhir_tools=("get_recent_notes", "get_medications"),
            use_demo_evidence=False,
            approved_document_source_types=(
                "intake_medication",
                "intake_history",
                "intake_allergy",
                "intake_chief_concern",
            ),
            use_vector_search=not restrictive,
        )

    if _mentions_medications(tokens) and _mentions_allergies(tokens):
        return RetrievalPlan(
            intent="medications_allergies_lookup",
            evidence_limit=5 if restrictive else 6,
            fhir_tools=("get_patient_demographics", "get_medications", "get_allergies"),
            approved_document_source_types=("intake_medication", "intake_allergy"),
        )

    if _mentions_medications(tokens):
        return RetrievalPlan(
            intent="medications_lookup",
            evidence_limit=4 if restrictive else 5,
            fhir_tools=("get_patient_demographics", "get_medications"),
            approved_document_source_types=("intake_medication",),
        )

    if _mentions_allergies(tokens):
        return RetrievalPlan(
            intent="allergies_lookup",
            evidence_limit=4 if restrictive else 5,
            fhir_tools=("get_patient_demographics", "get_allergies"),
            approved_document_source_types=("intake_allergy",),
        )

    if _mentions_guidelines(text, tokens):
        return RetrievalPlan(
            intent="guideline_context",
            evidence_limit=8 if restrictive else 10,
            fhir_tools=("get_patient_demographics", "get_active_problems", "get_recent_labs"),
            use_guidelines=True,
            use_vector_search=not restrictive,
        )

    if _mentions_labs(tokens):
        return RetrievalPlan(
            intent="lab_lookup",
            evidence_limit=5 if restrictive else 6,
            fhir_tools=("get_recent_labs",),
            approved_document_source_types=("lab_result",),
            use_vector_search=not restrictive,
        )

    if _mentions_social_or_documents(text, tokens):
        return RetrievalPlan(
            intent="document_context_lookup",
            evidence_limit=3 if restrictive else 5,
            fhir_tools=("get_recent_notes",),
            use_demo_evidence=False,
            approved_document_source_types=("intake_history", "intake_chief_concern"),
            use_vector_search=not restrictive,
        )

    if _mentions_problems(tokens):
        return RetrievalPlan(
            intent="problems_lookup",
            evidence_limit=4 if restrictive else 5,
            fhir_tools=("get_patient_demographics", "get_active_problems"),
            use_vector_search=False,
        )

    if _mentions_broad_brief(text, tokens):
        return RetrievalPlan(
            intent="broad_brief",
            evidence_limit=8 if restrictive else 12,
            fhir_tools=(
                "get_patient_demographics",
                "get_active_problems",
                "get_recent_labs",
                "get_recent_notes",
            ),
            use_guidelines=False,
            use_vector_search=not restrictive,
        )

    return RetrievalPlan(
        intent="focused_chart_lookup",
        evidence_limit=3 if restrictive else 5,
        fhir_tools=("get_patient_demographics", "get_active_problems", "get_recent_labs"),
        use_vector_search=False,
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _is_restrictive(text: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", text))
    return any(
        phrase in text
        for phrase in [
            "nothing else",
            "and nothing else",
            "one thing",
            "single fact",
        ]
    ) or bool(tokens & {"only", "just"})


def _mentions_demographics(text: str, tokens: set[str]) -> bool:
    return bool(tokens & {"demographic", "demographics", "name", "birth", "dob", "gender", "age"}) or (
        "date of birth" in text
    )


def _mentions_labs(tokens: set[str]) -> bool:
    return bool(
        tokens
        & {
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
            "lipids",
            "ldl",
            "hdl",
            "triglyceride",
            "triglycerides",
            "glucose",
            "potassium",
            "alt",
            "ast",
            "cbc",
            "platelet",
            "platelets",
            "kidney",
        }
    )


def _mentions_medications(tokens: set[str]) -> bool:
    return bool(tokens & {"medication", "medications", "medicine", "meds", "prescription", "drug"})


def _mentions_explicit_medications(tokens: set[str]) -> bool:
    return bool(tokens & {"medication", "medications", "medicine", "meds", "prescription"})


def _mentions_allergies(tokens: set[str]) -> bool:
    return bool(tokens & {"allergy", "allergies", "intolerance"})


def _mentions_guidelines(text: str, tokens: set[str]) -> bool:
    return (
        bool(tokens & {"guideline", "guidelines", "threshold", "goal", "goals"})
        or "guideline evidence" in text
        or (
            bool(tokens & {"diabetes", "lipid", "lipids", "ldl", "hypertension"})
            and (
                "pay attention" in text
                or bool(tokens & {"abnormality", "abnormalities", "changed", "review", "summarize"})
            )
        )
    )


def _mentions_social_or_documents(text: str, tokens: set[str]) -> bool:
    return bool(
        tokens
        & {
            "note",
            "notes",
            "visit",
            "hpi",
            "assessment",
            "subjective",
            "narrative",
            "social",
            "family",
            "barrier",
            "barriers",
            "intake",
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
        }
    ) or "work shift" in text


def _mentions_problems(tokens: set[str]) -> bool:
    return bool(tokens & {"problem", "problems", "history", "condition", "diagnosis"})


def _mentions_broad_brief(text: str, tokens: set[str]) -> bool:
    return (
        "before seeing" in text
        or "pre-room" in text
        or bool(tokens & {"know", "brief", "summary", "overview"})
    )

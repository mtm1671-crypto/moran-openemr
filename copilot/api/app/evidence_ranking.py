"""Deterministic sparse search and reranking for patient evidence.

Dense vectors are useful when the wording drifts, but clinical chat still needs
plain lexical anchors: lab names, dates, units, demographics, and document fact
labels. This module keeps that final relevance pass local and PHI-contained.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models import EvidenceObject


@dataclass(frozen=True)
class RankedEvidence:
    evidence: list[EvidenceObject]
    sparse_hit_count: int

    @property
    def tools(self) -> list[str]:
        tools = ["evidence_reranker"]
        if self.sparse_hit_count:
            tools.insert(0, "sparse_evidence_search")
        return tools


_STOPWORDS = {
    "a",
    "about",
    "all",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "give",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "patient",
    "please",
    "show",
    "that",
    "the",
    "there",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "with",
}

_QUERY_EXPANSIONS = {
    "abnormal": {"abnormal", "high", "low", "flag", "flagged", "h", "l"},
    "abnormalities": {"abnormal", "high", "low", "flag", "flagged", "h", "l"},
    "barrier": {"barrier", "barriers", "transportation", "work", "shift", "cost", "afford"},
    "barriers": {"barrier", "barriers", "transportation", "work", "shift", "cost", "afford"},
    "birth": {"birth", "birthdate", "dob", "date"},
    "cholesterol": {"cholesterol", "lipid", "ldl", "hdl", "triglycerides"},
    "date": {"date", "dob", "birth"},
    "diabetes": {"diabetes", "a1c", "hemoglobin", "glucose"},
    "dob": {"dob", "birth", "birthdate", "date"},
    "kidney": {"kidney", "creatinine", "egfr"},
    "lab": {"lab", "labs", "result", "results", "observation"},
    "labs": {"lab", "labs", "result", "results", "observation"},
    "lipid": {"lipid", "cholesterol", "ldl", "hdl", "triglycerides"},
    "lipids": {"lipid", "cholesterol", "ldl", "hdl", "triglycerides"},
    "liver": {"liver", "alt", "ast"},
    "meds": {"medication", "medications", "medicine", "meds", "prescription"},
    "name": {"name", "given", "family"},
    "platelet": {"platelet", "platelets"},
    "platelets": {"platelet", "platelets"},
    "social": {"social", "barrier", "barriers", "transportation", "work", "shift"},
    "triglyceride": {"triglyceride", "triglycerides"},
    "triglycerides": {"triglyceride", "triglycerides"},
}


def sparse_search_evidence(
    *,
    message: str,
    evidence: list[EvidenceObject],
    limit: int,
) -> list[EvidenceObject]:
    """Return lexical hits without using embeddings or external services."""

    if limit <= 0:
        return []
    scored = [
        (score, index, item)
        for index, item in enumerate(evidence)
        if (score := _sparse_score(message, item)) > 0
    ]
    scored.sort(key=lambda row: (row[0], _recency_score(row[2]), -row[1]), reverse=True)
    return [item for _score, _index, item in scored[:limit]]


def rank_evidence_for_query(
    *,
    message: str,
    evidence: list[EvidenceObject],
    limit: int,
) -> RankedEvidence:
    """Rerank evidence for final model context while preserving all hard filters."""

    if limit <= 0 or not evidence:
        return RankedEvidence(evidence=[], sparse_hit_count=0)

    intents = _query_intents(message)
    scored = [
        (_rerank_score(message, item, intents), index, item)
        for index, item in enumerate(evidence)
    ]
    positive_count = sum(1 for score, _index, _item in scored if score > 0)
    if positive_count == 0:
        return RankedEvidence(evidence=evidence[:limit], sparse_hit_count=0)

    scored.sort(key=lambda row: (row[0], _recency_score(row[2]), -row[1]), reverse=True)
    return RankedEvidence(
        evidence=[item for _score, _index, item in scored[:limit]],
        sparse_hit_count=min(positive_count, limit),
    )


def _rerank_score(message: str, item: EvidenceObject, intents: set[str]) -> float:
    score = _sparse_score(message, item)
    source_type = item.source_type
    field = str(item.metadata.get("field") or "").lower()
    text = _evidence_text(item)

    if "demographics" in intents:
        if source_type == "patient_demographics":
            score += 120
        if "name" in text and ("name" in intents or field == "name"):
            score += 30
        if field == "birthdate" or "birth date" in text or "dob" in intents:
            score += 30
        if field == "gender":
            score += 15

    if "labs" in intents and source_type == "lab_result":
        score += 40
        if "abnormal" in intents and _looks_abnormal(item):
            score += 35

    if "documents" in intents and _is_document_context(item):
        score += 45

    if "problems" in intents and source_type == "active_problem":
        score += 35
    if "medications" in intents and source_type in {"medication", "intake_medication"}:
        score += 35
    if "allergies" in intents and source_type in {"allergy", "intake_allergy"}:
        score += 35

    if item.metadata.get("schema") == "w2_document_fact_v1":
        score += 8
        if score > 8:
            score += 18

    score += min(_recency_score(item), 10)
    return score


def _sparse_score(message: str, item: EvidenceObject) -> float:
    query_tokens = _expanded_tokens(message)
    if not query_tokens:
        return 0
    display_tokens = _expanded_tokens(item.display_name)
    fact_tokens = _expanded_tokens(item.fact)
    metadata_tokens = _expanded_tokens(_metadata_text(item.metadata))
    source_tokens = _expanded_tokens(item.source_type)

    score = 0.0
    score += 4 * len(query_tokens & display_tokens)
    score += 2 * len(query_tokens & fact_tokens)
    score += len(query_tokens & metadata_tokens)
    score += len(query_tokens & source_tokens)

    lowered = f"{item.display_name} {item.fact}".lower()
    for phrase in _important_phrases(message):
        if phrase in lowered:
            score += 8
    return score


def _query_intents(message: str) -> set[str]:
    text = message.lower()
    tokens = _expanded_tokens(message)
    intents: set[str] = set()

    if tokens & {"name", "birth", "birthdate", "dob", "gender", "demographic", "demographics", "age"}:
        intents.add("demographics")
    if tokens & {
        "lab",
        "labs",
        "result",
        "results",
        "abnormal",
        "abnormalities",
        "a1c",
        "hemoglobin",
        "cholesterol",
        "lipid",
        "ldl",
        "hdl",
        "triglycerides",
        "creatinine",
        "egfr",
        "glucose",
        "potassium",
        "alt",
        "ast",
        "platelets",
        "wbc",
        "rbc",
    }:
        intents.add("labs")
    if tokens & {"problem", "problems", "history", "condition", "diagnosis"}:
        intents.add("problems")
    if tokens & {"medication", "medications", "medicine", "meds", "prescription"}:
        intents.add("medications")
    if tokens & {"allergy", "allergies", "intolerance"}:
        intents.add("allergies")
    if tokens & {
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
        "transportation",
        "work",
        "shift",
    }:
        intents.add("documents")
    if "before seeing" in text or "pre-room" in text or "brief" in tokens or "overview" in tokens:
        intents.update({"demographics", "problems", "labs", "documents"})
    if tokens & {"abnormal", "abnormalities", "high", "low", "flagged"}:
        intents.add("abnormal")
    return intents


def _expanded_tokens(text: str) -> set[str]:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token and token not in _STOPWORDS
    }
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_QUERY_EXPANSIONS.get(token, set()))
    return expanded


def _important_phrases(message: str) -> list[str]:
    text = re.sub(r"\s+", " ", message.lower()).strip()
    phrases = []
    for phrase in [
        "date of birth",
        "birth date",
        "patient name",
        "social barriers",
        "lab report",
        "kidney function",
        "liver enzymes",
    ]:
        if phrase in text:
            phrases.append(phrase)
    return phrases


def _evidence_text(item: EvidenceObject) -> str:
    return " ".join(
        [
            item.source_type,
            item.display_name,
            item.fact,
            _metadata_text(item.metadata),
        ]
    ).lower()


def _metadata_text(metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in metadata.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, bool):
            parts.append(str(value).lower())
        elif isinstance(value, (int, float)):
            parts.append(str(value))
        elif isinstance(value, dict):
            parts.append(_metadata_text(value))
        elif isinstance(value, list):
            parts.extend(str(item) for item in value if isinstance(item, (str, int, float, bool)))
    return " ".join(parts)


def _is_document_context(item: EvidenceObject) -> bool:
    return (
        item.source_type == "clinical_note"
        or item.source_type.startswith("intake_")
        or item.metadata.get("schema") == "w2_document_fact_v1"
    )


def _looks_abnormal(item: EvidenceObject) -> bool:
    if item.metadata.get("abnormal") is True:
        return True
    text = f"{item.fact} {item.metadata.get('interpretation') or ''}".lower()
    return any(token in text for token in ["abnormal", " high", "(high", " low", "(low", " h.", " l."])


def _recency_score(item: EvidenceObject) -> float:
    value = item.effective_at or item.source_updated_at or item.retrieved_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    days = max((datetime.now(tz=UTC) - value).days, 0)
    return max(0.0, 10.0 - min(days / 30.0, 10.0))
